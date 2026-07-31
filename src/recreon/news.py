"""Per-empire news feed.

Port of NEWS.PAS. The original keeps a heap-allocated linked list per empire
and drops items when the heap runs low; a list per empire capped at
MAX_NO_OF_NEWS_ITEMS does the same job.

Rendering headlines into prose is INTRFACE.PAS ``GetNewsLine``, in Phase 8.
The enum ordinals are load-bearing all the same -- the original passes
``Ord(ResourceType)`` and similar through the Parm fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING

from .galaxy import Location
from .types import MAX_NO_OF_NEWS_ITEMS, Empire, IDNumber

if TYPE_CHECKING:
    from .environ import GameEnvironment


class NewsTypes(IntEnum):
    """Headline kinds. Comments give the payload carried in Parm1..Parm3."""

    NoNews = 0
    Lack = 1  # (Loc, material) lacks raw material
    Starv = 2  # (Loc, 10s of mil) people starve
    NTech = 3  # (Loc, NewTech) new tech level
    RTech = 4  # (Loc, NewTech) regressed level
    ConsLack = 5
    ConsDone = 6
    Rebel = 7  # (Loc) world rebels
    URebel = 8  # (Loc, MenKilled) unsuccessful rebellion
    RebelW1 = 9
    RebelW2 = 10
    RebelW3 = 11
    RebelW4 = 12
    POk = 13
    NCapTech = 14
    NCapLvl = 15
    BattleL = 16
    BattleW1 = 17
    BattleW2 = 18
    WAddict = 19  # (Loc) world addicted to ambrosia
    UAddict = 20  # (Loc) world no longer addicted
    AddictDie = 21  # (Loc, Deaths) addicts die
    RiotsDie = 22  # (Loc, Deaths) people die from ambrosia riots
    IndDs = 23  # (Loc, Ind, IndI) industry destroyed
    DInd = 24
    Join = 25
    NewCap = 26
    EndEmp = 27
    NoFuel = 28
    FltDet = 29
    Mines = 30
    MinesDm = 31
    MinesDs = 32
    ConDs = 33
    GteDs = 34
    LAMDm = 35
    LAMDs = 36
    TrnsShp = 37
    Trns2 = 38
    NSellTech = 39
    GInd = 40
    NewPlEmp = 41
    DefLack = 42  # (Loc, material) needs resources to build defenses
    IndLack = 43  # (Loc, material) needs metals to build industry
    PCap = 44
    PDest = 45
    MessR = 46
    MessI = 47
    ConDsUNK = 48
    GteDsUNK = 49
    BattleW2UNK = 50
    BattleLUNK = 51
    HLPopKill = 52  # (Loc, pop) aliens kill population
    HLMenKill = 53  # (Loc, men, nnj) aliens attack troops
    HLJoin = 54  # (Loc, nnj) aliens join troops
    LAMDef = 55
    DestDetail = 56
    BseFuel = 57
    BseBlocked = 58
    FltBlocked = 59
    NebGate = 60
    SRMClear = 61
    BseSD = 62
    FltSD = 63
    WHolo = 64
    DthHolo = 65
    Disrupt = 66
    NoTriRes = 67  # (Loc) world has no more trillum
    TriResWarn1 = 68  # (Loc) very low on trillum reserves
    TriResWarn2 = 69  # (Loc) low on trillum reserves
    MilitRev = 70  # (Loc) world wants troops out
    RevControl = 71  # (Loc) military quiets rebellion
    GLBDest = 72
    GLBConq = 73
    GLBCapConq = 74
    GLBLAMStrk = 75
    GLBRev = 76  # (Loc, Emp) world revolts from empire
    OutProbe = 77
    OrdersSRMClear = 78
    OrdersNoSRMs = 79
    OrdersNoSSP = 80
    TerChaos = 81  # (Loc) terraforming failed miserably
    TerSuccess = 82  # (Loc) terraforming completed
    GTech = 83
    CLost = 84
    LostP = 85
    SMnR = 86
    JumpDm = 87
    JumpDs = 88
    ELost = 89
    TriAcc = 90
    LostF = 91


@dataclass(slots=True)
class NewsRecord:
    Headline: NewsTypes = NewsTypes.NoNews
    Loc1: Location = field(default_factory=Location)
    Parm1: int = 0
    Parm2: int = 0
    Parm3: int = 0


def add_news(
    game: GameEnvironment,
    player: Empire,
    head: NewsTypes,
    loc: Location,
    p1: int = 0,
    p2: int = 0,
    p3: int = 0,
) -> None:
    """File a headline for one empire.

    Independent and inactive empires read no news, so their items are
    dropped, exactly as the original does.
    """
    if player == Empire.Indep:
        return

    from .primintr import empire_active

    if not empire_active(game, player):
        return

    feed = game.News[player]
    if len(feed) >= MAX_NO_OF_NEWS_ITEMS:
        return
    feed.append(NewsRecord(head, loc, p1, p2, p3))


def add_global_news(
    game: GameEnvironment,
    exclude: set[Empire],
    source: IDNumber,
    head: NewsTypes,
    loc: Location,
    p1: int = 0,
    p2: int = 0,
    p3: int = 0,
) -> None:
    """File a headline for every empire that can see ``source``.

    The original gates this on whether the empire has scouted the object;
    everyone who has not is simply left out.
    """
    from .primintr import known

    for emp in Empire:
        if emp in exclude or emp == Empire.Indep:
            continue
        if known(game, emp, source):
            add_news(game, emp, head, loc, p1, p2, p3)


def erase_news(game: GameEnvironment, player: Empire) -> None:
    """Clear an empire's feed, ready for the next year."""
    game.News[player].clear()


def get_news_list(game: GameEnvironment, emp: Empire) -> list[NewsRecord]:
    return game.News[emp]
