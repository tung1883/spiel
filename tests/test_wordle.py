import asyncio

from textual.app import App

from src import config
from src.games.wordle import WordleGame, WordleScreen, score_guess
from src.games.wordle_words import WORDS


def test_word_pool_valid():
    assert all(len(w) == 5 and w.isalpha() and w.islower() for w in WORDS)
    assert len(WORDS) == len(set(WORDS))


def test_score_basic():
    assert score_guess("crane", "crane") == "ggggg"
    assert score_guess("zzzzz", "crane") == "xxxxx"
    assert score_guess("nacre", "crane") == "yyyyg"


def test_score_duplicates():
    assert score_guess("speed", "abide") == "xxyxy"
    assert score_guess("llama", "hello") == "yyxxx"
    assert score_guess("eerie", "elder") == "gyyxx"


def test_game_flow():
    g = WordleGame("crane")
    assert g.submit("abc") == "need 5 letters"
    assert g.submit("12345") == "letters only"
    for _ in range(5):
        assert g.submit("slate") is None
    assert not g.over
    assert g.submit("crane") is None and g.won
    assert g.submit("crane") == "game over"


def test_win_and_loss():
    g = WordleGame("crane")
    g.submit("slate")
    g.submit("crane")
    assert g.won and g.over
    g = WordleGame("crane")
    for _ in range(6):
        g.submit("slate")
    assert g.over and not g.won


def test_keyboard_best_mark():
    g = WordleGame("crane")
    g.submit("nacre")
    g.submit("crane")
    assert g.keyboard()["c"] == "g"


def test_screen_pilot(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_PATH", tmp_path / "c.json")

    class A(App):
        def on_mount(self):
            self.push_screen(WordleScreen("crane"))

    async def run():
        app = A()
        async with app.run_test() as pilot:
            await pilot.press(*"crane", "enter")
            assert app.screen.game.won

    asyncio.run(run())
    assert config.load()["wordle"]["won"] == 1
