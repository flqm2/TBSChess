"""카드술사의 네 문양과 카드 던지기 효과."""

from dataclasses import dataclass
from enum import Enum

from piece import Job, Piece, Team
from skills import Cell, Effect, Skill, pattern


class Suit(Enum):
    HEART = ("heart", "하트")
    CLUB = ("club", "클로버")
    SPADE = ("spade", "스페이드")
    DIAMOND = ("diamond", "다이아")

    def __init__(self, slug: str, label: str):
        self.slug = slug
        self.label = label


@dataclass(frozen=True)
class CardDraw:
    suit: Suit
    redraw: bool = False


@dataclass
class MagicBox:
    owner: Piece
    cell: Cell
    damage: int

    def next_cell(self) -> Cell:
        x, y = self.cell
        return x + (1 if self.owner.team is Team.BLUE else -1), y


THROW = "카드 던지기"
CARD_SKILLS = {
    Suit.HEART: (
        Skill(THROW, 0, Job.JOKER.directions, Effect.HEAL_ALLIES),
        Skill(THROW, 40, Job.JOKER.directions, Effect.HEAL_STRIKE),
    ),
    Suit.CLUB: (Skill(THROW, 0, (), Effect.SWAP), Skill(THROW, 0, (), Effect.TELEPORT)),
    Suit.SPADE: (Skill(THROW, 25, pattern((0, 2, 4))), Skill(THROW, 35, pattern((0, 2, 4)))),
    Suit.DIAMOND: (
        Skill(THROW, 20, pattern((0, 4)), Effect.STUN),
        Skill(THROW, 30, pattern((0, 4)), Effect.STUN),
    ),
}
REDRAW = Skill("카드 뽑기", 0, ((0, 0),), Effect.REDRAW)
MAGIC_BOX = Skill("마법사의 상자", 20, (), Effect.MAGIC_BOX)
TARGETED_EFFECTS = (Effect.SWAP, Effect.TELEPORT)
