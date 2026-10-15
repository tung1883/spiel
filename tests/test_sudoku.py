import random

import pytest

from tui_games import config
from tui_games.sudoku import bank, progress
from tui_games.sudoku.engine import SudokuGame, idx


def _rows_cols_boxes_ok(values: list[int]) -> bool:
    for r in range(9):
        if sorted(values[idx(r, c)] for c in range(9)) != list(range(1, 10)):
            return False
    for c in range(9):
        if sorted(values[idx(r, c)] for r in range(9)) != list(range(1, 10)):
            return False
    for br in range(3):
        for bc in range(3):
            cells = [values[idx(br * 3 + r, bc * 3 + c)] for r in range(3) for c in range(3)]
            if sorted(cells) != list(range(1, 10)):
                return False
    return True


@pytest.mark.parametrize("variant", bank.VARIANTS)
@pytest.mark.parametrize("difficulty", bank.DIFFICULTIES)
def test_every_solution_is_a_valid_completed_grid(variant, difficulty):
    size = bank.get_bank_size(variant, difficulty)
    assert size == 100
    # Sampling every solution in every bank is a lot of work for little extra signal beyond the
    # first few - check a handful per bucket, a full sweep for classic (the simplest case).
    indices = range(size) if variant == "classic" and difficulty == "easy" else random.sample(range(size), 5)
    for i in indices:
        data = bank.get_puzzle_at(difficulty, variant, i)
        solution = data["solution"]
        assert all(1 <= v <= 9 for v in solution)
        if variant == "inequality":
            # Futoshiki-style: rows/cols only, no 3x3 box constraint (see bank.py's check_boxes note).
            for r in range(9):
                assert sorted(solution[idx(r, c)] for c in range(9)) == list(range(1, 10))
            for c in range(9):
                assert sorted(solution[idx(r, c)] for r in range(9)) == list(range(1, 10))
        elif variant != "jigsaw":
            assert _rows_cols_boxes_ok(solution)
        else:
            # jigsaw: rows/cols still 1-9, but boxes are the puzzle's own (irregular) regions.
            for r in range(9):
                assert sorted(solution[idx(r, c)] for c in range(9)) == list(range(1, 10))
            for c in range(9):
                assert sorted(solution[idx(r, c)] for r in range(9)) == list(range(1, 10))
            for region in set(data["regions"]):
                cells = [solution[k] for k in range(81) if data["regions"][k] == region]
                assert sorted(cells) == list(range(1, 10))
        # every given clue in the puzzle must match the solution at that cell
        puzzle = data["puzzle"]
        assert all(p == 0 or p == s for p, s in zip(puzzle, solution))
        if data["inequalities"]:
            for a, edges in data["inequalities"].items():
                for b, must_be_greater in edges:
                    ok = (solution[a] > solution[b]) if must_be_greater else (solution[a] < solution[b])
                    assert ok, (variant, difficulty, i, a, b)


def _game(variant="classic", difficulty="easy", index=0) -> SudokuGame:
    data = bank.get_puzzle_at(difficulty, variant, index)
    return SudokuGame(index=index, puzzle=data["puzzle"], solution=data["solution"], regions=data["regions"],
                       check_boxes=data["check_boxes"], use_diagonals=data["use_diagonals"],
                       inequalities=data["inequalities"])


def test_fresh_game_matches_puzzle_and_is_not_solved():
    g = _game()
    assert g.values == g.puzzle
    assert not g.is_solved()


def test_given_cells_are_not_editable():
    g = _game()
    given = next(i for i, p in enumerate(g.puzzle) if p != 0)
    g.input_digit(given, 5, note_mode=False)
    assert g.values[given] == g.puzzle[given]


def test_input_digit_and_undo_roundtrip():
    g = _game()
    empty = next(i for i, p in enumerate(g.puzzle) if p == 0)
    g.input_digit(empty, 7, note_mode=False)
    assert g.values[empty] == 7
    assert g.can_undo
    g.undo()
    assert g.values[empty] == 0
    assert not g.can_undo


def test_note_mode_toggles_candidate_without_setting_value():
    g = _game()
    empty = next(i for i, p in enumerate(g.puzzle) if p == 0)
    g.input_digit(empty, 3, note_mode=True)
    assert g.values[empty] == 0
    assert 3 in g.notes[empty]
    g.input_digit(empty, 3, note_mode=True)  # toggles off
    assert 3 not in g.notes[empty]


def test_solving_the_whole_puzzle_sets_won():
    g = _game()
    for i, s in enumerate(g.solution):
        if g.puzzle[i] == 0:
            g.input_digit(i, s, note_mode=False)
    assert g.is_solved()
    assert g.won


def test_hint_fills_the_correct_value():
    g = _game()
    empty = next(i for i, p in enumerate(g.puzzle) if p == 0)
    g.hint(empty)
    assert g.values[empty] == g.solution[empty]


def test_conflict_detected_on_duplicate_in_row():
    g = _game()
    r = 0
    existing = next(v for v in (g.values[idx(r, c)] for c in range(9)) if v)
    empty_in_row = next(c for c in range(9) if g.puzzle[idx(r, c)] == 0)
    g.input_digit(idx(r, empty_in_row), existing, note_mode=False)
    assert g.has_conflict(r, empty_in_row)


def test_inequality_conflict_detected():
    data = bank.get_puzzle_at("extreme", "inequality", 0)
    g = SudokuGame(index=0, puzzle=data["puzzle"], solution=data["solution"], regions=data["regions"],
                   check_boxes=data["check_boxes"], use_diagonals=False, inequalities=data["inequalities"])
    a, edges = next(iter(data["inequalities"].items()))
    b, must_be_greater = edges[0]
    g.values[a] = 1 if must_be_greater else 9  # the smallest/largest possible value - guaranteed to violate
    g.values[b] = 9 if must_be_greater else 1
    assert g.has_conflict(*divmod(a, 9))


def test_progress_persist_and_resume(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "_PATH", tmp_path / "config.json")
    g = _game("classic", "easy", 0)
    empty = next(i for i, p in enumerate(g.puzzle) if p == 0)
    g.input_digit(empty, 4, note_mode=False)
    progress.persist("classic", "easy", g, seconds=42)

    resumed, seconds = progress.load_puzzle("easy", "classic", 0)
    assert resumed.values[empty] == 4
    assert seconds == 42
    assert not resumed.won


def test_best_time_only_improves(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "_PATH", tmp_path / "config.json")
    progress.record_time("classic:easy", 100)
    progress.record_time("classic:easy", 150)  # worse - ignored
    assert progress.load_best_times()["classic:easy"] == 100
    progress.record_time("classic:easy", 80)  # better - kept
    assert progress.load_best_times()["classic:easy"] == 80
