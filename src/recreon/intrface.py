"""High-level operations on entities.

Port of INTRFACE.PAS -- the Phase 3 subset: world creation and the optimum
industrial distribution. Gate passage, fleet balancing and the status-line
formatters arrive with the phases that use them.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .datacnst import (
    AMBROSIA_ADJ,
    DEFAULT_ISSP,
    ISSP,
    K4,
    K6,
    NORMAL_ISSP,
    SAFETY_ADJ,
    SUPPLIES_PER_BILLION,
    CargoSpace,
    ClassIndAdj,
    ClassStr,
    FltMovementRate,
    IndusNames,
    PrincipalIndustry,
    TechAdj2,
    TechN,
    TechnologyName,
    TechStr,
    ThgAdj,
    ThingNames,
    TypeData,
    TypeStr,
    YearsToBuild,
)
from .galaxy import Location, XYCoord
from .misc import fleet_cargo_space, total_prod
from .primintr import (
    get_base_type,
    get_class,
    get_efficiency,
    get_gate_type,
    get_issp,
    get_object,
    get_population,
    get_special,
    get_status,
    get_tech,
    get_type,
    get_warp_link_freq,
)
from .types import (
    MAX_NO_OF_CONSTR_SITES,
    MAX_NO_OF_FLEETS,
    MAX_NO_OF_STARBASES,
    MAX_NO_OF_STARGATES,
    SHIP_TYPES,
    Empire,
    IDNumber,
    IndusTypes,
    ObjectTypes,
    SpecialConditions,
    TechLevel,
    TechnologyTypes,
    WorldTypes,
    empty_quadrant,
    indus_range,
    ship_array,
    tech_range,
)
from .utils.pascal import pascal_round

#: Pascal's ``SYGInd TO SYTInd`` -- the four shipyard industries.
SHIPYARD_INDUSTRIES = indus_range(IndusTypes.SYGInd, IndusTypes.SYTInd)

if TYPE_CHECKING:
    from .environ import GameEnvironment

IT = IndusTypes

#: Cross-elasticity of each raw-material industry against each production
#: industry: how much Che/Min/Tri capacity one unit of the main industry
#: needs. Only the Che, Min and Tri rows are non-zero.
Gamma: dict[IT, dict[IT, float]] = {
    IT.BioInd: dict.fromkeys(IndusTypes, 0.0),
    IT.CheInd: {
        IT.BioInd: 1.12857,
        IT.CheInd: 0.0,
        IT.MinInd: 0.0,
        IT.SYGInd: 0.19143,
        IT.SYJInd: 0.50000,
        IT.SYSInd: 0.36714,
        IT.SYTInd: 0.25286,
        IT.SupInd: 0.0,
        IT.TriInd: 0.0,
    },
    IT.MinInd: {
        IT.BioInd: 0.10000,
        IT.CheInd: 0.0,
        IT.MinInd: 0.0,
        IT.SYGInd: 0.30514,
        IT.SYJInd: 0.27286,
        IT.SYSInd: 0.53714,
        IT.SYTInd: 0.83571,
        IT.SupInd: 0.0,
        IT.TriInd: 0.0,
    },
    IT.SYGInd: dict.fromkeys(IndusTypes, 0.0),
    IT.SYJInd: dict.fromkeys(IndusTypes, 0.0),
    IT.SYSInd: dict.fromkeys(IndusTypes, 0.0),
    IT.SYTInd: dict.fromkeys(IndusTypes, 0.0),
    IT.SupInd: dict.fromkeys(IndusTypes, 0.0),
    IT.TriInd: {
        IT.BioInd: 0.10000,
        IT.CheInd: 0.0,
        IT.MinInd: 0.0,
        IT.SYGInd: 0.07627,
        IT.SYJInd: 0.20400,
        IT.SYSInd: 0.16667,
        IT.SYTInd: 0.08000,
        IT.SupInd: 0.0,
        IT.TriInd: 0.0,
    },
}

#: World types with no production industry: the raw-material percentages are
#: shares of whatever industry the supply requirement leaves over.
_RAW_MATERIAL_TYPES = frozenset(
    {
        WorldTypes.AgrTyp,
        WorldTypes.CheTyp,
        WorldTypes.MinTyp,
        WorldTypes.RawTyp,
        WorldTypes.RawSTyp,
        # Pascal's `RsrTyp..TriTyp` subrange.
        WorldTypes.RsrTyp,
        WorldTypes.TerTyp,
        WorldTypes.TriTyp,
    }
)


def get_industrial_distribution(
    game: GameEnvironment, obj: IDNumber
) -> dict[IT, float]:
    """Optimum share of industry for each industry type, as percentages.

    Supply industry is sized first, from population and the world's supply
    ISSP. What remains is split either as fixed shares (raw-material worlds)
    or around the world's principal industry, with the raw-material
    industries sized to feed it via :data:`Gamma`.
    """
    tech = get_tech(game, obj)
    cls = get_class(game, obj)
    pop = get_population(game, obj)
    typ = get_type(game, obj)
    eff = get_efficiency(game, obj)
    amb_addict = SpecialConditions.AmbAddict in get_special(game, obj)

    ind_dist: dict[IT, float] = dict.fromkeys(IndusTypes, 0.0)

    alpha = (TechAdj2[tech] / 100) * (eff + 250) / K6
    tip = float(total_prod(pop, tech))
    if amb_addict:
        tip *= AMBROSIA_ADJ
    tip = min(tip, 999)

    # Beta[i] = TIP * ClassIndAdj[Cls, i] / 10000, floored at 1 so it can be
    # divided by safely.
    temp = tip / 10000
    beta = {}
    for ind in IndusTypes:
        beta[ind] = temp * ClassIndAdj[cls][ind]
        if beta[ind] == 0:
            beta[ind] = 1

    # Supply industry.
    i = (
        math.sqrt(
            (
                SAFETY_ADJ
                * ISSP[get_issp(game, obj, IT.SupInd)]
                * (SUPPLIES_PER_BILLION / 100)
                * pop
            )
            / ((ThgAdj[IT.SupInd][TechnologyTypes.sup] / 100) * alpha)
        )
        - K4
    ) / beta[IT.SupInd]
    if i > 95 or i < 0 or typ == WorldTypes.AgrTyp:
        i = 95
    ind_dist[IT.SupInd] = i

    if typ in _RAW_MATERIAL_TYPES:
        # No production industry: split the remainder by fixed shares.
        i = 100 - ind_dist[IT.SupInd]
        ind_dist[IT.CheInd] = i * (TypeData[typ][IT.CheInd] / 100)
        ind_dist[IT.MinInd] = i * (TypeData[typ][IT.MinInd] / 100)
        ind_dist[IT.TriInd] = i * (TypeData[typ][IT.TriInd] / 100)
        return ind_dist

    main_ind = PrincipalIndustry[typ]

    a = -K4 * (1 / beta[IT.CheInd] + 1 / beta[IT.MinInd] + 1 / beta[IT.TriInd])
    b = (
        math.sqrt(SAFETY_ADJ * ISSP[get_issp(game, obj, IT.CheInd)] * Gamma[IT.CheInd][main_ind])
        / beta[IT.CheInd]
        + math.sqrt(SAFETY_ADJ * ISSP[get_issp(game, obj, IT.MinInd)] * Gamma[IT.MinInd][main_ind])
        / beta[IT.MinInd]
        + math.sqrt(SAFETY_ADJ * ISSP[get_issp(game, obj, IT.TriInd)] * Gamma[IT.TriInd][main_ind])
        / beta[IT.TriInd]
    )

    i = (100 - (ind_dist[IT.SupInd] + a + (K4 * b))) / (1 + (beta[main_ind] * b))
    i = min(i, TypeData[typ][main_ind])
    ind_dist[main_ind] = i

    for raw in (IT.CheInd, IT.MinInd, IT.TriInd):
        i = (
            (ind_dist[main_ind] * beta[main_ind] + K4)
            * math.sqrt(SAFETY_ADJ * ISSP[get_issp(game, obj, raw)] * Gamma[raw][main_ind])
            - K4
        ) / beta[raw]
        if i < 0:
            i = 1
        ind_dist[raw] = i

    return ind_dist


def get_optimum_indus(game: GameEnvironment, obj: IDNumber) -> dict[IT, int]:
    """The industry array a world would settle at, given its distribution.

    Used when a world is created already developed, rather than growing into
    its industry year by year.
    """
    from .datacnst import ClassIndAdj as _cls_adj
    from .utils.pascal import pascal_round

    ind_dist = get_industrial_distribution(game, obj)
    cls = get_class(game, obj)
    tech = get_tech(game, obj)
    pop = get_population(game, obj)

    tip = total_prod(pop, tech)
    temp = tip / 10000

    indus: dict[IT, int] = {}
    for ind in IndusTypes:
        level = pascal_round(temp * ind_dist[ind] * _cls_adj[cls][ind])
        if ind_dist[ind] > 0 and level == 0:
            level = 1
        indus[ind] = min(level, 999)
    return indus


def clear_known_set(game: GameEnvironment, emp: Empire) -> None:
    """Wipe everything ``emp`` knows *of*, not merely what it can see.

    The harder counterpart to :func:`~recreon.primintr.clear_scout_set`, which
    runs every turn: this drops ``KnownBy``, the level the map itself keys on,
    so an empire that has had this done to it starts blind rather than merely
    out of touch. Its one caller is ``AddPlayerEmpire`` -- an empire joining a
    galaxy mid-game must not inherit the previous occupant's charts.

    Fleets are untouched, though ``FleetRecord`` carries a ``KnownBy`` too.
    Faithful to the original, which sweeps planets, starbases, gates and
    construction sites and stops there; a fleet the new empire "knows" is
    transient enough that the next ``set_up_turn`` settles it either way.
    """
    universe = game.Universe

    for planet in universe.Planet[1 : game.NoOfPlanets + 1]:
        if planet is not None:
            planet.KnownBy.discard(emp)

    for index in game.GlobalSets.SetOfActiveStarbases:
        universe.Starbase[index].KnownBy.discard(emp)

    for index in game.GlobalSets.SetOfActiveGates:
        universe.Stargate[index].KnownBy.discard(emp)

    for index in game.GlobalSets.SetOfActiveConstructionSites:
        universe.Constr[index].KnownBy.discard(emp)


def scout(game: GameEnvironment, emp: Empire, xy: XYCoord) -> None:
    """Reveal the eight sectors around ``xy`` to ``emp``.

    A dark nebula blocks the sweep -- the original bails out of the whole
    loop on hitting one, so which sectors get revealed depends on scan order.
    Preserved as-is.
    """
    from .datacnst import DirX, DirY
    from .news import NewsTypes, add_news
    from .primintr import (
        get_nebula,
        get_object,
        get_status,
        known,
        scout_object,
        scouted,
    )
    from .types import Directions, NebulaTypes

    if xy == XYCoord(0, 0):
        return

    for direction in Directions:
        x = xy.x + DirX[direction]
        y = xy.y + DirY[direction]
        if not game.Galaxy.in_galaxy(x, y):
            continue

        temp = XYCoord(x, y)
        obj = get_object(game, temp)
        other_emp = get_status(game, obj)

        if obj.ObjTyp != ObjectTypes.Void and not scouted(game, emp, obj):
            if not known(game, emp, obj) and other_emp != emp:
                add_news(game, emp, NewsTypes.POk, Location(XY=XYCoord(0, 0), ID=obj))
            scout_object(game, emp, obj)

        if get_nebula(game, temp) == NebulaTypes.DarkNebula:
            return


def probe_scout(game: GameEnvironment, emp: Empire, xy: XYCoord) -> None:
    """Reveal the sectors around ``xy`` to ``emp``, at risk of losing the probe.

    Like :func:`scout` but with two differences that matter. It sweeps
    ``NoDir`` first, so the probe's own sector is revealed as well as the eight
    around it. And a garrisoned world can shoot it down: the chance is
    ``ISqrt(Cargo[men])`` percent, so a world holding 2500 troops destroys a
    probe half the time. An independent world never fires -- only an owned one.

    A destroyed probe stops the whole sweep, so everything the pass had not yet
    reached stays hidden. A dark nebula ends it the same way.
    """
    from .datacnst import DirX, DirY
    from .misc import same_xy
    from .news import NewsTypes, add_news
    from .primintr import (
        get_cargo,
        get_nebula,
        get_object,
        get_status,
        known,
        scout_object,
        scouted,
    )
    from .types import Directions, NebulaTypes
    from .utils.int_utils import isqrt, rnd

    if same_xy(xy, XYCoord(0, 0)):
        return

    for direction in Directions:
        x = xy.x + DirX[direction]
        y = xy.y + DirY[direction]
        if not game.Galaxy.in_galaxy(x, y):
            continue

        temp = XYCoord(x, y)
        obj = get_object(game, temp)
        other_emp = get_status(game, obj)

        if not scouted(game, emp, obj) and obj.ObjTyp != ObjectTypes.Void:
            loc = Location(XY=XYCoord(0, 0), ID=obj)
            chance_to_destroy = isqrt(get_cargo(game, obj)[TechnologyTypes.men])
            if other_emp != Empire.Indep and rnd(1, 100) < chance_to_destroy:
                add_news(game, emp, NewsTypes.PDest, loc, 0, 0, 0)
                add_news(game, other_emp, NewsTypes.PCap, loc, int(emp), 0, 0)
                return

            if not known(game, emp, obj) and other_emp != emp:
                add_news(game, emp, NewsTypes.POk, loc, 0, 0, 0)

            scout_object(game, emp, obj)

        if get_nebula(game, temp) == NebulaTypes.DarkNebula:
            return


def update_probes(game: GameEnvironment, emp: Empire) -> None:
    """Land every probe in transit and free it for relaunch.

    Probes are not really in flight -- one launched last turn arrives here at
    the start of the next, reveals what it found and is immediately ``PReady``
    again. Without this an empire launches its whole stock once and is blind
    from then on, since :func:`~recreon.primintr.get_probe` only ever returns a
    ``PReady`` one.
    """
    from .types import NO_OF_PROBES_PER_EMPIRE, ProbeStatus

    for i in range(1, NO_OF_PROBES_PER_EMPIRE + 1):
        probe = game.Universe.EmpireData[emp].Probe[i]
        if probe.Status == ProbeStatus.PInTrans:
            probe_scout(game, emp, probe.Dest)
            probe.Status = ProbeStatus.PReady


#: GetNewsLine's own cargo-name table, which is *not* `ThingNames`. Troops and
#: ninjas are deliberately blank: no headline that uses this table can be
#: about them, so the slots exist only to keep the array indexed by CargoTypes.
_THG_N: dict[TechnologyTypes, str] = {
    TechnologyTypes.men: "",
    TechnologyTypes.nnj: "",
    TechnologyTypes.amb: "ambrosia",
    TechnologyTypes.che: "chemicals",
    TechnologyTypes.met: "metals",
    TechnologyTypes.sup: "supplies",
    TechnologyTypes.tri: "trillum",
}

#: The five ways a world can complain about a shortage, picked at random so
#: repeated years of the same shortage do not read identically.
_LACK_VERBS = (
    " needs more ",
    " lacks ",
    " has run out of ",
    " requires more ",
    " has used up all its ",
)


def _death_toll(parm1: int) -> str:
    """Population figures, which are stored in hundreds of millions.

    Under 100 the figure is rendered in millions as a plain integer; at or
    above it, in billions to one decimal at width 4 -- so the billions form
    carries a leading space, e.g. ``" 1.5 billion"``. Transcribed as written,
    including that space.
    """
    if parm1 < 100:
        return f"{parm1 * 10} million"
    return f"{parm1 / 100:4.1f} billion"


def get_news_line(game: GameEnvironment, player: Empire, item) -> str:
    """Render one news item as the sentence the player reads.

    Port of INTRFACE.PAS ``GetNewsLine``. Each headline has a template in
    which ``*`` stands for the location and ``@`` for an empire -- the empire
    named by ``Parm1``, which is why nearly every combat headline files the
    attacker there. Both are substituted at the end, after the template is
    chosen.

    ``Parm2`` and ``Parm3`` carry whatever else the headline needs: a resource
    for the detail lines, an industry for ``IndDs``, a second empire for the
    global ``GLB*`` bulletins.

    Two notes on faithfulness:

    **Substitution uses Python's ``str.replace``, not the original's
    ``StringReplace``.** That routine caches the line's length before its
    replacement loop and never refreshes it, so a template containing the same
    marker twice truncates the tail on the second pass -- and it loops
    ``while pos(Find,Line) <> 0``, so a *name* containing ``*`` or ``@`` never
    terminates. Neither is reachable from the shipped templates (none has a
    repeated marker), but the second becomes reachable the moment the player
    can name a world; see issue #44.

    **Nine headline types have no arm and no ``ELSE``.** ``GTech``, ``CLost``,
    ``LostP``, ``SMnR``, ``JumpDm``, ``JumpDs``, ``ELost``, ``TriAcc`` and
    ``LostF`` are declared in NEWS.PAS and fall straight through, leaving the
    caller's buffer untouched -- so the previous item's line would be shown
    twice. Nothing in the game ever files one of them, so they are vestiges of
    an earlier design; the port returns an empty string rather than inventing
    prose for a headline that cannot occur.
    """
    from .news import NewsTypes
    from .primintr import empire_name, get_name
    from .utils.int_utils import rnd

    N = NewsTypes
    headline = item.Headline
    p1, p2 = item.Parm1, item.Parm2

    loc_n = get_name(game, player, item.Loc1, True)
    emp_n = empire_name(game, Empire(p1)) if 0 <= p1 <= 8 else ""
    deaths = _death_toll(p1)

    def thg(value: int) -> str:
        try:
            return _THG_N[TechnologyTypes(value)]
        except (KeyError, ValueError):
            return ""

    def lack() -> str:
        # The verb is drawn before the sentence is built, so this consumes a
        # draw from the generator whether or not the line is ever displayed.
        return f"*{_LACK_VERBS[rnd(1, 5) - 1]}{thg(p1)}."

    simple = {
        N.DefLack: lambda: f"* needs {thg(p1)} to build defenses.",
        N.IndLack: lambda: "* cannot build up its industry due to a lack of metals.",
        N.Starv: lambda: f"{deaths} people have died of starvation on *.",
        N.NTech: lambda: f"* has advanced to {TechN[TechLevel(p1)]} level technology.",
        N.RTech: lambda: f"* has regressed to {TechN[TechLevel(p1)]} level technology.",
        N.Lack: lack,
        N.ConsLack: lack,
        N.ConsDone: lambda: "Construction at * has been completed.",
        N.RebelW1: lambda: "The people of * are dissatisfied with the empire.",
        N.RebelW2: lambda: "Riots and demonstrations are widespread on *.",
        N.RebelW3: lambda: "Some signs of organized rebellion detected on *.",
        N.RebelW4: lambda: "Rebel forces on * are well organized and plan an attack.",
        N.Rebel: lambda: "Rebel forces on * have succeeded in taking over.",
        N.URebel: lambda: f"Imperial troops ended a rebellion on *.  {p1} legions lost.",
        N.POk: lambda: "Imperial probe has scouted *.",
        N.NCapTech: lambda: (
            f"* has developed {TechnologyName[TechnologyTypes(p1)]} technology."
        ),
        N.NCapLvl: lambda: f"* has developed {TechN[TechLevel(p1)]} level technology.",
        N.BattleW1: lambda: "* was attacked by @.  Attack force destroyed.",
        N.BattleW2: lambda: "* was attacked by @.  Attack force retreated.",
        N.BattleL: lambda: "* has been conquered by the empire of @.",
        N.WAddict: lambda: "The people of * are now addicted to ambrosia.",
        N.UAddict: lambda: "* is no longer addicted to ambrosia.",
        N.AddictDie: lambda: f"{deaths} people have died on * of ambrosia withdrawal.",
        N.RiotsDie: lambda: f"{deaths} people have died in large-scale riots on *.",
        N.IndDs: lambda: (
            f"   {p1} {IndusNames[IndusTypes(p2)]} have been destroyed on *."
        ),
        N.DInd: lambda: "* has declared independence.",
        N.Join: lambda: "* has joined the empire of @.",
        N.NewCap: lambda: "* has become the temporary capital of the empire.",
        N.EndEmp: lambda: "The empire has been conquered.",
        N.NoFuel: lambda: "* is out of fuel.",
        N.FltDet: lambda: "@ fleet has been scanned near *.",
        N.MinesDm: lambda: "* suffered damage from @ SRM field.",
        N.MinesDs: lambda: "* was destroyed in @ SRM field.",
        N.Mines: lambda: "@ fleet damaged in SRM field at *.",
        N.ConDs: lambda: "@ has attacked and destroyed construction at *.",
        N.GteDs: lambda: "Stargate at * has been destroyed by @.",
        N.LAMDm: lambda: "* was damaged by @ LAMs.",
        N.LAMDs: lambda: "* has been destroyed by a @ LAM attack.",
        N.LAMDef: lambda: "* has been hit by @ LAMs.",
        N.DestDetail: lambda: (
            f"   {p1} {ThingNames[TechnologyTypes(p2)]} destroyed."
        ),
        N.TrnsShp: lambda: "* has received the following resources from @:",
        N.Trns2: lambda: f"   {p1} {ThingNames[TechnologyTypes(p2)]}",
        N.NSellTech: lambda: (
            "@ has given the empire "
            f"{TechnologyName[TechnologyTypes(p2)]} technology."
        ),
        N.GInd: lambda: "@ has granted this empire the rights to *.",
        N.NewPlEmp: lambda: "The empire of @ has been formed on *.",
        N.PCap: lambda: "Enemy probe from @ destroyed at *.",
        N.PDest: lambda: "Lost contact with probe at *.",
        N.MessR: lambda: "Message received from @.",
        N.MessI: lambda: "* has intercepted a message from @.",
        N.ConDsUNK: lambda: "Construction at * has been destroyed by unknown force.",
        N.GteDsUNK: lambda: "Unknown forces have destroyed stargate at *.",
        N.BattleW2UNK: lambda: "* has been attacked by unknown forces.",
        N.BattleLUNK: lambda: "Lost contact with *.  Presume destroyed.",
        N.HLPopKill: lambda: f"Native alien life-forms have killed {deaths} on *.",
        N.HLMenKill: lambda: (
            f"Aliens on * attack.  Casualties: {p1} men, {p2} ninja."
        ),
        N.HLJoin: lambda: f"{p1} alien legions have joined imperial forces on *.",
        N.BseFuel: lambda: "* is out of trillum.",
        N.BseBlocked: lambda: "* blocked in transit.",
        N.SRMClear: lambda: "SRMs at * have been cleared by @.",
        N.OrdersSRMClear: lambda: "* sweeped SRMs as ordered.",
        N.OrdersNoSRMs: lambda: "SRM sweep by * failed - no SRMs found.",
        N.OrdersNoSSP: lambda: "SRM sweep by * failed - not enough starships.",
        N.FltBlocked: lambda: "* blocked by dense nebula.",
        N.NebGate: lambda: "* unable to gate to inpenetrable nebula.",
        N.BseSD: lambda: "@ has destroyed *.",
        N.FltSD: lambda: "* destroyed by explosion.",
        N.WHolo: lambda: "Population centers on * have been bombarded by @.",
        N.DthHolo: lambda: f"   {deaths} people were killed in the attack.",
        N.Disrupt: lambda: "* has been stopped by @ disrupter.",
        N.NoTriRes: lambda: "All trillum deposits on * have been exhausted.",
        N.TriResWarn1: lambda: "Trillum deposits on * are nearly depleted.",
        N.TriResWarn2: lambda: "Trillum deposits on * are very low.",
        N.MilitRev: lambda: (
            "Demonstrations on * call for removal of imperial troops."
        ),
        N.RevControl: lambda: "Imperial troops on * disband angry rioters.",
        N.GLBDest: lambda: (
            f"@ has attacked * ({empire_name(game, Empire(p2))}). Attack Failed."
        ),
        N.GLBConq: lambda: f"@ has conquered * ({empire_name(game, Empire(p2))}).",
        N.GLBCapConq: lambda: (
            "@ has attacked and conquered the "
            f"{empire_name(game, Empire(p2))} capital."
        ),
        N.GLBLAMStrk: lambda: (
            f"@ has hit * ({empire_name(game, Empire(p2))}) with LAMs."
        ),
        N.GLBRev: lambda: "* has declared independence from @.",
        N.OutProbe: lambda: "* has been scouted by outpost scanners.",
        N.TerChaos: lambda: "Terraforming on * catastrophically failed.",
        N.TerSuccess: lambda: "Terraforming on * has been completed successfully.",
    }

    build = simple.get(headline)
    if build is None:
        return ""

    return build().replace("*", loc_n).replace("@", emp_n)


def in_range_of_starbase(game: GameEnvironment, emp: Empire, obj_xy: XYCoord) -> bool:
    """Whether any of ``emp``'s scanning starbases covers ``obj_xy``.

    Industrial complexes do not scan -- only command bases, fortresses,
    outposts and the rest. The radius is under 6, so 5 sectors.
    """
    from .misc import distance
    from .primintr import get_base_type, get_coord

    for i in range(1, MAX_NO_OF_STARBASES + 1):
        if i not in game.GlobalSets.SetOfStarbasesOf[emp]:
            continue
        base_id = IDNumber(ObjectTypes.Base, i)
        if distance(get_coord(game, base_id), obj_xy) < 6:
            if get_base_type(game, base_id) != TechnologyTypes.cmp:
                return True
    return False


def in_range_of_planet(
    game: GameEnvironment, emp: Empire, f_typ, obj_xy: XYCoord
) -> bool:
    """Whether one of ``emp``'s worlds can *detect* a fleet at ``obj_xy``.

    Weaker than scouting: it tells the empire something is there without
    revealing what. Hunter-killers and penetrators are built to slip this, and
    any nebula at all defeats it.
    """
    from .misc import distance
    from .primintr import get_coord, get_nebula
    from .types import FleetTypes, NebulaTypes

    if f_typ in (FleetTypes.HKFleet, FleetTypes.Penetrator):
        return False
    if get_nebula(game, obj_xy) != NebulaTypes.NoNeb:
        return False

    for i in range(1, game.NoOfPlanets + 1):
        if i not in game.GlobalSets.SetOfPlanetsOf[emp]:
            continue
        base_id = IDNumber(ObjectTypes.Pln, i)
        if distance(get_coord(game, base_id), obj_xy) <= 5:
            return True
    return False


def determine_if_scouted(game: GameEnvironment, emp: Empire, obj: IDNumber) -> None:
    """Decide whether ``emp`` can see ``obj`` in detail this turn.

    Two quite different paths, keyed on whether the empire knows the object
    exists at all:

    - **Known already**: it is scouted if the empire owns it, or it is within 5
      sectors of the capital, or a scanning starbase covers it. So an empire
      sees its own space and its border in detail and nothing else.
    - **Not known**: only a starbase scan can reveal it, and only on a coin
      flip -- ``Rnd(1,2)=1``. This is the one path by which an empire discovers
      something it had no idea was there, and it files an ``OutProbe``
      headline when it does.

    The coin flip means a newly-built starbase takes a few years to map its
    surroundings rather than revealing everything at once.
    """
    from .misc import distance
    from .news import NewsTypes, add_news
    from .primintr import get_capital, get_coord, get_status, known, scout_object, scouted
    from .utils.int_utils import rnd

    obj_xy = get_coord(game, obj)

    if known(game, emp, obj):
        if scouted(game, emp, obj):
            return
        cap_xy = get_coord(game, get_capital(game, emp))
        if get_status(game, obj) == emp:
            scout_object(game, emp, obj)
        elif distance(cap_xy, obj_xy) < 6:
            scout_object(game, emp, obj)
        elif in_range_of_starbase(game, emp, obj_xy):
            scout_object(game, emp, obj)
    elif rnd(1, 2) == 1 and in_range_of_starbase(game, emp, obj_xy):
        add_news(game, emp, NewsTypes.OutProbe, Location(XY=XYCoord(0, 0), ID=obj), 0, 0, 0)
        scout_object(game, emp, obj)


def scout_fleets(game: GameEnvironment, player_emp: Empire) -> None:
    """Recompute which fleets ``player_emp`` can see, and how well.

    Three tiers, and the difference between them is the whole of fleet fog of
    war:

    - **Own fleets** are always both scouted and known.
    - **Scouted** (you see what it is made of): the fleet is adjacent to one of
      your worlds or fleets -- but *only if it is not a hunter-killer group*,
      which is what lets HK raiders sit next to a world unseen -- or it is
      inside a starbase's scan.
    - **Known only** (you see something is there): `in_range_of_planet` picks
      it up at 5 sectors, unless it is an HK or penetrator fleet or sitting in
      a nebula.

    Both flags are cleared for this empire first, so a fleet that has moved out
    of range this turn is genuinely forgotten rather than remembered forever.

    A fleet spotted next to your territory files a ``FltDet`` headline. The
    location it reports is the *observer*: the world that saw it, or -- when
    the spotter was a fleet rather than a world -- the highest-numbered of your
    fleets in that sector, found by counting down from ``MaxNoOfFleets``.
    """
    from .datacnst import DirX, DirY
    from .news import NewsTypes, add_news
    from .primintr import get_fleets, get_status, type_of_fleet
    from .types import Directions, FleetTypes

    for i in range(1, MAX_NO_OF_FLEETS + 1):
        if i not in game.GlobalSets.SetOfActiveFleets:
            continue

        fleet = game.Universe.Fleet[i]
        flt_id = IDNumber(ObjectTypes.Flt, i)
        f_typ = type_of_fleet(game, flt_id)

        fleet.ScoutedBy.discard(player_emp)
        fleet.KnownBy.discard(player_emp)

        if fleet.Emp == player_emp:
            fleet.ScoutedBy.add(player_emp)
            fleet.KnownBy.add(player_emp)
            continue

        spotted = False
        if f_typ != FleetTypes.HKFleet:
            for direction in Directions:
                x = fleet.XY.x + DirX[direction]
                y = fleet.XY.y + DirY[direction]
                if not game.Galaxy.in_galaxy(x, y):
                    continue

                sector = game.Galaxy.sector(XYCoord(x, y))
                if get_status(game, sector.Obj) != player_emp and (
                    player_emp not in sector.Flts
                ):
                    continue

                fleet.ScoutedBy.add(player_emp)
                fleet.KnownBy.add(player_emp)

                loc_id = sector.Obj
                if get_status(game, sector.Obj) != player_emp:
                    # Spotted by a fleet, not a world: report the highest-
                    # numbered friendly fleet in that sector.
                    mine = get_fleets(game, XYCoord(x, y)) & (
                        game.GlobalSets.SetOfFleetsOf[player_emp]
                    )
                    j = MAX_NO_OF_FLEETS
                    while j > 0 and j not in mine:
                        j -= 1
                    loc_id = IDNumber(ObjectTypes.Flt, j)

                add_news(
                    game,
                    player_emp,
                    NewsTypes.FltDet,
                    Location(XY=XYCoord(0, 0), ID=loc_id),
                    int(fleet.Emp),
                    0,
                    0,
                )
                spotted = True
                break

        if spotted:
            continue

        if in_range_of_starbase(game, player_emp, fleet.XY):
            fleet.ScoutedBy.add(player_emp)
            fleet.KnownBy.add(player_emp)
            continue

        if in_range_of_planet(game, player_emp, f_typ, fleet.XY):
            fleet.KnownBy.add(player_emp)


def scout_objects(game: GameEnvironment, emp: Empire) -> None:
    """Sweep the space around everything ``emp`` owns, then rescan for the rest.

    Two halves. First :func:`scout` runs from every world and every fleet the
    empire holds, revealing the ring of sectors around each. Then every world,
    starbase and stargate in the galaxy is put through
    :func:`determine_if_scouted`, which is what picks up objects at a distance
    via capital and starbase scans.

    Note the second half sweeps **every** world, not only known ones -- that is
    how an empire first learns a world exists.
    """
    from .primintr import get_coord

    for i in range(1, game.NoOfPlanets + 1):
        if i in game.GlobalSets.SetOfPlanetsOf[emp]:
            scout(game, emp, get_coord(game, IDNumber(ObjectTypes.Pln, i)))

    active_empire_fleets = (
        game.GlobalSets.SetOfFleetsOf[emp] & game.GlobalSets.SetOfActiveFleets
    )
    for i in range(1, MAX_NO_OF_FLEETS + 1):
        if i in active_empire_fleets:
            scout(game, emp, get_coord(game, IDNumber(ObjectTypes.Flt, i)))

    for i in range(1, game.NoOfPlanets + 1):
        determine_if_scouted(game, emp, IDNumber(ObjectTypes.Pln, i))

    for i in range(1, MAX_NO_OF_STARBASES + 1):
        if i in game.GlobalSets.SetOfActiveStarbases:
            determine_if_scouted(game, emp, IDNumber(ObjectTypes.Base, i))

    for i in range(1, MAX_NO_OF_STARGATES + 1):
        if i in game.GlobalSets.SetOfActiveGates:
            determine_if_scouted(game, emp, IDNumber(ObjectTypes.Gate, i))


def probes_return(game: GameEnvironment, emp: Empire) -> None:
    """Free any probe sitting at its destination for relaunch.

    Nothing in v2.0 sets ``PAtDest`` -- :func:`update_probes` takes a probe
    straight from ``PInTrans`` back to ``PReady`` -- so this never has anything
    to do. Ported as part of the unit's interface.
    """
    from .types import NO_OF_PROBES_PER_EMPIRE, ProbeStatus

    for i in range(1, NO_OF_PROBES_PER_EMPIRE + 1):
        probe = game.Universe.EmpireData[emp].Probe[i]
        if probe.Status == ProbeStatus.PAtDest:
            probe.Status = ProbeStatus.PReady


def next_stargate_slot(game: GameEnvironment) -> int:
    """Highest free stargate index, or 0 when all are taken."""
    slot = len(game.Universe.Stargate) - 1
    while slot > 0 and slot in game.GlobalSets.SetOfActiveGates:
        slot -= 1
    return slot


def create_stargate(
    game: GameEnvironment,
    obj: IDNumber,
    new_emp: Empire,
    gate_type: TechnologyTypes,
    pos: XYCoord,
) -> None:
    game.Galaxy.sector(pos).Obj = obj

    gate = game.Universe.Stargate[obj.Index]
    gate.XY = pos
    gate.GTyp = gate_type
    gate.Emp = new_emp
    game.GlobalSets.SetOfActiveGates.add(obj.Index)


def destroy_stargate(game: GameEnvironment, gte_id: IDNumber) -> None:
    """Remove a stargate, emptying the sector it stood in.

    The gate record itself is left as it was; only the sector pointer and the
    active set are cleared, so the slot is free for reuse.
    """
    gate = game.Universe.Stargate[gte_id.Index]
    game.Galaxy.sector(gate.XY).Obj = empty_quadrant()
    game.GlobalSets.SetOfActiveGates.discard(gte_id.Index)


def create_planet(game: GameEnvironment, obj: IDNumber, new_xy: XYCoord) -> None:
    """Place a planet into the world and register it in its sector."""
    game.Galaxy.sector(new_xy).Obj = obj

    planet = game.Universe.Planet[obj.Index]
    planet.XY = new_xy
    planet.ImpExp = DEFAULT_ISSP
    game.GlobalSets.SetOfActivePlanets.add(obj.Index)
    game.GlobalSets.SetOfPlanetsOf[planet.Emp].add(obj.Index)


def next_starbase_slot(game: GameEnvironment) -> int:
    """Highest free starbase index, or 0 when all are taken.

    Counts down from the top, as the original does, so slot assignment
    matches when comparing runs side by side.
    """
    slot = len(game.Universe.Starbase) - 1
    while slot > 0 and slot in game.GlobalSets.SetOfActiveStarbases:
        slot -= 1
    return slot


def create_starbase(
    game: GameEnvironment,
    obj: IDNumber,
    new_emp,
    new_xy: XYCoord,
    new_typ: TechnologyTypes,
) -> None:
    game.Galaxy.sector(new_xy).Obj = obj

    base = game.Universe.Starbase[obj.Index]
    base.XY = new_xy
    base.STyp = new_typ
    base.Emp = new_emp
    game.GlobalSets.SetOfActiveStarbases.add(obj.Index)
    game.GlobalSets.SetOfStarbasesOf[new_emp].add(obj.Index)


# --- Construction ------------------------------------------------------------


def next_constr_slot(game: GameEnvironment) -> int:
    """Highest free construction-site index, or 0 when all are taken.

    Counts down from the top like the starbase and stargate allocators, so
    slot assignment matches when comparing runs side by side.
    """
    slot = MAX_NO_OF_CONSTR_SITES
    while slot > 0 and slot in game.GlobalSets.SetOfActiveConstructionSites:
        slot -= 1
    return slot


def construction(
    game: GameEnvironment,
    empr: Empire,
    cons_type: TechnologyTypes,
    loc: XYCoord,
) -> IDNumber:
    """Break ground on a construction site. Returns its ID, or EmptyQuadrant.

    The site occupies its sector immediately -- it is a real object that can
    be scouted, named and attacked from the moment it exists, long before it
    finishes. Only the builder knows about it to begin with.

    Silently does nothing when every slot is in use, as the original does.
    """
    i = next_constr_slot(game)
    if i == 0:
        return empty_quadrant()

    con_id = IDNumber(ObjectTypes.Con, i)
    site = game.Universe.Constr[i]
    site.XY = loc
    site.Emp = empr
    site.CTyp = cons_type
    site.ScoutedBy = {empr}
    site.KnownBy = {empr}
    site.TimeToCompletion = YearsToBuild[cons_type]

    game.GlobalSets.SetOfActiveConstructionSites.add(i)
    game.GlobalSets.SetOfConstructionSitesOf[empr].add(i)
    game.Galaxy.sector(loc).Obj = con_id
    return con_id


def destroy_construction(game: GameEnvironment, con_id: IDNumber) -> None:
    """Cancel a construction site, emptying the sector it occupied."""
    site = game.Universe.Constr[con_id.Index]
    old_emp = site.Emp
    game.Galaxy.sector(site.XY).Obj = empty_quadrant()
    game.GlobalSets.SetOfActiveConstructionSites.discard(con_id.Index)
    game.GlobalSets.SetOfConstructionSitesOf[old_emp].discard(con_id.Index)


# --- Fleet helpers -----------------------------------------------------------

#: Order in which BalanceFleet jettisons cargo: cheapest first, ambrosia last.
#: 1-based in the original; index 0 is unused here for the same reason.
CARGO_PRIORITY: tuple[TechnologyTypes | None, ...] = (
    None,
    TechnologyTypes.che,
    TechnologyTypes.sup,
    TechnologyTypes.met,
    TechnologyTypes.men,
    TechnologyTypes.nnj,
    TechnologyTypes.tri,
    TechnologyTypes.amb,
)


def balance_fleet(ships: dict[TechnologyTypes, int], cargo: dict[TechnologyTypes, int]) -> None:
    """Jettison cargo in place until the fleet fits in its own transports.

    Works down CARGO_PRIORITY dumping whole cargo types, then partly refills
    the last one to exactly fill the space that freed up. A fleet whose
    transports were destroyed loses cargo this way rather than becoming
    illegal.
    """
    to_remove = 1
    thing = CARGO_PRIORITY[to_remove]
    space_left = fleet_cargo_space(ships, cargo)

    while space_left < 0:
        cargo[thing] = 0
        new_space_left = fleet_cargo_space(ships, cargo)
        if new_space_left < 0:
            space_left = new_space_left
            to_remove += 1
            thing = CARGO_PRIORITY[to_remove]
        else:
            cargo[thing] = new_space_left * CargoSpace[thing]
            space_left = 0


def passing_through_fortress(game: GameEnvironment, flt_xy: XYCoord) -> bool:
    """Whether a fortress starbase sits on the fleet's current sector."""
    base_obj = get_object(game, flt_xy)
    return (
        base_obj.ObjTyp == ObjectTypes.Base
        and get_base_type(game, base_obj) == TechnologyTypes.frt
    )


