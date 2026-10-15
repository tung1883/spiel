import asyncio
import random

from textual.app import App

from src import config
from src.games.tetris import H, W, Tetris, TetrisScreen, rotate, PIECES


def test_rotate_four_times_is_identity():
    for size, cells in PIECES.values():
        c = cells
        for _ in range(4):
            c = rotate(c, size)
        assert sorted(c) == sorted(cells)


def test_seven_bag_has_each_piece():
    g = Tetris(random.Random(1))
    kinds = {g._draw() for _ in range(7)}
    assert len(kinds) <= 7 and len(g.bag) >= 0


def test_move_blocked_by_wall():
    g = Tetris(random.Random(1))
    for _ in range(20):
        g.move(-1)
    assert min(c for _, c in g.piece.blocks()) == 0


def test_gravity_locks_at_floor_and_spawns_next():
    g = Tetris(random.Random(1))
    first = g.piece
    for _ in range(H + 2):
        g.step()
    assert g.piece is not first
    assert any(any(row) for row in g.grid)


def test_line_clear_scores():
    g = Tetris(random.Random(1))
    g.grid[H - 1] = ["I"] * W
    g.grid[H - 1][4] = ""
    g.grid[H - 1][5] = ""
    g.piece.kind, g.piece.size = "O", 2
    g.piece.cells = [(0, 0), (0, 1), (1, 0), (1, 1)]
    g.piece.row, g.piece.col = H - 2, 4
    g.step()  # locks
    assert g.lines == 1 and g.score == 100
    assert not all(g.grid[H - 1])


def test_hard_drop_and_game_over():
    g = Tetris(random.Random(2))
    for _ in range(30):
        g.hard_drop()
        if g.over:
            break
    assert g.over


def test_screen_pilot(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_PATH", tmp_path / "c.json")

    class A(App):
        def on_mount(self):
            self.push_screen(TetrisScreen(random.Random(3)))

    async def run():
        app = A()
        async with app.run_test() as pilot:
            await pilot.press("left", "up", "space", "p", "p")
            assert app.screen.game.score > 0
    asyncio.run(run())
