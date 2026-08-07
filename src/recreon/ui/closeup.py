"""World close-up and production screens.

The Textual half of CLSCOMM.PAS. What the screens compute is
:mod:`recreon.clscomm`; this lays it out.

Both act on whatever the map cursor is over, which is how the original reaches
them too -- they take an `IDNumber` the map supplies. Reached with ``z``
(close-up) and ``i`` (production).
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ..clscomm import close_up, production_com
from ..datacnst import ClassStr, IndusNames, TechN, ThingNames, TypeName
from ..environ import GameEnvironment
from ..misc import hi_lo
from ..primintr import empire_name
from ..types import CARGO_TYPES, DEFNS_TYPES, SHIP_TYPES, Empire, IDNumber, IndusTypes


def _table(rows: list[tuple[str, object]], width: int = 26) -> str:
    return "\n".join(f"  {label:<{width}}{value}" for label, value in rows)


class CloseUpScreen(Screen[None]):
    """Everything visible about a world or base. Port of ``CloseUpCom``."""

    BINDINGS = [Binding("escape", "close", "Close")]

    CSS = """
    CloseUpScreen { layout: vertical; }
    #heading { height: auto; padding: 1 2; text-style: bold; }
    #body { height: 1fr; padding: 0 2; }
    .section { padding: 1 0 0 0; text-style: bold; }
    """

    def __init__(
        self, game: GameEnvironment, player: Empire, obj: IDNumber
    ) -> None:
        super().__init__()
        self.game = game
        self.player = player
        self.obj = obj

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="heading")
        yield VerticalScroll(id="body")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        self.report = close_up(self.game, self.player, self.obj)
        info = self.report.info

        self.query_one("#heading", Static).update(f"Close-up: {info.name}")
        body = self.query_one("#body", VerticalScroll)

        body.mount(
            Static(
                _table(
                    [
                        ("Class", ClassStr[info.cls]),
                        ("Designation", TypeName[info.typ]),
                        ("Technology", TechN[info.tech]),
                        ("Population", info.pop),
                        ("Efficiency", f"{info.eff}%"),
                        ("Unrest", f"{hi_lo(info.rev)} ({info.rev})"),
                        ("Ambrosia addicted", "yes" if info.amb_addict else "no"),
                    ]
                )
            )
        )

        for title, amounts, kinds in (
            ("Ships", self.report.ships, SHIP_TYPES),
            ("Cargo", self.report.cargo, CARGO_TYPES),
            ("Defenses", self.report.defenses, DEFNS_TYPES),
        ):
            present = [(ThingNames[k], amounts[k]) for k in kinds if amounts[k]]
            if present:
                body.mount(Static(title, classes="section"), Static(_table(present)))

        if self.report.fleets:
            body.mount(
                Static("Fleets in this sector", classes="section"),
                Static(
                    _table(
                        [
                            (name, empire_name(self.game, emp) or emp.name)
                            for _, name, emp in self.report.fleets
                        ]
                    )
                ),
            )

    def action_close(self) -> None:
        self.dismiss(None)


class ProductionScreen(Screen[None]):
    """What the world will make next year. Port of ``ProductionCom``.

    The figures are a *projection*, computed by a second copy of the
    production formula that has drifted from the real one -- issue #62. The
    trillum line in particular ignores an exhausted reserve, so the screen
    carries the reserve figure beside it where the original put it, which is
    the only way a player can tell.
    """

    BINDINGS = [Binding("escape", "close", "Close")]

    CSS = """
    ProductionScreen { layout: vertical; }
    #heading { height: auto; padding: 1 2; text-style: bold; }
    #body { height: 1fr; padding: 0 2; }
    .section { padding: 1 0 0 0; text-style: bold; }
    """

    def __init__(
        self, game: GameEnvironment, player: Empire, obj: IDNumber
    ) -> None:
        super().__init__()
        self.game = game
        self.player = player
        self.obj = obj

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="heading")
        yield VerticalScroll(id="body")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        self.report = production_com(self.game, self.player, self.obj)
        report = self.report
        info = report.info

        self.query_one("#heading", Static).update(f"Production: {info.name}")
        body = self.query_one("#body", VerticalScroll)

        body.mount(
            Static(
                _table(
                    [
                        ("Technology", TechN[info.tech]),
                        ("Population", info.pop),
                        ("Efficiency", f"{info.eff}%"),
                        ("Available industry (TIP)", report.atip),
                        ("Trillum reserves", report.forecast.trillum_reserves),
                    ]
                )
            )
        )

        industry = [
            (
                IndusNames[ind],
                f"{report.industry.actual[ind]:>5}  "
                f"optimum {report.industry.optimum[ind]:>5}",
            )
            for ind in IndusTypes
            if report.industry.actual[ind] or report.industry.optimum[ind]
        ]
        if industry:
            body.mount(
                Static("Industry", classes="section"), Static(_table(industry))
            )

        produced = [
            (ThingNames[k], v)
            for k, v in list(report.forecast.ships.items())
            + list(report.forecast.cargo.items())
            if v
        ]
        if produced:
            body.mount(
                Static("Projected production per year", classes="section"),
                Static(_table(produced)),
            )

        consumed = [
            (ThingNames[k], v) for k, v in report.forecast.consumed.items() if v
        ]
        if consumed:
            body.mount(
                Static("Raw material consumed", classes="section"),
                Static(_table(consumed)),
            )

        defenses = [
            (
                ThingNames[d],
                f"{report.defenses.available[d]:>5}  "
                f"optimum {report.defenses.optimum[d]:>5}  "
                f"per year {report.defenses.buildable[d]:>5}",
            )
            for d in DEFNS_TYPES
            if report.defenses.available[d] or report.defenses.optimum[d]
        ]
        if defenses:
            body.mount(
                Static("Defenses", classes="section"), Static(_table(defenses))
            )

    def action_close(self) -> None:
        self.dismiss(None)
