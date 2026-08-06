"""Which persona runs a non-player empire's turn.

Port of NPE.PAS. The whole unit is a five-way ``CASE`` on ``NPEData[Emp].Typ``,
repeated once per lifecycle event: set up, run a turn, tear down. Everything it
dispatches to lives in the four persona modules.

Two details of that ``CASE`` are load-bearing:

**The two kingdoms share an implementation.** ``Kingdom1NPE..Kingdom2NPE`` is a
subrange arm and it calls the *Kingdom1* routines for both. The difference
between a passive and an aggressive kingdom is entirely in the persona record
each is initialised with -- initialisation is the one place they are told apart.

**An unrecognised type is run as a pirate.** Every ``CASE`` has an ``ELSE``
falling back to the pirate routines, so an empire whose ``Typ`` was never set
(``NoNPE``, ordinal 0) behaves as a pirate rather than doing nothing. A
scenario that creates an NPE without declaring a type still gets an AI. The
same arm catches ``TraderNPE``, which is declared in `NPEmpireTypes` and has no
implementation anywhere in the original -- a trader empire plays as a pirate.

``LoadNPE``/``SaveNPE`` are Phase 8 and belong with the rest of LOADSAVE.PAS.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..types import Empire
from . import berserker, guardian, kingdom, pirate
from .types import (
    BerserkerDataRecord,
    GuardianDataRecord,
    Kingdom1DataRecord,
    NPEmpireTypes,
    PirateDataRecord,
)

if TYPE_CHECKING:
    from ..environ import GameEnvironment

#: The payload each persona type expects hanging off ``NPEDataRecord.Data``.
_DATA_CLASS = {
    NPEmpireTypes.PirateNPE: PirateDataRecord,
    NPEmpireTypes.Kingdom1NPE: Kingdom1DataRecord,
    NPEmpireTypes.Kingdom2NPE: Kingdom1DataRecord,
    NPEmpireTypes.BerserkerNPE: BerserkerDataRecord,
    NPEmpireTypes.GuardianNPE: GuardianDataRecord,
}


def clean_up_npe(game: GameEnvironment, emp: Empire) -> None:
    """Release whatever the empire's persona was holding.

    Called when an empire is destroyed. Nothing in the port owns an external
    resource, so every arm is a no-op -- but the dispatch is kept so that
    wiring this into ``intrface.destroy_empire`` is a one-line change rather
    than a redesign.
    """
    data = game.NPEData[emp]
    if data.Data is None:
        return

    if data.Typ == NPEmpireTypes.PirateNPE:
        pirate.clean_up_pirate_npe(game, data.Data)
    elif data.Typ in (NPEmpireTypes.Kingdom1NPE, NPEmpireTypes.Kingdom2NPE):
        kingdom.clean_up_kingdom_npe(game, data.Data)
    elif data.Typ == NPEmpireTypes.BerserkerNPE:
        berserker.clean_up_berserker_npe(game, data.Data)
    elif data.Typ == NPEmpireTypes.GuardianNPE:
        guardian.clean_up_guardian_npe(game, data.Data)
    else:
        pirate.clean_up_pirate_npe(game, data.Data)

    data.Data = None


def initialize_npe(game: GameEnvironment, emp: Empire, e_typ: NPEmpireTypes) -> None:
    """Set an empire's persona type and roll its starting character.

    The record the original allocates with ``New(Data)`` is created here, since
    Python has no uninitialised heap block to hand a persona. Kingdom1 and
    Kingdom2 are the one place the two kingdoms diverge.
    """
    data = game.NPEData[emp]
    data.Typ = e_typ
    data.Data = _DATA_CLASS.get(e_typ, PirateDataRecord)()

    if e_typ == NPEmpireTypes.PirateNPE:
        pirate.initialize_pirate_npe(game, emp, data.Data)
    elif e_typ == NPEmpireTypes.Kingdom1NPE:
        kingdom.initialize_kingdom1_npe(game, emp, data.Data)
    elif e_typ == NPEmpireTypes.Kingdom2NPE:
        kingdom.initialize_kingdom2_npe(game, emp, data.Data)
    elif e_typ == NPEmpireTypes.BerserkerNPE:
        berserker.initialize_berserker_npe(game, emp, data.Data)
    elif e_typ == NPEmpireTypes.GuardianNPE:
        guardian.initialize_guardian_npe(game, emp, data.Data)
    else:
        pirate.initialize_pirate_npe(game, emp, data.Data)


def implement_npe(game: GameEnvironment, emp: Empire) -> None:
    """Run one turn for a non-player empire.

    The original opens an ``Updating Empire N...`` window around this; that is
    presentation and belongs with the UI, so it is not reproduced.

    An empire whose ``Data`` was never allocated -- a scenario that named a
    type but never ran `initialize_npe` -- is initialised here rather than
    crashing. The original has the same hole and fills it with an
    uninitialised heap pointer.
    """
    data = game.NPEData[emp]
    if data.Data is None:
        initialize_npe(game, emp, data.Typ)

    if data.Typ == NPEmpireTypes.PirateNPE:
        pirate.implement_pirate_npe(game, emp, data.Data)
    elif data.Typ in (NPEmpireTypes.Kingdom1NPE, NPEmpireTypes.Kingdom2NPE):
        kingdom.implement_kingdom1_npe(game, emp, data.Data)
    elif data.Typ == NPEmpireTypes.BerserkerNPE:
        berserker.implement_berserker_npe(game, emp, data.Data)
    elif data.Typ == NPEmpireTypes.GuardianNPE:
        guardian.implement_guardian_npe(game, emp, data.Data)
    else:
        pirate.implement_pirate_npe(game, emp, data.Data)
