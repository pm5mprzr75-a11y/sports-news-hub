"""RSS 适配器：BBC / Guardian / ESPN / 央视 等标准 RSS。"""
import time
from datetime import datetime

import feedparser

from crawlers.base import SourceAdapter


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
            }))
        return arts
