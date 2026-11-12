"""직업별 한 칸 이동, 진영 경계와 점유 충돌의 공통 판정."""

from board import Board
from piece import Piece


class MovementRules:
    def __init__(self, board: Board):
        self.board = board

    def rejection(self, piece: Piece, destination: tuple[int, int] | None) -> str | None:
        if destination is None or not self.board.contains(destination):
            return "보드 밖으로 이동할 수 없습니다."
        if not self.board.allows_movement(piece.team, destination):
            return "중앙 경계선을 넘어 상대 진영으로 이동할 수 없습니다."
        if destination == piece.position:
            return "현재 위치입니다. 표시된 이동 가능 칸을 선택하세요."
        occupant = self.board.piece_at(destination)
        if occupant is not None:
            relationship = "아군" if occupant.team is piece.team else "상대"
            return f"{relationship} 기물이 있는 칸에는 이동할 수 없습니다."
        dx = destination[0] - piece.position[0]
        dy = destination[1] - piece.position[1]
        if (dx, dy) not in piece.job.directions:
            return "직업별 이동 방향으로 인접한 한 칸만 이동할 수 있습니다."
        return None

    def destinations(self, piece: Piece) -> tuple[tuple[int, int], ...]:
        x, y = piece.position
        candidates = ((x + dx, y + dy) for dx, dy in piece.job.directions)
        return tuple(cell for cell in candidates if self.rejection(piece, cell) is None)

