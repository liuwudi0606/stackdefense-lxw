"""将 pygbag 网页运行所需文件下载到 build/web/cdn/。"""
from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "build" / "web"
CDN_VER = "0.9.3"
PYGAME_CDN = "https://pygame-web.github.io/cdn"
BASE = f"{PYGAME_CDN}/{CDN_VER}"
LOCAL = WEB / "cdn" / CDN_VER
LOCAL_CDN_ROOT = WEB / "cdn"

# pygame-web 已不再托管 browserfs，需单独获取
BROWSERFS_URL = (
    "https://cdn.jsdelivr.net/npm/browserfs@2.0.0/dist/browserfs.min.js"
)
PYGAME_WHEEL = (
    f"{PYGAME_CDN}/cp312/"
    "pygame_ce-2.5.7-cp312-cp312-wasm32_bi_emscripten.whl"
)
INDEX_JSON = f"{PYGAME_CDN}/index-0.9.3-cp312.json"

RUNTIME_FILES = [
    "pythons.js",
    "cpython312/main.js",
    "cpython312/main.wasm",
    "cpython312/main.data",
]

# pythons.js 会动态 import ../vtx.js；iframe 需要 empty.html
EXTRA_CDN_FILES = [
    ("vtx.js", LOCAL_CDN_ROOT / "vtx.js"),
    ("vt.js", LOCAL_CDN_ROOT / "vt.js"),
    ("vt/xterm.css", LOCAL_CDN_ROOT / "vt" / "xterm.css"),
    ("vt/xterm.js", LOCAL_CDN_ROOT / "vt" / "xterm.js"),
    ("vt/xterm-addon-image.js", LOCAL_CDN_ROOT / "vt" / "xterm-addon-image.js"),
    (f"{CDN_VER}/empty.html", LOCAL / "empty.html"),
]


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 0:
        print(f"  skip {dest.relative_to(WEB)} ({dest.stat().st_size} B)")
        return
    print(f"  get {url}")
    urllib.request.urlretrieve(url, dest)
    print(f"  ok  {dest.relative_to(WEB)} ({dest.stat().st_size} B)")


def main() -> int:
    if not (WEB / "index.html").is_file():
        print(f"缺少 {WEB / 'index.html'}，请先运行 build_web.bat")
        return 1

    print("下载 BrowserFS …")
    download(BROWSERFS_URL, LOCAL / "browserfs.min.js")

    print(f"下载 Python 运行时到 {LOCAL} …")
    ok = 0
    for rel in RUNTIME_FILES:
        try:
            download(f"{BASE}/{rel}", LOCAL / rel.replace("/", os.sep))
            ok += 1
        except Exception as e:
            print(f"  WARN {rel}: {e}")

    print("下载 pygame-ce wasm wheel …")
    try:
        download(
            PYGAME_WHEEL,
            LOCAL_CDN_ROOT / "cp312" / PYGAME_WHEEL.rsplit("/", 1)[-1],
        )
    except Exception as e:
        print(f"  WARN pygame wheel: {e}")

    print("下载包索引 index-0.9.3-cp312.json …")
    try:
        dest = LOCAL_CDN_ROOT / "index-0.9.3-cp312.json"
        download(INDEX_JSON, dest)
        # 兼容 pythons 从站点根目录拉取索引
        download(INDEX_JSON, WEB / "index-0.9.3-cp312.json")
    except Exception as e:
        print(f"  WARN index json: {e}")

    print("下载 pygbag 辅助脚本（vtx / empty.html 等）…")
    extra_ok = 0
    for rel, dest in EXTRA_CDN_FILES:
        try:
            download(f"{PYGAME_CDN}/{rel}", dest)
            extra_ok += 1
        except Exception as e:
            print(f"  WARN {rel}: {e}")

    if ok < 3:
        print("Python 运行时下载不完整，请检查网络后重试。")
        return 1
    if extra_ok < 1:
        print("辅助 CDN 文件下载失败，请检查网络后重试。")
        return 1

    print("完成。请运行 preview_web.bat 或: python tools/serve_web.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
