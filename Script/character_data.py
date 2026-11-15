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
    CharacterDefinition("slayer", "슬레이어", Job.MELEE, "남색 망토의 대검 슬레이어-1.png", 150),
    CharacterDefinition("warrior", "워리어", Job.MELEE, "푸른 방패의 수호 기사-3.png", 200),
    CharacterDefinition("archer", "아처", Job.RANGED, "초록 망토의 숲 궁수-4.png", 130),
    CharacterDefinition("mage", "메이지", Job.RANGED, "은발의 푸른 마도사-6.png", 150),
    CharacterDefinition("assassin", "암살자", Job.JOKER, "고요한 쌍단검 암살자-2.png", 100),
    CharacterDefinition("cardmaster", "카드술사", Job.JOKER, "라벤더 카드를 든 마법사-5.png", 130),
)
CHARACTER_BY_ID = {character.identifier: character for character in CHARACTERS}
