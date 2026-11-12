"""선택·배치 화면과 입력 영역. 실제 선택/배치 유효성은 컨트롤러가 판정한다."""

from time import monotonic

from battle_view import BattleView
from battle_help import BattleHelp
from cards import Suit
from character_data import CHARACTERS
from game_controller import GameController, Stage
from piece import Team
from prototype import ActionMode, Prototype


class GameView(BattleView):
    roster_confirm_button = (1360, 338, 1684, 399)
    deployment_confirm_button = (1360, 187, 1726, 249)
    back_button = (1360, 110, 1726, 172)

    def __init__(self, controller: GameController):
        super().__init__()
        self.controller = controller
        self.help_overlay: BattleHelp | None = None

    @staticmethod
    def character_bounds(index):
        x = 94 + (index % 3) * 398
        y = 539 - (index // 3) * 350
        return x, y, x + 376, y + 328

    @staticmethod
    def deployment_slot_bounds(index):
        x = 94 + index * 409
        return x, 905, x + 392, 964

    @classmethod
    def hit(cls, bounds, x, screen_y):
        left, bottom, right, top = bounds
        return left <= x <= right and bottom <= cls.height - 1 - screen_y <= top

    @property
    def ai_turn(self) -> bool:
        ai, battle = self.controller.ai, self.controller.battle
        return ai is not None and battle is not None and ai.owns_turn(battle)

    def update(self) -> None:
        if self.help_overlay is not None:
            return
        if self.controller.stage is Stage.MOVEMENT:
            battle = self.controller.battle
            if self.initiative_revealing(battle) or self.card_revealing(battle):
                return
            if battle.redraw_pending:
                battle.resolve_redraw()
            elif self.controller.ai is not None:
                self.controller.ai.update(battle, monotonic())

    def click(self, x, screen_y) -> None:
        controller = self.controller
        if controller.stage is Stage.MOVEMENT:
            battle = controller.battle
            if self.initiative_revealing(battle):
                return
            if self.help_overlay is not None:
                if self.hit(self.help_overlay.close_button, x, screen_y):
                    self.help_overlay = None
                else:
                    self.help_overlay.select_at(x, self.height - 1 - screen_y)
                return
            if self.hit(self.help_button, x, screen_y):
                self.help_overlay = BattleHelp(battle.board, battle.current, self.width, self.height)
                self.hover = None
                self.passive_hovered = False
                return
            if battle.revival_pending is not None:
                if self.controller.ai is not None and battle.revival_pending.team is Team.RED:
                    return
                for slot, suit in enumerate(Suit):
                    if self.hit(self.revival_card_bounds(slot), x, screen_y):
                        battle.choose_revival_card(suit)
                        break
                return
            if battle.is_over or self.ai_turn or self.card_revealing(battle):
                return
            if self.action_panel_progress(battle) < 1:
                return
            cell = self.cell_at_pixel(x, screen_y)
            if self.hit(self.pass_button, x, screen_y):
                battle.skip_turn()
                return
            if battle.action_mode is None:
                if self.hit(self.attack_button, x, screen_y):
                    battle.open_attack()
                elif self.hit(self.move_button, x, screen_y):
                    battle.open_movement()
                return
            if self.hit(self.action_back_button, x, screen_y):
                battle.back_to_actions()
                return
            if battle.action_mode is ActionMode.ATTACK:
                if battle.card_target_pending and cell is not None:
                    battle.choose_card_target(cell)
                    return
                for slot in range(len(battle.skills)):
                    if self.hit(self.skill_bounds(slot), x, screen_y):
                        battle.click_skill(slot)
                        return
            if battle.move_preview and cell is not None:
                battle.try_move(cell)
            return
        if controller.stage is Stage.SELECTION:
            if self.hit(self.roster_confirm_button, x, screen_y):
                controller.confirm()
                return
            for index, character in enumerate(CHARACTERS):
                if self.hit(self.character_bounds(index), x, screen_y):
                    controller.select_character(character.identifier)
                    break
            return
        if self.hit(self.deployment_confirm_button, x, screen_y):
            controller.confirm()
            return
        if self.hit(self.back_button, x, screen_y):
            controller.back_to_selection()
            return
        for index in range(4):
            if self.hit(self.deployment_slot_bounds(index), x, screen_y):
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
            difficulty = self.controller.ai.policy.label if self.ai_turn else None
            super().draw(ai_difficulty=difficulty)
            if self.help_overlay is not None:
                self.help_overlay.draw(self)
            return
        self.rectangle((0, 0, self.width - 1, self.height - 1), self.background)
        self.label(94, 1020, "전략 RPG 체스", 32)
        self.label(1360, 1020, "선택 → 배치 → 전투", 22, self.accent)
        if self.controller.stage is Stage.SELECTION:
            self.draw_selection()
        else:
            self.draw_deployment()
        self.label(94, 134, self.controller.message, 20,
                   self.red if self.controller.failed else self.text)

    def button(self, bounds, title, enabled=True):
        self.rectangle(bounds, (46, 64, 77) if enabled else (31, 39, 49))
        self.rectangle(bounds, self.blue if enabled else (70, 82, 96), False)
        self.centered_label((bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2, title, 20,
                            self.text if enabled else self.muted)

    def draw_selection(self):
        selected = self.controller.roster.selected
        self.label(94, 962, "캐릭터 6종 중 4기 선택 · 선택 순서가 행동 순서가 됩니다", 20, self.muted)
        for index, character in enumerate(CHARACTERS):
            bounds = self.character_bounds(index)
            x, y = bounds[:2]
            chosen = character in selected
            self.rectangle(bounds, (31, 48, 59) if chosen else (27, 35, 46))
            self.rectangle(bounds, self.blue if chosen else (65, 79, 95), False)
            self.label(x + 22, y + 291, character.name, 26)
            self.label(x + 22, y + 252, f"{character.job.value}  /  {self.movement_labels[character.job]}", 18, self.muted)
            self.portrait(character, x + 188, y + 145, 184, 180)
            self.label(x + 22, y + 31, "선택 해제" if chosen else "클릭하여 선택", 18,
                       self.blue if chosen else self.muted)
            self.label(x + 271, y + 31, f"체력 {character.max_hp}", 18, self.text)
            if chosen:
                self.label(x + 314, y + 291, f"{selected.index(character) + 1:02}", 26, self.accent)
        self.label(1360, 847, "선택한 순서", 22, self.muted)
        self.label(1603, 847, f"{len(selected)} / 4", 26, self.accent)
        for index in range(4):
            y = 756 - index * 96
            self.rectangle((1360, y - 36, 1684, y + 38), (27, 35, 46))
            character = selected[index] if index < len(selected) else None
            self.label(1380, y + 12, f"{index + 1:02}  {character.name if character else '선택 대기'}", 22,
                       self.text if character else self.muted)
            if character:
                self.label(1380, y - 16, character.job.value, 16, self.blue)
        self.button(self.roster_confirm_button, "배치하기  /  Enter", self.controller.roster.ready)
        self.label(1360, 299, "캐릭터 중복 선택 불가", 16, self.muted)
        self.label(1360, 268, "같은 직업의 다른 캐릭터 허용", 16, self.muted)
        self.label(94, 52, "클릭  선택·해제     Enter  배치 화면으로     Esc  종료", 16, self.muted)

    def draw_deployment(self):
        deployment = self.controller.deployment
        self.label(94, 986, "왼쪽 진영에 4기 배치 · 상단 기물이나 배치된 기물을 눌러 위치 수정", 20, self.muted)
        for index, character in enumerate(deployment.selected):
            bounds = self.deployment_slot_bounds(index)
            x = bounds[0]
            active = index == deployment.active_index
            self.rectangle(bounds, (36, 47, 60) if active else (26, 34, 45))
            self.rectangle(bounds, self.accent if active else (65, 79, 95), False)
            self.label(x + 18, 934, f"청{index + 1} {character.name}", 22, self.blue)
            cell = deployment.positions[index]
            self.label(x + 285, 934, Prototype.cell_name(cell) if cell is not None else "미배치", 18, self.muted)
        board = deployment.board
        current = next((p for p in board.pieces if p.identifier == f"청{deployment.active_index + 1}"), None)
        self.draw_board(board=board, current=current, area_action="배치")
        character = deployment.selected[deployment.active_index]
        self.portrait(character, 169, 203, 136, 126)
        self.label(258, 241, f"청{deployment.active_index + 1} {character.name}", 22, self.blue)
        self.label(258, 204, f"{character.job.value}  /  {self.movement_labels[character.job]}", 18)
        self.label(258, 170, f"배치 완료  {len(deployment.players)} / 4", 18, self.accent)
        self.draw_action_button(self.deployment_confirm_button, "전투 시작  /  Enter", self.blue, 22, deployment.ready)
        self.draw_action_button(self.back_button, "캐릭터 선택으로", self.muted, 20)
        self.label(896, 225, "상대 고정 편성", 18, self.red)
        self.label(896, 187, "슬레이어 · 워리어 · 아처 · 암살자", 18, self.muted)
        self.label(94, 52, "클릭  기물 선택·배치     Enter  4기 배치 후 전투 시작     Esc  종료", 16, self.muted)
