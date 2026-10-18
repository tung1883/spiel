"""Terminal Caverns screens: mission list + a terminal-feeling play screen (RichLog scrollback,
Input command line, side panel with the objective/hints/par)."""
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, OptionList, RichLog, Static
from textual.widgets.option_list import Option

from ...base import AppScreen
from .. import progress
from .levels import MISSIONS, MissionRun


class ShellRegionMenu(AppScreen):
    BINDINGS = [Binding("escape,q", "app.pop_screen", "Back")]
    CSS = "ShellRegionMenu #intro {padding: 1 2;}"

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static("Terminal Caverns - the blacksmith forges a pipeline. The server is dying; fix it.", id="intro")
        yield OptionList(
            *(Option(f"Mission {i + 1}: {m.title}", id=str(i)) for i, m in enumerate(MISSIONS)),
            id="missions",
        )
        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.app.push_screen(MissionScreen(int(event.option.id)))


class MissionScreen(AppScreen):
    """Type shell commands at the prompt. escape = mission list, ctrl+r = restart, ctrl+g = hint."""

    BINDINGS = [
        Binding("escape", "back", "Back"),
        Binding("ctrl+r", "restart", "Restart"),
        Binding("ctrl+g", "hint", "Hint"),
    ]
    CSS = """
    MissionScreen #term {width: 2fr;}
    MissionScreen #scrollback {height: 1fr; border: round $primary;}
    MissionScreen #side {width: 1fr; padding: 1 2; border: round $primary;}
    """

    def __init__(self, index: int):
        super().__init__()
        self.index = index
        self.mission = MISSIONS[index]
        self.run = MissionRun(self.mission)
        self.hint_shown = False
        self.saved = False

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        with Horizontal():
            with Vertical(id="term"):
                yield RichLog(id="scrollback", wrap=True, markup=False, highlight=False)
                yield Input(placeholder="type a command, Enter to run", id="cmdline")
            yield Static(id="side")
        yield Footer()

    def on_mount(self) -> None:
        super().on_mount()
        log = self.query_one("#scrollback", RichLog)
        log.write(self.mission.story)
        log.write("")
        self._draw_side()
        self.query_one("#cmdline", Input).focus()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_restart(self) -> None:
        self.run = MissionRun(self.mission)
        self.hint_shown = self.saved = False
        self.query_one("#scrollback", RichLog).clear()
        self.query_one("#scrollback", RichLog).write(self.mission.story)
        self._draw_side()

    def action_hint(self) -> None:
        self.hint_shown = not self.hint_shown
        self._draw_side()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        box = self.query_one("#cmdline", Input)
        if self.run.done:
            self.app.pop_screen()
            return
        line = event.value
        box.value = ""
        if not line.strip():
            return
        log = self.query_one("#scrollback", RichLog)
        log.write(f"$ {line}")
        output = self.run.run(line)
        if output:
            log.write(output.rstrip("\n"))
        if self.run.done and not self.saved:
            self.saved = True
            progress.record("shell", str(self.index), self.run.commands_used, self.mission.par_commands)
        self._draw_side()

    def _draw_side(self) -> None:
        m, run = self.mission, self.run
        side = Text(f"{m.title}\n", style="bold")
        side.append(m.objective + "\n\n")
        side.append(f"commands used: {run.commands_used}  (par {m.par_commands})\n", style="dim")
        if self.hint_shown:
            side.append("\nhints:\n", style="dim")
            for h in m.hints:
                side.append(f"- {h}\n", style="dim")
            side.append("solution:\n", style="dim")
            for s in m.solution:
                side.append(f"  {s}\n", style="dim")
        accent = self.app.theme_variables.get("primary", "#0178d4")
        if run.done:
            verdict = "perfect!" if run.commands_used <= m.par_commands else f"{run.commands_used - m.par_commands} over par"
            side.append(f"\nMission complete in {run.commands_used} commands - {verdict}\n", style=accent)
            side.append("Enter = back to the mission list", style=accent)
        else:
            side.append("\nescape back   ctrl+r restart   ctrl+g hint", style="dim")
        self.query_one("#side", Static).update(side)
