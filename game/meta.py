from copy import deepcopy

import config
from game.storage import META_STORAGE_KEY, delete_stored, read_json, write_json

SAVE_PATH = config.ROOT / "save.json"

_META_FLAGS = (
    "unlock_cannon_start",
    "unlock_laser_start",
    "unlock_wind_start",
    "unlock_barracks_start",
    "unlock_mint_start",
)


class MetaProgress:
    def __init__(self, meta_data: dict) -> None:
        self.data = meta_data
        self.tokens = 0
        self.purchased: set[str] = set()
        self.total_wins = 0
        self.load()

    def load(self) -> None:
        d = read_json(SAVE_PATH, web_key=META_STORAGE_KEY)
        if not d:
            return
        self.tokens = d.get("tokens", 0)
        self.purchased = set(d.get("purchased", []))
        self.total_wins = d.get("total_wins", 0)

    def save(self) -> None:
        write_json(
            SAVE_PATH,
            {
                "tokens": self.tokens,
                "purchased": sorted(self.purchased),
                "total_wins": self.total_wins,
            },
            web_key=META_STORAGE_KEY,
        )

    def on_win(self, level: int) -> int:
        gain = self.data["win_tokens_base"] + level * self.data["win_tokens_per_level"]
        gain += self.aggregated_effects().get("win_tokens_bonus", 0)
        self.tokens += gain
        self.total_wins += 1
        self.save()
        return gain

    def can_buy(self, unlock: dict) -> bool:
        uid = unlock["id"]
        if uid in self.purchased:
            return False
        req = unlock.get("requires")
        if req and req not in self.purchased:
            return False
        return self.tokens >= unlock["cost"]

    def buy(self, unlock_id: str) -> bool:
        unlock = next((u for u in self.data["unlocks"] if u["id"] == unlock_id), None)
        if not unlock or not self.can_buy(unlock):
            return False
        self.tokens -= unlock["cost"]
        self.purchased.add(unlock_id)
        self.save()
        return True

    def aggregated_effects(self) -> dict:
        eff: dict = {
            "max_layers_bonus": 0,
            "start_gold_bonus": 0,
            "base_hp_mult": 0.0,
            "win_tokens_bonus": 0,
            "unlock_cannon_start": False,
            "unlock_laser_start": False,
            "unlock_wind_start": False,
            "unlock_barracks_start": False,
            "unlock_mint_start": False,
            "stat_effect": {},
        }
        stat: dict = eff["stat_effect"]
        for u in self.data["unlocks"]:
            if u["id"] not in self.purchased:
                continue
            for key, val in u.get("effect", {}).items():
                if key == "max_layers_bonus":
                    eff["max_layers_bonus"] += int(val)
                elif key == "start_gold_bonus":
                    eff["start_gold_bonus"] += int(val)
                elif key == "base_hp_mult":
                    eff["base_hp_mult"] += float(val)
                elif key == "win_tokens_bonus":
                    eff["win_tokens_bonus"] += int(val)
                elif key in _META_FLAGS:
                    if val:
                        eff[key] = True
                elif key == "type_damage" and isinstance(val, dict):
                    td = stat.setdefault("type_damage", {})
                    for tid, delta in val.items():
                        td[tid] = td.get(tid, 0.0) + float(delta)
                elif isinstance(val, bool):
                    if val:
                        stat[key] = True
                elif isinstance(val, (int, float)):
                    stat[key] = stat.get(key, 0) + val
        return eff

    def list_unlocks(self) -> list[dict]:
        out = []
        for u in self.data["unlocks"]:
            item = deepcopy(u)
            item["owned"] = u["id"] in self.purchased
            item["can_buy"] = self.can_buy(u)
            out.append(item)
        return out

