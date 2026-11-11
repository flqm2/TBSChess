"""프로토타입 기물 데이터. 화면과 관계없이 보드 좌표로 위치를 저장한다."""

from dataclasses import dataclass, field
from enum import Enum


class Team(Enum):
    BLUE = "청팀"
    RED = "홍팀"


class Job(Enum):
    MELEE = "근거리"
    RANGED = "원거리"
    JOKER = "조커"

    @property
    def directions(self) -> tuple[tuple[int, int], ...]:
        orthogonal = ((0, -1), (1, 0), (0, 1), (-1, 0))
        diagonal = ((-1, -1), (1, -1), (1, 1), (-1, 1))
        if self is Job.MELEE:
            return orthogonal
        if self is Job.RANGED:
            return diagonal
        return orthogonal + diagonal


@dataclass
class Piece:
    identifier: str
    name: str
    team: Team
    job: Job
    image_name: str
    position: tuple[int, int]
    max_hp: int
    character_id: str = ""
    current_hp: int = field(init=False)
    hero: bool = field(default=False, init=False)
    hero_skill_round: int | None = field(default=None, init=False)
    stunned_round: int = field(default=0, init=False)
    marks: dict[str, int] = field(default_factory=dict, init=False)
    empowered_mark: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.max_hp <= 0:
            raise ValueError("최대 체력은 0보다 커야 합니다.")
        self.current_hp = self.max_hp

