"""Starting a game: the scenario picker, the introduction, and empire naming.

The Textual half of NEWGAME.PAS's front end -- ``GetScenarios``,
``ScenarioIntroduction``, ``InputEmpireName`` and ``SuggestionsWindow``. What
they *decide* lives in :mod:`recreon.newgame`; this draws it.

The original runs all of this inside its single forward pass over the scenario
file, printing the intro as it reads and prompting between directives. An
event-driven UI cannot answer a question from inside a blocking parse, so the
flow here reads the header and intro first (:func:`~recreon.newgame.read_scenario_intro`),
collects every answer, and then makes the real pass with them in hand. The
galaxy that comes out is the same one -- neither the header nor the intro
draws from the generator.

Four steps, in the original's order:

1. **Pick a scenario.** ``GetScenarios`` scans for `*.SCN` and lists title,
   difficulty, players and duration in fixed columns.
2. **Read the introduction**, a page at a time.
3. **Choose a player count**, but only when the scenario allows a range --
   a fixed scenario just tells you what it is, as ``NoChoice`` does.
4. **Name each empire**, with a suggestion offered and Esc for the full list.
"""

from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, Static

from ..environ import GameEnvironment
from ..newgame import (
    RND_EMPIRE_NAMES,
    EmpireIdentity,
    ScenarioEntry,
    ScenarioError,
    ScenarioFrontEnd,
    ScenarioHeader,
    get_scenarios,
    read_scenario_intro,
    start_new_game,
)
from ..types import PLAYER_EMPIRES, Empire
from ..utils.int_utils import rnd


def suggest_empire_name(taken: set[str]) -> str:
    """A name from the table that nobody has claimed.

    Port of ``GetRandomEmpireName``: rolls ``Rnd(1, 59)`` and rejects a name
    already in use, rather than drawing once from a filtered list. Same
    routine the scenario loader uses for ``RndName`` empires, and the same
    reason for the retry -- a filtered draw would call ``Rnd`` with a
    different bound and shift every draw after it.
    """
    while True:
        name = RND_EMPIRE_NAMES[rnd(1, len(RND_EMPIRE_NAMES)) - 1]
        if name not in taken:
            return name


