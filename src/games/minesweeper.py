"""Minesweeper. Rules/difficulties ported from butler-web's minesweeper engine."""
import random
import time
from dataclasses import dataclass

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from .. import config

ROWS, COLS, MINES = 16, 30, 99  # expert only
NUM_COLORS = {1: "#5c9dff", 2: "#4ec36b", 3: "#ff6b6b", 4: "#b48cff", 5: "#ff9f43", 6: "#3ddbd9", 7: "#e0e0e0", 8: "#9aa0a6"}
HIDDEN_BGS, OPEN_BG = ("#434958", "#4d5465"), "#1a1d23"  # hidden cells checkerboard so cells stay distinguishable
CELL_W = 3


@dataclass
class Cell:
    mine: bool = False
    revealed: bool = False
    flagged: bool = False
    exploded: bool = False
    count: int = 0


class Minefield:
    def __init__(self, rows: int, cols: int, mines: int):
        self.rows, self.cols, self.mines = rows, cols, mines
        self.grid: list[Cell] = [Cell() for _ in range(rows * cols)]
        self.started = self.over = self.won = False

    def idx(self, r: int, c: int) -> int:
        return r * self.cols + c

    def neighbors(self, r: int, c: int):
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                nr, nc = r + dr, c + dc
                if (dr or dc) and 0 <= nr < self.rows and 0 <= nc < self.cols:
                    yield nr, nc

    def cell(self, r: int, c: int) -> Cell:
        return self.grid[self.idx(r, c)]

    def flags(self) -> int:
        return sum(c.flagged for c in self.grid)

    def _place(self, safe_r: int, safe_c: int) -> None:
        safe = {self.idx(safe_r, safe_c)} | {self.idx(r, c) for r, c in self.neighbors(safe_r, safe_c)}
        pool = [i for i in range(self.rows * self.cols) if i not in safe]
        for i in random.sample(pool, self.mines):
            self.grid[i].mine = True
        for r in range(self.rows):
            for c in range(self.cols):
                self.cell(r, c).count = sum(self.cell(nr, nc).mine for nr, nc in self.neighbors(r, c))

    def _flood(self, r: int, c: int) -> None:
        stack = [(r, c)]
        while stack:
            cr, cc = stack.pop()
            cell = self.cell(cr, cc)
            if cell.revealed or cell.flagged or cell.mine:
                continue
            cell.revealed = True
            if cell.count == 0:
                stack.extend(n for n in self.neighbors(cr, cc) if not self.cell(*n).revealed)

    def toggle_flag(self, r: int, c: int) -> None:
        cell = self.cell(r, c)
        if not self.over and not cell.revealed:
            cell.flagged = not cell.flagged

    def reveal(self, r: int, c: int) -> None:
        """Reveal a cell; on an already-revealed number, chord (reveal neighbours if flags match)."""
        if self.over:
            return
        if not self.started:
            self._place(r, c)
            self.started = True
        cell = self.cell(r, c)
        if cell.revealed and cell.count > 0:
            nbrs = list(self.neighbors(r, c))
            if sum(self.cell(*n).flagged for n in nbrs) != cell.count:
                return
            for n in nbrs:
                nc = self.cell(*n)
                if nc.revealed or nc.flagged:
                    continue
                if nc.mine:
                    nc.revealed = nc.exploded = True
                    self._lose()
                    return
                self._flood(*n)
        elif cell.revealed or cell.flagged:
            return
        elif cell.mine:
            cell.revealed = cell.exploded = True
            self._lose()
            return
        else:
            self._flood(r, c)
        if all(c.mine or c.revealed for c in self.grid):
            self.over = self.won = True
            for c in self.grid:
                if c.mine:
                    c.flagged = True

    def _lose(self) -> None:
        self.over = True
        for c in self.grid:
            if c.mine and not c.flagged:
                c.revealed = True


