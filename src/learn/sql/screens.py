"""Archive of Queries screens: region menu (3 cases + drills), a drill screen (with an Explain
Mode panel), and a case screen (world-aware - each case runs against its own seeded dataset).

Run key: PLAN.md flagged `ctrl+enter` as unverified under Textual on Windows (see
docs/learn-research.md). Both `f5` and `ctrl+enter` are bound to run the query here; `f5` is the
one documented in the footer/hints since it is the reliable fallback.
"""
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Input, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from .. import progress
from . import db
from .levels import CASES, DRILLS

RUN_BINDINGS = [Binding("f5", "run_query", "Run"), Binding("ctrl+enter", "run_query", "Run")]


class SqlRegionMenu(Screen):
    BINDINGS = [Binding("escape,q", "app.pop_screen", "Back")]
    CSS = "SqlRegionMenu #intro {padding: 1 2;}"

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static("Archive of Queries - the archivist follows a clue.", id="intro")
        options = [Option(f"Case {i + 1}: {c.title}", id=f"case:{i}") for i, c in enumerate(CASES)]
        options += [
            Option(f"{i + 1:>2}. {d.title} ({d.teach})", id=f"drill:{i}") for i, d in enumerate(DRILLS)
        ]
        yield OptionList(*options, id="levels")
        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        oid = event.option.id
        if oid.startswith("case:"):
            self.app.push_screen(CaseScreen(int(oid.split(":")[1])))
        elif oid.startswith("drill:"):
            self.app.push_screen(DrillScreen(int(oid.split(":")[1])))


def _fill_table(table: DataTable, cols: list[str], rows: list[tuple]) -> None:
    table.clear(columns=True)
    for c in cols:
        table.add_column(c)
    for row in rows[:200]:
        table.add_row(*(str(v) for v in row))


class DrillScreen(Screen):
    """A single query-matching drill. f5/ctrl+enter run, ctrl+r clear, f2 hint, f3 explain, escape back."""

    BINDINGS = [*RUN_BINDINGS, Binding("ctrl+r", "clear", "Clear"), Binding("f2", "toggle_hint", "Hint"),
                Binding("f3", "toggle_explain", "Explain"), Binding("escape", "app.pop_screen", "Back")]
    CSS = """
    DrillScreen #info {padding: 1 2 0 2; height: auto;}
    DrillScreen #sql {height: 6; margin: 1 2 0 2; border: solid $primary;}
    DrillScreen #results {height: 10; margin: 0 2;}
    DrillScreen #status {padding: 1 2; height: auto;}
    """

    def __init__(self, index: int):
        super().__init__()
        self.index = index
        self.drill = DRILLS[index]
        self.attempts = 0
        self.done = False
        self.saved = False
        self.hint = False
        self.explain_on = False
        self.explain_lines: list[str] = []
        self.status_msg = ""

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(id="info")
        yield TextArea(id="sql")
        yield DataTable(id="results")
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#results", DataTable).cursor_type = "row"
        self.query_one("#sql", TextArea).focus()
        self._draw()

    def action_clear(self) -> None:
        self.query_one("#sql", TextArea).text = ""

    def action_toggle_hint(self) -> None:
        self.hint = not self.hint
        self._draw()

    def action_toggle_explain(self) -> None:
        self.explain_on = not self.explain_on
        self._draw()

    def _connect(self):
        return db.connect_writable(self.drill.world) if self.drill.writable else db.connect(self.drill.world)

    def action_run_query(self) -> None:
        if self.done:
            return
        sql = self.query_one("#sql", TextArea).text.strip()
        if not sql:
            return
        self.attempts += 1
        d = self.drill
        try:
            if d.writable:
                conn = self._connect()
                db.run(conn, sql)
                cols, rows = db.run(conn, d.verify_sql)
                ref_conn = self._connect()
                db.run(ref_conn, d.reference_sql)
                _, ref_rows = db.run(ref_conn, d.verify_sql)
                if self.explain_on:
                    self.explain_lines = ["(explain is for the read-only chapters only)"]
            else:
                conn = self._connect()
                cols, rows = db.run(conn, sql)
                ref_conn = self._connect()
                _, ref_rows = db.run(ref_conn, d.reference_sql)
                if self.explain_on:
                    self.explain_lines = db.explain(self._connect(), sql)
        except (db.QueryError, db.QueryTimeout) as exc:
            self.status_msg = str(exc)
            self._draw()
            return
        _fill_table(self.query_one("#results", DataTable), cols, rows)
        if db.rows_match(rows, ref_rows, d.ordered):
            self.done = True
            self.status_msg = "correct!"
            if not self.saved:
                self.saved = True
                progress.record("sql", d.id, self.attempts, 2)
        else:
            self.status_msg = f"not quite - {len(rows)} row(s) back, that's not the expected result"
        self._draw()

    def _draw(self) -> None:
        d = self.drill
        info = Text(f"{d.title} ({d.teach})\n", style="bold")
        info.append(d.prompt)
        if d.writable:
            info.append("\n(this runs on a throwaway copy of the data - nothing else is affected)", style="dim")
        self.query_one("#info", Static).update(info)
        accent = self.app.theme_variables.get("primary", "#0178d4")
        st = Text(self.status_msg, style=accent if self.done else "yellow" if self.status_msg else "")
        if self.done:
            st.append(f"\nsolved in {self.attempts} attempt(s)   escape = back", style=accent)
        else:
            if self.hint:
                st.append("\nhint: " + "; ".join(d.hints), style="dim")
            if self.explain_on and self.explain_lines:
                st.append("\nquery plan:\n  " + "\n  ".join(self.explain_lines), style="dim")
            st.append("\nf5/ctrl+enter run   ctrl+r clear   f2 hint   f3 explain   escape back", style="dim")
        self.query_one("#status", Static).update(st)


