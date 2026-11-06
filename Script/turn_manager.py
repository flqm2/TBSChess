"""고정 기물 순서와 라운드. 성공한 이동 또는 검증용 넘김만 턴을 소모한다."""

from collections.abc import Iterable

from piece import Piece


class TurnManager:
    def __init__(self, order: Iterable[Piece]):
        self.order = tuple(order)
        if not self.order or len({p.identifier for p in self.order}) != len(self.order):
            raise ValueError("턴 순서는 중복 없이 한 기물 이상이어야 합니다.")
        self.index = 0
        self.round = 1

    @property
    def current(self) -> Piece:
        return self.order[self.index]

    @property
    def acted(self) -> tuple[Piece, ...]:
        return self.order[:self.index]

    def advance(self) -> None:
        self.index += 1
        if self.index == len(self.order):
            self.index = 0
            self.round += 1

