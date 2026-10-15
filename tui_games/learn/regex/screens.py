"""Pattern Marsh screens: region/level menu and three play modes - golf (accept/reject lists),
extract (matches must equal an exact target list), and substitute (pattern+replacement must turn
`before` into `after`)."""
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, OptionList, Static
from textual.widgets.option_list import Option

from .. import progress
from . import engine
from .explain import explain
from .levels import LEVELS


class RegexRegionMenu(Screen):
    BINDINGS = [Binding("escape,q", "app.pop_screen", "Back")]
    CSS = "RegexRegionMenu #intro {padding: 1 2;}"

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(
            "Pattern Marsh - the witch of the marsh never writes a pattern longer than it needs to be.",
            id="intro",
        )
        yield OptionList(id="levels")
        yield Footer()

    def on_mount(self) -> None:
        self._fill()

    def on_screen_resume(self) -> None:
        self._fill()

    def _fill(self) -> None:
        learn, ol = progress.load(), self.query_one("#levels", OptionList)
        hi = ol.highlighted or 0
        ol.clear_options()
        for i, lv in enumerate(LEVELS):
            best = learn["levels"].get(f"regex:{lv.id}")
            mark = f"best {best['best']} chars, {best['stars']}* (par {lv.par})" if best else f"par {lv.par}"
            tag = {"golf": "", "extract": "[extract] ", "substitute": "[sub] "}[lv.mode]
            ol.add_option(Option(f"{i + 1:>2}. {tag}{lv.title:<30} {mark}", id=str(i)))
        ol.highlighted = min(hi, len(LEVELS) - 1)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.app.push_screen(RegexLevelScreen(int(event.option.id)))


