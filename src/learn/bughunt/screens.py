"""Bug Swamp screens: a level list (Hunt mode) and the hunt-then-fix play screen.

Modes implemented (PLAN.md section 7): Hunt (move a cursor over the buggy code, accuse a line),
Fix it (edit the accused line inline, hidden tests run in the sandbox), Diagnose (pick the bug's
class from a short list before seeing the explanation), and Trace (step through a real execution
of the code, line-by-line, with locals shown - 't' during Hunt, costs no stars, just time, per
PLAN.md). Review mode and the multi-language display-only entries are still deferred.
"""
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, OptionList, Static
from textual.widgets.option_list import Option

from ...base import AppScreen
from .. import progress
from . import sandbox, tracer
from .levels import LEVELS, BugLevel, apply_fix, build_script

PAR = 3  # one correct accusation + one successful fix + one correct diagnosis
_TIER_ORDER = {"beginner": 0, "intermediate": 1, "expert": 2}
ALL_BUG_CLASSES = sorted({lv.bug_class for lv in LEVELS})


def diagnose_options(level: BugLevel) -> list[str]:
    """A short, deterministic multiple-choice list that always includes the correct class."""
    others = [c for c in ALL_BUG_CLASSES if c != level.bug_class]
    i = LEVELS.index(level)
    picked: list[str] = []
    for k in range(len(others)):
        candidate = others[(i * 3 + k) % len(others)]
        if candidate not in picked:
            picked.append(candidate)
        if len(picked) == min(4, len(others)):
            break
    return sorted(picked + [level.bug_class])


class BugHuntRegionMenu(AppScreen):
    BINDINGS = [Binding("escape,q", "app.pop_screen", "Back")]
    CSS = "BugHuntRegionMenu #intro {padding: 1 2;}"

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static("Bug Swamp - the exterminator hunts a bug in each snippet.", id="intro")
        order = sorted(range(len(LEVELS)), key=lambda i: (_TIER_ORDER[LEVELS[i].tier], i))
        options = [
            Option(f"[{LEVELS[i].tier:<12}] {LEVELS[i].title}", id=str(i)) for i in order
        ]
        yield OptionList(*options, id="levels")
        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.app.push_screen(BugHuntLevelScreen(int(event.option.id)))


