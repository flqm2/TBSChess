"""캐릭터별 시트와 전투 동작의 재생."""

from dataclasses import dataclass
from pathlib import Path

from pico2d import pico2d

from character_data import CHARACTERS
from portraits import damage_tint


# 원본 픽셀의 2배 해상도로 텍스처를 올려 큰 시트도 작은 렌더러에서 재생한다.
TEXTURE_DIVISOR = 5


@dataclass(frozen=True)
class Clip:
    frames: int
    fps: int
    width: int = 960
    height: int = 960
    x_padding: int = 0
    stun_loop: tuple[int, int] | None = None

    @property
    def duration(self) -> float:
        return self.frames / self.fps

    @property
    def texture_size(self) -> tuple[int, int]:
        return self.width // TEXTURE_DIVISOR, self.height // TEXTURE_DIVISOR

    def held_frame(self, frame: int) -> int:
        start, end = self.stun_loop
        return start + (frame - start) % (end - start)


HIT = Clip(5, 12)
IDLE = Clip(5, 6)
CLIPS = {
    "warrior": {
        "idle": IDLE, "active": Clip(9, 14), "hero": Clip(21, 14, 1280, 1280, 160),
        "hit": HIT, "stun": Clip(9, 10, stun_loop=(3, 8)), "death": Clip(12, 10),
    },
    "slayer": {
        "idle": IDLE, "skill1": Clip(9, 14), "skill2": Clip(9, 14, 1440, 960, 110),
        "hero": Clip(21, 14, 1600, 1600, 320), "passive": Clip(13, 14),
        "hit": HIT, "stun": Clip(9, 10, stun_loop=(5, 9)), "death": Clip(13, 10),
    },
    "archer": {
        "idle": IDLE, "skill1": Clip(9, 14, 1280, 1280, 160),
        "skill2": Clip(9, 14, 1280, 1280, 160), "hero": Clip(17, 14, 1600, 1600, 320),
    },
    "mage": {
        "idle": IDLE, "active": Clip(13, 14), "hero": Clip(21, 14), "hit": HIT,
        "stun": Clip(9, 10, stun_loop=(3, 9)), "death": Clip(10, 10),
    },
    "cardmaster": {
        "idle": Clip(9, 6), "skill1": Clip(13, 14, 1280, 960),
        "skill2": Clip(13, 14, 1280, 960), "hero": Clip(17, 14, 1600, 1600, 320),
        "passive": Clip(12, 12), "hit": HIT, "stun": Clip(9, 10, stun_loop=(6, 9)),
        "death": Clip(12, 10),
    },
}


@dataclass(frozen=True)
class Reaction:
    name: str
    clip: Clip
    started: float


