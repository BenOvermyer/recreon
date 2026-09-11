# Worlds and Their Economies

> *A world is worth exactly what its factories say it is worth, and
> not one headline more.*
> -- Ledger of the Fourth Reconstruction

Every planet is a small economy with a population, a technology
level, and a stack of industries that turn raw materials into the
things the empire needs. Worlds are where the game is actually won;
fleets only spend what the worlds produce.

## The anatomy of a world

A world's close-up (`z` on its sector) shows its:

- **Class** -- what the world physically is: Paradise, Ice world,
  Gas Giant, Ancient ruins, and the rest of the twenty-two classes.
  The class is permanent except by terraforming (see below), and it
  sets the world's trillum reserve, how much its terrain helps
  ground defense, and the percentage of each industry that runs
  effectively there. The class table in the appendix lists all of
  them; a Paradise world is worth more than a Barren one at the same
  population, and the map glyph tells you which is which at a glance.
- **Designation** -- the job you assign: agricultural world, metal
  mine, shipyard base, university, capital, and so on. Designations
  require a minimum technology, set the world's principal industry,
  and change how its leftover industry distributes. You change them
  with *Worlds ▸ Designate*.
- **Population**, counted in units of 100 million. Population grows
  toward the maximum its technology supports; the base figure for a
  world at 50% efficiency runs from 3 (a hundred million, pre-tech)
  to 3,000 (three hundred billion, gate technology).
- **Technology level**, 0 to 10, from pre-tech to gate. It governs
  what the world's industry can produce at all, and it can outrun
  the empire's own level -- which matters for research, not just
  production.
- **Efficiency**, 0..100: how well the population actually works,
  worn down by famine, ambrosia withdrawal, occupation and shock,
  and rebuilt in calmer years.
- **Revolution index**, 0..100: unrest. Unrest grows with distance
  from the capital, with the empire's overall mood, with starvation
  and with garrisons on quiet worlds. Above 30 the world mutters,
  above 43 it marches, above 66 it rioted last week; above 75 it
  may rebel outright. A rebellion either gets crushed by the local
  troops and ninjas or succeeds, and the world goes independent.
  The capital never rebels. You can see the mood building in the
  news long before the map changes color.
- **Hold cargo**: troops, ninjas, and stocks of the four raw
  materials sitting in the world's warehouses, plus its fixed
  defenses spread across the orbital shells.

## Production: where everything comes from

Each year, a world's **industrial potential** -- driven by
population, technology, class and efficiency -- is distributed among
the nine industries:

| Industry | Makes |
| --- | --- |
| food factories | supplies |
| chemical plants | chemicals |
| metal mines | metal |
| trillum mines | trillum |
| bio-tech labs | ambrosia (and ninjas, with the right class) |
| ship yards | fighters and transports, mostly |
| jumpship yards | jumpships, hunter-killers, jumptransports |
| starship yards | starships and penetrators |
| transport yards | transports and fighters |

Yards consume raw materials (the cost tables are in the appendix)
and spit out hulls every year without being told; the split between
what a world keeps as raw material and what it converts is set by
its designation and by the **ISSP** slider.

**ISSP** (*Worlds ▸ ISSP*) is four sliders -- one for each raw
material: chemicals, metal, supplies, trillum -- each set 0 to 10,
with 5 meaning the world produces exactly what it needs of that
material. Set a world's supplies slider to 10 and it pours industry
into food factories to feed its neighbours; set it to 1 and it
starves politely and lets its chemical plants eat the difference,
hoping someone ships. The budget is shared, so every slider raised
takes industry from somewhere else.

Raw output is a forecast (*Worlds ▸ Production*), not a promise:
an exhausted trillum reserve, or a world that cannot feed itself,
will produce less than the screen projects.

## Feeding everyone

Supplies are the economy's heartbeat. Every billion people consume
25 megatons of supplies a year. A world that cannot produce them
from its own food factories is **not self-sufficient**, and must be
shipped food by fleet -- run the convoy aground, and the news starts
reporting starvation. Famine kills population, drops efficiency and
pushes the revolution index up; in the old DOS manual's phrase, a
blockaded world is a loyal world right up until it isn't.

## Ambrosia

Bio-tech technology (level 7) unlocks ambrosia, and ambrosia is a
trap with a payoff attached. Worlds with bio-tech labs produce it;
at 11.5 kilotons per billion people a year it holds off addiction,
each year a world's population has a 25% chance of becoming
dependent. An addicted world kept off its drug suffers mass
casualties -- and the deaths drag efficiency and the revolution
index down into the basement. Delivered on time, though, ambrosia
makes the population work harder: an addicted-and-satisfied world
runs its industry at 145%. Many late-game empires are, functionally,
drug dealers with a navy. Independent worlds drift toward
addiction anyway; liberating a world does not liberate its
habits.

## Special worlds

- **Capital** (*Worlds ▸ Designate* to move it, if you can stomach
  the staff's objections): +12% annual research chance, immune to
  rebellion, and in some scenarios the loss of it loses the empire.
- **University worlds** (designatable at jump tech) are the engine
  of research -- see chapter 4.
- **Ancient ruins** worlds from the old empire yield a small
  research bonus and, according to scenario authors, occasionally
  something worse.
- **Hostile life** worlds have natives: a strong garrison deters
  them, and under some empires they can be enlisted as ninja legions
  instead of fighting them.
- **Terraforming** worlds are mid-transformation -- see below.

You cannot designate every world every job: universities need jump
technology, ambrosia worlds need bio-tech, ninja worlds need
starship tech, and the gate-tier variants of every base type need
gate tech. The appendix table gives the minimums.

## Terraforming

*Worlds ▸ Terraform* (warp technology, and a world already paid for
in metal and patience) rewrites a world's class. The target class is
drawn from a short list each class may become -- a Desert can turn
greener, an Ice world can be melted -- and harder targets terraform
more slowly: Paradise, the best land there is, completes on about
one annual roll in ten, and every attempt carries its own standing
chance of catastrophic failure, which leaves the world something
worse than it started. While the job runs the world is a
Terraforming world: half its former industry and a fraction of its
efficiency. Finish it and you own the empire's best kind of real
estate: a new Paradise. Fail to protect it and the enemy inherits
it.

## Designing for the long run

Three habits separate a Reconstruction that outlives its first
century from one that dissolves into the news archive:

1. **Match designations to classes.** A trillum mine on a Desert
   runs at 190% strength; the same mine on a Poisonous world runs at
   80%. The class table in the appendix says exactly where each
   industry earns its keep.
2. **Watch the revolution index like fuel.** Garrisons put down
   revolts, but quiet worlds resently garrisoned push unrest the
   other way; military index is a dial, not a setting.
3. **Feed the labs, then the yards.** Production you cannot scout
   with is production the enemy will take delivery of.
