"""生成像素风贴图（运行: python tools/gen_sprites.py）"""

import math
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    import subprocess
    import sys

    subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow", "-q"])
    from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "assets" / "sprites"
OUT.mkdir(parents=True, exist_ok=True)

FW, FH = 56, 40
TW, TH = 54, 38


def px(w: int, h: int) -> Image.Image:
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def save(name: str, img: Image.Image) -> None:
    print("wrote", OUT / name)
    img.save(OUT / name)


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _mix(c1: tuple, c2: tuple, t: float) -> tuple:
    return tuple(_lerp(c1[i], c2[i], t) for i in range(3))


def draw_iso_footprint(
    d: ImageDraw.Draw,
    cx: int,
    cy: int,
    rw: int,
    rh: int,
    top: tuple,
    side: tuple,
    edge: tuple,
    height: int = 6,
) -> None:
    top_pts = [(cx, cy - rh), (cx + rw, cy), (cx, cy + rh // 2), (cx - rw, cy)]
    d.polygon(top_pts, fill=top, outline=edge)
    side_pts = [
        (cx - rw, cy),
        (cx, cy + rh // 2),
        (cx, cy + rh // 2 + height),
        (cx - rw, cy + height),
    ]
    d.polygon(side_pts, fill=side)
    side2 = [
        (cx + rw, cy),
        (cx, cy + rh // 2),
        (cx, cy + rh // 2 + height),
        (cx + rw, cy + height),
    ]
    d.polygon(side2, fill=tuple(max(0, c - 22) for c in side[:3]) + (255,))


def _tower_block(colors: tuple, accent: tuple, deco_fn, *, side_dark: int = 35) -> Image.Image:
    im = px(TW, TH)
    d = ImageDraw.Draw(im)
    draw_iso_footprint(
        d,
        27,
        20,
        25,
        12,
        top=(*colors[:3], 255),
        side=tuple(max(0, c - side_dark) for c in colors[:3]) + (255,),
        edge=(30, 32, 42, 255),
    )
    deco_fn(d, accent)
    return im


# --- 背景：战场草地 + 通向中心的淡径 + 碎石 ---

def draw_bg() -> None:
    for variant, offset in [("bg_tile.png", 0), ("bg_tile_alt.png", 16)]:
        im = px(32, 32)
        p = im.load()
        for y in range(32):
            for x in range(32):
                # 棋盘微差 + 中心略亮（暗示基地方向）
                cx, cy = 15.5, 15.5
                dist = math.hypot(x - cx, y - cy) / 22
                base = _mix((22, 28, 36), (32, 42, 54), max(0, 1 - dist * 0.35))
                checker = 4 if (x // 4 + y // 4 + offset) % 2 else 0
                v = tuple(min(255, c + checker) for c in base)
                # 斜向草纹
                if (x + y * 2 + offset) % 7 == 0:
                    v = _mix(v, (48, 62, 48), 0.35)
                p[x, y] = (*v, 255)
        d = ImageDraw.Draw(im)
        # 淡路径（十字指向瓦片中心 = 叠层基地）
        path_c = (55, 68, 52, 70)
        d.line([(16, 0), (16, 32)], fill=path_c, width=1)
        d.line([(0, 16), (32, 16)], fill=path_c, width=1)
        # 碎石点
        for sx, sy in [(4, 6), (24, 9), (8, 22), (26, 24), (14, 12)]:
            d.rectangle([sx, sy, sx + 2, sy + 1], fill=(40, 48, 58, 200))
        save(variant, im)


# --- 地基：要塞指挥核心 ---

def draw_foundation_iso() -> None:
    im = px(FW, FH)
    d = ImageDraw.Draw(im)
    draw_iso_footprint(
        d,
        28,
        22,
        26,
        13,
        top=(118, 108, 88, 255),
        side=(82, 72, 58, 255),
        edge=(55, 48, 38, 255),
        height=8,
    )
    # 四角棱堡
    for bx, by in [(12, 14), (40, 14), (10, 20), (42, 20)]:
        d.rectangle([bx, by, bx + 4, by + 5], fill=(95, 85, 70, 255), outline=(60, 52, 42, 255))
    # 能量核心
    d.ellipse([22, 12, 34, 22], fill=(255, 210, 90, 255), outline=(200, 150, 60, 255))
    d.ellipse([25, 14, 31, 18], fill=(255, 245, 200, 255))
    # 天线
    d.rectangle([26, 6, 28, 12], fill=(70, 75, 90, 255))
    d.polygon([(27, 4), (29, 4), (28, 1)], fill=(180, 200, 255, 255))
    # 护城河纹
    d.arc([8, 8, 48, 28], 0, 180, fill=(60, 90, 110, 120), width=2)
    save("foundation.png", im)


# --- 塔：六种鲜明造型 ---

def draw_tower_arrow() -> None:
    def deco(d, acc):
        # 木质箭楼 + 金色箭垛
        d.rectangle([16, 8, 38, 18], fill=(95, 65, 40, 255), outline=(60, 40, 25, 255))
        d.polygon([(27, 3), (32, 9), (22, 9)], fill=(255, 220, 80, 255))
        d.rectangle([24, 10, 30, 14], fill=(60, 45, 30, 255))
        d.line([27, 9, 27, 14], fill=(255, 240, 150, 255), width=1)

    save("tower_arrow.png", _tower_block((62, 118, 185), (255, 230, 120), deco))


def draw_tower_slow() -> None:
    def deco(d, acc):
        # 冰晶尖塔
        d.polygon([(27, 2), (34, 12), (27, 18), (20, 12)], fill=(160, 220, 255, 255), outline=(220, 245, 255, 255))
        d.polygon([(27, 6), (30, 11), (27, 14), (24, 11)], fill=(230, 250, 255, 255))
        for i in range(3):
            d.line([22 + i * 5, 4, 20 + i * 5, 10], fill=(200, 240, 255, 180), width=1)

    save("tower_slow.png", _tower_block((70, 155, 210), (180, 240, 255), deco, side_dark=40))


def draw_tower_cannon() -> None:
    def deco(d, acc):
        # 青铜炮座 + 粗炮管
        d.rectangle([12, 10, 42, 18], fill=(75, 48, 32, 255))
        d.rectangle([14, 6, 40, 11], fill=(110, 70, 45, 255))
        d.rectangle([32, 7, 42, 10], fill=(*acc[:3], 255))
        d.ellipse([14, 12, 20, 16], fill=(50, 35, 25, 255))

    save("tower_cannon.png", _tower_block((175, 95, 55), (255, 175, 90), deco))


def draw_tower_laser() -> None:
    def deco(d, acc):
        # 紫晶聚焦器
        d.rectangle([18, 8, 36, 16], fill=(45, 25, 65, 255))
        d.ellipse([22, 4, 32, 12], fill=(*acc[:3], 255), outline=(255, 180, 255, 255))
        d.line([27, 1, 27, 4], fill=(255, 220, 255, 255), width=2)
        d.line([24, 6, 30, 6], fill=(200, 120, 255, 200), width=1)

    save("tower_laser.png", _tower_block((130, 65, 175), (240, 160, 255), deco))


def draw_tower_wind() -> None:
    def deco(d, acc):
        # 三叶风机
        d.ellipse([23, 9, 31, 13], fill=(50, 100, 85, 255))
        hub = (27, 11)
        for i in range(3):
            ang = -math.pi / 2 + i * (2 * math.pi / 3)
            x2 = hub[0] + int(math.cos(ang) * 14)
            y2 = hub[1] + int(math.sin(ang) * 6)
            d.line([*hub, x2, y2], fill=(*acc[:3], 230), width=3)
        d.ellipse([25, 9, 29, 13], fill=(200, 255, 230, 255))

    save("tower_wind.png", _tower_block((55, 145, 115), (170, 255, 210), deco))


def draw_tower_barracks() -> None:
    def deco(d, acc):
        # 营帐 + 旗
        d.polygon([(14, 12), (40, 12), (36, 20), (18, 20)], fill=(70, 95, 130, 255), outline=(45, 60, 85, 255))
        d.rectangle([20, 14, 34, 18], fill=(90, 110, 145, 255))
        d.polygon([(38, 6), (40, 14), (36, 14)], fill=(200, 60, 60, 255))
        d.rectangle([37, 4, 39, 8], fill=(*acc[:3], 255))

    save("tower_barracks.png", _tower_block((75, 105, 155), (190, 215, 255), deco))


# --- 护卫：盾形步兵（与敌人圆球区分） ---

def draw_guard_sprite() -> None:
    im = px(18, 20)
    d = ImageDraw.Draw(im)
    # 盾 + 头盔
    d.polygon([(9, 4), (14, 3), (14, 16), (9, 17), (4, 16), (4, 3)], fill=(60, 120, 190, 255), outline=(200, 230, 255, 255))
    d.rectangle([7, 6, 11, 10], fill=(90, 160, 220, 255))
    d.ellipse([7, 2, 11, 6], fill=(70, 130, 200, 255))
    d.rectangle([8, 14, 10, 18], fill=(50, 90, 140, 255))
    save("guard.png", im)


# --- 子弹 ---

def draw_bullet_arrow() -> None:
    im = px(16, 8)
    p = im.load()
    for x in range(10):
        p[x + 2, 3] = (255, 220, 90, 255)
        p[x + 2, 4] = (255, 220, 90, 255)
    for y in range(8):
        for x in range(16):
            if x >= 10 and abs(y - 3.5) <= max(0, 1.5 - (x - 10) * 0.15):
                p[x, y] = (255, 240, 180, 255)
    p[14, 3] = p[14, 4] = (255, 255, 255, 255)
    save("bullet_arrow.png", im)


def draw_bullet_snow() -> None:
    im = px(14, 14)
    p = im.load()
    cx, cy = 7, 7
    for i in range(6):
        ang = i * math.pi / 3
        for r in range(6):
            x = int(cx + math.cos(ang) * r)
            y = int(cy + math.sin(ang) * r * 0.55)
            if 0 <= x < 14 and 0 <= y < 14:
                p[x, y] = (200, 235, 255, 255)
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            if abs(dx) + abs(dy) <= 2:
                p[cx + dx, cy + dy] = (255, 255, 255, 255)
    save("bullet_slow.png", im)


def draw_bullet_cannon() -> None:
    im = px(12, 12)
    p = im.load()
    for y in range(12):
        for x in range(12):
            if (x - 6) ** 2 + (y - 6) ** 2 <= 20:
                p[x, y] = (255, 130, 50, 255)
    p[6, 6] = (255, 200, 100, 255)
    save("bullet_cannon.png", im)


# --- 敌人：按类型定制轮廓 ---

ENEMY_STYLES: dict[str, dict] = {
    "grunt": {"size": 18, "body": (195, 75, 75), "accent": (240, 120, 120), "shape": "grunt"},
    "runner": {"size": 16, "body": (255, 175, 45), "accent": (255, 220, 100), "shape": "runner"},
    "archer": {"size": 17, "body": (185, 140, 65), "accent": (220, 190, 100), "shape": "archer"},
    "tank": {"size": 22, "body": (130, 55, 150), "accent": (180, 100, 200), "shape": "tank"},
    "elite": {"size": 22, "body": (255, 55, 130), "accent": (255, 120, 180), "shape": "elite"},
    "boss": {"size": 32, "body": (210, 35, 35), "accent": (255, 80, 60), "shape": "boss"},
    "shielded": {"size": 22, "body": (115, 95, 200), "accent": (170, 150, 255), "shape": "shielded"},
    "juggernaut": {"size": 22, "body": (85, 70, 140), "accent": (130, 110, 180), "shape": "juggernaut"},
    "colossus": {"size": 36, "body": (165, 45, 195), "accent": (220, 100, 240), "shape": "colossus"},
    "brute": {"size": 20, "body": (160, 90, 70), "accent": (210, 140, 100), "shape": "tank"},
    "sapper": {"size": 15, "body": (255, 100, 90), "accent": (255, 180, 120), "shape": "runner"},
    "wraith": {"size": 18, "body": (90, 200, 220), "accent": (160, 240, 255), "shape": "archer"},
    "warlord": {"size": 33, "body": (200, 50, 50), "accent": (255, 90, 70), "shape": "boss"},
    "hive_matron": {"size": 32, "body": (120, 200, 80), "accent": (180, 255, 140), "shape": "elite"},
    "storm_herald": {"size": 30, "body": (80, 160, 255), "accent": (180, 220, 255), "shape": "archer"},
    "iron_titan": {"size": 34, "body": (90, 90, 120), "accent": (150, 150, 180), "shape": "juggernaut"},
}


def _draw_enemy_shape(d: ImageDraw.Draw, shape: str, cx: int, cy: int, r: int, body: tuple, accent: tuple) -> None:
    if shape == "grunt":
        d.ellipse([cx - r, cy - r + 2, cx + r, cy + r], fill=body, outline=accent)
        d.rectangle([cx - 3, cy - r - 2, cx + 3, cy - r + 2], fill=accent)
    elif shape == "runner":
        d.ellipse([cx - r + 2, cy - r + 3, cx + r, cy + r - 1], fill=body, outline=accent)
        for i in range(3):
            d.line([cx - r - 2 - i * 2, cy - 2 + i, cx - r + 2, cy + i], fill=accent, width=1)
    elif shape == "archer":
        d.ellipse([cx - r + 3, cy - r + 4, cx + r - 2, cy + r], fill=body, outline=accent)
        d.arc([cx - r, cy - r, cx + r, cy + r], 200, 340, fill=accent, width=2)
        d.line([cx + r - 2, cy, cx + r + 4, cy - 3], fill=accent, width=2)
    elif shape == "tank":
        d.rectangle([cx - r, cy - r + 4, cx + r, cy + r], fill=body, outline=accent)
        d.rectangle([cx - r + 2, cy - r, cx + r - 2, cy - r + 6], fill=accent)
    elif shape == "elite":
        d.polygon(
            [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)],
            fill=body,
            outline=accent,
        )
        d.polygon([(cx, cy - r - 2), (cx - 4, cy - r + 2), (cx + 4, cy - r + 2)], fill=accent)
    elif shape == "boss":
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=body, outline=accent)
        d.rectangle([cx - r // 2, cy - r - 4, cx + r // 2, cy - r + 2], fill=(80, 20, 20, 255))
        for ox in (-r // 2, r // 2):
            d.polygon([(cx + ox, cy - r - 2), (cx + ox + 4, cy - r + 4), (cx + ox - 4, cy - r + 4)], fill=accent)
    elif shape == "shielded":
        d.ellipse([cx - r + 2, cy - r + 3, cx + r - 2, cy + r], fill=body)
        d.polygon(
            [(cx, cy - r - 2), (cx + r, cy), (cx, cy + r + 2), (cx - r, cy)],
            fill=None,
            outline=accent,
            width=2,
        )
        d.line([cx, cy - r, cx, cy + r], fill=accent, width=1)
    elif shape == "juggernaut":
        d.rectangle([cx - r, cy - r + 2, cx + r, cy + r], fill=body, outline=accent)
        d.rectangle([cx - r + 3, cy - 2, cx + r - 3, cy + 2], fill=(50, 40, 70, 255))
    elif shape == "colossus":
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=body, outline=accent)
        d.ellipse([cx - r // 2, cy - r // 2, cx + r // 2, cy + r // 2], fill=(100, 30, 120, 180))
        d.rectangle([cx - 6, cy - r - 6, cx + 6, cy - r], fill=accent)
    else:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=body, outline=accent)


def draw_enemy_distinct(kind: str, fname: str, style: dict) -> None:
    size = style["size"]
    im = px(size, size)
    d = ImageDraw.Draw(im)
    cx, cy = size // 2, size // 2
    r = size // 2 - 2
    _draw_enemy_shape(d, style["shape"], cx, cy, r, style["body"], style["accent"])
    save(fname, im)


def main() -> None:
    draw_bg()
    draw_foundation_iso()
    draw_tower_arrow()
    draw_tower_slow()
    draw_tower_cannon()
    draw_tower_laser()
    draw_tower_wind()
    draw_tower_barracks()
    draw_guard_sprite()
    draw_bullet_arrow()
    draw_bullet_snow()
    draw_bullet_cannon()
    for kind, style in ENEMY_STYLES.items():
        draw_enemy_distinct(kind, f"enemy_{kind}.png", style)
    print("done.")


if __name__ == "__main__":
    main()
