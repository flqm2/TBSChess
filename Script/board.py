"""8×4 보드의 좌표와 점유 상태. 렌더링이나 턴을 계산하지 않는다."""

from collections.abc import Iterable

from piece import Piece, Team


class Board:
    columns = 8
    rows = 4

    def __init__(self, pieces: Iterable[Piece]):
        self.pieces = tuple(pieces)
        identifiers = {piece.identifier for piece in self.pieces}
        positions = {piece.position for piece in self.pieces}
        if len(identifiers) != len(self.pieces):
            raise ValueError("기물 식별자는 중복될 수 없습니다.")
        if len(positions) != len(self.pieces):
            raise ValueError("같은 칸에 기물을 겹쳐 배치할 수 없습니다.")
        if any(not self.contains(piece.position) for piece in self.pieces):
            raise ValueError("기물은 보드 안에 배치해야 합니다.")

    def contains(self, cell: tuple[int, int]) -> bool:
        x, y = cell
        return 0 <= x < self.columns and 0 <= y < self.rows

    def piece_at(self, cell: tuple[int, int]) -> Piece | None:
        return next((piece for piece in self.pieces if piece.current_hp > 0 and piece.position == cell), None)

    @property
    def living_pieces(self) -> tuple[Piece, ...]:
        return tuple(piece for piece in self.pieces if piece.current_hp > 0)

    def in_territory(self, team: Team, cell: tuple[int, int]) -> bool:
        if not self.contains(cell):
            return False
        midpoint = self.columns // 2
        return cell[0] < midpoint if team is Team.BLUE else cell[0] >= midpoint

