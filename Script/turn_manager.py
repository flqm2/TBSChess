"""고정 기물 순서와 라운드. 기절하거나 처치된 슬롯은 건너뛴다."""

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

    def advance(self) -> tuple[Piece, ...]:
        if not any(piece.current_hp > 0 for piece in self.order):
            return ()
        skipped = []
        while True:
            self.index += 1
            if self.index == len(self.order):
                self.index = 0
                self.round += 1
            piece = self.current
            if piece.current_hp == 0:
                continue
            if piece.stunned:
                piece.stunned = False
                skipped.append(piece)
            else:
                return tuple(skipped)

