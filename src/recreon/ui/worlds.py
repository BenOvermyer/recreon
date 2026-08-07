"""World and empire command screens.

The Textual half of DESIGN.PAS's commands. What they do is
:mod:`recreon.designcom`; this collects the choices.

Reached from the Worlds and Empire menus, and from Ministry of War for LAMs.
All of them act on whatever the map cursor is over, except the two message
commands and technology trading, which are empire-wide.
"""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static, TextArea

from ..datacnst import ThingNames, TypeName
from ..designcom import (
    ClassN,
    designate_command,
    designation_options,
    designation_warnings,
    grant_independence_command,
    inbox,
    independence_recipients,
    issp_settings,
    lam_targets,
    launch_lam,
    message_recipients,
    read_message,
    sell_technology,
    send_message_command,
    set_issp_settings,
    technology_recipients,
    terraform_command,
    terraform_options,
    tradeable_technologies,
)
from ..datacnst import TechnologyName
from ..environ import GameEnvironment
from ..primintr import empire_name, get_defns, my_lord, object_name
from ..types import Empire, IDNumber, IndusTypes, ObjectTypes, TechnologyTypes
from .prologue import Attention, ChooseFrom, TextPrompt

T = TechnologyTypes


def _confirm(app, message: str, detail: str, then) -> None:
    """Ask, and run ``then`` on yes. The shape every command here shares."""
    def answered(yes: bool) -> None:
        if yes:
            then()

    app.push_screen(Attention(message, detail, confirm=True), answered)


class DesignateScreen(Screen[None]):
    """Redesignate a world. Port of ``DesignateCommand``.

    Its five warnings are advice, never refusals -- the original asks and
    proceeds, so a player may make any of them deliberately.
    """

    BINDINGS = [Binding("escape", "close", "Close")]

    def __init__(self, game: GameEnvironment, player: Empire, world: IDNumber) -> None:
        super().__init__()
        self.game = game
        self.player = player
        self.world = world

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Designate:", id="heading")
        yield VerticalScroll(id="body")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        options = designation_options(self.game, self.world)
        if not options:
            self._done("There is nothing this world can be designated as.")
            return

        name = object_name(self.game, self.player, self.world, long_format=True)
        from ..primintr import get_type

        self.query_one("#body", VerticalScroll).mount(
            Static(
                f"{my_lord(self.game, self.player)}, {name} is currently "
                f"{TypeName[get_type(self.game, self.world)]}."
            )
        )
        self.app.push_screen(
            ChooseFrom(
                "What shall its new designation be?",
                [(typ, f"{label:<30}{industry}") for typ, label, industry in options],
            ),
            self._chosen,
        )

    def action_close(self) -> None:
        self.dismiss(None)

    def _done(self, *lines: str) -> None:
        self.query_one("#body", VerticalScroll).mount(Static("\n".join(lines)))

    def _chosen(self, new_type) -> None:
        if new_type is None:
            self.dismiss(None)
            return

        def apply() -> None:
            self._done(*designate_command(self.game, self.player, self.world, new_type))

        warnings = designation_warnings(
            self.game, self.player, self.world, new_type
        )
        if warnings:
            _confirm(self.app, warnings[0], "\n".join(warnings[1:]), apply)
        else:
            apply()


class TerraformScreen(Screen[None]):
    """Begin terraforming. Port of ``TerraformCommand``."""

    BINDINGS = [Binding("escape", "close", "Close")]

    def __init__(self, game: GameEnvironment, player: Empire, world: IDNumber) -> None:
        super().__init__()
        self.game = game
        self.player = player
        self.world = world

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Terraform:", id="heading")
        yield VerticalScroll(id="body")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        options = terraform_options(self.game, self.world)
        if not options:
            self.query_one("#body", VerticalScroll).mount(
                Static("This world cannot be terraformed.")
            )
            return

        self.app.push_screen(
            ChooseFrom("What shall this world become?", options), self._chosen
        )

    def action_close(self) -> None:
        self.dismiss(None)

    def _chosen(self, new_class) -> None:
        if new_class is None:
            self.dismiss(None)
            return

        def apply() -> None:
            lines = terraform_command(
                self.game, self.player, self.world, new_class
            )
            self.query_one("#body", VerticalScroll).mount(
                Static("\n".join(lines) or "Nothing to do.")
            )

        _confirm(
            self.app,
            f"Terraform towards {ClassN[new_class]}?",
            "Terraforming takes years and can fail.",
            apply,
        )


