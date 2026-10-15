"""Async client for play.typeracer.com's /api/action endpoint (guest session)."""
import httpx

from .wire import CONTENT_TYPE, encode

BASE = "https://play.typeracer.com"


class TypeRacerError(Exception):
    pass


class RaceState:
    """Merged view of the game, built from full and delta (`since`) responses."""

    def __init__(self, data: dict):
        self.game: dict = {}
        self.progress: dict = {}
        self.results: dict = {}
        self.users: dict = {}
        self.text: dict = {}
        self.server_offset = 0  # serverNow - local now, ms
        self.merge(data)

    def merge(self, data: dict, local_now_ms: float = 0) -> None:
        self.game.update(data.get("game") or {})
        self.progress = data.get("progress") or self.progress
        self.results.update(data.get("results") or {})
        self.users.update(data.get("users") or {})
        self.text = data.get("gameText") or self.text
        if "serverNow" in data and local_now_ms:
            self.server_offset = data["serverNow"] - local_now_ms
        self.extra = {k: data[k] for k in ("challenge", "save") if k in data}

    @property
    def id(self) -> str:
        return self.game.get("id", "")

    @property
    def status(self) -> str:
        return self.game.get("status", "")

    def name(self, uid: str) -> str:
        u = (self.users.get(uid) or {}).get("user") or {}
        return u.get("name") or u.get("username") or "Guest"


class TypeRacerClient:
    def __init__(self, universe: str = "play"):
        self.universe = universe
        self.http = httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0 tui-games", "Origin": BASE, "Referer": BASE + "/"},
            follow_redirects=True,
            timeout=15,
        )
        self.uid = ""

    async def start(self) -> None:
        r = await self.http.get(f"{BASE}/", params={"universe": self.universe})
        r.raise_for_status()
        marker = '"uid":"'
        i = r.text.find(marker)
        if i >= 0:
            self.uid = r.text[i + len(marker): r.text.find('"', i + len(marker))]

    async def close(self) -> None:
        await self.http.aclose()

    async def action(self, **action) -> dict:
        r = await self.http.post(
            f"{BASE}/api/action",
            params={"universe": self.universe},
            content=encode(action),
            headers={"Content-Type": CONTENT_TYPE},
        )
        try:
            data = r.json()
        except ValueError:
            data = {}
        if r.status_code != 200:
            raise TypeRacerError(data.get("error") or f"HTTP {r.status_code}")
        if "fatalError" in data:
            raise TypeRacerError(str(data["fatalError"]))
        return data

    async def match(self, mode: str) -> dict:
        return await self.action(**{"action": {"auto": "match-automatic", "practice": "match-practice", "qotd": "match-qotd"}[mode]})