class SuggestionsScreen(Screen[str | None]):
    """The whole name table, to pick from. Port of ``SuggestionsWindow``.

    Reached with Esc from the name prompt, exactly as the original's help line
    advertises, and dismissing with Esc returns nothing so the prompt keeps
    whatever was typed.
    """

    BINDINGS = [Binding("escape", "cancel", "Back")]

    CSS = """
    SuggestionsScreen { align: center middle; }
    #box { width: 40; height: 24; border: solid $accent; background: $surface; }
    #box > Label { padding: 0 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Label("Suggestions")
            yield ListView(
                *[ListItem(Label(name), name=name) for name in RND_EMPIRE_NAMES]
            )
        yield Footer()

    @on(ListView.Selected)
    def _chosen(self, event: ListView.Selected) -> None:
        self.dismiss(event.item.name)

    def action_cancel(self) -> None:
        self.dismiss(None)


class NewGameScreen(Screen[GameEnvironment | None]):
    """Pick a scenario, read it, name the empires, and build the galaxy.

    Dismisses with the new :class:`~recreon.environ.GameEnvironment`, or with
    ``None`` if the player backs out -- which is what ``StartNewGame``'s
    ``Exit`` flag means, and what sends the original back to its prologue menu.
    """

    BINDINGS = [Binding("escape", "back", "Back")]

    CSS = """
    NewGameScreen { layout: vertical; }
    #prompt { height: auto; padding: 1 2; }
    #body { height: 1fr; padding: 0 2; }
    #row { height: auto; padding: 1 2; }
    #row Input { width: 40; }
    #hint { height: auto; padding: 0 2; color: $text-muted; }
    .intro { padding: 0 1; }
    """

    def __init__(self, directory: str | Path) -> None:
        super().__init__()
        self.directory = Path(directory)
        self.entries: list[ScenarioEntry] = []
        self.entry: ScenarioEntry | None = None
        self.header: ScenarioHeader | None = None
        self.pages: list[str] = []
        self.page = 0
        self.count = 1
        self.identities: dict[Empire, EmpireIdentity] = {}
        self.naming: Empire = Empire.Empire1

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="prompt")
        yield VerticalScroll(id="body")
        with Horizontal(id="row"):
            yield Input(placeholder="", id="answer")
            yield Button("OK", variant="primary", id="ok")
        yield Static(id="hint")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        self._show_scenarios()

    # --- Step 1: pick a scenario ---------------------------------------------

    def _show_scenarios(self) -> None:
        self.step = "scenario"
        self.entries = get_scenarios(self.directory)

        self.query_one("#row").display = False
        body = self.query_one("#body", VerticalScroll)
        body.remove_children()

        if not self.entries:
            # AttentionWindow('There are no Anacreon scenario', 'files in "…"')
            self.query_one("#prompt", Static).update(
                f'There are no Anacreon scenario files in "{self.directory}".'
            )
            self.query_one("#hint", Static).update("Esc: back")
            return

        self.query_one("#prompt", Static).update("Please select a scenario:")
        body.mount(
            Static("Name                 Difficulty    Players    Duration"),
            ListView(
                *[
                    ListItem(Label(entry.menu_line()), name=str(i))
                    for i, entry in enumerate(self.entries)
                ]
            ),
        )
        self.query_one("#hint", Static).update("↑↓: move  Enter: select  Esc: exit")
        self.set_focus(body.query_one(ListView))

    @on(ListView.Selected)
    def _scenario_chosen(self, event: ListView.Selected) -> None:
        if self.step != "scenario":
            return
        self.entry = self.entries[int(event.item.name)]
        try:
            self.header, self.pages = read_scenario_intro(self.entry.path)
        except ScenarioError as exc:
            self.query_one("#prompt", Static).update(
                f"{self.entry.path.name} could not be read:\n{exc}"
            )
            return
        self.page = 0
        self._show_page()

    # --- Step 2: the introduction --------------------------------------------

    def _show_page(self) -> None:
        self.step = "intro"
        self.query_one("#row").display = False

        body = self.query_one("#body", VerticalScroll)
        body.remove_children()
        text = self.pages[self.page] if self.pages else ""
        body.mount(Static(text, classes="intro"))

        self.query_one("#prompt", Static).update(
            f"{self.header.title}   (page {self.page + 1} of {max(len(self.pages), 1)})"
        )
        self.query_one("#hint", Static).update(
            "Enter/Space: continue  Esc: back to the scenario list"
        )
        self.set_focus(None)

    def _advance_page(self) -> None:
        if self.page + 1 < len(self.pages):
            self.page += 1
            self._show_page()
        else:
            self._ask_player_count()

    # --- Step 3: how many players --------------------------------------------

    def _ask_player_count(self) -> None:
        header = self.header
        if header.min_players >= header.max_players:
            # NoChoice: the scenario says what it is and waits for a keypress.
            self.count = header.min_players
            self._start_naming()
            return

        self.step = "count"
        body = self.query_one("#body", VerticalScroll)
        body.remove_children()

        self.query_one("#prompt", Static).update(
            f"How many players ({header.min_players}-{header.max_players}) ?"
        )
        self.query_one("#row").display = True
        answer = self.query_one("#answer", Input)
        answer.value = ""
        answer.placeholder = str(header.min_players)
        self.query_one("#hint", Static).update("Esc: back")
        self.set_focus(answer)

    def _accept_player_count(self, raw: str) -> None:
        header = self.header
        try:
            count = int(raw.strip())
        except ValueError:
            self.query_one("#hint", Static).update(
                "Please enter a valid number, or Esc to exit."
            )
            return

        if not header.min_players <= count <= header.max_players:
            self.query_one("#hint", Static).update(
                f"Please enter a number between {header.min_players} "
                f"and {header.max_players}, or Esc to exit."
            )
            return

        self.count = count
        self._start_naming()

    # --- Step 4: name the empires --------------------------------------------

    def _start_naming(self) -> None:
        self.identities = {}
        self.naming = PLAYER_EMPIRES[0]
        self._ask_name()

    def _ask_name(self) -> None:
        self.step = "name"
        index = PLAYER_EMPIRES.index(self.naming)
        self.suggestion = suggest_empire_name(
            {identity.name for identity in self.identities.values()}
        )

        body = self.query_one("#body", VerticalScroll)
        body.remove_children()
        if self.identities:
            body.mount(
                Static(
                    "\n".join(
                        f"  #{PLAYER_EMPIRES.index(emp) + 1}  {identity.name}"
                        for emp, identity in self.identities.items()
                    )
                )
            )

        self.query_one("#prompt", Static).update(
            f"Name of player empire #{index + 1} :"
        )
        self.query_one("#row").display = True
        answer = self.query_one("#answer", Input)
        answer.value = ""
        answer.placeholder = self.suggestion
        self.query_one("#hint", Static).update(
            f'Esc: suggestions   Default: "{self.suggestion}"'
        )
        self.set_focus(answer)

    def _accept_name(self, raw: str) -> None:
        # An empty name takes the suggestion, as the original does; the first
        # letter is capitalised either way.
        name = raw.strip() or self.suggestion
        name = name[:1].upper() + name[1:]

        # Sex is prompted for separately in the original and falls back to
        # Rnd(0,1) on anything that is not m or f. Nothing here asks yet, so
        # it takes that fallback -- and it must draw, because the loader no
        # longer does.
        self.identities[self.naming] = EmpireIdentity(
            name=name, password="", is_empress=bool(rnd(0, 1))
        )

        index = PLAYER_EMPIRES.index(self.naming) + 1
        if index < self.count:
            self.naming = PLAYER_EMPIRES[index]
            self._ask_name()
        else:
            self._build()

    # --- Build ----------------------------------------------------------------

    def _build(self) -> None:
        self.step = "building"
        self.query_one("#row").display = False
        self.query_one("#prompt", Static).update(
            "Please wait while the universe is created..."
        )
        self.query_one("#body", VerticalScroll).remove_children()
        self.query_one("#hint", Static).update("")

        front_end = ScenarioFrontEnd(self.identities)
        try:
            game = start_new_game(self.directory, self.entry, front_end=front_end)
        except ScenarioError as exc:
            self.step = "failed"
            self.query_one("#prompt", Static).update(
                f"{self.entry.path.name} could not be loaded:\n{exc}"
            )
            self.query_one("#hint", Static).update("Esc: back to the scenario list")
            return

        game.SceDirect = str(self.directory)
        self.dismiss(game)

    # --- Input routing --------------------------------------------------------

    @on(Input.Submitted)
    def _submitted(self, event: Input.Submitted) -> None:
        self._answer(event.value)

    @on(Button.Pressed, "#ok")
    def _ok(self) -> None:
        self._answer(self.query_one("#answer", Input).value)

    def _answer(self, value: str) -> None:
        if self.step == "count":
            self._accept_player_count(value)
        elif self.step == "name":
            self._accept_name(value)

    def on_key(self, event) -> None:
        if self.step == "intro" and event.key in ("enter", "space"):
            event.stop()
            self._advance_page()

    def action_back(self) -> None:
        """Esc. What it means depends on where you are, as in the original."""
        if self.step == "name":
            # 'Esc: Suggestions' -- the name prompt's Esc opens the list
            # rather than backing out.
            self.app.push_screen(SuggestionsScreen(), self._suggested)
        elif self.step in ("intro", "count", "failed"):
            self._show_scenarios()
        else:
            self.dismiss(None)

    def _suggested(self, name: str | None) -> None:
        if name:
            self.query_one("#answer", Input).value = name
