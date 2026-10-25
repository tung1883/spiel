import io

import chess.pgn

from src.chess import library

PGN = """
[Event "test"]
[White "Alice"]
[Black "Bob"]
[Date "2025.01.01"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 1-0
"""


def _games(n=1):
    out = []
    for _ in range(n):
        out.append(chess.pgn.read_game(io.StringIO(PGN)))
    return out


def test_append_and_load_round_trip(monkeypatch, tmp_path):
    monkeypatch.setattr(library, "LIBRARY_FILE", tmp_path / "lib.jsonl")
    ids = library.append_games("src1", _games(2))
    assert len(ids) == 2
    assert ids == ["src1:0", "src1:1"]
    all_games = library.load_all()
    assert len(all_games) == 2
    assert all_games[0]["white"] == "Alice"
    assert all_games[0]["source"] == "src1"


def test_append_continues_index_across_calls(monkeypatch, tmp_path):
    monkeypatch.setattr(library, "LIBRARY_FILE", tmp_path / "lib.jsonl")
    library.append_games("src1", _games(1))
    ids = library.append_games("src1", _games(1))
    assert ids == ["src1:1"]


def test_load_by_source_and_summary(monkeypatch, tmp_path):
    monkeypatch.setattr(library, "LIBRARY_FILE", tmp_path / "lib.jsonl")
    library.append_games("src1", _games(2))
    library.append_games("src2", _games(1))
    assert len(library.load_by_source("src1")) == 2
    assert len(library.load_by_source("src2")) == 1
    assert library.sources_summary() == {"src1": 2, "src2": 1}


def test_delete_source(monkeypatch, tmp_path):
    monkeypatch.setattr(library, "LIBRARY_FILE", tmp_path / "lib.jsonl")
    library.append_games("src1", _games(2))
    library.append_games("src2", _games(1))
    library.delete_source("src1")
    assert library.sources_summary() == {"src2": 1}
