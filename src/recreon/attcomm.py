"""Attack commands.

Port of ATTCOMM.PAS -- both halves. The unit has two entry points and they
differ only in who steers:

* ``AutoAttackCommand`` picks a target, confirms, and hands the whole fight to
  ``attnpe.npe_attack``, which decides movement, targeting and retreat itself.
  Despite the name that routine consults no AI persona, so it resolves a
  player's attack too.
* ``AttackCommand`` is the round-by-round version. The player splits the fleet
  into groups, and each round chooses whether to engage, walk groups between
  orbital shells, retarget them, or break off. The mechanics underneath are
  the same ``attack.battle`` / ``attack.advance_groups`` /
  ``attack.enemy_surrenders`` that the automatic version drives; what changes
  is the hand on them.

The interactive half is a state machine here rather than a loop, because the
original's ``REPEAT Menu(Comm) ... UNTIL EndBattle`` blocks on the keyboard and
Textual cannot. :class:`GroupSplitter` is ``GetGroups``, :class:`BattleSession`
is ``Engage`` plus the ``CleanUp`` that follows it, and ``ui/attack.py`` drives
both. The screen effects -- ``WarpIn``, ``WarpOut``, ``GroupsDestroyedSFX``,
``DrawScreen`` -- are direct writes to video memory and have no counterpart;
what they *said* survives as :attr:`BattleSession.report`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from .attack import (
    MAX_NO_OF_GROUPS,
    AttackIntentionTypes,
    AttackResultTypes,
    GroupRecord,
    GroupStatus,
    advance_groups,
    all_groups_destroyed,
    attack_array,
    battle,
    calculate_combat_data,
    default_distribution,
    destroy_construction_or_gate,
    detail_array,
    enemy_surrenders,
    forces_unknown,
    get_enemy,
    group_array,
    resolve_attack,
    restore_combatant,
)
from .attnpe import npe_attack
from .datacnst import CargoSpace, ObjName, TechDev, ThingNames, TrnAdj
from .environ import GameEnvironment
from .misc import no_ships, thg_lmt
from .primintr import (
    empire_active,
    empire_name,
    empress,
    get_cargo,
    get_coord,
    get_fleets,
    get_object,
    get_rev_index,
    get_ships,
    get_status,
    get_tech,
    get_type,
    my_lord,
    object_name,
    scouted,
)
from .scena import display_background
from .types import (
    ATTACK_TYPES,
    SHIP_TYPES,
    Empire,
    IDNumber,
    ObjectTypes,
    ShellPos,
    TechnologyTypes,
    WorldTypes,
    tech_range,
)
from .utils.int_utils import lesser_int, rnd
from .utils.pascal import pascal_round

T = TechnologyTypes

#: What can be attacked at all. Worlds, bases and fleets fight back; sites and
#: gates are simply razed by `npe_attack`.
TARGETABLE = (
    ObjectTypes.Pln,
    ObjectTypes.Base,
    ObjectTypes.Flt,
    ObjectTypes.Con,
    ObjectTypes.Gate,
)

#: Fights that resolve as a battle rather than a demolition.
FIGHTS_BACK = (ObjectTypes.Pln, ObjectTypes.Base, ObjectTypes.Flt)


# --- The battle display's own vocabulary --------------------------------------
#
# Three tables local to ATTCOMM.PAS. They are not in DATACNST and have no other
# caller, so they live here rather than with the balance tables.

#: One letter per attack type, which is how the player types a target. The
#: first is ``NoRes`` -- "no orders", not a thing that can be shot at.
ATSymb: dict[T, str] = dict(zip(ATTACK_TYPES, "-LDGIFHJTPSRMN", strict=True))

#: Six-column abbreviations for a group's type. Everything below ``fgt`` is
#: blank because no group is ever made of defenses. ``men`` reads ``GAT`` --
#: ground assault troops -- because by the time a group *is* ``men`` it has
#: landed.
TypN: dict[T, str] = dict(
    zip(
        ATTACK_TYPES,
        (
            "", "", "", "", "",
            "fgt sq", "hk    ", "jmpshp", "jmptrn",
            "pentr ", "strshp", "trnspt", "GAT   ", "ninja ",
        ),
        strict=True,
    )
)

#: Three-column abbreviations for the orbital shells.
PosN: dict[ShellPos, str] = dict(
    zip(ShellPos, ("DSp", "Hi ", "Std", "Sub", "Sur"), strict=True)
)

#: What ``GroupTarget`` will accept: any attack type's letter, plus ``-`` for
#: no orders. Ported as the set of types rather than the set of characters,
#: since the original only uses the characters to look the type back up.
TARGETTABLE = ATTACK_TYPES


# --- Splitting the fleet into groups (GetGroups) ------------------------------


class GroupSplitter:
    """The custom battle configuration screen. Port of ``GetGroups``.

    The player walks a fixed list of nine slots, picks a ship type for the
    selected slot, and moves ships into it out of a shared pool. The pool is
    the fleet's own manifest, so what is not assigned simply does not fight.

    Two things about the original are worth knowing before reading the methods:

    * **Changing a slot's type empties it back into the pool.** ``LoadShips``
      returns the slot's ships *and any troops it was carrying* before it will
      accept the new type. There is no way to have a slot hold two types.
    * **Loading ships always dumps the troops.** The second ``IF GAT>0`` in
      ``LoadShips`` runs unconditionally after the transfer, so adding one
      transport to a loaded group unloads every soldier aboard. The player has
      to press M or N again. That is faithful, not a slip.

    ``Exit`` is a ``VAR`` parameter the original assigns ``False`` and never
    anything else -- there is no way to abandon this screen once entered, only
    to leave it with whatever groups have been built. Escape ends the editing
    loop; it does not cancel the attack.
    """

    def __init__(self, game: GameEnvironment, flt_id: IDNumber) -> None:
        self.sh = get_ships(game, flt_id)
        self.cr = get_cargo(game, flt_id)
        self.gp = group_array()
        #: The slot the player is on, 1..MAX_NO_OF_GROUPS.
        self.cg = 1
        #: The type the *pool* cursor is on, which is not the selected slot's
        #: type until ships are actually moved.
        self.cur_typ: T = T.fgt

        for i in range(1, MAX_NO_OF_GROUPS + 1):
            self.gp[i].Typ = self.cur_typ

    # --- Moving the cursor ----------------------------------------------------

    def select(self, group: int) -> None:
        """Put the cursor on a slot, adopting that slot's ship type."""
        if not 1 <= group <= MAX_NO_OF_GROUPS:
            return
        self.cg = group
        self.cur_typ = self.gp[group].Typ

    def change_type(self, forward: bool) -> None:
        """Step the type cursor, wrapping ``trn`` round to ``fgt``.

        ``ChangeGroupType`` moves only the cursor. The selected slot keeps its
        own type until :meth:`load_ships` commits the change.
        """
        if forward:
            self.cur_typ = T.fgt if self.cur_typ == T.trn else T(int(self.cur_typ) + 1)
        else:
            self.cur_typ = T.trn if self.cur_typ == T.fgt else T(int(self.cur_typ) - 1)

    # --- Moving ships ---------------------------------------------------------

    def load_ships(self, trans: int) -> None:
        """Move ``trans`` ships between the pool and the selected slot.

        A negative count takes ships back out. Either way the count is clamped
        to what is actually there, and the cursor then falls to the next slot
        -- which is what makes the screen usable with nothing but the space bar.
        """
        group = self.gp[self.cg]

        if group.Typ != self.cur_typ:
            if group.Num > 0:
                self.sh[group.Typ] += group.Num
                group.Num = 0
                if group.GAT > 0:
                    self.cr[group.GATTyp] += group.GAT
                    group.GAT = 0
            group.Typ = self.cur_typ

        if trans > 0:
            trans = lesser_int(trans, self.sh[group.Typ])
        else:
            trans = -lesser_int(-trans, group.Num)

        self.sh[group.Typ] -= trans
        group.Num += trans

        # Unconditional: any change to the ship count spills the troops.
        if group.GAT > 0:
            self.cr[group.GATTyp] += group.GAT
            group.GAT = 0

        if self.cg < MAX_NO_OF_GROUPS:
            self.cg += 1

    def add_to_group(self, amount: int | None) -> None:
        """``ChangeGroupNumber``: the typed count. ``None`` means "all of it".

        The "all" case reads the *slot's* current type, not the cursor's, which
        matters when the two have diverged: typing Return on a slot holding
        fighters takes every fighter even if the cursor is on transports.
        """
        trans = self.sh[self.gp[self.cg].Typ] if amount is None else amount
        if trans != 0:
            self.load_ships(trans)

    def load_all_of_type(self) -> None:
        """The space bar: every ship of the cursor's type, into this slot."""
        self.load_ships(self.sh[self.cur_typ])

    def load_transports(self, ninja: bool) -> None:
        """``LoadTransports``: fill the slot's carrying capacity with troops.

        Nothing checks that the slot actually holds transports. Loading troops
        onto fighters is allowed and does nothing, because ``TrnAdj`` is 0 for
        every hull that is not a transport or a jump transport.
        """
        group = self.gp[self.cg]
        to_load = T.nnj if ninja else T.men

        if group.GAT > 0:
            self.cr[group.GATTyp] += group.GAT

        group.GAT = lesser_int(
            self.cr[to_load],
            thg_lmt(pascal_round(TrnAdj[group.Typ] * group.Num * CargoSpace[to_load])),
        )
        group.GATTyp = to_load
        self.cr[to_load] -= group.GAT

    # --- Reading the screen ---------------------------------------------------

    def group_line(self, i: int) -> str:
        """One slot as ``UpdateGroupDisplay`` writes it."""
        group = self.gp[i]
        # The original uppercases character 10 of the line, which for a
        # single-digit slot number is the first letter of the ship name.
        name = ThingNames[group.Typ]
        line = f"{i}: {group.Num:4}  {name[:1].upper()}{name[1:]}"
        line = f"{line:<30}"
        if group.GAT > 0:
            line += f"({group.GAT} {ThingNames[group.GATTyp]})"
        return line

    def pool_line(self) -> str:
        """The remaining manifest, as the header row over the slots."""
        ships = "".join(f"{self.sh[thing]:5}" for thing in SHIP_TYPES)
        troops = "".join(f"{self.cr[thing]:5}" for thing in (T.men, T.nnj))
        return f"{ships}          {troops}"

    # --- Handing over to the battle -------------------------------------------

    def finish(self) -> tuple[int, list[GroupRecord | None]]:
        """Compact the slots into the array the battle actually runs on.

        Warships are renumbered first and transports last, which is the
        invariant the whole of ATTNPE leans on -- "the transports" is a suffix
        of the array, never an interleaving.

        Any transport slot the player left empty of troops is then filled
        automatically, **preferring ordinary soldiers over ninjas**. That is
        the opposite of ``DefaultDistribution``, which prefers ninjas because
        they are worth five men each. Both are the original; nothing reconciles
        them.
        """
        out = group_array()
        n = 0

        for transports in (False, True):
            for i in range(1, MAX_NO_OF_GROUPS + 1):
                group = self.gp[i]
                is_transport = group.Typ in (T.trn, T.jtn)
                if group.Num > 0 and is_transport == transports:
                    n += 1
                    out[n] = replace(group)

        for i in range(1, n + 1):
            group = out[i]
            if group.Typ not in (T.trn, T.jtn) or group.GAT != 0:
                continue
            for troop in (T.men, T.nnj):
                if self.cr[troop] > 0:
                    trans = lesser_int(
                        self.cr[troop],
                        pascal_round(
                            CargoSpace[troop] * TrnAdj[group.Typ] * group.Num
                        ),
                    )
                    group.GAT = trans
                    group.GATTyp = troop
                    self.cr[troop] -= trans
                    break

        return n, out


