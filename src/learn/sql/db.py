"""Read-only, time- and row-capped sqlite connections for drills/cases, a DML/DDL throwaway-copy
connection for the write chapter, a plain-English EXPLAIN QUERY PLAN translator, and a friendlier
error rewriter. PLAN.md section 6 safety requirements: PRAGMA query_only, an authorizer restricted
to SELECT/WITH/EXPLAIN, a progress handler enforcing a wall-clock budget, and a row cap - all kept
exactly as before for the read-only chapters; only `connect_writable` grants write access, and only
on a throwaway in-memory copy that nothing else can see.
"""
import sqlite3
import time

from . import seed

ROW_CAP = 1000
TIME_BUDGET = 1.0  # seconds

_ALLOWED_AUTH = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    sqlite3.SQLITE_RECURSIVE,
}


def _authorize(action, arg1, arg2, db_name, trigger):
    return sqlite3.SQLITE_OK if action in _ALLOWED_AUTH else sqlite3.SQLITE_DENY


def connect(world: str = "company") -> sqlite3.Connection:
    """A locked-down connection for one of the seeded worlds: read-only, SELECT/WITH/EXPLAIN only,
    timed, row-capped. `world` is one of seed.WORLDS ("company", "shop", "stream")."""
    conn = seed.WORLDS[world]()
    conn.execute("PRAGMA query_only=ON")
    conn.set_authorizer(_authorize)
    return conn


def connect_writable(world: str = "company") -> sqlite3.Connection:
    """A throwaway copy of `world` with full INSERT/UPDATE/DELETE/CREATE access, for the DML/DDL
    chapter only. Each call is a fresh, independent in-memory db - nothing written here is ever
    visible to the read-only connect()."""
    return seed.WORLDS[world]()


class QueryTimeout(Exception):
    pass


class QueryError(Exception):
    """Carries a friendly message plus the original sqlite3 text."""

    def __init__(self, friendly: str, original: str):
        super().__init__(friendly)
        self.friendly = friendly
        self.original = original


def _friendly(msg: str) -> str:
    low = msg.lower()
    if "no such column" in low:
        return f"no such column - check the spelling / which table it belongs to ({msg})"
    if "no such table" in low:
        return f"no such table - check the spelling ({msg})"
    if "ambiguous column name" in low:
        return f"that column exists in more than one table here - qualify it as table.column ({msg})"
    if "syntax error" in low:
        return f"SQL syntax error ({msg})"
    if "not authorized" in low:
        return "only SELECT / WITH / EXPLAIN queries are allowed in this chapter"
    return msg


def run(conn: sqlite3.Connection, sql: str) -> tuple[list[str], list[tuple]]:
    """Run a query under the time/row budget. Returns (column names, rows). Works for both the
    read-only connections and `connect_writable` (INSERT/UPDATE/DELETE/CREATE included)."""
    deadline = time.monotonic() + TIME_BUDGET

    def _tick():
        return 1 if time.monotonic() > deadline else 0

    conn.set_progress_handler(_tick, 200)
    try:
        try:
            cur = conn.execute(sql)
        except sqlite3.ProgrammingError as exc:
            if "one statement" not in str(exc).lower():
                raise
            conn.executescript(sql)  # a multi-statement script (e.g. BEGIN; ...; ROLLBACK;)
            return [], []
        cols = [d[0] for d in (cur.description or [])]
        rows = cur.fetchmany(ROW_CAP)
        conn.commit()
        return cols, rows
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            raise QueryTimeout("query took too long (possible runaway join/recursion)") from exc
        raise QueryError(_friendly(str(exc)), str(exc)) from exc
    except sqlite3.DatabaseError as exc:
        raise QueryError(_friendly(str(exc)), str(exc)) from exc
    finally:
        conn.set_progress_handler(None, 0)


def rows_match(a: list[tuple], b: list[tuple], ordered: bool) -> bool:
    """Compare two result sets: order-insensitive by default, with float tolerance."""

    def norm(rows):
        out = []
        for row in rows:
            out.append(tuple(round(v, 6) if isinstance(v, float) else v for v in row))
        return out if ordered else sorted(out, key=repr)

    return norm(a) == norm(b)


# ---- Explain mode: EXPLAIN QUERY PLAN translated into one plain-English line per step ---------
def explain(conn: sqlite3.Connection, sql: str) -> list[str]:
    """Run `EXPLAIN QUERY PLAN <sql>` and translate each plan row into a short plain-English line
    (scan vs search, which table, which index if any). Read-only, uses the same connection/budget
    rules as `run` (query_only already blocks writes on a locked-down connection)."""
    cur = conn.execute("EXPLAIN QUERY PLAN " + sql)
    lines = []
    for _id, _parent, _notused, detail in cur.fetchall():
        lines.append(_translate_plan_line(detail))
    return lines or ["no plan rows (e.g. a constant or already-trivial query)"]


def _translate_plan_line(detail: str) -> str:
    d = detail.strip()
    low = d.lower()
    if low.startswith("scan"):
        table = d.split()[1] if len(d.split()) > 1 else "a table"
        return f"full scan of {table} - checks every row (no index used); add one if this table is big"
    if low.startswith("search"):
        table = d.split()[1] if len(d.split()) > 1 else "a table"
        if "using index" in low or "using covering index" in low:
            return f"search of {table} using an index - jumps straight to the matching rows"
        if "using integer primary key" in low or "using primary key" in low:
            return f"search of {table} by its primary key - the fastest lookup there is"
        return f"search of {table} - narrowed down, but not via a named index"
    if "use temp b-tree" in low:
        return "builds a temporary sorted structure (for ORDER BY / GROUP BY / DISTINCT without a matching index)"
    if "compound query" in low or "union" in low:
        return "combines the results of more than one sub-query"
    if "subquery" in low:
        return "runs an inner sub-query"
    return d
