from src import config
from src.chess import puzzle_progress


def test_progress_round_trip(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "_PATH", tmp_path / "config.json")
    puzzle_progress.save_progress("abcd", {"status": "inprogress"})
    assert puzzle_progress.load_progress("abcd") == {"status": "inprogress"}
    assert puzzle_progress.load_progress("missing") == {}


def test_streak_increments_and_resets(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "_PATH", tmp_path / "config.json")
    assert puzzle_progress.load_streak() == {"current": 0, "best": 0}
    puzzle_progress.record_result("p1", solved=True)
    puzzle_progress.record_result("p2", solved=True)
    assert puzzle_progress.load_streak() == {"current": 2, "best": 2}
    puzzle_progress.record_result("p3", solved=False)
    assert puzzle_progress.load_streak() == {"current": 0, "best": 2}
    assert puzzle_progress.load_progress("p3") == {"status": "failed"}
    assert puzzle_progress.load_progress("p1") == {"status": "solved"}
