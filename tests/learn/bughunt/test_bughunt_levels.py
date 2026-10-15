import pytest

from src.learn.bughunt import sandbox
from src.learn.bughunt.levels import LEVELS, apply_fix, build_script


@pytest.mark.parametrize("level", LEVELS, ids=[lv.id for lv in LEVELS])
def test_buggy_code_fails_the_hidden_test(level):
    result = sandbox.run_snippet(build_script(level.code, level))
    assert not result.ok, (level.title, result.stdout, result.stderr)


@pytest.mark.parametrize("level", LEVELS, ids=[lv.id for lv in LEVELS])
def test_fixed_code_passes_the_hidden_test(level):
    fixed = apply_fix(level)
    result = sandbox.run_snippet(build_script(fixed, level))
    assert result.ok and "OK" in result.stdout, (level.title, result.stdout, result.stderr)


def test_bug_line_is_within_the_snippet():
    for level in LEVELS:
        assert 1 <= level.bug_line <= len(level.code.split("\n"))