def passing_through_gate(
    game: GameEnvironment, flt_id: IDNumber, flt_xy: XYCoord, dest_xy: XYCoord
) -> bool:
    """Whether the fleet can jump from ``flt_xy`` to ``dest_xy`` via a gate.

    A plain gate (``gte``) sends a fleet anywhere. A link (``lnk``) only
    connects to another gate or link at the far end -- and, per the original,
    only when the destination gate's frequency does *not* match, which is what
    distinguishes a link's own network from a gate the fleet could simply use.

    Fortresses are handled separately by the caller.
    """
    gate_obj = get_object(game, flt_xy)
    if gate_obj.ObjTyp != ObjectTypes.Gate:
        return False
    if get_warp_link_freq(game, get_status(game, flt_id), gate_obj) != get_warp_link_freq(
        game, get_status(game, gate_obj), gate_obj
    ):
        return False

    gate_type = get_gate_type(game, gate_obj)
    if gate_type == TechnologyTypes.gte:
        return True
    if gate_type == TechnologyTypes.lnk:
        dest_obj = get_object(game, dest_xy)
        return (
            dest_obj.ObjTyp == ObjectTypes.Gate
            and get_gate_type(game, dest_obj)
            in (TechnologyTypes.lnk, TechnologyTypes.gte)
            and get_warp_link_freq(game, get_status(game, flt_id), dest_obj)
            != get_warp_link_freq(game, get_status(game, dest_obj), dest_obj)
        )
    return False


