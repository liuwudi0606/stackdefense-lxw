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
    def __init__(
        self,
        wave_data: dict,
        enemy_defs: dict | None = None,
        endless: bool = False,
    ) -> None:
        self.waves = sorted(wave_data["waves"], key=lambda w: w["at"])
        self.enemy_defs = enemy_defs or {}
        self.wave_index = 0
        self.waves_triggered = 0
        self.surge_count = 0
        self.alert_message: str | None = None
        self.spawn_queue: list[tuple[float, str, dict]] = []
        self.all_scheduled_spawned = False
        self.elapsed = 0.0
        self.endless = endless
        self.endless_cycle = 0
        self._endless_cd = config.ENDLESS_INITIAL_COOLDOWN if endless else 999999.0

    def consume_alert(self) -> str | None:
        msg = self.alert_message
        self.alert_message = None
        return msg

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

    def retry_wave_index(self) -> int:
        """失败重试时回退到的预定波次下标（spawn_queue 或当前时刻所属波）。"""
        if not self.waves:
            return 0
        if self.spawn_queue:
            t_ref = min(t for t, _, _ in self.spawn_queue)
        else:
            t_ref = self.elapsed
        idx = 0
        for i, w in enumerate(self.waves):
            if float(w["at"]) <= t_ref + 0.001:
                idx = i
        return idx

    def rewind_to_wave(self, idx: int) -> None:
        """从指定预定波次重新触发（清空待刷队列）。"""
        if not self.waves:
            self.spawn_queue = []
            self.all_scheduled_spawned = False
            return
        idx = max(0, min(idx, len(self.waves) - 1))
        w = self.waves[idx]
        self.elapsed = float(w["at"])
        self.wave_index = idx
        self.waves_triggered = idx
        self.surge_count = idx // max(1, int(config.WAVE_SURGE_EVERY))
        self.alert_message = None
        self.spawn_queue = []
        self.all_scheduled_spawned = False

    def _enemy_tier(self, etype: str) -> str:
        return str(self.enemy_defs.get(etype, {}).get("tier", "normal"))

    def _advanced_count_mult(self, etype: str, wave_at: float, wave_num: int) -> float:
        tier = self._enemy_tier(etype)
        if tier == "boss":
            return 1.0
        t_prog = min(1.0, wave_at / 1200.0)
        w_prog = float(wave_num) * float(config.WAVE_ELITE_COUNT_PER_WAVE)
        if tier == "elite":
            return (
                1.0
                + config.WAVE_ELITE_COUNT_BONUS
                + w_prog
                + t_prog * 0.18
            )
        if tier == "heavy":
            return (
                1.0
                + config.WAVE_HEAVY_COUNT_BONUS
                + float(wave_num) * float(config.WAVE_HEAVY_COUNT_PER_WAVE)
                + t_prog * 0.12
            )
        return 1.0

    def _wave_count_mult(self, wave_at: float) -> float:
        full = float(getattr(config, "NORMAL_WAVE_COUNT_MULT", 1.0))
        if full <= 1.0:
            return 1.0
        early = float(getattr(config, "NORMAL_WAVE_EARLY_MULT", full))
        ramp = float(getattr(config, "NORMAL_WAVE_EARLY_RAMP_SEC", 0.0))
        if ramp <= 0 or wave_at >= ramp:
            return full
        early = min(early, full)
        t = max(0.0, min(1.0, wave_at / ramp))
        return early + (full - early) * t

    def _scale_scheduled_count(
        self,
        count: int,
        wave_at: float = 0.0,
        etype: str | None = None,
        wave_num: int = 0,
    ) -> int:
        """普通模式预定波次：数量 × 倍率（开局渐升至 NORMAL_WAVE_COUNT_MULT）。"""
        if count <= 1:
            return count
        mult = self._wave_count_mult(wave_at)
        if etype and wave_num > 0:
            mult *= self._advanced_count_mult(etype, wave_at, wave_num)
        if mult <= 1.0:
            return count
        return max(count, int(round(count * mult)))

    def _scale_spawn_interval(self, count: int, scaled: int, interval: float) -> float:
        """数量放大后缩短间隔，使单波出怪总时长与原版接近。"""
        if interval <= 0 or scaled <= 1 or count <= 1:
            return interval
        span = (count - 1) * interval
        return max(0.02, span / max(1, scaled - 1))

    def _enqueue_cluster_batch(
        self,
        etype: str,
        count: int,
        t0: float,
        spread: float,
        inner: float = 0.06,
    ) -> None:
        angle = math.tau * random.random()
        opts = {"cluster_angle": angle, "cluster_spread": spread}
        for i in range(count):
            self.spawn_queue.append((t0 + i * inner, etype, opts))

    def _enqueue_wave_extras(self, w: dict, wave_num: int) -> None:
        """在预定波次上追加少量高级怪，提高中后期威胁密度。"""
        if wave_num < 8:
            return
        t0 = float(w["at"]) + 2.5
        if wave_num >= 10 and wave_num % 2 == 0:
            self.spawn_queue.append((t0, "elite", {}))
        if wave_num >= 14 and wave_num % 3 == 0:
            self.spawn_queue.append((t0 + 1.2, "brute", {}))
        if wave_num >= 18 and wave_num % 4 == 0:
            self.spawn_queue.append((t0 + 2.0, "archer", {}))
        if wave_num >= 24 and wave_num % 5 == 0:
            self.spawn_queue.append((t0 + 2.8, "tank", {}))
        if wave_num >= 32 and wave_num % 6 == 0:
            self.spawn_queue.append((t0 + 3.5, "wraith", {}))

    def _enqueue_monster_surge(self, level: int) -> None:
        """每 10 条预定波次追加一团怪潮（成团 + 少量精英）。"""
        t0 = self.elapsed + 0.8
        spread = float(config.CLUSTER_SPAWN_SPREAD)
        grunt_n = 18 + level * 4
        runner_n = 12 + level * 3
        sapper_n = 8 + max(0, level - 1) * 2
        self._enqueue_cluster_batch("grunt", grunt_n, t0, spread)
        self._enqueue_cluster_batch("runner", runner_n, t0 + 4.0, spread)
        self._enqueue_cluster_batch("sapper", sapper_n, t0 + 8.0, spread)
        elite_n = 2 + level // 2
        brute_n = 2 + level // 3
        for j in range(elite_n):
            self.spawn_queue.append((t0 + 12.0 + j * 1.1, "elite", {}))
        for j in range(brute_n):
            self.spawn_queue.append((t0 + 14.5 + j * 1.3, "brute", {}))
        if level >= 2:
            self._enqueue_cluster_batch(
                "archer", 6 + level, t0 + 18.0, spread, inner=0.08
            )
        if level >= 3:
            for j in range(1 + level // 4):
                self.spawn_queue.append((t0 + 22.0 + j * 2.4, "tank", {}))
        if level >= 5:
            self.spawn_queue.append((t0 + 26.0, "wraith", {}))
        self.spawn_queue.sort(key=lambda x: x[0])

    def _enqueue_wave(self, w: dict) -> None:
        etype = w["type"]
        t0 = float(w["at"])
        wave_num = self.wave_index + 1
        cluster = bool(w.get("cluster", False))
        spread = self._cluster_spread(w)

        if cluster and "clusters" in w:
            n_clusters = int(w["clusters"])
            raw_size = int(w.get("cluster_size", w.get("count", 5)))
            size = self._scale_scheduled_count(raw_size, t0, etype, wave_num)
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
            count = self._scale_scheduled_count(raw_count, t0, etype, wave_num)
            interval = self._scale_spawn_interval(
                raw_count, count, float(w.get("interval", 0.06))
            )
            angle = math.tau * random.random()
            opts = {"cluster_angle": angle, "cluster_spread": spread}
            for i in range(count):
                self.spawn_queue.append((t0 + i * interval, etype, opts))
        else:
            raw_count = int(w["count"])
            count = self._scale_scheduled_count(raw_count, t0, etype, wave_num)
            interval = self._scale_spawn_interval(
                raw_count, count, float(w.get("interval", 0.5))
            )
            for i in range(count):
                self.spawn_queue.append((t0 + i * interval, etype, {}))

        self._enqueue_wave_extras(w, wave_num)
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
            self.waves_triggered += 1
            if (
                self.waves_triggered > 0
                and self.waves_triggered % int(config.WAVE_SURGE_EVERY) == 0
            ):
                level = self.waves_triggered // int(config.WAVE_SURGE_EVERY)
                self.surge_count = level
                self._enqueue_monster_surge(level)
                self.alert_message = (
                    f"⚠ 怪潮来袭！（第 {self.waves_triggered} 波）"
                )

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
