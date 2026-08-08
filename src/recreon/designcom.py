"""World and empire commands.

Ports the command half of DESIGN.PAS. The mechanics half -- `designate_world`,
`terraform_world`, `change_issp` -- is :mod:`recreon.design`, and INTRFACE.PAS
is where the original actually keeps the first two.

Seven commands, and between them they close most of what the menus could not
reach: designate a world, terraform it, set its ISSP, hand it away, trade a
technology, send and read messages, and launch LAMs from a base.

**A theme worth noticing.** Four of these ask "are you sure (y/N)" and then
do as they are told. `DesignateCommand` alone has five such warnings -- a
university world less advanced than the capital, a mining world on an ocean,
an agricultural world on ice. The original consistently advises rather than
forbids, and the port keeps that: :func:`designation_warnings` returns text,
never a refusal.

Drawing all of it is :mod:`recreon.ui.worlds`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .attack import lam_attack
from .datacnst import (
    IndusNames,
    MinTechForType,
    PrincipalIndustry,
    TechDev,
    TechnologyName,
    TerraformPotentialClasses,
    TypeName,
)
from .design import change_issp, designate_world, terraform_world
from .environ import GameEnvironment
from .galaxy import Location, limbo
from .mess import MessageRecord, get_messages, send_message, set_message_read
from .misc import distance
from .news import NewsTypes, add_news
from .primintr import (
    empire_active,
    empire_name,
    get_base_type,
    get_capital,
    get_coord,
    get_defns,
    get_empire_technology,
    get_fleets,
    get_issp,
    get_status,
    get_tech,
    get_type,
    initialize_issp,
    known,
    my_lord,
    object_name,
    put_defns,
    scouted,
    set_empire_technology,
    set_status,
)
from .types import (
    PLAYER_EMPIRES,
    Empire,
    IDNumber,
    IndusTypes,
    ObjectTypes,
    TechLevel,
    TechnologyTypes,
    WorldClass,
    WorldTypes,
    empty_quadrant,
)

T = TechnologyTypes
IT = IndusTypes

#: How far LAMs reach from the base that launches them.
LAM_RANGE = 5

#: The four industries ISSP applies to, in the order the original's table
#: shows them. `ISSPArray` is `ARRAY [0..3]` and these are what it maps to.
ISSP_INDUSTRIES = (IT.CheInd, IT.MinInd, IT.SupInd, IT.TriInd)

#: World types the designation menu never offers: the starbase variants, the
#: outpost, and Terraforming, which is a state rather than a choice.
UNDESIGNATABLE = frozenset(
    {
        WorldTypes.OutTyp,
        WorldTypes.BseSTyp,
        WorldTypes.JmpSTyp,
        WorldTypes.StrSTyp,
        WorldTypes.TrnSTyp,
        WorldTypes.RawSTyp,
        WorldTypes.TerTyp,
    }
)

#: Full world-class names, from `ClassN` inside ``TerraformCommand``. A local
#: table in the original, and distinct from `ClassStr`'s single letters.
ClassN: dict[WorldClass, str] = {
    WorldClass.AmbCls: "Ambrosia",
    WorldClass.ArdCls: "Arid",
    WorldClass.ArtCls: "Artificial",
    WorldClass.BarCls: "Barren",
    WorldClass.ClsJ: "Class j",
    WorldClass.ClsK: "Class k",
    WorldClass.ClsL: "Class l",
    WorldClass.ClsM: "Class m",
    WorldClass.DrtCls: "Desert",
    WorldClass.EthCls: "Earth-like",
    WorldClass.FstCls: "Forest world",
    WorldClass.GsGCls: "Gas Giant",
    WorldClass.HLfCls: "Hostile life",
    WorldClass.IceCls: "Ice world",
    WorldClass.JngCls: "Jungle world",
    WorldClass.OcnCls: "Ocean world",
    WorldClass.ParCls: "Paradise",
    WorldClass.PsnCls: "Poisonous",
    WorldClass.RnsCls: "Ancient ruins",
    WorldClass.UndCls: "Underground",
    WorldClass.TerCls: "Terraforming",
    WorldClass.VlcCls: "Volcanic",
}


# --- Designate ---------------------------------------------------------------


def designation_options(
    game: GameEnvironment, world: IDNumber
) -> list[tuple[WorldTypes, str, str]]:
    """What a world may be redesignated as. Port of ``GetDesignation``.

    Returns (type, name, main industry). Three filters: the world's technology
    must reach ``MinTechForType``, the starbase variants and Terraforming are
    never offered, and an ambrosia world needs an ambrosia or paradise class.

    The industry column names what the designation is *for*, which is the
    point of the screen -- research and raw-material worlds get prose because
    they have no single principal industry.
    """
    tech = get_tech(game, world)
    cls = get_class_of(game, world)

    found: list[tuple[WorldTypes, str, str]] = []
    for typ in WorldTypes:
        if MinTechForType[typ] > tech or typ in UNDESIGNATABLE:
            continue
        if typ == WorldTypes.AmbTyp and cls not in (
            WorldClass.AmbCls,
            WorldClass.ParCls,
        ):
            continue

        if typ == WorldTypes.RsrTyp:
            industry = "(research)"
        elif typ == WorldTypes.RawTyp:
            industry = "raw material mining"
        elif typ == WorldTypes.CapTyp:
            industry = "administration"
        else:
            industry = IndusNames[PrincipalIndustry[typ]]

        found.append((typ, TypeName[typ].capitalize(), industry))

    return found


def get_class_of(game: GameEnvironment, obj: IDNumber) -> WorldClass:
    from .primintr import get_class

    return get_class(game, obj)


#: Classes on which large-scale mining goes badly.
POOR_MINING = frozenset(
    {WorldClass.GsGCls, WorldClass.IceCls, WorldClass.OcnCls, WorldClass.PsnCls}
)

#: Classes on which farming goes badly.
POOR_FARMING = frozenset(
    {
        WorldClass.ArdCls,
        WorldClass.ArtCls,
        WorldClass.BarCls,
        WorldClass.DrtCls,
        WorldClass.IceCls,
        WorldClass.PsnCls,
        WorldClass.UndCls,
        WorldClass.VlcCls,
    }
)

#: Designations worth giving an industrial complex.
COMPLEX_WORTHY = frozenset(
    {
        WorldTypes.BseTyp,
        WorldTypes.JmpTyp,
        WorldTypes.StrTyp,
        WorldTypes.TrnTyp,
        WorldTypes.CapTyp,
        WorldTypes.NnjTyp,
    }
)


def designation_warnings(
    game: GameEnvironment, player: Empire, world: IDNumber, new_type: WorldTypes
) -> list[str]:
    """Advice before redesignating. Port of ``DesignateCommand``'s five tests.

    **All five are warnings, none is a refusal.** The original asks "are you
    sure (y/N)" and proceeds on yes, so a player may make any of these
    mistakes deliberately -- and some are not mistakes at all once the world
    has been terraformed or the capital moved.

    Only the first matching test fires: the original's chain is ``ELSE IF``,
    so a capital designation never also warns about the class.
    """
    lord = my_lord(game, player)
    name = object_name(game, player, world, long_format=True)
    cls = get_class_of(game, world)

    if new_type == WorldTypes.CapTyp:
        return [
            f"{lord}, changing the capital will result in short-term loss of",
            "efficiency and increased unrest among the people of the empire.",
        ]

    if (
        world.ObjTyp == ObjectTypes.Base
        and get_base_type(game, world) == T.cmp
        and new_type not in COMPLEX_WORTHY
    ):
        return [
            f"But {lord}, an industrial complex would be wasted on such a trivial",
            "designation.",
        ]

    if new_type == WorldTypes.RsrTyp and get_tech(game, world) < get_tech(
        game, get_capital(game, player)
    ):
        return [
            f"But {lord}, {name} is not yet as advanced as the capital.",
            "As a university world it wouldn't be of much use.",
        ]

    if (
        new_type in (WorldTypes.MinTyp, WorldTypes.RawTyp, WorldTypes.TriTyp)
        and cls in POOR_MINING
    ):
        return [
            f"{lord}, the environment of {name} is not really suited to",
            "large scale mining operations.",
        ]

    if new_type == WorldTypes.AgrTyp and cls in POOR_FARMING:
        return [
            f"I hope you will reconsider, {lord}, {name} would not be",
            "an ideal agricultural world.",
        ]

    return []


def designate_command(
    game: GameEnvironment, player: Empire, world: IDNumber, new_type: WorldTypes
) -> list[str]:
    """Redesignate a world. Port of ``DesignateCommand`` past the warnings.

    Redesignating is skipped when the type has not changed, so re-confirming
    a world's existing designation costs it nothing -- `designate_world`
    redistributes every industry and would otherwise reset its efficiency.
    """
    from .primintr import get_efficiency

    name = object_name(game, player, world, long_format=True)

    if new_type != get_type(game, world):
        designate_world(game, world, new_type)

    return [
        f"{name} has been designated as {TypeName[new_type]}.",
        "All industries are being re-distributed. New efficiency: "
        f"{get_efficiency(game, world)}%",
    ]


# --- Terraform ---------------------------------------------------------------


def terraform_options(
    game: GameEnvironment, world: IDNumber
) -> list[tuple[WorldClass, str]]:
    """Classes this world could become. Port of ``GetNewClass``.

    Straight out of ``TerraformPotentialClasses``, dropping the world's own
    class -- which is also how the table's padding is filtered, since unused
    slots repeat the source class. An artificial world's row is nothing but
    padding, so it can be terraformed into nothing at all.
    """
    cls = get_class_of(game, world)
    return [
        (option, ClassN[option])
        for option in TerraformPotentialClasses[cls]
        if option is not None and option != cls
    ]


def terraform_command(
    game: GameEnvironment, player: Empire, world: IDNumber, new_class: WorldClass
) -> list[str]:
    """Begin terraforming. Port of ``TerraformCommand`` past its confirmation."""
    name = object_name(game, player, world, long_format=True)

    if new_class == get_class_of(game, world):
        return []

    terraform_world(game, world, new_class)
    return [f"{name} is being terraformed towards {ClassN[new_class]}."]


# --- ISSP --------------------------------------------------------------------


def issp_settings(game: GameEnvironment, world: IDNumber) -> dict[IT, int]:
    """The world's four import/export settings. ``GetISSPArray``."""
    return {ind: get_issp(game, world, ind) for ind in ISSP_INDUSTRIES}


