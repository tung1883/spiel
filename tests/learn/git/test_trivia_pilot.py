import pytest

from tui_games import config
from tui_games.app import GamesApp
from tui_games.learn.git.screens import TriviaScreen


@pytest.mark.asyncio
async def test_playthrough_menu_to_git_trivia_round_and_back(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "_PATH", tmp_path / "config.json")
    app = GamesApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.press("down", "down", "down", "down", "down")  # -> Learn to Code
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("down")  # Hub: Pattern Marsh, Branch Forest
        await pilot.press("enter")
        await pilot.pause()
        # GitRegionMenu: 18 levels then Trivia - press "end" then up won't exist, just navigate down
        # past every level entry instead of guessing the count.
        screen = app.screen
        option_list = screen.query_one("#levels")
        option_list.highlighted = option_list.option_count - 1  # the trivia entry is always last
        await pilot.press("enter")
        await pilot.pause()

        screen = app.screen
        assert isinstance(screen, TriviaScreen)
        for _ in range(len(screen.questions)):
            await pilot.press("1")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
        assert screen.done
        await pilot.press("escape")
        await pilot.pause()

    assert config.load()["git_trivia_best"] >= 0
