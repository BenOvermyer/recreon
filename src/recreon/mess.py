"""Diplomatic messages between empires.

Port of MESS.PAS. The message *windows* -- composing, reading, the recipient
picker -- are in the command handlers and stay unported with the rest of the
UI; what is here is the store, the delivery rules and the save/load sections
LOADSAVE.PAS calls into.

The original keeps a doubly-linked list of messages in a global
``MessageList``, newest first, and a message body as a ``TextStructure`` from
TEXTSTRC.PAS -- another linked list, of lines. Both collapse to Python lists:
``GameEnvironment.MessageList`` and ``MessageRecord.MesText``. Newest-first
ordering is preserved, because ``GetMessages`` hands the reader the list in
list order and the original inserts at the head.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .environ import GameEnvironment
from .galaxy import Location, limbo
from .misc import distance
from .news import NewsTypes, add_news
from .primintr import get_capital, get_coord
from .types import PLAYER_EMPIRES, Empire, IDNumber, ObjectTypes, empty_quadrant
from .utils.int_utils import lesser_int, rnd
from .utils.pascal import pascal_round

#: How many messages one empire's inbox window can show. The original's
#: ``MessageArray`` is ``ARRAY [1..20]``, and GetMessages writes past it
#: without checking -- see the note on :func:`get_messages`.
MAX_MESSAGES_SHOWN = 20


@dataclass(slots=True)
class MessageRecord:
    """One message, in flight or already read.

    ``Read`` is the flag the inbox greys out; it goes true only once *every*
    recipient has read it, which is why ``ReadBy`` is tracked separately.
    """

    Sender: Empire = Empire.Indep
    #: Empires it is addressed to.
    Recipient: set[Empire] = field(default_factory=set)
    #: Empires that have read it.
    ReadBy: set[Empire] = field(default_factory=set)
    Read: bool = False
    #: True if this is a garbled copy picked up by an eavesdropper.
    Intercepted: bool = False
    #: The body, one string per line. A ``TextStructure`` in the original.
    MesText: list[str] = field(default_factory=lambda: [""])


# --- The store ---------------------------------------------------------------


def new_message(game: GameEnvironment, message: MessageRecord) -> MessageRecord:
    """Push a message onto the head of the list, as ``NewMessage`` does."""
    game.MessageList.insert(0, message)
    return message


def delete_all_messages(game: GameEnvironment) -> None:
    game.MessageList.clear()


def delete_read_messages(game: GameEnvironment) -> None:
    """Drop every message all of whose recipients have read it."""
    game.MessageList[:] = [mess for mess in game.MessageList if not mess.Read]


def get_messages(game: GameEnvironment, emp: Empire) -> list[MessageRecord]:
    """Every message addressed to ``emp``, newest first.

    **Original bug (#49).** The original fills a fixed ``ARRAY [1..20]`` and
    counts without bounding the count, so a 21st message writes past the array
    -- the caller's stack. Returning a list makes the overrun unreachable
    rather than reproducing it: it is a memory-corruption bug, not a gameplay
    rule, and the only thing a faithful port would buy is a crash.
    :data:`MAX_MESSAGES_SHOWN` records what the window was sized for.
    """
    return [mess for mess in game.MessageList if emp in mess.Recipient]


def set_message_read(game: GameEnvironment, emp: Empire, mess: MessageRecord) -> None:
    """Mark ``mess`` read by ``emp``, and read outright once all have."""
    mess.ReadBy.add(emp)
    if mess.Recipient <= mess.ReadBy:
        mess.Read = True


# --- Delivery ----------------------------------------------------------------


def intercept_message(
    game: GameEnvironment,
    emp: Empire,
    interceptor: Empire,
    obj: IDNumber,
    message_text: list[str],
) -> None:
    """File a garbled copy of ``message_text`` in ``interceptor``'s inbox.

    The first line always survives intact -- it is the header the original
    writes the sender into -- and every line after it takes up to seven runs
    of dots over it. Lines of five characters or fewer are left alone, so a
    short message can come through clean.

    **Original bug (#47).** The Pascal builds the garbled copy by calling
    ``InsertLine(MessageText, GarbLine)`` -- passing the *sender's* text
    structure while inserting into the *garbled* one. The chain still comes
    out right, so the copy reads correctly, but ``GarbledText.NoOfLines``
    stays at 1 and ``MessageText.NoOfLines`` is inflated once per intercepted
    line. Nothing in save/load reads those counters, but the message windows
    do. Modelling a body as a list of strings leaves the bug nothing to
    corrupt, so the port cannot reproduce it.
    """
    garbled: list[str] = []
    for index, line in enumerate(message_text):
        if index == 0 or len(line) <= 5:
            garbled.append(line)
            continue

        chars = list(line)
        for _ in range(rnd(0, 7)):
            start_garb = rnd(1, len(chars) - 5)
            max_len = lesser_int(1 + len(chars) - start_garb, 10)
            # Pascal indexes a string from 1 and the FOR is inclusive at both
            # ends, so this is a 1-based closed range translated as-is.
            #
            # Original bug (#48): the `1 +` above lets the bound reach
            # Length+1, so the last iteration writes one character past the
            # line -- off the end of a LineStr when the line is a full 80
            # characters. The guard skips that write. Nothing visible changes:
            # the overflowing index never lands on a character of the line.
            for j in range(start_garb, start_garb + rnd(1, max_len) + 1):
                if j <= len(chars):
                    chars[j - 1] = "."
        garbled.append("".join(chars))

    new_message(
        game,
        MessageRecord(
            Sender=emp,
            Recipient={interceptor},
            ReadBy=set(),
            Read=False,
            Intercepted=True,
            MesText=garbled,
        ),
    )

    add_news(
        game,
        interceptor,
        NewsTypes.MessI,
        Location(XY=limbo(), ID=obj),
        int(emp),
    )


def send_message(
    game: GameEnvironment,
    emp: Empire,
    empires: set[Empire],
    message_text: list[str],
) -> None:
    """Send a message from ``emp`` to ``empires``, and roll for eavesdroppers.

    Every empire that is *not* a recipient gets a chance to intercept from
    each of its worlds, at ``150 / distance**2`` percent measured from the
    recipient's capital -- so listening posts near a capital are how a third
    party reads someone else's mail.

    Two quirks of the original are kept (#50):

    * When there is more than one recipient, the distance is measured from
      the capital of whichever recipient sorts *last*, not from each in turn.
      A broadcast is therefore no more interceptable than a single letter,
      and which capital it keys on depends on empire ordinal.
    * ``NoOfIntercepts <= 5`` is tested once per *empire*, before that
      empire's worlds are swept, and incremented once per *world*. So the cap
      bounds how many empires can start intercepting, not how many copies get
      made: one empire with forty worlds around the capital can file forty.
    """
    new_message(
        game,
        MessageRecord(
            Sender=emp,
            Recipient=set(empires),
            ReadBy=set(),
            Read=False,
            Intercepted=False,
            MesText=message_text,
        ),
    )

    # Pascal's FOR leaves TargetEmp holding the last recipient it saw.
    target_emp: Empire | None = None
    for emp_i in PLAYER_EMPIRES:
        if emp_i in empires:
            target_emp = emp_i

    if target_emp is None:
        # The original reads an uninitialised TargetEmp here. A message with
        # no recipients cannot be composed through the UI, so rather than
        # reproduce a read of uninitialised stack, there is nothing to deliver.
        return

    send_xy = get_coord(game, get_capital(game, target_emp))
    no_of_intercepts = 0
    loc = Location(XY=limbo(), ID=empty_quadrant())

    for emp_i in PLAYER_EMPIRES:
        if emp_i in empires:
            add_news(game, emp_i, NewsTypes.MessR, loc, int(emp))
            continue

        if emp_i == emp or no_of_intercepts > 5 or empires == {emp}:
            continue

        for j in range(1, game.NoOfPlanets + 1):
            if j not in game.GlobalSets.SetOfPlanetsOf[emp_i]:
                continue

            obj = IDNumber(ObjectTypes.Pln, j)
            int_xy = get_coord(game, obj)
            gap = distance(send_xy, int_xy)
            if gap == 0:
                # Division by zero in the original (#50). Unreachable in
                # practice -- one sector holds one object, so an interceptor's
                # world can never share the capital's coordinate.
                continue

            chance_to_intercept = pascal_round((1 / (gap * gap)) * 150)
            if rnd(1, 100) <= chance_to_intercept:
                intercept_message(game, emp, emp_i, obj, message_text)
                no_of_intercepts += 1


# --- Save/load ---------------------------------------------------------------


def save_message_data(game: GameEnvironment) -> list:
    """The message list, for the save file. Port of ``SaveMessageData``."""
    from .utils.serial import encode

    return [encode(mess) for mess in game.MessageList]


def load_message_data(game: GameEnvironment, data: list) -> None:
    """Restore the message list. Port of ``LoadMessageData``.

    The original discards every message if any one of them fails to read
    (``IF Error<>0 THEN DeleteAllMessages``); here a malformed section raises
    out of :func:`~recreon.loadsave.load_game`, which abandons the load
    entirely, so a half-read inbox is unreachable either way.

    **Original bug (#46).** ``LoadMessageData`` *appends* to ``MessageList``
    without clearing it, and ``InitializeUniverse`` does not clear it either,
    so the Pascal carries the previous game's diplomacy into the one being
    loaded. Assigning is a deliberate deviation: unlike the defects the port
    keeps, this one has no gameplay reading at all.
    """
    from .utils.serial import decode

    game.MessageList = [decode(MessageRecord, item) for item in data]


__all__ = [
    "MAX_MESSAGES_SHOWN",
    "MessageRecord",
    "delete_all_messages",
    "delete_read_messages",
    "get_messages",
    "intercept_message",
    "load_message_data",
    "new_message",
    "save_message_data",
    "send_message",
    "set_message_read",
]