class BugHuntLevelScreen(AppScreen):
    """j/k move the cursor, Enter accuses a line (Hunt), then edit + Enter runs the fix (Fix it),
    then j/k + Enter picks the bug class (Diagnose). 't' during Hunt opens the step tracer.
    q = level list, ctrl+r = restart, ? = reveal the buggy line."""

    BINDINGS = [Binding("ctrl+r", "restart", "Restart")]
    CSS = """
    BugHuntLevelScreen #info {padding: 1 2 0 2; height: auto;}
    BugHuntLevelScreen #code {padding: 1 2; height: auto;}
    BugHuntLevelScreen #status {padding: 1 2; height: auto;}
    """

    def __init__(self, index: int):
        super().__init__()
        self.index = index
        self.level: BugLevel = LEVELS[index]
        self._reset_state()

    def _reset_state(self) -> None:
        self.lines = self.level.code.split("\n")
        self.phase = "hunt"  # hunt -> (trace) -> fix -> diagnose -> done
        self.cursor = 0
        self.fix_text = ""
        self.attempts = 0
        self.fix_attempts = 0
        self.message = ""
        self.hint = False
        self.saved = False
        self.diagnose_choices = diagnose_options(self.level)
        self.diagnose_cursor = 0
        self.diagnose_correct: bool | None = None
        self.trace_steps: list[dict] = []
        self.trace_idx = 0
        self.trace_error: str | None = None
        self._return_phase = "hunt"

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
        self._reset_state()
        self._draw()

    def on_key(self, event: events.Key) -> None:
        key, ch = event.key, event.character
        if key == "ctrl+r":
            return  # binding
        event.stop()
        if self.phase in ("hunt", "diagnose") and ch == "q":
            self.app.pop_screen()
            return
        if self.phase in ("hunt", "diagnose") and ch == "?":
            self.hint = not self.hint
        elif self.phase == "done":
            if key == "enter":
                self.app.pop_screen()
                return
        elif self.phase == "hunt":
            self._hunt_key(key, ch)
        elif self.phase == "trace":
            self._trace_key(key, ch)
        elif self.phase == "fix":
            self._fix_key(key, ch)
        elif self.phase == "diagnose":
            self._diagnose_key(key, ch)
        self._draw()

    def _hunt_key(self, key: str, ch: str | None) -> None:
        if ch == "j":
            self.cursor = min(self.cursor + 1, len(self.lines) - 1)
        elif ch == "k":
            self.cursor = max(self.cursor - 1, 0)
        elif ch == "t":
            self._return_phase = "hunt"
            result = tracer.trace_snippet(self.level.code, self.level.tests)
            self.trace_steps = result.steps
            self.trace_error = result.error
            self.trace_idx = 0
            self.phase = "trace"
        elif key == "enter":
            self.attempts += 1
            if self.cursor + 1 == self.level.bug_line:
                self.phase = "fix"
                self.fix_text = self.lines[self.cursor]
                self.message = "correct line - edit it below, Enter to test the fix"
            else:
                self.message = "that line looks fine - try another (j/k, Enter, or t to trace)"

    def _trace_key(self, key: str, ch: str | None) -> None:
        if ch in ("q",) or key == "escape":
            self.phase = self._return_phase
            return
        if ch in ("j", "n") or key == "enter":
            self.trace_idx = min(self.trace_idx + 1, max(len(self.trace_steps) - 1, 0))
        elif ch in ("k", "p"):
            self.trace_idx = max(self.trace_idx - 1, 0)

    def _fix_key(self, key: str, ch: str | None) -> None:
        if key == "escape":
            self.phase = "hunt"
            self.message = "back to hunting"
        elif key == "backspace":
            self.fix_text = self.fix_text[:-1]
        elif key == "enter":
            self.fix_attempts += 1
            candidate_lines = list(self.lines)
            candidate_lines[self.level.bug_line - 1] = self.fix_text
            candidate = "\n".join(candidate_lines)
            result = sandbox.run_snippet(build_script(candidate, self.level))
            if result.ok and "OK" in result.stdout:
                self.lines = candidate_lines
                self.phase = "diagnose"
                self.message = "fixed! now diagnose the bug class you just squashed."
            else:
                detail = "timed out" if result.timed_out else (result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "did not pass the hidden test")
                self.message = f"still broken: {detail}"
        elif ch and ch.isprintable():
            self.fix_text += ch

    def _diagnose_key(self, key: str, ch: str | None) -> None:
        if ch == "j":
            self.diagnose_cursor = min(self.diagnose_cursor + 1, len(self.diagnose_choices) - 1)
        elif ch == "k":
            self.diagnose_cursor = max(self.diagnose_cursor - 1, 0)
        elif key == "enter":
            picked = self.diagnose_choices[self.diagnose_cursor]
            self.diagnose_correct = picked == self.level.bug_class
            self.phase = "done"
            if not self.saved:
                self.saved = True
                penalty = 0 if self.diagnose_correct else 1
                progress.record("bughunt", self.level.id, self.attempts + self.fix_attempts + penalty, PAR)

    def _draw(self) -> None:
        lv = self.level
        accent = self.app.theme_variables.get("primary", "#0178d4")

        info = Text(f"{lv.title}  [{lv.tier}]\n", style="bold")
        info.append({
            "hunt": "Find the buggy line: j/k to move, Enter to accuse, t to trace a real run.",
            "trace": "Stepping through a real run - j/n forward, k/p back, q/esc to stop.",
            "fix": "Edit the accused line, Enter to run the hidden test.",
            "diagnose": "What kind of bug was that? j/k to choose, Enter to answer.",
            "done": "Enter to go back.",
        }[self.phase])
        self.query_one("#info", Static).update(info)

        code = Text()
        trace_line = None
        if self.phase == "trace" and self.trace_steps:
            trace_line = self.trace_steps[self.trace_idx]["line"] - tracer.code_line_offset()
        for i, line in enumerate(self.lines):
            style = ""
            if self.phase == "hunt" and i == self.cursor:
                style = f"bold reverse {accent}"
            elif self.phase == "trace" and trace_line is not None and i == trace_line - 1:
                style = f"bold reverse {accent}"
            elif self.phase in ("fix", "diagnose", "done") and i == lv.bug_line - 1:
                style = "bold yellow" if self.phase == "fix" else "bold green"
            if self.phase == "fix" and i == lv.bug_line - 1:
                code.append(f"{i + 1:>3} | ", style="dim")
                code.append(self.fix_text or " ", style=style)
            else:
                code.append(f"{i + 1:>3} | ", style="dim")
                code.append(line, style=style)
            code.append("\n")
        self.query_one("#code", Static).update(code)

        st = Text(f"attempts: {self.attempts} hunt / {self.fix_attempts} fix", style="bold")
        if self.phase == "trace":
            if not self.trace_steps:
                st.append("\n(no steps captured" + (f" - {self.trace_error.strip().splitlines()[-1]})" if self.trace_error else ")"), style="yellow")
            else:
                step = self.trace_steps[self.trace_idx]
                st.append(f"\nstep {self.trace_idx + 1}/{len(self.trace_steps)}  in {step['func']}()", style=accent)
                locs = ", ".join(f"{k}={v}" for k, v in step["locals"].items()) or "(no locals yet)"
                st.append(f"\n{locs}", style="dim")
                if self.trace_idx == len(self.trace_steps) - 1 and self.trace_error:
                    st.append(f"\nended with: {self.trace_error.strip().splitlines()[-1]}", style="yellow")
        elif self.phase == "diagnose":
            for i, choice in enumerate(self.diagnose_choices):
                style = f"bold reverse {accent}" if i == self.diagnose_cursor else ""
                st.append(f"\n  {choice}", style=style)
        elif self.message:
            st.append("\n" + self.message, style="yellow")
        if self.phase == "done" and self.diagnose_correct is not None:
            verdict = "correctly diagnosed" if self.diagnose_correct else f"it was actually: {lv.bug_class}"
            st.append(f"\nFixed and {verdict}.", style=accent)
            st.append(f"\n{lv.bug_class} - {lv.explanation}", style="dim")
        if self.hint and self.phase in ("hunt", "trace"):
            st.append(f"\nline {lv.bug_line}: {lv.bug_class} - {lv.explanation}", style="dim")
        if self.phase in ("hunt",):
            st.append("\nq level list   ctrl+r restart   ? hint   t trace", style="dim")
        self.query_one("#status", Static).update(st)
