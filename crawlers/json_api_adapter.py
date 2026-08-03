"""JSON 接口适配器：新浪体育、网易体育。"""
import json
import re
from datetime import datetime

from crawlers.base import SourceAdapter


def _parse_dt_sina(ts) -> datetime:
    try:
        return datetime.fromtimestamp(int(ts))
    except Exception:
        return None


def _parse_dt_netense(s: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except Exception:
            continue
    return None


def parse_sina(cfg: dict, http, max_pages: int) -> list:
    out = []
    for page in range(1, max_pages + 1):
        url = cfg["url"].replace("{page}", str(page))
        r = http.get(url, parse_json=True)
        if r.status_code != 200:
            break
        try:
            data = r.json()
        except Exception:
            break
        items = data.get("result", {}).get("data") or []
        if not items:
            break
        for it in items:
            title = (it.get("title") or "").strip()
            link = it.get("url") or it.get("wapurl") or ""
            if not title or not link:
                continue
            summary = it.get("intro") or it.get("summary") or it.get("wapsummary") or ""
            author = it.get("media_name") or it.get("author") or ""
            pub = _parse_dt_sina(it.get("ctime") or it.get("mtime"))
            out.append({
                "title": title, "url": link, "summary": summary,
                "author": author, "published_at": pub,
            })
    return out


def parse_netease(cfg: dict, http, max_pages: int) -> list:
    out = []
    for i in range(max_pages):
        offset = i * 10
        url = cfg["url"].replace("{offset}", str(offset))
        r = http.get(url, parse_json=True)
        if r.status_code != 200:
            break
        text = r.text.strip()
        m = re.search(r"artiList\((.*)\)", text, re.S)
        if not m:
            # 也可能返回纯 JSON
            try:
                data = json.loads(text)
            except Exception:
                break
        else:
            try:
                data = json.loads(m.group(1))
            except Exception:
                break
        if not data:
            break
        key = next(iter(data))
        items = data.get(key) or []
        if not items:
            break
        for it in items:
            title = (it.get("title") or "").strip()
            link = it.get("url") or ""
            if not link and it.get("docid"):
                link = f"https://3g.163.com/news/article/{it['docid']}.html"
            if not title or not link:
                continue
            summary = it.get("digest") or ""
            author = it.get("source") or ""
            pub = _parse_dt_netense(it.get("ptime") or "")
            out.append({
                "title": title, "url": link, "summary": summary,
                "author": author, "published_at": pub,
            })
    return out


PARSERS = {"sina": parse_sina, "netease": parse_netease}


class JsonApiAdapter(SourceAdapter):
    def fetch_since(self, days: int = 7) -> list:
        parser = PARSERS.get(self.cfg.get("parser"))
        if not parser:
            return []
        max_pages = int(self.cfg.get("max_pages", 3))
        raw = parser(self.cfg, self.http, max_pages)
        arts = []
        for r in raw:
            if not r.get("published_at"):
                # 无时间则默认视为近期，仍纳入
                pass
            arts.append(self._to_article(r))
        return arts
