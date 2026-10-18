from textual.widgets import Static


class MiniPlayerBar(Static):
    """Thin top bar showing what's playing, visible on every screen.
    Collapses to nothing when no track has been started yet."""

    DEFAULT_CSS = """
    MiniPlayerBar {
        dock: top;
        height: 1;
        background: $panel;
        color: $accent;
        content-align: left middle;
        padding: 0 1;
    }
    MiniPlayerBar.-hidden {
        display: none;
    }
    """

    def on_mount(self) -> None:
        self.set_interval(1, self.refresh_text)
        self.refresh_text()

    def refresh_text(self) -> None:
        music = getattr(self.app, "music", None)
        track = music.current_track if music else None
        if music is None or track is None:
            self.add_class("-hidden")
            return
        self.remove_class("-hidden")
        state = "paused" if music.paused else "playing"
        bar = music.progress_bar(width=10)
        flags = []
        if music.shuffle:
            flags.append("shuffle")
        if music.repeat != "none":
            flags.append(f"repeat-{music.repeat}")
        flag_str = f"  [{' '.join(flags)}]" if flags else ""
        self.update(f"{state} {track.stem}  [{bar}] {music.position_str()}{flag_str}   ctrl+p player")
