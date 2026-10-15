"""Minimal Lichess Board API client (https://lichess.org/api#tag/Board)."""
import json
from collections.abc import AsyncIterator

import httpx

BASE = "https://lichess.org"


class LichessError(Exception):
    pass


class Lichess:
    def __init__(self, token: str):
        self.http = httpx.AsyncClient(
            base_url=BASE,
            headers={"Authorization": f"Bearer {token}", "User-Agent": "tui-games"},
            timeout=httpx.Timeout(15, read=None),
        )

    async def close(self) -> None:
        await self.http.aclose()

    @staticmethod
    def _check(r: httpx.Response) -> None:
        if r.status_code >= 400:
            try:
                msg = r.json().get("error") or r.text
            except ValueError:
                msg = r.text
            raise LichessError(f"{r.status_code}: {str(msg)[:200]}")

    async def _post(self, path: str, data: dict | None = None) -> dict:
        r = await self.http.post(path, data=data)
        self._check(r)
        return r.json() if r.content else {}

    async def _stream(self, method: str, path: str, data: dict | None = None) -> AsyncIterator[dict]:
        async with self.http.stream(method, path, data=data) as r:
            if r.status_code >= 400:
                await r.aread()
                self._check(r)
            async for line in r.aiter_lines():
                if line.strip():
                    yield json.loads(line)

    async def account(self) -> dict:
        r = await self.http.get("/api/account")
        self._check(r)
        return r.json()

    def events(self) -> AsyncIterator[dict]:
        return self._stream("GET", "/api/stream/event")

    def seek(self, minutes: int, increment: int, rated: bool = False) -> AsyncIterator[dict]:
        """Open seek; the HTTP request stays open until cancelled/closed. Game arrives via events()."""
        return self._stream(
            "POST", "/api/board/seek",
            {"time": minutes, "increment": increment, "rated": str(rated).lower(), "color": "random"},
        )

    async def challenge_ai(self, level: int, minutes: int, increment: int) -> dict:
        return await self._post(
            "/api/challenge/ai",
            {"level": level, "clock.limit": minutes * 60, "clock.increment": increment},
        )

    def game_stream(self, game_id: str) -> AsyncIterator[dict]:
        return self._stream("GET", f"/api/board/game/stream/{game_id}")

    async def move(self, game_id: str, uci: str) -> None:
        await self._post(f"/api/board/game/{game_id}/move/{uci}")

    async def resign(self, game_id: str) -> None:
        await self._post(f"/api/board/game/{game_id}/resign")

    async def abort(self, game_id: str) -> None:
        await self._post(f"/api/board/game/{game_id}/abort")

    async def draw(self, game_id: str, accept: bool = True) -> None:
        await self._post(f"/api/board/game/{game_id}/draw/{'yes' if accept else 'no'}")
