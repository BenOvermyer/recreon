"""Construction commands.

Port of CONSTR.PAS. Despite the name the unit holds no mechanics: starting a
site is ``intrface.construction``, cancelling it is
``intrface.destroy_construction``, and a year's progress is
``update.update_construction``. What is here is the four commands the player
drives them with, minus the drawing, which is :mod:`recreon.ui.construction`.

* **Construct** -- pick something the empire has the technology for, break
  ground on an empty sector, and report what it will cost.
* **Abort construction** -- confirm, then tear the site down.
* **Construction status** -- every site the player owns, when it finishes, and
  what it still needs delivered.
* **Warp link frequency** -- set the code the empire tunes a gate to.

The frequency command is the odd one out: it is filed under construction
because a warp link is a construction type, but it applies to any stargate the
player knows about, including other empires' -- setting yours to match theirs
is how you get to use someone else's gate.
"""

from __future__ import annotations

from dataclasses import dataclass

from .datacnst import ConsCargoNeeded, ThingNames, YearsToBuild
from .environ import GameEnvironment
from .galaxy import Location, XYCoord, limbo
from .intrface import construction, destroy_construction
from .misc import same_id, thg_lmt
from .primintr import (
    add_name,
    delete_name,
    empire_name,
    get_cargo,
    get_constr_time_left,
    get_constr_type,
    get_coord,
    get_coord_name,
    get_defined_name,
    get_empire_technology,
    get_fleets,
    get_object,
    get_status,
    get_warp_link_freq,
    known,
    location2index,
    my_lord,
    object_name,
    set_warp_link_freq,
)
from .types import (
    CONSTR_TYPES,
    MAX_NO_OF_CONSTR_SITES,
    MAX_NO_OF_STARGATES,
    Empire,
    IDNumber,
    ObjectTypes,
    TechnologyTypes,
    empty_quadrant,
    tech_range,
)
from .utils.int_utils import greater_int

T = TechnologyTypes

#: What each construction type is called, from ``ConsName``. Lower case in the
#: original's table; the menu upper-cases the first letter at display time and
#: ``Noun`` prefixes "a"/"an" in the confirmation line.
ConsName: dict[TechnologyTypes, str] = {
    T.SRM: "SRM field",
    T.cmm: "command base",
    T.frt: "fortress",
    T.cmp: "industrial complex",
    T.out: "outpost",
    T.gte: "stargate",
    T.lnk: "warp link",
    T.dis: "jumpspace disrupter",
}

#: Materials a site consumes, in the order the status table shows them.
#: ``ConstrStatusCommand`` sweeps ``che..tri`` and skips ``sup`` -- supplies
#: feed people, not building sites.
CONSTR_MATERIALS = tuple(
    thing for thing in tech_range(T.che, T.tri) if thing != T.sup
)

#: Highest warp link frequency. "Frequency must be between 0 and 9999."
MAX_WARP_LINK_FREQ = 9999


def noun(line: str) -> str:
    """"a fortress", "an outpost". Port of STRG.PAS ``Noun``.

    Vowel test only, and it counts ``Y`` as a vowel -- so it would say "an
    yard" given the chance. None of the eight construction names starts with
    one, so the quirk never shows.
    """
    return ("an " if line[:1].upper() in "AEIOUY" else "a ") + line


# --- Construct ---------------------------------------------------------------


def available_constr_types(
    game: GameEnvironment, player: Empire
) -> list[tuple[TechnologyTypes, str]]:
    """What the empire can build. Port of ``InputConstrType``'s menu.

    Gated on the empire's *technology set*, not its level -- so a scenario can
    hand out a single construction type without advancing anything else. An
    empty list is the "you don't have the technology to build anything!" case.
    """
    _, technology = get_empire_technology(game, player)
    return [
        (kind, ConsName[kind].capitalize())
        for kind in CONSTR_TYPES
        if kind in technology
    ]


def sector_is_free(game: GameEnvironment, xy: XYCoord) -> bool:
    """Whether ``xy`` can be built on. ``GetConstrXY``'s only test.

    One object per sector, so anything already there blocks it -- including
    another empire's world, which is why the error is about the sector rather
    than about permission.
    """
    return same_id(get_object(game, xy), empty_quadrant())


