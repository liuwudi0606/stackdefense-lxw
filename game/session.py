import math
import random
from enum import Enum, auto

import config
from game.buff_fx import (
    on_enemy_killed_visual,
    on_tower_shot_visual,
    update_buff_fx,
)
from game.laser_fx import on_laser_tick_visual
from game.wind_combat import (
    apply_wind_knockback,
    enemies_in_fan,
    wind_aim_target,
    wind_fan_half_angle_rad,
    wind_fire_rate,
    wind_knockback,
    wind_range,
)
from game.wind_fx import on_wind_gust_visual
from game.mint_combat import apply_mint_tick, count_enemies_in_mint_range, mint_interval, mint_range
from game.mint_fx import on_mint_tick_visual
from game.effects import ExplosionFx
from game.barracks_combat import barracks_spawn_interval, spawn_guards_from_barracks
from game.camera import camera_apply, focus_on_stack, reset_view, view_zoom
from game.iso import iso_angle
from game.entities import Base, Bullet, Enemy, Guard, TowerFloor, dist, find_target
from game.unit_combat import prune_guards, update_enemy_combat, update_guard_combat
from game.laser_combat import (
    enemies_in_laser_range,
    find_laser_target,
    laser_damage_factor,
    laser_dps,
    laser_effective_mode,
    laser_range,
    laser_sweep_dps,
    target_in_laser_range,
)
from game.iso import (
    FOUNDATION_RH,
    FOUNDATION_RW,
    effective_layer_step,
    refresh_stack_layout,
    stack_scale,
    tower_screen_pos,
)
from game.stats import RunStats
from game.ui_scroll import ScrollDragState
from game.upgrades import UpgradeManager
from game.base_upgrades import BaseUpgradeManager
from game.waves import WaveController


class GameState(Enum):
    PLAYING = auto()
    UPGRADE_PICK = auto()
    TOWER_MENU = auto()
    TOWER_SWAP = auto()
    ENEMY_MENU = auto()
    BASE_MENU = auto()
    ENDLESS_OFFER = auto()
    WON = auto()
    LOST = auto()


def _built_tower_types(towers: list[TowerFloor]) -> set[str]:
    return {t.type_id for t in towers}


def _is_playable_tower(tower_defs: dict, type_id: str) -> bool:
    t = tower_defs.get(type_id, {})
    if t.get("is_foundation"):
        return False
    attack = t.get("attack")
    return attack in ("laser", "wind", "barracks", "mint") or "damage" in t


def _tower_is_laser(tower_defs: dict, type_id: str) -> bool:
    return tower_defs.get(type_id, {}).get("attack") == "laser"


def _tower_is_wind(tower_defs: dict, type_id: str) -> bool:
    return tower_defs.get(type_id, {}).get("attack") == "wind"


def _tower_is_barracks(tower_defs: dict, type_id: str) -> bool:
    return tower_defs.get(type_id, {}).get("attack") == "barracks"


def _tower_is_mint(tower_defs: dict, type_id: str) -> bool:
    return tower_defs.get(type_id, {}).get("attack") == "mint"


