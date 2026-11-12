"""일반전과 최종전의 공통 선후공 판정."""

from dataclasses import dataclass
from random import randint

from piece import Team


@dataclass(frozen=True)
class InitiativeRoll:
    attempts: tuple[tuple[int, int], ...]

    @property
    def values(self) -> tuple[int, int]:
        return self.attempts[-1]

    @property
    def first_team(self) -> Team:
        blue, red = self.values
        return Team.BLUE if blue > red else Team.RED


def roll_initiative() -> InitiativeRoll:
    attempts = []
    while True:
        blue, red = randint(1, 6), randint(1, 6)
        attempts.append((blue, red))
        if blue != red:
            return InitiativeRoll(tuple(attempts))
