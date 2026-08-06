"""Saving and loading a game.

Port of LOADSAVE.PAS. ``InitializeUniverse`` already lives on
:class:`~recreon.environ.GameEnvironment`, where the rest of the global state
is; everything else in the unit is here.

The file format is JSON, not the original's raw record dump
=============================================================

The original writes records with ``BlockWrite`` straight out of memory, which
works because a Turbo Pascal record has a fixed layout the compiler and the
file agree on. Nothing in Python has that layout, so a byte-compatible port
would mean hand-rolling every record's DOS-era packing -- packed sets, the
1-byte length prefix on strings, ``Reserved`` padding fields that
:mod:`recreon.datastrc` deliberately dropped -- to read files that, as far as
this repo knows, do not exist: no ``.SAV`` or ``.BAK`` is shipped in
``original/``, and none can be generated without a DOS build.

So this is its own format, with its own signature and its own version line
starting at 1. Two consequences worth being plain about:

* **A save from the DOS build cannot be loaded, and never will be by this
  code.** That is a real capability the port does not have.
* **The version shims in the original are unportable, not merely unported.**
  ``SFVersion > 13`` reading ``TerraformTarget``, ``SFVersion > 14`` reading a
  stargate's ``WLF``, ``Version < 12`` reading the old eight-byte NPE
  ``FleetData`` -- each reinterprets a byte layout that has no counterpart
  here. They are documented at the sites that would have carried them.

What *is* ported is the structure and the behaviour: the sections in the
original's order, the per-empire sets rebuilt from the records rather than
saved, the world count recounted on load, the fleet-position sanitising, and
the two version warnings.
"""

from __future__ import annotations

import json
from pathlib import Path

from .datastrc import (
    ConstrRecord,
    EmpireDataRecord,
    FleetRecord,
    PlanetRecord,
    StarbaseRecord,
    StargateRecord,
)
from .environ import GameEnvironment
from .galaxy import XYCoord
from .mess import delete_all_messages, load_message_data, save_message_data
from .news import erase_news, load_news_data, save_news_data
from .npe.dispatch import clean_up_npe, load_npe_data, save_npe_data
from .orders import CommandRecord, get_fleet_code, initialize_orders, set_fleet_code
from .primintr import delete_all_names, empire_active, empire_player
from .types import (
    MAX_NO_OF_CONSTR_SITES,
    MAX_NO_OF_FLEETS,
    MAX_NO_OF_STARBASES,
    MAX_NO_OF_STARGATES,
    PLAYER_EMPIRES,
    Empire,
    IDNumber,
    ObjectTypes,
)
from .utils.serial import decode, encode, encode_record

#: Written into every save and checked on load, as ``SFSignature`` is. The
#: original's string names Anacreon and its own format; this one names neither,
#: because it is not that format -- see the module docstring.
SF_SIGNATURE = "Re:creon save file"

#: The port's own format version, unrelated to the original's
#: ``CurrentSFVersion = 15``. Bump it when a section's shape changes.
CURRENT_SF_VERSION = 1


class SaveFileError(Exception):
    """A save file that cannot be read.

    The original returns a DOS error code from every routine and threads it
    through ``IF Error<>0 THEN GOTO FileError``. An exception is the same
    control flow with the bookkeeping removed: a failed load abandons the
    whole file rather than leaving a half-built universe, which is what the
    ``GOTO`` achieves.
    """


# --- Planets -----------------------------------------------------------------


def save_planets(game: GameEnvironment) -> dict:
    """Port of ``SavePlanets``.

    Writes 1..NoOfPlanets rather than only the active ones. That is what the
    original does, and it matters: worlds are never destroyed, only conquered,
    so ``SetOfActivePlanets`` is exactly 1..NoOfPlanets and the index is the
    identity every ``IDNumber`` in the file refers to.
    """
    return {
        str(i): encode(game.Universe.Planet[i])
        for i in range(1, game.NoOfPlanets + 1)
        if game.Universe.Planet[i] is not None
    }


