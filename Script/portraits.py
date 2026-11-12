"""전투 초상화에 사용하는 흑백 텍스처."""

from ctypes import c_ubyte

from pico2d import pico2d


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
