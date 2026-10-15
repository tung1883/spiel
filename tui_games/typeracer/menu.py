"""Settings screen: typeracer (connection, mode, instant death, text/language) and chess (opponent, level). Saved in config.json."""
from textual.app import ComposeResult
from textual.binding import Binding
from rich.text import Text
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from .. import config
from .screen import RaceScreen

CONNECTION = [("online", "online"), ("offline", "offline")]
MODES = [("race", "race"), ("practice", "practice"), ("qotd", "qotd")]
DEATH = [("off", "off"), ("on", "on")]
CONTENT = [
    ("english", "play"), ("dictionary", "dictionary"), ("numbers", "numbers"), ("repeat", "repeat"), ("code", "code"),
]
# Languages typeracer.com has a universe for (CJK / RTL / Thai omitted: need IME or shaping a terminal can't do)
LANGUAGES = [
    ("es", "Spanish / español"), ("fr", "French / français"), ("de", "German / Deutsch"), ("it", "Italiano"),
    ("pt", "Português"), ("ru", "Russian / русский"), ("pl", "Polish / polski"), ("nl", "Dutch / Nederlands"),
    ("sv", "Swedish / svenska"), ("da", "Danish / dansk"), ("no", "Norwegian / Norsk"), ("fi", "Finnish / suomi"),
    ("cs", "Czech / čeština"), ("sk", "Slovak / slovenčina"), ("hu", "Hungarian / Magyar"), ("ro", "Romanian / română"),
    ("bg", "Bulgarian / български"), ("el", "Greek / Ελληνικά"), ("tr", "Turkish / Türkçe"), ("uk", "Ukrainian / Українська"),
    ("hr", "Croatian / hrvatski"), ("sr", "Serbian / српски"), ("sl", "Slovenian / slovenščina"), ("lt", "Lithuanian / lietuvių"),
    ("lv", "Latvian / latviešu"), ("et", "Estonian / eesti"), ("ca", "Catalan / Català"), ("vi", "Vietnamese / Tiếng Việt"),
    ("id", "Bahasa Indonesia"), ("ms", "Malay / bahasa Melayu"), ("tl", "Filipino / Tagalog"), ("hi", "Hinglish"),
    ("af", "Afrikaans"), ("ga", "Irish / Gaeilge"), ("cy", "Welsh / Cymraeg"), ("mk", "Macedonian / македонски"),
    ("be", "Belarusian / Беларуская"), ("de_dictionary", "Deutsch Wörterbuch"), ("pt_dictionary", "Português Dictionary"),
]
CONTENT += [(label, f"lang_{code}") for code, label in LANGUAGES]

CHESS = [("offline", "offline"), ("lichess", "lichess"), ("chess.com", "chesscom")]
LEVEL = [("easy", "1"), ("medium", "2"), ("hard", "3")]

DEFAULTS = {"connection": "online", "mode": "race", "death": "off", "content": "play", "chess": "offline", "level": "1"}
FIELDS = {"connection": CONNECTION, "mode": MODES, "death": DEATH, "content": CONTENT, "chess": CHESS, "level": LEVEL}


def load_settings() -> dict:
    saved = config.load().get("typeracer", {})
    return {k: saved[k] if saved.get(k) in [v for _, v in FIELDS[k]] else DEFAULTS[k] for k in DEFAULTS}


def race_screen(s: dict) -> RaceScreen:
    """Settings -> the RaceScreen that plays them."""
    death = s["death"] == "on"
    if s["connection"] == "offline":
        return RaceScreen("offline", s["content"], death)
    mode = {"race": "auto", "practice": "practice", "qotd": "qotd"}[s["mode"]]
    universe = s["content"]
    if death and universe == "play":
        universe = "accuracy"  # the site's own Instant Death universe
    return RaceScreen(mode, universe, death)


def chess_screen(s: dict) -> Screen:
    """Settings -> what the Chess row opens. Offline starts at once; the online sites still need a time control."""
    from ..chess.screen import ChessComMenu, GameScreen, LichessMenu

    if s["chess"] == "lichess":
        return LichessMenu()
    if s["chess"] == "chesscom":
        return ChessComMenu()
    from ..chess.local import LocalGame

    level = int(s["level"])
    return GameScreen(ai_level=level, api_factory=lambda: LocalGame(level))


class SettingsScreen(Screen):
    """vim-ish settings list: j/k move, h/l (or Enter/Space) change, Esc back. Saved on every change."""

    BINDINGS = [
        Binding("escape,q", "app.pop_screen", "Back"),
        Binding("up,k", "move(-1)", "Up", show=False),
        Binding("down,j", "move(1)", "Down", show=False),
        Binding("left,h", "change(-1)", "Prev"),
        Binding("right,l,enter,space", "change(1)", "Next"),
    ]
    CSS = "SettingsScreen #body {padding: 1 2;}"
    ROWS = [("connection", "connection"), ("mode", "mode"), ("death", "instant death"), ("content", "text"),
            ("chess", "opponent"), ("level", "level")]
    SECTIONS = {"connection": "typeracer", "chess": "chess"}

    def __init__(self):
        super().__init__()
        self.s = load_settings()
        self.row = 0

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(id="body")
        yield Footer()

    def on_mount(self) -> None:
        self._draw()

    def _opts(self, key: str):
        return FIELDS[key]

    def _idx(self, key: str) -> int:
        return [v for _, v in self._opts(key)].index(self.s[key])

    def _draw(self) -> None:
        t = Text("settings\n", style="bold")
        accent = self.app.theme_variables.get("primary", "#0178d4")  # follow the app theme (blue)
        offline = self.s["connection"] == "offline"
        for i, (key, name) in enumerate(self.ROWS):
            if key in self.SECTIONS:
                t.append(f"\n{self.SECTIONS[key]}\n", style="bold underline")
            sel = i == self.row
            dim = (offline and key == "mode") or (self.s["chess"] != "offline" and key == "level")
            opts = self._opts(key)
            cur = self._idx(key)
            t.append("> " if sel else "  ", style=f"bold {accent}")
            t.append(f"{name:<16}", style="dim" if dim else "bold")
            if len(opts) <= 4:  # inline: [chosen] others
                for j, (label, _) in enumerate(opts):
                    if j == cur:
                        t.append(f"[{label}]", style=f"reverse {accent}" if sel else accent)
                    else:
                        t.append(f" {label} ", style="dim")
                    t.append(" ")
            else:  # long list: show current with position
                t.append(f"< {opts[cur][0]} >", style=f"reverse {accent}" if sel else accent)
                t.append(f"  {cur + 1}/{len(opts)}", style="dim")
            t.append("\n")
        if not offline and self.s["mode"] == "qotd" and self.s["content"] != "play":
            t.append("\nqotd only exists for english text", style="dim")
        t.append("\n\nj/k move   h/l or enter change   esc back   (saved automatically)", style="dim")
        self.query_one("#body", Static).update(t)

    def action_move(self, d: str) -> None:
        self.row = (self.row + int(d)) % len(self.ROWS)
        self._draw()

    def action_change(self, d: str) -> None:
        key = self.ROWS[self.row][0]
        opts = self._opts(key)
        self.s[key] = opts[(self._idx(key) + int(d)) % len(opts)][1]
        cfg = config.load()
        cfg["typeracer"] = self.s
        config.save(cfg)
        self._draw()
