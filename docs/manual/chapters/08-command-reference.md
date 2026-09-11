# Command Reference

> *The map is the argument. Everything else is paperwork.*
> -- marginalia, Imperial staff college exercise files

This chapter is the whole interface in one place: every key, every
menu item, every window. Commands are entered by picking them off
the menu and answering prompts -- the shipped original never had a
typed-command parser, and this recreation does not add one.

## Function keys

| Key | Opens |
| --- | --- |
| `F1` | Help window -- the original's topic index |
| `F2` | Menu bar (same as `m`) |
| `F3` | World status window |
| `F4` | Military status window |
| `F5` | Fleet status window |
| `F6` | Fleet contents window |
| `F7` | News window |
| `F8` | Empire status window |
| `F9` | Names and records window |
| `F10` | Map (closes whatever window is open) |

`F3` and `F4` are one window: the world status table stacked over
the military status table, both listing the same worlds in the same
order, so the two halves line up row for row. `F5` and `F6` are the
same trick with fleets: position over contents. `PageUp` and
`PageDown` page through windows; `Esc` closes them.

The status tables are stricter about fog than the map is: a foreign
**world** is listed only if scouted, since the tables are made of
numbers and knowing a world exists tells you none of them. A merely
*known* enemy **fleet** does get a row, reading `(unknown)` and
`(out of range)` -- being warned that something is out there is the
point of that window.

## Direct keys on the map

| Key | Action |
| --- | --- |
| arrows / `h` `j` `k` `l` | Move the cursor |
| `f` | Fleet roster |
| `b` | Construction screen |
| `w` | Warp link frequencies |
| `d` | Defense grid for the cursor's world |
| `z` | Close-up of the cursor's object |
| `i` | Production report for it |
| `x` | Self-destruct it (if it is yours, and you are certain) |
| `g` | The prologue menu |
| `m` or `F2` | The command menu bar |
| `n` | Next turn -- end the year |
| `q` | Quit (asking first if unsaved) |

The close-up and production reports always act on whatever the
cursor is over, which is how the original reached them too.

## The menu bar

Seven pull-downs. The letter in parentheses is the accelerator,
counted exactly as the original wrote it -- which is why `caNcel
orders` answers to N and `auTo attack` to T.

**Info (I)**

- (A)bout Re:creon
- (D)OS shell

**Game (G)**

- (P)ause game
- (S)tatus hardcopy
- (N)ext turn
- (Q)uit

**Empire (E)**

- (S)end message
- (R)ead messages
- (T)rade technology
- (L)ink frequencies

**Worlds (W)**

- (C)lose up
- (D)esignate
- (P)roduction
- (I)SSP
- (N)ame
- (R)emove name
- (L)iberate
- (S)elf-destruct
- (T)erraform

**Fleet (F)**

- (D)eploy
- (C)hange destination
- (T)ransfer
- (A)bort/join
- (R)efuel
- (S)RM sweep
- (O)rders
- ca(N)cel orders
- (P)robe

**Build (B)**

- (S)ite status
- (N)ew construction site
- (A)bort construction

**Ministry of War (M)**

- (A)ttack
- au(T)o attack
- (L)aunch LAMs
- (D)efenses

*Status hardcopy* is the game's old printout -- *Game ▸ Status
hardcopy* builds the full report of your worlds, fleets and
holdings, and lets you write it to a file. Its numbers are encoded
the way a dot-matrix printer had room for: your own holdings in
hundreds (so `42` means about 4200, and `++` is past 99), while
another empire's read as estimates -- `no`, `y` plus thousands, or
`y+`, with raw materials as `--` because you cannot see them at
all.

## Interactive combat keys

The grouping screen, first. Build up to nine groups out of the
ships and cargo in the attacking fleet:

| Key | Action |
| --- | --- |
| `up` / `down` | Select group |
| `left` / `right` | Change its ship type |
| `space` | Auto-fill cargo |
| `enter` | Load an amount |
| `m` / `n` | Load men / ninjas |
| `Esc` | Confirm the grouping and fight |

Then, round by round:

| Key | Action |
| --- | --- |
| `e` | Engage -- fight the round |
| `m` | Manoeuvre a group: advance, retreat or hold |
| `t` | Assign a group's target |
| `d` | Damage report from last round |
| `r` | Retreat the attack |

Groups begin in deep space aiming at nothing. A player who only
presses `e` fights a battle in which nobody closes and nobody
fires, forever: `m` and `t` are the decisions the screen exists
for.

## Construction and defense screens

`b` lists the world's sites: `c` starts a new construction (pick
the kind, pay the materials, point at the object), `a` aborts one.
`w` opens the warp-link frequency screen, where each gate and link
of yours is retuned -- both ends have to agree, and retuning can
strand your own fleets mid-network.

`d` opens the defense grid: four fixed types, five shells, each
type's five percentages forced to total 100. The normalizer's
fallback layer is **sub-orbit**: ground percentages for things that
cannot land, any shortfall, and any rounding remainder all park
there. Percentages typed outside 0..100 store as zero, not as the
nearest bound.

## Fleet roster keys

The roster (`f`) lists your scouted fleets. Selecting one and
pressing enter opens its detail screen, where the Fleet menu items
act on it directly; the transfer, abort and refuel screens all pick
their counterpart fleets from the same sector.