# --- Travel estimates --------------------------------------------------------


def estimated_date_of_arrival(game: GameEnvironment, obj: IDNumber) -> int:
    """Years until ``obj`` reaches its destination.

    A fleet riding a gate always arrives next year whatever the distance. A
    fortress shortens the trip by the four sectors it catapults the fleet --
    ``passing_through_fortress`` is checked at the fleet's *current* position,
    so the boost only counts while the fleet is still standing on it.

    Bases move one sector a year, so their estimate is the raw Chebyshev
    distance. The original leaves the result uninitialised for any other
    object type; every caller passes a fleet or a base.
    """
    from .fleet import type_of_fleet

    if obj.ObjTyp == ObjectTypes.Flt:
        fleet = game.Universe.Fleet[obj.Index]
        if passing_through_gate(game, obj, fleet.XY, fleet.Dest):
            return 1

        dist = max(abs(fleet.XY.x - fleet.Dest.x), abs(fleet.XY.y - fleet.Dest.y))
        if passing_through_fortress(game, fleet.XY):
            dist = max(dist - 4, 1)

        quads_per_year = FltMovementRate[type_of_fleet(game, obj)]
        eda = dist // quads_per_year
        if dist % quads_per_year > 0:
            eda += 1
        return eda

    if obj.ObjTyp == ObjectTypes.Base:
        base = game.Universe.Starbase[obj.Index]
        return max(abs(base.XY.x - base.Dest.x), abs(base.XY.y - base.Dest.y))

    return 0


