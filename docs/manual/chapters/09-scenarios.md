# Scenarios

> *Every scenario is an argument about history, written by someone
> who expects to be contradicted.*
> -- attributed to the authors of the original twelve, in jest

A galaxy is not generated; it is *authored*. Every game of Re:creon
starts from a scenario file -- a plain-text list of worlds, owners,
fleets, nebulae, minefields, empires and prose, loaded in one
forward pass that asks you for the player count and your empire's
name *while* it reads. There is no procedural "random map" button,
because the original never had one.

## The fourteen you ship with

Thirteen of them are the scenarios that came with Anacreon:
Reconstruction 4021, imported byte-identical except for line 2 (the
title), so they play exactly as they did in 2004. The fourteenth,
*frontier.scn*, is new content written for this recreation.

| File | Title | Original name |
| --- | --- | --- |
| `frontier.scn` | Frontier | -- (authored for Re:creon) |
| `firstlight.scn` | First Light: 4021 | Reconstruction: 4021 |
| `twocrowns.scn` | Two Crowns | East vs. West |
| `triad.scn` | Triad | Trinity |
| `fourheirs.scn` | The Four Heirs | The Four Princes |
| `outerreach.scn` | The Outer Reach | The Periphery |
| `corsairs.scn` | Corsairs of Meridian | The Pirates of Jakarta |
| `boundary.scn` | The Boundary Stones | Algerian Fences |
| `reckoning.scn` | The Reckoning | The Aftermath |
| `longrun.scn` | The Long Run | The Gauntlet |
| `longsleep.scn` | The Long Sleep | A Rude Awakening |
| `thousandsuns.scn` | The Thousand Suns | Imperium Galactica |
| `veil.scn` | The Veil | The Nebula |
| `vhalsecc.scn` | Vhalsecc | Arronax |

**First game?** *First Light* is the introduction the original
boxed with the manual: a small, legible galaxy, and the scenario
the manual's advice was written against. *Corsairs of Meridian* is
where to go once you want the pirates to teach you about convoy
routes; *The Veil* is the nebula-warfare exam, authored around a
galaxy of dust you cannot scout through.

## What the introductions are, and where the prose comes from

Every scenario opens with one or more pages of background text --
read them; in several cases they contain hints that are otherwise
only discoverable by losing something. That prose is the original
authors', untouched.

The same files also carry **per-object background**: seven of the
shipped galaxies index prose blocks to specific worlds, starbases
and stargates, so closing up on a named place (`z`) or conquering
it can print the author's words for *that object* instead of a
generic report. When you take a place that has a passage written
about it, the conquest screen says so.

## Why two scenarios sometimes refuse to load

Each scenario places a mix of hand-authored and randomly-rolled
worlds, and the random rolls ask for open sectors inside their
zone -- up to a hundred attempts, and then they give up rather than
stack two worlds in one sector. The densest galaxies (*The Long
Run*, *The Long Sleep*, packed at 200 worlds) will therefore refuse
some rolls: roughly one in fifteen in the denser cases. This is the
authors' own density and the original's own failure mode -- the DOS
build quit on the same rolls. **Start a new game; it will place.**

## How a new game is assembled

1. Choose the scenario. The header (its declared format, its title)
   is checked before anything else happens; files from the original
   declare version 10.
2. The introduction pages scroll by.
3. Choose how many empires are run by human players -- one, two, or
   more -- and which slots those humans take.
4. Name each human empire, or take a random one from the original's
   table of 59. Computer empires are seated as their scenario
   specifies and pick up personalities at load: pirate, kingdom,
   guardian or berserker, each with its own temperament for
   escalating from raiding to annihilation.

Randomness in world placement, combat and events all runs through a
ported copy of the original's own generator, seeded by the clock
(the original did the same -- the galaxies players saw in 2004
never existed twice), so a scenario can genuinely unfold differently
on every run.

## Writing your own

The shipped files are plain text and readable: directives for
zones, `CreateWorld` blocks, empire seats, nebulae, the
`BEGINTEXT`/`ENDTEXT` prose blocks. Copy the smallest one that
looks like the game you want and start editing -- they are lightly
commented, and the scenario parser's test suite is a catalogue of
every accepted directive. A scenario that disagrees with the format
loses, every time -- the original files are the specification.
