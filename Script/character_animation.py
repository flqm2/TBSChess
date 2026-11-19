"""캐릭터별 시트와 전투 동작의 재생."""

from dataclasses import dataclass
from pathlib import Path

from pico2d import pico2d

from character_data import CHARACTERS
from portraits import damage_tint


# 원본 픽셀의 2배 해상도로 텍스처를 올려 큰 시트도 작은 렌더러에서 재생한다.
BASE_FRAME_SIZE = 96


@dataclass(frozen=True)
class Clip:
    frames: int
    fps: int
    width: int = 960
    height: int = 960
    x_padding: int = 0
    pixel_scale: int = 10

    @property
    def texture_size(self) -> tuple[int, int]:
        return self.width * 2 // self.pixel_scale, self.height * 2 // self.pixel_scale


HIT = Clip(5, 12)
IDLE = Clip(5, 6)
CLIPS = {
    "warrior": {
        "idle": IDLE, "active": Clip(9, 14), "hero": Clip(21, 14, 1280, 1280, 160),
        "hit": HIT, "stun": Clip(9, 10), "death": Clip(12, 10),
    },
    "slayer": {
        "idle": IDLE, "skill1": Clip(9, 14), "skill2": Clip(9, 14, 1440, 960, 110),
        "hero": Clip(21, 14, 1600, 1600, 320), "passive": Clip(13, 14),
        "hit": HIT, "stun": Clip(9, 10), "death": Clip(13, 10),
    },
    "archer": {
        "idle": IDLE, "skill1": Clip(9, 14, 1280, 1280, 160),
        "skill2": Clip(9, 14, 1280, 1280, 160), "hero": Clip(17, 14, 1600, 1600, 320),
        "hit": HIT, "stun": Clip(9, 10), "death": Clip(13, 10),
    },
    "mage": {
        "idle": IDLE, "active": Clip(13, 14), "hero": Clip(21, 14, 160, 160, 32, pixel_scale=1),
        "hit": HIT, "stun": Clip(9, 10), "death": Clip(10, 10),
    },
    "cardmaster": {
        "idle": Clip(9, 6), "skill1": Clip(13, 14, 1280, 960),
        "skill2": Clip(13, 14, 1280, 960), "hero": Clip(17, 14, 1600, 1600, 320),
        "hit": HIT, "stun": Clip(9, 10), "death": Clip(12, 10), "passive": Clip(12, 12),
    },
    "assassin": {
        "idle": IDLE, "idle_empowered": IDLE,
        "skill1": Clip(12, 14), "skill2": Clip(17, 14), "hero": Clip(17, 14),
        "hit": HIT, "stun": Clip(13, 10), "death": Clip(12, 10),
    },
}


@dataclass(frozen=True)
class StunMotion:
    loop: range
    recovery_clip: str
    recovery_frames: tuple[int, ...]


# 시트의 프레임 번호를 0부터 시작하는 인덱스로 변환해 기록한다.
STUN_MOTIONS = {
    "cardmaster": StunMotion(range(7, 9), "stun", (2, 1, 0)),
    "mage": StunMotion(range(4, 9), "stun", (2, 1, 0)),
    "slayer": StunMotion(range(6, 9), "hit", (3, 2, 1, 0)),
    "archer": StunMotion(range(3, 6), "stun", (6, 7, 8, 2, 1, 0)),
    "assassin": StunMotion(range(7, 10), "stun", (6, 5, 4, 3, 2, 1, 0)),
    "warrior": StunMotion(range(3, 6), "stun", (6, 7, 8)),
}

ATTACK_SEQUENCES = {
    ("assassin", 0): (*range(12), *range(6, -1, -1)),
}
IMPACT_FRAMES = {
    ("mage", 0): 11,
    ("mage", 1): 11,
    ("slayer", 0): 6,
    ("slayer", 1): 6,
    ("warrior", 0): 6,
    ("warrior", 1): 6,
    ("assassin", 0): 9,
    ("assassin", 1): 9,
    ("slayer", 2): 13,
    ("warrior", 2): 12,
    ("mage", 2): 15,
}


@dataclass(frozen=True)
class Reaction:
    name: str
    clip: Clip
    started: float
    frames: range | tuple[int, ...]

    @property
    def ended(self) -> float:
        return self.started + len(self.frames) / self.clip.fps


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
    if clip is None:
        return 0.48 if slot == 2 else 0.32
    frames = ATTACK_SEQUENCES.get((character_id, slot), range(clip.frames))
    return len(frames) / clip.fps


def attack_impact_time(character_id: str, slot: int) -> float | None:
    frame = IMPACT_FRAMES.get((character_id, slot))
    if frame is None:
        return None
    clip = CLIPS[character_id][attack_clip(character_id, slot)]
    return (frame - 1) / clip.fps


