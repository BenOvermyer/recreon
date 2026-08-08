"""Scenario loading and universe generation.

Port of NEWGAME.PAS. This is a scenario-*file interpreter*: it reads a `.scn`
text file and executes directives that build the universe. There is no code
path that generates a galaxy without one.

The 13 scenario files that shipped with Anacreon are in ``original/scenarios``
and are the authority on the format; 11 of them load. ``data/scenarios`` holds
newly authored content, which is not a port and reproduces no galaxy the
original shipped. See IMPLEMENTATION_PLAN.md §3.5.

Loading is a single forward pass over the file: header, then the introduction
(see :meth:`ScenarioLoader.read_introduction`), then directives until
``ENDSCENARIO``. Nothing seeks backwards, so a directive that reads the wrong
number of tokens desynchronises everything after it -- which is how both of
the two unloadable shipped scenarios fail.

The front end -- ``GetScenarios``, ``ScenarioIntroduction``,
``InputEmpireName`` and ``StartNewGame`` -- is here too, as
:func:`get_scenarios` and the :class:`ScenarioFrontEnd` protocol. The original
interleaves it with the parse: the intro pages, the player count and the
empire names are all read or asked for *between* the header and the first
directive, in the same forward pass. So the front end cannot be a wrapper
around loading; it has to be something loading calls into, which is what the
protocol is for. Drawing the screens is :mod:`recreon.ui.newgame`.

``BEGINARTIFACTS`` / ``BEGINTRANSACTIONS`` / ``BEGINVICTORYCONDITIONS`` are
deliberately not ported: they are commented out of the dispatch in v2.0, so
the artifact scripting engine is unreachable dead code. This is why
``cdetypes.py`` has no caller.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .datacnst import MinTechForClass, TechDev, TriResByClass
from .environ import GameEnvironment
from .galaxy import XYCoord, limbo
from .intrface import (
    create_planet,
    create_stargate,
    get_optimum_indus,
    next_stargate_slot,
    scout,
)
from .misc import thg_lmt
from .primintr import (
    create_empire,
    empire_active,
    enemy_mine,
    get_nebula,
    get_object,
    put_cargo,
    put_defns,
    put_indus,
    put_mine,
    put_nebula,
    put_ships,
    put_trillum_reserves,
    set_capital,
    set_class,
    set_efficiency,
    set_population,
    set_special,
    set_status,
    set_tech,
    set_terraform_target,
    set_type,
)
from .types import (
    CARGO_TYPES,
    DEFNS_TYPES,
    MAX_NO_OF_PLANETS,
    MAX_NO_OF_STARBASES,
    PLAYER_EMPIRES,
    SHIP_TYPES,
    Empire,
    EmpireModifiers,
    IDNumber,
    NebulaTypes,
    ObjectTypes,
    TechLevel,
    TechnologyTypes,
    WorldClass,
    WorldTypes,
)
from .utils.dfa import TokenError, TokenReader
from .utils.int_utils import greater_int, rnd, rnd_var
from .utils.pascal import pascal_round, pascal_val, randomize, set_rand_seed, trunc

T = TechnologyTypes

MAX_NO_OF_XY_POINTS = 25
MAX_NO_OF_ZONES = 20

#: Military strength multipliers for randomly generated worlds, by tech level.
RndMilTechAdj: dict[TechLevel, float] = {
    TechLevel.PreTchLvl: 0.01,
    TechLevel.PrimitLvl: 0.02,
    TechLevel.PreAtmLvl: 0.04,
    TechLevel.AtomicLvl: 0.05,
    TechLevel.PreWrpLvl: 0.10,
    TechLevel.WrpTchLvl: 0.30,
    TechLevel.JmpTchLvl: 0.35,
    TechLevel.BioTchLvl: 0.60,
    TechLevel.StrTchLvl: 0.75,
    TechLevel.PreGteLvl: 0.95,
    TechLevel.GteTchLvl: 1.00,
}

#: Names an empire declared ``RndName`` draws from, transcribed from
#: ``RndEmpireName`` at NEWGAME.PAS:62. All 59, in the original's order --
#: ``GetRandomEmpireName`` indexes it with ``Rnd(1, 59)``, so the order is
#: load-bearing and the count doubly so.
#:
#: This comment used to say the table "is not in the source, so these are
#: authored", and 16 invented names stood here. It is in the source; every
#: `RndName` empire in every shipped scenario had been getting a name Anacreon
#: never used.
RND_EMPIRE_NAMES = (
    "Aaraavon", "Antramis", "Azores",
    "Bok", "Brekandi", "Byzantium",
    "Cal'Dulmas", "Cerberon", "Chulron",
    "Dol Parem", "Doramis", "Drii",
    "Earon", "Entares", "Esperance",
    "Fahron", "First Sun", "Freberon",
    "Geldtried", "Gen-Tarem", "Ghaza",
    "Haar", "Hasarem", "Highguard", "Horace",
    "Iileron", "Illissia",
    "Jamin", "Jasper", "Jool Den",
    "Kandii", "Kendrezani",
    "Lazarus", "Lililth",
    "Moorline", "Mu", "Mutara",
    "Ny", "N'zares",
    "Occem", "Ovaris",
    "Palanhoth", "Pell", "Pharo",
    "Quezelquan",
    "Rho Kandii", "Rosseri",
    "Sarlok", "Sol-Terra",
    "Terminus", "Terra", "Trantor",
    "Ultarion",
    "Vex", "Vlandis",
    "Whorl",
    "Xi",
    "Yew", "Yolandis",
)


#: The original's scenario menu is a fixed `ARRAY [1..MaxNoOfScenarios]`, so a
#: directory with more than 20 loadable `.SCN` files silently drops the rest.
#: Kept as a documented limit rather than enforced -- see :func:`get_scenarios`.
MAX_NO_OF_SCENARIOS = 20

#: Difficulty labels in the scenario menu, from ``DiffStr`` in ``GetScenarios``.
#: Padded to 14 in the original; the padding is applied at format time here.
DIFFICULTY_NAMES = ("Beginner", "Intermediate", "Advanced", "Expert")


class ScenarioError(Exception):
    """A scenario file could not be loaded."""


@dataclass(slots=True)
class Zone:
    """A rectangle things can be placed randomly within."""

    x1: int = 0
    y1: int = 0
    x2: int = 0
    y2: int = 0


@dataclass(slots=True)
class ScenarioHeader:
    """The fixed fields at the top of every scenario file."""

    version: int = 0
    title: str = ""
    seed: int = 0
    min_players: int = 1
    max_players: int = 8
    size_of_galaxy: int = 50
    no_of_planets: int = 0
    difficulty: int = 0
    min_length: int = 0
    max_length: int = 0
    first_year: int = 4021


@dataclass(slots=True)
class EmpireIdentity:
    """What ``InputEmpireName`` collects for one player empire.

    Three parallel arrays in the original -- ``EmpireName``, ``Password`` and
    ``Sex`` -- bundled, because they are always filled and read together. A
    new Python-level structure rather than a ported record, so snake_case.
    """

    name: str = ""
    password: str = ""
    #: ``Sex[Emp]`` in the original: False is an emperor, True an empress.
    is_empress: bool = False


class ScenarioAborted(Exception):
    """The player escaped out of the front end rather than starting a game.

    The original signals this by returning ``Indep`` from
    ``ScenarioIntroduction``'s player-count prompt, or by leaving the name
    blank, and unwinds to the prologue menu.
    """


class ScenarioFrontEnd:
    """What loading asks the player, between the header and the directives.

    Not a wrapper around :func:`load_scenario` but something it calls into,
    because the original interleaves the two: ``ScenarioIntroduction`` pages
    the intro text and asks for a player count, then ``InputEmpireName`` runs
    once per player, and only then does the directive loop start -- all in one
    forward pass over the open file. A front end that ran first would have to
    read the file twice and hope it parsed the same way both times.

    This base class is the non-interactive default: it answers from names
    supplied up front, which is what tests and ``--scenario`` on the command
    line want. :mod:`recreon.ui.newgame` has the Textual implementation.
    """

    def __init__(self, identities: dict[Empire, EmpireIdentity] | None = None) -> None:
        self.identities = dict(identities or {})

    def introduction(self, header: ScenarioHeader, pages: list[str]) -> None:
        """Show the intro. The original pages it with "press any key"."""

    def no_of_players(self, header: ScenarioHeader) -> int:
        """How many player empires to create.

        The original prompts only when the scenario allows a range; a fixed
        scenario just says "This is a scenario for N players" and waits for a
        keypress. Raise :class:`ScenarioAborted` for the Esc path.
        """
        if header.min_players < header.max_players and self.identities:
            return min(len(self.identities), header.max_players)
        return header.min_players

    def empire_identity(self, emp: Empire, taken: set[str]) -> EmpireIdentity:
        """Name, password and sex for one player empire.

        ``taken`` is the names already claimed, which the original uses to
        keep its suggestion distinct.
        """
        return self.identities.get(emp) or EmpireIdentity(
            name=f"Empire {int(emp) + 1}"
        )


@dataclass(slots=True)
class ScenarioEntry:
    """One `.SCN` in the scenario directory, as ``GetScenarios`` lists it."""

    path: Path
    header: ScenarioHeader

    @property
    def difficulty(self) -> str:
        names = DIFFICULTY_NAMES
        index = self.header.difficulty
        return names[index] if 0 <= index < len(names) else str(index)

    @property
    def players(self) -> str:
        """"3 Players" or "1-4 Players", as the menu column reads.

        The original pluralises on ``MaxPlay > 1``, so a scenario for exactly
        one player reads "1 Player" and a 1-4 scenario reads "1-4 Players".
        """
        low, high = self.header.min_players, self.header.max_players
        count = str(low) if low == high else f"{low}-{high}"
        return f"{count} Player" + ("s" if high > 1 else "")

    @property
    def duration(self) -> str:
        """"200-400 years", or "200+ years" when there is no upper bound."""
        low, high = self.header.min_length, self.header.max_length
        return f"{low}+ years" if high == 0 else f"{low}-{high} years"

    def menu_line(self) -> str:
        """The row ``GetScenarios`` builds, at the original's column widths.

        ``AdjustString`` pads with spaces or truncates to exactly the width,
        so a long title loses its tail rather than pushing the columns out.
        """
        title = _adjust(self.header.title, 23)
        difficulty = _adjust(self.difficulty, 14)
        players = _adjust(self.players, 11)
        return f"{title} {difficulty}{players} {self.duration}"


def _adjust(text: str, width: int) -> str:
    """Port of STRG.PAS ``AdjustString``: pad or truncate to exactly ``width``."""
    return text[:width].ljust(width)


def check_sum(path: str | Path) -> int:
    """Sum of every byte in a scenario file. Port of ``CheckSum``.

    **Unreachable in the retail build.** Its only call site sits inside
    ``{$IFDEF Demo}`` in ``LoadScenario``, where the demo refused to load
    anything whose sum was not 43171, 6792 or 44304 -- three shipped
    scenarios, so the demo would play those and nothing else.

    Ported because it is cheap and it documents what the demo did, not because
    anything calls it. It cannot be validated: no demo build survives, and
    which three scenarios those sums identify is not recorded. Turbo Pascal's
    ``Read`` on a text file also stops at a ``#26`` end-of-file marker, which
    a DOS-authored `.SCN` may carry and this does not emulate -- so treat a
    computed sum as indicative, not authoritative.
    """
    return sum(Path(path).read_bytes())


#: The three checksums the demo build accepted. See :func:`check_sum`.
DEMO_CHECKSUMS = (43171, 6792, 44304)


def read_scenario_intro(path: str | Path) -> tuple[ScenarioHeader, list[str]]:
    """The header and introduction pages, without executing any directive.

    The original never does this: it parses in one forward pass over an open
    file, so the intro is displayed as it is consumed and the directives run
    off the same handle. An event-driven UI cannot answer a question from
    inside that pass without blocking its own loop, so the front end reads
    this much first, asks what it needs, and then hands the answers to
    :func:`load_scenario` to make the real pass.

    Reading twice is safe because **neither the header nor the introduction
    touches the generator** -- ``run`` is what seeds it, from the scenario's
    own ``Seed`` -- so the galaxy this produces is the one a single pass would
    have produced.

    Raises :class:`ScenarioError` if either part is malformed.
    """
    loader = ScenarioLoader(game=GameEnvironment(), reader=TokenReader.from_path(path))

    loader.read_header()
    if loader.failed:
        raise ScenarioError("\n".join(loader.errors))

    pages = loader.read_introduction()
    if loader.failed:
        raise ScenarioError("\n".join(loader.errors))

    return loader.header, pages


def get_scenarios(directory: str | Path) -> list[ScenarioEntry]:
    """Every Anacreon scenario in ``directory``. Port of ``GetScenarios``.

    A file counts if its first line starts with ``ANACREON``; anything else in
    the directory is skipped silently, as the original's check does. Files
    whose header will not parse are skipped too -- the original would read
    garbage into its menu columns, but it also could not have been handed a
    directory of arbitrary files the way a modern install can.

    Sorted by filename, which the original gets for free from DOS's
    ``FindFirst``/``FindNext`` order and this does not.

    The original's menu is an ``ARRAY [1..20]`` filled without a bounds check,
    so a 21st scenario writes past it. That is not reproduced: the list is
    returned whole, and :data:`MAX_NO_OF_SCENARIOS` records the limit the
    window was sized for.
    """
    entries: list[ScenarioEntry] = []

    for path in sorted(Path(directory).glob("*.[sS][cC][nN]")):
        try:
            with path.open("r", encoding="latin-1") as handle:
                if not handle.readline().startswith("ANACREON"):
                    continue
        except OSError:
            continue

        loader = ScenarioLoader(game=GameEnvironment(), reader=TokenReader.from_path(path))
        loader.read_header()
        if loader.failed:
            continue

        entries.append(ScenarioEntry(path=path, header=loader.header))

    return entries


@dataclass
class ScenarioLoader:
    """Executes one scenario file against a game.

    Errors accumulate rather than raising immediately, matching the original's
    ``ScenarioError`` flag -- but loading stops at the first one, as the
    original's dispatch loop does.
    """

    game: GameEnvironment
    reader: TokenReader
    header: ScenarioHeader = field(default_factory=ScenarioHeader)
    errors: list[str] = field(default_factory=list)
    debug: bool = False

    zones: dict[int, Zone] = field(default_factory=dict)
    xy_points: dict[str, XYCoord] = field(default_factory=dict)
    class_table: list[WorldClass] = field(default_factory=list)
    tech_table: list[TechLevel] = field(default_factory=list)
    tri_res: int = 100
    first_world: int = 1
    first_base: int = 1
    no_of_players: Empire = Empire.Empire1
    player_identities: dict[Empire, EmpireIdentity] = field(default_factory=dict)
    empire_names: dict[Empire, str] = field(default_factory=dict)
    #: Pascal's ``NextEmpToCreate``: how many empires have been created so
    #: far. RANDOMIZEPLAYERS uses it as the first slot it is allowed to
    #: shuffle, so empires already placed are left where they are.
    next_empire_to_create: int = 0

    @property
    def failed(self) -> bool:
        return bool(self.errors)

    def error(self, message: str) -> None:
        self.errors.append(message)

    # --- Coordinates ---------------------------------------------------------

    def get_random_xy(
        self, x1: int, y1: int, x2: int, y2: int, check_world: bool
    ) -> XYCoord:
        """A random free sector in a rectangle.

        With ``check_world`` set, retries until it finds a sector that is
        empty, unmined and not dense nebula -- giving up after 100 tries, as
        the original does, rather than looping forever on a full zone.
        """
        count = 0
        while True:
            xy = XYCoord(rnd(x1, x2), rnd(y1, y2))
            count += 1
            if (
                not check_world
                or count > 100
                or (
                    get_object(self.game, xy).ObjTyp == ObjectTypes.Void
                    and enemy_mine(self.game, xy) == Empire.Indep
                    and get_nebula(self.game, xy) != NebulaTypes.DenseNebula
                )
            ):
                break

        if count > 100:
            # Note this fires on the 101st attempt even when that attempt
            # found a free sector -- the original tests the counter after the
            # loop, not the outcome. Kept: it is a generation path, and the
            # draw count has to match.
            self.error("ERROR: No room for random world in zone.")
            return limbo()
        return xy

    @staticmethod
    def _range(text: str) -> tuple[int, int]:
        """Parse ``n`` or ``lo..hi``. Unparseable input reads as 0, as in the
        original, rather than failing the load."""
        if ".." not in text:
            try:
                value = pascal_val(text)
            except ValueError:
                return 0, 0
            return value, value

        low_text, _, high_text = text.partition("..")
        try:
            low = pascal_val(low_text)
        except ValueError:
            return 0, 0
        try:
            return low, pascal_val(high_text)
        except ValueError:
            return 0, 0

    def next_xy(self, check_worlds: bool) -> XYCoord:
        """Read a coordinate in the scenario's coordinate mini-language.

        =================  ====================================================
        ``x,y``            absolute
        ``Z:n``            random point inside zone ``n``
        ``R:x1..x2,y1..y2``  random point in an absolute range
        ``name:dx,dy``     random point relative to a named XY point, where
                           each component may be a ``lo..hi`` range
        =================  ====================================================
        """
        try:
            token = self.reader.next_token()
        except TokenError as exc:
            self.error(str(exc))
            return limbo()

        comma = token.find(",")
        colon = token.find(":")
        header = token[:2].upper() if len(token) >= 2 else ""

        if header == "Z:":
            try:
                zone_number = pascal_val(token[2:])
            except ValueError:
                self.error(f'ERROR: Illegal zone coordinate "{token}"')
                return limbo()
            zone = self.zones.get(zone_number)
            if zone is None:
                self.error(f"ERROR: Zone {zone_number} not defined.")
                return limbo()
            return self.get_random_xy(zone.x1, zone.y1, zone.x2, zone.y2, check_worlds)

        if header == "R:":
            x1, x2 = self._range(token[2:comma])
            y1, y2 = self._range(token[comma + 1 :])
            if self.game.Galaxy.in_galaxy(x1, y1) and self.game.Galaxy.in_galaxy(x2, y2):
                return self.get_random_xy(x1, y1, x2, y2, check_worlds)
            self.error(f'ERROR: Illegal random coordinates "{token}"')
            return limbo()

        if colon != -1:
            x1, x2 = self._range(token[colon + 1 : comma])
            y1, y2 = self._range(token[comma + 1 :])
            name = token[:colon].upper()
            point = self.xy_points.get(name)
            if point is None:
                self.error(f'ERROR: XYPoint not found "{name}"')
                return limbo()

            x1, x2 = point.x + x1, point.x + x2
            y1, y2 = point.y + y1, point.y + y2
            if self.game.Galaxy.in_galaxy(x1, y1) and self.game.Galaxy.in_galaxy(x2, y2):
                return self.get_random_xy(x1, y1, x2, y2, check_worlds)
            self.error("ERROR: Relative coordinates outside of galaxy.")
            return limbo()

        if comma != -1:
            try:
                x, y = pascal_val(token[:comma]), pascal_val(token[comma + 1 :])
            except ValueError:
                self.error(f'ERROR: Illegal coordinate "{token}"')
                return limbo()
            if self.game.Galaxy.in_galaxy(x, y):
                return XYCoord(x, y)
            self.error("ERROR: Absolute coordinates outside of galaxy.")
            return limbo()

        self.error(f'ERROR: Illegal coordinate "{token}"')
        return limbo()

    # --- World setup ---------------------------------------------------------

    def _rnd_group(
        self, amounts: dict[T, int], tech: TechLevel, variation: int, check_tech: bool
    ) -> dict[T, int]:
        """Apply +/- variation to each amount, zeroing what the tech forbids."""
        result = {}
        for thing, amount in amounts.items():
            value = thg_lmt(rnd_var(amount, variation))
            if check_tech and thing not in TechDev[tech]:
                value = 0
            result[thing] = value
        return result

    def set_up_world(
        self,
        world: IDNumber,
        cls: WorldClass,
        tech: TechLevel,
        typ: WorldTypes,
        emp: Empire,
        pop: int,
        eff: int,
        special: set,
        ships: dict[T, int],
        cargo: dict[T, int],
        defns: dict[T, int],
        check_tech: bool,
    ) -> None:
        """Fill in a world's attributes and starting stock."""
        set_class(self.game, world, cls)
        set_tech(self.game, world, tech)
        set_type(self.game, world, typ)
        set_status(self.game, world, emp)
        set_population(self.game, world, pop)
        set_efficiency(self.game, world, eff)
        set_special(self.game, world, special)

        from .primintr import get_coord

        scout(self.game, emp, get_coord(self.game, world))

        put_indus(self.game, world, get_optimum_indus(self.game, world))
        put_ships(self.game, world, self._rnd_group(ships, tech, 20, check_tech))
        put_cargo(self.game, world, self._rnd_group(cargo, tech, 20, check_tech))
        put_defns(self.game, world, self._rnd_group(defns, tech, 20, check_tech))

    @staticmethod
    def random_trillum_reserves(cls: WorldClass, region_reserves: int) -> int:
        temp = greater_int(region_reserves + rnd(-25, 25), 0)
        return pascal_round(temp * (TriResByClass[cls] / 100) + rnd(1, 100))

    def create_rnd_planet(
        self, obj: IDNumber, coord: XYCoord, cls: WorldClass, tech: TechLevel
    ) -> None:
        """An independent world with stock scaled to its tech level."""
        create_planet(self.game, obj, coord)
        if cls == WorldClass.TerCls:
            set_terraform_target(self.game, obj, WorldClass.EthCls)

        eff = rnd(40, 60)
        from .datacnst import BasePop

        pop = rnd_var(trunc((1 + (eff - 50) / 500) * BasePop[tech]), 10)

        # Three rolls rather than one, so military strength clusters toward
        # the middle instead of being flat.
        mi = rnd(1, 33) + rnd(1, 34) + rnd(1, 33)
        mi = pascal_round(mi * RndMilTechAdj[tech])

        self.set_up_world(
            obj,
            cls,
            tech,
            WorldTypes.IndTyp,
            Empire.Indep,
            pop,
            eff,
            set(),
            ships=dict(
                zip(SHIP_TYPES, (80 * mi, 7 * mi, 10 * mi, 6 * mi, 4 * mi, mi, 30 * mi), strict=True)
            ),
            cargo=dict(
                zip(CARGO_TYPES, (40 * mi, 0, 0, 30 * mi, 50 * mi, 25 * mi, 10 * mi), strict=True)
            ),
            defns=dict(zip(DEFNS_TYPES, (0, 30 * mi, 50 * mi, 40 * mi), strict=True)),
            check_tech=True,
        )

        if cls == WorldClass.TerCls:
            set_terraform_target(self.game, obj, WorldClass.EthCls)

    # --- Directives ----------------------------------------------------------

    def _read_amounts(self, keys) -> dict[T, int]:
        return {key: self.reader.next_integer() for key in keys}

    def do_class_table(self) -> None:
        """A 100-entry weighted table of world classes, given as percentages.

        Terraforming was not a class before format version 14, so older files
        omit its weight.
        """
        table: list[WorldClass] = []
        for cls in WorldClass:
            if self.header.version <= 13 and cls == WorldClass.TerCls:
                continue
            table.extend([cls] * self.reader.next_integer())

        if len(table) != 100:
            self.error("ERROR: Class table probabilities do not add up to 100.")
        self.class_table = table

    def do_tech_table(self) -> None:
        table: list[TechLevel] = []
        for tech in TechLevel:
            table.extend([tech] * self.reader.next_integer())

        if len(table) != 100:
            self.error("ERROR: Tech table probabilities do not add up to 100.")
        self.tech_table = table

    def do_set_trillum_reserves(self) -> None:
        self.tri_res = self.reader.next_integer()
        if not 0 <= self.tri_res <= 100:
            self.error("ERROR: Illegal trillum reserve setting.")

    def do_define_zone(self) -> None:
        number = self.reader.next_integer()
        xy1 = self.next_xy(False)
        xy2 = self.next_xy(False)
        self.zones[number] = Zone(xy1.x, xy1.y, xy2.x, xy2.y)

    def do_define_xy(self) -> None:
        if len(self.xy_points) >= MAX_NO_OF_XY_POINTS:
            self.error("ERROR: Too many XYPoints defined.")
            return
        name = self.reader.next_token().upper()
        self.xy_points[name] = self.next_xy(False)

    def do_create_world(self) -> None:
        self.reader.next_integer()  # world number, informational in the original
        xy = self.next_xy(True)

        cls_index = self.reader.next_integer()
        # Terraforming was inserted into WorldClass at 20, shifting everything
        # above it, so pre-14 files need their class indices nudged.
        if self.header.version < 14 and cls_index >= 20:
            cls_index += 1

        tech = TechLevel(self.reader.next_integer())
        typ_index = self.reader.next_integer()
        emp_index = self.reader.next_integer()
        pop = self.reader.next_integer()
        eff = self.reader.next_integer()
        tri_res = self.reader.next_integer() if self.header.version >= 12 else 100

        defns = self._read_amounts(DEFNS_TYPES)
        ships = self._read_amounts(SHIP_TYPES)
        cargo = self._read_amounts(CARGO_TYPES)

        if self.first_world > MAX_NO_OF_PLANETS:
            self.error(
                f"ERROR: Too many worlds created (limit {MAX_NO_OF_PLANETS})."
            )
            return
        obj = IDNumber(ObjectTypes.Pln, self.first_world)
        self.first_world += 1

        emp = Empire(emp_index)
        typ = WorldTypes(typ_index)
        # A world assigned to an empire that was never created falls back to
        # independent rather than dangling.
        if emp != Empire.Indep and not empire_active(self.game, emp):
            emp = Empire.Indep
            typ = WorldTypes.IndTyp

        cls = WorldClass(cls_index)
        create_planet(self.game, obj, xy)
        self.set_up_world(
            obj, cls, tech, typ, emp, rnd_var(pop, 15), eff, set(),
            ships, cargo, defns, check_tech=False,
        )
        put_trillum_reserves(
            self.game, obj, self.random_trillum_reserves(cls, tri_res)
        )

        if typ == WorldTypes.CapTyp:
            set_capital(self.game, emp, obj)

        self.game.NoOfPlanets = max(self.game.NoOfPlanets, obj.Index)

    def do_create_starbase(self) -> None:
        self.reader.next_integer()  # base number, informational
        xy = self.next_xy(True)

        base_type = TechnologyTypes(self.reader.next_integer())
        tech = TechLevel(self.reader.next_integer())
        typ_index = self.reader.next_integer()
        emp = Empire(self.reader.next_integer())
        pop = self.reader.next_integer()
        eff = self.reader.next_integer()

        defns = self._read_amounts(DEFNS_TYPES)
        ships = self._read_amounts(SHIP_TYPES)
        cargo = self._read_amounts(CARGO_TYPES)

        # The base kind dictates the world type for outposts and forts.
        if base_type == T.out:
            typ = WorldTypes.OutTyp
        elif base_type in (T.cmm, T.frt):
            typ = WorldTypes.BseTyp
        else:
            typ = WorldTypes(typ_index)

        if emp != Empire.Indep and not empire_active(self.game, emp):
            return
        if self.first_base > MAX_NO_OF_STARBASES:
            self.error("ERROR: Too many starbases created.")
            return

        from .intrface import create_starbase

        obj = IDNumber(ObjectTypes.Base, self.first_base)
        self.first_base += 1
        create_starbase(self.game, obj, emp, xy, base_type)
        self.set_up_world(
            obj, WorldClass.ArtCls, tech, typ, emp, rnd_var(pop, 15), eff, set(),
            ships, cargo, defns, check_tech=False,
        )

        if typ == WorldTypes.CapTyp:
            set_capital(self.game, emp, obj)

    def do_create_stargate(self) -> None:
        xy = self.next_xy(True)
        gate_type = TechnologyTypes(self.reader.next_integer())
        emp = Empire(self.reader.next_integer())

        slot = next_stargate_slot(self.game)
        if slot <= 0:
            self.error("ERROR: Too many stargates created.")
            return
        create_stargate(self.game, IDNumber(ObjectTypes.Gate, slot), emp, gate_type, xy)

    def do_create_random_worlds(self) -> None:
        count = self.reader.next_integer()
        zone_number = self.reader.next_integer()
        zone = self.zones.get(zone_number)
        if zone is None:
            self.error(f"ERROR: Zone {zone_number} not defined.")
            return
        if not self.class_table or not self.tech_table:
            self.error("ERROR: CreateRandomWorlds before ClassTable/TechTable.")
            return

        if self.first_world + count - 1 > MAX_NO_OF_PLANETS:
            # The original has no such check and writes past the planet array;
            # AWAKEN.SCN asks for 212 worlds against a limit of 200 and would
            # have corrupted memory in the DOS build. Reported rather than
            # silently truncated, following how the original handles the same
            # situation for starbases and stargates.
            self.error(
                f"ERROR: Too many worlds created (limit {MAX_NO_OF_PLANETS})."
            )
            return

        for index in range(self.first_world, self.first_world + count):
            coord = self.get_random_xy(zone.x1, zone.y1, zone.x2, zone.y2, True)

            # Reroll until the tech level can actually sustain the class.
            for safety in range(101):
                cls = self.class_table[rnd(1, 100) - 1]
                tech = self.tech_table[rnd(1, 100) - 1]
                if tech >= MinTechForClass[cls]:
                    break
            else:
                self.error("ERROR: Incompatible class and tech tables.")
                return

            obj = IDNumber(ObjectTypes.Pln, index)
            self.create_rnd_planet(obj, coord, cls, tech)
            put_trillum_reserves(
                self.game, obj, self.random_trillum_reserves(cls, self.tri_res)
            )
            self.game.NoOfPlanets = max(self.game.NoOfPlanets, index)

        self.first_world += count

    def _read_modifier_list(self) -> set[EmpireModifiers]:
        modifiers: set[EmpireModifiers] = set()
        if self.header.version < 12:
            return modifiers
        for _ in range(self.reader.next_integer()):
            if self.reader.next_token().upper() == "CENTRAL":
                modifiers.add(EmpireModifiers.CentralEMD)
        return modifiers

    def _read_known_techs(self, tech: TechLevel) -> set[T]:
        """An empire starts with everything one level below its own, plus any
        extras the scenario lists, intersected with what its level allows."""
        below = TechLevel(max(0, int(tech) - 1))
        known = set(TechDev[below])
        for _ in range(self.reader.next_integer()):
            known.add(TechnologyTypes(self.reader.next_integer()))
        return known & set(TechDev[tech])

    def do_create_player_empire(self) -> None:
        emp = Empire(self.reader.next_integer())
        rev_factor = self.reader.next_integer()
        tech = TechLevel(self.reader.next_integer())
        known = self._read_known_techs(tech)
        modifiers = self._read_modifier_list()

        identity = self.player_identities.get(emp)
        if not identity or not identity.name:
            # The original skips empires the player did not name, which is how
            # a scenario supports fewer players than it defines.
            return

        # No Rnd here, unlike CreateNPEmpire: a player's sex comes from
        # InputEmpireName, so the original makes no draw at this point. Rolling
        # one would consume a step of the LCG the original never consumes and
        # shift every draw in the rest of the scenario.
        create_empire(
            self.game, emp, is_player=True, is_empress=identity.is_empress,
            name=identity.name, password=identity.password, tech=tech,
            tech_set=known, rev_factor=rev_factor, modifiers=modifiers,
            year_founded=self.game.Year,
        )
        self.empire_names[emp] = identity.name
        self.next_empire_to_create += 1

    def do_create_np_empire(self) -> None:
        emp = Empire(self.reader.next_integer())
        npe_type = self.reader.next_integer()
        name = self.reader.next_token()
        rev_factor = self.reader.next_integer()
        tech = TechLevel(self.reader.next_integer())
        known = self._read_known_techs(tech)
        modifiers = self._read_modifier_list()

        if empire_active(self.game, emp):
            return

        if name == "RndName":
            name = self._random_empire_name()

        create_empire(
            self.game, emp, is_player=False, is_empress=bool(rnd(0, 1)),
            name=name, password="", tech=tech, tech_set=known,
            rev_factor=rev_factor, modifiers=modifiers, year_founded=self.game.Year,
        )
        # InitializeNPE sits between CreateEmpire and Inc(NextEmp) in the
        # original (NEWGAME.PAS:1278). It rolls the persona and the empire's
        # defense distribution, so it draws from the generator here -- moving
        # it would desynchronise every draw after it.
        from .npe.dispatch import initialize_npe
        from .npe.types import NPEmpireTypes

        initialize_npe(self.game, emp, NPEmpireTypes(npe_type))

        self.empire_names[emp] = name
        self.next_empire_to_create += 1

    def _random_empire_name(self) -> str:
        """An unused name from the table. Port of ``GetRandomEmpireName``.

        Rolls ``Rnd(1, 59)`` and rejects a name already in use, rather than
        drawing once from a filtered list. The distinction is not cosmetic:
        a filtered draw calls ``Rnd`` with a smaller bound and calls it exactly
        once, so both the value and the *number of draws* differ from the
        original the moment two empires collide -- and every draw after it in
        the whole scenario shifts. With 59 names and at most 8 empires a
        collision is likelier than not over a full galaxy.

        Cannot spin: there are 59 names and never more than 8 empires, which
        is why the original has no escape either.
        """
        taken = set(self.empire_names.values())
        while True:
            name = RND_EMPIRE_NAMES[rnd(1, len(RND_EMPIRE_NAMES)) - 1]
            if name not in taken:
                return name

    def do_create_nebula(self) -> None:
        neb_type = NebulaTypes(self.reader.next_integer())
        upper_left = self.next_xy(False)
        lower_right = self.next_xy(False)
        for x in range(upper_left.x, lower_right.x + 1):
            for y in range(upper_left.y, lower_right.y + 1):
                if self.game.Galaxy.in_galaxy(x, y):
                    put_nebula(self.game, XYCoord(x, y), neb_type)

    def do_create_random_nebula(self) -> None:
        kind = self.reader.next_integer()
        low = self.reader.next_integer()
        high = self.reader.next_integer()
        if kind == 1:
            self._nebulae_band()
        elif kind == 2:
            self._nebulae_patches(rnd(low, high))

    def _nebulae_band(self) -> None:
        """A ragged strip running top to bottom, tilting left or right.

        Bands starting near an edge tilt away from it, so they stay on the map.
        """
        size = self.game.Galaxy.size
        init_x = rnd(1, size)

        if init_x <= size // 4:
            x_disp = rnd(0, 3)
        elif init_x >= size * 3 // 4:
            x_disp = rnd(-3, 0)
        else:
            x_disp = rnd(-3, 3)

        start_x = init_x
        for y in range(1, size + 1):
            for x in range(start_x - rnd(1, 5), start_x + rnd(1, 5) + 1):
                if self.game.Galaxy.in_galaxy(x, y):
                    put_nebula(self.game, XYCoord(x, y), NebulaTypes.Nebula)
            start_x += x_disp

    def _nebulae_patches(self, count: int) -> None:
        """Roughly circular blobs -- the x-spread narrows with distance from
        the centre row."""
        size = self.game.Galaxy.size
        for _ in range(count):
            init_x = rnd(1, size)
            init_y = rnd(1, size)
            for y in range(init_y - rnd(1, 3), init_y + rnd(1, 3) + 1):
                spread = 4 - abs(y - init_y)
                if spread < 1:
                    continue
                for x in range(init_x - rnd(1, spread), init_x + rnd(1, spread) + 1):
                    if self.game.Galaxy.in_galaxy(x, y):
                        put_nebula(self.game, XYCoord(x, y), NebulaTypes.Nebula)

    def do_create_srms(self) -> None:
        emp = Empire(self.reader.next_integer())
        upper_left = self.next_xy(False)
        lower_right = self.next_xy(False)
        for x in range(upper_left.x, lower_right.x + 1):
            for y in range(upper_left.y, lower_right.y + 1):
                if not self.game.Galaxy.in_galaxy(x, y):
                    continue
                xy = XYCoord(x, y)
                # Minefields only go in empty sectors.
                if get_object(self.game, xy).ObjTyp == ObjectTypes.Void:
                    put_mine(self.game, xy, emp)

    def do_randomize_players(self) -> None:
        """Shuffle which empire slot each player occupies.

        Built by rejection sampling -- draw a slot, redraw while it collides
        with one already taken -- rather than by a shuffle. That is not an
        arbitrary choice: it consumes a specific, input-dependent number of
        RNG draws, and every later draw in the scenario shifts with it. A
        Fisher-Yates shuffle would give a valid permutation and the wrong
        galaxy.
        """
        first = self.next_empire_to_create
        last = self.header.max_players - 1
        if first >= last:
            return

        order: dict[int, int] = {first: rnd(first, last)}
        for i in range(first + 1, last + 1):
            while True:
                order[i] = rnd(first, last)
                if all(order[j] != order[i] for j in range(first, i)):
                    break

        # The original permutes EmpNames, Passes and Sexes in step, so a
        # player's password and sex follow their name into the new slot. One
        # identity per empire makes that automatic.
        was = dict(self.player_identities)
        for i in range(first, last + 1):
            src = PLAYER_EMPIRES[order[i]]
            self.player_identities[PLAYER_EMPIRES[i]] = was.get(src, EmpireIdentity())

    def _skip_until(self, marker: str) -> None:
        while True:
            line = self.reader.read_line()
            if marker in line.upper():
                return
            if self.reader.at_eof:
                self.error(f"ERROR: {marker.title()} not found.")
                return

    # --- Dispatch ------------------------------------------------------------

    def read_header(self) -> None:
        version_line = self.reader.read_line()
        # The version sits at a fixed offset -- `Copy(Vers, 10, 2)`, so
        # 1-based columns 10-11. The two characters must both be digits:
        # Python's int() would strip surrounding whitespace where Pascal's
        # Val errors, and a header off by one column would otherwise parse as
        # some low version and silently enable the old-format shims, which
        # desyncs every directive after it.
        raw_version = version_line[9:11]
        if not raw_version.isdigit():
            self.error(
                f'ERROR: No version at columns 10-11 of "{version_line}" '
                f"(found {raw_version!r})"
            )
            return
        self.header.version = pascal_val(raw_version)

        h = self.header
        h.title = self.reader.next_token()
        h.seed = self.reader.next_integer()
        h.min_players = self.reader.next_integer()
        h.max_players = self.reader.next_integer()
        h.size_of_galaxy = self.reader.next_integer()
        h.no_of_planets = self.reader.next_integer()
        h.difficulty = self.reader.next_integer()
        h.min_length = self.reader.next_integer()
        h.max_length = self.reader.next_integer()
        h.first_year = self.reader.next_integer()

    def read_introduction(self) -> list[str]:
        """Consume the scenario's introduction, returning its pages of text.

        Port of ``ScenarioIntroduction``, minus the interactive paging. It
        runs between the header and the directive loop, in the same single
        forward pass over the file, and does two things:

        * **Discards every token until ``BEGINTEXT``.** This is why scenarios
          can carry scratch between the header and the intro -- Nebula.SCN has
          a ``1234567890...`` column ruler there -- without the directive
          dispatch ever seeing it.
        * **Reads lines until ``ENDTEXT``**, with ``NEWPAGE`` splitting pages.
          Both are matched as substrings of the line, not as tokens, so a line
          merely containing the word ends the page.

        Every scenario the game shipped has exactly one ``BEGINTEXT``; a file
        without one runs this scan to EOF and fails, exactly as the original
        would.
        """
        while True:
            token = self.reader.next_token().upper()
            if token == "BEGINTEXT":
                break
            if self.reader.at_eof:
                self.error("ERROR: BEGINTEXT not found.")
                return []

        # The original follows the scan with an unconditional ReadLn to drop
        # anything trailing BEGINTEXT on its line. Here the tokenizer has
        # usually consumed the newline already, so this has to be conditional
        # or it swallows the intro's first line.
        if not self.reader.at_line_start:
            self.reader.read_line()

        pages: list[str] = []
        page: list[str] = []
        while True:
            line = self.reader.read_line()
            upper = line.upper()
            if "ENDTEXT" in upper:
                pages.append("\n".join(page))
                return pages
            if "NEWPAGE" in upper:
                pages.append("\n".join(page))
                page = []
                continue
            if self.reader.at_eof:
                self.error("ERROR: ENDTEXT not found.")
                return pages
            page.append(line)

    def run(self) -> None:
        """Execute directives until ENDSCENARIO, EOF or the first error."""
        # Zone 1 defaults to the whole galaxy.
        size = self.header.size_of_galaxy
        self.zones[1] = Zone(1, 1, size, size)

        # A non-zero seed makes the galaxy reproducible, and reproducible the
        # same way the DOS build was: `rnd` runs on Turbo Pascal's own
        # generator, so a seeded scenario regenerates the galaxy players saw.
        if self.header.seed != 0:
            set_rand_seed(self.header.seed)
        else:
            randomize()

        handlers = {
            "CLASSTABLE": self.do_class_table,
            "TECHTABLE": self.do_tech_table,
            "SETTRILLUMRESERVES": self.do_set_trillum_reserves,
            "DEFINEZONE": self.do_define_zone,
            "DEFINEXY": self.do_define_xy,
            "CREATEWORLD": self.do_create_world,
            "CREATERANDOMWORLDS": self.do_create_random_worlds,
            "CREATESTARBASE": self.do_create_starbase,
            "CREATESTARGATE": self.do_create_stargate,
            "CREATEPLAYEREMPIRE": self.do_create_player_empire,
            "CREATENPEMPIRE": self.do_create_np_empire,
            "CREATENEBULA": self.do_create_nebula,
            "CREATERANDOMNEBULA": self.do_create_random_nebula,
            "CREATESRMS": self.do_create_srms,
            "RANDOMIZEPLAYERS": self.do_randomize_players,
            "BEGINDESCRIPTION": lambda: self._skip_until("ENDDESCRIPTION"),
            "BEGINTEXT": lambda: self._skip_until("ENDTEXT"),
            "REPORT": self.reader.next_token,
            "PAUSE": lambda: None,
            "DEBUGSCENARIO": self._enable_debug,
        }

        while not self.failed:
            try:
                directive = self.reader.next_token().upper()
            except TokenError as exc:
                self.error(str(exc))
                return

            if directive == "ENDSCENARIO":
                return

            handler = handlers.get(directive)
            if handler is None:
                self.error(f'ERROR: Unknown command "{directive}"')
                return

            try:
                handler()
            except TokenError as exc:
                self.error(str(exc))
                return
            except (ValueError, KeyError) as exc:
                self.error(f"ERROR: {directive}: {exc}")
                return

    def _enable_debug(self) -> None:
        self.debug = True


