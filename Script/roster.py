"""중복 없는 4기 편성과 선택 순서. 화면이나 배치 좌표를 저장하지 않는다."""

from character_data import CHARACTER_BY_ID, CharacterDefinition


class RosterSelection:
    size = 4

    def __init__(self):
        self._identifiers: list[str] = []

    @property
    def selected(self) -> tuple[CharacterDefinition, ...]:
        return tuple(CHARACTER_BY_ID[key] for key in self._identifiers)

    @property
    def ready(self) -> bool:
        return len(self._identifiers) == self.size

    def toggle(self, identifier: str) -> None:
        if identifier not in CHARACTER_BY_ID:
            raise ValueError("목록에 있는 캐릭터를 선택하세요.")
        if identifier in self._identifiers:
            self._identifiers.remove(identifier)
        elif self.ready:
            raise ValueError("4기를 모두 선택했습니다. 해제할 캐릭터를 먼저 클릭하세요.")
        else:
            self._identifiers.append(identifier)
