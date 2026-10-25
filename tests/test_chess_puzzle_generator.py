import chess
import chess.engine
import chess.pgn
import pytest

from src.chess import puzzle_generator as pg


def _pov(value, mate, color):
    score = chess.engine.Mate(mate) if mate is not None else chess.engine.Cp(value)
    return chess.engine.PovScore(score, color)


class FakeEngine:
    """Stands in for AnalysisEngine: dispatches on `depth` to one of two scripted queues
    (pair queue for PAIR_DEPTH/multipv=2, defense queue for DEFENSE_DEPTH/multipv=1), each a
    list of (move_uci, cp_or_None, mate_or_None, second_cp_or_None, second_mate_or_None)."""

    def __init__(self, pair_queue=None, defense_queue=None):
        self.pair_queue = list(pair_queue or [])
        self.defense_queue = list(defense_queue or [])

    async def analyse(self, board, depth, multipv=1, time_limit=0.5):
        if depth == pg.DEFENSE_DEPTH:
            move_uci, cp, mate = self.defense_queue.pop(0)
            move = chess.Move.from_uci(move_uci)
            return [{"score": _pov(cp, mate, board.turn), "pv": [move]}]
        move_uci, cp, mate, second_cp, second_mate = self.pair_queue.pop(0)
        move = chess.Move.from_uci(move_uci)
        infos = [{"score": _pov(cp, mate, board.turn), "pv": [move]}]
        if second_cp is not None or second_mate is not None:
            infos.append({"score": _pov(second_cp, second_mate, board.turn), "pv": [move]})
        return infos


def _game(white="A", black="B"):
    g = chess.pgn.Game()
    g.headers["White"] = white
    g.headers["Black"] = black
    g.headers["Date"] = "2025.01.01"
    return g


# ---- pure functions --------------------------------------------------------

def test_win_chances_cp_and_mate_edges():
    assert pg.win_chances(chess.engine.Cp(0)) == pytest.approx(0.0)
    assert pg.win_chances(chess.engine.Cp(100)) == pytest.approx(2 / (1 + __import__("math").exp(-0.368208)) - 1)
    assert pg.win_chances(chess.engine.Mate(3)) == 1.0
    assert pg.win_chances(chess.engine.Mate(-3)) == -1.0


def test_score_key_total_ordering():
    keys = [pg._score_key(s) for s in [
        chess.engine.Mate(1), chess.engine.Mate(3), chess.engine.Cp(2000),
        chess.engine.Cp(-2000), chess.engine.Mate(-3), chess.engine.Mate(-1),
    ]]
    assert keys == sorted(keys, reverse=True)


def test_material_diff():
    board = chess.Board()
    board.remove_piece_at(chess.D1)  # white loses its queen
    assert pg._material_diff(board, chess.BLACK) == 9
    assert pg._material_diff(board, chess.WHITE) == -9


def test_count_immediate_mates_lone_king():
    board = chess.Board("7k/8/5QK1/8/8/8/8/8 w - - 0 1")
    assert pg._count_immediate_mates(board) == 3  # Qf8#, Qd8#, Qg7# all mate immediately
    board.push(chess.Move.from_uci("g6f7"))
    board.push(chess.Move.from_uci("h8h7"))
    assert pg._count_immediate_mates(board) == 2  # Qf6-h4# and Qf6-g7# both mate immediately


# ---- analyze_position skip conditions (no engine needed) ------------------

@pytest.mark.asyncio
async def test_analyze_position_skips_when_winner_already_material_ahead():
    board = chess.Board()
    board.remove_piece_at(chess.D8)  # black (about to move) is down a queen -> white's up
    result = await pg._analyze_position(None, board, chess.engine.Cp(20), chess.engine.Cp(500),
                                         _game(), "src", 1)
    assert result is None


@pytest.mark.asyncio
async def test_analyze_position_skips_trivial_mate_in_one():
    board = chess.Board("7k/8/5QK1/8/8/8/8/8 w - - 0 1")
    result = await pg._analyze_position(None, board, chess.engine.Cp(20), chess.engine.Mate(1),
                                         _game(), "src", 1)
    assert result is None


