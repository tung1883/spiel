import pytest

from src import config
from src.app import GamesApp


@pytest.mark.asyncio
async def test_playthrough_menu_to_shell_mission_and_back(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "_PATH", tmp_path / "config.json")
    app = GamesApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.press("down", "down", "down", "down", "down", "down")  # Menu -> Learn to Code
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("down", "down")  # Hub: Regex, Git, Shell
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("enter")  # ShellRegionMenu -> Mission 1: Into the Caverns
        await pilot.pause()
        for ch in "cd reports/2024":
            await pilot.press(ch)
        await pilot.press("enter")
        await pilot.pause()
        screen = app.screen
        assert screen.run.done
        await pilot.press("enter")  # leave back to the mission list
        await pilot.pause()
    learn = config.load()["learn"]
    assert learn["levels"]["shell:0"]["stars"] == 3
