import pytest
from textual.widgets import DataTable, TextArea

from src import config
from src.app import GamesApp
from src.learn.sql.levels import DRILLS


@pytest.mark.asyncio
async def test_playthrough_menu_to_sql_drill_and_back(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "_PATH", tmp_path / "config.json")
    app = GamesApp()
    async with app.run_test(size=(120, 45)) as pilot:
        await pilot.press(*["down"] * 7)  # Menu -> Learn to Code
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("down", "down", "down")  # Hub: regex, git, shell, sql
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("down", "down", "down")  # SqlRegionMenu: 3 cases, then drill 1 ("select-where")
        await pilot.press("enter")
        await pilot.pause()

        screen = app.screen
        drill = DRILLS[0]
        assert drill.id == "select-where"
        screen.query_one("#sql", TextArea).text = drill.reference_sql
        await pilot.press("f5")
        await pilot.pause()

        assert screen.done
        table = screen.query_one("#results", DataTable)
        assert table.row_count == 1  # exactly carol is an admin
        await pilot.press("escape")  # back to the region menu
        await pilot.pause()

    learn = config.load()["learn"]
    assert learn["levels"]["sql:select-where"]["stars"] == 3
