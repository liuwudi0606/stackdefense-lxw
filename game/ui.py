from __future__ import annotations

import math

import pygame

import config
from game.assets import SpriteBank
from game.entities import dist
from game.fonts import get_font
from game.buff_fx import (
    draw_base_buff_auras,
    draw_base_pulse_burst,
    draw_enemy_buff_marks,
    draw_range_ring,
    draw_tower_buff_glows,
    draw_world_fx,
)
from game.laser_fx import draw_laser_beams
from game.buffs import build_buff_lines
from game.base_info import base_detail_lines
from game.enemy_info import (
    enemy_detail_lines,
    enemy_shows_world_hud,
    enemy_tier,
    enemy_world_tag,
)
from game.tower_info import tower_preview_lines, tower_stat_lines
from game.upgrades import upgrade_pick_rows, upgrade_pick_title
from game.visual_style import ENEMY_TIER_RING, TOWER_PLATFORM_TINT
from game.iso import (
    FOUNDATION_RW,
    FOUNDATION_RH,
    draw_iso_platform,
    draw_stack_edges,
    draw_tower_layer_base,
    refresh_stack_layout,
    scaled_size,
    stack_scale,
    tower_screen_pos,
    world_to_screen,
)
from game.meta import MetaProgress
from game.session import GameSession, GameState
from game.ui_scroll import (
    clamp_scroll,
    drag_content_scroll_y,
    draw_scrollbar,
    drag_scroll_y,
    hit_scrollbar,
    scroll_y_from_thumb_top,
    scroll_thumb_rect,
    start_content_scroll_drag,
    start_scroll_drag,
)
from game.ui_text import (
    blit_in_rect,
    blit_scroll_text,
    blit_topleft,
    blit_wrapped,
    blit_wrapped_lines,
    draw_info_icon,
    fit_render,
    scroll_content_height,
)