def estimated_range(game: GameEnvironment, obj: IDNumber) -> int:
    """How many years of travel ``obj`` has fuel for.

    ``fuel_consumption`` starts at 1 rather than 0, so this cannot divide by
    zero even for an empty fleet. A base burns a flat 100 tons a year, which
    is where its divisor comes from.
    """
    from .fleet import get_fleet_fuel
    from .misc import fuel_consumption
    from .primintr import get_cargo, get_ships
    from .utils.pascal import trunc

    ships = get_ships(game, obj)
    cargo = get_cargo(game, obj)

    if obj.ObjTyp == ObjectTypes.Flt:
        return trunc(get_fleet_fuel(game, obj) / fuel_consumption(ships, cargo))
    if obj.ObjTyp == ObjectTypes.Base:
        return cargo[TechnologyTypes.tri] // 100
    return 0


# --- Status lines for the F-key windows --------------------------------------
#
# INTRFACE.PAS builds every row the §8.3 windows show. The windows themselves
# (STAWIND, FLTWIND, EMPWIND) only choose *which* objects to list and in what
# order; the text is all made here, which is why these live in `intrface.py`
# rather than with the windows.
#
# One rule runs through all of them: **what you may read depends on whose it
# is.** Your own worlds and fleets report exact figures; a scouted stranger's
# report `y`/`no` per line and `--` for anything you could not possibly count;
# an unscouted one reports `(out of range)`. That is the same three-valued fog
# the map uses, spelled out in columns.


