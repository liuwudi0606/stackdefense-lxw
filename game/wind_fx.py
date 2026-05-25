"""风塔扇形气流特效。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from game.buff_fx import spawn_fx

if TYPE_CHECKING:
    from game.session import GameSession


def on_wind_gust_visual(
    game: "GameSession",
    wx: float,
    wy: float,
    aim_rad: float,
    rng: float,
    half_angle: float,
    hit_count: int,
) -> None:
    spawn_fx(
        game,
        "wind_gust",
        wx,
        wy,
        0.4,
        aim=aim_rad,
        rng=rng,
        half_angle=half_angle,
        hits=hit_count,
    )
