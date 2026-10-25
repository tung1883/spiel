import chess

from src.chess import opening_book


def _moves(*sans):
    board = chess.Board()
    moves = []
    for san in sans:
        m = board.parse_san(san)
        moves.append(m)
        board.push(m)
    return moves


def test_classify_unknown_first_move_returns_none(monkeypatch):
    # the fixture trie only knows "e4" - "d4" has no match at all
    monkeypatch.setattr(opening_book, "_trie", lambda: {"children": {"e4": {"eco": "B00", "name": "King's Pawn", "children": {}}}})
    assert opening_book.classify(_moves("d4")) is None


def test_classify_deepest_match(monkeypatch):
    fixture = {
        "children": {
            "e4": {
                "eco": "B00", "name": "King's Pawn",
                "children": {"c5": {"eco": "B20", "name": "Sicilian Defense", "children": {}}},
            }
        }
    }
    monkeypatch.setattr(opening_book, "_trie", lambda: fixture)
    assert opening_book.classify(_moves("e4")) == ("B00", "King's Pawn")
    assert opening_book.classify(_moves("e4", "c5")) == ("B20", "Sicilian Defense")
    assert opening_book.classify(_moves("e4", "c5", "Nf3")) == ("B20", "Sicilian Defense")


def test_classify_against_bundled_eco_json():
    assert opening_book.classify(_moves("e4", "c5")) is not None
    eco, name = opening_book.classify(_moves("e4", "c5"))
    assert eco.startswith("B")