class BoardView(Static):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.field = Minefield(ROWS, COLS, MINES)
        self.cursor = (0, 0)

    def new(self, rows: int, cols: int, mines: int) -> None:
        self.field = Minefield(rows, cols, mines)
        self.cursor = (rows // 2, cols // 2)
        self.draw_board()

    def move(self, dr: int, dc: int) -> None:
        r, c = self.cursor
        self.cursor = (min(self.field.rows - 1, max(0, r + dr)), min(self.field.cols - 1, max(0, c + dc)))
        self.draw_board()

    def draw_board(self) -> None:
        f, out = self.field, Text()
        for r in range(f.rows):
            for c in range(f.cols):
                cell = f.cell(r, c)
                hidden_bg = HIDDEN_BGS[(r + c) % 2]
                if cell.revealed and cell.mine:
                    ch, style = ("*", "bold white on #c0392b") if cell.exploded else ("*", f"bold #ff6b6b on {OPEN_BG}")
                elif cell.revealed:
                    ch = str(cell.count) if cell.count else " "
                    style = f"bold {NUM_COLORS.get(cell.count, 'white')} on {OPEN_BG}"
                elif cell.flagged:
                    wrong = f.over and not f.won and not cell.mine
                    ch, style = ("x" if wrong else "F"), f"bold #ff6b6b on {hidden_bg}"
                else:
                    ch, style = " ", f"on {hidden_bg}"
                if (r, c) == self.cursor and not f.over:
                    style += " reverse"
                out.append(ch.center(CELL_W), style=style)
            out.append("\n")
        self.update(out)

    def cell_at(self, x: int, y: int):
        c, r = x // CELL_W, y
        return (r, c) if 0 <= r < self.field.rows and 0 <= c < self.field.cols else None


class MinesweeperScreen(Screen):
    BINDINGS = [
        Binding("up,k", "move(-1,0)", "Up", show=False),
        Binding("down,j", "move(1,0)", "Down", show=False),
        Binding("left,h", "move(0,-1)", "Left", show=False),
        Binding("right,l", "move(0,1)", "Right", show=False),
        Binding("space,enter", "reveal", "Reveal/chord"),
        Binding("f", "flag", "Flag"),
        Binding("n", "new", "New"),
        Binding("escape", "back", "Back"),
    ]
    CSS = "MinesweeperScreen {background: #0f1115;} #info {padding: 0 1; height: 3; color: #c9d1d9;} #board {padding: 0 1; width: auto; height: auto;}"

    def __init__(self):
        super().__init__()
        self.t0: float | None = None
        self.final_time: int | None = None
        self.saved = False

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(id="info")
        yield BoardView(id="board")
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(0.25, self._update_info)
        self.action_new()

    @property
    def view(self) -> BoardView:
        return self.query_one(BoardView)

    def action_new(self) -> None:
        self.t0, self.final_time, self.saved = None, None, False
        self.view.new(ROWS, COLS, MINES)
        self._update_info()

    def action_move(self, dr: str, dc: str) -> None:
        self.view.move(int(dr), int(dc))

    def _after_action(self) -> None:
        f = self.view.field
        if f.started and self.t0 is None:
            self.t0 = time.monotonic()
        if f.over and self.final_time is None:
            self.final_time = int(time.monotonic() - (self.t0 or time.monotonic()))
            if f.won and not self.saved:
                self.saved = True
                cfg = config.load()
                best = cfg.get("best_minesweeper_expert")
                if best is None or self.final_time < best:
                    cfg["best_minesweeper_expert"] = self.final_time
                    config.save(cfg)
        self.view.draw_board()
        self._update_info()

    def action_reveal(self) -> None:
        self.view.field.reveal(*self.view.cursor)
        self._after_action()

    def action_flag(self) -> None:
        self.view.field.toggle_flag(*self.view.cursor)
        self._after_action()

    def on_click(self, event: events.Click) -> None:
        if event.widget is not self.view:
            return
        pos = self.view.cell_at(event.x - 1, event.y)  # 1 = board padding
        if not pos:
            return
        self.view.cursor = pos
        (self.action_flag if event.button == 3 else self.action_reveal)()

    def _update_info(self) -> None:
        f = self.view.field
        if self.final_time is not None:
            secs = self.final_time
        else:
            secs = int(time.monotonic() - self.t0) if self.t0 else 0
        status = "YOU WIN!  " if f.won else ("BOOM - game over.  " if f.over else "")
        best = config.load().get("best_minesweeper_expert")
        best_txt = f"   best: {best}s" if best is not None else ""
        self.query_one("#info", Static).update(
            f"{status}mines left: {f.mines - f.flags()}   time: {min(secs, 999)}s{best_txt}\n"
            "arrows/hjkl move, space reveal (or chord), f flag, n new"
        )

    def action_back(self) -> None:
        self.app.pop_screen()
