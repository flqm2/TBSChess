"""선택·배치 화면과 입력 영역. 실제 선택/배치 유효성은 컨트롤러가 판정한다."""

from battle_view import BattleView
from character_data import CHARACTERS
from game_controller import GameController, Stage
from piece import Team
from prototype import ActionMode, Prototype


class GameView(BattleView):
    back_button = (840, 184, 1072, 224)

    def __init__(self, controller: GameController):
        super().__init__()
        self.controller = controller

    @staticmethod
    def character_bounds(index):
        x = 40 + (index % 3) * 260
        y = 442 - (index // 3) * 248
        return x, y, x + 244, y + 238

    @classmethod
    def hit(cls, bounds, x, screen_y):
        left, bottom, right, top = bounds
        return left <= x <= right and bottom <= cls.height - 1 - screen_y <= top

    def update(self) -> None:
        if self.controller.stage is Stage.MOVEMENT:
            battle = self.controller.battle
            if not self.card_revealing(battle):
                battle.resolve_redraw()

    def click(self, x, screen_y) -> None:
        controller = self.controller
        if controller.stage is Stage.MOVEMENT:
            battle = controller.battle
            if battle.winner is not None or self.card_revealing(battle):
                return
            cell = self.cell_at_pixel(x, screen_y)
            if battle.card_target_pending and cell is not None:
                battle.choose_card_target(cell)
                return
            if self.hit(self.attack_button, x, screen_y):
                battle.open_attack()
                return
            if self.hit(self.move_button, x, screen_y):
                battle.open_movement()
                return
            if self.hit(self.pass_button, x, screen_y):
                battle.skip_turn()
                return
            if battle.action_mode is ActionMode.ATTACK:
                for slot in range(len(battle.skills)):
                    if self.hit(self.skill_bounds(slot), x, screen_y):
                        battle.click_skill(slot)
                        return
            if battle.move_preview and cell is not None:
                battle.try_move(cell)
            return
        if self.skip_at_pixel(x, screen_y):
            controller.confirm()
            return
        if controller.stage is Stage.SELECTION:
            for index, character in enumerate(CHARACTERS):
                if self.hit(self.character_bounds(index), x, screen_y):
                    controller.select_character(character.identifier)
                    break
            return
        if self.hit(self.back_button, x, screen_y):
            controller.back_to_selection()
            return
        for index in range(4):
            if self.hit((40 + index * 260, 635, 290 + index * 260, 680), x, screen_y):
                controller.select_slot(index)
                return
        cell = self.cell_at_pixel(x, screen_y)
        occupant = controller.deployment.board.piece_at(cell) if cell is not None else None
        if occupant is not None and occupant.team is Team.BLUE:
            controller.select_slot(int(occupant.identifier[1:]) - 1)
        else:
            controller.place(cell)

    def draw(self) -> None:
        if self.controller.stage is Stage.MOVEMENT:
            self.game = self.controller.battle
            super().draw()
            return
        self.rectangle((0, 0, self.width - 1, self.height - 1), self.background)
        self.label(40, 735, "전략 RPG 체스", 30)
        self.label(850, 735, "선택 → 배치 → 전투", 18, self.accent)
        if self.controller.stage is Stage.SELECTION:
            self.draw_selection()
        else:
            self.draw_deployment()
        self.label(40, 153, self.controller.message, 18,
                   self.red if self.controller.failed else self.text)

    def portrait(self, character, x, y, max_width, max_height):
        image = self.images[character.image_name]
        scale = min(max_width / image.w, max_height / image.h)
        image.draw(x, y, image.w * scale, image.h * scale)

    def button(self, bounds, title, enabled=True):
        self.rectangle(bounds, (46, 64, 77) if enabled else (31, 39, 49))
        self.rectangle(bounds, self.blue if enabled else (70, 82, 96), False)
        self.label(bounds[0] + 16, (bounds[1] + bounds[3]) // 2, title, 16,
                   self.text if enabled else self.muted)

    def draw_selection(self):
        selected = self.controller.roster.selected
        self.label(40, 700, "01 / 캐릭터 6종 중 4기 선택 · 선택 순서가 행동 순서가 됩니다", 16, self.muted)
        for index, character in enumerate(CHARACTERS):
            bounds = self.character_bounds(index)
            x, y = bounds[:2]
            chosen = character in selected
            self.rectangle(bounds, (31, 48, 59) if chosen else (27, 35, 46))
            self.rectangle(bounds, self.blue if chosen else (65, 79, 95), False)
            self.label(x + 16, y + 210, character.name, 22)
            self.label(x + 16, y + 181, f"{character.job.value}  /  {self.movement_labels[character.job]}", 14, self.muted)
            self.portrait(character, x + 122, y + 101, 122, 126)
            self.label(x + 16, y + 23, "선택 해제" if chosen else "클릭하여 선택", 14,
                       self.blue if chosen else self.muted)
            self.label(x + 160, y + 23, f"체력 {character.max_hp}", 14, self.text)
            if chosen:
                self.label(x + 191, y + 210, f"{selected.index(character) + 1:02}", 22, self.accent)
        self.label(840, 658, "선택한 순서", 18, self.muted)
        self.label(840, 624, f"{len(selected)} / 4", 22, self.accent)
        for index in range(4):
            y = 568 - index * 78
            self.rectangle((840, y - 27, 1072, y + 33), (27, 35, 46))
            character = selected[index] if index < len(selected) else None
            self.label(854, y + 10, f"{index + 1:02}  {character.name if character else '선택 대기'}", 18,
                       self.text if character else self.muted)
            if character:
                self.label(854, y - 14, character.job.value, 14, self.blue)
        self.button(self.skip_button, "배치하기  /  Enter", self.controller.roster.ready)
        self.label(840, 218, "캐릭터 중복 선택 불가", 14, self.muted)
        self.label(840, 193, "같은 직업의 다른 캐릭터 허용", 14, self.muted)
        self.label(40, 20, "클릭  선택·해제     Enter  배치 화면으로     Esc  종료", 14, self.muted)

    def draw_deployment(self):
        deployment = self.controller.deployment
        self.label(40, 700, "02 / 왼쪽 진영에 4기 배치 · 상단 기물이나 배치된 기물을 눌러 위치 수정", 16, self.muted)
        for index, character in enumerate(deployment.selected):
            x = 40 + index * 260
            active = index == deployment.active_index
            self.rectangle((x, 635, x + 250, 680), (36, 47, 60) if active else (26, 34, 45))
            self.rectangle((x, 635, x + 250, 680), self.accent if active else (65, 79, 95), False)
            self.label(x + 12, 657, f"청{index + 1} {character.name}", 16, self.blue)
            cell = deployment.positions[index]
            self.label(x + 174, 657, Prototype.cell_name(cell) if cell is not None else "미배치", 14, self.muted)
        board = deployment.board
        current = next((p for p in board.pieces if p.identifier == f"청{deployment.active_index + 1}"), None)
        self.draw_board(board=board, current=current, area_action="배치")
        character = deployment.selected[deployment.active_index]
        self.label(840, 587, "배치할 기물", 14, self.muted)
        self.label(840, 553, f"청{deployment.active_index + 1} {character.name}", 22, self.blue)
        self.portrait(character, 956, 462, 132, 136)
        self.label(840, 373, f"{character.job.value}  /  {self.movement_labels[character.job]}", 16)
        self.label(840, 342, f"배치 완료  {len(deployment.players)} / 4", 18, self.accent)
        self.label(840, 315, "A~D열의 빈 칸을 클릭하세요.", 14, self.muted)
        self.button(self.skip_button, "전투 시작  /  Enter", deployment.ready)
        self.button(self.back_button, "캐릭터 선택으로")
        self.label(840, 145, "상대 고정 편성", 16, self.red)
        self.label(840, 119, "슬레이어 · 워리어 · 아처 · 암살자", 14, self.muted)
        self.label(840, 94, "근거리 2 / 원거리 1 / 조커 1", 14, self.muted)
        self.label(40, 20, "클릭  기물 선택·배치     Enter  4기 배치 후 전투 시작     Esc  종료", 14, self.muted)
