"""激光束绘制与命中特效。"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

import pygame

from game.entities import TowerFloor
from game.iso import world_to_screen
from game.laser_combat import enemies_in_laser_range, laser_phase, laser_range

if TYPE_CHECKING:
    from game.entities import Enemy
    from game.session import GameSession

_PHASE_STYLE = {
    1: {"width": 2, "outer": (140, 80, 220), "core": (220, 160, 255)},
    2: {"width": 5, "outer": (80, 160, 255), "core": (200, 240, 255)},
    3: {"width": 10, "outer": (255, 100, 240), "core": (255, 250, 255)},
}


def _beam_points(
    sx: float, sy: float, ex: float, ey: float, wobble: float
) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    mx = (sx + ex) * 0.5 + wobble
    my = (sy + ey) * 0.5 - wobble * 0.4
    return (int(sx), int(sy)), (int(mx), int(my)), (int(ex), int(ey))


def _draw_one_beam(
    surf: pygame.Surface,
    tsx: float,
    tsy: float,
    ex: float,
    ey: float,
    phase: int,
    phase_anim: float,
    floor: int,
    *,
    thin: bool = False,
) -> None:
    style = _PHASE_STYLE.get(phase, _PHASE_STYLE[1])
    if thin:
        style = {**style, "width": max(2, style["width"] - 2)}
    wobble = math.sin(phase_anim * 14 + floor) * (2 + phase)
    p0, pm, p1 = _beam_points(tsx, tsy, ex, ey, wobble)
    ow = style["width"] + 5
    pygame.draw.line(surf, style["outer"], p0, p1, ow)
    pygame.draw.lines(surf, style["outer"], False, [p0, pm, p1], style["width"] + 2)
    pygame.draw.lines(surf, style["core"], False, [p0, pm, p1], style["width"])


def draw_laser_beams(surf: pygame.Surface, game: "GameSession") -> None:
    phase_anim = game.fx_phase
    for tower in game.towers:
        if tower.type_id != "laser":
            continue
        tdef = game.tower_defs["laser"]
        wx, wy = tower.world_pos()
        tsx, tsy = world_to_screen(wx, wy)

        if tower.laser_sweeping:
            rng = laser_range(tdef, game.stats)
            targets = enemies_in_laser_range(game.enemies, rng)
            if not targets:
                continue
            for i, target in enumerate(targets):
                ex, ey = target.screen_pos()
                _draw_one_beam(
                    surf, tsx, tsy, ex, ey, 2, phase_anim, tower.floor + i, thin=True
                )
                pygame.draw.circle(surf, (180, 220, 255), (int(ex), int(ey)), 3)
            continue

        target = tower.laser_target
        if not target or not target.alive:
            continue
        phase = laser_phase(tdef, tower.laser_charge)
        style = _PHASE_STYLE.get(phase, _PHASE_STYLE[1])
        ex, ey = target.screen_pos()
        _draw_one_beam(surf, tsx, tsy, ex, ey, phase, phase_anim, tower.floor)

        if phase >= 2:
            pulse = 0.5 + 0.5 * math.sin(phase_anim * 10)
            ring_r = int(target.radius + 6 + phase * 2 + pulse * 3)
            ring = pygame.Surface((ring_r * 2 + 4, ring_r * 2 + 4), pygame.SRCALPHA)
            alpha = int(80 + 50 * pulse)
            pygame.draw.circle(
                ring,
                (*style["core"], alpha),
                (ring_r + 2, ring_r + 2),
                ring_r,
                2,
            )
            surf.blit(ring, (int(ex) - ring_r - 2, int(ey) - ring_r - 2))

        if phase >= 3:
            for i in range(4):
                ang = phase_anim * 8 + i * (math.tau / 4)
                px = int(ex + math.cos(ang) * (target.radius + 10))
                py = int(ey + math.sin(ang) * (target.radius + 6) * 0.55)
                pygame.draw.circle(surf, style["core"], (px, py), 3)

        core_r = 3 + phase
        pygame.draw.circle(surf, style["core"], (int(ex), int(ey)), core_r)
        pygame.draw.circle(surf, (255, 255, 255), (int(ex), int(ey)), max(1, core_r - 2))


def on_laser_tick_visual(
    game: "GameSession",
    tower: TowerFloor,
    target: "Enemy",
    nominal_dps: float,
) -> None:
    from game.buff_fx import spawn_fx

    phase = laser_phase(game.tower_defs["laser"], tower.laser_charge)
    spawn_fx(
        game,
        "laser_hit",
        target.x,
        target.y,
        0.18,
        phase=phase,
        seed=random.random(),
    )
