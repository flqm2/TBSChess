"""배치된 기물의 이동·턴 연결. pico2d 없이도 같은 규칙을 검증할 수 있다."""

from collections import deque
from collections.abc import Iterable
from itertools import zip_longest

from board import Board
from movement import MovementRules
from piece import Piece, Team
from turn_manager import TurnManager


class Prototype:
    def __init__(self, pieces: Iterable[Piece]):
        self.board = Board(pieces)
        self.movement = MovementRules(self.board)
        blue = [piece for piece in self.board.pieces if piece.team is Team.BLUE]
        red = [piece for piece in self.board.pieces if piece.team is Team.RED]
        order = (piece for pair in zip_longest(blue, red) for piece in pair if piece is not None)
        self.turns = TurnManager(order)
        self.message = f"{self.current.identifier} {self.current.name}의 이동 가능 칸을 클릭하세요."
        self.failed = False
        self.history: deque[str] = deque(maxlen=4)

    @property
    def current(self) -> Piece:
        return self.turns.current

    @property
    def legal_moves(self) -> tuple[tuple[int, int], ...]:
        return self.movement.destinations(self.current)

    def try_move(self, destination: tuple[int, int] | None) -> bool:
        piece = self.current
        reason = self.movement.rejection(piece, destination)
        if reason is not None:
            self.message = reason
            self.failed = True
            return False
        old = piece.position
        piece.position = destination
        self.history.appendleft(
            f"R{self.turns.round:02}  {piece.identifier} {piece.name}  "
            f"{self.cell_name(old)} → {self.cell_name(destination)}"
        )
        self.turns.advance()
        self.message = f"이동 완료. {self.current.identifier} {self.current.name} 차례입니다."
        self.failed = False
        return True

    def skip_turn(self) -> None:
        piece = self.current
        self.history.appendleft(f"R{self.turns.round:02}  {piece.identifier} {piece.name}  검증용 턴 넘김")
        self.turns.advance()
        self.message = f"턴 넘김. {self.current.identifier} {self.current.name} 차례입니다."
        self.failed = False

    @staticmethod
    def cell_name(cell: tuple[int, int]) -> str:
        return f"{chr(ord('A') + cell[0])}{cell[1] + 1}"

