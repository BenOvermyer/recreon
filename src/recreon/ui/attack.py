"""The attack commands.

The Textual half of ATTCOMM.PAS, both entry points. What they *do* is
:mod:`recreon.attcomm`; this is the screens.

* :class:`AutoAttackScreen` is ``AutoAttackCommand``: pick a target in the
  fleet's sector, confirm, and let `attnpe.npe_attack` resolve the whole thing.
* :class:`AttackScreen` is ``AttackCommand``: the same target selection, then
  an optional trip through :class:`GroupSplitterScreen` to divide the fleet by
  hand, then :class:`BattleScreen` -- the round-by-round loop where the player
  aims, closes and decides when to break off.

The original's battle display is a picture: concentric orbital shells drawn in
CP437 glyphs, with ships warping between them. None of that survives, and
nothing in Textual would gain from imitating it. What replaced it is the
information the picture carried -- where each group is, what it is shooting at,
and what the defender still has at each shell.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from ..attack import MAX_NO_OF_GROUPS, AttackResultTypes, GroupRecord, GroupStatus
from ..attcomm import (
    FIGHTS_BACK,
    ATSymb,
    BattleSession,
    GroupSplitter,
    attack_command,
    attack_targets,
    auto_attack_command,
    raze_command,
)
from ..datacnst import ThingNames
from ..environ import GameEnvironment
from ..fltcomm import player_fleets
from ..primintr import my_lord, object_name
from ..types import (
    ATTACK_TYPES,
    SHIP_TYPES,
    Empire,
    IDNumber,
    ShellPos,
    TechnologyTypes,
)
from .prologue import Attention, ChooseFrom, TextPrompt

T = TechnologyTypes

#: What a group can be pointed at, in ``ATSymb`` order. ``NoRes`` is "no orders"
#: -- the ``(-)`` in the roster -- and is offered so a group can be stood down.
TARGETS = ATTACK_TYPES


class AutoAttackScreen(Screen[None]):
    """Choose a fleet, choose a target, confirm, resolve."""

    BINDINGS = [Binding("escape", "close", "Close")]

    CSS = """
    AutoAttackScreen { layout: vertical; }
    #heading { height: auto; padding: 1 2; text-style: bold; }
    #body { height: 1fr; padding: 0 2; }
    """

    def __init__(self, game: GameEnvironment, player: Empire) -> None:
        super().__init__()
        self.game = game
        self.player = player

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Auto Attack:", id="heading")
        yield VerticalScroll(id="body")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        fleets = player_fleets(self.game, self.player)

        if not fleets:
            self._say("You have no fleets deployed.")
            return

        self.app.push_screen(
            ChooseFrom("Which fleet shall attack?", fleets), self._fleet_chosen
        )

    def _say(self, *lines: str) -> None:
        self.query_one("#body", VerticalScroll).mount(Static("\n".join(lines)))

    def action_close(self) -> None:
        self.dismiss(None)

    # --- The flow -------------------------------------------------------------

    def _fleet_chosen(self, flt: IDNumber | None) -> None:
        if flt is None:
            self.dismiss(None)
            return

        targets = attack_targets(self.game, self.player, flt)
        if not targets:
            self.dismiss(None)
            self.app.push_screen(
                Attention(
                    f"There is nothing here to attack, {my_lord(self.game, self.player)}."
                )
            )
            return

        fleet_name = object_name(self.game, self.player, flt, long_format=True)

        def target_chosen(target: IDNumber | None) -> None:
            if target is None:
                self.dismiss(None)
                return

            target_name = object_name(
                self.game, self.player, target, long_format=True
            )

            def confirmed(yes: bool) -> None:
                if not yes:
                    self.dismiss(None)
                    return
                self._resolve(flt, target)

            self.app.push_screen(
                Attention(
                    f"{fleet_name} ready to attack {target_name}.",
                    "Give confirmation order?",
                    confirm=True,
                ),
                confirmed,
            )

        self.app.push_screen(
            ChooseFrom(
                f"{fleet_name} awaiting targetting instructions, "
                f"{my_lord(self.game, self.player)}.",
                targets,
            ),
            target_chosen,
        )

    def _resolve(self, flt: IDNumber, target: IDNumber) -> None:
        outcome = auto_attack_command(self.game, self.player, flt, target)

        self._say(*outcome.lines)
        if outcome.casualties:
            self._say(
                "",
                "Casualties:",
                *[
                    f"  {ThingNames[ship]:<24}{lost}"
                    for ship, lost in outcome.casualties.items()
                ],
            )
        if outcome.spoils:
            self._say("", f"Worlds taken: {len(outcome.spoils)}")


# --- Splitting the fleet by hand (GetGroups) ----------------------------------


class GroupSplitterScreen(ModalScreen[object]):
    """The custom battle configuration. Port of ``GetGroups``'s screen.

    Nine slots, a shared pool of ships above them, and a cursor. The original
    drives this with arrow keys and the space bar and so does this: up/down
    picks a slot, left/right picks a ship type out of the pool, space fills the
    slot with every ship of that type, a number fills it with that many, and
    M/N load troops onto transports.

    Escape does not cancel -- ``GetGroups`` assigns ``Exit := False`` and never
    anything else. It commits whatever has been built, which may be nothing, in
    which case the attack quietly does not happen.
    """

    BINDINGS = [
        Binding("up", "prev_slot", "Slot"),
        Binding("down", "next_slot", "Slot"),
        Binding("left", "prev_type", "Type"),
        Binding("right", "next_type", "Type"),
        Binding("space", "load_all", "Load all"),
        Binding("enter", "load_some", "Load n"),
        Binding("m", "load_men", "Men"),
        Binding("n", "load_ninja", "Ninja"),
        Binding("escape", "done", "Done"),
    ]

    CSS = """
    GroupSplitterScreen { layout: vertical; }
    #heading { height: auto; padding: 1 2; text-style: bold; }
    #body { height: 1fr; padding: 0 2; }
    .cursor { text-style: reverse; }
    """

    def __init__(self, game: GameEnvironment, flt_id: IDNumber) -> None:
        super().__init__()
        self.splitter = GroupSplitter(game, flt_id)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Attack:  Fleet configuration", id="heading")
        yield VerticalScroll(Static(id="sheet"), id="body")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        self._redraw()

    def _redraw(self) -> None:
        s = self.splitter
        header = "  fgt   hk  jmp  jtn  pen  str  trn            men ninj"
        lines = [header, s.pool_line(), ""]
        for i in range(1, MAX_NO_OF_GROUPS + 1):
            mark = ">" if i == s.cg else " "
            lines.append(f"{mark} {s.group_line(i)}")
        lines += ["", f"Type cursor: {ThingNames[s.cur_typ]}"]
        self.query_one("#sheet", Static).update("\n".join(lines))

    # --- Keys -----------------------------------------------------------------

    def action_prev_slot(self) -> None:
        self.splitter.select(self.splitter.cg - 1)
        self._redraw()

    def action_next_slot(self) -> None:
        self.splitter.select(self.splitter.cg + 1)
        self._redraw()

    def action_prev_type(self) -> None:
        self.splitter.change_type(forward=False)
        self._redraw()

    def action_next_type(self) -> None:
        self.splitter.change_type(forward=True)
        self._redraw()

    def action_load_all(self) -> None:
        self.splitter.load_all_of_type()
        self._redraw()

    def action_load_some(self) -> None:
        def answered(text: str | None) -> None:
            if text is None:
                return
            text = text.strip()
            if text == "":
                self.splitter.add_to_group(None)
            else:
                try:
                    self.splitter.add_to_group(int(text))
                except ValueError:
                    return
            self._redraw()

        self.app.push_screen(TextPrompt("Add how many to this group: "), answered)

    def action_load_men(self) -> None:
        self.splitter.load_transports(ninja=False)
        self._redraw()

    def action_load_ninja(self) -> None:
        self.splitter.load_transports(ninja=True)
        self._redraw()

    def action_done(self) -> None:
        self.dismiss(self.splitter.finish())


# --- One round's decisions ----------------------------------------------------


class MoveScreen(ModalScreen[object]):
    """Which groups move, and which way. Port of ``GroupMove``'s prompts.

    The original walks the groups one at a time asking S/A/R. Here they are all
    on one list and each row cycles through its own legal choices, which is the
    same decision with less typing. Escape aborts the whole manoeuvre, as
    Escape does mid-list there.
    """

    BINDINGS = [
        Binding("a", "advance", "Advance"),
        Binding("r", "retreat", "Retreat"),
        Binding("s", "stay", "Stay"),
        Binding("enter", "confirm", "Manoeuvre"),
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    MoveScreen { align: center middle; }
    #box { width: 64; height: auto; max-height: 22; border: solid $accent;
           background: $surface; padding: 1 2; }
    """

    def __init__(self, session: BattleSession) -> None:
        super().__init__()
        self.session = session
        self.options = session.move_options()
        self.orders: dict[int, GroupStatus] = {
            option.group: GroupStatus.GReady for option in self.options
        }

    def compose(self) -> ComposeResult:
        yield Label("Designated groups ready for manoeuvre.", id="box-title")
        with VerticalScroll(id="box"):
            yield ListView(
                *[ListItem(Label(""), name=str(o.group)) for o in self.options]
            )
            yield Label("A advance   R retreat   S stay   Enter manoeuvre", id="hint")

    def on_mount(self) -> None:
        self._redraw()

    def _redraw(self) -> None:
        roster = {
            i + 1: line for i, line in enumerate(self.session.group_lines())
        }
        for item in self.query(ListItem):
            group = int(item.name)
            choice = {
                GroupStatus.GAdvc: "advance",
                GroupStatus.GRtrt: "retreat",
            }.get(self.orders[group], "stay")
            item.query_one(Label).update(f"{roster[group]}   -> {choice}")

    def _current(self) -> int | None:
        item = self.query_one(ListView).highlighted_child
        return int(item.name) if item is not None else None

    def _set(self, status: GroupStatus, allowed: bool) -> None:
        group = self._current()
        if group is None or not allowed:
            return
        self.orders[group] = status
        self._redraw()

    def _option(self, group: int):
        return next(o for o in self.options if o.group == group)

    def action_advance(self) -> None:
        group = self._current()
        if group is not None:
            self._set(GroupStatus.GAdvc, self._option(group).can_advance)

    def action_retreat(self) -> None:
        group = self._current()
        if group is not None:
            self._set(GroupStatus.GRtrt, self._option(group).can_retreat)

    def action_stay(self) -> None:
        self._set(GroupStatus.GReady, allowed=True)

    def action_confirm(self) -> None:
        self.dismiss(self.orders)

    def action_cancel(self) -> None:
        self.dismiss(None)


