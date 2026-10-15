from tui_games.learn.regex.engine import check


def test_basic_pass_and_fail():
    r = check(r"^[0-9]+$", ["123", "0"], ["abc", "12a"])
    assert r["passed"] and not r["error"] and not r["timeout"]


def test_bad_pattern_reports_error_not_crash():
    r = check("(", ["a"], ["b"])
    assert r["error"] and not r["passed"]


def test_empty_pattern_fails_cleanly():
    r = check("", ["a"], ["b"])
    assert r["error"] and not r["passed"]


def test_catastrophic_backtracking_times_out_instead_of_hanging():
    r = check("(a+)+$", ["aaaa"], ["a" * 30 + "!"])
    assert r["timeout"] and not r["passed"]
