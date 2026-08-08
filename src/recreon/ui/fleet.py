"""Fleet commands.

The Textual half of FLTCOMM.PAS, and the last of Phase 4's outstanding UI
(§4.3). What the commands do is :mod:`recreon.fltcomm`; this lists the
player's fleets, hangs the nine commands off them, and draws the distribution
grid that launch and transfer share.

Reached from the map with ``f``. The original hangs these off the Fleet
pull-down, which is MENU.PAS and still to come.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static, TextArea

from ..datacnst import ThingNames
from ..environ import GameEnvironment
from ..fltcomm import (
    OrderCompileError,
    abort_fleet_command,
    abort_warnings,
    change_destination_command,
    distribution_error,
    fleet_cancel_orders_command,
    fleet_order_source,
    fleet_orders_command,
    ground_candidates,
    launch_fleet_command,
    masked_amounts,
    max_trillum_to_use,
    mine_sweeper_command,
    player_fleets,
    refuel_fleet_command,
    report_transfer_to_other_empire,
    transfer_fleet_command,
    trillum_to_use,
)
from ..galaxy import XYCoord
from ..misc import fleet_cargo_space
from ..playturn import Command, ParameterSession, trap_command_errors
from ..primintr import (
    absolute_x,
    absolute_y,
    get_cargo,
    get_fleet_fuel,
    get_ships,
    get_status,
    object_name,
)
from ..types import (
    CARGO_TYPES,
    SHIP_TYPES,
    Empire,
    IDNumber,
    TechnologyTypes,
    cargo_array,
    ship_array,
)
from .prologue import Attention, ChooseFrom, TextPrompt

T = TechnologyTypes

#: Everything the distribution grid can move, in the original's row order:
#: ships first, then cargo.
TRANSFERABLE = tuple(SHIP_TYPES) + tuple(CARGO_TYPES)


class DistributionScreen(Screen[dict | None]):
    """Split ships and cargo between a fleet and something else.

    Port of ``InputNewDistribution``, which serves both Launch (where the
    "fleet" side starts empty) and Transfer. Dismisses with the new split, or
    None if the player backed out.

    Two of the original's rules are the interesting ones. **Another empire's
    holdings read ``????``** -- you can move things across but not count what
    is there. And **the grid refuses to close while the fleet is overloaded**:
    cargo needs transports to lift it, so a fleet can be loaded past its
    capacity and has to be fixed before leaving.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "accept", "Accept"),
    ]

    CSS = """
    DistributionScreen { layout: vertical; }
    #heading { height: auto; padding: 1 2; text-style: bold; }
    #rows { height: 1fr; padding: 0 2; }
    #note { height: auto; padding: 0 2; color: $warning; }
    """

    def __init__(
        self,
        game: GameEnvironment,
        player: Empire,
        title: str,
        ground: IDNumber,
        fleet_ships: dict[T, int],
        fleet_cargo: dict[T, int],
        ground_ships: dict[T, int],
        ground_cargo: dict[T, int],
    ) -> None:
        super().__init__()
        self.game = game
        self.player = player
        self.heading = title
        self.ground = ground
        self.ground_status = get_status(game, ground)
        self.fleet_ships = dict(fleet_ships)
        self.fleet_cargo = dict(fleet_cargo)
        self.ground_ships = dict(ground_ships)
        self.ground_cargo = dict(ground_cargo)
        self.note = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self.heading, id="heading")
        yield VerticalScroll(id="rows")
        yield Static(id="note")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        self._rebuild()

    def _side(self, thing: T) -> tuple[dict, dict]:
        """Which pair of dicts holds ``thing`` -- ships or cargo."""
        if thing in SHIP_TYPES:
            return self.fleet_ships, self.ground_ships
        return self.fleet_cargo, self.ground_cargo

    def _rebuild(self) -> None:
        rows = self.query_one("#rows", VerticalScroll)
        rows.remove_children()

        masked_ships = masked_amounts(
            self.ground_ships, self.ground_status, self.player
        )
        masked_cargo = masked_amounts(
            self.ground_cargo, self.ground_status, self.player
        )

        items = []
        for thing in TRANSFERABLE:
            fleet, _ = self._side(thing)
            shown = (masked_ships if thing in SHIP_TYPES else masked_cargo)[thing]
            items.append(
                ListItem(
                    Label(
                        f"{ThingNames[thing][:22]:<24}"
                        f"fleet {fleet[thing]:>6}    there {shown:>6}"
                    ),
                    name=str(int(thing)),
                )
            )

        space = fleet_cargo_space(self.fleet_ships, self.fleet_cargo)
        rows.mount(
            Static(f"Cargo space in the fleet: {space}"),
            ListView(*items),
        )
        self.query_one("#note", Static).update(self.note)
        self.set_focus(rows.query_one(ListView))

    @on(ListView.Selected)
    def _selected(self, event: ListView.Selected) -> None:
        thing = T(int(event.item.name))
        fleet, ground = self._side(thing)

        def entered(text: str | None) -> None:
            if text is None:
                return
            try:
                wanted = int(text)
            except ValueError:
                return

            total = fleet[thing] + ground[thing]
            wanted = max(0, min(wanted, total))
            ground[thing] = total - wanted
            fleet[thing] = wanted
            self.note = ""
            self._rebuild()

        self.app.push_screen(
            TextPrompt(
                f"How many {ThingNames[thing]} in the fleet?",
                str(fleet[thing]),
                detail=f"{fleet[thing] + ground[thing]} available between the two.",
            ),
            entered,
        )

    def action_accept(self) -> None:
        problem = distribution_error(
            self.ground,
            self.ground_status,
            self.player,
            self.fleet_ships,
            self.fleet_cargo,
            self.ground_ships,
            self.ground_cargo,
        )
        if problem is not None:
            self.note = problem
            self._rebuild()
            return

        self.dismiss(
            {
                "fleet_ships": self.fleet_ships,
                "fleet_cargo": self.fleet_cargo,
                "ground_ships": self.ground_ships,
                "ground_cargo": self.ground_cargo,
            }
        )

    def action_cancel(self) -> None:
        self.dismiss(None)


