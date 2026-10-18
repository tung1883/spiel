import asyncio
import time

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Static

from ..base import AppScreen
from .client import RaceState, TypeRacerClient, TypeRacerError
from .analytics import RaceStats, ghost_chars, load_ghost, save_ghost, save_result
from .keylog import Keylog
from .local import LocalTypeRacerClient, remember_quote

OVERTYPE_LIMIT = 12
LOCAL_COUNTDOWN = {"practice": 3, "qotd": 3}  # offline has none: the timer starts at your first key


def _now_ms() -> float:
    return time.time() * 1000


class RaceScreen(AppScreen):
    BINDINGS = [
        Binding("escape", "leave", "Leave"),
        Binding("enter", "again", "New race (when done)"),
        Binding("r", "replay", "Replay + ghost (when done)"),
    ]
    CSS = """
    #info {height: 3; padding: 1 2;}
    #players {height: auto; padding: 0 2;}
    #text {padding: 1 2; height: auto;}
    #input {padding: 0 2; height: auto; color: $text-muted;}
    #stats {padding: 1 2; height: auto; color: $text-muted;}
    """

    def __init__(self, mode: str, universe: str = "play", death: bool = False):
        super().__init__()
        self.mode = mode  # auto | practice | qotd | offline
        self.base_mode = mode
        self.universe = universe
        self.death = death or universe == "accuracy"  # instant death: first wrong key ends the race
        self.client: TypeRacerClient | LocalTypeRacerClient | None = None
        self.replay_text = ""
        self._reset()

    def _reset(self) -> None:
        self.state: RaceState | None = None
        self.words: list[str] = []
        self.offsets: list[int] = []
        self.wi = 0
        self.buf = ""
        self.keylog: Keylog | None = None
        self.stats: RaceStats | None = None
        self.report = ""
        self.ghost: dict | None = None  # best earlier run on this text
        self.started_at = 0.0
        self.go_at = 0.0  # local ms when typing opens
        self.finished = False
        self.failed = False
        self.error = ""
        self._poll_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static("Connecting...", id="info")
        yield Static(id="players")
        yield Static(id="text")
        yield Static(id="input")
        yield Static(id="stats")
        yield Footer()

    async def on_mount(self) -> None:
        super().on_mount()
        self.client = self._make_client()
        self.set_interval(0.1, self._redraw)
        await self._join()

    def _make_client(self):
        return LocalTypeRacerClient(self.universe) if self.mode == "offline" else TypeRacerClient(self.universe)

    async def _join(self) -> None:
        self._reset()
        try:
            if self.replay_text:  # same text again, solo, against the ghost
                if self.mode != "offline":
                    await self.client.close()
                    self.mode = "offline"
                    self.client = self._make_client()
                self.client.forced = self.replay_text
            elif self.mode == "offline":
                self.client.forced = ""
            if not self.client.uid:
                await self.client.start()
            self.state = RaceState(await self.client.match(self.mode))
        except Exception as e:  # network / server errors shown in UI
            self.error = str(e)
            return
        text = self.state.text["text"]
        if self.mode != "offline":
            remember_quote(text, self.universe)
        self.words = text.split(" ")
        o = 0
        for w in self.words:
            self.offsets.append(o)
            o += len(w) + 1
        self.keylog = Keylog(text, self.state.text.get("language", "en"))
        self.stats = RaceStats(self.words)
        self.ghost = load_ghost(text)
        if self.mode in LOCAL_COUNTDOWN:
            self.go_at = _now_ms() + LOCAL_COUNTDOWN[self.mode] * 1000
        self._poll_task = asyncio.create_task(self._poll_loop())

    # ---- network loop -------------------------------------------------
    def _typing_open(self) -> bool:
        if not self.state or self.finished or self.failed or self.error:
            return False
        if self.mode == "offline":
            return True
        if self.mode in LOCAL_COUNTDOWN:
            return _now_ms() >= self.go_at
        starts = self.state.game.get("raceStartsAt")
        return bool(starts) and _now_ms() + self.state.server_offset >= starts

    async def _poll_loop(self) -> None:
        st = self.state
        while st is self.state and not self.error:
            try:
                sent = _now_ms()
                since = st.game.get("updatedAt", 0)
                if self.started_at and not self.finished:
                    data = await self.client.action(action="progress", gameId=st.id, wordsTyped=self.wi, since=since)
                else:
                    data = await self.client.action(action="poll", gameId=st.id, since=since)
                st.merge(data, (sent + _now_ms()) / 2)
                if self.failed or (self.finished and self.client.uid in st.results and st.status == "finished"):
                    return
            except TypeRacerError as e:
                self.error = str(e)
                return
            except Exception:
                pass  # transient network error; retry next tick
            await asyncio.sleep(0.4)

    async def _send_finish(self) -> None:
        self.keylog.seal(self.offsets[-1])
        try:
            self.state.merge(await self.client.action(action="finish", gameId=self.state.id, keylog=self.keylog.build()))
        except TypeRacerError as e:
            self.error = str(e)

    async def _send_start(self) -> None:
        try:
            await self.client.action(action="start-race", gameId=self.state.id)
        except TypeRacerError as e:
            self.error = str(e)

    # ---- input --------------------------------------------------------
    def _correct_prefix(self) -> int:
        w, n = self.words[self.wi], 0
        while n < len(self.buf) and n < len(w) and self.buf[n] == w[n]:
            n += 1
        return n

    async def on_key(self, event: events.Key) -> None:
        if event.key in ("escape", "enter") or not self._typing_open():
            return
        word_kill = event.key in ("ctrl+backspace", "ctrl+w")
        if event.key == "backspace" or word_kill:
            ch = None
        elif event.character and event.character.isprintable():
            ch = event.character
        else:
            return
        event.stop()
        now = _now_ms()
        if not self.started_at:
            self.started_at = now
            self.keylog.seed(now - 1)
            if self.mode in LOCAL_COUNTDOWN or self.mode == "offline":
                asyncio.create_task(self._send_start())
        word, off = self.words[self.wi], self.offsets[self.wi]
        last = self.wi == len(self.words) - 1
        prev = self.buf
        if word_kill:
            new = ""
        elif ch is None:
            new = prev[:-1]
        elif len(prev) >= self._correct_prefix() + OVERTYPE_LIMIT:
            return
        else:
            new = prev + ch
        expected = word if last else word + " "
        if ch is None:
            self.stats.backspace(now)
        else:
            ok = expected.startswith(new)
            self.stats.key(now, ok, expected[len(prev)] if len(prev) < len(expected) else None)
            if self.death and not ok:
                self._fail()
                return
        self.keylog.record_input(prev, new, now, off)
        if not last and new == expected:
            self.keylog.word_boundary(off, now)
            self.stats.word_done(self.wi, now)
            self.wi += 1
            self.buf = ""
        else:
            self.buf = new
            if last and new == word:
                self.finished = True
                self.stats.word_done(self.wi, now)
                self.stats.finish(now)
                self.wi = len(self.words)
                self.report = self.stats.report(self.mode_key())  # before save_result: history excludes this race
                self.report += self._ghost_verdict()
                save_result(self.mode_key(), self.stats)
                save_ghost(" ".join(self.words), self.stats)
                asyncio.create_task(self._send_finish())
        self.stats.progress(now, self._chars_done())
        self._redraw()  # echo keystroke now, not on next 100ms tick

    def _ghost_verdict(self) -> str:
        mine = self.stats.net_wpm(self.stats.total_chars)
        if not self.ghost:
            return "\nghost: first run on this text saved - press r to race it"
        diff = mine - self.ghost["wpm"]
        word = "beat" if diff > 0 else "lost to"
        saved = "  - new ghost saved" if diff > 0 else ""
        return f"\nghost: you {word} your best by {abs(diff):.1f} wpm (best was {self.ghost['wpm']:.0f}){saved}"

    def mode_key(self) -> str:
        """History bucket: universe (+ mode when solo)."""
        return self.universe if self.mode == "auto" else f"{self.universe}:{self.mode}"

    def _fail(self) -> None:
        self.failed = True
        self.stats.finish(_now_ms())
        self.report = self.stats.report(self.mode_key(), self._chars_done())
        if self.mode != "offline" and self.state:
            asyncio.create_task(self._send_fail())
        self._redraw()

    async def _send_fail(self) -> None:
        try:
            await self.client.action(action="fail", gameId=self.state.id)
        except Exception:
            pass

    # ---- actions ------------------------------------------------------
    async def action_again(self) -> None:
        if self.finished or self.failed or self.error:
            await self._leave_race()
            self.replay_text = ""
            if self.mode != self.base_mode:  # leave replay: back to the configured mode
                self.mode = self.base_mode
                self.client = self._make_client()
            await self._join()

    async def action_replay(self) -> None:
        if (self.finished or self.failed) and self.words:
            text = " ".join(self.words)
            await self._leave_race()
            self.replay_text = text
            await self._join()

    async def _leave_race(self) -> None:
        if self._poll_task:
            self._poll_task.cancel()
        st = self.state
        if st and st.id:
            try:
                await self.client.action(action="leave-race", gameId=st.id)
            except Exception:
                pass

    async def action_leave(self) -> None:
        await self._leave_race()
        await self.client.close()
        self.app.pop_screen()

    # ---- rendering ----------------------------------------------------
    def _chars_done(self) -> int:
        if self.wi >= len(self.words):
            return self.stats.total_chars
        return self.offsets[self.wi] + self._correct_prefix()

    def _wpm(self) -> float:
        if not self.started_at or not self.words:
            return 0.0
        if self.wi >= len(self.words):
            chars = sum(len(w) + 1 for w in self.words) - 1
        else:
            chars = self.offsets[self.wi] + self._correct_prefix()
        mins = (_now_ms() - self.started_at) / 60000
        return chars / 5 / mins if mins > 0 else 0.0

    def _redraw(self) -> None:
        info, players, text, inp, stats = (
            self.query_one(f"#{i}", Static) for i in ("info", "players", "text", "input", "stats")
        )
        if self.error:
            info.update(Text(f"Error: {self.error}   (Esc leave, Enter retry)", style="bold red"))
            return
        st = self.state
        if not st:
            return
        now = _now_ms()
        if self.failed:
            info.update(Text("DEAD - wrong key. Enter = new race, r = replay vs ghost, Esc = back", style="bold red"))
        elif self.finished:
            info.update(Text("Finished! Enter = new race, r = replay vs ghost, Esc = back", style="bold green"))
        elif self._typing_open():
            msg = ("Start typing - the timer starts at your first key"
                   if self.mode == "offline" and not self.started_at else "GO! Start typing")
            info.update(Text(msg, style="bold green"))
        elif self.mode in LOCAL_COUNTDOWN:
            info.update(Text(f"Starting in {max(0, (self.go_at - now) / 1000):.0f}s", style="bold yellow"))
        elif st.game.get("raceStartsAt"):
            left = (st.game["raceStartsAt"] - now - st.server_offset) / 1000
            info.update(Text(f"Race starts in {max(0, left):.0f}s  ({len(st.game.get('players', []))} racers)", style="bold yellow"))
        else:
            info.update(Text("Waiting for racers...", style="yellow"))
        total = max(1, len(self.words))
        players.update(self._render_players(st, total, now))
        text.update(self._render_text())
        inp.update(self._render_input())
        extra = ""
        mine = st.results.get(self.client.uid)
        if isinstance(mine, dict):
            extra = "   result: " + ", ".join(
                f"{k}={round(v, 1) if isinstance(v, float) else v}" for k, v in mine.items() if k in ("wpm", "accuracy", "rank", "points")
            )
        if (self.finished or self.failed) and self.report:
            stats.update(self.report + (f"\n{extra.strip()}" if extra else ""))
        else:
            live = self.stats.live_line(self._chars_done(), now) if self.stats and self.started_at else "0 wpm"
            stats.update(f"{live}   word {min(self.wi + 1, total)}/{total}{extra}")

    def _ghost_frac(self, now: float) -> float:
        """Ghost's progress 0..1 (it starts when you press your first key)."""
        if not self.ghost or not self.stats:
            return 0.0
        ms = now - self.started_at if self.started_at else 0
        return min(1.0, ghost_chars(self.ghost, ms) / max(1, self.stats.total_chars))

    def _render_players(self, st: RaceState, total: int, now: float) -> Text:
        accent = self.app.theme_variables.get("primary", "#0178d4")
        width = 36
        t = Text()
        uids = st.game.get("players", []) or list(st.progress)
        others = [u for u in uids if u != self.client.uid]
        rows = []  # (label, fraction, style, tail)
        mine = st.results.get(self.client.uid)
        rows.append(("you", min(self.wi, total) / total, f"bold {accent}",
                     f"{mine['wpm']:.0f} wpm" if isinstance(mine, dict) and "wpm" in mine else f"{min(self.wi, total)}/{total}"))
        for n, uid in enumerate(others, 1):
            name = st.name(uid)
            label = f"{name} {n}" if name == "Guest" else name
            words = st.progress.get(uid, 0)
            res = st.results.get(uid)
            done = isinstance(res, dict) and "wpm" in res
            rows.append((label, min(words, total) / total, "green" if done else "white",
                         f"{res['wpm']:.0f} wpm" if done else f"{min(words, total)}/{total}"))
        if self.ghost:
            rows.append((f"ghost {self.ghost['wpm']:.0f}wpm", self._ghost_frac(now), "magenta", ""))
        if not others and self.mode not in ("offline", "practice", "qotd"):
            t.append("waiting for other racers...\n", style="dim")
        for label, frac, style, tail in rows:
            filled = int(width * frac)
            t.append(f"{label[:16]:<16} ", style=style)
            t.append("█" * filled, style=style)
            t.append("░" * (width - filled), style="dim")
            t.append(f" {tail}\n")
        return t

    def _render_input(self) -> Text:
        t = Text("> ")
        if self.wi >= len(self.words) or not self.buf:
            t.append(self.buf)
            return t
        good = self._correct_prefix()
        t.append(self.buf[:good], style="green")
        t.append(self.buf[good:], style="white on red")
        return t

    def _render_text(self) -> Text:
        t = Text()
        if not self.words:
            return t
        full = " ".join(self.words)
        if self.wi >= len(self.words):
            t.append(full, style="green")
            return t
        ok = self.offsets[self.wi] + self._correct_prefix()
        bad = max(0, len(self.buf) - self._correct_prefix())
        t.append(full[:ok], style="green")
        wrong_end = min(len(full), ok + bad)
        t.append(full[ok:wrong_end], style="white on red")
        if wrong_end < len(full):
            t.append(full[wrong_end], style="reverse")
            t.append(full[wrong_end + 1:], style="dim")
        return t
