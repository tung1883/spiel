"""Puzzle generation from a game: ported from plainphone's PuzzleGenerator.java (itself a port
of lichess-org/lichess-puzzler's generator.py), using AnalysisEngine instead of a dedicated
multi-process Stockfish setup, and python-chess instead of a custom rules engine.

Walks a game ply by ply with a shallow eval (WALK_DEPTH/WALK_TIME), flags a win-chance swing
(the lichess-puzzler sigmoid) as a Mate or Advantage candidate, then verifies it's a genuine
forced line by replaying it move by move at a deeper search (PAIR_DEPTH), taking the opponent's
"best defense" as just the engine's own top move (no alternative-defense search - confirmed
this is deliberately simple in the original). At most one puzzle is extracted per game: the
walk returns the instant any ply produces one.

Score comparisons mirror the Java port's own `key()` ordering exactly (mate scores sort faster-
mate-first, ahead of any cp score, ahead of slower-mate-for-the-opponent) rather than reasoning
in win-chance space, to stay faithful to the original's exact thresholds.
"""
import math
import uuid
from dataclasses import dataclass

import chess
import chess.engine
import chess.pgn
import chess.polyglot

from .engine_manager import AnalysisEngine

WALK_DEPTH, WALK_TIME = 8, 0.3
PAIR_DEPTH = 14
DEFENSE_DEPTH = 10
SWING_THRESHOLD = 0.4              # relaxed from upstream lichess-puzzler's 0.6-0.7: shallow
                                    # on-device/local depth otherwise yields almost no puzzles
ONLY_MOVE_MARGIN = 0.5
NON_MATE_WIN_THRESHOLD = 0.6
MATE_SOON_PLIES = 15

# pawn=1 scale (not the cp-ish scale local.py's VALUES uses) - matches the Java port's own
# materialDiff, which compares against small integer thresholds like "> -1".
PIECE_VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}


@dataclass
class GeneratedPuzzle:
    id: str
    source: str
    white: str
    black: str
    date: str
    start_fen: str
    start_ply: int
    solution_uci: list
    winner_white: bool
    category: str
    cp: int | None


@dataclass
class _Pair:
    best_move: chess.Move
    best_score: chess.engine.Score
    second_score: chess.engine.Score | None


def win_chances(score: chess.engine.Score) -> float:
    """lichess-puzzler's sigmoid: win probability-like value in -1..1, exact coefficient
    confirmed from PuzzleGenerator.java's Score.winChances()."""
    mate = score.mate()
    if mate is not None:
        return 1.0 if mate > 0 else -1.0
    cp = score.score()
    if cp is None:
        return 0.0
    return 2.0 / (1.0 + math.exp(-0.00368208 * cp)) - 1.0


def _score_key(score: chess.engine.Score) -> int:
    """Mirrors the Java port's Score.key(): total ordering where any positive mate > any cp
    score > any negative mate, faster mates ranking higher than slower ones."""
    mate = score.mate()
    if mate is not None:
        return 1_000_000 - mate if mate > 0 else -1_000_000 - mate
    cp = score.score()
    return cp if cp is not None else 0


def _mate_key(plies: int) -> int:
    return 1_000_000 - plies


MATE_SOON_KEY = _mate_key(MATE_SOON_PLIES)
MATE_IN_ONE_KEY = _mate_key(1)


def _material_diff(board: chess.Board, color: bool) -> int:
    diff = 0
    for pt, v in PIECE_VALUE.items():
        if pt == chess.KING:
            continue
        diff += v * (len(board.pieces(pt, color)) - len(board.pieces(pt, not color)))
    return diff


def _count_immediate_mates(board: chess.Board) -> int:
    count = 0
    for move in board.legal_moves:
        board.push(move)
        if board.is_checkmate():
            count += 1
        board.pop()
    return count


async def _walk_score(engine: AnalysisEngine, board: chess.Board) -> chess.engine.Score | None:
    infos = await engine.analyse(board, depth=WALK_DEPTH, multipv=1, time_limit=WALK_TIME)
    if not infos:
        return None
    return infos[0]["score"].relative


async def _get_next_pair(engine: AnalysisEngine, board: chess.Board, winner: bool) -> _Pair | None:
    infos = await engine.analyse(board, depth=PAIR_DEPTH, multipv=2)
    if not infos:
        return None
    best_move = infos[0]["pv"][0]
    best_score = infos[0]["score"].pov(winner)
    second_score = infos[1]["score"].pov(winner) if len(infos) > 1 else None
    pair = _Pair(best_move, best_score, second_score)
    if board.turn == winner and not await _is_valid_attack(engine, board, winner, pair):
        return None
    return pair


async def _is_valid_attack(engine: AnalysisEngine, board: chess.Board, winner: bool, pair: _Pair) -> bool:
    if pair.second_score is None:
        return True
    if await _is_valid_mate_in_one(engine, board, winner, pair):
        return True
    return win_chances(pair.best_score) > win_chances(pair.second_score) + ONLY_MOVE_MARGIN


