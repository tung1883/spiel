import asyncio

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Input, Static

from .. import config
from ..base import AppScreen
from . import engine_manager


class EngineSettingsScreen(AppScreen):
    """Shows where the Stockfish binary is coming from and lets the user override, clear, or
    download it. Not folded into typeracer/menu.py's SettingsScreen: that screen only cycles
    small fixed enum rows, not a free-text path or a download progress bar."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(id="status")
        yield Input(placeholder="path to a stockfish binary, or: :clear / :download", id="path")
        yield Footer()

    def on_mount(self) -> None:
        super().on_mount()
        self._draw()

    def _draw(self) -> None:
        path = engine_manager.find_engine()
        source = engine_manager.engine_source(path)
        label = {"none": "none found", "override": "your override", "system": "system install",
                  "downloaded": "downloaded by spiel"}[source]
        lines = [f"Engine: {label}", f"Path: {path or '(none)'}", "",
                 "Type a path and Enter to set an override, or type: :clear / :download"]
        self.query_one("#status", Static).update("\n".join(lines))

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        import os

        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        if text.lower() == ":clear":
            config.set_engine_path_override("")
            self._draw()
            return
        if text.lower() == ":download":
            self.app.push_screen(EngineDownloadScreen(then=self._draw))
            return
        if not os.path.exists(text):
            self.query_one("#status", Static).update(f"No such file: {text}")
            return
        config.set_engine_path_override(text)
        self._draw()


class EngineDownloadScreen(AppScreen):
    """Downloads a Stockfish release build for this OS/arch into engine_manager.DOWNLOAD_DIR.
    Runs as a plain asyncio task (httpx's async client already yields control, so the Textual
    loop stays responsive without needing a thread)."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, then=None):
        super().__init__()
        self.then = then
        self._task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static("Downloading Stockfish...", id="status")
        yield Footer()

    def on_mount(self) -> None:
        super().on_mount()
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        status = self.query_one("#status", Static)
        try:
            path = await engine_manager.download_engine(progress_cb=self._progress)
        except engine_manager.EngineDownloadError as e:
            status.update(f"Download failed: {e}")
            return
        status.update(f"Done: {path}")
        await asyncio.sleep(1)
        self.app.pop_screen()
        if self.then:
            self.then()

    def _progress(self, downloaded: int, total: int) -> None:
        status = self.query_one("#status", Static)
        if total:
            status.update(f"Downloading Stockfish... {downloaded * 100 // total}% ({downloaded // 1024} KB / {total // 1024} KB)")
        else:
            status.update(f"Downloading Stockfish... {downloaded // 1024} KB")

    def action_cancel(self) -> None:
        if self._task:
            self._task.cancel()
        self.app.pop_screen()
