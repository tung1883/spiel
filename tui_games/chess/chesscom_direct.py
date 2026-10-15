"""Chess.com without a browser: plain HTTP for matchmaking + RSocket/WebSocket for the game.

Same interface as the Lichess client (see docs/chesscom-protocol.md). Needs a saved session
(chesscom_session), created by pasting the CHESSCOM_REMEMBERME cookie once; no browser is involved.
"""
import asyncio
import re
import time
import uuid
from collections.abc import AsyncIterator

import chess
import httpx
from websockets.asyncio.client import connect

from . import chesscom_session as cs
from .lichess import LichessError
from .pubsub import PubSub
from .rsocket import RSocket, RSocketError, code_to_uci, uci_to_code

BASE = "https://www.chess.com"
CLIENT_VERSION = "2026.10.2"


def parse_time_control(label: str) -> tuple[int, int]:
    """'10 min' -> (600, 0); '3 + 2' -> (180, 2)."""
    m = re.match(r"\s*(\d+)\s*(?:min)?\s*(?:\+\s*(\d+))?", label)
    if not m:
        raise LichessError(f"bad time control: {label}")
    return int(m.group(1)) * 60, int(m.group(2) or 0)


def _find_path(obj, needle: str, path=()):
    """Path to the first string value equal to `needle` inside nested dict/list data."""
    if obj == needle:
        return path
    items = obj.items() if isinstance(obj, dict) else enumerate(obj) if isinstance(obj, list) else ()
    for k, v in items:
        p = _find_path(v, needle, path + (k,))
        if p is not None:
            return p
    return None


