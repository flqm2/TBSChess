"""공통 주사위 이미지 위에 눈과 선후공 결과를 그린다."""

from pathlib import Path
from time import monotonic

import pico2d

from initiative import InitiativeRoll
from piece import Team


class DiceView:
    tie_seconds = 0.7
    result_seconds = 1.25
    pips = (
        ((0, 0),),
        ((-1, 1), (1, -1)),
        ((-1, 1), (0, 0), (1, -1)),
        ((-1, 1), (1, 1), (-1, -1), (1, -1)),
        ((-1, 1), (1, 1), (0, 0), (-1, -1), (1, -1)),
        ((-1, 1), (1, 1), (-1, 0), (1, 0), (-1, -1), (1, -1)),
    )

    def __init__(self, path: Path):
        self.image = pico2d.load_image(str(path))
        self.roll: InitiativeRoll | None = None
        self.started = 0.0
        self.delay = 0.0

    def showing(self, roll: InitiativeRoll | None, delay: float = 0.0) -> bool:
        if roll is not self.roll:
            self.roll = roll
            self.started = monotonic()
            self.delay = delay
        if roll is None:
            return False
        return monotonic() - self.started < self.delay + self.tie_seconds * (len(roll.attempts) - 1) + self.result_seconds

    def draw_face(self, x: int, y: int, size: int, value: int) -> None:
        self.image.draw(x, y, size, size)
        step = round(size * 0.22)
        radius = max(2, round(size * 0.062))
        for dx, dy in self.pips[value - 1]:
            pico2d.draw_circle(x + dx * step, y + dy * step, radius, 34, 39, 50, filled=True)

    def draw_announcement(self, view) -> None:
        elapsed = monotonic() - self.started - self.delay
        if elapsed < 0 or self.roll is None:
            return
        attempts = self.roll.attempts
        index = min(int(elapsed / self.tie_seconds), len(attempts) - 1)
        blue, red = attempts[index]
        x, y = view.width // 2, view.height // 2
        bounds = (x - 316, y - 154, x + 316, y + 171)
        view.dim()
        view.rectangle(bounds, (29, 40, 54))
        view.rectangle(bounds, view.accent, False)
        view.centered_label(x, y + 127, "선후공 결정", 32)
        for offset, team, value in ((-123, Team.BLUE, blue), (123, Team.RED, red)):
            view.centered_label(x + offset, y + 65, team.value, 22, view.team_color(team))
            self.draw_face(x + offset, y - 14, 115, value)
        if blue == red:
            view.centered_label(x, y - 106, "동점 · 다시 굴립니다", 22, view.muted)
        else:
            first = self.roll.first_team
            view.centered_label(x, y - 106, f"{first.value} 선공", 26, view.team_color(first))
