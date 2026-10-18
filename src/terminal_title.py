import os
import sys
import unicodedata


def _ascii_fallback(title: str) -> str:
    """Strips diacritics (Đôi Bờ -> Doi Bo). Windows' legacy console host doesn't
    render UTF-8 bytes correctly in OSC title sequences regardless of codepage, so
    non-ASCII titles come out as mojibake there; plain ASCII always displays."""
    title = title.replace("Đ", "D").replace("đ", "d")  # no canonical decomposition
    decomposed = unicodedata.normalize("NFKD", title)
    return "".join(c for c in decomposed if not unicodedata.combining(c)) or title


def set_terminal_title(title: str) -> None:
    """OSC 0: the real terminal window/tab title, not Textual's own Header widget.
    Most terminals (Windows Terminal, ConEmu, xterm-likes) consume this invisibly
    even while an app holds the alt-screen, so it's safe to call during a run."""
    try:
        os.write(sys.__stdout__.fileno(), f"\x1b]0;{_ascii_fallback(title)}\x07".encode("ascii", "replace"))
    except OSError:
        pass