def attack_targets(
    game: GameEnvironment, player: Empire, flt_id: IDNumber
) -> list[tuple[IDNumber, str]]:
    """What the fleet may attack in its own sector. Port of ``GetTarget``.

    **A world cannot be targeted while an enemy fleet is in the sector.** The
    original adds the object under the fleet only ``IF ListSize=0`` -- after
    finding no enemy fleets -- so a fleet in orbit screens the world beneath
    it, and has to be destroyed first. That is a real mechanic and not a
    display quirk.

    Enemy fleets must have been **scouted** to be offered; the object beneath
    gets no such test, because you can see what a world is without scouting
    what is on it.
    """
    xy = get_coord(game, flt_id)
    found: list[tuple[IDNumber, str]] = []

    for index in sorted(get_fleets(game, xy)):
        other = IDNumber(ObjectTypes.Flt, index)
        status = get_status(game, other)
        if status != player and scouted(game, player, other):
            found.append((other, _label(game, player, other, status)))

    if not found:
        obj = get_object(game, xy)
        status = get_status(game, obj)
        if obj.ObjTyp in TARGETABLE and status != player:
            found.append((obj, _label(game, player, obj, status)))

    return found


def _label(
    game: GameEnvironment, player: Empire, obj: IDNumber, emp: Empire
) -> str:
    name = object_name(game, player, obj, long_format=True)
    return f"{name}  ({empire_name(game, emp) or emp.name})"


