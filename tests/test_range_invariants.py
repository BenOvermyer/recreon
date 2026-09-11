"""Play real scenarios for centuries and watch for values the Pascal could not hold.

Phase 9 §9.3 asks for the port's numbers to be validated against the original's.
Tables can be compared directly (`test_pascal_tables.py`); **formulas cannot**,
short of re-deriving each one by hand, which is what the translation already
did. This is a different lever on the same question.

Turbo Pascal's declarations bound what a field can contain, and the bounds come
in two strengths that are worth keeping apart:

**Storage.** `Resources = 0..9999` needs 16 bits, so Turbo Pascal allocates a
Word and the field holds 0..65535 without complaint. `Index = 0..100` gets a
Byte: 0..255. Range checking is off, so nothing raises -- but a value past the
*width* wraps. If a field here exceeds it, the port is carrying a number the
DOS build physically could not, and behaviour has already diverged.

**The declared subrange.** `0..9999` itself is enforced by `ThgLmt` and friends
in code, not by the type. Exceeding it is not proof of a bug, but it means some
path skipped a clamp the original applies -- a lead worth following.

**And negatives.** Every one of these fields is unsigned in the Pascal. A
negative here is the signature of the whole bug class Phase 9 hunts: Python
going below zero where the original wrapped or clamped. This is what would have
caught #29 (a troop load underflowing to a huge number) had it existed then.

None of the three fires today, across four shipped scenarios and roughly a
thousand simulated years. That is the result; the value is that it keeps
holding.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from recreon.main import set_up_turn, update_turn
from recreon.newgame import ScenarioError, load_scenario
from recreon.types import Empire
from recreon.utils.pascal import set_rand_seed

SCENARIOS = Path(__file__).resolve().parents[1] / "original" / "scenarios"

#: field -> (declared subrange top, storage width top). From TYPES.PAS:
#: `Resources`/`Population` are 0..9999 in a Word, `Index` 0..100 in a Byte,
#: `IndusIndex` 0..999 in a Word, `TriReserve` a bare Word.
SCALAR_BOUNDS = {
    "Pop": (9999, 65535),
    "Eff": (100, 255),
    "RevIndex": (100, 255),
    "TriReserve": (65535, 65535),
}

ARRAY_BOUNDS = {
    "Ships": (9999, 65535),
    "Cargo": (9999, 65535),
    "Defns": (9999, 65535),
    "Indus": (999, 65535),
}


class Violations:
    """What escaped, and how far. Collected rather than asserted per-field so
    a failure names every offender instead of the first one."""

    def __init__(self) -> None:
        self.negative: list[str] = []
        self.over_declared: list[str] = []
        self.over_storage: list[str] = []

    def check(self, where: str, record) -> None:
        for field, (declared, storage) in SCALAR_BOUNDS.items():
            if not hasattr(record, field):
                continue
            self._one(f"{where}.{field}", getattr(record, field), declared, storage)

        for field, (declared, storage) in ARRAY_BOUNDS.items():
            table = getattr(record, field, None)
            if table is None:
                continue
            for key, value in table.items():
                self._one(f"{where}.{field}[{key.name}]", value, declared, storage)

    def _one(self, tag: str, value: int, declared: int, storage: int) -> None:
        if value < 0:
            self.negative.append(f"{tag} = {value}")
        elif value > storage:
            self.over_storage.append(f"{tag} = {value} (width {storage})")
        elif value > declared:
            self.over_declared.append(f"{tag} = {value} (declared {declared})")

    def sweep(self, game) -> None:
        for i in range(1, game.NoOfPlanets + 1):
            self.check(f"Planet[{i}]", game.Universe.Planet[i])
        for i in sorted(game.GlobalSets.SetOfActiveStarbases):
            self.check(f"Starbase[{i}]", game.Universe.Starbase[i])
        for i in sorted(game.GlobalSets.SetOfActiveFleets):
            self.check(f"Fleet[{i}]", game.Universe.Fleet[i])


def _total_ships(game) -> int:
    """Every hull in the galaxy. Ownership change is scenario-dependent --
    `JAKARTA` holds at three worlds for centuries -- but production is not, so
    this is the progress signal that works everywhere."""
    total = 0
    for i in range(1, game.NoOfPlanets + 1):
        total += sum(game.Universe.Planet[i].Ships.values())
    for i in sorted(game.GlobalSets.SetOfActiveStarbases):
        total += sum(game.Universe.Starbase[i].Ships.values())
    for i in sorted(game.GlobalSets.SetOfActiveFleets):
        total += sum(game.Universe.Fleet[i].Ships.values())
    return total


def play(name: str, turns: int):
    """Load a shipped scenario and run it, checking every record every turn.

    Returns the violations alongside a before/after ship count, because a
    galaxy where nothing happens satisfies every bound trivially and would make
    these tests pass for the wrong reason.
    """
    set_rand_seed(4021)
    try:
        game = load_scenario(SCENARIOS / name, {Empire.Empire1: "A"})
    except ScenarioError as exc:  # pragma: no cover -- see GAUNTLET below
        pytest.skip(f"{name} did not load: {exc}")

    before = _total_ships(game)
    found = Violations()
    for _ in range(turns):
        set_up_turn(game, game.Player)
        update_turn(game)
        found.sweep(game)
    return found, game, before, _total_ships(game)


#: Four of the eleven that load, chosen for coverage rather than count:
#: `INTRO` is small and quiet, `ARRONAX` has eight empires and starbases,
#: `EASTWEST` is two large symmetric empires, `JAKARTA` has independents worth
#: attacking. `GAUNTLET` is left out on purpose -- it fails to load about 8% of
#: the time by design (see AGENTS.md), and a flaky invariant test is worse than
#: a narrower one.
@pytest.mark.parametrize(
    "scenario,turns",
    [
        ("INTRO.SCN", 200),
        ("ARRONAX.SCN", 150),
        ("EASTWEST.SCN", 150),
        ("JAKARTA.SCN", 150),
    ],
)
def test_no_field_leaves_the_range_the_pascal_could_hold(scenario, turns):
    found, game, before, after = play(scenario, turns)

    # A galaxy where nothing happens satisfies every bound trivially, so
    # establish that centuries actually passed and empires actually moved
    # before reading anything into the bounds holding.
    assert game.Year > 0
    assert after > before, f"{scenario}: the galaxy should have built ships"

    assert found.negative == [], (
        "an unsigned Pascal field went negative -- this is the shape of #29 "
        "and #27, where Python goes below zero and the original wraps"
    )
    assert found.over_storage == [], (
        "a field exceeded the width Turbo Pascal allocated, so the DOS build "
        "would have wrapped here and the port has already diverged"
    )
    assert found.over_declared == [], (
        "a field exceeded its declared subrange, so some path skipped a "
        "ThgLmt the original applies"
    )


def test_the_sweep_would_notice_a_violation():
    """The invariant tests above pass, so they need to be shown to be capable
    of failing -- otherwise a broken sweep reads exactly like a clean run."""
    from recreon.datastrc import PlanetRecord

    found = Violations()

    record = PlanetRecord()
    record.Pop = -1
    found.check("Planet[1]", record)
    assert found.negative == ["Planet[1].Pop = -1"]

    record = PlanetRecord()
    record.Eff = 120
    found.check("Planet[2]", record)
    assert found.over_declared == ["Planet[2].Eff = 120 (declared 100)"]

    record = PlanetRecord()
    record.Pop = 70000
    found.check("Planet[3]", record)
    assert found.over_storage == ["Planet[3].Pop = 70000 (width 65535)"]

