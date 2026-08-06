"""Diplomatic messages, ported from MESS.PAS."""

import pytest
from conftest import blank_game, place_world

from recreon.environ import GameEnvironment
from recreon.galaxy import XYCoord
from recreon.loadsave import load_game, save_game
from recreon.mess import (
    MessageRecord,
    delete_all_messages,
    delete_read_messages,
    get_messages,
    intercept_message,
    new_message,
    send_message,
    set_message_read,
)
from recreon.news import NewsTypes
from recreon.types import Empire, IDNumber, ObjectTypes
from recreon.utils.pascal import set_rand_seed


@pytest.fixture(autouse=True)
def deterministic():
    set_rand_seed(4021)


@pytest.fixture
def game():
    """Three empires, each with a capital, spread across the galaxy."""
    g = blank_game(size=30, empires=3)
    for index, (emp, xy) in enumerate(
        [
            (Empire.Empire1, XYCoord(5, 5)),
            (Empire.Empire2, XYCoord(25, 25)),
            (Empire.Empire3, XYCoord(15, 15)),
        ],
        start=1,
    ):
        world = place_world(g, index, xy, emp=emp)
        g.Universe.EmpireData[emp].Capital = world
    return g


# --- The store ---------------------------------------------------------------


def test_messages_are_kept_newest_first(game):
    """NewMessage links onto the head of the list, so the inbox reads newest
    down to oldest without the reader having to sort."""
    new_message(game, MessageRecord(Sender=Empire.Empire1, MesText=["first"]))
    new_message(game, MessageRecord(Sender=Empire.Empire1, MesText=["second"]))

    assert [m.MesText[0] for m in game.MessageList] == ["second", "first"]


def test_get_messages_returns_only_what_is_addressed_to_you(game):
    new_message(
        game, MessageRecord(Sender=Empire.Empire1, Recipient={Empire.Empire2})
    )
    new_message(
        game, MessageRecord(Sender=Empire.Empire1, Recipient={Empire.Empire3})
    )

    assert len(get_messages(game, Empire.Empire2)) == 1
    assert len(get_messages(game, Empire.Empire3)) == 1
    assert get_messages(game, Empire.Empire1) == []


def test_a_message_is_read_only_once_every_recipient_has_read_it(game):
    """``Read`` greys the message out; ``ReadBy`` is what decides when.

    A message to two empires is still live in the second one's inbox after
    the first has opened it, which is why the two are tracked apart.
    """
    mess = new_message(
        game,
        MessageRecord(Recipient={Empire.Empire2, Empire.Empire3}),
    )

    set_message_read(game, Empire.Empire2, mess)
    assert mess.ReadBy == {Empire.Empire2}
    assert not mess.Read

    set_message_read(game, Empire.Empire3, mess)
    assert mess.Read


def test_delete_read_messages_keeps_the_unread_ones(game):
    unread = new_message(game, MessageRecord(Recipient={Empire.Empire2}))
    read = new_message(game, MessageRecord(Recipient={Empire.Empire2}))
    set_message_read(game, Empire.Empire2, read)

    delete_read_messages(game)
    assert game.MessageList == [unread]


def test_delete_all_messages_empties_the_list(game):
    new_message(game, MessageRecord(Recipient={Empire.Empire2}))
    delete_all_messages(game)
    assert game.MessageList == []


# --- Delivery ----------------------------------------------------------------


def test_sending_files_the_message_and_tells_the_recipient(game):
    send_message(game, Empire.Empire1, {Empire.Empire2}, ["Header", "Body text"])

    inbox = get_messages(game, Empire.Empire2)
    assert len(inbox) == 1
    assert inbox[0].Sender is Empire.Empire1
    assert not inbox[0].Intercepted
    assert any(
        item.Headline is NewsTypes.MessR for item in game.News[Empire.Empire2]
    )


def test_a_message_to_yourself_is_never_intercepted(game):
    """``Empires<>[Emp]`` guards the whole intercept sweep."""
    send_message(game, Empire.Empire1, {Empire.Empire1}, ["Note", "to self"])

    assert len(game.MessageList) == 1
    assert not game.MessageList[0].Intercepted


def test_an_eavesdropper_next_to_the_capital_reads_the_mail(game):
    """Interception chance is ``150 / distance**2`` percent, per world.

    A listening post one sector from the recipient's capital is therefore a
    certainty, which is the whole mechanic: worlds near a capital are how a
    third party reads someone else's diplomacy.
    """
    place_world(game, 4, XYCoord(25, 24), emp=Empire.Empire3)

    send_message(game, Empire.Empire1, {Empire.Empire2}, ["Header", "The fleet sails"])

    intercepted = get_messages(game, Empire.Empire3)
    assert len(intercepted) == 1
    assert intercepted[0].Intercepted
    assert intercepted[0].Sender is Empire.Empire1
    assert any(
        item.Headline is NewsTypes.MessI for item in game.News[Empire.Empire3]
    )


