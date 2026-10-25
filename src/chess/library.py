"""Local game library: a flat JSONL file of imported games, one record per line. Append-only
on import; delete reads the whole file, filters, and atomically replaces it - same shape as
plainphone's ChessPuzzles.java (confirmed: true appends via an append-mode file handle, deletes
via read-all/filter/temp-file-then-atomic-rename)."""
import json
import os
from pathlib import Path

import chess.pgn

LIBRARY_FILE = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "spiel" / "chess_library.jsonl"


def _game_record(source: str, index: int, game: chess.pgn.Game) -> dict:
    h = game.headers
    exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
    return {
        "id": f"{source}:{index}",
        "source": source,
        "white": h.get("White", "?"),
        "black": h.get("Black", "?"),
        "date": h.get("Date", "?"),
        "result": h.get("Result", "*"),
        "pgn": game.accept(exporter),
    }


def append_games(source: str, games: list[chess.pgn.Game]) -> list[str]:
    LIBRARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing = len(load_by_source(source))
    records = [_game_record(source, existing + i, g) for i, g in enumerate(games)]
    with open(LIBRARY_FILE, "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return [r["id"] for r in records]


def load_all() -> list[dict]:
    try:
        lines = LIBRARY_FILE.read_text("utf-8").splitlines()
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
    return out


def load_by_source(source: str) -> list[dict]:
    return [g for g in load_all() if g["source"] == source]


def sources_summary() -> dict[str, int]:
    counts: dict[str, int] = {}
    for g in load_all():
        counts[g["source"]] = counts.get(g["source"], 0) + 1
    return counts


def delete_source(source: str) -> None:
    keep = [g for g in load_all() if g["source"] != source]
    tmp = LIBRARY_FILE.with_suffix(".jsonl.tmp")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        for r in keep:
            f.write(json.dumps(r) + "\n")
    tmp.replace(LIBRARY_FILE)
