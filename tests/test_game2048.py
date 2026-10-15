from tui_games.games.game2048 import Board2048, _compress_merge


def test_compress_merge_basic_cases():
    assert _compress_merge([2, 2, 0, 0]) == ([4, 0, 0, 0], 4, True)
    assert _compress_merge([2, 0, 2, 2]) == ([4, 2, 0, 0], 4, True)
    assert _compress_merge([4, 2, 2, 4]) == ([4, 4, 4, 0], 4, True)  # no cascading re-merge
    assert _compress_merge([0, 0, 0, 0]) == ([0, 0, 0, 0], 0, False)
    assert _compress_merge([2, 4, 8, 16]) == ([2, 4, 8, 16], 0, False)  # already fully compressed


def test_new_board_has_exactly_two_tiles():
    b = Board2048()
    tiles = [v for row in b.grid for v in row if v]
    assert len(tiles) == 2
    assert all(v in (2, 4) for v in tiles)


def test_move_left_slides_and_merges_a_row():
    b = Board2048()
    b.grid = [[2, 2, 4, 4], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    moved = b.move("h")
    assert moved
    assert b.grid[0][:2] == [4, 8]
    assert b.score == 12


def test_move_up_slides_a_column():
    b = Board2048()
    b.grid = [[2, 0, 0, 0], [2, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    b.move("k")
    assert b.grid[0][0] == 4


def test_move_that_changes_nothing_reports_not_moved_and_does_not_spawn():
    b = Board2048()
    b.grid = [[2, 4, 8, 16], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    before = [row[:] for row in b.grid]
    moved = b.move("h")  # already fully compressed left, nothing to merge
    assert not moved
    assert b.grid == before


def test_game_over_detection():
    b = Board2048()
    b.grid = [[2, 4, 2, 4], [4, 2, 4, 2], [2, 4, 2, 4], [4, 2, 4, 2]]  # full, no adjacent equal
    assert b.is_game_over()
    b.grid[0][0] = 4  # now (0,0)==(0,... no; make an adjacent equal pair instead
    b.grid[0] = [4, 4, 2, 4]
    assert not b.is_game_over()


def test_reaching_2048_sets_won():
    b = Board2048()
    b.grid = [[1024, 1024, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    b.move("h")
    assert b.won
