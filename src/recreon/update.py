"""Annual universe update.

Port of UPDATE.PAS -- the world update, which is the whole economy. The
per-step order in :func:`update_world` matters: production consumes the raw
materials produced earlier in the same year, and population is fed only after
it has already grown.

Cargo is carried through production as a plain int dict rather than being
clamped at every step. The original does the same (TotalCargoArray is
LongInt where the stored CargoArray is 0..9999), and lets intermediate totals
overshoot before PutTotalCargo clamps them back. Clamping early would silently
change output.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .datacnst import (
    ADDICT_DEATH_COEFF,
    ADDICT_EFF_COEFF,
    ADDICT_REV_I_COEFF,
    AMBROSIA_ADJ,
    CHANCE_TO_ADDICT,
    DRUGS_PER_BILLION,
    K4,
    K6,
    SUPPLIES_PER_BILLION,
    TECH_LVL_INC,
    BasePop,
    ClassIndAdj,
    ConsCargoNeeded,
    DefAdj,
    DefBuildRate,
    NewIndRawN,
    OptMilitary,
    RawM,
    TechAdj2,
    TechDev,
    ThgAdj,
)
from .galaxy import Location, XYCoord, limbo
from .intrface import (
    create_starbase,
    create_stargate,
    get_optimum_indus,
    next_starbase_slot,
    next_stargate_slot,
)
from .misc import move_things, tech_range, thg_lmt, total_prod
from .news import NewsTypes, add_global_news, add_news
from .primintr import (
    add_name,
    change_rev_index,
    delete_name,
    get_defined_name,
    get_fleets,
    get_base_type,
    get_capital,
    get_cargo,
    get_class,
    get_coord,
    get_efficiency,
    get_empire_technology,
    get_population,
    get_rev_index,
    get_status,
    get_tech,
    get_terraform_target,
    get_type,
    initialize_issp,
    location2index,
    put_cargo,
    put_indus,
    put_mine,
    put_trillum_reserves,
    set_class,
    set_efficiency,
    set_population,
    set_status,
    set_tech,
    set_type,
    total_rev_index,
    trillum_reserves,
    troop_strength,
)
from .types import (
    CARGO_TYPES,
    STARBASE_TYPES,
    STARGATE_TYPES,
    MAX_INDUS_INDEX,
    MAX_RESOURCES,
    SHIP_TYPES,
    Empire,
    IDNumber,
    IndusTypes,
    ObjectTypes,
    SpecialConditions,
    TechLevel,
    TechnologyTypes,
    WorldClass,
    WorldTypes,
    empty_quadrant,
    indus_range,
)
from .utils.int_utils import greater_int, lesser_int, rnd, rnd_var
from .utils.pascal import pascal_round, trunc

if TYPE_CHECKING:
    from .environ import GameEnvironment

T = TechnologyTypes
IT = IndusTypes


# --- Per-class tables local to UPDATE.PAS ------------------------------------

#: Yearly chance that terraforming to this class completes.
ProbabilityOfChange: dict[WorldClass, int] = {
    WorldClass.AmbCls: 14,
    WorldClass.ArdCls: 20,
    WorldClass.ArtCls: 0,
    WorldClass.BarCls: 20,
    WorldClass.ClsJ: 17,
    WorldClass.ClsK: 17,
    WorldClass.ClsL: 17,
    WorldClass.ClsM: 16,
    WorldClass.DrtCls: 13,
    WorldClass.EthCls: 20,
    WorldClass.FstCls: 21,
    WorldClass.GsGCls: 13,
    WorldClass.HLfCls: 0,
    WorldClass.IceCls: 22,
    WorldClass.JngCls: 21,
    WorldClass.OcnCls: 18,
    WorldClass.ParCls: 10,
    WorldClass.PsnCls: 16,
    WorldClass.RnsCls: 0,
    WorldClass.UndCls: 22,
    WorldClass.TerCls: 0,
    WorldClass.VlcCls: 17,
}

#: Yearly chance that terraforming to this class ends in disaster. Classes
#: that can never be reached are 100, so attempting them always fails.
ProbabilityOfChaos: dict[WorldClass, int] = {
    WorldClass.AmbCls: 3,
    WorldClass.ArdCls: 1,
    WorldClass.ArtCls: 100,
    WorldClass.BarCls: 1,
    WorldClass.ClsJ: 1,
    WorldClass.ClsK: 1,
    WorldClass.ClsL: 1,
    WorldClass.ClsM: 1,
    WorldClass.DrtCls: 2,
    WorldClass.EthCls: 2,
    WorldClass.FstCls: 3,
    WorldClass.GsGCls: 1,
    WorldClass.HLfCls: 100,
    WorldClass.IceCls: 1,
    WorldClass.JngCls: 3,
    WorldClass.OcnCls: 3,
    WorldClass.ParCls: 4,
    WorldClass.PsnCls: 3,
    WorldClass.RnsCls: 100,
    WorldClass.UndCls: 2,
    WorldClass.TerCls: 100,
    WorldClass.VlcCls: 4,
}

#: What the world becomes when terraforming goes wrong.
TargetOfChaos: dict[WorldClass, WorldClass] = {
    WorldClass.AmbCls: WorldClass.ArdCls,
    WorldClass.ArdCls: WorldClass.BarCls,
    WorldClass.ArtCls: WorldClass.BarCls,
    WorldClass.BarCls: WorldClass.IceCls,
    WorldClass.ClsJ: WorldClass.ArdCls,
    WorldClass.ClsK: WorldClass.IceCls,
    WorldClass.ClsL: WorldClass.ArdCls,
    WorldClass.ClsM: WorldClass.DrtCls,
    WorldClass.DrtCls: WorldClass.IceCls,
    WorldClass.EthCls: WorldClass.IceCls,
    WorldClass.FstCls: WorldClass.DrtCls,
    WorldClass.GsGCls: WorldClass.IceCls,
    WorldClass.HLfCls: WorldClass.IceCls,
    WorldClass.IceCls: WorldClass.UndCls,
    WorldClass.JngCls: WorldClass.PsnCls,
    WorldClass.OcnCls: WorldClass.IceCls,
    WorldClass.ParCls: WorldClass.OcnCls,
    WorldClass.PsnCls: WorldClass.BarCls,
    WorldClass.RnsCls: WorldClass.IceCls,
    WorldClass.UndCls: WorldClass.BarCls,
    WorldClass.TerCls: WorldClass.IceCls,
    WorldClass.VlcCls: WorldClass.BarCls,
}

#: Population ceiling by world class.
MaxPop: dict[WorldClass, int] = {
    WorldClass.AmbCls: 4830,
    WorldClass.ArdCls: 4100,
    WorldClass.ArtCls: 3100,
    WorldClass.BarCls: 2340,
    WorldClass.ClsJ: 4610,
    WorldClass.ClsK: 4600,
    WorldClass.ClsL: 4220,
    WorldClass.ClsM: 4800,
    WorldClass.DrtCls: 3580,
    WorldClass.EthCls: 4500,
    WorldClass.FstCls: 4710,
    WorldClass.GsGCls: 2010,
    WorldClass.HLfCls: 4010,
    WorldClass.IceCls: 1920,
    WorldClass.JngCls: 4720,
    WorldClass.OcnCls: 3520,
    WorldClass.ParCls: 5000,
    WorldClass.PsnCls: 2100,
    WorldClass.RnsCls: 4590,
    WorldClass.UndCls: 4500,
    WorldClass.TerCls: 100,
    WorldClass.VlcCls: 3950,
}

#: Revolution-index points per 100 million starved, by tech level. Low-tech
#: worlds are used to famine and revolt less readily. Distinct from the
#: TechAdj in DATACNST.PAS -- UPDATE.PAS shadows the name with its own table.
StarveTechAdj: dict[TechLevel, int] = {
    TechLevel.PreTchLvl: 100,
    TechLevel.PrimitLvl: 100,
    TechLevel.PreAtmLvl: 30,
    TechLevel.AtomicLvl: 20,
    TechLevel.PreWrpLvl: 15,
    TechLevel.WrpTchLvl: 13,
    TechLevel.JmpTchLvl: 12,
    TechLevel.BioTchLvl: 13,
    TechLevel.StrTchLvl: 14,
    TechLevel.PreGteLvl: 14,
    TechLevel.GteTchLvl: 15,
}

#: World types whose surplus a nearby industrial complex may draw on.
_SUPPLY_LINK_TYPES = frozenset(
    {
        WorldTypes.AgrTyp,
        WorldTypes.CheTyp,
        WorldTypes.MinTyp,
        WorldTypes.RawTyp,
        WorldTypes.TriTyp,
    }
)


def _location(game: GameEnvironment, obj: IDNumber) -> Location:
    """A news location for ``obj``. The original leaves XY as Limbo here."""
    return Location(XY=limbo(), ID=obj)


def report_planet_lack(
    game: GameEnvironment,
    sta: Empire,
    obj: IDNumber,
    headline: NewsTypes,
    p1: int,
    other_reports: set[T],
) -> None:
    """Report a shortage once per world per year, and nudge the rev index.

    ``other_reports`` accumulates what has already been reported this year,
    so a world short of three things does not file three separate items for
    the same material.
    """
    material = T(p1)
    if material in other_reports or sta == Empire.Indep:
        return
    add_news(game, sta, headline, _location(game, obj), p1, 0, 0)
    other_reports.add(material)
    change_rev_index(game, obj, 1)


# --- Production --------------------------------------------------------------


def produce_trillum(
    game: GameEnvironment, obj: IDNumber, tri_prod: int, tri_avail: int
) -> int:
    """Draw ``tri_prod`` trillum from the world's reserves.

    Returns the amount actually produced. Reserves deplete at a hundredth of
    what is mined, and running low raises the revolution index.
    """
    tri_reserves = trillum_reserves(game, obj)
    loc = _location(game, obj)
    emp = get_status(game, obj)

    tri_avail = lesser_int(tri_avail, MAX_RESOURCES)
    tri_prod = lesser_int(tri_prod, MAX_RESOURCES - tri_avail)

    if tri_reserves == 0:
        tri_prod = 0
        add_news(game, emp, NewsTypes.NoTriRes, loc)
        change_rev_index(game, obj, rnd(10, 20))
    elif tri_reserves * 20 < tri_prod:
        add_news(game, emp, NewsTypes.TriResWarn1, loc)
        change_rev_index(game, obj, rnd(5, 10))
    elif tri_reserves * 10 < tri_prod and rnd(1, 2) == 1:
        add_news(game, emp, NewsTypes.TriResWarn2, loc)
        change_rev_index(game, obj, rnd(3, 5))

    put_trillum_reserves(
        game, obj, greater_int(0, tri_reserves - pascal_round(tri_prod / 100))
    )
    return tri_prod


def produce_raw_material(
    game: GameEnvironment,
    obj: IDNumber,
    indus: dict[IT, int],
    technology: set[T],
    ip: float,
    temp_cargo: dict[T, int],
) -> None:
    """Run the chemical, metal and trillum industries.

    Output scales with the *square* of industry level, which is why a world's
    industry mattering more than its population is the core of the economy.

    Despite the name, this runs every industry from CheInd to TriInd -- the
    ordinal range, which sweeps up the shipyards and SupInd too. SupInd
    producing supplies here is the only thing that feeds a world, so
    narrowing this to the three raw-material industries starves the galaxy.
    """
    for ind in indus_range(IT.CheInd, IT.TriInd):
        if indus[ind] <= 0:
            continue
        prod_adj = ip * (indus[ind] + K4) ** 2
        for thing in tech_range(T.che, T.tri):
            if ThgAdj[ind][thing] == 0 or thing not in technology:
                continue
            prod = greater_int(1, thg_lmt(prod_adj * ThgAdj[ind][thing]))

            if thing == T.tri:
                prod = produce_trillum(game, obj, prod, temp_cargo[T.tri])

            temp_cargo[thing] += prod


def production(
    game: GameEnvironment,
    obj: IDNumber,
    typ: WorldTypes,
    indus: dict[IT, int],
    technology: set[T],
    ip: float,
    ships: dict[T, int],
    cargo: dict[T, int],
    other_reports: set[T],
) -> None:
    """Run the manufacturing industries, consuming raw materials.

    Ninja and ambrosia are gated on world type and, for ambrosia, on world
    class as well -- only ambrosia and paradise worlds can grow it.
    """
    for ind in indus_range(IT.BioInd, IT.SYTInd):
        if indus[ind] <= 0:
            continue
        prod_adj = ip * (indus[ind] + K4) ** 2

        for thing in tech_range(T.fgt, T.amb):
            if ThgAdj[ind][thing] == 0 or thing not in technology:
                continue

            prod = thg_lmt(prod_adj * ThgAdj[ind][thing])

            if thing == T.nnj and typ != WorldTypes.NnjTyp:
                prod = 0
            elif thing == T.amb and typ != WorldTypes.AmbTyp:
                prod = 0
            elif thing == T.amb and get_class(game, obj) not in (
                WorldClass.AmbCls,
                WorldClass.ParCls,
            ):
                prod = 0
            elif prod <= 0:
                prod = 1

            # Do not produce past the storage ceiling.
            if thing in SHIP_TYPES:
                prod = lesser_int(prod, MAX_RESOURCES - ships[thing])
            else:
                prod = lesser_int(
                    prod, MAX_RESOURCES - lesser_int(cargo[thing], MAX_RESOURCES)
                )

            # Cut production back to what the raw materials support.
            raw_needed: dict[T, int] = {}
            for raw in tech_range(T.amb, T.tri):
                if RawM[thing][raw] > 0:
                    raw_needed[raw] = thg_lmt(prod * (RawM[thing][raw] / 100))
                    if raw_needed[raw] > cargo[raw]:
                        prod = thg_lmt((cargo[raw] / RawM[thing][raw]) * 100)
                        raw_needed[raw] = thg_lmt(prod * (RawM[thing][raw] / 100))
                        if obj.ObjTyp != ObjectTypes.Base:
                            report_planet_lack(
                                game,
                                get_status(game, obj),
                                obj,
                                NewsTypes.Lack,
                                int(raw),
                                other_reports,
                            )
                else:
                    raw_needed[raw] = 0

            for raw in tech_range(T.che, T.tri):
                taken = lesser_int(cargo[raw], raw_needed[raw])
                cargo[raw] -= taken

            if thing in SHIP_TYPES:
                ships[thing] = lesser_int(MAX_RESOURCES, ships[thing] + prod)
            else:
                cargo[thing] += prod


# --- World sub-updates -------------------------------------------------------


def update_terraforming(game: GameEnvironment, obj: IDNumber) -> None:
    """Advance a terraforming world toward, or away from, its target class."""
    if get_class(game, obj) != WorldClass.TerCls:
        return

    loc = Location(XY=get_coord(game, obj), ID=obj)
    target = get_terraform_target(game, obj)

    if rnd(1, 100) <= ProbabilityOfChaos[target]:
        set_type(game, obj, WorldTypes.IndTyp)
        set_class(game, obj, TargetOfChaos[target])
        add_news(game, game.Player, NewsTypes.TerChaos, loc)
    elif rnd(1, 100) <= ProbabilityOfChange[target]:
        set_type(game, obj, WorldTypes.IndTyp)
        set_class(game, obj, target)
        add_news(game, game.Player, NewsTypes.TerSuccess, loc)
    else:
        # Terraforming continues; the upheaval costs 1-3% of the population.
        set_population(
            game, obj, pascal_round(get_population(game, obj) / 100 * rnd(97, 99))
        )


def update_industry(
    game: GameEnvironment,
    obj: IDNumber,
    cls: WorldClass,
    tech: TechLevel,
    eff: int,
    pop: int,
    amb_addict: bool,
    ind_dist: dict[IT, float],
    indus: dict[IT, int],
    cargo: dict[T, int],
    other_reports: set[T],
) -> None:
    """Grow or shrink each industry toward its optimum level.

    Growth costs metal and is capped by efficiency; decay is free and runs at
    half the efficiency rate.
    """
    tip = total_prod(pop, tech)
    if amb_addict:
        tip = pascal_round(tip * AMBROSIA_ADJ)
    tip = min(tip, MAX_INDUS_INDEX)

    temp = tip / 10000
    for ind in IndusTypes:
        optimum_level = pascal_round(temp * ind_dist[ind] * ClassIndAdj[cls][ind])
        if ind_dist[ind] > 0 and optimum_level == 0:
            optimum_level = 1

        if indus[ind] < optimum_level:
            cons_rate = pascal_round(optimum_level * (eff / 500))
            if cons_rate < 1:
                cons_rate = 1
            cons_rate = lesser_int(cons_rate, optimum_level - indus[ind])
            raw_needed = thg_lmt((cons_rate / 100) * NewIndRawN[ind])
            if raw_needed > cargo[T.met]:
                cons_rate = trunc(100 * (cargo[T.met] / NewIndRawN[ind])) if NewIndRawN[ind] else 0
                raw_needed = cargo[T.met]
                report_planet_lack(
                    game,
                    get_status(game, obj),
                    obj,
                    NewsTypes.IndLack,
                    int(T.met),
                    other_reports,
                )
        elif indus[ind] > optimum_level:
            cons_rate = -pascal_round(eff / 2)
            if cons_rate > -1:
                cons_rate = -1
            if indus[ind] + cons_rate < optimum_level:
                cons_rate = optimum_level - indus[ind]
            raw_needed = 0
        else:
            cons_rate = 0
            raw_needed = 0

        if indus[ind] + cons_rate > MAX_INDUS_INDEX:
            cons_rate = MAX_INDUS_INDEX - indus[ind]
            raw_needed = thg_lmt((cons_rate / 100) * NewIndRawN[ind])
        elif indus[ind] + cons_rate < 0:
            cons_rate = -indus[ind]
            raw_needed = 0

        indus[ind] += cons_rate

        raw_needed = lesser_int(cargo[T.met], raw_needed)
        cargo[T.met] -= raw_needed


def update_efficiency(emp: Empire, eff: int) -> int:
    """Efficiency climbs fast when low and crawls near the ceiling."""
    if emp == Empire.Indep:
        inc = rnd(0, 1)
    elif 0 <= eff <= 25:
        inc = rnd(5, 12)
    elif 26 <= eff <= 50:
        inc = rnd(3, 8)
    elif 51 <= eff <= 75:
        inc = rnd(2, 5)
    elif 76 <= eff <= 90:
        inc = rnd(0, 3)
    elif 91 <= eff <= 99:
        inc = rnd(0, 1)
    else:
        inc = 0

    return lesser_int(100, eff + inc)


def update_tech_level(
    game: GameEnvironment, obj: IDNumber, emp: Empire, tech: TechLevel
) -> TechLevel:
    """Pull a world's tech level toward its empire's capital.

    Worlds above the capital *regress* -- tech is sustained by the centre,
    not held permanently.
    """
    if tech == TechLevel.GteTchLvl:
        return tech

    if emp == Empire.Indep:
        if rnd(1, 50) == 1:
            return TechLevel(int(tech) + 1)
        return tech

    capital_tech = get_tech(game, get_capital(game, emp))
    loc = _location(game, obj)

    if capital_tech > tech:
        if rnd(1, 100) <= TECH_LVL_INC:
            tech = TechLevel(int(tech) + 1)
            add_news(game, emp, NewsTypes.NTech, loc, int(tech))
    elif capital_tech < tech:
        if rnd(1, 15) == 1:
            tech = TechLevel(int(tech) - 1)
            add_news(game, emp, NewsTypes.RTech, loc, int(tech))

    return tech


def update_population(cls: WorldClass, tech: TechLevel, pop: int) -> int:
    """Grow the population.

    Growth is exponential below the tech level's base population and linear
    above it; at the class ceiling it just jitters.
    """
    if pop >= MaxPop[cls]:
        increase = rnd(-10, 10)
    elif pop < 75:
        increase = rnd(2, 5)
    elif pop > BasePop[tech]:
        increase = BasePop[tech] / 100
    else:
        increase = 128.0 * pop / MaxPop[cls]

    return pop + pascal_round(increase)


def use_up_food(
    game: GameEnvironment, obj: IDNumber, pop: int, food: int
) -> tuple[int, int]:
    """Feed the population. Returns the new ``(pop, food)``.

    A shortfall starves a sixth of the missing supply, capped at a tenth of
    the population, and drives the revolution index up.
    """
    food_needed = thg_lmt((pop / 100) * SUPPLIES_PER_BILLION)

    if food_needed <= food:
        return pop, food - food_needed

    lack = food_needed - food
    food = 0
    starve = lack // 6
    if starve > pop // 10:
        starve = pop // 10

    pop -= starve

    if starve > 0:
        tech = get_tech(game, obj)
        add_news(
            game, get_status(game, obj), NewsTypes.Starv, _location(game, obj), starve
        )
        rev_inc = lesser_int(trunc(StarveTechAdj[tech] * (starve / 10)), 45)
        change_rev_index(game, obj, rev_inc)

    return pop, food


def use_up_ambrosia(
    game: GameEnvironment,
    obj: IDNumber,
    emp: Empire,
    special: set[SpecialConditions],
    pop: int,
    eff: int,
    tech: TechLevel,
    indus: dict[IT, int],
    ambrosia: int,
) -> tuple[int, int, TechLevel, int]:
    """Feed an ambrosia habit, or risk acquiring one.

    Returns ``(pop, eff, tech, ambrosia)``. Withdrawal kills, wrecks
    efficiency, and rolls on a table of further misfortunes.
    """
    amb_needed = thg_lmt((pop / 100) * DRUGS_PER_BILLION)
    loc = _location(game, obj)

    if SpecialConditions.AmbAddict in special:
        if amb_needed <= ambrosia:
            return pop, eff, tech, ambrosia - amb_needed

        lack = amb_needed - ambrosia
        ambrosia = 0

        die = thg_lmt(ADDICT_DEATH_COEFF * lack)
        if die > pop // 7:
            die = pop // 7
        pop -= die

        if die > 0:
            add_news(game, emp, NewsTypes.AddictDie, loc, die)

        eff_change = lesser_int(trunc(ADDICT_EFF_COEFF * die), eff)
        eff -= eff_change

        change_rev_index(game, obj, trunc(ADDICT_REV_I_COEFF * die))

        roll = rnd(1, 10)
        if 5 <= roll <= 7:
            die = thg_lmt((rnd(50, 120) / 100) * die)
            if die > 0:
                pop -= die
                add_news(game, emp, NewsTypes.RiotsDie, loc, die)
        elif 8 <= roll <= 9:
            for ind in IndusTypes:
                ind_dest = trunc(indus[ind] * rnd(0, 20) / 100)
                indus[ind] -= ind_dest
                if ind_dest > 0:
                    add_news(game, emp, NewsTypes.IndDs, loc, ind_dest, int(ind))
        elif roll == 10:
            if tech > TechLevel.PreTchLvl:
                tech = TechLevel(int(tech) - 1)
            add_news(game, emp, NewsTypes.RTech, loc, int(tech))

        # Note the original reuses ChanceToAddict here as the chance of
        # *breaking* the habit.
        if rnd(1, 100) <= CHANCE_TO_ADDICT:
            special.discard(SpecialConditions.AmbAddict)
            add_news(game, emp, NewsTypes.UAddict, loc)

        return pop, eff, tech, ambrosia

    # Not addicted: a well-supplied world may pick up the habit.
    if ambrosia > 0:
        if amb_needed <= ambrosia and rnd(1, 100) < CHANCE_TO_ADDICT:
            special.add(SpecialConditions.AmbAddict)
            add_news(game, emp, NewsTypes.WAddict, loc)

        amb_needed //= 2
        ambrosia = ambrosia - amb_needed if amb_needed <= ambrosia else 0

    return pop, eff, tech, ambrosia


def update_military(typ: WorldTypes, pop: int, mpop: int) -> int:
    """Recruit toward the world type's optimum troop level."""
    optimum_military = thg_lmt(rnd_var(pascal_round((pop / 150) * OptMilitary[typ]), 10))
    if optimum_military > mpop:
        return thg_lmt(mpop + (pop / 10) * (OptMilitary[typ] / 100))
    return mpop