class TargetScreen(ModalScreen[object]):
    """What each group shoots at. Port of ``GroupTarget``.

    There is no priority calculation and no range check: a group pointed at
    something that is not at its shell simply wastes the round. That is the
    price of steering by hand, and the reason the auto-attack often does better.
    """

    BINDINGS = [
        Binding("enter", "confirm", "Confirm"),
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    TargetScreen { align: center middle; }
    #box { width: 72; height: auto; max-height: 22; border: solid $accent;
           background: $surface; padding: 1 2; }
    """

    def __init__(self, session: BattleSession) -> None:
        super().__init__()
        self.session = session
        self.groups = session.target_options()
        self.targets: dict[int, T] = {i: session.gp[i].Trg for i in self.groups}

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="box"):
            yield Label("New target for each group:")
            yield ListView(
                *[ListItem(Label(""), name=str(i)) for i in self.groups]
            )
            yield Label(
                "  ".join(f"{ATSymb[thing]}:{ThingNames[thing]}" for thing in TARGETS),
                id="key",
            )

    def on_mount(self) -> None:
        self._redraw()

    def _redraw(self) -> None:
        roster = {i + 1: line for i, line in enumerate(self.session.group_lines())}
        for item in self.query(ListItem):
            group = int(item.name)
            item.query_one(Label).update(
                f"{roster[group]}   -> {ThingNames[self.targets[group]] or 'no orders'}"
            )

    def on_key(self, event) -> None:
        letter = event.key.upper()
        for thing in TARGETS:
            if ATSymb[thing] == letter:
                item = self.query_one(ListView).highlighted_child
                if item is not None:
                    self.targets[int(item.name)] = thing
                    self._redraw()
                event.stop()
                return

    def action_confirm(self) -> None:
        self.dismiss(self.targets)

    def action_cancel(self) -> None:
        self.dismiss(None)


# --- The battle ---------------------------------------------------------------


class BattleScreen(Screen[object]):
    """The round-by-round loop. Port of ``Engage``'s menu and displays.

    ``E`` fights a round, ``M`` moves groups (and fights the round that
    follows), ``T`` retargets, ``G`` shows the roster, ``D`` shows what the last
    round cost, ``R`` breaks off. The original blocks on each of these; here
    each is a screen or an immediate redraw, and :attr:`BattleSession.end_battle`
    is what closes the loop.
    """

    BINDINGS = [
        Binding("e", "engage", "Engage"),
        Binding("m", "move", "Move"),
        Binding("t", "target", "Target"),
        Binding("d", "details", "Details"),
        Binding("r", "retreat", "Retreat"),
    ]

    CSS = """
    BattleScreen { layout: vertical; }
    #heading { height: auto; padding: 1 2; text-style: bold; }
    #panes { height: 1fr; }
    #groups { width: 1fr; padding: 0 2; }
    #enemy { width: 1fr; padding: 0 2; }
    #log { height: 8; padding: 0 2; border-top: solid $accent; }
    """

    def __init__(self, session: BattleSession) -> None:
        super().__init__()
        self.session = session
        self.showing_details = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="heading")
        with Horizontal(id="panes"):
            yield VerticalScroll(Static(id="groups-sheet"), id="groups")
            yield VerticalScroll(Static(id="enemy-sheet"), id="enemy")
        yield VerticalScroll(Static(id="log-sheet"), id="log")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        self._redraw()

    # --- Drawing --------------------------------------------------------------

    def _redraw(self) -> None:
        s = self.session
        target = object_name(s.game, s.player, s.target, long_format=True)
        self.query_one("#heading", Static).update(f"Attack: {target}")

        if self.showing_details:
            columns = "".join(f"{i:5}" for i in range(1, s.no_of_groups + 1))
            body = [
                "Ships destroyed by enemy, last round:",
                "",
                " " * 22 + columns,
            ]
            body += [
                f"{name:>20}: " + "".join(f"{n:5}" for n in per_group)
                for name, per_group in s.detail_rows()
            ] or ["  (nothing scored)"]
            body += ["", "Press D again for the group roster."]
            self.query_one("#groups-sheet", Static).update("\n".join(body))
        else:
            self.query_one("#groups-sheet", Static).update(
                "\n".join(["Your groups:", ""] + s.group_lines())
            )

        self.query_one("#enemy-sheet", Static).update("\n".join(self._enemy_lines()))
        self.query_one("#log-sheet", Static).update("\n".join(s.report[-12:]))

    def _enemy_lines(self) -> list[str]:
        """``EnemyStatus``'s window: what the defender still has, per shell."""
        en = self.session.en
        head = "                    " + "".join(f"{shell.name:>6}" for shell in ShellPos)
        lines = ["Enemy:", "", head]
        for thing in SHIP_TYPES:
            counts = "".join(f"{en[shell][thing]:6}" for shell in ShellPos)
            lines.append(f"{ThingNames[thing]:>20}" + counts)
        lines.append("")
        for thing in (T.def_, T.GDM, T.ion, T.LAM, T.men, T.nnj):
            total = sum(en[shell][thing] for shell in ShellPos)
            if total:
                lines.append(f"{ThingNames[thing]:>20}{total:6}")
        return lines

    # --- The menu -------------------------------------------------------------

    def action_engage(self) -> None:
        self.showing_details = False
        self.session.engage()
        self._finish_round()

    def action_details(self) -> None:
        self.showing_details = not self.showing_details
        self._redraw()

    def action_move(self) -> None:
        def moved(orders: object) -> None:
            if orders is None:  # Escape: the whole manoeuvre is cancelled.
                self.session.cancel_moves()
                return
            if not self.session.set_moves(orders):
                # Nothing is actually moving, so no round is fought and the
                # enemy gets no free shot. `Ok` stays false in the original too.
                self.session.cancel_moves()
                self._redraw()
                return
            self.showing_details = False
            self.session.engage()
            self._finish_round()

        self.app.push_screen(MoveScreen(self.session), moved)

    def action_target(self) -> None:
        def targeted(targets: object) -> None:
            if targets is not None:
                self.session.set_targets(targets)
            self._redraw()

        self.app.push_screen(TargetScreen(self.session), targeted)

    def action_retreat(self) -> None:
        def confirmed(yes: bool) -> None:
            if not yes:
                return
            self.session.retreat()
            self._finish_round()

        self.app.push_screen(
            Attention("Break off the attack?", "Are you sure?", confirm=True), confirmed
        )

    def _finish_round(self) -> None:
        self._redraw()
        if self.session.end_battle:
            self.app.call_after_refresh(self._conclude)

    # --- CleanUp --------------------------------------------------------------

    def _conclude(self) -> None:
        session = self.session
        report = session.conclude()

        def settle(capture: bool) -> None:
            session.settle(report, capture)
            self.dismiss(report)

        question = report.capture_question
        if question is None:
            settle(capture=True)
            return

        captured = "\n".join(
            f"  {count} {ThingNames[ship]}" for ship, count in question.ships.items()
        )

        def answered(destroy: bool) -> None:
            # "Yes, destroy them" sets Capture := False. The polite answer is
            # the greedy one.
            settle(capture=not destroy)

        self.app.push_screen(
            Attention(
                "You have captured:\n" + captured + "\n\n" + "\n".join(question.lines),
                "Do you wish to destroy the enemy fleet?",
                confirm=True,
            ),
            answered,
        )


