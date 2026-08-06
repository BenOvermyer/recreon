"""The prologue menu: what you see before and between games.

The Textual half of PROLOG.PAS. What the commands *do* is in
:mod:`recreon.prolog`; this is the menu bar and the little windows it opens.

The original is a pull-down bar (MENU.PAS, PULLDOWN.PAS) over a starfield with
the Anacreon logo zooming in. The starfield and the logo are direct
video-memory work with no Python equivalent; the menu is a list here, keyed by
the same letters the original underlines, so muscle memory carries over.

Four commands are dropped rather than drawn: DOS shell, print map (writes to
``LST:``), mono/colour, and the configuration file. See
:mod:`recreon.prolog` for why.
"""

from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, Static

from ..environ import GameEnvironment
from ..loadsave import SaveFileError
from ..prolog import (
    PrologueError,
    PrologueState,
    add_player_empire,
    change_time_limit,
    continue_old_game,
    delete_player_empire,
    deletable_empires,
    menu_labels,
    needs_saving,
    quit_game,
    save_the_game,
    start_a_new_game,
    toggle_auto_save,
    toggle_pause,
    toggle_turn_sync,
)
from ..newgame import EmpireIdentity


class Attention(ModalScreen[bool]):
    """One message and a way out. Port of ``AttentionWindow``.

    The original's ``Abort`` parameter doubles as input and output: passed
    True it offers a choice and reports which was taken, passed False it is
    only an acknowledgement. Same here -- ``confirm`` picks which.
    """

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    Attention { align: center middle; }
    #box { width: 60; height: auto; border: solid $accent; background: $surface;
           padding: 1 2; }
    #box Button { margin: 1 1 0 0; }
    """

    def __init__(self, message: str, detail: str = "", confirm: bool = False) -> None:
        super().__init__()
        self.message = message
        self.detail = detail
        self.confirm = confirm

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Label(self.message)
            if self.detail:
                yield Label(self.detail)
            with Horizontal():
                if self.confirm:
                    yield Button("Yes", variant="primary", id="yes")
                    yield Button("No", id="no")
                else:
                    yield Button("OK", variant="primary", id="no")

    @on(Button.Pressed, "#yes")
    def _yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def _no(self) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)


class TextPrompt(ModalScreen[str | None]):
    """A one-line prompt with a default, as ``InputString`` offers one."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    TextPrompt { align: center middle; }
    #box { width: 64; height: auto; border: solid $accent; background: $surface;
           padding: 1 2; }
    """

    def __init__(self, prompt: str, value: str = "", detail: str = "") -> None:
        super().__init__()
        self.prompt = prompt
        self.value = value
        self.detail = detail

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            if self.detail:
                yield Label(self.detail)
            yield Label(self.prompt)
            yield Input(value=self.value)

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    @on(Input.Submitted)
    def _submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ChooseFrom(ModalScreen[object | None]):
    """Pick one of a list. ``ChoosePlayer`` and the save-file picker."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    ChooseFrom { align: center middle; }
    #box { width: 56; height: auto; max-height: 20; border: solid $accent;
           background: $surface; padding: 1 2; }
    """

    def __init__(self, prompt: str, options: list[tuple[object, str]]) -> None:
        super().__init__()
        self.prompt = prompt
        self.options = options

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Label(self.prompt)
            yield ListView(
                *[
                    ListItem(Label(label), name=str(i))
                    for i, (_, label) in enumerate(self.options)
                ]
            )

    @on(ListView.Selected)
    def _chosen(self, event: ListView.Selected) -> None:
        self.dismiss(self.options[int(event.item.name)][0])

    def action_cancel(self) -> None:
        self.dismiss(None)


class PrologueScreen(Screen[str | None]):
    """The prologue menu itself.

    Dismisses with ``"begin"`` when the player is ready to take a turn, or
    ``"quit"`` when they are done -- the two ways ``Prologue``'s ``REPEAT``
    loop ends, via its ``Continue`` and ``EndGame`` flags.
    """

    BINDINGS = [Binding("escape", "dismiss_menu", "Close", show=False)]

    CSS = """
    PrologueScreen { layout: vertical; align: center middle; }
    #title { height: auto; padding: 1 2; text-align: center; }
    #menu { width: 52; height: auto; max-height: 22; border: solid $panel;
            padding: 0 1; }
    #status { height: auto; padding: 1 2; color: $text-muted; }
    """

    def __init__(
        self,
        game: GameEnvironment,
        state: PrologueState,
        scenario_dir: Path,
        save_dir: Path,
    ) -> None:
        super().__init__()
        self.game = game
        self.state = state
        self.scenario_dir = scenario_dir
        self.save_dir = save_dir

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("A N A C R E O N\nReconstruction 4021", id="title")
        yield VerticalScroll(id="menu")
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Re:creon"
        self._rebuild()

    # --- The menu -------------------------------------------------------------

    def _commands(self) -> list[tuple[str, str]]:
        """(id, label) per row, in the original's bar order.

        Labels carry the toggles' settings the way ``UpdateMenuBar`` writes
        them into the menu lines.
        """
        labels = menu_labels(self.game)
        return [
            ("begin", "Begin..."),
            ("new", "New game"),
            ("load", "Load game"),
            ("save", "Save game"),
            ("quit", "Quit"),
            ("time", "Time limit"),
            ("add", "New player empire"),
            ("delete", "Delete player empire"),
            ("autosave", f"Auto backup          {labels['auto_backup']:>8}"),
            ("pause", f"Pause                {labels['pause']:>8}"),
            ("sync", f"Sequential play      {labels['sequential_play']:>8}"),
        ]

    def _rebuild(self) -> None:
        menu = self.query_one("#menu", VerticalScroll)
        menu.remove_children()
        menu.mount(
            ListView(
                *[
                    ListItem(Label(label), name=key)
                    for key, label in self._commands()
                ]
            )
        )
        self._show_status()
        self.set_focus(menu.query_one(ListView))

    def _show_status(self) -> None:
        if not self.state.game_loaded:
            self.query_one("#status", Static).update("No game loaded.")
            return

        modified = " (unsaved)" if self.state.game_modified else ""
        self.query_one("#status", Static).update(
            f"{self.game.CurrentGame}{modified}   "
            f"year {self.game.Year}, {self.game.NoOfPlanets} worlds"
        )

    @on(ListView.Selected)
    def _selected(self, event: ListView.Selected) -> None:
        self.run_command(event.item.name)

    def action_dismiss_menu(self) -> None:
        """Esc leaves the menu only when there is a game to go back to."""
        if self.state.game_loaded:
            self.dismiss("begin")

    # --- Commands -------------------------------------------------------------

    def run_command(self, key: str) -> None:
        handler = getattr(self, f"_cmd_{key}")
        try:
            handler()
        except PrologueError as exc:
            self.app.push_screen(Attention(str(exc)))
        except SaveFileError as exc:
            self.app.push_screen(Attention("Could not save the game.", str(exc)))

    def _cmd_begin(self) -> None:
        """Start playing. Command 5, which loads a game first if none is up."""
        if not self.state.game_loaded:
            self._cmd_load()
            return
        self.state.game_modified = True
        self.dismiss("begin")

    def _cmd_new(self) -> None:
        from .newgame import NewGameScreen

        def started(game: GameEnvironment | None) -> None:
            if game is None:
                return
            # StartANewGame has already torn the old universe down by here.
            self.app.adopt_game(game)
            self.game = game
            start_a_new_game(game, self.state)
            self._rebuild()

        self._if_saved(lambda: self.app.push_screen(
            NewGameScreen(self.scenario_dir), started
        ))

    def _cmd_load(self) -> None:
        saves = sorted(self.save_dir.glob("*.[sS][aA][vV]")) + sorted(
            self.save_dir.glob("*.[bB][aA][kK]")
        )
        if not saves:
            raise PrologueError(f'There are no saved games in "{self.save_dir}".')

        def chosen(path: Path | None) -> None:
            if path is None:
                return
            try:
                warnings = continue_old_game(self.game, self.state, path)
            except SaveFileError as exc:
                self.app.push_screen(
                    Attention(f'"{path.name}" is probably not', "an Anacreon save file.")
                )
                return
            self.app.adopt_game(self.game)
            self._rebuild()
            for warning in warnings:
                self.app.push_screen(Attention(warning))

        self._if_saved(lambda: self.app.push_screen(
            ChooseFrom(
                "Select a saved game:", [(p, p.name) for p in saves]
            ),
            chosen,
        ))

    def _cmd_save(self, after=None) -> None:
        """Save, then run ``after`` if the save succeeded.

        The continuation matters: ``GameNotSaved`` calls ``SaveTheGame``
        synchronously and control falls straight back into whatever asked --
        so answering "yes, save" on the way out of ``QuitGame`` saves *and*
        quits. Without it the player would have to ask to quit twice.
        """
        self.state.require_game()

        def named(name: str | None) -> None:
            if name is None:
                # Esc out of the filename prompt abandons the save, and with
                # it whatever it was on the way to doing.
                return
            try:
                save_the_game(self.game, self.state, name.upper())
            except SaveFileError as exc:
                self.app.push_screen(Attention("Could not save the game.", str(exc)))
                return
            self._rebuild()
            if after is not None:
                after()

        self.app.push_screen(
            TextPrompt("Filename to save to :", self.game.CurrentGame), named
        )

    def _cmd_quit(self) -> None:
        def done(_=None) -> None:
            if quit_game(self.state):
                self.dismiss("quit")

        self._if_saved(done)

    def _cmd_time(self) -> None:
        self.state.require_game()

        def entered(value: str | None) -> None:
            if value is None:
                return
            try:
                change_time_limit(self.game, self.state, int(value))
            except ValueError:
                self.app.push_screen(Attention("Please enter a positive integer."))
            except PrologueError as exc:
                self.app.push_screen(Attention(str(exc)))
            self._rebuild()

        self.app.push_screen(
            TextPrompt(
                "Time added per turn (minutes) :",
                str(self.game.TimePerTurn // 60),
                detail="This controls the time added to a player's turn each year.",
            ),
            entered,
        )

    def _cmd_add(self) -> None:
        from .newgame import suggest_empire_name
        from ..prolog import DWARF_AMONG_GIANTS

        self.state.require_game()

        def named(name: str | None) -> None:
            if name is None:
                return
            chosen = name.strip() or suggest_empire_name(set())
            try:
                add_player_empire(
                    self.game,
                    self.state,
                    EmpireIdentity(name=chosen[:1].upper() + chosen[1:]),
                )
            except PrologueError as exc:
                self.app.push_screen(Attention(str(exc)))
            self._rebuild()

        self.app.push_screen(
            TextPrompt(
                "Name of the new empire :",
                suggest_empire_name(set()),
                detail=DWARF_AMONG_GIANTS,
            ),
            named,
        )

    def _cmd_delete(self) -> None:
        self.state.require_game()
        options = deletable_empires(self.game)

        def chosen(emp) -> None:
            if emp is None:
                return

            def confirmed(yes: bool) -> None:
                if not yes:
                    return
                try:
                    delete_player_empire(self.game, self.state, emp)
                except PrologueError as exc:
                    self.app.push_screen(Attention(str(exc)))
                self._rebuild()

            name = dict(options)[emp]
            self.app.push_screen(
                Attention(
                    f"Do you really want to delete the {name} Empire?",
                    "This cannot be undone.",
                    confirm=True,
                ),
                confirmed,
            )

        self.app.push_screen(
            ChooseFrom("Which empire do you want to delete?", options), chosen
        )

    def _cmd_autosave(self) -> None:
        self._announce(toggle_auto_save(self.game, self.state))

    def _cmd_pause(self) -> None:
        self._announce(toggle_pause(self.game, self.state))

    def _cmd_sync(self) -> None:
        self._announce(toggle_turn_sync(self.game, self.state))

    # --- Helpers --------------------------------------------------------------

    def _announce(self, line: str) -> None:
        self._rebuild()
        self.app.push_screen(Attention(line))

    def _if_saved(self, then) -> None:
        """Run ``then`` once unsaved changes are dealt with. ``GameNotSaved``.

        Yes saves first; No discards, which the original models by clearing
        ``GameModified`` -- the changes are gone, so there is nothing left to
        warn about.
        """
        if not needs_saving(self.state):
            then()
            return

        def answered(save: bool) -> None:
            if save:
                self._cmd_save(after=then)
                return
            # Esc, or No: "Press <Esc> to lose changes." The original clears
            # the flag rather than saving, so nothing warns about them again.
            self.state.game_modified = False
            then()

        self.app.push_screen(
            Attention(
                "This game is not saved. Do you want to save it?",
                "Choosing No will lose your changes.",
                confirm=True,
            ),
            answered,
        )
