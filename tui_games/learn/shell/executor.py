"""Ties parser.Segment chains to commands.run_command: pipes feed stdout into the next command's
stdin, a trailing redirect writes to a file instead of printing, &&/||/; gate on the previous exit code.
"""
from __future__ import annotations

from .commands import run_command
from .fs import FS, FSError
from .parser import parse


def _expand_command_substitution(fs: FS, line: str) -> str:
    """Replace every unquoted-or-double-quoted $(cmd) with that command's stdout (trailing newlines
    stripped), evaluated recursively against the live fs. A $( inside single quotes is left alone,
    matching real shell quoting rules."""
    out: list[str] = []
    i, n = 0, len(line)
    in_single = False
    while i < n:
        ch = line[i]
        if ch == "'":
            in_single = not in_single
            out.append(ch)
            i += 1
        elif not in_single and line[i:i + 2] == "$(":
            depth, j = 1, i + 2
            while j < n and depth:
                if line[j] == "(":
                    depth += 1
                elif line[j] == ")":
                    depth -= 1
                j += 1
            inner = line[i + 2:j - 1]
            stdout, _code = run_line(fs, inner)
            # unquoted $() word-splits on whitespace in a real shell; collapsing embedded newlines
            # to spaces here gets the common case (e.g. `rm $(find ...)` over several matches) right.
            out.append(stdout.strip("\n").replace("\n", " "))
            i = j
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def run_line(fs: FS, line: str) -> tuple[str, int]:
    """Parse and run one input line. Returns (combined output text for the scrollback, last exit code)."""
    line = _expand_command_substitution(fs, line)
    segments = parse(line, fs.env)
    out_chunks: list[str] = []
    code = 0
    skip = False
    for seg in segments:
        if skip:
            skip = False
            continue
        stdout, code = _run_pipeline(fs, seg.pipeline)
        if stdout:
            out_chunks.append(stdout)
        if seg.joiner == "&&" and code != 0:
            skip = True
        elif seg.joiner == "||" and code == 0:
            skip = True
    return "".join(out_chunks), code


def _run_pipeline(fs: FS, commands) -> tuple[str, int]:
    if not commands:
        return "", 0
    stdin = ""
    stdout, code = "", 0
    for cmd in commands:
        try:
            stdout, stderr, code = run_command(fs, cmd.argv, stdin)
        except FSError as e:
            return str(e) + "\n", 1
        if stderr:
            stdout = stdout + stderr
        stdin = stdout
    last = commands[-1]
    if last.redirect:
        mode, filename = last.redirect
        fs.write(filename, stdout, append=(mode == ">>"))
        return "", code
    return stdout, code
