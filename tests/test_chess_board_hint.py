import chess

from src.chess.board import HIGHLIGHT, HINT, TARGET, BoardWidget


def _widget() -> BoardWidget:
    w = BoardWidget()
    w.board = chess.Board()
    return w


def test_hint_only_shows_on_otherwise_plain_square():
    w = _widget()
    w.hint_squares = {chess.G1, chess.F3}
    assert w._bg(chess.G1, set()) == HINT
    assert w._bg(chess.F3, set()) == HINT
    assert w._bg(chess.A1, set()) != HINT  # unrelated square unaffected


def test_hint_loses_to_higher_priority_states():
    w = _widget()
    w.hint_squares = {chess.G1, chess.F3}
    w.selected = chess.G1
    assert w._bg(chess.G1, set()) == HIGHLIGHT  # selected beats hint
    w.selected = None
    w.last_move = chess.Move.from_uci("e2e4")
    assert w._bg(chess.E4, {chess.F3}) == HIGHLIGHT  # last-move beats hint too


def test_hint_loses_to_legal_target():
    w = _widget()
    w.hint_squares = {chess.G1, chess.F3}
    assert w._bg(chess.F3, {chess.F3}) == TARGET


def test_set_hint_computes_from_to_squares(monkeypatch):
    w = _widget()
    monkeypatch.setattr(w, "refresh_board", lambda: None)  # no active app in this test
    w.set_hint(chess.Move.from_uci("g1f3"))
    assert w.hint_squares == {chess.G1, chess.F3}
    w.set_hint(None)
    assert w.hint_squares == set()
