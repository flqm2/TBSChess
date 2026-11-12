"""공용 전투 화면에서 최종전 1라운드 또는 서든데스 직전부터 실행한다."""

from argparse import ArgumentParser

from main import main
from character_data import CHARACTER_BY_ID
from game_controller import GameController
from piece import Team


def make_game(sudden_death: bool = False) -> GameController:
    blue = CHARACTER_BY_ID["mage"].create_piece(Team.BLUE, 1, (3, 1))
    red = CHARACTER_BY_ID["assassin"].create_piece(Team.RED, 1, (5, 2))
    game = GameController()
    game.start_battle((blue, red))
    if sudden_death:
        battle = game.battle
        while battle.final_battle.round < 5:
            battle.skip_turn()
        blue.current_hp = red.current_hp = 10
        battle.combat_notices.clear()
        battle.history.clear()
        battle.message = "서든데스 테스트 · 두 기물이 턴을 넘기면 다음 라운드에서 발동합니다."
    return game


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--sudden-death", action="store_true", help="서든데스 직전인 최종전 5라운드에서 시작")
    main(make_game(parser.parse_args().sudden_death))
