from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pygame

ROOT = Path(__file__).resolve().parent.parent
SPRITES = ROOT / "assets" / "sprites"


class SpriteBank:
    def __init__(self) -> None:
        self.images: dict[str, object] = {}
        self.missing = False

    def load_all(self) -> None:
        import pygame

        if not SPRITES.is_dir():
            self.missing = True
            return
        for path in SPRITES.glob("*.png"):
            surf = pygame.image.load(str(path)).convert_alpha()
            self.images[path.stem] = surf
        self.missing = len(self.images) == 0

    def get(self, key: str):
        return self.images.get(key)

    def tower(self, type_id: str):
        return self.get(f"tower_{type_id}")

    def bullet(self, type_id: str):
        return self.get(f"bullet_{type_id}")

    def enemy(self, type_id: str):
        return self.get(f"enemy_{type_id}")