def update_defenses(
    game: GameEnvironment,
    obj: IDNumber,
    pop: int,
    typ: WorldTypes,
    eff: int,
    technology: set[T],
    defns: dict[T, int],
    cargo: dict[T, int],
    other_reports: set[T],
) -> None:
    """Auto-build planetary defenses toward the optimum for the garrison."""
    mpop = troop_strength(game, obj)
    build_rate = (mpop / 2000) * (1 + ((eff - 50) / 100))
    optimum = mpop / 100
    base_type = None

    if obj.ObjTyp == ObjectTypes.Pln:
        build_rate *= pop / 2000
    elif obj.ObjTyp == ObjectTypes.Base:
        base_type = get_base_type(game, obj)
        if base_type == T.out:
            optimum /= 4
        elif base_type in (T.cmm, T.frt):
            optimum *= 4
            build_rate *= 4

    for defence in tech_range(T.LAM, T.ion):
        if defence not in technology:
            continue

        optimum_def = thg_lmt(optimum * DefAdj[defence])
        if obj.ObjTyp == ObjectTypes.Base and base_type == T.out and defence == T.def_:
            optimum_def = 0
        if defence == T.LAM and typ not in (WorldTypes.BseTyp, WorldTypes.CapTyp):
            optimum_def = 0

        if defns[defence] >= optimum_def:
            continue

        max_build = greater_int(thg_lmt(build_rate * DefBuildRate[defence]), 1)
        build = lesser_int(optimum_def - defns[defence], max_build)

        for car in tech_range(T.che, T.tri):
            if RawM[defence][car] <= 0:
                continue
            raw_needed = thg_lmt((RawM[defence][car] / 100) * build)
            if raw_needed > cargo[car]:
                build = thg_lmt((cargo[car] / RawM[defence][car]) * 100)
                report_planet_lack(
                    game,
                    get_status(game, obj),
                    obj,
                    NewsTypes.DefLack,
                    int(car),
                    other_reports,
                )

        for car in tech_range(T.che, T.tri):
            raw_needed = thg_lmt(build * (RawM[defence][car] / 100))
            cargo[car], _ = move_things(raw_needed, cargo[car], 0)

        _, defns[defence] = move_things(build, MAX_RESOURCES, defns[defence])


