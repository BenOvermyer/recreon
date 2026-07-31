"""Scenario file tokenizer.

Port of DFA.PAS. The original reads a Turbo Pascal TEXT file character by
character through a state machine; here the whole file is held as a string
with a cursor, which also gives ``read_line`` for the directives that consume
raw lines (``BEGINDESCRIPTION``, ``BEGINTEXT``).

Token syntax:

* tokens are separated by whitespace or line breaks
* a token may contain spaces if wrapped in double quotes
* ``\\`` escapes the next character, so ``"`` and ``\\`` can appear in a token
* ``;`` starts a comment that runs to the end of the line
"""

from __future__ import annotations

from enum import Enum, auto

#: DOS end-of-file marker. Turbo Pascal hands this back at the end of a TEXT
#: file, and the state machine keys off it, so the port produces it too.
EOF_CH = "\x1a"
RETURN_CH = "\r"
LINE_FEED_CH = "\n"
TAB_CH = "\t"

WHITESPACE = frozenset({EOF_CH, RETURN_CH, LINE_FEED_CH, TAB_CH, " "})

EOF_MESSAGE = "ERROR: Unexpected end of file."
LBRK_MESSAGE = "ERROR: Unexpected line break."


class _State(Enum):
    START = auto()
    COMMENT = auto()
    QUOTE = auto()
    SLASH1 = auto()
    SLASH2 = auto()
    TOKEN1 = auto()
    TOKEN2 = auto()
    FINAL = auto()


class TokenError(Exception):
    """Raised when the tokenizer cannot produce a token.

    The original sets an ``Error`` flag and returns the message as the token;
    raising keeps callers from mistaking an error string for real input.
    """


class TokenReader:
    """A cursor over scenario text."""

    __slots__ = ("text", "pos")

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    @classmethod
    def from_path(cls, path) -> TokenReader:
        from pathlib import Path

        return cls(Path(path).read_text(encoding="cp437"))

    @property
    def at_eof(self) -> bool:
        return self.pos >= len(self.text)

    def _read_char(self) -> str:
        if self.pos >= len(self.text):
            self.pos += 1
            return EOF_CH
        ch = self.text[self.pos]
        self.pos += 1
        return ch

    def read_line(self) -> str:
        """One raw line, newline consumed. Empty string past the end."""
        if self.at_eof:
            return ""
        end = self.text.find("\n", self.pos)
        if end == -1:
            line = self.text[self.pos :]
            self.pos = len(self.text)
        else:
            line = self.text[self.pos : end]
            self.pos = end + 1
        return line.rstrip("\r")

    def next_token(self) -> str:
        """The next token.

        Faithful to the original state machine, including its quirk that an
        empty quoted string (``""``) returns to START and is skipped rather
        than yielding an empty token.
        """
        token: list[str] = []
        state = _State.START

        while state is not _State.FINAL:
            ch = self._read_char()

            match state:
                case _State.START:
                    if ch == ";":
                        state = _State.COMMENT
                    elif ch == '"':
                        state = _State.QUOTE
                    elif ch == "\\":
                        state = _State.SLASH2
                    elif ch == EOF_CH:
                        raise TokenError(EOF_MESSAGE)
                    elif ch not in WHITESPACE:
                        state = _State.TOKEN2
                        token.append(ch)

                case _State.COMMENT:
                    if ch in (RETURN_CH, LINE_FEED_CH):
                        state = _State.START
                    elif ch == EOF_CH:
                        raise TokenError(EOF_MESSAGE)

                case _State.QUOTE:
                    if ch == '"':
                        state = _State.START
                    elif ch == "\\":
                        state = _State.SLASH1
                    elif ch in (EOF_CH, RETURN_CH, LINE_FEED_CH):
                        raise TokenError(LBRK_MESSAGE)
                    else:
                        state = _State.TOKEN1
                        token.append(ch)

                case _State.SLASH1:
                    if ch in (EOF_CH, LINE_FEED_CH, RETURN_CH):
                        raise TokenError(LBRK_MESSAGE)
                    state = _State.TOKEN1
                    token.append(ch)

                case _State.SLASH2:
                    if ch in (EOF_CH, LINE_FEED_CH, RETURN_CH):
                        raise TokenError(LBRK_MESSAGE)
                    state = _State.TOKEN2
                    token.append(ch)

                case _State.TOKEN1:
                    if ch in ('"', LINE_FEED_CH, RETURN_CH, EOF_CH):
                        state = _State.FINAL
                    elif ch == "\\":
                        state = _State.SLASH1
                    else:
                        token.append(ch)

                case _State.TOKEN2:
                    if ch in WHITESPACE:
                        state = _State.FINAL
                    elif ch == "\\":
                        state = _State.SLASH2
                    else:
                        token.append(ch)

        return "".join(token)

    def next_integer(self) -> int:
        """The next token parsed as an integer."""
        token = self.next_token()
        try:
            return int(token)
        except ValueError:
            raise TokenError(f'ERROR: Illegal number format "{token}"') from None
