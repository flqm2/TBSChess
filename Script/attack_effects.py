"""공격 판정 시 재생하는 3열 × 2행 이펙트 시트."""

from dataclasses import dataclass

from pico2d import pico2d


EFFECTS = {
    ("slayer", 0): "slayer_slash",
    ("slayer", 1): "slayer_thrust",
    ("warrior", 0): "warrior_slam",
    ("warrior", 1): "warrior_sweep",
}
FRAME_COUNT = 6
FPS = 18


@dataclass(frozen=True)
class Playback:
    name: str
    cells: tuple[tuple[int, int], ...]
    facing: int
    started: float


class AttackEffects:
    def __init__(self, directory):
        self.directory = directory
        self.images = {}
        self.playback: Playback | None = None

    def play(self, caster, pending, now: float) -> None:
        name = EFFECTS.get((caster.character_id, pending.slot))
        if name is not None and pending.cells:
            self.playback = Playback(name, pending.cells, caster.facing, now)

    def playing(self, now: float) -> bool:
        return self.playback is not None and 0 <= now - self.playback.started < FRAME_COUNT / FPS

    def draw(self, now: float, cell_bounds) -> None:
        if not self.playing(now):
            return
        playback = self.playback
        if playback.name not in self.images:
            image = pico2d.load_image(str(self.directory / f"{playback.name}.png"))
            if image.w % 3 or image.h % 2:
                raise ValueError(f"공격 이펙트는 3열 × 2행 시트가 필요합니다: {playback.name}")
            self.images[playback.name] = image
        image = self.images[playback.name]
        frame = min(FRAME_COUNT - 1, int((now - playback.started) * FPS))
        row, column = divmod(frame, 3)
        frame_width, frame_height = image.w // 3, image.h // 2
        bounds = tuple(cell_bounds(cell) for cell in playback.cells)
        left = min(b[0] for b in bounds)
        bottom = min(b[1] for b in bounds)
        right = max(b[2] for b in bounds)
        top = max(b[3] for b in bounds)
        tile_width = bounds[0][2] - bounds[0][0]
        tile_height = bounds[0][3] - bounds[0][1]
        width = right - left + tile_width * 0.4
        height = top - bottom + tile_height * 0.4
        y = (bottom + top) / 2
        if playback.name == "warrior_slam":
            y += height * 0.25
        image.clip_composite_draw(column * frame_width, image.h - (row + 1) * frame_height,
                                   frame_width, frame_height, 0, "h" if playback.facing < 0 else "",
                                   (left + right) / 2, y, width, height)
