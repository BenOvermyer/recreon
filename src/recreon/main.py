"""Entry point.

Port of ANACREON.PAS. The game loop it drives -- Prolog, NewGame, the
per-empire PlayerTakesTurn / UpdateUniverse cycle -- arrives in Phase 2; for
now this only reports what has been ported.
"""

from __future__ import annotations

from . import __version__


def main() -> None:
    print(f"Re:creon {__version__}")
    print("Core data structures only; no game loop yet (see docs/IMPLEMENTATION_PLAN.md).")


if __name__ == "__main__":
    main()