def load_scenario(
    path: str | Path,
    player_names: dict[Empire, str] | None = None,
    game: GameEnvironment | None = None,
    front_end: ScenarioFrontEnd | None = None,
) -> GameEnvironment:
    """Build a game from a scenario file. Port of ``LoadScenario``.

    ``player_names`` maps empire slots to the names their players chose;
    ``CREATEPLAYEREMPIRE`` skips any slot with no name, which is how a
    scenario supports fewer players than it defines.

    ``front_end`` is asked for the player count and the empire identities at
    the point the original asks -- after the introduction, before the first
    directive. Passing both is allowed: the names seed the default front end.

    Raises :class:`ScenarioError` if the file is malformed, and lets
    :class:`ScenarioAborted` through if the player backs out.
    """
    game = game or GameEnvironment()
    reader = TokenReader.from_path(path)

    if front_end is None:
        names = player_names or {Empire.Empire1: "Player"}
        front_end = ScenarioFrontEnd(
            {emp: EmpireIdentity(name=name) for emp, name in names.items()}
        )

    loader = ScenarioLoader(game=game, reader=reader)

    loader.read_header()
    if loader.failed:
        raise ScenarioError("\n".join(loader.errors))

    game.initialize_universe(
        starting_year=loader.header.first_year,
        size=loader.header.size_of_galaxy,
        planets=loader.header.no_of_planets,
    )
    # initialize_universe resets NoOfPlanets; the directives grow it as they
    # place worlds, and the header value is only an upper bound.
    game.NoOfPlanets = 0

    # ENVIRON.PAS keeps the scenario a game came from, and save/load carries
    # it. Set after initialize_universe, which does not clear it but would be
    # the wrong order to rely on.
    game.ScenaFilename = str(path)

    # The introduction is consumed here, in the same forward pass, and shown
    # before anything is asked -- the intro is what the player decides on.
    game.ScenarioIntroduction = loader.read_introduction()
    if loader.failed:
        raise ScenarioError("\n".join(loader.errors))

    front_end.introduction(loader.header, game.ScenarioIntroduction)

    count = front_end.no_of_players(loader.header)
    count = max(loader.header.min_players, min(count, loader.header.max_players))
    loader.no_of_players = Empire(count - 1)

    # InputEmpireName runs once per player, in slot order, before any
    # directive is executed. `taken` is the running set the original keeps so
    # its suggestion never repeats a name already chosen.
    taken: set[str] = set()
    for i in range(count):
        emp = PLAYER_EMPIRES[i]
        identity = front_end.empire_identity(emp, taken)
        loader.player_identities[emp] = identity
        if identity.name:
            taken.add(identity.name)

    loader.run()
    if loader.failed:
        raise ScenarioError("\n".join(loader.errors))

    game.Player = Empire.Empire1
    game.reset_empires_to_move()
    return game


def start_new_game(
    directory: str | Path,
    scenario: ScenarioEntry,
    front_end: ScenarioFrontEnd | None = None,
    game: GameEnvironment | None = None,
) -> GameEnvironment:
    """Load the chosen scenario. The tail of ``StartNewGame``.

    The original loops -- list scenarios, pick one, load it, and go round
    again if loading was escaped out of -- with the menu inline. The listing
    and the picking are the UI's (:mod:`recreon.ui.newgame`); this is the part
    that happens once a choice is made, and it sets ``ScenaFilename`` to the
    bare filename the way ``StartNewGame`` does rather than the full path.
    """
    game = load_scenario(scenario.path, game=game, front_end=front_end)
    game.ScenaFilename = scenario.path.name
    game.SceDirect = str(directory)
    return game