def set_issp_settings(
    game: GameEnvironment, world: IDNumber, settings: dict[IT, int]
) -> None:
    """Store them back. ``SetISSPArray``.

    Only the four: chemicals, metals, supplies and trillum are the things a
    world trades. Everything else it makes is used where it stands.
    """
    for ind in ISSP_INDUSTRIES:
        if ind in settings:
            change_issp(game, world, ind, settings[ind])


# --- Liberate ----------------------------------------------------------------


def independence_recipients(
    game: GameEnvironment, player: Empire, world: IDNumber
) -> list[tuple[Empire, str]]:
    """Who a world may be handed to. Port of ``GetNewEmpire``.

    Independence is always offered. Beyond that, **only an empire with a
    scouted fleet in the world's own sector** -- you cannot gift a world to
    someone who is not there to take it, which makes handing worlds over a
    negotiated act rather than a free one.
    """
    xy = get_coord(game, world)
    found: list[tuple[Empire, str]] = [
        (Empire.Indep, empire_name(game, Empire.Indep) or "Independent")
    ]
    seen = {player, Empire.Indep}

    for index in sorted(get_fleets(game, xy)):
        flt = IDNumber(ObjectTypes.Flt, index)
        emp = get_status(game, flt)
        if emp not in seen and scouted(game, player, flt):
            seen.add(emp)
            found.append((emp, empire_name(game, emp) or emp.name))

    return found


