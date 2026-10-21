import os
import sys
import unicodedata


def _ascii_fallback(title: str) -> str:
    """Strips diacritics (Đôi Bờ -> Doi Bo) for when the Unicode path is unavailable."""
    title = title.replace("Đ", "D").replace("đ", "d")  # no canonical decomposition
    decomposed = unicodedata.normalize("NFKD", title)
    return "".join(c for c in decomposed if not unicodedata.combining(c)) or title


def _set_title_win32(title: str) -> bool:
    """Windows' legacy console host mangles UTF-8 bytes in OSC title sequences
    regardless of codepage, but SetConsoleTitleW takes UTF-16 and works in conhost
    and Windows Terminal (via conpty) alike."""
    try:
        import ctypes

        return bool(ctypes.windll.kernel32.SetConsoleTitleW(title))
    except (AttributeError, OSError):
        return False


def set_terminal_title(title: str) -> None:
    """OSC 0: the real terminal window/tab title, not Textual's own Header widget.
    Most terminals (Windows Terminal, ConEmu, xterm-likes) consume this invisibly
    even while an app holds the alt-screen, so it's safe to call during a run."""
    if sys.platform == "win32":
        if _set_title_win32(title):
            return
        title = _ascii_fallback(title)
    try:
        os.write(sys.__stdout__.fileno(), f"\x1b]0;{title}\x07".encode("utf-8", "replace"))
    except OSError:
        pass