@dataclass(slots=True)
class ConstructionReport:
    """What ``ConstructCommand`` prints once the site exists."""

    con_id: IDNumber
    kind: TechnologyTypes
    coord_name: str
    years: int
    #: Material, quantity per year -- in the original's display order.
    materials: list[tuple[str, int]]

    def headline(self) -> str:
        return (
            f"Starting construction of {noun(ConsName[self.kind])} "
            f"at {self.coord_name}."
        )

    def lines(self) -> list[str]:
        return [
            f"Construction will take approximately {self.years} years to "
            "finish and will",
            "require the following quantities of raw material:",
            *[f"{amount} {name} per year." for name, amount in self.materials],
        ]


def construct_command(
    game: GameEnvironment,
    player: Empire,
    cons_type: TechnologyTypes,
    xy: XYCoord,
) -> ConstructionReport | None:
    """Break ground. Port of ``ConstructCommand``.

    Returns None when no site could be created -- every slot taken, which the
    original does not check for at all: ``Construction`` hands back
    ``EmptyQuadrant`` and the command carries on printing a report about a
    site that does not exist.

    **A name pinned to the coordinate follows the site.** If the player had
    named that empty sector, the label is moved off the coordinate and onto
    the new site's ID, so it keeps tracking the thing rather than the place.
    That matters because a completed site becomes a base or a gate, which can
    then move.
    """
    con_id = construction(game, player, cons_type, xy)
    if same_id(con_id, empty_quadrant()):
        return None

    report = ConstructionReport(
        con_id=con_id,
        kind=cons_type,
        coord_name=get_coord_name(game, xy),
        years=YearsToBuild[cons_type],
        materials=[
            (ThingNames[material], ConsCargoNeeded[cons_type][material])
            for material in CONSTR_MATERIALS
        ],
    )

    existing = location2index(game, player, Location(XY=xy, ID=empty_quadrant()))
    if existing is not None:
        label, _ = get_defined_name(existing)
        delete_name(game, player, label)
        add_name(game, player, Location(XY=limbo(), ID=con_id), label)

    return report


# --- Abort -------------------------------------------------------------------


def abort_construction_command(
    game: GameEnvironment, player: Empire, con_id: IDNumber
) -> str:
    """Tear a site down. Port of ``AbortConstructionCommand``, past the "y/N".

    Returns the acknowledgement the original writes to the command line. The
    confirmation itself is the UI's; this is what happens once it is given.
    """
    name = object_name(game, player, con_id, long_format=True)
    destroy_construction(game, con_id)
    return f"{name[:1].upper()}{name[1:]} aborted, {my_lord(game, player)}."


# --- Status ------------------------------------------------------------------


@dataclass(slots=True)
class ConstrStatusRow:
    """One line of the construction status table."""

    con_id: IDNumber
    name: str
    kind: TechnologyTypes
    completion_year: int
    #: Material, still needed this year after what is already on hand.
    shortfall: list[tuple[TechnologyTypes, int]]

    def as_line(self) -> str:
        """The original's fixed columns: 10, 32, 47, then 5 per material."""
        line = f"{self.name[:10]:<10}{ConsName[self.kind]}"[:32].ljust(32)
        line = f"{line}{self.completion_year}"[:47].ljust(47)
        return line + "".join(f"{amount:>5}" for _, amount in self.shortfall)


def constr_status_rows(
    game: GameEnvironment, player: Empire
) -> list[ConstrStatusRow]:
    """Every site the player owns. Port of ``ConstrStatusCommand``.

    The shortfall column is what makes the table worth reading: a site consumes
    material *per year*, and only the owner's fleets parked on the site can
    supply it, so this is "how much more must be sitting there when the year
    turns". Negative shortfalls are clamped to zero -- a surplus is not shown.
    """
    rows: list[ConstrStatusRow] = []

    for i in range(1, MAX_NO_OF_CONSTR_SITES + 1):
        if i not in game.GlobalSets.SetOfConstructionSitesOf[player]:
            continue

        con_id = IDNumber(ObjectTypes.Con, i)
        kind = get_constr_type(game, con_id)
        site_xy = get_coord(game, con_id)

        # Only this empire's fleets, and only the ones actually on the site.
        available = {material: 0 for material in CONSTR_MATERIALS}
        for index in get_fleets(game, site_xy) & game.GlobalSets.SetOfFleetsOf[player]:
            cargo = get_cargo(game, IDNumber(ObjectTypes.Flt, index))
            for material in CONSTR_MATERIALS:
                available[material] = thg_lmt(available[material] + cargo[material])

        rows.append(
            ConstrStatusRow(
                con_id=con_id,
                name=object_name(game, player, con_id),
                kind=kind,
                completion_year=game.Year + get_constr_time_left(game, con_id),
                shortfall=[
                    (
                        material,
                        greater_int(
                            0, ConsCargoNeeded[kind][material] - available[material]
                        ),
                    )
                    for material in CONSTR_MATERIALS
                ],
            )
        )

    return rows