# --- The round-by-round battle (Engage) ---------------------------------------


@dataclass(slots=True)
class MoveOption:
    """One group's legal manoeuvres this round, for the ``M`` screen."""

    group: int
    can_advance: bool
    can_retreat: bool


@dataclass(slots=True)
class CaptureQuestion:
    """The beaten fleet's ships, and what its commander has to say.

    Answering *yes* to "destroy the enemy fleet" sets ``Capture := False``, so
    the polite answer is the greedy one.
    """

    ships: dict[T, int]
    lines: list[str]


@dataclass(slots=True)
class BattleReport:
    """Everything ``CleanUp`` has to say, in the order it says it."""

    result: AttackResultTypes
    lines: list[str] = field(default_factory=list)
    #: Obsolete hulls found in orbit over a conquered independent world.
    old_ships: dict[T, int] = field(default_factory=dict)
    #: Set when the player still has to decide whether to spare an enemy fleet.
    capture_question: CaptureQuestion | None = None
    #: Worlds inherited by conquering a capital, filled in by ``settle``.
    spoils: set[int] = field(default_factory=set)


class BattleSession:
    """One interactive engagement, held open between the player's decisions.

    The original is a blocking ``REPEAT Menu(Comm) ... UNTIL EndBattle`` loop.
    Nothing in Textual can block, so the loop is inverted: the caller asks what
    is legal, applies a decision, and reads :attr:`end_battle` to know when the
    fight is over. The mechanics called in between are exactly the ones
    ``attnpe`` calls.

    **Two values the original never initialises.** ``Result`` is a local of
    ``AttackCommand`` passed straight into ``Engage`` as a ``VAR`` parameter
    and read -- ``ELSE IF Result<>AttRetreatsART`` -- before anything assigns
    it, so on the first round the surrender check hangs off whatever was on the
    stack (#69). ``Capture`` is the same shape: ``CleanUp`` only assigns it via
    ``AskToCapture``, which is skipped when the beaten fleet has no ships left,
    and then passes it to ``ResolveAttack`` anyway (#70). Here they take their
    defined readings, ``NoART`` and *capture*.
    """

    def __init__(
        self,
        game: GameEnvironment,
        player: Empire,
        flt_id: IDNumber,
        target: IDNumber,
        no_of_groups: int,
        gp: list[GroupRecord | None],
    ) -> None:
        self.game = game
        self.player = player
        self.flt_id = flt_id
        self.target = target
        self.no_of_groups = no_of_groups
        self.gp = gp

        self.hk_surprise = forces_unknown(game, flt_id, target)
        self.combat_data = calculate_combat_data(game, player, flt_id, target)
        self.en = get_enemy(game, target)

        self.killed = attack_array()
        self.casualties = attack_array()
        self.details = detail_array()
        self.result = AttackResultTypes.NoART
        self.end_battle = False
        #: What ``AttReport`` would have flashed across the battle display.
        self.report: list[str] = []

    # --- <E>ngage -------------------------------------------------------------

    def engage(self) -> None:
        """Fight one full round: all five shells, outermost first.

        ``Details`` is cleared per round, so the ``D`` screen shows what the
        *last* round cost and not a running total; ``Casualties`` and ``Killed``
        do accumulate, because they are what gets written back to the two
        fleets at the end.
        """
        self.details = detail_array()
        for pos in ShellPos:
            destroyed = battle(
                self.no_of_groups,
                self.gp,
                self.en,
                pos,
                self.combat_data,
                self.details,
                self.casualties,
                self.killed,
            )
            for i in sorted(destroyed):
                self.report.append(f"Group {i:2} destroyed.")

        advance_groups(self.no_of_groups, self.gp)

        if all_groups_destroyed(self.no_of_groups, self.gp):
            self.report.append("ALL GROUPS DESTROYED")
            self.end_battle = True
            self.result = AttackResultTypes.AttDestroyedART
        elif self.result != AttackResultTypes.AttRetreatsART and enemy_surrenders(
            self.no_of_groups,
            self.gp,
            self.en,
            self.casualties,
            self.killed,
            self.combat_data,
        ):
            self.report.append("THE ENEMY HAS SURRENDERED")
            self.end_battle = True
            self.result = AttackResultTypes.DefConqueredART

    # --- <M>ove ---------------------------------------------------------------

    def move_options(self) -> list[MoveOption]:
        """Which groups may move, and which way. Port of ``GroupMove``'s tests.

        Three rules, and each of them is a real constraint on how a fight goes:

        * Nothing advances off the ground, and **against a fleet nothing goes
          below standard orbit** -- there is no surface to assault.
        * Only fighters, transports and jump transports can drop from sub-orbit
          to the ground. Starships and penetrators stay in space.
        * Nothing retreats out of deep space, and once troops are down only
          fighters can lift off again. Landing is close to a commitment.

        A group that can do neither is not offered at all, which is also how
        the original skips it.
        """
        options: list[MoveOption] = []
        for i in range(1, self.no_of_groups + 1):
            group = self.gp[i]
            if group.Sta == GroupStatus.GDst:
                continue

            advance = (
                group.Pos != ShellPos.Grnd
                and (
                    self.combat_data.DTyp != ObjectTypes.Flt
                    or group.Pos != ShellPos.Orbit
                )
                and (group.Pos != ShellPos.SbOrb or group.Typ in (T.fgt, T.trn, T.jtn))
            )
            retreat = not (
                (group.Pos == ShellPos.Grnd and group.Typ != T.fgt)
                or group.Pos == ShellPos.DpSpc
            )

            if advance or retreat:
                options.append(MoveOption(i, advance, retreat))
        return options

    def set_moves(self, orders: dict[int, GroupStatus]) -> bool:
        """Stage a manoeuvre. Returns whether anything is actually moving.

        A round in which every group stays put costs nothing -- ``Ok`` stays
        false, the original cancels out and never calls ``GroupEngage``. So
        "stand fast" is free, and only ordering someone to move buys the enemy
        a round of fire.
        """
        moving = False
        for i, status in orders.items():
            group = self.gp[i]
            if status in (GroupStatus.GAdvc, GroupStatus.GRtrt):
                group.Sta = status
                moving = True
            else:
                group.Sta = GroupStatus.GReady
        return moving

    def cancel_moves(self) -> None:
        """``CancelAdvance``: put every staged group back to ready."""
        for i in range(1, self.no_of_groups + 1):
            group = self.gp[i]
            if group.Sta in (GroupStatus.GAdvc, GroupStatus.GRtrt):
                group.Sta = GroupStatus.GReady

    # --- <T>arget -------------------------------------------------------------

    def target_options(self) -> list[int]:
        """The groups that can be retargeted, i.e. the ones still alive."""
        return [
            i
            for i in range(1, self.no_of_groups + 1)
            if self.gp[i].Sta != GroupStatus.GDst
        ]

    def set_targets(self, targets: dict[int, T]) -> None:
        """Point groups at what the player wants dead.

        Unlike the automatic version there is no priority calculation and no
        check that the target is in range: a group ordered to shoot at
        something that is not at its shell simply wastes the round.
        """
        for i, trg in targets.items():
            if self.gp[i].Sta != GroupStatus.GDst:
                self.gp[i].Trg = trg

    # --- <R>etreat ------------------------------------------------------------

    def retreat(self) -> None:
        """Break off. Costs one more round of fire on the way out.

        The retreat is declared *before* the round is fought, which is what
        suppresses the surrender check inside :meth:`engage` -- a fleet leaving
        does not get to accept a surrender on its way past. It can still be
        wiped out in that round, and then the result is destruction, not
        retreat.
        """
        self.report.append("ALL GROUPS RETREATING")
        self.result = AttackResultTypes.AttRetreatsART
        self.engage()
        self.end_battle = True

    # --- <G>roup status and <D>etails ----------------------------------------

    def group_lines(self) -> list[str]:
        """The group roster, as ``GroupStatus`` writes it.

        A transport group shows the troops it is carrying; an undetected
        hunter-killer shows ``Clk``, which is the only place the cloak is
        visible to the player.
        """
        lines: list[str] = []
        for i in range(1, self.no_of_groups + 1):
            group = self.gp[i]
            line = (
                f"{i:2}: {group.Num:4} {TypN[group.Typ]} "
                f"O:{PosN[group.Pos]} ({ATSymb[group.Trg]}) "
            )
            if group.Sta == GroupStatus.GDst:
                line += "Dst"
            elif group.Typ in (T.trn, T.jtn):
                line += f"{group.GAT:4}"
            elif group.Typ == T.hkr and not group.Flg:
                line += "Clk"
            lines.append(line.rstrip())
        return lines

    def detail_rows(self) -> list[tuple[str, list[int]]]:
        """What each enemy weapon destroyed, per group, in the last round.

        Slot 0 of a ``DetailArray`` row is not a group but the flag saying this
        weapon hit something, which is what selects the rows worth printing.
        """
        return [
            (ThingNames[thing], self.details[thing][1 : self.no_of_groups + 1])
            for thing in tech_range(T.LAM, T.nnj)
            if self.details[thing][0] != 0
        ]

    # --- CleanUp --------------------------------------------------------------

    def conclude(self) -> BattleReport:
        """Write the losses back and say what happened. First half of ``CleanUp``.

        Both combatants are restored before any of the messages are built, so
        the narrative reads the survivors -- which is how ``AskToCapture`` knows
        what it is offering and ``OldShipsFound`` knows what is left in orbit.
        Ownership has *not* changed yet: :meth:`settle` does that, and the
        messages here still see the old owner.
        """
        restore_combatant(self.game, self.flt_id, self.casualties)
        restore_combatant(self.game, self.target, self.killed)

        report = BattleReport(result=self.result)

        if self.result == AttackResultTypes.AttDestroyedART:
            report.lines = _battle_lost(self.game, self.player, self.target)
        elif self.result == AttackResultTypes.AttRetreatsART:
            report.lines = [
                f"The attacking force has retreated, {my_lord(self.game, self.player)}."
            ]
        elif self.result == AttackResultTypes.DefConqueredART:
            report.old_ships = _old_ships_found(self.game, self.target)
            report.capture_question = _ask_to_capture(
                self.game, self.player, self.target
            )
            report.lines = _enemy_conquered(
                self.game, self.player, self.flt_id, self.target
            )

        return report

    def settle(self, report: BattleReport, capture: bool = True) -> BattleReport:
        """Apply the outcome. Second half of ``CleanUp``.

        ``capture`` only ever matters against a fleet -- ``resolve_attack``
        ignores it for a world -- and decides whether the survivors are pressed
        into the attacking fleet or destroyed with it.
        """
        report.spoils = resolve_attack(
            self.game,
            self.result,
            self.flt_id,
            self.target,
            self.hk_surprise,
            capture,
            self.casualties,
            self.killed,
        )
        return report


