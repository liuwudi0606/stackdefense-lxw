"""地基详情面板文案。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import config

if TYPE_CHECKING:
    from game.session import GameSession


def base_detail_lines(game: "GameSession") -> list[str]:
    b = game.base
    s = game.stats
    lines: list[str] = [
        f"生命 {int(b.hp)} / {int(b.max_hp)}",
    ]
    if s.base_shield > 0 or b.shield > 0:
        sh = f"能量护盾 {int(b.shield)}"
        if s.base_shield > 0:
            sh += f" / {int(s.base_shield)}"
        if s.base_shield_regen > 0:
            sh += f" · 回复 {s.base_shield_regen:.1f}/秒"
        lines.append(sh)
    if s.base_regen > 0:
        lines.append(f"回复 {s.base_regen:.1f} / 秒")
    if s.base_thorns > 0:
        lines.append(f"反伤 {s.base_thorns:.0f} / 次（攻基地）")
    if b.pulse_enabled or s.base_pulse:
        from game.base_pulse import pulse_params

        params = pulse_params(s)
        if params:
            dmg, radius, pulse_cd = params
            cd = max(0.0, b.pulse_timer) if b.pulse_enabled else pulse_cd
            lvl = s.upgrade_stacks.get("base_pulse", 1)
            lines.append(
                f"脉冲环 Lv{lvl}：{dmg:.0f} 伤 · 半径 {radius:.0f} · "
                f"{'冷却 ' + f'{cd:.1f}s' if b.pulse_enabled else f'间隔 {pulse_cd:.1f}s'}"
            )
    if s.base_aura_slow > 0:
        lines.append(
            f"寒场：半径 {config.BASE_AURA_RADIUS:.0f} · "
            f"减速 {int(s.base_aura_slow * 100)}%"
        )
    if s.kill_heal > 0:
        lines.append(f"击杀回复 {s.kill_heal:.0f} / 只")

    lines.append("")
    lines.append(f"塔层 {game.tower_count()} / {game.max_tower_floors_limit()}")
    if game.guards:
        alive = sum(1 for g in game.guards if g.alive)
        lines.append(f"护卫 {alive} / {len(game.guards)}（场上）")

    base_fx: list[str] = []
    if s.base_hp_mult:
        sign = "+" if s.base_hp_mult > 0 else ""
        base_fx.append(f"最大生命 {sign}{int(s.base_hp_mult * 100)}%")
    if getattr(game, "meta_hp_mult", 0):
        base_fx.append(f"局外生命 +{int(game.meta_hp_mult * 100)}%")
    if base_fx:
        lines.append("")
        lines.append("【地基增益】")
        lines.extend(base_fx)

    lines.append("")
    lines.append("说明：点选底部塔种后，点地基或塔堆、拖放或")
    lines.append("双击塔种按钮即可叠建新层。")
    return lines
