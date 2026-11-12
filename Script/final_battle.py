"""양측 최후 생존 기물의 라운드 규칙."""

from random import randint

from piece import Piece, Team


class FinalBattleRules:
    def __init__(self, blue: Piece, red: Piece):
        self.pieces = (blue, red)
        self.round = 0
        self.dice: tuple[int, int] | None = None
        self.winner: Team | None = None
        self.drawn = False
        self._stun_round: dict[str, int] = {}

    @property
    def sudden_death(self) -> bool:
        return self.round >= 6

    def start_round(self) -> tuple[tuple[Piece, ...], tuple[tuple[Piece, int], ...]]:
        self.round += 1
        self.dice = None
        damage = ()
        if self.sudden_death:
            previous_hp = tuple(piece.current_hp for piece in self.pieces)
            damage = tuple((piece, min(hp, piece.max_hp // 10))
                           for piece, hp in zip(self.pieces, previous_hp))
            for piece, lost in damage:
                piece.current_hp -= lost
            living = tuple(piece for piece in self.pieces if piece.current_hp > 0)
            if len(living) == 1:
                self.winner = living[0].team
            elif not living:
                blue_hp, red_hp = previous_hp
                if blue_hp == red_hp:
                    self.drawn = True
                else:
                    self.winner = Team.BLUE if blue_hp > red_hp else Team.RED
            if self.winner is not None or self.drawn:
                return (), damage

        blue, red = randint(1, 6), randint(1, 6)
        while blue == red:
            blue, red = randint(1, 6), randint(1, 6)
        self.dice = blue, red
        return (self.pieces if blue > red else self.pieces[::-1]), damage

    def apply_stun(self, piece: Piece) -> bool:
        previous = self._stun_round.get(piece.identifier)
        if previous is not None and self.round == previous + 1:
            return False
        if not piece.stunned:
            piece.stunned = True
            self._stun_round[piece.identifier] = self.round
        return True