def _adjust(text: str, width: int) -> str:
    """Pascal's ``AdjustString``: pad or truncate to exactly ``width``."""
    return text[:width].ljust(width)


def get_import_export_str(game: GameEnvironment, obj: IDNumber) -> str:
    """The Impt/Expt pair on the world status row.

    Four industries can be over- or under-supplied -- chemicals, metals,
    supplies and trillum -- and each shows as its own initial in one column or
    the other, or ``-`` in both when it is at ``NormalISSP``. So ``-C--`` under
    Impt means the world is buying chemicals.

    The loop runs ``CheInd TO TriInd`` and then filters back down to those
    four, which is the original's way of fixing the column order regardless of
    where the industries sit in the enum.
    """
    #: Pascal's ``IndN``, one initial per industry; the five it never reaches
    #: are dashes.
    indus_initial = "BCM----ST"

    imports = ""
    exports = ""
    for ind in indus_range(IT.CheInd, IT.TriInd):
        if ind not in (IT.CheInd, IT.MinInd, IT.SupInd, IT.TriInd):
            continue
        issp = get_issp(game, obj, ind)
        letter = indus_initial[int(ind)]
        if issp == NORMAL_ISSP:
            imports += "-"
            exports += "-"
        elif issp > NORMAL_ISSP:
            imports += "-"
            exports += letter
        else:
            imports += letter
            exports += "-"

    return f"{imports} {exports}"


