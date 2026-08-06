"""Miscellaneous commands: defense settings and self-destruct.

Port of MSCCOMM.PAS's live half. The unit declares five commands but three of
them -- ``HolocaustCommand``, ``ArtifactCommand`` and ``TransactionCommand`` --
sit inside the ``(* ... *)`` block spanning lines 533-655 and are unreachable
in v2.0. That block is why ``attack.holocaust_world`` has no caller and why
``cdetypes.py`` has none either.

What is live:

* **Defenses** -- how the empire spreads each ship type across the five
  orbital shells. Standing orders, applied whenever a world or base is
  attacked, so this is the one screen that shapes every future battle.
* **Self-destruct** -- scuttle a starbase or stargate.

Drawing them is :mod:`recreon.ui.defenses`.
"""

from __future__ import annotations

from .datastrc import DefenseRecord
from .environ import GameEnvironment
from .primintr import (
    empire_name,
    get_base_type,
    get_population,
    get_status,
    my_lord,
    object_name,
)
from .sbase import self_destruct_object
from .types import SHIP_TYPES, Empire, IDNumber, ObjectTypes, ShellPos, TechnologyTypes
from .utils.pascal import trunc

T = TechnologyTypes

#: The only ship types that may sit on the ground. Fighters and both kinds of
#: transport land; everything else is confined to orbit and above.
GROUND_CAPABLE = frozenset({T.fgt, T.trn, T.jtn})

#: Where the normaliser puts anything it has to move or make up. Sub-orbit is
#: the default berth: close enough to defend the surface, not on it.
DEFAULT_SHELL = ShellPos.SbOrb

TOTAL_MUST_BE_100 = "Total for each ship type must be 100 .. Normalizing"
ONLY_SOME_ON_GROUND = "Only fgt, trn and jtn can be on the ground .. Normalizing"


Distribution = dict[ShellPos, dict[TechnologyTypes, int]]


# --- Defenses ----------------------------------------------------------------


def shell_total(dist: Distribution, ship: TechnologyTypes) -> int:
    """What one ship type's percentages add up to across the five shells."""
    return sum(dist[shell][ship] for shell in ShellPos)


def illegal_amounts(dist: Distribution) -> str | None:
    """The complaint the editor shows on the way out, or None if it is legal.

    Port of ``CheckForIllegalAmounts``. Two rules, and the *last* one to fail
    is the one reported -- the original overwrites ``ErrorStr`` rather than
    collecting, and sweeps ship types in order, so a distribution breaking
    both shows the ground message.
    """
    message: str | None = None

    for ship in SHIP_TYPES:
        if shell_total(dist, ship) != 100:
            message = TOTAL_MUST_BE_100
        if dist[ShellPos.Grnd][ship] != 0 and ship not in GROUND_CAPABLE:
            message = ONLY_SOME_ON_GROUND

    return message


def normalize_defenses(dist: Distribution) -> None:
    """Force every ship type's shells to add to 100, in place. ``Normalize``.

    Three steps per ship type, in this order:

    1. **Ground is cleared** for anything that cannot land -- the percentage
       moves to sub-orbit rather than being discarded, so the ships stay in
       the defence.
    2. **A shortfall goes to sub-orbit.** Under 100 means the player left
       ships unassigned, and they default to the close berth.
    3. **A surplus is scaled down**, each shell to ``Trunc(v / total * 100)``,
       and whatever the truncation loses is handed back to sub-orbit.

    Step 3's truncation always rounds down, so sub-orbit collects the
    remainder every time -- an even split of 100 across three shells comes out
    33/33/34 with the extra in sub-orbit, not spread. Deliberate as far as
    the code shows: sub-orbit is the same fallback all three steps use.
    """
    for ship in SHIP_TYPES:
        if ship not in GROUND_CAPABLE:
            dist[DEFAULT_SHELL][ship] += dist[ShellPos.Grnd][ship]
            dist[ShellPos.Grnd][ship] = 0

        total = shell_total(dist, ship)

        if total < 100:
            dist[DEFAULT_SHELL][ship] += 100 - total

        if total > 100:
            for shell in ShellPos:
                dist[shell][ship] = trunc((dist[shell][ship] / total) * 100)
            scaled = shell_total(dist, ship)
            if scaled < 100:
                dist[DEFAULT_SHELL][ship] += 100 - scaled


def clamp_percent(value: int) -> int:
    """What ``ChangePercent`` stores for a typed-in setting.

    Anything outside 0..100 becomes **0**, not the nearest bound -- so a
    fat-fingered 150 empties that shell rather than filling it. Surprising,
    but it is what the original does, and the normaliser puts the missing
    percentage into sub-orbit on the way out.
    """
    return 0 if value < 0 or value > 100 else value


def defense_settings_for_editing(
    game: GameEnvironment, player: Empire
) -> DefenseRecord:
    """A copy of the empire's standing orders, safe to edit before saving."""
    from .primintr import get_defense_settings

    return get_defense_settings(game, player)


