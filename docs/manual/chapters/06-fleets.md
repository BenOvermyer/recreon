# Fleets and Movement

> *Amateurs discuss tactics. Professionals discuss fuel.*
> -- inscription, unofficial, on the wall of the Logistics Directorate

## What a fleet is

A fleet is a named pile of ships and cargo sitting in one sector --
yours or nobody's -- with a destination, a fuel load, and standing
orders. *Fleet ▸ Deploy* creates one out of the ships and cargo at
any object you select: a world, a base, or another fleet. Each empire
can field thirty fleets; the map can hold two hundred and forty
between all of them.

Fleets are not uniform. A fleet's **type** is worked out from what
it *lacks* -- one transport hides inside a battle fleet and drags the
whole thing down -- and the type decides the speed:

| Fleet type | Composition | Sectors per year |
| --- | --- | --- |
| Standard fleet | contains transports, fighters or starships | 1 |
| Advanced-warp fleet | penetrators and jumpships, nothing slower | 2 |
| Penetrator force | only penetrators (with escorts of hunter-killers) | 2 |
| Jump fleet | jumpships and jumptransports (and hunter-killers), no sublight hulls | 10 |
| Hunter-killer force | hunter-killers alone | 10 |

Movement is measured with a **Chebyshev metric**: the cost of a move
is the larger of the horizontal and vertical distance, so a diagonal
sector is exactly as cheap as an orthogonal one and fleets travel in
straight lines, diagonally included. Your coordinates are relative to
your capital, +Y north; another empire's coordinates are relative to
theirs, and typing one into your destination prompt gets you what you
deserve.

## Fuel: the trillum treadmill

Every ship's hold is part fuel tank: each type has a capacity and a
consumption per sector, and **fuel is trillum** -- the only fuel
there is. Fleet movement burns it; standing in space burns a tenth of
the same per-year rate whether the fleet moves or not. A fleet that
runs dry stops dead and reports its status as *out of trillum*, and
the only way out of that is *Fleet ▸ Refuel* on a friendly world or
base with reserves.

The numbers have teeth. A hunter-killer sips fuel by sector and
carries a deep tank -- that is what raiders are made of. A starship
drinks 1.4 times a transport's rate per sector and moves at half the
speed of anything crossing its own space, which is why capital fleets
live off base chains. And raw trillum as cargo is expensive to ship:
100 kilotons a transport.

Refuel early, refuel where the reserves are: every world's class
sets how much trillum it started with (a Barren world's 1,200 beats
your Paradise's 600), reserves do not grow back fast, and a fuel
picture is a strategic map in its own right. The scouts' reports of
enemy reserves, remember, are estimates -- the status windows show
another empire's holdings in a rough notation (see chapter 8), and
your own in exact hundreds.

## Cargo and loading

Ships that carry: transports (5 legions, 3 megatons of chemicals,
2 of supplies), jumptransports (a fifth of a transport), and cargo
itself. *Fleet ▸ Transfer* moves ships or cargo between two fleets
in the same sector. When you deploy an attack, the grouping screen
auto-loads troops into empty transport slots in the groups -- and
beware the original's temper: changing a slot's ship type, or its
count, spills that group's whole cargo back into the common hold,
soldiers included. Load your groups last, or load them and then
leave them alone.

## Standing orders

*Fleet ▸ Orders* compiles a program for a fleet -- the original's
most ambitious interface, and still the fastest way to run a police
force:

```
DEST <coordinates or name>   set destination
TRANS <resource> <amount>    transfer cargo at arrival
SRMS                         sweep minefields
WAIT <years>                 sit
REPE                         repeat the order list
ABORT                        return to base
DEST <place> / TRANS / ...   chain as many lines as you like
```

Compiled orders move fleets and dump cargo automatically each year
without touching anything; a supply fleet on a repeat loop
`DEST convoy route / TRANS sup 2000 / WAIT 1 / REPE` is a convoy
that never needs a signal officer again. *caNcel orders* wipes the
program. Orders break silently on arrival if the target has vanished
-- read the news, it will tell you.

## Probes

*Fleet ▸ Probe* pokes a destination you already know with a sensor
pack: up to ten per empire, each launched probe lands its news the
following turn and is ready again. Probes are cheap knowledge about
specific places; starbase scans (chapter 2) are patient knowledge
about areas; and neither is a substitute for a fleet whose orders
say *DEST and find out*.

## Hazards of the deep

- **Nebulae** blind: any nebula hides what sits in it from remote
  sensors; a **dark** nebula additionally stops a scout's line of
  sight, so worlds behind one stay unknown; a **dense** nebula is a
  wall -- warp movement into it simply fails, and a jump that ends
  in one makes the news instead of the destination.
- **Black holes, pulsars, wormholes** damage or vanish anything
  passing through; wormholes also move things, to somewhere.
- **Minefields** (chapter 5) hit jump traffic only.
- **Enemy disrupters** stop jump movement outright inside their
  field -- friendly ones, as noted, speed *warp* traffic to jump
  pace instead.