class CaseScreen(Screen):
    """One case's console: a free query box plus an answer box to submit each step's clue.
    World-aware - every query here runs against that case's own seeded dataset (CASES[i].world)."""

    BINDINGS = [*RUN_BINDINGS, Binding("ctrl+r", "clear", "Clear"), Binding("f2", "toggle_hint", "Hint"),
                Binding("escape", "app.pop_screen", "Back")]
    CSS = """
    CaseScreen #info {padding: 1 2 0 2; height: auto;}
    CaseScreen #notebook {padding: 0 2; height: auto; color: $text-muted;}
    CaseScreen #sql {height: 6; margin: 1 2 0 2; border: solid $primary;}
    CaseScreen #results {height: 7; margin: 0 2;}
    CaseScreen #answer {margin: 0 2;}
    CaseScreen #status {padding: 1 2; height: auto;}
    """

    def __init__(self, index: int):
        super().__init__()
        self.index = index
        self.case = CASES[index]
        self.step = 0
        self.attempts = 0
        self.notebook: list[str] = []
        self.done = False
        self.saved = False
        self.hint = False
        self.status_msg = ""

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(id="info")
        yield Static(id="notebook")
        yield TextArea(id="sql")
        yield DataTable(id="results")
        yield Input(placeholder="submit your answer here, then Enter", id="answer")
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#results", DataTable).cursor_type = "row"
        self.query_one("#sql", TextArea).focus()
        self._draw()

    def action_clear(self) -> None:
        self.query_one("#sql", TextArea).text = ""

    def action_toggle_hint(self) -> None:
        self.hint = not self.hint
        self._draw()

    def action_run_query(self) -> None:
        sql = self.query_one("#sql", TextArea).text.strip()
        if not sql:
            return
        try:
            cols, rows = db.run(db.connect(self.case.world), sql)
        except (db.QueryError, db.QueryTimeout) as exc:
            self.status_msg = str(exc)
            self._draw()
            return
        _fill_table(self.query_one("#results", DataTable), cols, rows)
        self.status_msg = f"{len(rows)} row(s) back"
        self._draw()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.done:
            return
        self.attempts += 1
        current = self.case.steps[self.step]
        if event.value.strip().lower() == current.answer.strip().lower():
            self.notebook.append(f"{self.step + 1}. {current.answer}")
            self.step += 1
            self.query_one("#answer", Input).value = ""
            if self.step >= len(self.case.steps):
                self.done = True
                if not self.saved:
                    self.saved = True
                    progress.record("sql", f"case:{self.case.id}", self.attempts, len(self.case.steps))
                self.status_msg = "Case closed - caught by the data."
            else:
                self.status_msg = "correct - next clue."
        else:
            self.status_msg = "not quite - check your query again."
        self._draw()

    def _draw(self) -> None:
        info = Text(f"{self.case.title}\n", style="bold")
        if not self.done:
            info.append(f"Step {self.step + 1}/{len(self.case.steps)}: ", style="dim")
            info.append(self.case.steps[self.step].prompt)
        else:
            info.append(self.case.intro, style="dim")
        self.query_one("#info", Static).update(info)
        self.query_one("#notebook", Static).update("notebook: " + "; ".join(self.notebook))
        accent = self.app.theme_variables.get("primary", "#0178d4")
        st = Text(self.status_msg, style=accent if self.done else "")
        if self.hint and not self.done:
            st.append("\nhint query: " + self.case.steps[self.step].reference_sql, style="dim")
        st.append(
            "\nf5/ctrl+enter run   ctrl+r clear   f2 hint   type answer + Enter   escape back", style="dim"
        )
        self.query_one("#status", Static).update(st)
