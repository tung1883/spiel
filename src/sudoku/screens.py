"""Sudoku screens: a variant+difficulty+puzzle picker, and the board itself. Ported from
butler-web's Sudoku.jsx (same bank, same resume/undo/hint/best-time rules), re-done for a
keyboard-only terminal UI instead of click/tap."""
import time

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Static

from ..base import AppScreen
from . import bank, progress
from .render import render

DIFFS = ["easy", "medium", "hard", "expert", "extreme"]
VARIANT_LABEL = {"classic": "Classic", "jigsaw": "Jigsaw", "cross": "Cross", "inequality": "Inequality"}


def _fmt_time(seconds: int | None) -> str:
    if seconds is None:
        return "--"
    return f"{seconds // 60}:{seconds % 60:02d}"


GRID_COLS = 10


class SudokuMenu(AppScreen):
    """Pick a variant and difficulty, then a puzzle from that 100-puzzle bank, laid out as a
    10x10 grid (all 100 visible at once) under variant tabs + a difficulty bar."""

    BINDINGS = [Binding("escape,q", "app.pop_screen", "Back")]
    CSS = """
    SudokuMenu #tabs {padding: 1 2 0 2; height: auto;}
    SudokuMenu #diffbar {padding: 0 2; height: auto;}
    SudokuMenu #grid {padding: 1 2; height: auto;}
    SudokuMenu #legend {padding: 0 2; height: auto; color: $text-muted;}
    """

    def __init__(self):
        super().__init__()
        self.variant = "classic"
        self.difficulty = "medium"
        self.selected = 0
        self._prog: dict = {}
        self._best: int | None = None
        self._bank_size = 100

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(id="tabs")
        yield Static(id="diffbar")
        yield Static(id="grid")
        yield Static(id="legend")
        yield Footer()

    def on_mount(self) -> None:
        super().on_mount()
        self._load()
        self._fill(relayout=True)

    def on_screen_resume(self) -> None:
        self._load()
        self._fill(relayout=True)

    def on_key(self, event: events.Key) -> None:
        ch, key = event.character, event.key
        variants = bank.VARIANTS
        reload = False
        if key == "tab":
            self.variant = variants[(variants.index(self.variant) + 1) % len(variants)]
            reload = True
        elif key == "shift+tab":
            self.variant = variants[(variants.index(self.variant) - 1) % len(variants)]
            reload = True
        elif ch == "[":
            self.difficulty = DIFFS[(DIFFS.index(self.difficulty) - 1) % len(DIFFS)]
            reload = True
        elif ch == "]":
            self.difficulty = DIFFS[(DIFFS.index(self.difficulty) + 1) % len(DIFFS)]
            reload = True
        elif key in ("up", "k"):
            self.selected = max(0, self.selected - GRID_COLS)
        elif key in ("down", "j"):
            self.selected = min(self._bank_size - 1, self.selected + GRID_COLS)
        elif key in ("left", "h"):
            r, c = divmod(self.selected, GRID_COLS)
            self.selected = r * GRID_COLS + max(0, c - 1)
        elif key in ("right", "l"):
            r, c = divmod(self.selected, GRID_COLS)
            self.selected = r * GRID_COLS + min(GRID_COLS - 1, c + 1, self._bank_size - 1 - r * GRID_COLS)
        elif key == "enter":
            self.app.push_screen(SudokuScreen(self.variant, self.difficulty, self.selected))
            return
        else:
            return
        event.stop()
        if reload:
            self._load()
            self.selected = min(self.selected, self._bank_size - 1)
            self._fill(relayout=True)  # label widths can change across variants/difficulties
        else:
            self._fill()  # pure cursor move: cheap repaint, no relayout, no disk read

    def _load(self) -> None:
        """Pull progress/best-time/bank-size from disk - only on mount or variant/difficulty change,
        never on plain cursor movement (that was the picker's lag: a config.json re-read per arrow press)."""
        level = bank.DIFF_LEVELS[self.difficulty]
        self._prog = progress.load_progress(self.variant, level)
        self._best = progress.load_best_times().get(f"{self.variant}:{self.difficulty}")
        self._bank_size = bank.get_bank_size(self.variant, self.difficulty)

    def _fill(self, relayout: bool = False) -> None:
        accent = self.app.theme_variables.get("primary", "#0178d4")

        tabs = Text()
        for i, v in enumerate(bank.VARIANTS):
            if i:
                tabs.append(" | ")
            tabs.append(VARIANT_LABEL[v], style=f"bold {accent} underline" if v == self.variant else "dim")
        self.query_one("#tabs", Static).update(tabs, layout=relayout)

        diffbar = Text()
        for i, d in enumerate(DIFFS):
            if i:
                diffbar.append("  ")
            diffbar.append(d, style="bold" if d == self.difficulty else "dim")
        diffbar.append(f"    best: {_fmt_time(self._best)}")
        self.query_one("#diffbar", Static).update(diffbar, layout=relayout)

        grid = Text()
        for i in range(self._bank_size):
            if i and i % GRID_COLS == 0:
                grid.append("\n")
            status = self._prog.get(str(i), {}).get("status")
            mark = "*" if status == "done" else "~" if status == "inprogress" else " "
            cell = f"{mark}{i + 1:>3} "
            style = f"bold on {accent}" if i == self.selected else (
                "bold green" if status == "done" else "yellow" if status == "inprogress" else "dim")
            grid.append(cell, style=style)
        self.query_one("#grid", Static).update(grid, layout=relayout)

        if relayout:
            self.query_one("#legend", Static).update(
                Text("arrows move   tab: variant   [ ]: difficulty   enter: play   "
                     "* done   ~ in progress", style="dim"))


