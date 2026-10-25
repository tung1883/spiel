"""ECO opening classification from a bundled lichess-org/chess-openings trie (eco.json, built
offline by scripts/build_eco.py). Same package-data loading mechanism sudoku/bank.py uses."""
import json
from functools import lru_cache
from importlib import resources

import chess


@lru_cache(maxsize=None)
def _trie() -> dict:
    text = resources.files("src.chess").joinpath("eco.json").read_text()
    return json.loads(text)


def classify(board_moves: list[chess.Move]) -> tuple[str, str] | None:
    """Replays a game's moves through the trie, returning the (eco, name) of the deepest
    matching known line, or None if even the first move isn't in the book."""
    node = _trie()
    best: tuple[str, str] | None = None
    replay = chess.Board()
    for move in board_moves:
        san = replay.san(move)
        replay.push(move)
        children = node.get("children", {})
        if san not in children:
            break
        node = children[san]
        if "eco" in node:
            best = (node["eco"], node["name"])
    return best