# --- CleanUp's messages -------------------------------------------------------


def _battle_lost(
    game: GameEnvironment, player: Empire, target: IDNumber
) -> list[str]:
    """What the staff say when the whole attack force dies. ``BattleLost``.

    Four speeches, and the odds depend on who you lost to. Against an empire it
    is an even draw between all four; against independents the two that talk
    about *reputation* are crowded out ten-to-two by the generic scolding,
    because losing to nobody is embarrassing rather than dangerous.
    """
    lord = my_lord(game, player)

    def message1() -> list[str]:
        # Names the player's most restive world, if it is restive enough.
        lines = [
            f"I'm sorry, {lord}, the entire attack force has been destroyed.",
            "I hope I do not have to remind you about the repercussion that this",
            "loss will have.  Cetain factions within the Empire are already counting",
            "on fear to incite rebellion.",
        ]
        max_rev = 0
        worst: IDNumber | None = None
        for i in sorted(game.GlobalSets.SetOfPlanetsOf[player]):
            obj = IDNumber(ObjectTypes.Pln, i)
            if get_rev_index(game, obj) > max_rev:
                worst = obj
                max_rev = get_rev_index(game, obj)

        world = object_name(game, player, worst) if worst is not None else ""
        if max_rev > 20 and world:
            lines += [
                f"Do not forget that {world} is quickly growing doubtful of "
                "the Empire's",
                "ability to defend itself.",
            ]
        return lines

    def message2() -> list[str]:
        return [
            f"{lord}, I'm sorry to report that the entire attack force was lost",
            "in the battle.  At the risk of offending Your Highness, I would like to",
            "point out that an option to retreat was open at all times.  Although",
            "sacrifice is something that all your troops know, it is often best to",
            "allow them the luxury of living to fight another day.",
        ]

    def message3() -> list[str]:
        # Names some other active empire. The original's REPEAT..UNTIL only
        # terminates because this branch is unreachable when the defender was
        # independent, so there is always at least one other empire alive.
        while True:
            emp = Empire(rnd(int(Empire.Empire1), int(Empire.Empire8)))
            if emp != player and empire_active(game, emp):
                break
        return [
            f"{lord}, the entire attack force was destroyed in battle.",
            "Although I certainly do not question the orders and decision of Your",
            "Highness, I should like to mention that this defeat will not go",
            f"unnoticed in the Galaxy.  Already {empire_name(game, emp)} is starting to",
            "believe that this Empire would not be an overly costly target.",
        ]

    def message4() -> list[str]:
        tail = {
            1: "You must be careful, Your Highness, or greater battles will be lost.",
            2: "Do not think that this defeat will go unnoticed in the Galaxy.",
            3: "You must be careful, other star systems grow suspicious of your "
            "defenses.",
        }[rnd(1, 3)]
        return [
            f"{lord}, the attack force has been totally destroyed by the enemy.",
            tail,
        ]

    if get_status(game, target) == Empire.Indep:
        choice = rnd(1, 12)
        if choice == 1:
            return message1()
        if choice == 2:
            return message2()
        return message4()

    choice = rnd(1, 4)
    return {1: message1, 2: message2, 3: message3, 4: message4}[choice]()


