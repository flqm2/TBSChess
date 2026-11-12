"""현재 기물별 기본 공격 범위를 보여주는 독립 도움말 창."""

import tkinter as tk
from math import ceil
from pathlib import Path

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
    width, height = 800, 512
    grid_x, grid_y, cell = 230, 152, 66
    background = "#131922"
    text = "#e9edf1"
    muted = "#aab7c7"
    accent = "#f3d384"
    attack = "#244f76"
    overlap = "#2d709e"

    def __init__(self, board: Board, current: Piece):
        self.board = board
        self.pieces = board.living_pieces
        self.window = tk.Tk(className="TBSChessHelp")
        self.window.title("전략 RPG 체스 · 전투 도움말")
        self.window.geometry(f"{self.width}x{self.height}")
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind("<Escape>", lambda _: self.close())
        self.canvas = tk.Canvas(self.window, width=self.width, height=self.height,
                                bg=self.background, highlightthickness=0)
        self.canvas.pack()
        self.roster = tk.Listbox(self.window, font=("맑은 고딕", 12), bd=0, highlightthickness=0,
                                 bg="#202b39", fg=self.text, selectbackground="#244f76",
                                 selectforeground=self.text, activestyle="none", exportselection=False)
        self.roster.place(x=26, y=self.grid_y, width=168, height=self.cell * 4)
        for piece in self.pieces:
            self.roster.insert(tk.END, f"  {piece.identifier}  {piece.name}")
        index = next((i for i, piece in enumerate(self.pieces) if piece is current), 0)
        self.roster.selection_set(index)
        self.roster.activate(index)
        self.roster.bind("<<ListboxSelect>>", self.draw)
        self.roster.focus_set()
        self.portrait = None
        self.draw()
        self.window.update_idletasks()

    @property
    def is_open(self) -> bool:
        return self.window is not None

    def close(self) -> None:
        if self.window is not None:
            window, self.window = self.window, None
            window.destroy()

    def update(self) -> None:
        if self.window is not None:
            self.window.update()

    def label(self, x, y, text, size=12, color=None):
        self.canvas.create_text(x, y, text=text, fill=color or self.text, anchor="w",
                                font=("맑은 고딕", size))

    def draw(self, _event=None) -> None:
        selection = self.roster.curselection()
        if not selection:
            return
        piece = self.pieces[selection[0]]
        ranges = attack_ranges(self.board, piece)
        self.canvas.delete("all")
        self.label(26, 33, "전투 도움말", 22)
        self.label(26, 69, "기물을 선택하면 현재 위치에서 닿는 기본 공격 범위를 합쳐 보여줍니다.", 12, self.muted)
        facing = "오른쪽 →" if piece.team is Team.BLUE else "← 왼쪽"
        x, y = piece.position
        state = "  /  영웅화" if piece.hero else ""
        self.label(self.grid_x, 103, f"{piece.identifier} {piece.name}  /  {chr(65 + x)}{y + 1}  /  정면 {facing}{state}", 14)
        self.label(26, 127, "기물", 12, self.muted)

        for column in range(self.board.columns):
            self.label(self.grid_x + column * self.cell + 28, 135, chr(65 + column), 11, self.muted)
        for row in range(self.board.rows):
            self.label(209, self.grid_y + row * self.cell + 33, str(row + 1), 11, self.muted)
            for column in range(self.board.columns):
                cell = column, row
                left = self.grid_x + column * self.cell
                top = self.grid_y + row * self.cell
                count = sum(cell in cells for _, cells in ranges)
                fill = "#1b2b3a" if column < 4 else "#33252e"
                if count:
                    fill = self.overlap if count > 1 else self.attack
                self.canvas.create_rectangle(left, top, left + self.cell, top + self.cell,
                                             fill=fill, outline="#526170")
                occupant = self.board.piece_at(cell)
                if occupant is not None and occupant is not piece:
                    self.label(left + 7, top + 50, occupant.identifier, 11, self.muted)
                if cell == piece.position:
                    self.draw_caster(piece, left, top)

        boundary = self.grid_x + 4 * self.cell
        self.canvas.create_line(boundary, self.grid_y, boundary, self.grid_y + 4 * self.cell,
                                fill=self.accent, width=2)
        self.canvas.create_rectangle(230, 435, 248, 451, fill=self.attack, outline="")
        self.label(255, 443, "공격 가능", 11)
        self.canvas.create_rectangle(366, 435, 384, 451, fill=self.overlap, outline="")
        self.label(391, 443, "공격 범위 겹침", 11)
        names = " · ".join(name for name, _ in ranges)
        self.label(230, 475, f"포함된 공격  {names}" if names else "표시할 기본 공격이 없습니다.", 12, self.muted)

    def draw_caster(self, piece: Piece, left: int, top: int) -> None:
        self.canvas.create_rectangle(left + 1, top + 1, left + 65, top + 65, outline=self.accent, width=2)
        path = Path(__file__).resolve().parents[1] / "Resource" / piece.image_name
        sprite = tk.PhotoImage(master=self.window, file=str(path))
        scale = max(1, ceil(max(sprite.width(), sprite.height()) / 42))
        self.portrait = sprite.subsample(scale, scale)
        self.canvas.create_image(left + 33, top + 25, image=self.portrait)
        self.label(left + 7, top + 51, piece.identifier, 11, self.accent)
