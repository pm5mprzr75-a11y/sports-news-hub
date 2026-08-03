"""微博适配器：按运动项目搜索 UGC 内容 + 热评抓取。

说明：
- 微博有「新浪访客系统」拦截，首次需拿到访客 cookie 才能调用搜索 API。
  本适配器实现标准 cookie 握手；若仍被拦截（如 IP 被风控），会优雅降级返回空。
- 接口依赖 m.weibo.cn 移动端 JSON API，需在用户本机（非受限网络）运行。
"""
import json
import random
import re
import time
from datetime import datetime, timedelta
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from crawlers.base import SourceAdapter
from nlp.keyword_matcher import KeywordMatcher
from store.models import Comment

MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")


def _clean(html: str) -> str:
    return BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)


def _parse_weibo_date(s: str):
    if not s:
        return None
    s = s.strip()
    now = datetime.now()
    if "刚刚" in s:
        return now
    m = re.search(r"(\d+)\s*分钟前", s)
    if m:
        return now - timedelta(minutes=int(m.group(1)))
    m = re.search(r"(\d+)\s*小时前", s)
    if m:
        return now - timedelta(hours=int(m.group(1)))
    if "今天" in s:
        t = re.search(r"(\d+):(\d+)", s)
        if t:
            return now.replace(hour=int(t.group(1)), minute=int(t.group(2)), second=0)
    if "昨天" in s:
        t = re.search(r"(\d+):(\d+)", s)
        base = now - timedelta(days=1)
        if t:
            return base.replace(hour=int(t.group(1)), minute=int(t.group(2)), second=0)
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"(\d{2})-(\d{2})", s)
    if m:
        return datetime(now.year, int(m.group(1)), int(m.group(2)))
    return None


class WeiboAdapter(SourceAdapter):
    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.session = self.http.session
        self.session.headers.update({
            "User-Agent": MOBILE_UA,
            "Referer": "https://m.weibo.cn/",
            "Accept": "application/json, text/plain, */*",
            "MWeibo-Pwa": "1",
            "X-Requested-With": "XMLHttpRequest",
        })
        self.matcher = KeywordMatcher()
        self.max_per_sport = cfg.get("max_per_sport", 8)
        self._visitor_ok = False

    def _ensure_visitor(self):
        """拿到访客 cookie（幂等）。失败则标记已尝试，不再重试。"""
        if self._visitor_ok:
            return
        try:
            c1 = quote(json.dumps({"a": 1, "cb": "gen_callback"}))
            r = self.session.get(f"https://m.weibo.cn/visitor/visitor?a=genvisitor&c={c1}", timeout=15)
            m = re.search(r'"tid"\s*:\s*"([^"]+)"', r.text)
            if m:
                tid = m.group(1)
                c2 = quote(json.dumps({"a": 1, "cb": "visit_callback", "tid": tid}))
                self.session.get(f"https://m.weibo.cn/visitor/visitor?a=genvisitor&c={c2}", timeout=15)
        except Exception:
            pass
        finally:
            self._visitor_ok = True

    def _search(self, query: str, pages: int = 1):
        out = []
        for p in range(1, pages + 1):
            url = (f"https://m.weibo.cn/api/container/getIndex?"
                   f"containerid=100103type%3D1%26q%3D{quote(query)}&page_type=searchall&page={p}")
            r = self.http.get(url, parse_json=True)
            if r.status_code != 200:
                continue
            try:
                data = r.json()
            except Exception:
                continue
            # 访客拦截时返回的是 HTML 而非 JSON
            if not isinstance(data, dict) or "data" not in data:
                break
            for card in data.get("data", {}).get("cards", []):
                mb = card.get("mblog")
                if mb:
                    out.append(mb)
        return out

    def fetch_since(self, days: int = 7):
        self._ensure_visitor()
        arts, seen = [], set()
        for sport in self.matcher.sports():
            try:
                mblogs = self._search(sport, pages=1)
            except Exception:
                mblogs = []
            for mb in mblogs[:self.max_per_sport]:
                bid = mb.get("bid") or mb.get("id") or mb.get("mid")
                if not bid:
                    continue
                url = f"https://m.weibo.cn/detail/{bid}"
                if url in seen:
                    continue
                seen.add(url)
                content = _clean(mb.get("text", ""))
                if len(content) < 5:
                    continue
                raw = {
                    "title": content[:60],
                    "url": url,
                    "author": (mb.get("user") or {}).get("screen_name", ""),
                    "published_at": _parse_weibo_date(mb.get("created_at")),
                    "summary": content[:140],
                    "content": content,
                }
                a = self._to_article(raw)
                extra = [s for s in self.matcher.sport_tags_for(content) if s != sport]
                a.sport_tags = [sport] + extra
                a.comment_count = int(mb.get("comments_count") or 0)
                arts.append(a)
            time.sleep(random.uniform(0.4, 1.0))
        return arts


# ---------------------------------------------------------------------------
# 评论抓取（供 comments 调度调用）
# ---------------------------------------------------------------------------
def _comment_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": MOBILE_UA,
        "Referer": "https://m.weibo.cn/",
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
    })
    return s


def fetch_weibo_comments(article) -> list:
    m = re.search(r"/detail/(\w+)", article.url or "")
    if not m:
        return []
    bid = m.group(1)
    out = []
    try:
        s = _comment_session()
        for max_id_type in (0, 1):
            url = (f"https://m.weibo.cn/comments/hotflow?id={bid}&mid={bid}"
                   f"&max_id_type={max_id_type}")
            r = s.get(url, timeout=15)
            if r.status_code != 200:
                break
            try:
                data = r.json()
            except Exception:
                break
            items = (data.get("data") or {}).get("data") or []
            if not items:
                break
            for c in items:
                content = _clean(c.get("text", ""))
                if not content:
                    continue
                out.append(Comment(
                    article_id=article.id,
                    author=(c.get("user") or {}).get("screen_name", ""),
                    content=content,
                    published_at=None,
                    likes=int(c.get("like_count") or 0),
                    source="微博",
                ))
    except Exception:
        pass
    return out