class RegexLevelScreen(Screen):
    """Golf: one pattern Input, checked live (debounced) against yes/no. Extract: one pattern
    Input, checked against a text's exact match list. Substitute: pattern + replacement Inputs,
    checked by applying both to `before` and comparing to `after`. Enter forces an immediate
    check; Enter again once solved leaves the level. Escape always leaves. F1 toggles hint."""

    BINDINGS = [Binding("escape", "back", "Back"), Binding("f1", "hint", "Hint")]
    CSS = """
    RegexLevelScreen #info {padding: 1 2 0 2; height: auto;}
    RegexLevelScreen #explain {padding: 0 2; height: auto; color: $text-muted;}
    RegexLevelScreen #results {padding: 1 2; height: auto;}
    RegexLevelScreen #status {padding: 1 2; height: auto;}
    """

    def __init__(self, index: int):
        super().__init__()
        self.index = index
        self.level = LEVELS[index]
        self.done = False
        self.saved = False
        self.hint = False
        self.result: dict | None = None
        self._timer = None

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(id="info")
        yield Input(placeholder="pattern...", id="pattern")
        if self.level.mode == "substitute":
            yield Input(placeholder="replacement...", id="repl")
        yield Static(id="explain")
        yield Static(id="results")
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self._draw("")
        self.query_one("#pattern", Input).focus()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_hint(self) -> None:
        self.hint = not self.hint
        self._draw(self.query_one("#pattern", Input).value)

    def _repl(self) -> str:
        if self.level.mode != "substitute":
            return ""
        try:
            return self.query_one("#repl", Input).value
        except Exception:
            return ""

    def on_input_changed(self, event: Input.Changed) -> None:
        if self.done:
            return
        if self._timer:
            self._timer.stop()
        pattern = self.query_one("#pattern", Input).value
        self._timer = self.set_timer(0.3, lambda: self._check(pattern))
        self._draw(pattern, checking=True)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.done:
            self.app.pop_screen()
            return
        if self._timer:
            self._timer.stop()
        self._check(self.query_one("#pattern", Input).value)

    def _score(self, pattern: str) -> int:
        return len(pattern) + (len(self._repl()) + 1 if self.level.mode == "substitute" else 0)

    def _check(self, pattern: str) -> None:
        lv = self.level
        if lv.mode == "extract":
            self.result = engine.check_extract(pattern, lv.text, lv.targets)
        elif lv.mode == "substitute":
            self.result = engine.check_substitute(pattern, self._repl(), lv.before, lv.after)
        else:
            self.result = engine.check(pattern, lv.yes, lv.no)
        if self.result["passed"]:
            self.done = True
            if not self.saved:
                self.saved = True
                progress.record("regex", lv.id, self._score(pattern), lv.par)
        self._draw(pattern)

    def _draw(self, pattern: str, checking: bool = False) -> None:
        lv = self.level
        info = Text(f"{lv.title}\n", style="bold")
        info.append(lv.teach)
        self.query_one("#info", Static).update(info)

        ex = Text()
        for frag, note in explain(pattern):
            ex.append(f"{frag!r} ", style="bold")
            ex.append(f"- {note}\n")
        self.query_one("#explain", Static).update(ex)

        accent = self.app.theme_variables.get("primary", "#0178d4")
        r = self.result
        results = Text()
        if lv.mode == "golf":
            self._draw_golf(results, lv, r, checking)
        elif lv.mode == "extract":
            self._draw_extract(results, lv, r, checking)
        else:
            self._draw_substitute(results, lv, r, checking)
        self.query_one("#results", Static).update(results)

        score = self._score(pattern)
        st = Text(f"score {score} (par {lv.par})", style="bold")
        if self.done:
            verdict = "perfect!" if score <= lv.par else f"{score - lv.par} over par"
            st.append(f"\nSolved - {verdict}   Enter = back to map", style=accent)
        elif r and r.get("timeout"):
            st.append("\ntoo slow (catastrophic backtracking) - try a narrower pattern", style="yellow")
        elif r and r.get("error"):
            st.append(f"\n{r['error']}", style="yellow")
        if not self.done:
            if self.hint:
                st.append("\nhint: " + "; ".join(lv.hints), style="dim")
            st.append("\nesc back   f1 hint   Enter to check now", style="dim")
        self.query_one("#status", Static).update(st)

    def _draw_golf(self, results: Text, lv, r, checking) -> None:
        for label, strings in (("must match:", lv.yes), ("must NOT match:", lv.no)):
            results.append(label + "\n", style="bold")
            for i, s in enumerate(strings):
                ok = None if r is None or checking else (r["yes"] if label.startswith("must m") else r["no"])[i]
                mark = "?" if ok is None else ("v" if (ok if label.startswith("must m") else not ok) else "x")
                style = "dim" if ok is None else ("green" if mark == "v" else "red")
                results.append(f"  [{mark}] {s}\n", style=style)

    def _draw_extract(self, results: Text, lv, r, checking) -> None:
        results.append("text:\n  " + lv.text + "\n\n", style="")
        found = [] if (r is None or checking) else r.get("found", [])
        results.append("targets (must be found, in order, and nothing extra):\n", style="bold")
        for i, t in enumerate(lv.targets):
            hit = i < len(found) and found[i] == t
            style = "dim" if (r is None or checking) else ("green" if hit else "red")
            mark = "?" if (r is None or checking) else ("v" if hit else "x")
            results.append(f"  [{mark}] {t!r}\n", style=style)
        if not (r is None or checking) and len(found) > len(lv.targets):
            results.append("  extra matches found: " + ", ".join(repr(x) for x in found[len(lv.targets):]) + "\n",
                            style="red")

    def _draw_substitute(self, results: Text, lv, r, checking) -> None:
        results.append("before:\n  " + lv.before + "\n", style="")
        results.append("after (target):\n  " + lv.after + "\n", style="bold")
        if not (r is None or checking):
            got = r.get("result")
            style = "green" if got == lv.after else "red"
            results.append("your result:\n  " + (got if got is not None else "(error)") + "\n", style=style)