async def _is_valid_mate_in_one(engine: AnalysisEngine, board: chess.Board, winner: bool, pair: _Pair) -> bool:
    if pair.best_score.mate() != 1:
        return False
    if pair.second_score is None or win_chances(pair.second_score) <= NON_MATE_WIN_THRESHOLD:
        return True
    if pair.second_score.mate() == 1:
        mates = _count_immediate_mates(board)
        infos = await engine.analyse(board, depth=PAIR_DEPTH, multipv=mates + 1)
        if len(infos) < mates + 1:
            return True
        last_score = infos[-1]["score"].pov(winner)
        if last_score.mate() is None and win_chances(last_score) > NON_MATE_WIN_THRESHOLD:
            return False
        return True
    return False


async def _cook_mate(engine: AnalysisEngine, board: chess.Board, winner: bool) -> list[chess.Move] | None:
    if board.is_game_over():
        return []
    if board.turn == winner:
        pair = await _get_next_pair(engine, board, winner)
        if pair is None or _score_key(pair.best_score) < MATE_SOON_KEY:
            return None
        move = pair.best_move
    else:
        infos = await engine.analyse(board, depth=DEFENSE_DEPTH, multipv=1)
        if not infos:
            return None
        move = infos[0]["pv"][0]
    board.push(move)
    rest = await _cook_mate(engine, board, winner)
    board.pop()
    if rest is None:
        return None
    return [move] + rest


async def _cook_advantage(engine: AnalysisEngine, board: chess.Board, winner: bool,
                           seen_keys: set[int] | None = None) -> list[_Pair] | None:
    if seen_keys is None:
        seen_keys = set()
    key = chess.polyglot.zobrist_hash(board)
    if key in seen_keys:
        return None
    seen_keys.add(key)
    pair = await _get_next_pair(engine, board, winner)
    if pair is None:
        return []
    if _score_key(pair.best_score) < 200:
        return None
    board.push(pair.best_move)
    rest = await _cook_advantage(engine, board, winner, seen_keys)
    board.pop()
    if rest is None:
        return None
    return [pair] + rest


def _build_puzzle(board: chess.Board, winner: bool, game: chess.pgn.Game, source: str, ply: int,
                   solution_uci: list[str], category: str, cp: int | None) -> GeneratedPuzzle:
    h = game.headers
    return GeneratedPuzzle(
        id=str(uuid.uuid4()), source=source, white=h.get("White", "?"), black=h.get("Black", "?"),
        date=h.get("Date", "?"), start_fen=board.fen(), start_ply=ply, solution_uci=solution_uci,
        winner_white=winner, category=category, cp=cp,
    )


async def _try_mate(engine: AnalysisEngine, board: chess.Board, winner: bool, game: chess.pgn.Game,
                     source: str, ply: int) -> GeneratedPuzzle | None:
    line = await _cook_mate(engine, board, winner)
    if not line:
        return None
    return _build_puzzle(board, winner, game, source, ply, [m.uci() for m in line], "mate", None)


async def _try_advantage(engine: AnalysisEngine, board: chess.Board, winner: bool, game: chess.pgn.Game,
                          source: str, ply: int) -> GeneratedPuzzle | None:
    pairs = await _cook_advantage(engine, board, winner)
    if pairs is None:
        return None
    solution = list(pairs)
    while solution and (len(solution) % 2 == 0 or solution[-1].second_score is None):
        solution.pop()
    if len(solution) <= 1:
        return None
    return _build_puzzle(board, winner, game, source, ply, [p.best_move.uci() for p in solution],
                          "advantage", solution[-1].best_score.score())


async def _analyze_position(engine: AnalysisEngine, board: chess.Board, prev_score: chess.engine.Score,
                             score: chess.engine.Score, game: chess.pgn.Game, source: str,
                             ply: int) -> GeneratedPuzzle | None:
    winner = board.turn
    if len(list(board.legal_moves)) < 2:
        return None
    if _score_key(prev_score) > 300 and _score_key(score) < MATE_SOON_KEY:
        return None
    if _material_diff(board, winner) > 0:
        return None
    if _score_key(score) >= MATE_IN_ONE_KEY:
        return None
    if _score_key(score) > MATE_SOON_KEY:
        return await _try_mate(engine, board, winner, game, source, ply)
    if _score_key(score) >= 200 and win_chances(score) > win_chances(prev_score) + SWING_THRESHOLD:
        if _score_key(score) < 400 and _material_diff(board, winner) > -1:
            return None
        return await _try_advantage(engine, board, winner, game, source, ply)
    return None


async def analyze_game(engine: AnalysisEngine, game: chess.pgn.Game, source: str = "",
                        cancel_check=lambda: False) -> GeneratedPuzzle | None:
    board = game.board()
    moves = list(game.mainline_moves())
    prev_score: chess.engine.Score = chess.engine.Cp(20)
    seen_keys: set[int] = set()
    skip_until_irreversible = False
    for ply_index, move in enumerate(moves):
        if cancel_check():
            return None
        irreversible = board.is_irreversible(move)
        board.push(move)
        if skip_until_irreversible:
            if irreversible:
                skip_until_irreversible = False
                seen_keys = set()
            continue
        key = chess.polyglot.zobrist_hash(board)
        if key in seen_keys:
            skip_until_irreversible = True
            continue
        seen_keys.add(key)
        score = await _walk_score(engine, board)
        if score is None:
            continue
        puzzle = await _analyze_position(engine, board, prev_score, score, game, source, ply_index + 1)
        if puzzle is not None:
            return puzzle
        prev_score = -score
    return None