def grant_independence_command(
    game: GameEnvironment, player: Empire, world: IDNumber, new_emp: Empire
) -> str:
    """Hand a world away. Port of ``GrantIndependenceCommand``.

    A world set free becomes an industrial world; one given to another empire
    keeps its designation. Either way it is redesignated, which redistributes
    its industry, and its ISSP is reset -- the new owner inherits the place,
    not the previous owner's trade arrangements.
    """
    name = object_name(game, player, world, long_format=True)

    if new_emp == Empire.Indep and world.ObjTyp != ObjectTypes.Base:
        designate_world(game, world, WorldTypes.IndTyp)
    else:
        designate_world(game, world, get_type(game, world))

    initialize_issp(game, world)
    set_status(game, world, new_emp)
    add_news(
        game, new_emp, NewsTypes.GInd, Location(XY=limbo(), ID=world), int(player)
    )

    if new_emp == Empire.Indep:
        return f"{name} is now independent."
    return f"{name} is now part of the empire of {empire_name(game, new_emp)}."


# --- Trade technology --------------------------------------------------------


def tradeable_technologies(
    game: GameEnvironment, player: Empire, other: Empire
) -> set[T]:
    """What ``player`` could give ``other``. ``PlyTechSet * (TechDev[Tech] -
    TechDev[Pred(Tech)])``.

    Only technologies belonging to the recipient's **own current tier** that
    the player happens to have. You cannot advance anyone a level -- only fill
    the gaps at the level they already occupy, which a scenario can leave by
    granting a partial technology set.

    Note what is *not* tested: whether the recipient already has the thing.
    The intersection is with what the **player** holds, not with what the
    other empire lacks, so two empires at the same level are always offered
    each other's whole tier and the "you have nothing that others would want"
    branch almost never fires. Reproduced.
    """
    _, mine = get_empire_technology(game, player)
    tech, _ = get_empire_technology(game, other)

    tier = set(TechDev[tech])
    if tech > TechLevel.PreTchLvl:
        tier -= set(TechDev[TechLevel(int(tech) - 1)])

    return mine & tier


