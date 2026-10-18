"""Per-race typing analytics + a small persistent history."""
import hashlib
import json
import os
import statistics
import time
from collections import Counter
from pathlib import Path

HISTORY = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "spiel" / "typeracer-history.json"
GHOSTS = HISTORY.with_name("typeracer-ghosts.json")
SPARK = "▁▂▃▄▅▆▇"  # partial blocks, 1/8..7/8


class RaceStats:
    def __init__(self, words: list[str]):
        self.words = words
        self.total_chars = len(" ".join(words))
        self.start = 0.0
        self.end = 0.0
        self.keys = 0  # printable keystrokes
        self.correct = 0
        self.backspaces = 0
        self.missed: Counter = Counter()  # expected char -> times mistyped
        self.word_end: dict[int, float] = {}
        self.error_times: list[float] = []  # ms since start of each mistyped key
        self.curve: list[tuple[float, int]] = []  # (ms since start, correct chars typed so far)

    def key(self, now: float, ok: bool, expected: str | None) -> None:
        if not self.start:
            self.start = now
        self.keys += 1
        if ok:
            self.correct += 1
        else:
            self.missed[expected or "(extra)"] += 1
            self.error_times.append(now - self.start)

    def backspace(self, now: float) -> None:
        if not self.start:
            self.start = now
        self.backspaces += 1

    def progress(self, now: float, chars: int) -> None:
        if self.start:
            self.curve.append((now - self.start, chars))

    def word_done(self, wi: int, now: float) -> None:
        self.word_end[wi] = now

    def finish(self, now: float) -> None:
        self.end = now

    # ---- derived ----------------------------------------------------------
    def elapsed_min(self, now: float | None = None) -> float:
        if not self.start:
            return 0.0
        return max(((self.end or now or time.time() * 1000) - self.start) / 60000, 1e-9)

    def accuracy(self) -> float:
        return 100.0 * self.correct / self.keys if self.keys else 100.0

    def raw_wpm(self, now: float | None = None) -> float:
        m = self.elapsed_min(now)
        return self.keys / 5 / m if m else 0.0

    def net_wpm(self, chars: int, now: float | None = None) -> float:
        m = self.elapsed_min(now)
        return chars / 5 / m if m else 0.0

    def word_wpms(self) -> list[tuple[int, float]]:
        out, prev = [], self.start
        for i in sorted(self.word_end):
            dur = self.word_end[i] - prev
            prev = self.word_end[i]
            if dur > 0:
                out.append((i, (len(self.words[i]) + 1) / 5 / (dur / 60000)))
        return out

    def consistency(self) -> float:
        w = [v for _, v in self.word_wpms()]
        if len(w) < 3:
            return 100.0
        return max(0.0, 100.0 * (1 - statistics.pstdev(w) / statistics.mean(w)))

    def wpm_series(self, cols: int) -> list[float]:
        """Speed per time column, in WPM (3-column moving average over correct chars typed)."""
        if len(self.curve) < 2:
            return []
        total = self.curve[-1][0] or 1
        at, j, c = [], 0, 0
        for i in range(cols + 1):  # chars typed by the end of each column
            edge = total * i / cols
            while j < len(self.curve) and self.curve[j][0] <= edge:
                c = self.curve[j][1]
                j += 1
            at.append(c)
        col_min = total / cols / 60000
        raw = [max(0, at[i + 1] - at[i]) / 5 / col_min for i in range(cols)]
        return [sum(raw[max(0, i - 1):i + 2]) / len(raw[max(0, i - 1):i + 2]) for i in range(cols)]

    def chart(self, cols: int = 56, rows: int = 8) -> list[str]:
        """WPM over time as a block chart with y axis (WPM), x axis (seconds) and an error marker row."""
        series = self.wpm_series(cols)
        if not series:
            return []
        total = self.curve[-1][0]
        top = max(20, -(-int(max(series)) // 20) * 20)  # multiple of 20 so every 2nd-row label is a whole number
        out = ["WPM over time"]
        for r in range(rows, 0, -1):  # r = row from the bottom, 1-based
            label = f"{top * r // rows:>4}" if r % 2 == 0 else "    "
            line = ""
            for v in series:
                eighths = v / top * rows * 8 - (r - 1) * 8
                line += "█" if eighths >= 8 else SPARK[int(eighths) - 1] if eighths >= 1 else " "
            out.append(f"{label} ┤{line}")
        secs = total / 1000
        step = next((st for st in (0.5, 1, 2, 5, 10, 15, 20, 30, 60, 120, 300, 600) if secs / st <= 7), 1200)
        tick_cols = {}  # column -> label, ticks at round seconds
        k = 0
        while k * step <= secs:
            tick_cols[min(cols - 1, round(k * step / secs * cols))] = f"{k * step:g}s"
            k += 1
        axis = "".join("┬" if i in tick_cols else "─" for i in range(cols))
        out.append(f"   0 ┴{axis}")
        ticks, end = [" "] * (cols + 8), -1
        for col, lab in sorted(tick_cols.items()):
            if col > end:  # skip a label that would touch the previous one
                ticks[col:col + len(lab)] = lab
                end = col + len(lab)
        out.append("      " + "".join(ticks).rstrip() + f"   (race: {secs:.1f}s)")
        marks = [" "] * cols
        for t in self.error_times:
            marks[min(cols - 1, int(t / total * cols))] = "x"
        if "x" in marks:
            out.append("errors" + "".join(marks) + "  (x = mistyped key)")
        avg = self.net_wpm(self.total_chars)
        out.append(f"      avg {avg:.0f} wpm, peak {max(series):.0f} wpm (smoothed), low {min(series):.0f} wpm")
        return out

    def live_line(self, chars: int, now: float) -> str:
        return (f"{self.net_wpm(chars, now):.0f} wpm  raw {self.raw_wpm(now):.0f}  acc {self.accuracy():.1f}%  "
                f"errors {self.keys - self.correct}")

    def report(self, mode: str, chars: int | None = None) -> str:
        """chars = correct chars typed (all of them on a finished race)."""
        chars = self.total_chars if chars is None else chars
        wp = self.word_wpms()
        slow = sorted((x for x in wp if len(self.words[x[0]]) >= 3), key=lambda x: x[1])[:3]
        fast = max(wp, key=lambda x: x[1]) if wp else None
        lines = [
            f"WPM {self.net_wpm(chars):.1f}   raw {self.raw_wpm():.1f}   accuracy {self.accuracy():.1f}%   "
            f"consistency {self.consistency():.0f}%",
            f"time {self.elapsed_min() * 60:.1f}s   chars {chars}/{self.total_chars}   errors {self.keys - self.correct}"
            f"   backspaces {self.backspaces}",
        ]
        chart = self.chart()
        if chart:
            lines += ["", *chart, ""]
        if fast:
            lines.append(f"fastest word '{self.words[fast[0]]}' {fast[1]:.0f} wpm")
        if slow:
            lines.append("slowest words " + ", ".join(f"'{self.words[i]}' {v:.0f}" for i, v in slow))
        if self.missed:
            lines.append("most missed keys " + "  ".join(f"{k!r}x{n}" for k, n in self.missed.most_common(5)))
        lines.append(history_summary(mode))
        return "\n".join(lines)


def _load() -> list[dict]:
    try:
        return json.loads(HISTORY.read_text("utf-8"))
    except (OSError, ValueError):
        return []


def save_result(mode: str, stats: RaceStats) -> None:
    hist = _load()
    hist.append({"t": int(time.time()), "mode": mode, "wpm": round(stats.net_wpm(stats.total_chars), 1),
                 "raw": round(stats.raw_wpm(), 1), "acc": round(stats.accuracy(), 1), "chars": stats.total_chars})
    try:
        HISTORY.parent.mkdir(parents=True, exist_ok=True)
        HISTORY.write_text(json.dumps(hist[-500:]), "utf-8")
    except OSError:
        pass


def history_summary(mode: str) -> str:
    """Stats over previous races (call before save_result so the current race is not included)."""
    hist = [h for h in _load() if h.get("mode") == mode]
    if not hist:
        return "first recorded race in this mode"
    last = [h["wpm"] for h in hist[-10:]]
    return f"history ({len(hist)} races): best {max(h['wpm'] for h in hist):.0f}   avg last {len(last)}: {sum(last) / len(last):.0f}"


# ---- ghosts: best run per text, replayed next time that text comes up ----------
def _gkey(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def _gload() -> dict:
    try:
        return json.loads(GHOSTS.read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def load_ghost(text: str) -> dict | None:
    """{'wpm': float, 'curve': [[ms, chars], ...]} of the best finished run on this text."""
    return _gload().get(_gkey(text))


def save_ghost(text: str, stats: RaceStats) -> bool:
    """Keep this run if it beats the stored one. Returns True when it is the new best."""
    wpm = stats.net_wpm(stats.total_chars)
    ghosts = _gload()
    old = ghosts.get(_gkey(text))
    if old and old["wpm"] >= wpm:
        return False
    step = max(1, len(stats.curve) // 300)
    curve = [[round(t), c] for t, c in stats.curve[::step]]
    if stats.curve and curve[-1][0] != round(stats.curve[-1][0]):
        curve.append([round(stats.curve[-1][0]), stats.curve[-1][1]])
    ghosts.pop(_gkey(text), None)
    ghosts[_gkey(text)] = {"wpm": round(wpm, 1), "curve": curve}
    while len(ghosts) > 300:  # drop oldest
        ghosts.pop(next(iter(ghosts)))
    try:
        GHOSTS.parent.mkdir(parents=True, exist_ok=True)
        GHOSTS.write_text(json.dumps(ghosts), "utf-8")
    except OSError:
        pass
    return True


def ghost_chars(ghost: dict, ms: float) -> int:
    """Correct chars the ghost had typed `ms` after its first key."""
    n = 0
    for t, c in ghost["curve"]:
        if t > ms:
            break
        n = c
    return n