class ChessComDirect:
    untimed = False

    def __init__(self, start: tuple[str, str] = ("live", "10 min")):
        self.start = start
        self.hint = "Connecting..."
        self.session: dict | None = None
        self.http: httpx.AsyncClient | None = None
        self.rs: RSocket | None = None
        self.ps: PubSub | None = None  # presence: seeks only go active while this socket is connected
        self.seek_href: str | None = None
        self.names = ("?", "?")
        self.game_id: str | None = None
        self.my_index = 0  # 0 = white
        self.ply = 0
        self.clocks = [0.0, 0.0]
        self.rated = False  # keep False until the flow is proven; flip with TUI_GAMES_CHESSCOM_RATED=1

    # ---- HTTP -------------------------------------------------------------
    def _headers(self) -> dict:
        return {"User-Agent": self.session["user_agent"], "Accept": "application/json", "Referer": f"{BASE}/play/online",
                "Origin": BASE, "x-chesscom-no-csrf": "1", "x-chesscom-client": f"LC6;{CLIENT_VERSION}"}

    async def _get(self, path: str):
        r = await self.http.get(BASE + path)
        if r.status_code in (401, 403):
            raise LichessError(f"chess.com refused the session ({r.status_code}); delete {cs.SESSION_FILE.name} and retry")
        r.raise_for_status()
        return r.json()

    # ---- interface --------------------------------------------------------
    async def account(self) -> dict:
        import os

        self.rated = bool(os.environ.get("TUI_GAMES_CHESSCOM_RATED"))
        self.session = cs.load()
        if not self.session:
            raise LichessError("not logged in to chess.com")
        if (await self._probe()) in (401, 403):
            self.hint = "Session expired, renewing..."
            try:
                self.session = await cs.refresh()
            except cs.LoginError as e:
                raise LichessError(f"chess.com login expired ({e}); open Chess.com again to log in")
            await self._probe()
        self.ps = await PubSub.open(self.session["cookies"], self.session["user_agent"], self.session["user_id"],
                                    ["matcher/tickets/users/:me", "tournaments/games/users/:me"])
        await asyncio.sleep(1.5)
        if self.start[0] == "live":
            base, inc = parse_time_control(self.start[1])
            self.hint = "Looking for an opponent..."
            body = {"capabilities": ["rated"], "rated": self.rated, "gameType": "chess",
                    "timeControl": {"base": f"PT{base}S", "increment": f"PT{inc}S"},
                    "ratingRange": {"upper": None, "lower": -25}}
            r = await self.http.post(f"{BASE}/service/matcher/seeks/chess", json=body)
            if r.status_code >= 400:
                raise LichessError(f"seek failed: HTTP {r.status_code}")
            self.seek_href = (r.json() or {}).get("href")
        else:
            self.hint = "Waiting for a game on your account..."
        return {"id": self.session["user_id"]}

    async def _probe(self) -> int:
        """Open the HTTP client with the saved session; return the status of an authenticated GET."""
        if self.http:
            await self.http.aclose()
        self.http = httpx.AsyncClient(cookies=self.session["cookies"], headers=self._headers(), timeout=10,
                                      follow_redirects=True)
        return (await self.http.get(f"{BASE}/service/matcher/seeks")).status_code

    async def challenge_ai(self, *_) -> dict:
        return {"id": "direct"}

    async def _wait_for_game(self) -> dict:
        while True:
            games = await self._get("/service/play/games")
            games = games if isinstance(games, list) else games.get("games", [])
            if games:
                return games[0]
            await asyncio.sleep(1)

    def _setup(self) -> dict:
        return {"acknowledgements": True, "authentication": "strict", "userId": self.session["user_id"],
                "client": f"LC6;chrome/154.0.0/browser;Windows 10;{uuid.uuid4()};{CLIENT_VERSION}"}

    async def game_stream(self, _gid: str) -> AsyncIterator[dict]:
        game = await self._wait_for_game()
        self.game_id = str(game.get("id") or game.get("gameId"))
        self.my_index = game["players"].index(self.session["user_id"])  # players = [white, black]
        by_id = {d["id"]: d["username"] for d in game.get("playersDetails", [])}
        self.names = tuple(by_id.get(p, "?") for p in game["players"])
        ws = await connect(BASE.replace("https", "wss") + game["transports"]["rsocket"]["url"], additional_headers={
            "Cookie": "; ".join(f"{k}={v}" for k, v in self.session["cookies"].items()),
            "Origin": BASE}, user_agent_header=self.session["user_agent"], max_size=None)
        self.rs = await RSocket.open(ws, self._setup())
        first = True
        try:
            async for ev in self.rs.request_stream(f"games.{self.game_id}.events"):
                self.clocks = ev.get("clocks", self.clocks)
                moves = [code_to_uci(m[0]) for m in ev.get("moves", [])]
                self.ply = len(moves)
                gs = {"type": "gameState", "moves": " ".join(moves), "wtime": self.clocks[0], "btime": self.clocks[1],
                      "status": "started"}
                acts = ev.get("actions") or [[], []]
                if "draw-reject" in acts[self.my_index]:  # offer pending to me -> opponent offered
                    gs["wdraw" if self.my_index == 1 else "bdraw"] = True
                results = ev.get("results")
                if results:
                    gs["status"] = "finished"
                    gs["winner"] = "white" if results[0] == "win" else "black" if results[1] == "win" else None
                if first:
                    first = False
                    mine, opp = ({"id": "me", "name": self.names[self.my_index]},
                                 {"id": "opp", "name": self.names[1 - self.my_index]})
                    white, black = (mine, opp) if self.my_index == 0 else (opp, mine)
                    yield {"type": "gameFull", "white": white, "black": black, "initialFen": "startpos", "state": gs}
                else:
                    yield gs
                await self.rs.fire(f"games.{self.game_id}.acknowledgments",
                                   {"eventUpdatedAt": ev.get("updatedAt"), "receivedAt": int(time.time() * 1000)})
        except RSocketError as e:
            raise LichessError(str(e))

    async def move(self, _gid: str, uci: str) -> None:
        mine = self.clocks[self.my_index]
        body = {"clock": mine, "gameId": self.game_id, "index": self.ply,
                "metadata": {"clockms": mine, "toggledMove": False, "changeOfHeartMove": False, "moveHoldTime": 0},
                "move": uci_to_code(uci)}
        try:
            await self.rs.request(f"games.{self.game_id}.moves", body)
        except (RSocketError, asyncio.TimeoutError) as e:
            raise LichessError(f"chess.com rejected the move: {e}")

    async def _action(self, kind: str) -> None:
        try:
            await self.rs.request(f"games.{self.game_id}.actions", {"index": self.my_index, "type": kind})
        except (RSocketError, asyncio.TimeoutError) as e:
            raise LichessError(f"{kind} failed: {e}")

    async def resign(self, _gid: str) -> None:
        await self._action("resign")

    async def abort(self, _gid: str) -> None:
        await self._action("abort")

    async def draw(self, _gid: str, accept: bool = True) -> None:
        await self._action("draw" if accept else "draw-reject")  # "draw" = offer, or accept a pending offer

    async def close(self) -> None:
        if self.rs:
            await self.rs.close()
        if self.ps:
            await self.ps.close()
        if self.http:
            if self.seek_href and not self.game_id:  # leaving while still seeking: cancel the seek
                try:
                    await self.http.delete(BASE + self.seek_href)
                except httpx.HTTPError:
                    pass
            await self.http.aclose()
