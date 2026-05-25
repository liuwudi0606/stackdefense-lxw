"""修补 build/web/index.html：加载 UI、本地 CDN、英文包名。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "build" / "web"
INDEX = WEB / "index.html"
ARCHIVE_OLD = "独立游戏"
ARCHIVE_NEW = "stackdefense"
CDN_REMOTE = "https://pygame-web.github.io/cdn/0.9.3/"
CDN_LOCAL = "./cdn/0.9.3/"

REPLACEMENTS: list[tuple[str, str]] = [
    (
        "    # patched: keep transfer visible during load\n"
        '    platform.window.canvas.style.visibility = "hidden"\n\n',
        "",
    ),
    (
        "    await shell.source(main, callback=ui_callback)\n\n"
        "    # if you don't reach that step\n"
        "    # your main.py has an infinite sync loop somewhere !\n\n",
        "    await shell.runpy(main, callback=ui_callback)\n"
        "    inst = aio.toplevel.handler.instance\n"
        '    src = "\\n".join(inst.buffer)\n'
        "    inst.buffer.clear()\n"
        '    inst.runsource(src, str(main), symbol="exec")\n\n',
    ),
    (
        '    platform.window.infobox.style.display = "none"\n'
        "    platform.window.config.gui_divider = 1\n"
        "    platform.window.window_resize()",
        "    platform.window.transfer.hidden = True\n"
        '    platform.window.infobox.style.display = "none"\n'
        '    platform.window.canvas.style.visibility = "visible"\n'
        "    platform.window.config.gui_divider = 1\n"
        "    platform.window.window_resize()",
    ),
    (
        "        transfer.hidden = debug_hidden\n"
        "        info.hidden = debug_hidden\n"
        "        box.hidden =  debug_hidden\n\n"
        "        show_infobox()",
        "        info.hidden = debug_hidden\n"
        "        box.hidden = debug_hidden\n"
        "        transfer.hidden = false\n"
        '        const status = document.getElementById("status")\n'
        '        const progress = document.getElementById("progress")\n'
        "        if (status) {\n"
        "            status.hidden = false\n"
        '            status.textContent = "正在加载 Python 运行时（约 20MB）…"\n'
        "        }\n"
        "        if (progress) {\n"
        "            progress.hidden = false\n"
        "            progress.value = 0\n"
        "            progress.max = 200\n"
        "        }\n"
        '        const infobox = document.getElementById("infobox")\n'
        '        if (infobox) infobox.innerText = "《叠层防线》加载中，请稍候…"\n'
        "        show_infobox()",
    ),
    (
        "    ume_block : 1,",
        "    ume_block : 0,",
    ),
    (
        "    gui_divider : 2,\n"
        "    ume_block : 0,\n"
        "    can_close : 0,\n"
        "    archive : \"stackdefense\",\n"
        "    gui_debug : 2,",
        "    gui_divider : 1,\n"
        "    ume_block : 0,\n"
        "    can_close : 0,\n"
        "    archive : \"stackdefense\",\n"
        "    gui_debug : 1,",
    ),
    (
        "    function debug() {\n"
        "        // allow to gain access to dev tools from js console\n"
        "        // but only on desktop. difficult to reach when in iframe\n"
        "        python.config.debug = true\n"
        "        custom_onload(false)\n"
        "        Module.PyRun_SimpleString(\"shell.uptime()\")\n"
        "        window_resize()\n"
        "    }",
        "    function debug() {\n"
        "        python.config.debug = true\n"
        "        python.config.gui_debug = 1\n"
        "        python.config.gui_divider = 1\n"
        "        custom_onload(false)\n"
        "        Module.PyRun_SimpleString(\"shell.uptime()\")\n"
        "        window_resize(1)\n"
        "    }",
    ),
]

# 将旧版 custom_site 启动块迁移到当前 run_main + shell.source 流程
LEGACY_CUSTOM_SITE: list[tuple[str, str]] = [
    (
        'async with platform.fopen(f"{bundle}.tar.gz", "rb") as archive:',
        'async with platform.fopen(f"{bundle}.tar.gz?b={BUILD_STAMP}", "rb") as archive:',
    ),
    (
        'async with platform.fopen(f"{bundle}.apk", "rb") as archive:',
        'async with platform.fopen(f"{bundle}.apk?b={BUILD_STAMP}", "rb") as archive:',
    ),
    (
        "        show_infobox()\n"
        '        const infobox = document.getElementById("infobox")\n'
        '        if (infobox) infobox.innerText = "《叠层防线》加载中，请稍候…"',
        '        const infobox = document.getElementById("infobox")\n'
        '        if (infobox) infobox.innerText = "《叠层防线》加载中，请稍候…"\n'
        "        show_infobox()",
    ),
    (
        "function show_infobox() {\n"
        "    infobox.style.display = \"block\";\n\n"
        "    // Measure box\n"
        "    const w = infobox.offsetWidth;\n"
        "    const h = infobox.offsetHeight;\n\n"
        "    // Center in viewport\n"
        "    const left = (window.innerWidth - w) / 2;\n"
        "    const top = (window.innerHeight - h) / 2;\n\n"
        "    infobox.style.left = left + \"px\";\n"
        "    infobox.style.top = top + \"px\";\n"
        "}",
        "function show_infobox() {\n"
        "    infobox.style.display = \"block\";\n"
        '    infobox.style.left = "50%";\n'
        '    infobox.style.top = "58%";\n'
        '    infobox.style.transform = "translate(-50%, -50%)";\n'
        "}",
    ),
    (
        "        #infobox {\n"
        "            position: fixed;\n"
        "            background: rgba(20, 24, 40, 0.92);\n"
        "            color: #f0f0f8;\n"
        "            font-weight: bold;\n"
        "            padding: 12px 24px;\n"
        "            border-radius: 8px;\n"
        "            border: 1px solid rgba(255,255,255,0.15);\n"
        "            z-index: 999999;\n"
        "        }",
        "        #infobox {\n"
        "            position: fixed;\n"
        "            left: 50%;\n"
        "            top: 58%;\n"
        "            transform: translate(-50%, -50%);\n"
        "            background: rgba(20, 24, 40, 0.92);\n"
        "            color: #f0f0f8;\n"
        "            font-weight: bold;\n"
        "            padding: 12px 24px;\n"
        "            border-radius: 8px;\n"
        "            border: 1px solid rgba(255,255,255,0.15);\n"
        "            z-index: 999999;\n"
        "            text-align: center;\n"
        "            white-space: nowrap;\n"
        "            max-width: 92vw;\n"
        "            box-sizing: border-box;\n"
        "        }",
    ),
    (
        '        log("[stackdefense] TopLevel + pip")\n'
        "        await TopLevel_async_handler.start_toplevel(platform.shell, console=False)\n"
        "        import aio.pep0723\n"
        '        await aio.pep0723.pip_install("pygame-ce")\n'
        '        await aio.pep0723.pip_install("pillow")\n\n'
        '        log("[stackdefense] waiting preload")\n'
        "        wait = 0\n"
        "        while embed.counter() < 0:\n"
        "            await asyncio.sleep(0.1)\n"
        "            wait += 1\n"
        "            if wait > 600:\n"
        '                log("[stackdefense] preload timeout, force continue")\n'
        "                break\n"
        "        embed.run()\n\n"
        "        platform.window.transfer.hidden = True\n"
        '        platform.window.infobox.style.display = "none"\n'
        '        platform.window.canvas.style.visibility = "visible"\n'
        "        platform.window.config.gui_divider = 1\n"
        "        platform.window.config.gui_debug = 1\n"
        "        platform.window.window_resize()\n\n"
        '        log("[stackdefense] run_main(main.py)")\n'
        '        platform.run_main(PyConfig, loaderhome=assets, loadermain="main.py")\n'
        '        log("[stackdefense] awaiting game loop")\n'
        "        await asyncio.sleep(0)\n"
        "        await asyncio.sleep(0)\n"
        "        if platform.window.location.hash.find(\"#debug\") >= 0:\n"
        "            shell.interactive()\n"
        "        while True:\n"
        "            await asyncio.sleep(3600)",
        '        await TopLevel_async_handler.start_toplevel(platform.shell, console=False)\n\n'
        "        platform.run_main(PyConfig, loaderhome=assets, loadermain=None)\n\n"
        "        wait = 0\n"
        "        while embed.counter() < 0:\n"
        "            await asyncio.sleep(0.1)\n"
        "            wait += 1\n"
        "            if wait > 600:\n"
        "                break\n\n"
        "        if not platform.window.MM.UME:\n"
        '            platform.window.infobox.innerText = "点击页面开始游戏"\n'
        "            while not platform.window.MM.UME:\n"
        "                await asyncio.sleep(0.1)\n\n"
        "        platform.window.canvas.style.visibility = \"visible\"\n"
        "        platform.window.config.gui_divider = 1\n"
        "        platform.window.config.gui_debug = 1\n\n"
        "        def ui_callback(pkg):\n"
        '            platform.window.infobox.innerText = f"正在加载 {pkg}…"\n\n'
        "        await shell.source(main, callback=ui_callback)\n\n"
        "        platform.window.transfer.hidden = True\n"
        '        platform.window.infobox.style.display = "none"\n'
        "        platform.window.window_resize()\n"
        "        if platform.window.location.hash.find(\"#debug\") >= 0:\n"
        "            shell.interactive()\n"
        "        while True:\n"
        "            await asyncio.sleep(3600)",
    ),
]

LOADER_WATCHDOG = """
    window.addEventListener("load", () => {
        const site = document.getElementById("site");
        const status = document.getElementById("status");
        if (site && status) {
            site.addEventListener("error", () => {
                status.textContent = "无法加载运行时：请运行 python tools/vendor_web_cdn.py";
            });
        }
        setTimeout(() => {
            const p = document.getElementById("progress");
            if (!p || p.value > 0) return;
            if (status) status.textContent = "仍在下载/编译 WASM，请耐心等待…";
        }, 12000);
    });
