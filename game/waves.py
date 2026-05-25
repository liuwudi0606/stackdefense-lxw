import random

import config
from game.iso import spawn_at_edge

# 无尽阶段刷怪权重（随 cycle 解锁更强怪）
_ENDLESS_POOL = [
    ("grunt", 32),
    ("runner", 26),
    ("archer", 18),
    ("sapper", 16),
    ("tank", 16),
    ("brute", 14),
    ("elite", 12),
    ("wraith", 10),
    ("juggernaut", 8),
    ("shielded", 8),
    ("boss", 5),
    ("warlord", 4),
    ("hive_matron", 4),
    ("storm_herald", 4),
    ("iron_titan", 3),
    ("colossus", 2),
]


class WaveController:
    def __init__(self, wave_data: dict, endless: bool = False) -> None:
        self.waves = sorted(wave_data["waves"], key=lambda w: w["at"])
        self.wave_index = 0
        self.spawn_queue: list[tuple[float, str]] = []
        self.all_scheduled_spawned = False
        self.elapsed = 0.0
        self.endless = endless
        self.endless_cycle = 0
        self._endless_cd = config.ENDLESS_INITIAL_COOLDOWN if endless else 999999.0

    def set_endless_enabled(self, enabled: bool) -> None:
        """开启/关闭无尽刷怪（预定波次清完后才刷无尽怪）。"""
        self.endless = enabled
        if enabled:
            if self.wave_index >= len(self.waves) and not self.spawn_queue:
                self.all_scheduled_spawned = True
            if self.all_scheduled_spawned:
                self._endless_cd = min(self._endless_cd, config.ENDLESS_INITIAL_COOLDOWN)
        else:
            self._endless_cd = 999999.0

    def _endless_spawn_interval(self) -> float:
        redu = self.endless_cycle * config.ENDLESS_INTERVAL_CYCLE_STEP
        time_redu = min(
            config.ENDLESS_INTERVAL_TIME_CAP,
            self.elapsed * config.ENDLESS_INTERVAL_TIME_SCALE,
        )
        return max(
            config.ENDLESS_INTERVAL_MIN,
            config.ENDLESS_INTERVAL_BASE - redu - time_redu,
        )

    def _endless_batch_size(self) -> int:
        extra = self.endless_cycle // config.ENDLESS_BATCH_EVERY_CYCLES
        return min(config.ENDLESS_BATCH_MAX, config.ENDLESS_BATCH_BASE + extra)

    def _pick_endless_type(self) -> str:
        cycle = self.endless_cycle
        pool = []
        for tid, w in _ENDLESS_POOL:
            if tid == "tank" and cycle < 2:
                continue
            if tid == "elite" and cycle < 4:
                continue
            if tid == "boss" and cycle < 6:
                continue
            if tid == "juggernaut" and cycle < 3:
                continue
            if tid == "shielded" and cycle < 5:
                continue
            if tid == "colossus" and cycle < 10:
                continue
            if tid == "brute" and cycle < 2:
                continue
            if tid == "sapper" and cycle < 3:
                continue
            if tid == "wraith" and cycle < 4:
                continue
            if tid == "warlord" and cycle < 8:
                continue
            if tid == "hive_matron" and cycle < 10:
                continue
            if tid == "storm_herald" and cycle < 12:
                continue
            if tid == "iron_titan" and cycle < 14:
                continue
            pool.extend([tid] * max(1, w + cycle))
        return random.choice(pool) if pool else "grunt"

    def update(self, dt: float, *, advance_time: bool = True) -> list[dict]:
        if advance_time:
            self.elapsed += dt
        spawns = []

        while self.wave_index < len(self.waves):
            w = self.waves[self.wave_index]
            if self.elapsed < w["at"]:
                break
            etype = w["type"]
            count = w["count"]
            interval = w.get("interval", 0.5)
            t0 = w["at"]
            for i in range(count):
                self.spawn_queue.append((t0 + i * interval, etype))
            self.spawn_queue.sort(key=lambda x: x[0])
            self.wave_index += 1

        ready = []
        remaining = []
        for t, etype in self.spawn_queue:
            if t <= self.elapsed:
                ready.append(etype)
            else:
                remaining.append((t, etype))
        self.spawn_queue = remaining

        for etype in ready:
            x, y = spawn_at_edge()
            spawns.append({"type": etype, "x": x, "y": y})

        if self.wave_index >= len(self.waves) and not self.spawn_queue:
            self.all_scheduled_spawned = True

        if self.endless and self.all_scheduled_spawned and advance_time:
            self._endless_cd -= dt
            # 每帧最多触发一轮，避免卡顿补帧时连刷多轮导致怪潮
            if self._endless_cd <= 0:
                self._endless_cd = self._endless_spawn_interval()
                self.endless_cycle += 1
                for _ in range(self._endless_batch_size()):
                    etype = self._pick_endless_type()
                    x, y = spawn_at_edge()
                    spawns.append({"type": etype, "x": x, "y": y})

        return spawns
