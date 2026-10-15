"""Built-in commands. Each is `fn(fs, args, stdin) -> (stdout, stderr, exit_code)`. Deterministic:
fixed sort order, no real mtimes/locale. Everything operates on the in-memory fs.FS only."""
from __future__ import annotations

import fnmatch
import re

from .fs import FS, FSError, Node


def _split_flags(args: list[str], flag_chars: str) -> tuple[set[str], list[str]]:
    """Split `-la foo` style short flags (each char in flag_chars) from positional args."""
    flags: set[str] = set()
    rest: list[str] = []
    for a in args:
        if a.startswith("-") and a != "-" and all(c in flag_chars for c in a[1:]):
            flags.update(a[1:])
        else:
            rest.append(a)
    return flags, rest


def _expand_all(fs: FS, paths: list[str]) -> list[str]:
    out: list[str] = []
    for p in paths:
        out.extend(fs.expand_glob(p))
    return out


def _read_file(fs: FS, path: str) -> str:
    node = fs.get(path)
    if node is None:
        raise FSError(f"{path}: No such file or directory")
    if node.is_dir:
        raise FSError(f"{path}: Is a directory")
    return node.content


def cmd_pwd(fs: FS, args: list[str], stdin: str) -> tuple[str, str, int]:
    return fs.cwd_str() + "\n", "", 0


def cmd_cd(fs: FS, args: list[str], stdin: str) -> tuple[str, str, int]:
    path = args[0] if args else "~"
    try:
        fs.chdir(path)
    except FSError as e:
        return "", str(e) + "\n", 1
    return "", "", 0


def cmd_ls(fs: FS, args: list[str], stdin: str) -> tuple[str, str, int]:
    flags, rest = _split_flags(args, "al")
    path = rest[0] if rest else "."
    node = fs.get(path)
    if node is None:
        return "", f"ls: cannot access '{path}': No such file or directory\n", 1
    names = sorted(node.children) if node.is_dir else [node.name]
    if "a" not in flags:
        names = [n for n in names if not n.startswith(".")]
    if "l" not in flags:
        return ("  ".join(names) + ("\n" if names else ""), "", 0)
    lines = []
    for n in names:
        child = node.children[n] if node.is_dir else node
        kind = "d" if child.is_dir else "-"
        size = 0 if child.is_dir else len(child.content)
        lines.append(f"{kind}{oct(child.mode)[2:]:>4} {size:>6} {n}")
    return "\n".join(lines) + ("\n" if lines else ""), "", 0


def cmd_cat(fs: FS, args: list[str], stdin: str) -> tuple[str, str, int]:
    if not args:
        return stdin, "", 0
    out = []
    for p in _expand_all(fs, args):
        try:
            out.append(_read_file(fs, p))
        except FSError as e:
            return "".join(out), str(e) + "\n", 1
    return "".join(out), "", 0


def _head_tail(fs: FS, args: list[str], stdin: str, take_last: bool) -> tuple[str, str, int]:
    n = 10
    rest = []
    i = 0
    while i < len(args):
        if args[i] == "-n" and i + 1 < len(args):
            n = int(args[i + 1]); i += 2
        else:
            rest.append(args[i]); i += 1
    text = stdin if not rest else "".join(_read_file(fs, p) for p in _expand_all(fs, rest))
    lines = text.splitlines()
    chosen = lines[-n:] if take_last else lines[:n]
    return ("\n".join(chosen) + ("\n" if chosen else "")), "", 0


def cmd_head(fs: FS, args: list[str], stdin: str) -> tuple[str, str, int]:
    return _head_tail(fs, args, stdin, take_last=False)


def cmd_tail(fs: FS, args: list[str], stdin: str) -> tuple[str, str, int]:
    return _head_tail(fs, args, stdin, take_last=True)


def cmd_wc(fs: FS, args: list[str], stdin: str) -> tuple[str, str, int]:
    flags, rest = _split_flags(args, "lwc")
    text = stdin if not rest else "".join(_read_file(fs, p) for p in _expand_all(fs, rest))
    lines, words, chars = text.count("\n"), len(text.split()), len(text)
    parts = []
    if not flags or "l" in flags:
        parts.append(str(lines))
    if not flags or "w" in flags:
        parts.append(str(words))
    if not flags or "c" in flags:
        parts.append(str(chars))
    return " ".join(parts) + "\n", "", 0


_LEADING_NUM = re.compile(r"\s*(-?\d+(?:\.\d+)?)")


def _numeric_key(s: str) -> float:
    m = _LEADING_NUM.match(s)
    return float(m.group(1)) if m else 0.0


