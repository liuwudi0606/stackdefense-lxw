"""运行时加成汇总（Roguelike 强化叠加）。"""

import config


class RunStats:
    def __init__(self) -> None:
        self.base_hp_mult = 0.0
        self.base_regen = 0.0
        self.base_thorns = 0
        self.base_pulse = False
        self.base_aura_slow = 0.0
        self.base_shield = 0.0
        self.base_shield_regen = 0.0
        self.kill_heal = 0

        self.tower_damage_mult = 0.0
        self.tower_fire_rate_mult = 0.0
        self.tower_range_mult = 0.0
        self.type_damage: dict[str, float] = {}
        self.slow_mult = 0.0
        self.splash_mult = 0.0
        self.double_shot_chance = 0.0
        self.laser_ramp_mult = 0.0
        self.laser_cap_mult = 0.0
        self.laser_range_mult = 0.0
        self.laser_sweep_unlock = False
        self.wind_fan_mult = 0.0
        self.wind_knockback_mult = 0.0
        self.wind_rate_mult = 0.0
        self.wind_range_mult = 0.0
        self.barracks_spawn_rate_mult = 0.0
        self.barracks_guard_hp_mult = 0.0
        self.barracks_guard_damage_mult = 0.0
        self.barracks_guard_rate_mult = 0.0
        self.barracks_max_guards_bonus = 0
        self.barracks_spawn_count_bonus = 0
        self.mint_yield_mult = 0.0
        self.mint_hoard_mult = 0.0
        self.mint_rate_mult = 0.0
        self.mint_range_mult = 0.0
        self.mint_cap_mult = 0.0

        self.exp_mult = 0.0
        self.gold_mult = 0.0
        self.build_cost_mult = 0.0
        self.xp_need_mult = 0.0
        self.enemy_hp_mult = 0.0
        self.max_layers_bonus = 0

        self.unlocked_towers: set[str] = set()
        self.upgrade_stacks: dict[str, int] = {}

    def apply_effect(self, effect: dict) -> None:
        if "instant_gold" in effect:
            return
        if "unlock_tower" in effect:
            self.unlocked_towers.add(effect["unlock_tower"])
            return
        if "free_arrow_layer" in effect:
            return
        if effect.get("base_pulse"):
            self.base_pulse = True
        for key, val in effect.items():
            if key in ("instant_gold", "unlock_tower", "free_arrow_layer", "base_pulse"):
                continue
            if key == "type_damage":
                for t, v in val.items():
                    self.type_damage[t] = self.type_damage.get(t, 0) + v
            elif key == "max_layers":
                self.max_layers_bonus += int(val)
            elif hasattr(self, key):
                cur = getattr(self, key)
                if isinstance(cur, bool):
                    if val:
                        setattr(self, key, True)
                elif isinstance(cur, (int, float)) and isinstance(val, (int, float)):
                    setattr(self, key, cur + val)

    def tower_damage_factor(self, tower_type: str) -> float:
        return 1.0 + self.tower_damage_mult + self.type_damage.get(tower_type, 0)

    def build_cost_factor(self) -> float:
        return max(0.4, 1.0 + self.build_cost_mult)

    def xp_needed(self, level: int, base: float, growth: float) -> int:
        power = float(level - 1)
        soften_from = int(getattr(config, "EXP_LEVEL_SOFTEN_FROM", 8))
        if level > soften_from:
            extra = level - soften_from
            step = float(getattr(config, "EXP_LEVEL_SOFTEN_STEP", 0.92))
            power = (soften_from - 1) + sum(step**i for i in range(extra))
        need = base * (growth**power)
        return max(28, int(need * max(0.5, 1.0 + self.xp_need_mult)))
