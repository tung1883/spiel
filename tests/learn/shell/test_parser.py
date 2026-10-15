from src.learn.shell.parser import parse


def test_single_command():
    segs = parse("ls -la /tmp", {})
    assert len(segs) == 1
    assert segs[0].pipeline[0].argv == ["ls", "-la", "/tmp"]


def test_quoting_keeps_spaces_together():
    segs = parse("echo 'two words' \"three  spaced\"", {})
    assert segs[0].pipeline[0].argv == ["echo", "two words", "three  spaced"]


def test_single_quotes_skip_var_expansion():
    segs = parse("echo '$HOME' $HOME", {"HOME": "/home/player"})
    assert segs[0].pipeline[0].argv == ["echo", "$HOME", "/home/player"]


def test_pipe_splits_into_multiple_commands():
    segs = parse("cat f | sort | uniq -c", {})
    cmds = segs[0].pipeline
    assert [c.argv for c in cmds] == [["cat", "f"], ["sort"], ["uniq", "-c"]]


def test_redirect_out_and_append():
    segs = parse("echo hi > a.txt", {})
    assert segs[0].pipeline[0].redirect == (">", "a.txt")
    segs = parse("echo hi >> a.txt", {})
    assert segs[0].pipeline[0].redirect == (">>", "a.txt")


def test_and_or_semicolon_join_segments():
    segs = parse("a && b || c ; d", {})
    assert [s.joiner for s in segs] == ["&&", "||", ";", ""]
    assert [s.pipeline[0].argv[0] for s in segs] == ["a", "b", "c", "d"]