def cmd_sort(fs: FS, args: list[str], stdin: str) -> tuple[str, str, int]:
    flags, rest = _split_flags(args, "nru")
    text = stdin if not rest else "".join(_read_file(fs, p) for p in _expand_all(fs, rest))
    lines = text.splitlines()
    key = _numeric_key if "n" in flags else (lambda s: s)
    lines.sort(key=key, reverse="r" in flags)
    if "u" in flags:
        seen, uniq = set(), []
        for l in lines:
            if l not in seen:
                seen.add(l); uniq.append(l)
        lines = uniq
    return "\n".join(lines) + ("\n" if lines else ""), "", 0


def cmd_uniq(fs: FS, args: list[str], stdin: str) -> tuple[str, str, int]:
    flags, rest = _split_flags(args, "c")
    text = stdin if not rest else "".join(_read_file(fs, p) for p in _expand_all(fs, rest))
    lines = text.splitlines()
    out = []
    for line in lines:
        if out and out[-1][1] == line:
            out[-1] = (out[-1][0] + 1, line)
        else:
            out.append((1, line))
    if "c" in flags:
        return "\n".join(f"{c:>4} {l}" for c, l in out) + ("\n" if out else ""), "", 0
    return "\n".join(l for _, l in out) + ("\n" if out else ""), "", 0


def cmd_cut(fs: FS, args: list[str], stdin: str) -> tuple[str, str, int]:
    delim, fields = "\t", []
    rest = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-d" and i + 1 < len(args):
            delim = args[i + 1]; i += 2
        elif a.startswith("-d") and len(a) > 2:
            delim = a[2:]; i += 1
        elif a == "-f" and i + 1 < len(args):
            fields = [int(x) for x in args[i + 1].split(",")]; i += 2
        elif a.startswith("-f") and len(a) > 2:
            fields = [int(x) for x in a[2:].split(",")]; i += 1
        else:
            rest.append(a); i += 1
    text = stdin if not rest else "".join(_read_file(fs, p) for p in _expand_all(fs, rest))
    out_lines = []
    for line in text.splitlines():
        parts = line.split(delim)
        picked = [parts[f - 1] for f in fields if 0 < f <= len(parts)]
        out_lines.append(delim.join(picked))
    return "\n".join(out_lines) + ("\n" if out_lines else ""), "", 0


def cmd_grep(fs: FS, args: list[str], stdin: str) -> tuple[str, str, int]:
    flags, rest = _split_flags(args, "invcl")
    if not rest:
        return "", "grep: missing pattern\n", 2
    pattern, paths = rest[0], rest[1:]
    if not paths:
        sources = [("", stdin)]
    else:
        sources = [(p, _read_file(fs, p)) for p in _expand_all(fs, paths)]
    hits = []
    matched_files = []
    for name, text in sources:
        file_matched = False
        for i, line in enumerate(text.splitlines(), start=1):
            hay, needle = (line.lower(), pattern.lower()) if "i" in flags else (line, pattern)
            matched = needle in hay
            if matched != ("v" in flags):
                file_matched = True
                prefix = f"{name}:" if name and len(sources) > 1 else ""
                prefix += f"{i}:" if "n" in flags else ""
                hits.append(prefix + line)
        if file_matched:
            matched_files.append(name)
    if "l" in flags:
        return "\n".join(matched_files) + ("\n" if matched_files else ""), "", 0 if matched_files else 1
    if "c" in flags:
        return f"{len(hits)}\n", "", 0 if hits else 1
    return "\n".join(hits) + ("\n" if hits else ""), "", 0 if hits else 1


def cmd_find(fs: FS, args: list[str], stdin: str) -> tuple[str, str, int]:
    start, name_pat = ".", None
    rest = []
    i = 0
    while i < len(args):
        if args[i] == "-name" and i + 1 < len(args):
            name_pat = args[i + 1]; i += 2
        else:
            rest.append(args[i]); i += 1
    if rest:
        start = rest[0]
    base = fs.get(start)
    if base is None:
        return "", f"find: '{start}': No such file or directory\n", 1
    results: list[str] = []

    def walk(node: Node, path: str) -> None:
        if name_pat is None or fnmatch.fnmatch(node.name, name_pat):
            results.append(path)
        if node.is_dir:
            for child_name in sorted(node.children):
                walk(node.children[child_name], f"{path}/{child_name}" if path != "." else child_name)

    walk(base, start)
    return "\n".join(results) + ("\n" if results else ""), "", 0


def cmd_mkdir(fs: FS, args: list[str], stdin: str) -> tuple[str, str, int]:
    flags, rest = _split_flags(args, "p")
    try:
        for p in rest:
            fs.mkdir(p, parents="p" in flags)
    except FSError as e:
        return "", str(e) + "\n", 1
    return "", "", 0


def cmd_rm(fs: FS, args: list[str], stdin: str) -> tuple[str, str, int]:
    flags, rest = _split_flags(args, "rf")
    try:
        for p in _expand_all(fs, rest):
            fs.remove(p, recursive="r" in flags)
    except FSError as e:
        if "f" in flags:
            return "", "", 0
        return "", str(e) + "\n", 1
    return "", "", 0