#: The status table's two header rows, at the original's column offsets.
CONSTR_STATUS_HEADER = (
    " " * 32 + "Date of         Materials Needed",
    "Site      Type                Completion         che  met  tri",
)


def no_construction_sites_message(game: GameEnvironment, player: Empire) -> str:
    return f"{my_lord(game, player)}, there are no active construction sites."


# --- Warp link frequency -----------------------------------------------------


@dataclass(slots=True)
class WarpLinkEntry:
    """One stargate the player knows of, and the frequency tuned to it."""

    obj: IDNumber
    name: str
    owner: Empire
    owner_name: str
    frequency: int

    def as_line(self) -> str:
        return f"{self.name} ({self.owner_name})"[:32].ljust(32) + f"  {self.frequency}"


def warp_link_freq_list(
    game: GameEnvironment, player: Empire
) -> list[WarpLinkEntry]:
    """Every stargate the player knows of. Port of ``WarpLinkFreqList``.

    Other empires' gates are listed too, and that is the point: matching your
    frequency to theirs is how you get to use someone else's gate.

    Sweeps all ``MaxNoOfStargates`` slots and filters on ``Known`` alone,
    without consulting ``SetOfActiveGates`` -- so it reads records outside the
    active set. Harmless, because an unused slot's ``KnownBy`` is empty and the
    test fails, but it is why this does not check the set either.
    """
    entries: list[WarpLinkEntry] = []

    for i in range(1, MAX_NO_OF_STARGATES + 1):
        obj = IDNumber(ObjectTypes.Gate, i)
        if not known(game, player, obj):
            continue

        owner = get_status(game, obj)
        entries.append(
            WarpLinkEntry(
                obj=obj,
                name=object_name(game, player, obj, long_format=True),
                owner=owner,
                owner_name=empire_name(game, owner) or owner.name,
                frequency=get_warp_link_freq(game, player, obj),
            )
        )

    return entries


def no_stargates_message(game: GameEnvironment, player: Empire) -> str:
    return f"There are no known stargates in the galaxy, {my_lord(game, player)}"


class FrequencyError(ValueError):
    """A frequency outside 0..9999."""


def set_warp_link_frequency(
    game: GameEnvironment, player: Empire, obj: IDNumber, frequency: int
) -> None:
    """Tune the empire's receiver for one gate. ``WarpLinkFrequencyCommand``.

    The frequency is per *empire*, per gate -- each empire keeps its own guess
    at every gate's code, which is why one gate has eight of them.
    """
    if not 0 <= frequency <= MAX_WARP_LINK_FREQ:
        raise FrequencyError(
            f"Frequency must be between 0 and {MAX_WARP_LINK_FREQ}."
        )
    set_warp_link_freq(game, player, obj, frequency)


def warp_link_advice(
    game: GameEnvironment, player: Empire, obj: IDNumber
) -> list[str]:
    """What the command says after setting a frequency.

    Different advice depending on whose gate it is: keep your own code quiet,
    or match the owner's or it will not work.
    """
    owner = get_status(game, obj)
    if owner == player:
        return [
            "Please be careful how you divulge this frequency, as other empires",
            "who know or guess it will have access to our device.",
        ]
    return [
        f"If this is not the same frequency that "
        f"{empire_name(game, owner) or owner.name} has",
        "configured, we will still not be able to use this device.",
    ]


__all__ = [
    "CONSTR_MATERIALS",
    "CONSTR_STATUS_HEADER",
    "ConsName",
    "ConstrStatusRow",
    "ConstructionReport",
    "FrequencyError",
    "MAX_WARP_LINK_FREQ",
    "WarpLinkEntry",
    "abort_construction_command",
    "available_constr_types",
    "constr_status_rows",
    "construct_command",
    "no_construction_sites_message",
    "no_stargates_message",
    "noun",
    "sector_is_free",
    "set_warp_link_frequency",
    "warp_link_advice",
    "warp_link_freq_list",
]