class ISSPScreen(Screen[None]):
    """The four import/export settings. Port of ``ChangeISSPCom``."""

    BINDINGS = [Binding("escape", "close", "Close")]

    CSS = """
    ISSPScreen { layout: vertical; }
    #heading { height: auto; padding: 1 2; text-style: bold; }
    #body { height: 1fr; padding: 0 2; }
    """

    def __init__(self, game: GameEnvironment, player: Empire, world: IDNumber) -> None:
        super().__init__()
        self.game = game
        self.player = player
        self.world = world

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Industrial Self-Sufficiency:", id="heading")
        yield VerticalScroll(id="body")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        self.settings = issp_settings(self.game, self.world)
        self._rebuild()

    def _rebuild(self) -> None:
        from ..datacnst import ISSP, IndusNames

        body = self.query_one("#body", VerticalScroll)
        body.remove_children()
        body.mount(
            Static("0 exports everything, 10 keeps everything."),
            ListView(
                *[
                    ListItem(
                        Label(
                            f"{IndusNames[ind]:<20}{level:>3}   "
                            f"({ISSP[level]:.0%} kept)"
                        ),
                        name=str(int(ind)),
                    )
                    for ind, level in self.settings.items()
                ]
            ),
        )
        self.set_focus(body.query_one(ListView))

    def action_close(self) -> None:
        set_issp_settings(self.game, self.world, self.settings)
        self.dismiss(None)

    @on(ListView.Selected)
    def _selected(self, event: ListView.Selected) -> None:
        from ..datacnst import MAX_ISSP

        ind = IndusTypes(int(event.item.name))

        def entered(text: str | None) -> None:
            if text is None:
                return
            try:
                value = int(text)
            except ValueError:
                return
            self.settings[ind] = max(0, min(value, MAX_ISSP))
            self._rebuild()

        self.app.push_screen(
            TextPrompt(f"New setting (0-{MAX_ISSP}):", str(self.settings[ind])),
            entered,
        )


class LiberateScreen(Screen[None]):
    """Hand a world away. Port of ``GrantIndependenceCommand``."""

    BINDINGS = [Binding("escape", "close", "Close")]

    def __init__(self, game: GameEnvironment, player: Empire, world: IDNumber) -> None:
        super().__init__()
        self.game = game
        self.player = player
        self.world = world

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Liberate:", id="heading")
        yield VerticalScroll(id="body")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        self.app.push_screen(
            ChooseFrom(
                "Which empire do you wish to give this world to?",
                independence_recipients(self.game, self.player, self.world),
            ),
            self._chosen,
        )

    def action_close(self) -> None:
        self.dismiss(None)

    def _chosen(self, emp) -> None:
        if emp is None:
            self.dismiss(None)
            return

        name = object_name(self.game, self.player, self.world, long_format=True)
        question = (
            f"Do you really want to grant independence to {name}?"
            if emp == Empire.Indep
            else f"Do you really want to give {name} to "
            f"{empire_name(self.game, emp)}?"
        )

        def apply() -> None:
            message = grant_independence_command(
                self.game, self.player, self.world, emp
            )
            self.query_one("#body", VerticalScroll).mount(Static(message))

        _confirm(self.app, question, "This cannot be undone.", apply)


class TradeTechnologyScreen(Screen[None]):
    """Give a technology away. Port of ``SellTechnology``.

    Nothing is asked in return -- the command's name and the menu's "Trade"
    both overstate it.
    """

    BINDINGS = [Binding("escape", "close", "Close")]

    def __init__(self, game: GameEnvironment, player: Empire) -> None:
        super().__init__()
        self.game = game
        self.player = player

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Trade Technology:", id="heading")
        yield VerticalScroll(id="body")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        recipients = technology_recipients(self.game, self.player)
        if not recipients:
            self.query_one("#body", VerticalScroll).mount(
                Static(
                    f"Unfortunately, {my_lord(self.game, self.player)}, you have "
                    "nothing that others would want."
                )
            )
            return

        self.app.push_screen(
            ChooseFrom(
                "Which empire do you wish to transfer technology to?", recipients
            ),
            self._empire_chosen,
        )

    def action_close(self) -> None:
        self.dismiss(None)

    def _empire_chosen(self, emp) -> None:
        if emp is None:
            self.dismiss(None)
            return

        offered = sorted(
            tradeable_technologies(self.game, self.player, emp), key=int
        )

        def chosen(tech) -> None:
            if tech is None:
                self.dismiss(None)
                return
            message = sell_technology(self.game, self.player, emp, tech)
            self.query_one("#body", VerticalScroll).mount(Static(message))

        self.app.push_screen(
            ChooseFrom(
                "Which technology do you wish to transfer?",
                [
                    (tech, f"{TechnologyName[tech].capitalize()} technology")
                    for tech in offered
                ],
            ),
            chosen,
        )


