"""Minimal client for Lichess's puzzle endpoints (https://lichess.org/api#tag/Puzzles) - a
separate, unauthenticated client from Lichess (lichess.py), since those GETs need no bearer
token and don't belong on a class built around holding one."""
import io

import chess
import chess.pgn
import httpx

from .lichess import LichessError

BASE = "https://lichess.org"


class LichessPuzzle:
    def __init__(self):
        self.http = httpx.AsyncClient(base_url=BASE, headers={"User-Agent": "spiel"}, timeout=15)

    async def close(self) -> None:
        await self.http.aclose()

    @staticmethod
    def _check(r: httpx.Response) -> None:
        if r.status_code >= 400:
            try:
                msg = r.json().get("error") or r.text
            except ValueError:
                msg = r.text
            raise LichessError(f"{r.status_code}: {str(msg)[:200]}")

    async def daily(self) -> dict:
        r = await self.http.get("/api/puzzle/daily")
        self._check(r)
        return r.json()

    async def next(self, angle: str = "mix") -> dict:
        r = await self.http.get(f"/api/puzzle/next?angle={angle}")
        self._check(r)
        return r.json()


def build_puzzle_position(data: dict) -> tuple[chess.Board, list[chess.Move], str]:
    """A Lichess puzzle payload's `game.pgn` always ends in the position the puzzle starts from,
    one ply BEFORE the opponent's setup move at `puzzle.initialPly` - that setup move is itself
    played out here, so the returned board is the position the human is actually meant to solve
    from, and `puzzle.solution` (UCI strings) becomes the alternating solver/opponent move list."""
    game = chess.pgn.read_game(io.StringIO(data["game"]["pgn"]))
    initial_ply = data["puzzle"]["initialPly"]
    moves = list(game.mainline_moves()) if game else []
    board = chess.Board()
    for move in moves[: initial_ply + 1]:
        board.push(move)
    solution = [chess.Move.from_uci(uci) for uci in data["puzzle"]["solution"]]
    return board, solution, data["puzzle"]["id"]
