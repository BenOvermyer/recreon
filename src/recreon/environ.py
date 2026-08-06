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

        #: Pages of the scenario's introduction text, as loaded. The original
        #: displays these before the galaxy is built and keeps nothing; they
        #: are kept here for the Phase 8 UI to show.
        self.ScenarioIntroduction: list[str] = []

        #: Scenario this game was built from. Saved and restored, as the
        #: original saves ``ScenaFilename``; nothing reads it back yet.
        self.ScenaFilename: str = ""

        #: Diplomatic messages in flight, newest first. MESS.PAS keeps this in
        #: a global ``MessageList``; the records are in :mod:`recreon.mess`.
        self.MessageList: list = []

        #: Save file this game is playing out of; autosave writes the ``.BAK``
        #: beside it. A typed constant in ENVIRON.PAS, and session state rather
        #: than saved state -- a loaded game takes the name of the file it came
        #: from, not the name it had when it was saved.
        self.CurrentGame: str = "recreon.sav"

        #: Directory the save files live in. ENVIRON.PAS reads this from
        #: ANACREON.CNF along with the scenario and help paths; the config file
        #: itself belongs with the options UI and is not ported.
        self.SavDirect: str = ""

        #: Directory the scenario picker scans for ``*.SCN``.
        self.SceDirect: str = ""

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

    # --- Save/load -----------------------------------------------------------

    def save_environment(self) -> dict:
        """The loose globals, for the save file. Port of ``SaveEnvironment``.

        The original writes exactly nine values here, and this writes the same
        nine. ``NoOfPlanets`` is *not* among them: LoadPlanets recounts it from
        the records it reads, so a save carries no separate world count to fall
        out of step with the worlds themselves.
        """
        return {
            "Year": self.Year,
            "Player": int(self.Player),
            "EmpiresToMove": sorted(int(emp) for emp in self.EmpiresToMove),
            "ScenaFilename": self.ScenaFilename,
            "TimePerTurn": self.TimePerTurn,
            "AutoSave": self.AutoSave,
            "AsyncTurns": self.AsyncTurns,
            "PauseActive": self.PauseActive,
            "ReEnterGame": self.ReEnterGame,
        }

    def load_environment(self, data: dict) -> None:
        """Restore the loose globals. Port of ``LoadEnvironment``."""
        self.Year = data["Year"]
        self.Player = Empire(data["Player"])
        self.EmpiresToMove = {Empire(emp) for emp in data["EmpiresToMove"]}
        self.ScenaFilename = data["ScenaFilename"]
        self.TimePerTurn = data["TimePerTurn"]
        self.AutoSave = data["AutoSave"]
        self.AsyncTurns = data["AsyncTurns"]
        self.PauseActive = data["PauseActive"]
        self.ReEnterGame = data["ReEnterGame"]

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
