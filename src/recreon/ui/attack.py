"""The attack command.

The Textual half of ATTCOMM.PAS's auto-attack: pick a target in the fleet's
sector, confirm, and let `attnpe.npe_attack` resolve it. What it does is
:mod:`recreon.attcomm`.

The round-by-round interactive attack -- where the player moves groups between
orbital shells and retargets them each round -- is the larger half of
ATTCOMM.PAS and is not ported. The Ministry of War menu says so.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ..attcomm import attack_targets, auto_attack_command
from ..datacnst import ThingNames
from ..environ import GameEnvironment
from ..fltcomm import player_fleets
from ..primintr import my_lord, object_name
from ..types import Empire, IDNumber
from .prologue import Attention, ChooseFrom


class AutoAttackScreen(Screen[None]):
    """Choose a fleet, choose a target, confirm, resolve."""

    BINDINGS = [Binding("escape", "close", "Close")]

    CSS = """
    AutoAttackScreen { layout: vertical; }
    #heading { height: auto; padding: 1 2; text-style: bold; }
    #body { height: 1fr; padding: 0 2; }
    """

    def __init__(self, game: GameEnvironment, player: Empire) -> None:
        super().__init__()
        self.game = game
        self.player = player

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Auto Attack:", id="heading")
        yield VerticalScroll(id="body")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        fleets = player_fleets(self.game, self.player)

        if not fleets:
            self._say("You have no fleets deployed.")
            return

        self.app.push_screen(
            ChooseFrom("Which fleet shall attack?", fleets), self._fleet_chosen
        )

    def _say(self, *lines: str) -> None:
        self.query_one("#body", VerticalScroll).mount(Static("\n".join(lines)))

    def action_close(self) -> None:
        self.dismiss(None)

    # --- The flow -------------------------------------------------------------

    def _fleet_chosen(self, flt: IDNumber | None) -> None:
        if flt is None:
            self.dismiss(None)
            return

        targets = attack_targets(self.game, self.player, flt)
        if not targets:
            self.dismiss(None)
            self.app.push_screen(
                Attention(
                    f"There is nothing here to attack, {my_lord(self.game, self.player)}."
                )
            )
            return

        fleet_name = object_name(self.game, self.player, flt, long_format=True)

        def target_chosen(target: IDNumber | None) -> None:
            if target is None:
                self.dismiss(None)
                return

            target_name = object_name(
                self.game, self.player, target, long_format=True
            )

            def confirmed(yes: bool) -> None:
                if not yes:
                    self.dismiss(None)
                    return
                self._resolve(flt, target)

            self.app.push_screen(
                Attention(
                    f"{fleet_name} ready to attack {target_name}.",
                    "Give confirmation order?",
                    confirm=True,
                ),
                confirmed,
            )

        self.app.push_screen(
            ChooseFrom(
                f"{fleet_name} awaiting targetting instructions, "
                f"{my_lord(self.game, self.player)}.",
                targets,
            ),
            target_chosen,
        )

    def _resolve(self, flt: IDNumber, target: IDNumber) -> None:
        outcome = auto_attack_command(self.game, self.player, flt, target)

        self._say(*outcome.lines)
        if outcome.casualties:
            self._say(
                "",
                "Casualties:",
                *[
                    f"  {ThingNames[ship]:<24}{lost}"
                    for ship, lost in outcome.casualties.items()
                ],
            )
        if outcome.spoils:
            self._say("", f"Worlds taken: {len(outcome.spoils)}")
