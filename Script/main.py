"""실행 진입점. 기존 Python에 설치된 pico2d로 실행한다."""

import sys
from ctypes import byref

# 실행 중 검증·캐시 파일을 프로젝트에 남기지 않는다.
sys.dont_write_bytecode = True

from pico2d import pico2d

from game_controller import GameController, Stage
from game_view import GameView


def fit_canvas(width: int, height: int) -> None:
    """화면에 맞춰 창을 줄여도 그리기와 클릭에는 같은 게임 좌표를 사용한다."""
    window = pico2d.window
    display = pico2d.SDL_GetWindowDisplayIndex(window)
    area = pico2d.SDL_Rect()
    if display >= 0 and pico2d.SDL_GetDisplayUsableBounds(display, byref(area)) == 0:
        scale = min(1.0, (area.w - 24) / width, (area.h - 64) / height)
        if 0 < scale < 1:
            window_width = round(width * scale)
            window_height = round(height * scale)
            pico2d.SDL_SetWindowSize(window, window_width, window_height)
            pico2d.SDL_SetWindowPosition(window, area.x + (area.w - window_width) // 2,
                                         area.y + (area.h - window_height) // 2)
    pico2d.SDL_RenderSetLogicalSize(pico2d.renderer, width, height)


def handle_event(event, game: GameController, view: GameView) -> bool:
    """종료 요청이면 False를 반환한다."""
    if event.type == pico2d.SDL_QUIT:
        return False
    if event.type == pico2d.SDL_MOUSEBUTTONDOWN and event.button == pico2d.SDL_BUTTON_LEFT:
        view.click(event.x, event.y)
        return True
    if view.help_overlay is not None:
        if event.type == pico2d.SDL_KEYDOWN:
            if event.key == pico2d.SDLK_ESCAPE:
                view.help_overlay = None
            elif event.key == pico2d.SDLK_UP:
                view.help_overlay.move_selection(-1)
            elif event.key == pico2d.SDLK_DOWN:
                view.help_overlay.move_selection(1)
        return True
    if event.type == pico2d.SDL_KEYDOWN:
        if event.key == pico2d.SDLK_ESCAPE:
            return False
        if (event.key == pico2d.SDLK_SPACE and game.stage is Stage.MOVEMENT
                and not view.initiative_revealing(game.battle)
                and not view.card_revealing(game.battle)):
            game.battle.skip_turn()
        elif event.key == pico2d.SDLK_RETURN and game.stage is not Stage.MOVEMENT:
            game.confirm()
    elif event.type == pico2d.SDL_MOUSEMOTION:
        view.point_at(event.x, event.y)
    return True


def main(game: GameController | None = None) -> None:
    pico2d.SDL_SetHint(pico2d.SDL_HINT_RENDER_SCALE_QUALITY, b"1")
    pico2d.SDL_SetHint(pico2d.SDL_HINT_RENDER_LINE_METHOD, b"3")
    pico2d.open_canvas(GameView.width, GameView.height, sync=True)
    view = None
    try:
        fit_canvas(GameView.width, GameView.height)
        if game is None:
            game = GameController()
        view = GameView(game)
        running = True
        while running:
            view.update()
            for event in pico2d.get_events():
                if not handle_event(event, game, view):
                    running = False
                    break
            if running:
                view.draw()
                pico2d.update_canvas()
                pico2d.delay(0.01)
    finally:
        if view is not None:
            # SDL 렌더러가 살아 있을 때 원본 이미지의 텍스처부터 해제한다.
            view.images.clear()
            view.grayscale_portraits.clear()
            view.card_faces.clear()
            view.card_back = None
            view.dice_view.image = None
        pico2d.close_canvas()


if __name__ == "__main__":
    main()
