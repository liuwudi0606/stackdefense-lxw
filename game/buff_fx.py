"""增益/减益的视觉呈现（基地光环、触发特效、塔强化标识）。"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

import config
from game.camera import base_screen, view_zoom
from game.fonts import get_font
from game.iso import ISO_Y_SCALE, scaled_size, stack_scale, tower_screen_pos, world_to_screen

if TYPE_CHECKING:
    from game.entities import Enemy
    from game.session import GameSession


@dataclass
class WorldFx:
    kind: str
    wx: float
    wy: float
    t: float = 0.0
    duration: float = 0.5
    extra: dict = field(default_factory=dict)

    def update(self, dt: float) -> bool:
        self.t += dt
        return self.t < self.duration

    def p(self) -> float:
        return min(1.0, self.t / max(0.01, self.duration))


def spawn_fx(game: "GameSession", kind: str, wx: float, wy: float, duration: float = 0.5, **extra) -> None:
    game.world_fx.append(WorldFx(kind=kind, wx=wx, wy=wy, duration=duration, extra=extra))


def update_buff_fx(game: "GameSession", dt: float) -> None:
    s = game.stats
    if s.base_regen > 0:
        game._regen_fx_cd -= dt
        if game._regen_fx_cd <= 0:
            game._regen_fx_cd = 0.45
            spawn_fx(
                game,
                "regen",
                config.BASE_X,
                config.BASE_Y,
                0.7,
                seed=random.random() * 10,
            )

    game.world_fx = [fx for fx in game.world_fx if fx.update(dt)]


def _ellipse_surface(rx: int, ry: int, color: tuple, width: int = 0) -> pygame.Surface:
    surf = pygame.Surface((rx * 2 + 8, ry * 2 + 8), pygame.SRCALPHA)
    rect = surf.get_rect()
    if width:
        pygame.draw.ellipse(surf, color, rect, width)
    else:
        pygame.draw.ellipse(surf, color, rect)
    return surf


def draw_range_ring(surf: pygame.Surface, game: "GameSession") -> None:
    if game.stats.tower_range_mult <= 0 or not game.towers:
        return
    from game.tower_range_util import tower_attack_range

    max_r = 0.0
    for t in game.towers:
        r = tower_attack_range(game, t.type_id)
        max_r = max(max_r, r)
    if max_r <= 0:
        return
    z = view_zoom()
    rx = int(max_r * z)
    ry = int(max_r * ISO_Y_SCALE * z)
    pulse = 0.5 + 0.5 * math.sin(game.fx_phase * 1.5)
    alpha = int(22 + 14 * pulse)
    ring = _ellipse_surface(rx, ry, (255, 220, 100, alpha), 2)
    surf.blit(ring, ring.get_rect(center=base_screen()))


def draw_base_buff_auras(surf: pygame.Surface, game: "GameSession") -> None:
    """地基周围持续光环（画在塔层之下）。"""
    s = game.stats
    b = game.base
    cx, cy = base_screen()
    z = view_zoom()
    phase = game.fx_phase
    hp_bonus = s.base_hp_mult + getattr(game, "meta_hp_mult", 0.0)

    if s.base_aura_slow > 0:
        rx = int(config.BASE_AURA_RADIUS * z)
        ry = int(config.BASE_AURA_RADIUS * ISO_Y_SCALE * z)
        a = int(35 + 25 * (0.55 + 0.45 * math.sin(phase * 2.2)))
        ring = _ellipse_surface(rx, ry, (120, 190, 255, a), 3)
        surf.blit(ring, ring.get_rect(center=(cx, cy)))

    if s.base_thorns > 0:
        r = int((config.BASE_RADIUS + 14) * z)
        for i in range(10):
            ang = phase * 1.8 + i * (math.tau / 10)
            x1 = cx + int(math.cos(ang) * r)
            y1 = cy + int(math.sin(ang) * r * ISO_Y_SCALE)
            x2 = cx + int(math.cos(ang) * (r + 10))
            y2 = cy + int(math.sin(ang) * (r + 10) * ISO_Y_SCALE)
            pygame.draw.line(surf, (220, 70, 70), (x1, y1), (x2, y2), 2)
        spike = _ellipse_surface(r + 6, int((r + 6) * ISO_Y_SCALE), (255, 80, 80, 40), 2)
        surf.blit(spike, spike.get_rect(center=(cx, cy)))

    if s.base_regen > 0:
        mist = _ellipse_surface(
            int((config.BASE_RADIUS + 8) * z),
            int((config.BASE_RADIUS + 8) * ISO_Y_SCALE * z),
            (80, 220, 120, 28),
        )
        surf.blit(mist, mist.get_rect(center=(cx, cy)))

    if hp_bonus > 0:
        br = int((config.BASE_RADIUS + 6) * z)
        for i in range(6):
            ang = i * (math.tau / 6) + phase * 0.4
            px = cx + int(math.cos(ang) * br)
            py = cy + int(math.sin(ang) * br * ISO_Y_SCALE)
            pygame.draw.circle(surf, (180, 150, 90), (px, py), 5)
            pygame.draw.circle(surf, (90, 75, 50), (px, py), 5, 1)
    elif s.base_hp_mult < 0:
        crack = _ellipse_surface(
            int((config.BASE_RADIUS + 4) * z),
            int((config.BASE_RADIUS + 4) * ISO_Y_SCALE * z),
            (255, 60, 60, 35),
            2,
        )
        surf.blit(crack, crack.get_rect(center=(cx, cy)))

    if s.kill_heal > 0:
        for i in range(5):
            ang = phase * 2.5 + i * (math.tau / 5)
            px = cx + int(math.cos(ang) * (config.BASE_RADIUS + 18) * z)
            py = cy + int(math.sin(ang) * (config.BASE_RADIUS + 18) * ISO_Y_SCALE * z)
            pygame.draw.circle(surf, (100, 255, 140), (px, py), 4)

    if b.pulse_enabled or s.base_pulse:
        from game.base_pulse import pulse_params

        params = pulse_params(s)
        pulse_radius = params[1] if params else config.BASE_PULSE_RADIUS
        total = params[2] if params else config.BASE_PULSE_COOLDOWN
        charge = 1.0 - max(0.0, b.pulse_timer) / max(0.01, total)
        pr = int(pulse_radius * (0.55 + 0.12 * charge) * z)
        pry = int(pr * ISO_Y_SCALE)
        pa = int(40 + 35 * charge)
        pre = _ellipse_surface(pr, pry, (255, 200, 80, pa), 2)
        surf.blit(pre, pre.get_rect(center=(cx, cy)))

    if b.shield > 0:
        ratio = min(1.0, b.shield / max(50.0, b.max_hp * 0.15))
        sr = int((config.BASE_RADIUS + 12 + 6 * ratio) * z)
        sry = int(sr * ISO_Y_SCALE)
        sh = _ellipse_surface(sr, sry, (100, 180, 255, int(50 + 40 * ratio)))
        surf.blit(sh, sh.get_rect(center=(cx, cy)))
        pygame.draw.ellipse(
            surf,
            (140, 210, 255),
            pygame.Rect(cx - sr, cy - sry, sr * 2, sry * 2),
            2,
        )
        for i in range(6):
            ang = phase * 1.2 + i * (math.tau / 6)
            hx = cx + int(math.cos(ang) * sr)
            hy = cy + int(math.sin(ang) * sry)
            pygame.draw.circle(surf, (200, 240, 255), (hx, hy), 3)


def draw_base_pulse_burst(surf: pygame.Surface, game: "GameSession") -> None:
    b = game.base
    if b.pulse_flash <= 0:
        return
    cx, cy = base_screen()
    z = view_zoom()
    progress = 1.0 - b.pulse_flash / 0.45
    from game.base_pulse import pulse_params

    params = pulse_params(game.stats)
    pulse_radius = params[1] if params else config.BASE_PULSE_RADIUS
    rx = int(pulse_radius * (0.25 + 0.75 * progress) * z)
    ry = int(rx * ISO_Y_SCALE)
    alpha = int(200 * (1.0 - progress))
    ring = _ellipse_surface(rx, ry, (255, 200, 80, alpha), 4)
    surf.blit(ring, ring.get_rect(center=(cx, cy)))
    inner = _ellipse_surface(
        max(8, rx - 20), max(6, ry - 12), (255, 240, 180, max(0, alpha - 60)), 2
    )
    surf.blit(inner, inner.get_rect(center=(cx, cy)))


def draw_base_buff_layers(surf: pygame.Surface, game: "GameSession") -> None:
    draw_base_buff_auras(surf, game)
    draw_base_pulse_burst(surf, game)


def draw_tower_buff_glows(surf: pygame.Surface, game: "GameSession") -> None:
    s = game.stats
    dmg_on = s.tower_damage_mult > 0 or any(s.type_damage.values())
    rate_on = s.tower_fire_rate_mult > 0
    sc = stack_scale()
    for tower in game.towers:
        sx, sy = tower_screen_pos(tower.floor)
        hw, hh = scaled_size(46, 24), scaled_size(28, 14)
        rect = pygame.Rect(sx - hw, sy - hh, hw * 2, hh * 2)
        if dmg_on:
            glow = int(35 + 20 * math.sin(game.fx_phase * 3 + tower.floor))
            overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
            overlay.fill((255, 200, 80, glow))
            surf.blit(overlay, rect.topleft)
        if rate_on:
            pygame.draw.ellipse(surf, (255, 160, 90), rect, 2)
        if tower.type_id == "arrow" and s.double_shot_chance > 0:
            badge = pygame.Rect(sx + 28, sy - 20, 18, 16)
            pygame.draw.rect(surf, (70, 100, 160), badge, border_radius=3)
            # small "2" via circle dots
            pygame.draw.circle(surf, (220, 235, 255), (badge.centerx - 3, badge.centery), 2)
            pygame.draw.circle(surf, (220, 235, 255), (badge.centerx + 3, badge.centery), 2)
        if tower.type_id == "slow" and s.slow_mult > 0:
            pygame.draw.ellipse(surf, (100, 200, 255), rect.inflate(6, 4), 2)
        if tower.type_id == "cannon" and s.splash_mult > 0:
            pygame.draw.ellipse(surf, (255, 140, 60), rect.inflate(8, 6), 2)
        if tower.type_id == "wind" and (
            s.wind_fan_mult > 0
            or s.wind_knockback_mult > 0
            or s.wind_rate_mult > 0
            or s.wind_range_mult > 0
        ):
            pygame.draw.ellipse(surf, (120, 220, 180), rect.inflate(6, 4), 2)
        if tower.type_id == "laser" and (
            s.laser_ramp_mult > 0 or s.laser_cap_mult > 0 or s.type_damage.get("laser", 0) > 0
        ):
            pygame.draw.ellipse(surf, (200, 120, 255), rect.inflate(4, 4), 2)
            if tower.laser_target and tower.laser_charge > 0:
                pulse = int(30 + 25 * math.sin(game.fx_phase * 6 + tower.floor))
                dot = pygame.Surface((20, 20), pygame.SRCALPHA)
                dot.fill((255, 160, 255, pulse))
                surf.blit(dot, (sx - 10, sy - 28))


def draw_enemy_buff_marks(
    surf: pygame.Surface, e: "Enemy", game: "GameSession", *, show_hud: bool
) -> None:
    if not show_hud:
        return
    sx, sy = int(e.screen_pos()[0]), int(e.screen_pos()[1])
    r = int(e.radius)

    if e.weakened:
        pygame.draw.circle(surf, (180, 100, 255), (sx, sy), r + 5, 2)
        weak_ic = get_font(18).render("弱", True, (210, 170, 255))
        surf.blit(weak_ic, (sx + r - 4, sy - r - 8))
    if e.buffed:
        pygame.draw.circle(surf, (255, 90, 90), (sx, sy), r + 5, 2)
        buff_ic = get_font(18).render("强", True, (255, 150, 130))
        surf.blit(buff_ic, (sx + r - 4, sy - r - 8))
    if e.laser_resist < 0.95:
        pygame.draw.circle(surf, (160, 140, 255), (sx, sy), r + 7, 2)
        ic = get_font(16).render("盾", True, (200, 190, 255))
        surf.blit(ic, (sx - r - 2, sy - r - 6))
    elif e.laser_vuln > 1.05:
        pygame.draw.circle(surf, (255, 120, 200), (sx, sy), r + 7, 2)
        ic = get_font(16).render("灼", True, (255, 200, 240))
        surf.blit(ic, (sx - r - 2, sy - r - 6))
    if e.wind_resist < 0.5:
        pygame.draw.circle(surf, (100, 180, 150), (sx, sy), r + 7, 2)
        ic = get_font(16).render("沉", True, (160, 230, 200))
        surf.blit(ic, (sx + r - 6, sy - r - 6))
    if e.skill_flags.get("enraged"):
        pygame.draw.circle(surf, (255, 80, 60), (sx, sy), r + 9, 2)
        ic = get_font(16).render("怒", True, (255, 160, 120))
        surf.blit(ic, (sx - r - 4, sy + r - 10))

    if e.in_base_aura:
        pygame.draw.circle(surf, (140, 200, 255), (sx, sy), r + 6, 2)

    if e.is_slowed():
        frost_r = r + 6
        frost = pygame.Surface((frost_r * 2 + 4, frost_r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(frost, (100, 180, 255, 90), (frost_r + 2, frost_r + 2), frost_r)
        surf.blit(frost, (sx - frost_r - 2, sy - frost_r - 2))
        for i in range(6):
            ang = e.frost_phase + i * (math.tau / 6)
            px = sx + int(math.cos(ang) * (frost_r + 4))
            py = sy + int(math.sin(ang) * (frost_r + 4) * 0.55)
            pygame.draw.circle(surf, (200, 240, 255), (px, py), 3)
        ic = get_font(18).render("冻", True, (220, 245, 255))
        surf.blit(ic, (sx - 8, sy - frost_r - 18))


def draw_world_fx(surf: pygame.Surface, game: "GameSession") -> None:
    cx, cy = base_screen()
    z = view_zoom()
    for fx in game.world_fx:
        sx, sy = world_to_screen(fx.wx, fx.wy)
        sx, sy = int(sx), int(sy)
        p = fx.p()
        if fx.kind == "regen":
            for i in range(3):
                off = fx.extra.get("seed", 0) + i
                px = cx + int(math.sin(off + fx.t * 4) * 20 * z)
                py = cy - int((20 + p * 40 + i * 8) * z)
                pygame.draw.circle(surf, (120, 255, 160), (px, py), max(1, 3 - int(p * 2)))
        elif fx.kind == "thorn":
            for i in range(8):
                ang = i * (math.tau / 8)
                d = 12 + p * 28
                x2 = sx + int(math.cos(ang) * d)
                y2 = sy + int(math.sin(ang) * d * ISO_Y_SCALE)
                pygame.draw.line(surf, (255, 90, 90), (sx, sy), (x2, y2), 2)
        elif fx.kind == "drain":
            tx = fx.extra.get("tx", cx)
            ty = fx.extra.get("ty", cy)
            tsx, tsy = world_to_screen(tx, ty)
            lx = sx + (cx - tsx) * p
            ly = sy + (cy - tsy) * p
            pygame.draw.line(surf, (80, 255, 120), (int(tsx), int(tsy)), (int(lx), int(ly)), 3)
            pygame.draw.circle(surf, (140, 255, 180), (int(lx), int(ly)), 5)
        elif fx.kind == "gold":
            for i in range(5):
                ang = i * 1.2 + fx.t * 5
                d = p * 22
                pygame.draw.circle(
                    surf,
                    (255, 220, 80),
                    (sx + int(math.cos(ang) * d), sy + int(math.sin(ang) * d * 0.5) - int(p * 15)),
                    max(1, 4 - int(p * 3)),
                )
        elif fx.kind == "exp":
            for i in range(4):
                ang = i * 1.5 + fx.t * 4
                d = p * 18
                pygame.draw.circle(
                    surf,
                    (120, 180, 255),
                    (sx + int(math.cos(ang) * d), sy + int(math.sin(ang) * d * 0.5)),
                    max(1, 3 - int(p * 2)),
                )
        elif fx.kind == "muzzle":
            col = fx.extra.get("color", (255, 200, 100))
            rad = int(8 * (1.0 - p))
            pygame.draw.circle(surf, col, (sx, sy), max(2, rad))
            if fx.extra.get("twin"):
                pygame.draw.circle(surf, col, (sx + 6, sy - 4), max(2, rad - 2))
        elif fx.kind == "slam":
            rad = int(fx.extra.get("radius", 100) * view_zoom() * (0.6 + 0.4 * p))
            z = view_zoom()
            rx = max(20, rad)
            ry = max(12, int(rad * ISO_Y_SCALE))
            ring = _ellipse_surface(rx, ry, (255, 120, 80, int(140 * (1.0 - p))), 3)
            surf.blit(ring, ring.get_rect(center=(sx, sy)))
        elif fx.kind == "lightning":
            for i in range(6):
                ang = fx.extra.get("seed", 0) + i * 1.05 + fx.t * 8
                d = (1.0 - p) * (30 + i * 6)
                pygame.draw.line(
                    surf,
                    (200, 220, 255),
                    (sx, sy),
                    (sx + int(math.cos(ang) * d), sy + int(math.sin(ang) * d * ISO_Y_SCALE)),
                    max(1, 3 - i // 2),
                )
            pygame.draw.circle(surf, (240, 250, 255), (sx, sy), max(3, int(14 * (1.0 - p))))
        elif fx.kind == "wind_gust":
            aim = fx.extra.get("aim", 0.0)
            rng = fx.extra.get("rng", 120)
            half = fx.extra.get("half_angle", 0.4)
            fade = 1.0 - p
            alpha = int(90 * fade)
            bx, by = sx, sy
            ex = bx + int(math.cos(aim) * rng)
            ey = by + int(math.sin(aim) * rng * ISO_Y_SCALE)
            left = aim + half
            right = aim - half
            lx = bx + int(math.cos(left) * rng * 0.85)
            ly = by + int(math.sin(left) * rng * 0.85 * ISO_Y_SCALE)
            rx = bx + int(math.cos(right) * rng * 0.85)
            ry = by + int(math.sin(right) * rng * 0.85 * ISO_Y_SCALE)
            fan = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)
            pygame.draw.polygon(
                fan,
                (140, 220, 200, alpha),
                [(bx, by), (lx, ly), (ex, ey), (rx, ry)],
            )
            surf.blit(fan, (0, 0))
            for i in range(5):
                t = i / 4
                px = bx + int(math.cos(aim) * rng * t * fade)
                py = by + int(math.sin(aim) * rng * t * ISO_Y_SCALE * fade)
                pygame.draw.circle(surf, (200, 255, 230), (px, py), max(1, 3 - i // 2))
        elif fx.kind == "laser_hit":
            phase = fx.extra.get("phase", 1)
            col = (255, 180, 255) if phase >= 3 else (180, 220, 255)
            for i in range(3 + phase):
                ang = fx.extra.get("seed", 0) + i * 2.1 + fx.t * 12
                d = (1.0 - p) * (10 + phase * 4)
                pygame.draw.circle(
                    surf,
                    col,
                    (sx + int(math.cos(ang) * d), sy + int(math.sin(ang) * d * 0.55)),
                    max(1, 3 - int(p * 2)),
                )


def on_base_thorns_hit(game: "GameSession", ex: float, ey: float) -> None:
    spawn_fx(game, "thorn", ex, ey, 0.35)


def on_enemy_killed_visual(game: "GameSession", enemy: "Enemy") -> None:
    if game.stats.kill_heal > 0:
        spawn_fx(
            game,
            "drain",
            enemy.x,
            enemy.y,
            0.4,
            tx=config.BASE_X,
            ty=config.BASE_Y,
        )
    if game.stats.gold_mult > 0:
        spawn_fx(game, "gold", enemy.x, enemy.y, 0.45)
    if game.stats.exp_mult > 0:
        spawn_fx(game, "exp", enemy.x, enemy.y, 0.4)


def on_tower_shot_visual(
    game: "GameSession", wx: float, wy: float, tower_type: str, shots: int, color: tuple
) -> None:
    spawn_fx(
        game,
        "muzzle",
        wx,
        wy,
        0.12,
        color=color,
        twin=shots > 1 and tower_type == "arrow",
    )
