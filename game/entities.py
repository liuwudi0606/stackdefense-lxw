import math
from collections.abc import Callable
from dataclasses import dataclass, field

import config
from game.iso import tower_screen_pos, tower_world_pos, world_to_screen


def dist(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


@dataclass
class Bullet:
    x: float
    y: float
    tx: float
    ty: float
    speed: float
    damage: float
    color: tuple[int, int, int]
    tower_type: str = "arrow"
    splash: float = 0
    slow_factor: float = 0
    slow_duration: float = 0
    alive: bool = True
    target: "Enemy | None" = None
    max_range: float = 500.0
    traveled: float = 0.0
    spawn_delay: float = 0.0

    def update(self, dt: float, enemies: list["Enemy"]) -> None:
        if self.spawn_delay > 0:
            self.spawn_delay -= dt
            return

        if self.target and not self.target.alive:
            self.target = None

        if self.target and self.target.alive:
            self.tx, self.ty = self.target.x, self.target.y
            hit_r = max(36, self.target.radius + 22)
            if dist(self.x, self.y, self.target.x, self.target.y) <= hit_r:
                self._apply_hit(enemies)
                self.alive = False
                return

        d = dist(self.x, self.y, self.tx, self.ty)
        if d < 6:
            self._apply_hit(enemies)
            self.alive = False
            return

        step = min(self.speed * dt, d)
        self.traveled += step
        if self.traveled > self.max_range * 1.15:
            self.alive = False
            return

        if step >= d:
            self.x, self.y = self.tx, self.ty
            self._apply_hit(enemies)
            self.alive = False
        else:
            self.x += (self.tx - self.x) / d * step
            self.y += (self.ty - self.y) / d * step

    def _apply_hit(self, enemies: list["Enemy"]) -> None:
        if self.splash > 0:
            cx, cy = self.x, self.y
            primary = self.target if self.target and self.target.alive else None
            if primary:
                cx, cy = primary.x, primary.y
            splash_dmg = self.damage * config.CANNON_SPLASH_SECONDARY_MULT
            for e in enemies:
                if not e.alive:
                    continue
                if dist(cx, cy, e.x, e.y) > self.splash:
                    continue
                if primary is not None and e is primary:
                    e.take_damage(self.damage)
                else:
                    e.take_damage(splash_dmg)
                e.apply_slow(self.slow_factor, self.slow_duration)
            return

        if self.target and self.target.alive:
            self.target.take_damage(self.damage)
            self.target.apply_slow(self.slow_factor, self.slow_duration)
            return

        # 双发第二箭时目标可能已被第一箭击杀，改判落点周围敌人
        best = None
        best_d = 99999.0
        for e in enemies:
            if not e.alive:
                continue
            dd = dist(self.x, self.y, e.x, e.y)
            if dd < 40 and dd < best_d:
                best_d = dd
                best = e
        if best:
            best.take_damage(self.damage)
            best.apply_slow(self.slow_factor, self.slow_duration)


@dataclass
class Enemy:
    type_id: str
    x: float
    y: float
    hp: float
    max_hp: float
    speed: float
    exp: int
    gold: int
    radius: float
    color: tuple[int, int, int]
    alive: bool = True
    slow_timer: float = 0
    slow_factor: float = 1.0
    frost_phase: float = 0.0
    in_base_aura: bool = False
    weakened: bool = False
    buffed: bool = False
    laser_resist: float = 1.0
    laser_vuln: float = 1.0
    wind_resist: float = 1.0
    attack_mode: str = "melee"
    damage: float = 6.0
    attack_range: float = 38.0
    attack_rate: float = 1.0
    attack_cd: float = 0.0
    aggro_guard_uid: int | None = None
    knockback_vx: float = 0.0
    knockback_vy: float = 0.0
    knockback_time: float = 0.0
    skill_cds: dict[str, float] = field(default_factory=dict)
    skill_flags: dict[str, bool] = field(default_factory=dict)

    def apply_slow(self, factor: float, duration: float) -> None:
        if factor <= 0 or duration <= 0:
            return
        self.slow_timer = max(self.slow_timer, duration)
        self.slow_factor = min(self.slow_factor, factor)

    def take_damage(self, amount: float) -> None:
        self.hp -= amount
        if self.hp <= 0:
            self.alive = False

    def is_slowed(self) -> bool:
        return self.slow_timer > 0

    def screen_pos(self) -> tuple[float, float]:
        return world_to_screen(self.x, self.y)


@dataclass
class Guard:
    uid: int
    x: float
    y: float
    hp: float
    max_hp: float
    damage: float
    attack_range: float
    attack_rate: float
    radius: float = config.GUARD_DEFAULT_RADIUS
    move_speed: float = config.GUARD_MOVE_SPEED_DEFAULT
    seek_range: float = config.GUARD_SEEK_RANGE_DEFAULT
    spawn_x: float = 0.0
    spawn_y: float = 0.0
    alive: bool = True
    attack_cd: float = 0.0
    source_floor: int = 0

    def take_damage(self, amount: float) -> None:
        self.hp -= amount
        if self.hp <= 0:
            self.alive = False

    def screen_pos(self) -> tuple[float, float]:
        return world_to_screen(self.x, self.y)


@dataclass
class TowerFloor:
    """叠在地基之上的塔层，每层一座。"""

    type_id: str
    floor: int
    level: int = 1
    cooldown: float = 0
    laser_target: "Enemy | None" = None
    laser_charge: float = 0.0
    laser_break_timer: float = 0.0
    laser_mode: str = "single"
    laser_auto: bool = True
    laser_sweeping: bool = False

    def world_pos(self) -> tuple[float, float]:
        return tower_world_pos(self.floor)

    def screen_pos(self) -> tuple[int, int]:
        return tower_screen_pos(self.floor)


@dataclass
class Base:
    hp: float
    max_hp: float
    shield: float = 0
    pulse_timer: float = 0
    pulse_enabled: bool = False
    pulse_flash: float = 0.0

    def recalc_max_hp(self, game) -> None:
        meta = getattr(game, "meta_hp_mult", 0.0)
        mult = 1.0 + meta + game.stats.base_hp_mult
        self.max_hp = config.BASE_HP_START * mult
        self.hp = min(self.hp, self.max_hp)

    def take_damage(self, amount: float) -> None:
        if self.shield > 0:
            absorb = min(self.shield, amount)
            self.shield -= absorb
            amount -= absorb
        self.hp -= amount

    def update(self, dt: float, game) -> None:
        if self.pulse_flash > 0:
            self.pulse_flash = max(0.0, self.pulse_flash - dt)
        if game.stats.base_regen > 0:
            self.hp = min(self.max_hp, self.hp + game.stats.base_regen * dt)
        cap = game.stats.base_shield
        if cap > 0 and game.stats.base_shield_regen > 0 and self.shield < cap:
            self.shield = min(cap, self.shield + game.stats.base_shield_regen * dt)
        if self.pulse_enabled:
            from game.base_pulse import pulse_params

            params = pulse_params(game.stats)
            if not params:
                return
            pulse_dmg, pulse_radius, pulse_cd = params
            self.pulse_timer -= dt
            if self.pulse_timer <= 0:
                self.pulse_timer = pulse_cd
                self.pulse_flash = 0.45
                for e in game.enemies:
                    if e.alive and dist(e.x, e.y, config.BASE_X, config.BASE_Y) < pulse_radius:
                        e.take_damage(pulse_dmg)


def find_target(
    ex: float,
    ey: float,
    enemies: list[Enemy],
    rng: float,
    *,
    eligible: Callable[[Enemy], bool] | None = None,
) -> Enemy | None:
    best = None
    best_d = rng
    for e in enemies:
        if not e.alive:
            continue
        if eligible is not None and not eligible(e):
            continue
        d = dist(ex, ey, e.x, e.y)
        if d <= rng and d < best_d:
            best_d = d
            best = e
    return best
