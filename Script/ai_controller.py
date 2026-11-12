"""노멀 난이도의 행동 평가와 홍팀 차례 실행."""

from copy import copy
from dataclasses import dataclass

from board import Board
from cards import CARD_SKILLS, MAGIC_BOX, Suit
from passives import attack_damage, protected_pieces
from piece import Piece, Team
from prototype import Prototype
from skills import Cell, Effect, SKILLS, Skill


@dataclass(frozen=True)
class AIAction:
    skill_slot: int | None = None
    destination: Cell | None = None


class NormalPolicy:
    label = "노멀"

    def choose(self, battle: Prototype) -> AIAction:
        piece = battle.current
        attacks = tuple((slot, skill) for slot, skill in enumerate(battle.skills)
                        if skill.damage > 0 and battle.skill_unavailable(slot) is None)
        candidates = []
        for slot, skill in attacks:
            score = self.attack_score(battle, battle.board, piece, skill)
            if score is not None:
                candidates.append((score, slot))
        if candidates:
            _, slot = max(candidates, key=lambda candidate: candidate[0])
            return AIAction(skill_slot=slot)

        moves = battle.legal_moves
        if not moves or self.risk(battle, battle.board, piece) == 0:
            return AIAction()

        def move_score(cell: Cell) -> tuple[float, float, int]:
            projected = Board(copy(other) for other in battle.board.living_pieces)
            projected.boundary_open = battle.board.boundary_open
            mover = projected.piece_at(piece.position)
            mover.position = cell
            projected.refresh_facing()
            risk = self.risk(battle, projected, mover)
            attack = max((self.attack_score(battle, projected, mover, skill) or 0 for _, skill in attacks),
                         default=0)
            distance = min(abs(cell[0] - other.position[0]) + abs(cell[1] - other.position[1])
                           for other in projected.living_pieces if other.team is not mover.team)
            return -risk, attack, -distance

        return AIAction(destination=max(moves, key=move_score))

    def attack_score(self, battle: Prototype, board: Board, caster: Piece, skill: Skill) -> float | None:
        cells = skill.cells(board, caster)
        targets = tuple(board.piece_at(cell) for cell in cells)
        enemies = tuple(target for target in targets if target is not None and target.team is not caster.team)
        if not enemies:
            return None
        protected = protected_pieces(board)
        score = sum(self.hit_score(battle, caster, target, skill, protected) for target in enemies)
        if skill.effect is Effect.RANDOM_MARK:
            allies = (target for target in targets if target is not None and target.team is caster.team)
            score -= sum(self.hit_score(battle, caster, target, skill, protected) for target in allies)
            score /= len(cells)
        return score

    def risk(self, battle: Prototype, board: Board, piece: Piece) -> float:
        protected = protected_pieces(board)
        acted = {other.identifier for other in battle.turns.acted}
        score = 0.0
        for enemy in board.living_pieces:
            if enemy.team is piece.team or enemy.stunned:
                continue
            round_number = battle.turns.round + int(enemy.identifier in acted)
            threats = []
            for skill in self.known_attacks(enemy, round_number):
                cells = skill.cells(board, enemy)
                if skill.damage > 0 and piece.position in cells:
                    value = self.hit_score(battle, enemy, piece, skill, protected)
                    threats.append(value / len(cells) if skill.effect is Effect.RANDOM_MARK else value)
            score += max(threats, default=0)
        for box in battle.boxes:
            if (box.owner.team is not piece.team and box.owner.current_hp > 0
                    and piece.position == box.next_cell()
                    and board.in_territory(piece.team, piece.position)):
                score += box.damage + 10
        return score

    @staticmethod
    def known_attacks(piece: Piece, round_number: int) -> tuple[Skill, ...]:
        if piece.character_id == "cardmaster":
            # 다음 카드의 실제 값은 아직 알 수 없으므로 가능한 공격 범위를 사용한다.
            cards = tuple(variants[int(piece.hero)] for variants in CARD_SKILLS.values())
            return cards + ((MAGIC_BOX,) if piece.hero_skill_available(round_number) else ())
        entry = SKILLS.get(piece.character_id)
        if entry is None:
            return ()
        basic = entry[int(piece.hero)]
        return (*basic, entry[2]) if piece.hero_skill_available(round_number) else basic

    @staticmethod
    def hit_score(battle: Prototype, caster: Piece, target: Piece, skill: Skill, protected: set[str]) -> int:
        if target.shield:
            return 12
        damage = attack_damage(caster, target, skill.damage, protected)
        marks = 0
        if skill.effect in (Effect.MARK, Effect.RANDOM_MARK):
            marks = target.marks.get(caster.identifier, 0) + 1 + int(caster.empowered_mark)
        if damage >= target.current_hp or marks >= 3:
            if target.character_id == "cardmaster" and not target.passive_used:
                return target.current_hp + 25
            return target.current_hp + 80
        score = damage + (8 * marks)
        if skill.effect is Effect.STUN and not target.stunned:
            if battle.final_battle is None or not battle.final_battle.stun_immune(target):
                score += 24
        return score


class AIController:
    action_delay = 0.55

    def __init__(self, policy: NormalPolicy):
        self.policy = policy
        self._turn = None
        self._action = AIAction()
        self._ready_at = 0.0

    @staticmethod
    def owns_turn(battle: Prototype) -> bool:
        return not battle.is_over and battle.current.team is Team.RED

    def update(self, battle: Prototype, now: float) -> None:
        if battle.revival_pending is not None:
            if battle.revival_pending.team is Team.RED:
                battle.choose_revival_card(Suit.DIAMOND)
            return
        if not self.owns_turn(battle):
            return

        turn = battle, battle.turns.round, battle.turns.index
        if turn != self._turn:
            self._turn = turn
            self._action = self.policy.choose(battle)
            self._ready_at = now + self.action_delay
            if self._action.skill_slot is not None:
                battle.open_attack()
                battle.click_skill(self._action.skill_slot)
            elif self._action.destination is not None:
                battle.open_movement()
            return
        if now < self._ready_at:
            return
        if self._action.skill_slot is not None:
            if battle.click_skill(self._action.skill_slot):
                return
        elif self._action.destination is not None:
            if battle.try_move(self._action.destination):
                return
        battle.skip_turn()