def _ask_to_capture(
    game: GameEnvironment, player: Empire, target: IDNumber
) -> CaptureQuestion | None:
    """The offer to spare a beaten fleet. Port of ``AskToCapture``.

    Only a fleet with ships left is worth asking about. The enemy commander's
    line is drawn at random and is pure flavour -- it does not change what
    either answer does.
    """
    if target.ObjTyp != ObjectTypes.Flt:
        return None

    ships = get_ships(game, target)
    if no_ships(ships):
        return None

    lord = my_lord(game, player)
    plea = {
        1: [
            "The commander of the enemy fleet begs Your Majesty to spare his life.",
        ],
        2: [
            f'Message from enemy commander: "...{lord}, please allow me the honor',
            'of death in battle.  Destroy this fleet..."',
        ],
        3: [
            "Death in space is the only honorable way for a vanquished enemy.",
        ],
    }[rnd(1, 3)]

    return CaptureQuestion(
        ships={thing: ships[thing] for thing in SHIP_TYPES if ships[thing] > 0},
        lines=plea,
    )


def _enemy_conquered(
    game: GameEnvironment, player: Empire, flt_id: IDNumber, target: IDNumber
) -> list[str]:
    """The victory speech. Port of ``EnemyConquered``'s message half.

    **A scenario's own words come first.** ``DisplayBackground`` is asked for
    an ``A:`` entry covering this world, and anything it finds replaces the
    speech entirely -- seven of the thirteen shipped scenarios carry such an
    index, so in those this is the usual outcome rather than the exception.

    Two details of that call are load-bearing. It is made with ``DummyEmp``,
    which is ``Indep`` and not the conquering player, so any ``[N…]`` in the
    authored text renders the world's name as an outsider would see it. And
    **it happens before `ResolveAttack`**, so the world still belongs to the
    defender -- which is what lets `JAKARTA.SCN` write ``A:8`` and mean
    "when an independent world is taken".

    Failing that: taking a *capital* always gets the formal declaration, and
    anything else draws one of three. The draw sits inside the original's
    ``IF NOT Message``, so **a scenario that supplies text also spends no
    randomness** -- neither the `Rnd(1,3)` nor the `MyLord` calls beneath it.
    Keeping that shape keeps the generator in step.
    """
    background = display_background(game, Empire.Indep, target, conquer=True)
    if background:
        return background

    emp_n = empire_name(game, player)
    declaration = (
        f"In the name of Her Imperial Majesty, Lady of {emp_n}, I hereby declare"
        if empress(game, player)
        else f"In the name of His Imperial Majesty, Lord of {emp_n}, I hereby declare"
    )

    def message1() -> list[str]:
        return [
            declaration,
            f"this {ObjName[target.ObjTyp]} to be under the sovereign "
            "jurisdiction of the",
            f"{emp_n} Empire.",
        ]

    if get_type(game, target) == WorldTypes.CapTyp:
        return message1()

    choice = rnd(1, 3)
    if choice == 1:
        return message1()

    lord = my_lord(game, player)
    if choice == 2:
        target_n = object_name(game, player, target, long_format=True)
        flt_n = object_name(game, player, flt_id, long_format=True)
        return [
            f"Congratulations {lord}, {flt_n} has succeeded in its attack against",
            f"{target_n}.  No doubt some of your enemies will in the future ",
            "be more careful when challenging this empire.",
        ]

    return [
        f"Congratulations on your victory, {lord}, but remember that not",
        "all battles will be this easy.",
    ]


