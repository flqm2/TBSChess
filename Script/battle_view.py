"""pico2d 표시와 화면 좌표 변환. 이동 판정은 Prototype의 공통 규칙을 사용한다."""

import os
from math import sin, tau
from pathlib import Path
from time import monotonic

import pico2d

from character_data import CHARACTERS
from piece import Job, Piece, Team
from prototype import Prototype


class BattleView:
    width, height = 1120, 780
    board_x, board_y, cell_size = 56, 220, 94
    skip_button = (840, 244, 1072, 288)
    move_button = (840, 244, 1072, 288)
    pass_button = (840, 185, 1072, 225)
    background = (19, 25, 34)
    text = (233, 237, 241)
    muted = (151, 166, 183)
    blue = (104, 191, 242)
    red = (244, 143, 141)
    accent = (243, 211, 132)
    movement_labels = {Job.MELEE: "상하좌우 1칸", Job.RANGED: "대각선 1칸", Job.JOKER: "전 방향 1칸"}

    def __init__(self, game: Prototype | None = None):
        self.game = game
        root = Path(__file__).resolve().parents[1]
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        font = next((p for p in (fonts / "malgun.ttf", fonts / "gulim.ttc") if p.is_file()), None)
        if font is None:
            raise FileNotFoundError("한국어 표시를 위한 맑은 고딕 또는 굴림 글꼴이 필요합니다.")
        self.fonts = {size: pico2d.load_font(str(font), size) for size in (14, 16, 18, 22, 30)}
        self.images = {
            character.image_name: pico2d.load_image(str(root / "Resource" / character.image_name))
            for character in CHARACTERS
        }
        self.hover: tuple[int, int] | None = None
        self._shown_cast = None
        self._cast_started = 0.0

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
        self.rectangle((0, 0, self.width - 1, self.height - 1), self.background)
        self.label(40, 735, "전략 RPG 체스", 30)
        self.label(40, 700, "이동 · 스킬", 16, self.muted)
        self.label(884, 735, f"ROUND {self.game.turns.round:02}", 22, self.accent)
        self.label(884, 704, f"양측 수동 조작 / {len(self.game.board.pieces)}기", 14, self.muted)
        self.draw_turn_order()
        self.draw_board()
        self.draw_details()
        self.draw_skills()
        self.draw_footer()

    def draw_turn_order(self) -> None:
        slot_width = 1040 // len(self.game.turns.order)
        for index, piece in enumerate(self.game.turns.order):
            x = 40 + index * slot_width
            active = piece is self.game.current and self.game.winner is None
            self.rectangle((x, 635, x + slot_width - 10, 680), (36, 47, 60) if active else (26, 34, 45))
            self.rectangle((x, 635, x + 3, 680), self.team_color(piece.team))
            if piece.current_hp == 0:
                status = "처치됨"
            elif piece.stunned_round == self.game.turns.round:
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
                self.label(x + 22, y + 27, str(sum(piece.marks.values())), 14, (221, 165, 245))
        if cast is not None:
            for hit in cast.hits:
                x, y = self.cell_center(hit.cell)
                y += 8 + int(32 * age)
                self.label(x - 19, y - 1, f"-{hit.damage}", 22, (23, 14, 20))
                self.label(x - 20, y, f"-{hit.damage}", 22, (255, 180, 157))
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

    def draw_skills(self) -> None:
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
            self.label(x, 158, skill.name, 18, self.muted if unavailable else self.text)
            if skill.damage:
                self.label(bounds[2] - 70, 158, f"피해 {skill.damage}", 14, self.muted)
            self.label(x, 132, skill.effect.value, 14)
            status = unavailable or ("다시 클릭하여 발동" if selected else "클릭하여 범위 표시")
            if slot == 2 and unavailable is None and not selected:
                status = "영웅 스킬 · 클릭하여 범위 표시"
            self.label(x, 108, status, 14, self.blue if selected else self.muted)

    def draw_details(self) -> None:
        piece = self.game.current
        x = 840
        title = "경기 종료" if self.game.winner else ("영웅화 기물" if piece.hero else "현재 기물")
        self.label(x, 587, title, 14, self.muted)
        self.label(x, 553, f"{piece.identifier}  {piece.name}", 22, self.team_color(piece.team))
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
        self.rectangle(self.move_button, (30, 80, 70) if self.game.move_preview else (46, 57, 71))
        self.rectangle(self.move_button, (94, 177, 166) if self.game.move_preview else (92, 108, 125), False)
        self.label(x + 16, 266, "이동  ·  목적지 선택" if self.game.move_preview else "이동  ·  범위 표시", 16,
                   self.text if self.game.legal_moves else self.muted)
        self.rectangle(self.pass_button, (46, 57, 71))
        self.rectangle(self.pass_button, (92, 108, 125), False)
        self.label(x + 16, 205, "턴 넘김  /  Space", 16)

    def draw_footer(self) -> None:
        color = self.red if self.game.failed else self.text
        self.label(56, 65, self.game.message, 16, color)
        if self.game.history:
            self.label(56, 39, self.game.history[0], 14, self.muted)
        self.label(840, 145, "초록 칸  이동 범위", 14, self.muted)
        self.label(840, 120, "파란 칸  스킬 범위", 14, self.muted)
        self.label(840, 18, "Esc  종료", 14, self.muted)
