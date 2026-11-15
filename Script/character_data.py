"""6종 캐릭터의 공통 정의. 경기 기물은 같은 정의로 생성한다."""

from dataclasses import dataclass

from piece import Job, Piece, Team


@dataclass(frozen=True)
class CharacterDefinition:
    identifier: str
    name: str
    job: Job
    image_name: str
    max_hp: int

    def create_piece(self, team: Team, number: int, position: tuple[int, int]) -> Piece:
        prefix = "청" if team is Team.BLUE else "홍"
        return Piece(f"{prefix}{number}", self.name, team, self.job, self.image_name,
                     position, self.max_hp, character_id=self.identifier)


CHARACTERS = (
    CharacterDefinition("slayer", "슬레이어", Job.MELEE, "sd-slayer.png", 150),
    CharacterDefinition("warrior", "워리어", Job.MELEE, "sd-warrior.png", 200),
    CharacterDefinition("archer", "아처", Job.RANGED, "sd-archer.png", 130),
    CharacterDefinition("mage", "메이지", Job.RANGED, "sd-mage.png", 150),
    CharacterDefinition("assassin", "암살자", Job.JOKER, "sd-assassin.png", 100),
    CharacterDefinition("cardmaster", "카드술사", Job.JOKER, "sd-cardmaster.png", 130),
)
CHARACTER_BY_ID = {character.identifier: character for character in CHARACTERS}
