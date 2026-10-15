"""Offline practice: same interface as TypeRacerClient, no network."""
import json
import os
import random
import time
from pathlib import Path

CACHE = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "tui-games" / "quotes.json"

QUOTES = [
    "It is a truth universally acknowledged, that a single man in possession of a good fortune, must be in want of a wife.",
    "Call me Ishmael. Some years ago, never mind how long precisely, having little or no money in my purse, I thought I would sail about a little and see the watery part of the world.",
    "It was the best of times, it was the worst of times, it was the age of wisdom, it was the age of foolishness.",
    "All happy families are alike; each unhappy family is unhappy in its own way.",
    "The only thing we have to fear is fear itself, nameless, unreasoning, unjustified terror which paralyzes needed efforts to convert retreat into advance.",
    "The quick brown fox jumps over the lazy dog while the five boxing wizards jump quickly past the sphinx of black quartz.",
    "In the middle of the journey of our life I found myself within a dark wood, for the straight way was lost.",
    "To be, or not to be, that is the question: whether it is nobler in the mind to suffer the slings and arrows of outrageous fortune.",
    "A journey of a thousand miles begins with a single step, and every great program starts with a single line of code.",
    "Whenever you find yourself on the side of the majority, it is time to pause and reflect.",
]


def _pool_key(universe: str) -> str:
    return "play" if universe in ("play", "accuracy") else universe  # accuracy = English quotes


def _load_cache() -> dict[str, list[str]]:
    try:
        data = json.loads(CACHE.read_text("utf-8"))
    except (OSError, ValueError):
        return {}
    if isinstance(data, list):  # old format: a flat list of English texts
        return {"play": [q for q in data if isinstance(q, str)]}
    return {k: [q for q in v if isinstance(q, str)] for k, v in data.items() if isinstance(v, list)}


def cached_quotes(universe: str = "play") -> list[str]:
    return _load_cache().get(_pool_key(universe), [])


def remember_quote(text: str, universe: str = "play") -> None:
    """Add a text seen online to the offline pool of that universe (language / mode)."""
    cache, key = _load_cache(), _pool_key(universe)
    if text and text not in cache.get(key, []):
        cache.setdefault(key, []).append(text)
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False), "utf-8")


async def fetch_quotes(n: int = 60, delay: float = 1.0, universe: str = "play") -> int:
    """Seed the cache with n practice texts of a universe from typeracer.com (one request each, throttled)."""
    import asyncio

    from .client import RaceState, TypeRacerClient

    c, added = TypeRacerClient(universe), 0
    await c.start()
    try:
        for _ in range(n):
            st = RaceState(await c.match("practice"))
            before = len(cached_quotes(universe))
            remember_quote(st.text["text"], universe)
            added += len(cached_quotes(universe)) - before
            try:
                await c.action(action="leave-race", gameId=st.id)
            except Exception:
                pass
            await asyncio.sleep(delay)
    finally:
        await c.close()
    return added


class LocalTypeRacerClient:
    uid = "me"
    universe = "local"

    def __init__(self, universe: str = "play"):
        self.text = ""
        self.started = 0.0
        self.pool_universe = universe
        self.forced = ""  # replay: always serve this text

    async def start(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def match(self, _mode: str) -> dict:
        key = _pool_key(self.pool_universe)
        pool = [self.forced] if self.forced else ((QUOTES if key == "play" else []) + cached_quotes(key))
        if not pool:
            raise RuntimeError(f"no offline texts for '{key}' yet - play it online once (practice) to cache some, "
                               f"or run fetch_quotes(50, universe='{key}')")
        self.text = random.choice(pool)
        self.started = 0.0
        now = int(time.time() * 1000)
        return {
            "game": {"id": "local", "status": "pending", "players": ["me"], "updatedAt": now},
            "progress": {"me": 0},
            "results": {},
            "users": {"me": {"user": {"name": "You"}}},
            "gameText": {"text": self.text, "language": key.removeprefix("lang_").split("_")[0] if key.startswith("lang_") else "en", "wordCount": len(self.text.split())},
            "serverNow": now,
        }

    async def action(self, **a) -> dict:
        kind = a["action"]
        if kind == "start-race":
            self.started = time.time()
        elif kind == "finish":
            mins = max((time.time() - (self.started or time.time())) / 60, 1e-6)
            wpm = len(self.text) / 5 / mins
            return {
                "game": {"status": "finished", "updatedAt": int(time.time() * 1000)},
                "results": {"me": {"wpm": wpm, "rank": 1}},
            }
        return {}
