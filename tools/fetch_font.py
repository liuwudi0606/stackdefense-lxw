"""下载网页/桌面共用的 Noto Sans SC 子集字体（约 8MB）。"""
from __future__ import annotations

import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "fonts" / "NotoSansSC-Regular.otf"
URL = (
    "https://github.com/notofonts/noto-cjk/raw/main/"
    "Sans/SubsetOTF/SC/NotoSansSC-Regular.otf"
)


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.is_file() and OUT.stat().st_size > 500_000:
        print(f"已有字体: {OUT}")
        return 0
    print(f"下载 {URL} …")
    urllib.request.urlretrieve(URL, OUT)
    print(f"已保存 {OUT} ({OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
