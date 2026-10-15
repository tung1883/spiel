import time

from tui_games.learn.bughunt.levels import LEVELS, apply_fix
from tui_games.learn.bughunt.tracer import MAX_STEPS, REPR_CAP, trace_snippet


def test_traces_buggy_and_fixed_code_with_differing_step_counts():
    lv = LEVELS[0]  # "Sum to N": buggy loops one fewer time than fixed
    buggy = trace_snippet(lv.code, lv.tests)
    fixed = trace_snippet(apply_fix(lv), lv.tests)
    assert buggy.error is not None and "AssertionError" in buggy.error
    assert fixed.error is None
    assert len(buggy.steps) > 0 and len(fixed.steps) > len(buggy.steps)
    assert any(s["func"] == "sum_to" for s in fixed.steps)


def test_locals_are_captured_per_step():
    lv = LEVELS[0]
    r = trace_snippet(apply_fix(lv), lv.tests)
    sum_to_steps = [s for s in r.steps if s["func"] == "sum_to"]
    assert any("total" in s["locals"] and "i" in s["locals"] for s in sum_to_steps)


def test_hostile_infinite_loop_is_killed_within_timeout():
    code = "def spin():\n    x = 0\n    while True:\n        x += 1\n"
    start = time.monotonic()
    r = trace_snippet(code, "spin()", timeout=1.0)
    elapsed = time.monotonic() - start
    assert r.timed_out
    assert len(r.steps) <= MAX_STEPS
    assert elapsed < 5  # proves the kill actually happened, not a hung test


def test_hostile_tight_loop_self_disables_tracer_under_the_step_cap():
    code = "def many():\n    total = 0\n    for i in range(2_000_000):\n        total += i\n    return total\n"
    r = trace_snippet(code, "many()", timeout=5.0)
    assert not r.timed_out
    assert r.truncated
    assert len(r.steps) == MAX_STEPS


def test_hostile_huge_local_repr_is_capped():
    code = 'def huge():\n    big = "x" * 10_000_000\n    return big\n'
    r = trace_snippet(code, "huge()", timeout=2.0)
    assert not r.timed_out
    for step in r.steps:
        for value in step["locals"].values():
            assert len(value) <= REPR_CAP + 20