# ---- mate path --------------------------------------------------------------

@pytest.mark.asyncio
async def test_cook_mate_and_try_mate_find_a_genuine_forced_mate():
    # Verified with python-chess alone (no engine): from this position, Kf7 forces ...Kh7,
    # after which Qh4# is the only mate-in-1 - a genuine forced mate in 2.
    board = chess.Board("7k/8/5QK1/8/8/8/8/8 w - - 0 1")
    engine = FakeEngine(
        pair_queue=[("g6f7", None, 2, None, None), ("f6h4", None, 1, None, None)],
        defense_queue=[("h8h7", None, None)],
    )
    puzzle = await pg._try_mate(engine, board, chess.WHITE, _game(), "src", 5)
    assert puzzle is not None
    assert puzzle.category == "mate"
    assert puzzle.solution_uci == ["g6f7", "h8h7", "f6h4"]
    assert puzzle.cp is None
    assert puzzle.winner_white is True


@pytest.mark.asyncio
async def test_cook_mate_rejects_when_pair_never_reaches_mate_soon():
    board = chess.Board("7k/8/5QK1/8/8/8/8/8 w - - 0 1")
    engine = FakeEngine(pair_queue=[("g6f7", 50, None, None, None)])  # not a mate at all
    result = await pg._cook_mate(engine, board, chess.WHITE)
    assert result is None


# ---- advantage path ----------------------------------------------------------

@pytest.mark.asyncio
async def test_cook_advantage_terminates_on_validation_failure_and_trims():
    board = chess.Board()
    # cp values are each from the MOVER's own point of view (UCI convention) - get_next_pair
    # converts to winner=white's pov itself, so black-ply entries are negative (white's ahead
    # means black's own-pov score is bad) even though white is the one benefiting overall.
    engine = FakeEngine(pair_queue=[
        ("e2e4", 300, None, -100, None),     # white, valid attack (big win-chance gap) - kept
        ("e7e5", -290, None, -280, None),    # black, unvalidated - kept
        ("g1f3", 280, None, -100, None),     # white, valid attack - kept
        ("b8c6", -270, None, -260, None),    # black, unvalidated - kept
        ("f1b5", 260, None, 250, None),      # white, gap too small - invalid -> stop
    ])
    puzzle = await pg._try_advantage(engine, board, chess.WHITE, _game(), "src", 1)
    assert puzzle is not None
    assert puzzle.category == "advantage"
    assert puzzle.solution_uci == ["e2e4", "e7e5", "g1f3"]
    assert puzzle.cp == 280


@pytest.mark.asyncio
async def test_try_advantage_rejects_a_one_mover():
    board = chess.Board()
    engine = FakeEngine(pair_queue=[
        ("e2e4", 300, None, -100, None),     # white, valid attack - kept
        ("e7e5", -290, None, -280, None),    # black, unvalidated - kept, but trimmed off below
        ("g1f3", 280, None, 270, None),      # white, gap too small - invalid -> stop
    ])
    # 2 pairs accumulate, trimmed down to 1 (even-length trim) - too short, rejected.
    puzzle = await pg._try_advantage(engine, board, chess.WHITE, _game(), "src", 1)
    assert puzzle is None


# ---- full ply-walk, quiet game ----------------------------------------------

@pytest.mark.asyncio
async def test_analyze_game_finds_nothing_in_a_quiet_game():
    class QuietEngine:
        async def analyse(self, board, depth, multipv=1, time_limit=0.5):
            return [{"score": chess.engine.PovScore(chess.engine.Cp(10), board.turn), "pv": [next(iter(board.legal_moves))]}]

    game = _game()
    board = chess.Board()
    for san in ["e4", "e5", "Nf3", "Nc6"]:
        board.push_san(san)
    node = game
    for move in board.move_stack:
        node = node.add_variation(move)

    result = await pg.analyze_game(QuietEngine(), game, source="src")
    assert result is None
