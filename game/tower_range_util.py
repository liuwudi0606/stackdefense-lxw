"""各塔类型有效射程（用于射程环等 UI，兵营等无攻击射程返回 0）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.session import GameSession


def tower_attack_range(game: "GameSession", type_id: str) -> float:
    tdef = game.tower_defs.get(type_id, {})
    attack = tdef.get("attack")
    stats = game.stats

    if attack == "laser":
        from game.laser_combat import laser_range

        return laser_range(tdef, stats)
    if attack == "wind":
        from game.wind_combat import wind_range

        return wind_range(tdef, stats)
    if attack == "barracks":
        return 0.0
    if "range" in tdef:
        return float(tdef["range"]) * (1.0 + stats.tower_range_mult)
    return 0.0
