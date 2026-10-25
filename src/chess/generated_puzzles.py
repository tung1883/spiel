"""Storage for puzzles generated from the user's own games (puzzle_generator.py), plus the
persisted scan state (scanned-game-ids file + a per-scope resume cursor) that lets a stopped
generation run pick back up instead of rescanning from the start - mirrors plainphone's
ChessPuzzleJobs.java (own scanned-ids file) and its per-scope cursor."""
import json
import os
from dataclasses import asdict
from pathlib import Path

from .. import config

_DIR = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "spiel"
PUZZLES_FILE = _DIR / "chess_generated_puzzles.jsonl"
SCANNED_IDS_FILE = _DIR / "chess_puzzlegen_scanned.txt"


def append_puzzle(puzzle) -> None:
    PUZZLES_FILE.parent.mkdir(parents=True, exist_ok=True)
    record = asdict(puzzle) if not isinstance(puzzle, dict) else puzzle
    with open(PUZZLES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def load_all() -> list[dict]:
    try:
        lines = PUZZLES_FILE.read_text("utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    out.reverse()  # newest-first, mirrors ChessPuzzles.loadAll
    return out


def delete_ids(ids: set[str]) -> None:
    keep = [p for p in load_all() if p["id"] not in ids]
    keep.reverse()  # load_all() already reversed to newest-first; restore append order on disk
    tmp = PUZZLES_FILE.with_suffix(".jsonl.tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        for r in keep:
            f.write(json.dumps(r) + "\n")
    tmp.replace(PUZZLES_FILE)


def load_scanned_ids() -> set[str]:
    try:
        return {line.strip() for line in SCANNED_IDS_FILE.read_text("utf-8").splitlines() if line.strip()}
    except OSError:
        return set()


def mark_scanned(game_id: str) -> None:
    SCANNED_IDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SCANNED_IDS_FILE, "a", encoding="utf-8") as f:
        f.write(game_id + "\n")


def puzzlegen_cursor(scope: str) -> int:
    return config.load().get("chess_puzzlegen", {}).get("cursor", {}).get(scope, 0)


def set_puzzlegen_cursor(scope: str, index: int) -> None:
    cfg = config.load()
    pg = cfg.setdefault("chess_puzzlegen", {"cursor": {}})
    pg.setdefault("cursor", {})[scope] = index
    config.save(cfg)
