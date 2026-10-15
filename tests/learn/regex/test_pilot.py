import pytest

from src import config
from src.app import GamesApp


@pytest.mark.asyncio
async def test_playthrough_menu_to_regex_level_and_back(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "_PATH", tmp_path / "config.json")
    app = GamesApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.press("down", "down", "down", "down", "down")  # Menu -> Learn to Code
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("enter")  # Hub: Pattern Marsh (first region)
        await pilot.pause()
        await pilot.press("enter")  # RegexRegionMenu -> level 1 "Literals" (reference "cat")
        await pilot.pause()
        for ch in "cat":
            await pilot.press(ch)
        await pilot.press("enter")  # force an immediate check
        await pilot.pause()
        screen = app.screen
        assert screen.done
        await pilot.press("enter")  # leave back to the region menu
        await pilot.pause()
    learn = config.load()["learn"]
    assert learn["levels"]["regex:literal"]["stars"] == 3
