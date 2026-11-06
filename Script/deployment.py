"""선택 순번과 배치 좌표를 분리하고 플레이어의 수동 배치를 검증한다."""

from collections.abc import Sequence

from board import Board
from character_data import CHARACTER_BY_ID, CharacterDefinition
from piece import Piece, Team


class Deployment:
    def __init__(self, selected: Sequence[CharacterDefinition]):
        if len(selected) != 4 or len({c.identifier for c in selected}) != 4:
            raise ValueError("서로 다른 캐릭터 4기를 먼저 선택해야 합니다.")
        self.selected = tuple(selected)
        self.positions: list[tuple[int, int] | None] = [None] * 4
        self.active_index = 0
        fixed = (("slayer", (5, 0)), ("warrior", (5, 2)),
                 ("archer", (7, 1)), ("assassin", (6, 3)))
        self.enemies = tuple(CHARACTER_BY_ID[key].create_piece(Team.RED, i + 1, cell)
                             for i, (key, cell) in enumerate(fixed))

    @property
    def ready(self) -> bool:
        return all(cell is not None for cell in self.positions)

    @property
    def players(self) -> tuple[Piece, ...]:
        return tuple(character.create_piece(Team.BLUE, i + 1, cell)
                     for i, (character, cell) in enumerate(zip(self.selected, self.positions))
                     if cell is not None)

    @property
    def board(self) -> Board:
        return Board((*self.players, *self.enemies))

    def select_slot(self, index: int) -> None:
        if not 0 <= index < len(self.selected):
            raise ValueError("배치할 기물을 선택하세요.")
        self.active_index = index

    def place(self, cell: tuple[int, int] | None) -> None:
        board = self.board
        if cell is None or not board.contains(cell):
            raise ValueError("보드 안의 칸을 선택하세요.")
        if not board.in_territory(Team.BLUE, cell):
            raise ValueError("플레이어는 왼쪽 A~D열에만 배치할 수 있습니다.")
        occupant = board.piece_at(cell)
        if occupant is not None and occupant.identifier != f"청{self.active_index + 1}":
            raise ValueError("다른 기물이 있는 칸에는 배치할 수 없습니다.")
        self.positions[self.active_index] = cell
        for offset in range(1, 5):
            candidate = (self.active_index + offset) % 4
            if self.positions[candidate] is None:
                self.active_index = candidate
                break
