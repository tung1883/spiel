from src.learn.git import trivia


def test_bank_entries_are_well_formed():
    for q in trivia.BANK:
        assert 2 <= len(q.options) <= 4
        assert 0 <= q.correct < len(q.options)
        assert q.prompt and q.explain


def test_new_round_picks_distinct_questions():
    round_ = trivia.new_round(10)
    assert len(round_) == 10
    assert len(set(id(q) for q in round_)) == 10


def test_new_round_caps_at_bank_size():
    round_ = trivia.new_round(1000)
    assert len(round_) == len(trivia.BANK)
