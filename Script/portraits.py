"""픽셀 경계를 유지하는 캐릭터 텍스처와 흑백 초상화."""

from ctypes import c_ubyte

from pico2d import pico2d


def load_sprite(path):
    image = pico2d.load_image(str(path))
    pico2d.SDL_SetTextureScaleMode(image.texture, pico2d.SDL_ScaleModeNearest)
    return image


def load_grayscale_portrait(path):
    source = pico2d.IMG_Load(str(path).encode("utf-8"))
    if not source:
        raise OSError(f"초상화를 읽을 수 없습니다: {path}")
    try:
        surface = pico2d.SDL_ConvertSurfaceFormat(source, pico2d.SDL_PIXELFORMAT_RGBA32, 0)
        if not surface:
            raise OSError("초상화 표면을 만들 수 없습니다.")
        try:
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
            pico2d.SDL_SetTextureScaleMode(texture, pico2d.SDL_ScaleModeNearest)
            return pico2d.Image(texture)
        finally:
            pico2d.SDL_FreeSurface(surface)
    finally:
        pico2d.SDL_FreeSurface(source)
