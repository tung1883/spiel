import json
import os
from pathlib import Path

_PATH = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "tui-games" / "config.json"


def load() -> dict:
    try:
        return json.loads(_PATH.read_text())
    except (OSError, ValueError):
        return {}


def save(cfg: dict) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(cfg))


def lichess_token() -> str:
    return os.environ.get("LICHESS_TOKEN") or load().get("lichess_token", "")


def set_lichess_token(token: str) -> None:
    cfg = load()
    cfg["lichess_token"] = token
    save(cfg)