def _old_ships_found(game: GameEnvironment, target: IDNumber) -> dict[T, int]:
    """Obsolete hulls inherited with an independent world. ``OldShipsFound``.

    An independent can be sitting on ships its own tech level could never have
    built -- left over from whoever held the world before it went its own way.
    The report exists because those are a windfall the player would otherwise
    miss.
    """
    if target.ObjTyp != ObjectTypes.Pln or get_status(game, target) != Empire.Indep:
        return {}

    ships = get_ships(game, target)
    tech = get_tech(game, target)
    return {
        thing: ships[thing]
        for thing in SHIP_TYPES
        if thing not in TechDev[tech] and ships[thing] > 0
    }


def attack_command(
    game: GameEnvironment,
    player: Empire,
    flt_id: IDNumber,
    target: IDNumber,
    groups: tuple[int, list[GroupRecord | None]] | None = None,
) -> BattleSession | None:
    """Open an interactive engagement. Port of ``AttackCommand``'s setup.

    ``groups`` is what :meth:`GroupSplitter.finish` returned, or ``None`` for
    the standard distribution -- the "Standard battle configuration (Y/n)"
    question. A fleet that ends up with no groups at all cannot attack, and the
    original quietly does nothing; so does this, returning ``None``.

    Construction sites and stargates are not battles and never reach here: see
    :func:`raze_command`.
    """
    if target.ObjTyp not in FIGHTS_BACK:
        return None

    no_of_groups, gp = groups if groups is not None else default_distribution(
        game, flt_id
    )
    if no_of_groups == 0:
        return None

    return BattleSession(game, player, flt_id, target, no_of_groups, gp)


