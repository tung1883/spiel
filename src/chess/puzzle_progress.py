"""Persistence for chess puzzles: per-puzzle result and a solve streak, under config.json's
"chess_puzzles" key. Schema mirrors sudoku/progress.py's "sudoku" key (per-id progress map,
a sibling summary map), so the data model is proven."""
from .. import config


def load_progress(puzzle_id: str) -> dict:
    return config.load().get("chess_puzzles", {}).get("progress", {}).get(puzzle_id, {})


def save_progress(puzzle_id: str, entry: dict) -> None:
    cfg = config.load()
    cp = cfg.setdefault("chess_puzzles", {"progress": {}, "streak": {"current": 0, "best": 0}})
    cp.setdefault("progress", {})[puzzle_id] = entry
    config.save(cfg)


def load_streak() -> dict:
    return config.load().get("chess_puzzles", {}).get("streak", {"current": 0, "best": 0})


def record_result(puzzle_id: str, solved: bool) -> dict:
    cfg = config.load()
    cp = cfg.setdefault("chess_puzzles", {"progress": {}, "streak": {"current": 0, "best": 0}})
    cp.setdefault("progress", {})[puzzle_id] = {"status": "solved" if solved else "failed"}
    streak = cp.setdefault("streak", {"current": 0, "best": 0})
    streak["current"] = streak["current"] + 1 if solved else 0
    streak["best"] = max(streak["best"], streak["current"])
    config.save(cfg)
    return streak