class OrdersScreen(Screen[list[str] | None]):
    """The fleet order editor. Port of ``FleetOrdersCommand``'s edit loop."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "accept", "Compile"),
    ]

    CSS = """
    OrdersScreen { layout: vertical; }
    #heading { height: auto; padding: 1 2; text-style: bold; }
    TextArea { height: 1fr; margin: 0 2; }
    #note { height: auto; padding: 0 2; color: $warning; }
    """

    def __init__(self, name: str, source: list[str]) -> None:
        super().__init__()
        self.heading = f"Orders for {name}"
        self.source = source

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(self.heading, id="heading")
        yield TextArea("\n".join(self.source))
        yield Static("Ctrl+S: compile   Esc: cancel", id="note")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        self.query_one(TextArea).focus()

    def action_accept(self) -> None:
        text = self.query_one(TextArea).text
        self.dismiss([line for line in text.splitlines()])

    def action_cancel(self) -> None:
        self.dismiss(None)


class FleetScreen(Screen[None]):
    """The player's fleets, with the nine commands on them."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("l", "deploy", "Deploy"),
        Binding("d", "destination", "Destination"),
        Binding("t", "transfer", "Transfer"),
        Binding("a", "abort", "Abort/join"),
        Binding("r", "refuel", "Refuel"),
        Binding("s", "sweep", "SRM sweep"),
        Binding("o", "orders", "Orders"),
        Binding("c", "cancel_orders", "Cancel orders"),
        Binding("p", "probe", "Probe"),
    ]

    CSS = """
    FleetScreen { layout: vertical; }
    #heading { height: auto; padding: 1 2; text-style: bold; }
    #list { height: 1fr; padding: 0 2; }
    """

    def __init__(self, game: GameEnvironment, player: Empire) -> None:
        super().__init__()
        self.game = game
        self.player = player

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Fleets:", id="heading")
        yield VerticalScroll(id="list")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        self._rebuild()

    def _rebuild(self) -> None:
        listing = self.query_one("#list", VerticalScroll)
        listing.remove_children()

        self.fleets = player_fleets(self.game, self.player)
        if not self.fleets:
            listing.mount(Static("You have no fleets deployed."))
            return

        rows = []
        for i, (flt, name) in enumerate(self.fleets):
            ships = get_ships(self.game, flt)
            total = sum(ships.values())
            fleet = self.game.Universe.Fleet[flt.Index]
            rows.append(
                ListItem(
                    Label(
                        f"{name[:18]:<20}{total:>6} ships   "
                        f"at {fleet.XY.x},{fleet.XY.y}  "
                        f"-> {fleet.Dest.x},{fleet.Dest.y}   "
                        f"fuel {int(get_fleet_fuel(self.game, flt))}"
                    ),
                    name=str(i),
                )
            )

        listing.mount(ListView(*rows))
        self.set_focus(listing.query_one(ListView))

    @property
    def selected(self) -> IDNumber | None:
        if not self.fleets:
            return None
        try:
            listing = self.query_one("#list", VerticalScroll).query_one(ListView)
        except Exception:
            return None
        return self.fleets[listing.index or 0][0]

    def action_close(self) -> None:
        self.dismiss(None)

    def _report(self, message: str) -> None:
        if message:
            self.app.push_screen(Attention(message))
        self._rebuild()

    # --- Commands -------------------------------------------------------------

    def action_deploy(self) -> None:
        """Deploy a new fleet -- the one command here that starts without one.

        This is the only screen in the port driven by PLAYTURN.PAS's parameter
        table rather than by parameters the screen picks for itself, and
        deliberately so: ``FLaunchCom`` is the table's richest row -- three
        parameters, the only ``IDParm2`` in the game -- and driving it from
        :class:`~recreon.playturn.ParameterSession` is what makes the table
        load-bearing instead of decorative. The player sees the original's own
        questions, in its order, with its error messages.
        """
        refusal = trap_command_errors(self.game, self.player, Command.FLaunchCom)
        if refusal:
            self.app.push_screen(Attention(refusal))
            return

        session = ParameterSession(self.game, self.player, Command.FLaunchCom)

        def ask(detail: str = "") -> None:
            def answered(text: str | None) -> None:
                # Escape gives None and an empty field gives ""; the original
                # makes no distinction -- `InputParameter` maps Escape to '' --
                # and either abandons the command.
                session.answer(text or "")
                if session.cancelled:
                    return
                if session.message:
                    ask(session.message)
                elif session.done:
                    self._distribute(session.result)
                else:
                    ask()

            self.app.push_screen(
                TextPrompt(session.question(), detail=detail), answered
            )

        ask()

    def _distribute(self, result) -> None:
        """The distribution grid, with the fleet side empty. ``FillChar(FltSh,0)``."""
        launch_pt = result.Obj2
        ground_name = object_name(self.game, self.player, launch_pt, True)

        def split(split_result) -> None:
            if split_result is None:
                return
            self._report(
                launch_fleet_command(
                    self.game,
                    self.player,
                    result.NewName,
                    launch_pt,
                    split_result["fleet_ships"],
                    split_result["fleet_cargo"],
                    result.Coord,
                )[1]
            )

        self.app.push_screen(
            DistributionScreen(
                self.game,
                self.player,
                f"{result.NewName} ready to be deployed from {ground_name}.",
                launch_pt,
                ship_array(),
                cargo_array(),
                get_ships(self.game, launch_pt),
                get_cargo(self.game, launch_pt),
            ),
            split,
        )

    def action_destination(self) -> None:
        flt = self.selected
        if flt is None:
            return

        def entered(text: str | None) -> None:
            if not text:
                return
            xy = self._interpret_xy(text)
            if xy is None:
                self.app.push_screen(Attention("Please give a coordinate as x,y."))
                return
            self._report(change_destination_command(self.game, self.player, flt, xy))

        self.app.push_screen(
            TextPrompt(
                "Where shall the fleet go?",
                detail="Coordinates are relative to your capital.",
            ),
            entered,
        )

    def action_transfer(self) -> None:
        flt = self.selected
        if flt is None:
            return

        targets = ground_candidates(self.game, self.player, flt, False, False)
        if not targets:
            self.app.push_screen(
                Attention("There is nothing here to transfer with.")
            )
            return

        def chosen(ground) -> None:
            if ground is None:
                return
            before = dict(get_cargo(self.game, ground))
            before.update(get_ships(self.game, ground))

            def split(result) -> None:
                if result is None:
                    return
                ground_status = get_status(self.game, ground)
                message = transfer_fleet_command(
                    self.game,
                    self.player,
                    flt,
                    ground,
                    result["fleet_ships"],
                    result["fleet_cargo"],
                    result["ground_ships"],
                    result["ground_cargo"],
                )
                moved = {
                    thing: before.get(thing, 0)
                    - (
                        result["ground_ships"]
                        if thing in SHIP_TYPES
                        else result["ground_cargo"]
                    )[thing]
                    for thing in TRANSFERABLE
                }
                report_transfer_to_other_empire(
                    self.game, self.player, ground, ground_status, moved
                )
                self._report(message)

            self.app.push_screen(
                DistributionScreen(
                    self.game,
                    self.player,
                    f"{object_name(self.game, self.player, flt)} ready for transfer",
                    ground,
                    get_ships(self.game, flt),
                    get_cargo(self.game, flt),
                    get_ships(self.game, ground),
                    get_cargo(self.game, ground),
                ),
                split,
            )

        self.app.push_screen(
            ChooseFrom("What shall I use as the target of the transfer?", targets),
            chosen,
        )

    def action_abort(self) -> None:
        flt = self.selected
        if flt is None:
            return

        targets = ground_candidates(self.game, self.player, flt, False, False)
        if not targets:
            self.app.push_screen(Attention("There is nothing here to join with."))
            return

        def chosen(ground) -> None:
            if ground is None:
                return
            warnings = abort_warnings(self.game, self.player, flt, ground)

            def confirmed(yes: bool) -> None:
                if not yes:
                    return
                self._report(
                    abort_fleet_command(self.game, self.player, flt, ground)
                )

            if warnings:
                self.app.push_screen(
                    Attention(
                        warnings[0],
                        "\n".join(warnings[1:] + ["Abort the fleet anyway?"]),
                        confirm=True,
                    ),
                    confirmed,
                )
            else:
                confirmed(True)

        self.app.push_screen(
            ChooseFrom("What do you wish to join the fleet with?", targets), chosen
        )

    def action_refuel(self) -> None:
        flt = self.selected
        if flt is None:
            return

        targets = ground_candidates(self.game, self.player, flt, True, True)
        if not targets:
            self.app.push_screen(Attention("There is nowhere here to refuel from."))
            return

        def chosen(ground) -> None:
            if ground is None:
                return
            maximum = max_trillum_to_use(self.game, flt, ground)

            def entered(text: str | None) -> None:
                if text is None:
                    return
                try:
                    tons = trillum_to_use(int(text or 0), maximum)
                except ValueError as exc:
                    self.app.push_screen(Attention(str(exc)))
                    return
                refuel_fleet_command(self.game, self.player, flt, ground, tons)
                self._report(f"Refuelled with {tons} tons of trillum.")

            self.app.push_screen(
                TextPrompt(
                    f"Tons of trillum (max: {maximum}):",
                    "0",
                    detail="Zero takes the maximum.",
                ),
                entered,
            )

        self.app.push_screen(
            ChooseFrom("Where shall I refuel from?", targets), chosen
        )

    def action_sweep(self) -> None:
        flt = self.selected
        if flt is None:
            return
        self._report(mine_sweeper_command(self.game, self.player, flt))

    def action_orders(self) -> None:
        flt = self.selected
        if flt is None:
            return

        name = object_name(self.game, self.player, flt, long_format=True)

        def edited(source: list[str] | None) -> None:
            if source is None:
                return
            try:
                message = fleet_orders_command(self.game, self.player, flt, source)
            except OrderCompileError as exc:
                self.app.push_screen(Attention(str(exc)))
                return
            self._report(message)

        self.app.push_screen(
            OrdersScreen(name, fleet_order_source(self.game, self.player, flt)),
            edited,
        )

    def action_cancel_orders(self) -> None:
        flt = self.selected
        if flt is None:
            return
        self._report(fleet_cancel_orders_command(self.game, self.player, flt))

    def action_probe(self) -> None:
        from ..fltcomm import launch_probe_command

        def entered(text: str | None) -> None:
            if not text:
                return
            xy = self._interpret_xy(text)
            if xy is None:
                self.app.push_screen(Attention("Please give a coordinate as x,y."))
                return
            self._report(launch_probe_command(self.game, self.player, xy))

        self.app.push_screen(
            TextPrompt(
                "Where shall the probe go?",
                detail="Coordinates are relative to your capital.",
            ),
            entered,
        )

    def _interpret_xy(self, text: str) -> XYCoord | None:
        parts = text.replace(" ", "").split(",")
        if len(parts) != 2:
            return None
        try:
            rel_x, rel_y = int(parts[0]), int(parts[1])
        except ValueError:
            return None

        xy = XYCoord(absolute_x(self.game, rel_x), absolute_y(self.game, rel_y))
        return xy if self.game.Galaxy.in_galaxy(xy.x, xy.y) else None