class SudokuScreen(AppScreen):
    """Arrow keys move the selection; 1-9 enter a digit; n toggles note mode; e erases; u undoes;
    ? reveals the selected cell (hint); q leaves (progress is saved after every edit)."""

    CSS = """
    SudokuScreen #status {padding: 1 2 0 2; height: auto;}
    SudokuScreen #board {padding: 1 2; height: auto;}
    SudokuScreen #help {padding: 0 2; height: auto; color: $text-muted;}
    """

    def __init__(self, variant: str, difficulty: str, index: int):
        super().__init__()
        self.variant = variant
        self.difficulty = difficulty
        self.game, self.base_seconds = progress.load_puzzle(difficulty, variant, index)
        self.selected: int | None = 0
        self.note_mode = False
        self.t0 = time.monotonic()
        self.recorded = self.game.won
        self._best = progress.load_best_times().get(f"{variant}:{difficulty}")

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(id="status")
        yield Static(id="board")
        yield Static(id="help")
        yield Footer()

    def on_mount(self) -> None:
        super().on_mount()
        self.set_interval(1.0, self._tick)
        self._draw(relayout=True)

    @property
    def seconds(self) -> int:
        return self.base_seconds + (0 if self.game.won else int(time.monotonic() - self.t0))

    def _tick(self) -> None:
        if not self.game.won:
            self._draw()

    def _after_edit(self) -> None:
        progress.persist(self.variant, self.difficulty, self.game, self.seconds)
        if self.game.won and not self.recorded:
            self.recorded = True
            key = f"{self.variant}:{self.difficulty}"
            self._best = progress.record_time(key, self.seconds).get(key, self._best)
        self._draw(relayout=self.game.won)  # "Solved in ...!" adds a status line only on the win edit

    def on_key(self, event: events.Key) -> None:
        ch, key = event.character, event.key
        event.stop()
        if key == "escape":
            if self.selected is None:
                self.app.pop_screen()
                return
            self.selected = None
        elif key in ("up", "k") and self.selected is not None:
            self.selected = max(0, self.selected - 9)
        elif key in ("down", "j") and self.selected is not None:
            self.selected = min(80, self.selected + 9)
        elif key in ("left", "h") and self.selected is not None:
            r, c = divmod(self.selected, 9)
            self.selected = r * 9 + max(0, c - 1)
        elif key in ("right", "l") and self.selected is not None:
            r, c = divmod(self.selected, 9)
            self.selected = r * 9 + min(8, c + 1)
        elif ch == "n":
            self.note_mode = not self.note_mode
        elif ch == "u":
            self.game.undo()
            self._after_edit()
            return
        elif ch in ("e",) or key in ("delete", "backspace"):
            if self.selected is not None:
                self.game.erase(self.selected)
                self._after_edit()
            return
        elif ch == "?":
            if self.selected is not None:
                self.game.hint(self.selected)
                self._after_edit()
            return
        elif ch and ch.isdigit() and ch != "0" and self.selected is not None:
            self.game.input_digit(self.selected, int(ch), self.note_mode)
            self._after_edit()
            return
        else:
            return
        self._draw()

    def _draw(self, relayout: bool = False) -> None:
        g = self.game
        accent = self.app.theme_variables.get("primary", "#0178d4")
        bank_size = bank.get_bank_size(self.variant, self.difficulty)
        status = Text(
            f"{VARIANT_LABEL[self.variant]} {self.difficulty}  #{g.index + 1}/{bank_size}   "
            f"{_fmt_time(self.seconds)}   best: {_fmt_time(self._best)}" + ("   NOTES" if self.note_mode else ""),
            style="bold",
        )
        if g.won:
            status.append(f"\nSolved in {_fmt_time(self.seconds)}!", style=accent)
        self.query_one("#status", Static).update(status, layout=relayout)
        self.query_one("#board", Static).update(render(g, self.selected, accent), layout=relayout)
        if relayout:
            self.query_one("#help", Static).update(
                Text("arrows move   1-9 enter digit   n toggle notes   e erase   u undo   ? hint   esc deselect/back",
                     style="dim"))
