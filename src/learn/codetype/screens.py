"""Typing Forge screens: a mode picker, a snippet picker per mode, and the race screens themselves.
Reuses typeracer's RaceStats/ghost/history machinery (src/typeracer/analytics.py) rather than
duplicating it - the whole snippet is passed to RaceStats as a single "word" so total_chars matches
len(code) exactly (newlines included), which keeps the existing WPM/accuracy/ghost math correct
unmodified.

Modes: Snippet (plain typing, CodeRaceScreen), Recall (memorize then type blind,
RecallRaceScreen), Explain-then-type (a one-line quiz on the snippet's `note` first,
ExplainQuizScreen -> CodeRaceScreen), Boss (a tier="expert" program under a visible time limit,
BossRaceScreen), and a post-run Symbols drill (SymbolsDrillScreen) offered from the result line of
any finished race, built from whichever characters RaceStats.missed recorded."""
import random
import time

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, OptionList, Static
from textual.widgets.option_list import Option

from ...base import AppScreen
from .. import progress
from .levels import BOSS_SNIPPETS, SNIPPETS, Snippet, distractor_notes


def _now_ms() -> float:
    return time.time() * 1000


# ---- menu ---------------------------------------------------------------------------------
class CodeTypeRegionMenu(AppScreen):
    BINDINGS = [Binding("escape,q", "app.pop_screen", "Back")]
    CSS = "CodeTypeRegionMenu #intro {padding: 1 2;}"

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static("Typing Forge - the bard races the clock.", id="intro")
        yield OptionList(
            Option("Snippet practice - type a snippet straight through", id="mode:snippet"),
            Option("Recall - memorize it, then type it blind", id="mode:recall"),
            Option("Explain-then-type - answer what it does, then type it", id="mode:explain"),
            Option("Boss fights - a longer program under a time limit", id="mode:boss"),
            id="modes",
        )
        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        mode = event.option.id.split(":")[1]
        self.app.push_screen(SnippetPickScreen(mode))


class SnippetPickScreen(AppScreen):
    """Pick a snippet for the given mode - Boss only offers tier="expert" material."""

    BINDINGS = [Binding("escape,q", "app.pop_screen", "Back")]
    CSS = "SnippetPickScreen #intro {padding: 1 2;}"

    def __init__(self, mode: str):
        super().__init__()
        self.mode = mode
        self.pool = BOSS_SNIPPETS if mode == "boss" else SNIPPETS

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(f"Mode: {self.mode}", id="intro")
        options = [Option(f"{s.lang:<10} {s.title}", id=f"snip:{i}") for i, s in enumerate(self.pool)]
        yield OptionList(*options, id="snippets")
        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        index = int(event.option.id.split(":")[1])
        snippet = self.pool[index]
        if self.mode == "snippet":
            self.app.push_screen(CodeRaceScreen(snippet))
        elif self.mode == "recall":
            self.app.push_screen(RecallRaceScreen(snippet))
        elif self.mode == "explain":
            self.app.push_screen(ExplainQuizScreen(snippet))
        elif self.mode == "boss":
            self.app.push_screen(BossRaceScreen(snippet))


class ExplainQuizScreen(AppScreen):
    """One-line "what does this do?" quiz on the snippet's `note` before typing it."""

    BINDINGS = [Binding("escape,q", "app.pop_screen", "Back")]
    CSS = "ExplainQuizScreen #question {padding: 1 2; height: auto;}"

    def __init__(self, snippet: Snippet):
        super().__init__()
        self.snippet = snippet
        options = [snippet.note] + distractor_notes(snippet, 3)
        random.shuffle(options)
        self.options = options
        self.answered = False

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(id="question")
        yield OptionList(*(Option(o, id=str(i)) for i, o in enumerate(self.options)), id="choices")
        yield Footer()

    def on_mount(self) -> None:
        super().on_mount()
        self.query_one("#question", Static).update(
            Text(f"What does this {self.snippet.lang} snippet do?\n", style="bold")
            + Text(self.snippet.code, style="dim")
        )

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if self.answered:
            self.app.push_screen(CodeRaceScreen(self.snippet))
            return
        self.answered = True
        picked = self.options[int(event.option.id)]
        verdict = "Correct!" if picked == self.snippet.note else f"Not quite - it's: {self.snippet.note}"
        self.query_one("#question", Static).update(
            Text(f"What does this {self.snippet.lang} snippet do?\n", style="bold")
            + Text(self.snippet.code + "\n\n", style="dim")
            + Text(verdict + "  (pick any option to start typing)", style="bold")
        )


