from src.games.game2048 import Board2048, _compress_merge


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


def _back_test(key, expect_back=True):
    import asyncio
    from textual.app import App
    from textual.screen import Screen
    from src.games.game2048 import Game2048Screen

    quit_called = []

    class Base(Screen):
        BINDINGS = [("q", "app.quit", "Quit")]

    class A(App):
        def on_mount(self):
            self.push_screen(Base())
            self.push_screen(Game2048Screen())

        async def action_quit(self):
            quit_called.append(1)

    async def run():
        app = A()
        async with app.run_test() as pilot:
            await pilot.press(key)
            await pilot.pause()
            assert isinstance(app.screen, Base) == expect_back
    asyncio.run(run())
    assert not quit_called


def test_q_does_nothing():
    _back_test("q", expect_back=False)


def test_escape_goes_back():
    _back_test("escape")


def test_move_records_tile_paths():
    b = Board2048()
    b.grid = [[0, 2, 0, 2], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    b.move("h")
    assert sorted(b.last_moves) == [(2, (0, 1), (0, 0)), (2, (0, 3), (0, 0))]  # both slide into the same cell
    b.grid = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [4, 0, 0, 0]]
    b.move("k")
    assert (4, (3, 0), (0, 0)) in b.last_moves
    b.grid = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 8, 0]]
    b.move("l")
    assert (8, (3, 2), (3, 3)) in b.last_moves


def test_render_motion_interpolates():
    from src.games.game2048 import BOARD_H, BOARD_W, render_board, render_motion
    b = Board2048()
    b.grid = [[0, 0, 0, 2], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    b.move("h")
    start, mid, end = (render_motion(b, t).plain for t in (0.0, 0.5, 1.0))
    assert len({start, mid, end}) == 3
    assert all(len(s.split(chr(10))) == BOARD_H and len(s.split(chr(10))[0]) == BOARD_W for s in (start, mid, end))
    assert len(render_board(b.grid).plain.split(chr(10))) == BOARD_H


def test_screen_animates_then_settles(tmp_path, monkeypatch):
    import asyncio
    from textual.app import App
    from src import config
    from src.games.game2048 import FRAMES, Game2048Screen

    monkeypatch.setattr(config, "_PATH", tmp_path / "c.json")
    monkeypatch.setattr("src.games.game2048.FRAME_DT", 30.0)  # timer never fires; frames stepped by hand

    class A(App):
        def on_mount(self):
            self.push_screen(Game2048Screen())

    async def run():
        app = A()
        async with app.run_test() as pilot:
            scr = app.screen
            scr.board.grid = [[0, 0, 0, 2], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
            await pilot.press("left")
            assert scr.animating
            await pilot.press("right")  # interrupts, starts a fresh animation
            assert scr.animating
            for _ in range(FRAMES - 1):
                scr._step_anim()
                assert scr.animating
            scr._step_anim()
            assert not scr.animating
    asyncio.run(run())
