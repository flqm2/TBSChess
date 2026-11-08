"""pico2d 표시와 화면 좌표 변환. 이동 판정은 Prototype의 공통 규칙을 사용한다."""

import os
from pathlib import Path

import pico2d

from character_data import CHARACTERS
from piece import Job, Piece, Team
from prototype import Prototype


class BattleView:
    width, height = 1120, 780
    board_x, board_y, cell_size = 56, 220, 94
    skip_button = (840, 244, 1072, 288)
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
        self.label(40, 700, "03 / 선택한 편성으로 이동 · 충돌 · 턴 확인", 16, self.muted)
        self.label(884, 735, f"ROUND {self.game.turns.round:02}", 22, self.accent)
        self.label(884, 704, f"양측 수동 조작 / {len(self.game.board.pieces)}기", 14, self.muted)
        self.draw_turn_order()
        self.draw_board()
        self.draw_details()
        self.draw_footer()

    def draw_turn_order(self) -> None:
        slot_width = 1040 // len(self.game.turns.order)
        for index, piece in enumerate(self.game.turns.order):
            x = 40 + index * slot_width
            active = piece is self.game.current
            self.rectangle((x, 635, x + slot_width - 10, 680), (36, 47, 60) if active else (26, 34, 45))
            self.rectangle((x, 635, x + 3, 680), self.team_color(piece.team))
            if active:
                status = "현재 차례"
            elif index < self.game.turns.index:
                status = "행동 완료"
            else:
                status = "대기"
            self.label(x + 10, 666, f"{piece.identifier} {piece.name}", 14,
                       self.team_color(piece.team) if active else self.text)
            self.label(x + 10, 646, status, 14, self.accent if active else self.muted)

    def draw_board(self, board=None, current=None, legal=(), area_action="이동") -> None:
        if board is None:
            board, current, legal = self.game.board, self.game.current, self.game.legal_moves
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
        for piece in board.pieces:
            x, y = self.cell_center(piece.position)
            color = self.team_color(piece.team)
            if current is not None and piece.identifier == current.identifier:
                self.rectangle((x - 44, y - 44, x + 44, y + 44), self.accent, False)
                self.rectangle((x - 43, y - 43, x + 43, y + 43), self.accent, False)
            image = self.images[piece.image_name]
            scale = min(76 / image.w, 62 / image.h)
            image.draw(x, y + 11, image.w * scale, image.h * scale)
            self.draw_health_bar(piece, x - 29, y - 26, 58, 5)
            self.label(x - 37, y - 35, f"{piece.identifier} {piece.name}", 14, color)
        self.label(left, bottom - 20, f"청팀 {area_action} 영역", 14, self.blue)
        self.label(left + 4 * size + 8, bottom - 20, f"홍팀 {area_action} 영역", 14, self.red)

    def draw_details(self) -> None:
        piece = self.game.current
        x = 840
        self.label(x, 587, "현재 기물", 14, self.muted)
        self.label(x, 553, f"{piece.identifier}  {piece.name}", 22, self.team_color(piece.team))
        image = self.images[piece.image_name]
        scale = min(132 / image.w, 136 / image.h)
        image.draw(956, 462, image.w * scale, image.h * scale)
        self.label(x, 373, f"{piece.job.value}  /  {self.movement_labels[piece.job]}", 16)
        self.label(x, 347, f"체력  {piece.current_hp} / {piece.max_hp}", 16)
        self.draw_health_bar(piece, x, 329, 232, 7)
        self.label(x, 309, f"위치  {self.game.cell_name(piece.position)}   /   이동 가능  {len(self.game.legal_moves)}칸",
                   14, self.muted)
        self.rectangle(self.skip_button, (46, 57, 71))
        self.rectangle(self.skip_button, (92, 108, 125), False)
        self.label(x + 16, 266, "Space  검증용 턴 넘김", 16)
        self.label(x, 225, "이동 성공 시 다음 기물 차례", 14, self.muted)
        self.label(x, 202, "이동 실패 시 위치·턴 유지", 14, self.muted)

    def draw_footer(self) -> None:
        color = self.red if self.game.failed else self.text
        self.label(40, 153, self.game.message, 18, color)
        for index, entry in enumerate(self.game.history):
            self.label(40, 121 - index * 21, entry, 14, self.muted)
        self.label(840, 145, "초록 칸: 이동 가능 / 금색: 현재", 14, self.muted)
        self.label(840, 120, "중앙 경계선 통과 불가", 14, self.muted)
        self.label(840, 95, "양 진영의 점유 칸은 진입 불가", 14, self.muted)
        self.label(40, 20, "왼쪽 클릭  이동     Space  턴 넘김     Esc  종료", 14, self.muted)
