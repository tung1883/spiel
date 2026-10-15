"""Chessboard widget: text-only pieces (capital letter = white, lowercase = black) on a dark slate board.

Layout follows chess-tui (https://github.com/thomas-mauran/chess-tui, MIT): blue cursor, green selection and last
move, amber legal-move squares, magenta king in check.
"""
import chess
from rich.text import Text
from textual.widgets import Static

# Dark slate theme. Black pieces stay near-black, so the squares are mid-dark.
LIGHT, DARK = "#66707F", "#434B58"
WHITE_PIECE, BLACK_PIECE = "#F4F1E6", "#0B0D11"
CURSOR, HIGHLIGHT, TARGET, CHECK = "#3B82C4", "#4E8A5B", "#8A7A4A", "#B04A8F"
COORD = "#8B93A1"

CELL_W, CELL_H = 3, 1  # compact: one text row per rank


class BoardWidget(Static):
    """Chessboard with an optional keyboard cursor (cursor < 0 hides it)."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.board = chess.Board()
        self.flipped = False
        self.cursor = chess.E2
        self.selected: int | None = None
        self.last_move: chess.Move | None = None

    def set_position(self, board: chess.Board, last_move: chess.Move | None = None) -> None:
        self.board, self.last_move = board, last_move
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
        else:
            bg = LIGHT if (chess.square_file(sq) + chess.square_rank(sq)) % 2 == 1 else DARK
        return CURSOR if sq == self.cursor else bg

    def _build(self) -> Text:
        ranks = range(8) if self.flipped else range(7, -1, -1)
        files = range(7, -1, -1) if self.flipped else range(8)
        targets = self.targets()
        out = Text()
        for rank in ranks:
            for line in range(CELL_H):
                out.append(f"{rank + 1} " if line == CELL_H // 2 else "  ", style=COORD)
                for file in files:
                    sq = chess.square(file, rank)
                    piece = self.board.piece_at(sq)
                    fg, label = WHITE_PIECE, " " * CELL_W
                    if piece and line == CELL_H // 2:
                        fg = WHITE_PIECE if piece.color else BLACK_PIECE
                        label = piece.symbol().center(CELL_W)
                    out.append(label, style=f"bold {fg} on {self._bg(sq, targets)}")
                out.append("\n")
        out.append("  ")
        for file in files:
            out.append(chess.FILE_NAMES[file].center(CELL_W), style=COORD)
        return out
