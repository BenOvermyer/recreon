# About This Manual

> *The empire is not a battle. It is a budget that occasionally fights.*
> -- Imperial Staff primer, author unknown

Re:creon is a faithful recreation, in Python, of **Anacreon:
Reconstruction 4021** -- a turn-based 4X space strategy game first
published in 1990 and released as Turbo Pascal source code in 2004.
Every number, table and rule in the game you are about to play was
transcribed from that source rather than reimagined, which makes the
original's quirks as much a part of this game as its good ideas.

This manual replaces the printed booklet that came in Anacreon's box.
The original shipped no tutorial and its in-game help was a stub; the
paper manual was the only way to learn the game. This version covers
the same ground as that manual's index -- combat, construction,
defenses, fleet orders, materials, ships, technology, world classes --
and adds what the old one took for granted: how to actually install
and start the game, and how this recreation's screens work.

## What kind of game this is

You run an empire. Time moves one **year per turn**, and a turn is
divided into orders you give -- to worlds, fleets, construction,
diplomacy -- and a year of consequences you watch unfold in the news
window. Each of up to eight empires is run by a player or by one of
several computer personalities; in the default mode you play one
empire and the others act after you.

The levers are the classic 4X ones, but filtered through a 1990
design sensibility that rewards reading tables:

- **Explore.** Your sensors see only what your fleets and worlds
  have scouted. Starbases slowly map their neighborhoods; probes fly
  ahead of you.
- **Expand.** Worlds are claimed, designated for a job, and built up
  with industry and construction.
- **Exploit.** Every ship, base and gate has a raw-material bill --
  chemicals, metal, supplies and trillum -- paid out of a planetary
  economy that can starve, riot or get addicted to ambrosia.
- **Exterminate.** Combat is resolved shell by shell, from deep space
  down to the ground, with a published table of what destroys what.

## Conventions used here

- Key names appear as `F3`, `Enter`, `Esc`. Combinations are written
  out (`Ctrl+C`).
- Menu choices are written `Menu ▸ Item`, e.g. *Game ▸ Next turn*.
  Each menu item also has a one-letter accelerator shown in its
  label; the letter is not always the first one (the original chose
  `caNcel orders` and `auTo attack`).
- Coordinates are always **relative to your capital**, which reads as
  `0,0`. North is +Y. Sector means the same thing as star system
  here: one cell of the square grid the map shows.
- Chapter 8 lists every command, key and status window in one place;
  the reference appendix (last chapter) reproduces the game's actual
  data tables, so a number quoted here and a number the simulation
  uses are never two different numbers.

## Where the name comes from

*Anacreon* was itself named after the ancient Greek poet.
*Reconstruction 4021* was the subtitle of the 2004 release -- the
year, in the game's own fiction, that the old empire fell apart and
the reconstruction began. Re:creon keeps both halves: it is the
original game, reconstructed once more.

The rest of this manual assumes you have never played the original.
If you have: nothing here will surprise you, and that is the point.
