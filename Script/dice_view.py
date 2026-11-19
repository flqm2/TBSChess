"""3×3 주사위 흔들림 시트를 재생한 뒤 선후공 결과를 표시한다."""

from pathlib import Path
from time import monotonic

import pico2d

from initiative import InitiativeRoll
from piece import Team


class DiceView:
    roll_frames = 9
    roll_fps = 14
    roll_seconds = roll_frames / roll_fps
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
        self.animation = pico2d.load_image(str(path.with_name("아이보리 주사위 3×3 흔들림 애니메이션.png")))
        if self.animation.w % 3 or self.animation.h % 3:
            raise ValueError("주사위 시트는 같은 크기의 3열 × 3행이 필요합니다.")
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
        duration = (self.roll_seconds * len(roll.attempts)
                    + self.tie_seconds * (len(roll.attempts) - 1) + self.result_seconds)
        return monotonic() - self.started < self.delay + duration

    def draw_roll(self, x: int, y: int, size: int, elapsed: float) -> None:
        frame = min(self.roll_frames - 1, int(elapsed * self.roll_fps))
        row, column = divmod(frame, 3)
        width, height = self.animation.w // 3, self.animation.h // 3
        self.animation.clip_draw(column * width, self.animation.h - (row + 1) * height,
                                 width, height, x, y, size, size)

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
        attempt_seconds = self.roll_seconds + self.tie_seconds
        index = min(int(elapsed / attempt_seconds), len(attempts) - 1)
        attempt_age = elapsed - index * attempt_seconds
        rolling = attempt_age < self.roll_seconds
        blue, red = attempts[index]
        x, y = view.width // 2, view.height // 2
        bounds = (x - 316, y - 154, x + 316, y + 171)
        view.dim()
        view.rectangle(bounds, (29, 40, 54))
        view.rectangle(bounds, view.accent, False)
        view.centered_label(x, y + 127, "선후공 결정", 32)
        for offset, team, value in ((-123, Team.BLUE, blue), (123, Team.RED, red)):
            view.centered_label(x + offset, y + 65, team.value, 22, view.team_color(team))
            if rolling:
                self.draw_roll(x + offset, y - 14, 115, attempt_age)
            else:
                self.draw_face(x + offset, y - 14, 115, value)
        if rolling:
            view.centered_label(x, y - 106, "주사위를 굴립니다", 22, view.muted)
        elif blue == red:
            view.centered_label(x, y - 106, "동점 · 다시 굴립니다", 22, view.muted)
        else:
            first = self.roll.first_team
            view.centered_label(x, y - 106, f"{first.value} 선공", 26, view.team_color(first))
