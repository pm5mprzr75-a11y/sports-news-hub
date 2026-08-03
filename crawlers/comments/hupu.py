"""虎扑评论抓取（best-effort）。

虎扑 BBS 帖子页服务端渲染了回复楼层（.discuss-card），每个楼层含
用户名 / 内容 / 时间 / 点赞数。直接解析这些楼层即可拿到评论。
"""
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from store.models import Comment

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"


def _parse_dt(s) -> datetime:
    if not s:
        return None
    if isinstance(s, (int, float)):
        try:
            return datetime.fromtimestamp(s / 1000 if s > 1e12 else s)
        except Exception:
            return None
    s = str(s).strip()
    if isinstance(s, str):
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            pass
    # 中文/短日期：MM月DD日 HH:MM / YYYY-MM-DD HH:MM / MM-DD HH:MM / 今天 HH:MM
    now = datetime.now()
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})\s*(\d{1,2}):(\d{2})", s)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)))
    m = re.search(r"(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})", s)
    if m:
        return datetime(now.year, int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
    m = re.search(r"(\d{1,2})-(\d{1,2})\s*(\d{1,2}):(\d{2})", s)
    if m:
        return datetime(now.year, int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
    return None


def fetch_hupu_comments(article) -> list:
    try:
        r = requests.get(article.url, headers={"User-Agent": UA}, timeout=15)
    except Exception:
        return []
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "lxml")
    cards = soup.select("div.discuss-card") or soup.select("div.hp-m-discuss-card")
    out = []
    for card in cards:
        content_el = card.select_one(".discuss-card__content") or card.select_one(".content")
        if not content_el:
            continue
        content = content_el.get_text(strip=True)
        if not content:
            continue
        user_el = card.select_one(".discuss-card__username") or card.select_one(".username")
        author = user_el.get_text(strip=True) if user_el else "匿名"
        time_el = card.select_one(".discuss-card__time") or card.select_one(".time")
        dt = _parse_dt(time_el.get_text(strip=True)) if time_el else None
        likes = 0
        light = card.select_one(".discuss-card__actions .light") or card.select_one(".light")
        if light:
            mm = re.search(r"(\d+)", light.get_text())
            if mm:
                likes = int(mm.group(1))
        out.append(Comment(
            article_id=0,
            author=author,
            content=content,
            published_at=dt,
            likes=likes,
            source="hupu",
        ))
        if len(out) >= 30:
            break
    return out
