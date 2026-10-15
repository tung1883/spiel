from tui_games.learn.bughunt.levels import LEVELS
from tui_games.learn.bughunt.screens import diagnose_options


def test_diagnose_options_always_include_the_correct_class():
    for level in LEVELS:
        opts = diagnose_options(level)
        assert level.bug_class in opts
        assert len(opts) == len(set(opts))  # no duplicates
        assert 2 <= len(opts) <= 5


def test_diagnose_options_are_deterministic():
    for level in LEVELS:
        assert diagnose_options(level) == diagnose_options(level)
