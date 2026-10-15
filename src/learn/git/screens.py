"""Branch Forest screens: region menu (14 levels) and the level-play screen (command input,
graph view, plain-English consequence log)."""
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, OptionList, Static
from textual.widgets.option_list import Option

from .. import progress
from . import graph, trivia
from .levels import LEVELS, LevelRun
from ... import config


class GitRegionMenu(Screen):
    BINDINGS = [Binding("escape,q", "app.pop_screen", "Back")]
    CSS = "GitRegionMenu #intro {padding: 1 2;}"

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static("Branch Forest - the cartographer maps a graph.", id="intro")
        options = [Option(f"Level {i + 1}: {lv.title}", id=str(i)) for i, lv in enumerate(LEVELS)]
        options.append(Option("Git Trivia (10-question quiz)", id="trivia"))
        yield OptionList(*options, id="levels")
        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id == "trivia":
            self.app.push_screen(TriviaScreen())
        else:
            self.app.push_screen(GitLevelScreen(int(event.option.id)))


class GitLevelScreen(Screen):
    """Type a git-like command and press Enter. escape = region map, ctrl+r = restart, ctrl+z = undo."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+r", "restart", "Restart"),
        Binding("ctrl+z", "undo", "Undo"),
    ]
    CSS = """
    GitLevelScreen #info {padding: 1 2 0 2; height: auto;}
    GitLevelScreen #graph {padding: 0 2; height: auto; border: round $primary; margin: 0 2;}
    GitLevelScreen #files {padding: 0 2; height: auto; border: round $primary-darken-1; margin: 0 2;}
    GitLevelScreen #cmd {margin: 1 2 0 2;}
    GitLevelScreen #status {padding: 1 2; height: auto;}
    """

    def __init__(self, index: int):
        super().__init__()
        self.index = index
        self.level = LEVELS[index]
        self.run = LevelRun(self.level)
        self.hint = False
        self.saved = False

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(id="info")
        yield Static(id="graph")
        yield Static(id="files")
        yield Input(placeholder="edit <path> set/append/delete | commit -m \"...\" | merge | rebase | ...", id="cmd")
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self._draw()
        self.query_one("#cmd", Input).focus()

    def action_restart(self) -> None:
        self.run = LevelRun(self.level)
        self.hint = self.saved = False
        self._draw()

    def action_undo(self) -> None:
        self.run.undo()
        self._draw()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text or self.run.done:
            return
        if text == "?":
            self.hint = not self.hint
            self._draw()
            return
        self.run.run(text)
        if self.run.done and not self.saved:
            self.saved = True
            progress.record("git", str(self.index), self.run.count, self.level.par)
        self._draw()

    def _draw(self) -> None:
        run, lv = self.run, self.level
        info = Text(f"{lv.title}\n", style="bold")
        info.append(lv.teach + "\n")
        info.append("goal: " + lv.goal, style="dim")
        self.query_one("#info", Static).update(info)
        self.query_one("#graph", Static).update(graph.render(run.engine))

        files = Text()
        for path in sorted(run.engine.working):
            conflicted = path in run.engine.conflicts
            files.append(f"{path}{'  (CONFLICT)' if conflicted else ''}\n", style="bold red" if conflicted else "bold")
            for ln in run.engine.working[path]:
                style = "red" if ln.startswith(("<<<<<<<", "=======", ">>>>>>>")) else ""
                files.append(f"  {ln}\n", style=style)
        self.query_one("#files", Static).update(files)

        accent = self.app.theme_variables.get("primary", "#0178d4")
        st = Text(f"commands used: {run.count} (par {lv.par})", style="bold")
        if run.log:
            st.append("\n" + run.log[-1])
        if run.done:
            verdict = "perfect!" if run.count <= lv.par else f"{run.count - lv.par} over par"
            st.append(f"\n\nGoal reached in {run.count} commands - {verdict}   escape = back to map", style=accent)
        else:
            if self.hint:
                st.append("\nsolution: " + " | ".join(lv.solution), style="dim")
            st.append("\nctrl+z undo   ctrl+r restart   type ? for a hint, escape to leave", style="dim")
        self.query_one("#status", Static).update(st)


class TriviaScreen(Screen):
    """1-4 picks an option. escape leaves (no credit for the round)."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]
    CSS = """
    TriviaScreen #prompt {padding: 1 2; height: auto;}
    TriviaScreen #options {padding: 0 2; height: auto;}
    TriviaScreen #status {padding: 1 2; height: auto;}
    """

    def __init__(self):
        super().__init__()
        self.questions = trivia.new_round()
        self.i = 0
        self.correct = 0
        self.picked: int | None = None
        self.done = False

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(id="prompt")
        yield Static(id="options")
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self._draw()

    def on_key(self, event: events.Key) -> None:
        ch = event.character
        if self.done:
            return
        if self.picked is None and ch and ch.isdigit() and 1 <= int(ch) <= len(self.questions[self.i].options):
            self.picked = int(ch) - 1
            if self.picked == self.questions[self.i].correct:
                self.correct += 1
            self._draw()
        elif self.picked is not None and (ch == " " or event.key == "enter"):
            self.i += 1
            self.picked = None
            if self.i >= len(self.questions):
                self._finish()
            self._draw()

    def _finish(self) -> None:
        self.done = True
        cfg = config.load()
        if self.correct > cfg.get("git_trivia_best", 0):
            cfg["git_trivia_best"] = self.correct
            config.save(cfg)

    def _draw(self) -> None:
        best = max(config.load().get("git_trivia_best", 0), self.correct)
        if self.done:
            self.query_one("#prompt", Static).update(Text("Round over!", style="bold"))
            self.query_one("#options", Static).update(Text(""))
            accent = self.app.theme_variables.get("primary", "#0178d4")
            st = Text(f"{self.correct}/{len(self.questions)} correct   best: {best}", style=accent)
            st.append("\nescape = back to map", style="dim")
            self.query_one("#status", Static).update(st)
            return

        q = self.questions[self.i]
        self.query_one("#prompt", Static).update(
            Text(f"Question {self.i + 1}/{len(self.questions)}\n", style="bold") + Text(q.prompt))
        opts = Text()
        for i, opt in enumerate(q.options):
            style = ""
            if self.picked is not None:
                if i == q.correct:
                    style = "bold green"
                elif i == self.picked:
                    style = "bold red"
            opts.append(f"{i + 1}. {opt}\n", style=style)
        self.query_one("#options", Static).update(opts)

        st = Text(f"score so far: {self.correct}/{self.i}", style="dim")
        if self.picked is not None:
            verdict = "Correct!" if self.picked == q.correct else "Not quite."
            st = Text(f"{verdict} {q.explain}\n", style="bold") + Text("space/enter: next question", style="dim")
        else:
            st.append("\npress 1-4 to answer", style="dim")
        self.query_one("#status", Static).update(st)
