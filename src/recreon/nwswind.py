"""The news window (F7), ported from NWSWIND.PAS.

The year's headlines, rendered by `intrface.get_news_line`. The window's own
contribution is the ordering.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .intrface import get_news_line
from .news import LOCAL_NEWS, NewsRecord
from .types import Empire

if TYPE_CHECKING:
    from .environ import GameEnvironment


def news_rows(game: GameEnvironment, player: Empire) -> list[NewsRecord]:
    """The feed, reordered for reading. ``InitNewsDataArray``.

    Two passes over the same list: everything **not** in
    :data:`~recreon.news.LOCAL_NEWS` first, then everything that is. So a raid,
    a conquest or a rebellion sorts above a world reporting it is short of
    metals, regardless of which was filed first.

    Nothing is dropped. Within each half the feed's own order survives, which
    is the order :func:`~recreon.news.add_news` built it in.
    """
    feed = game.News[player]
    return [item for item in feed if item.Headline not in LOCAL_NEWS] + [
        item for item in feed if item.Headline in LOCAL_NEWS
    ]


def news_lines(game: GameEnvironment, player: Empire) -> list[str]:
    """The same feed as prose, ready to display."""
    return [get_news_line(game, player, item) for item in news_rows(game, player)]


__all__ = ["news_lines", "news_rows"]