def technology_recipients(
    game: GameEnvironment, player: Empire
) -> list[tuple[Empire, str]]:
    """Empires there is anything to give. Port of ``GetEmpireToSell``.

    An empty list is the "you have nothing that others would want" case.
    """
    return [
        (emp, empire_name(game, emp) or emp.name)
        for emp in PLAYER_EMPIRES
        if empire_active(game, emp)
        and emp != player
        and tradeable_technologies(game, player, emp)
    ]


def sell_technology(
    game: GameEnvironment, player: Empire, other: Empire, technology: T
) -> str:
    """Transfer one technology. Port of ``SellTechnology``.

    **Nothing is asked in return.** The command is called "sell" and the menu
    says "Trade technology", but no payment, cargo or promise changes hands --
    it is a gift, and the only thing the player gets is whatever goodwill the
    `NSellTech` headline buys.

    The recipient's *level* is unchanged; only their technology set grows.
    """
    tech, tech_set = get_empire_technology(game, other)
    set_empire_technology(game, other, tech, tech_set | {technology})

    add_news(
        game,
        other,
        NewsTypes.NSellTech,
        Location(XY=limbo(), ID=empty_quadrant()),
        int(player),
        int(technology),
    )
    return (
        f"Transfer of {TechnologyName[technology]} technology to "
        f"{empire_name(game, other)} completed."
    )


# --- Messages ----------------------------------------------------------------


def message_recipients(game: GameEnvironment) -> list[tuple[Empire, str]]:
    """Who a message may be addressed to. Port of ``GetEmpires``.

    Every active empire **including the sender** -- the original applies no
    filter. Writing to yourself is allowed and is never intercepted, since
    `send_message` skips the eavesdropping sweep for ``Empires = [Emp]``.
    """
    return [
        (emp, empire_name(game, emp) or emp.name)
        for emp in PLAYER_EMPIRES
        if empire_active(game, emp)
    ]


