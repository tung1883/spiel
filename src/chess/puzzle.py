import asyncio

import chess
import httpx
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Input, Static

from ..base import AppScreen
from . import engine_manager, generated_puzzles, puzzle_progress
from .board import BoardWidget
from .lichess import LichessError
from .lichess_puzzle import LichessPuzzle, build_puzzle_position


class PuzzleScreen(AppScreen):
    """Lichess tactics puzzles (or your own, generated from your game library - type 'mine' /
    'lichess' to switch source): type the solving side's move, wrong tries recorded against the
    puzzle streak, or type h/hint for an engine hint, n/next to skip to the next puzzle."""

    BINDINGS = [Binding("escape", "back", "Back")]
    CSS = """
    PuzzleScreen #board {width: auto; height: auto; margin: 1 0 0 1;}
    #status {margin: 0 1; border: round #5B6370; color: #D8D4C8; padding: 0 1;}
    #move {margin: 0 1;}
    """

    def __init__(self):
        super().__init__()
        self.client = LichessPuzzle()
        self.engine: engine_manager.AnalysisEngine | None = None
        self.board = chess.Board()
        self.solution: list[chess.Move] = []
        self.ply = 0
        self.puzzle_id = ""
        self.message = "Loading puzzle..."
        self.source = "lichess"
        self._mine_queue: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield BoardWidget(id="board")
        yield Static(id="status")
        yield Input(placeholder="your move, or: hint / next / mine / lichess", id="move")
        yield Footer()

    async def on_mount(self) -> None:
        super().on_mount()
        self._draw()
        await self._load_next()
        self.query_one("#move", Input).focus()

    async def _load_next(self) -> None:
        if self.source == "mine":
            await self._load_next_mine()
            return
        self.message = "Loading puzzle..."
        self._draw()
        try:
            data = await self.client.next()
        except (LichessError, httpx.HTTPError) as e:
            self.message = f"Could not load a puzzle: {e}"
            self._draw()
            return
        self.board, self.solution, self.puzzle_id = build_puzzle_position(data)
        self.ply = 0
        self.message = f"Find the best move for {'White' if self.board.turn else 'Black'}."
        self.query_one(BoardWidget).set_hint(None)
        self.query_one(BoardWidget).set_position(self.board)
        self._draw()

    async def _load_next_mine(self) -> None:
        if not self._mine_queue:
            self._mine_queue = [p for p in generated_puzzles.load_all()
                                 if puzzle_progress.load_progress(p["id"]).get("status") != "solved"]
        if not self._mine_queue:
            self.message = "No unsolved generated puzzles - go generate some from your Library."
            self._draw()
            return
        record = self._mine_queue.pop(0)
        self.board = chess.Board(record["start_fen"])
        self.solution = [chess.Move.from_uci(u) for u in record["solution_uci"]]
        self.puzzle_id = record["id"]
        self.ply = 0
        self.message = f"Find the best move for {'White' if self.board.turn else 'Black'}."
        self.query_one(BoardWidget).set_hint(None)
        self.query_one(BoardWidget).set_position(self.board)
        self._draw()

    def _draw(self) -> None:
        streak = puzzle_progress.load_streak()
        status = self.query_one("#status", Static)
        source_label = "mine" if self.source == "mine" else "lichess"
        status.update(f"Source: {source_label}\n{self.message}\nStreak: {streak['current']} (best {streak['best']})")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        if text.lower() in ("h", "hint"):
            await self._hint()
            return
        if text.lower() in ("n", "next"):
            await self._load_next()
            return
        if text.lower() == "mine":
            self.source = "mine"
            self._mine_queue = []
            await self._load_next()
            return
        if text.lower() == "lichess":
            self.source = "lichess"
            await self._load_next()
            return
        if self.ply >= len(self.solution):
            return
        try:
            try:
                move = self.board.parse_san(text)
            except ValueError:
                move = self.board.parse_uci(text.lower())
        except ValueError:
            self.message = f"Illegal/unknown move: {text}"
            self._draw()
            return
        await self._play_move(move)

    async def on_board_widget_move_requested(self, event: BoardWidget.MoveRequested) -> None:
        if self.ply < len(self.solution):
            await self._play_move(event.move)

    async def _play_move(self, move: chess.Move) -> None:
        if move != self.solution[self.ply]:
            self.message = "Not the solution - try again."
            puzzle_progress.record_result(self.puzzle_id, solved=False)
            self._draw()
            return
        self.board.push(move)
        self.ply += 1
        self.query_one(BoardWidget).set_position(self.board, move)
        if self.ply >= len(self.solution):
            self.message = "Solved!"
            puzzle_progress.record_result(self.puzzle_id, solved=True)
            self._draw()
            return
        self.message = "Correct - opponent replies..."
        self._draw()
        await asyncio.sleep(0.4)
        reply = self.solution[self.ply]
        self.board.push(reply)
        self.ply += 1
        self.query_one(BoardWidget).set_position(self.board, reply)
        self.message = "Your move."
        self._draw()

    async def _hint(self) -> None:
        if self.ply >= len(self.solution):
            return
        if self.engine is None:
            path = engine_manager.find_engine()
            if path is None:
                self.message = "No engine found - set one up in Engine settings."
                self._draw()
                return
            self.engine = engine_manager.AnalysisEngine(path)
            await self.engine.open()
        move = await self.engine.hint_move(self.board)
        self.query_one(BoardWidget).set_hint(move)

    async def action_back(self) -> None:
        await self.client.close()
        if self.engine:
            await self.engine.close()
        self.app.pop_screen()
