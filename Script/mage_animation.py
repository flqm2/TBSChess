"""메이지의 960×960 스프라이트 시트와 전투 상태별 재생."""

from dataclasses import dataclass

from pico2d import pico2d


SOURCE_FRAME_SIZE = 960
# 원본 픽셀의 2배 해상도로 텍스처를 올려 4800px 시트도 작은 렌더러에서 재생한다.
TEXTURE_FRAME_SIZE = 192
STUN_LOOP_START = 3  # 시트의 4번 프레임


@dataclass(frozen=True)
class Clip:
    frames: int
    fps: int


CLIPS = {
    "idle": Clip(5, 6),
    "death": Clip(10, 10),
    "stun": Clip(8, 10),
    "hit": Clip(5, 12),
    "hero": Clip(21, 14),
    "active": Clip(13, 14),
}


def load_sheet(path, frames: int):
    source = pico2d.IMG_Load(str(path).encode("utf-8"))
    if not source:
        raise OSError(f"스프라이트 시트를 읽을 수 없습니다: {path}")
    try:
        columns, extra_width = divmod(source.contents.w, SOURCE_FRAME_SIZE)
        rows, extra_height = divmod(source.contents.h, SOURCE_FRAME_SIZE)
        if extra_width or extra_height or columns * rows < frames:
            raise ValueError(f"960×960 프레임으로 구성된 스프라이트 시트가 필요합니다: {path}")
        surface = pico2d.SDL_CreateRGBSurfaceWithFormat(
            0, columns * TEXTURE_FRAME_SIZE, rows * TEXTURE_FRAME_SIZE,
            32, pico2d.SDL_PIXELFORMAT_RGBA32,
        )
        if not surface:
            raise OSError(f"스프라이트 시트 표면을 만들 수 없습니다: {path}")
        try:
            pico2d.SDL_SetSurfaceBlendMode(source, pico2d.SDL_BLENDMODE_NONE)
            if pico2d.SDL_BlitScaled(source, None, surface, None) < 0:
                raise OSError(f"스프라이트 시트 크기를 조정할 수 없습니다: {path}")
            texture = pico2d.SDL_CreateTextureFromSurface(pico2d.renderer, surface)
            if not texture:
                raise OSError(f"스프라이트 시트 텍스처를 만들 수 없습니다: {path}")
            return pico2d.Image(texture)
        finally:
            pico2d.SDL_FreeSurface(surface)
    finally:
        pico2d.SDL_FreeSurface(source)


def attack_clip(hero_skill: bool) -> str:
    return "hero" if hero_skill else "active"


def attack_duration(hero_skill: bool) -> float:
    clip = CLIPS[attack_clip(hero_skill)]
    return clip.frames / clip.fps


class MageAnimations:
    def __init__(self, resource_dir, layout):
        self.layout = layout
        self.images = {
            name: load_sheet(resource_dir / "Mage" / f"{name}.png", clip.frames)
            for name, clip in CLIPS.items()
        }
        self._battle = None
        self._cast = None
        self._playing: dict[str, tuple[str, float]] = {}

    def sync(self, battle, now: float) -> None:
        if self._battle is not battle:
            self._battle = battle
            self._cast = None
            self._playing.clear()

        cast = battle.last_cast
        if cast is self._cast:
            return
        self._cast = cast
        if cast is None:
            return

        for piece in battle.board.pieces:
            if piece.character_id != "mage":
                continue
            hits = tuple(hit for hit in cast.hits if hit.piece_id == piece.identifier)
            if hits and piece.current_hp == 0:
                self._playing[piece.identifier] = ("death", now)
            elif any(hit.stun_applied for hit in hits):
                self._playing[piece.identifier] = ("stun", now)
            elif piece.stunned:
                continue
            elif any(hit.damage > 0 for hit in hits):
                self._playing[piece.identifier] = ("hit", now)

    @staticmethod
    def _one_shot_frames(name: str) -> int:
        # 적용과 턴 건너뛰기가 같은 행동에서 끝나도 첫 별 프레임까지 보여 준다.
        return STUN_LOOP_START + 1 if name == "stun" else CLIPS[name].frames

    def playing_one_shot(self, now: float) -> bool:
        return any(
            (now - started) * CLIPS[name].fps < self._one_shot_frames(name)
            for name, started in self._playing.values()
        )

    def frame(self, piece, now: float) -> tuple[str, int] | None:
        playback = self._playing.get(piece.identifier)
        if playback is not None:
            name, started = playback
            clip = CLIPS[name]
            frame = int((now - started) * clip.fps)
            if frame < self._one_shot_frames(name):
                return name, frame
            if name == "stun" and piece.stunned:
                return name, STUN_LOOP_START + (frame - STUN_LOOP_START) % (clip.frames - STUN_LOOP_START)
        if piece.current_hp > 0:
            clip = CLIPS["idle"]
            return "idle", int(now * clip.fps) % clip.frames
        return None

    def draw(self, piece, x: int, foot_y: int, width: int, now: float) -> None:
        pose = self.frame(piece, now)
        if pose is not None:
            self._draw_frame(*pose, piece, x, foot_y, width)

    def draw_attack(self, piece, x: int, foot_y: int, width: int, hero_skill: bool, elapsed: float) -> None:
        name = attack_clip(hero_skill)
        clip = CLIPS[name]
        frame = min(clip.frames - 1, int(elapsed * clip.fps))
        self._draw_frame(name, frame, piece, x, foot_y, width)

    def _draw_frame(self, name: str, frame: int, piece, x: int, foot_y: int, width: int) -> None:
        image = self.images[name]
        size = TEXTURE_FRAME_SIZE
        row, column = divmod(frame, image.w // size)
        left = column * size
        bottom = image.h - (row + 1) * size
        mirrored = piece.facing < 0
        # 모든 프레임을 기본 자세와 같은 비율로 그려 공격 이펙트의 크기와 발 위치를 고정한다.
        placement = self.layout.placement(x, foot_y, width, mirrored)
        image.clip_composite_draw(left, bottom, size, size, 0, "h" if mirrored else "", *placement)
