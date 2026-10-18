import os
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")  # keep stdout clean for Textual

import pygame

AUDIO_EXTS = {".mp3", ".flac", ".wav", ".ogg"}  # what SDL_mixer (pygame's backend) decodes


def scan_tracks(folder: Path) -> list[Path]:
    return sorted(
        (p for p in folder.rglob("*") if p.suffix.lower() in AUDIO_EXTS),
        key=lambda p: str(p).lower(),
    )


class MusicPlayer:
    """Plays audio in-process via pygame's bundled SDL_mixer — no external player,
    no subprocess, no window. Decodes mp3/flac/wav/ogg itself."""

    def __init__(self) -> None:
        pygame.mixer.init()
        self.paused = False

    def play_path(self, path: Path) -> None:
        pygame.mixer.music.load(str(path))
        pygame.mixer.music.play()
        self.paused = False

    def toggle_pause(self) -> None:
        if self.paused:
            pygame.mixer.music.unpause()
        else:
            pygame.mixer.music.pause()
        self.paused = not self.paused

    def set_volume(self, volume: float) -> None:
        pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))

    def finished(self) -> bool:
        """True once the current track has played through (not just paused)."""
        return not self.paused and not pygame.mixer.music.get_busy()

    def elapsed_ms(self) -> int:
        """Milliseconds since play_path() was called, or -1 before playback starts."""
        return pygame.mixer.music.get_pos()

    def close(self) -> None:
        pygame.mixer.music.stop()
        pygame.mixer.quit()
