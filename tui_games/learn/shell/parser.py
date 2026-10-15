"""Tiny POSIX-ish tokenizer/grammar: quotes, $VAR expansion, pipes, redirects, && || ;. $(cmd)
substitution happens one layer up, in executor.run_line, before this module ever sees the line (it
needs to execute the inner command against the live fs, which this module has no access to).
Still deferred for this pass: for/if loops. Globs are expanded later by fs.expand_glob, not here.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_VAR = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


class ParseError(Exception):
    pass


@dataclass
class Command:
    argv: list[str]
    redirect: tuple[str, str] | None = None  # (">" or ">>", filename)


@dataclass
class Segment:
    pipeline: list[Command]
    joiner: str  # "&&" / "||" / ";" joining THIS segment to the next one, "" for the last


def _raw_tokens(line: str) -> list[tuple[str, bool]]:
    """Return (token, literal) pairs; literal=True means built from a single-quoted part (no $ expansion)."""
    tokens: list[tuple[str, bool]] = []
    buf, literal = "", False
    i, n = 0, len(line)

    def flush() -> None:
        nonlocal buf, literal
        if buf or literal:
            tokens.append((buf, literal))
        buf, literal = "", False

    while i < n:
        ch = line[i]
        if ch in " \t":
            flush()
            i += 1
        elif ch == "'":
            j = line.find("'", i + 1)
            if j == -1:
                raise ParseError("unterminated '")
            buf += line[i + 1:j]
            literal = True
            i = j + 1
        elif ch == '"':
            j = line.find('"', i + 1)
            if j == -1:
                raise ParseError('unterminated "')
            buf += line[i + 1:j]
            i = j + 1
        elif line[i:i + 2] == "&&":
            flush(); tokens.append(("&&", True)); i += 2
        elif line[i:i + 2] == "||":
            flush(); tokens.append(("||", True)); i += 2
        elif line[i:i + 2] == ">>":
            flush(); tokens.append((">>", True)); i += 2
        elif ch in "|>;":
            flush(); tokens.append((ch, True)); i += 1
        else:
            buf += ch
            i += 1
    flush()
    return tokens


def _expand(token: str, env: dict[str, str]) -> str:
    return _VAR.sub(lambda m: env.get(m.group(1), ""), token)


def parse(line: str, env: dict[str, str]) -> list[Segment]:
    """Parse one input line into ';'/'&&'/'||'-joined segments, each a '|'-pipeline of Commands."""
    words = [tok if lit else _expand(tok, env) for tok, lit in _raw_tokens(line)]
    return _split_and_build(words)


def _split_and_build(words: list[str]) -> list[Segment]:
    segments: list[Segment] = []
    current: list[str] = []
    for w in words:
        if w in (";", "&&", "||"):
            segments.append(Segment(_build_pipeline(current), w))
            current = []
        else:
            current.append(w)
    segments.append(Segment(_build_pipeline(current), ""))
    return [s for s in segments if s.pipeline or s.joiner]


def _build_pipeline(words: list[str]) -> list[Command]:
    if not words:
        return []
    commands: list[Command] = []
    argv: list[str] = []
    redirect: tuple[str, str] | None = None
    i = 0
    while i < len(words):
        w = words[i]
        if w == "|":
            commands.append(Command(argv, redirect))
            argv, redirect = [], None
        elif w in (">", ">>"):
            if i + 1 >= len(words):
                raise ParseError(f"syntax error near unexpected token `{w}'")
            redirect = (w, words[i + 1])
            i += 1
        else:
            argv.append(w)
        i += 1
    commands.append(Command(argv, redirect))
    if any(not c.argv for c in commands):
        raise ParseError("syntax error: empty command")
    return commands