def cmd_cp(fs: FS, args: list[str], stdin: str) -> tuple[str, str, int]:
    flags, rest = _split_flags(args, "r")
    if len(rest) != 2:
        return "", "cp: usage: cp SRC DEST\n", 2
    try:
        fs.copy(rest[0], rest[1])
    except FSError as e:
        return "", str(e) + "\n", 1
    return "", "", 0


def cmd_mv(fs: FS, args: list[str], stdin: str) -> tuple[str, str, int]:
    if len(args) != 2:
        return "", "mv: usage: mv SRC DEST\n", 2
    try:
        fs.move(args[0], args[1])
    except FSError as e:
        return "", str(e) + "\n", 1
    return "", "", 0


def cmd_touch(fs: FS, args: list[str], stdin: str) -> tuple[str, str, int]:
    try:
        for p in args:
            fs.touch(p)
    except FSError as e:
        return "", str(e) + "\n", 1
    return "", "", 0


def cmd_chmod(fs: FS, args: list[str], stdin: str) -> tuple[str, str, int]:
    if len(args) != 2:
        return "", "chmod: usage: chmod MODE PATH\n", 2
    try:
        fs.chmod(args[0], args[1])
    except FSError as e:
        return "", str(e) + "\n", 1
    return "", "", 0


def cmd_echo(fs: FS, args: list[str], stdin: str) -> tuple[str, str, int]:
    return " ".join(args) + "\n", "", 0


_AWK_PRINT = re.compile(r"\{\s*print(?:\s+(.*?))?\s*;?\s*\}")


def cmd_awk(fs: FS, args: list[str], stdin: str) -> tuple[str, str, int]:
    """A tiny awk subset: '{print}' , '{print $N}' , '{print $1, $3}' , '$0' = whole line, '$NF' = last field."""
    if not args:
        return "", "awk: missing program\n", 2
    prog, files = args[0], args[1:]
    m = _AWK_PRINT.match(prog.strip())
    if not m:
        return "", f"awk: unsupported program: {prog}\n", 2
    fields_expr = [p.strip() for p in (m.group(1) or "$0").split(",")]
    text = stdin if not files else "".join(_read_file(fs, p) for p in _expand_all(fs, files))

    def value(tok: str, line: str, fields: list[str]) -> str:
        if tok == "$0":
            return line
        if tok == "$NF":
            return fields[-1] if fields else ""
        if tok.startswith("$") and tok[1:].isdigit():
            i = int(tok[1:])
            return fields[i - 1] if 0 < i <= len(fields) else ""
        return tok.strip('"')

    out_lines = []
    for line in text.splitlines():
        fields = line.split()
        out_lines.append(" ".join(value(tok, line, fields) for tok in fields_expr))
    return "\n".join(out_lines) + ("\n" if out_lines else ""), "", 0


def cmd_sed(fs: FS, args: list[str], stdin: str) -> tuple[str, str, int]:
    """A tiny sed subset: 's/pattern/replacement/' and the trailing 'g' flag for all-occurrences."""
    if not args:
        return "", "sed: missing script\n", 2
    script, files = args[0], args[1:]
    if len(script) < 2 or script[0] != "s":
        return "", f"sed: unsupported script: {script}\n", 2
    delim = script[1]
    parts = script[2:].split(delim)
    if len(parts) < 2:
        return "", f"sed: unsupported script: {script}\n", 2
    pattern, repl = parts[0], parts[1]
    flags = parts[2] if len(parts) > 2 else ""
    text = stdin if not files else "".join(_read_file(fs, p) for p in _expand_all(fs, files))
    count = 0 if "g" in flags else 1
    try:
        out_lines = [re.sub(pattern, repl, line, count=count) for line in text.splitlines()]
    except re.error as e:
        return "", f"sed: {e}\n", 2
    return "\n".join(out_lines) + ("\n" if out_lines else ""), "", 0


COMMANDS = {
    "pwd": cmd_pwd, "cd": cmd_cd, "ls": cmd_ls, "cat": cmd_cat, "head": cmd_head, "tail": cmd_tail,
    "wc": cmd_wc, "sort": cmd_sort, "uniq": cmd_uniq, "cut": cmd_cut, "grep": cmd_grep, "find": cmd_find,
    "mkdir": cmd_mkdir, "rm": cmd_rm, "cp": cmd_cp, "mv": cmd_mv, "touch": cmd_touch, "chmod": cmd_chmod,
    "echo": cmd_echo, "awk": cmd_awk, "sed": cmd_sed,
}


def run_command(fs: FS, argv: list[str], stdin: str) -> tuple[str, str, int]:
    if not argv:
        return "", "", 0
    name, args = argv[0], argv[1:]
    fn = COMMANDS.get(name)
    if fn is None:
        return "", f"{name}: command not found\n", 127
    try:
        return fn(fs, args, stdin)
    except FSError as e:
        return "", str(e) + "\n", 1
