"""pico2d 표시와 화면 좌표 변환. 이동 판정은 Prototype의 공통 규칙을 사용한다."""

import os
from ctypes import byref, c_int
from math import cos, pi, sin, tau
from pathlib import Path
from time import monotonic

import pico2d

from character_data import CHARACTERS
from cards import Suit
from passives import DESCRIPTIONS, aura_cells
from piece import Job, Piece, Team
from portraits import load_grayscale_portrait
from prototype import ActionMode, Prototype


class BattleView:
    width, height = 1920, 1080
    board_x, board_y = 94, 306
    cell_width, cell_height = 204, 135
    action_panel = (460, 89, 1726, 228)
    attack_button = (460, 89, 870, 228)
    move_button = (888, 89, 1298, 228)
    pass_button = (1316, 89, 1726, 228)
    action_back_button = (1498, 89, 1726, 228)
    submenu_pass_button = (1528, 24, 1726, 64)
    menu_card = (796, 159, 52, 73)
    passive_icon = (228, 91, 344, 123)
    background = (19, 25, 34)
    text = (233, 237, 241)
    muted = (151, 166, 183)
    blue = (104, 191, 242)
    red = (244, 143, 141)
    accent = (243, 211, 132)
    card_reveal_seconds = 0.8
    movement_labels = {Job.MELEE: "상하좌우 1칸", Job.RANGED: "대각선 1칸", Job.JOKER: "전 방향 1칸"}

    def __init__(self, game: Prototype | None = None):
        self.game = game
        root = Path(__file__).resolve().parents[1]
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        font = next((p for p in (fonts / "malgun.ttf", fonts / "gulim.ttc") if p.is_file()), None)
        if font is None:
            raise FileNotFoundError("한국어 표시를 위한 맑은 고딕 또는 굴림 글꼴이 필요합니다.")
        self.fonts = {size: pico2d.load_font(str(font), size) for size in (14, 16, 18, 20, 22, 26, 32, 46)}
        self.resource_dir = root / "Resource"
        self.images = {
            character.image_name: pico2d.load_image(str(self.resource_dir / character.image_name))
            for character in CHARACTERS
        }
        self.grayscale_portraits = {}
        card_dir = self.resource_dir / "Cards"
        self.card_faces = {suit: pico2d.load_image(str(card_dir / f"ace_{suit.slug}.png")) for suit in Suit}
        self.card_back = pico2d.load_image(str(card_dir / "back.png"))
        self.help_button = (self.width - 91, 22, self.width - 29, 80)
        self.hover: tuple[int, int] | None = None
        self.passive_hovered = False
        self._shown_cast = None
        self._cast_started = 0.0
        self._shown_draw = None
        self._draw_started = 0.0
        self._shown_action_mode = None
        self._action_changed_at = None
        self._notice_battle = None
        self._notice_index = -1
        self._notice_until = 0.0
        self._stack_order = ()
        self._stack_from = ()
        self._stack_started = 0.0
        self._shown_stun_skips = ()
        self._stun_visible_until = {}

    def point_at(self, x: int, screen_y: int) -> None:
        self.hover = self.cell_at_pixel(x, screen_y)
        left, bottom, right, top = self.passive_icon
        self.passive_hovered = left <= x <= right and bottom <= self.height - 1 - screen_y <= top

    def card_revealing(self, battle: Prototype) -> bool:
        if battle.card_draw is not self._shown_draw:
            self._shown_draw = battle.card_draw
            self._draw_started = monotonic()
        return self._shown_draw is not None and monotonic() - self._draw_started < self.card_reveal_seconds

    @classmethod
    def cell_at_pixel(cls, x: int, screen_y: int) -> tuple[int, int] | None:
        """SDL 왼쪽 위 원점 입력을 보드 왼쪽 위 원점 좌표로 바꾼다."""
        canvas_y = cls.height - 1 - screen_y
        column = (x - cls.board_x) // cls.cell_width
        row_from_bottom = (canvas_y - cls.board_y) // cls.cell_height
        if not (0 <= column < 8 and 0 <= row_from_bottom < 4):
            return None
        return column, 3 - row_from_bottom

    @classmethod
    def cell_center(cls, cell: tuple[int, int]) -> tuple[int, int]:
        return (cls.board_x + cell[0] * cls.cell_width + cls.cell_width // 2,
                cls.board_y + (3 - cell[1]) * cls.cell_height + cls.cell_height // 2)

    @staticmethod
    def rectangle(bounds, color, filled=True):
        pico2d.draw_rectangle(*bounds, *color, filled=filled)

    def label(self, x, y, text, size=16, color=None):
        self.fonts[size].draw(x, y, text, color or self.text)

    def centered_label(self, x, y, text, size=16, color=None):
        width = c_int()
        pico2d.TTF_SizeUTF8(self.fonts[size].font, text.encode("utf-8"), byref(width), None)
        self.label(x - width.value // 2, y, text, size, color)

    def portrait(self, character, x, y, max_width, max_height, grayscale=False):
        name = character.image_name
        if grayscale:
            if name not in self.grayscale_portraits:
                self.grayscale_portraits[name] = load_grayscale_portrait(self.resource_dir / name)
            image = self.grayscale_portraits[name]
        else:
            image = self.images[name]
        scale = min(max_width / image.w, max_height / image.h)
        image.draw(x, y, image.w * scale, image.h * scale)

    def team_color(self, team):
        return self.blue if team is Team.BLUE else self.red

    def draw_health_bar(self, piece: Piece, x: int, y: int, width: int, height: int) -> None:
        top = y + height - 1
        self.rectangle((x, y, x + width - 1, top), (12, 18, 24))
        filled = max(0, min(width, round(width * piece.current_hp / piece.max_hp)))
        if filled:
            self.rectangle((x, y, x + filled - 1, top), self.team_color(piece.team))

    def draw(self) -> None:
        revealing = self.card_revealing(self.game)
        self.rectangle((0, 0, self.width - 1, self.height - 1), self.background)
        self.draw_health_and_round()
        self.draw_turn_order()
        self.draw_board()
        self.draw_details()
        self.draw_actions(revealing)
        self.draw_footer(revealing)
        self.draw_combat_notice()
        self.draw_passive_icon(self.game.current)
        self.draw_action_button(self.help_button, "?", self.blue, 26)
        if self.game.revival_pending is not None:
            self.draw_revival_choices()
        elif revealing:
            self.draw_card_reveal()

    def draw_health_and_round(self) -> None:
        center = self.width // 2
        self.centered_label(center, 1010, "라운드", 22, self.muted)
        self.centered_label(center, 954, f"{self.game.turns.round:02}", 46, self.accent)
        team_left = {Team.BLUE: self.board_x, Team.RED: self.width - self.board_x - 480}
        team_slots = {team: 0 for team in Team}
        for piece in self.game.turns.order:
            left = team_left[piece.team]
            y = 1024 - team_slots[piece.team] * 38
            team_slots[piece.team] += 1
            label_color = self.team_color(piece.team) if piece.current_hp else self.muted
            self.label(left, y, f"{piece.identifier}  {piece.name}", 18, label_color)
            self.draw_health_bar(piece, left + 156, y - 9, 205, 18)
            self.label(left + 374, y, f"{piece.current_hp} / {piece.max_hp}", 16, label_color)

    def draw_turn_order(self) -> None:
        now = monotonic()
        order = self.game.turns.upcoming
        identifiers = tuple(piece.identifier for piece in order)
        if identifiers != self._stack_order:
            previous_slots = {identifier: index for index, identifier in enumerate(self._stack_order)}
            self._stack_from = tuple(previous_slots.get(key, index) for index, key in enumerate(identifiers))
            self._stack_order = identifiers
            self._stack_started = now
        if self.game.last_stun_skips is not self._shown_stun_skips:
            self._shown_stun_skips = self.game.last_stun_skips
            for piece in self._shown_stun_skips:
                self._stun_visible_until[piece.identifier] = now + 1.2

        progress = min(1.0, (now - self._stack_started) / 0.24)
        remaining = (1 - progress) ** 2
        x = (self.board_x + 8 * self.cell_width + self.width) // 2
        step, first_y = 77, 802
        rail = (x - 65, first_y - step * (len(order) - 1) - 44, x + 65, first_y + 44)
        self.rectangle(rail, (23, 31, 41))
        self.rectangle(rail, (65, 79, 95), False)
        # 뒤로 옮긴 초상화를 먼저 그려 아직 위로 이동 중인 기물과 겹치지 않게 한다.
        slots = sorted(range(len(order)), key=lambda index: self._stack_from[index] >= index)
        for index in slots:
            piece = order[index]
            start = self._stack_from[index]
            y = first_y - step * index
            if start >= index:
                y -= round(step * (start - index) * remaining)
            portrait_x = x + round(12 * remaining) if start < index else x
            active = piece is self.game.current and self.game.winner is None
            alive = piece.current_hp > 0
            if active:
                self._stun_visible_until.pop(piece.identifier, None)
            stunned = alive and (piece.stunned or now < self._stun_visible_until.get(piece.identifier, 0))
            self.draw_turn_portrait(piece, portrait_x, y, active, stunned, alive)

    def draw_turn_portrait(self, piece, x, y, active, stunned, alive) -> None:
        bounds = (x - 42, y - 33, x + 42, y + 33)
        self.rectangle(bounds, (37, 48, 61) if active else (29, 38, 49))
        color = self.team_color(piece.team)
        self.rectangle(bounds, color, False)
        if active:
            self.rectangle((x - 47, y - 37, x + 47, y + 37), self.accent, False)
        self.portrait(piece, x, y + 5, 68, 51, grayscale=stunned or not alive)
        if stunned:
            for offset in range(-1, 2):
                pico2d.draw_line(x - 28, y + 25 + offset, x + 28, y - 20 + offset, 247, 61, 69)
        self.centered_label(x, y - 24, piece.identifier if alive else "처치", 14,
                            color if alive else self.muted)

    def draw_board(self, board=None, current=None, legal=(), area_action="이동") -> None:
        battle = self.game if board is None else None
        attack = ()
        cast = None
        age = 0.0
        now = monotonic()
        if battle is not None:
            board = battle.board
            current = battle.current if battle.winner is None else None
            legal = battle.legal_moves if battle.move_preview else ()
            attack = battle.skill_preview
            if battle.last_cast is not self._shown_cast:
                self._shown_cast = battle.last_cast
                self._cast_started = now
            age = now - self._cast_started
            if age < 0.8:
                cast = self._shown_cast
        left, bottom = self.board_x, self.board_y
        width, height = self.cell_width, self.cell_height
        boundary = left + width * 4
        right, top = left + width * 8, bottom + height * 4
        self.rectangle((left, bottom, boundary, top), (27, 43, 58))
        self.rectangle((boundary, bottom, right, top), (51, 35, 44))
        if battle is not None:
            for warrior in board.living_pieces:
                if warrior.character_id != "warrior":
                    continue
                for cell in aura_cells(board, warrior):
                    tint = (37, 56, 62) if cell[0] < 4 else (61, 48, 55)
                    self.rectangle(self.cell_bounds(cell, 2), tint)
        for cell in legal:
            x, y = self.cell_center(cell)
            self.draw_cell_fill(cell, (37, 75, 77), (94, 177, 166))
            self.centered_label(x, y, "·", 32, (145, 222, 202))
        for cell in attack:
            self.draw_cell_fill(cell, (30, 80, 126), self.blue)
        if cast is not None and age < 0.22:
            for cell in cast.cells:
                self.draw_cell_fill(cell, (43, 104, 147), self.blue)
            for hit in cast.hits:
                self.draw_cell_fill(hit.cell, (127, 54, 56), self.red)
        if self.hover is not None:
            color = (145, 222, 202) if self.hover in legal else self.muted
            self.rectangle(self.cell_bounds(self.hover, 3), color, False)
        for column in range(9):
            x = left + column * width
            pico2d.draw_line(x, bottom, x, top, 86, 99, 113)
        for row in range(5):
            y = bottom + row * height
            pico2d.draw_line(left, y, right, y, 86, 99, 113)
        for offset in (-1, 0, 1):
            pico2d.draw_line(boundary + offset, bottom, boundary + offset, top, *self.accent)
        for column in range(8):
            self.centered_label(self.cell_center((column, 0))[0], top + 19, chr(ord("A") + column), 16, self.muted)
        for row in range(4):
            self.centered_label(left - 24, self.cell_center((0, row))[1], str(row + 1), 16, self.muted)
        if battle is not None:
            for box in battle.boxes:
                if box.owner.current_hp > 0:
                    x, y = self.cell_center(box.cell)
                    bounds = (x + 59, y + 31, x + 93, y + 55)
                    self.rectangle(bounds, (89, 54, 104))
                    self.rectangle(bounds, self.accent, False)
                    self.centered_label(x + 76, y + 43, str(box.damage), 16, self.accent)
        hit_ids = {hit.piece_id for hit in cast.hits} if cast is not None and age < 0.22 else set()
        for piece in board.living_pieces:
            x, y = self.cell_center(piece.position)
            color = self.team_color(piece.team)
            active = current is not None and piece.identifier == current.identifier
            if active:
                self.rectangle(self.cell_bounds(piece.position, 3), self.accent, False)
            shake = int(5 * sin(age * 65)) if piece.identifier in hit_ids else 0
            self.portrait(piece, x + shake, y + 3, 126, 88)
            self.centered_label(x, y - 49, f"{piece.identifier} {piece.name}", 16, color)
            if battle is not None and active:
                self.centered_label(x, y + 54 + int(4 * sin(now * tau / 0.8)), "▼", 18, self.accent)
            if battle is not None and piece.marks:
                self.rectangle((x + 57, y - 3, x + 95, y + 21), (66, 38, 88))
                self.centered_label(x + 76, y + 9, f"◆ {sum(piece.marks.values())}", 14, (238, 192, 255))
            if battle is not None and piece.stunned:
                self.label(x - 93, y + 39, "기절", 16, self.accent)
        if battle is not None:
            for cell, percent in battle.mage_preview:
                x, y = self.cell_center(cell)
                self.rectangle((x - 75, y + 31, x + 75, y + 56), (23, 39, 58))
                self.centered_label(x, y + 44, f"+{percent}% 추가 피해", 16, self.accent)
        if cast is not None:
            for hit in cast.hits:
                x, y = self.cell_center(hit.cell)
                y += 8 + int(32 * age)
                self.centered_label(x + 1, y - 1, f"-{hit.damage}", 26, (23, 14, 20))
                self.centered_label(x, y, f"-{hit.damage}", 26, (255, 180, 157))
        if battle is None:
            self.label(left, bottom - 20, f"청팀 {area_action} 영역", 14, self.blue)
            self.label(boundary + 8, bottom - 20, f"홍팀 {area_action} 영역", 14, self.red)

    def cell_bounds(self, cell, inset):
        x, y = self.cell_center(cell)
        half_width = self.cell_width // 2 - inset
        half_height = self.cell_height // 2 - inset
        return x - half_width, y - half_height, x + half_width, y + half_height

    def draw_cell_fill(self, cell, color, border) -> None:
        bounds = self.cell_bounds(cell, 5)
        self.rectangle(bounds, color)
        self.rectangle(bounds, border, False)

    @staticmethod
    def skill_bounds(slot: int) -> tuple[int, int, int, int]:
        left = 460 + slot * 346
        return left, 89, left + 328, 228

    def action_panel_progress(self, battle: Prototype) -> float:
        now = monotonic()
        mode = battle.action_mode
        if mode is not self._shown_action_mode:
            self._shown_action_mode = mode
            self._action_changed_at = now
        if self._action_changed_at is None:
            return 1.0
        return min(1.0, (now - self._action_changed_at) / 0.16)

    def draw_actions(self, revealing: bool) -> None:
        if self.game.winner is not None:
            return
        progress = self.action_panel_progress(self.game)
        mode = self.game.action_mode
        self.rectangle(self.action_panel, (23, 31, 41))
        if mode is None:
            self.draw_action_button(self.attack_button, "공격", self.blue, 32)
            self.draw_action_button(self.move_button, "이동", (94, 177, 166), 32,
                                    bool(self.game.legal_moves) and not self.game.redraw_pending)
            self.draw_action_button(self.pass_button, "턴 넘김", self.muted, 32)
            if self.game.card_draw is not None:
                image = self.card_back if revealing else self.card_faces[self.game.card_draw.suit]
                image.draw(*self.menu_card)
        else:
            if mode is ActionMode.ATTACK:
                self.draw_skills(revealing)
            else:
                self.label(486, 170, "이동", 26)
                self.label(486, 131, "보드에서 표시된 칸을 클릭하세요.", 20, self.muted)
            self.draw_action_button(self.action_back_button, "뒤로가기", self.muted, 22)
            self.draw_action_button(self.submenu_pass_button, "턴 넘김 / Space", self.muted, 16)

        if progress < 1:
            left, bottom, right, top = self.action_panel
            self.rectangle((left + 1, bottom + 1, right - 1, top - 1 - int((top - bottom - 2) * progress)),
                           (23, 31, 41))

    def draw_action_button(self, bounds, title, border, size, enabled=True) -> None:
        left, bottom, right, top = bounds
        self.rectangle(bounds, (36, 50, 65) if enabled else (29, 38, 49))
        self.rectangle(bounds, border if enabled else (84, 101, 119), False)
        self.centered_label((left + right) // 2, (bottom + top) // 2,
                            title, size, self.text if enabled else self.muted)

    def draw_skills(self, revealing: bool = False) -> None:
        if not self.game.skills:
            self.label(486, 159, "사용할 수 있는 액티브 스킬이 없습니다.", 20, self.muted)
            return
        for slot, skill in enumerate(self.game.skills):
            bounds = self.skill_bounds(slot)
            x = bounds[0] + 14
            selected = self.game.selected_skill == slot
            unavailable = self.game.skill_unavailable(slot)
            self.rectangle(bounds, (29, 57, 84) if selected else (29, 38, 49))
            self.rectangle(bounds, self.blue if selected else (84, 101, 119), False)
            draw = self.game.card_draw if slot == 0 else None
            if draw is not None:
                self.draw_card_skill(bounds, draw.suit, skill, revealing, unavailable)
                continue
            self.label(x, 193, skill.name, 22, self.muted if unavailable else self.text)
            if skill.damage:
                self.label(bounds[2] - 93, 193, f"피해 {skill.damage}", 16, self.muted)
            self.label(x, 156, skill.effect.value, 18)
            status = unavailable or ("다시 클릭하여 발동" if selected else "클릭하여 범위 표시")
            if slot == 2 and unavailable is None and not selected:
                status = "영웅 스킬 · 클릭하여 범위 표시"
            self.label(x, 118, status, 16, self.blue if selected else self.muted)

    def draw_card_skill(self, bounds, suit, skill, revealing, unavailable) -> None:
        card_x, card_y, card_width, card_height = self.skill_card
        x = bounds[0] + 96
        image = self.card_back if revealing else self.card_faces[suit]
        image.draw(card_x, card_y, card_width, card_height)
        self.label(x, 198, "카드 던지기", 20)
        if revealing:
            self.label(x, 153, "카드 공개 중", 16, self.muted)
            return
        self.label(x, 174, f"{suit.label} A", 16, self.accent)
        if suit is Suit.HEART:
            detail = "자신 10% 회복 · 인접 피해 40" if self.game.current.hero else "인접 아군 HP 10% 회복"
        elif suit is Suit.CLUB:
            detail = "내 진영 빈 칸 이동" if self.game.current.hero else "아군과 위치 교환"
        else:
            detail = f"피해 {skill.damage}" + (" · 기절" if suit is Suit.DIAMOND else " · 2칸")
        self.label(x, 148, detail, 16)
        status = unavailable or "클릭하여 범위 표시"
        if self.game.card_target_pending:
            status = "파란 칸에서 대상 선택"
        elif self.game.selected_skill == 0:
            status = "다시 클릭하여 발동"
        self.label(x, 120, status, 16, self.blue if self.game.selected_skill == 0 else self.muted)

    @property
    def skill_card(self):
        return self.skill_bounds(0)[0] + 48, 159, 65, 91

    def draw_card_reveal(self) -> None:
        progress = min(1.0, (monotonic() - self._draw_started) / self.card_reveal_seconds)
        x, y = self.board_x + 4 * self.cell_width, 543 + 46 * min(1.0, progress / 0.28)
        width, height = 128.0, 179.0
        if progress > 0.67:
            slide = min(1.0, (progress - 0.67) / 0.33)
            slide = slide * slide * (3 - 2 * slide)
            target = self.skill_card if self.game.action_mode is ActionMode.ATTACK else self.menu_card
            target_x, target_y, target_width, target_height = target
            x += (target_x - x) * slide
            y += (target_y - y) * slide
            width += (target_width - width) * slide
            height += (target_height - height) * slide
        turn = max(0.0, min(1.0, (progress - 0.25) / 0.31))
        face = self.card_faces[self._shown_draw.suit] if turn >= 0.5 else self.card_back
        face.draw(round(x), round(y), max(2, round(width * abs(cos(pi * turn)))), round(height))

    def draw_details(self) -> None:
        piece = self.game.current
        x = 228
        title = "경기 종료" if self.game.winner else ("영웅화 기물" if piece.hero else "현재 기물")
        self.label(x, 230, title, 16, self.muted)
        self.label(x, 196, f"{piece.identifier}  {piece.name}", 26, self.team_color(piece.team))
        if piece.character_id == "assassin":
            self.label(x, 67, "정면 →" if piece.team is Team.BLUE else "정면 ←", 16, self.muted)
        pico2d.draw_circle(124, 144, 86, 30, 43, 56, filled=True)
        pico2d.draw_circle(124, 144, 86, *self.team_color(piece.team), filled=False)
        self.portrait(piece, 124, 144, 139, 148)
        self.label(x, 160, f"{piece.job.value} / {self.movement_labels[piece.job]}", 18)
        self.label(x, 138, f"{self.game.cell_name(piece.position)} / 이동 가능 {len(self.game.legal_moves)}칸",
                   16, self.muted)
        if self.game.winner is not None:
            self.label(460, 166, "승리" if self.game.winner is Team.BLUE else "패배", 46, self.accent)

    def draw_passive_icon(self, piece: Piece) -> None:
        lines = DESCRIPTIONS.get(piece.character_id)
        if not lines or self.game.winner is not None:
            return
        color = (213, 176, 246) if not piece.passive_used or piece.shield else self.muted
        self.rectangle(self.passive_icon, (54, 42, 73))
        self.rectangle(self.passive_icon, color, False)
        self.centered_label(286, 107, "◆ 패시브", 16, color)
        if self.passive_hovered:
            left, bottom = 228, 238
            status = "보호막 활성" if piece.shield else ("이번 경기에서 사용함" if piece.passive_used else "")
            rows = (*lines, status) if status else lines
            top = bottom + 16 + 24 * len(rows)
            bounds = (left, bottom, left + 338, top)
            self.rectangle(bounds, (26, 25, 43))
            self.rectangle(bounds, color, False)
            for i, line in enumerate(rows):
                self.label(left + 14, top - 20 - i * 24, line, 16, color if line == status else self.text)

    def draw_combat_notice(self) -> None:
        if self.game is not self._notice_battle:
            self._notice_battle = self.game
            self._notice_index, self._notice_until = -1, 0.0
        now = monotonic()
        messages = self.game.combat_notices
        if now >= self._notice_until and self._notice_index + 1 < len(messages):
            self._notice_index += 1
            self._notice_until = now + 2.2
        if now < self._notice_until:
            self.rectangle((616, 246, 1516, 284), (50, 38, 66))
            kind, text = messages[self._notice_index]
            self.label(632, 265, f"{kind}  {text}", 18, (236, 202, 255))

    @staticmethod
    def revival_card_bounds(slot: int) -> tuple[int, int, int, int]:
        left = 603 + slot * 158
        return left, 465, left + 140, 638

    def draw_revival_choices(self) -> None:
        piece = self.game.revival_pending
        bounds = (580, 442, 1240, 706)
        self.rectangle(bounds, (29, 24, 46))
        self.rectangle(bounds, self.accent, False)
        self.label(603, 673, f"{piece.identifier} {piece.name} 부활 · 사용할 카드를 고르세요.", 22)
        for slot, suit in enumerate(Suit):
            left, bottom, right, top = self.revival_card_bounds(slot)
            card_bounds = (left, bottom, right, top)
            self.rectangle(card_bounds, (49, 39, 66))
            self.rectangle(card_bounds, self.muted, False)
            self.card_faces[suit].draw((left + right) // 2, 565, 80, 112)
            self.centered_label((left + right) // 2, 489, f"{suit.label} A", 18, self.accent)

    def draw_footer(self, revealing: bool = False) -> None:
        color = self.red if self.game.failed and not revealing else self.text
        message = "카드를 뽑습니다." if revealing else self.game.message
        self.label(460, 60, message, 18, color)
        if self.game.history:
            self.label(460, 30, self.game.history[0], 16, self.muted)
        self.label(39, 25, "Esc  종료", 14, self.muted)
