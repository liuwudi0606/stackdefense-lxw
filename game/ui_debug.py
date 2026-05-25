"""调试菜单 UI。"""



from __future__ import annotations



import pygame



import config

from game.session import GameSession

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
    draw_info_icon,
    fit_render,
    scroll_content_height,
)

from game.debug_buff_catalog import (
    BuffListEntry,
    build_buff_list_entries,
    entry_height,
)
from game.upgrades import find_upgrade, upgrade_detail_lines


_DEBUG_SCROLL_WIDTH = 5
_DEBUG_SCROLL_GAP = 2


class DebugUI:

    QUICK = [

        ("gold500", "+500 金"),

        ("gold2000", "+2000 金"),

        ("clear", "清空敌人"),

        ("heal", "地基满血"),

        ("level", "升 1 级"),

        ("exp", "满经验条"),

        ("spawn", "刷 10 怪"),

        ("god", "无敌 开/关"),

        ("endless", "无尽 开/关"),

        ("close", "关闭 F1"),

    ]



    _LEFT_W = 320

    _ROW1_OFF = 44

    _ROW1_H = 30

    _BODY_OFF = 82

    _INFO_BTN_W = 28

    _FOOTER_H = 40

    @property
    def PANEL(self) -> pygame.Rect:
        if config.PORTRAIT:
            return pygame.Rect(8, 36, config.WIDTH - 16, config.HEIGHT - 72)
        return pygame.Rect(config.WIDTH // 2 - 340, 36, 680, config.HEIGHT - 72)

    def panel(self) -> pygame.Rect:

        return self.PANEL



    def quick_buttons(self) -> list[tuple[str, pygame.Rect]]:

        out = []

        x0 = self.PANEL.x + 14

        y = self.PANEL.y + self._BODY_OFF

        for i, (aid, _) in enumerate(self.QUICK):

            col = i % 2

            row = i // 2

            r = pygame.Rect(x0 + col * 152, y + row * 34, 142, 30)

            out.append((aid, r))

        return out



    def buff_clip_rect(self) -> pygame.Rect:

        p = self.PANEL

        bx = p.x + self._LEFT_W + 8

        body_y = p.y + self._BODY_OFF
        return pygame.Rect(
            bx,
            body_y,
            p.width - self._LEFT_W - 14,
            p.bottom - self._FOOTER_H - 8 - body_y,
        )



    def buff_entries(self, game: GameSession) -> list[BuffListEntry]:
        return build_buff_list_entries(game.upgrades.pool)

    def _buff_entry_y(self, entries: list[BuffListEntry], index: int) -> int:
        return sum(entry_height(entries[i]) for i in range(index))

    def _buff_entry_rect(
        self, index: int, entries: list[BuffListEntry], clip: pygame.Rect, scroll: int
    ) -> pygame.Rect:
        h = entry_height(entries[index])
        y = clip.y - scroll + self._buff_entry_y(entries, index)
        return pygame.Rect(clip.x + 4, y, clip.width - 12, h - 2)



    def _buff_pick_rect(self, row: pygame.Rect) -> pygame.Rect:

        return pygame.Rect(row.x, row.y, row.width - self._INFO_BTN_W, row.height)



    def _buff_info_rect(self, row: pygame.Rect) -> pygame.Rect:

        return pygame.Rect(row.right - self._INFO_BTN_W + 2, row.y + 1, 24, row.height - 2)



    def buff_buttons(self, game: GameSession, scroll: int) -> list[tuple[str, pygame.Rect]]:

        out = []

        clip = self.buff_clip_rect()
        entries = self.buff_entries(game)

        for i, entry in enumerate(entries):
            if entry.kind != "card" or not entry.card:
                continue
            row = self._buff_entry_rect(i, entries, clip, scroll)
            if not row.colliderect(clip):
                continue
            out.append((entry.card["id"], self._buff_pick_rect(row)))

        return out



    def buff_info_buttons(self, game: GameSession, scroll: int) -> list[tuple[str, pygame.Rect]]:

        out = []

        clip = self.buff_clip_rect()
        entries = self.buff_entries(game)

        for i, entry in enumerate(entries):
            if entry.kind != "card" or not entry.card:
                continue
            row = self._buff_entry_rect(i, entries, clip, scroll)
            if not row.colliderect(clip):
                continue
            out.append((entry.card["id"], self._buff_info_rect(row)))

        return out



    def buff_content_height(self, game: GameSession) -> int:
        entries = self.buff_entries(game)
        if not entries:
            return 0
        return sum(entry_height(e) for e in entries) + 8



    def max_debug_scroll(self, game: GameSession) -> int:

        clip = self.buff_clip_rect()

        return max(0, self.buff_content_height(game) - clip.height)



    def buff_info_panel_rect(self) -> pygame.Rect:

        p = self.PANEL

        h = min(260, p.height - 80)

        return pygame.Rect(p.centerx - 150, p.centery - h // 2, 300, h)



    def buff_info_close_rect(self, panel: pygame.Rect) -> pygame.Rect:

        return pygame.Rect(panel.right - 28, panel.y + 6, 22, 22)



    def buff_info_content_rect(self, panel: pygame.Rect) -> pygame.Rect:

        return pygame.Rect(panel.x + 12, panel.y + 44, panel.width - 24, panel.height - 52)



    def buff_detail_lines(self, game: GameSession) -> list[str]:

        cid = game.debug_buff_info

        if not cid:

            return []

        card = find_upgrade(game.upgrades.pool, cid)

        if not card:

            return ["未找到该 Buff"]

        stacks = game.stats.upgrade_stacks.get(cid, 0)

        return upgrade_detail_lines(card, stacks, game.stats)



    def buff_info_scroll_max(self, game: GameSession, f_sm) -> int:

        return self._buff_info_metrics(game, f_sm)[1]



    def handle_buff_info_wheel(self, game: GameSession, f_sm, delta_y: int) -> bool:

        if not game.debug_buff_info:

            return False

        max_s = self.buff_info_scroll_max(game, f_sm)

        if max_s <= 0:

            game.ui_scroll_y = 0

            return False

        step = int(delta_y * 22)

        game.ui_scroll_y = clamp_scroll(game.ui_scroll_y - step, max_s)

        return True

    def _buff_info_metrics(self, game: GameSession, f_sm) -> tuple[pygame.Rect, int]:

        panel = self.buff_info_panel_rect()

        content = self.buff_info_content_rect(panel)

        inner = content.inflate(-4, -4)

        total = scroll_content_height(f_sm, self.buff_detail_lines(game), inner.width)

        max_s = max(0, total - inner.height)

        return content, max_s

    def try_begin_scroll_drag(self, game: GameSession, mx: int, my: int, f_sm) -> bool:

        if game.debug_buff_info:

            content, max_s = self._buff_info_metrics(game, f_sm)

            if max_s <= 0:

                game.ui_scroll_y = 0

                return False

            scroll_y = clamp_scroll(game.ui_scroll_y, max_s)

            game.ui_scroll_y = scroll_y

            hit = hit_scrollbar(
                mx, my, content, scroll_y, max_s,
                width=_DEBUG_SCROLL_WIDTH, gap=_DEBUG_SCROLL_GAP,
            )
            if hit:
                if hit == "track":
                    th = scroll_thumb_rect(
                        content, scroll_y, max_s,
                        width=_DEBUG_SCROLL_WIDTH, gap=_DEBUG_SCROLL_GAP,
                    )
                    scroll_y = scroll_y_from_thumb_top(
                        content, my - th.height // 2, max_s,
                        width=_DEBUG_SCROLL_WIDTH, gap=_DEBUG_SCROLL_GAP,
                    )
                    game.ui_scroll_y = clamp_scroll(scroll_y, max_s)
                thumb = scroll_thumb_rect(
                    content, game.ui_scroll_y, max_s,
                    width=_DEBUG_SCROLL_WIDTH, gap=_DEBUG_SCROLL_GAP,
                )
                game.scroll_drag = start_scroll_drag("debug_info", mx, my, thumb)
                return True
            if content.collidepoint(mx, my):
                panel = self.buff_info_panel_rect()
                if not self.buff_info_close_rect(panel).collidepoint(mx, my):
                    game.scroll_drag = start_content_scroll_drag("debug_info", my, scroll_y)
                    return True
            return False

        clip = self.buff_clip_rect()

        max_s = self.max_debug_scroll(game)

        if max_s <= 0:

            game.debug_scroll = 0

            return False

        scroll_y = clamp_scroll(game.debug_scroll, max_s)

        game.debug_scroll = scroll_y

        hit = hit_scrollbar(
            mx, my, clip, scroll_y, max_s,
            width=_DEBUG_SCROLL_WIDTH, gap=_DEBUG_SCROLL_GAP,
        )
        if hit:
            if hit == "track":
                th = scroll_thumb_rect(
                    clip, scroll_y, max_s,
                    width=_DEBUG_SCROLL_WIDTH, gap=_DEBUG_SCROLL_GAP,
                )
                scroll_y = scroll_y_from_thumb_top(
                    clip, my - th.height // 2, max_s,
                    width=_DEBUG_SCROLL_WIDTH, gap=_DEBUG_SCROLL_GAP,
                )
                game.debug_scroll = clamp_scroll(scroll_y, max_s)
            thumb = scroll_thumb_rect(
                clip, game.debug_scroll, max_s,
                width=_DEBUG_SCROLL_WIDTH, gap=_DEBUG_SCROLL_GAP,
            )
            game.scroll_drag = start_scroll_drag("debug_list", mx, my, thumb)
            return True
        if clip.collidepoint(mx, my) and not self._debug_click_blocks_scroll(
            game, mx, my
        ):
            game.scroll_drag = start_content_scroll_drag("debug_list", my, scroll_y)
            return True
        return False

    def _debug_click_blocks_scroll(self, game: GameSession, mx: int, my: int) -> bool:
        """可点击控件区域不启动拖滚动，避免与发放增益等操作冲突。"""
        if any(r.collidepoint(mx, my) for _, r in self.quick_buttons()):
            return True
        for _, r in self.buff_buttons(game, game.debug_scroll):
            if r.collidepoint(mx, my):
                return True
        for _, r in self.buff_info_buttons(game, game.debug_scroll):
            if r.collidepoint(mx, my):
                return True
        return False

    def update_scroll_drag(self, game: GameSession, my: int, f_sm) -> bool:

        if not game.scroll_drag:

            return False

        if game.scroll_drag.kind == "debug_list":

            clip = self.buff_clip_rect()

            max_s = self.max_debug_scroll(game)

            if max_s <= 0:

                game.scroll_drag = None

                return False

            if game.scroll_drag.drag_mode == "content":
                game.debug_scroll = drag_content_scroll_y(my, game.scroll_drag, max_s)
            else:
                game.debug_scroll = drag_scroll_y(
                    my, game.scroll_drag, clip, max_s,
                    width=_DEBUG_SCROLL_WIDTH, gap=_DEBUG_SCROLL_GAP,
                )

            return True

        if game.scroll_drag.kind == "debug_info" and game.debug_buff_info:

            content, max_s = self._buff_info_metrics(game, f_sm)

            if max_s <= 0:

                game.scroll_drag = None

                game.ui_scroll_y = 0

                return False

            if game.scroll_drag.drag_mode == "content":
                game.ui_scroll_y = drag_content_scroll_y(my, game.scroll_drag, max_s)
            else:
                game.ui_scroll_y = drag_scroll_y(
                    my, game.scroll_drag, content, max_s,
                    width=_DEBUG_SCROLL_WIDTH, gap=_DEBUG_SCROLL_GAP,
                )

            return True

        return False



    def hit(self, mx: int, my: int, game: GameSession) -> tuple[str, str] | None:

        if game.debug_buff_info:

            panel = self.buff_info_panel_rect()

            close_r = self.buff_info_close_rect(panel)

            if close_r.collidepoint(mx, my):

                return ("close_buff_info", "")

            if panel.collidepoint(mx, my):

                return None

            return ("close_buff_info", "")



        if not self.PANEL.collidepoint(mx, my):

            return ("close", "")



        for cid, r in self.buff_info_buttons(game, game.debug_scroll):

            if r.collidepoint(mx, my):

                return ("buff_info", cid)



        for cid, r in self.buff_buttons(game, game.debug_scroll):

            if r.collidepoint(mx, my):

                return ("buff", cid)



        for aid, r in self.quick_buttons():

            if r.collidepoint(mx, my):

                return (aid, "")



        return None



    def _draw_buff_info_popup(self, surf: pygame.Surface, game: GameSession, fonts) -> None:

        f_sm, f_md, _f_lg = fonts

        cid = game.debug_buff_info

        if not cid:

            return

        card = find_upgrade(game.upgrades.pool, cid)

        if not card:

            return



        panel = self.buff_info_panel_rect()

        dim = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)

        dim.fill((0, 0, 0, 100))

        surf.blit(dim, (0, 0))



        tag_colors = {

            "base": (80, 200, 140),

            "tower": (90, 160, 220),

            "global": (200, 180, 80),

            "curse": (200, 80, 120),

        }

        border = tag_colors.get(card.get("tag", ""), (140, 90, 160))

        pygame.draw.rect(surf, (28, 26, 38), panel, border_radius=8)

        pygame.draw.rect(surf, border, panel, 2, border_radius=8)



        title_r = pygame.Rect(panel.x + 12, panel.y + 8, panel.width - 48, 32)

        blit_in_rect(surf, f_md, card["name"], title_r, (240, 240, 250), align="left", pad=2)



        close_r = self.buff_info_close_rect(panel)

        pygame.draw.rect(surf, (60, 65, 80), close_r, border_radius=4)

        blit_in_rect(surf, f_sm, "×", close_r, (240, 240, 250), pad=0)



        content = self.buff_info_content_rect(panel)

        lines = self.buff_detail_lines(game)

        _total, max_s = self._buff_info_metrics(game, f_sm)

        scroll_y = clamp_scroll(game.ui_scroll_y, max_s)

        game.ui_scroll_y = scroll_y

        blit_scroll_text(surf, f_sm, lines, content, scroll_y, (200, 205, 220))

        draw_scrollbar(
            surf, content, scroll_y, max_s,
            width=_DEBUG_SCROLL_WIDTH, gap=_DEBUG_SCROLL_GAP,
        )



    def draw(self, surf: pygame.Surface, game: GameSession, fonts) -> None:

        f_sm, f_md, f_lg = fonts

        overlay = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)

        overlay.fill((0, 0, 0, 160))

        surf.blit(overlay, (0, 0))

        p = self.PANEL

        pygame.draw.rect(surf, (32, 28, 42), p, border_radius=10)

        pygame.draw.rect(surf, (140, 90, 160), p, 2, border_radius=10)



        title_r = pygame.Rect(p.x + 14, p.y + 10, 260, 30)

        blit_in_rect(surf, f_lg, "调试菜单 (F1)", title_r, (255, 200, 255), align="left", pad=2)

        sub_r = pygame.Rect(p.x + 280, p.y + 16, p.width - 300, 22)

        endless_on = "开" if game.endless_mode else "关"
        blit_in_rect(
            surf,
            f_sm,
            f"无尽模式 {endless_on} · 自动存档",
            sub_r,
            (180, 170, 200),
            align="left",
            pad=2,
        )



        row1_y = p.y + self._ROW1_OFF
        hdr_l = pygame.Rect(p.x + 14, row1_y, 100, self._ROW1_H)
        blit_in_rect(surf, f_md, "快捷", hdr_l, (220, 210, 240), align="left", pad=2)

        bx = p.x + self._LEFT_W + 8
        buff_w = p.width - self._LEFT_W - 16
        title_r = pygame.Rect(bx, row1_y, buff_w - 40, self._ROW1_H)
        blit_in_rect(surf, f_md, "获得 Buff", title_r, (220, 210, 240), align="left", pad=2)
        draw_info_icon(surf, bx + buff_w - 22, row1_y + self._ROW1_H // 2, f_sm, 8)

        body_y = p.y + self._BODY_OFF
        pygame.draw.line(
            surf, (80, 70, 100), (bx - 4, body_y - 4), (bx - 4, p.bottom - self._FOOTER_H)
        )



        for aid, r in self.quick_buttons():

            col = (70, 55, 90) if aid != "close" else (90, 60, 60)

            if aid == "god" and game.debug_god_mode:

                col = (120, 90, 50)

            pygame.draw.rect(surf, col, r, border_radius=4)

            label = next(l for a, l in self.QUICK if a == aid)

            if aid == "god" and game.debug_god_mode:

                label = "无敌 ON"

            blit_in_rect(surf, f_sm, label, r, (240, 240, 250), pad=4)



        clip = self.buff_clip_rect()

        max_scroll = max(0, self.buff_content_height(game) - clip.height)

        game.debug_scroll = max(0, min(max_scroll, game.debug_scroll))

        old_clip = surf.get_clip()

        surf.set_clip(clip)
        pygame.draw.rect(surf, (28, 26, 38), clip)

        entries = self.buff_entries(game)
        for i, entry in enumerate(entries):
            row = self._buff_entry_rect(i, entries, clip, game.debug_scroll)
            if not row.colliderect(clip):
                continue
            if entry.kind == "header":
                hdr = pygame.Rect(row.x + 2, row.y + 4, row.width - 4, row.height - 12)
                blit_in_rect(
                    surf, f_sm, f"【{entry.text}】", hdr, (255, 200, 130), align="left", pad=2
                )
                sep_y = row.bottom - 2
                pygame.draw.line(
                    surf, (70, 62, 85), (hdr.x, sep_y), (hdr.right, sep_y)
                )
                continue
            card = entry.card
            if not card:
                continue
            pick_r = self._buff_pick_rect(row)
            info_r = self._buff_info_rect(row)
            pygame.draw.rect(surf, (48, 42, 58), pick_r, border_radius=4)
            pygame.draw.rect(surf, (72, 65, 88), pick_r, 1, border_radius=4)
            stacks = game.stats.upgrade_stacks.get(card["id"], 0)
            label = card["name"] + (f" x{stacks}" if stacks else "")
            blit_in_rect(surf, f_sm, label, pick_r, (210, 215, 230), align="left", pad=6)
            active = game.debug_buff_info == card["id"]
            if active:
                pygame.draw.rect(surf, (90, 110, 150), info_r, border_radius=4)
            draw_info_icon(surf, info_r.centerx, info_r.centery, f_sm, 8)

        surf.set_clip(old_clip)



        draw_scrollbar(
            surf, clip, game.debug_scroll, max_scroll,
            width=_DEBUG_SCROLL_WIDTH, gap=_DEBUG_SCROLL_GAP,
        )

        foot_y = p.bottom - self._FOOTER_H
        foot_r = pygame.Rect(p.x + 12, foot_y + 2, p.width - 24, self._FOOTER_H - 6)
        god = "开" if game.debug_god_mode else "关"
        endl = "开" if game.endless_mode else "关"
        info = (
            f"金{game.gold}  Lv{game.level}  敌{len(game.enemies)}  卫{len(game.guards)}  "
            f"无尽:{endl} 轮{game.waves.endless_cycle}  无敌:{god}"
        )
        blit_in_rect(surf, f_sm, info, foot_r, (160, 155, 180), align="left", pad=2)



        if game.debug_buff_info:

            self._draw_buff_info_popup(surf, game, fonts)


