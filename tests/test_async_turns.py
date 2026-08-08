"""Play-by-mail turns: the other branch of ANACREON.PAS's `UpdateTurn`.

Asynchronous play is not "the same turns in a different order". Nobody
rotates. Each human picks themselves out of `EmpiresToMove` from the prologue,
takes one turn, and the loop returns so the save file can be passed on. The
year turns only once the last human has moved.

The port offered the `Sequential play ON/OFF` toggle for a while without
implementing the branch behind it, so the setting did nothing. These tests are
mostly about the difference being real.
"""

from __future__ import annotations

import pytest

from recreon.main import new_game, update_turn
from recreon.types import PLAYER_EMPIRES, Empire
from recreon.utils.pascal import set_rand_seed


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


def two_player_game():
    """A game with two humans, so `EmpiresToMove` takes two turns to empty."""
    game = new_game()
    for emp in (Empire.Empire1, Empire.Empire2):
        data = game.Universe.EmpireData[emp]
        data.InUse = True
        data.IsAPlayer = True
    game.reset_empires_to_move()
    return game


# --- The year turns on the last human, not on a rotation ---------------------


def test_the_year_holds_until_every_human_has_moved():
    game = two_player_game()
    game.AsyncTurns = True
    year = game.Year

    game.Player = Empire.Empire1
    update_turn(game)

    assert game.Year == year, "one of two players has moved; the year waits"
    assert Empire.Empire2 in game.EmpiresToMove

    game.Player = Empire.Empire2
    update_turn(game)

    assert game.Year == year + 1, "the last human moved, so the year turns"


def test_the_roster_refills_when_the_year_turns():
    """`ResetEmpiresToMove` runs before the AI acts, so the next round is
    already open by the time the save is passed on."""
    game = two_player_game()
    game.AsyncTurns = True

    for emp in (Empire.Empire1, Empire.Empire2):
        game.Player = emp
        update_turn(game)

    assert Empire.Empire1 in game.EmpiresToMove
    assert Empire.Empire2 in game.EmpiresToMove


def test_the_player_always_returns_to_empire1():
    """`Player := Empire1` is unconditional at the end of the async branch --
    it runs whether or not the year turned. The prologue then asks who is
    actually sitting down, so this is a resting value rather than a choice."""
    game = two_player_game()
    game.AsyncTurns = True

    game.Player = Empire.Empire2
    update_turn(game)

    assert game.Player == Empire.Empire1


# --- It is a different branch, not a reordering ------------------------------


def test_sequential_play_advances_the_year_on_its_own_rotation():
    """The contrast that makes the setting worth having. Sequential rotates
    through every empire itself and turns the year when it wraps; asynchronous
    never rotates at all."""
    game = two_player_game()
    game.AsyncTurns = False
    year = game.Year

    game.Player = Empire.Empire1
    update_turn(game)

    # Rotation stopped at the next *human*, having run the AI empires between.
    assert game.Player == Empire.Empire2
    assert game.Year == year


def test_a_single_player_async_game_turns_the_year_every_turn():
    """With one human there is nobody to wait for, so async collapses to one
    year per turn -- which is what makes it usable solo."""
    game = new_game()
    game.AsyncTurns = True
    year = game.Year

    game.Player = Empire.Empire1
    update_turn(game)

    assert game.Year == year + 1


# --- Original bug #85 --------------------------------------------------------


def test_no_ai_empire_rebuilds_its_fog_of_war(monkeypatch):
    """Issue #85, pinned.

    The Pascal's async branch calls `ClearScoutSet(Player)` and its three
    companions inside a `FOR Emp` loop -- passing the departing human rather
    than the AI empire whose turn it is. Only `ImplementNPE` and `EraseNews`
    got updated when the block was copy-pasted from the sequential branch.

    So in a play-by-mail game the AI never refreshes what it can see. Do not
    "fix" this by passing `emp`: that is a balance change, and #85 says why.
    """
    import recreon.main as main

    scouted_for: list[Empire] = []
    acted_for: list[Empire] = []

    monkeypatch.setattr(main, "set_up_turn", lambda g, p: scouted_for.append(p))
    monkeypatch.setattr(main, "implement_npe", lambda g, e: acted_for.append(e))

    game = new_game()
    game.AsyncTurns = True
    game.Player = Empire.Empire1
    update_turn(game)

    npes = [
        emp
        for emp in PLAYER_EMPIRES
        if game.Universe.EmpireData[emp].InUse
        and not game.Universe.EmpireData[emp].IsAPlayer
    ]

    assert acted_for == npes, "every AI empire should still take its turn"
    assert scouted_for == [Empire.Empire1] * len(npes), (
        "and every one of them should scout for the departing human instead "
        "of for itself -- that is the bug"
    )
