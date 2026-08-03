"""站点注册表与抓取编排：加载 sources.yaml -> 分发适配器 -> 过滤/打标/入库/评论。"""
import os
import json
from datetime import datetime, timedelta

import yaml
import time

from crawlers.comments import fetch_comments
from crawlers.html_adapter import HtmlAdapter
from crawlers.json_api_adapter import JsonApiAdapter
from crawlers.rss_adapter import RssAdapter
from crawlers.tieba_adapter import TiebaAdapter
from crawlers.weibo_adapter import WeiboAdapter
from nlp.keyword_matcher import KeywordMatcher
from nlp import textproc as tp
from store import db

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
SOURCES_YAML = os.path.join(CONFIG_DIR, "sources.yaml")
KEYWORDS_YAML = os.path.join(CONFIG_DIR, "keywords.yaml")


def load_sources() -> list:
    with open(SOURCES_YAML, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["sources"]


def load_keyword_dict() -> dict:
    with open(KEYWORDS_YAML, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["categories"]


def build_adapter(cfg):
    t = cfg.get("type")
    if t == "rss":
        return RssAdapter(cfg)
    if t == "json_api":
        return JsonApiAdapter(cfg)
    if t == "html":
        return HtmlAdapter(cfg)
    if t == "weibo":
        return WeiboAdapter(cfg)
    if t == "tieba":
        return TiebaAdapter(cfg)
    # selenium 类源在 v1 默认关闭，且需额外依赖，这里返回 None
    return None


def run_crawl(days: int = 7, source_ids: list = None, with_comments: bool = True) -> dict:
    """执行抓取。返回 {source_id: {fetched, status}}。"""
    db.init_db()
    # 预置关键词入库
    db.load_preset_keywords(load_keyword_dict())
    matcher = KeywordMatcher()

    sources = [s for s in load_sources() if s.get("enabled")]
    if source_ids:
        sources = [s for s in sources if s["id"] in source_ids]

    cutoff = datetime.now() - timedelta(days=days)
    report = {}
    for cfg in sources:
        adapter = build_adapter(cfg)
        if adapter is None:
            report[cfg["id"]] = {"fetched": 0, "status": "skipped(no adapter)"}
            continue
        t0 = time.time()
        try:
            raw = adapter.fetch_since(days)
        except Exception as e:
            dur = int((time.time() - t0) * 1000)
            db.log_crawl_run(cfg["id"], 0, f"error:{str(e)[:120]}", total=0,
                             duration_ms=dur, error=str(e)[:200])
            report[cfg["id"]] = {"fetched": 0, "status": f"error:{str(e)[:120]}"}
            continue

        kept = []
        for a in raw:
            if a.published_at and a.published_at < cutoff:
                continue
            cats, kws = matcher.match(a.text())
            a.category_tags = cats
            a.matched_keywords = kws
            a.sport_tags = matcher.sport_tags_for(a.text())
            a.entity_tags = matcher.entity_tags_for(a.text())
            # 智能文本处理：摘要 / 情感 / 关键词
            try:
                info = tp.analyze(a.text())
                a.summary = info["summary"] or a.summary
                a.sentiment = info["sentiment"]["label"]
                a.sentiment_score = info["sentiment"]["score"]
                a.kw_tags = info["keywords"]
            except Exception:
                pass
            aid = db.upsert_article(a)
            a.id = aid
            kept.append(a)

        # best-effort 评论抓取（限制数量，避免过慢）
        if with_comments and cfg.get("comment_adapter"):
            for a in kept[:30]:
                if db.get_comment_count(a.id) == 0:
                    comments = fetch_comments(a)
                    if comments:
                        for c in comments:
                            c.article_id = a.id
                        db.insert_comments(comments, a.id)

        dur = int((time.time() - t0) * 1000)
        db.log_crawl_run(cfg["id"], len(kept), "ok", total=len(raw),
                         duration_ms=dur, started_at=datetime.now().isoformat(timespec="seconds"))
        report[cfg["id"]] = {"fetched": len(kept), "status": "ok"}
    return report


def retag_all() -> int:
    """用当前关键词（含用户自定义）与运动分类重新为全部文章打标。"""
    db.load_preset_keywords(load_keyword_dict())
    matcher = KeywordMatcher()
    conn = db.get_conn()
    rows = conn.execute("SELECT id, title, summary, content FROM articles").fetchall()
    n = 0
    for r in rows:
        text = f"{r['title']} {r['summary'] or ''} {r['content'] or ''}"
        cats, kws = matcher.match(text)
        sports = matcher.sport_tags_for(text)
        entities = matcher.entity_tags_for(text)
        sent_label, sent_score, kwtags = "neu", 0.5, []
        try:
            info = tp.analyze(text)
            sent_label = info["sentiment"]["label"]
            sent_score = info["sentiment"]["score"]
            kwtags = info["keywords"]
        except Exception:
            pass
        conn.execute(
            "UPDATE articles SET category_tags=?, matched_keywords=?, sport_tags=?, entity_tags=?, "
            "sentiment=?, sentiment_score=?, kw_tags=? WHERE id=?",
            (json.dumps(cats, ensure_ascii=False), json.dumps(kws, ensure_ascii=False),
             json.dumps(sports, ensure_ascii=False), json.dumps(entities, ensure_ascii=False),
             sent_label, sent_score, json.dumps(kwtags, ensure_ascii=False), r["id"]),
        )
        n += 1
    conn.commit()
    conn.close()
    return n


def enrich_content(article):
    from crawlers.content import extract_from_html
    import requests
    try:
        r = requests.get(article.url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code == 200 and len(r.text) > 500:
            d = extract_from_html(r.text, article.url)
            if d.get("content"):
                article.content = d["content"]
                conn = db.get_conn()
                conn.execute("UPDATE articles SET content=? WHERE id=?", (d["content"], article.id))
                conn.commit()
                conn.close()
    except Exception:
        pass
    return article
