import time

from tui_games.learn.bughunt import sandbox


def test_runs_ok_snippet():
    r = sandbox.run_snippet('assert 1 + 1 == 2\nprint("OK")')
    assert r.ok and "OK" in r.stdout


def test_catches_assertion_failure():
    r = sandbox.run_snippet('assert 1 == 2\nprint("OK")')
    assert not r.ok and not r.timed_out


def test_kills_infinite_loop_within_timeout():
    start = time.monotonic()
    r = sandbox.run_snippet("while True:\n    pass\n", timeout=1.0)
    elapsed = time.monotonic() - start
    assert r.timed_out and not r.ok
    assert elapsed < 5  # well under the test's own run, proves the kill actually happened
