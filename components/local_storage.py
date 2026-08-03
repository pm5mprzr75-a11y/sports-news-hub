"""浏览器本地存储封装（基于 streamlit-local-storage）。

收藏 / 浏览历史 / 订阅 / 关键词监控 都存浏览器 localStorage，
因此「每台设备」独立、云端也持久（关掉网页再开仍在），且不占用服务器数据库。
"""
from __future__ import annotations

import json

from streamlit_local_storage import LocalStorage

_ls = LocalStorage()

# 统一命名空间下的键
_K_BOOKMARKS = "sports_hub_bookmarks"
_K_HISTORY = "sports_hub_history"
_K_SUBS = "sports_hub_subs"
_K_MONITORS = "sports_hub_monitors"
_K_MON_LASTTS = "sports_hub_mon_lastts"


def load_json(key: str, default):
    raw = _ls.getItem(key)
    if raw in (None, ""):
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def save_json(key: str, value) -> None:
    _ls.setItem(key, json.dumps(value, ensure_ascii=False))


# ---- 收藏 ----
def get_bookmarks() -> list:
    return load_json(_K_BOOKMARKS, [])


def add_bookmark(art) -> None:
    bms = get_bookmarks()
    if any(b["url"] == art.url for b in bms):
        return
    bms.insert(0, {
        "id": art.id, "title": art.title, "url": art.url,
        "source": art.source_name, "published": art.published_at.isoformat()
        if art.published_at else "",
    })
    save_json(_K_BOOKMARKS, bms[:200])


def remove_bookmark(url: str) -> None:
    bms = [b for b in get_bookmarks() if b["url"] != url]
    save_json(_K_BOOKMARKS, bms)


def is_bookmarked(url: str) -> bool:
    return any(b["url"] == url for b in get_bookmarks())


# ---- 浏览历史 ----
def add_history(art) -> None:
    hist = get_history()
    hist = [h for h in hist if h["url"] != art.url]
    hist.insert(0, {
        "id": art.id, "title": art.title, "url": art.url,
        "source": art.source_name, "published": art.published_at.isoformat()
        if art.published_at else "",
    })
    save_json(_K_HISTORY, hist[:100])


def get_history() -> list:
    return load_json(_K_HISTORY, [])


# ---- 订阅 ----
def get_subs() -> dict:
    return load_json(_K_SUBS, {"sports": [], "entities": []})


def set_subs(sports: list, entities: list) -> None:
    save_json(_K_SUBS, {"sports": sports, "entities": entities})


# ---- 关键词监控 ----
def get_monitors() -> list:
    return load_json(_K_MONITORS, [])


def set_monitors(words: list) -> None:
    save_json(_K_MONITORS, words)


def get_mon_last_ts() -> str:
    return load_json(_K_MON_LASTTS, "")


def set_mon_last_ts(ts: str) -> None:
    save_json(_K_MON_LASTTS, ts)
