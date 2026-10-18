"""Wordle: guess the 5-letter word in 6 tries. Original implementation of the public word-game rules."""
import random

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Static

from .. import config
from ..base import AppScreen
from .wordle_words import WORDS

LENGTH = 5
MAX_TRIES = 6
CORRECT, PRESENT, ABSENT = "g", "y", "x"


def score_guess(guess: str, answer: str) -> str:
    """Per-letter marks: 'g' right spot, 'y' wrong spot, 'x' absent. Greens claim their letter first,
    then yellows use up the remaining copies left to right (so duplicates are never over-marked)."""
    marks = [ABSENT] * LENGTH
    left: dict[str, int] = {}
    for i, (g, a) in enumerate(zip(guess, answer)):
        if g == a:
            marks[i] = CORRECT
        else:
            left[a] = left.get(a, 0) + 1
    for i, g in enumerate(guess):
        if marks[i] == ABSENT and left.get(g, 0) > 0:
            marks[i] = PRESENT
            left[g] -= 1
    return "".join(marks)


class WordleGame:
    def __init__(self, answer: str | None = None):
        self.answer = answer or random.choice(WORDS)
        self.guesses: list[str] = []
        self.marks: list[str] = []

    @property
    def won(self) -> bool:
        return bool(self.guesses) and self.guesses[-1] == self.answer

    @property
    def over(self) -> bool:
        return self.won or len(self.guesses) >= MAX_TRIES

    def submit(self, word: str) -> str | None:
        """Returns an error message, or None when the guess was accepted."""
        word = word.lower()
        if self.over:
            return "game over"
        if len(word) != LENGTH:
            return "need 5 letters"
        if not (word.isalpha() and word.isascii()):
            return "letters only"
        self.guesses.append(word)
        self.marks.append(score_guess(word, self.answer))
        return None

    def keyboard(self) -> dict[str, str]:
        """Best known mark per letter (g beats y beats x)."""
        rank = {ABSENT: 0, PRESENT: 1, CORRECT: 2}
        best: dict[str, str] = {}
        for word, marks in zip(self.guesses, self.marks):
            for ch, m in zip(word, marks):
                if ch not in best or rank[m] > rank[best[ch]]:
                    best[ch] = m
        return best


_STYLE = {CORRECT: "bold white on #538d4e", PRESENT: "bold white on #b59f3b", ABSENT: "bold white on #3a3a3c"}
_KEY_STYLE = {CORRECT: "bold #538d4e", PRESENT: "bold #b59f3b", ABSENT: "dim strike"}
_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")


def record_result(won: bool) -> None:
    cfg = config.load()
    st = cfg.get("wordle", {"played": 0, "won": 0, "streak": 0, "best_streak": 0})
    st["played"] += 1
    if won:
        st["won"] += 1
        st["streak"] += 1
        st["best_streak"] = max(st["best_streak"], st["streak"])
    else:
        st["streak"] = 0
    cfg["wordle"] = st
    config.save(cfg)


class WordleScreen(AppScreen):
    """type letters, enter submits, backspace deletes, ctrl+n = new word, escape = back."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back"), Binding("ctrl+n", "new_game", "New word")]
    CSS = """
    WordleScreen #grid {padding: 1 2 0 2; height: auto;}
    WordleScreen #kb {padding: 1 2 0 2; height: auto;}
    WordleScreen #msg {padding: 1 2 0 2; height: auto;}
    """

    def __init__(self, answer: str | None = None):
        super().__init__()
        self.game = WordleGame(answer)
        self.current = ""
        self.message = ""
        self.recorded = False

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(id="grid")
        yield Static(id="kb")
        yield Static(id="msg")
        yield Footer()

    def on_mount(self) -> None:
        super().on_mount()
        self._draw()

    def action_new_game(self) -> None:
        self.game = WordleGame()
        self.current = ""
        self.message = ""
        self.recorded = False
        self._draw()

    def on_key(self, event: events.Key) -> None:
        key, ch = event.key, event.character
        if self.game.over:
            return
        if key == "enter":
            err = self.game.submit(self.current)
            if err:
                self.message = err
            else:
                self.current = ""
                self.message = ""
                if self.game.over and not self.recorded:
                    self.recorded = True
                    record_result(self.game.won)
        elif key == "backspace":
            self.current = self.current[:-1]
            self.message = ""
        elif ch and len(ch) == 1 and ch.isascii() and ch.isalpha():
            if len(self.current) < LENGTH:
                self.current += ch.lower()
            self.message = ""
        else:
            return
        event.stop()
        self._draw()

    def _draw(self) -> None:
        g = self.game
        grid = Text()
        for r in range(MAX_TRIES):
            if r < len(g.guesses):
                cells = [(c.upper(), _STYLE[m]) for c, m in zip(g.guesses[r], g.marks[r])]
            elif r == len(g.guesses) and not g.over:
                cells = [((self.current[i].upper() if i < len(self.current) else "_"), "bold") for i in range(LENGTH)]
            else:
                cells = [("_", "dim")] * LENGTH
            for ch, style in cells:
                grid.append(f" {ch} ", style=style)
                grid.append(" ")
            grid.append("\n")
        self.query_one("#grid", Static).update(grid)

        best = g.keyboard()
        kb = Text()
        for i, row in enumerate(_ROWS):
            kb.append(" " * i)
            for ch in row:
                kb.append(ch.upper() + " ", style=_KEY_STYLE.get(best.get(ch), ""))
            kb.append("\n")
        self.query_one("#kb", Static).update(kb)

        msg = Text()
        if g.won:
            msg.append(f"solved in {len(g.guesses)}/{MAX_TRIES}!", style="bold green")
        elif g.over:
            msg.append(f"the word was {g.answer.upper()}", style="bold yellow")
        elif self.message:
            msg.append(self.message, style="red")
        else:
            msg.append("type a word, enter to guess", style="dim")
        if g.over:
            st = config.load().get("wordle", {})
            msg.append(
                f"\nplayed {st.get('played', 0)}  won {st.get('won', 0)}  "
                f"streak {st.get('streak', 0)}  best {st.get('best_streak', 0)}\nctrl+n new word   esc back",
                style="dim",
            )
        self.query_one("#msg", Static).update(msg)
