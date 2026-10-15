"""Port of TypeRacer's keylog (TLv1) recorder. Format reverse-engineered from the web client."""
import re


def _diff(old: str, new: str) -> list[tuple[int, str, str]]:
    """Edit script turning old into new: (index, '+'|'-'|'$', char)."""
    if old == new:
        return []
    a, b = list(old), list(new)
    i = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        i += 1
    a, b = a[i:], b[i:]
    s, c = len(a), len(b)
    dp = [[0] * (c + 1) for _ in range(s + 1)]
    for x in range(s + 1):
        dp[x][0] = x
    for y in range(c + 1):
        dp[0][y] = y
    for x in range(1, s + 1):
        for y in range(1, c + 1):
            dp[x][y] = min(dp[x - 1][y] + 1, dp[x][y - 1] + 1, dp[x - 1][y - 1] + (a[x - 1] != b[y - 1]))
    ops = []
    d, f = s, c
    while d > 0 or f > 0:
        e = dp[d][f]
        if d > 0 and f > 0 and a[d - 1] == b[f - 1] and e == dp[d - 1][f - 1]:
            d -= 1
            f -= 1
        elif d > 0 and e == dp[d - 1][f] + 1:
            ops.append(("-", d - 1, f))
            d -= 1
        elif f > 0 and e == dp[d][f - 1] + 1:
            ops.append(("+", d, f - 1))
            f -= 1
        else:
            ops.append(("$", d - 1, f - 1))
            d -= 1
            f -= 1
    out = []
    shift = 0
    for typ, ai, bj in reversed(ops):
        idx = i + ai + shift
        if typ == "-":
            out.append((idx, "-", a[ai]))
            shift -= 1
        else:
            out.append((idx, typ, b[bj]))
            if typ == "+":
                shift += 1
    return out


def _tok(ch: str, dt: float) -> str:
    return ("\b" if re.match(r"[0-9-]", ch) else "") + ch + str(max(0, round(dt)))


class Keylog:
    def __init__(self, text: str, language: str = "en"):
        self.text, self.language = text, language
        self._last = self._edit_base = self._edit_last = 0
        self._pending: list[tuple[int, str]] = []
        self._keys = ""
        self._edits = ""
        self._prefix = 0

    def seed(self, ts_ms: float) -> None:
        self._last = self._edit_base = self._edit_last = ts_ms

    def record_input(self, prev: str, cur: str, now: float, word_offset: int) -> None:
        d = _diff(prev, cur)
        if d:
            base = self._edit_base if not self._pending else self._edit_last
            self._pending.append((max(0, now - base), "".join(f"{i}{t}{c}" for i, t, c in d)))
            self._edit_last = now
        p = 0
        while p < len(cur) and word_offset + p < len(self.text) and cur[p] == self.text[word_offset + p] and cur[p] != " ":
            p += 1
        for e in range(self._prefix, p):
            self._keys += _tok(self.text[word_offset + e] if word_offset + e < len(self.text) else "", now - self._last)
            self._last = now
        self._prefix = max(self._prefix, p)

    def word_boundary(self, word_offset: int, now: float) -> None:
        self._keys += _tok(" ", now - self._last)
        self._last = now
        self.seal(word_offset)
        self._prefix = 0
        self._edit_base = self._edit_last = now

    def seal(self, word_offset: int) -> None:
        if not self._pending:
            return
        parts = [str(word_offset), str(len(self._pending))]
        for ts, tok in self._pending:
            parts += [str(round(ts)), tok]
        chunk = ",".join(parts)
        self._edits = f"{self._edits},{chunk}" if self._edits else chunk
        self._pending = []

    def build(self) -> str:
        return f"TLv1,{self.language},{len(self.text)},{self._keys}|{self._edits},"
