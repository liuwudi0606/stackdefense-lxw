# /// script
# dependencies = ["pygame-ce", "pillow"]
# ///
"""Stack Defense - main entry (pygbag / desktop)."""

from __future__ import annotations

import asyncio
import os
import sys
from enum import Enum, auto

if sys.platform in ("emscripten", "wasi"):
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from game.platform_util import ensure_pygame_init, is_web, web_disable_chromakey

if sys.platform not in ("emscripten", "wasi"):
    import pygame

    import config
    from game.assets import SpriteBank
    from game.audio import AudioManager
    from game.buffs import meta_buff_labels
    from game.meta import MetaProgress
    from game.save_run import (
        delete_run_save,
        has_run_save,
        load_saved_session,
        save_run,
    )
    from game.session import GameSession, GameState
    from game.display import DisplayManager
    from game.ui import UI
    from game.ui_debug import DebugUI


def _import_game_stack() -> None:
    """网页版须在 shell.source 装好 wasm pygame-ce 后再 import 会用到 pygame 的子模块。"""
    global config, SpriteBank, AudioManager, meta_buff_labels, MetaProgress
    global delete_run_save, has_run_save, load_saved_session, save_run
    global GameSession, GameState, DisplayManager, UI, DebugUI

    import config
    from game.assets import SpriteBank
    from game.audio import AudioManager
    from game.buffs import meta_buff_labels
    from game.meta import MetaProgress
    from game.save_run import (
        delete_run_save,
        has_run_save,
        load_saved_session,
        save_run,
    )
    from game.session import GameSession, GameState
    from game.display import DisplayManager
    from game.ui import UI
    from game.ui_debug import DebugUI


class AppState(Enum):
    MENU = auto()
    PLAYING = auto()
    SHOP = auto()


def new_game(
    meta: MetaProgress,
    audio: AudioManager,
    *,
    endless: bool | None = None,
    open_debug: bool = False,
) -> GameSession:
    effects = meta.aggregated_effects()
    g = GameSession(
        tower_defs=config.load_json("towers.json"),
        enemy_defs=config.load_json("enemies.json"),
        wave_data=config.load_json("waves.json"),
        upgrade_pool=config.load_json("upgrades.json"),
        meta_effects=effects,
        on_sound=audio.play,
    )
    g.meta_buff_lines = meta_buff_labels(meta.data, meta.purchased)
    if endless is not None:
        g.set_endless_mode(endless)
    if open_debug:
        g.debug_menu_open = True
    return g


def try_load_save(meta: MetaProgress, audio: AudioManager) -> GameSession | None:
    effects = meta.aggregated_effects()
    g = load_saved_session(
        config.load_json("towers.json"),
        config.load_json("enemies.json"),
        config.load_json("waves.json"),
        config.load_json("upgrades.json"),
        meta_effects=effects,
        on_sound=audio.play,
    )
    if g and not g.meta_buff_lines:
        g.meta_buff_lines = meta_buff_labels(meta.data, meta.purchased)
    return g


def _event_pos(display: DisplayManager, pos: tuple[int, int]) -> tuple[int, int] | None:
    return display.to_game(pos[0], pos[1])


async def main() -> None:
    await _main_async()


