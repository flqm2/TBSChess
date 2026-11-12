"""패시브 설명과 공통 피해 판정."""

from dataclasses import dataclass

from board import Board
from piece import Job, Piece
from skills import Cell


DESCRIPTIONS = {
    "slayer": ("체력이 50% 미만으로 남으면", "최대 체력의 30%를 회복합니다.", "경기당 1회"),
    "warrior": ("주변 8칸에 있는 아군이", "받는 공격 피해를 10% 줄입니다."),
    "archer": ("체력이 30% 미만으로 남으면", "다음 공격을 막는 보호막을 얻습니다.", "경기당 1회"),
    "mage": ("대상까지 가로·세로 거리 1칸당", "스킬 피해가 5% 증가합니다."),
    "assassin": ("같은 대상의 표식 3개로 처치합니다.", "다른 대상을 맞히면", "이전 대상의 표식이 사라집니다."),
    "cardmaster": ("체력이 0이면 최대 체력의 20%로", "부활하고 카드 한 장을 고릅니다.", "경기당 1회"),
}


@dataclass(frozen=True)
class DamageResult:
    damage: int
    notice: str = ""
    blocked: bool = False
    revived: bool = False


def aura_cells(board: Board, warrior: Piece) -> tuple[Cell, ...]:
    x, y = warrior.position
    cells = ((x + dx, y + dy) for dx, dy in Job.JOKER.directions)
    return tuple(cell for cell in cells if board.contains(cell))


def protected_pieces(board: Board) -> set[str]:
    living = board.living_pieces
    protected = set()
    for warrior in living:
        if warrior.character_id == "warrior":
            cells = aura_cells(board, warrior)
            protected.update(piece.identifier for piece in living
                             if piece.team is warrior.team and piece.position in cells)
    return protected


def mage_bonus(caster: Piece, cell: Cell) -> int:
    if caster.character_id != "mage":
        return 0
    x, y = caster.position
    return 5 * (abs(cell[0] - x) + abs(cell[1] - y))


def attack_damage(caster: Piece, target: Piece, base_damage: int, protected: set[str]) -> int:
    reduction = 90 if target.identifier in protected else 100
    return base_damage * (100 + mage_bonus(caster, target.position)) * reduction // 10000


def apply_damage(board: Board, caster: Piece, target: Piece, base_damage: int,
                 protected: set[str], marks: int = 0) -> DamageResult:
    name = f"{target.identifier} {target.name}"
    if target.shield:
        target.shield = False
        return DamageResult(0, f"{name} · 보호막으로 공격 차단", blocked=True)

    damage = attack_damage(caster, target, base_damage, protected)
    before = target.current_hp
    target.current_hp = max(0, before - damage)
    executed = False
    if marks:
        for piece in board.pieces:
            if piece is not target:
                piece.marks.pop(caster.identifier, None)
        if target.current_hp > 0:
            count = target.marks.get(caster.identifier, 0) + marks
            target.marks[caster.identifier] = count
            if count >= 3:
                target.current_hp = 0
                executed = True
    lost = before - target.current_hp
    if target.current_hp == 0:
        target.marks.clear()
        if target.character_id == "cardmaster" and not target.passive_used:
            target.passive_used = True
            target.current_hp = max(1, target.max_hp // 5)
            return DamageResult(lost, f"{name} · 부활, 체력 {target.current_hp} 회복", revived=True)
        if executed:
            return DamageResult(lost, f"{name} · 표식 3개로 처치")
    elif not target.passive_used:
        if target.character_id == "slayer" and target.current_hp * 2 < target.max_hp:
            target.passive_used = True
            healed = target.max_hp * 3 // 10
            target.current_hp += healed
            return DamageResult(lost, f"{name} · 체력 {healed} 회복")
        if target.character_id == "archer" and target.current_hp * 10 < target.max_hp * 3:
            target.passive_used = True
            target.shield = True
            return DamageResult(lost, f"{name} · 보호막 획득")
    return DamageResult(lost)
