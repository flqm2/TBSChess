"""캐릭터 텍스처와 보드 위 배치를 위한 이미지 경계."""

from ctypes import c_ubyte, string_at
from dataclasses import dataclass

from pico2d import pico2d


@dataclass(frozen=True)
class SpriteLayout:
    image_width: int
    image_height: int
    left: int
    right: int
    bottom: int

    def placement(self, x, foot_y, width, mirrored=False):
        scale = width / (self.right - self.left)
        offset_x = (self.image_width - self.left - self.right) * scale / 2
        offset_y = (self.bottom - self.image_height / 2) * scale
        return (x - offset_x if mirrored else x + offset_x, foot_y + offset_y,
                self.image_width * scale, self.image_height * scale)


# 희미한 외곽 픽셀은 남겨 두되, 캐릭터 크기 계산에서는 제외한다.
OPAQUE_ALPHA = bytes(0 if alpha < 128 else 255 for alpha in range(256))


def load_portrait(path):
    source = pico2d.IMG_Load(str(path).encode("utf-8"))
    if not source:
        raise OSError(f"초상화를 읽을 수 없습니다: {path}")
    try:
        surface = pico2d.SDL_ConvertSurfaceFormat(source, pico2d.SDL_PIXELFORMAT_RGBA32, 0)
    finally:
        pico2d.SDL_FreeSurface(source)
    if not surface:
        raise OSError(f"초상화를 RGBA로 변환할 수 없습니다: {path}")
    try:
        data = surface.contents
        left, right, bottom = data.w, 0, 0
        if pico2d.SDL_LockSurface(surface) < 0:
            raise OSError(f"초상화의 픽셀을 읽을 수 없습니다: {path}")
        try:
            for row in range(data.h):
                rgba = string_at(data.pixels + row * data.pitch, data.w * 4)
                alpha = rgba[3::4].translate(OPAQUE_ALPHA)
                last = len(alpha.rstrip(b"\0"))
                if last:
                    left = min(left, data.w - len(alpha.lstrip(b"\0")))
                    right = max(right, last)
                    bottom = row + 1
        finally:
            pico2d.SDL_UnlockSurface(surface)
        if not bottom:
            left, right, bottom = 0, data.w, data.h
        texture = pico2d.SDL_CreateTextureFromSurface(pico2d.renderer, surface)
        if not texture:
            raise OSError(f"초상화 텍스처를 만들 수 없습니다: {path}")
        return pico2d.Image(texture), SpriteLayout(data.w, data.h, left, right, bottom)
    finally:
        pico2d.SDL_FreeSurface(surface)


def load_grayscale_portrait(path):
    source = pico2d.IMG_Load(str(path).encode("utf-8"))
    if not source:
        raise OSError(f"초상화를 읽을 수 없습니다: {path}")
    try:
        width, height = source.contents.w, source.contents.h
        scale = min(96 / width, 96 / height, 1)
        surface = pico2d.SDL_CreateRGBSurfaceWithFormat(
            0, max(1, round(width * scale)), max(1, round(height * scale)),
            32, pico2d.SDL_PIXELFORMAT_RGBA32,
        )
        if not surface:
            raise OSError("초상화 표면을 만들 수 없습니다.")
        try:
            pico2d.SDL_SetSurfaceBlendMode(source, pico2d.SDL_BLENDMODE_NONE)
            if pico2d.SDL_BlitScaled(source, None, surface, None) < 0:
                raise OSError("초상화 크기를 조정할 수 없습니다.")
            if pico2d.SDL_LockSurface(surface) < 0:
                raise OSError("초상화의 픽셀을 읽을 수 없습니다.")
            try:
                data = surface.contents
                for row in range(data.h):
                    pixels = (c_ubyte * (data.w * 4)).from_address(data.pixels + row * data.pitch)
                    for offset in range(0, len(pixels), 4):
                        red, green, blue = pixels[offset:offset + 3]
                        gray = (299 * red + 587 * green + 114 * blue) // 1000
                        pixels[offset:offset + 3] = (gray, gray, gray)
            finally:
                pico2d.SDL_UnlockSurface(surface)
            texture = pico2d.SDL_CreateTextureFromSurface(pico2d.renderer, surface)
            if not texture:
                raise OSError("흑백 초상화를 만들 수 없습니다.")
            return pico2d.Image(texture)
        finally:
            pico2d.SDL_FreeSurface(surface)
    finally:
        pico2d.SDL_FreeSurface(source)
