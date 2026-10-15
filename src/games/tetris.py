"""Tetris: 10x20 well, 7 tetrominoes, 7-bag randomizer, simple wall kicks. Original implementation of the public rules."""
import random

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from .. import config

W, H = 10, 20
# Each piece is a set of (row, col) cells in its spawn orientation, inside a bounding box of side `size`.
PIECES: dict[str, tuple[int, list[tuple[int, int]]]] = {
    "I": (4, [(1, 0), (1, 1), (1, 2), (1, 3)]),
    "O": (2, [(0, 0), (0, 1), (1, 0), (1, 1)]),
    "T": (3, [(0, 1), (1, 0), (1, 1), (1, 2)]),
    "S": (3, [(0, 1), (0, 2), (1, 0), (1, 1)]),
    "Z": (3, [(0, 0), (0, 1), (1, 1), (1, 2)]),
    "J": (3, [(0, 0), (1, 0), (1, 1), (1, 2)]),
    "L": (3, [(0, 2), (1, 0), (1, 1), (1, 2)]),
}
COLORS = {"I": "cyan", "O": "yellow", "T": "magenta", "S": "green", "Z": "red", "J": "blue", "L": "orange1"}
LINE_POINTS = {1: 100, 2: 300, 3: 500, 4: 800}


def rotate(cells: list[tuple[int, int]], size: int) -> list[tuple[int, int]]:
    """Rotate clockwise inside a size x size box."""
    return [(c, size - 1 - r) for r, c in cells]


class Piece:
    def __init__(self, kind: str):
        self.kind = kind
        self.size, self.cells = PIECES[kind]
        self.row = 0
        self.col = (W - self.size) // 2 if kind != "I" else 3

    def blocks(self, cells=None, row=None, col=None) -> list[tuple[int, int]]:
        cells = self.cells if cells is None else cells
        row = self.row if row is None else row
        col = self.col if col is None else col
        return [(row + r, col + c) for r, c in cells]


class Tetris:
    def __init__(self, rng: random.Random | None = None):
        self.rng = rng or random.Random()
        self.grid: list[list[str]] = [[""] * W for _ in range(H)]
        self.score = 0
        self.lines = 0
        self.over = False
        self.bag: list[str] = []
        self.next_kind = self._draw()
        self.piece = self._spawn()

    @property
    def level(self) -> int:
        return self.lines // 10 + 1

    @property
    def interval(self) -> float:
        """Seconds per gravity step."""
        return max(0.06, 0.8 * (0.85 ** (self.level - 1)))

    def _draw(self) -> str:
        if not self.bag:
            self.bag = list(PIECES)
            self.rng.shuffle(self.bag)
        return self.bag.pop()

    def _spawn(self) -> Piece:
        p = Piece(self.next_kind)
        self.next_kind = self._draw()
        if not self._fits(p.blocks()):
            self.over = True
        return p

    def _fits(self, blocks) -> bool:
        return all(0 <= c < W and r < H and (r < 0 or not self.grid[r][c]) for r, c in blocks)

    def move(self, dc: int) -> bool:
        if self.over:
            return False
        p = self.piece
        if self._fits(p.blocks(col=p.col + dc)):
            p.col += dc
            return True
        return False

    def rotate(self) -> bool:
        if self.over:
            return False
        p = self.piece
        cells = rotate(p.cells, p.size)
        for kick in (0, -1, 1, -2, 2):
            if self._fits(p.blocks(cells=cells, col=p.col + kick)):
                p.cells, p.col = cells, p.col + kick
                return True
        return False

    def step(self) -> bool:
        """Gravity: move down one row, or lock the piece. Returns True if the piece locked."""
        if self.over:
            return False
        p = self.piece
        if self._fits(p.blocks(row=p.row + 1)):
            p.row += 1
            return False
        self._lock()
        return True

    def soft_drop(self) -> None:
        if not self.over and not self.step():
            self.score += 1

    def hard_drop(self) -> None:
        if self.over:
            return
        p = self.piece
        while self._fits(p.blocks(row=p.row + 1)):
            p.row += 1
            self.score += 2
        self._lock()

    def ghost_row(self) -> int:
        p = self.piece
        row = p.row
        while self._fits(p.blocks(row=row + 1)):
            row += 1
        return row

    def _lock(self) -> None:
        for r, c in self.piece.blocks():
            if r < 0:
                self.over = True
                return
            self.grid[r][c] = self.piece.kind
        full = [r for r in range(H) if all(self.grid[r])]
        if full:
            self.grid = [[""] * W for _ in full] + [row for i, row in enumerate(self.grid) if i not in full]
            self.lines += len(full)
            self.score += LINE_POINTS[len(full)] * self.level
        self.piece = self._spawn()