def get_world_status(
    game: GameEnvironment, emp: Empire, world_id: IDNumber
) -> str:
    """One row of the F3 planetary status table. Port of ``GetWorldStatus``.

    Columns: name, owner, class, type, tech, population, efficiency, ambrosia
    addiction, import/export, revolution index, then transports and cargo.

    **A population under 0.1 billion reads ``<0.1`` rather than rounding to
    0.0**, which is the one place the game admits a world is inhabited without
    saying by how few.

    The last seven columns are the fog boundary: your own world shows counts,
    anyone else's shows `y`/`no` for the two transport types and `--` for all
    five cargoes. You can see hulls in orbit; you cannot audit a warehouse.
    """
    from .misc import hi_lo, yes_no
    from .primintr import (
        empire_name,
        get_cargo,
        get_rev_index,
        get_ships_known,
        object_name,
    )

    name = _adjust(object_name(game, emp, world_id), 8)
    status = get_status(game, world_id)
    owner = _adjust(empire_name(game, status) or "", 3)

    ships = get_ships_known(game, emp, world_id)
    cargo = get_cargo(game, world_id)
    special = get_special(game, world_id)
    pop = get_population(game, world_id)

    line = (
        f"{name} {owner} "
        f"{ClassStr[get_class(game, world_id)]} "
        f"{TypeStr[get_type(game, world_id)]} "
        f"{TechStr[get_tech(game, world_id)]} "
    )
    line += (f"{pop / 100:4.1f}" if pop > 9 else "<0.1") + " "
    line += f"{get_efficiency(game, world_id):3} "
    line += "y " if SpecialConditions.AmbAddict in special else "- "
    line += get_import_export_str(game, world_id) + " "
    line += hi_lo(get_rev_index(game, world_id))

    if emp == status:
        line += f"{ships[TechnologyTypes.jtn]:5}{ships[TechnologyTypes.trn]:5}"
        for thing in tech_range(TechnologyTypes.amb, TechnologyTypes.tri):
            line += f"{cargo[thing]:5}"
    else:
        line += (
            yes_no(ships[TechnologyTypes.jtn])
            + yes_no(ships[TechnologyTypes.trn])
            + "  --   --   --   --   --  "
        )

    return line


