import pytest
from textual import events

from src import config
from src.app import GamesApp
from src.learn.codetype.levels import BOSS_SNIPPETS, SNIPPETS
from src.learn.codetype.screens import (
    BossRaceScreen,
    CodeRaceScreen,
    CodeTypeRegionMenu,
    ExplainQuizScreen,
    RecallRaceScreen,
    SnippetPickScreen,
    SymbolsDrillScreen,
)
from src.typeracer import analytics


def _use_tmp_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "_PATH", tmp_path / "config.json")
    monkeypatch.setattr(analytics, "HISTORY", tmp_path / "typeracer-history.json")
    monkeypatch.setattr(analytics, "GHOSTS", tmp_path / "typeracer-ghosts.json")


def _type(screen, text: str) -> None:
    for ch in text:
        if ch == "\n":
            screen.on_key(events.Key("enter", None))
        else:
            screen.on_key(events.Key(ch, ch))


@pytest.mark.asyncio
async def test_auto_indent_skips_leading_spaces_for_free(monkeypatch, tmp_path):
    _use_tmp_storage(monkeypatch, tmp_path)
    snippet = next(s for s in SNIPPETS if s.id == "py3")  # has an indented body
    app = GamesApp()
    async with app.run_test(size=(100, 40)) as pilot:
        screen = CodeRaceScreen(snippet)
        app.push_screen(screen)
        await pilot.pause()
        code = screen.snippet.code
        up_to_colon = code.index("class Point:") + len("class Point:\n")
        _type(screen, code[:up_to_colon])
        await pilot.pause()
        # the next line is "    x: float" - the 4 leading spaces should be skipped for free
        assert code[screen.pos] == "x"
        assert screen.pos == code.index("x: float")


@pytest.mark.asyncio
async def test_playthrough_menu_to_codetype_snippet_mode_and_back(monkeypatch, tmp_path):
    _use_tmp_storage(monkeypatch, tmp_path)
    app = GamesApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.press("down", "down", "down", "down", "down")  # Menu -> Learn to Code
        await pilot.press("enter")
        await pilot.pause()
        # Hub regions: regex, git, shell, sql, bughunt, codetype
        await pilot.press("down", "down", "down", "down", "down")
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, CodeTypeRegionMenu)
        await pilot.press("enter")  # "Snippet practice" (first mode)
        await pilot.pause()
        assert isinstance(app.screen, SnippetPickScreen)
        await pilot.press("enter")  # first snippet in the list
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, CodeRaceScreen)
        _type(screen, screen.snippet.code)
        await pilot.pause()
        assert screen.done
        await pilot.press("enter")  # back to the snippet list
        await pilot.pause()
    learn = config.load()["learn"]
    key = f"codetype:{SNIPPETS[0].id}"
    assert key in learn["levels"]


@pytest.mark.asyncio
async def test_recall_mode_hides_code_after_memorize_phase_and_masks_untyped_tail(monkeypatch, tmp_path):
    _use_tmp_storage(monkeypatch, tmp_path)
    snippet = SNIPPETS[0]
    app = GamesApp()
    async with app.run_test(size=(100, 40)) as pilot:
        screen = RecallRaceScreen(snippet)
        app.push_screen(screen)
        await pilot.pause()
        assert screen.revealing
        screen._hide()  # don't wait on the real timer in a test
        await pilot.pause()
        assert not screen.revealing
        rendered = screen._code_text().plain
        # position 0 is the real cursor char (code[0]); everything after it must be masked to
        # '.' (or a preserved space/newline) - never a leaked real character from the snippet.
        after_cursor = rendered[1:]
        assert all(c in (".", " ", "\n") for c in after_cursor)


@pytest.mark.asyncio
async def test_explain_quiz_offers_the_real_note_plus_distractors_then_leads_to_typing(monkeypatch, tmp_path):
    _use_tmp_storage(monkeypatch, tmp_path)
    snippet = SNIPPETS[0]
    app = GamesApp()
    async with app.run_test(size=(100, 40)) as pilot:
        screen = ExplainQuizScreen(snippet)
        app.push_screen(screen)
        await pilot.pause()
        assert snippet.note in screen.options
        assert len(screen.options) == 4
        await pilot.press("enter")  # answer (whichever is highlighted)
        await pilot.pause()
        assert screen.answered
        await pilot.press("enter")  # proceed to typing
        await pilot.pause()
        assert isinstance(app.screen, CodeRaceScreen)
        assert app.screen.snippet is snippet


@pytest.mark.asyncio
async def test_boss_mode_fails_on_timeout(monkeypatch, tmp_path):
    _use_tmp_storage(monkeypatch, tmp_path)
    snippet = BOSS_SNIPPETS[0]
    app = GamesApp()
    async with app.run_test(size=(100, 40)) as pilot:
        screen = BossRaceScreen(snippet)
        app.push_screen(screen)
        await pilot.pause()
        screen.on_key(events.Key(snippet.code[0], snippet.code[0]))  # start the clock
        await pilot.pause()
        screen.time_limit_s = 0.0  # force an immediate timeout without a real sleep
        screen.on_key(events.Key(snippet.code[1] if len(snippet.code) > 1 else " ",
                                  snippet.code[1] if len(snippet.code) > 1 else " "))
        await pilot.pause()
        assert screen.done
        assert screen.failed
        assert "Time's up" in screen.report


@pytest.mark.asyncio
async def test_boss_mode_completes_normally_within_time(monkeypatch, tmp_path):
    _use_tmp_storage(monkeypatch, tmp_path)
    snippet = BOSS_SNIPPETS[0]
    app = GamesApp()
    async with app.run_test(size=(100, 40)) as pilot:
        screen = BossRaceScreen(snippet)
        app.push_screen(screen)
        await pilot.pause()
        _type(screen, snippet.code)
        await pilot.pause()
        assert screen.done
        assert not screen.failed


@pytest.mark.asyncio
async def test_symbols_drill_reachable_after_a_finished_race_with_mistakes(monkeypatch, tmp_path):
    _use_tmp_storage(monkeypatch, tmp_path)
    snippet = next(s for s in SNIPPETS if "(" in s.code)
    app = GamesApp()
    async with app.run_test(size=(100, 40)) as pilot:
        screen = CodeRaceScreen(snippet)
        app.push_screen(screen)
        await pilot.pause()
        # type one deliberate mistake on the first character, then the real snippet
        wrong = "z" if snippet.code[0] != "z" else "y"
        screen.on_key(events.Key(wrong, wrong))
        _type(screen, snippet.code)
        await pilot.pause()
        assert screen.done
        assert screen.stats.missed
        screen.on_key(events.Key("s", "s"))
        await pilot.pause()
        assert isinstance(app.screen, SymbolsDrillScreen)
