"""The empire status window (F8), ported from EMPWIND.PAS.

The shortest of the windows: the player's own line, then one line per rival.
All the work is `intrface.get_empire_status_line`; what is here is the rule
about who appears and how much of them you get to see.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .intrface import get_empire_status_line
from .primintr import empire_active, get_capital, known, scouted
from .types import PLAYER_EMPIRES, Empire

if TYPE_CHECKING:
    from .environ import GameEnvironment

#: The column header, transcribed from `InitTitle`.
EMPIRE_HEADER = (
    "Empire       Tl Pln SInd   Pop    fgt    hkr    jmp    jtn    pen    str    trn "
)


def empire_rows(game: GameEnvironment, player: Empire) -> list[str]:
    """Every empire the player can see, as rendered lines. ``DrawEmpireWindow``.

    **An empire appears only once you know where its capital is**, and you get
    its fleet strength only once you have scouted that capital. So the table
    fills in two stages as a rival is discovered: first its name, technology,
    size and population; later what it can put in space.

    Keying the whole empire off one world is a strong simplification on the
    original's part -- you may have fought that empire's fleets for years
    without its capital ever entering your range, and it will not be listed.
    Reproduced as written.

    The player's own line always comes first and is always full.
    """
    rows = [get_empire_status_line(game, player, True)]

    for emp in PLAYER_EMPIRES:
        if not empire_active(game, emp) or emp == player:
            continue
        capital = get_capital(game, emp)
        if known(game, player, capital):
            rows.append(
                get_empire_status_line(game, emp, scouted(game, player, capital))
            )

    return rows


__all__ = ["EMPIRE_HEADER", "empire_rows"]
