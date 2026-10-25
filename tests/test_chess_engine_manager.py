from pathlib import Path

import httpx
import pytest

from src import config
from src.chess import engine_manager


def _touch(path: Path) -> str:
    path.write_text("")
    return str(path)


def test_find_engine_prefers_override(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "_PATH", tmp_path / "config.json")
    override = _touch(tmp_path / "override-stockfish")
    config.set_engine_path_override(override)
    monkeypatch.setattr(engine_manager, "path_from_env_or_path", lambda: "/usr/bin/stockfish")
    monkeypatch.setattr(engine_manager, "downloaded_engine_path", lambda: str(tmp_path / "downloaded"))
    assert engine_manager.find_engine() == override


def test_find_engine_falls_back_to_env_then_downloaded(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "_PATH", tmp_path / "config.json")
    monkeypatch.setattr(engine_manager, "path_from_env_or_path", lambda: None)
    downloaded = _touch(tmp_path / "downloaded-stockfish")
    monkeypatch.setattr(engine_manager, "downloaded_engine_path", lambda: downloaded)
    assert engine_manager.find_engine() == downloaded

    monkeypatch.setattr(engine_manager, "path_from_env_or_path", lambda: "/usr/bin/stockfish")
    assert engine_manager.find_engine() == "/usr/bin/stockfish"


def test_find_engine_returns_none_when_nothing_found(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "_PATH", tmp_path / "config.json")
    monkeypatch.setattr(engine_manager, "path_from_env_or_path", lambda: None)
    monkeypatch.setattr(engine_manager, "downloaded_engine_path", lambda: None)
    assert engine_manager.find_engine() is None


@pytest.mark.parametrize(("system", "machine", "expected"), [
    ("Windows", "AMD64", ("windows", "x86-64")),
    ("Linux", "x86_64", ("linux", "x86-64")),
    ("Darwin", "arm64", ("macos", "arm64")),
    ("Linux", "aarch64", ("linux", "arm64")),
])
def test_os_arch_tokens(monkeypatch, system, machine, expected):
    monkeypatch.setattr(engine_manager.platform, "system", lambda: system)
    monkeypatch.setattr(engine_manager.platform, "machine", lambda: machine)
    assert engine_manager._os_arch_tokens() == expected


@pytest.mark.asyncio
async def test_pick_asset_matches_os_and_arch(monkeypatch):
    monkeypatch.setattr(engine_manager, "_os_arch_tokens", lambda: ("linux", "x86-64"))
    body = {"assets": [
        {"name": "stockfish-linux-arm64-universal.tar.gz", "browser_download_url": "a", "size": 1},
        {"name": "stockfish-linux-x86-64-universal.tar.gz", "browser_download_url": "b", "size": 1},
        {"name": "stockfish-windows-x86-64-universal.zip", "browser_download_url": "c", "size": 1},
    ]}

    def handler(request):
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        asset = await engine_manager.pick_asset(client)
    assert asset["name"] == "stockfish-linux-x86-64-universal.tar.gz"


@pytest.mark.asyncio
async def test_pick_asset_macos_has_no_arch_split(monkeypatch):
    monkeypatch.setattr(engine_manager, "_os_arch_tokens", lambda: ("macos", "arm64"))
    body = {"assets": [
        {"name": "stockfish-macos-universal.tar.gz", "browser_download_url": "a", "size": 1},
        {"name": "stockfish-windows-x86-64-universal.zip", "browser_download_url": "c", "size": 1},
    ]}

    def handler(request):
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        asset = await engine_manager.pick_asset(client)
    assert asset["name"] == "stockfish-macos-universal.tar.gz"


@pytest.mark.asyncio
async def test_pick_asset_raises_when_nothing_matches(monkeypatch):
    monkeypatch.setattr(engine_manager, "_os_arch_tokens", lambda: ("linux", "x86-64"))
    body = {"assets": [{"name": "stockfish-windows-x86-64-universal.zip", "browser_download_url": "z", "size": 1}]}

    def handler(request):
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(engine_manager.EngineDownloadError):
            await engine_manager.pick_asset(client)


def test_make_executable_tolerates_errors(tmp_path, monkeypatch):
    path = tmp_path / "stockfish"
    path.write_text("")
    monkeypatch.setattr(Path, "chmod", lambda self, mode: (_ for _ in ()).throw(OSError("no chmod here")))
    engine_manager._make_executable(path)  # must not raise


def test_extract_finds_release_style_binary(tmp_path):
    import tarfile

    src_dir = tmp_path / "build" / "stockfish"  # distinct from the final "stockfish" output path below
    src_dir.mkdir(parents=True)
    (src_dir / "README.md").write_text("docs")
    (src_dir / "net.sh").write_text("#!/bin/sh\necho hi\n")
    binary = src_dir / "stockfish-linux-x86-64-universal"
    binary.write_bytes(b"0" * 2_000_000)  # big enough to beat the size filter

    archive_path = tmp_path / "stockfish-linux-x86-64-universal.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tf:
        tf.add(src_dir, arcname="stockfish")

    final_path = engine_manager._extract(archive_path)
    assert final_path.name == "stockfish"
    assert final_path.read_bytes() == binary.read_bytes()
