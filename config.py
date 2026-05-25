import json
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
ASSETS = ROOT / "assets"

# 逻辑分辨率（玩法与 UI 布局）；实际窗口可缩放/全屏
PORTRAIT = False
WIDTH = 960
HEIGHT = 640
FPS = 60
WINDOW_MIN_W = 640
WINDOW_MIN_H = 480

# 游戏区域内滚轮视角缩放（相对默认 1.0）
VIEW_ZOOM_DEFAULT = 1.0
VIEW_ZOOM_MIN = 0.72
VIEW_ZOOM_MAX = 1.48
VIEW_ZOOM_STEP = 1.08

BASE_X = WIDTH // 2
BASE_Y = HEIGHT // 2 + 20
BASE_RADIUS = 42
BUILD_CLICK_RADIUS = 90

# 敌人生成：绕中心一圈（四面八方）
SPAWN_RADIUS = 400
# 成团刷怪：同批敌人入口角相同，位置在 spread 内随机散布（便于范围炮命中）
CLUSTER_SPAWN_SPREAD = 38


def _recompute_layout_constants() -> None:
    global BASE_X, BASE_Y, BASE_RADIUS, BUILD_CLICK_RADIUS, SPAWN_RADIUS, CLUSTER_SPAWN_SPREAD
    BASE_X = WIDTH // 2
    BASE_Y = HEIGHT // 2 + (24 if PORTRAIT else 20)
    BASE_RADIUS = 40 if PORTRAIT else 42
    BUILD_CLICK_RADIUS = 82 if PORTRAIT else 90
    SPAWN_RADIUS = min(340, int(min(WIDTH, HEIGHT) * 0.42))
    CLUSTER_SPAWN_SPREAD = max(28, int(SPAWN_RADIUS * 0.095))


def apply_layout(portrait: bool) -> None:
    """切换横屏 960×640 / 竖屏 540×960（手机）。"""
    global PORTRAIT, WIDTH, HEIGHT, BUILD_BAR_HEIGHT, WINDOW_MIN_W, WINDOW_MIN_H
    global VIEW_ZOOM_MIN, VIEW_ZOOM_MAX

    if portrait == PORTRAIT and (
        (portrait and WIDTH == 540) or (not portrait and WIDTH == 960)
    ):
        _recompute_layout_constants()
        return

    PORTRAIT = portrait
    if portrait:
        WIDTH, HEIGHT = 540, 960
        BUILD_BAR_HEIGHT = 76
        WINDOW_MIN_W, WINDOW_MIN_H = 360, 640
        VIEW_ZOOM_MIN = 0.68
        VIEW_ZOOM_MAX = 1.38
    else:
        WIDTH, HEIGHT = 960, 640
        BUILD_BAR_HEIGHT = 62
        WINDOW_MIN_W, WINDOW_MIN_H = 640, 480
        VIEW_ZOOM_MIN = 0.72
        VIEW_ZOOM_MAX = 1.48
    _recompute_layout_constants()


_recompute_layout_constants()

MAX_TOWER_FLOORS_DEFAULT = 10
# 与 game/iso.py 中 TOWER_LAYER_STEP 一致
TOWER_LAYER_STEP = 30

BASE_HP_START = 500
BASE_DAMAGE_ON_HIT = 12
ENEMY_MELEE_PADDING = 6
# 护卫反击仇恨：护卫造成伤害后敌人追打该护卫的最远距离
ENEMY_AGGRO_DROP_RANGE = 280
GUARD_DEFAULT_RADIUS = 11
GUARD_SEEK_RANGE_DEFAULT = 320
GUARD_MOVE_SPEED_DEFAULT = 50
# 护卫在基地外围的出生环半径（世界坐标）
GUARD_SPAWN_RING_RADIUS = 78
GUARD_SPAWN_ANGLE_SPREAD = 0.35
# 风塔击退位移持续时间（秒），与 knockback 距离配合决定滑动速度
WIND_KNOCKBACK_DURATION = 0.22
BASE_AURA_RADIUS = 120
BASE_PULSE_RADIUS = 100
BASE_PULSE_DAMAGE = 15
BASE_PULSE_COOLDOWN = 5.0
BASE_PULSE_DAMAGE_PER_STACK = 5
BASE_PULSE_RADIUS_PER_STACK = 12
BASE_PULSE_COOLDOWN_PER_STACK = 0.4
BASE_PULSE_COOLDOWN_MIN = 2.5
EXP_TO_LEVEL_BASE = 100
EXP_LEVEL_GROWTH = 1.25

START_GOLD = 500
BUILD_TOWER_TYPES_DEFAULT = ["arrow", "slow"]

TOWER_LEVEL_MAX = 20
TOWER_UPGRADE_COST_MULT = 0.55
TOWER_SELL_REFUND_RATIO = 0.6
TOWER_HIT_W = 52
TOWER_HIT_H = 36
BUILD_BAR_HEIGHT = 62

# 通关模式：清完预定波次且场上无敌人即胜利；改 True 则进入无尽续战
ENDLESS_MODE = False
AUTO_SAVE_INTERVAL = 4.0

# 平衡：叠层造价递增、同塔递减、溅射次级伤害比例
BUILD_COST_PER_FLOOR = 0.07
TOWER_TYPE_STACK_PENALTY = 0.12
CANNON_SPLASH_SECONDARY_MULT = 0.65
LASER_CHARGE_KEEP_ON_BREAK = 0.4
LASER_CHARGE_KEEP_ON_KILL = 0.2
# 普通模式（预定波次）每组出怪数量倍率；Boss/单次精英（count≤1）不放大
NORMAL_WAVE_COUNT_MULT = 3.0
# 随对战时间略微抬高敌人生命（无尽轮次额外叠加在 spawn_enemy）
# 普通模式约 30 分钟；随时间抬高敌人生命（1800s 时约 +105%）
WAVE_HP_TIME_SCALE = 0.00058
WAVE_HP_ENDLESS_PER_CYCLE = 0.045

# 无尽模式刷怪节奏（预定波次打完后的续战）
ENDLESS_INITIAL_COOLDOWN = 5.0
ENDLESS_INTERVAL_BASE = 3.5
ENDLESS_INTERVAL_MIN = 1.4
ENDLESS_INTERVAL_CYCLE_STEP = 0.015
ENDLESS_INTERVAL_TIME_SCALE = 0.00012
ENDLESS_INTERVAL_TIME_CAP = 0.35
ENDLESS_BATCH_BASE = 1
ENDLESS_BATCH_EVERY_CYCLES = 10
ENDLESS_BATCH_MAX = 2


def load_json(name: str) -> dict | list:
    with open(DATA / name, encoding="utf-8") as f:
        return json.load(f)
