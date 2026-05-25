"""粗略数值体检（非完整模拟，仅供平衡讨论）。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config

towers = json.loads((ROOT / "data/towers.json").read_text(encoding="utf-8"))
enemies = json.loads((ROOT / "data/enemies.json").read_text(encoding="utf-8"))
waves = json.loads((ROOT / "data/waves.json").read_text(encoding="utf-8"))["waves"]

BASE_HP = config.BASE_HP_START
START_GOLD = config.START_GOLD


def stack_mult(n: int) -> float:
    if n <= 1:
        return 1.0
    return 1.0 / (1.0 + config.TOWER_TYPE_STACK_PENALTY * (n - 1))


def tower_dps(tid: str, lvl: int = 1, stacks: int = 1, stats: dict | None = None) -> float:
    stats = stats or {}
    td = towers[tid]
    sm = stack_mult(stacks)
    dmg_m = 1 + 0.18 * (lvl - 1)
    rate_m = 1 + 0.1 * (lvl - 1)
    gdm = 1 + stats.get("tower_damage_mult", 0) + stats.get("type_damage", {}).get(tid, 0)
    grm = 1 + stats.get("tower_fire_rate_mult", 0)
    if td.get("attack") == "laser":
        return td["base_dps"] * td["max_ramp_mult"] * gdm * dmg_m * sm
    if td.get("attack") in ("wind", "barracks"):
        return 0.0
    dmg = td["damage"] * gdm * dmg_m * sm
    rate = td["fire_rate"] * grm * rate_m
    return dmg * rate


def hp_at_time(base_hp: float, elapsed: float) -> float:
    return base_hp * (1.0 + config.WAVE_HP_TIME_SCALE * elapsed)


def main() -> None:
    print("=== 5 层同塔有效 DPS（含叠层惩罚）===")
    for tid in ("arrow", "cannon", "laser"):
        single = tower_dps(tid)
        stacked = tower_dps(tid, stacks=5) * 5
        print(f"  {tid}: 单层 {single:.1f}  五层合计 {stacked:.1f}  (旧版约 {single*5:.1f})")

    print("\n=== 激光峰值 vs 抗性（满蓄）===")
    peak = tower_dps("laser")
    for eid in ("shielded", "juggernaut", "colossus", "boss"):
        ed = enemies[eid]
        fac = max(0.05, ed.get("laser_resist", 1) * ed.get("laser_vuln", 1))
        hp = hp_at_time(ed["hp"], 400)
        print(f"  {eid}: ttk@400s={hp/(peak*fac):.1f}s  hp={hp:.0f}")

    print(f"\nENDLESS_MODE={config.ENDLESS_MODE}")
    print(f"第10层箭塔造价≈{int(towers['arrow']['cost'] * (1 + config.BUILD_COST_PER_FLOOR * 9))} 金")


if __name__ == "__main__":
    main()
