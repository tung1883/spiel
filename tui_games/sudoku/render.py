"""Renders a SudokuGame as a Rich Text grid. Each of the 81 cells is a 5x3 character block (a
digit centred, or up to 9 pencil-marks laid out 1..9 reading order with a blank column between
them so they don't run together) with a 1-character gap between cells; a gap gets a box-drawing
line only where the two cells' `regions` differ - the same rule works for classic's regular 3x3
boxes and jigsaw's irregular shapes without a separate code path (ported from butler-web's
Sudoku.jsx border logic, applied to lines instead of CSS borders). Inequality arrows (the
"inequality" variant) are drawn in the gap too, independent of region lines. The selected cell
is a solid accent-coloured block (no border glyphs) - smoother than box-drawing, and cheaper.
"""
from rich.text import Text

from .engine import SudokuGame, idx

CELL_W = 5  # 3 pencil-mark columns with a blank column between each
CELL_H = 3
GAP = 1
BLOCK_W = CELL_W + GAP
BLOCK_H = CELL_H + GAP
WIDTH = 9 * CELL_W + 8 * GAP
HEIGHT = 9 * CELL_H + 8 * GAP


def _cell_origin(r: int, c: int) -> tuple[int, int]:
    return r * BLOCK_H, c * BLOCK_W


def _note_glyph(notes: set[int], sub_r: int, sub_c: int) -> str:
    n = sub_r * 3 + sub_c + 1
    return str(n) if n in notes else " "


def render(game: SudokuGame, selected: int | None, accent: str = "#0178d4") -> Text:
    grid: list[list[str]] = [[" "] * WIDTH for _ in range(HEIGHT)]
    styles: list[list[str]] = [[""] * WIDTH for _ in range(HEIGHT)]

    sel_r = selected // 9 if selected is not None else None
    sel_c = selected % 9 if selected is not None else None
    sel_val = game.values[selected] if selected is not None else 0

    for r in range(9):
        for c in range(9):
            i = idx(r, c)
            val = game.values[i]
            or0, oc0 = _cell_origin(r, c)
            if val:
                grid[or0 + 1][oc0 + 2] = str(val)
            else:
                for sr in range(3):
                    for sc in range(3):
                        grid[or0 + sr][oc0 + sc * 2] = _note_glyph(game.notes[i], sr, sc)

            is_given = game.is_given(i)
            is_selected = i == selected
            is_peer = selected is not None and (r == sel_r or c == sel_c or game.regions[i] == game.regions[selected])
            is_same_value = sel_val and val == sel_val
            conflict = val != 0 and game.has_conflict(r, c)
            on_diagonal = game.use_diagonals and (r == c or r + c == 8)

            style = ""
            if conflict:
                style = f"bold red on {accent}" if is_selected else "bold red"
            elif is_selected:
                style = f"bold on {accent}"
            elif is_given:
                style = "bold" if not is_peer else "bold on grey19" if not on_diagonal else "bold on grey23"
            elif is_same_value and not is_selected:
                style = f"bold {accent}"
            elif is_peer:
                style = "on grey19" if not on_diagonal else "on grey23"
            elif on_diagonal:
                style = "dim italic"
            if val == 0 and not style:
                style = "dim cyan" if game.notes[i] else "dim"

            for sr in range(CELL_H):
                for sc in range(CELL_W):
                    if not styles[or0 + sr][oc0 + sc]:
                        styles[or0 + sr][oc0 + sc] = style

            # region-boundary lines, drawn in the gap row/col right after this cell
            if c < 8 and game.regions[i] != game.regions[idx(r, c + 1)]:
                for sr in range(CELL_H):
                    grid[or0 + sr][oc0 + CELL_W] = "|"
                    styles[or0 + sr][oc0 + CELL_W] = "dim"
            if r < 8 and game.regions[i] != game.regions[idx(r + 1, c)]:
                for sc in range(CELL_W):
                    grid[or0 + CELL_H][oc0 + sc] = "-"
                    styles[or0 + CELL_H][oc0 + sc] = "dim"

            if game.inequalities:
                if c < 8:
                    sym = game.inequality_symbol(i, idx(r, c + 1))
                    if sym:
                        grid[or0 + 1][oc0 + CELL_W] = sym
                        styles[or0 + 1][oc0 + CELL_W] = "bold yellow"
                if r < 8:
                    sym = game.inequality_symbol(i, idx(r + 1, c))
                    if sym:
                        grid[or0 + CELL_H][oc0 + 2] = "v" if sym == ">" else "^"
                        styles[or0 + CELL_H][oc0 + 2] = "bold yellow"

    out = Text()
    for row in range(HEIGHT):
        for col in range(WIDTH):
            out.append(grid[row][col], style=styles[row][col])
        out.append("\n")
    return out
