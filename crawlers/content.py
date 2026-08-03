"""通用网页正文抽取（用于 HTML 源详情页，以及 UI 按需补全全文）。"""
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

_DATE_PATTERNS = [
    (r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}(?::\d{2})?)", "%Y-%m-%d %H:%M:%S"),
    (r"(\d{4}年\d{1,2}月\d{1,2}日)\s*(\d{1,2}[:：]\d{2})", None),  # 特殊处理
    (r"(\d{4}/\d{2}/\d{2})\s+(\d{2}:\d{2})", "%Y/%m/%d %H:%M"),
    (r"(\d{4}-\d{2}-\d{2})", "%Y-%m-%d"),
]


def clean(soup: BeautifulSoup) -> None:
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "iframe", "svg"]):
        tag.decompose()


def extract_title(soup: BeautifulSoup) -> str:
    m = soup.find("meta", property="og:title")
    if m and m.get("content"):
        return m["content"].strip()
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return ""


def extract_date_from_text(text: str):
    """从任意文本中抽取日期（供列表页锚文本复用）。"""
    if not text:
        return None
    for pat, fmt in _DATE_PATTERNS:
        mm = re.search(pat, text)
        if mm:
            try:
                if fmt is None:
                    # 中文日期
                    cn = mm.group(1).replace("年", "-").replace("月", "-").replace("日", "")
                    tm = mm.group(2).replace("：", ":")
                    return datetime.strptime(f"{cn} {tm}", "%Y-%m-%d %H:%M")
                return datetime.strptime(f"{mm.group(1)} {mm.group(2)}", fmt)
            except Exception:
                continue
    return None


def extract_published(soup: BeautifulSoup, html_text: str) -> datetime:
    m = soup.find("meta", property="article:published_time")
    if m and m.get("content"):
        try:
            return datetime.fromisoformat(m["content"].replace("Z", "+00:00"))
        except Exception:
            pass
    m = soup.find("meta", attrs={"name": "pubdate"})
    if m and m.get("content"):
        try:
            return datetime.fromisoformat(m["content"].replace("Z", "+00:00"))
        except Exception:
            pass
    return extract_date_from_text(html_text)


def extract_content(soup: BeautifulSoup, max_len: int = 4000) -> str:
    clean(soup)
    # 优先取 <article>
    root = soup.find("article") or soup.find("main") or soup.body or soup
    paras = [p.get_text(strip=True) for p in root.find_all("p")]
    paras = [p for p in paras if len(p) > 15]
    text = "\n".join(paras)
    if len(text) < 200:
        # 退而求其次：取最长文本块
        chunks = [c.get_text(strip=True) for c in root.find_all(["div", "section"])]
        chunks = [c for c in chunks if len(c) > 50]
        chunks.sort(key=len, reverse=True)
        text = chunks[0] if chunks else text
    return text[:max_len].strip()


def extract_from_html(html: str, base_url: str = "") -> dict:
    soup = BeautifulSoup(html, "lxml")
    title = extract_title(soup)
    pub = extract_published(soup, html)
    content = extract_content(soup)
    author = ""
    am = soup.find("meta", attrs={"name": "author"})
    if am and am.get("content"):
        author = am["content"]
    return {"title": title, "published_at": pub, "content": content, "author": author}
