"""为静态托管写入 COOP/COEP 响应头（Surge / Netlify / Cloudflare Pages 通用）。"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "build" / "web"

_HEADERS = """/*
  Cross-Origin-Opener-Policy: cross-origin
  Cross-Origin-Embedder-Policy: require-corp
  Cross-Origin-Resource-Policy: cross-origin
  Access-Control-Allow-Origin: *
"""


def main() -> int:
    if not WEB.is_dir():
        print(f"缺少 {WEB}，请先运行 build_web.bat")
        return 1
    (WEB / "_headers").write_text(_HEADERS, encoding="utf-8")
    print(f"已写入 {WEB / '_headers'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
