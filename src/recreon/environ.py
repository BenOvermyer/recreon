"""Global game state.

Port of ENVIRON.PAS, plus ``InitializeUniverse`` from LOADSAVE.PAS, which is
what actually brings a game into being.

Everything the original kept in module-level ``VAR`` lives on
:class:`GameEnvironment`; ported functions take an instance rather than
reaching for a global. Configuration load/save (ANACREON.CNF) and the
save-game routines are Phase 8.
"""

from __future__ import annotations

from .datacnst import init_defense_record
from .datastrc import GlobalSetsRecord, UniverseRecord
from .galaxy import Galaxy
from .types import MAX_NO_OF_PLANETS, PLAYER_EMPIRES, Empire

#: Year the canonical scenario opens on. The original reads this from the
#: scenario file (NEWGAME.PAS) rather than hardcoding it.
DEFAULT_STARTING_YEAR = 4021

#: Seconds allowed per turn, set by InitializeUniverse.
DEFAULT_TIME_PER_TURN = 300


class GameEnvironment:
    """One running game.

    Holding this as an object rather than globals means tests can build
    several independent games, which the Pascal could not do.
    """

    def __init__(self) -> None:
        self.Year: int = DEFAULT_STARTING_YEAR
        self.Player: Empire = Empire.Empire1
        self.Universe: UniverseRecord = UniverseRecord()
        self.Galaxy: Galaxy = Galaxy()
        self.GlobalSets: GlobalSetsRecord = GlobalSetsRecord()

        #: Empires that have not yet moved this year.
        self.EmpiresToMove: set[Empire] = set()

        #: Per-empire news feed, cleared at the start of each empire's turn.
        self.News: dict[Empire, list] = {emp: [] for emp in Empire}

        #: Revolution-index deltas accumulated during one universe update and
        #: applied to empires at the end of it.
        self.NewTotalRevIndex: dict[Empire, int] = {emp: 0 for emp in Empire}

        #: Per-empire AI state. Scenario loading sets the type; the behaviour
        #: that reads it is Phase 7.
        from .npe.types import npe_data_array

        self.NPEData = npe_data_array()
        self.NoOfPlanets: int = 0
        self.TimePerTurn: int = DEFAULT_TIME_PER_TURN

        # Session flags, from the ENVIRON.PAS typed constants.
        self.AutoSave: bool = True
        self.PauseActive: bool = True
        self.AsyncTurns: bool = False
        self.ReEnterGame: bool = False

        # Loop control, from the ANACREON.PAS main program.
        self.ExitProgram: bool = False
        self.ExitGame: bool = False

    # --- Setup ---------------------------------------------------------------

    def initialize_universe(
        self,
        starting_year: int = DEFAULT_STARTING_YEAR,
        size: int = 0,
        planets: int = 0,
    ) -> None:
        """Set up a blank universe.

        Port of LOADSAVE.PAS ``InitializeUniverse``. No active planets,
        starbases, constructions, gates or fleets; the galaxy is empty, with
        no nebulae or minefields. Populating it is NEWGAME.PAS, in Phase 3.
        """
        from .npe.types import npe_data_array

        self.Universe = UniverseRecord()
        self.GlobalSets = GlobalSetsRecord()
        self.News = {emp: [] for emp in Empire}
        self.NPEData = npe_data_array()

        self.Year = starting_year
        self.TimePerTurn = DEFAULT_TIME_PER_TURN
        self.NoOfPlanets = min(planets, MAX_NO_OF_PLANETS)

        self.Galaxy = Galaxy()
        self.Galaxy.initialize(size)

        self._initialize_independent_record()

    def _initialize_independent_record(self) -> None:
        """Fill in the pseudo-empire that owns unclaimed worlds."""
        indep = self.Universe.EmpireData[Empire.Indep]
        indep.EmpireName = "Independent"
        indep.DefenseSettings = init_defense_record()

    # --- Turn order ----------------------------------------------------------

    def reset_empires_to_move(self) -> None:
        """Refill the pending-move set with every active human empire.

        NPEs are excluded: they are resolved by the update, not by waiting on
        a player to finish.
        """
        from .primintr import empire_active, empire_player

        self.EmpiresToMove = {
            emp
            for emp in PLAYER_EMPIRES
            if empire_active(self, emp) and empire_player(self, emp)
        }
