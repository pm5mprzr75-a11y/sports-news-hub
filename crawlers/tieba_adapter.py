"""百度贴吧适配器：按运动项目抓取各「吧」的帖子 + 楼层回复。

说明：
- 贴吧反爬较严（移动 API 已不稳定，PC 列表页需正常 UA/Cookie）。
- 采用「PC 吧列表页(HMTL) → 帖子页(HTML) 抽楼层回复」的方式，best-effort。
- 若本机网络被风控，会优雅降级返回空，不影响其他源。
"""
import json
import random
import re
import time
from datetime import datetime
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from crawlers.base import SourceAdapter
from nlp.keyword_matcher import KeywordMatcher
from store.models import Comment

PC_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def _parse_tieba_date(s: str):
    if not s:
        return None
    s = s.strip()
    now = datetime.now()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"(\d{2})-(\d{2})", s)
    if m:
        return datetime(now.year, int(m.group(1)), int(m.group(2)))
    return None


class TiebaAdapter(SourceAdapter):
    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.session = self.http.session
        self.session.headers.update({
            "User-Agent": PC_UA,
            "Referer": "https://tieba.baidu.com/",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        })
        # 贴吧对无 BAIDUID 的请求直接 403，先种一个种子 cookie 以绕过初始拦截
        self.session.cookies.set("BAIDUID", "B9D8A3E8C9F2A1B4:FG=1", domain=".baidu.com")
        self.matcher = KeywordMatcher()
        self.max_per_sport = cfg.get("max_per_sport", 8)

    def _thread_list(self, tieba_name: str):
        out = []
        url = f"https://tieba.baidu.com/f?kw={quote(tieba_name)}&pn=0"
        r = self.http.get(url)
        if r.status_code != 200 or len(r.text) < 500:
            return out
        soup = BeautifulSoup(r.text, "lxml")
        for li in soup.select("li.j_thread_list"):
            tid = li.get("data-tid")
            if not tid:
                continue
            a = li.select_one("a.j_th_tit")
            if not a:
                a = li.select_one("a[href^='/p/']")
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if not href.startswith("/p/"):
                continue
            # 回复/日期
            rep = li.select_one(".threadlist_rep_num")
            reply_num = int(re.sub(r"\D", "", rep.get_text() or "0") or 0) if rep else 0
            date_span = li.select_one(".threadlist_reply_date")
            pub = _parse_tieba_date(date_span.get_text() if date_span else "")
            out.append({
                "tid": tid,
                "title": title,
                "url": "https://tieba.baidu.com" + href,
                "reply_num": reply_num,
                "published_at": pub,
            })
        return out

    def fetch_since(self, days: int = 7):
        arts, seen = [], set()
        for sport in self.matcher.sports():
            tieba_name = self.matcher.sport_tieba(sport)
            try:
                threads = self._thread_list(tieba_name)
            except Exception:
                threads = []
            for th in threads[:self.max_per_sport]:
                if th["url"] in seen:
                    continue
                seen.add(th["url"])
                if not th["title"]:
                    continue
                a = self._to_article({
                    "title": th["title"],
                    "url": th["url"],
                    "published_at": th["published_at"],
                    "summary": "",
                })
                a.sport_tags = [sport]
                a.comment_adapter = "tieba"
                a.comment_count = th["reply_num"]
                arts.append(a)
            time.sleep(random.uniform(0.4, 1.0))
        return arts


# ---------------------------------------------------------------------------
# 楼层回复抓取
# ---------------------------------------------------------------------------
def fetch_tieba_comments(article) -> list:
    m = re.search(r"/p/(\d+)", article.url or "")
    if not m:
        return []
    tid = m.group(1)
    out = []
    try:
        s = requests.Session()
        s.headers.update({"User-Agent": PC_UA, "Referer": article.url})
        r = s.get(f"https://tieba.baidu.com/p/{tid}?pn=1", timeout=15)
        if r.status_code != 200:
            return out
        soup = BeautifulSoup(r.text, "lxml")
        for div in soup.select("div.d_post_content"):
            content = div.get_text(" ", strip=True)
            if len(content) < 2:
                continue
            # 用户名来自最近带 data-field 的祖先
            author = ""
            node = div
            for _ in range(4):
                node = node.parent
                if node is None:
                    break
                df = node.get("data-field")
                if df:
                    try:
                        author = json.loads(df).get("author", {}).get("user_name", "")
                    except Exception:
                        author = ""
                    break
            out.append(Comment(
                article_id=article.id,
                author=author or "匿名",
                content=content,
                published_at=None,
                likes=0,
                source="百度贴吧",
            ))
            if len(out) >= 30:
                break
    except Exception:
        pass
    return out
