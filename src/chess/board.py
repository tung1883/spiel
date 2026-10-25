"""Chessboard widget: 8x8 pixel-art pieces (light = white, dark = black) on a dark slate board.

Layout follows chess-tui (https://github.com/thomas-mauran/chess-tui, MIT): blue cursor, green selection and last
move, amber legal-move squares, magenta king in check.
"""
import chess
from rich.text import Text
from textual import events
from textual.message import Message
from textual.widgets import Static

# Dark slate theme. Black pieces stay near-black, so the squares are mid-dark.
LIGHT, DARK = "#66707F", "#434B58"
WHITE_PIECE, BLACK_PIECE = "#F4F1E6", "#0B0D11"
CURSOR, HIGHLIGHT, TARGET, CHECK = "#3B82C4", "#4E8A5B", "#8A7A4A", "#B04A8F"
HINT = "#22D3EE"
COORD = "#8B93A1"

CELL_W, CELL_H = 8, 4  # each piece is an 8x8 pixel bitmap drawn with half-blocks (2 pixel rows per text row)

# Pixel-art pieces in the style of Darokahn/Chess: "#" = piece pixel.
SPRITES = {
    "p": ("........", "........", "...##...", "..####..", "..####..", "...##...", "..####..", ".######."),
    "r": ("........", ".#.##.#.", ".######.", "..####..", "..####..", "..####..", ".######.", ".######."),
    "n": ("........", "...##...", "..####..", ".#####..", ".#####..", "...###..", "..####..", ".######."),
    "b": ("........", "...##...", "..##....", "..####..", "...##...", "...##...", "..####..", ".######."),
    "q": ("........", "...##...", ".#.##.#.", ".######.", "..####..", "...##...", "..####..", ".######."),
    "k": ("........", "...##...", "..####..", "...##...", ".######.", "..####..", "..####..", ".######."),
}


class BoardWidget(Static):
    """Chessboard with an optional keyboard cursor (cursor < 0 hides it).

    Mouse: click a piece of `side` (default: side to move), then click a highlighted square. Posts MoveRequested
    (pawn promotions become queens). Set `clickable = False` for read-only boards.
    """

    class MoveRequested(Message):
        def __init__(self, move: chess.Move):
            super().__init__()
            self.move = move

    def __init__(self, clickable: bool = True, **kw):
        super().__init__(**kw)
        self.board = chess.Board()
        self.flipped = False
        self.cursor = chess.E2
        self.selected: int | None = None
        self.last_move: chess.Move | None = None
        self.hint_squares: set[int] = set()
        self.clickable = clickable
        self.side: bool | None = None

    def set_position(self, board: chess.Board, last_move: chess.Move | None = None) -> None:
        self.board, self.last_move = board, last_move
        self.selected = None
        self.refresh_board()

    def set_hint(self, move: chess.Move | None) -> None:
        """Highlights an engine best-move/puzzle-hint as a pair of squares (from/to) - lowest
        priority in _bg(), so it never overrides check/selection/last-move/legal-target coloring."""
        self.hint_squares = {move.from_square, move.to_square} if move else set()
        self.refresh_board()

    def on_click(self, event: events.Click) -> None:
        file, row = (event.x - 2) // CELL_W, event.y // CELL_H
        if not self.clickable or not (0 <= file < 8 and 0 <= row < 8):
            return
        sq = chess.square(7 - file if self.flipped else file, row if self.flipped else 7 - row)
        piece = self.board.piece_at(sq)
        side = self.board.turn if self.side is None else self.side
        if self.selected is not None and sq in self.targets():
            move = chess.Move(self.selected, sq)
            if self.board.piece_type_at(self.selected) == chess.PAWN and chess.square_rank(sq) in (0, 7):
                move.promotion = chess.QUEEN
            self.selected = None
            self.refresh_board()
            self.post_message(self.MoveRequested(move))
            return
        self.selected = sq if piece and piece.color == side and sq != self.selected else None
        self.refresh_board()

    def move_cursor(self, dfile: int, drank: int) -> None:
        if self.flipped:
            dfile, drank = -dfile, -drank
        f = min(7, max(0, chess.square_file(self.cursor) + dfile))
        r = min(7, max(0, chess.square_rank(self.cursor) + drank))
        self.cursor = chess.square(f, r)
        self.refresh_board()

    def targets(self) -> set[int]:
        if self.selected is None:
            return set()
        return {m.to_square for m in self.board.legal_moves if m.from_square == self.selected}

    def refresh_board(self) -> None:
        self.update(self._build())

    def _bg(self, sq: int, targets: set[int]) -> str:
        """Square colour, in chess-tui's priority: check > selected / last move > legal target > plain."""
        if self.board.is_check() and sq == self.board.king(self.board.turn):
            bg = CHECK
        elif sq == self.selected or (self.last_move and sq == self.last_move.to_square) or (
                self.last_move and sq == self.last_move.from_square and sq not in targets):
            bg = HIGHLIGHT
        elif sq in targets:
            bg = TARGET
        elif sq in self.hint_squares:
            bg = HINT
        else:
            bg = LIGHT if (chess.square_file(sq) + chess.square_rank(sq)) % 2 == 1 else DARK
        return CURSOR if sq == self.cursor else bg

    def _build(self) -> Text:
        ranks = range(8) if self.flipped else range(7, -1, -1)
        files = range(7, -1, -1) if self.flipped else range(8)
        targets = self.targets()
        out = Text()
        for rank in ranks:
            cells = []
            for file in files:
                sq = chess.square(file, rank)
                piece = self.board.piece_at(sq)
                bg = self._bg(sq, targets)
                sprite = SPRITES[piece.symbol().lower()] if piece else None
                fg = WHITE_PIECE if piece and piece.color else BLACK_PIECE
                cells.append((bg, sprite, fg))
            for line in range(CELL_H):
                out.append(f"{rank + 1} " if line == CELL_H // 2 else "  ", style=COORD)
                for bg, sprite, fg in cells:
                    for x in range(CELL_W):
                        top = sprite is not None and sprite[2 * line][x] == "#"
                        bot = sprite is not None and sprite[2 * line + 1][x] == "#"
                        out.append("▀", style=f"{fg if top else bg} on {fg if bot else bg}")
                out.append("\n")
        out.append("  ")
        for file in files:
            out.append(chess.FILE_NAMES[file].center(CELL_W), style=COORD)
        return out
