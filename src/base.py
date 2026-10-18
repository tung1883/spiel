from textual.screen import Screen

from .music.widgets import MiniPlayerBar


class AppScreen(Screen):
    """Base for every screen in spiel except the music screens themselves: mounts
    the mini player bar so music stays visible and controllable (ctrl+p) no matter
    what game or quiz is on screen. Subclasses that override on_mount must call
    super().on_mount() first."""

    def on_mount(self) -> None:
        self.mount(MiniPlayerBar())
