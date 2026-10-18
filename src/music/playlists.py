from pathlib import Path

from .. import config


def load_all() -> dict[str, list[str]]:
    return config.load().get("playlists", {})


def save_all(playlists: dict[str, list[str]]) -> None:
    cfg = config.load()
    cfg["playlists"] = playlists
    config.save(cfg)


def names() -> list[str]:
    return sorted(load_all().keys())


def tracks_of(name: str) -> list[Path]:
    return [Path(p) for p in load_all().get(name, []) if Path(p).exists()]


def create(name: str) -> None:
    pls = load_all()
    pls.setdefault(name, [])
    save_all(pls)


def add_paths(name: str, paths: list[Path]) -> None:
    pls = load_all()
    existing = pls.setdefault(name, [])
    for p in paths:
        s = str(p)
        if s not in existing:
            existing.append(s)
    save_all(pls)


def remove_path(name: str, path: Path) -> None:
    pls = load_all()
    if name in pls:
        pls[name] = [p for p in pls[name] if p != str(path)]
        save_all(pls)


def delete(name: str) -> None:
    pls = load_all()
    pls.pop(name, None)
    save_all(pls)