# ---- plain Snippet mode ---------------------------------------------------------------------
class CodeRaceScreen(AppScreen):
    """Character-accurate code typing. Enter types a newline; indentation on the next line is free
    (auto-skipped), like a code-typing mode that doesn't make you re-type leading whitespace.
    escape leaves, ctrl+r restarts, Enter leaves once finished, s offers a Symbols drill on your
    missed characters once finished."""

    BINDINGS = [Binding("ctrl+r", "restart", "Restart")]
    CSS = """
    CodeRaceScreen #info {padding: 1 2 0 2; height: auto;}
    CodeRaceScreen #code {padding: 1 2; height: auto;}
    CodeRaceScreen #status {padding: 1 2; height: auto;}
    """

    def __init__(self, snippet: Snippet, mode_label: str = "codetype"):
        super().__init__()
        self.snippet = snippet
        self.mode_label = mode_label
        self._reset()

    def _reset(self) -> None:
        from ...typeracer.analytics import RaceStats, load_ghost

        self.pos = 0
        self.started = False
        self.done = False
        self.saved = False
        self.report = ""
        self.stats = RaceStats([self.snippet.code])
        self.ghost = load_ghost(self.snippet.code)

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(id="info")
        yield Static(id="code")
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        super().on_mount()
        self._draw()

    def action_restart(self) -> None:
        self._reset()
        self._draw()

    def on_key(self, event: events.Key) -> None:
        key, ch = event.key, event.character
        if key == "ctrl+r":
            return  # binding
        if self.done:
            event.stop()
            if key == "enter":
                self.app.pop_screen()
            elif ch == "s":
                self.app.push_screen(SymbolsDrillScreen(self.stats.missed))
            return
        if key == "escape":
            event.stop()
            self.app.pop_screen()
            return
        event.stop()
        code = self.snippet.code
        if self.pos >= len(code):
            return
        expected = code[self.pos]
        now = _now_ms()
        if expected == "\n":
            if key != "enter":
                return
            matched = True
        else:
            if not ch or not ch.isprintable():
                return
            matched = ch == expected
        if not self.started:
            self.started = True
        self.stats.key(now, matched, expected)
        if matched:
            self.pos += 1
            if expected == "\n":  # auto-indent: skip the next line's leading spaces for free
                while self.pos < len(code) and code[self.pos] == " ":
                    self.pos += 1
            self.stats.progress(now, self.pos)
            if self.pos >= len(code):
                self._finish(now)
        self._draw()

    def _finish(self, now: float) -> None:
        from ...typeracer.analytics import save_ghost, save_result

        self.done = True
        self.stats.finish(now)
        mode = f"{self.mode_label}:{self.snippet.lang}"
        self.report = self.stats.report(mode) + self._ghost_verdict()
        save_result(mode, self.stats)
        save_ghost(self.snippet.code, self.stats)
        if not self.saved:
            self.saved = True
            elapsed_s = max(1, round(self.stats.elapsed_min(now) * 60))
            par_s = max(1, round(len(self.snippet.code) / 5 / 40 * 60))  # par pace: 40 wpm
            progress.record(self.mode_label, self.snippet.id, elapsed_s, par_s)

    def _ghost_verdict(self) -> str:
        mine = self.stats.net_wpm(self.stats.total_chars)
        if not self.ghost:
            return "\nghost: first run on this snippet saved"
        diff = mine - self.ghost["wpm"]
        word = "beat" if diff > 0 else "lost to"
        return f"\nghost: you {word} your best by {abs(diff):.1f} wpm (best was {self.ghost['wpm']:.0f})"

    def _code_text(self) -> Text:
        """Overridable: how the code panel renders. Recall mode masks the untyped tail."""
        accent = self.app.theme_variables.get("primary", "#0178d4")
        code = self.snippet.code
        buf = Text()
        buf.append(code[:self.pos], style="green")
        if self.pos < len(code):
            buf.append(code[self.pos], style=f"bold reverse {accent}")
            buf.append(code[self.pos + 1:], style="dim")
        return buf

    def _draw(self) -> None:
        info = Text(f"{self.snippet.title} ({self.snippet.lang})\n", style="bold")
        info.append(self.snippet.note, style="dim")
        self.query_one("#info", Static).update(info)
        self.query_one("#code", Static).update(self._code_text())

        status = self.query_one("#status", Static)
        if self.done:
            extra = "   s = drill your missed keys" if self.stats.missed else ""
            status.update(self.report + f"\n\nEnter = back to the list{extra}")
        else:
            live = self.stats.live_line(self.pos, _now_ms()) if self.started else "0 wpm"
            status.update(Text(f"{live}\nescape leave   ctrl+r restart", style="dim"))