class GameSession:
    def __init__(
        self,
        tower_defs: dict,
        enemy_defs: dict,
        wave_data: dict,
        upgrade_pool: list,
        base_upgrade_pool: list | None = None,
        meta_effects: dict | None = None,
        on_sound=None,
    ) -> None:
        self.tower_defs = tower_defs
        self.enemy_defs = enemy_defs
        self.stats = RunStats()
        self.stats.unlocked_towers = set()
        self.endless_mode = config.ENDLESS_MODE
        self.waves = WaveController(
            wave_data, enemy_defs=enemy_defs, endless=self.endless_mode
        )
        run_pool = [c for c in upgrade_pool if c.get("tag") != "base"]
        self.upgrades = UpgradeManager(run_pool)
        self.base_upgrades = BaseUpgradeManager(
            base_upgrade_pool or []
        )
        self.on_sound = on_sound or (lambda _n: None)

        me = meta_effects or {}
        self.meta_hp_mult = me.get("base_hp_mult", 0.0)
        self.meta_start_gold = me.get("start_gold_bonus", 0)
        hp_mult = 1.0 + self.meta_hp_mult
        max_hp = config.BASE_HP_START * hp_mult
        self.state = GameState.PLAYING
        self.base = Base(hp=max_hp, max_hp=max_hp)
        self.towers: list[TowerFloor] = []
        self.enemies: list[Enemy] = []
        self.guards: list[Guard] = []
        self._guard_uid = 0
        self.base_alert_timer = 0.0
        self.loss_retry_wave_index = 0
        self.bullets: list[Bullet] = []
        self.explosions: list[ExplosionFx] = []
        self.gold = config.START_GOLD + me.get("start_gold_bonus", 0)
        self.exp = 0
        self.level = 1
        self.build_types = list(config.BUILD_TOWER_TYPES_DEFAULT)
        for tid, flag in (
            ("cannon", "unlock_cannon_start"),
            ("laser", "unlock_laser_start"),
            ("wind", "unlock_wind_start"),
            ("barracks", "unlock_barracks_start"),
            ("mint", "unlock_mint_start"),
        ):
            if me.get(flag) and tid not in self.build_types:
                self.build_types.append(tid)
        self.selected_build: str | None = self.build_types[0]
        self.upgrade_choices: list[dict] = []
        self.picked_upgrades: list[str] = []
        self.pending_level_ups = 0
        self.meta_buff_lines: list[str] = []
        self.buff_panel_open = False
        self.fx_phase = 0.0
        self.world_fx: list = []
        self._regen_fx_cd = 0.0
        reset_view()
        self._stack_focus_floors = -1

        self.max_tower_floors = config.MAX_TOWER_FLOORS_DEFAULT + me.get("max_layers_bonus", 0)
        stat_effect = me.get("stat_effect") or {}
        if stat_effect:
            self.stats.apply_effect(stat_effect)
            if self.stats.base_shield > 0:
                self.base.shield = self.stats.base_shield
        self.win_token_gain = 0
        self.clear_reward_applied = False
        self._shoot_sfx_cd = 0.0
        self._laser_sfx_cd = 0.0
        self._laser_hit_fx_cd = 0.0
        self.selected_tower_index: int | None = None
        self.selected_enemy_index: int | None = None
        self.swap_source_index: int | None = None
        self.debug_menu_open = False
        self.debug_god_mode = False
        self.debug_scroll = 0
        self.debug_buff_info: str | None = None
        self.build_info_tower: str | None = None
        self.base_upgrade_info: str | None = None
        self.build_drag: str | None = None
        self.ui_scroll_y = 0
        self.scroll_drag: ScrollDragState | None = None
        self.toast_message = ""
        self.toast_timer = 0.0

    def set_endless_mode(self, enabled: bool) -> None:
        self.endless_mode = enabled
        self.waves.set_endless_enabled(enabled)

    def accept_endless_continue(self) -> None:
        """普通模式通关后选择进入无尽续战。"""
        self.set_endless_mode(True)
        self.waves._endless_cd = config.ENDLESS_INITIAL_COOLDOWN
        self.state = GameState.PLAYING
        self.debug_menu_open = False
        self.buff_panel_open = False

    def finish_campaign_victory(self) -> None:
        """拒绝无尽，进入最终胜利结算。"""
        self.state = GameState.WON

    def _on_base_destroyed(self) -> None:
        self.loss_retry_wave_index = self.waves.retry_wave_index()
        self.state = GameState.LOST

    def restart_wave_after_loss(self) -> None:
        """地基被毁后重开本波：保留金币、等级、塔与 Buff，重刷当前波敌人。"""
        hp_mult = 1.0 + self.meta_hp_mult + self.stats.base_hp_mult
        self.base.max_hp = config.BASE_HP_START * hp_mult
        self.base.hp = self.base.max_hp
        if self.stats.base_shield > 0:
            self.base.shield = float(self.stats.base_shield)
        else:
            self.base.shield = 0.0
        self.base.pulse_flash = 0.0
        self.base_alert_timer = 0.0

        self.enemies.clear()
        self.guards.clear()
        self.bullets.clear()
        self.explosions.clear()
        self.world_fx.clear()

        for tower in self.towers:
            tower.cooldown = 0.0
            tower.laser_target = None
            tower.laser_charge = 0.0
            tower.laser_break_timer = 0.0
            tower.laser_sweeping = False

        if self.waves.endless and self.waves.all_scheduled_spawned:
            self.waves._endless_cd = max(self.waves._endless_cd, 2.5)
        else:
            self.waves.rewind_to_wave(self.loss_retry_wave_index)

        self.selected_tower_index = None
        self.selected_enemy_index = None
        self.swap_source_index = None
        self.build_drag = None
        self.debug_menu_open = False
        self.buff_panel_open = False
        self.state = GameState.PLAYING
        self.show_toast("本波重来 — 金币与进度已保留")

    def build_bar_types(self) -> list[str]:
        return [t for t in self.build_types if _is_playable_tower(self.tower_defs, t)]

    def tower_count(self) -> int:
        return len(self.towers)

    def max_tower_floors_limit(self) -> int:
        return self.max_tower_floors + self.stats.max_layers_bonus

    def xp_to_next(self) -> int:
        return self.stats.xp_needed(
            self.level, config.EXP_TO_LEVEL_BASE, config.EXP_LEVEL_GROWTH
        )

    def add_exp(self, amount: int) -> None:
        if self.state != GameState.PLAYING:
            return
        amt = int(amount * (1.0 + self.stats.exp_mult))
        self.exp += amt
        while self.exp >= self.xp_to_next():
            self.exp -= self.xp_to_next()
            self.level += 1
            self.pending_level_ups += 1
        self._try_open_upgrade_pick()

    def _try_open_upgrade_pick(self) -> None:
        if self.pending_level_ups <= 0 or self.state != GameState.PLAYING:
            return
        self.pending_level_ups -= 1
        self.upgrade_choices = self.upgrades.roll_four(
            self.stats, _built_tower_types(self.towers), self
        )
        self.state = GameState.UPGRADE_PICK
        self.on_sound("upgrade")

    def pick_upgrade(self, index: int) -> None:
        if index < 0 or index >= len(self.upgrade_choices):
            return
        card = self.upgrade_choices[index]
        old_hp_stat = self.stats.enemy_hp_mult
        self.upgrades.apply_choice(card, self.stats, self)
        if "enemy_hp_mult" in (card.get("effect") or {}):
            self.rescale_living_enemies_hp_buff(old_hp_stat)
        self.picked_upgrades.append(card["name"])
        if self.pending_level_ups > 0:
            self.upgrade_choices = self.upgrades.roll_four(
                self.stats, _built_tower_types(self.towers), self
            )
            self.state = GameState.UPGRADE_PICK
        else:
            self.upgrade_choices = []
            self.state = GameState.PLAYING

    def add_free_layer(self, tower_type: str) -> None:
        if self.tower_count() < self.max_tower_floors_limit():
            self._add_tower(tower_type)
            self._sync_build_selection()

    def build_cost(self, build_type: str) -> int:
        base = self.tower_defs[build_type]["cost"]
        floor_mult = 1.0 + config.BUILD_COST_PER_FLOOR * len(self.towers)
        return max(5, int(base * self.stats.build_cost_factor() * floor_mult))

    def tower_type_stack_mult(self, tower: TowerFloor) -> float:
        """同塔种叠层越多，单层有效输出递减，鼓励混搭。"""
        n = sum(1 for t in self.towers if t.type_id == tower.type_id)
        if n <= 1:
            return 1.0
        return 1.0 / (1.0 + config.TOWER_TYPE_STACK_PENALTY * (n - 1))

    @staticmethod
    def enemy_hp_buff_mult(stat_mult: float) -> float:
        """局内 enemy_hp_mult（虚弱/贪婪等），削弱下限 ENEMY_HP_DEBUFF_MIN_MULT。"""
        if stat_mult >= 0:
            return 1.0 + stat_mult
        floor = float(getattr(config, "ENEMY_HP_DEBUFF_MIN_MULT", 0.5))
        return max(floor, 1.0 + stat_mult)

    def enemy_hp_wave_scale(self) -> float:
        mult = 1.0
        mult *= 1.0 + config.WAVE_HP_TIME_SCALE * self.waves.elapsed
        mult *= 1.0 + config.WAVE_HP_PER_WAVE_SCALE * self.waves.waves_triggered
        if self.waves.surge_count > 0:
            mult *= 1.0 + config.WAVE_HP_PER_SURGE_SCALE * self.waves.surge_count
        if self.endless_mode and self.waves.all_scheduled_spawned:
            mult *= 1.0 + config.WAVE_HP_ENDLESS_PER_CYCLE * self.waves.endless_cycle
        return mult

    def enemy_hp_scale(self) -> float:
        return self.enemy_hp_buff_mult(self.stats.enemy_hp_mult) * self.enemy_hp_wave_scale()

    def rescale_living_enemies_hp_buff(self, old_stat_mult: float) -> None:
        """虚弱射线等变更后，按比例调整场上敌人生命（仅 Buff 部分，不含波次缩放）。"""
        old_b = self.enemy_hp_buff_mult(old_stat_mult)
        new_b = self.enemy_hp_buff_mult(self.stats.enemy_hp_mult)
        if abs(new_b - old_b) < 1e-6:
            return
        ratio = new_b / old_b
        for e in self.enemies:
            if not e.alive:
                continue
            e.hp = max(1.0, e.hp * ratio)
            e.max_hp = max(1.0, e.max_hp * ratio)

    def enemy_wave_stat_scale(self) -> tuple[float, float]:
        """随波次与时间提高伤害与移速，返回 (damage_mult, speed_mult)。"""
        wt = float(self.waves.waves_triggered)
        el = self.waves.elapsed
        dmg = 1.0 + config.WAVE_DAMAGE_PER_WAVE_SCALE * wt
        dmg += config.WAVE_DAMAGE_TIME_SCALE * el
        spd = 1.0 + config.WAVE_SPEED_PER_WAVE_SCALE * wt
        spd += config.WAVE_SPEED_TIME_SCALE * el
        spd = min(config.WAVE_SPEED_CAP_MULT, spd)
        return dmg, spd

    def can_build_stack(self, build_type: str) -> bool:
        if not _is_playable_tower(self.tower_defs, build_type):
            return False
        if build_type not in self.build_types:
            return False
        if self.gold < self.build_cost(build_type):
            return False
        if self.tower_count() >= self.max_tower_floors_limit():
            return False
        return True

    def build_hint(self, build_type: str) -> str:
        if not _is_playable_tower(self.tower_defs, build_type):
            return "选择塔种"
        if self.tower_count() >= self.max_tower_floors_limit():
            return "塔层已满，无法继续叠层"
        if self.gold < self.build_cost(build_type):
            return "金币不足"
        return f"叠第{self.tower_count() + 1}层·{self.tower_defs[build_type]['name']}"

    def show_toast(self, message: str, duration: float = 2.2) -> None:
        if message:
            self.toast_message = message
            self.toast_timer = max(self.toast_timer, duration)

    def notify_build_blocked(self, build_type: str | None = None) -> None:
        tid = build_type or self.build_drag or self.selected_build
        if tid:
            self.show_toast(self.build_hint(tid))
        else:
            self.show_toast("塔层已满，无法继续叠层")
        self.on_sound("click")

    def tick_toast(self, dt: float) -> None:
        if self.toast_timer > 0:
            self.toast_timer = max(0.0, self.toast_timer - dt)
            if self.toast_timer <= 0:
                self.toast_message = ""

    def _sync_stack_layout(self) -> None:
        n = len(self.towers)
        refresh_stack_layout(n, build_bar_h=config.BUILD_BAR_HEIGHT)
        if n != self._stack_focus_floors:
            self._stack_focus_floors = n
            focus_on_stack(n)

    def _tower_pick_metrics(self) -> tuple[float, float, float]:
        """返回 (view_zoom, stack_scale, layer_step_px)。"""
        z = view_zoom()
        sc = stack_scale()
        return z, sc, effective_layer_step() * z

    def tower_index_at(self, mx: int, my: int) -> int | None:
        """点击最近的一层塔（按精灵中心距离，避免误选上下层）。"""
        if not self.towers:
            return None
        self._sync_stack_layout()
        z, sc, step = self._tower_pick_metrics()
        hit_rx = max(16.0, config.TOWER_HIT_W * 0.42 * z * max(0.75, sc))
        hit_ry = max(12.0, step * 0.52)
        sprite_lift = max(6.0, 10.0 * z * sc)

        best_i: int | None = None
        best_score = 1e9
        for i, t in enumerate(self.towers):
            tx, ty = tower_screen_pos(t.floor)
            ax, ay = tx, ty - sprite_lift
            dx = (mx - ax) / hit_rx
            dy = (my - ay) / hit_ry
            ell = dx * dx + dy * dy
            if ell > 1.0:
                continue
            score = math.hypot(mx - ax, my - ay)
            # 距离接近时优先更高层，减少“想点上层却点到下层”
            if score < best_score - 1.5:
                best_score = score
                best_i = i
            elif abs(score - best_score) <= 1.5 and (
                best_i is None or t.floor > self.towers[best_i].floor
            ):
                best_score = score
                best_i = i
        return best_i

    def _point_on_foundation_ellipse(self, mx: int, my: int) -> bool:
        bx, by = camera_apply(config.BASE_X, config.BASE_Y)
        z = view_zoom()
        rx = max(20, int(FOUNDATION_RW * z * 0.92))
        ry = max(12, int(FOUNDATION_RH * z * 1.05))
        dx = (mx - bx) / rx
        dy = (my - by) / ry
        return dx * dx + dy * dy <= 1.0

    def click_on_foundation(self, mx: int, my: int) -> bool:
        """是否点在地基平台（未点到具体塔层）。"""
        if self.tower_index_at(mx, my) is not None:
            return False
        return self._point_on_foundation_ellipse(mx, my)

    def click_on_stack_build_area(self, mx: int, my: int) -> bool:
        """地基或塔堆任意层 — 用于叠层建造。"""
        if self.tower_index_at(mx, my) is not None:
            return True
        return self._point_on_foundation_ellipse(mx, my)

    def enemy_index_at(self, mx: int, my: int) -> int | None:
        hit = None
        best_d = 1e9
        for i, e in enumerate(self.enemies):
            if not e.alive:
                continue
            sx, sy = e.screen_pos()
            d = dist(mx, my, sx, sy)
            pad = (e.radius + 16) * view_zoom()
            if d <= pad and d < best_d:
                best_d = d
                hit = i
        return hit

    def buy_base_upgrade(self, card_id: str) -> bool:
        ok = self.base_upgrades.purchase(self, card_id)
        if not ok:
            _can, msg = self.base_upgrades.can_purchase(self, card_id)
            if msg:
                self.show_toast(msg)
                self.on_sound("click")
        return ok

    def open_base_menu(self) -> None:
        self.close_tower_ui()
        self.close_enemy_ui()
        self.base_upgrade_info = None
        self.ui_scroll_y = 0
        self.state = GameState.BASE_MENU

    def close_base_ui(self) -> None:
        self.base_upgrade_info = None
        if self.state == GameState.BASE_MENU:
            self.state = GameState.PLAYING

    def open_tower_menu(self, index: int) -> None:
        if 0 <= index < len(self.towers):
            self.close_enemy_ui()
            self.close_base_ui()
            self.selected_tower_index = index
            self.swap_source_index = None
            self.ui_scroll_y = 0
            self.state = GameState.TOWER_MENU

    def open_enemy_menu(self, index: int) -> None:
        if 0 <= index < len(self.enemies) and self.enemies[index].alive:
            self.close_tower_ui()
            self.close_base_ui()
            self.selected_enemy_index = index
            self.ui_scroll_y = 0
            self.state = GameState.ENEMY_MENU

    def close_enemy_ui(self) -> None:
        self.selected_enemy_index = None
        if self.state == GameState.ENEMY_MENU:
            self.state = GameState.PLAYING

    def close_tower_ui(self) -> None:
        self.selected_tower_index = None
        self.swap_source_index = None
        if self.state in (GameState.TOWER_MENU, GameState.TOWER_SWAP):
            self.state = GameState.PLAYING

    def close_unit_ui(self) -> None:
        self.close_tower_ui()
        self.close_enemy_ui()
        self.close_base_ui()

    def selected_tower(self) -> TowerFloor | None:
        if self.selected_tower_index is None:
            return None
        return self.towers[self.selected_tower_index]

    def _renumber_floors(self) -> None:
        for i, t in enumerate(self.towers):
            t.floor = i + 1

    def sell_tower(self, index: int) -> bool:
        if index < 0 or index >= len(self.towers):
            return False
        t = self.towers[index]
        base = self.build_cost(t.type_id)
        refund = int(base * config.TOWER_SELL_REFUND_RATIO * (1 + 0.1 * (t.level - 1)))
        self.gold += refund
        del self.towers[index]
        self._renumber_floors()
        self.close_tower_ui()
        self.on_sound("build")
        return True

    def upgrade_tower_cost(self, index: int) -> int:
        t = self.towers[index]
        return max(10, int(self.build_cost(t.type_id) * config.TOWER_UPGRADE_COST_MULT * t.level))

    def can_upgrade_tower(self, index: int) -> bool:
        if index < 0 or index >= len(self.towers):
            return False
        t = self.towers[index]
        return t.level < config.TOWER_LEVEL_MAX and self.gold >= self.upgrade_tower_cost(index)

    def upgrade_tower_label(self, index: int) -> str:
        """塔菜单「升级」按钮文案（含费用与还差金币）。"""
        if index < 0 or index >= len(self.towers):
            return "升级"
        t = self.towers[index]
        if t.level >= config.TOWER_LEVEL_MAX:
            return f"已满级 (Lv{config.TOWER_LEVEL_MAX})"
        cost = self.upgrade_tower_cost(index)
        if self.gold >= cost:
            return f"升级 ({cost}金)"
        short = cost - self.gold
        return f"升级 需{cost}金·还差{short}"

    def upgrade_tower(self, index: int) -> bool:
        if not self.can_upgrade_tower(index):
            return False
        self.gold -= self.upgrade_tower_cost(index)
        self.towers[index].level += 1
        self.on_sound("upgrade")
        return True

    def start_swap_tower(self, index: int) -> None:
        if index < 0 or index >= len(self.towers):
            return
        self.swap_source_index = index
        self.selected_tower_index = index
        self.state = GameState.TOWER_SWAP

    def swap_towers(self, index_a: int, index_b: int) -> bool:
        if index_a == index_b or not (0 <= index_a < len(self.towers) and 0 <= index_b < len(self.towers)):
            return False
        self.towers[index_a], self.towers[index_b] = self.towers[index_b], self.towers[index_a]
        self._renumber_floors()
        self.close_tower_ui()
        self.on_sound("click")
        return True

    def tower_damage_mult(self, tower: TowerFloor) -> float:
        return 1.0 + config.TOWER_LEVEL_DAMAGE_PER * (tower.level - 1)

    def tower_fire_rate_mult(self, tower: TowerFloor) -> float:
        return 1.0 + config.TOWER_LEVEL_RATE_PER * (tower.level - 1)

    def try_build_stack(self, build_type: str | None) -> bool:
        if not build_type:
            return False
        if not self.can_build_stack(build_type):
            if self.tower_count() >= self.max_tower_floors_limit():
                self.notify_build_blocked(build_type)
            elif self.gold < self.build_cost(build_type):
                self.show_toast(self.build_hint(build_type))
                self.on_sound("click")
            return False
        self.gold -= self.build_cost(build_type)
        self._add_tower(build_type)
        self.selected_build = None
        self.build_drag = None
        self.build_info_tower = None
        self.on_sound("build")
        return True

    def _add_tower(self, tower_type: str) -> None:
        floor = 1 + len(self.towers)
        self.towers.append(TowerFloor(type_id=tower_type, floor=floor))

    def _next_guard_id(self) -> int:
        self._guard_uid += 1
        return self._guard_uid

    def spawn_enemy(self, type_id: str, x: float, y: float) -> None:
        from game.enemy_skills import init_enemy_skills

        d = self.enemy_defs[type_id]
        hp_mult = self.enemy_hp_scale()
        dmg_mult, spd_mult = self.enemy_wave_stat_scale()
        atk = d.get("attack", "melee")
        enemy = Enemy(
                type_id=type_id,
                x=float(x),
                y=float(y),
                hp=d["hp"] * hp_mult,
                max_hp=d["hp"] * hp_mult,
                speed=d["speed"] * spd_mult,
                exp=d["exp"],
                gold=d["gold"],
                radius=d["radius"],
                color=tuple(d["color"]),
                weakened=self.stats.enemy_hp_mult < 0,
                buffed=self.stats.enemy_hp_mult > 0,
                laser_resist=float(d.get("laser_resist", 1.0)),
                laser_vuln=float(d.get("laser_vuln", 1.0)),
                wind_resist=float(d.get("wind_resist", 1.0)),
                attack_mode=atk,
                damage=float(d.get("damage", 6)) * dmg_mult,
                attack_range=float(
                    d.get("attack_range", 165 if atk == "ranged" else config.BASE_RADIUS + 8)
                ),
                attack_rate=float(d.get("attack_rate", 1.0)),
                attack_cd=0.0,
        )
        init_enemy_skills(enemy, d)
        self.enemies.append(enemy)

    def on_enemy_killed(self, enemy: Enemy) -> None:
        gold = int(enemy.gold * (1.0 + self.stats.gold_mult))
        self.gold += gold
        self.add_exp(enemy.exp)
        self.on_sound("kill")
        if self.stats.kill_heal > 0:
            self.base.hp = min(self.base.max_hp, self.base.hp + self.stats.kill_heal)
        on_enemy_killed_visual(self, enemy)

    def _sync_build_selection(self) -> None:
        if self.selected_build and self.selected_build not in self.build_types:
            self.selected_build = None
        if self.build_drag and self.build_drag not in self.build_types:
            self.build_drag = None

    def _tick_waves(self, dt: float, *, advance_time: bool = True) -> None:
        for sp in self.waves.update(dt, advance_time=advance_time):
            self.spawn_enemy(sp["type"], sp["x"], sp["y"])
        if msg := self.waves.consume_alert():
            self.show_toast(msg, config.WAVE_SURGE_TOAST_SEC)

    def update_playing(self, dt: float) -> None:
        self.tick_toast(dt)
        self._sync_stack_layout()
        self._sync_build_selection()
        self.fx_phase += dt
        update_buff_fx(self, dt)
        self._tick_waves(dt)
        if self.base_alert_timer > 0:
            self.base_alert_timer = max(0.0, self.base_alert_timer - dt)

        self.base.update(dt, self)

        for g in self.guards:
            if g.alive:
                update_guard_combat(self, g, dt)
        prune_guards(self)

        for e in self.enemies[:]:
            if not e.alive:
                continue
            if update_enemy_combat(self, e, dt):
                self._on_base_destroyed()
                break

        dead = [e for e in self.enemies if not e.alive]
        for e in dead:
            if e.hp <= 0:
                self.on_enemy_killed(e)
        self.enemies = [e for e in self.enemies if e.alive]

        self._update_towers(dt)
        self._update_bullets(dt)

        if (
            not self.endless_mode
            and self.waves.all_scheduled_spawned
            and not self.enemies
            and self.state == GameState.PLAYING
        ):
            self.state = GameState.ENDLESS_OFFER

    def _arrow_shot_count(self, tower_type: str) -> int:
        """箭塔双重装填：概率可叠加，100% 时稳定双发。"""
        if tower_type != "arrow":
            return 1
        chance = min(1.0, self.stats.double_shot_chance)
        if chance <= 0:
            return 1
        return 1 + (1 if random.random() < chance else 0)

    def _release_laser_lock(self, tower: TowerFloor, charge_keep: float = 0.0) -> None:
        tower.laser_target = None
        tower.laser_sweeping = False
        tower.laser_charge *= max(0.0, min(1.0, charge_keep))
        tower.laser_break_timer = 0.0

    def toggle_laser_auto(self, index: int) -> None:
        if index < 0 or index >= len(self.towers):
            return
        tower = self.towers[index]
        if tower.type_id != "laser" or not self.stats.laser_sweep_unlock:
            return
        tower.laser_auto = not tower.laser_auto
        self.on_sound("click")

    def cycle_laser_mode(self, index: int) -> None:
        if index < 0 or index >= len(self.towers):
            return
        tower = self.towers[index]
        if tower.type_id != "laser" or not self.stats.laser_sweep_unlock:
            return
        tower.laser_mode = "sweep" if tower.laser_mode == "single" else "single"
        if not tower.laser_auto:
            self._release_laser_lock(tower, 0.0)
        self.on_sound("click")

    def _update_laser_single(self, tower: TowerFloor, dt: float, tdef: dict, rng: float) -> None:
        tower.laser_sweeping = False
        cur = tower.laser_target
        if cur is not None and not cur.alive:
            self._release_laser_lock(tower, config.LASER_CHARGE_KEEP_ON_KILL)
            cur = None

        if cur is None:
            cur = find_laser_target(config.BASE_X, config.BASE_Y, self.enemies, rng)
            if cur is None:
                return
            tower.laser_target = cur
            tower.laser_break_timer = 0.0

        if not target_in_laser_range(cur, rng):
            grace = float(tdef.get("lock_break_grace", 0.2))
            tower.laser_break_timer += dt
            if tower.laser_break_timer >= grace:
                self._release_laser_lock(tower, config.LASER_CHARGE_KEEP_ON_BREAK)
            return

        tower.laser_break_timer = 0.0
        tower.laser_charge += dt
        stack = self.tower_type_stack_mult(tower)
        from game.tower_range_bands import band_damage_mult

        band = band_damage_mult(config.BASE_X, config.BASE_Y, cur, rng)
        dps = laser_dps(self, tower, tdef) * laser_damage_factor(cur) * stack * band
        if dps > 0:
            cur.take_damage(dps * dt)
            self._laser_hit_fx_cd = max(0.0, self._laser_hit_fx_cd - dt)
            nominal = laser_dps(self, tower, tdef)
            if nominal >= 25 and self._laser_hit_fx_cd <= 0:
                self._laser_hit_fx_cd = 0.07
                on_laser_tick_visual(self, tower, cur, nominal)

        self._laser_sfx_cd = max(0.0, self._laser_sfx_cd - dt)
        if self._laser_sfx_cd <= 0 and dps > 0:
            self.on_sound("shoot")
            self._laser_sfx_cd = 0.12

    def _update_laser_sweep(self, tower: TowerFloor, dt: float, tdef: dict, rng: float) -> None:
        in_range = enemies_in_laser_range(self.enemies, rng)
        if not in_range:
            self._release_laser_lock(tower, 0.0)
            return

        tower.laser_sweeping = True
        tower.laser_target = in_range[0]
        tower.laser_break_timer = 0.0
        tower.laser_charge = 0.0

        stack = self.tower_type_stack_mult(tower)
        base_dps = laser_sweep_dps(self, tower, tdef) * stack
        hit_any = False
        from game.tower_range_bands import band_damage_mult

        for e in in_range:
            band = band_damage_mult(config.BASE_X, config.BASE_Y, e, rng)
            dps = base_dps * laser_damage_factor(e) * band
            if dps <= 0:
                continue
            e.take_damage(dps * dt)
            hit_any = True

        if hit_any:
            self._laser_hit_fx_cd = max(0.0, self._laser_hit_fx_cd - dt)
            if base_dps >= 18 and self._laser_hit_fx_cd <= 0:
                self._laser_hit_fx_cd = 0.09
                on_laser_tick_visual(self, tower, in_range[0], base_dps)
            self._laser_sfx_cd = max(0.0, self._laser_sfx_cd - dt)
            if self._laser_sfx_cd <= 0:
                self.on_sound("shoot")
                self._laser_sfx_cd = 0.14

    def _update_laser_tower(self, tower: TowerFloor, dt: float) -> None:
        tdef = self.tower_defs[tower.type_id]
        rng = laser_range(tdef, self.stats)
        mode = laser_effective_mode(self, tower, tdef)
        if mode == "sweep":
            self._update_laser_sweep(tower, dt, tdef, rng)
        else:
            self._update_laser_single(tower, dt, tdef, rng)

    def _update_wind_tower(self, tower: TowerFloor, dt: float) -> None:
        tdef = self.tower_defs[tower.type_id]
        rng = wind_range(tdef, self.stats, tower)
        target = wind_aim_target(self, rng)
        if not target:
            return
        half = wind_fan_half_angle_rad(tdef, tower, self.stats.wind_fan_mult)
        aim = iso_angle(config.BASE_X, config.BASE_Y, target.x, target.y)
        hits = enemies_in_fan(
            config.BASE_X, config.BASE_Y, aim, rng, half, self.enemies
        )
        if not hits:
            return
        tower.cooldown = 1.0 / wind_fire_rate(tdef, tower, self.stats)
        force = wind_knockback(tdef, tower, self.stats.wind_knockback_mult)
        apply_wind_knockback(
            hits, config.BASE_X, config.BASE_Y, force, inner_rng=rng
        )
        wx, wy = tower.world_pos()
        on_wind_gust_visual(self, wx, wy, aim, rng, half, len(hits))
        if self._shoot_sfx_cd <= 0:
            self.on_sound("shoot")
            self._shoot_sfx_cd = 0.08

    def _update_mint_tower(self, tower: TowerFloor, dt: float) -> None:
        tdef = self.tower_defs[tower.type_id]
        rng = mint_range(tdef, self.stats)
        count = count_enemies_in_mint_range(self, rng)
        gold = apply_mint_tick(self, tower, tdef, count)
        tower.cooldown = mint_interval(tdef, tower, self.stats)
        wx, wy = tower.world_pos()
        on_mint_tick_visual(self, wx, wy, rng, count, gold)
        if gold > 0 and self._shoot_sfx_cd <= 0:
            self.on_sound("coin")
            self._shoot_sfx_cd = 0.12

    def _update_towers(self, dt: float) -> None:
        """仅塔层射击；中心地基不发射子弹。"""
        self._shoot_sfx_cd = max(0.0, self._shoot_sfx_cd - dt)
        for tower in self.towers:
            if _tower_is_laser(self.tower_defs, tower.type_id):
                self._update_laser_tower(tower, dt)
                continue
            if _tower_is_wind(self.tower_defs, tower.type_id):
                tower.cooldown -= dt
                if tower.cooldown > 0:
                    continue
                self._update_wind_tower(tower, dt)
                continue
            if _tower_is_barracks(self.tower_defs, tower.type_id):
                tower.cooldown -= dt
                if tower.cooldown > 0:
                    continue
                tdef = self.tower_defs[tower.type_id]
                tower.cooldown = barracks_spawn_interval(tdef, tower, self.stats)
                n = spawn_guards_from_barracks(self, tower, tdef)
                if n > 0 and self._shoot_sfx_cd <= 0:
                    self.on_sound("build")
                    self._shoot_sfx_cd = 0.15
                continue
            if _tower_is_mint(self.tower_defs, tower.type_id):
                tower.cooldown -= dt
                if tower.cooldown > 0:
                    continue
                self._update_mint_tower(tower, dt)
                continue
            tower.cooldown -= dt
            if tower.cooldown > 0:
                continue
            tdef = self.tower_defs[tower.type_id]
            wx, wy = tower.world_pos()
            rng = tdef["range"] * (1.0 + self.stats.tower_range_mult)
            from game.tower_range_bands import find_target_with_far

            # 射程以地基为中心；外圈敌人按 50% 伤害
            if tower.type_id == "slow":
                target, far_mult = find_target_with_far(
                    config.BASE_X,
                    config.BASE_Y,
                    self.enemies,
                    rng,
                    eligible=lambda e: not e.is_slowed(),
                )
                if target is None:
                    target, far_mult = find_target_with_far(
                        config.BASE_X, config.BASE_Y, self.enemies, rng
                    )
            else:
                target, far_mult = find_target_with_far(
                    config.BASE_X, config.BASE_Y, self.enemies, rng
                )
            if not target:
                continue
            rate = (
                tdef["fire_rate"]
                * (1.0 + self.stats.tower_fire_rate_mult)
                * self.tower_fire_rate_mult(tower)
            )
            tower.cooldown = 1.0 / max(0.1, rate)
            dmg = (
                tdef["damage"]
                * self.stats.tower_damage_factor(tower.type_id)
                * self.tower_damage_mult(tower)
                * self.tower_type_stack_mult(tower)
                * far_mult
            )
            bullet_color = tuple(tdef.get("bullet_color", tdef["color"]))
            slow_f = 0
            slow_d = 0
            splash = 0
            if tower.type_id == "slow":
                slow_base = tdef.get("slow_factor", 0.5)
                # slow_mult 叠加：每 +0.2 约让敌人移速再×0.8（更强减速）
                slow_f = slow_base * max(0.2, 1.0 - self.stats.slow_mult)
                slow_d = tdef.get("slow_duration", 1.5)
            if tower.type_id == "cannon":
                splash = tdef.get("splash_radius", 40) * (1.0 + self.stats.splash_mult)
            shots = self._arrow_shot_count(tower.type_id)
            base_ang = math.atan2(target.y - wy, target.x - wx)
            for i in range(shots):
                spread = 0.0
                delay = 0.0
                if shots > 1:
                    spread = (i - (shots - 1) / 2) * 0.14
                    delay = i * 0.07
                ang = base_ang + spread
                ox = wx + math.cos(ang) * 5
                oy = wy + math.sin(ang) * 5
                self.bullets.append(
                    Bullet(
                        x=ox,
                        y=oy,
                        tx=target.x,
                        ty=target.y,
                        speed=420,
                        damage=dmg,
                        color=bullet_color,
                        tower_type=tower.type_id,
                        splash=splash,
                        slow_factor=slow_f,
                        slow_duration=slow_d,
                        target=target,
                        max_range=rng,
                        spawn_delay=delay,
                    )
                )
            on_tower_shot_visual(self, wx, wy, tower.type_id, shots, bullet_color)
            if self._shoot_sfx_cd <= 0:
                self.on_sound("shoot")
                self._shoot_sfx_cd = 0.06

    def _spawn_explosion(self, wx: float, wy: float, radius: float) -> None:
        dur = 0.4
        if self.stats.splash_mult > 0:
            dur = 0.52
        self.explosions.append(ExplosionFx(wx=wx, wy=wy, radius=radius, duration=dur))

    def _update_bullets(self, dt: float) -> None:
        for b in self.bullets:
            if not b.alive:
                continue
            splash_r = b.splash
            b.update(dt, self.enemies)
            if not b.alive and splash_r > 0:
                hx, hy = b.x, b.y
                if b.target and b.target.alive:
                    hx, hy = b.target.x, b.target.y
                self._spawn_explosion(hx, hy, splash_r)
        self.bullets = [b for b in self.bullets if b.alive]
        self.explosions = [e for e in self.explosions if e.update(dt)]

    def run_debug_action(self, action: str, extra: str = "") -> str | None:
        from game.debug import (
            debug_add_exp,
            debug_add_gold,
            debug_add_level,
            debug_clear_enemies,
            debug_grant_upgrade,
            debug_heal_base,
            debug_spawn_pack,
            debug_toggle_god,
            debug_toggle_endless,
        )

        if action == "gold500":
            debug_add_gold(self, 500)
        elif action == "gold2000":
            debug_add_gold(self, 2000)
        elif action == "clear":
            debug_clear_enemies(self)
        elif action == "heal":
            debug_heal_base(self)
        elif action == "level":
            debug_add_level(self)
        elif action == "exp":
            debug_add_exp(self)
        elif action == "spawn":
            debug_spawn_pack(self, 10)
        elif action == "god":
            on = debug_toggle_god(self)
            return "god_on" if on else "god_off"
        elif action == "endless":
            on = debug_toggle_endless(self)
            return "endless_on" if on else "endless_off"
        elif action == "buff" and extra:
            if debug_grant_upgrade(self, extra):
                return "buff_ok"
            return "buff_fail"
        elif action == "buff_info" and extra:
            if self.debug_buff_info == extra:
                self.debug_buff_info = None
            else:
                self.debug_buff_info = extra
                self.ui_scroll_y = 0
        elif action == "close_buff_info":
            self.debug_buff_info = None
        elif action == "close":
            self.debug_menu_open = False
            self.debug_buff_info = None
        return None

    def update(self, dt: float) -> None:
        if self.state == GameState.TOWER_MENU:
            idx = self.selected_tower_index
            if idx is None or idx < 0 or idx >= len(self.towers):
                self.close_tower_ui()
        elif self.state == GameState.TOWER_SWAP:
            idx = self.selected_tower_index
            if idx is None or idx < 0 or idx >= len(self.towers):
                self.close_tower_ui()
        if self.state == GameState.ENEMY_MENU:
            idx = self.selected_enemy_index
            if (
                idx is None
                or idx >= len(self.enemies)
                or not self.enemies[idx].alive
            ):
                self.close_enemy_ui()
                return
        if self.debug_menu_open:
            # 调试菜单暂停战斗，但无尽/预定波次计时仍推进，避免 F1 清空后一直等不到下一轮
            if self.state == GameState.PLAYING:
                self._tick_waves(dt)
            return
        if self.state == GameState.PLAYING:
            self.update_playing(dt)
        # TOWER_MENU / TOWER_SWAP / UPGRADE_PICK / ENEMY_MENU / BASE_MENU 时暂停战斗
