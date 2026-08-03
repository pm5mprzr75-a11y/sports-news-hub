"""基础 HTTP 客户端与适配器抽象类。"""
import random
import time

import requests

from store.models import Article

UA_LIST = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
]

# 不同反爬等级对应的请求间隔（秒）
BAN_DELAY = {"low": (0.3, 0.8), "medium": (0.8, 1.6), "high": (1.5, 3.0)}


class HttpClient:
    def __init__(self, anti_ban: str = "low", timeout: int = 15):
        self.anti_ban = anti_ban
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })

    def get(self, url: str, parse_json: bool = False, **kwargs):
        ua = random.choice(UA_LIST)
        self.session.headers["User-Agent"] = ua
        lo, hi = BAN_DELAY.get(self.anti_ban, (0.5, 1.0))
        time.sleep(random.uniform(lo, hi))
        try:
            resp = self.session.get(url, timeout=self.timeout, **kwargs)
            if parse_json:
                return resp
            return resp
        except requests.RequestException as e:
            resp = requests.Response()
            resp.status_code = 0
            resp._content = b""
            resp.reason = str(e)
            return resp


class SourceAdapter:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.http = HttpClient(cfg.get("anti_ban", "low"))

    def fetch_since(self, days: int = 7) -> list:
        raise NotImplementedError

    # 工具：把抓取到的原始 dict 归一化为 Article
    def _to_article(self, raw: dict) -> Article:
        return Article(
            source_id=self.cfg["id"],
            source_name=self.cfg["name"],
            title=raw.get("title", "").strip(),
            url=raw.get("url", "").strip(),
            author=raw.get("author", "").strip(),
            published_at=raw.get("published_at"),
            summary=raw.get("summary", "").strip(),
            content=raw.get("content", "").strip(),
            lang=self.cfg.get("lang", "zh"),
            comment_adapter=self.cfg.get("comment_adapter"),
        )
