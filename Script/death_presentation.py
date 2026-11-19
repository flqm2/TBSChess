"""사망 모션의 8번 프레임까지 전투 재생을 늦추고 카메라 초점을 유지한다."""


class DeathPresentation:
    speed = 0.35
    stop_frame = 8
    zoom = 1.12

    def __init__(self):
        self.reset(0.0)

    def reset(self, now: float) -> None:
        self.real_time = now
        self.scene_time = now
        self.started = now
        self.slow_until = now
        self.cells = ()
        self._cast = None

    def time_at(self, now: float) -> float:
        elapsed = max(0.0, now - self.real_time)
        remaining = max(0.0, self.slow_until - self.scene_time)
        slow_seconds = min(elapsed, remaining / self.speed)
        return self.scene_time + slow_seconds * self.speed + elapsed - slow_seconds

    def advance(self, now: float) -> float:
        self.scene_time = self.time_at(now)
        self.real_time = now
        return self.scene_time

    def sync(self, battle, now: float, clips) -> None:
        cast = battle.last_cast
        if cast is self._cast:
            return
        self._cast = cast
        if cast is None:
            return
        hit_ids = {hit.piece_id for hit in cast.hits}
        fallen = tuple(piece for piece in battle.board.pieces
                       if piece.identifier in hit_ids and piece.current_hp == 0)
        if not fallen:
            return
        self.started = now
        self.slow_until = now + max((self.stop_frame - 1) / clips[p.character_id]["death"].fps
                                    for p in fallen)
        self.cells = tuple(piece.position for piece in fallen)

    def camera(self, now: float):
        if not self.cells or now >= self.slow_until:
            return None
        fade = min(1.0, max(0.0, (now - self.started) / 0.06),
                   max(0.0, (self.slow_until - now) / 0.08))
        fade = fade * fade * (3 - 2 * fade)
        return self.cells, 1 + (self.zoom - 1) * fade
