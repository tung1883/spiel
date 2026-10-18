import random
from pathlib import Path
from typing import Callable

import mutagen

from .player import AUDIO_EXTS, MusicPlayer


def _fmt(seconds: float) -> str:
    s = max(0, int(seconds))
    return f"{s // 60}:{s % 60:02d}"


def _bar(fraction: float, width: int = 20) -> str:
    filled = round(max(0.0, min(1.0, fraction)) * width)
    return "█" * filled + "░" * (width - filled)


class MusicController:
    """Owns playback state for the whole app (one instance lives on GamesApp),
    so music keeps playing — and stays controllable — across every screen push/pop,
    not just while the music screen itself is open.

    `tracks` is the active queue: the files in one folder (queue_kind="folder",
    queue_name=its path relative to the library root, "." for the root itself) or a
    saved playlist's contents (queue_kind="playlist", queue_name=<its name>).
    Playing a file scopes the queue to that file's own folder — not the whole
    library recursively — so next/prev stay local to wherever you're browsing."""

    def __init__(self) -> None:
        self.player: MusicPlayer | None = None
        self.tracks: list[Path] = []
        self.folder: Path | None = None
        self.queue_kind: str = "folder"  # "folder" | "playlist"
        self.queue_name: str = "."
        self.index = 0
        self.volume = 0.8
        self.started = False
        self.duration: float | None = None  # seconds; None when unreadable
        self.shuffle = False
        self.repeat = "none"  # "none" | "all" | "one"
        self.on_change: Callable[[], None] | None = None
        self._shuffle_order: list[int] = []
        self._shuffle_pos = 0

    @property
    def current_track(self) -> Path | None:
        return self.tracks[self.index] if self.started and self.tracks else None

    @property
    def paused(self) -> bool:
        return bool(self.player and self.player.paused)

    @property
    def queue_label(self) -> str:
        if self.queue_kind == "folder" and self.queue_name == "." and self.folder:
            return self.folder.name
        return self.queue_name

    def load_folder(self, folder: Path) -> None:
        self.folder = folder
        files = sorted(
            (p for p in folder.iterdir() if p.suffix.lower() in AUDIO_EXTS),
            key=lambda p: p.name.lower(),
        )
        self.set_queue(files, "folder", ".")

    def set_queue(self, tracks: list[Path], kind: str, name: str) -> None:
        self.tracks = tracks
        self.queue_kind = kind
        self.queue_name = name
        self.index = 0
        self.started = False
        self._reshuffle()

    def enqueue(self, paths: list[Path]) -> None:
        """Appends to the current queue in place, without touching what's playing.
        Skips anything already queued, so re-adding the same folder is a no-op."""
        existing = set(self.tracks)
        new = [p for p in paths if p not in existing]
        if not new:
            return
        start = len(self.tracks)
        self.tracks.extend(new)
        if self.shuffle:
            new_indices = list(range(start, len(self.tracks)))
            random.shuffle(new_indices)
            self._shuffle_order.extend(new_indices)

    def _reshuffle(self) -> None:
        self._shuffle_order = list(range(len(self.tracks)))
        random.shuffle(self._shuffle_order)
        self._shuffle_pos = 0

    def toggle_shuffle(self) -> None:
        self.shuffle = not self.shuffle
        if self.shuffle:
            self._reshuffle()
            try:
                self._shuffle_pos = self._shuffle_order.index(self.index)
            except ValueError:
                pass

    def cycle_repeat(self) -> None:
        self.repeat = {"none": "all", "all": "one", "one": "none"}[self.repeat]

    def _player(self) -> MusicPlayer:
        if self.player is None:
            self.player = MusicPlayer()
            self.player.set_volume(self.volume)
        return self.player

    def play_index(self, index: int) -> None:
        if not self.tracks:
            return
        self.index = index % len(self.tracks)
        track = self.tracks[self.index]
        self._player().play_path(track)
        self.started = True
        self.duration = self._read_duration(track)
        if self.shuffle:
            try:
                self._shuffle_pos = self._shuffle_order.index(self.index)
            except ValueError:
                self._reshuffle()
        self._notify()

    @staticmethod
    def _read_duration(path: Path) -> float | None:
        try:
            info = mutagen.File(path)
            return info.info.length if info else None
        except Exception:
            return None

    def next(self, manual: bool = False) -> None:
        if not self.tracks:
            return
        if self.repeat == "one" and not manual:
            self.play_index(self.index)
            return
        if self.shuffle:
            self._shuffle_pos += 1
            if self._shuffle_pos >= len(self._shuffle_order):
                if self.repeat == "all":
                    self._reshuffle()
                else:
                    self._shuffle_pos = len(self._shuffle_order) - 1
                    return
            self.play_index(self._shuffle_order[self._shuffle_pos])
        else:
            nxt = self.index + 1
            if nxt >= len(self.tracks):
                if self.repeat != "all":
                    return
                nxt = 0
            self.play_index(nxt)

    def prev(self) -> None:
        if not self.tracks:
            return
        if self.shuffle:
            self._shuffle_pos = max(0, self._shuffle_pos - 1)
            self.play_index(self._shuffle_order[self._shuffle_pos])
        else:
            self.play_index((self.index - 1) % len(self.tracks))

    def toggle_pause(self) -> None:
        if self.player:
            self.player.toggle_pause()
            self._notify()

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, volume))
        if self.player:
            self.player.set_volume(self.volume)

    def finished(self) -> bool:
        return bool(self.started and self.player and self.player.finished())

    def elapsed_seconds(self) -> float:
        if not self.player or not self.started:
            return 0.0
        ms = self.player.elapsed_ms()
        return max(0.0, ms / 1000) if ms >= 0 else 0.0

    def progress_fraction(self) -> float:
        if not self.duration:
            return 0.0
        return min(1.0, self.elapsed_seconds() / self.duration)

    def progress_bar(self, width: int = 20) -> str:
        return _bar(self.progress_fraction(), width)

    def volume_bar(self, width: int = 10) -> str:
        return _bar(self.volume, width)

    def position_str(self) -> str:
        """'1:42/2:44', or '1:42' when the total length couldn't be read."""
        if not self.player or not self.started:
            return ""
        elapsed = _fmt(self.elapsed_seconds())
        return f"{elapsed}/{_fmt(self.duration)}" if self.duration else elapsed

    def _notify(self) -> None:
        if self.on_change:
            self.on_change()
