from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Input, OptionList, Static
from textual.widgets.option_list import Option

from ..base import AppScreen
from . import game_import, library


class LibraryScreen(AppScreen):
    """Lists imported games grouped by source. No Input on this screen - Textual's OptionList
    has no letter-key bindings of its own, so these single-letter screen bindings are safe
    (unlike Input-focused screens, which need typed commands instead - see puzzle.py)."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back"), Binding("i", "import", "Import"),
                Binding("g", "generate", "Generate puzzles"), Binding("d", "delete", "Delete source")]

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(id="msg")
        yield OptionList(id="sources")
        yield Footer()

    def on_mount(self) -> None:
        super().on_mount()
        self._refresh()

    def _refresh(self) -> None:
        summary = library.sources_summary()
        total = sum(summary.values())
        self.query_one("#msg", Static).update(f"{total} games across {len(summary)} source(s)")
        options = self.query_one("#sources", OptionList)
        options.clear_options()
        for source, count in summary.items():
            options.add_option(Option(f"{source}  ({count} games)", id=source))

    def _highlighted_source(self) -> str | None:
        options = self.query_one("#sources", OptionList)
        if options.highlighted is None:
            return None
        return options.get_option_at_index(options.highlighted).id

    def action_import(self) -> None:
        self.app.push_screen(ImportScreen(then=self._refresh))

    def action_generate(self) -> None:
        from .generate_screen import GenerateScreen

        source = self._highlighted_source()
        self.app.push_screen(GenerateScreen(source or "all"))

    def action_delete(self) -> None:
        source = self._highlighted_source()
        if source:
            library.delete_source(source)
            self._refresh()


class ImportScreen(AppScreen):
    """Pick a source kind (OptionList, safe), then an Input appears for that one value - only
    ever one Input-driving mode active, same reasoning as EngineSettingsScreen/AnalysisScreen."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]
    KINDS = [("lichess", "Lichess username (public games)"), ("chesscom", "Chess.com username (public games)"),
             ("pgnfile", "PGN file (path)"), ("pgntext", "Paste PGN text")]
    PLACEHOLDERS = {"lichess": "lichess username", "chesscom": "chess.com username",
                     "pgnfile": "path to a .pgn file", "pgntext": "paste PGN text (one or more games)"}

    def __init__(self, then=None):
        super().__init__()
        self.then = then
        self.kind: str | None = None

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(id="status")
        yield OptionList(*[Option(label, id=kid) for kid, label in self.KINDS], id="kinds")
        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.kind = event.option.id
        self.query_one("#kinds", OptionList).remove()
        self.mount(Input(placeholder=self.PLACEHOLDERS[self.kind], id="value"))
        self.query_one("#value", Input).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value:
            return
        status = self.query_one("#status", Static)
        status.update("Importing...")
        try:
            games, source = await self._fetch(value)
        except Exception as e:  # noqa: BLE001 - surfaced to the user, not a crash
            status.update(f"Import failed: {e}")
            return
        if not games:
            status.update("No games found")
            return
        library.delete_source(source)  # re-import replaces this source's games
        ids = library.append_games(source, games)
        status.update(f"Imported {len(ids)} games as '{source}'")
        if self.then:
            self.then()

    async def _fetch(self, value: str) -> tuple[list, str]:
        if self.kind == "lichess":
            return await game_import.fetch_lichess_games(value), f"lichess:{value}"
        if self.kind == "chesscom":
            return await game_import.fetch_chesscom_games(value), f"chesscom:{value}"
        if self.kind == "pgnfile":
            return game_import.read_pgn_file(value), f"file:{value}"
        return game_import.parse_pgn_text(value), "pasted"
