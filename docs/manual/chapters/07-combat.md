# Combat and Conflict

> *The shells are the same five in every system in the galaxy. Only
> the arithmetic changes.*
> -- Gunnery handbook of the Reconstruction, first edition

Combat happens when your fleet and someone else's object share a
sector. Two commands reach it from the map, both under *Ministry of
War*:

- **Attack** opens the interactive battle: you command each group
  round by round.
- **auTo attack** hands the whole fight to the same tactical routine
  the computer empires use and shows you the result. If you have
  ever wondered what the AI thinks of your formation, this is the
  button that says so.

Defensively, there is no button: enemy computer empires attack you
the moment they weigh the odds as favourable, and the fight simply
appears in the news. Position is diplomacy.

## Who can be fought

Attacks target enemy fleets in the sector, then enemy objects. One
rule surprises people the first time: **a fleet in orbit screens the
world beneath it.** If hostile fleets are present, the world is not
offered as a target at all -- you fight the navy first, and only
then the planet. The same is true in reverse when you are defending:
one surviving corvette in low orbit keeps your capital legally
untouchable, which is occasionally worth more than the corvette.

## The five shells

Everything in a fight stands at one of five altitudes, and combat
resolves from the outside in, one round at a time:

1. **Deep space** (`DpSpc`) -- where fleets arrive.
2. **High orbit**
3. **Orbit** -- where starbases and defense satellites live.
4. **Sub-orbit** -- the catch-all layer; the defense grid puts any
   remainder here.
5. **Ground** -- where populations die.

Groups start in deep space with no targets. Ships at the same shell
as a target shoot at it; shells that are uncontested let the fight
descend toward the surface. This means combat is mostly a race and
an alignment problem: the attacker must *close*, and the defender
survives by making every shell above the ground cost more than it
is worth.

## The arithmetic

Each round, every group fires at its target. The damage a weapon
does is looked up in the combat table -- attacker type against
defender type -- and modified by the attacker-vs-defender technology
table, the defender's terrain (ground fighting only), and any base
in the sector (command bases 150%, fortresses 250%, outposts 125%).
Points accumulate against each defender; **100 points destroy one
unit**, 200 destroy two, and so on. The full tables are in the
appendix; the short version is that a fighter squadron does 15
points of damage to a hunter-killer where a starship does 250 to the
same target -- but the fighter costs a twentieth the metal and is
worth five points to your bookkeeping against a starship's two
hundred. Cheap hulls swarm; expensive hulls win the rounds nobody
can afford to repeat; transports are cargo that happens to be on
fire.

A world under attack answers with its **ground-defense missiles** --
a salvo sized by the world's technology (up to 2,759 at gate tech),
of which the attackers shoot a fixed number down on approach per
ten ships depending on hull type. Fighters catch nothing; starships
catch twenty apiece.

The **defense grid** (`d` on any world you own) is where you decide
what that fight looks like before it starts: percentages of each of
the four fixed defenses -- LAMs, defense satellites, GDMs, ion
cannons -- distributed across the five shells so that each type's
five numbers total 100. The grid normalizes whatever you type, and
**sub-orbit is where every rounding error and impossible request
ends up**, which is worth knowing the first time your even 100/100
split comes back 33/33/33 with a stray 1 parked in sub-orbit.

## Closing: the interactive battle

The attack screen lists your groups -- up to nine per attack -- and
the enemy roster. Groups do nothing unless you tell them to:

- **`m`** manoeuvres a group: advance a shell, retreat a shell, or
  hold station.
- **`t`** gives a group its target.
- **`e`** fights the round.
- **`d`** shows the damage detail from last round, and **`r`**
  extracts everyone.

A player who only ever presses `e` will sit in a perfect battle in
which nobody moves, nobody aims and nobody fires, forever. Closing
and aiming are the entire point of the screen -- the original's
author put it in the manual's place where the help file could not:
the computer aims for you only when you let it.

When you load transports for an assault the grouping screen
auto-loads troops for you, with the two caveats from chapter 6: the
auto-loader prefers men over ninjas, and changing a group's ships
spills its cargo back to the hold.

## After the shooting

Resolution cascades down: fleet wins the shells and the world is
next; a beaten world's survival turn comes its own arithmetic of
population, morale, the power of its remaining weapons and the size
of the occupying force -- worlds that lose their navy are liable to
sue for terms rather than die on the ground, and the technology
band a world sits in changes how often terms are offered. A
conquest puts the world in your empire: population and industry
change hands intact, morale shock and revolution index arrive
together, and the news runs a headline either way. Scenarios with
written background text give conquered worlds their own epitaphs.

Losses are tallied where you can read them -- the news headlines
carry the casualty figures, and the empire status and records
windows (`F8`, `F9`) report what survived -- and destroyed
construction sites and stargates are announced as destroyed whether
or not the wreckage agrees.

## The tools you use to say no

- **LAMs** (*Ministry of War ▸ Launch LAMs*): light attack missiles,
  stockpiled as a base's fixed defense and fired without moving a
  fleet or risking a fight. Against an enemy fleet the salvo spreads
  by what each hull is worth, concentrating on the ships actually
  worth killing -- a LAM barrage can clear a sector's navy before
  the invasion starts; against a world it strips fixed defenses
  evenly. The missiles are spent whether they hit or not, the
  target cannot intercept, and the news will be very clear about who
  fired. It is the cheapest violence in the game and the least
  deniable.
- **Self-destruct** (`x` / *Worlds ▸ Self-destruct*): what you do
  to your own world when it is clearly about to change hands.
  Industries die, population dies, the enemy inherits a rock.
- **Minefields, disrupters, fortresses**: chapter 5. A war won in
  the construction menu is a war not fought.