async def _main_async() -> None:
    if is_web():
        web_disable_chromakey()
        for _ in range(120):
            try:
                ensure_pygame_init()
                import pygame

                if callable(getattr(pygame, "init", None)):
                    break
            except ModuleNotFoundError:
                from game.platform_util import purge_pygame_modules

                purge_pygame_modules()
            await asyncio.sleep(0.05)
        else:
            raise RuntimeError("pygame-ce 未就绪：请刷新页面或重新部署网页版")
        _import_game_stack()
    else:
        ensure_pygame_init()
        import pygame

    display = DisplayManager()
    pygame.display.set_caption("叠层防线")
    clock = pygame.time.Clock()

    sprites = SpriteBank()
    sprites.load_all()
    audio = AudioManager()
    audio.init()
    meta = MetaProgress(config.load_json("meta.json"))
    ui = UI(sprites)
    debug_ui = DebugUI()

    app_state = AppState.MENU
    game: GameSession | None = None
    end_handled = False
    save_timer = 0.0

    if has_run_save():
        loaded = try_load_save(meta, audio)
        if loaded:
            game = loaded
            app_state = AppState.PLAYING

    running = True
    if app_state == AppState.MENU:
        ui.draw_menu(display.surface, meta, has_run_save())
        display.present()
        await asyncio.sleep(0)

    while running:
        if is_web():
            dt = 1.0 / config.FPS
        else:
            dt = clock.tick(config.FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                if game and app_state == AppState.PLAYING:
                    save_run(game)
                if not is_web():
                    display.save_settings()
                    pygame.quit()
                    sys.exit()
                running = False
                break

            if event.type == pygame.VIDEORESIZE and not is_web():
                display.on_resize(event.w, event.h)
                continue
            win_resize = getattr(pygame, "WINDOWSIZECHANGED", None)
            if (
                not is_web()
                and win_resize is not None
                and event.type == win_resize
            ):
                display.on_resize(event.x, event.y)
                continue

            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11 and not is_web():
                display.toggle_fullscreen()
                continue

            if event.type == pygame.KEYDOWN and event.key == pygame.K_F1:
                if app_state == AppState.MENU:
                    from game.debug import debug_skip_to_endless

                    delete_run_save()
                    game = new_game(meta, audio, endless=True)
                    debug_skip_to_endless(game)
                    save_run(game)
                    end_handled = False
                    app_state = AppState.PLAYING
                    continue
                if app_state == AppState.PLAYING and game:
                    game.debug_menu_open = not game.debug_menu_open
                    if game.debug_menu_open:
                        game.buff_panel_open = False
                    else:
                        game.debug_buff_info = None
                    continue

            if event.type == pygame.KEYDOWN and event.key == pygame.K_b:
                if app_state == AppState.PLAYING and game and not game.debug_menu_open:
                    game.buff_panel_open = not game.buff_panel_open
                    if game.buff_panel_open:
                        game.ui_scroll_y = 0
                    continue

            if event.type == pygame.MOUSEWHEEL and app_state == AppState.SHOP:
                ui.meta_shop_scroll_wheel(event.y, meta)
                continue

            if event.type == pygame.MOUSEWHEEL and game and app_state == AppState.PLAYING:
                if game.debug_menu_open:
                    if game.debug_buff_info:
                        if debug_ui.handle_buff_info_wheel(game, ui.f_sm, event.y):
                            continue
                    else:
                        max_ds = debug_ui.max_debug_scroll(game)
                        if max_ds > 0:
                            game.debug_scroll = max(
                                0,
                                min(max_ds, game.debug_scroll - event.y * 28),
                            )
                            continue
                if (
                    game.state == GameState.PLAYING
                    and not game.debug_menu_open
                    and not game.buff_panel_open
                ):
                    gpos = display.game_mouse_pos()
                    if gpos and gpos[1] < ui.build_bar_y() - 6:
                        from game.camera import apply_wheel_zoom

                        apply_wheel_zoom(event.y, gpos[0], gpos[1])
                        continue
                if ui.handle_scroll_wheel(game, event.y):
                    continue

            if event.type == pygame.MOUSEMOTION and game and app_state == AppState.PLAYING:
                if pygame.mouse.get_pressed()[0]:
                    gpos = _event_pos(display, event.pos)
                    if gpos is None:
                        continue
                    if game.scroll_drag:
                        if game.scroll_drag.kind.startswith("debug"):
                            if debug_ui.update_scroll_drag(game, gpos[1], ui.f_sm):
                                continue
                        elif ui.update_scroll_drag(game, gpos[0], gpos[1]):
                            continue

            if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and game:
                ui.end_scroll_drag(game)
                if app_state == AppState.PLAYING and game.build_drag:
                    gpos = _event_pos(display, event.pos)
                    if gpos and game.state == GameState.PLAYING:
                        mx, my = gpos
                        if game.click_on_stack_build_area(mx, my):
                            game.try_build_stack(game.build_drag)
                    game.build_drag = None

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if app_state == AppState.PLAYING and game:
                    if game.debug_menu_open:
                        if game.debug_buff_info:
                            game.debug_buff_info = None
                        else:
                            game.debug_menu_open = False
                        continue
                    if game.buff_panel_open:
                        game.buff_panel_open = False
                        game.ui_scroll_y = 0
                        ui.end_scroll_drag(game)
                        continue
                    if game.build_info_tower:
                        game.build_info_tower = None
                        continue
                    if game.state in (
                        GameState.TOWER_MENU,
                        GameState.TOWER_SWAP,
                        GameState.ENEMY_MENU,
                        GameState.BASE_MENU,
                    ):
                        game.close_unit_ui()
                        continue
                    if game.state == GameState.PLAYING:
                        save_run(game)
                        display.save_settings()
                        app_state = AppState.MENU
                        game = None
                        continue
                if app_state == AppState.SHOP:
                    app_state = AppState.MENU
                    continue

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                gpos = _event_pos(display, event.pos)
                if gpos is None:
                    continue
                mx, my = gpos
                audio.play("click")

                if app_state == AppState.MENU:
                    hit = ui.menu_hit(mx, my, has_run_save())
                    if hit == "continue":
                        game = try_load_save(meta, audio)
                        if game:
                            end_handled = False
                            app_state = AppState.PLAYING
                    elif hit == "start":
                        delete_run_save()
                        game = new_game(meta, audio)
                        save_run(game)
                        end_handled = False
                        app_state = AppState.PLAYING
                    elif hit == "shop":
                        ui.meta_shop_scroll = 0
                        app_state = AppState.SHOP
                    continue

                if app_state == AppState.SHOP:
                    uid = ui.meta_shop_hit(mx, my, meta)
                    if uid and meta.buy(uid):
                        audio.play("upgrade")
                    else:
                        view = pygame.Rect(
                            36, ui.META_SHOP_TOP, config.WIDTH - 72, ui.META_SHOP_VIEW_H
                        )
                        if not view.collidepoint(mx, my):
                            app_state = AppState.MENU
                    continue

                if app_state != AppState.PLAYING or game is None:
                    continue

                if game.state == GameState.ENDLESS_OFFER:
                    choice = ui.endless_offer_hit(mx, my)
                    if choice == "yes":
                        game.accept_endless_continue()
                        save_run(game)
                    elif choice == "no":
                        game.finish_campaign_victory()
                    continue

                if game.debug_menu_open:
                    hit = debug_ui.hit(mx, my, game)
                    if hit:
                        game.run_debug_action(hit[0], hit[1])
                        continue
                    if debug_ui.try_begin_scroll_drag(game, mx, my, ui.f_sm):
                        continue

                if game.buff_panel_open:
                    if ui.try_begin_scroll_drag(game, mx, my):
                        continue
                    if ui.buff_panel_hit(mx, my, game):
                        game.buff_panel_open = False
                    continue

                if ui.try_begin_scroll_drag(game, mx, my):
                    continue

                if game.state in (GameState.WON, GameState.LOST):
                    delete_run_save()
                    app_state = AppState.MENU
                    game = None
                    continue

                if game.state == GameState.UPGRADE_PICK:
                    idx = ui.upgrade_card_hit(mx, my, game)
                    if idx is not None:
                        game.pick_upgrade(idx)
                    continue

                if game.state == GameState.ENEMY_MENU:
                    action = ui.enemy_menu_hit(mx, my, game)
                    if action == "close":
                        game.close_enemy_ui()
                    continue

                if game.state == GameState.BASE_MENU:
                    if ui.base_menu_hit(mx, my, game) == "close":
                        game.close_base_ui()
                    continue

                if game.state == GameState.TOWER_MENU:
                    action = ui.tower_menu_hit(mx, my, game)
                    if action == "sell" and game.selected_tower_index is not None:
                        game.sell_tower(game.selected_tower_index)
                    elif action == "upgrade" and game.selected_tower_index is not None:
                        game.upgrade_tower(game.selected_tower_index)
                    elif action == "swap" and game.selected_tower_index is not None:
                        game.start_swap_tower(game.selected_tower_index)
                    elif action == "laser_smart" and game.selected_tower_index is not None:
                        game.toggle_laser_auto(game.selected_tower_index)
                    elif action == "laser_mode" and game.selected_tower_index is not None:
                        game.cycle_laser_mode(game.selected_tower_index)
                    elif action == "close":
                        game.close_tower_ui()
                    continue

                if game.state == GameState.TOWER_SWAP:
                    ui.tower_menu_hit(mx, my, game)
                    continue

                if game.state == GameState.PLAYING:
                    if ui.buff_panel_btn_rect().collidepoint(
                        mx, my
                    ):
                        game.buff_panel_open = not game.buff_panel_open
                        if game.buff_panel_open:
                            game.ui_scroll_y = 0
                        continue
                    act, tid = ui.build_bar_hit(mx, my, game)
                    if act == "close_info":
                        game.build_info_tower = None
                        continue
                    if act == "info" and tid:
                        if game.build_info_tower == tid:
                            game.build_info_tower = None
                        else:
                            game.build_info_tower = tid
                            game.ui_scroll_y = 0
                        continue
                    if act == "select" and tid:
                        if game.tower_count() >= game.max_tower_floors_limit():
                            game.selected_build = None
                            game.build_drag = None
                            continue
                        clicks = getattr(event, "clicks", 1)
                        if clicks >= 2:
                            game.selected_build = tid
                            game.try_build_stack(tid)
                            game.build_drag = None
                            game.build_info_tower = None
                            continue
                        if game.selected_build == tid:
                            game.selected_build = None
                            game.build_drag = None
                        else:
                            game.selected_build = tid
                            game.build_drag = tid
                        game.build_info_tower = None
                        continue
                    if game.build_info_tower:
                        continue
                    if game.state != GameState.PLAYING:
                        continue
                    if game.selected_build and game.click_on_stack_build_area(mx, my):
                        game.try_build_stack(game.selected_build)
                        continue
                    ti = game.tower_index_at(mx, my)
                    if ti is not None:
                        game.open_tower_menu(ti)
                        continue
                    ei = game.enemy_index_at(mx, my)
                    if ei is not None:
                        game.open_enemy_menu(ei)
                        continue
                    if game.click_on_foundation(mx, my):
                        game.open_base_menu()
                        continue

        if not running:
            break

        if app_state == AppState.PLAYING and game:
            if game.state == GameState.PLAYING:
                game.update(dt)

        if app_state == AppState.PLAYING and game and not end_handled:
            if game.state == GameState.ENDLESS_OFFER:
                if not game.clear_reward_applied:
                    game.win_token_gain = meta.on_win(game.level)
                    game.clear_reward_applied = True
                    audio.play("win")
            elif game.state == GameState.WON:
                delete_run_save()
                end_handled = True
            elif game.state == GameState.LOST:
                delete_run_save()
                audio.play("lose")
                end_handled = True

        if app_state == AppState.PLAYING and game:
            save_timer += dt
            if save_timer >= config.AUTO_SAVE_INTERVAL:
                save_run(game)
                save_timer = 0.0

        surf = display.surface
        if app_state == AppState.MENU:
            ui.draw_menu(surf, meta, has_run_save())
        elif app_state == AppState.SHOP:
            ui.draw_menu(surf, meta, has_run_save())
            ui.draw_meta_shop(surf, meta)
        elif game:
            ui.draw_world(surf, game)
            ui.draw_hud(surf, game)
            if game.state in (GameState.PLAYING, GameState.UPGRADE_PICK):
                ui.draw_build_bar(surf, game)
            if game.state == GameState.UPGRADE_PICK:
                ui.draw_upgrade_overlay(surf, game)
            if game.state in (GameState.TOWER_MENU, GameState.TOWER_SWAP):
                ui.draw_tower_menu(surf, game)
            if game.state == GameState.ENEMY_MENU:
                ui.draw_enemy_menu(surf, game)
            if game.state == GameState.BASE_MENU:
                ui.draw_base_menu(surf, game)
            if game.state == GameState.ENDLESS_OFFER:
                ui.draw_endless_offer(surf, game, game.win_token_gain)
            if game.state == GameState.WON:
                ui.draw_end_screen(surf, game, True, game.win_token_gain)
            if game.state == GameState.LOST:
                ui.draw_end_screen(surf, game, False)
            if game.state == GameState.PLAYING:
                gmp = display.game_mouse_pos()
                if gmp:
                    if game.build_drag:
                        ui.draw_build_drag(surf, game, gmp[0], gmp[1])
                    elif game.selected_build:
                        ui.draw_stack_highlight(surf, game, gmp[0], gmp[1])
            if game.buff_panel_open:
                ui.draw_buff_panel(surf, game)
            if game.debug_menu_open:
                debug_ui.draw(surf, game, (ui.f_sm, ui.f_md, ui.f_lg))

        display.present()
        await asyncio.sleep(0)

    pygame.quit()


asyncio.run(main())
