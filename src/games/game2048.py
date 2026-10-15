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


def _slide(line: list[int]) -> tuple[list[int], int, list[tuple[int, int]]]:
    """Slide one row/column toward index 0, merging equal adjacent tiles once each.
    Returns (new_line, score_gained, trace) where trace lists (source_index, destination_index) per tile."""
    src = [i for i, v in enumerate(line) if v]
    merged: list[int] = []
    trace: list[tuple[int, int]] = []
    gained = 0
    k = 0
    while k < len(src):
        v = line[src[k]]
        if k + 1 < len(src) and line[src[k + 1]] == v:
            merged.append(v * 2)
            gained += v * 2
            trace += [(src[k], len(merged) - 1), (src[k + 1], len(merged) - 1)]
            k += 2
        else:
            merged.append(v)
            trace.append((src[k], len(merged) - 1))
            k += 1
    merged += [0] * (SIZE - len(merged))
    return merged, gained, trace


def _compress_merge(line: list[int]) -> tuple[list[int], int, bool]:
    """Returns (new_line, score_gained, moved)."""
    merged, gained, _ = _slide(line)
    return merged, gained, merged != line


class Board2048:
    """direction: 'h' (left) 'l' (right) 'k' (up) 'j' (down) - vim-style, matches this repo's convention."""

    def __init__(self):
        self.grid = [[0] * SIZE for _ in range(SIZE)]
        self.score = 0
        self.won = False
        self.last_moves: list[tuple[int, tuple[int, int], tuple[int, int]]] = []  # (value, from_rc, to_rc)
        self.last_spawn: tuple[int, int] | None = None
        self.spawn()
        self.spawn()

    def spawn(self) -> None:
        empties = [(r, c) for r in range(SIZE) for c in range(SIZE) if self.grid[r][c] == 0]
        if not empties:
            return
        r, c = random.choice(empties)
        self.grid[r][c] = 4 if random.random() < 0.1 else 2
        self.last_spawn = (r, c)

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

    @staticmethod
    def _to_rc(direction: str, line_idx: int, pos: int) -> tuple[int, int]:
        """Map (line, position-within-line) back to a grid (row, col) for the given direction."""
        if direction == "h":
            return line_idx, pos
        if direction == "l":
            return line_idx, SIZE - 1 - pos
        if direction == "k":
            return pos, line_idx
        return SIZE - 1 - pos, line_idx

    def move(self, direction: str) -> bool:
        lines = self._lines(direction)
        any_moved = False
        moves: list[tuple[int, tuple[int, int], tuple[int, int]]] = []
        for i, line in enumerate(lines):
            new_line, gained, trace = _slide(line)
            moves += [(line[s], self._to_rc(direction, i, s), self._to_rc(direction, i, d)) for s, d in trace]
            lines[i] = new_line
            self.score += gained
            any_moved = any_moved or new_line != line
            if any(v >= 2048 for v in new_line):
                self.won = True
        if any_moved:
            self._unlines(direction, lines)
            self.last_moves = moves
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


# value -> (background, foreground): the classic 2048 palette
_TILE = {
    0: ("#2a2a36", "#2a2a36"),
    2: ("#eee4da", "#776e65"), 4: ("#ede0c8", "#776e65"), 8: ("#f2b179", "#ffffff"), 16: ("#f59563", "#ffffff"),
    32: ("#f67c5f", "#ffffff"), 64: ("#f65e3b", "#ffffff"), 128: ("#edcf72", "#ffffff"), 256: ("#edcc61", "#ffffff"),
    512: ("#edc850", "#ffffff"), 1024: ("#edc53f", "#ffffff"), 2048: ("#edc22e", "#ffffff"),
}
_BIG = ("#3c3a32", "#ffffff")
TILE_W, TILE_H = 6, 3  # terminal cells are ~twice as tall as wide, so 6x3 looks square
GAP_W, GAP_H = 2, 1
_FRAME = "on #15151f"
BOARD_W = GAP_W + SIZE * (TILE_W + GAP_W)
BOARD_H = GAP_H + SIZE * (TILE_H + GAP_H)
FRAMES = 3  # animation length in frames
FRAME_DT = 0.016


def _tile_style(v: int) -> str:
    bg, fg = _TILE.get(v, _BIG)
    return f"bold {fg} on {bg}"


def _origin(r: float, c: float) -> tuple[int, int]:
    """Top-left screen cell (x, y) of the tile slot at (possibly fractional) grid position (r, c)."""
    return round(GAP_W + c * (TILE_W + GAP_W)), round(GAP_H + r * (TILE_H + GAP_H))


