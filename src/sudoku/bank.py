"""Puzzle bank: 4 variants x 5 difficulties x 100 real curated puzzles each (ported from the
user's butler-web sudoku game, ..\\butler\\butler-web\\src\\games\\sudoku\\ - same puzzle data,
same encoding). Loaded once from src/sudoku/puzzles/*.json (packaged data, see pyproject.toml).
"""
import json
from functools import lru_cache
from importlib import resources

SIZE = 9
CELLS = SIZE * SIZE

VARIANTS = ["classic", "jigsaw", "cross", "inequality"]
DIFF_LEVELS = {"easy": 1, "medium": 2, "hard": 3, "expert": 4, "extreme": 5}
DIFFICULTIES = ["easy", "medium", "hard", "expert", "extreme"]


@lru_cache(maxsize=None)
def _bank(variant: str) -> dict:
    text = resources.files("src.sudoku.puzzles").joinpath(f"{variant}.json").read_text()
    return json.loads(text)


def _digits(s: str) -> list[int]:
    return [int(ch) for ch in s]


def _box_regions() -> list[int]:
    regions = [0] * CELLS
    for i in range(CELLS):
        r, c = divmod(i, SIZE)
        regions[i] = (r // 3) * 3 + (c // 3)
    return regions


# Encoding (matches the reference app's solved grids, verified in butler): '1' at (r,c) means the
# cell must be greater than its right/bottom neighbour, '2' means less than; every adjacent pair in
# range is marked, only the padding row/column is '0'.
def _decode_inequalities(h_str: str, v_str: str) -> dict[int, list[tuple[int, bool]]]:
    h, v = _digits(h_str), _digits(v_str)
    edges: dict[int, list[tuple[int, bool]]] = {}

    def add_edge(a: int, b: int, a_greater: bool) -> None:
        edges.setdefault(a, []).append((b, a_greater))
        edges.setdefault(b, []).append((a, not a_greater))

    for r in range(9):
        for c in range(8):
            code = h[r * 9 + c]
            if code:
                add_edge(r * 9 + c, r * 9 + c + 1, code == 1)
    for r in range(8):
        for c in range(9):
            code = v[r * 9 + c]
            if code:
                add_edge(r * 9 + c, (r + 1) * 9 + c, code == 1)
    return edges


def _build_puzzle(variant: str, entry: list[str]) -> dict:
    question, answer, *extra = entry
    puzzle, solution = _digits(question), _digits(answer)
    if variant == "jigsaw":
        return {"puzzle": puzzle, "solution": solution, "regions": _digits(extra[0]), "check_boxes": True,
                "use_diagonals": False, "inequalities": None}
    if variant == "inequality":
        # Futoshiki-style: only rows/cols/inequalities are constrained, not 3x3 boxes - verified by
        # checking the bank's own solved grids, which do contain duplicate values within a box (the
        # source app's hasConflict() still checked box regions anyway, a latent bug we don't repeat:
        # keep regions=boxRegions() for the cosmetic box lines/peer-highlight, but check_boxes=False
        # so SudokuGame.has_conflict never flags a correctly solved puzzle over a non-constraint.
        return {"puzzle": puzzle, "solution": solution, "regions": _box_regions(), "check_boxes": False,
                "use_diagonals": False, "inequalities": _decode_inequalities(extra[0], extra[1])}
    return {"puzzle": puzzle, "solution": solution, "regions": _box_regions(), "check_boxes": True,
            "use_diagonals": variant == "cross", "inequalities": None}


def get_bank_size(variant: str, difficulty: str) -> int:
    level = DIFF_LEVELS.get(difficulty, DIFF_LEVELS["medium"])
    return len(_bank(variant)[str(level)])


def get_puzzle_at(difficulty: str, variant: str, index: int) -> dict:
    level = DIFF_LEVELS.get(difficulty, DIFF_LEVELS["medium"])
    data = _build_puzzle(variant, _bank(variant)[str(level)][index])
    return {"index": index, **data}