def send_message_command(
    game: GameEnvironment, player: Empire, empires: set[Empire], text: list[str]
) -> str:
    """Send a message. ``SendMessageCommand`` past the composing."""
    send_message(game, player, empires, text)
    return f"Message sent, {my_lord(game, player)}."


def inbox(game: GameEnvironment, player: Empire) -> list[MessageRecord]:
    """The player's messages, newest first. ``ReadMessageCommand``."""
    return get_messages(game, player)


def read_message(
    game: GameEnvironment, player: Empire, message: MessageRecord
) -> None:
    """Mark one read. Goes read outright only once every recipient has."""
    set_message_read(game, player, message)


# --- LAMs --------------------------------------------------------------------


def lam_targets(
    game: GameEnvironment, player: Empire, base_id: IDNumber
) -> list[tuple[IDNumber, str]]:
    """What LAMs from ``base_id`` can reach. Port of ``LaunchLAM``'s GetTarget.

    Everything **known** and not the player's own, within five sectors:
    fleets, then worlds, then starbases, in that order.

    Note the test is ``Known``, not ``Scouted`` -- a fleet you know is there
    but cannot see the composition of is still a legitimate target. The
    original labels such a target by coordinate rather than by name.
    """
    base_xy = get_coord(game, base_id)
    found: list[tuple[IDNumber, str]] = []

    def add(obj: IDNumber) -> None:
        if not known(game, player, obj):
            return
        if distance(base_xy, get_coord(game, obj)) > LAM_RANGE:
            return
        emp = get_status(game, obj)
        name = object_name(game, player, obj, long_format=True)
        found.append((obj, f"{name}  ({empire_name(game, emp) or emp.name})"))

    for index in sorted(
        game.GlobalSets.SetOfActiveFleets - game.GlobalSets.SetOfFleetsOf[player]
    ):
        add(IDNumber(ObjectTypes.Flt, index))

    for index in range(1, game.NoOfPlanets + 1):
        obj = IDNumber(ObjectTypes.Pln, index)
        if get_status(game, obj) != player:
            add(obj)

    for index in sorted(game.GlobalSets.SetOfActiveStarbases):
        obj = IDNumber(ObjectTypes.Base, index)
        if get_status(game, obj) != player:
            add(obj)

    return found


@dataclass(slots=True)
class LAMResult:
    """What a missile strike destroyed."""

    ships: dict[T, int] = field(default_factory=dict)
    defenses: dict[T, int] = field(default_factory=dict)

    @property
    def hit_anything(self) -> bool:
        return bool(self.ships or self.defenses)


def launch_lam(
    game: GameEnvironment,
    player: Empire,
    base_id: IDNumber,
    target: IDNumber,
    count: int,
) -> LAMResult:
    """Fire ``count`` LAMs from a base. Port of ``LaunchLAM``.

    The missiles are spent whether or not they hit: the base's stock is
    reduced by the number launched, not by the number that told.
    """
    stock = get_defns(game, base_id)
    count = max(0, min(count, stock[T.LAM]))
    if count == 0:
        return LAMResult()

    ships, defenses = lam_attack(game, player, count, target)

    stock[T.LAM] -= count
    put_defns(game, base_id, stock)

    return LAMResult(
        ships={k: v for k, v in ships.items() if v},
        defenses={k: v for k, v in defenses.items() if v},
    )


__all__ = [
    "ISSP_INDUSTRIES",
    "LAM_RANGE",
    "ClassN",
    "LAMResult",
    "designate_command",
    "designation_options",
    "designation_warnings",
    "grant_independence_command",
    "inbox",
    "independence_recipients",
    "issp_settings",
    "lam_targets",
    "launch_lam",
    "message_recipients",
    "read_message",
    "sell_technology",
    "send_message_command",
    "set_issp_settings",
    "technology_recipients",
    "terraform_command",
    "terraform_options",
    "tradeable_technologies",
]
