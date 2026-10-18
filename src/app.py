from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.theme import Theme
from textual.widgets import Footer, Header, OptionList
from textual.widgets.option_list import Option

from .base import AppScreen
from .music.controller import MusicController
from .terminal_title import set_terminal_title

SPIEL_DARK = Theme(
    name="spiel-dark",
    primary="#7c3aed",
    secondary="#22d3ee",
    accent="#a855f7",
    warning="#f59e0b",
    error="#ef4444",
    success="#22c55e",
    foreground="#d4d4e0",
    background="#08080c",
    surface="#0f0f16",
    panel="#15151f",
    dark=True,
)


class Menu(AppScreen):
    BINDINGS = [
        Binding("q", "app.quit", "Quit"),
        Binding("s", "app.settings", "Settings"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
    ]

    def action_cursor_down(self) -> None:
        self.query_one(OptionList).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one(OptionList).action_cursor_up()

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield OptionList(
            Option("TypeRacer", id="typeracer"),
            Option("Chess", id="chess"),
            Option("Minesweeper", id="minesweeper"),
            Option("Sudoku", id="sudoku"),
            Option("2048", id="2048"),
            Option("Wordle", id="wordle"),
            Option("Tetris", id="tetris"),
            Option("Learn to Code", id="learn"),
            Option("Music", id="music"),
            Option("Settings", id="settings"),
        )
        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        oid = event.option.id
        if oid == "typeracer":
            from .typeracer.menu import load_settings, race_screen

            self.app.push_screen(race_screen(load_settings()))  # uses the saved settings, no setup needed
        elif oid == "settings":
            from .typeracer.menu import SettingsScreen

            self.app.push_screen(SettingsScreen())
        elif oid == "chess":
            from .typeracer.menu import chess_screen, load_settings

            self.app.push_screen(chess_screen(load_settings()))
        elif oid == "learn":
            from .learn.hub import HubScreen

            self.app.push_screen(HubScreen())
        elif oid == "minesweeper":
            from .games.minesweeper import MinesweeperScreen

            self.app.push_screen(MinesweeperScreen())
        elif oid == "sudoku":
            from .sudoku.screens import SudokuMenu

            self.app.push_screen(SudokuMenu())
        elif oid == "2048":
            from .games.game2048 import Game2048Screen

            self.app.push_screen(Game2048Screen())
        elif oid == "wordle":
            from .games.wordle import WordleScreen

            self.app.push_screen(WordleScreen())
        elif oid == "tetris":
            from .games.tetris import TetrisScreen

            self.app.push_screen(TetrisScreen())
        elif oid == "music":
            from .music.screens import music_screen

            self.app.push_screen(music_screen(self.app))


class GamesApp(App):
    TITLE = "Spiel"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS = [
        Binding("ctrl+s", "settings", "Settings", show=False),
        Binding("ctrl+p", "toggle_music", "Music", show=False),
    ]

    def action_settings(self) -> None:
        from .typeracer.menu import SettingsScreen

        if not isinstance(self.screen, SettingsScreen):
            self.push_screen(SettingsScreen())

    def action_toggle_music(self) -> None:
        from .music.screens import FolderPromptScreen, MusicScreen, music_screen

        if isinstance(self.screen, (MusicScreen, FolderPromptScreen)):
            self.pop_screen()
        else:
            self.push_screen(music_screen(self))

    def _check_music_finished(self) -> None:
        if self.music.finished():
            self.music.next()

    def _update_title(self) -> None:
        track = self.music.current_track
        if track is None:
            set_terminal_title("Spiel")
        else:
            suffix = " (paused)" if self.music.paused else ""
            set_terminal_title(f"{track.stem}{suffix} - Spiel")

    def on_mount(self) -> None:
        self.register_theme(SPIEL_DARK)
        self.theme = "spiel-dark"
        self.music = MusicController()
        self.music.on_change = self._update_title
        set_terminal_title("Spiel")
        self.set_interval(0.5, self._check_music_finished)
        self.push_screen(Menu())


def main() -> None:
    GamesApp().run()


if __name__ == "__main__":
    main()
