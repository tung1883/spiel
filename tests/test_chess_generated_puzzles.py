from src import config
from src.chess import generated_puzzles as gp
from src.chess.puzzle_generator import GeneratedPuzzle


def _puzzle(id_="p1", cp=None, category="mate"):
    return GeneratedPuzzle(id=id_, source="src1", white="A", black="B", date="2025.01.01",
                            start_fen="startpos", start_ply=5, solution_uci=["e2e4"],
                            winner_white=True, category=category, cp=cp)


def test_append_and_load_round_trip(monkeypatch, tmp_path):
    monkeypatch.setattr(gp, "PUZZLES_FILE", tmp_path / "puzzles.jsonl")
    gp.append_puzzle(_puzzle("p1"))
    gp.append_puzzle(_puzzle("p2"))
    all_puzzles = gp.load_all()
    assert [p["id"] for p in all_puzzles] == ["p2", "p1"]  # newest-first


def test_delete_ids(monkeypatch, tmp_path):
    monkeypatch.setattr(gp, "PUZZLES_FILE", tmp_path / "puzzles.jsonl")
    gp.append_puzzle(_puzzle("p1"))
    gp.append_puzzle(_puzzle("p2"))
    gp.delete_ids({"p1"})
    assert [p["id"] for p in gp.load_all()] == ["p2"]


def test_scanned_ids_round_trip(monkeypatch, tmp_path):
    monkeypatch.setattr(gp, "SCANNED_IDS_FILE", tmp_path / "scanned.txt")
    assert gp.load_scanned_ids() == set()
    gp.mark_scanned("src1:0")
    gp.mark_scanned("src1:1")
    assert gp.load_scanned_ids() == {"src1:0", "src1:1"}


def test_cursor_round_trip_independent_per_scope(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "_PATH", tmp_path / "config.json")
    assert gp.puzzlegen_cursor("all") == 0
    gp.set_puzzlegen_cursor("all", 5)
    gp.set_puzzlegen_cursor("src1", 2)
    assert gp.puzzlegen_cursor("all") == 5
    assert gp.puzzlegen_cursor("src1") == 2