def raze_command(
    game: GameEnvironment, player: Empire, flt_id: IDNumber, target: IDNumber
) -> list[str]:
    """Destroy a construction site or stargate. Port of ``TakeOverConOrGate``.

    No battle: a half-built hull and a warp gate have nothing to shoot with.
    Both the interactive and auto-attack commands use this path so that the
    target is removed and its owner receives the corresponding consequences.
    """
    name = object_name(game, player, target, long_format=True)
    hk_surprise = forces_unknown(game, flt_id, target)
    destroy_construction_or_gate(game, player, hk_surprise, target)
    return [f"{name} has been destroyed."]


@dataclass(slots=True)
class AttackOutcome:
    """What the auto-attack has to report afterwards."""

    result: AttackResultTypes
    #: Ships lost, by type -- only the types that took losses.
    casualties: dict[T, int] = field(default_factory=dict)
    #: Worlds taken as spoils, by planet index.
    spoils: set[int] = field(default_factory=set)
    lines: list[str] = field(default_factory=list)


def result_message(
    game: GameEnvironment,
    player: Empire,
    target: IDNumber,
    result: AttackResultTypes,
) -> list[str]:
    """What the staff say about the outcome. Port of ``ResultMessage``.

    A destroyed attack force draws one of two consolations at random, which is
    a draw from the generator in a message -- the same class of thing as
    ``my_lord``. A conquest is announced in the ruler's name, and the wording
    differs for an empress.
    """
    lord = my_lord(game, player)

    if result == AttackResultTypes.AttDestroyedART:
        excuse = (
            "Perhaps if you had been there to direct the attack..."
            if rnd(1, 2) == 1
            else "The fleet commander fought bravely and did not surrender."
        )
        return [
            f"I'm sorry, {lord}, the entire attack force has been destroyed.",
            excuse,
        ]

    if result == AttackResultTypes.AttRetreatsART:
        return [f"I'm sorry, {lord}, the fleet was forced to retreat."]

    if result == AttackResultTypes.DefConqueredART:
        if target.ObjTyp == ObjectTypes.Flt:
            return [f"The enemy fleet has been destroyed, {lord}."]

        name = empire_name(game, player) or player.name
        style = (
            f"In the name of Her Imperial Majesty, Lady of {name}, I hereby declare"
            if empress(game, player)
            else f"In the name of His Imperial Majesty, Lord of {name}, I hereby declare"
        )
        return [
            style,
            f"this {ObjName[target.ObjTyp]} to be under the sovereign "
            "jurisdiction of the",
            f"{name} Empire.",
        ]

    return []


