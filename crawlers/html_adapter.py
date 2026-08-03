"""HTML 列表+详情适配器（通用）：腾讯/搜狐/新华/人民/虎扑/直播吧/路透。"""
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawlers.base import SourceAdapter
from crawlers.content import extract_from_html, extract_date_from_text


class HtmlAdapter(SourceAdapter):
    def fetch_since(self, days: int = 7) -> list:
        r = self.http.get(self.list_url())
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "lxml")
        base = self.cfg.get("list_url")
        pattern = self.cfg.get("article_url_pattern")
        rx = re.compile(pattern) if pattern else None
        max_articles = int(self.cfg.get("max_articles", 40))

        seen, candidates = set(), []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(strip=True)
            if not href or href.startswith(("javascript:", "#", "mailto:")):
                continue
            abs_url = urljoin(base, href)
            if rx:
                if not rx.search(abs_url):
                    continue
                if len(text) < 6:
                    continue
            else:
                # 无 pattern 时的启发式：站内链接 + 足够长的锚文本
                if not abs_url.startswith("http"):
                    continue
                if len(text) < 12:
                    continue
            if abs_url in seen:
                continue
            seen.add(abs_url)
            # 从列表锚文本尝试抽取发布时间（新华等站点日期嵌在标题里）
            list_date = extract_date_from_text(text)
            candidates.append((abs_url, text, list_date))

        arts = []
        for url, list_title, list_date in candidates[:max_articles]:
            detail = self._fetch_detail(url)
            if not detail or not detail.get("title"):
                # 至少保留列表标题
                arts.append(self._to_article({"title": list_title, "url": url,
                                              "summary": "", "published_at": list_date}))
                continue
            detail["url"] = url
            if not detail.get("summary"):
                detail["summary"] = ""
            # 详情页没解析到时间时，回退到列表锚文本时间
            if not detail.get("published_at") and list_date:
                detail["published_at"] = list_date
            arts.append(self._to_article(detail))
        return arts

    def list_url(self) -> str:
        return self.cfg.get("list_url")

    def _fetch_detail(self, url: str) -> dict:
        r = self.http.get(url)
        if r.status_code != 200:
            return {}
        return extract_from_html(r.text, url)