def attack_frame(character_id: str, slot: int, elapsed: float) -> tuple[str, int] | None:
    name = attack_clip(character_id, slot)
    clip = CLIPS.get(character_id, {}).get(name)
    if clip is None:
        return None
    frames = ATTACK_SEQUENCES.get((character_id, slot), range(clip.frames))
    return name, frames[min(len(frames) - 1, int(elapsed * clip.fps + 1e-8))]


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
        self._holding_stun: dict[str, Reaction] = {}
        self._spent_empowered_idle: set[str] = set()

    def sync(self, battle, now: float) -> None:
        if self._battle is not battle:
            self._battle = battle
            self._cast = None
            self._playing.clear()
            self._holding_stun.clear()
            self._spent_empowered_idle.clear()

        cast = battle.last_cast
        new_cast = cast if cast is not self._cast else None
        self._cast = cast
        pending = battle.pending_skill
        if pending is not None and battle.current.character_id == "assassin":
            identifier = battle.current.identifier
            if pending.hero_skill:
                self._spent_empowered_idle.discard(identifier)
            else:
                self._spent_empowered_idle.add(identifier)

        for piece in battle.board.pieces:
            if new_cast is not None:
                self._play_cast(piece, new_cast, now)
            held = self._holding_stun.get(piece.identifier)
            if piece.current_hp == 0:
                self._holding_stun.pop(piece.identifier, None)
            elif held is None and piece.stunned:
                self._start_stun(piece, now)
            elif held is not None and not piece.stunned:
                motion = STUN_MOTIONS[piece.character_id]
                queue = self._playing[piece.identifier]
                started = max(now, queue[-1].ended, held.ended)
                recovery = Reaction(motion.recovery_clip, CLIPS[piece.character_id][motion.recovery_clip],
                                    started, motion.recovery_frames)
                self._playing[piece.identifier] = (*queue, recovery)
                del self._holding_stun[piece.identifier]

    def _play_cast(self, piece, cast, now: float) -> None:
        clips = CLIPS.get(piece.character_id, {})
        names = []
        hits = tuple(hit for hit in cast.hits if hit.piece_id == piece.identifier)
        stunned = piece.current_hp > 0 and any(hit.stun_applied for hit in hits)
        if hits:
            if piece.current_hp == 0:
                names.append("death")
            else:
                revived = piece.character_id == "cardmaster" and any(hit.passive_triggered for hit in hits)
                if (not stunned and not revived and piece.identifier not in self._holding_stun
                        and any(hit.damage > 0 for hit in hits)):
                    names.append("hit")
                if any(hit.passive_triggered for hit in hits):
                    names.append("passive")
        reactions = []
        started = now
        for name in names:
            if name in clips:
                clip = clips[name]
                reaction = Reaction(name, clip, started, range(clip.frames))
                reactions.append(reaction)
                started = reaction.ended
        if reactions:
            self._playing[piece.identifier] = tuple(reactions)
        if stunned:
            self._start_stun(piece, started)

    def _start_stun(self, piece, now: float) -> None:
        motion = STUN_MOTIONS.get(piece.character_id)
        if motion is None:
            return
        # 같은 행동에서 차례를 건너뛰더라도 초기 피격과 반복 구간을 한 번 보여 준다.
        clip = CLIPS[piece.character_id]["stun"]
        reaction = Reaction("stun", clip, now, range(motion.loop.stop))
        queue = self._playing.get(piece.identifier, ())
        self._playing[piece.identifier] = (*(r for r in queue if r.ended <= now), reaction)
        self._holding_stun[piece.identifier] = reaction

    def playing_one_shot(self, now: float) -> bool:
        return any(now < reactions[-1].ended for reactions in self._playing.values())

    def frame(self, piece, now: float) -> tuple[str, int] | None:
        clips = CLIPS.get(piece.character_id, {})
        for reaction in self._playing.get(piece.identifier, ()):
            if reaction.started <= now < reaction.ended:
                index = min(len(reaction.frames) - 1, int((now - reaction.started) * reaction.clip.fps))
                return reaction.name, reaction.frames[index]
        if piece.current_hp > 0:
            held = self._holding_stun.get(piece.identifier)
            if held is not None:
                loop = STUN_MOTIONS[piece.character_id].loop
                index = max(0, int((now - held.ended) * held.clip.fps))
                return "stun", loop[index % len(loop)]
            if "idle" in clips:
                name = "idle"
                if ("idle_empowered" in clips and piece.empowered_mark
                        and piece.identifier not in self._spent_empowered_idle):
                    name = "idle_empowered"
                clip = clips[name]
                return name, int(now * clip.fps) % clip.frames
        return None

    def draw(self, piece, x: int, foot_y: int, height: int, now: float,
             shake: int = 0, tint_channel: int = 255) -> bool:
        pose = self.frame(piece, now)
        if pose is None:
            return False
        self._draw_frame(*pose, piece, x + (shake if pose[0] == "idle" else 0), foot_y, height, tint_channel)
        return True

    def draw_attack(self, piece, x: int, foot_y: int, height: int, slot: int, elapsed: float) -> bool:
        pose = attack_frame(piece.character_id, slot, elapsed)
        if pose is None:
            return False
        self._draw_frame(*pose, piece, x, foot_y, height)
        return True

    def draw_idle(self, piece, x: int, foot_y: int, height: int, elapsed: float) -> None:
        clip = CLIPS[piece.character_id]["idle"]
        self._draw_frame("idle", int(elapsed * clip.fps) % clip.frames, piece, x, foot_y, height)

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
        source_ratio = clip.pixel_scale * BASE_FRAME_SIZE / layout.image_width
        scale = base_height / (layout.image_height * source_ratio)
        # 이펙트 공간이 넓은 시트에서도 캐릭터의 크기와 첫 프레임의 발 위치를 유지한다.
        shift_x = (clip.width - layout.image_width * source_ratio) / 2 - clip.x_padding
        shift_y = (clip.height - layout.image_height * source_ratio) / 2
        with damage_tint(image, tint_channel):
            image.clip_composite_draw(left, bottom, texture_width, texture_height, 0, "h" if mirrored else "",
                                      base_x + piece.facing * shift_x * scale, base_y + shift_y * scale,
                                      clip.width * scale, clip.height * scale)
