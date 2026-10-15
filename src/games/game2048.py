"""2048: the classic sliding-tile merge puzzle. Original implementation (rules only - a 4x4 grid,
slide/merge/spawn - are a well-known public game mechanic, no code or assets taken from anywhere)."""
import random

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from .. import config

SIZE = 4


def _compress_merge(line: list[int]) -> tuple[list[int], int, bool]:
    """Slide one row/column toward index 0, merging equal adjacent tiles once each.
    Returns (new_line, score_gained, moved)."""
    vals = [v for v in line if v]
    merged: list[int] = []
    gained = 0
    i = 0
    while i < len(vals):
        if i + 1 < len(vals) and vals[i] == vals[i + 1]:
            merged.append(vals[i] * 2)
            gained += vals[i] * 2
            i += 2
        else:
            merged.append(vals[i])
            i += 1
    merged += [0] * (SIZE - len(merged))
    return merged, gained, merged != line


class Board2048:
    """direction: 'h' (left) 'l' (right) 'k' (up) 'j' (down) - vim-style, matches this repo's convention."""

    def __init__(self):
        self.grid = [[0] * SIZE for _ in range(SIZE)]
        self.score = 0
        self.won = False
        self.spawn()
        self.spawn()

    def spawn(self) -> None:
        empties = [(r, c) for r in range(SIZE) for c in range(SIZE) if self.grid[r][c] == 0]
        if not empties:
            return
        r, c = random.choice(empties)
        self.grid[r][c] = 4 if random.random() < 0.1 else 2

    def _lines(self, direction: str) -> list[list[int]]:
        if direction in ("h", "l"):
            lines = [row[:] for row in self.grid]
        else:
            lines = [[self.grid[r][c] for r in range(SIZE)] for c in range(SIZE)]
        if direction in ("l", "j"):
            lines = [line[::-1] for line in lines]
        return lines

    def _unlines(self, direction: str, lines: list[list[int]]) -> None:
        if direction in ("l", "j"):
            lines = [line[::-1] for line in lines]
        if direction in ("h", "l"):
            self.grid = lines
        else:
            for c in range(SIZE):
                for r in range(SIZE):
                    self.grid[r][c] = lines[c][r]

    def move(self, direction: str) -> bool:
        lines = self._lines(direction)
        any_moved = False
        for i, line in enumerate(lines):
            new_line, gained, moved = _compress_merge(line)
            lines[i] = new_line
            self.score += gained
            any_moved = any_moved or moved
            if any(v >= 2048 for v in new_line):
                self.won = True
        if any_moved:
            self._unlines(direction, lines)
            self.spawn()
        return any_moved

    def is_game_over(self) -> bool:
        if any(0 in row for row in self.grid):
            return False
        for r in range(SIZE):
            for c in range(SIZE - 1):
                if self.grid[r][c] == self.grid[r][c + 1]:
                    return False
        for c in range(SIZE):
            for r in range(SIZE - 1):
                if self.grid[r][c] == self.grid[r + 1][c]:
                    return False
        return True


_COLOR_BY_VALUE = {
    2: "white", 4: "white", 8: "yellow", 16: "yellow", 32: "orange1", 64: "orange1",
    128: "gold1", 256: "gold1", 512: "green", 1024: "magenta", 2048: "bold red",
}


class Game2048Screen(Screen):
    """arrows/hjkl slide, n = new game, esc = back."""

    BINDINGS = [Binding("n", "new_game", "New game"), Binding("escape", "app.pop_screen", "Back")]
    CSS = """
    Game2048Screen #status {padding: 1 2 0 2; height: auto;}
    Game2048Screen #board {padding: 1 2; height: auto;}
    Game2048Screen #help {padding: 0 2; height: auto; color: $text-muted;}
    """

    def __init__(self):
        super().__init__()
        self.board = Board2048()
        self.saved = False

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(id="status")
        yield Static(id="board")
        yield Static(id="help")
        yield Footer()

    def on_mount(self) -> None:
        self._draw()

    def action_new_game(self) -> None:
        self.board = Board2048()
        self.saved = False
        self._draw()

    def on_key(self, event: events.Key) -> None:
        key, ch = event.key, event.character
        over = self.board.is_game_over()
        if over:
            return
        moved = False
        if key in ("left", "h"):
            moved = self.board.move("h")
        elif key in ("right", "l"):
            moved = self.board.move("l")
        elif key in ("up", "k"):
            moved = self.board.move("k")
        elif key in ("down", "j"):
            moved = self.board.move("j")
        else:
            return
        event.stop()
        if moved and self.board.is_game_over() and not self.saved:
            self.saved = True
            cfg = config.load()
            if self.board.score > cfg.get("best_2048", 0):
                cfg["best_2048"] = self.board.score
                config.save(cfg)
        self._draw()

    def _draw(self) -> None:
        board = self.board
        best = max(config.load().get("best_2048", 0), board.score)
        status = Text(f"score {board.score}   best {best}", style="bold")
        if board.won:
            status.append("   2048!", style="bold green")
        if board.is_game_over():
            status.append("\ngame over - n for a new game", style="yellow")
        self.query_one("#status", Static).update(status)

        buf = Text()
        for row in board.grid:
            cells = []
            for v in row:
                text = str(v) if v else "."
                style = _COLOR_BY_VALUE.get(v, "dim") if v else "dim"
                cells.append((f"{text:>5}", style))
            for text, style in cells:
                buf.append(text, style=style)
            buf.append("\n")
        self.query_one("#board", Static).update(buf)
        self.query_one("#help", Static).update(Text("arrows/hjkl slide   n new game   esc back", style="dim"))
