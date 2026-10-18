import os
import sys


def set_terminal_title(title: str) -> None:
    """OSC 0: the real terminal window/tab title, not Textual's own Header widget.
    Most terminals (Windows Terminal, ConEmu, xterm-likes) consume this invisibly
    even while an app holds the alt-screen, so it's safe to call during a run."""
    try:
        os.write(sys.__stdout__.fileno(), f"\x1b]0;{title}\x07".encode())
    except OSError:
        pass
