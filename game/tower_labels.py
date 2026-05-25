"""防御塔类型 → 玩家可见中文名（与 data/towers.json 的 name 一致）。"""

from __future__ import annotations

# 内部 type_id 仅用于代码与存档，界面文案一律用下列中文名
TOWER_TYPE_LABELS: dict[str, str] = {
    "arrow": "箭塔",
    "slow": "寒塔",
    "cannon": "重炮",
    "laser": "激光塔",
    "wind": "风塔",
    "barracks": "兵营",
    "mint": "钱塔",
}


def tower_label(type_id: str, tower_defs: dict | None = None) -> str:
    if tower_defs and type_id in tower_defs:
        name = tower_defs[type_id].get("name")
        if name:
            return str(name)
    return TOWER_TYPE_LABELS.get(type_id, type_id)


def tower_damage_label(type_id: str, tower_defs: dict | None = None) -> str:
    return f"{tower_label(type_id, tower_defs)}伤害"
