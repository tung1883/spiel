"""Persistence for sudoku: per-puzzle progress (resume in place, picker status) and best times,
under config.json's "sudoku" key. Schema mirrors butler-web's localStorage shape (per variant:level
progress maps, a flat variant:difficulty -> seconds best-times map) so the data model is proven."""
from . import bank
from .. import config


def load_progress(variant: str, level: int) -> dict:
    return config.load().get("sudoku", {}).get("progress", {}).get(f"{variant}:{level}", {})


def save_progress(variant: str, level: int, index: int, entry: dict) -> None:
    cfg = config.load()
    sk = cfg.setdefault("sudoku", {"progress": {}, "best_times": {}})
    key = f"{variant}:{level}"
    sk.setdefault("progress", {}).setdefault(key, {})[str(index)] = entry
    config.save(cfg)


def get_entry(variant: str, level: int, index: int) -> dict | None:
    return load_progress(variant, level).get(str(index))


def load_best_times() -> dict:
    return config.load().get("sudoku", {}).get("best_times", {})


def record_time(best_key: str, seconds: int) -> dict:
    cfg = config.load()
    sk = cfg.setdefault("sudoku", {"progress": {}, "best_times": {}})
    times = sk.setdefault("best_times", {})
    if best_key not in times or seconds < times[best_key]:
        times[best_key] = seconds
        config.save(cfg)
    return times


def pick_random_index(difficulty: str, variant: str) -> int:
    import random

    level = bank.DIFF_LEVELS.get(difficulty, bank.DIFF_LEVELS["medium"])
    size = bank.get_bank_size(variant, difficulty)
    progress = load_progress(variant, level)
    unplayed = [i for i in range(size) if not progress.get(str(i))]
    pool = unplayed or list(range(size))
    return random.choice(pool)


def load_puzzle(difficulty: str, variant: str, index: int) -> tuple:
    """Returns (game, seconds) - a fresh or resumed SudokuGame, and its saved elapsed time."""
    from .engine import SudokuGame

    level = bank.DIFF_LEVELS.get(difficulty, bank.DIFF_LEVELS["medium"])
    data = bank.get_puzzle_at(difficulty, variant, index)
    entry = get_entry(variant, level, index)
    values = list(entry["values"]) if entry else list(data["puzzle"])
    notes = [set(s) for s in entry["notes"]] if entry else [set() for _ in range(81)]
    game = SudokuGame(
        index=data["index"], puzzle=data["puzzle"], solution=data["solution"], regions=data["regions"],
        check_boxes=data["check_boxes"], use_diagonals=data["use_diagonals"], inequalities=data["inequalities"],
        values=values, notes=notes, won=(entry is not None and entry.get("status") == "done"),
    )
    return game, (entry["seconds"] if entry else 0)


def persist(variant: str, difficulty: str, game, seconds: int) -> None:
    level = bank.DIFF_LEVELS.get(difficulty, bank.DIFF_LEVELS["medium"])
    save_progress(variant, level, game.index, {
        "status": "done" if game.is_solved() else "inprogress",
        "values": list(game.values),
        "notes": [sorted(s) for s in game.notes],
        "seconds": seconds,
    })
