"""战斗特效（爆炸等）。"""

from dataclasses import dataclass

import config
from game.iso import world_to_screen


@dataclass
class ExplosionFx:
    wx: float
    wy: float
    radius: float
    t: float = 0.0
    duration: float = 0.4

    def update(self, dt: float) -> bool:
        self.t += dt
        return self.t < self.duration

    def progress(self) -> float:
        return min(1.0, self.t / max(0.01, self.duration))

    def screen_center(self) -> tuple[float, float]:
        return world_to_screen(self.wx, self.wy)

    def screen_radius(self) -> float:
        sx, _ = world_to_screen(self.wx + self.radius, self.wy)
        cx, _ = world_to_screen(self.wx, self.wy)
        return abs(sx - cx)
