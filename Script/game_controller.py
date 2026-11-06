"""캐릭터 선택 → 수동 배치 → 기존 이동 검증의 화면 상태 전환."""

from enum import Enum

from deployment import Deployment
from prototype import Prototype
from roster import RosterSelection


class Stage(Enum):
    SELECTION = "캐릭터 선택"
    DEPLOYMENT = "기물 배치"
    MOVEMENT = "이동 검증"


class GameController:
    def __init__(self):
        self.stage = Stage.SELECTION
        self.roster = RosterSelection()
        self.deployment: Deployment | None = None
        self.battle: Prototype | None = None
        self.message = "캐릭터 6종 중 함께할 4기를 선택하세요."
        self.failed = False

    def select_character(self, identifier: str) -> None:
        if self.stage is not Stage.SELECTION:
            return
        try:
            self.roster.toggle(identifier)
        except ValueError as error:
            self.message, self.failed = str(error), True
            return
        self.message = ("4기를 선택했습니다. 배치하기를 누르세요." if self.roster.ready
                        else f"선택 {len(self.roster.selected)}/4 · 캐릭터를 다시 클릭하면 해제됩니다.")
        self.failed = False

    def confirm(self) -> None:
        if self.stage is Stage.SELECTION:
            if not self.roster.ready:
                self.message, self.failed = "캐릭터 4기를 모두 선택하세요.", True
                return
            self.deployment = Deployment(self.roster.selected)
            self.stage = Stage.DEPLOYMENT
            self.message = "청1 기물을 배치할 왼쪽 진영의 빈 칸을 클릭하세요."
        elif self.stage is Stage.DEPLOYMENT:
            if not self.deployment.ready:
                self.message, self.failed = "선택한 4기를 모두 배치해야 시작할 수 있습니다.", True
                return
            self.battle = Prototype((*self.deployment.players, *self.deployment.enemies))
            self.stage = Stage.MOVEMENT
        self.failed = False

    def back_to_selection(self) -> None:
        if self.stage is Stage.DEPLOYMENT:
            self.stage = Stage.SELECTION
            self.deployment = None
            self.message = "편성을 수정할 수 있습니다. 배치 위치는 다시 지정하세요."
            self.failed = False

    def select_slot(self, index: int) -> None:
        if self.stage is not Stage.DEPLOYMENT:
            return
        try:
            self.deployment.select_slot(index)
        except ValueError as error:
            self.message, self.failed = str(error), True
            return
        self.message = f"청{index + 1} {self.deployment.selected[index].name}의 배치 칸을 선택하세요."
        self.failed = False

    def place(self, cell: tuple[int, int] | None) -> None:
        if self.stage is not Stage.DEPLOYMENT:
            return
        try:
            self.deployment.place(cell)
        except ValueError as error:
            self.message, self.failed = str(error), True
            return
        self.message = ("4기 배치 완료. 위치를 수정하거나 이동 시작을 누르세요."
                        if self.deployment.ready else
                        f"다음은 청{self.deployment.active_index + 1} 기물입니다. 빈 칸을 클릭하세요.")
        self.failed = False
