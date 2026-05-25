"""基地强化：花金币在地基菜单购买，与升级三选一分离。"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

import config
from game.upgrades import apply_upgrade_card

if TYPE_CHECKING:
    from game.session import GameSession
    from game.stats import RunStats


class BaseUpgradeManager:
    def __init__(self, pool: list[dict]) -> None:
        self.pool = list(pool)
        self._by_id = {c["id"]: c for c in self.pool}

    def find(self, card_id: str) -> dict | None:
        card = self._by_id.get(card_id)
        return deepcopy(card) if card else None

    def stacks(self, stats: "RunStats", card_id: str) -> int:
        return int(stats.upgrade_stacks.get(card_id, 0))

    def max_stacks(self, card: dict) -> int:
        return int(card.get("max_stacks", 99))

    def is_maxed(self, stats: "RunStats", card: dict) -> bool:
        return self.stacks(stats, card["id"]) >= self.max_stacks(card)

    def purchase_cost(self, card: dict, stats: "RunStats") -> int:
        stacks = self.stacks(stats, card["id"])
        base = int(card.get("cost", config.BASE_UPGRADE_COST_DEFAULT))
        rarity = int(card.get("rarity", 1))
        mult = 0.9 + 0.12 * rarity
        return max(
            12,
            int(base * mult * (config.BASE_UPGRADE_COST_STACK_GROWTH**stacks)),
        )

    def can_purchase(self, game: "GameSession", card_id: str) -> tuple[bool, str]:
        card = self._by_id.get(card_id)
        if not card:
            return False, "无效强化"
        if self.is_maxed(game.stats, card):
            return False, "已满级"
        cost = self.purchase_cost(card, game.stats)
        if game.gold < cost:
            return False, f"还差 {cost - game.gold} 金"
        return True, ""

    def purchase(self, game: "GameSession", card_id: str) -> bool:
        card = self.find(card_id)
        if not card:
            return False
        ok, _ = self.can_purchase(game, card_id)
        if not ok:
            return False
        cost = self.purchase_cost(card, game.stats)
        game.gold -= cost
        apply_upgrade_card(card, game.stats, game)
        game.picked_upgrades.append(card["name"])
        game.on_sound("upgrade")
        return True


def base_upgrade_button_label(game: "GameSession", card: dict) -> str:
    stacks = game.base_upgrades.stacks(game.stats, card["id"])
    max_s = game.base_upgrades.max_stacks(card)
    if stacks >= max_s:
        return f"{card['name']} Lv{stacks}/{max_s} · 已满"
    cost = game.base_upgrades.purchase_cost(card, game.stats)
    nxt = stacks + 1
    if game.gold >= cost:
        return f"{card['name']} → Lv{nxt} ({cost}金)"
    return f"{card['name']} → Lv{nxt} 需{cost}金"
