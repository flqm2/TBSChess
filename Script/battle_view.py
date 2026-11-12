"""pico2d 표시와 화면 좌표 변환. 이동 판정은 Prototype의 공통 규칙을 사용한다."""

import os
from math import cos, pi, sin, tau
from pathlib import Path
from time import monotonic

import pico2d

from character_data import CHARACTERS
from cards import Suit
from passives import DESCRIPTIONS, aura_cells
from piece import Job, Piece, Team
from prototype import ActionMode, Prototype


class BattleView:
    width, height = 1120, 780
    board_x, board_y, cell_size = 56, 220, 94
    skip_button = (840, 244, 1072, 288)
    action_panel = (40, 86, 1072, 212)
    attack_button = (56, 103, 548, 195)
    move_button = (564, 103, 1056, 195)
    action_back_button = (828, 103, 1056, 179)
    menu_card = (488, 149, 42, 59)
    pass_button = (840, 244, 1072, 288)
    passive_icon = (1002, 569, 1072, 596)
    help_button = (1030, 721, 1072, 752)
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
        self.fonts = {size: pico2d.load_font(str(font), size) for size in (12, 14, 16, 18, 22, 30)}
        self.images = {
            character.image_name: pico2d.load_image(str(root / "Resource" / character.image_name))
            for character in CHARACTERS
        }
        card_dir = root / "Resource" / "Cards"
        self.card_faces = {suit: pico2d.load_image(str(card_dir / f"ace_{suit.slug}.png")) for suit in Suit}
        self.card_back = pico2d.load_image(str(card_dir / "back.png"))
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
        column = (x - cls.board_x) // cls.cell_size
        row_from_bottom = (canvas_y - cls.board_y) // cls.cell_size
        if not (0 <= column < 8 and 0 <= row_from_bottom < 4):
            return None
        return column, 3 - row_from_bottom

    @classmethod
    def skip_at_pixel(cls, x: int, screen_y: int) -> bool:
        left, bottom, right, top = cls.skip_button
        return left <= x <= right and bottom <= cls.height - 1 - screen_y <= top

    @classmethod
    def cell_center(cls, cell: tuple[int, int]) -> tuple[int, int]:
        return (cls.board_x + cell[0] * cls.cell_size + cls.cell_size // 2,
                cls.board_y + (3 - cell[1]) * cls.cell_size + cls.cell_size // 2)

    @staticmethod
    def rectangle(bounds, color, filled=True):
        pico2d.draw_rectangle(*bounds, *color, filled=filled)

    def label(self, x, y, text, size=16, color=None):
        self.fonts[size].draw(x, y, text, color or self.text)

    def team_color(self, team):
        return self.blue if team is Team.BLUE else self.red

    def draw_health_bar(self, piece: Piece, x: int, y: int, width: int, height: int) -> None:
        top = y + height - 1
        self.rectangle((x, y, x + width - 1, top), (12, 18, 24))
        filled = max(0, min(width, round(width * piece.current_hp / piece.max_hp)))
        if filled:
            color = (100, 209, 145) if piece.team is Team.BLUE else self.red
            self.rectangle((x, y, x + filled - 1, top), color)

    def draw(self) -> None:
        revealing = self.card_revealing(self.game)
        self.rectangle((0, 0, self.width - 1, self.height - 1), self.background)
        self.label(40, 735, "전략 RPG 체스", 30)
        self.label(40, 700, "이동 · 스킬", 16, self.muted)
        self.label(884, 735, f"ROUND {self.game.turns.round:02}", 22, self.accent)
        self.draw_action_button(self.help_button, "?", self.blue, 18)
        self.label(884, 704, f"양측 수동 조작 / {len(self.game.board.pieces)}기", 14, self.muted)
        self.draw_turn_order()
        self.draw_board()
        self.draw_details()
        self.draw_actions(revealing)
        self.draw_footer(revealing)
        self.draw_combat_notice()
        if self.game.revival_pending is not None:
            self.draw_revival_choices()
        elif revealing:
            self.draw_card_reveal()

    def draw_turn_order(self) -> None:
        slot_width = 1040 // len(self.game.turns.order)
        for index, piece in enumerate(self.game.turns.order):
            x = 40 + index * slot_width
            active = piece is self.game.current and self.game.winner is None
            self.rectangle((x, 635, x + slot_width - 10, 680), (36, 47, 60) if active else (26, 34, 45))
            self.rectangle((x, 635, x + 3, 680), self.team_color(piece.team))
            if piece.current_hp == 0:
                status = "처치됨"
            elif piece.stunned:
                status = "기절"
            elif active:
                status = "현재 차례"
            elif index < self.game.turns.index:
                status = "행동 완료"
            else:
                status = "대기"
            self.label(x + 10, 666, f"{piece.identifier} {piece.name}", 14,
                       self.team_color(piece.team) if active else self.text)
            self.label(x + 10, 646, status, 14, self.accent if active else self.muted)

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
        left, bottom, size = self.board_x, self.board_y, self.cell_size
        right, top = left + size * 8, bottom + size * 4
        self.rectangle((left, bottom, left + size * 4, top), (27, 43, 58))
        self.rectangle((left + size * 4, bottom, right, top), (51, 35, 44))
        if battle is not None:
            for warrior in board.living_pieces:
                if warrior.character_id != "warrior":
                    continue
                for cell in aura_cells(board, warrior):
                    x, y = self.cell_center(cell)
                    half = size // 2 - 2
                    tint = (37, 56, 62) if cell[0] < 4 else (61, 48, 55)
                    self.rectangle((x - half, y - half, x + half, y + half), tint)
        for cell in legal:
            x, y = self.cell_center(cell)
            half = size // 2 - 5
            self.rectangle((x - half, y - half, x + half, y + half), (37, 75, 77))
            self.rectangle((x - half, y - half, x + half, y + half), (94, 177, 166), False)
            self.label(x - 6, y, "·", 30, (145, 222, 202))
        for cell in attack:
            self.draw_cell_fill(cell, (30, 80, 126), self.blue)
        if cast is not None and age < 0.22:
            for cell in cast.cells:
                self.draw_cell_fill(cell, (43, 104, 147), self.blue)
            for hit in cast.hits:
                self.draw_cell_fill(hit.cell, (127, 54, 56), self.red)
        if self.hover is not None:
            x, y = self.cell_center(self.hover)
            half = size // 2 - 3
            color = (145, 222, 202) if self.hover in legal else self.muted
            self.rectangle((x - half, y - half, x + half, y + half), color, False)
        for column in range(9):
            x = left + column * size
            pico2d.draw_line(x, bottom, x, top, 86, 99, 113)
        for row in range(5):
            y = bottom + row * size
            pico2d.draw_line(left, y, right, y, 86, 99, 113)
        for offset in (-1, 0, 1):
            pico2d.draw_line(left + 4 * size + offset, bottom, left + 4 * size + offset, top, *self.accent)
        for column in range(8):
            self.label(left + column * size + 40, top + 16, chr(ord("A") + column), 14, self.muted)
        for row in range(4):
            self.label(30, self.cell_center((0, row))[1], str(row + 1), 14, self.muted)
        if battle is not None:
            for box in battle.boxes:
                if box.owner.current_hp > 0:
                    x, y = self.cell_center(box.cell)
                    self.rectangle((x + 11, y + 22, x + 43, y + 42), (89, 54, 104))
                    self.rectangle((x + 11, y + 22, x + 43, y + 42), self.accent, False)
                    self.label(x + 16, y + 32, str(box.damage), 14, self.accent)
        hit_ids = {hit.piece_id for hit in cast.hits} if cast is not None and age < 0.22 else set()
        for piece in board.living_pieces:
            x, y = self.cell_center(piece.position)
            color = self.team_color(piece.team)
            active = current is not None and piece.identifier == current.identifier
            if active:
                self.rectangle((x - 44, y - 44, x + 44, y + 44), self.accent, False)
            image = self.images[piece.image_name]
            scale = min(76 / image.w, 55 / image.h)
            shake = int(5 * sin(age * 65)) if piece.identifier in hit_ids else 0
            image.draw(x + shake, y + 8, image.w * scale, image.h * scale)
            self.draw_health_bar(piece, x - 29, y - 26, 58, 5)
            self.label(x - 37, y - 35, f"{piece.identifier} {piece.name}", 14, color)
            if battle is not None and active:
                self.label(x - 8, y + 42 + int(4 * sin(now * tau / 0.8)), "▼", 16, self.accent)
            if battle is not None and piece.marks:
                self.rectangle((x + 9, y + 17, x + 43, y + 35), (66, 38, 88))
                self.label(x + 13, y + 26, f"◆ {sum(piece.marks.values())}", 14, (238, 192, 255))
            if battle is not None and piece.stunned:
                self.label(x - 39, y + 27, "기절", 14, self.accent)
        if battle is not None:
            for cell, percent in battle.mage_preview:
                x, y = self.cell_center(cell)
                self.rectangle((x - 46, y + 26, x + 46, y + 45), (23, 39, 58))
                self.label(x - 44, y + 35, f"+{percent}% 추가 피해", 12, self.accent)
        if cast is not None:
            for hit in cast.hits:
                x, y = self.cell_center(hit.cell)
                y += 8 + int(32 * age)
                self.label(x - 19, y - 1, f"-{hit.damage}", 22, (23, 14, 20))
                self.label(x - 20, y, f"-{hit.damage}", 22, (255, 180, 157))
        if battle is None:
            self.label(left, bottom - 20, f"청팀 {area_action} 영역", 14, self.blue)
            self.label(left + 4 * size + 8, bottom - 20, f"홍팀 {area_action} 영역", 14, self.red)

    def draw_cell_fill(self, cell, color, border) -> None:
        x, y = self.cell_center(cell)
        half = self.cell_size // 2 - 5
        bounds = (x - half, y - half, x + half, y + half)
        self.rectangle(bounds, color)
        self.rectangle(bounds, border, False)

    @staticmethod
    def skill_bounds(slot: int) -> tuple[int, int, int, int]:
        left = 56 + slot * 252
        return left, 92, left + 240, 179

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
        self.rectangle(self.action_panel, (84, 101, 119), False)
        if mode is None:
            self.draw_action_button(self.attack_button, "공격", self.blue, 30)
            self.draw_action_button(self.move_button, "이동", (94, 177, 166), 30,
                                    bool(self.game.legal_moves) and not self.game.redraw_pending)
            if self.game.card_draw is not None:
                image = self.card_back if revealing else self.card_faces[self.game.card_draw.suit]
                image.draw(*self.menu_card)
        else:
            if mode is ActionMode.ATTACK:
                self.draw_skills(revealing)
            else:
                self.label(66, 161, "이동", 22)
                color = self.red if self.game.failed else self.muted
                self.label(66, 127, self.game.message, 16, color)
            self.draw_action_button(self.action_back_button, "뒤로가기", self.muted, 22)

        if progress < 1:
            left, bottom, right, top = self.action_panel
            self.rectangle((left + 1, bottom + 1, right - 1, top - 1 - int((top - bottom - 2) * progress)),
                           (23, 31, 41))

    def draw_action_button(self, bounds, title, border, size, enabled=True) -> None:
        left, bottom, right, top = bounds
        self.rectangle(bounds, (36, 50, 65) if enabled else (29, 38, 49))
        self.rectangle(bounds, border if enabled else (84, 101, 119), False)
        self.label((left + right - len(title) * size) // 2, (bottom + top) // 2,
                   title, size, self.text if enabled else self.muted)

    def draw_skills(self, revealing: bool = False) -> None:
        if not self.game.skills:
            self.label(56, 140, "사용할 수 있는 액티브 스킬이 없습니다.", 16, self.muted)
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
            self.label(x, 158, skill.name, 18, self.muted if unavailable else self.text)
            if skill.damage:
                self.label(bounds[2] - 70, 158, f"피해 {skill.damage}", 14, self.muted)
            self.label(x, 132, skill.effect.value, 14)
            status = unavailable or ("다시 클릭하여 발동" if selected else "클릭하여 범위 표시")
            if slot == 2 and unavailable is None and not selected:
                status = "영웅 스킬 · 클릭하여 범위 표시"
            self.label(x, 108, status, 14, self.blue if selected else self.muted)

    def draw_card_skill(self, bounds, suit, skill, revealing, unavailable) -> None:
        x = bounds[0] + 69
        image = self.card_back if revealing else self.card_faces[suit]
        image.draw(bounds[0] + 34, 136, 48, 67)
        self.label(x, 160, "카드 던지기", 16)
        if revealing:
            self.label(x, 131, "카드 공개 중", 14, self.muted)
            return
        self.label(x, 142, f"{suit.label} A", 14, self.accent)
        if suit is Suit.HEART:
            detail = "자신 10% 회복 · 인접 피해 40" if self.game.current.hero else "인접 아군 HP 10% 회복"
        elif suit is Suit.CLUB:
            detail = "내 진영 빈 칸 이동" if self.game.current.hero else "아군과 위치 교환"
        else:
            detail = f"피해 {skill.damage}" + (" · 기절" if suit is Suit.DIAMOND else " · 2칸")
        self.label(x, 123, detail, 14)
        status = unavailable or "클릭하여 범위 표시"
        if self.game.card_target_pending:
            status = "파란 칸에서 대상 선택"
        elif self.game.selected_skill == 0:
            status = "다시 클릭하여 발동"
        self.label(x, 104, status, 14, self.blue if self.game.selected_skill == 0 else self.muted)

    def draw_card_reveal(self) -> None:
        progress = min(1.0, (monotonic() - self._draw_started) / self.card_reveal_seconds)
        x, y = 432.0, 382.0 + 46 * min(1.0, progress / 0.28)
        width, height = 106.0, 148.0
        if progress > 0.67:
            slide = min(1.0, (progress - 0.67) / 0.33)
            slide = slide * slide * (3 - 2 * slide)
            target = (90, 136, 48, 67) if self.game.action_mode is ActionMode.ATTACK else self.menu_card
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
        x = 840
        title = "경기 종료" if self.game.winner else ("영웅화 기물" if piece.hero else "현재 기물")
        self.label(x, 587, title, 14, self.muted)
        self.label(x, 553, f"{piece.identifier}  {piece.name}", 22, self.team_color(piece.team))
        if piece.character_id == "assassin":
            self.label(1006, 553, "정면 →" if piece.team is Team.BLUE else "정면 ←", 14, self.muted)
        image = self.images[piece.image_name]
        scale = min(132 / image.w, 136 / image.h)
        image.draw(956, 462, image.w * scale, image.h * scale)
        self.label(x, 373, f"{piece.job.value}  /  {self.movement_labels[piece.job]}", 16)
        self.label(x, 347, f"체력  {piece.current_hp} / {piece.max_hp}", 16)
        self.draw_health_bar(piece, x, 329, 232, 7)
        self.label(x, 309, f"위치  {self.game.cell_name(piece.position)}   /   이동 가능  {len(self.game.legal_moves)}칸",
                   14, self.muted)
        if self.game.winner is not None:
            self.label(x, 267, "승리" if self.game.winner is Team.BLUE else "패배", 30, self.accent)
            return
        self.rectangle(self.pass_button, (46, 57, 71))
        self.rectangle(self.pass_button, (92, 108, 125), False)
        self.label(x + 16, 266, "턴 넘김  /  Space", 16)
        self.draw_passive_icon(piece)

    def draw_passive_icon(self, piece: Piece) -> None:
        lines = DESCRIPTIONS.get(piece.character_id)
        if not lines:
            return
        color = (213, 176, 246) if not piece.passive_used or piece.shield else self.muted
        self.rectangle(self.passive_icon, (54, 42, 73))
        self.rectangle(self.passive_icon, color, False)
        self.label(1008, 582, "◆ 패시브", 14, color)
        if self.passive_hovered:
            top = 532
            status = "보호막 활성" if piece.shield else ("이번 경기에서 사용함" if piece.passive_used else "")
            rows = (*lines, status) if status else lines
            self.rectangle((816, top - 16 - 22 * len(rows), 1072, top), (26, 25, 43))
            self.rectangle((816, top - 16 - 22 * len(rows), 1072, top), color, False)
            for i, line in enumerate(rows):
                self.label(827, top - 19 - i * 22, line, 14, color if line == status else self.text)

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
            self.rectangle((246, 686, 810, 717), (50, 38, 66))
            kind, text = messages[self._notice_index]
            self.label(260, 701, f"{kind}  {text}", 16, (236, 202, 255))

    @staticmethod
    def revival_card_bounds(slot: int) -> tuple[int, int, int, int]:
        left = 276 + slot * 132
        return left, 329, left + 120, 469

    def draw_revival_choices(self) -> None:
        piece = self.game.revival_pending
        bounds = (254, 306, 812, 516)
        self.rectangle(bounds, (29, 24, 46))
        self.rectangle(bounds, self.accent, False)
        self.label(276, 492, f"{piece.identifier} {piece.name} 부활 · 사용할 카드를 고르세요.", 18)
        for slot, suit in enumerate(Suit):
            left, bottom, right, top = self.revival_card_bounds(slot)
            card_bounds = (left, bottom, right, top)
            self.rectangle(card_bounds, (49, 39, 66))
            self.rectangle(card_bounds, self.muted, False)
            self.card_faces[suit].draw((left + right) // 2, 411, 66, 92)
            self.label(left + 14, 347, f"{suit.label} A", 14, self.accent)

    def draw_footer(self, revealing: bool = False) -> None:
        color = self.red if self.game.failed and not revealing else self.text
        message = "카드를 뽑습니다." if revealing else self.game.message
        if not self.game.move_preview or revealing:
            self.label(56, 65, message, 16, color)
        if self.game.history:
            self.label(56, 39, self.game.history[0], 14, self.muted)
        self.label(840, 18, "Esc  종료", 14, self.muted)
