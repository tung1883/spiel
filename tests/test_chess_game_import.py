from src.chess import game_import

TWO_GAMES = """
[Event "e1"]
[White "A"]
[Black "B"]
[Date "2025.01.01"]
[Result "1-0"]

1. e4 e5 2. Nf3 1-0

[Event "e2"]
[White "C"]
[Black "D"]
[Date "2025.01.02"]
[Result "0-1"]

1. d4 d5 0-1
"""


def test_parse_pgn_text_multi_game():
    games = game_import.parse_pgn_text(TWO_GAMES)
    assert len(games) == 2
    assert games[0].headers["White"] == "A"
    assert games[1].headers["White"] == "C"


def test_parse_pgn_text_empty():
    assert game_import.parse_pgn_text("") == []


def test_read_pgn_file(tmp_path):
    p = tmp_path / "games.pgn"
    p.write_text(TWO_GAMES, encoding="utf-8")
    games = game_import.read_pgn_file(str(p))
    assert len(games) == 2
