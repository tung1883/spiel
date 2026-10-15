import re

import pytest

from src.learn.regex import engine
from src.learn.regex.levels import LEVELS

GOLF = [lv for lv in LEVELS if lv.mode == "golf"]
EXTRACT = [lv for lv in LEVELS if lv.mode == "extract"]
SUBSTITUTE = [lv for lv in LEVELS if lv.mode == "substitute"]


@pytest.mark.parametrize("level", GOLF, ids=[lv.id for lv in GOLF])
def test_reference_solves_the_golf_level(level):
    rx = re.compile(level.reference)
    assert all(rx.search(s) for s in level.yes), (level.id, "missed a yes string")
    assert not any(rx.search(s) for s in level.no), (level.id, "matched a no string")


@pytest.mark.parametrize("level", EXTRACT, ids=[lv.id for lv in EXTRACT])
def test_reference_solves_the_extract_level(level):
    r = engine.check_extract(level.reference, level.text, level.targets)
    assert r["passed"], (level.id, r)


@pytest.mark.parametrize("level", SUBSTITUTE, ids=[lv.id for lv in SUBSTITUTE])
def test_reference_solves_the_substitute_level(level):
    r = engine.check_substitute(level.reference, level.repl, level.before, level.after)
    assert r["passed"], (level.id, r)


@pytest.mark.parametrize("level", LEVELS, ids=[lv.id for lv in LEVELS])
def test_reference_is_not_absurdly_over_par(level):
    score = len(level.reference) + (len(level.repl) + 1 if level.mode == "substitute" else 0)
    assert score <= level.par


def test_ids_are_unique():
    assert len({lv.id for lv in LEVELS}) == len(LEVELS)


def test_every_level_has_a_mode_specific_payload():
    for lv in LEVELS:
        if lv.mode == "golf":
            assert lv.yes and lv.no
        elif lv.mode == "extract":
            assert lv.text and lv.targets
        else:
            assert lv.before and lv.after
