import collections

from src.learn.shell.executor import run_line
from src.learn.shell.fs import FS


def test_sort_and_uniq_c_match_python_reference():
    fs = FS()
    lines = ["b", "a", "b", "c", "a", "a"]
    fs.write("data.txt", "\n".join(lines) + "\n", append=False)
    out, code = run_line(fs, "cat data.txt | sort | uniq -c")
    assert code == 0
    expected = sorted(collections.Counter(lines).items())
    expected_text = "".join(f"{n:>4} {w}\n" for w, n in expected)
    assert out == expected_text


def test_grep_count_matches_manual_count():
    fs = FS()
    fs.write("log.txt", "ERROR a\nINFO b\nERROR c\n", append=False)
    out, code = run_line(fs, "grep -c ERROR log.txt")
    assert out == "2\n" and code == 0


def test_cut_with_attached_flags():
    fs = FS()
    fs.write("roster.txt", "ada:eng\njo:ops\n", append=False)
    out, _ = run_line(fs, "cut -d: -f2 roster.txt")
    assert out == "eng\nops\n"


def test_redirect_overwrite_then_append():
    fs = FS()
    run_line(fs, "echo one > f.txt")
    run_line(fs, "echo two >> f.txt")
    assert fs.get("f.txt").content == "one\ntwo\n"


def test_and_or_short_circuit():
    fs = FS()
    out, code = run_line(fs, "grep nope nowhere.txt && echo should-not-print")
    assert "should-not-print" not in out and code != 0
    out, code = run_line(fs, "grep nope nowhere.txt || echo fallback-ok")
    assert "fallback-ok" in out


def test_command_not_found():
    fs = FS()
    out, code = run_line(fs, "frobnicate")
    assert code == 127 and "not found" in out


def test_mkdir_rm_roundtrip():
    fs = FS()
    run_line(fs, "mkdir -p a/b/c")
    assert fs.get("a/b/c") is not None
    run_line(fs, "rm -r a")
    assert fs.get("a") is None


def test_awk_print_field_and_nf():
    fs = FS()
    fs.write("f.txt", "a b c\none two three four\n", append=False)
    out, code = run_line(fs, "awk '{print $2}' f.txt")
    assert out == "b\ntwo\n" and code == 0
    out, code = run_line(fs, "awk '{print $NF}' f.txt")
    assert out == "c\nfour\n" and code == 0


def test_sed_substitute_first_vs_global():
    fs = FS()
    fs.write("f.txt", "aa aa aa\n", append=False)
    out, _ = run_line(fs, "sed 's/aa/bb/' f.txt")
    assert out == "bb aa aa\n"
    out, _ = run_line(fs, "sed 's/aa/bb/g' f.txt")
    assert out == "bb bb bb\n"


def test_command_substitution_splits_multiline_output_into_words():
    fs = FS()
    fs.write("a.tmp", "x", append=False)
    fs.write("b.tmp", "x", append=False)
    out, code = run_line(fs, 'rm $(find . -name "*.tmp")')
    assert code == 0
    assert fs.get("a.tmp") is None and fs.get("b.tmp") is None


def test_command_substitution_is_skipped_inside_single_quotes():
    fs = FS()
    out, code = run_line(fs, "echo '$(pwd)'")
    assert out == "$(pwd)\n"


def test_sort_numeric_ignores_trailing_text():
    fs = FS()
    fs.write("f.txt", "  10 b\n   2 a\n   3 c\n", append=False)
    out, _ = run_line(fs, "sort -rn f.txt")
    assert out == "  10 b\n   3 c\n   2 a\n"


def test_grep_list_filenames_only():
    fs = FS()
    fs.write("x.txt", "hit here\n", append=False)
    fs.write("y.txt", "nothing\n", append=False)
    out, code = run_line(fs, "grep -l hit x.txt y.txt")
    assert out == "x.txt\n" and code == 0
