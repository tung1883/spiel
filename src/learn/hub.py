"""Overworld hub: rank/XP banner + list of regions. Entry point from the main menu."""
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, OptionList, Static
from textual.widgets.option_list import Option

from ..base import AppScreen
from . import progress, story


class HubScreen(AppScreen):
    BINDINGS = [Binding("escape,q", "app.pop_screen", "Back")]
    CSS = "HubScreen #status {padding: 1 2; height: auto;}"

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(id="status")
        yield OptionList(id="regions")
        yield Footer()

    def on_mount(self) -> None:
        super().on_mount()
        self._fill()

    def on_screen_resume(self) -> None:
        self._fill()

    def _fill(self) -> None:
        learn = progress.load()
        xp = learn.get("xp", 0)
        self.query_one("#status", Static).update(
            f"The Terminal Kingdom - Rank: {story.rank_for(xp)}   XP: {xp}"
        )
        ol = self.query_one("#regions", OptionList)
        hi = ol.highlighted or 0
        ol.clear_options()
        for gid, title, blurb in story.REGIONS:
            ol.add_option(Option(f"{title:<20} {blurb}", id=gid))
        ol.highlighted = min(hi, len(story.REGIONS) - 1)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opener = _REGION_SCREENS.get(event.option.id)
        if opener:
            self.app.push_screen(opener())


def _open_regex():
    from .regex.screens import RegexRegionMenu

    return RegexRegionMenu()


def _open_git():
    from .git.screens import GitRegionMenu

    return GitRegionMenu()


def _open_shell():
    from .shell.screens import ShellRegionMenu

    return ShellRegionMenu()


def _open_sql():
    from .sql.screens import SqlRegionMenu

    return SqlRegionMenu()


def _open_bughunt():
    from .bughunt.screens import BugHuntRegionMenu

    return BugHuntRegionMenu()


def _open_codetype():
    from .codetype.screens import CodeTypeRegionMenu

    return CodeTypeRegionMenu()


_REGION_SCREENS = {
    "regex": _open_regex,
    "git": _open_git,
    "shell": _open_shell,
    "sql": _open_sql,
    "bughunt": _open_bughunt,
    "codetype": _open_codetype,
}
