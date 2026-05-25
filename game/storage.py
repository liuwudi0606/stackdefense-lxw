"""存档读写：桌面用本地文件，网页用浏览器 localStorage（刷新不丢）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from game.platform_util import is_web

META_STORAGE_KEY = "stackdefense_meta_v1"
RUN_STORAGE_KEY = "stackdefense_run_v1"


def _web_get(key: str) -> str | None:
    try:
        import platform as pw

        v = pw.window.localStorage.getItem(key)
        if v is None or v == "":
            return None
        return str(v)
    except Exception:
        return None


def _web_set(key: str, value: str) -> bool:
    try:
        import platform as pw

        pw.window.localStorage.setItem(key, value)
        return True
    except Exception:
        return False


def _web_remove(key: str) -> None:
    try:
        import platform as pw

        pw.window.localStorage.removeItem(key)
    except Exception:
        pass


def read_json(path: Path, *, web_key: str) -> dict | None:
    if is_web():
        raw = _web_get(web_key)
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None
    if not path.is_file():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def write_json(path: Path, data: Any, *, web_key: str) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if is_web():
        _web_set(web_key, text)
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError:
        pass


def has_stored(path: Path, *, web_key: str) -> bool:
    if is_web():
        return _web_get(web_key) is not None
    return path.is_file()


def delete_stored(path: Path, *, web_key: str) -> None:
    if is_web():
        _web_remove(web_key)
        return
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            pass