def get_military_status(
    game: GameEnvironment, emp: Empire, world_id: IDNumber
) -> str:
    """One row of the F4 military status table. Port of ``GetMilitaryStatus``.

    Troops, then every ship type, then the four fixed defenses. Note the
    defenses are read with :func:`~recreon.primintr.get_defns` for *both*
    branches, but only printed for your own world -- a stranger's row stops
    after the ships, which is why the table is narrower on the right for
    everyone else.
    """
    from .misc import yes_no
    from .primintr import (
        empire_name,
        get_cargo,
        get_defns,
        get_ships,
        get_ships_known,
        object_name,
    )

    name = _adjust(object_name(game, emp, world_id), 8)
    status = get_status(game, world_id)
    cargo = get_cargo(game, world_id)
    defns = get_defns(game, world_id)
    owner = _adjust(empire_name(game, status) or "", 3)

    line = f"{name} {owner} "

    if emp == status:
        ships = get_ships(game, world_id)
        line += f"{cargo[TechnologyTypes.men]:5}{cargo[TechnologyTypes.nnj]:5}"
        for thing in SHIP_TYPES:
            line += f"{ships[thing]:5}"
        for thing in tech_range(TechnologyTypes.LAM, TechnologyTypes.ion):
            line += f"{defns[thing]:5}"
    else:
        ships = get_ships_known(game, emp, world_id)
        line += yes_no(cargo[TechnologyTypes.men]) + yes_no(cargo[TechnologyTypes.nnj])
        for thing in SHIP_TYPES:
            line += yes_no(ships[thing])

    return line


def get_empire_status_line(
    game: GameEnvironment, emp: Empire, full: bool
) -> str:
    """One row of the F8 empire table. Port of ``GetEmpireStatusLine``.

    ``full`` is the fog: an empire whose capital you have merely *found* shows
    its size and technology but dashes where its fleet strength would be. You
    learn how big a rival is long before you learn what it can field.

    The technology shown is the *capital's*, not the empire record's, which
    differ while a newly taken capital is still catching up.
    """
    from .primintr import empire_name

    capital = game.Universe.EmpireData[emp].Capital
    line = _adjust(empire_name(game, emp) or "", 12)
    line += " " + TechStr[get_tech(game, capital)] + " "

    planets, total_pop, s_ind, total_ships = get_empire_status(game, emp)
    line += f"{planets:3} {s_ind / 10:4.1f} {total_pop / 100:5.1f} "

    if full:
        for thing in SHIP_TYPES:
            line += f"{total_ships[thing]:6} "
    else:
        line += " ----   ----   ----   ----   ----   ----   ----  "

    return line


def get_fleet_position_status(
    game: GameEnvironment, emp: Empire, obj: IDNumber
) -> str:
    """The top half of the F5 fleet table. Port of ``GetFleetPositionStatus``.

    Where a fleet is, where it is going, how it is doing and how far it can
    still travel. Bases appear here too, which is why the coordinate columns
    are built two different ways: a fleet's position goes through
    :func:`~recreon.primintr.get_name` so a named sector reads by its name,
    while a base's goes straight to :func:`get_coord_name`.

    Three details of the enemy branch are deliberate:

    * A ready enemy fleet's *destination* column repeats its position. It is
      not going anywhere, and the original writes ``PosName`` twice rather
      than inventing a blank.
    * An unscouted fleet reads ``(unknown)`` for destination and
      ``(out of range)`` for status -- you know it exists, nothing more.
    * The range column is omitted entirely. Fuel is your business alone.

    ``(orders)`` on your own fleet means it is running a compiled order list.
    """
    from .orders import fleet_next_statement
    from .primintr import (
        empire_name,
        get_coord_name,
        get_name,
        object_name,
        scouted,
    )
    from .types import FleetStatus

    #: The four ``FleetStatus`` labels, by ordinal. ``FInTrans``'s is a
    #: placeholder -- the live path substitutes the estimated arrival year for
    #: the ``?``.
    #:
    #: Note ``FInactive`` reads **"out of trillum"**. The enum member is named
    #: for the state and the label for its only cause: a fleet goes inactive
    #: when it cannot pay for the next jump.
    fleet_status_name = {
        FleetStatus.FReady: "at destination    ",
        FleetStatus.FInTrans: "In transit (?)    ",
        FleetStatus.FInactive: "out of trillum    ",
        FleetStatus.FLost: "lost              ",
    }

    if obj.ObjTyp == ObjectTypes.Flt:
        entity = game.Universe.Fleet[obj.Index]
    else:
        entity = game.Universe.Starbase[obj.Index]
    location, destination = entity.XY, entity.Dest
    flt_sta, flt_emp = entity.Status, entity.Emp

    if obj.ObjTyp == ObjectTypes.Flt:
        pos_name = get_name(game, emp, Location(XY=location, ID=empty_quadrant()))
        des_name = get_name(game, emp, Location(XY=destination, ID=empty_quadrant()))
    else:
        pos_name = get_coord_name(game, location)
        des_name = get_coord_name(game, destination)

    pos_name = _adjust(pos_name, 8)
    des_name = _adjust(des_name, 8)
    flt_name = _adjust(object_name(game, emp, obj), 8)

    if flt_emp == emp:
        line = f"     {flt_name}   {pos_name}   {des_name}   "
        if flt_sta == FleetStatus.FInTrans:
            sta_name = f"In transit ({estimated_date_of_arrival(game, obj)})"
        else:
            sta_name = fleet_status_name[flt_sta]
        line += _adjust(sta_name, 18) + "   "
        line += f"{estimated_range(game, obj):3}"
        if obj.ObjTyp == ObjectTypes.Flt and fleet_next_statement(game, obj) != 0:
            line += "       (orders)"
        return line

    line = _adjust(empire_name(game, flt_emp) or "", 3)
    line += f"  {flt_name}   {pos_name}   "
    if flt_sta == FleetStatus.FReady and scouted(game, emp, obj):
        line += f"{pos_name}   "
    else:
        line += "(unknown)  "
    sta_name = (
        fleet_status_name[flt_sta] if scouted(game, emp, obj) else "(out of range)"
    )
    return line + _adjust(sta_name, 18) + "      "


