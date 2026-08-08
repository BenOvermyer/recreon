"""What is in the v2.0 build, and what the port must therefore leave alone.

`original/` ships 77 units. **Fifteen of them are not in the build**: nothing
reachable from `ANACREON.PAS`'s `USES` graph mentions them. That is a stronger
statement than "has no caller" -- it means the Turbo Pascal compiler never saw
them when `ANACREON.EXE` was produced, so no behaviour of the shipped game
depends on a line inside any of them.

Three of the fifteen are ported anyway, because they are complete units with
transcribed tables worth keeping: `battle.py`, `resource.py` and `cdetypes.py`.
The invariant that matters is that **nothing in the port calls into them**,
because the moment something does, the port is running code the original never
ran. That is what the second test here checks.

The reachability computation is the same one that answers "is `SubtractCasualties`
dead?" -- its only caller is `BOMBER.PAS`, which is itself unreachable.
"""

import ast
import pathlib
import re

ORIGINAL = pathlib.Path(__file__).resolve().parents[1] / "original"
SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "recreon"

#: Units `original/` ships that `ANACREON.PAS` cannot reach. Transcribed from
#: the reachability walk below rather than assumed; the test is what keeps it
#: honest.
#:
#: They fall into four groups. An **alternative implementation** that lost:
#: `BATTLE` (a coarser combat model), `SORT`/`LSORT` (superseded by `QSORT`,
#: which *is* in the build), `RESOURCE` (a second cargo scale). The **artifact
#: scripting subsystem**, commented out of the scenario dispatch in v2.0:
#: `ARTIFACT`, `CODE`, `CDETYPES`, `TRANSACT`. **Scratch and scaffolding**:
#: `DEADCODE`, `TEST`, `TEST1`, `VIEWMAP`, `BITCOMP`, `DLIST`. And `BOMBER`,
#: which is the only thing that ever called `RESOURCE.SubtractCasualties`.
UNREACHABLE_UNITS = {
    "ARTIFACT",
    "BATTLE",
    "BITCOMP",
    "BOMBER",
    "CDETYPES",
    "CODE",
    "DEADCODE",
    "DLIST",
    "LSORT",
    "RESOURCE",
    "SORT",
    "TEST",
    "TEST1",
    "TRANSACT",
    "VIEWMAP",
}

#: Ported modules whose Pascal unit is unreachable. Kept because each is a
#: complete unit carrying transcribed tables, and because "we looked at it and
#: it is dead" is worth more than a gap. Nothing in `src/` may import them.
PORTED_BUT_DEAD = {
    "battle": "BATTLE.PAS",
    "resource": "RESOURCE.PAS",
    "cdetypes": "CDETYPES.PAS",
}

_USES = re.compile(r"\bUSES\b(.*?);", re.I | re.S)


def _units_used(path: pathlib.Path) -> set[str]:
    text = path.read_bytes().decode("cp437")
    # Strip comments, so a unit named only inside `(* ... *)` does not count --
    # which is the whole reason the artifact subsystem is unreachable.
    text = re.sub(r"\{[^}]*\}", " ", text)
    text = re.sub(r"\(\*.*?\*\)", " ", text, flags=re.S)

    found = set()
    for block in _USES.findall(text):
        for name in block.split(","):
            name = name.strip()
            if re.fullmatch(r"[A-Za-z_]\w*", name):
                found.add(name.upper())
    return found


def _reachable_units() -> set[str]:
    available = {p.stem.upper(): p for p in ORIGINAL.glob("*.PAS")}
    seen: set[str] = set()
    queue = ["ANACREON"]
    while queue:
        unit = queue.pop()
        if unit in seen or unit not in available:
            continue
        seen.add(unit)
        queue.extend(_units_used(available[unit]))
    return seen


def test_the_unreachable_units_are_what_we_think_they_are():
    """Walks `USES` from ANACREON.PAS. If this fails, either a unit moved into
    the build or the inventory above is wrong -- and which one matters, because
    the port's decisions about dead code all rest on this."""
    available = {p.stem.upper() for p in ORIGINAL.glob("*.PAS")}
    unreachable = available - _reachable_units()

    assert unreachable == UNREACHABLE_UNITS


def test_the_build_is_most_of_the_tree():
    """A sanity check on the walk itself: if the regex broke and matched
    nothing, everything would look unreachable and the test above would fail
    in a confusing way rather than an obvious one."""
    available = {p.stem.upper() for p in ORIGINAL.glob("*.PAS")}
    reachable = _reachable_units() & available

    assert len(reachable) == 62
    # Spot-check the spine.
    for unit in ("ANACREON", "UPDATE", "ATTACK", "PRIMINTR", "PLAYTURN", "QSORT"):
        assert unit in reachable


def _imports_of(path: pathlib.Path) -> set[str]:
    """Module names this file imports from within the package."""
    tree = ast.parse(path.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level:
            names.add(node.module.split(".")[-1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[-1])
    return names


def test_nothing_in_the_port_calls_into_a_dead_module():
    """The invariant that actually matters.

    `battle.py`, `resource.py` and `cdetypes.py` port units the shipped
    executable never linked. Importing one would mean the port runs code the
    original could not, which is a divergence however correct the code is.
    """
    offenders = []
    for path in sorted(SRC.rglob("*.py")):
        if path.stem in PORTED_BUT_DEAD:
            continue
        for name in _imports_of(path):
            if name in PORTED_BUT_DEAD:
                offenders.append(f"{path.relative_to(SRC)} imports {name}")

    assert offenders == []


def test_every_dead_module_says_so_in_its_first_line():
    """One wording, so the status is greppable and cannot drift into "not yet
    ported" -- which reads as a promise rather than a decision."""
    for module in PORTED_BUT_DEAD:
        doc = ast.get_docstring(ast.parse((SRC / f"{module}.py").read_text())) or ""
        assert "Unreachable in v2.0" in doc, module