# ---- Recall mode: memorize, then type blind ------------------------------------------------
class RecallRaceScreen(CodeRaceScreen):
    """Shows the snippet for a few seconds, then hides it (masking the untyped tail with '.') and
    has the player retype it from memory. Scored through the same RaceStats pipeline."""

    REVEAL_PER_CHAR = 0.06  # seconds of reveal per character, plus a floor/ceiling below
    REVEAL_MIN = 4.0
    REVEAL_MAX = 18.0

    def __init__(self, snippet: Snippet):
        super().__init__(snippet, mode_label="codetype:recall")

    def _reset(self) -> None:
        super()._reset()
        self.revealing = True
        seconds = max(self.REVEAL_MIN, min(self.REVEAL_MAX, len(self.snippet.code) * self.REVEAL_PER_CHAR))
        self.reveal_deadline = _now_ms() + seconds * 1000
        self._hide_timer = self.set_timer(seconds, self._hide)

    def _hide(self) -> None:
        self.revealing = False
        self._draw()

    def action_restart(self) -> None:
        try:
            self._hide_timer.stop()
        except Exception:
            pass
        self._reset()
        self._draw()

    def on_key(self, event: events.Key) -> None:
        if self.revealing and event.key not in ("escape", "ctrl+r"):
            event.stop()  # ignore typing during the memorize phase
            return
        super().on_key(event)

    def _code_text(self) -> Text:
        if self.revealing:
            remaining = max(0, (self.reveal_deadline - _now_ms()) / 1000)
            txt = Text(self.snippet.code, style="dim")
            txt.append(f"\n\nmemorize... ({remaining:.0f}s)", style="bold yellow")
            return txt
        code = self.snippet.code
        accent = self.app.theme_variables.get("primary", "#0178d4")
        buf = Text()
        buf.append(code[:self.pos], style="green")
        if self.pos < len(code):
            buf.append(code[self.pos], style=f"bold reverse {accent}")
            masked = "".join(ch if ch in ("\n", " ") else "." for ch in code[self.pos + 1:])
            buf.append(masked, style="dim")
        return buf


