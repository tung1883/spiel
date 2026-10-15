import pytest

from tui_games.learn.git.commands import GitEngine
from tui_games.learn.git.levels import LEVELS, LevelRun, solve


def test_fresh_repo_has_one_root_commit_on_main():
    engine = GitEngine()
    assert len(engine.repo.commits) == 1
    assert engine.repo.head == engine.repo.branches["main"]


def test_commit_advances_head_and_snapshots_the_working_tree():
    engine = GitEngine({"notes.txt": ["a"]})
    root = engine.repo.head
    engine.run('edit notes.txt append "b"')
    engine.run('commit -m "first"')
    assert engine.repo.head != root
    assert engine.repo.commits[engine.repo.head].parents == [root]
    assert engine.repo.commits[engine.repo.head].message == "first"
    assert engine.repo.commits[engine.repo.head].files["notes.txt"] == ("a", "b")


def test_branch_and_switch_create_a_divergent_graph():
    engine = GitEngine()
    engine.run("switch -b feature")
    engine.run('commit -m "on feature"')
    assert engine.repo.branches["feature"] != engine.repo.branches["main"]
    engine.run("switch main")
    engine.run('commit -m "on main"')
    base = engine.repo.merge_base(engine.repo.branches["main"], engine.repo.branches["feature"])
    assert base not in (engine.repo.branches["main"], engine.repo.branches["feature"])


def test_switch_refuses_to_discard_uncommitted_edits():
    engine = GitEngine({"notes.txt": ["a"]})
    engine.run("switch -b feature")
    engine.run('edit notes.txt append "dirty"')
    msg = engine.run("switch main")
    assert "error" in msg and "uncommitted" in msg


def test_fast_forward_merge_moves_pointer_without_merge_commit():
    engine = GitEngine()
    engine.run("switch -b feature")
    engine.run('commit -m "add header"')
    engine.run("switch main")
    msg = engine.run("merge feature")
    assert "fast-forwarded" in msg
    assert engine.repo.branches["main"] == engine.repo.branches["feature"]


def test_merge_of_different_lines_auto_resolves_with_both_changes():
    engine = GitEngine({"app.py": ["a", "b", "c"]})
    engine.run("switch -b feature")
    engine.run('edit app.py set 1 "A"')
    engine.run('commit -m "feature changes line 1"')
    engine.run("switch main")
    engine.run('edit app.py set 3 "C"')
    engine.run('commit -m "main changes line 3"')
    msg = engine.run("merge feature")
    assert "merge" in msg.lower() and "CONFLICT" not in msg
    assert engine.working["app.py"] == ["A", "b", "C"]


def test_conflicting_merge_produces_real_markers_and_requires_resolve_then_continue():
    engine = GitEngine({"config.py": ["PORT = 8000"]})
    engine.run("switch -b feature")
    engine.run('edit config.py set 1 "PORT = 9000"')
    engine.run('commit -m "feature edits"')
    engine.run("switch main")
    engine.run('edit config.py set 1 "PORT = 8080"')
    engine.run('commit -m "main edits"')
    msg = engine.run("merge feature")
    assert "CONFLICT" in msg and engine.pending is not None
    assert any(ln.startswith("<<<<<<<") for ln in engine.working["config.py"])
    engine.run("resolve config.py both")
    assert not engine.conflicts
    msg2 = engine.run("merge --continue")
    assert "merge completed" in msg2
    assert len(engine.repo.commits[engine.repo.head].parents) == 2
    assert engine.working["config.py"] == ["PORT = 8080", "PORT = 9000"]


def test_hand_editing_away_the_conflict_markers_also_resolves_it():
    engine = GitEngine({"config.py": ["PORT = 8000"]})
    engine.run("switch -b feature")
    engine.run('edit config.py set 1 "PORT = 9000"')
    engine.run('commit -m "feature edits"')
    engine.run("switch main")
    engine.run('edit config.py set 1 "PORT = 8080"')
    engine.run('commit -m "main edits"')
    engine.run("merge feature")
    assert engine.conflicts == {"config.py"}
    engine.run('edit config.py set 1 "PORT = 9999"')
    for _ in range(4):
        engine.run("edit config.py delete 2")
    assert not engine.conflicts  # the edit tool notices the markers are gone
    msg = engine.run("merge --continue")
    assert "merge completed" in msg
    assert engine.working["config.py"] == ["PORT = 9999"]


def test_rebase_replays_commits_onto_a_new_base():
    engine = GitEngine({"notes.txt": ["base"]})
    engine.run("switch -b feature")
    engine.run('edit notes.txt set 1 "feature base"')
    engine.run('commit -m "feature step"')
    engine.run("switch main")
    engine.run('edit notes.txt append "hotfix"')
    engine.run('commit -m hotfix')
    engine.run("switch feature")
    msg = engine.run("rebase main")
    assert "rebase complete" in msg
    assert engine.repo.is_ancestor(engine.repo.branches["main"], engine.repo.head)


def test_undo_reverts_last_command():
    engine = GitEngine()
    root = engine.repo.head
    engine.run('commit -m "oops"')
    assert engine.repo.head != root
    engine.undo()
    assert engine.repo.head == root


@pytest.mark.parametrize("i", range(len(LEVELS)))
def test_level_not_solved_right_after_setup(i):
    run = LevelRun(LEVELS[i])
    assert not run.done, LEVELS[i].title


@pytest.mark.parametrize("i", range(len(LEVELS)))
def test_reference_solution_reaches_the_goal_exactly_at_par(i):
    run = solve(LEVELS[i])
    assert run.done, (LEVELS[i].title, run.count)
    assert run.count == LEVELS[i].par