def casualty_report(
    before: dict[T, int], after: dict[T, int]
) -> dict[T, int]:
    """Ships lost, by type. Port of ``CasualtyReport``.

    Only losses: a fight that *captured* transports leaves a negative
    difference, and the original's report has no column for it.
    """
    return {
        ship: before[ship] - after[ship]
        for ship in SHIP_TYPES
        if before[ship] > after[ship]
    }


def auto_attack_command(
    game: GameEnvironment, player: Empire, flt_id: IDNumber, target: IDNumber
) -> AttackOutcome:
    """Resolve an attack without the player directing it. ``AutoAttackCommand``.

    The intent is always ``ConquerAIT``: a player attacking by hand is trying
    to take the thing, not to deny its cargo.

    **Original bug (#65).** The original reads the fleet's ships again after
    the fight -- ``GetShips(FltID, NewShips)`` -- without checking whether the
    fleet still exists, and then subtracts to get the casualty list. When the
    attack force is destroyed the record has been disposed, so it reads freed
    memory and reports a casualty list built from whatever is there. The code
    plainly knows the fleet can die: ``ResultMessage`` has a branch for
    exactly that outcome.

    Here that reads a ``None`` slot, so the port takes the defined reading: a
    destroyed fleet lost everything it had, which is both true and what the
    subtraction was reaching for.
    """
    if target.ObjTyp not in FIGHTS_BACK:
        name = object_name(game, player, target, long_format=True)
        destroy_construction_or_gate(
            game, player, forces_unknown(game, flt_id, target), target
        )
        return AttackOutcome(
            result=AttackResultTypes.NoART,
            lines=[f"{name} has been destroyed."],
        )

    before = get_ships(game, flt_id)
    result, spoils = npe_attack(
        game, flt_id, target, AttackIntentionTypes.ConquerAIT
    )

    if flt_id.Index in game.GlobalSets.SetOfActiveFleets:
        after = get_ships(game, flt_id)
    else:
        # Destroyed: everything aboard was lost. See #65.
        after = {ship: 0 for ship in before}

    return AttackOutcome(
        result=result,
        casualties=casualty_report(before, after),
        spoils=spoils,
        lines=result_message(game, player, target, result),
    )


__all__ = [
    "ATSymb",
    "FIGHTS_BACK",
    "TARGETABLE",
    "TARGETTABLE",
    "AttackOutcome",
    "BattleReport",
    "BattleSession",
    "CaptureQuestion",
    "GroupSplitter",
    "MoveOption",
    "PosN",
    "TypN",
    "attack_command",
    "attack_targets",
    "auto_attack_command",
    "casualty_report",
    "raze_command",
    "result_message",
]
