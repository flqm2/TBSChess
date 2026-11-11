"""배치된 기물의 이동·액티브 스킬·턴 진행."""

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import zip_longest
from random import choice

from board import Board
from movement import MovementRules
from piece import Piece, Team
from skills import Cell, Effect, SKILLS, Skill
from turn_manager import TurnManager


@dataclass(frozen=True)
class Hit:
    piece_id: str
    cell: Cell
    damage: int


@dataclass(frozen=True)
class SkillCast:
    cells: tuple[Cell, ...]
    hits: tuple[Hit, ...]


class Prototype:
    def __init__(self, pieces: Iterable[Piece]):
        self.board = Board(pieces)
        self.movement = MovementRules(self.board)
        blue = [piece for piece in self.board.pieces if piece.team is Team.BLUE]
        red = [piece for piece in self.board.pieces if piece.team is Team.RED]
        order = (piece for pair in zip_longest(blue, red) for piece in pair if piece is not None)
        self.turns = TurnManager(order)
        self.message = f"{self.current.identifier} {self.current.name} 차례. 이동 또는 스킬을 선택하세요."
        self.failed = False
        self.history: deque[str] = deque(maxlen=4)
        self.move_preview = False
        self.selected_skill: int | None = None
        self.last_cast: SkillCast | None = None
        self.winner: Team | None = None

    @property
    def current(self) -> Piece:
        return self.turns.current

    @property
    def legal_moves(self) -> tuple[tuple[int, int], ...]:
        return self.movement.destinations(self.current)

    @property
    def skills(self) -> tuple[Skill, ...]:
        entry = SKILLS.get(self.current.character_id)
        if entry is None:
            return ()
        normal, upgraded, hero_skill = entry
        return (*(upgraded if self.current.hero else normal), hero_skill)

    @property
    def skill_preview(self) -> tuple[Cell, ...]:
        if self.selected_skill is None:
            return ()
        return self.skills[self.selected_skill].cells(self.board, self.current)

    def skill_unavailable(self, slot: int) -> str | None:
        if self.winner is not None:
            return "경기 종료"
        if slot == 2:
            if not self.current.hero:
                return "영웅화 후 사용 가능"
            used = self.current.hero_skill_round
            if used is not None and self.turns.round <= used + 1:
                return f"{used + 2}라운드부터 사용 가능"
        return None

    def open_movement(self) -> None:
        if self.winner is not None:
            return
        if not self.legal_moves:
            self.message, self.failed = "이동할 수 있는 칸이 없습니다.", True
            return
        self.selected_skill = None
        self.move_preview = True
        self.message, self.failed = "표시된 칸을 클릭하면 이동합니다.", False

    def click_skill(self, slot: int) -> bool:
        skills = self.skills
        if not 0 <= slot < len(skills):
            return False
        reason = self.skill_unavailable(slot)
        if reason is not None:
            self.message, self.failed = reason, True
            return False
        skill = skills[slot]
        cells = skill.cells(self.board, self.current)
        self.move_preview = False
        if not cells:
            self.selected_skill = None
            self.message, self.failed = "보드 안에 스킬 범위가 없습니다.", True
            return False
        if self.selected_skill != slot:
            self.selected_skill = slot
            self.message, self.failed = f"{skill.name} 범위. 같은 스킬 버튼을 다시 클릭해 발동하세요.", False
            return False

        caster = self.current
        self.last_cast = self._apply_skill(caster, skill, cells)
        if slot == 2:
            caster.hero_skill_round = self.turns.round
        hits = self.last_cast.hits
        detail = f"{len(hits)}기 피격" if hits else "명중 없음"
        if skill.effect is Effect.EMPOWER:
            detail = "다음 공격 표식 강화"
        self._finish_action(f"{skill.name} · {detail}")
        return True

    def _apply_skill(self, caster: Piece, skill: Skill, cells: tuple[Cell, ...]) -> SkillCast:
        if skill.effect is Effect.EMPOWER:
            caster.empowered_mark = True
            return SkillCast(cells, ())
        random_target = skill.effect is Effect.RANDOM_MARK
        if random_target:
            cells = (choice(cells),)
        hits = []
        forward = 1 if caster.team is Team.BLUE else -1
        targets = tuple(self.board.piece_at(cell) for cell in cells)
        for target in targets:
            if target is None or (target.team is caster.team and not random_target):
                continue
            damage = min(target.current_hp, skill.damage)
            target.current_hp -= damage
            if skill.effect in (Effect.MARK, Effect.RANDOM_MARK):
                marks = target.marks.get(caster.identifier, 0)
                target.marks[caster.identifier] = marks + 1 + int(caster.empowered_mark)
                caster.empowered_mark = False
            if target.current_hp > 0:
                if skill.effect is Effect.STUN and target not in self.turns.acted:
                    target.stunned_round = self.turns.round
                elif skill.effect is Effect.PULL:
                    x, y = target.position
                    self._shift_piece(target, (x - forward, y))
            hits.append(Hit(target.identifier, target.position, damage))
        if skill.effect is Effect.RETREAT:
            x, y = caster.position
            self._shift_piece(caster, (x - forward, y))
        return SkillCast(cells, tuple(hits))

    def _shift_piece(self, piece: Piece, cell: Cell) -> None:
        if self.board.in_territory(piece.team, cell) and self.board.piece_at(cell) is None:
            piece.position = cell

    def _finish_action(self, action: str) -> None:
        piece = self.current
        self.history.appendleft(f"R{self.turns.round:02}  {piece.identifier} {piece.name}  {action}")
        self.selected_skill = None
        self.move_preview = False
        self.failed = False
        living = self.board.living_pieces
        teams = {p.team for p in living}
        if len(teams) == 1:
            self.winner = next(iter(teams))
            self.message = f"{action}. {'승리' if self.winner is Team.BLUE else '패배'}. {self.winner.value} 승리."
            return
        heroes = []
        for team in Team:
            survivors = [p for p in living if p.team is team]
            if len(survivors) != 1 or not any(p.team is team and p.current_hp == 0 for p in self.board.pieces):
                continue
            hero = survivors[0]
            if not hero.hero:
                hero.hero = True
                hero.max_hp = hero.max_hp * 13 // 10
                hero.current_hp = min(hero.max_hp, hero.current_hp + hero.max_hp // 5)
                heroes.append(f"{hero.identifier} 영웅화")
        self.turns.advance()
        summary = " · ".join((action, *heroes))
        self.message = f"{summary}. {self.current.identifier} {self.current.name} 차례."

    def try_move(self, destination: tuple[int, int] | None) -> bool:
        if self.winner is not None:
            return False
        piece = self.current
        reason = self.movement.rejection(piece, destination)
        if reason is not None:
            self.message = reason
            self.failed = True
            return False
        old = piece.position
        piece.position = destination
        self._finish_action(f"이동 {self.cell_name(old)} → {self.cell_name(destination)}")
        return True

    def skip_turn(self) -> None:
        if self.winner is None:
            self._finish_action("턴 넘김")

    @staticmethod
    def cell_name(cell: tuple[int, int]) -> str:
        return f"{chr(ord('A') + cell[0])}{cell[1] + 1}"

