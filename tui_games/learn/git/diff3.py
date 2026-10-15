"""A small, deliberately-limited three-way line merge (PLAN.md section 4: "Conflicts are real: a
3-way line merge, <<<<<<< markers"). Each commit snapshots a file as a full list of lines; this
compares a `base` snapshot against two descendants (`ours`/`theirs`) and merges per file.

Scope: built for the kind of single-contiguous-edit-per-commit changes this game's levels make
(one small hunk at a time, as a real small diff usually is) - not a general diff3 implementation.
When a side's edits don't reduce to one hunk against base, falls back to a whole-file conflict
rather than guessing.
"""
import difflib
from dataclasses import dataclass


def _hunks(base: list[str], other: list[str]) -> list[tuple[int, int, int, int]]:
    """Non-equal opcodes of base -> other, as (base_start, base_end, other_start, other_end)."""
    sm = difflib.SequenceMatcher(None, base, other, autojunk=False)
    return [(i1, i2, j1, j2) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal"]


@dataclass
class FileMerge:
    lines: list[str]
    conflict: bool
    ours_hunk: list[str] | None = None
    theirs_hunk: list[str] | None = None
    pre: list[str] | None = None
    post: list[str] | None = None


def merge_file(base: list[str], ours: list[str], theirs: list[str]) -> FileMerge:
    if ours == base:
        return FileMerge(list(theirs), False)
    if theirs == base:
        return FileMerge(list(ours), False)
    if ours == theirs:
        return FileMerge(list(ours), False)

    ops_o, ops_t = _hunks(base, ours), _hunks(base, theirs)
    if len(ops_o) != 1 or len(ops_t) != 1:
        # Multiple/zero hunks on one side relative to base: too complex for this merge to untangle
        # precisely, so hand the player the two whole files as a conflict instead of guessing.
        return FileMerge(list(ours), True, list(ours), list(theirs), [], [])

    o_i1, o_i2, o_j1, o_j2 = ops_o[0]
    t_i1, t_i2, t_j1, t_j2 = ops_t[0]
    if o_i2 <= t_i1 or t_i2 <= o_i1:
        # disjoint base ranges: apply both edits to a copy of base, further-right edit first so
        # earlier indices stay valid
        merged = list(base)
        for i1, i2, j1, j2, side in sorted(
            [(o_i1, o_i2, o_j1, o_j2, ours), (t_i1, t_i2, t_j1, t_j2, theirs)], key=lambda e: -e[0]
        ):
            merged[i1:i2] = side[j1:j2]
        return FileMerge(merged, False)

    lo, hi = min(o_i1, t_i1), max(o_i2, t_i2)
    pre, post = base[:lo], base[hi:]
    ours_hunk = base[lo:o_i1] + ours[o_j1:o_j2] + base[o_i2:hi]
    theirs_hunk = base[lo:t_i1] + theirs[t_j1:t_j2] + base[t_i2:hi]
    if ours_hunk == theirs_hunk:
        return FileMerge(pre + ours_hunk + post, False)
    return FileMerge(pre + ours_hunk + post, True, ours_hunk, theirs_hunk, pre, post)


def conflict_markers(fm: FileMerge, ours_label: str = "ours", theirs_label: str = "theirs") -> list[str]:
    assert fm.conflict and fm.pre is not None and fm.post is not None
    return (
        fm.pre
        + [f"<<<<<<< {ours_label}"]
        + fm.ours_hunk
        + ["======="]
        + fm.theirs_hunk
        + [f">>>>>>> {theirs_label}"]
        + fm.post
    )
