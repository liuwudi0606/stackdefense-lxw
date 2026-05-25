"""在 build/web 上启动本地预览（COOP/COEP + wasm MIME + CDN 回源）。"""
from __future__ import annotations

import hashlib
import mimetypes
import os
import sys
import urllib.request
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "build" / "web"
CACHE = ROOT / "build" / "web-cache" / "proxy"
REMOTE_CDN = "https://pygame-web.github.io/cdn/"


class WebHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cross-Origin-Resource-Policy", "cross-origin")
        self.send_header("Cross-Origin-Opener-Policy", "cross-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        req = self.path.split("?", 1)[0]
        if req.endswith((".html", ".tar.gz", ".apk", ".js", ".wasm", ".json")):
            self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def _request_path(self) -> str:
        path = self.path.split("?", 1)[0]
        if path.startswith("/"):
            return path
        return "/" + path

    def send_head(self):
        self.path = self._request_path()
        path = self.translate_path(self.path)
        if self.path.endswith("/"):
            return super().send_head()

        if os.path.isfile(path):
            return super().send_head()

        # /cdn/... 本地缺失时从 pygame-web 拉取并缓存
        if self.path.startswith("/cdn/"):
            rel = self.path[len("/cdn/") :].lstrip("/")
            if rel:
                return self._serve_cached_remote(rel, path)

        return super().send_head()

    def _serve_cached_remote(self, rel: str, local_path: str):
        url = REMOTE_CDN + rel
        CACHE.mkdir(parents=True, exist_ok=True)
        key = hashlib.md5(url.encode()).hexdigest()
        cached = CACHE / key
        if not cached.is_file():
            print(f"  proxy {url}")
            try:
                urllib.request.urlretrieve(url, cached)
            except Exception as e:
                print(f"  proxy FAIL {url}: {e}")
                self.send_error(HTTPStatus.NOT_FOUND, f"Not found: {rel}")
                return None

        ctype = self.guess_type(str(cached))
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(cached.stat().st_size))
        self.end_headers()
        return cached.open("rb")


def main() -> int:
    if not (WEB / "index.html").is_file():
        print(f"缺少 {WEB / 'index.html'}，请先运行 build_web.bat")
        return 1

    if ".wasm" not in mimetypes.types_map:
        mimetypes.types_map[".wasm"] = "application/wasm"

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    os.chdir(WEB)
    handler = partial(WebHandler, directory=str(WEB))
    httpd = ThreadingHTTPServer(("localhost", port), handler)
    print(f"《叠层防线》网页预览: http://localhost:{port}/")
    print("（本地优先，缺失的 /cdn/* 会自动从 pygame-web 下载）")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
