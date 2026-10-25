import io

import chess
import chess.engine
import chess.pgn
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Input, Static

from ..base import AppScreen
from . import engine_manager, opening_book
from .board import BoardWidget


def _format_score(score: chess.engine.PovScore) -> str:
    white = score.white()
    if white.is_mate():
        return f"#{white.mate()}"
    cp = white.score()
    return f"{cp / 100:+.2f}" if cp is not None else "?"


class AnalysisScreen(AppScreen):
    """Live eval + top engine lines on a loaded position. Best move highlighted on the board."""

    BINDINGS = [Binding("escape", "back", "Back")]
    CSS = """
    AnalysisScreen #body {height: 1fr;}
    #board {width: auto; height: auto; margin: 1 0 0 1;}
    #lines {height: 1fr; margin: 0 1; border: round #5B6370; color: #D8D4C8; padding: 0 1;}
    #load {margin: 0 1;}
    """

    def __init__(self, fen: str | None = None):
        super().__init__()
        self.board = chess.Board(fen) if fen else chess.Board()
        self.engine: engine_manager.AnalysisEngine | None = None
        self.message = ""

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        with Horizontal(id="body"):
            yield BoardWidget(id="board", clickable=False)
            yield Static(id="lines")
        yield Input(placeholder="FEN or PGN to load, blank or 'r' to re-analyse", id="load")
        yield Footer()

    async def on_mount(self) -> None:
        super().on_mount()
        self.query_one(BoardWidget).set_position(self.board)
        path = engine_manager.find_engine()
        if path is None:
            from .engine_settings import EngineSettingsScreen

            self.message = "No engine found - set one up in Engine settings, then come back."
            self._draw()
            self.app.push_screen(EngineSettingsScreen())
            return
        self.engine = engine_manager.AnalysisEngine(path)
        await self.engine.open()
        await self._analyse()

    async def _analyse(self) -> None:
        if self.engine is None:
            return
        self.message = "Analysing..."
        self._draw()
        try:
            infos = await self.engine.analyse(self.board, multipv=3)
        except chess.engine.EngineError as e:
            self.message = f"Engine error: {e}"
            self._draw()
            return
        self.message = ""
        self.infos = infos
        if infos and infos[0].get("pv"):
            self.query_one(BoardWidget).set_hint(infos[0]["pv"][0])
        self._draw()

    def _draw(self) -> None:
        lines = self.query_one("#lines", Static)
        if self.message:
            lines.update(self.message)
            return
        opening = opening_book.classify(self.board.move_stack) if self.board.move_stack else None
        rows = [f"{opening[0]} {opening[1]}", ""] if opening else []
        for info in getattr(self, "infos", []):
            pv = info.get("pv", [])
            score = _format_score(info["score"]) if "score" in info else "?"
            replay = self.board.copy()
            sans = []
            for move in pv[:6]:
                sans.append(replay.san(move))
                replay.push(move)
            rows.append(f"{score:<7} {' '.join(sans)}")
        lines.update("\n".join(rows) or "(no lines)")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if text and text.lower() != "r":
            try:
                self.board = chess.Board(text)
            except ValueError:
                game = chess.pgn.read_game(io.StringIO(text))
                if game is None:
                    self.message = "Could not parse that as a FEN or PGN"
                    self._draw()
                    return
                self.board = game.end().board()
            self.query_one(BoardWidget).set_position(self.board)
        await self._analyse()

    async def action_back(self) -> None:
        if self.engine:
            await self.engine.close()
        self.app.pop_screen()