class SendMessageScreen(Screen[None]):
    """Compose and send. Port of ``SendMessageCommand``."""

    BINDINGS = [
        Binding("escape", "close", "Cancel"),
        Binding("ctrl+s", "send", "Send"),
    ]

    CSS = """
    SendMessageScreen { layout: vertical; }
    #heading { height: auto; padding: 1 2; text-style: bold; }
    TextArea { height: 1fr; margin: 0 2; }
    #hint { height: auto; padding: 0 2; color: $text-muted; }
    """

    def __init__(self, game: GameEnvironment, player: Empire) -> None:
        super().__init__()
        self.game = game
        self.player = player
        self.to: set[Empire] = set()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Send message:", id="heading")
        yield TextArea()
        yield Static("Ctrl+S: send   Esc: cancel", id="hint")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        self.app.push_screen(
            ChooseFrom("Who shall receive it?", message_recipients(self.game)),
            self._chosen,
        )

    def _chosen(self, emp) -> None:
        if emp is None:
            self.dismiss(None)
            return
        self.to = {emp}
        self.query_one("#heading", Static).update(
            f"Send message to {empire_name(self.game, emp) or emp.name}:"
        )
        self.query_one(TextArea).focus()

    def action_close(self) -> None:
        self.dismiss(None)

    def action_send(self) -> None:
        if not self.to:
            return
        text = self.query_one(TextArea).text.splitlines() or [""]
        message = send_message_command(self.game, self.player, self.to, text)
        self.dismiss(None)
        self.app.push_screen(Attention(message))


class ReadMessagesScreen(Screen[None]):
    """The inbox. Port of ``ReadMessageCommand``."""

    BINDINGS = [Binding("escape", "close", "Close")]

    CSS = """
    ReadMessagesScreen { layout: vertical; }
    #heading { height: auto; padding: 1 2; text-style: bold; }
    #body { height: 1fr; padding: 0 2; }
    """

    def __init__(self, game: GameEnvironment, player: Empire) -> None:
        super().__init__()
        self.game = game
        self.player = player

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Messages:", id="heading")
        yield VerticalScroll(id="body")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        self.messages = inbox(self.game, self.player)
        body = self.query_one("#body", VerticalScroll)

        if not self.messages:
            body.mount(Static("There are no messages."))
            return

        body.mount(
            ListView(
                *[
                    ListItem(
                        Label(
                            f"{'   ' if message.Read else ' * '}"
                            f"from {empire_name(self.game, message.Sender)}"
                            f"{'  (intercepted)' if message.Intercepted else ''}"
                        ),
                        name=str(i),
                    )
                    for i, message in enumerate(self.messages)
                ]
            )
        )
        self.set_focus(body.query_one(ListView))

    def action_close(self) -> None:
        self.dismiss(None)

    @on(ListView.Selected)
    def _selected(self, event: ListView.Selected) -> None:
        message = self.messages[int(event.item.name)]
        read_message(self.game, self.player, message)
        self.app.push_screen(
            Attention(
                f"From {empire_name(self.game, message.Sender)}:",
                "\n".join(message.MesText),
            )
        )


class LaunchLAMScreen(Screen[None]):
    """Fire missiles from a base. Port of ``LaunchLAM``."""

    BINDINGS = [Binding("escape", "close", "Close")]

    def __init__(self, game: GameEnvironment, player: Empire, base: IDNumber) -> None:
        super().__init__()
        self.game = game
        self.player = player
        self.base = base

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Launch LAMs:", id="heading")
        yield VerticalScroll(id="body")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        stock = get_defns(self.game, self.base)[T.LAM]
        if stock <= 0:
            self.query_one("#body", VerticalScroll).mount(
                Static("There are no LAMs here.")
            )
            return

        targets = lam_targets(self.game, self.player, self.base)
        if not targets:
            self.query_one("#body", VerticalScroll).mount(
                Static("There is nothing in range.")
            )
            return

        self.app.push_screen(
            ChooseFrom("Which target?", targets), self._chosen
        )

    def action_close(self) -> None:
        self.dismiss(None)

    def _chosen(self, target) -> None:
        if target is None:
            self.dismiss(None)
            return

        stock = get_defns(self.game, self.base)[T.LAM]
        base_name = object_name(self.game, self.player, self.base, long_format=True)

        def entered(text: str | None) -> None:
            if text is None:
                return
            try:
                count = int(text)
            except ValueError:
                return

            result = launch_lam(self.game, self.player, self.base, target, count)
            body = self.query_one("#body", VerticalScroll)

            if not result.hit_anything:
                body.mount(Static("The missiles did no damage."))
                return

            destroyed = {**result.ships, **result.defenses}
            body.mount(
                Static(
                    "Destroyed:\n"
                    + "\n".join(
                        f"  {ThingNames[thing]:<24}{count}"
                        for thing, count in destroyed.items()
                    )
                )
            )

        self.app.push_screen(
            TextPrompt(
                "Launch how many?",
                str(stock),
                detail=f"There are {stock} LAMs at {base_name}.",
            ),
            entered,
        )
