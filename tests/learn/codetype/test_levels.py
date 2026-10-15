from collections import Counter

from src.learn.codetype.levels import ALL_SNIPPETS, BOSS_SNIPPETS, SNIPPETS, distractor_notes, validate_all


def test_all_snippets_valid():
    validate_all()  # no tabs/trailing whitespace, sane length, python parses


def test_language_spread():
    counts = Counter(s.lang for s in SNIPPETS)
    assert len(SNIPPETS) == 50
    assert set(counts) == {"python", "javascript", "go", "rust", "sql"}
    assert all(n == 10 for n in counts.values())


def test_boss_snippets_are_one_per_language_and_tier_expert():
    assert len(BOSS_SNIPPETS) == 5
    assert {s.lang for s in BOSS_SNIPPETS} == {"python", "javascript", "go", "rust", "sql"}
    assert all(s.tier == "expert" for s in BOSS_SNIPPETS)


def test_tier_spread_has_all_three():
    tiers = Counter(s.tier for s in ALL_SNIPPETS)
    assert set(tiers) == {"beginner", "intermediate", "expert"}
    assert tiers["intermediate"] >= 10


def test_ids_are_unique():
    ids = [s.id for s in ALL_SNIPPETS]
    assert len(ids) == len(set(ids))


def test_distractor_notes_never_includes_the_correct_answer():
    for s in SNIPPETS[:5]:
        picks = distractor_notes(s, count=3)
        assert s.note not in picks
        assert len(picks) == 3
