"""钱塔光效：待机金环、结算金币脉冲。"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import pygame

import config
from game.buff_fx import _ellipse_surface, spawn_fx
from game.camera import view_zoom
from game.iso import ISO_Y_SCALE, tower_screen_pos, world_to_screen

if TYPE_CHECKING:
    from game.session import GameSession


def on_mint_tick_visual(
    game: "GameSession",
    wx: float,
    wy: float,
    rng: float,
    enemy_count: int,
    gold: int,
) -> None:
    spawn_fx(
        game,
        "mint_pulse",
        wx,
        wy,
        0.85,
        rng=rng,
        count=enemy_count,
        gold=gold,
        seed=random.random() * 10,
    )
    if gold > 0:
        spawn_fx(game, "gold", wx, wy - 12, 0.55, amount=gold)


def draw_mint_tower_idle(surf, game: "GameSession") -> None:
    """钱塔待机：金环呼吸 + 蓄能亮点。"""
    from game.mint_combat import mint_interval, mint_range

    z = view_zoom()
    phase = game.fx_phase
    for tower in game.towers:
        if tower.type_id != "mint":
            continue
        tdef = game.tower_defs.get("mint", {})
        sx, sy = tower_screen_pos(tower.floor)
        rng = mint_range(tdef, game.stats)
        rx = max(14, int(rng * z * 0.42))
        ry = max(8, int(rng * z * 0.42 * ISO_Y_SCALE))
        pulse = 0.5 + 0.5 * math.sin(phase * 2.4 + tower.floor * 0.7)
        alpha = int(28 + 38 * pulse)
        ring = _ellipse_surface(rx, ry, (255, 210, 70, alpha), 2)
        surf.blit(ring, ring.get_rect(center=(sx, sy)))
        inner = _ellipse_surface(
            max(8, rx - 6), max(5, ry - 4), (255, 240, 140, int(18 + 22 * pulse)), 1
        )
        surf.blit(inner, inner.get_rect(center=(sx, sy)))
        iv = mint_interval(tdef, tower, game.stats)
        ready = 1.0 - max(0.0, min(1.0, tower.cooldown / max(0.01, iv)))
        if ready > 0.55:
            glow = int(50 + 80 * ready * pulse)
            dot = _ellipse_surface(6, 4, (255, 230, 100, glow))
            surf.blit(dot, dot.get_rect(center=(sx, sy - int(14 * z))))
        for i in range(3):
            ang = phase * 1.6 + tower.floor + i * (math.tau / 3)
            px = sx + int(math.cos(ang) * (rx + 4))
            py = sy + int(math.sin(ang) * (ry + 3) * ISO_Y_SCALE)
            pygame.draw.circle(surf, (255, 220, 90), (px, py), 2)


def draw_mint_pulse_fx(surf, game: "GameSession", fx) -> None:
    from game.fonts import get_font

    z = view_zoom()
    p = fx.p()
    fade = 1.0 - p * 0.85
    sx, sy = world_to_screen(fx.wx, fx.wy)
    bx, by = world_to_screen(config.BASE_X, config.BASE_Y)
    rng = fx.extra.get("rng", 300) * z
    count = int(fx.extra.get("count", 0))
    gold = int(fx.extra.get("gold", 0))
    seed = fx.extra.get("seed", 0.0)

    brx = max(24, int(rng))
    bry = max(14, int(rng * ISO_Y_SCALE))
    ring_a = int(120 * fade * (0.7 + 0.3 * min(1.0, count / 8)))
    burst = _ellipse_surface(brx, bry, (255, 200, 60, ring_a), 3)
    surf.blit(burst, burst.get_rect(center=(int(bx), int(by))))

    if count > 0:
        for i in range(min(10, count + 2)):
            ang = seed + i * (math.tau / max(1, count)) + fx.t * 2.5
            dist_e = rng * (0.35 + 0.55 * (i / max(1, count + 1)))
            ex = bx + int(math.cos(ang) * dist_e)
            ey = by + int(math.sin(ang) * dist_e * ISO_Y_SCALE)
            pygame.draw.line(
                surf,
                (255, 230, 120, int(90 * fade)),
                (sx, sy - int(8 * z)),
                (ex, ey),
                max(1, 2 - i // 4),
            )

    for i in range(6 + min(6, count)):
        ang = seed + i * 1.4 + fx.t * 6
        d = p * (18 + i * 3)
        pygame.draw.circle(
            surf,
            (255, 220, 80),
            (
                sx + int(math.cos(ang) * d * 0.6),
                sy - int(12 * z) - int(p * 22) - i * 2,
            ),
            max(1, 4 - int(p * 2)),
        )

    if gold > 0:
        font = get_font(17)
        txt = font.render(f"+{gold}", True, (255, 245, 160))
        ty = sy - int(28 * z) - int(p * 18)
        surf.blit(txt, txt.get_rect(center=(sx, ty)))