def load_planets(game: GameEnvironment, data: dict) -> None:
    """Port of ``LoadPlanets``.

    ``NoOfPlanets`` is recounted here rather than read from the file, and the
    active/per-empire sets are rebuilt from each record's own ``Emp``. Both
    are the original's behaviour, and both are why a save cannot disagree
    with itself about who owns what.
    """
    game.GlobalSets.SetOfActivePlanets = set()
    for emp in Empire:
        game.GlobalSets.SetOfPlanetsOf[emp] = set()

    game.NoOfPlanets = 0
    for key, record in sorted(data.items(), key=lambda kv: int(kv[0])):
        index = int(key)
        game.NoOfPlanets += 1
        planet = decode(PlanetRecord, record)
        game.Universe.Planet[index] = planet

        game.GlobalSets.SetOfActivePlanets.add(index)
        game.GlobalSets.SetOfPlanetsOf[planet.Emp].add(index)


# --- Starbases ---------------------------------------------------------------


def save_starbases(game: GameEnvironment) -> dict:
    """Port of ``SaveStarbases``."""
    return {
        str(i): encode(game.Universe.Starbase[i])
        for i in range(1, MAX_NO_OF_STARBASES + 1)
        if i in game.GlobalSets.SetOfActiveStarbases
    }


def load_starbases(game: GameEnvironment, data: dict) -> None:
    """Port of ``LoadStarbases``."""
    game.GlobalSets.SetOfActiveStarbases = set()
    for emp in Empire:
        game.GlobalSets.SetOfStarbasesOf[emp] = set()

    for key, record in data.items():
        index = int(key)
        base = decode(StarbaseRecord, record)
        game.Universe.Starbase[index] = base

        game.GlobalSets.SetOfActiveStarbases.add(index)
        game.GlobalSets.SetOfStarbasesOf[base.Emp].add(index)


# --- Fleets ------------------------------------------------------------------


def save_fleets(game: GameEnvironment) -> dict:
    """Port of ``SaveFleets``.

    A fleet's compiled orders go out as their own block beside the record, as
    the original writes ``NoOfComs`` and then the commands -- the Pascal has
    to, because ``OrderData`` is six bytes type-punned onto a heap pointer,
    and here because the field is annotated as a bare ``list``.

    The original only writes orders when ``FleetNextStatement > 0``, so a
    fleet holding compiled orders it has finished running (``NextOrder`` back
    at 0) saves with an empty list and loses them. Kept: a fleet that has run
    off the end of its orders has nothing left to execute, so the loss is not
    observable -- but it is why the check is on ``NextOrder`` and not on
    whether the list is empty.
    """
    fleets = {}
    for i in range(1, MAX_NO_OF_FLEETS + 1):
        if i not in game.GlobalSets.SetOfActiveFleets:
            continue

        fleet = game.Universe.Fleet[i]
        flt_id = IDNumber(ObjectTypes.Flt, i)

        orders: list = []
        if fleet.NextOrder > 0:
            orders = [encode(command) for command in get_fleet_code(game, flt_id)]

        fleets[str(i)] = {
            "fleet": encode_record(fleet, skip=("OrderData",)),
            "orders": orders,
        }
    return fleets


def load_fleets(game: GameEnvironment, data: dict) -> None:
    """Port of ``LoadFleets``.

    Carries the original's coordinate repair: a fleet whose position *or*
    destination has a zero component is moved to (1, 1) and pointed at (1, 1).
    Zero is Limbo, so this is catching a fleet that was saved nowhere -- and
    it is a blunt fix, dumping it in the galaxy's top-left corner regardless
    of whose it is or where it was going. Reproduced rather than improved: a
    fleet at Limbo would crash the sector lookups instead.
    """
    game.GlobalSets.SetOfActiveFleets = set()
    for emp in Empire:
        game.GlobalSets.SetOfFleetsOf[emp] = set()

    for key, entry in data.items():
        index = int(key)
        fleet = decode(FleetRecord, entry["fleet"])
        game.Universe.Fleet[index] = fleet

        if 0 in (fleet.Dest.x, fleet.Dest.y, fleet.XY.x, fleet.XY.y):
            fleet.Dest = XYCoord(1, 1)
            fleet.XY = XYCoord(1, 1)

        game.GlobalSets.SetOfFleetsOf[fleet.Emp].add(index)
        game.GlobalSets.SetOfActiveFleets.add(index)

        code = initialize_orders()
        for command in entry["orders"]:
            code.append(decode(CommandRecord, command))
        set_fleet_code(game, IDNumber(ObjectTypes.Flt, index), code)


# --- Stargates ---------------------------------------------------------------


def save_stargates(game: GameEnvironment) -> dict:
    """Port of ``SaveStargates``."""
    return {
        str(i): encode(game.Universe.Stargate[i])
        for i in range(1, MAX_NO_OF_STARGATES + 1)
        if i in game.GlobalSets.SetOfActiveGates
    }


