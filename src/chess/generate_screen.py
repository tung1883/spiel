import asyncio
import io

import chess.pgn
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Static

from ..base import AppScreen
from . import engine_manager, generated_puzzles, library, puzzle_generator


class GenerateScreen(AppScreen):
    """Progress + Stop for a generation run over one source (or "all"). Unlike
    EngineDownloadScreen's task.cancel(), Stop here is a cooperative flag checked between
    engine calls - abrupt cancellation would skip the per-game checkpoint write - so the first
    Escape asks the run to wind down gracefully and the screen pops itself once it has
    (showing the final status first); a second Escape while still winding down leaves right
    away instead of waiting.

    Checkpoint granularity matches plainphone's own: cancellation is checked between engine
    calls inside analyze_game (so a Stop can land mid-game), but the scanned-ids/cursor
    checkpoint is only written once a game's analysis call returns - a game interrupted
    mid-ply is NOT marked scanned and is retried whole on the next run."""

    BINDINGS = [Binding("escape", "stop", "Stop")]

    def __init__(self, scope: str):
        super().__init__()
        self.scope = scope
        self._stopping = False
        self._task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static("Starting...", id="status")
        yield Footer()

    def on_mount(self) -> None:
        super().on_mount()
        self._task = asyncio.create_task(self._run())

    def _status(self, text: str) -> None:
        if not self.is_attached:
            return  # screen already left (e.g. a second Escape, or app shutdown) - nothing to draw
        self.query_one("#status", Static).update(text)

    async def _finish(self, text: str) -> None:
        self._status(text)
        await asyncio.sleep(1)
        if self.is_attached and self.app.screen is self:
            self.app.pop_screen()

    async def _run(self) -> None:
        path = engine_manager.find_engine()
        if path is None:
            from .engine_settings import EngineSettingsScreen

            await self._finish("No engine found - set one up in Engine settings, then come back.")
            if self.is_attached:
                self.app.push_screen(EngineSettingsScreen())
            return
        games = library.load_all() if self.scope == "all" else library.load_by_source(self.scope)
        if not games:
            await self._finish("No games to scan")
            return
        scanned_ids = generated_puzzles.load_scanned_ids()
        start = generated_puzzles.puzzlegen_cursor(self.scope)
        engine = engine_manager.AnalysisEngine(path)
        await engine.open()
        found = 0
        try:
            for idx in range(start, len(games)):
                if self._stopping:
                    generated_puzzles.set_puzzlegen_cursor(self.scope, idx)
                    await self._finish(f"Stopped at {idx}/{len(games)} games, {found} puzzle(s) found")
                    return
                record = games[idx]
                if record["id"] not in scanned_ids:
                    game = chess.pgn.read_game(io.StringIO(record["pgn"]))
                    if game is not None:
                        puzzle = await puzzle_generator.analyze_game(
                            engine, game, source=record["source"], cancel_check=lambda: self._stopping)
                        if puzzle is not None:
                            generated_puzzles.append_puzzle(puzzle)
                            found += 1
                    generated_puzzles.mark_scanned(record["id"])
                    scanned_ids.add(record["id"])
                generated_puzzles.set_puzzlegen_cursor(self.scope, idx + 1)
                self._status(f"Scanning... {idx + 1}/{len(games)} games, {found} puzzle(s) found")
            await self._finish(f"Done: {found} puzzle(s) found across {len(games)} games")
        finally:
            await engine.close()

    def action_stop(self) -> None:
        if self._stopping:
            self.app.pop_screen()  # asked twice - leave now instead of waiting for a checkpoint
        else:
            self._stopping = True
            self._status("Stopping...")
