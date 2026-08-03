"""网易新闻评论抓取（best-effort）。

网易评论接口历史上为：
  https://comment.api.163.com/api/v1/products/<pid>/threads/<docid>/comments/newsList
其中 pid 为固定产品 id，docid 取自文章 URL。接口可能随站点改版失效，
因此本实现采用"容错递归解析"：在返回 JSON 中递归寻找含 content+userName 的对象。
"""
import re
from datetime import datetime

import requests

from store.models import Comment

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
PID = "a2869674571f77b5a0867c3d71db5856"
ENDPOINTS = [
    "https://comment.api.163.com/api/v1/products/{pid}/threads/{docid}/comments/newsList?offset=0&limit=30",
    "https://comment.news.163.com/api/v1/products/{pid}/threads/{docid}/comments/newsList?offset=0&limit=30",
]


def _extract_docid(url: str) -> str:
    m = re.search(r"/([A-Za-z0-9]{10,})\.html", url)
    if m:
        return m.group(1)
    m = re.search(r"docid=([A-Za-z0-9]+)", url)
    return m.group(1) if m else ""


def _collect(obj, out: list, seen: set) -> None:
    if isinstance(obj, dict):
        content = obj.get("content")
        if isinstance(content, str) and content.strip():
            uname = obj.get("userName") or obj.get("nickname") or obj.get("user") or "匿名"
            ctime = obj.get("createTime") or obj.get("time") or None
            likes = obj.get("vote") or obj.get("praise") or obj.get("likes") or 0
            dt = None
            if isinstance(ctime, (int, float)):
                try:
                    dt = datetime.fromtimestamp(ctime / 1000 if ctime > 1e12 else ctime)
                except Exception:
                    pass
            elif isinstance(ctime, str):
                try:
                    dt = datetime.fromisoformat(ctime.replace("Z", "+00:00"))
                except Exception:
                    pass
            key = (uname, content[:40])
            if key not in seen:
                seen.add(key)
                out.append(Comment(
                    article_id=0, author=str(uname), content=content.strip(),
                    published_at=dt, likes=int(likes or 0), source="netease",
                ))
        for v in obj.values():
            _collect(v, out, seen)
    elif isinstance(obj, list):
        for v in obj:
            _collect(v, out, seen)


def fetch_netease_comments(article) -> list:
    docid = _extract_docid(article.url)
    if not docid:
        return []
    for tpl in ENDPOINTS:
        url = tpl.format(pid=PID, docid=docid)
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
        except Exception:
            continue
        if r.status_code != 200:
            continue
        try:
            data = r.json()
        except Exception:
            continue
        out, seen = [], set()
        _collect(data, out, seen)
        if out:
            return out[:30]
    return []
