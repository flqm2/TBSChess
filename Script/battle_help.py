"""게임 화면 위에 기물별 기본 공격 범위를 보여주는 도움말 패널."""

from ctypes import byref, c_int

from pico2d import pico2d

from board import Board
from cards import CARD_SKILLS, Suit
from piece import Piece, Team
from skills import Cell, SKILLS


def attack_ranges(board: Board, piece: Piece) -> tuple[tuple[str, tuple[Cell, ...]], ...]:
    """영웅화 상태의 기본기까지 포함하고 세 번째 영웅 스킬은 제외한다."""
    if piece.character_id == "cardmaster":
        suits = (Suit.SPADE, Suit.DIAMOND, Suit.HEART) if piece.hero else (Suit.SPADE, Suit.DIAMOND)
        return tuple((suit.label, CARD_SKILLS[suit][int(piece.hero)].cells(board, piece)) for suit in suits)
    entry = SKILLS.get(piece.character_id)
    if entry is None:
        return ()
    return tuple((skill.name, skill.cells(board, piece)) for skill in entry[int(piece.hero)])


class BattleHelp:
    width, height = 1056, 648
    cell_size = 82
    attack = (36, 79, 118)
    overlap = (45, 112, 158)
    border = (82, 97, 112)

    def __init__(self, board: Board, current: Piece, canvas_width: int, canvas_height: int):
        self.board = board
        self.pieces = board.living_pieces
        self.selected = next((i for i, piece in enumerate(self.pieces) if piece is current), 0)
        self.x = (canvas_width - self.width) // 2
        self.y = (canvas_height - self.height) // 2
        self.close_button = (self.x + 976, self.y + 584, self.x + 1030, self.y + 630)

    def row_bounds(self, index):
        top = self.y + 474 - index * 40
        return self.x + 30, top - 36, self.x + 260, top

    def select_at(self, x: int, y: int) -> None:
        for index in range(len(self.pieces)):
            left, bottom, right, top = self.row_bounds(index)
            if left <= x <= right and bottom <= y <= top:
                self.selected = index
                return

    def move_selection(self, step: int) -> None:
        if self.pieces:
            self.selected = max(0, min(len(self.pieces) - 1, self.selected + step))

    def draw(self, view) -> None:
        blend = c_int()
        pico2d.SDL_GetRenderDrawBlendMode(pico2d.renderer, byref(blend))
        pico2d.SDL_SetRenderDrawBlendMode(pico2d.renderer, pico2d.SDL_BLENDMODE_BLEND)
        pico2d.draw_rectangle(0, 0, view.width - 1, view.height - 1, 8, 12, 20, 172, filled=True)
        pico2d.SDL_SetRenderDrawBlendMode(pico2d.renderer, blend.value)

        x, y = self.x, self.y
        right, top = x + self.width, y + self.height
        bounds = (x, y, right, top)
        view.rectangle((x + 8, y - 8, right + 8, top - 8), (8, 12, 18))
        view.rectangle(bounds, (24, 32, 44))
        view.rectangle((x, top - 81, right, top), (36, 49, 65))
        view.rectangle(bounds, self.border, False)
        view.label(x + 30, top - 40, "전투 도움말", 32)
        view.draw_action_button(self.close_button, "×", view.muted, 26)
        view.label(x + 30, y + 540, "기물을 선택하면 현재 위치에서 닿는 기본 공격 범위를 합쳐 보여줍니다.",
                   18, view.muted)
        view.label(x + 30, y + 502, "기물", 18, view.muted)
        if not self.pieces:
            view.label(x + 30, y + 450, "표시할 기물이 없습니다.", 18)
            return
        for index, piece in enumerate(self.pieces):
            row = self.row_bounds(index)
            selected = index == self.selected
            team_color = view.team_color(piece.team)
            view.rectangle(row, (36, 66, 91) if selected else (30, 41, 55))
            view.rectangle((row[0], row[1], row[0] + 3, row[3]), team_color)
            if selected:
                view.rectangle(row, team_color, False)
            view.label(row[0] + 15, (row[1] + row[3]) // 2, f"{piece.identifier}  {piece.name}", 18)

        piece = self.pieces[self.selected]
        grid_x = x + 322
        facing = "오른쪽 →" if piece.team is Team.BLUE else "← 왼쪽"
        column, row = piece.position
        hero = "  /  영웅화" if piece.hero else ""
        view.label(grid_x, y + 502,
                   f"{piece.identifier} {piece.name}  /  {chr(65 + column)}{row + 1}  /  정면 {facing}{hero}", 20)
        ranges = attack_ranges(self.board, piece)
        self.draw_grid(view, piece, ranges)
        for left, color, label in ((grid_x, self.attack, "공격 가능"),
                                   (grid_x + 164, self.overlap, "공격 범위 겹침")):
            view.rectangle((left, y + 86, left + 21, y + 104), color)
            view.label(left + 30, y + 95, label, 16)
        names = " · ".join(name for name, _ in ranges)
        view.label(grid_x, y + 48, f"포함된 공격  {names}" if names else "표시할 기본 공격이 없습니다.",
                   18, view.muted)

    def draw_grid(self, view, piece: Piece, ranges) -> None:
        x, top = self.x + 322, self.y + 447
        size = self.cell_size
        for column in range(self.board.columns):
            view.centered_label(x + column * size + size // 2, top + 16, chr(65 + column), 16, view.muted)
        for row in range(self.board.rows):
            bottom = top - (row + 1) * size
            view.centered_label(x - 20, bottom + size // 2, str(row + 1), 16, view.muted)
            for column in range(self.board.columns):
                cell = column, row
                left = x + column * size
                bounds = (left, bottom, left + size, bottom + size)
                count = sum(cell in cells for _, cells in ranges)
                if count:
                    fill = self.overlap if count > 1 else self.attack
                else:
                    fill = (27, 43, 58) if self.board.in_territory(Team.BLUE, cell) else (51, 37, 46)
                view.rectangle(bounds, fill)
                view.rectangle(bounds, self.border, False)
                occupant = self.board.piece_at(cell)
                if occupant is piece:
                    view.rectangle((left + 2, bottom + 2, left + size - 2, bottom + size - 2), view.accent, False)
                    view.portrait(piece, left + size // 2, bottom + 47, 54, 53)
                    view.centered_label(left + size // 2, bottom + 14, piece.identifier, 14, view.accent)
                elif occupant is not None:
                    view.label(left + 8, bottom + 14, occupant.identifier, 14, view.team_color(occupant.team))
        boundary = x + self.board.columns // 2 * size
        view.rectangle((boundary, top - self.board.rows * size, boundary + 1, top), view.accent)
