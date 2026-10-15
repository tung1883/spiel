from tui_games.learn.regex.explain import explain


def test_explains_common_constructs():
    notes = dict(explain(r"^\d{3}$"))
    assert notes["^"] == "start of string"
    assert notes[r"\d"] == "a digit"
    assert "3" in notes["{3}"]
    assert notes["$"] == "end of string"


def test_unknown_byte_falls_back_to_literal_note():
    notes = dict(explain("a"))
    assert "a" in notes["a"]