class AttackScreen(Screen[None]):
    """``AttackCommand``: choose a fleet and a target, then fight it by hand."""

    BINDINGS = [Binding("escape", "close", "Close")]

    CSS = """
    AttackScreen { layout: vertical; }
    #heading { height: auto; padding: 1 2; text-style: bold; }
    #body { height: 1fr; padding: 0 2; }
    """

    def __init__(self, game: GameEnvironment, player: Empire) -> None:
        super().__init__()
        self.game = game
        self.player = player

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Attack:", id="heading")
        yield VerticalScroll(id="body")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        fleets = player_fleets(self.game, self.player)
        if not fleets:
            self._say("You have no fleets deployed.")
            return
        self.app.push_screen(
            ChooseFrom("Which fleet shall attack?", fleets), self._fleet_chosen
        )

    def _say(self, *lines: str) -> None:
        self.query_one("#body", VerticalScroll).mount(Static("\n".join(lines)))

    def action_close(self) -> None:
        self.dismiss(None)

    # --- The flow -------------------------------------------------------------

    def _fleet_chosen(self, flt: IDNumber | None) -> None:
        if flt is None:
            self.dismiss(None)
            return

        targets = attack_targets(self.game, self.player, flt)
        if not targets:
            self.dismiss(None)
            self.app.push_screen(
                Attention(
                    "There is nothing here to attack, "
                    f"{my_lord(self.game, self.player)}."
                )
            )
            return

        fleet_name = object_name(self.game, self.player, flt, long_format=True)
        self.app.push_screen(
            ChooseFrom(
                f"{fleet_name} awaiting targetting instructions, "
                f"{my_lord(self.game, self.player)}.",
                targets,
            ),
            lambda target: self._target_chosen(flt, target),
        )

    def _target_chosen(self, flt: IDNumber, target: IDNumber | None) -> None:
        if target is None:
            self.dismiss(None)
            return

        if target.ObjTyp not in FIGHTS_BACK:
            # A construction site or a stargate: razed, not fought.
            self._say(*raze_command(self.game, self.player, flt, target))
            return

        def configured(standard: bool) -> None:
            if standard:
                self._open_battle(flt, target, groups=None)
                return
            self.app.push_screen(
                GroupSplitterScreen(self.game, flt),
                lambda groups: self._open_battle(flt, target, groups),
            )

        self.app.push_screen(
            Attention(
                f"{object_name(self.game, self.player, flt, long_format=True)} ready "
                f"to attack {object_name(self.game, self.player, target, True)}.",
                "Standard battle configuration?",
                confirm=True,
            ),
            configured,
        )

    def _open_battle(
        self,
        flt: IDNumber,
        target: IDNumber,
        groups: tuple[int, list[GroupRecord | None]] | None,
    ) -> None:
        session = attack_command(self.game, self.player, flt, target, groups)
        if session is None:
            self._say("There is nothing aboard to attack with.")
            return
        self.app.push_screen(BattleScreen(session), self._battle_over)

    def _battle_over(self, report: object) -> None:
        if report is None:
            self.dismiss(None)
            return

        self._say(*report.lines)
        if report.old_ships:
            self._say(
                "",
                "Ships found in orbit:",
                *[
                    f"  {count} {ThingNames[ship]}"
                    for ship, count in report.old_ships.items()
                ],
            )
        if report.spoils:
            self._say("", f"Worlds taken: {len(report.spoils)}")
        if report.result is AttackResultTypes.NoART:
            self._say("", "The engagement ended without a decision.")
