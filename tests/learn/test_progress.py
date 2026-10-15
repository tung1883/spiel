from tui_games import config
from tui_games.learn import progress


def _use_tmp_config(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "_PATH", tmp_path / "config.json")


def test_stars_thresholds():
    assert progress.stars(10, 10) == 3
    assert progress.stars(14, 10) == 2
    assert progress.stars(15, 10) == 2
    assert progress.stars(16, 10) == 1


def test_fresh_player_has_zero_xp(monkeypatch, tmp_path):
    _use_tmp_config(monkeypatch, tmp_path)
    learn = progress.load()
    assert learn == {"v": 1, "xp": 0, "badges": [], "levels": {}}
    assert progress.rank(0) == "Novice"


def test_record_awards_xp_and_keeps_best(monkeypatch, tmp_path):
    _use_tmp_config(monkeypatch, tmp_path)
    s1, xp1 = progress.record("regex:world", "0", 16, 16)
    assert (s1, xp1) == (3, 30)
    # worse attempt: no xp lost, stars/best do not regress
    s2, xp2 = progress.record("regex:world", "0", 30, 16)
    assert xp2 == 0
    learn = progress.load()
    assert learn["levels"]["regex:world:0"] == {"stars": 3, "best": 16}
    assert learn["xp"] == 30


def test_corrupted_config_is_tolerated(monkeypatch, tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json")
    monkeypatch.setattr(config, "_PATH", path)
    assert progress.load()["xp"] == 0
