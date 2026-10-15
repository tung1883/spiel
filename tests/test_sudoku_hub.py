import pytest

from src import config
from src.app import GamesApp
from src.sudoku import bank


@pytest.mark.asyncio
async def test_playthrough_menu_to_sudoku_solve_and_back(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "_PATH", tmp_path / "config.json")
    app = GamesApp()
    async with app.run_test(size=(100, 50)) as pilot:
        await pilot.press("down", "down", "down")  # Menu: TypeRacer, Chess, Minesweeper, Sudoku
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("enter")  # SudokuMenu -> puzzle #1 (classic/medium, the default)
        await pilot.pause()

        screen = app.screen
        g = screen.game
        # Solve the whole puzzle through the real screen (one keypress per empty cell), proving the
        # input/navigation/win-detection path end to end rather than poking the engine directly.
        for i, s in enumerate(g.solution):
            if g.puzzle[i] == 0:
                screen.selected = i
                await pilot.press(str(s))
        await pilot.pause()
        assert screen.game.won

        await pilot.press("q")  # back to the puzzle picker
        await pilot.pause()

    level = bank.DIFF_LEVELS["medium"]
    saved = config.load()["sudoku"]["progress"][f"classic:{level}"]["0"]
    assert saved["status"] == "done"
    assert config.load()["sudoku"]["best_times"]["classic:medium"] >= 0