def save_defense_settings(
    game: GameEnvironment, player: Empire, defense: DefenseRecord
) -> None:
    """Store the edited orders. ``DefenseCommand`` does this on the way out."""
    from .primintr import set_defense_settings

    set_defense_settings(game, player, defense)


#: Column headings for the editor grid, as ``DefenseCommand`` writes them.
SHELL_HEADINGS = ("DeepSp", "HighOrb", "Orbit", "SubOrb", "Ground")


# --- Self-destruct -----------------------------------------------------------


class SelfDestructError(Exception):
    """Something that cannot be scuttled, carrying the original's message."""


def can_self_destruct(
    game: GameEnvironment, player: Empire, obj: IDNumber
) -> None:
    """Check ``obj`` may be destroyed. ``GetBaseToDestroy``'s two tests.

    Raises :class:`SelfDestructError` with the message the original writes to
    the error line.

    Only bases and stargates, and **not an industrial complex** -- ``cmp`` is
    excluded by name. A complex sits on a world rather than standing alone, so
    there is nothing to scuttle independently of the world under it.
    """
    if get_status(game, obj) != player:
        name = object_name(game, player, obj, long_format=True)
        raise SelfDestructError(
            f'"{name[:1].upper()}{name[1:]}" is not a part of '
            f"{empire_name(game, player)}, {my_lord(game, player)}."
        )

    is_base = obj.ObjTyp == ObjectTypes.Base
    if (not is_base or get_base_type(game, obj) == T.cmp) and (
        obj.ObjTyp != ObjectTypes.Gate
    ):
        raise SelfDestructError(
            f"{my_lord(game, player)}, only bases, and stargates can be destroyed."
        )


def self_destruct_warning(
    game: GameEnvironment, player: Empire, obj: IDNumber
) -> list[str]:
    """What the player is told before confirming.

    A base kills its population and every ship in the sector; a gate is only
    an expensive loss. The population figure is ``Pop * 10`` million, the
    original's conversion from its internal unit.
    """
    name = object_name(game, player, obj, long_format=True)
    name = f"{name[:1].upper()}{name[1:]}"
    lord = my_lord(game, player)

    if obj.ObjTyp == ObjectTypes.Base:
        deaths = get_population(game, obj) * 10
        return [
            f"{name} reports: Destruct sequence activated...",
            f"Are you sure about this, {lord}?  Destruction of the base will",
            f"result in the deaths of {deaths} million people and will destroy "
            "all ships",
            "in the sector.",
        ]

    return [
        f"Atomic charges set on {name}...",
        f"Are you sure about this, {lord}?  It took us many years to build",
        "this structure.",
    ]


def self_destruct_command(
    game: GameEnvironment, player: Empire, obj: IDNumber
) -> str:
    """Scuttle ``obj``. Port of ``SelfDestructCommand`` past the confirmation.

    Returns the acknowledgement for the command line. Validation is
    :func:`can_self_destruct`; the confirmation itself is the UI's.
    """
    name = object_name(game, player, obj, long_format=True)
    name = f"{name[:1].upper()}{name[1:]}"

    self_destruct_object(game, obj)
    return f"{name} has been destroyed, {my_lord(game, player)}."


def self_destruct_aborted(game: GameEnvironment, player: Empire) -> str:
    return f"Self-destruct aborted, {my_lord(game, player)}."


def destructible_objects(
    game: GameEnvironment, player: Empire
) -> list[tuple[IDNumber, str]]:
    """Everything the player owns that could be scuttled.

    The original asks for a name and interprets it; a list is the same choice
    made visible, and it applies the same rules -- bases that are not
    industrial complexes, and stargates.
    """
    found: list[tuple[IDNumber, str]] = []

    for index in sorted(game.GlobalSets.SetOfStarbasesOf[player]):
        obj = IDNumber(ObjectTypes.Base, index)
        if get_base_type(game, obj) != T.cmp:
            found.append((obj, object_name(game, player, obj, long_format=True)))

    for index in sorted(game.GlobalSets.SetOfActiveGates):
        obj = IDNumber(ObjectTypes.Gate, index)
        if get_status(game, obj) == player:
            found.append((obj, object_name(game, player, obj, long_format=True)))

    return found


__all__ = [
    "DEFAULT_SHELL",
    "GROUND_CAPABLE",
    "ONLY_SOME_ON_GROUND",
    "SHELL_HEADINGS",
    "TOTAL_MUST_BE_100",
    "SelfDestructError",
    "can_self_destruct",
    "clamp_percent",
    "defense_settings_for_editing",
    "destructible_objects",
    "illegal_amounts",
    "normalize_defenses",
    "save_defense_settings",
    "self_destruct_aborted",
    "self_destruct_command",
    "self_destruct_warning",
    "shell_total",
]
