"""The sudoku game state: one puzzle in play. Conflict checking and the edit/undo rules are a
direct port of butler-web's generator.js + the Sudoku.jsx reducer logic, same semantics."""
from dataclasses import dataclass, field

SIZE = 9
CELLS = SIZE * SIZE


def idx(r: int, c: int) -> int:
    return r * SIZE + c


@dataclass
class SudokuGame:
    index: int
    puzzle: list[int]  # 0 = empty/editable, 1-9 = a given clue
    solution: list[int]
    regions: list[int]  # CELLS ints, which of the 9 regions each cell belongs to (box or jigsaw)
    check_boxes: bool  # False for "inequality": regions exist for the cosmetic lines, not a real rule
    use_diagonals: bool  # "cross" variant: both main diagonals are extra regions
    inequalities: dict[int, list[tuple[int, bool]]] | None  # cell -> [(other_cell, must_be_greater)]
    values: list[int] = field(default_factory=list)
    notes: list[set[int]] = field(default_factory=list)
    won: bool = False

    def __post_init__(self):
        if not self.values:
            self.values = list(self.puzzle)
        if not self.notes:
            self.notes = [set() for _ in range(CELLS)]
        self._history: list[tuple[list[int], list[set[int]]]] = []

    def is_given(self, i: int) -> bool:
        return self.puzzle[i] != 0

    def is_solved(self) -> bool:
        return self.values == self.solution

    def has_conflict(self, r: int, c: int) -> bool:
        i = idx(r, c)
        val = self.values[i]
        if not val:
            return False
        for k in range(9):
            if k != c and self.values[idx(r, k)] == val:
                return True
            if k != r and self.values[idx(k, c)] == val:
                return True
        if self.check_boxes:
            region = self.regions[i]
            for k in range(CELLS):
                if k != i and self.regions[k] == region and self.values[k] == val:
                    return True
        if self.use_diagonals:
            if r == c:
                for k in range(9):
                    if k != r and self.values[idx(k, k)] == val:
                        return True
            if r + c == 8:
                for k in range(9):
                    if k != r and self.values[idx(k, 8 - k)] == val:
                        return True
        if self.inequalities:
            for other, must_be_greater in self.inequalities.get(i, []):
                other_val = self.values[other]
                if not other_val:
                    continue
                if must_be_greater and not (val > other_val):
                    return True
                if not must_be_greater and not (val < other_val):
                    return True
        return False

    def _push_history(self) -> None:
        self._history.append((list(self.values), [set(s) for s in self.notes]))

    @property
    def can_undo(self) -> bool:
        return bool(self._history)

    def undo(self) -> None:
        if self._history:
            self.values, self.notes = self._history.pop()

    def input_digit(self, i: int, d: int, note_mode: bool) -> None:
        if self.is_given(i) or self.won:
            return
        self._push_history()
        if note_mode:
            if self.values[i] == 0:
                (self.notes[i].discard if d in self.notes[i] else self.notes[i].add)(d)
        else:
            self.values[i] = d
            self.notes[i].clear()
        if self.is_solved():
            self.won = True

    def erase(self, i: int) -> None:
        if self.is_given(i) or self.won:
            return
        self._push_history()
        self.values[i] = 0
        self.notes[i].clear()

    def hint(self, i: int) -> None:
        if self.is_given(i) or self.won:
            return
        self._push_history()
        self.values[i] = self.solution[i]
        self.notes[i].clear()
        if self.is_solved():
            self.won = True

    def inequality_symbol(self, a: int, b: int) -> str | None:
        if not self.inequalities:
            return None
        for other, must_be_greater in self.inequalities.get(a, []):
            if other == b:
                return ">" if must_be_greater else "<"
        return None
