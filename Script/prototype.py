"""배치된 기물의 이동·턴 연결. pico2d 없이도 같은 규칙을 검증할 수 있다."""

from collections import deque
from collections.abc import Iterable
from itertools import zip_longest

from board import Board
from movement import MovementRules
from piece import Job, Piece, Team
from turn_manager import TurnManager


class Prototype:
    def __init__(self, pieces: Iterable[Piece] | None = None):
        blue1 = Piece("청1", "슬레이어", Team.BLUE, Job.MELEE,
                      "남색 망토의 대검 슬레이어-1.png", (2, 1))
        blue2 = Piece("청2", "암살자", Team.BLUE, Job.JOKER,
                      "고요한 쌍단검 암살자-2.png", (1, 2))
        red1 = Piece("홍1", "메이지", Team.RED, Job.RANGED,
                     "은발의 푸른 마도사-6.png", (5, 1))
        red2 = Piece("홍2", "카드술사", Team.RED, Job.JOKER,
                     "라벤더 카드를 든 마법사-5.png", (6, 2))
        self.board = Board(pieces if pieces is not None else (blue1, blue2, red1, red2))
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

