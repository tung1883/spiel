"""Shared XP/stars/unlock persistence for every Learn to Code game. Lives under config.json["learn"];
never touches the other top-level keys (typeracer, lichess_token, best_minesweeper_expert).
"""
from .. import config
from . import story


def stars(actual: int, par: int) -> int:
    if actual <= par:
        return 3
    if actual <= par * 1.5:
        return 2
    return 1


def _learn(cfg: dict) -> dict:
    """Return cfg["learn"], creating it if absent."""
    learn = cfg.get("learn")
    if not isinstance(learn, dict) or learn.get("v") != 1:
        learn = {"v": 1, "xp": 0, "badges": [], "levels": {}}
    learn.setdefault("xp", 0)
    learn.setdefault("badges", [])
    learn.setdefault("levels", {})
    return learn


def load() -> dict:
    return _learn(config.load())


def record(game: str, level_id: str, actual: int, par: int) -> tuple[int, int]:
    """Save a level result. Returns (stars earned this attempt, xp gained)."""
    cfg = config.load()
    learn = _learn(cfg)
    key = f"{game}:{level_id}"
    earned = stars(actual, par)
    prev = learn["levels"].get(key)
    prev_stars = prev["stars"] if prev else 0
    best = min(actual, prev["best"]) if prev else actual
    gained = max(0, 10 * earned - 10 * prev_stars)
    learn["levels"][key] = {"stars": max(earned, prev_stars), "best": best}
    learn["xp"] = learn.get("xp", 0) + gained
    cfg["learn"] = learn
    config.save(cfg)
    return earned, gained


def rank(xp: int) -> str:
    return story.rank_for(xp)