def get_fleet_status_line(
    game: GameEnvironment, emp: Empire, obj: IDNumber
) -> str:
    """The bottom half of the F5 fleet table. Port of ``GetFleetStatusLine``.

    What is aboard: every hull, then every cargo. A stranger's fleet shows
    `y`/`no` per hull and `--` for the whole hold; an unscouted one shows
    nothing at all beyond its name.

    Note the ownership test is against the *empire asking*, so this is the one
    of the pair that never mentions an enemy's destination or fuel.
    """
    from .misc import yes_no
    from .primintr import get_cargo, get_ships, object_name, scouted

    name = _adjust(object_name(game, emp, obj), 8)
    status = get_status(game, obj)
    ships = get_ships(game, obj)
    cargo = get_cargo(game, obj)

    if status == emp:
        line = name
        for thing in SHIP_TYPES:
            line += f"{ships[thing]:5}"
        for thing in tech_range(TechnologyTypes.men, TechnologyTypes.tri):
            line += f"{cargo[thing]:5}"
        return line

    if scouted(game, emp, obj):
        line = name
        for thing in SHIP_TYPES:
            line += yes_no(ships[thing])
        return line + "  --   --   --   --   --   --   -- "

    return name + " (out of range)"


def get_nearest_worlds(
    game: GameEnvironment, xy: XYCoord, n: int, set_to_consider: set[int]
) -> list[IDNumber]:
    """The ``n`` worlds in ``set_to_consider`` closest to ``xy``.

    A bucket sort by distance rather than a comparison sort: every world is
    dropped into the bucket for its distance, then the buckets are read out in
    order until ``n`` have been taken. Worlds tie-break by index, because the
    original appends to each bucket's list rather than prepending.

    A world sitting exactly on ``xy`` lands in bucket 0 and so comes back
    first. Returns fewer than ``n`` when the set holds fewer -- and an empty
    list for an empty set, which is where the original hands its caller a nil
    pointer to dereference.
    """
    from .misc import distance
    from .primintr import get_coord

    size = game.Galaxy.size
    buckets: list[list[IDNumber]] = [[] for _ in range(size + 1)]

    for i in range(1, game.NoOfPlanets + 1):
        if i not in set_to_consider:
            continue
        pln_id = IDNumber(ObjectTypes.Pln, i)
        dist = distance(get_coord(game, pln_id), xy)
        if dist <= size:
            buckets[dist].append(pln_id)

    near: list[IDNumber] = []
    for bucket in buckets:
        for pln_id in bucket:
            if len(near) >= n:
                return near
            near.append(pln_id)

    return near


# --- Empire totals -----------------------------------------------------------


def get_empire_status(
    game: GameEnvironment, emp: Empire
) -> tuple[int, int, int, dict[TechnologyTypes, int]]:
    """Vital statistics for an empire. Port of ``GetEmpireStatus``.

    Returns ``(planets, total_pop, ship_ind, total_ships)`` -- world count,
    population in tens of millions, shipyard industry in tenths, and every
    ship the empire owns wherever it is standing.

    Two things are easy to get wrong. **Starbases count toward ``planets``**
    alongside worlds and add their population to the total, so the "number of
    worlds" this reports is really "number of holdings" -- but only a ``cmp``
    industrial complex contributes shipyard industry, since a command base or
    fortress builds nothing. And the ship total **sweeps fleets as well as
    worlds**, so a fleet in transit is still counted: this is a census of the
    empire, not of what is sitting still.
    """
    planets = 0
    total_pop = 0
    ship_ind = 0.0
    total_ships = ship_array()

    universe = game.Universe

    for i in range(1, game.NoOfPlanets + 1):
        if i not in game.GlobalSets.SetOfPlanetsOf[emp]:
            continue
        planet = universe.Planet[i]
        planets += 1
        total_pop += planet.Pop
        ip = (TechAdj2[planet.Tech] / 100) * ((planet.Eff + 250) / 100) / K6
        for ind in SHIPYARD_INDUSTRIES:
            ship_ind += ip * (planet.Indus[ind] + K4) ** 2
        for shp in SHIP_TYPES:
            total_ships[shp] += planet.Ships[shp]

    for i in range(1, MAX_NO_OF_STARBASES + 1):
        if i not in game.GlobalSets.SetOfStarbasesOf[emp]:
            continue
        base = universe.Starbase[i]
        planets += 1
        total_pop += base.Pop
        for shp in SHIP_TYPES:
            total_ships[shp] += base.Ships[shp]
        if base.STyp == TechnologyTypes.cmp:
            ip = (TechAdj2[base.Tech] / 100) * ((base.Eff + 250) / 100) / K6
            for ind in SHIPYARD_INDUSTRIES:
                ship_ind += ip * (base.Indus[ind] + K4) ** 2

    active = game.GlobalSets.SetOfFleetsOf[emp] & game.GlobalSets.SetOfActiveFleets
    for i in sorted(active):
        fleet = universe.Fleet[i]
        for shp in SHIP_TYPES:
            total_ships[shp] += fleet.Ships[shp]

    return planets, total_pop, pascal_round(ship_ind), total_ships


def destroy_empire(game: GameEnvironment, emp: Empire) -> None:
    """Wipe an empire out: worlds go independent, fleets are aborted and lost.

    Starbases change hands but keep their contents. Fleets are unloaded onto
    whatever object shares their sector before being destroyed, so a fleet
    dying over a friendly world still hands its cargo over.

    ``CleanUpNPE`` is not called. The NPE subsystem is Phase 7, and while
    ``npe/core.py`` is now ported nothing drives it yet, so there is still
    nothing for it to release. This needs wiring once the personas own
    per-empire state -- ``conquer_empire`` reaches here whenever a non-player
    empire's capital falls with no successor world.
    """
    from .fleet import abort_fleet, destroy_fleet
    from .news import erase_news
    from .primintr import (
        delete_all_names,
        get_coord,
        initialize_issp,
        set_status,
        set_type,
    )

    for index in range(1, game.NoOfPlanets + 1):
        obj = IDNumber(ObjectTypes.Pln, index)
        if get_status(game, obj) == emp:
            set_status(game, obj, Empire.Indep)
            set_type(game, obj, WorldTypes.IndTyp)
            initialize_issp(game, obj)

    for index in sorted(game.GlobalSets.SetOfStarbasesOf[emp]):
        set_status(game, IDNumber(ObjectTypes.Base, index), Empire.Indep)

    fleets = game.GlobalSets.SetOfFleetsOf[emp] & game.GlobalSets.SetOfActiveFleets
    for index in sorted(fleets):
        flt_id = IDNumber(ObjectTypes.Flt, index)
        ground = get_object(game, get_coord(game, flt_id))
        if ground != empty_quadrant():
            abort_fleet(game, flt_id, ground, True)
        destroy_fleet(game, flt_id)

    erase_news(game, emp)
    delete_all_names(game, emp)

    game.Universe.EmpireData[emp].InUse = False


__all__ = [
    "CARGO_PRIORITY",
    "SHIPYARD_INDUSTRIES",
    "get_empire_status",
    "get_empire_status_line",
    "get_fleet_position_status",
    "get_fleet_status_line",
    "get_import_export_str",
    "get_military_status",
    "get_world_status",
    "Gamma",
    "balance_fleet",
    "create_planet",
    "create_stargate",
    "construction",
    "destroy_construction",
    "destroy_empire",
    "destroy_stargate",
    "next_constr_slot",
    "next_stargate_slot",
    "passing_through_fortress",
    "passing_through_gate",
    "scout",
    "create_starbase",
    "get_industrial_distribution",
    "get_optimum_indus",
    "next_starbase_slot",
    "ObjectTypes",
]
