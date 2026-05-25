import math
import random

import config
from game.iso import spawn_at_edge, spawn_in_cluster

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

# 无尽成团：偏脆皮群，方便体现范围炮
_ENDLESS_CLUSTER_POOL = [
    ("grunt", 40),
    ("runner", 30),
    ("sapper", 22),
    ("archer", 14),
]


class WaveController:
    def __init__(self, wave_data: dict, endless: bool = False) -> None:
        self.waves = sorted(wave_data["waves"], key=lambda w: w["at"])
        self.wave_index = 0
        self.spawn_queue: list[tuple[float, str, dict]] = []
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

    def _pick_endless_cluster_type(self) -> str:
        cycle = self.endless_cycle
        pool = []
        for tid, w in _ENDLESS_CLUSTER_POOL:
            if tid == "sapper" and cycle < 3:
                continue
            if tid == "archer" and cycle < 2:
                continue
            pool.extend([tid] * max(1, w))
        return random.choice(pool) if pool else "grunt"

    def _cluster_spread(self, w: dict) -> float:
        return float(w.get("cluster_spread", config.CLUSTER_SPAWN_SPREAD))

    def _scale_scheduled_count(self, count: int) -> int:
        """普通模式预定波次：小怪潮数量约 ×NORMAL_WAVE_COUNT_MULT。"""
        if count <= 1:
            return count
        mult = getattr(config, "NORMAL_WAVE_COUNT_MULT", 1.0)
        if mult <= 1.0:
            return count
        return max(count, int(round(count * mult)))

    def _scale_spawn_interval(self, count: int, scaled: int, interval: float) -> float:
        """数量放大后缩短间隔，使单波出怪总时长与原版接近。"""
        if interval <= 0 or scaled <= 1 or count <= 1:
            return interval
        span = (count - 1) * interval
        return max(0.02, span / max(1, scaled - 1))

    def _enqueue_wave(self, w: dict) -> None:
        etype = w["type"]
        t0 = float(w["at"])
        cluster = bool(w.get("cluster", False))
        spread = self._cluster_spread(w)

        if cluster and "clusters" in w:
            n_clusters = int(w["clusters"])
            raw_size = int(w.get("cluster_size", w.get("count", 5)))
            size = self._scale_scheduled_count(raw_size)
            gap = float(w.get("cluster_interval", 4.0))
            inner = self._scale_spawn_interval(
                raw_size, size, float(w.get("interval", 0.06))
            )
            for _c in range(n_clusters):
                angle = math.tau * random.random()
                opts = {"cluster_angle": angle, "cluster_spread": spread}
                for i in range(size):
                    self.spawn_queue.append((t0 + _c * gap + i * inner, etype, opts))
        elif cluster:
            raw_count = int(w["count"])
            count = self._scale_scheduled_count(raw_count)
            interval = self._scale_spawn_interval(
                raw_count, count, float(w.get("interval", 0.06))
            )
            angle = math.tau * random.random()
            opts = {"cluster_angle": angle, "cluster_spread": spread}
            for i in range(count):
                self.spawn_queue.append((t0 + i * interval, etype, opts))
        else:
            raw_count = int(w["count"])
            count = self._scale_scheduled_count(raw_count)
            interval = self._scale_spawn_interval(
                raw_count, count, float(w.get("interval", 0.5))
            )
            for i in range(count):
                self.spawn_queue.append((t0 + i * interval, etype, {}))

        self.spawn_queue.sort(key=lambda x: x[0])

    def _spawn_from_opts(self, etype: str, opts: dict) -> dict:
        if opts.get("cluster_angle") is not None:
            angle = float(opts["cluster_angle"])
            spread = float(opts.get("cluster_spread", config.CLUSTER_SPAWN_SPREAD))
            x, y = spawn_in_cluster(angle, spread)
        else:
            x, y = spawn_at_edge()
        return {"type": etype, "x": x, "y": y}

    def _endless_use_cluster(self, batch_size: int) -> bool:
        if batch_size < 3 or self.endless_cycle < 2:
            return False
        return self.endless_cycle % 3 != 1

    def update(self, dt: float, *, advance_time: bool = True) -> list[dict]:
        if advance_time:
            self.elapsed += dt
        spawns = []

        while self.wave_index < len(self.waves):
            w = self.waves[self.wave_index]
            if self.elapsed < w["at"]:
                break
            self._enqueue_wave(w)
            self.wave_index += 1

        ready: list[tuple[str, dict]] = []
        remaining: list[tuple[float, str, dict]] = []
        for t, etype, opts in self.spawn_queue:
            if t <= self.elapsed:
                ready.append((etype, opts))
            else:
                remaining.append((t, etype, opts))
        self.spawn_queue = remaining

        for etype, opts in ready:
            spawns.append(self._spawn_from_opts(etype, opts))

        if self.wave_index >= len(self.waves) and not self.spawn_queue:
            self.all_scheduled_spawned = True

        if self.endless and self.all_scheduled_spawned and advance_time:
            self._endless_cd -= dt
            if self._endless_cd <= 0:
                self._endless_cd = self._endless_spawn_interval()
                self.endless_cycle += 1
                batch = self._endless_batch_size()
                if self._endless_use_cluster(batch):
                    etype = self._pick_endless_cluster_type()
                    angle = math.tau * random.random()
                    spread = float(config.CLUSTER_SPAWN_SPREAD)
                    opts = {"cluster_angle": angle, "cluster_spread": spread}
                    for _ in range(batch):
                        spawns.append(self._spawn_from_opts(etype, opts))
                else:
                    for _ in range(batch):
                        etype = self._pick_endless_type()
                        spawns.append(self._spawn_from_opts(etype, {}))

        return spawns
