"""Step-through tracer for Bug Hunt: the "hunting aid and the lesson in how to debug" from
PLAN.md section 7. Runs the snippet plus a short call expression inside the exact same sandbox as
sandbox.py (temp dir, stripped env, `-I -S`, hard wall-clock timeout) with sys.settrace recording
(line, function, locals-repr) at each executed line of the snippet's own file, then serializes the
trace back to the parent process as one JSON line on stdout.

Bounded by design, not just by hope: MAX_STEPS caps how many line events are ever recorded (the
tracer disables itself via sys.settrace(None) once the cap is hit, so a hostile infinite loop can't
grow the trace without bound - the subprocess timeout in sandbox.py still kills the process itself),
and REPR_CAP caps the length of every individual value's repr (so one huge local can't blow up the
payload either). Never executes anything beyond the snippet's own bundled code plus the bundled
`run_expr` - never arbitrary/player-authored code beyond the one line Fix mode already lets them
edit before this is called.
"""
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .sandbox import TIMEOUT

MAX_STEPS = 500
REPR_CAP = 120
_MARKER = "@@TRACE@@"

_PRELUDE = f"""
import sys as _sys, json as _json

_STEPS = []
_MAX_STEPS = {MAX_STEPS}
_REPR_CAP = {REPR_CAP}
_TARGET = __file__

def _safe_repr(v):
    try:
        r = repr(v)
    except Exception:
        r = "<unrepr-able>"
    if len(r) > _REPR_CAP:
        r = r[:_REPR_CAP] + "...<truncated>"
    return r

def _tracer(frame, event, arg):
    if frame.f_code.co_filename != _TARGET:
        return _tracer
    if event == "line":
        if len(_STEPS) >= _MAX_STEPS:
            _sys.settrace(None)
            return None
        locs = {{k: _safe_repr(v) for k, v in frame.f_locals.items() if not k.startswith("_")}}
        _STEPS.append({{"line": frame.f_lineno, "func": frame.f_code.co_name, "locals": locs}})
    return _tracer

_sys.settrace(_tracer)
_sys._getframe().f_trace = _tracer
"""

_EPILOGUE = f"""
_sys.settrace(None)
print({_MARKER!r} + _json.dumps({{"steps": _STEPS[:_MAX_STEPS], "error": _ERR}}))
"""


@dataclass
class TraceResult:
    steps: list[dict]
    error: str | None  # the run_expr's traceback text, if it raised (tracing still succeeds either way)
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    truncated: bool

    @property
    def ok(self) -> bool:
        return not self.timed_out and self.exit_code == 0


def trace_snippet(code: str, run_expr: str, timeout: float = TIMEOUT) -> TraceResult:
    """Run `code` then `run_expr` (a short block that calls into it, e.g. a level's `tests` text)
    under a line tracer, inside the same sandbox constraints as sandbox.run_snippet. `run_expr`
    raising (e.g. the buggy version failing its own assertions) does not stop the trace from being
    captured and returned - debugging the failure is the whole point - it is reported separately
    via `TraceResult.error`."""
    indented = "\n".join("    " + ln for ln in run_expr.split("\n"))
    guarded_run = f"try:\n{indented}\nexcept Exception:\n    import traceback as _tb\n    _ERR = _tb.format_exc()\nelse:\n    _ERR = None\n"
    script_body = _PRELUDE + "\n" + code + "\n" + guarded_run + "\n" + _EPILOGUE
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "snippet.py"
        script.write_text(script_body, encoding="utf-8")
        env = {"SYSTEMROOT": os.environ.get("SYSTEMROOT", ""), "PATH": ""}
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-S", str(script)],
                capture_output=True,
                timeout=timeout,
                cwd=tmp,
                env=env,
                text=True,
            )
            steps, error, truncated = _extract(proc.stdout)
            return TraceResult(steps, error, proc.stdout, proc.stderr, proc.returncode, False, truncated)
        except subprocess.TimeoutExpired as exc:
            steps, error, truncated = _extract(exc.stdout or "")
            return TraceResult(steps, error, exc.stdout or "", exc.stderr or "", -1, True, truncated)


def code_line_offset() -> int:
    """How many lines of generated prelude sit before `code` in the traced script - subtract this
    from a step's `line` to get the 1-indexed line number within the original snippet `code`."""
    return _PRELUDE.count("\n") + 1


def _extract(stdout: str) -> tuple[list[dict], str | None, bool]:
    idx = stdout.rfind(_MARKER)
    if idx == -1:
        return [], None, False
    try:
        payload = json.loads(stdout[idx + len(_MARKER):])
    except json.JSONDecodeError:
        return [], None, False
    steps = payload.get("steps", [])
    return steps, payload.get("error"), len(steps) >= MAX_STEPS
