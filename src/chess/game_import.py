"""Fetchers for a user's game history (Lichess, Chess.com) plus PGN file/text parsing - all
funnel into parse_pgn_text, which normalizes every source into a list of chess.pgn.Game."""
import io

import chess.pgn
import httpx

from .. import config

LICHESS_BASE = "https://lichess.org"
CHESSCOM_BASE = "https://api.chess.com/pub"


def parse_pgn_text(text: str) -> list[chess.pgn.Game]:
    games = []
    handle = io.StringIO(text)
    while (game := chess.pgn.read_game(handle)) is not None:
        games.append(game)
    return games


def read_pgn_file(path: str) -> list[chess.pgn.Game]:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return parse_pgn_text(f.read())


async def fetch_lichess_games(username: str, max_games: int = 200) -> list[chess.pgn.Game]:
    headers = {"User-Agent": "spiel"}
    token = config.lichess_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    chunks: list[bytes] = []
    async with httpx.AsyncClient(base_url=LICHESS_BASE, timeout=httpx.Timeout(30, read=None)) as client:
        params = {"max": max_games, "opening": "true"}
        async with client.stream("GET", f"/api/games/user/{username}", params=params, headers=headers) as r:
            if r.status_code >= 400:
                await r.aread()
                raise httpx.HTTPStatusError(f"{r.status_code}: {r.text[:200]}", request=r.request, response=r)
            async for chunk in r.aiter_bytes(65536):
                chunks.append(chunk)
    return parse_pgn_text(b"".join(chunks).decode("utf-8", errors="replace"))


async def fetch_chesscom_games(username: str, max_months: int = 6) -> list[chess.pgn.Game]:
    """Chess.com has no max-games query param (unlike Lichess) - a prolific player can have
    hundreds of monthly archives, so this caps how many of the MOST RECENT months get fetched
    rather than walking the whole history by default."""
    async with httpx.AsyncClient(headers={"User-Agent": "spiel"}, timeout=20) as client:
        r = await client.get(f"{CHESSCOM_BASE}/player/{username}/games/archives")
        r.raise_for_status()
        archive_urls = r.json().get("archives", [])[-max_months:]
        pgns = []
        for url in archive_urls:
            month = await client.get(url)
            month.raise_for_status()
            for g in month.json().get("games", []):
                pgn = g.get("pgn")
                if pgn:
                    pgns.append(pgn)
    return parse_pgn_text("\n\n".join(pgns))
