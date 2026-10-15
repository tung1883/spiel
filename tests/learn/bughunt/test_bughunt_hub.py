import pytest

from src import config
from src.app import GamesApp
from src.learn.bughunt.levels import LEVELS


@pytest.mark.asyncio
async def test_playthrough_menu_to_bughunt_level_and_back(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "_PATH", tmp_path / "config.json")
    app = GamesApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.press("down", "down", "down", "down", "down", "down")  # Menu -> Learn to Code
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("down", "down", "down", "down")  # Hub: regex, git, shell, sql, bughunt
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("enter")  # BugHuntRegionMenu -> first level ("Sum to N", tier beginner)
        await pilot.pause()

        level = LEVELS[0]
        screen = app.screen
        assert screen.level.id == "1"

        for _ in range(level.bug_line - 1):
            await pilot.press("j")
        await pilot.press("enter")  # accuse the correct line
        await pilot.pause()
        assert screen.phase == "fix"

        screen.fix_text = level.fix
        await pilot.press("enter")  # submit the fix
        await pilot.pause()
        assert screen.phase == "diagnose"

        correct_index = screen.diagnose_choices.index(level.bug_class)
        for _ in range(correct_index):
            await pilot.press("j")
        await pilot.press("enter")  # diagnose correctly
        await pilot.pause()
        assert screen.phase == "done"
        assert screen.diagnose_correct is True

        await pilot.press("enter")  # back to the region menu
        await pilot.pause()
    learn = config.load()["learn"]
    assert learn["levels"]["bughunt:1"]["stars"] == 3
