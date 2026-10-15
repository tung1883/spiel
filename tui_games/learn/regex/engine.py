"""Regex Golf engine. Dialect is Python's `re`. A candidate pattern is checked against a level's
yes/no string lists in a short-lived subprocess with a hard wall-clock timeout, so a catastrophic
pattern like `(a+)+$` cannot hang the game - it is reported as "too slow" instead, which doubles as
the lesson (PLAN.md section 3).
"""
import multiprocessing as mp
import re

TIMEOUT = 0.6  # wall clock from process spawn to kill; generous to absorb Windows spawn overhead


def _match_worker(pattern: str, strings: list[str], q: "mp.Queue") -> None:
    try:
        rx = re.compile(pattern)
    except re.error as exc:
        q.put(("error", str(exc)))
        return
    q.put(("ok", [bool(rx.search(s)) for s in strings]))


def _extract_worker(pattern: str, text: str, q: "mp.Queue") -> None:
    try:
        rx = re.compile(pattern)
    except re.error as exc:
        q.put(("error", str(exc)))
        return
    q.put(("ok", [m.group(0) for m in rx.finditer(text)]))


def _sub_worker(pattern: str, repl: str, text: str, q: "mp.Queue") -> None:
    try:
        rx = re.compile(pattern)
    except re.error as exc:
        q.put(("error", str(exc)))
        return
    try:
        q.put(("ok", rx.sub(repl, text)))
    except (re.error, IndexError) as exc:
        q.put(("error", str(exc)))


def _run_timed(target, args) -> tuple[str, object]:
    """Run `target(*args, q)` in a short-lived subprocess with a hard timeout. Returns
    (kind, payload) with kind in "ok"/"error"/"timeout"/"crashed"."""
    q: mp.Queue = mp.Queue()
    proc = mp.Process(target=target, args=(*args, q), daemon=True)
    proc.start()
    proc.join(TIMEOUT)
    if proc.is_alive():
        proc.terminate()
        proc.join()
        return "timeout", None
    if q.empty():
        return "crashed", None
    return q.get()


def check_extract(pattern: str, text: str, targets: list[str]) -> dict:
    """Extract mode: the pattern's matches (in order, exact substrings) must equal `targets`
    exactly - no missing target, no extra match. Returns {"error","timeout","passed","found"}."""
    empty = {"error": None, "timeout": False, "passed": False, "found": []}
    if not pattern:
        return dict(empty, error="empty pattern")
    try:
        re.compile(pattern)
    except re.error as exc:
        return dict(empty, error=str(exc))
    kind, payload = _run_timed(_extract_worker, (pattern, text))
    if kind == "timeout":
        return dict(empty, timeout=True)
    if kind != "ok":
        return dict(empty, error=payload if isinstance(payload, str) else "pattern evaluation crashed")
    found: list[str] = payload
    return {"error": None, "timeout": False, "passed": found == targets, "found": found}


def check_substitute(pattern: str, repl: str, before: str, after: str) -> dict:
    """Substitute mode: re.sub(pattern, repl, before) must equal `after` exactly.
    Returns {"error","timeout","passed","result"}."""
    empty = {"error": None, "timeout": False, "passed": False, "result": None}
    if not pattern:
        return dict(empty, error="empty pattern")
    try:
        re.compile(pattern)
    except re.error as exc:
        return dict(empty, error=str(exc))
    kind, payload = _run_timed(_sub_worker, (pattern, repl, before))
    if kind == "timeout":
        return dict(empty, timeout=True)
    if kind != "ok":
        return dict(empty, error=payload if isinstance(payload, str) else "pattern evaluation crashed")
    return {"error": None, "timeout": False, "passed": payload == after, "result": payload}


def check(pattern: str, yes: list[str], no: list[str]) -> dict:
    """Returns {"error": str|None, "timeout": bool, "passed": bool, "yes": [bool], "no": [bool]}."""
    empty = {"error": None, "timeout": False, "passed": False, "yes": [False] * len(yes), "no": [False] * len(no)}
    if not pattern:
        return dict(empty, error="empty pattern")
    try:
        re.compile(pattern)
    except re.error as exc:
        return dict(empty, error=str(exc))

    strings = yes + no
    q: mp.Queue = mp.Queue()
    proc = mp.Process(target=_match_worker, args=(pattern, strings, q), daemon=True)
    proc.start()
    proc.join(TIMEOUT)
    if proc.is_alive():
        proc.terminate()
        proc.join()
        return dict(empty, timeout=True)
    if q.empty():
        return dict(empty, error="pattern evaluation crashed")
    kind, payload = q.get()
    if kind == "error":
        return dict(empty, error=payload)
    results: list[bool] = payload
    yes_r, no_r = results[: len(yes)], results[len(yes):]
    passed = all(yes_r) and not any(no_r)
    return {"error": None, "timeout": False, "passed": passed, "yes": yes_r, "no": no_r}
