import pytest

from src import config
from src.app import GamesApp
from src.learn.git.levels import LEVELS
from src.learn.git.screens import GitLevelScreen


@pytest.mark.asyncio
async def test_playthrough_menu_to_branch_forest_level_and_back(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "_PATH", tmp_path / "config.json")
    app = GamesApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.press(*["down"] * 7)  # Menu -> Learn to Code
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("down")  # Hub: Pattern Marsh, Branch Forest
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("enter")  # GitRegionMenu -> Level 1: First branch
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, GitLevelScreen)
        for line in LEVELS[0].solution:
            screen.query_one("#cmd").value = line
            await pilot.press("enter")
            await pilot.pause()
        assert screen.run.done
        await pilot.press("escape")  # back to the region menu
        await pilot.pause()
    learn = config.load()["learn"]
    assert learn["levels"]["git:0"]["stars"] == 3
