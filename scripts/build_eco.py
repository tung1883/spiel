"""One-off maintenance script: builds src/chess/eco.json from lichess-org/chess-openings'
public-domain TSV files. Not run at app runtime - its output is committed like the sudoku
puzzle JSON files are. Re-run this manually if the opening book needs refreshing.

Usage: python scripts/build_eco.py
"""
import json
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/lichess-org/chess-openings/master/{}.tsv"
LETTERS = "abcde"
OUT_PATH = Path(__file__).resolve().parent.parent / "src" / "chess" / "eco.json"


def fetch(letter: str) -> str:
    with urllib.request.urlopen(BASE.format(letter), timeout=30) as r:
        return r.read().decode("utf-8")


def tokenize(pgn_movetext: str) -> list[str]:
    """'1. e4 c5 2. Nf3' -> ['e4', 'c5', 'Nf3'] (strip move numbers/dots)."""
    tokens = []
    for tok in pgn_movetext.split():
        if tok.endswith("."):
            continue
        tokens.append(tok)
    return tokens


def insert(trie: dict, eco: str, name: str, moves: list[str]) -> None:
    node = trie
    for move in moves:
        node = node.setdefault("children", {}).setdefault(move, {})
    node["eco"] = eco
    node["name"] = name


def main() -> None:
    trie: dict = {}
    total = 0
    for letter in LETTERS:
        text = fetch(letter)
        lines = text.splitlines()[1:]  # skip header
        for line in lines:
            if not line.strip():
                continue
            eco, name, pgn = line.split("\t")
            moves = tokenize(pgn)
            if not moves:
                continue
            insert(trie, eco, name, moves)
            total += 1
    OUT_PATH.write_text(json.dumps(trie, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT_PATH} ({total} lines, {OUT_PATH.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
