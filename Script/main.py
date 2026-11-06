"""실행 진입점. 기존 Python에 설치된 pico2d로 실행한다."""

import sys

# 실행 중 검증·캐시 파일을 프로젝트에 남기지 않는다.
sys.dont_write_bytecode = True

import pico2d

from battle_view import BattleView
from prototype import Prototype


def handle_event(event, game: Prototype, view: BattleView) -> bool:
    """종료 요청이면 False를 반환한다."""
    if event.type == pico2d.SDL_QUIT:
        return False
    if event.type == pico2d.SDL_KEYDOWN:
        if event.key == pico2d.SDLK_ESCAPE:
            return False
        if event.key == pico2d.SDLK_SPACE:
            game.skip_turn()
    elif event.type == pico2d.SDL_MOUSEMOTION:
        view.hover = view.cell_at_pixel(event.x, event.y)
    elif event.type == pico2d.SDL_MOUSEBUTTONDOWN and event.button == pico2d.SDL_BUTTON_LEFT:
        if view.skip_at_pixel(event.x, event.y):
            game.skip_turn()
        else:
            game.try_move(view.cell_at_pixel(event.x, event.y))
    return True


def main() -> None:
    pico2d.open_canvas(BattleView.width, BattleView.height, sync=True)
    view = None
    try:
        game = Prototype()
        view = BattleView(game)
        running = True
        while running:
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
        pico2d.close_canvas()


if __name__ == "__main__":
    main()