class UI:
    def __init__(self, sprites: SpriteBank) -> None:
        self.sprites = sprites
        self.f_xs = get_font(15)
        self.f_sm = get_font(18 if not config.PORTRAIT else 17)
        self.f_md = get_font(22 if not config.PORTRAIT else 20)
        self.f_lg = get_font(28 if not config.PORTRAIT else 24)
        self.f_title = get_font(36 if not config.PORTRAIT else 30)
        self._build_bar_h = config.BUILD_BAR_HEIGHT
        self.build_bar_scroll_x = 0
        self._build_bar_h_drag: tuple[int, int] | None = None
        self._bg_tile = sprites.get("bg_tile")
        self._bg_tile_alt = sprites.get("bg_tile_alt") or self._bg_tile

    def _blit_center(self, surf, image: pygame.Surface, cx: int, cy: int) -> None:
        surf.blit(image, image.get_rect(center=(cx, cy)))

    def _blit_center_scaled(
        self, surf: pygame.Surface, image: pygame.Surface, cx: int, cy: int, scale: float
    ) -> None:
        if scale >= 0.999:
            self._blit_center(surf, image, cx, cy)
            return
        w = max(1, int(image.get_width() * scale))
        h = max(1, int(image.get_height() * scale))
        img = pygame.transform.smoothscale(image, (w, h))
        self._blit_center(surf, img, cx, cy)

    def _blit_entity_sprite(
        self,
        surf: pygame.Surface,
        image: pygame.Surface,
        cx: int,
        cy: int,
        world_radius: float,
        view_zoom: float,
    ) -> None:
        """按实体半径与视角缩放贴图，大怪/护卫更易辨认。"""
        base = max(image.get_width(), image.get_height())
        target = max(12, int(world_radius * 2.4 * view_zoom))
        self._blit_center_scaled(surf, image, cx, cy, target / base)

    def _btn(self, surf, rect: pygame.Rect, text: str, font=None, color=(240, 240, 250)) -> None:
        blit_in_rect(surf, font or self.f_md, text, rect, color, align="center", pad=8)

    def _detail_content_rect(self, panel: pygame.Rect, footer_h: int = 0) -> pygame.Rect:
        return pygame.Rect(
            panel.x + 8, panel.y + 36, panel.width - 24, max(40, panel.height - 44 - footer_h)
        )

    def _scroll_inner(self, content: pygame.Rect) -> pygame.Rect:
        return content.inflate(-4, -4)

    def _scroll_metrics(self, lines: list[str], content: pygame.Rect) -> tuple[int, int]:
        inner = self._scroll_inner(content)
        total = scroll_content_height(self.f_sm, lines, inner.width)
        max_scroll = max(0, total - inner.height)
        return total, max_scroll

    def _apply_scroll(self, game: GameSession, scroll_y: int, max_scroll: int) -> int:
        game.ui_scroll_y = clamp_scroll(scroll_y, max_scroll)
        return game.ui_scroll_y

    def _text_scroll_context(
        self, game: GameSession
    ) -> tuple[str, pygame.Rect, list[str]] | None:
        if game.build_info_tower:
            panel = self._build_info_panel_rect(game)
            lines = tower_preview_lines(game, game.build_info_tower)
            return ("build_info", self._detail_content_rect(panel), lines)
        if game.buff_panel_open:
            panel = self.buff_panel_rect()
            content = pygame.Rect(panel.x + 12, panel.y + 52, panel.width - 28, panel.height - 80)
            return ("buff", content, build_buff_lines(game))
        if game.state == GameState.TOWER_MENU and game.selected_tower_index is not None:
            _, stats, _ = self._tower_menu_layout(game, game.selected_tower_index)
            t = game.towers[game.selected_tower_index]
            lines = tower_stat_lines(game, t, game.selected_tower_index)
            return ("tower", self._detail_content_rect(stats), lines)
        if game.state == GameState.ENEMY_MENU and game.selected_enemy_index is not None:
            _, stats = self._enemy_menu_layout(game, game.selected_enemy_index)
            e = game.enemies[game.selected_enemy_index]
            lines = enemy_detail_lines(game, e)
            return ("enemy", self._detail_content_rect(stats), lines)
        if game.state == GameState.BASE_MENU:
            stats, _close = self._base_menu_layout(game)
            return ("base", self._detail_content_rect(stats), base_detail_lines(game))
        return None

    def try_begin_scroll_drag(self, game: GameSession, mx: int, my: int) -> bool:
        ctx = self._text_scroll_context(game)
        if not ctx:
            return False
        _kind, content, lines = ctx
        _total, max_scroll = self._scroll_metrics(lines, content)
        if max_scroll <= 0:
            return False
        scroll_y = self._apply_scroll(game, game.ui_scroll_y, max_scroll)
        inner = self._scroll_inner(content)
        hit = hit_scrollbar(mx, my, content, scroll_y, max_scroll)
        if hit:
            if hit == "track":
                th = scroll_thumb_rect(content, scroll_y, max_scroll)
                scroll_y = scroll_y_from_thumb_top(content, my - th.height // 2, max_scroll)
                scroll_y = self._apply_scroll(game, scroll_y, max_scroll)
            thumb = scroll_thumb_rect(content, scroll_y, max_scroll)
            game.scroll_drag = start_scroll_drag(_kind, mx, my, thumb)
            return True
        if inner.collidepoint(mx, my):
            game.scroll_drag = start_content_scroll_drag(_kind, my, scroll_y)
            return True
        return False

    def update_scroll_drag(self, game: GameSession, mx: int, my: int) -> bool:
        if not game.scroll_drag or game.scroll_drag.kind not in (
            "buff",
            "build_info",
            "tower",
            "enemy",
            "base",
        ):
            return False
        ctx = self._text_scroll_context(game)
        if not ctx or ctx[0] != game.scroll_drag.kind:
            return False
        _kind, content, lines = ctx
        _total, max_scroll = self._scroll_metrics(lines, content)
        if max_scroll <= 0:
            game.scroll_drag = None
            return False
        if game.scroll_drag.drag_mode == "content":
            y = drag_content_scroll_y(my, game.scroll_drag, max_scroll)
        else:
            y = drag_scroll_y(my, game.scroll_drag, content, max_scroll)
        self._apply_scroll(game, y, max_scroll)
        return True

    def end_scroll_drag(self, game: GameSession) -> None:
        game.scroll_drag = None

    def _draw_scrollbar(
        self, surf: pygame.Surface, content: pygame.Rect, scroll_y: int, max_scroll: int
    ) -> None:
        draw_scrollbar(surf, content, scroll_y, max_scroll)

    def _draw_detail_panel(
        self,
        surf: pygame.Surface,
        rect: pygame.Rect,
        title: str,
        lines: list[str],
        scroll_y: int = 0,
        *,
        border=(100, 120, 160),
        title_color=(255, 240, 200),
    ) -> int:
        """绘制详情面板，返回最大 scroll 值。"""
        pygame.draw.rect(surf, (28, 32, 42), rect, border_radius=8)
        pygame.draw.rect(surf, border, rect, 2, border_radius=8)
        title_r = pygame.Rect(rect.x + 8, rect.y + 6, rect.width - 40, 28)
        blit_in_rect(surf, self.f_md, title, title_r, title_color, pad=4)
        content = self._detail_content_rect(rect)
        max_scroll = self._scroll_metrics(lines, content)[1]
        scroll_y = clamp_scroll(scroll_y, max_scroll)
        blit_scroll_text(surf, self.f_sm, lines, content, scroll_y, (200, 205, 220))
        self._draw_scrollbar(surf, content, scroll_y, max_scroll)
        return max_scroll

    def handle_scroll_wheel(self, game: GameSession, delta_y: int) -> bool:
        ctx = self._text_scroll_context(game)
        if not ctx:
            return False
        _kind, content, lines = ctx
        _total, max_s = self._scroll_metrics(lines, content)
        if max_s <= 0:
            self._apply_scroll(game, 0, 0)
            return False
        step = int(delta_y * 22)
        self._apply_scroll(game, game.ui_scroll_y - step, max_s)
        return True

    def _menu_button_y(self, has_save: bool) -> int:
        """主菜单按钮区起始 Y，与 draw_menu 布局一致。"""
        return 280 if config.PORTRAIT else 200

    meta_shop_scroll: int = 0

    @property
    def META_SHOP_TOP(self) -> int:
        return 100 if config.PORTRAIT else 118

    @property
    def META_SHOP_ITEM_H(self) -> int:
        return 64 if config.PORTRAIT else 68

    @property
    def META_SHOP_VIEW_H(self) -> int:
        return max(280, config.HEIGHT - 200) if config.PORTRAIT else 430

    def draw_menu(self, surf: pygame.Surface, meta: MetaProgress, has_save: bool = False) -> None:
        self._draw_bg(surf)
        cx = config.WIDTH // 2
        title = self.f_title.render("叠层防线", True, (255, 220, 120))
        surf.blit(title, title.get_rect(center=(cx, 88 if config.PORTRAIT else 100)))

        y = self._menu_button_y(has_save)
        if has_save:
            btn_cont = pygame.Rect(cx - 120, y, 240, 50)
            pygame.draw.rect(surf, (80, 130, 180), btn_cont, border_radius=8)
            self._btn(surf, btn_cont, "继续存档")
            y += 62
        btn_start = pygame.Rect(cx - 120, y, 240, 50)
        btn_shop = pygame.Rect(cx - 120, y + 62, 240, 50)
        pygame.draw.rect(surf, (60, 140, 100), btn_start, border_radius=8)
        pygame.draw.rect(surf, (70, 90, 140), btn_shop, border_radius=8)
        label = "新游戏（覆盖存档）" if has_save else "开始游戏"
        self._btn(surf, btn_start, label)
        self._btn(surf, btn_shop, "局外解锁")

    def menu_hit(self, mx: int, my: int, has_save: bool = False) -> str | None:
        cx = config.WIDTH // 2
        y = self._menu_button_y(has_save)
        if has_save:
            if pygame.Rect(cx - 120, y, 240, 50).collidepoint(mx, my):
                return "continue"
            y += 62
        if pygame.Rect(cx - 120, y, 240, 50).collidepoint(mx, my):
            return "start"
        if pygame.Rect(cx - 120, y + 62, 240, 50).collidepoint(mx, my):
            return "shop"
        return None

    def _meta_shop_max_scroll(self, count: int) -> int:
        return max(0, count * self.META_SHOP_ITEM_H - self.META_SHOP_VIEW_H)

    def meta_shop_scroll_wheel(self, delta_y: int, meta: MetaProgress) -> None:
        max_s = self._meta_shop_max_scroll(len(meta.list_unlocks()))
        self.meta_shop_scroll = max(
            0, min(max_s, self.meta_shop_scroll - int(delta_y * 36))
        )

    def draw_meta_shop(self, surf: pygame.Surface, meta: MetaProgress) -> None:
        overlay = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        surf.blit(overlay, (0, 0))
        surf.blit(self.f_title.render("局外解锁", True, (255, 220, 120)), (40, 28))
        owned = len(meta.purchased)
        total = len(meta.data.get("unlocks", []))
        surf.blit(
            self.f_md.render(
                f"代币 {meta.tokens}  ·  已解锁 {owned}/{total}", True, (180, 200, 255)
            ),
            (40, 72),
        )
        unlocks = meta.list_unlocks()
        max_scroll = self._meta_shop_max_scroll(len(unlocks))
        self.meta_shop_scroll = max(0, min(max_scroll, self.meta_shop_scroll))
        view = pygame.Rect(36, self.META_SHOP_TOP, config.WIDTH - 72, self.META_SHOP_VIEW_H)
        pygame.draw.rect(surf, (28, 32, 48), view, border_radius=8)
        old_clip = surf.get_clip()
        surf.set_clip(view)
        y = self.META_SHOP_TOP + 6 - self.meta_shop_scroll
        for u in unlocks:
            rect = pygame.Rect(44, y, config.WIDTH - 88, self.META_SHOP_ITEM_H - 6)
            if rect.bottom < view.top or rect.top > view.bottom:
                y += self.META_SHOP_ITEM_H
                continue
            col = (50, 70, 55) if u["owned"] else (55, 65, 90) if u["can_buy"] else (45, 48, 58)
            pygame.draw.rect(surf, col, rect, border_radius=6)
            name_r = pygame.Rect(rect.x + 10, rect.y + 6, rect.width - 128, 24)
            blit_in_rect(surf, self.f_md, u["name"], name_r, (230, 235, 245), align="left", pad=4)
            desc_r = pygame.Rect(rect.x + 10, rect.y + 30, rect.width - 128, 30)
            blit_wrapped(surf, self.f_xs, u["desc"], desc_r, (160, 170, 190), pad=2)
            if u["owned"]:
                st = "已拥有"
            elif u["can_buy"]:
                st = f"购买 {u['cost']}"
            elif u.get("requires") and u["requires"] not in meta.purchased:
                st = "需前置"
            else:
                st = f"{u['cost']} 代币"
            st_r = pygame.Rect(rect.right - 118, rect.y + 10, 108, rect.height - 20)
            blit_in_rect(surf, self.f_xs, st, st_r, (200, 210, 230), align="center", pad=2)
            y += self.META_SHOP_ITEM_H
        surf.set_clip(old_clip)
        if max_scroll > 0:
            track = pygame.Rect(config.WIDTH - 28, self.META_SHOP_TOP + 4, 8, self.META_SHOP_VIEW_H - 8)
            pygame.draw.rect(surf, (40, 45, 60), track, border_radius=4)
            thumb_h = max(24, int(track.height * view.height / (len(unlocks) * self.META_SHOP_ITEM_H)))
            thumb_y = track.y + int(
                (track.height - thumb_h) * self.meta_shop_scroll / max_scroll
            )
            pygame.draw.rect(surf, (100, 120, 170), (track.x, thumb_y, track.width, thumb_h), border_radius=4)
        surf.blit(
            self.f_xs.render("滚轮浏览 · 点击空白处关闭", True, (130, 140, 160)),
            (40, config.HEIGHT - 28),
        )

    def meta_shop_hit(self, mx: int, my: int, meta: MetaProgress) -> str | None:
        view = pygame.Rect(36, self.META_SHOP_TOP, config.WIDTH - 72, self.META_SHOP_VIEW_H)
        if not view.collidepoint(mx, my):
            return None
        y = self.META_SHOP_TOP + 6 - self.meta_shop_scroll
        for u in meta.list_unlocks():
            rect = pygame.Rect(44, y, config.WIDTH - 88, self.META_SHOP_ITEM_H - 6)
            if rect.collidepoint(mx, my) and u["can_buy"]:
                return u["id"]
            y += self.META_SHOP_ITEM_H
        return None

    def _draw_bg(self, surf: pygame.Surface) -> None:
        if self._bg_tile:
            tw, th = self._bg_tile.get_size()
            for y in range(0, config.HEIGHT, th):
                for x in range(0, config.WIDTH, tw):
                    tile = self._bg_tile_alt if ((x // tw) + (y // th)) % 2 else self._bg_tile
                    surf.blit(tile, (x, y))
            vignette = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)
            cx, cy = config.WIDTH // 2, config.HEIGHT // 2 - 20
            for ring in range(8, 0, -1):
                alpha = int(12 + ring * 5)
                rx = int(config.WIDTH * 0.52 + ring * 28)
                ry = int(config.HEIGHT * 0.48 + ring * 22)
                pygame.draw.ellipse(
                    vignette, (8, 10, 18, alpha), (cx - rx, cy - ry, rx * 2, ry * 2), 4
                )
            surf.blit(vignette, (0, 0))
        else:
            surf.fill((26, 32, 42))

    def _draw_bullets(self, surf: pygame.Surface, game: GameSession) -> None:
        for b in game.bullets:
            if not b.alive:
                continue
            bsx, bsy = world_to_screen(b.x, b.y)
            bim = self.sprites.bullet(b.tower_type)
            if bim:
                if b.tower_type == "arrow":
                    dx, dy = b.tx - b.x, b.ty - b.y
                    if abs(dx) + abs(dy) > 0.01:
                        angle = math.degrees(math.atan2(-dy, dx))
                        img = pygame.transform.rotate(bim, angle)
                    else:
                        img = bim
                    rect = img.get_rect(center=(int(bsx), int(bsy)))
                    surf.blit(img, rect)
                else:
                    self._blit_center(surf, bim, int(bsx), int(bsy))
            else:
                pygame.draw.circle(surf, b.color, (int(bsx), int(bsy)), 5)

    def _draw_explosions(self, surf: pygame.Surface, game: GameSession) -> None:
        splash_boost = game.stats.splash_mult > 0
        for ex in game.explosions:
            p = ex.progress()
            cx, cy = ex.screen_center()
            scale = 1.0 + (0.12 if splash_boost else 0.0)
            r = ex.screen_radius() * (0.35 + p * 0.85) * scale
            alpha = int(220 * (1.0 - p))
            ring = pygame.Surface((int(r * 2 + 4), int(r * 2 + 4)), pygame.SRCALPHA)
            pygame.draw.circle(ring, (255, 160, 60, alpha), (int(r) + 2, int(r) + 2), int(r), 3)
            surf.blit(ring, (int(cx - r - 2), int(cy - r - 2)))
            core = pygame.Surface((int(r * 1.2), int(r * 1.2)), pygame.SRCALPHA)
            pygame.draw.circle(core, (255, 220, 120, int(140 * (1.0 - p))), (int(r * 0.6), int(r * 0.6)), int(r * 0.45))
            surf.blit(core, core.get_rect(center=(int(cx), int(cy))))
            for i in range(8):
                ang = i * (math.tau / 8) + p * 2.5
                dist = r * (0.5 + p * 0.5)
                px = int(cx + math.cos(ang) * dist)
                py = int(cy + math.sin(ang) * dist * 0.55)
                pygame.draw.circle(surf, (255, 200, 80), (px, py), max(2, int(4 * (1 - p))))

    def draw_world(self, surf: pygame.Surface, game: GameSession) -> None:
        from game.camera import camera_apply, view_zoom

        refresh_stack_layout(len(game.towers), build_bar_h=self.build_bar_height(game))
        scale = stack_scale()
        vz = view_zoom()
        self._draw_bg(surf)

        bx, by = camera_apply(config.BASE_X, config.BASE_Y)
        erx = int(config.SPAWN_RADIUS * vz)
        ery = int(config.SPAWN_RADIUS * 0.58 * vz)
        pygame.draw.ellipse(
            surf,
            (42, 48, 60),
            pygame.Rect(bx - erx, by - ery, erx * 2, ery * 2),
            2,
        )

        draw_range_ring(surf, game)

        guards_sorted = sorted(game.guards, key=lambda g: g.screen_pos()[1])
        for g in guards_sorted:
            if not g.alive:
                continue
            sx, sy = g.screen_pos()
            sx, sy = int(sx), int(sy)
            gr = max(4, int(g.radius * vz))
            gim = self.sprites.get("guard")
            if gim:
                self._blit_entity_sprite(surf, gim, sx, sy, g.radius, vz)
            else:
                pygame.draw.circle(surf, (90, 160, 220), (sx, sy), gr)
                pygame.draw.circle(surf, (200, 230, 255), (sx, sy), gr, 2)
            w = max(gr * 2, 28)
            bar_y = sy - int(g.radius) - 10
            ratio = max(0, g.hp / g.max_hp)
            pygame.draw.rect(surf, (35, 40, 50), pygame.Rect(sx - w // 2, bar_y, w, 4))
            pygame.draw.rect(
                surf, (80, 180, 255), pygame.Rect(sx - w // 2, bar_y, int(w * ratio), 4)
            )

        # 敌人（按屏幕 Y 排序，远的先画）
        enemies_sorted = sorted(game.enemies, key=lambda e: e.screen_pos()[1])
        for e in enemies_sorted:
            if not e.alive:
                continue
            sx, sy = e.screen_pos()
            sx, sy = int(sx), int(sy)
            eim = self.sprites.enemy(e.type_id)
            show_hud = enemy_shows_world_hud(game.enemy_defs, e.type_id)
            draw_enemy_buff_marks(surf, e, game, show_hud=show_hud)
            er = max(4, int(e.radius * vz))
            tier = enemy_tier(game.enemy_defs, e.type_id)
            ring_c = ENEMY_TIER_RING.get(tier, (160, 100, 100, 120))
            pygame.draw.circle(surf, ring_c[:3], (sx, sy), er + 3, 2)
            if eim:
                tint = eim.copy()
                if e.is_slowed():
                    tint.fill((100, 160, 255, 60), special_flags=pygame.BLEND_RGBA_ADD)
                    pygame.draw.circle(surf, (160, 210, 255), (sx, sy), er + 2, 2)
                self._blit_entity_sprite(surf, tint, sx, sy, e.radius, vz)
            else:
                col = e.color
                if e.is_slowed():
                    col = tuple(min(255, c + 40) for c in col)
                pygame.draw.circle(surf, col, (sx, sy), er)
            if show_hud:
                tag = enemy_world_tag(game.enemy_defs, e.type_id)
                w = max(er * 2, 36)
                bar_y = sy - er - 14
                ratio = max(0, e.hp / e.max_hp)
                pygame.draw.rect(surf, (40, 40, 40), pygame.Rect(sx - w // 2, bar_y, w, 5))
                pygame.draw.rect(
                    surf, (220, 60, 60), pygame.Rect(sx - w // 2, bar_y, int(w * ratio), 5)
                )
                if tag:
                    tag_img = self.f_sm.render(tag, True, (255, 220, 180))
                    surf.blit(tag_img, tag_img.get_rect(midbottom=(sx, bar_y - 2)))
            if (
                game.selected_enemy_index is not None
                and game.enemies[game.selected_enemy_index] is e
            ):
                er = max(4, int(e.radius * vz))
                pygame.draw.circle(surf, (255, 200, 100), (sx, sy), er + 8, 2)

        fx, fy = camera_apply(config.BASE_X, config.BASE_Y + 2)
        frw = max(20, int(FOUNDATION_RW * vz))
        frh = max(10, int(FOUNDATION_RH * vz))
        draw_iso_platform(
            surf,
            int(fx),
            int(fy),
            frw,
            frh,
            (72, 65, 52),
            (45, 40, 32),
        )
        found_img = self.sprites.get("foundation") or self.sprites.get("base")
        if found_img:
            self._blit_center_scaled(surf, found_img, int(fx), int(fy), max(0.55, vz))
        else:
            draw_iso_platform(
                surf, int(fx), int(fy), frw, frh, (120, 105, 80)
            )

        draw_base_buff_auras(surf, game)

        if game.towers:
            draw_stack_edges(surf, len(game.towers))

        # 塔层从低到高：每层先画平台阴影再画塔体（层数过高时整体缩小）
        label_font = self.f_xs if scale < 0.72 else self.f_sm
        for tower in sorted(game.towers, key=lambda t: t.floor):
            draw_tower_layer_base(surf, tower.floor, shadow=True)
            draw_tower_layer_base(surf, tower.floor)
            sx, sy = tower_screen_pos(tower.floor)
            tim = self.sprites.tower(tower.type_id)
            if tim:
                self._blit_center_scaled(surf, tim, sx, sy - 2, scale)
            else:
                tdef = game.tower_defs[tower.type_id]
                rw = scaled_size(48, 26)
                rh = scaled_size(22, 12)
                tint = TOWER_PLATFORM_TINT.get(tower.type_id, tuple(tdef["color"]))
                draw_iso_platform(surf, sx, sy, rw, rh, tint, (35, 38, 48))
            half_w = scaled_size(44, 22)
            pygame.draw.line(
                surf,
                (30, 34, 42),
                (sx - half_w, sy + int(10 * scale)),
                (sx + half_w, sy + int(10 * scale)),
                max(1, int(2 * scale)),
            )
            fl = label_font.render(f"{tower.floor}F Lv{tower.level}", True, (255, 248, 220))
            surf.blit(fl, (sx + scaled_size(32, 16), sy - scaled_size(22, 12)))
            if (
                game.selected_tower_index is not None
                and game.towers[game.selected_tower_index] is tower
            ):
                sel = scaled_size(46, 24)
                pygame.draw.ellipse(
                    surf,
                    (255, 220, 100),
                    pygame.Rect(sx - sel, sy - int(30 * scale), sel * 2, int(58 * scale)),
                    max(1, int(3 * scale)),
                )

        lx, ly = camera_apply(config.BASE_X, config.BASE_Y + 24)
        fd_label = self.f_sm.render("地基", True, (255, 240, 200))
        surf.blit(fd_label, fd_label.get_rect(center=(int(lx), int(ly))))

        draw_tower_buff_glows(surf, game)
        draw_base_pulse_burst(surf, game)
        draw_laser_beams(surf, game)

        draw_world_fx(surf, game)
        self._draw_bullets(surf, game)
        self._draw_explosions(surf, game)

    def buff_panel_rect(self) -> pygame.Rect:
        if config.PORTRAIT:
            return pygame.Rect(12, 96, config.WIDTH - 24, config.HEIGHT - 200)
        return pygame.Rect(config.WIDTH // 2 - 220, 72, 440, config.HEIGHT - 160)

    def buff_panel_btn_rect(self) -> pygame.Rect:
        return pygame.Rect(config.WIDTH - 100, 10, 88, 30)

    def buff_panel_hit(self, mx: int, my: int, game: GameSession) -> bool:
        """点击面板外或关闭区则关闭。"""
        panel = self.buff_panel_rect()
        close = pygame.Rect(panel.right - 34, panel.y + 10, 26, 26)
        if close.collidepoint(mx, my):
            return True
        return not panel.collidepoint(mx, my)

    def draw_buff_panel(self, surf: pygame.Surface, game: GameSession) -> None:
        overlay = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        surf.blit(overlay, (0, 0))
        panel = self.buff_panel_rect()
        pygame.draw.rect(surf, (28, 32, 42), panel, border_radius=10)
        pygame.draw.rect(surf, (90, 110, 150), panel, 2, border_radius=10)
        title = self.f_lg.render("当前增益", True, (255, 230, 160))
        surf.blit(title, title.get_rect(center=(panel.centerx, panel.y + 28)))
        close_r = pygame.Rect(panel.right - 34, panel.y + 10, 26, 26)
        pygame.draw.rect(surf, (70, 75, 90), close_r, border_radius=4)
        blit_in_rect(surf, self.f_sm, "×", close_r, (240, 240, 250), pad=2)
        content = pygame.Rect(panel.x + 12, panel.y + 52, panel.width - 28, panel.height - 102)
        lines = build_buff_lines(game)
        _total, max_s = self._scroll_metrics(lines, content)
        scroll_y = self._apply_scroll(game, game.ui_scroll_y, max_s)
        blit_scroll_text(surf, self.f_sm, lines, content, scroll_y, (210, 215, 230))
        self._draw_scrollbar(surf, content, scroll_y, max_s)
        foot_r = pygame.Rect(panel.x + 12, panel.bottom - 36, panel.width - 28, 28)
        hint_txt = "B/空白关闭"
        blit_in_rect(surf, self.f_sm, hint_txt, foot_r, (150, 160, 175), align="center", pad=2)

    def draw_toast(self, surf: pygame.Surface, game: GameSession) -> None:
        if not game.toast_message or game.toast_timer <= 0:
            return
        alpha = min(255, int(255 * min(1.0, game.toast_timer / 0.35)))
        pad_x, pad_y = 12, 0
        if config.PORTRAIT:
            pad_y = self.build_bar_y(game) - 36
        else:
            pad_y = self.build_bar_y(game) - 32
        text = self.f_md.render(game.toast_message, True, (255, 230, 200))
        bg = pygame.Surface((text.get_width() + pad_x * 2, text.get_height() + 12), pygame.SRCALPHA)
        bg.fill((30, 24, 18, min(220, alpha)))
        pygame.draw.rect(bg, (255, 140, 90, alpha), bg.get_rect(), 2, border_radius=6)
        rx = (config.WIDTH - bg.get_width()) // 2
        surf.blit(bg, (rx, max(8, pad_y - bg.get_height() // 2)))
        surf.blit(text, (rx + pad_x, max(14, pad_y - text.get_height() // 2)))

    def draw_hud(self, surf: pygame.Surface, game: GameSession) -> None:
        bar_w = min(200, config.WIDTH - 118) if config.PORTRAIT else 200
        pygame.draw.rect(surf, (40, 40, 50), pygame.Rect(12, 12, bar_w, 14))
        hr = max(0, game.base.hp / max(1, game.base.max_hp))
        pygame.draw.rect(surf, (70, 200, 120), pygame.Rect(12, 12, int(bar_w * hr), 14))
        surf.blit(
            self.f_sm.render(
                f"地基 {int(game.base.hp)}/{int(game.base.max_hp)}  "
                f"护盾 {int(game.base.shield)}"
                + (
                    f"/{int(game.stats.base_shield)}"
                    if game.stats.base_shield > 0
                    else ""
                )
                + (
                    f" +{game.stats.base_shield_regen:.0f}/s"
                    if game.stats.base_shield_regen > 0
                    else ""
                )
                + "  "
                f"塔层 {game.tower_count()}/{game.max_tower_floors_limit()}",
                True,
                (220, 220, 230),
            ),
            (12, 30),
        )
        mins = int(game.waves.elapsed // 60)
        secs = int(game.waves.elapsed % 60)
        surf.blit(
            self.f_sm.render(
                f"时间 {mins:02d}:{secs:02d}  金币 {game.gold}  Lv.{game.level}",
                True,
                (200, 205, 220),
            ),
            (12, 52),
        )
        exp_need = game.xp_to_next()
        exp_w = min(180, bar_w - 20)
        pygame.draw.rect(surf, (40, 40, 50), pygame.Rect(12, 76, exp_w, 8))
        er = min(1, game.exp / max(1, exp_need))
        pygame.draw.rect(surf, (120, 160, 255), pygame.Rect(12, 76, int(exp_w * er), 8))
        surf.blit(self.f_sm.render(f"经验 {game.exp}/{exp_need}", True, (180, 190, 210)), (12, 88))
        if game.stats.double_shot_chance > 0:
            pct = int(min(100, game.stats.double_shot_chance * 100))
            surf.blit(
                self.f_sm.render(f"箭塔双发概率 {pct}%", True, (200, 220, 255)),
                (12, 128),
            )
        alive = sum(1 for e in game.enemies if e.alive)
        msg = f"场上敌人 {alive}"
        if game.endless_mode:
            msg += f"  |  无尽 第{game.waves.endless_cycle}轮"
        elif game.waves.all_scheduled_spawned:
            msg += "  |  最后一波！清空即胜"
        else:
            msg += "  |  四面八方来敌"
        surf.blit(self.f_sm.render(msg, True, (180, 190, 210)), (12, 108))
        btn = self.buff_panel_btn_rect()
        hot = game.buff_panel_open
        pygame.draw.rect(surf, (55, 70, 100) if hot else (45, 50, 62), btn, border_radius=5)
        pygame.draw.rect(surf, (120, 150, 200) if hot else (80, 90, 110), btn, 2, border_radius=5)
        n = sum(game.stats.upgrade_stacks.values()) + len(game.meta_buff_lines)
        label = f"增益({n})" if n else "增益(B)"
        blit_in_rect(surf, self.f_sm, label, btn, (220, 225, 240), pad=4)

    def _build_bar_layout(self, count: int) -> dict:
        pad_x, pad_top = 8, 7
        gap_x = 8
        slot_w, slot_h = (108, 48) if config.PORTRAIT else (124, 50)
        content_w = pad_x * 2 + max(0, count) * slot_w + max(0, count - 1) * gap_x
        max_scroll_x = max(0, content_w - config.WIDTH)
        return {
            "slot_w": slot_w,
            "slot_h": slot_h,
            "gap_x": gap_x,
            "pad_x": pad_x,
            "pad_top": pad_top,
            "content_w": content_w,
            "max_scroll_x": max_scroll_x,
            "total_h": config.BUILD_BAR_HEIGHT,
        }

    def build_bar_height(self, game: GameSession) -> int:
        return config.BUILD_BAR_HEIGHT

    def build_bar_y(self, game: GameSession | None = None) -> int:
        return config.HEIGHT - config.BUILD_BAR_HEIGHT

    def _build_bar_viewport(self, game: GameSession) -> pygame.Rect:
        y = self.build_bar_y(game)
        return pygame.Rect(0, y, config.WIDTH, config.BUILD_BAR_HEIGHT)

    def _clamp_build_bar_scroll(self, game: GameSession) -> None:
        max_s = self._build_bar_layout(len(game.build_bar_types()))["max_scroll_x"]
        self.build_bar_scroll_x = max(0, min(max_s, self.build_bar_scroll_x))

    def _build_bar_scroll_track(self, game: GameSession) -> tuple[pygame.Rect, pygame.Rect]:
        vp = self._build_bar_viewport(game)
        max_s = self._build_bar_layout(len(game.build_bar_types()))["max_scroll_x"]
        track = pygame.Rect(vp.x + 6, vp.bottom - 6, vp.width - 12, 4)
        if max_s <= 0:
            return track, pygame.Rect(track.x, track.y, 0, 0)
        tw = max(24, int(track.width * vp.width / (vp.width + max_s)))
        tx = track.x + int((track.width - tw) * self.build_bar_scroll_x / max_s)
        return track, pygame.Rect(tx, track.y, tw, track.height)

    def build_bar_scroll_wheel(self, game: GameSession, delta_y: int) -> bool:
        max_s = self._build_bar_layout(len(game.build_bar_types()))["max_scroll_x"]
        if max_s <= 0:
            return False
        self.build_bar_scroll_x -= int(delta_y * 48)
        self._clamp_build_bar_scroll(game)
        return True

    def try_begin_build_bar_scroll_drag(self, game: GameSession, mx: int, my: int) -> bool:
        if not self._build_bar_viewport(game).collidepoint(mx, my):
            return False
        track, thumb = self._build_bar_scroll_track(game)
        max_s = self._build_bar_layout(len(game.build_bar_types()))["max_scroll_x"]
        if max_s <= 0:
            return False
        if thumb.width > 0 and thumb.collidepoint(mx, my):
            self._build_bar_h_drag = (mx, self.build_bar_scroll_x)
            return True
        if track.collidepoint(mx, my):
            tw = max(24, thumb.width)
            rel = max(0, min(track.width - tw, mx - track.x - tw // 2))
            self.build_bar_scroll_x = int(rel / max(1, track.width - tw) * max_s)
            self._clamp_build_bar_scroll(game)
            self._build_bar_h_drag = (mx, self.build_bar_scroll_x)
            return True
        return False

    def update_build_bar_scroll_drag(self, game: GameSession, mx: int) -> bool:
        if self._build_bar_h_drag is None:
            return False
        start_mx, start_scroll = self._build_bar_h_drag
        track, _thumb = self._build_bar_scroll_track(game)
        max_s = self._build_bar_layout(len(game.build_bar_types()))["max_scroll_x"]
        tw = max(24, int(track.width * config.WIDTH / (config.WIDTH + max_s)))
        travel = max(1, track.width - tw)
        self.build_bar_scroll_x = start_scroll + int((mx - start_mx) / travel * max_s)
        self._clamp_build_bar_scroll(game)
        return True

    def end_build_bar_scroll_drag(self) -> None:
        self._build_bar_h_drag = None

    def _build_bar_slots(self, game: GameSession) -> list[dict]:
        types = game.build_bar_types()
        layout = self._build_bar_layout(len(types))
        self._clamp_build_bar_scroll(game)
        scroll_x = self.build_bar_scroll_x
        bar_top = config.HEIGHT - layout["total_h"]
        slots = []
        for i, tid in enumerate(types):
            x0 = layout["pad_x"] + i * (layout["slot_w"] + layout["gap_x"]) - scroll_x
            y0 = bar_top + layout["pad_top"]
            rect = pygame.Rect(x0, y0, layout["slot_w"], layout["slot_h"])
            info_r = pygame.Rect(rect.right - 30, rect.centery - 12, 24, 24)
            pick_r = pygame.Rect(rect.x, rect.y, rect.width - 34, rect.height)
            slots.append({"id": tid, "rect": rect, "info": info_r, "pick": pick_r})
        return slots

    def draw_build_bar(self, surf: pygame.Surface, game: GameSession) -> None:
        layout = self._build_bar_layout(len(game.build_bar_types()))
        vp = self._build_bar_viewport(game)
        pygame.draw.rect(surf, (22, 26, 34), vp)
        bar_clip = surf.get_clip()
        surf.set_clip(vp)
        try:
            for slot in self._build_bar_slots(game):
                tid = slot["id"]
                rect = slot["rect"]
                tdef = game.tower_defs[tid]
                sel = game.selected_build is not None and tid == game.selected_build
                col = (90, 110, 150) if sel else (55, 62, 78)
                pygame.draw.rect(surf, col, rect, border_radius=6)
                if sel:
                    pygame.draw.rect(surf, (140, 180, 255), rect, 2, border_radius=6)
                tim = self.sprites.tower(tid)
                if tim:
                    scale = min(1.0, 40 / max(tim.get_width(), tim.get_height()))
                    tw, th = int(tim.get_width() * scale), int(tim.get_height() * scale)
                    icon = pygame.transform.smoothscale(tim, (max(1, tw), max(1, th)))
                    surf.blit(icon, icon.get_rect(center=(rect.x + 22, rect.centery)))
                text_area = pygame.Rect(rect.x + 40, rect.y + 3, rect.width - 74, rect.height - 6)
                text_clip = surf.get_clip()
                surf.set_clip(text_area)
                try:
                    ty = text_area.y + 2
                    ty += blit_topleft(
                        surf, self.f_xs, tdef["name"], text_area.x, ty, text_area.width, (230, 230, 240)
                    )
                    ty += 4
                    price = f"{game.build_cost(tid)}金"
                    price_img = fit_render(self.f_xs, price, text_area.width, (255, 220, 120))
                    price_y = min(ty, text_area.bottom - price_img.get_height() - 1)
                    surf.blit(price_img, (text_area.x, price_y))
                finally:
                    surf.set_clip(text_clip)
                info_r = slot["info"]
                draw_info_icon(surf, info_r.centerx, info_r.centery, self.f_xs, 9)
        finally:
            surf.set_clip(bar_clip)

        track, thumb = self._build_bar_scroll_track(game)
        if layout["max_scroll_x"] > 0:
            pygame.draw.rect(surf, (38, 42, 52), track, border_radius=2)
            if thumb.width > 0:
                pygame.draw.rect(surf, (95, 115, 155), thumb, border_radius=2)

        if game.build_info_tower:
            self._draw_build_info_popup(surf, game)

    def _build_info_panel_rect(self, game: GameSession) -> pygame.Rect:
        tid = game.build_info_tower
        if not tid:
            return pygame.Rect(0, 0, 0, 0)
        bar_h = self.build_bar_height(game)
        max_h = min(240, config.HEIGHT - bar_h - 40)
        panel = pygame.Rect(config.WIDTH // 2 - 130, self.build_bar_y(game) - max_h - 8, 260, max_h)
        panel.clamp_ip(pygame.Rect(8, 8, config.WIDTH - 16, config.HEIGHT - 16))
        return panel

    def _draw_build_info_popup(self, surf: pygame.Surface, game: GameSession) -> None:
        tid = game.build_info_tower
        if not tid:
            return
        tdef = game.tower_defs[tid]
        panel = self._build_info_panel_rect(game)
        overlay = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 80))
        surf.blit(overlay, (0, 0))
        lines = tower_preview_lines(game, tid)
        content = self._detail_content_rect(panel)
        _total, max_s = self._scroll_metrics(lines, content)
        scroll_y = self._apply_scroll(game, game.ui_scroll_y, max_s)
        self._draw_detail_panel(
            surf,
            panel,
            f"{tdef['name']} · 详情",
            lines,
            scroll_y,
            border=(100, 150, 200),
        )
        close_r = pygame.Rect(panel.right - 28, panel.y + 6, 22, 22)
        pygame.draw.rect(surf, (60, 65, 80), close_r, border_radius=4)
        blit_in_rect(surf, self.f_xs, "×", close_r, (240, 240, 250), pad=0)

    def build_bar_hit(self, mx: int, my: int, game: GameSession) -> tuple[str, str | None]:
        """返回 (action, tower_id)。action: select | info | close_info | None"""
        if game.build_info_tower:
            panel = self._build_info_panel_rect(game)
            close_r = pygame.Rect(panel.right - 28, panel.y + 6, 22, 22)
            if close_r.collidepoint(mx, my):
                return ("close_info", None)
            if panel.collidepoint(mx, my):
                return ("none", None)
            return ("close_info", None)
        if my < self.build_bar_y(game):
            return ("none", None)
        for slot in self._build_bar_slots(game):
            if slot["info"].collidepoint(mx, my):
                return ("info", slot["id"])
            if slot["pick"].collidepoint(mx, my):
                return ("select", slot["id"])
        return ("none", None)

    def _upgrade_card_layout(self, count: int) -> tuple[int, int, int, int, int]:
        if config.PORTRAIT:
            card_w, card_h, gap, cols = 230, 200, 12, 2
            grid_w = cols * card_w + (cols - 1) * gap
            x0 = (config.WIDTH - grid_w) // 2
            y0 = 118
            return card_w, card_h, gap, x0, y0
        card_w, card_h, gap = 200, 248, 16
        x0 = (config.WIDTH - (4 * card_w + 3 * gap)) // 2
        return card_w, card_h, gap, x0, 132

    def draw_upgrade_overlay(self, surf: pygame.Surface, game: GameSession) -> None:
        overlay = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surf.blit(overlay, (0, 0))
        t = self.f_title.render("经验已满 — 选择一项强化", True, (255, 220, 120))
        surf.blit(t, t.get_rect(center=(config.WIDTH // 2, 72 if config.PORTRAIT else 80)))
        card_w, card_h, gap, x0, y0 = self._upgrade_card_layout(len(game.upgrade_choices))
        cols = 2 if config.PORTRAIT else 4
        for i, card in enumerate(game.upgrade_choices):
            col = i % cols
            row = i // cols
            rect = pygame.Rect(
                x0 + col * (card_w + gap),
                y0 + row * (card_h + gap),
                card_w,
                card_h,
            )
            border = {
                "base": (80, 200, 140),
                "tower": (90, 160, 220),
                "global": (200, 180, 80),
                "curse": (200, 80, 120),
            }.get(card.get("tag", ""), (120, 120, 140))
            pygame.draw.rect(surf, (35, 40, 52), rect, border_radius=8)
            pygame.draw.rect(surf, border, rect, 2, border_radius=8)
            name_r = pygame.Rect(rect.x + 8, rect.y + 10, rect.width - 16, 32)
            blit_in_rect(
                surf, self.f_md, upgrade_pick_title(card, game.stats), name_r, (240, 240, 250), pad=4
            )
            pick_rows = upgrade_pick_rows(card, game.stats)
            if pick_rows:
                stat_r = pygame.Rect(rect.x + 8, rect.y + 48, rect.width - 16, rect.height - 56)
                inner = stat_r.inflate(-8, -8)
                y = inner.y
                old_clip = surf.get_clip()
                surf.set_clip(stat_r)
                for desc, value in pick_rows:
                    if y >= inner.bottom:
                        break
                    desc_img = fit_render(self.f_sm, desc, inner.width, (200, 205, 220))
                    if y + desc_img.get_height() <= inner.bottom:
                        surf.blit(desc_img, (inner.x, y))
                        y += desc_img.get_height() + 2
                    if value is None:
                        y += 4
                        continue
                    val_img = fit_render(self.f_sm, value, inner.width, (255, 215, 120))
                    if y + val_img.get_height() <= inner.bottom:
                        surf.blit(val_img, (inner.x, y))
                        y += val_img.get_height() + 6
                surf.set_clip(old_clip)
            else:
                desc_r = pygame.Rect(rect.x + 8, rect.y + 44, rect.width - 16, rect.height - 52)
                blit_wrapped(surf, self.f_sm, card["desc"], desc_r, (180, 185, 200), pad=2)

    def upgrade_card_hit(self, mx: int, my: int, game: GameSession) -> int | None:
        card_w, card_h, gap, x0, y0 = self._upgrade_card_layout(len(game.upgrade_choices))
        cols = 2 if config.PORTRAIT else 4
        for i in range(len(game.upgrade_choices)):
            col = i % cols
            row = i // cols
            rect = pygame.Rect(
                x0 + col * (card_w + gap),
                y0 + row * (card_h + gap),
                card_w,
                card_h,
            )
            if rect.collidepoint(mx, my):
                return i
        return None

    def _endless_offer_layout(self) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
        pw, ph = (config.WIDTH - 32, 236) if config.PORTRAIT else (440, 236)
        panel = pygame.Rect(config.WIDTH // 2 - pw // 2, config.HEIGHT // 2 - ph // 2, pw, ph)
        btn_w, btn_h, gap = 168, 44, 20
        y = panel.bottom - 16 - btn_h
        x0 = panel.centerx - btn_w - gap // 2
        yes_r = pygame.Rect(x0, y, btn_w, btn_h)
        no_r = pygame.Rect(x0 + btn_w + gap, y, btn_w, btn_h)
        return panel, yes_r, no_r

    def endless_offer_hit(self, mx: int, my: int) -> str | None:
        _panel, yes_r, no_r = self._endless_offer_layout()
        if yes_r.collidepoint(mx, my):
            return "yes"
        if no_r.collidepoint(mx, my):
            return "no"
        return None

    def draw_endless_offer(
        self, surf: pygame.Surface, game: GameSession, token_gain: int = 0
    ) -> None:
        overlay = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        surf.blit(overlay, (0, 0))
        panel, yes_r, no_r = self._endless_offer_layout()
        pygame.draw.rect(surf, (32, 38, 52), panel, border_radius=12)
        pygame.draw.rect(surf, (90, 110, 150), panel, 2, border_radius=12)
        title = self.f_title.render("预定波次已清空！", True, (120, 255, 180))
        surf.blit(title, title.get_rect(center=(panel.centerx, panel.y + 42)))
        mins = int(game.waves.elapsed // 60)
        secs = int(game.waves.elapsed % 60)
        extra = f"  ·  代币 +{token_gain}" if token_gain else ""
        sub = self.f_md.render(
            f"用时 {mins:02d}:{secs:02d}  ·  等级 {game.level}{extra}",
            True,
            (210, 215, 230),
        )
        surf.blit(sub, sub.get_rect(center=(panel.centerx, panel.y + 88)))
        hint = self.f_sm.render("是否进入无尽模式继续战斗？", True, (180, 190, 210))
        surf.blit(hint, hint.get_rect(center=(panel.centerx, panel.y + 122)))
        for rect, label, fill, border in (
            (yes_r, "进入无尽", (55, 95, 75), (100, 200, 140)),
            (no_r, "返回结算", (55, 58, 72), (120, 130, 160)),
        ):
            pygame.draw.rect(surf, fill, rect, border_radius=8)
            pygame.draw.rect(surf, border, rect, 2, border_radius=8)
            blit_in_rect(surf, self.f_md, label, rect, (235, 240, 250), pad=6)

    def draw_end_screen(
        self, surf: pygame.Surface, game: GameSession, won: bool, token_gain: int = 0
    ) -> None:
        overlay = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surf.blit(overlay, (0, 0))
        title = "胜利！" if won else "地基被毁"
        col = (120, 255, 160) if won else (255, 100, 100)
        t = self.f_title.render(title, True, col)
        surf.blit(t, t.get_rect(center=(config.WIDTH // 2, config.HEIGHT // 2 - 50)))
        mins = int(game.waves.elapsed // 60)
        secs = int(game.waves.elapsed % 60)
        extra = f"  |  获得代币 +{token_gain}" if won and token_gain else ""
        sub = self.f_md.render(
            f"用时 {mins:02d}:{secs:02d}  |  等级 {game.level}{extra}  |  点击返回主菜单",
            True,
            (220, 220, 230),
        )
        surf.blit(sub, sub.get_rect(center=(config.WIDTH // 2, config.HEIGHT // 2 + 10)))

    def draw_stack_highlight(self, surf: pygame.Surface, game: GameSession, mx: int, my: int) -> None:
        from game.camera import camera_apply, view_zoom

        tid = game.build_drag or game.selected_build
        if game.state != GameState.PLAYING or not tid:
            return
        if not game.click_on_stack_build_area(mx, my):
            return
        can = game.can_build_stack(tid)
        col = (120, 200, 255) if can else (255, 100, 100)
        z = view_zoom()
        ti = game.tower_index_at(mx, my)
        if ti is not None:
            t = game.towers[ti]
            ox, oy = tower_screen_pos(t.floor)
            rw = max(22, int(44 * z))
            rh = max(14, int(28 * z))
            pygame.draw.ellipse(
                surf, col, pygame.Rect(int(ox) - rw, int(oy) - rh, rw * 2, rh * 2), max(1, int(2 * z))
            )
        else:
            bx, by = camera_apply(config.BASE_X, config.BASE_Y)
            rw = max(20, int(52 * z * 0.92))
            rh = max(12, int(26 * z * 1.05))
            pygame.draw.ellipse(
                surf, col, pygame.Rect(int(bx) - rw, int(by) - rh, rw * 2, rh * 2), max(1, int(2 * z))
            )
        hint = self.f_sm.render(game.build_hint(tid), True, col)
        surf.blit(hint, (mx + 12, my - 8))

    def draw_build_drag(self, surf: pygame.Surface, game: GameSession, mx: int, my: int) -> None:
        tid = game.build_drag
        if not tid or game.state != GameState.PLAYING:
            return
        tim = self.sprites.tower(tid)
        if tim:
            scale = min(1.2, 48 / max(tim.get_width(), tim.get_height()))
            tw, th = int(tim.get_width() * scale), int(tim.get_height() * scale)
            icon = pygame.transform.smoothscale(tim, (max(1, tw), max(1, th)))
            surf.blit(icon, icon.get_rect(center=(mx, my - 16)))
        can = game.can_build_stack(tid)
        col = (120, 200, 255) if can else (255, 100, 100)
        hint = self.f_sm.render(game.build_hint(tid), True, col)
        surf.blit(hint, (mx + 14, my + 6))
        self.draw_stack_highlight(surf, game, mx, my)

    def _tower_menu_button_defs(self, game: GameSession, index: int) -> list[str]:
        t = game.towers[index]
        keys = ["upgrade", "swap"]
        if t.type_id == "laser" and game.stats.laser_sweep_unlock:
            keys.extend(["laser_smart", "laser_mode"])
        keys.extend(["sell", "close"])
        return keys

    def _tower_menu_layout(
        self, game: GameSession, index: int
    ) -> tuple[pygame.Rect, pygame.Rect, list[tuple[str, pygame.Rect]]]:
        t = game.towers[index]
        sx, sy = tower_screen_pos(t.floor)
        n_btn = len(self._tower_menu_button_defs(game, index))
        action_h = 44 + n_btn * 32 + 8
        stats_h = max(220, action_h)
        h = max(action_h, stats_h)
        action = pygame.Rect(sx - 92, sy - h - 8, 184, action_h)
        stats = pygame.Rect(action.right + 8, action.y, 200, stats_h)
        combined = action.union(stats)
        if combined.right > config.WIDTH - 8:
            shift = combined.right - (config.WIDTH - 8)
            action.x -= shift
            stats.x -= shift
        if combined.left < 8:
            shift = 8 - combined.left
            action.x += shift
            stats.x += shift
        if combined.top < 8:
            action.y += 8 - combined.top
            stats.y = action.y
        if combined.bottom > config.HEIGHT - 80:
            action.y -= combined.bottom - (config.HEIGHT - 80)
            stats.y = action.y
        buttons = []
        y = action.y + 44
        for key in self._tower_menu_button_defs(game, index):
            r = pygame.Rect(action.x + 8, y, action.width - 16, 30)
            buttons.append((key, r))
            y += 32
        return action, stats, buttons

    def _base_menu_layout(self, game: GameSession) -> tuple[pygame.Rect, pygame.Rect]:
        from game.camera import camera_apply

        bx, by = camera_apply(config.BASE_X, config.BASE_Y)
        panel_h = min(300, config.HEIGHT - 96)
        stats = pygame.Rect(int(bx) - 110, int(by) - panel_h - 20, 220, panel_h)
        stats.clamp_ip(pygame.Rect(8, 8, config.WIDTH - 16, config.HEIGHT - 88))
        close_r = pygame.Rect(stats.x + 8, stats.bottom - 40, stats.width - 16, 32)
        return stats, close_r

    def _enemy_menu_layout(self, game: GameSession, index: int) -> tuple[pygame.Rect, pygame.Rect]:
        e = game.enemies[index]
        sx, sy = int(e.screen_pos()[0]), int(e.screen_pos()[1])
        action = pygame.Rect(sx + 24, sy - 100, 160, 88)
        stats = pygame.Rect(action.right + 8, action.y, 220, min(220, config.HEIGHT - 100))
        combined = action.union(stats)
        if combined.right > config.WIDTH - 8:
            shift = combined.right - (config.WIDTH - 8)
            action.x -= shift
            stats.x -= shift
        if combined.left < 8:
            shift = 8 - combined.left
            action.x += shift
            stats.x += shift
        if combined.top < 8:
            action.y = 8
            stats.y = 8
        if combined.bottom > config.HEIGHT - 80:
            action.y = config.HEIGHT - 80 - combined.height
            stats.y = action.y
        return action, stats

    def draw_tower_menu(self, surf: pygame.Surface, game: GameSession) -> None:
        refresh_stack_layout(len(game.towers), build_bar_h=self.build_bar_height(game))
        if game.selected_tower_index is None:
            return
        idx = game.selected_tower_index
        t = game.towers[idx]
        tdef = game.tower_defs[t.type_id]

        if game.state == GameState.TOWER_SWAP:
            overlay = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            surf.blit(overlay, (0, 0))
            tip = self.f_md.render(
                f"调换位置：点击另一层与 {t.floor}F·{tdef['name']} 交换", True, (255, 220, 120)
            )
            surf.blit(tip, tip.get_rect(center=(config.WIDTH // 2, 48)))
            for i, other in enumerate(game.towers):
                if i == game.swap_source_index:
                    continue
                ox, oy = tower_screen_pos(other.floor)
                pygame.draw.ellipse(surf, (120, 200, 255), pygame.Rect(ox - 48, oy - 32, 96, 60), 2)
            return

        action, stats, buttons = self._tower_menu_layout(game, idx)
        overlay = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))
        surf.blit(overlay, (0, 0))
        title_text = f"{t.floor}F · {tdef['name']} Lv{t.level}"
        title_r = pygame.Rect(action.x + 8, action.y + 8, action.width - 16, 32)
        pygame.draw.rect(surf, (32, 38, 50), action, border_radius=8)
        pygame.draw.rect(surf, (100, 120, 160), action, 2, border_radius=8)
        blit_in_rect(surf, self.f_md, title_text, title_r, (255, 240, 200), pad=4)
        lines = tower_stat_lines(game, t, idx)
        content = self._detail_content_rect(stats)
        _total, max_s = self._scroll_metrics(lines, content)
        scroll_y = self._apply_scroll(game, game.ui_scroll_y, max_s)
        self._draw_detail_panel(
            surf,
            stats,
            "塔属性",
            lines,
            scroll_y,
            border=(90, 130, 170),
        )

        from game.laser_combat import laser_mode_label

        for key, rect in buttons:
            if key == "sell":
                refund = int(
                    game.build_cost(t.type_id)
                    * config.TOWER_SELL_REFUND_RATIO
                    * (1 + 0.1 * (t.level - 1))
                )
                label = f"出售 (+{refund}金)"
                col = (70, 100, 75)
            elif key == "upgrade":
                ok = game.can_upgrade_tower(idx)
                label = game.upgrade_tower_label(idx)
                col = (65, 85, 120) if ok else (55, 55, 62)
            elif key == "swap":
                if len(game.towers) < 2:
                    label = "调换(需2层+)"
                    col = (55, 55, 62)
                else:
                    label = "调换层位"
                    col = (85, 75, 110)
            elif key == "laser_smart":
                label = f"智能切换 {'开' if t.laser_auto else '关'}"
                col = (90, 75, 130) if t.laser_auto else (65, 60, 85)
            elif key == "laser_mode":
                if t.laser_auto:
                    label = f"当前·{laser_mode_label(game, t, tdef)}"
                    col = (55, 55, 62)
                else:
                    label = "攻击：扫射" if t.laser_mode == "sweep" else "攻击：单体蓄能"
                    col = (75, 90, 130) if t.laser_mode == "sweep" else (85, 75, 110)
            else:
                label = "关闭"
                col = (60, 62, 72)
            pygame.draw.rect(surf, col, rect, border_radius=4)
            blit_in_rect(surf, self.f_sm, label, rect, (235, 238, 245), align="center", pad=6)

    def draw_enemy_menu(self, surf: pygame.Surface, game: GameSession) -> None:
        if game.selected_enemy_index is None:
            return
        idx = game.selected_enemy_index
        if idx >= len(game.enemies) or not game.enemies[idx].alive:
            return
        e = game.enemies[idx]
        edef = game.enemy_defs[e.type_id]
        action, stats = self._enemy_menu_layout(game, idx)
        overlay = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))
        surf.blit(overlay, (0, 0))
        pygame.draw.rect(surf, (40, 34, 48), action, border_radius=8)
        pygame.draw.rect(surf, (160, 100, 120), action, 2, border_radius=8)
        close_r = pygame.Rect(action.x + 8, action.y + 44, action.width - 16, 34)
        pygame.draw.rect(surf, (65, 55, 72), close_r, border_radius=4)
        blit_in_rect(surf, self.f_sm, "关闭", close_r, (235, 238, 245), pad=6)
        title = f"{edef['name']}"
        if enemy_shows_world_hud(game.enemy_defs, e.type_id):
            title += f" · {enemy_world_tag(game.enemy_defs, e.type_id)}"
        title_r = pygame.Rect(action.x + 8, action.y + 6, action.width - 16, 32)
        blit_in_rect(surf, self.f_md, title, title_r, (255, 220, 200), pad=4)
        lines = enemy_detail_lines(game, e)
        content = self._detail_content_rect(stats)
        _total, max_s = self._scroll_metrics(lines, content)
        scroll_y = self._apply_scroll(game, game.ui_scroll_y, max_s)
        self._draw_detail_panel(
            surf,
            stats,
            "敌人情报",
            lines,
            scroll_y,
            border=(140, 90, 110),
            title_color=(255, 210, 200),
        )

    def draw_base_menu(self, surf: pygame.Surface, game: GameSession) -> None:
        from game.camera import camera_apply, view_zoom

        stats, close_r = self._base_menu_layout(game)
        overlay = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))
        surf.blit(overlay, (0, 0))
        bx, by = camera_apply(config.BASE_X, config.BASE_Y)
        z = view_zoom()
        rw = max(20, int(52 * z * 0.92))
        rh = max(12, int(26 * z * 1.05))
        pygame.draw.ellipse(
            surf, (255, 220, 140), pygame.Rect(int(bx) - rw, int(by) - rh, rw * 2, rh * 2), 3
        )
        lines = base_detail_lines(game)
        content = self._detail_content_rect(stats, footer_h=48)
        _total, max_s = self._scroll_metrics(lines, content)
        scroll_y = self._apply_scroll(game, game.ui_scroll_y, max_s)
        self._draw_detail_panel(
            surf,
            stats,
            "地基状态",
            lines,
            scroll_y,
            border=(150, 130, 90),
            title_color=(255, 230, 170),
        )
        pygame.draw.rect(surf, (60, 62, 72), close_r, border_radius=4)
        blit_in_rect(surf, self.f_sm, "关闭", close_r, (235, 238, 245), align="center", pad=6)

    def base_menu_hit(self, mx: int, my: int, game: GameSession) -> str | None:
        stats, close_r = self._base_menu_layout(game)
        if close_r.collidepoint(mx, my):
            return "close"
        if stats.collidepoint(mx, my):
            return None
        return "close"

    def enemy_menu_hit(self, mx: int, my: int, game: GameSession) -> str | None:
        if game.selected_enemy_index is None:
            return None
        action, stats = self._enemy_menu_layout(game, game.selected_enemy_index)
        if action.collidepoint(mx, my):
            close_r = pygame.Rect(action.x + 8, action.y + 44, action.width - 16, 34)
            if close_r.collidepoint(mx, my):
                return "close"
            return None
        if stats.collidepoint(mx, my):
            return None
        return "close"

    def tower_menu_hit(self, mx: int, my: int, game: GameSession) -> str | None:
        if game.selected_tower_index is None:
            return None
        if game.state == GameState.TOWER_SWAP:
            ti = game.tower_index_at(mx, my)
            if ti is not None and ti != game.swap_source_index:
                game.swap_towers(game.swap_source_index, ti)
            elif dist(mx, my, config.BASE_X, config.BASE_Y) > 200:
                game.close_tower_ui()
            return "swap_done"
        action, stats, buttons = self._tower_menu_layout(game, game.selected_tower_index)
        if not action.collidepoint(mx, my) and not stats.collidepoint(mx, my):
            return "close"
        if stats.collidepoint(mx, my) and not action.collidepoint(mx, my):
            return None
        for key, rect in buttons:
            if rect.collidepoint(mx, my):
                if key == "swap" and len(game.towers) < 2:
                    return None
                if key == "laser_mode" and game.towers[game.selected_tower_index].laser_auto:
                    return None
                return key
        return None