def load_stargates(game: GameEnvironment, data: dict) -> None:
    """Port of ``LoadStargates``.

    Gates have no per-empire set -- a gate is infrastructure anyone can use,
    with per-empire access carried in ``WLF`` instead -- so only
    ``SetOfActiveGates`` is rebuilt.
    """
    game.GlobalSets.SetOfActiveGates = set()

    for key, record in data.items():
        index = int(key)
        game.Universe.Stargate[index] = decode(StargateRecord, record)
        game.GlobalSets.SetOfActiveGates.add(index)


# --- Construction sites ------------------------------------------------------


def save_constr(game: GameEnvironment) -> dict:
    """Port of ``SaveConstr``."""
    return {
        str(i): encode(game.Universe.Constr[i])
        for i in range(1, MAX_NO_OF_CONSTR_SITES + 1)
        if i in game.GlobalSets.SetOfActiveConstructionSites
    }


def load_constr(game: GameEnvironment, data: dict) -> None:
    """Port of ``LoadConstr``."""
    game.GlobalSets.SetOfActiveConstructionSites = set()
    for emp in Empire:
        game.GlobalSets.SetOfConstructionSitesOf[emp] = set()

    for key, record in data.items():
        index = int(key)
        site = decode(ConstrRecord, record)
        game.Universe.Constr[index] = site

        game.GlobalSets.SetOfActiveConstructionSites.add(index)
        game.GlobalSets.SetOfConstructionSitesOf[site.Emp].add(index)


# --- Empire data -------------------------------------------------------------


def save_empire_data(game: GameEnvironment) -> dict:
    """Port of ``SaveEmpireData``.

    Empire1..Empire8 only, as the original does. ``Indep`` is rebuilt from
    scratch by ``initialize_universe``, so saving it would only give a stale
    copy something to overwrite the fresh one with.

    Each empire's place names ride along in the same record; the original
    writes a count and then walks the linked list, which is a list here.
    """
    return {
        str(int(emp)): encode(game.Universe.EmpireData[emp]) for emp in PLAYER_EMPIRES
    }


def load_empire_data(game: GameEnvironment, data: dict) -> None:
    """Port of ``LoadEmpireData``."""
    for key, record in data.items():
        game.Universe.EmpireData[Empire(int(key))] = decode(EmpireDataRecord, record)


# --- The whole game ----------------------------------------------------------


def clean_up_universe(game: GameEnvironment) -> None:
    """Release everything a game was holding. Port of ``CleanUpUniverse``.

    Every arm of the original is a heap ``Dispose``, so in Python none of this
    frees anything -- it is Python's garbage collector's job. It is ported
    anyway, in the original's order, because two of the arms have side effects
    that are *not* deallocation: ``DestroyFleet`` clears the fleet's empire out
    of its sector's ``Flts`` set, and ``clean_up_npe`` drops the persona
    payload. A caller that reuses a :class:`~recreon.environ.GameEnvironment`
    needs both to have happened.
    """
    # Deferred: fleet.py imports loadsave-adjacent modules at import time.
    from .fleet import destroy_fleet

    delete_all_messages(game)

    for i in range(1, MAX_NO_OF_FLEETS + 1):
        if i in game.GlobalSets.SetOfActiveFleets:
            destroy_fleet(game, IDNumber(ObjectTypes.Flt, i))

    for emp in PLAYER_EMPIRES:
        if empire_active(game, emp):
            erase_news(game, emp)
            delete_all_names(game, emp)

            if not empire_player(game, emp):
                clean_up_npe(game, emp)

    game.Galaxy.initialize(0)