# ---- Boss mode: a longer program under a visible time limit ---------------------------------
class BossRaceScreen(CodeRaceScreen):
    """A tier="expert" program, same typing mechanics as plain Snippet mode, but with a visible
    countdown; running out of time ends the attempt as a loss rather than a result."""

    PACE_WPM = 35  # slower par pace than plain snippets, since boss programs are longer/harder
    SLACK = 1.6  # the time budget is this much longer than par, not a tight speedrun

    def __init__(self, snippet: Snippet):
        super().__init__(snippet, mode_label="codetype:boss")

    def _reset(self) -> None:
        super()._reset()
        par_s = len(self.snippet.code) / 5 / self.PACE_WPM * 60
        self.time_limit_s = max(20.0, par_s * self.SLACK)
        self.failed = False

    def on_key(self, event: events.Key) -> None:
        if not self.done and self.started and not self.failed:
            elapsed = (_now_ms() - self.stats.start) / 1000
            if elapsed > self.time_limit_s:
                self.failed = True
                self.done = True
                self.report = f"Time's up! {self.pos}/{len(self.snippet.code)} characters typed."
        super().on_key(event)

    def _draw(self) -> None:
        info = Text(f"{self.snippet.title} ({self.snippet.lang}) - BOSS\n", style="bold")
        info.append(self.snippet.note, style="dim")
        self.query_one("#info", Static).update(info)
        self.query_one("#code", Static).update(self._code_text())

        status = self.query_one("#status", Static)
        if self.done:
            extra = "   s = drill your missed keys" if self.stats.missed else ""
            status.update(self.report + f"\n\nEnter = back to the list{extra}")
        else:
            live = self.stats.live_line(self.pos, _now_ms()) if self.started else "0 wpm"
            remaining = self.time_limit_s
            if self.started:
                remaining = max(0, self.time_limit_s - (_now_ms() - self.stats.start) / 1000)
            text = Text(f"{live}\nescape leave   ctrl+r restart", style="dim")
            text.append(f"\ntime left: {remaining:.0f}s", style="bold red")
            status.update(text)


# ---- Symbols drill: practice whatever characters you just missed -----------------------------
class SymbolsDrillScreen(AppScreen):
    """A short follow-up drill built from the characters a finished race's RaceStats.missed
    recorded most often - adaptive-lite, no persistent per-player heatmap, just "what you just
    got wrong, right now"."""

    BINDINGS = [Binding("escape,q", "app.pop_screen", "Back")]
    CSS = """
    SymbolsDrillScreen #info {padding: 1 2 0 2; height: auto;}
    SymbolsDrillScreen #code {padding: 1 2; height: auto;}
    SymbolsDrillScreen #status {padding: 1 2; height: auto;}
    """

    def __init__(self, missed, repeats: int = 6):
        super().__init__()
        chars = [c for c, _ in missed.most_common(5)] if missed else list("(){}[]:;\"'")
        chars = [c for c in chars if c not in ("\n",)] or list("(){}[]:;\"'")
        self.drill = (" ".join(chars) + " ") * repeats
        self.drill = self.drill.rstrip()
        self.pos = 0
        self.errors = 0
        self.done = False

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(f"Symbols drill - the keys you just missed: {' '.join(dict.fromkeys(self.drill.split()))}",
                     id="info")
        yield Static(id="code")
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        super().on_mount()
        self._draw()

    def on_key(self, event: events.Key) -> None:
        if self.done:
            event.stop()
            if event.key == "enter":
                self.app.pop_screen()
            return
        if event.key == "escape":
            event.stop()
            self.app.pop_screen()
            return
        ch = event.character
        if not ch or not ch.isprintable():
            return
        event.stop()
        if ch == self.drill[self.pos]:
            self.pos += 1
        else:
            self.errors += 1
        if self.pos >= len(self.drill):
            self.done = True
        self._draw()

    def _draw(self) -> None:
        buf = Text()
        buf.append(self.drill[:self.pos], style="green")
        if self.pos < len(self.drill):
            buf.append(self.drill[self.pos], style="bold reverse")
            buf.append(self.drill[self.pos + 1:], style="dim")
        self.query_one("#code", Static).update(buf)
        status = self.query_one("#status", Static)
        if self.done:
            status.update(f"Drill complete, {self.errors} errors.   Enter = back")
        else:
            status.update(f"errors so far: {self.errors}   escape leave")
