from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, OptionList
from textual.widgets.option_list import Option

from ..base import AppScreen


class ChessMenu(AppScreen):
    """Hub for everything chess: playing (unchanged, settings-driven), analysis, puzzles,
    and the engine source used by both."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield OptionList(
            Option("Play", id="play"),
            Option("Analysis", id="analysis"),
            Option("Puzzles", id="puzzles"),
            Option("Library", id="library"),
            Option("Engine settings", id="engine"),
        )
        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        oid = event.option.id
        if oid == "play":
            from ..typeracer.menu import chess_screen, load_settings

            self.app.push_screen(chess_screen(load_settings()))
        elif oid == "analysis":
            from .analysis import AnalysisScreen

            self.app.push_screen(AnalysisScreen())
        elif oid == "puzzles":
            from .puzzle import PuzzleScreen

            self.app.push_screen(PuzzleScreen())
        elif oid == "library":
            from .library_screen import LibraryScreen

            self.app.push_screen(LibraryScreen())
        elif oid == "engine":
            from .engine_settings import EngineSettingsScreen

            self.app.push_screen(EngineSettingsScreen())
