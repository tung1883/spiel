import pytest

from tui_games.learn.sql import db
from tui_games.learn.sql.levels import CASES, DRILLS


@pytest.fixture
def conn():
    return db.connect()


@pytest.mark.parametrize("drill", [d for d in DRILLS if not d.writable], ids=[d.id for d in DRILLS if not d.writable])
def test_readonly_drill_reference_sql_runs(drill):
    cols, rows = db.run(db.connect(drill.world), drill.reference_sql)
    assert cols
    assert rows, drill.id  # every drill's reference has at least one row back


@pytest.mark.parametrize("drill", [d for d in DRILLS if d.writable], ids=[d.id for d in DRILLS if d.writable])
def test_writable_drill_reference_sql_lands_and_verifies(drill):
    conn = db.connect_writable(drill.world)
    db.run(conn, drill.reference_sql)
    cols, rows = db.run(conn, drill.verify_sql)
    assert cols
    assert rows, drill.id  # the verify query proves the INSERT/UPDATE/DELETE/CREATE/rollback landed


def test_writable_drills_never_touch_the_readonly_connection(conn):
    # the fixture's read-only connection must still reject writes even though writable drills exist
    with pytest.raises(db.QueryError):
        db.run(conn, "INSERT INTO users VALUES (9,'heidi','heidi@corp.dev','2024-07-01',0)")


def test_drills_have_unique_ids():
    assert len(DRILLS) == len(set(d.id for d in DRILLS))


def test_drill_count_is_substantial():
    assert len(DRILLS) >= 24


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_case_steps_chain_to_their_answers(case):
    conn = db.connect(case.world)
    for step in case.steps:
        _, rows = db.run(conn, step.reference_sql)
        assert rows, (case.id, step.prompt)
        got = str(rows[0][0]).strip().lower()
        assert got == step.answer.strip().lower(), (case.id, step.prompt, rows)


def test_three_cases_exist():
    assert len(CASES) == 3
    assert len({c.world for c in CASES}) == 3  # each case has its own distinct seeded world


def test_readonly_connection_rejects_writes(conn):
    with pytest.raises(db.QueryError):
        db.run(conn, "DELETE FROM users")
    with pytest.raises(db.QueryError):
        db.run(conn, "DROP TABLE users")
    with pytest.raises(db.QueryError):
        db.run(conn, "ATTACH DATABASE ':memory:' AS evil")
    # the data is still intact
    _, rows = db.run(conn, "SELECT COUNT(*) FROM users")
    assert rows[0][0] == 8


def test_bad_sql_gives_friendly_error(conn):
    with pytest.raises(db.QueryError) as exc:
        db.run(conn, "SELECT nope FROM users")
    assert "no such column" in exc.value.friendly


def test_rows_match_is_order_insensitive_with_float_tolerance():
    a = [(1, 1.0000001), (2, 2.0)]
    b = [(2, 2.0), (1, 1.0)]
    assert db.rows_match(a, b, ordered=False)
    assert not db.rows_match(a, b, ordered=True)


def test_query_timeout_on_runaway_query(conn):
    # COUNT(*) over a 5-way self-cross-join forces the full cartesian product before any row is
    # returned (the row cap can't short-circuit it), so a zeroed time budget reliably trips.
    old = db.TIME_BUDGET
    db.TIME_BUDGET = 0.0
    try:
        with pytest.raises((db.QueryTimeout, db.QueryError)):
            db.run(conn, "SELECT COUNT(*) FROM commits a, commits b, commits c, commits d, commits e")
    finally:
        db.TIME_BUDGET = old


def test_explain_translates_scan_vs_search():
    conn = db.connect()
    lines = db.explain(conn, "SELECT * FROM users WHERE id=1")
    assert any("primary key" in l.lower() or "search" in l.lower() for l in lines)
    lines2 = db.explain(conn, "SELECT * FROM commits WHERE message LIKE '%fix%'")
    assert any("scan" in l.lower() for l in lines2)


def test_shop_and_stream_worlds_are_seeded_independently():
    shop = db.connect("shop")
    _, rows = db.run(shop, "SELECT COUNT(*) FROM customers")
    assert rows[0][0] == 6
    stream = db.connect("stream")
    _, rows = db.run(stream, "SELECT COUNT(*) FROM artists")
    assert rows[0][0] == 5
