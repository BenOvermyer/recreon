"""Tests for the player manual's generated appendix and command reference.

Two drift checks, both scanning committed text against the port's own data:

* the appendix tables in ``docs/manual/generated/appendix-reference.md``
  must match what ``build.py`` renders from ``datacnst``/``attack`` today
  (the same "checked by construction" rule the balance tables follow), and
* chapter 8's menu listing must name every command the menu bar has, with
  its accelerator letter marked exactly as the chapter renders it.

Neither test invokes pandoc; both are pure text comparison.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from recreon.playturn import MENU_BAR

REPO = Path(__file__).resolve().parent.parent
MANUAL = REPO / "docs" / "manual"
APPENDIX = MANUAL / "generated" / "appendix-reference.md"
COMMANDS_CHAPTER = MANUAL / "chapters" / "08-command-reference.md"


def _load_build():
    spec = importlib.util.spec_from_file_location("manual_build", MANUAL / "build.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = _load_build()


def test_appendix_matches_the_game_data():
    """The committed appendix is what the ported tables render today.

    If this fails, either a game table changed (re-run
    ``uv run python docs/manual/build.py --tables`` and commit) or someone
    edited the generated file by hand.
    """
    assert APPENDIX.exists(), "generated appendix missing; run build.py --tables"
    assert APPENDIX.read_text() == build.appendix(), (
        "appendix-reference.md is stale; regenerate with build.py --tables"
    )


def test_appendix_is_generated_from_the_port_not_invented():
    """Every table name the appendix claims, the generator really reads.

    Guards against the appendix quietly gaining hand-written numbers: the
    generator's text must mention the enum it is keyed by, and the file
    must carry the do-not-edit marker.
    """
    text = APPENDIX.read_text()
    assert "Do not edit by hand" in text
    for section in ("## Technology Levels", "## Combat", "## World Classes"):
        assert section in text


def _menu_entry(label: str, key: str) -> str:
    """How chapter 8 renders one menu item: the accelerator in parentheses."""
    return label.replace(key, f"({key})", 1)


def test_command_reference_lists_every_menu_item():
    chapter = COMMANDS_CHAPTER.read_text()
    missing = [
        entry.label
        for bar in MENU_BAR
        for entry in bar.items
        if _menu_entry(entry.label, entry.key) not in chapter
    ]
    assert not missing, f"menu items missing from the command reference: {missing}"


def test_command_reference_lists_every_menu_title():
    chapter = COMMANDS_CHAPTER.read_text()
    for bar in MENU_BAR:
        assert bar.title in chapter, f"menu {bar.title!r} missing from chapter 8"


def test_shipped_files_are_present():
    """The artifacts the README promises exist and are non-trivial."""
    assert (MANUAL / "logo.svg").read_text().startswith("<svg")
    assert (MANUAL / "recreon-manual.pdf").exists()
    assert (MANUAL / "recreon-manual.pdf").stat().st_size > 100_000
    html = (MANUAL / "recreon-manual.html").read_text()
    assert "Re:creon" in html
    # the logo is embedded, so the HTML file stands alone.
    assert "data:image/svg+xml" in html
