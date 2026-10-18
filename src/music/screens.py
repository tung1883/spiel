from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from .. import config
from . import playlists
from .controller import MusicController
from .player import AUDIO_EXTS, scan_tracks


def _now_playing_text(music: MusicController) -> Text:
    if music.current_track is None:
        return Text("Nothing playing", style="dim")
    track = music.current_track
    t = Text(f"NOW PLAYING: {track.stem}\n", style="bold")
    t.append(f"[{music.progress_bar()}] {music.position_str()}\n\n")
    t.append(f"Vol [{music.volume_bar()}] {round(music.volume * 100)}%\n")
    t.append(f"Shuffle: {'on' if music.shuffle else 'off'}   Repeat: {music.repeat}\n")
    t.append("paused" if music.paused else "playing", style="dim")
    return t


class FolderPromptScreen(Screen):
    """Asked once, on first use: where the music lives. Saved for next time."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Cancel")]

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Vertical(
            Label("Music folder (searched recursively):"),
            Input(placeholder=r"D:\music-flac", id="folder"),
            Label("", id="error"),
        )
        yield Footer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        folder = Path(event.value.strip().strip('"'))
        if not folder.is_dir():
            self.query_one("#error", Label).update(f"Not a folder: {folder}")
            return
        cfg = config.load()
        cfg["music_folder"] = str(folder)
        config.save(cfg)
        self.app.music.load_folder(folder)
        self.app.pop_screen()
        self.app.push_screen(MusicScreen())


class NamePromptScreen(Screen):
    """A one-field text prompt that dismisses with the typed value (or None on cancel)."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, prompt: str, placeholder: str = "") -> None:
        super().__init__()
        self.prompt = prompt
        self.placeholder = placeholder

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Vertical(Label(self.prompt), Input(placeholder=self.placeholder, id="name"))
        yield Footer()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class PlaylistPickScreen(Screen):
    """Pick an existing playlist, or create a new one. Dismisses with the chosen
    name, or None on cancel."""

    BINDINGS = [Binding("escape,q", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield OptionList(id="names")
        yield Footer()

    def on_mount(self) -> None:
        option_list = self.query_one("#names", OptionList)
        option_list.add_option(Option("+ New playlist...", id="new"))
        for name in playlists.names():
            option_list.add_option(Option(name, id=f"pl:{name}"))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id == "new":
            def got_name(name: str | None) -> None:
                if name:
                    playlists.create(name)
                self.dismiss(name)

            self.app.push_screen(NamePromptScreen("New playlist name:"), got_name)
        else:
            self.dismiss(event.option.id[len("pl:"):])

    def action_cancel(self) -> None:
        self.dismiss(None)


class MusicScreen(Screen):
    """Detailed player: a persistent "Lists" box (current queue + every saved
    playlist, always visible, pick one anytime) above a folder browser. Drives the
    one shared MusicController on the app, so changes here show up in every other
    screen's mini-bar too, and playback keeps going after this screen is closed.

    Views (self.view), all shown in the lower #tracks box: "browse" (folder tree,
    the default) and "playlist" (one playlist's contents, self.open_playlist)."""

    CSS = """
    MusicScreen #now-playing {height: auto; padding: 1 2;}
    MusicScreen #nav {height: 8; border: round $primary;}
    MusicScreen #tracks {height: 1fr;}
    MusicScreen #help {dock: bottom; height: 2; padding: 0 2; color: $text-muted;}
    """

    HELP_KEYS = [
        [("enter", "play/open"), ("backspace/esc", "up"), ("tab", "switch list"),
         ("n/p", "next/prev"), ("space", "pause"), ("+/-", "vol")],
        [("v", "select"), ("a", "add to playlist"), ("e", "enqueue"), ("x", "remove"),
         ("s", "shuffle"), ("r", "repeat"), ("q/esc", "back")],
    ]

    BINDINGS = [
        Binding("q,escape", "back_or_leave", "Back", show=False),
        Binding("backspace", "up_dir", "Up", show=False),
        Binding("space", "toggle_pause", "Pause/Resume", show=False),
        Binding("n", "next_track", "Next", show=False),
        Binding("p", "prev_track", "Prev", show=False),
        Binding("enter", "play_selected", "Open/Play", show=False),
        Binding("tab", "app.focus_next", "Switch list", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("+", "volume_up", "Vol+", show=False),
        Binding("-", "volume_down", "Vol-", show=False),
        Binding("a", "add_to_playlist", "Add to playlist", show=False),
        Binding("e", "enqueue", "Add to current queue", show=False),
        Binding("v", "toggle_select", "Select", show=False),
        Binding("x", "remove_entry", "Remove", show=False),
        Binding("s", "toggle_shuffle", "Shuffle", show=False),
        Binding("r", "cycle_repeat", "Repeat", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.view = "browse"
        self.current_dir = Path(".")  # relative to music.folder, used in "browse"
        self.open_playlist: str | None = None  # used in "playlist"
        self.selected: set[str] = set()  # marked "dir:"/"file:" ids, browse view only

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static("", id="now-playing")
        yield OptionList(id="nav")
        yield OptionList(id="tracks")
        yield Static(id="help")

    def _help_text(self) -> Text:
        accent = self.app.theme_variables.get("accent", "#a855f7")
        rows = self.HELP_KEYS
        col_width = [
            max(len(f"{key} {desc}") for row in rows if col < len(row) for key, desc in [row[col]])
            for col in range(max(len(r) for r in rows))
        ]

        t = Text()
        for i, row in enumerate(rows):
            if i:
                t.append("\n")
            for j, (key, desc) in enumerate(row):
                cell = f"{key} {desc}"
                t.append(key, style=f"bold {accent}")
                t.append(f" {desc}", style="dim")
                t.append(" " * (col_width[j] - len(cell) + 3))
        return t

    def on_mount(self) -> None:
        self.query_one("#help", Static).update(self._help_text())
        music = self.app.music
        if not music.folder:
            self.query_one("#now-playing", Static).update("No audio files found.")
            return
        self._build_nav()
        self._list_dir(self.current_dir)
        self.query_one("#tracks", OptionList).focus()
        self.set_interval(0.5, self._refresh)
        self._refresh()

    # ---- the persistent "Lists" box: current queue + every saved playlist -------
    def _build_nav(self) -> None:
        music = self.app.music
        nav = self.query_one("#nav", OptionList)
        keep_highlight = nav.highlighted
        nav.clear_options()
        nav.add_option(Option(f"Current List: {music.queue_label} ({len(music.tracks)})", id="nav:queue"))
        for name in playlists.names():
            nav.add_option(Option(f"{name} ({len(playlists.tracks_of(name))})", id=f"nav:pl:{name}"))
        nav.add_option(Option("+ New playlist...", id="nav:new"))
        if keep_highlight is not None and keep_highlight < nav.option_count:
            nav.highlighted = keep_highlight

    def _open_nav(self, option_id: str) -> None:
        if option_id == "nav:queue":
            self._list_queue()
        elif option_id == "nav:new":
            self._create_playlist()
            return
        elif option_id.startswith("nav:pl:"):
            self._list_playlist(option_id[len("nav:pl:"):])
        else:
            return
        self.query_one("#tracks", OptionList).focus()

    # ---- view builders (fill #tracks) ------------------------------------------
    def _list_dir(self, rel_dir: Path) -> None:
        """Browse view: rel_dir's immediate subfolders and audio files."""
        if rel_dir != self.current_dir:
            self.selected = set()  # a real navigation, not just a selection redraw
        self.view = "browse"
        music = self.app.music
        self.current_dir = rel_dir
        abs_dir = music.folder / rel_dir
        subdirs = sorted((p for p in abs_dir.iterdir() if p.is_dir()), key=lambda p: p.name.lower())
        files = sorted(
            (p for p in abs_dir.iterdir() if p.suffix.lower() in AUDIO_EXTS),
            key=lambda p: p.name.lower(),
        )

        option_list = self.query_one("#tracks", OptionList)
        option_list.clear_options()
        if rel_dir != Path("."):
            option_list.add_option(Option("../", id="up"))
        for d in subdirs:
            did = f"dir:{d.relative_to(music.folder)}"
            mark = "* " if did in self.selected else "  "
            option_list.add_option(Option(f"{mark}{d.name}/", id=did))
        for f in files:
            fid = f"file:{f}"
            mark = "* " if fid in self.selected else "  "
            option_list.add_option(Option(f"{mark}{f.name}", id=fid))

        current = music.current_track
        if current and music.queue_kind == "folder" and current.parent == abs_dir:
            try:
                option_list.highlighted = option_list.get_option_index(f"file:{current}")
            except Exception:
                pass

    def _list_queue(self) -> None:
        self.view = "queue"
        music = self.app.music
        option_list = self.query_one("#tracks", OptionList)
        option_list.clear_options()
        for i, t in enumerate(music.tracks):
            option_list.add_option(Option(t.stem, id=f"qtrack:{i}"))
        if music.started:
            try:
                option_list.highlighted = option_list.get_option_index(f"qtrack:{music.index}")
            except Exception:
                pass

    def _list_playlist(self, name: str) -> None:
        self.view = "playlist"
        self.open_playlist = name
        option_list = self.query_one("#tracks", OptionList)
        option_list.clear_options()
        for i, t in enumerate(playlists.tracks_of(name)):
            option_list.add_option(Option(t.stem, id=f"pfile:{i}"))

    def _refresh(self) -> None:
        self.query_one("#now-playing", Static).update(_now_playing_text(self.app.music))
        self._build_nav()

    # ---- navigation -------------------------------------------------------------
    def action_cursor_down(self) -> None:
        if isinstance(self.focused, OptionList):
            self.focused.action_cursor_down()

    def action_cursor_up(self) -> None:
        if isinstance(self.focused, OptionList):
            self.focused.action_cursor_up()

    def action_up_dir(self) -> None:
        if self.view in ("queue", "playlist"):
            self._list_dir(Path("."))
        elif self.view == "browse" and self.current_dir != Path("."):
            self._list_dir(self.current_dir.parent)

    def action_back_or_leave(self) -> None:
        """escape/q: go up one level first (a folder, or out of the queue/playlist
        view), then leave the screen once already at the browse root."""
        if self.view != "browse" or self.current_dir != Path("."):
            self.action_up_dir()
        else:
            self.app.pop_screen()

    # ---- selection ----------------------------------------------------------------
    def _highlighted_id(self) -> str | None:
        option_list = self.query_one("#tracks", OptionList)
        if option_list.highlighted is None:
            return None
        return option_list.get_option_at_index(option_list.highlighted).id

    def _open_selected(self, option_id: str | None) -> None:
        if option_id is None:
            return
        if option_id == "up":
            self.action_up_dir()
            return
        if self.view == "browse":
            if option_id.startswith("dir:"):
                self._list_dir(Path(option_id[len("dir:"):]))
            elif option_id.startswith("file:"):
                self._play_library_file(Path(option_id[len("file:"):]))
        elif self.view == "queue":
            if option_id.startswith("qtrack:"):
                self.app.music.play_index(int(option_id[len("qtrack:"):]))
        elif self.view == "playlist":
            if option_id.startswith("pfile:"):
                idx = int(option_id[len("pfile:"):])
                tracks = playlists.tracks_of(self.open_playlist)
                self.app.music.set_queue(tracks, "playlist", self.open_playlist)
                self.app.music.play_index(idx)
        self._build_nav()

    def _play_library_file(self, path: Path) -> None:
        """Scopes the queue to this file's own folder (not the whole library), unless
        the queue is already exactly that folder — so n/p stay local to the folder
        you're browsing, like playing a track inside a regular file manager."""
        music = self.app.music
        rel_dir = path.parent.relative_to(music.folder)
        already_here = music.queue_kind == "folder" and music.queue_name == str(rel_dir)
        if not already_here:
            folder_files = sorted(
                (p for p in path.parent.iterdir() if p.suffix.lower() in AUDIO_EXTS),
                key=lambda p: p.name.lower(),
            )
            music.set_queue(folder_files, "folder", str(rel_dir))
        try:
            index = music.tracks.index(path)
        except ValueError:
            return
        music.play_index(index)

    def _create_playlist(self) -> None:
        def got_name(name: str | None) -> None:
            if name:
                playlists.create(name)
                self._build_nav()

        self.app.push_screen(NamePromptScreen("New playlist name:"), got_name)

    def action_play_selected(self) -> None:
        if isinstance(self.focused, OptionList) and self.focused.id == "nav":
            if self.focused.highlighted is not None:
                self._open_nav(self.focused.get_option_at_index(self.focused.highlighted).id)
        else:
            self._open_selected(self._highlighted_id())

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "nav":
            self._open_nav(event.option.id)
        else:
            self._open_selected(event.option.id)

    # ---- multi-select + playlist editing ---------------------------------------
    def action_toggle_select(self) -> None:
        if self.view != "browse":
            return
        option_id = self._highlighted_id()
        if not option_id or not (option_id.startswith("file:") or option_id.startswith("dir:")):
            return
        self.selected.symmetric_difference_update({option_id})
        keep = self.query_one("#tracks", OptionList).highlighted
        self._list_dir(self.current_dir)
        tracks = self.query_one("#tracks", OptionList)
        if keep is not None and keep < tracks.option_count:
            tracks.highlighted = keep

    def _resolve_paths(self, option_id: str) -> list[Path]:
        if option_id.startswith("file:"):
            return [Path(option_id[len("file:"):])]
        if option_id.startswith("dir:"):
            return scan_tracks(self.app.music.folder / option_id[len("dir:"):])
        return []

    def _selected_paths(self) -> list[Path]:
        """Every marked file/folder's tracks, or — with nothing marked — just the
        highlighted one. Empty outside the browse view or with nothing suitable."""
        if self.view != "browse":
            return []
        ids = self.selected if self.selected else {self._highlighted_id()} - {None}
        paths: list[Path] = []
        for option_id in ids:
            paths.extend(self._resolve_paths(option_id))
        return paths

    def action_enqueue(self) -> None:
        self.app.music.enqueue(self._selected_paths())
        self.selected = set()
        self._list_dir(self.current_dir)
        self._build_nav()

    def action_add_to_playlist(self) -> None:
        paths = self._selected_paths()
        if not paths:
            return

        def got_name(name: str | None) -> None:
            if name:
                playlists.add_paths(name, paths)
                self._build_nav()
            self.selected = set()
            self._list_dir(self.current_dir)

        self.app.push_screen(PlaylistPickScreen(), got_name)

    def action_remove_entry(self) -> None:
        if isinstance(self.focused, OptionList) and self.focused.id == "nav":
            if self.focused.highlighted is None:
                return
            option_id = self.focused.get_option_at_index(self.focused.highlighted).id
            if option_id and option_id.startswith("nav:pl:"):
                playlists.delete(option_id[len("nav:pl:"):])
                self._build_nav()
            return

        option_id = self._highlighted_id()
        if option_id is None:
            return
        if self.view == "queue" and option_id.startswith("qtrack:"):
            idx = int(option_id[len("qtrack:"):])
            music = self.app.music
            if 0 <= idx < len(music.tracks):
                del music.tracks[idx]
                if music.index > idx:
                    music.index -= 1
                elif music.index == idx:
                    music.started = False
                self._list_queue()
        elif self.view == "playlist" and option_id.startswith("pfile:"):
            idx = int(option_id[len("pfile:"):])
            tracks = playlists.tracks_of(self.open_playlist)
            if 0 <= idx < len(tracks):
                playlists.remove_path(self.open_playlist, tracks[idx])
                self._list_playlist(self.open_playlist)
        self._build_nav()

    # ---- transport ----------------------------------------------------------------
    def action_next_track(self) -> None:
        self.app.music.next(manual=True)

    def action_prev_track(self) -> None:
        self.app.music.prev()

    def action_toggle_pause(self) -> None:
        self.app.music.toggle_pause()

    def action_volume_up(self) -> None:
        self.app.music.set_volume(self.app.music.volume + 0.05)

    def action_volume_down(self) -> None:
        self.app.music.set_volume(self.app.music.volume - 0.05)

    def action_toggle_shuffle(self) -> None:
        self.app.music.toggle_shuffle()

    def action_cycle_repeat(self) -> None:
        self.app.music.cycle_repeat()


def music_screen(app: App) -> Screen:
    folder_str = config.load().get("music_folder", "")
    if folder_str and Path(folder_str).is_dir():
        if not app.music.tracks:
            app.music.load_folder(Path(folder_str))
        return MusicScreen()
    return FolderPromptScreen()
