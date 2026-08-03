"""静态站点数据导出：读取 SQLite，生成 docs/data.json 供纯前端消费。

运行：python build_site.py
输出：docs/data.json（articles 列表 + 各类统计）
GitHub Pages 前端（docs/index.html）加载该 JSON 渲染全部内容。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from store import db

ROOT = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(ROOT, "docs")
os.makedirs(DOCS, exist_ok=True)

RECENT_DAYS = 30          # 统计时间窗（热度/情感/词云）
MAX_ARTICLES = 2000       # 导出文章上限（控制 data.json 体积）


def _to_record(a) -> dict:
    return {
        "id": a.id,
        "title": a.title,
        "url": a.url,
        "source_name": a.source_name or "",
        "source_id": a.source_id or "",
        "published_at": a.published_at.isoformat(timespec="seconds") if a.published_at else "",
        "summary": a.summary or "",
        "sport_tags": a.sport_tags or [],
        "category_tags": a.category_tags or [],
        "entity_tags": a.entity_tags or [],
        "kw_tags": a.kw_tags or [],
        "sentiment": a.sentiment or "neu",
        "sentiment_score": a.sentiment_score if a.sentiment_score is not None else 0.5,
        "image_url": a.image_url or "",
        "comment_count": a.comment_count or 0,
    }


def build() -> dict:
    db.init_db()

    # ---- 文章 ----
    arts = db.query_articles(days=36500, limit=MAX_ARTICLES)
    articles = [_to_record(a) for a in arts]

    # ---- 统计 ----
    src_rows = db.get_sources_status()
    source_pie = {r["source_name"]: r["cnt"] for r in src_rows}
    sentiment_pie = db.get_sentiment_dist(RECENT_DAYS)
    daily_sport = db.get_daily_sport_counts(RECENT_DAYS)
    daily_total = db.get_daily_counts(RECENT_DAYS)
    keyword_freq = db.get_keyword_freq(RECENT_DAYS, top_k=60)
    crawl_stats = db.get_crawl_stats(30)
    last_crawl = db.get_last_crawl()
    overview = db.get_overview()

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "articles": articles,
        "stats": {
            "total": overview.get("total", 0),
            "with_comments": overview.get("with_comments", 0),
            "comments_total": overview.get("comments_total", 0),
            "source_pie": source_pie,
            "sentiment_pie": sentiment_pie,
            "daily_sport": daily_sport,
            "daily_total": daily_total,
            "keyword_freq": keyword_freq,
            "crawl_stats": crawl_stats,
            "last_crawl": last_crawl,
            "sports_overview": overview.get("sports", {}),
        },
    }


def main() -> None:
    data = build()
    out_path = os.path.join(DOCS, "data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    # 确保 WAL 模式下的数据落盘到主库文件，便于提交回仓库
    try:
        conn = db.get_conn()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
    except Exception as e:
        print("[build_site] checkpoint warn:", e)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"[build_site] 文章 {len(data['articles'])} 篇 | data.json {size_kb:.1f} KB -> {out_path}")


if __name__ == "__main__":
    main()