def _canvas(tiles: list[tuple[int, int, int]]) -> Text:
    """Draw (value, x, y) tiles over the dark frame, in order (later tiles paint over earlier ones)."""
    cells = [[(" ", _FRAME)] * BOARD_W for _ in range(BOARD_H)]
    for v, x, y in tiles:
        style = _tile_style(v)
        for dy in range(TILE_H):
            label = str(v).center(TILE_W) if v and dy == TILE_H // 2 else " " * TILE_W
            for dx in range(TILE_W):
                if 0 <= y + dy < BOARD_H and 0 <= x + dx < BOARD_W:
                    cells[y + dy][x + dx] = (label[dx], style)
    buf = Text()
    for i, row in enumerate(cells):
        run, run_style = "", row[0][1]
        for ch, style in row:
            if style != run_style:
                buf.append(run, style=run_style)
                run, run_style = "", style
            run += ch
        buf.append(run, style=run_style)
        if i < BOARD_H - 1:
            buf.append(chr(10))
    return buf


def _empties() -> list[tuple[int, int, int]]:
    return [(0, *_origin(r, c)) for r in range(SIZE) for c in range(SIZE)]


def render_board(grid: list[list[int]]) -> Text:
    tiles = _empties()
    tiles += [(v, *_origin(r, c)) for r, row in enumerate(grid) for c, v in enumerate(row) if v]
    return _canvas(tiles)


def render_motion(board: Board2048, t: float) -> Text:
    """One animation frame: tiles of the previous position slid fraction t (0..1) of the way to where they landed.
    The freshly spawned tile is held back until the slide ends."""
    ease = 1 - (1 - t) ** 2
    tiles = _empties()
    for v, (r0, c0), (r1, c1) in board.last_moves:
        tiles.append((v, *_origin(r0 + (r1 - r0) * ease, c0 + (c1 - c0) * ease)))
    return _canvas(tiles)


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
        self.best = config.load().get("best_2048", 0)
        self.frame = 0  # >0 while a slide animation is playing
        self._timer = None

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(id="status")
        yield Static(id="board")
        yield Static(id="help")
        yield Footer()

    def on_mount(self) -> None:
        self._draw()

    @property
    def animating(self) -> bool:
        return self.frame > 0

    def _stop_anim(self) -> None:
        self.frame = 0
        if self._timer:
            self._timer.stop()
            self._timer = None

    def _start_anim(self) -> None:
        self._stop_anim()
        self.frame = 1
        self._timer = self.set_interval(FRAME_DT, self._step_anim)

    def _step_anim(self) -> None:
        self.frame += 1
        if self.frame > FRAMES:
            self._stop_anim()
        self._draw_board()

    def action_new_game(self) -> None:
        self._stop_anim()
        self.board = Board2048()
        self.saved = False
        self._draw()

    def on_key(self, event: events.Key) -> None:
        key = event.key
        over = self.board.is_game_over()
        if over:
            return
        direction = {"left": "h", "h": "h", "right": "l", "l": "l", "up": "k", "k": "k", "down": "j", "j": "j"}.get(key)
        if direction is None:
            return
        event.stop()
        if self.animating:  # a new move cuts the running slide short
            self._stop_anim()
        if self.board.move(direction):
            if self.board.is_game_over() and not self.saved:
                self.saved = True
                cfg = config.load()
                if self.board.score > cfg.get("best_2048", 0):
                    self.best = cfg["best_2048"] = self.board.score
                    config.save(cfg)
            self._start_anim()
        self._draw()

    def _draw(self) -> None:
        self._draw_status()
        self._draw_board()
        self.query_one("#help", Static).update(Text("arrows/hjkl slide   n new game   esc back", style="dim"))

    def _draw_status(self) -> None:
        board = self.board
        status = Text()
        status.append(" SCORE ", style="bold #bbada0 on #15151f")
        status.append(f" {board.score:<7}", style="bold white on #3c3a32")
        status.append("  ")
        status.append(" BEST ", style="bold #bbada0 on #15151f")
        status.append(f" {max(self.best, board.score):<7}", style="bold white on #3c3a32")
        if board.is_game_over():
            status.append("\ngame over - n for a new game", style="bold yellow")
        elif board.won:
            status.append("\nyou made 2048! keep going", style="bold green")
        self.query_one("#status", Static).update(status)

    def _draw_board(self) -> None:
        if self.animating and self.frame <= FRAMES:
            text = render_motion(self.board, self.frame / FRAMES)
        else:
            text = render_board(self.board.grid)
        self.query_one("#board", Static).update(text)