def load_sheet(path, clip: Clip):
    source = pico2d.IMG_Load(str(path).encode("utf-8"))
    if not source:
        raise OSError(f"스프라이트 시트를 읽을 수 없습니다: {path}")
    try:
        columns, extra_width = divmod(source.contents.w, clip.width)
        rows, extra_height = divmod(source.contents.h, clip.height)
        if extra_width or extra_height or columns * rows < clip.frames:
            raise ValueError(f"{clip.width}×{clip.height} 프레임 시트가 필요합니다: {path}")
        width, height = clip.texture_size
        surface = pico2d.SDL_CreateRGBSurfaceWithFormat(
            0, columns * width, rows * height,
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


def attack_clip(character_id: str, slot: int) -> str:
    if slot == 2:
        return "hero"
    if "active" in CLIPS.get(character_id, {}):
        return "active"
    return ("skill1", "skill2")[slot]


def attack_duration(character_id: str, slot: int) -> float:
    clip = CLIPS.get(character_id, {}).get(attack_clip(character_id, slot))
    if clip is not None:
        return clip.duration
    return 0.48 if slot == 2 else 0.32


class CharacterAnimations:
    def __init__(self, resource_dir, layouts):
        self.layouts = layouts
        self.directories = {
            character.identifier: resource_dir / Path(character.image_name).parent
            for character in CHARACTERS
        }
        self.images = {}
        self._battle = None
        self._cast = None
        self._playing: dict[str, tuple[Reaction, ...]] = {}

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
            clips = CLIPS.get(piece.character_id, {})
            names = []
            if cast.caster_id == piece.identifier and cast.follow_up_slot is not None:
                names.append(attack_clip(piece.character_id, cast.follow_up_slot))
            hits = tuple(hit for hit in cast.hits if hit.piece_id == piece.identifier)
            if hits:
                if piece.current_hp == 0:
                    names.append("death")
                else:
                    stunned = any(hit.stun_applied for hit in hits)
                    if not (stunned and "stun" in clips) and any(hit.damage > 0 for hit in hits):
                        names.append("hit")
                    if any(hit.passive_triggered for hit in hits):
                        names.append("passive")
                    if stunned:
                        names.append("stun")
            reactions = []
            started = now
            for name in names:
                if name in clips:
                    clip = clips[name]
                    reactions.append(Reaction(name, clip, started))
                    started += clip.duration
            if reactions:
                self._playing[piece.identifier] = tuple(reactions)

    def playing_one_shot(self, now: float) -> bool:
        return any(now < reactions[-1].started + reactions[-1].clip.duration
                   for reactions in self._playing.values())

    def frame(self, piece, now: float) -> tuple[str, int] | None:
        clips = CLIPS.get(piece.character_id, {})
        stun_started = 0.0
        for reaction in self._playing.get(piece.identifier, ()):
            if reaction.name == "stun":
                stun_started = reaction.started
            if now < reaction.started + reaction.clip.duration:
                clip = reaction.clip
                frame = min(clip.frames - 1, int((now - reaction.started) * clip.fps))
                if piece.stunned and clip.stun_loop and frame >= clip.stun_loop[1]:
                    frame = clip.held_frame(frame)
                return reaction.name, frame
        if piece.current_hp > 0:
            if piece.stunned and "stun" in clips:
                clip = clips["stun"]
                return "stun", clip.held_frame(int((now - stun_started) * clip.fps))
            if "idle" in clips:
                clip = clips["idle"]
                return "idle", int(now * clip.fps) % clip.frames
        return None

    def draw(self, piece, x: int, foot_y: int, height: int, now: float,
             shake: int = 0, tint_channel: int = 255) -> bool:
        pose = self.frame(piece, now)
        if pose is None:
            return False
        self._draw_frame(*pose, piece, x + (shake if pose[0] == "idle" else 0), foot_y, height, tint_channel)
        return True

    def draw_attack(self, piece, x: int, foot_y: int, height: int, slot: int, elapsed: float) -> bool:
        name = attack_clip(piece.character_id, slot)
        clip = CLIPS.get(piece.character_id, {}).get(name)
        if clip is None:
            return False
        frame = min(clip.frames - 1, int(elapsed * clip.fps))
        self._draw_frame(name, frame, piece, x, foot_y, height)
        return True

    def _draw_frame(self, name: str, frame: int, piece, x: int, foot_y: int, height: int,
                    tint_channel: int = 255) -> None:
        character_id = piece.character_id
        clip = CLIPS[character_id][name]
        key = (character_id, name)
        if key not in self.images:
            self.images[key] = load_sheet(self.directories[character_id] / f"{name}.png", clip)
        image = self.images[key]
        texture_width, texture_height = clip.texture_size
        row, column = divmod(frame, image.w // texture_width)
        left = column * texture_width
        bottom = image.h - (row + 1) * texture_height
        mirrored = piece.facing < 0
        layout = self.layouts[piece.image_name]
        base_x, base_y, _, base_height = layout.placement(x, foot_y, height, mirrored)
        scale = base_height / layout.image_height
        # 이펙트 공간이 넓은 시트에서도 캐릭터의 크기와 첫 프레임의 발 위치를 유지한다.
        shift_x = (clip.width - layout.image_width) / 2 - clip.x_padding
        shift_y = (clip.height - layout.image_height) / 2
        with damage_tint(image, tint_channel):
            image.clip_composite_draw(left, bottom, texture_width, texture_height, 0, "h" if mirrored else "",
                                      base_x + piece.facing * shift_x * scale, base_y + shift_y * scale,
                                      clip.width * scale, clip.height * scale)
