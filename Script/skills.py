"""PPT 공격 도식에서 옮긴 시전자 기준 스킬 범위와 효과."""

from dataclasses import dataclass
from enum import Enum

from board import Board
from piece import Piece, Team

Cell = tuple[int, int]


class Effect(Enum):
    DAMAGE = "범위 내 적 타격"
    PULL = "적을 가로 1칸 끌기"
    STUN = "적의 다음 차례를 건너뜀"
    RETREAT = "사용 후 뒤로 1칸"
    MARK = "표식 1개"
    RANDOM_MARK = "정면 무작위 · 표식 +1 · 아군 포함"
    EMPOWER = "다음 공격 적중 시 표식 +1"
    HEAL_ALLIES = "인접 아군 최대 HP 10% 회복"
    HEAL_STRIKE = "자신 최대 HP 10% 회복 · 인접 적 타격"
    SWAP = "자기 진영의 아군과 위치 교환"
    TELEPORT = "자기 진영의 빈 칸으로 이동"
    REDRAW = "다시 뽑고 카드 던지기 발동"
    MAGIC_BOX = "적 턴마다 전진 · 피해 +10"


@dataclass(frozen=True)
class Skill:
    name: str
    damage: int
    offsets: tuple[Cell, ...]
    effect: Effect = Effect.DAMAGE

    def cells(self, board: Board, caster: Piece) -> tuple[Cell, ...]:
        x, y = caster.position
        if self.effect is Effect.SWAP:
            return tuple(piece.position for piece in board.living_pieces
                         if piece is not caster and piece.team is caster.team
                         and board.in_territory(caster.team, piece.position))
        if self.effect is Effect.TELEPORT:
            return tuple((column, row) for row in range(board.rows) for column in range(board.columns)
                         if board.in_territory(caster.team, (column, row))
                         and board.piece_at((column, row)) is None)
        if self.effect is Effect.MAGIC_BOX:
            boundary = board.columns // 2
            return ((boundary if caster.team is Team.BLUE else boundary - 1, y),)
        forward = 1 if caster.team is Team.BLUE else -1
        if self.effect is Effect.RANDOM_MARK:
            edge = board.columns if forward == 1 else -1
            return tuple((column, y) for column in range(x + forward, edge, forward))
        candidates = ((x + distance * forward, y + row) for distance, row in self.offsets)
        return tuple(cell for cell in candidates if board.contains(cell))


def pattern(*rows: tuple[int, ...]) -> tuple[Cell, ...]:
    """각 행은 (시전자 기준 행 차이, 전방 거리, …)로 적는다."""
    return tuple((distance, row) for row, *distances in rows for distance in distances)


SWING = Skill("휘두르기", 25, pattern((-1, 1), (0, 1), (1, 1)))
THRUST = Skill("찌르기", 20, pattern((0, 1, 2)))
CRUSH = Skill("내려치기", 15, pattern((0, 1, 2), (1, 1, 2)))
SWEEP = Skill("쓸어담기", 10, pattern((-1, 2), (0, 2), (1, 2)), Effect.PULL)
# 원거리 도식의 형태를 유지하고 Q05의 빈칸 2칸 기준에 맞춰 한 칸 당겼다.
BACKSHOT = Skill("백샷", 25, pattern((-1, 4), (0, 5), (1, 4)), Effect.RETREAT)
MULTISHOT = Skill("멀티샷", 30, pattern((-1, 5), (0, 5), (1, 5)))
LIGHTNING = Skill("라이트닝", 10, pattern((-1, 4), (0, 3, 5), (1, 4)), Effect.STUN)
FIREBALL = Skill("파이어볼", 25, pattern((0, 4, 5), (1, 4, 5)))
ASSASSIN_STRIKE = Skill("암격", 10, pattern((0, 4)), Effect.MARK)
ASSASSIN_FLURRY = Skill("난도", 10, (), Effect.RANDOM_MARK)


# 일반형과 영웅형은 버튼 순서를 공유한다. 마지막 버튼은 영웅 스킬이다.
SKILLS = {
    "slayer": (
        (SWING, THRUST),
        (
            Skill("휘두르기", 35, pattern((-1, 1), (0, 1, 2), (1, 1, 2), (2, 1))),
            Skill("찌르기", 30, pattern((-1, 1), (0, 1, 2, 3), (1, 1))),
        ),
        Skill("대검격", 50, pattern((-1, 2, 3), (0, 2, 3), (1, 2, 3), (2, 2, 3))),
    ),
    "warrior": (
        (CRUSH, SWEEP),
        (
            Skill("내려치기", 25, pattern((-1, 3), (0, 2, 3), (1, 2, 3), (2, 3))),
            Skill("쓸어담기", 20, pattern((-1, 2), (0, 3), (1, 3), (2, 2)), Effect.PULL),
        ),
        Skill("파쇄 일격", 50, pattern((-1, 1, 3), (0, 2), (1, 1, 3)), Effect.STUN),
    ),
    "archer": (
        (BACKSHOT, MULTISHOT),
        (
            Skill("백샷", 35, pattern((-1, 4), (0, 4, 5), (1, 4, 5), (2, 4)), Effect.RETREAT),
            Skill("멀티샷", 40, pattern((-1, 5), (0, 3, 5), (1, 3, 5), (2, 5))),
        ),
        Skill("화살비", 60, pattern((-1, 4, 6), (0, 5), (1, 4, 6), (2, 5))),
    ),
    "mage": (
        (LIGHTNING, FIREBALL),
        (
            Skill("라이트닝", 20, pattern((-1, 3, 4, 5), (0, 3, 5), (1, 3, 4, 5)), Effect.STUN),
            Skill("파이어볼", 35, pattern((-1, 4), (0, 3, 4, 5), (1, 4), (2, 4))),
        ),
        Skill("드래곤 브래스", 50, pattern((0, 3, 4, 5, 6), (1, 3, 4, 5, 6))),
    ),
    "assassin": (
        (ASSASSIN_STRIKE, ASSASSIN_FLURRY),
        (ASSASSIN_STRIKE, ASSASSIN_FLURRY),
        Skill("암살 비기", 0, ((0, 0),), Effect.EMPOWER),
    ),
}
