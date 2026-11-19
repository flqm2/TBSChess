"""실제 전투 렌더러로 기물의 동작을 한 번씩 재생하는 테스트 화면."""

from time import monotonic

from pico2d import pico2d

from battle_view import BattleView
from cards import CardDraw, Suit
from character_animation import CLIPS, attack_frame
from character_data import CHARACTERS, CHARACTER_BY_ID
from piece import Job, Team
from prototype import Hit, Prototype, SkillCast
from turn_manager import TurnManager


SHEET_NAMES = {
    "idle": "IDLE", "idle_empowered": "IDLE_강화", "active": "스킬1_2",
    "skill1": "스킬1", "skill2": "스킬2", "hero": "영웅스킬",
    "passive": "패시브_회복", "hit": "피격", "stun": "피격_기절", "death": "사망",
}


class AnimationTestView(BattleView):
    controls = ("스킬 1", "스킬 2", "영웅 스킬", "기절", "기절 해제", "사망", "초기화")

    def __init__(self):
        super().__init__()
        self.selected = CHARACTERS[0]
        self.reset()

    def reset(self, *, hero=False, empowered=False) -> None:
        column = 2 if self.selected.job is Job.RANGED else 3
        self.subject = self.selected.create_piece(Team.BLUE, 1, (column, 1))
        self.subject.hero = hero
        self.subject.empowered_mark = empowered
        ally = CHARACTER_BY_ID["assassin"].create_piece(Team.BLUE, 2, (column - 1, 2))
        ally.current_hp //= 2
        targets = tuple(CHARACTER_BY_ID["archer"].create_piece(Team.RED, number, (x, 1))
                        for number, x in enumerate(range(4, 8), 1))
        pieces = (self.subject, ally, *targets)
        self.game = Prototype(pieces, animate_skills=True)
        self.game.turns = TurnManager(pieces)
        self.game.card_draw = CardDraw(Suit.SPADE) if self.selected.identifier == "cardmaster" else None
        self.status = "대기"

    def play_skill(self, slot: int) -> None:
        self.reset(hero=slot == 2, empowered=self.subject.empowered_mark)
        self.status = self.game.skills[slot].name
        self.game.open_attack()
        self.game.click_skill(slot)
        self.game.click_skill(slot)
        self.choose_card_target()

    def apply_stun(self) -> None:
        self.reset(empowered=self.subject.empowered_mark)
        self.subject.stunned = True
        self.subject.current_hp -= 10
        hit = Hit(self.subject.identifier, self.subject.position, 10, stun_applied=True)
        self.game.last_cast = SkillCast((self.subject.position,), (hit,))
        self.status = "기절"
        self._sync_combat(self.game, monotonic())

    def release_stun(self) -> None:
        if self.subject.stunned:
            self.subject.stunned = False
            self.status = "기절 해제"
            self._sync_combat(self.game, monotonic())

    def apply_death(self) -> None:
        self.reset()
        hit = Hit(self.subject.identifier, self.subject.position, self.subject.current_hp)
        self.subject.current_hp = 0
        self.game.last_cast = SkillCast((self.subject.position,), (hit,))
        self.status = "사망"
        self._sync_combat(self.game, monotonic())

    def choose_card_target(self) -> None:
        if self.game.pending_skill is None and self.game.card_target_pending:
            self.game.choose_card_target(self.game.skill_preview[0])

    def update(self) -> None:
        self.update_combat(self.game)
        if self.game.redraw_pending and not self.card_revealing(self.game):
            self.game.resolve_redraw()
            self.choose_card_target()

    @staticmethod
    def button_bounds(index, bottom, top, columns=6):
        step = 1740 // columns
        left = 96 + index * step
        return left, bottom, left + step - 12, top

    def click(self, x, screen_y) -> None:
        y = self.height - 1 - screen_y
        for index, character in enumerate(CHARACTERS):
            left, bottom, right, top = self.button_bounds(index, 934, 1016)
            if left <= x <= right and bottom <= y <= top:
                self.selected = character
                self.reset()
                return

        actions = (lambda: self.play_skill(0), lambda: self.play_skill(1), lambda: self.play_skill(2),
                   self.apply_stun, self.release_stun, self.apply_death, self.reset)
        for index, action in enumerate(actions):
            left, bottom, right, top = self.button_bounds(index, 70, 153, len(self.controls))
            if left <= x <= right and bottom <= y <= top:
                action()
                return

    def handle_event(self, event) -> bool:
        if event.type == pico2d.SDL_QUIT or (
                event.type == pico2d.SDL_KEYDOWN and event.key == pico2d.SDLK_ESCAPE):
            return False
        if event.type == pico2d.SDL_MOUSEBUTTONDOWN and event.button == pico2d.SDL_BUTTON_LEFT:
            self.click(event.x, event.y)
        return True

    @property
    def skill_card(self):
        return 1707, 603, 80, 112

    def draw(self) -> None:
        self.draw_scene(913, 244)
        now = self.death_presentation.time_at(monotonic())
        self.label(96, 1048, "전투 애니메이션 테스트", 32)
        for index, character in enumerate(CHARACTERS):
            left, bottom, right, top = bounds = self.button_bounds(index, 934, 1016)
            color = self.accent if character is self.selected else self.muted
            self.rectangle(bounds, (31, 43, 57))
            self.rectangle(bounds, color, False)
            self.portrait(character, left + 58, (bottom + top) // 2, 74, 76)
            self.label(left + 110, (bottom + top) // 2, character.name, 26, color)

        self.label(96, 202, self.selected.name, 26, self.accent)
        status = self.status
        if self.game.pending_skill is not None:
            pose = attack_frame(self.subject.character_id, self.game.pending_skill.slot,
                                self.attack_elapsed(now))
        else:
            pose = self.character_animations.frame(self.subject, now)
        if pose is not None:
            name, frame = pose
            frames = CLIPS[self.subject.character_id][name].frames
            status = f"{status}  ·  {SHEET_NAMES[name]}  {frame + 1}/{frames}"
        self.label(305, 202, status, 22, self.text)
        for index, title in enumerate(self.controls):
            enabled = index != 4 or self.subject.stunned
            bounds = self.button_bounds(index, 70, 153, len(self.controls))
            self.draw_action_button(bounds, title, self.accent if index in (3, 4, 5) else self.blue,
                                    26, enabled)
        self.label(96, 32, "기절은 해제 버튼을 누를 때까지 유지됩니다.", 18, self.muted)
        if self.game.redraw_pending and self.card_revealing(self.game):
            self.draw_card_reveal()