"""


def _detect_bundle_name() -> str:
    preferred = WEB / f"{ARCHIVE_NEW}.tar.gz"
    if preferred.is_file():
        return ARCHIVE_NEW
    archives = sorted(WEB.glob("*.tar.gz"))
    if archives:
        return archives[0].name.removesuffix(".tar.gz")
    return ARCHIVE_NEW


def _build_stamp() -> str:
    for name in (_detect_bundle_name() + ".tar.gz",):
        tar = WEB / name
        if tar.is_file():
            st = tar.stat()
            return f"{int(st.st_mtime)}-{st.st_size}"
    return "0"


def _sync_archive_references(text: str, bundle: str) -> tuple[str, int]:
    """只改明确的 bundle / archive 字段，避免把 stackdefense 嵌进 stackdefense-lxw。"""
    n = 0
    suffix = bundle.rsplit("-", 1)[-1]
    doubled = f"{bundle}-{suffix}"
    if doubled in text:
        text = text.replace(doubled, bundle)
        n += 1
    text, c = re.subn(r'bundle = "[^"]+"', f'bundle = "{bundle}"', text, count=1)
    n += c
    text, c = re.subn(r'archive\s*:\s*"[^"]+"', f'archive : "{bundle}"', text, count=1)
    n += c
    text, c = re.subn(
        r'Loading [^\n]+ from [^\n]+\.apk',
        f'Loading {bundle} from {bundle}.apk',
        text,
        count=1,
    )
    n += c
    text, c = re.subn(r'Folder\s+:\s*[^\n]+', f'Folder  : {bundle}', text, count=1)
    n += c
    text, c = re.subn(r'Title\s+:\s*[^\n]+', f'Title   : {bundle}', text, count=1)
    n += c
    if ARCHIVE_OLD in text:
        text = text.replace(ARCHIVE_OLD, bundle)
        n += 1
    return text, n


def _inject_build_stamp(text: str) -> tuple[str, int]:
    stamp = _build_stamp()
    n = 0
    if "__BUILD_STAMP__" in text:
        text = text.replace("__BUILD_STAMP__", stamp)
        n += 1
    text, c = re.subn(r'BUILD_STAMP = "[^"]*"', f'BUILD_STAMP = "{stamp}"', text)
    n += c
    if "BUILD_STAMP" not in text:
        needle = f'        bundle = "{_detect_bundle_name()}"\n'
        insert = f'{needle}        BUILD_STAMP = "{stamp}"\n'
        if needle in text:
            text = text.replace(needle, insert, 1)
            n += 1
        else:
            needle2 = '        bundle = "stackdefense"\n'
            insert2 = f'{needle2}        BUILD_STAMP = "{stamp}"\n'
            if needle2 in text:
                text = text.replace(needle2, insert2, 1)
                n += 1
    return text, n


def _inject_rmtree_before_extract(text: str) -> tuple[str, int]:
    if "shutil.rmtree(appdir" in text:
        return text, 0
    old = (
        '        appdir = Path(f"/data/data/{bundle}")\n'
        "        appdir.mkdir()\n"
        "        assets = appdir / \"assets\"\n"
    )
    new = (
        '        appdir = Path(f"/data/data/{bundle}")\n'
        "        assets = appdir / \"assets\"\n"
        "        if appdir.is_dir():\n"
        "            import shutil\n"
        "            shutil.rmtree(appdir, ignore_errors=True)\n"
        "        appdir.mkdir()\n"
    )
    if old in text:
        return text.replace(old, new, 1), 1
    return text, 0


def _fix_shell_interactive(text: str) -> tuple[str, int]:
    import re

    text, n = re.subn(
        r'(        if platform\.window\.location\.hash\.find\("#debug"\) >= 0:\n)+'
        r'        shell\.interactive\(\)',
        '        if platform.window.location.hash.find("#debug") >= 0:\n'
        "            shell.interactive()",
        text,
    )
    if n:
        return text, n
    needle = "        shell.interactive()\n"
    repl = (
        '        if platform.window.location.hash.find("#debug") >= 0:\n'
        "            shell.interactive()\n"
    )
    if needle in text and 'find("#debug")' not in text.split("shell.interactive()")[0][-200:]:
        return text.replace(needle, repl, 1), 1
    return text, 0


def _dedupe_loader_watchdog(text: str) -> tuple[str, int]:
    marker = "仍在下载/编译 WASM，请耐心等待"
    if text.count(marker) <= 1:
        return text, 0
    first = text.find('window.addEventListener("load", () => {')
    second = text.find('window.addEventListener("load", () => {', first + 1)
    if second < 0:
        return text, 0
    third = text.find('window.addEventListener("load", () => {', second + 1)
    if third < 0:
        return text, 0
    end = text.find("function frame_online", third)
    if end < 0:
        return text, 0
    return text[:second] + text[end:], 1


def _rename_archives() -> int:
    """本地中文目录名 → stackdefense；CI 上保留 pygbag 实际包名（如 stackdefense-lxw）。"""
    n = 0
    for ext in (".tar.gz", ".apk"):
        legacy = WEB / f"{ARCHIVE_OLD}{ext}"
        target = WEB / f"{ARCHIVE_NEW}{ext}"
        if not legacy.is_file():
            continue
        if target.is_file():
            target.unlink()
        legacy.rename(target)
        n += 1
        print(f"  rename {legacy.name} -> {target.name}")
    return n


def _strip_broken_pip_install(text: str) -> tuple[str, int]:
    """WASM 上 pip_install(pygame-ce) 会装残缺包，须改由 shell.source + wasm wheel 安装。"""
    blocks = [
        (
            "        import aio.pep0723\n"
            '        platform.window.infobox.innerText = "正在安装 pygame-ce…"\n'
            '        await aio.pep0723.pip_install("pygame-ce")\n'
            '        await aio.pep0723.pip_install("pillow")\n\n',
            "",
        ),
        (
            "        import aio.pep0723\n"
            '        await aio.pep0723.pip_install("pygame-ce")\n'
            '        await aio.pep0723.pip_install("pillow")\n\n',
            "",
        ),
    ]
    n = 0
    for old, new in blocks:
        if old in text:
            text = text.replace(old, new, 1)
            n += 1
    return text, n


def _fix_web_startup(text: str) -> tuple[str, int]:
    """官方顺序：run_main(None) → preload → shell.source(main)，勿手动 pip pygame-ce。"""
    n = 0
    text, c = _strip_broken_pip_install(text)
    n += c
    if 'loadermain="main.py"' in text and "await shell.source(main" not in text:
        text = text.replace(
            'platform.run_main(PyConfig, loaderhome=assets, loadermain="main.py")',
            "platform.run_main(PyConfig, loaderhome=assets, loadermain=None)",
            1,
        )
        n += 1
    if (
        "await TopLevel_async_handler.start_toplevel" not in text
        and "async def custom_site" in text
        and "if not main.is_file():" in text
    ):
        needle = "        if not main.is_file():\n"
        insert = (
            "        await TopLevel_async_handler.start_toplevel(platform.shell, console=False)\n\n"
        )
        if insert.strip() not in text:
            text = text.replace(needle, insert + needle, 1)
            n += 1
    if "await shell.source(main" not in text and "loadermain=None" in text:
        anchor = "        platform.window.window_resize()\n"
        block = (
            "        def ui_callback(pkg):\n"
            '            platform.window.infobox.innerText = f"正在加载 {pkg}…"\n\n'
            "        await shell.source(main, callback=ui_callback)\n\n"
        )
        if anchor in text and block not in text:
            text = text.replace(anchor, block + anchor, 1)
            n += 1
    return text, n


def main() -> int:
    if not INDEX.is_file():
        print(f"skip: {INDEX} not found (run pygbag first)")
        return 1

    _rename_archives()
    bundle = _detect_bundle_name()
    text = INDEX.read_text(encoding="utf-8")
    changed = 0

    if ARCHIVE_OLD in text:
        text = text.replace(ARCHIVE_OLD, bundle if bundle != ARCHIVE_OLD else ARCHIVE_NEW)
        changed += 1

    text, n = _sync_archive_references(text, bundle)
    changed += n

    text, n = _fix_web_startup(text)
    changed += n

    if CDN_REMOTE in text:
        text = text.replace(CDN_REMOTE, CDN_LOCAL)
        changed += 1

    bfs = "./cdn/0.9.3/browserfs.min.js"
    if bfs not in text and "browserfs.min.js" in text:
        text = text.replace(
            '<html lang="en-us"><script src="./cdn/0.9.3/pythons.js"',
            f'<html lang="en-us"><script src="{bfs}"></script>'
            '<script src="./cdn/0.9.3/pythons.js"',
            1,
        )
        changed += 1
    text = text.replace("./cdn/0.9.3//browserfs.min.js", bfs)
    text = text.replace(
        '    <script src="./cdn/0.9.3/browserfs.min.js"></script>\n\n</head>',
        "</head>",
    )

    for old, new in REPLACEMENTS:
        if old in text:
            text = text.replace(old, new, 1)
            changed += 1

    for old, new in LEGACY_CUSTOM_SITE:
        if old in text:
            text = text.replace(old, new, 1)
            changed += 1

    text, n = _inject_build_stamp(text)
    changed += n
    text, n = _inject_rmtree_before_extract(text)
    changed += n
    text, n = _fix_shell_interactive(text)
    changed += n
    text, n = _dedupe_loader_watchdog(text)
    changed += n

    if LOADER_WATCHDOG.strip() not in text:
        text = text.replace("function frame_online(url) {", LOADER_WATCHDOG + "\n    function frame_online(url) {", 1)
        changed += 1

    if 'data-os="vtx,snd,gui"' in text:
        text = text.replace('data-os="vtx,snd,gui"', 'data-os="snd,gui"', 1)
        changed += 1

    sw_old = (
        "        if (navigator.serviceWorker)\n"
        '            navigator.serviceWorker.register("./cdn/0.9.3/pygbag0.9.3.js")\n'
        "        else\n"
        '            console.warn("Service workers not supported")'
    )
    sw_new = (
        "        // GitHub Pages 静态托管无需 pygbag service worker\n"
        "        // if (navigator.serviceWorker)\n"
        '        //     navigator.serviceWorker.register("./cdn/0.9.3/pygbag0.9.3.js")'
    )
    if sw_old in text:
        text = text.replace(sw_old, sw_new, 1)
        changed += 1
    elif "navigator.serviceWorker.register" in text and "pygbag0.9.3.js" in text:
        text, c = re.subn(
            r"\s*if \(navigator\.serviceWorker\)\s*\n"
            r'\s*navigator\.serviceWorker\.register\("\./cdn/0\.9\.3/pygbag0\.9\.3\.js"\)\s*\n'
            r"\s*else\s*\n"
            r'\s*console\.warn\("Service workers not supported"\)',
            "\n" + sw_new,
            text,
            count=1,
        )
        changed += c

    legacy_run = "asyncio.run( custom_site() )"
    if legacy_run in text:
        text = text.replace(
            legacy_run,
            "import aio\naio.create_task(custom_site())",
            1,
        )
        changed += 1

    if "z-index: 5;" in text and "canvas.emscripten" in text:
        text = text.replace("            z-index: 5;\n\n", "")
        changed += 1
    if "background-color: transparent;" in text and "canvas.emscripten" in text:
        pass

    INDEX.write_text(text, encoding="utf-8")
    print(f"patched {INDEX} ({changed} change(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
