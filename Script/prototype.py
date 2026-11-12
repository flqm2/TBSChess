"""배치된 기물의 이동·액티브 스킬·턴 진행."""

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum, auto
from itertools import zip_longest
from random import choice

from board import Board
from cards import CARD_SKILLS, MAGIC_BOX, REDRAW, TARGETED_EFFECTS, CardDraw, MagicBox, Suit
from final_battle import FinalBattleRules
from movement import MovementRules
from passives import DamageResult, apply_damage, mage_bonus, protected_pieces
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


class ActionMode(Enum):
    ATTACK = auto()
    MOVE = auto()


class Prototype:
    def __init__(self, pieces: Iterable[Piece]):
        self.board = Board(pieces)
        self.movement = MovementRules(self.board)
        blue = [piece for piece in self.board.pieces if piece.team is Team.BLUE]
        red = [piece for piece in self.board.pieces if piece.team is Team.RED]
        order = (piece for pair in zip_longest(blue, red) for piece in pair if piece is not None)
        self.turns = TurnManager(order)
        self.message = f"{self.current.identifier} {self.current.name} 차례. 공격 또는 이동을 선택하세요."
        self.failed = False
        self.history: deque[str] = deque(maxlen=4)
        self.action_mode: ActionMode | None = None
        self.selected_skill: int | None = None
        self.last_cast: SkillCast | None = None
        self.winner: Team | None = None
        self.drawn = False
        self.final_battle: FinalBattleRules | None = None
        self.card_draw: CardDraw | None = None
        self.redraw_pending = False
        self.card_target_pending = False
        self.boxes: list[MagicBox] = []
        self.combat_notices: list[tuple[str, str]] = []
        self.last_stun_skips: tuple[Piece, ...] = ()
        self._revival_choices: deque[Piece] = deque()
        self._revival_cards: dict[str, Suit] = {}
        if self._enter_final_if_ready():
            self._update_survivors()
            self.turns = TurnManager(self._start_final_round([]))
            self.message = f"최종전 시작. {self.current.identifier} {self.current.name} 차례."
        self._draw_turn_card()

    @property
    def is_over(self) -> bool:
        return self.winner is not None or self.drawn

    @property
    def result_label(self) -> str:
        if self.drawn:
            return "무승부"
        return "승리" if self.winner is Team.BLUE else "패배"

    @property
    def current(self) -> Piece:
        return self.turns.current

    @property
    def legal_moves(self) -> tuple[tuple[int, int], ...]:
        return self.movement.destinations(self.current)

    @property
    def move_preview(self) -> bool:
        return self.action_mode is ActionMode.MOVE

    @property
    def skills(self) -> tuple[Skill, ...]:
        if self.card_draw is not None:
            throw = CARD_SKILLS[self.card_draw.suit][int(self.current.hero)]
            return throw, REDRAW, MAGIC_BOX
        entry = SKILLS.get(self.current.character_id)
        if entry is None:
            return ()
        normal, upgraded, hero_skill = entry
        return (*(upgraded if self.current.hero else normal), hero_skill)

    @property
    def skill_preview(self) -> tuple[Cell, ...]:
        if self.action_mode is not ActionMode.ATTACK or self.selected_skill is None:
            return ()
        return self.skills[self.selected_skill].cells(self.board, self.current)

    @property
    def mage_preview(self) -> tuple[tuple[Cell, int], ...]:
        if self.current.character_id != "mage":
            return ()
        cells = self.skill_preview
        return tuple((piece.position, mage_bonus(self.current, piece.position))
                     for piece in self.board.living_pieces
                     if piece.team is not self.current.team and piece.position in cells)

    @property
    def revival_pending(self) -> Piece | None:
        return self._revival_choices[0] if self._revival_choices else None

    def choose_revival_card(self, suit: Suit) -> None:
        if not self._revival_choices:
            return
        piece = self._revival_choices.popleft()
        if piece is self.current:
            self.card_draw = CardDraw(suit)
        else:
            self._revival_cards[piece.identifier] = suit

    def skill_unavailable(self, slot: int) -> str | None:
        if self.is_over:
            return "경기 종료"
        if self.revival_pending is not None:
            return "부활 카드 선택 중"
        if self.redraw_pending and not (slot == 0 and self.card_target_pending):
            return "새 카드 발동 중"
        if slot == 2:
            if not self.current.hero:
                return "영웅화 후 사용 가능"
            used = self.current.hero_skill_round
            if used is not None and self.turns.round <= used + 1:
                return f"{used + 2}라운드부터 사용 가능"
        return None

    def open_movement(self) -> None:
        if self.is_over or self.redraw_pending or self.revival_pending is not None:
            return
        if not self.legal_moves:
            self.message, self.failed = "이동할 수 있는 칸이 없습니다.", True
            return
        self.selected_skill = None
        self.card_target_pending = False
        self.action_mode = ActionMode.MOVE
        self.message, self.failed = "보드에서 초록색 칸을 클릭하세요.", False

    def open_attack(self) -> None:
        if (self.is_over or self.revival_pending is not None
                or self.action_mode is ActionMode.ATTACK):
            return
        if self.redraw_pending and not self.card_target_pending:
            return
        self.action_mode = ActionMode.ATTACK
        self.message = ("파란 칸에서 클로버의 대상을 고르세요."
                        if self.card_target_pending else "스킬을 선택하세요.")
        self.failed = False

    def back_to_actions(self) -> None:
        if self.is_over or self.action_mode is None:
            return
        if self.redraw_pending and not self.card_target_pending:
            return
        self.action_mode = None
        if self.redraw_pending:
            self.message = "뽑은 카드의 대상을 고르려면 공격을 선택하세요."
        else:
            self.selected_skill = None
            self.card_target_pending = False
            self.message = "공격 또는 이동을 선택하세요."
        self.failed = False

    def click_skill(self, slot: int) -> bool:
        skills = self.skills
        if not 0 <= slot < len(skills):
            return False
        if self.redraw_pending:
            return False
        reason = self.skill_unavailable(slot)
        if reason is not None:
            self.message, self.failed = reason, True
            return False
        skill = skills[slot]
        cells = skill.cells(self.board, self.current)
        self.action_mode = ActionMode.ATTACK
        if not cells:
            self.selected_skill = None
            self.card_target_pending = False
            self.message = ("클로버로 선택할 대상이 없습니다." if skill.effect in TARGETED_EFFECTS
                            else "보드 안에 스킬 범위가 없습니다.")
            self.failed = True
            return False
        if self.selected_skill != slot:
            self.selected_skill = slot
            self.card_target_pending = False
            self.message, self.failed = f"{skill.name} 범위. 같은 스킬 버튼을 다시 클릭해 발동하세요.", False
            return False

        if skill.effect is Effect.REDRAW:
            self.card_draw = CardDraw(choice(tuple(Suit)), redraw=True)
            self.redraw_pending = True
            self.selected_skill = None
            self.message = "새 카드를 뽑습니다."
            return True
        if skill.effect in TARGETED_EFFECTS:
            self._request_card_target()
            return False
        self._cast(slot, skill, cells)
        return True

    def _draw_turn_card(self) -> None:
        self.card_draw = None
        if self.current.character_id != "cardmaster" or self.current in self._revival_choices:
            return
        suit = self._revival_cards.pop(self.current.identifier, None)
        self.card_draw = CardDraw(suit if suit is not None else choice(tuple(Suit)))
        self.message = f"{self.current.identifier} 카드술사 · {self.card_draw.suit.label} A"

    def _request_card_target(self) -> None:
        self.card_target_pending = True
        self.selected_skill = 0
        self.message, self.failed = "파란 칸에서 클로버의 대상을 고르세요.", False

    def resolve_redraw(self) -> None:
        if not self.redraw_pending or self.card_target_pending:
            return
        skill = self.skills[0]
        cells = skill.cells(self.board, self.current)
        if skill.effect in TARGETED_EFFECTS and cells:
            self._request_card_target()
            return
        self._cast(0, skill, cells)

    def choose_card_target(self, cell: Cell) -> bool:
        if not self.card_target_pending:
            return False
        if cell not in self.skill_preview:
            self.message, self.failed = "파란 칸에 있는 유효한 대상을 선택하세요.", True
            return False
        self._cast(0, self.skills[0], (cell,))
        return True

    def _cast(self, slot: int, skill: Skill, cells: tuple[Cell, ...]) -> None:
        caster = self.current
        self.last_cast = self._apply_skill(caster, skill, cells)
        if slot == 2:
            caster.hero_skill_round = self.turns.round
        hits = self.last_cast.hits
        detail = f"{len(hits)}기 피격" if hits else "명중 없음"
        if skill.effect is Effect.EMPOWER:
            detail = "다음 공격 표식 강화"
        elif skill.effect is Effect.HEAL_ALLIES:
            detail = "인접 아군 회복"
        elif skill.effect is Effect.HEAL_STRIKE:
            detail = f"자기 회복 · {detail}"
        elif skill.effect in TARGETED_EFFECTS:
            detail = "위치 변경" if cells else "대상 없음"
        elif skill.effect is Effect.MAGIC_BOX:
            detail = f"상자 설치 · {detail}"
        action = skill.name
        if slot == 0 and self.card_draw is not None:
            action = f"{'카드 뽑기 → ' if self.redraw_pending else ''}{self.card_draw.suit.label} 카드 던지기"
        self._finish_action(f"{action} · {detail}", self.last_cast)

    def _apply_skill(self, caster: Piece, skill: Skill, cells: tuple[Cell, ...]) -> SkillCast:
        if skill.effect is Effect.EMPOWER:
            caster.empowered_mark = True
            return SkillCast(cells, ())
        if skill.effect in TARGETED_EFFECTS:
            if cells:
                if skill.effect is Effect.SWAP:
                    ally = self.board.piece_at(cells[0])
                    ally.position = caster.position
                caster.position = cells[0]
            return SkillCast(cells, ())
        if skill.effect is Effect.MAGIC_BOX:
            self.boxes = [box for box in self.boxes if box.owner is not caster]
            box = MagicBox(caster, cells[0], skill.damage)
            self.boxes.append(box)
            hit = self._box_hit(box)
            return SkillCast(cells, (hit,) if hit else ())
        if skill.effect is Effect.HEAL_STRIKE:
            self._heal(caster)
        random_target = skill.effect is Effect.RANDOM_MARK
        if random_target:
            cells = (choice(cells),)
        hits = []
        forward = caster.facing
        targets = tuple(self.board.piece_at(cell) for cell in cells)
        protected = protected_pieces(self.board)
        for target in targets:
            if skill.effect is Effect.HEAL_ALLIES:
                if target is not None and target.team is caster.team and target is not caster:
                    self._heal(target)
                continue
            if target is None or (target.team is caster.team and not random_target):
                continue
            marks = 1 + int(caster.empowered_mark) if skill.effect in (Effect.MARK, Effect.RANDOM_MARK) else 0
            result = self._hit(caster, target, skill.damage, protected, marks)
            if result.blocked:
                continue
            if marks:
                caster.empowered_mark = False
            if target.current_hp > 0 and not result.revived:
                if skill.effect is Effect.STUN:
                    if self.final_battle is None:
                        target.stunned = True
                    elif not self.final_battle.apply_stun(target):
                        self.combat_notices.append(("기절 면역", f"{target.identifier} {target.name}"))
                elif skill.effect is Effect.PULL:
                    x, y = target.position
                    self._shift_piece(target, (x - forward, y))
            hits.append(Hit(target.identifier, target.position, result.damage))
        if skill.effect is Effect.RETREAT:
            x, y = caster.position
            self._shift_piece(caster, (x - forward, y))
        return SkillCast(cells, tuple(hits))

    @staticmethod
    def _heal(piece: Piece) -> None:
        piece.current_hp = min(piece.max_hp, piece.current_hp + piece.max_hp // 10)

    def _box_hit(self, box: MagicBox) -> Hit | None:
        target = self.board.piece_at(box.cell)
        if target is None or target.team is box.owner.team:
            return None
        result = self._hit(box.owner, target, box.damage, protected_pieces(self.board))
        return None if result.blocked else Hit(target.identifier, box.cell, result.damage)

    def _hit(self, caster: Piece, target: Piece, damage: int, protected: set[str], marks: int = 0) -> DamageResult:
        result = apply_damage(self.board, caster, target, damage, protected, marks)
        if result.notice:
            self.combat_notices.append(("패시브", result.notice))
        if result.revived:
            self._revival_choices.append(target)
        return result

    def _advance_boxes(self) -> SkillCast | None:
        remaining = []
        hits = []
        moved = []
        for box in self.boxes:
            if box.owner.current_hp == 0:
                continue
            if box.owner.team is not self.current.team:
                x, y = box.cell
                x += 1 if box.owner.team is Team.BLUE else -1
                if not self.board.in_territory(self.current.team, (x, y)):
                    continue
                box.cell = x, y
                box.damage += 10
                moved.append(box.cell)
                hit = self._box_hit(box)
                if hit is not None:
                    hits.append(hit)
                if x in (0, self.board.columns - 1):
                    continue
            remaining.append(box)
        self.boxes = remaining
        return SkillCast(tuple(moved), tuple(hits)) if moved else None

    def _shift_piece(self, piece: Piece, cell: Cell) -> None:
        if self.board.allows_movement(piece.team, cell) and self.board.piece_at(cell) is None:
            piece.position = cell

    def _enter_final_if_ready(self) -> bool:
        if self.final_battle is not None or self.is_over:
            return False
        living = self.board.living_pieces
        if len(living) != 2 or living[0].team is living[1].team:
            return False
        blue, red = living if living[0].team is Team.BLUE else living[::-1]
        self.final_battle = FinalBattleRules(blue, red)
        self.board.boundary_open = True
        self.board.refresh_facing()
        self.combat_notices.append(("최종전", "중앙 경계가 해제됩니다."))
        return True

    def _start_final_round(self, casts: list[SkillCast]) -> tuple[Piece, ...]:
        order, damage = self.final_battle.start_round()
        self.winner = self.final_battle.winner
        self.drawn = self.final_battle.drawn
        if damage:
            hits = tuple(Hit(piece.identifier, piece.position, lost) for piece, lost in damage)
            casts.append(SkillCast((), hits))
            self.combat_notices.append(("서든데스", "양 진영에 최대 체력의 10% 피해"))
        return order

    def _finish_action(self, action: str, cast: SkillCast | None = None) -> None:
        piece = self.current
        self.history.appendleft(f"R{self.turns.round:02}  {piece.identifier} {piece.name}  {action}")
        self.selected_skill = None
        self.action_mode = None
        self.redraw_pending = False
        self.card_target_pending = False
        self.failed = False
        heroes = self._update_survivors()
        casts = [cast] if cast is not None else []
        restart_round = self._enter_final_if_ready()
        self.board.refresh_facing()
        stun_skips = []
        while not self.is_over:
            next_round = (lambda: self._start_final_round(casts)) if self.final_battle else None
            for skipped in self.turns.advance(next_round, restart_round=restart_round):
                stun_skips.append(skipped)
                self.combat_notices.append(("기절", f"{skipped.identifier} {skipped.name} · 차례를 건너뜁니다."))
            if self.is_over:
                break
            box_cast = self._advance_boxes()
            if box_cast is not None:
                casts.append(box_cast)
                if box_cast.hits:
                    heroes.extend(self._update_survivors())
            restart_round = self._enter_final_if_ready()
            if not restart_round and self.current.current_hp > 0:
                break
        self.last_stun_skips = tuple(stun_skips)
        if casts:
            self.last_cast = SkillCast(
                tuple(dict.fromkeys(cell for result in casts for cell in result.cells)),
                tuple(hit for result in casts for hit in result.hits),
            )
        summary = " · ".join((action, *heroes))
        if self.is_over:
            self.card_draw = None
            result = f"{self.winner.value} 승리" if self.winner else self.result_label
            self.message = f"{summary}. {result}."
        else:
            self.message = f"{summary}. {self.current.identifier} {self.current.name} 차례."
            self._draw_turn_card()

    def _update_survivors(self) -> list[str]:
        living = self.board.living_pieces
        teams = {p.team for p in living}
        if not teams:
            self.drawn = True
            return []
        if len(teams) == 1:
            self.winner = next(iter(teams))
            return []
        heroes = []
        for team in Team:
            survivors = [p for p in living if p.team is team]
            has_fallen = any(p.team is team and p.current_hp == 0 for p in self.board.pieces)
            if len(survivors) != 1 or (len(living) != 2 and not has_fallen):
                continue
            hero = survivors[0]
            if not hero.hero:
                hero.hero = True
                old_max = hero.max_hp
                hero.max_hp = old_max * 13 // 10
                hero.current_hp = min(hero.max_hp, (65 * hero.current_hp + 13 * old_max) // 50)
                heroes.append(f"{hero.identifier} 영웅화")
        return heroes

    def try_move(self, destination: tuple[int, int] | None) -> bool:
        if self.is_over or self.redraw_pending or self.revival_pending is not None:
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
        if not self.is_over and not self.redraw_pending and self.revival_pending is None:
            self._finish_action("턴 넘김")

    @staticmethod
    def cell_name(cell: tuple[int, int]) -> str:
        return f"{chr(ord('A') + cell[0])}{cell[1] + 1}"

