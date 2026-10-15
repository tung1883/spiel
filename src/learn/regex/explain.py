"""Turns a regex pattern into plain-English fragments, e.g. `\\d{3}` -> "exactly 3 digits". A small
own tokenizer (not `re._parser`/`sre_parse`, which are internal and unstable across versions) -
covers the common constructs taught by this game's levels, not the whole `re` grammar.
"""
import re

_CLASS_NAMES = {
    r"\d": "a digit", r"\D": "a non-digit",
    r"\w": "a word character", r"\W": "a non-word character",
    r"\s": "whitespace", r"\S": "non-whitespace",
    ".": "any character",
}
_ANCHOR_NAMES = {"^": "start of string", "$": "end of string", r"\b": "a word boundary", r"\B": "not a word boundary"}

_TOKEN_RE = re.compile(
    r"""
    (?P<group_open>\(\?: | \( )
  | (?P<group_close>\))
  | (?P<alt>\|)
  | (?P<backref>\\[1-9])
  | (?P<class>\\d|\\D|\\w|\\W|\\s|\\S)
  | (?P<anchor>\^|\$|\\b|\\B)
  | (?P<charclass>\[\^?(?:\\.|[^\]])*\])
  | (?P<quant>\{\d+(?:,\d*)?\}\??|[*+?]\??)
  | (?P<escaped>\\.)
  | (?P<dot>\.)
  | (?P<literal>[^.^$*+?{}()|\[\]\\]+)
    """,
    re.VERBOSE,
)


def _quant_text(q: str) -> str:
    lazy = q.endswith("?") and q != "?"
    core = q[:-1] if lazy else q
    if core == "*":
        word = "0 or more (as many as possible)"
    elif core == "+":
        word = "1 or more (as many as possible)"
    elif core == "?":
        return "optionally" if not lazy else "optionally (prefers fewer)"
    else:
        body = core[1:-1]
        if "," in body:
            lo, hi = body.split(",", 1)
            if hi == "":
                word = f"{lo} or more"
            else:
                word = f"between {lo} and {hi}"
        else:
            word = f"exactly {body}"
        word += " (as many as possible)" if not lazy else ""
    return word + " (prefers fewer)" if lazy and core not in ("?",) else word


def _charclass_text(frag: str) -> str:
    neg = frag.startswith("[^")
    body = frag[2:-1] if neg else frag[1:-1]
    return ("none of " if neg else "one of ") + repr(body)


def explain(pattern: str) -> list[tuple[str, str]]:
    """Returns [(fragment, plain-English note), ...] covering as much of `pattern` as this
    tokenizer understands; unrecognised bytes fall back to a literal character note."""
    out: list[tuple[str, str]] = []
    pos = 0
    while pos < len(pattern):
        m = _TOKEN_RE.match(pattern, pos)
        if not m:
            ch = pattern[pos]
            out.append((ch, f"the character '{ch}'"))
            pos += 1
            continue
        frag = m.group(0)
        kind = m.lastgroup
        if kind == "group_open":
            note = "start of a non-capturing group" if frag == "(?:" else "start of a group"
        elif kind == "group_close":
            note = "end of the group"
        elif kind == "alt":
            note = "or"
        elif kind == "backref":
            note = f"the same text group {frag[1:]} matched"
        elif kind == "class":
            note = _CLASS_NAMES[frag]
        elif kind == "anchor":
            note = _ANCHOR_NAMES[frag]
        elif kind == "charclass":
            note = _charclass_text(frag)
        elif kind == "quant":
            note = _quant_text(frag)
        elif kind == "escaped":
            note = f"a literal '{frag[1]}'"
        elif kind == "dot":
            note = "any character"
        else:  # literal
            note = f"the text {frag!r}"
        out.append((frag, note))
        pos = m.end()
    return out
