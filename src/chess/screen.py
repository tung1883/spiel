import asyncio
import io
import time

import chess
import chess.pgn
import httpx
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, OptionList, Static
from textual.widgets.option_list import Option

from .. import config
from ..base import AppScreen
from . import opening_book
from .board import BoardWidget
from .lichess import Lichess, LichessError

SEEKS = [("seek-10-0", "Play online 10+0 (casual)", 10, 0), ("seek-5-3", "Play online 5+3 (casual)", 5, 3),
         ("seek-15-10", "Play online 15+10 (casual)", 15, 10)]
AI = [("ai-1", "Play Stockfish level 1 (10+0)", 1), ("ai-4", "Play Stockfish level 4 (10+0)", 4), ("ai-7", "Play Stockfish level 7 (10+0)", 7)]


def _fmt_clock(ms: float) -> str:
    s = max(0, int(ms // 1000))
    return f"{s // 60}:{s % 60:02d}"


class LichessMenu(AppScreen):
    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        if config.lichess_token():
            options = [Option(label, id=oid) for oid, label, *_ in SEEKS] + [Option(label, id=oid) for oid, label, _ in AI]
            yield Static("Lichess - pick a game", id="msg")
            yield OptionList(*options)
        else:
            yield Static(
                "Paste a Lichess API token (https://lichess.org/account/oauth/token, scopes: board:play, challenge:write).\n"
                "Or set LICHESS_TOKEN. Stored in your user config dir.",
                id="msg",
            )
            yield Input(placeholder="lip_...", password=True, id="token")
        yield Footer()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        token = event.value.strip()
        if not token:
            return
        config.set_lichess_token(token)
        self.app.pop_screen()
        self.app.push_screen(LichessMenu())

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        oid = event.option.id
        for sid, _, minutes, inc in SEEKS:
            if oid == sid:
                self.app.push_screen(GameScreen(seek=(minutes, inc)))
        for aid, _, level in AI:
            if oid == aid:
                self.app.push_screen(GameScreen(ai_level=level))


class GameScreen(AppScreen):
    """Text-only game: type moves (e4, Nf3, e2e4) or a command (resign, draw, abort, back) and press Enter."""

    BINDINGS = [Binding("escape", "back", "Back")]
    CSS = """
    GameScreen {background: #000000;}
    #body {height: 1fr;}
    #board {width: auto; height: auto; margin: 1 0 0 1;}
    #side {height: 1fr; max-width: 60; margin: 0 1;}
    #side Static {border: round #5B6370; color: #D8D4C8; padding: 0 1;}
    #opp, #me {height: 4;}
    #hist {height: 1fr;}
    #status {height: auto; min-height: 3; max-height: 8;}
    #move {margin: 0 1;}
    """

    def __init__(self, seek: tuple[int, int] | None = None, ai_level: int | None = None, api_factory=None):
        super().__init__()
        self.seek, self.ai_level, self.api_factory = seek, ai_level, api_factory
        self.api: Lichess | None = None
        self.game_id = ""
        self.me = ""
        self.my_color: bool | None = None
        self.names = {chess.WHITE: "?", chess.BLACK: "?"}
        self.clocks = {chess.WHITE: 0.0, chess.BLACK: 0.0}
        self.clock_stamp = time.monotonic()
        self.status = "created"
        self.result = ""
        self.draw_offered = False
        self.message = "Connecting..."
        self.initial_fen: str | None = None
        self.board = chess.Board()
        self.tasks: list[asyncio.Task] = []

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        with Horizontal(id="body"):
            yield BoardWidget(id="board")
            with Vertical(id="side"):
                yield Static(id="opp")
                yield Static(id="hist")
                yield Static(id="me")
                yield Static(id="status")
        yield Input(placeholder="move (e4, Nf3, e2e4) or: resign  draw  abort  back", id="move")
        yield Footer()

    async def on_mount(self) -> None:
        super().on_mount()
        self.api = self.api_factory() if self.api_factory else Lichess(config.lichess_token())
        self.set_interval(0.2, self._tick)
        self.tasks.append(asyncio.create_task(self._run()))
        self._draw()
        self.query_one(BoardWidget).cursor = -1  # no cursor: moves are typed
        self.query_one("#move", Input).focus()

    # ---- network ------------------------------------------------------
    async def _run(self) -> None:
        try:
            acct = await self.api.account()
            self.me = acct["id"]
            if self.seek is None and self.ai_level is None:
                self.game_id = "browser"  # mirror a game already open elsewhere (chess.com)
            elif self.ai_level:
                self.message = "Starting game vs Stockfish..."
                game = await self.api.challenge_ai(self.ai_level, 10, 0)
                self.game_id = game["id"]
            else:
                self.game_id = await self._seek()
            await self._play()
        except LichessError as e:
            self.message = f"Lichess error: {e}"
        except httpx.HTTPError as e:
            self.message = f"Network error: {e}"
        except asyncio.CancelledError:
            raise

    async def _seek(self) -> str:
        minutes, inc = self.seek
        self.message = f"Seeking {minutes}+{inc} opponent... (b to cancel)"
        self._draw()
        found: asyncio.Future[str] = asyncio.get_running_loop().create_future()

        async def watch_events():
            async for ev in self.api.events():
                if ev.get("type") == "gameStart" and not found.done():
                    found.set_result(ev["game"]["gameId"])

        async def hold_seek():
            async for _ in self.api.seek(minutes, inc):
                pass

        watchers = [asyncio.create_task(watch_events()), asyncio.create_task(hold_seek())]
        self.tasks += watchers
        try:
            done = asyncio.ensure_future(found)
            while not done.done():
                for t in watchers:
                    if t.done() and t.exception():
                        raise t.exception()
                await asyncio.wait([done], timeout=0.5)
            return done.result()
        finally:
            for t in watchers:
                t.cancel()  # closing the seek request cancels the seek

    async def _play(self) -> None:
        async for ev in self.api.game_stream(self.game_id):
            kind = ev.get("type")
            if kind == "gameFull":
                white, black = ev["white"], ev["black"]
                self.my_color = chess.WHITE if white.get("id") == self.me else chess.BLACK
                self.names[chess.WHITE] = self._player_name(white)
                self.names[chess.BLACK] = self._player_name(black)
                self.query_one(BoardWidget).flipped = self.my_color == chess.BLACK
                self.query_one(BoardWidget).side = self.my_color
                fen = ev.get("initialFen")
                self.initial_fen = None if fen in (None, "startpos") else fen
                self.message = ""
                self._apply_state(ev["state"])
            elif kind == "gameState":
                self._apply_state(ev)
            self._draw()

    @staticmethod
    def _player_name(p: dict) -> str:
        if "aiLevel" in p:
            return f"Stockfish L{p['aiLevel']}"
        title = f"{p['title']} " if p.get("title") else ""
        rating = f" ({p['rating']})" if "rating" in p else ""
        return f"{title}{p.get('name', '?')}{rating}"

    def _apply_state(self, st: dict) -> None:
        board = chess.Board(self.initial_fen) if self.initial_fen else chess.Board()
        last = None
        for uci in st.get("moves", "").split():
            last = chess.Move.from_uci(uci)
            board.push(last)
        self.board = board
        self.query_one(BoardWidget).set_position(board, last)
        self.clocks = {chess.WHITE: float(st.get("wtime", 0)), chess.BLACK: float(st.get("btime", 0))}
        self.clock_stamp = time.monotonic()
        self.status = st.get("status", "started")
        self.draw_offered = bool(st.get("bdraw" if self.my_color == chess.WHITE else "wdraw"))
        if self.status not in ("created", "started"):
            winner = st.get("winner")
            self.result = f"{self.status}" + (f" - {winner} wins" if winner else "")

    # ---- UI -----------------------------------------------------------
    @property
    def live(self) -> bool:
        return self.status in ("created", "started") and self.my_color is not None

    def _tick(self) -> None:
        self._draw()

    ORDER = [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN]
    START = {chess.QUEEN: 1, chess.ROOK: 2, chess.BISHOP: 2, chess.KNIGHT: 2, chess.PAWN: 8}
    VALUE = {chess.QUEEN: 9, chess.ROOK: 5, chess.BISHOP: 3, chess.KNIGHT: 3, chess.PAWN: 1}

    def _material(self, by: bool) -> tuple[str, int]:
        """(pieces `by` has captured as icons, material points `by` is ahead by)."""
        def missing(color):
            return {t: max(0, n - len(self.board.pieces(t, color))) for t, n in self.START.items()}
        lost, mine_lost = missing(not by), missing(by)
        icons = " ".join(chess.piece_symbol(t).upper() * lost[t] for t in self.ORDER if lost[t])
        lead = sum(self.VALUE[t] * (lost[t] - mine_lost[t]) for t in self.ORDER)
        return icons, lead

    def _draw(self) -> None:
        opp, hist, me, status = (self.query_one(f"#{i}", Static) for i in ("opp", "hist", "me", "status"))
        for w, title in ((opp, ""), (hist, "History"), (me, ""), (status, "")):
            w.border_title = title
        if self.my_color is None:
            status.update(getattr(self.api, "hint", "") or self.message)
            return
        elapsed = (time.monotonic() - self.clock_stamp) * 1000
        for w, color in ((opp, not self.my_color), (me, self.my_color)):
            ms = self.clocks[color]
            if self.live and self.board.turn == color and len(self.board.move_stack) >= 2:
                ms -= elapsed
            icons, lead = self._material(color)
            w.border_title = self.names[color]
            w.border_subtitle = _fmt_clock(ms)
            w.update(f"{icons}{'  +' + str(lead) if lead > 0 else ''}" if icons else "")
        info = self.result or ("Your move" if self.board.turn == self.my_color else "Opponent thinking...")
        if self.draw_offered and self.live:
            info += "\nOpponent offers a draw (d to accept)"
        if self.message and not self.result:
            info += f"\n{self.message}"
        status.update(info)
        replay = chess.Board(self.initial_fen) if self.initial_fen else chess.Board()
        moves = []
        for m in self.board.move_stack:
            moves.append(replay.san(m))
            replay.push(m)
        rows = [f"{i // 2 + 1:>3}. {moves[i]:<8}{moves[i + 1] if i + 1 < len(moves) else ''}" for i in range(0, len(moves), 2)]
        visible = max(1, hist.size.height - 2)
        hist.update("\n".join(rows[-visible:]))
        opening = opening_book.classify(self.board.move_stack)
        hist.border_subtitle = f"{opening[0]} {opening[1]}" if opening else ""

    async def _send_move(self, move: chess.Move) -> None:
        try:
            await self.api.move(self.game_id, move.uci())
            self.message = ""
        except LichessError as e:
            self.message = f"Move rejected: {e}"

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        command = {"resign": self.action_resign, "abort": self.action_abort, "draw": self.action_draw,
                   "back": self.action_back, "quit": self.action_back}.get(text.lower())
        if command:
            await command()
            return
        if not self.live:
            self.message = "No game in progress"
            return
        if self.board.turn != self.my_color:
            self.message = "Not your move"
            return
        try:
            try:
                move = self.board.parse_san(text)
            except ValueError:
                move = self.board.parse_uci(text.lower())
        except ValueError:
            self.message = f"Illegal/unknown move: {text}"
            return
        await self._send_move(move)

    async def on_board_widget_move_requested(self, event: BoardWidget.MoveRequested) -> None:
        if self.live and self.board.turn == self.my_color:
            await self._send_move(event.move)

    async def _guard(self, coro) -> None:
        if not self.game_id or not self.live:
            return
        try:
            await coro
        except LichessError as e:
            self.message = str(e)

    async def action_resign(self) -> None:
        await self._guard(self.api.resign(self.game_id))

    async def action_abort(self) -> None:
        await self._guard(self.api.abort(self.game_id))

    async def action_draw(self) -> None:
        await self._guard(self.api.draw(self.game_id, True))

    async def action_back(self) -> None:
        for t in self.tasks:
            t.cancel()
        await self.api.close()
        self.app.pop_screen()


class ChessComScreen(AppScreen):
    """Read-only Chess.com view: no official/public API exists for making moves."""

    BINDINGS = [Binding("escape", "back", "Back")]
    API = "https://api.chess.com/pub"

    def __init__(self):
        super().__init__()
        self.games: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static("Chess.com has no public API for playing moves. Enter a username to view their current daily games.", id="msg")
        yield Input(placeholder="chess.com username", id="user")
        yield OptionList(id="games")
        yield BoardWidget(id="board", clickable=False)
        yield Footer()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user = event.value.strip().lower()
        msg = self.query_one("#msg", Static)
        if not user:
            return
        try:
            async with httpx.AsyncClient(headers={"User-Agent": "spiel"}, timeout=15) as c:
                r = await c.get(f"{self.API}/player/{user}/games")
                r.raise_for_status()
                self.games = r.json().get("games", [])
        except httpx.HTTPError as e:
            msg.update(f"Error: {e}")
            return
        options = self.query_one("#games", OptionList)
        options.clear_options()
        for i, g in enumerate(self.games):
            w = g["white"].rsplit("/", 1)[-1]
            b = g["black"].rsplit("/", 1)[-1]
            options.add_option(Option(f"{w} vs {b}  ({g.get('time_class', '')}, {g.get('turn', '?')} to move)", id=str(i)))
        msg.update(f"{len(self.games)} daily game(s) for {user}" if self.games else f"No daily games in progress for {user}")
        options.focus()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option.id is None:
            return
        g = self.games[int(event.option.id)]
        pgn = chess.pgn.read_game(io.StringIO(g.get("pgn", "")))
        board = chess.Board(g["fen"]) if g.get("fen") else (pgn.end().board() if pgn else chess.Board())
        w = self.query_one(BoardWidget)
        w.flipped = False
        w.set_position(board, pgn.end().move if pgn and pgn.end().move else None)

    def action_back(self) -> None:
        self.app.pop_screen()


class ChessComLogin(AppScreen):
    """One-time login: paste the CHESSCOM_REMEMBERME cookie (chess.com's password login is behind a bot check)."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]
    HELP = "\n".join([
        "Chess.com login (one time)",
        "",
        "Passwords can't be sent from here (chess.com protects login with a bot check), so log in in your own",
        "browser, then copy one cookie:",
        "  1. open chess.com, F12 -> Application (Chrome) / Storage (Firefox) -> Cookies -> https://www.chess.com",
        "  2. copy the Value of CHESSCOM_REMEMBERME and paste it below, Enter",
        "",
        "It stays on this machine (chesscom-session.json) and renews the session by itself.",
    ])
    CSS = "ChessComLogin #msg {padding: 1 2;} ChessComLogin #status {padding: 0 2;}"

    def __init__(self, then=None):
        super().__init__()
        self.then = then

    def compose(self) -> ComposeResult:
        yield Header(icon="")
        yield Static(self.HELP, id="msg")
        yield Input(placeholder="CHESSCOM_REMEMBERME value", password=True, id="cookie")
        yield Static("", id="status")
        yield Footer()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        from . import chesscom_session as cs

        status = self.query_one("#status", Static)
        status.update("checking...")
        try:
            sess = await cs.login_from_remember(event.value)
        except cs.LoginError as e:
            status.update(f"failed: {e}")
            return
        self.app.pop_screen()
        if self.then:
            self.then(sess)


class ChessComMenu(AppScreen):
    """Chess.com live games: plain HTTP + WebSocket, no browser (chesscom_direct.py)."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back"), Binding("l", "logout", "Log out")]
    OPTIONS = [
        ("live-10", "Live game 10 min", "10 min"),
        ("live-5", "Live game 5 min", "5 min"),
        ("live-3+2", "Live game 3 + 2", "3 + 2"),
        ("live-15+10", "Live game 15 + 10", "15 + 10"),
        ("view", "View a user's daily games (read-only, public API)", None),
    ]

    def compose(self) -> ComposeResult:
        from . import chesscom_session as cs

        who = (cs.load() or {}).get("username")
        yield Header(icon="")
        yield Static(
            f"Logged in as {who}. " if who else "Not logged in yet (you'll be asked to paste a cookie). "
            "Games are UNRATED unless TUI_GAMES_CHESSCOM_RATED=1.",
            id="msg",
        )
        yield OptionList(*[Option(label, id=oid) for oid, label, _ in self.OPTIONS])
        yield Footer()

    def action_logout(self) -> None:
        from . import chesscom_session as cs

        cs.clear()
        self.query_one("#msg", Static).update("Logged out.")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        from . import chesscom_session as cs
        from .chesscom_direct import ChessComDirect

        tc = next(t for oid, _, t in self.OPTIONS if oid == event.option.id)
        if tc is None:
            self.app.push_screen(ChessComScreen())
            return

        def play(_sess=None):
            self.app.push_screen(GameScreen(api_factory=lambda: ChessComDirect(("live", tc))))

        if cs.load():
            play()
        else:
            self.app.push_screen(ChessComLogin(then=play))
