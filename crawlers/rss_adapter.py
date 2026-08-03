"""RSS 适配器：BBC / Guardian / ESPN / 央视 等标准 RSS。"""
import re
import time
from datetime import datetime

import feedparser

from crawlers.base import SourceAdapter


def _rss_image(entry) -> str:
    """从 RSS 条目尽力提取封面图。"""
    # media:content / media:thumbnail
    mc = entry.get("media_content") or []
    for m in mc:
        if m.get("url") and m.get("medium") in (None, "image"):
            return m["url"]
    mt = entry.get("media_thumbnail") or []
    for m in mt:
        if m.get("url"):
            return m["url"]
    enc = entry.get("enclosures") or []
    for m in enc:
        if m.get("type", "").startswith("image") and m.get("href"):
            return m["href"]
    # 描述里的第一张图
    desc = entry.get("summary") or entry.get("description") or ""
    mm = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
    if mm:
        return mm.group(1)
    return ""


class RssAdapter(SourceAdapter):
    def fetch_since(self, days: int = 7) -> list:
        r = self.http.get(self.cfg["url"])
        if r.status_code != 200:
            return []
        # feedparser 接受 bytes
        feed = feedparser.parse(r.content)
        arts = []
        for e in feed.entries:
            title = (e.get("title") or "").strip()
            link = e.get("link") or ""
            if not title or not link:
                continue
            summary = e.get("summary") or e.get("description") or ""
            author = e.get("author") or ""
            pub = None
            for key in ("published_parsed", "updated_parsed", "created_parsed"):
                tp = e.get(key)
                if tp:
                    try:
                        pub = datetime.fromtimestamp(time.mktime(tp))
                        break
                    except Exception:
                        pass
            arts.append(self._to_article({
                "title": title, "url": link, "summary": summary,
                "author": author, "published_at": pub,
                "image_url": _rss_image(e),
            }))
        return arts
