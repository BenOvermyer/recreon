# Bundled scenarios

The scenarios the game ships with, and what each one came from.

`frontier.scn` is new content authored against the file format — it reproduces
no galaxy the original shipped. The other thirteen adapt the scenarios from
`original/scenarios/` under new titles and filenames. A direct line comparison
shows that all thirteen also revise their introductions. `corsairs.scn` and
`vhalsecc.scn` carry internal name changes, including some background text;
`longsleep.scn` and `fourheirs.scn` carry structural repairs. They are not
byte-identical copies or guaranteed to produce identical playthroughs.

| Bundled | Title | From | Original title |
| --- | --- | --- | --- |
| `boundary.scn` | The Boundary Stones | `FENCES.SCN` | Algerian Fences |
| `corsairs.scn` | Corsairs of Meridian | `JAKARTA.SCN` | The Pirates of Jakarta |
| `firstlight.scn` | First Light: 4021 | `INTRO.SCN` | Reconstruction: 4021 |
| `fourheirs.scn` | The Four Heirs | `PRINCES.SCN` | The Four Princes |
| `longrun.scn` | The Long Run | `GAUNTLET.SCN` | The Gauntlet |
| `longsleep.scn` | The Long Sleep | `AWAKEN.SCN` | A Rude Awakening |
| `outerreach.scn` | The Outer Reach | `PERIPHER.SCN` | The Periphery |
| `reckoning.scn` | The Reckoning | `AFTERMAT.SCN` | The Aftermath |
| `thousandsuns.scn` | The Thousand Suns | `IMPERIUM.SCN` | Imperium Galactica |
| `triad.scn` | Triad | `TRINITY.SCN` | Trinity |
| `twocrowns.scn` | Two Crowns | `EASTWEST.SCN` | East vs. West |
| `veil.scn` | The Veil | `Nebula.SCN` | The Nebula |
| `vhalsecc.scn` | Vhalsecc | `ARRONAX.SCN` | Arronax |

## Text and name changes

The introductions in every imported file were revised. Most per-object
background passages remain from the original files, but `corsairs.scn` and
`vhalsecc.scn` also replace references to Jakarta and Arronax with Meridian
and Vhalsecc. Their scenario definitions use the renamed places and empires
consistently. The character art in `corsairs.scn` also changed during the
import. Compare the bundled files with `original/scenarios/` when tracing a
passage or scenario rule back to its source.

## The two that were repaired

Two of the thirteen could not load, in the DOS build as much as here. These
are the two changes to scenario structure that make their bundled versions
playable:

- **`longsleep.scn`** (AWAKEN) asked for 212 worlds — 36 explicit plus 176
  random — against `MaxNoOfPlanets = 200`. The original has no bounds check
  and would have written past the planet array. Twelve worlds came off the
  central pool, which is the largest single group and the only one outside the
  four-way symmetry the scenario is built around (12 each for four players, 16
  each for West/East/North/South). The `ClassTable` above it is a percentage
  distribution, so the count is independent of it.

  It now fills the array to exactly 200, which leaves it as tightly packed as
  `longrun.scn`: `GetRandomXY` gives up after 101 tries, so roughly one roll in
  fifteen still reports `No room for random world in zone`. Start a new game
  and it will place. That density is the scenario's own, not something the trim
  introduced.

- **`fourheirs.scn`** (PRINCES) had a stray `0 ; (reserved)` token in its one
  `CreateStarbase` block. Every other scenario's has six fields after the
  coordinate — type, tech, base planet, empire, population, efficiency — and
  this one had seven, so the block ran long and its trailing cargo amount was
  read as the next directive. The stray line is deleted; the remaining six
  match the block's own comments.

`tests/test_newgame.py` pins both fixes, and keeps the originals' defects
pinned separately against `original/scenarios/`, which is untouched.

## A third that fails on an unlucky roll

`longrun.scn` (GAUNTLET) packs 172 worlds into small zones and legitimately
fails to place them on a few per cent of new games. Nothing is wrong with it —
the DOS build failed on the same rolls. Every shipped scenario carries `Seed 0`
(Randomize), so the galaxy is rolled fresh each time and a failure just means
trying again.