def save_game(game: GameEnvironment, filename: str | Path) -> None:
    """Write ``game`` to ``filename``. Port of ``SaveGame``.

    Sections are written in the original's order. That order is not arbitrary:
    empire data has to precede the NPE section, because which empires get a
    persona payload is decided by ``InUse``/``IsAPlayer`` from empire data, and
    the loader walks the same test to know how many payloads to expect.

    A failed write deletes the partial file, as the original's ``FileError``
    label does ``Close`` then ``Erase`` -- half a save file is worse than
    none, since the name is usually the one autosave keeps overwriting.
    """
    path = Path(filename)
    document = {
        "signature": SF_SIGNATURE,
        "version": CURRENT_SF_VERSION,
        "environment": game.save_environment(),
        "sector": game.Galaxy.save_sector(),
        "planets": save_planets(game),
        "starbases": save_starbases(game),
        "fleets": save_fleets(game),
        "stargates": save_stargates(game),
        "constr": save_constr(game),
        "messages": save_message_data(game),
        "empires": save_empire_data(game),
        "news": save_news_data(game),
        "npe": save_npe_data(game),
    }

    try:
        path.write_text(json.dumps(document, indent=1), encoding="utf-8")
    except OSError as exc:
        path.unlink(missing_ok=True)
        raise SaveFileError(f"cannot save to {path}: {exc}") from exc


def load_game(game: GameEnvironment, filename: str | Path) -> list[str]:
    """Load ``filename`` into ``game``. Port of ``LoadGame``.

    Returns any warnings to show the player -- the original opens a window for
    each, and both survive here because they are about the file rather than
    about the UI: a save older than this build may be about to be overwritten
    in a format the older build cannot read, and a save newer than this build
    may not load correctly.

    Two things the original does that this does not, both filed as #46:

    * It calls ``InitializeUniverse`` and *not* ``CleanUpUniverse``, so
      loading over a running game leaks every fleet, name, news item, persona
      and sector row the old one held.
    * ``LoadMessageData`` pushes onto ``MessageList`` without clearing it, and
      ``InitializeUniverse`` does not clear it either, so the previous game's
      inbox survives into the new one.

    :func:`clean_up_universe` runs first here, which fixes the second as a
    side effect -- reproducing it would mean deliberately carrying one game's
    diplomacy into another, and unlike the defects the port does keep, this
    one has no gameplay reading at all.
    """
    path = Path(filename)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SaveFileError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SaveFileError(f"{path} is not a save file: {exc}") from exc

    if not isinstance(document, dict) or document.get("signature") != SF_SIGNATURE:
        raise SaveFileError(f"{path} is not a Re:creon save file")

    version = document.get("version", 0)
    warnings = []
    if version < CURRENT_SF_VERSION:
        warnings.append(
            "The savegame format has changed. If you save this game over the "
            "old save file, you will not be able to re-open it in earlier "
            "versions of Re:creon."
        )
    if version > CURRENT_SF_VERSION:
        warnings.append(
            "This save file was created by a version of Re:creon that is "
            "newer than this version. It may not load properly."
        )

    clean_up_universe(game)
    game.initialize_universe(0, 0, 0)

    try:
        game.load_environment(document["environment"])
        game.Galaxy.load_sector(document["sector"])
        load_planets(game, document["planets"])
        load_starbases(game, document["starbases"])
        load_fleets(game, document["fleets"])
        load_stargates(game, document["stargates"])
        load_constr(game, document["constr"])
        load_message_data(game, document["messages"])
        load_empire_data(game, document["empires"])
        load_news_data(game, document["news"])
        load_npe_data(game, document["npe"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SaveFileError(f"{path} is damaged: {exc}") from exc

    return warnings


def backup_path(game: GameEnvironment) -> Path:
    """Where autosave writes: ``<SavDirect>/<CurrentGame without extension>.BAK``.

    Port of the path ANACREON.PAS builds inline with ``AddDefaultPath`` and
    ``FNameWithoutExt``. The backup sits beside the save it shadows and never
    overwrites it, so a player who quits into a bad position still has the
    file they saved by hand.
    """
    return Path(game.SavDirect) / (Path(game.CurrentGame).stem + ".BAK")


def auto_backup(game: GameEnvironment, filename: str | Path | None = None) -> list[str]:
    """Back the game up if autosave is on. Port of ``AutoBackup``.

    ANACREON.PAS runs this after every completed turn. Returns the warning it
    would have put in a window rather than raising: a backup that fails must
    not take the turn down with it, which is the whole point of the original
    telling the player to save manually instead of stopping.
    """
    if not game.AutoSave:
        return []

    try:
        save_game(game, filename if filename is not None else backup_path(game))
    except SaveFileError:
        return [
            "AutoSave: Can't save the game on default drive. "
            "Be sure to save the game manually."
        ]
    return []


__all__ = [
    "CURRENT_SF_VERSION",
    "SF_SIGNATURE",
    "SaveFileError",
    "auto_backup",
    "backup_path",
    "clean_up_universe",
    "load_game",
    "save_game",
]
