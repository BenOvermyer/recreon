# License and source provenance

## Re:creon contributions

Ben Overmyer's original contributions to Re:creon are offered under the
[MIT License](../LICENSE.md). This includes original code, documentation,
and the new `frontier.scn` scenario only to the extent that each is Ben's
original work. The grant does not replace any rights needed for material
copied or adapted from Anacreon or another contributor.

The package metadata deliberately does not declare one license for the
entire distribution: its contents have different provenance.

## Original Anacreon material

- `original/` contains the recovered Pascal source and thirteen original
  scenarios for *Anacreon: Reconstruction 4021*, version 2.0. The game's
  [DOS Edition page](https://neurohack.com/anacreon/DOSEdition.html) offers
  the [source archive](https://neurohack.com/downloads/DOSAnacreonSource20.zip)
  and [game archive](https://neurohack.com/downloads/DOSAnacreon20.zip).
  `original/TMA.PAS` credits George Moromisato and carries an
  all-rights-reserved notice and warranty disclaimer.
  `original/SORT.PAS` and `original/LSORT.PAS` also carry Borland copyright
  notices; `original/COLORS.INC` carries a Thinking Machine Associates notice.
- Thirteen files in `src/recreon/data/scenarios/` adapt those original
  scenarios. All have revised titles and introductions. `corsairs.scn`
  and `vhalsecc.scn` also rename places and empires; `longsleep.scn` and
  `fourheirs.scn` have structural repairs. Their remaining scenario prose
  and game data still draw on the originals. The
  [scenario provenance](../src/recreon/data/scenarios/README.md) records
  the changes.
- Much of the Python game logic and its tables closely translate the Pascal
  implementation. The MIT grant above applies to Ben's original expression
  and contributions, not to any underlying third-party expression or data.

No permission terms for reuse, adaptation, or redistribution of the DOS
source and scenarios are recorded in this repository. Availability for
download and a freeware release are not themselves a license for those
uses. Permission for distributing the original material and adaptations,
including a bundled executable, remains to be established with the
appropriate rights holders. Record that evidence here before presenting
the complete game as MIT-licensed or publishing a release package.

## Archive verification

Checked against the official downloads on 2026-10-01: all 83 files from
`DOSAnacreonSource20.zip` match their counterparts in `original/` byte for
byte, and all 13 `.SCN` files from `DOSAnacreon20.zip` match the files in
`original/scenarios/` byte for byte. The archives contain no separate
license file or explicit grant for redistribution or adaptation.

| Archive | SHA-256 |
| --- | --- |
| `DOSAnacreonSource20.zip` | `e48e11e26f9bf02044f341d1cee9ab78e87467c056b25b3ce8679d9bff6e8a34` |
| `DOSAnacreon20.zip` | `401a3bdf820596c9f64c1bec83d552ef451d3f26feff1aaca6ade9ca2ca4dd62` |
