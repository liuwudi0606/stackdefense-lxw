"""地基脉冲环：按叠层计算伤害、半径与冷却。"""

from __future__ import annotations

import config
from game.stats import RunStats


def pulse_stack_level(stats: RunStats) -> int:
    return max(0, stats.upgrade_stacks.get("base_pulse", 0))


def pulse_params(
    stats: RunStats, *, after_pick: bool = False
) -> tuple[float, float, float] | None:
    """返回 (伤害, 半径, 冷却秒)。after_pick=True 表示选中本卡之后的数值。"""
    lvl = pulse_stack_level(stats)
    if after_pick:
        lvl += 1
    if lvl <= 0 and not stats.base_pulse:
        return None
    lvl = max(1, lvl)
    dmg = config.BASE_PULSE_DAMAGE + (lvl - 1) * config.BASE_PULSE_DAMAGE_PER_STACK
    radius = config.BASE_PULSE_RADIUS + (lvl - 1) * config.BASE_PULSE_RADIUS_PER_STACK
    cd = max(
        config.BASE_PULSE_COOLDOWN_MIN,
        config.BASE_PULSE_COOLDOWN - (lvl - 1) * config.BASE_PULSE_COOLDOWN_PER_STACK,
    )
    return dmg, radius, cd


def pulse_pick_rows(stats: RunStats) -> list[tuple[str, str | None]]:
    cur = pulse_params(stats)
    nxt = pulse_params(stats, after_pick=True)
    if nxt is None:
        return []
    nd, nr, nc = nxt
    if cur is None:
        return [
            ("脉冲伤害", f"{nd:.0f}"),
            ("脉冲半径", f"{nr:.0f}"),
            ("脉冲间隔", f"{nc:.1f}秒"),
        ]
    cd, cr, cc = cur
    lines: list[tuple[str, str | None]] = []
    if abs(nd - cd) > 0.01:
        lines.append(("脉冲伤害", f"{cd:.0f} -> {nd:.0f}"))
    else:
        lines.append(("脉冲伤害", f"{cd:.0f}"))
    if abs(nr - cr) > 0.01:
        lines.append(("脉冲半径", f"{cr:.0f} -> {nr:.0f}"))
    else:
        lines.append(("脉冲半径", f"{cr:.0f}"))
    if abs(nc - cc) > 0.01:
        lines.append(("脉冲间隔", f"{cc:.1f}秒 -> {nc:.1f}秒"))
    else:
        lines.append(("脉冲间隔", f"{cc:.1f}秒"))
    return lines
