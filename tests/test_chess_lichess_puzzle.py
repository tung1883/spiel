import chess

from src.chess.lichess_puzzle import build_puzzle_position

MATE_IN_ONE = {
    "game": {"pgn": "1. f3 e5 2. g4"},
    "puzzle": {"id": "mate1", "initialPly": 2, "solution": ["d8h4"]},
}

PROMOTION = {
    "game": {"pgn": "1. e4 e5 2. Nf3 Nc6 3. Bb5"},
    "puzzle": {"id": "promo1", "initialPly": 4, "solution": ["a7a8q", "e8d7"]},
}


def test_build_puzzle_position_mate_in_one():
    board, solution, puzzle_id = build_puzzle_position(MATE_IN_ONE)
    assert puzzle_id == "mate1"
    assert board.turn == chess.BLACK
    assert board.fullmove_number == 2
    assert solution == [chess.Move.from_uci("d8h4")]


def test_build_puzzle_position_multi_move_solution():
    board, solution, puzzle_id = build_puzzle_position(PROMOTION)
    assert puzzle_id == "promo1"
    assert board.turn == chess.BLACK
    assert solution == [chess.Move.from_uci("a7a8q"), chess.Move.from_uci("e8d7")]