def rebellion(game: GameEnvironment, obj: IDNumber, military: int) -> None:
    """Resolve an uprising: either the empire crushes it or the world secedes."""
    pop = get_population(game, obj)
    eff = get_efficiency(game, obj)
    emp = get_status(game, obj)
    cargo = get_cargo(game, obj)
    loc = _location(game, obj)

    rebels = greater_int(1, thg_lmt(math.sqrt(pop) * 65))
    men_lost = rebels // 5
    chance_to_end_rebel = (military / math.sqrt(rebels)) * 1.414213

    lost = lesser_int(cargo[T.men], men_lost)
    cargo[T.men] -= lost
    men_lost -= lost
    lost = lesser_int(cargo[T.nnj], men_lost // 5)
    cargo[T.nnj] -= lost

    if rnd(1, 100) < chance_to_end_rebel:
        change_rev_index(game, obj, rnd(-15, 5))
        add_news(game, emp, NewsTypes.URebel, loc, men_lost)
        game.NewTotalRevIndex[emp] -= rnd(1, 5)
    else:
        set_status(game, obj, Empire.Indep)
        set_type(game, obj, WorldTypes.IndTyp)
        initialize_issp(game, obj)
        change_rev_index(game, obj, -rnd(40, 50))
        add_global_news(game, {emp}, obj, NewsTypes.GLBRev, loc, int(emp))
        add_news(game, emp, NewsTypes.Rebel, loc)

        cargo[T.men] = thg_lmt(rebels)
        game.NewTotalRevIndex[emp] += rnd(5, 10)

    put_cargo(game, obj, cargo)
    set_population(game, obj, thg_lmt(pop - military / 1000))
    set_efficiency(game, obj, greater_int(0, eff - rnd(5, 15)))


def update_revolution(game: GameEnvironment, obj: IDNumber) -> None:
    """Move the revolution index and, past 75, risk an actual rebellion."""
    emp = get_status(game, obj)
    pop = get_population(game, obj)
    typ = get_type(game, obj)

    emp_rev_adj = rnd_var(total_rev_index(game, emp), 50)
    if typ == WorldTypes.CapTyp:
        change_rev_index(game, obj, -rnd(20, 30))
    else:
        change_rev_index(game, obj, emp_rev_adj + rnd(-5, 2))

    if emp == Empire.Indep:
        return

    rev_index = get_rev_index(game, obj)
    cargo = get_cargo(game, obj)
    loc = _location(game, obj)

    optimum_military = thg_lmt(rnd_var(pascal_round((pop / 150) * OptMilitary[typ]), 10))
    military = thg_lmt(cargo[T.men] + 5.0 * cargo[T.nnj])

    if military > optimum_military:
        if rev_index > 30:
            # Troops put a lid on it.
            factor = rnd(1, (military - optimum_military) // 100)
            change_rev_index(game, obj, -factor)
            if factor > 5:
                add_news(game, emp, NewsTypes.RevControl, loc)
        elif typ not in (WorldTypes.CapTyp, WorldTypes.BseTyp):
            # A calm world resents the garrison.
            if rnd(1, 5) == 1:
                change_rev_index(game, obj, rnd(5, 15))
                add_news(game, emp, NewsTypes.MilitRev, loc)

    rev_index = get_rev_index(game, obj)

    if rev_index > 75:
        if rnd(1, 100) < rev_index and typ != WorldTypes.CapTyp:
            rebellion(game, obj, military)
        else:
            add_news(game, emp, NewsTypes.RebelW4, loc)
    elif rev_index > 70:
        add_news(game, emp, NewsTypes.RebelW4, loc)
    elif rev_index > 66:
        add_news(game, emp, NewsTypes.RebelW3, loc)
    elif rev_index > 43:
        add_news(game, emp, NewsTypes.RebelW2, loc)
    elif rev_index > 30:
        add_news(game, emp, NewsTypes.RebelW1, loc)


def hostile_life(game: GameEnvironment, obj: IDNumber) -> None:
    """Resolve the natives on a hostile-life world.

    A strong garrison deters attacks entirely; under an owning empire the
    aliens may instead enlist as ninja legions.
    """
    eff = get_efficiency(game, obj)
    pop = get_population(game, obj)
    cargo = get_cargo(game, obj)
    emp = get_status(game, obj)
    loc = _location(game, obj)

    men_adj = (eff + 50) * ((cargo[T.men] + 5 * cargo[T.nnj]) / 100)
    chance_of_attack = greater_int(0, 25 - pascal_round((men_adj - 2000) / 100))

    if rnd(1, 100) <= chance_of_attack:
        if rnd(1, 100) <= 25:
            pop_killed = lesser_int(pop, rnd(10, 50))
            change_rev_index(game, obj, rnd(5, 15))
            set_population(game, obj, pop - pop_killed)
            add_news(game, emp, NewsTypes.HLPopKill, loc, pop_killed)
        else:
            men_killed = lesser_int(cargo[T.men], rnd(200, 300))
            nnj_killed = lesser_int(cargo[T.nnj], rnd(20, 50))
            cargo[T.men] -= men_killed
            cargo[T.nnj] -= nnj_killed
            put_cargo(game, obj, cargo)
            add_news(game, emp, NewsTypes.HLMenKill, loc, men_killed, nnj_killed)
    elif emp != Empire.Indep and rnd(1, 100) <= 20:
        aliens = rnd(50, 150)
        cargo[T.nnj] += aliens
        put_cargo(game, obj, cargo)
        add_news(game, emp, NewsTypes.HLJoin, loc, aliens)


def supply_link(game: GameEnvironment, base_id: IDNumber, temp_cargo: dict[T, int]) -> None:
    """Draw raw materials from friendly mines in the eight adjacent sectors."""
    from .datacnst import DirX, DirY
    from .galaxy import XYCoord
    from .types import Directions

    base_xy = get_coord(game, base_id)
    emp = get_status(game, base_id)

    for direction in Directions:
        if direction == Directions.NoDir:
            continue
        x = base_xy.x + DirX[direction]
        y = base_xy.y + DirY[direction]
        if not game.Galaxy.in_galaxy(x, y):
            continue

        xy = XYCoord(x, y)
        mine_id = game.Galaxy.sector(xy).Obj
        if (
            mine_id.ObjTyp != ObjectTypes.Pln
            or get_status(game, mine_id) != emp
            or get_type(game, mine_id) not in _SUPPLY_LINK_TYPES
        ):
            continue

        cargo = get_cargo(game, mine_id)
        for raw in tech_range(T.che, T.tri):
            # Leave the mine a working reserve of 200-250.
            transfer = cargo[raw] - rnd(200, 250) if cargo[raw] > 250 else 0
            cargo[raw] -= transfer
            temp_cargo[raw] += transfer
        put_cargo(game, mine_id, cargo)


# --- The world update --------------------------------------------------------


def update_world(game: GameEnvironment, world: IDNumber) -> None:
    """One year for one planet or starbase.

    The step order is the original's and is load-bearing: raw materials are
    produced before the industries that consume them, industry is resized
    before production runs, and the population is fed only after it grows.
    """
    if world.ObjTyp == ObjectTypes.Pln:
        _update_planet(game, world)
    elif world.ObjTyp == ObjectTypes.Base:
        _update_starbase(game, world)


def _world_technology(game: GameEnvironment, emp: Empire, tech: TechLevel) -> set[T]:
    """What a world can actually build: its empire's tech, capped by its own.

    Independent worlds run one tech level behind their own level.
    """
    if emp == Empire.Indep:
        if tech > TechLevel.PreTchLvl:
            return set(TechDev[TechLevel(int(tech) - 1)])
        return set(TechDev[tech])

    _, empire_tech = get_empire_technology(game, emp)
    return set(empire_tech) & set(TechDev[tech])


def _update_planet(game: GameEnvironment, world: IDNumber) -> None:
    from .intrface import get_industrial_distribution

    planet = game.Universe.Planet[world.Index]
    other_reports: set[T] = set()

    technology = _world_technology(game, planet.Emp, planet.Tech)

    update_terraforming(game, world)

    # Industrial Production coefficient, shared by every industry this year.
    ip = (TechAdj2[planet.Tech] / 100) * ((planet.Eff + 250) / 100) / K6

    temp_cargo = {c: planet.Cargo[c] for c in CARGO_TYPES}
    produce_raw_material(game, world, planet.Indus, technology, ip, temp_cargo)
    ind_dist = get_industrial_distribution(game, world)
    update_industry(
        game,
        world,
        planet.Cls,
        planet.Tech,
        planet.Eff,
        planet.Pop,
        SpecialConditions.AmbAddict in planet.Special,
        ind_dist,
        planet.Indus,
        temp_cargo,
        other_reports,
    )
    production(
        game,
        world,
        planet.Typ,
        planet.Indus,
        technology,
        ip,
        planet.Ships,
        temp_cargo,
        other_reports,
    )
    for c in CARGO_TYPES:
        planet.Cargo[c] = thg_lmt(temp_cargo[c])

    if planet.Cls != WorldClass.TerCls:
        planet.Eff = update_efficiency(planet.Emp, planet.Eff)
    planet.Tech = update_tech_level(game, world, planet.Emp, planet.Tech)
    planet.Pop = update_population(planet.Cls, planet.Tech, planet.Pop)
    planet.Pop, planet.Cargo[T.sup] = use_up_food(
        game, world, planet.Pop, planet.Cargo[T.sup]
    )
    planet.Pop, planet.Eff, planet.Tech, planet.Cargo[T.amb] = use_up_ambrosia(
        game,
        world,
        planet.Emp,
        planet.Special,
        planet.Pop,
        planet.Eff,
        planet.Tech,
        planet.Indus,
        planet.Cargo[T.amb],
    )
    planet.Cargo[T.men] = update_military(planet.Typ, planet.Pop, planet.Cargo[T.men])
    update_defenses(
        game,
        world,
        planet.Pop,
        planet.Typ,
        planet.Eff,
        technology,
        planet.Defns,
        planet.Cargo,
        other_reports,
    )
    update_revolution(game, world)
    if planet.Cls == WorldClass.HLfCls:
        hostile_life(game, world)


def _update_starbase(game: GameEnvironment, world: IDNumber) -> None:
    from .intrface import get_industrial_distribution

    base = game.Universe.Starbase[world.Index]
    other_reports: set[T] = set()

    technology = _world_technology(game, base.Emp, base.Tech)

    # Only industrial complexes have an economy; other bases just hold ground.
    if base.STyp == T.cmp:
        ip = (TechAdj2[base.Tech] / 100) * ((base.Eff + 250) / 100) / K6

        temp_cargo = {c: base.Cargo[c] for c in CARGO_TYPES}
        supply_link(game, world, temp_cargo)
        produce_raw_material(game, world, base.Indus, technology, ip, temp_cargo)
        ind_dist = get_industrial_distribution(game, world)
        update_industry(
            game,
            world,
            WorldClass.ArtCls,
            base.Tech,
            base.Eff,
            base.Pop,
            SpecialConditions.AmbAddict in base.Special,
            ind_dist,
            base.Indus,
            temp_cargo,
            other_reports,
        )
        production(
            game,
            world,
            base.Typ,
            base.Indus,
            technology,
            ip,
            base.Ships,
            temp_cargo,
            other_reports,
        )
        # UPDATE.PAS:1527 calls SurplusLink(World,TempCargo) here, between
        # Production and PutTotalCargo -- it returns an industrial complex's
        # surplus to nearby raw-material worlds. Unported (see #3), so a
        # complex currently hoards what it does not consume.
        for c in CARGO_TYPES:
            base.Cargo[c] = thg_lmt(temp_cargo[c])

    base.Eff = update_efficiency(base.Emp, base.Eff)
    base.Tech = update_tech_level(game, world, base.Emp, base.Tech)

    if base.STyp == T.cmp:
        base.Pop = update_population(WorldClass.ArtCls, base.Tech, base.Pop)
        base.Pop, base.Cargo[T.sup] = use_up_food(game, world, base.Pop, base.Cargo[T.sup])
        base.Pop, base.Eff, base.Tech, base.Cargo[T.amb] = use_up_ambrosia(
            game,
            world,
            base.Emp,
            base.Special,
            base.Pop,
            base.Eff,
            base.Tech,
            base.Indus,
            base.Cargo[T.amb],
        )
        base.Cargo[T.men] = update_military(base.Typ, base.Pop, base.Cargo[T.men])
        update_revolution(game, world)

    update_defenses(
        game,
        world,
        base.Pop,
        base.Typ,
        base.Eff,
        technology,
        base.Defns,
        base.Cargo,
        other_reports,
    )


# --- Construction ------------------------------------------------------------


def construct_starbase(
    game: GameEnvironment, emp: Empire, styp: TechnologyTypes, xy: XYCoord
) -> IDNumber:
    """Turn a finished construction site into a starbase.

    The three kinds start life very differently. An outpost is a single
    caretaker; an industrial complex arrives already populated and running at
    its optimum industry, which is what makes it worth ten years of material;
    a command base or fortress starts as a garrison of ten to twenty. All
    inherit the empire's technology and open at 10-20% efficiency.

    Returns EmptyQuadrant when no starbase slot is free -- the site is
    consumed either way, as in the original.
    """
    obj = IDNumber(ObjectTypes.Base, next_starbase_slot(game))
    if obj.Index <= 0:
        return empty_quadrant()

    create_starbase(game, obj, emp, xy, styp)
    set_efficiency(game, obj, rnd(10, 20))
    emp_tech, _ = get_empire_technology(game, emp)
    set_tech(game, obj, emp_tech)

    if styp == TechnologyTypes.out:
        set_population(game, obj, 1)
        set_type(game, obj, WorldTypes.OutTyp)
    elif styp == TechnologyTypes.cmp:
        set_population(game, obj, rnd(400, 700))
        set_type(game, obj, WorldTypes.BseTyp)
        put_indus(game, obj, get_optimum_indus(game, obj))
    else:
        set_population(game, obj, rnd(10, 20))
        set_type(game, obj, WorldTypes.BseTyp)

    return obj


def construct_stargate(
    game: GameEnvironment, emp: Empire, gtyp: TechnologyTypes, xy: XYCoord
) -> IDNumber:
    """Turn a finished construction site into a stargate, link or disrupter."""
    obj = IDNumber(ObjectTypes.Gate, next_stargate_slot(game))
    if obj.Index <= 0:
        return empty_quadrant()

    create_stargate(game, obj, emp, gtyp, xy)
    return obj


def _use_up_raw_material(
    game: GameEnvironment,
    typ: TechnologyTypes,
    sta: Empire,
    con_id: IDNumber,
    constr_fleets: set[int],
) -> bool:
    """Spend a year's materials off the fleets parked on the site.

    All or nothing: if any one cargo type comes up short the whole draw is
    abandoned and *nothing* is consumed. The original gets this by working on
    a copy of every fleet's cargo and jumping past the write-back on failure,
    so a half-supplied site never quietly eats what did arrive.

    Fleets are drained in index order, so the lowest-numbered fleet on the
    sector is emptied first.
    """
    cargo = {i: get_cargo(game, IDNumber(ObjectTypes.Flt, i)) for i in constr_fleets}

    for thing in tech_range(TechnologyTypes.amb, TechnologyTypes.tri):
        raw_needed = ConsCargoNeeded[typ][thing]
        for i in sorted(constr_fleets):
            cargo_to_use = lesser_int(raw_needed, cargo[i][thing])
            cargo[i][thing] -= cargo_to_use
            raw_needed -= cargo_to_use

        if raw_needed > 0:
            add_news(
                game,
                sta,
                NewsTypes.ConsLack,
                Location(XY=limbo(), ID=con_id),
                int(thing),
            )
            return False

    for i in sorted(constr_fleets):
        put_cargo(game, IDNumber(ObjectTypes.Flt, i), cargo[i])
    return True


def update_construction(game: GameEnvironment, i: int) -> None:
    """Advance one construction site by a year.

    Progress is bought, not waited out: only the owner's fleets sitting on the
    site count, and a year with insufficient material on hand costs a year of
    nothing -- the clock does not move.

    The name-transfer step is meant to hand a name the builder gave the site
    over to whatever it becomes, which is why the name is read and deleted
    before the sector is cleared. **It never fires.** ``AddName`` normalises a
    ``Con`` location by overwriting ``XY`` with the site's real coordinate
    before storing it, while the lookup here passes ``XY = Limbo``, and
    ``SameLocation`` compares both fields. So the search always misses,
    ``con_name`` is always empty, and a named site loses its name on
    completion. Faithful to the original, which has the same mismatch.

    Two consequences worth knowing before "fixing" it: the orphaned
    ``NameRecord`` still points at a ``Con`` ID whose slot is now free, so a
    later site that lands in the same slot *at the same coordinate* inherits
    the old name; and making the lookup succeed would start exercising the
    ``add_name`` calls below, which have never run.
    """
    site = game.Universe.Constr[i]
    con_id = IDNumber(ObjectTypes.Con, i)

    constr_fleets = get_fleets(game, site.XY) & game.GlobalSets.SetOfFleetsOf[site.Emp]
    if not _use_up_raw_material(game, site.CTyp, site.Emp, con_id, constr_fleets):
        return

    site.TimeToCompletion -= 1
    if site.TimeToCompletion != 0:
        return

    game.GlobalSets.SetOfActiveConstructionSites.discard(i)
    game.GlobalSets.SetOfConstructionSitesOf[site.Emp].discard(i)

    name_slot = location2index(game, site.Emp, Location(XY=limbo(), ID=con_id))
    if name_slot is not None:
        con_name, _ = get_defined_name(name_slot)
        delete_name(game, site.Emp, con_name)
    else:
        con_name = ""

    game.Galaxy.sector(site.XY).Obj = empty_quadrant()

    new_id = empty_quadrant()
    if site.CTyp == TechnologyTypes.SRM:
        put_mine(game, site.XY, site.Emp)
    elif site.CTyp in STARBASE_TYPES:
        new_id = construct_starbase(game, site.Emp, site.CTyp, site.XY)
        if con_name:
            add_name(game, site.Emp, Location(XY=limbo(), ID=new_id), con_name)
    elif site.CTyp in STARGATE_TYPES:
        new_id = construct_stargate(game, site.Emp, site.CTyp, site.XY)
        if con_name:
            add_name(game, site.Emp, Location(XY=limbo(), ID=new_id), con_name)

    add_news(
        game,
        site.Emp,
        NewsTypes.ConsDone,
        Location(XY=site.XY, ID=empty_quadrant()),
        int(site.CTyp),
    )


def update_universe(game: GameEnvironment) -> None:
    """Advance the whole world by one year.

    Port of UPDATE.PAS ``UpdateUniverse``. Empire research (``UpdateEmpire``)
    is still unported, so no empire advances in technology on its own yet.
    """
    game.NewTotalRevIndex = {emp: 0 for emp in Empire}

    game.Year += 1

    for i in range(1, game.NoOfPlanets + 1):
        update_world(game, IDNumber(ObjectTypes.Pln, i))

    for i in sorted(game.GlobalSets.SetOfActiveStarbases):
        update_world(game, IDNumber(ObjectTypes.Base, i))

    # Iterated over a copy: a site that completes drops out of the set.
    for i in sorted(game.GlobalSets.SetOfActiveConstructionSites):
        update_construction(game, i)
