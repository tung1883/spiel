"""Runs a Python snippet in a sandboxed subprocess: fresh temp dir, stripped env, isolated
interpreter (-I -S, no user site-packages, no network reachable beyond the loopback-less default),
hard wall-clock timeout. Never executes anything beyond the exact script text handed to it - the
caller is responsible for only ever building that text from bundled level code plus the player's
one-line edit, never from arbitrary input.

Deferred: a sys.addaudithook-based network/file block (PLAN.md section 7's "no network" safeguard
beyond temp-cwd + stripped env + timeout) - noted as out of scope for this pass.
"""
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

TIMEOUT = 2.0


@dataclass
class RunResult:
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool

    @property
    def ok(self) -> bool:
        return not self.timed_out and self.exit_code == 0


def run_snippet(code: str, timeout: float = TIMEOUT) -> RunResult:
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "snippet.py"
        script.write_text(code, encoding="utf-8")
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
            return RunResult(proc.stdout, proc.stderr, proc.returncode, False)
        except subprocess.TimeoutExpired as exc:
            return RunResult(exc.stdout or "", exc.stderr or "", -1, True)
