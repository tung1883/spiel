"""Stockfish discovery, download, and a persistent analysis engine.

Discovery order: a user-set config override path, then the env-var/PATH check LocalGame has
always used, then a binary previously fetched by download_engine() into DOWNLOAD_DIR, else None
(callers offer a download). LocalGame's own per-move opponent engine is untouched by this
module beyond delegating its env/PATH lookup here - it still opens its own short-lived
SimpleEngine per move, since that's cheap at the pace a human plays moves.

AnalysisEngine is different: analysis mode re-queries on every position change, so it keeps one
SimpleEngine subprocess alive for the screen's lifetime instead of paying a ~50-200ms process
spawn on every query. chess.engine.SimpleEngine is a blocking wrapper, so every call into it goes
through asyncio.to_thread - same async-offload idiom LocalGame._pick/_reply already use - guarded
by a lock so two overlapping queries can't interleave writes to the same UCI subprocess.
"""
import asyncio
import os
import platform
import shutil
import stat
import tarfile
import zipfile
from pathlib import Path

import chess
import chess.engine
import httpx

DOWNLOAD_DIR = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "spiel" / "engine"
RELEASES_URL = "https://api.github.com/repos/official-stockfish/Stockfish/releases/latest"
USER_AGENT = "spiel"


class EngineDownloadError(Exception):
    pass


def path_from_env_or_path() -> str | None:
    """The original LocalGame.find_engine() body: STOCKFISH_PATH env var, else PATH."""
    path = os.environ.get("STOCKFISH_PATH")
    if path and os.path.exists(path):
        return path
    return shutil.which("stockfish")


def downloaded_engine_path() -> str | None:
    for name in ("stockfish.exe", "stockfish"):
        candidate = DOWNLOAD_DIR / name
        if candidate.exists():
            return str(candidate)
    return None


def find_engine() -> str | None:
    override = _override_if_valid()
    if override:
        return override
    found = path_from_env_or_path()
    if found:
        return found
    return downloaded_engine_path()


def _override_if_valid() -> str | None:
    from .. import config

    path = config.engine_path_override()
    return path if path and os.path.exists(path) else None


def engine_source(path: str | None) -> str:
    if not path:
        return "none"
    if path == _override_if_valid():
        return "override"
    if path == downloaded_engine_path():
        return "downloaded"
    return "system"


def _os_arch_tokens() -> tuple[str, str]:
    system = {"Windows": "windows", "Linux": "linux", "Darwin": "macos"}.get(platform.system(), "linux")
    machine = platform.machine().lower()
    arch = "arm64" if machine in ("arm64", "aarch64") else "x86-64"
    return system, arch


def _asset_name_ok(name: str, os_token: str, arch_token: str) -> bool:
    lname = name.lower()
    return os_token in lname and (os_token == "macos" or arch_token in lname)


async def pick_asset(client: httpx.AsyncClient) -> dict:
    os_token, arch_token = _os_arch_tokens()
    r = await client.get(RELEASES_URL, headers={"User-Agent": USER_AGENT})
    if r.status_code >= 400:
        raise EngineDownloadError(f"could not reach GitHub releases: {r.status_code}")
    assets = r.json().get("assets", [])
    matches = [a for a in assets if _asset_name_ok(a["name"], os_token, arch_token)]
    if not matches:
        raise EngineDownloadError(f"no release asset matches {os_token}/{arch_token}")
    return matches[0]


def _make_executable(path: Path) -> None:
    try:
        path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


def _extract(archive_path: Path) -> Path:
    dest_dir = archive_path.parent / "_extract"
    dest_dir.mkdir(exist_ok=True)
    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(dest_dir)
    else:
        with tarfile.open(archive_path) as tf:
            tf.extractall(dest_dir)
    # Current releases name the binary after the asset itself (e.g.
    # "stockfish-windows-x86-64-universal.exe"), not literally "stockfish[.exe]" - match on
    # that shape instead: starts with "stockfish", no extension or ".exe", and large enough to
    # rule out the repo's small shell scripts/docs that also start with that prefix.
    def _looks_like_binary(p: Path) -> bool:
        name = p.name.lower()
        if not name.startswith("stockfish"):
            return False
        suffix = p.suffix.lower()
        if suffix not in ("", ".exe"):
            return False
        return p.stat().st_size > 1_000_000

    binary = next((p for p in dest_dir.rglob("*") if p.is_file() and _looks_like_binary(p)), None)
    if binary is None:
        raise EngineDownloadError("downloaded archive did not contain a stockfish binary")
    final_name = "stockfish.exe" if binary.name.lower().endswith(".exe") else "stockfish"
    final_path = archive_path.parent / final_name
    binary.replace(final_path)
    shutil.rmtree(dest_dir, ignore_errors=True)
    return final_path


async def verify_engine(path: str) -> None:
    def _check():
        with chess.engine.SimpleEngine.popen_uci(path) as eng:
            eng.id.get("name")

    try:
        await asyncio.to_thread(_check)
    except (chess.engine.EngineError, OSError) as e:
        raise EngineDownloadError(f"downloaded engine failed to start: {e}")


async def download_engine(progress_cb=None) -> str:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(30, read=None)) as client:
        asset = await pick_asset(client)
        archive_path = DOWNLOAD_DIR / asset["name"]
        total = asset.get("size", 0)
        downloaded = 0
        async with client.stream("GET", asset["browser_download_url"], headers={"User-Agent": USER_AGENT}) as r:
            if r.status_code >= 400:
                raise EngineDownloadError(f"download failed: {r.status_code}")
            with open(archive_path, "wb") as f:
                async for chunk in r.aiter_bytes(65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        progress_cb(downloaded, total)
    binary_path = await asyncio.to_thread(_extract, archive_path)
    await asyncio.to_thread(_make_executable, binary_path)
    archive_path.unlink(missing_ok=True)
    await verify_engine(str(binary_path))
    return str(binary_path)


class AnalysisEngine:
    """A long-lived Stockfish process for repeated analysis queries (unlike LocalGame's
    per-move popen) - analysis mode re-queries on every position change, so paying the process
    spawn cost once instead of per-query matters here."""

    def __init__(self, path: str):
        self.path = path
        self._engine: chess.engine.SimpleEngine | None = None
        self._lock = asyncio.Lock()

    async def open(self) -> None:
        self._engine = await asyncio.to_thread(chess.engine.SimpleEngine.popen_uci, self.path)

    async def analyse(self, board: chess.Board, depth: int = 18, multipv: int = 3,
                       time_limit: float = 0.5) -> list[chess.engine.InfoDict]:
        limit = chess.engine.Limit(depth=depth, time=time_limit)
        async with self._lock:
            return await asyncio.to_thread(self._engine.analyse, board, limit, multipv=multipv)

    async def hint_move(self, board: chess.Board, time_limit: float = 0.3) -> chess.Move:
        limit = chess.engine.Limit(time=time_limit)
        async with self._lock:
            result = await asyncio.to_thread(self._engine.play, board, limit)
            return result.move

    async def close(self) -> None:
        if self._engine is not None:
            await asyncio.to_thread(self._engine.quit)
            self._engine = None