def test_interception_falls_off_with_the_square_of_the_distance(game):
    """A listening post pays for being close, steeply.

    Empire3's capital is ten sectors from Empire2's, giving
    ``Round(150 / 100) == 2`` percent; a world one sector away gives 150, which
    the ``Rnd(1,100)`` test can never beat. Measured over independent trials
    rather than asserted on one roll, since the near case is the only one the
    formula makes certain.
    """
    far, near = 0, 0
    for seed in range(60):
        set_rand_seed(seed)
        delete_all_messages(game)
        send_message(game, Empire.Empire1, {Empire.Empire2}, ["Header", "Body"])
        far += len(get_messages(game, Empire.Empire3))

    place_world(game, 4, XYCoord(25, 24), emp=Empire.Empire3)
    for seed in range(60):
        set_rand_seed(seed)
        delete_all_messages(game)
        send_message(game, Empire.Empire1, {Empire.Empire2}, ["Header", "Body"])
        near += len(get_messages(game, Empire.Empire3))

    # 2% over 60 trials: seeing more than a quarter of them would mean the
    # distance term had dropped out of the formula.
    assert far < 15
    # 150% from the adjacent world, on every single trial.
    assert near >= 60


def test_an_intercepted_copy_keeps_its_first_line_and_garbles_the_rest(game):
    obj = IDNumber(ObjectTypes.Pln, 3)
    body = ["From the Sarkhon", "The fleet sails at dawn for the Kaldor line"]

    intercept_message(game, Empire.Empire1, Empire.Empire3, obj, body)

    copy = get_messages(game, Empire.Empire3)[0]
    assert copy.MesText[0] == body[0]
    assert copy.MesText[1] != body[1]
    assert len(copy.MesText[1]) == len(body[1])
    assert "." in copy.MesText[1]


def test_short_lines_come_through_a_garbled_copy_intact(game):
    """``IF Length(Temp)>5`` -- five characters or fewer are left alone."""
    body = ["Header", "Yes", "No", "Go"]

    intercept_message(
        game, Empire.Empire1, Empire.Empire3, IDNumber(ObjectTypes.Pln, 3), body
    )

    assert get_messages(game, Empire.Empire3)[0].MesText == body


def test_the_original_message_is_not_garbled_by_an_interception(game):
    """The sender's copy is the same object the interceptor's is built from.

    The Pascal garbles into a scratch ``TextStructure``; the port has to keep
    the caller's list untouched for the same reason.
    """
    place_world(game, 4, XYCoord(25, 24), emp=Empire.Empire3)
    body = ["Header", "The fleet sails at dawn for the Kaldor line"]

    send_message(game, Empire.Empire1, {Empire.Empire2}, body)

    assert get_messages(game, Empire.Empire2)[0].MesText == [
        "Header",
        "The fleet sails at dawn for the Kaldor line",
    ]


# --- Save/load ---------------------------------------------------------------


def test_messages_survive_a_save(game, tmp_path):
    send_message(
        game, Empire.Empire1, {Empire.Empire2, Empire.Empire3}, ["Header", "Body"]
    )
    set_message_read(game, Empire.Empire2, game.MessageList[0])

    saved = tmp_path / "game.sav"
    save_game(game, saved)
    loaded = GameEnvironment()
    load_game(loaded, saved)

    restored = get_messages(loaded, Empire.Empire3)[0]
    assert restored.Sender is Empire.Empire1
    assert restored.Recipient == {Empire.Empire2, Empire.Empire3}
    assert restored.ReadBy == {Empire.Empire2}
    assert not restored.Read
    assert restored.MesText == ["Header", "Body"]


def test_loading_replaces_the_inbox_rather_than_adding_to_it(game, tmp_path):
    """Deviation from the original, deliberately.

    ``LoadMessageData`` pushes onto ``MessageList`` without clearing it and
    ``InitializeUniverse`` does not clear it either, so the Pascal carries the
    previous game's diplomacy into the one being loaded. Filed as an original
    bug; unlike the defects the port keeps, it has no gameplay reading at all.
    """
    saved = tmp_path / "game.sav"
    save_game(game, saved)

    other = blank_game(empires=2)
    new_message(other, MessageRecord(Recipient={Empire.Empire2}, MesText=["stale"]))
    load_game(other, saved)

    assert other.MessageList == []
