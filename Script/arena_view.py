"""일반 경기장과 차단막 해제, 최종전의 6프레임 배경."""

from ctypes import byref

from pico2d import pico2d


FRAME_COUNT = 6
FPS = 6
OPENING_SECONDS = FRAME_COUNT / FPS


def load_arena_sheet(path):
    source = pico2d.IMG_Load(str(path).encode("utf-8"))
    if not source:
        raise OSError(f"경기장 시트를 읽을 수 없습니다: {path}")
    try:
        width, x_remainder = divmod(source.contents.w, 3)
        height, y_remainder = divmod(source.contents.h, 2)
        if x_remainder or y_remainder:
            raise ValueError(f"경기장 시트는 같은 크기의 3열 × 2행이 필요합니다: {path}")
        # 4096px 텍스처 한도를 넘지 않도록 원본 프레임을 축소 없이 2열 × 3행으로 옮긴다.
        surface = pico2d.SDL_CreateRGBSurfaceWithFormat(0, 2 * width, 3 * height, 32,
                                                        pico2d.SDL_PIXELFORMAT_RGBA32)
        if not surface:
            raise OSError(f"경기장 시트 표면을 만들 수 없습니다: {path}")
        try:
            pico2d.SDL_SetSurfaceBlendMode(source, pico2d.SDL_BLENDMODE_NONE)
            for frame in range(FRAME_COUNT):
                row, column = divmod(frame, 3)
                source_rect = pico2d.SDL_Rect(column * width, row * height, width, height)
                row, column = divmod(frame, 2)
                dest_rect = pico2d.SDL_Rect(column * width, row * height, width, height)
                if pico2d.SDL_BlitSurface(source, byref(source_rect), surface, byref(dest_rect)) < 0:
                    raise OSError(f"경기장 프레임을 옮길 수 없습니다: {path}")
            texture = pico2d.SDL_CreateTextureFromSurface(pico2d.renderer, surface)
            if not texture:
                raise OSError(f"경기장 텍스처를 만들 수 없습니다: {path}")
            return pico2d.Image(texture)
        finally:
            pico2d.SDL_FreeSurface(surface)
    finally:
        pico2d.SDL_FreeSurface(source)


class ArenaView:
    def __init__(self, directory):
        self.sheets = {name: load_arena_sheet(directory / f"{name}.png")
                       for name in ("normal", "opening", "final")}
        self.battle = None
        self.opening_started: float | None = None

    def sync(self, battle, now: float, *, ready: bool) -> None:
        if self.battle is not battle:
            self.battle = battle
            self.opening_started = None
        if (battle is not None and battle.final_battle is not None and battle.final_battle.round <= 1
                and self.opening_started is None and ready):
            self.opening_started = now

    def waiting(self, battle, now: float) -> bool:
        return (battle is not None and battle.final_battle is not None and battle.final_battle.round <= 1
                and not self.opening_finished(now))

    def opening_finished(self, now: float) -> bool:
        return self.opening_started is not None and now >= self.opening_started + OPENING_SECONDS

    def frame(self, battle, now: float) -> tuple[str, int]:
        if battle is not None and battle.final_battle is not None:
            if self.opening_started is not None:
                age = now - self.opening_started
                if age < OPENING_SECONDS:
                    return "opening", min(FRAME_COUNT - 1, int(age * FPS))
                return "final", int((age - OPENING_SECONDS) * FPS) % FRAME_COUNT
            if battle.final_battle.round > 1:
                return "final", int(now * FPS) % FRAME_COUNT
        return "normal", int(now * FPS) % FRAME_COUNT

    def draw(self, battle, now: float, width: int, height: int) -> None:
        name, frame = self.frame(battle, now)
        image = self.sheets[name]
        frame_width, frame_height = image.w // 2, image.h // 3
        row, column = divmod(frame, 2)
        image.clip_draw(column * frame_width, image.h - (row + 1) * frame_height,
                        frame_width, frame_height, width // 2, height // 2, width, height)
