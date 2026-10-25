"""Offline opponent exposing the same interface GameScreen uses for Lichess.

Uses a UCI engine when available (see engine_manager.find_engine: a config-set override path,
STOCKFISH_PATH env var or `stockfish` on PATH, or a binary spiel downloaded itself), otherwise a
small built-in alpha-beta search.
"""
import asyncio
import random
from collections.abc import AsyncIterator

import chess
import chess.engine

from .engine_manager import find_engine
from .lichess import LichessError

VALUES = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330, chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}
INF = 10**9


def _evaluate(board: chess.Board) -> int:
    """Score from the side-to-move's perspective: material + centre/advancement bonus."""
    score = 0
    for sq, piece in board.piece_map().items():
        v = VALUES[piece.piece_type]
        if piece.piece_type != chess.KING:
            f, r = chess.square_file(sq), chess.square_rank(sq)
            v += int(10 - (abs(3.5 - f) + abs(3.5 - r)) * 2)
            if piece.piece_type == chess.PAWN:
                v += 5 * (r if piece.color else 7 - r)
        score += v if piece.color == board.turn else -v
    return score


def _ordered(board: chess.Board):
    def key(m: chess.Move) -> int:
        cap = board.piece_type_at(m.to_square)
        return (VALUES[cap] * 10 - VALUES[board.piece_type_at(m.from_square)]) if cap else (50 if m.promotion else 0)

    return sorted(board.legal_moves, key=key, reverse=True)


def _search(board: chess.Board, depth: int, alpha: int, beta: int) -> int:
    if board.is_checkmate():
        return -100000 - depth
    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_threefold_repetition():
        return 0
    if depth == 0:
        return _evaluate(board)
    for m in _ordered(board):
        board.push(m)
        score = -_search(board, depth - 1, -beta, -alpha)
        board.pop()
        if score >= beta:
            return beta
        alpha = max(alpha, score)
    return alpha


def builtin_move(board: chess.Board, level: int) -> chess.Move:
    depth = min(3, max(1, level))
    scored = []
    for m in _ordered(board):
        board.push(m)
        scored.append((-_search(board, depth - 1, -INF, INF), m))
        board.pop()
    scored.sort(key=lambda x: x[0], reverse=True)
    if level <= 1:  # weakest: pick randomly among the better half
        return random.choice(scored[: max(1, len(scored) // 2)])[1]
    best = scored[0][0]
    return random.choice([m for s, m in scored if s >= best - 5])


class LocalGame:
    """Drop-in replacement for the Lichess client: you are White, no clock."""

    untimed = True

    def __init__(self, level: int = 2):
        self.level = level
        self.board = chess.Board()
        self.moves: list[str] = []
        self.status = "started"
        self.winner: str | None = None
        self.queue: asyncio.Queue[dict] = asyncio.Queue()
        self.engine_path = find_engine()
        self.engine_name = "Stockfish" if self.engine_path else "Built-in engine"

    async def close(self) -> None:
        pass

    async def account(self) -> dict:
        return {"id": "me"}

    async def challenge_ai(self, *_) -> dict:
        return {"id": "local"}

    def _state(self) -> dict:
        st = {"type": "gameState", "moves": " ".join(self.moves), "wtime": 0, "btime": 0, "status": self.status}
        if self.winner:
            st["winner"] = self.winner
        return st

    async def game_stream(self, _gid: str) -> AsyncIterator[dict]:
        yield {
            "type": "gameFull",
            "white": {"id": "me", "name": "You"},
            "black": {"id": "cpu", "name": f"{self.engine_name} L{self.level}"},
            "initialFen": "startpos",
            "state": self._state(),
        }
        while True:
            ev = await self.queue.get()
            yield ev
            if ev["status"] != "started":
                return

    def _finish_check(self) -> None:
        if self.board.is_checkmate():
            self.status, self.winner = "mate", "black" if self.board.turn else "white"
        elif self.board.is_game_over(claim_draw=True):
            self.status = "stalemate" if self.board.is_stalemate() else "draw"

    async def move(self, _gid: str, uci: str) -> None:
        if self.status != "started":
            return
        mv = chess.Move.from_uci(uci)
        if mv not in self.board.legal_moves:
            raise LichessError("illegal move")
        self.board.push(mv)
        self.moves.append(uci)
        self._finish_check()
        self.queue.put_nowait(self._state())
        if self.status == "started":
            asyncio.create_task(self._reply())

    async def _reply(self) -> None:
        reply = await asyncio.to_thread(self._pick)
        if self.status != "started":
            return
        self.board.push(reply)
        self.moves.append(reply.uci())
        self._finish_check()
        self.queue.put_nowait(self._state())

    def _pick(self) -> chess.Move:
        if self.engine_path:
            try:
                with chess.engine.SimpleEngine.popen_uci(self.engine_path) as eng:
                    eng.configure({"Skill Level": min(20, self.level * 3)})
                    return eng.play(self.board, chess.engine.Limit(time=0.05 * self.level + 0.05)).move
            except (chess.engine.EngineError, OSError):
                pass
        return builtin_move(self.board.copy(), self.level)

    async def resign(self, _gid: str) -> None:
        self.status, self.winner = "resign", "black"
        self.queue.put_nowait(self._state())

    async def abort(self, _gid: str) -> None:
        self.status = "aborted"
        self.queue.put_nowait(self._state())

    async def draw(self, *_) -> None:
        pass