class TetrisScreen(Screen):
    """arrows/hjkl move+rotate+soft drop, space hard drop, p pause, n new game, esc back."""

    BINDINGS = [Binding("n", "new_game", "New game"), Binding("p", "pause", "Pause"), Binding("escape", "app.pop_screen", "Back")]
    CSS = """
    TetrisScreen #status {padding: 1 2 0 2; height: auto;}
    TetrisScreen #board {padding: 0 2; height: auto;}
    TetrisScreen #help {padding: 0 2; height: auto; color: $text-muted;}
    """

    def __init__(self, rng: random.Random | None = None):
        super().__init__()
        self._rng = rng
        self.game = Tetris(rng)
        self.paused = False
        self.saved = False
        self._timer = None

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(id="status")
        yield Static(id="board")
        yield Static(id="help")
        yield Footer()

    def on_mount(self) -> None:
        self._schedule()
        self._draw()

    def _schedule(self) -> None:
        if self._timer:
            self._timer.stop()
        self._timer = self.set_timer(self.game.interval, self._tick)

    def _tick(self) -> None:
        if not self.paused and not self.game.over:
            self.game.step()
            self._after()
        self._schedule()

    def _after(self) -> None:
        if self.game.over and not self.saved:
            self.saved = True
            cfg = config.load()
            if self.game.score > cfg.get("best_tetris", 0):
                cfg["best_tetris"] = self.game.score
                config.save(cfg)
        self._draw()

    def action_new_game(self) -> None:
        self.game = Tetris(self._rng)
        self.paused = False
        self.saved = False
        self._schedule()
        self._draw()

    def action_pause(self) -> None:
        if not self.game.over:
            self.paused = not self.paused
            self._draw()

    def on_key(self, event: events.Key) -> None:
        key = event.key
        if self.paused or self.game.over:
            return
        g = self.game
        if key in ("left", "h"):
            g.move(-1)
        elif key in ("right", "l"):
            g.move(1)
        elif key in ("up", "k", "x"):
            g.rotate()
        elif key in ("down", "j"):
            g.soft_drop()
        elif key == "space":
            g.hard_drop()
        else:
            return
        event.stop()
        self._after()

    def _draw(self) -> None:
        g = self.game
        best = max(config.load().get("best_tetris", 0), g.score)
        status = Text(f"score {g.score}   lines {g.lines}   level {g.level}   best {best}", style="bold")
        status.append(f"\nnext: {g.next_kind}", style=COLORS[g.next_kind])
        if g.over:
            status.append("   game over - n for a new game", style="yellow")
        elif self.paused:
            status.append("   paused", style="yellow")
        self.query_one("#status", Static).update(status)

        cur = set(g.piece.blocks()) if not g.over else set()
        ghost = set(g.piece.blocks(row=g.ghost_row())) if not g.over else set()
        buf = Text()
        for r in range(H):
            buf.append("|", style="dim")
            for c in range(W):
                kind = g.grid[r][c]
                if (r, c) in cur:
                    buf.append("██", style=COLORS[g.piece.kind])
                elif kind:
                    buf.append("██", style=COLORS[kind])
                elif (r, c) in ghost:
                    buf.append("░░", style="dim " + COLORS[g.piece.kind])
                else:
                    buf.append(" .", style="dim")
            buf.append("|\n", style="dim")
        buf.append("+" + "--" * W + "+", style="dim")
        self.query_one("#board", Static).update(buf)
        self.query_one("#help", Static).update(
            Text("arrows/hjkl move/rotate/drop   space hard drop   p pause   n new   esc back", style="dim")
        )
