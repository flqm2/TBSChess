"""기물 순서와 라운드. 기절하거나 처치된 슬롯은 건너뛴다."""

from collections.abc import Callable, Iterable

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

    @property
    def upcoming(self) -> tuple[Piece, ...]:
        return self.order[self.index:] + self.acted

    def advance(self, next_round: Callable[[], tuple[Piece, ...]] | None = None,
                *, restart_round: bool = False) -> tuple[Piece, ...]:
        if not any(piece.current_hp > 0 for piece in self.order):
            return ()
        skipped = []
        if restart_round:
            self.index = len(self.order) - 1
        while True:
            self.index += 1
            if self.index == len(self.order):
                self.index = 0
                self.round += 1
                if next_round is not None:
                    order = next_round()
                    if not order:
                        return tuple(skipped)
                    self.order = order
            piece = self.current
            if piece.current_hp == 0:
                continue
            if piece.stunned:
                piece.stunned = False
                skipped.append(piece)
            else:
                return tuple(skipped)

