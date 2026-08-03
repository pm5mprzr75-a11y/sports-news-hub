"""SQLite 存储层：文章 / 评论 / 关键词 / 抓取记录 + FTS5 全文索引。"""
import json
import os
import sqlite3
from datetime import datetime, timedelta

from store.models import Article, Comment

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "sports_news.db")

# ---------------------------------------------------------------------------
# 初始化
# ---------------------------------------------------------------------------
def get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT,
            source_name TEXT,
            title TEXT,
            url TEXT UNIQUE,
            author TEXT,
            published_at TEXT,
            summary TEXT,
            content TEXT,
            category_tags TEXT,
            matched_keywords TEXT,
            sport_tags TEXT,
            lang TEXT,
            comment_adapter TEXT,
            has_comments INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            fetched_at TEXT
        );
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            article_id INTEGER,
            author TEXT,
            content TEXT,
            published_at TEXT,
            likes INTEGER DEFAULT 0,
            source TEXT,
            fetched_at TEXT,
            FOREIGN KEY(article_id) REFERENCES articles(id)
        );
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            term TEXT,
            user_added INTEGER DEFAULT 0,
            UNIQUE(category, term)
        );
        CREATE TABLE IF NOT EXISTS crawl_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT,
            finished_at TEXT,
            source_id TEXT,
            fetched INTEGER DEFAULT 0,
            status TEXT,
            total INTEGER DEFAULT 0,
            duration_ms INTEGER DEFAULT 0,
            error TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_articles_src ON articles(source_id);
        CREATE INDEX IF NOT EXISTS idx_articles_pub ON articles(published_at);
        CREATE INDEX IF NOT EXISTS idx_comments_art ON comments(article_id);
        """
    )
    # 兼容旧库：缺失 sport_tags / entity_tags 列时补齐（幂等迁移）
    cur.execute("PRAGMA table_info(articles)")
    cols = {r[1] for r in cur.fetchall()}
    if "sport_tags" not in cols:
        cur.execute("ALTER TABLE articles ADD COLUMN sport_tags TEXT;")
    if "entity_tags" not in cols:
        cur.execute("ALTER TABLE articles ADD COLUMN entity_tags TEXT;")
    if "image_url" not in cols:
        cur.execute("ALTER TABLE articles ADD COLUMN image_url TEXT DEFAULT '';")
    if "sentiment" not in cols:
        cur.execute("ALTER TABLE articles ADD COLUMN sentiment TEXT DEFAULT 'neu';")
    if "sentiment_score" not in cols:
        cur.execute("ALTER TABLE articles ADD COLUMN sentiment_score REAL DEFAULT 0.5;")
    if "kw_tags" not in cols:
        cur.execute("ALTER TABLE articles ADD COLUMN kw_tags TEXT;")
    # 兼容旧库：crawl_runs 可能缺少部分列（幂等迁移，避免 log_crawl_run 写入时崩）
    cur.execute("PRAGMA table_info(crawl_runs)")
    cr_cols = {r[1] for r in cur.fetchall()}
    expected_cr = {
        "started_at": "TEXT",
        "finished_at": "TEXT",
        "source_id": "TEXT",
        "fetched": "INTEGER DEFAULT 0",
        "status": "TEXT",
        "total": "INTEGER DEFAULT 0",
        "duration_ms": "INTEGER DEFAULT 0",
        "error": "TEXT",
    }
    for col, typ in expected_cr.items():
        if col not in cr_cols:
            cur.execute(f"ALTER TABLE crawl_runs ADD COLUMN {col} {typ};")
    # FTS5 全文索引（外部内容表，关联 articles.id）
    cur.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts
        USING fts5(title, summary, content, content='articles', content_rowid='id');
        """
    )
    # 触发器保持 FTS 同步
    cur.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS articles_ai AFTER INSERT ON articles BEGIN
            INSERT INTO articles_fts(rowid, title, summary, content)
            VALUES (new.id, new.title, new.summary, new.content);
        END;
        CREATE TRIGGER IF NOT EXISTS articles_ad AFTER DELETE ON articles BEGIN
            INSERT INTO articles_fts(articles_fts, rowid, title, summary, content)
            VALUES('delete', old.id, old.title, old.summary, old.content);
        END;
        CREATE TRIGGER IF NOT EXISTS articles_au AFTER UPDATE ON articles BEGIN
            INSERT INTO articles_fts(articles_fts, rowid, title, summary, content)
            VALUES('delete', old.id, old.title, old.summary, old.content);
            INSERT INTO articles_fts(rowid, title, summary, content)
            VALUES (new.id, new.title, new.summary, new.content);
        END;
        """
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# 文章
# ---------------------------------------------------------------------------
def upsert_article(a: Article) -> int:
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    pub = a.published_at.isoformat(timespec="seconds") if a.published_at else None
    cur.execute(
        """
        INSERT INTO articles
          (source_id, source_name, title, url, author, published_at, summary, content,
           category_tags, matched_keywords, sport_tags, entity_tags, image_url, sentiment,
           sentiment_score, kw_tags, lang, comment_adapter, has_comments, comment_count, fetched_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(url) DO UPDATE SET
          source_name=excluded.source_name, title=excluded.title, author=excluded.author,
          published_at=excluded.published_at, summary=excluded.summary, content=excluded.content,
          category_tags=excluded.category_tags, matched_keywords=excluded.matched_keywords,
          sport_tags=excluded.sport_tags, entity_tags=excluded.entity_tags,
          image_url=COALESCE(NULLIF(excluded.image_url,''), articles.image_url),
          sentiment=excluded.sentiment, sentiment_score=excluded.sentiment_score,
          kw_tags=excluded.kw_tags,
          comment_adapter=excluded.comment_adapter, comment_count=excluded.comment_count,
          fetched_at=excluded.fetched_at
        """,
        (
            a.source_id, a.source_name, a.title, a.url, a.author, pub, a.summary, a.content,
            json.dumps(a.category_tags, ensure_ascii=False),
            json.dumps(a.matched_keywords, ensure_ascii=False),
            json.dumps(a.sport_tags, ensure_ascii=False),
            json.dumps(a.entity_tags, ensure_ascii=False),
            a.image_url or "",
            a.sentiment or "neu",
            a.sentiment_score if a.sentiment_score is not None else 0.5,
            json.dumps(a.kw_tags, ensure_ascii=False),
            a.lang, a.comment_adapter, 1 if a.comment_count > 0 else 0,
            a.comment_count, now,
        ),
    )
    if a.id is None:
        cur.execute("SELECT id FROM articles WHERE url=?", (a.url,))
        a.id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return a.id


def get_article(article_id: int) -> Article:
    conn = get_conn()
    row = conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
    conn.close()
    return _row_to_article(row)


def _row_to_article(row) -> Article:
    return Article(
        id=row["id"],
        source_id=row["source_id"],
        source_name=row["source_name"],
        title=row["title"],
        url=row["url"],
        author=row["author"] or "",
        published_at=datetime.fromisoformat(row["published_at"]) if row["published_at"] else None,
        summary=row["summary"] or "",
        content=row["content"] or "",
        category_tags=json.loads(row["category_tags"] or "[]"),
        matched_keywords=json.loads(row["matched_keywords"] or "[]"),
        sport_tags=json.loads(row["sport_tags"] or "[]"),
        entity_tags=json.loads(row["entity_tags"] or "[]"),
        image_url=row["image_url"] or "",
        sentiment=row["sentiment"] or "neu",
        sentiment_score=row["sentiment_score"] if row["sentiment_score"] is not None else 0.5,
        kw_tags=json.loads(row["kw_tags"] or "[]"),
        lang=row["lang"] or "zh",
        comment_adapter=row["comment_adapter"],
        has_comments=bool(row["has_comments"]),
        comment_count=row["comment_count"] or 0,
        fetched_at=datetime.fromisoformat(row["fetched_at"]) if row["fetched_at"] else None,
    )


def article_exists(url: str) -> bool:
    conn = get_conn()
    r = conn.execute("SELECT 1 FROM articles WHERE url=?", (url,)).fetchone()
    conn.close()
    return r is not None


def query_articles(days: int = 7, sources: list = None, categories: list = None,
                   sports: list = None, entities: list = None, text: str = "",
                   only_comments: bool = False, sentiment: list = None, limit: int = 500) -> list:
    conn = get_conn()
    wheres, params = [], []
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    wheres.append("(published_at >= ? OR published_at IS NULL)")
    params.append(cutoff)
    if sources:
        ph = ",".join("?" * len(sources))
        wheres.append(f"source_id IN ({ph})")
        params += sources
    if categories:
        ors = " OR ".join(["EXISTS(SELECT 1 FROM json_each(category_tags) WHERE value=?)"] * len(categories))
        wheres.append("(" + ors + ")")
        params += categories
    if sports:
        ors = " OR ".join(["EXISTS(SELECT 1 FROM json_each(sport_tags) WHERE value=?)"] * len(sports))
        wheres.append("(" + ors + ")")
        params += sports
    if entities:
        ors = " OR ".join(["EXISTS(SELECT 1 FROM json_each(entity_tags) WHERE value=?)"] * len(entities))
        wheres.append("(" + ors + ")")
        params += entities
    if only_comments:
        wheres.append("comment_count > 0")
    if sentiment:
        ph = ",".join("?" * len(sentiment))
        wheres.append(f"sentiment IN ({ph})")
        params += sentiment
    if text:
        wheres.append("(title LIKE ? OR summary LIKE ? OR content LIKE ?)")
        like = f"%{text}%"
        params += [like, like, like]
    sql = (
        "SELECT * FROM articles WHERE " + " AND ".join(wheres)
        + " ORDER BY (CASE WHEN published_at IS NULL THEN 1 ELSE 0 END), published_at DESC LIMIT ?"
    )
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_article(r) for r in rows]


def get_sources_status() -> list:
    """返回各 source 的文章数与最近抓取时间。"""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT source_id, source_name, COUNT(*) AS cnt,
               MAX(published_at) AS latest,
               SUM(comment_count) AS comments
        FROM articles GROUP BY source_id, source_name
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_overview() -> dict:
    """返回总览统计：总数 / 有评论数 / 评论总数，以及运动、实体、分类的分布。"""
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*), SUM(comment_count), "
                         "SUM(CASE WHEN comment_count>0 THEN 1 ELSE 0 END) FROM articles").fetchone()
    def dist(col: str) -> dict:
        rows = conn.execute(
            f"SELECT value, COUNT(*) c FROM articles, json_each({col}) GROUP BY value ORDER BY c DESC"
        ).fetchall()
        return {r["value"]: r["c"] for r in rows}
    out = {
        "total": total[0] or 0,
        "comments_total": total[1] or 0,
        "with_comments": total[2] or 0,
        "sports": dist("sport_tags"),
        "entities": dist("entity_tags"),
        "categories": dist("category_tags"),
    }
    conn.close()
    return out


def get_last_crawl() -> dict:
    """返回最近一次抓取记录（用于总览展示定时任务是否在跑）。"""
    conn = get_conn()
    r = conn.execute(
        "SELECT started_at, source_id, fetched, status, duration_ms, total FROM crawl_runs "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(r) if r else {}


def get_crawl_stats(limit: int = 20) -> dict:
    """抓取状态面板数据：最近若干次抓取 + 成功/失败汇总 + 平均耗时。"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT started_at, finished_at, source_id, fetched, status, total, duration_ms, error "
        "FROM crawl_runs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    runs = [dict(r) for r in rows]
    ok = sum(1 for r in runs if r["status"] == "ok")
    fail = sum(1 for r in runs if r["status"] and r["status"] != "ok")
    durs = [r["duration_ms"] for r in runs if r["duration_ms"]]
    avg_dur = int(sum(durs) / len(durs)) if durs else 0
    conn.close()
    return {"runs": runs, "ok": ok, "fail": fail, "avg_duration_ms": avg_dur}


def get_daily_counts(days: int = 7) -> dict:
    """近 N 天每天的文章数（按发布日期分组），用于热度折线图。"""
    conn = get_conn()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    rows = conn.execute(
        "SELECT substr(published_at,1,10) AS d, COUNT(*) c FROM articles "
        "WHERE published_at >= ? GROUP BY d ORDER BY d", (cutoff,)
    ).fetchall()
    conn.close()
    return {r["d"]: r["c"] for r in rows}


def get_daily_sport_counts(days: int = 7, sports: list = None) -> dict:
    """近 N 天，各运动的日发布量（堆叠柱状图）。返回 {sport: {date: count}}。"""
    conn = get_conn()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    sports_clause = ""
    params = [cutoff]
    if sports:
        ph = ",".join("?" * len(sports))
        sports_clause = f"AND EXISTS(SELECT 1 FROM json_each(sport_tags) WHERE value IN ({ph}))"
        params += sports
    rows = conn.execute(
        f"SELECT substr(published_at,1,10) AS d, value AS sport FROM articles, "
        f"json_each(sport_tags) WHERE published_at >= ? {sports_clause}",
        params,
    ).fetchall()
    conn.close()
    out: dict = {}
    for r in rows:
        out.setdefault(r["sport"], {})[r["d"]] = out.get(r["sport"], {}).get(r["d"], 0) + 1
    return out


def get_keyword_freq(days: int = 7, sports: list = None, top_k: int = 40) -> dict:
    """聚合文章智能关键词，返回 {词: 频次}（用于词云）。"""
    conn = get_conn()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    sports_clause = ""
    params = [cutoff]
    if sports:
        ph = ",".join("?" * len(sports))
        sports_clause = f"AND EXISTS(SELECT 1 FROM json_each(sport_tags) WHERE value IN ({ph}))"
        params += sports
    rows = conn.execute(
        f"SELECT kw_tags FROM articles WHERE published_at >= ? {sports_clause}", params
    ).fetchall()
    conn.close()
    from collections import Counter
    freq = Counter()
    for r in rows:
        try:
            tags = json.loads(r["kw_tags"] or "[]")
        except Exception:
            tags = []
        for t in tags:
            if t:
                freq[t] += 1
    return dict(freq.most_common(top_k))


def get_sentiment_dist(days: int = 7) -> dict:
    conn = get_conn()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    rows = conn.execute(
        "SELECT sentiment, COUNT(*) c FROM articles WHERE published_at >= ? GROUP BY sentiment",
        (cutoff,),
    ).fetchall()
    conn.close()
    return {r["sentiment"]: r["c"] for r in rows}


# ---------------------------------------------------------------------------
# 评论
# ---------------------------------------------------------------------------
def insert_comments(comments: list, article_id: int) -> int:
    if not comments:
        return 0
    conn = get_conn()
    now = datetime.now().isoformat(timespec="seconds")
    rows = []
    for c in comments:
        pub = c.published_at.isoformat(timespec="seconds") if c.published_at else None
        rows.append((article_id, c.author, c.content, pub, c.likes, c.source, now))
    conn.executemany(
        """
        INSERT INTO comments (article_id, author, content, published_at, likes, source, fetched_at)
        VALUES (?,?,?,?,?,?,?)
        """,
        rows,
    )
    conn.execute("UPDATE articles SET has_comments=1, comment_count=? WHERE id=?",
                 (len(comments), article_id))
    conn.commit()
    conn.close()
    return len(comments)


def get_comments(article_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM comments WHERE article_id=? ORDER BY likes DESC, published_at DESC",
        (article_id,),
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        out.append(Comment(
            id=r["id"], article_id=r["article_id"], author=r["author"], content=r["content"],
            published_at=datetime.fromisoformat(r["published_at"]) if r["published_at"] else None,
            likes=r["likes"], source=r["source"],
            fetched_at=datetime.fromisoformat(r["fetched_at"]) if r["fetched_at"] else None,
        ))
    return out


def get_comment_count(article_id: int) -> int:
    conn = get_conn()
    r = conn.execute("SELECT comment_count FROM articles WHERE id=?", (article_id,)).fetchone()
    conn.close()
    return r["comment_count"] if r else 0


# ---------------------------------------------------------------------------
# 关键词
# ---------------------------------------------------------------------------
def load_preset_keywords(cat_dict: dict) -> None:
    """将 config/keywords.yaml 的分类词典写入 keywords 表（user_added=0）。"""
    conn = get_conn()
    for cat, terms in cat_dict.items():
        for t in terms:
            conn.execute(
                "INSERT OR IGNORE INTO keywords(category, term, user_added) VALUES(?,?,0)",
                (cat, t),
            )
    conn.commit()
    conn.close()


def add_custom_keyword(term: str, category: str = "自定义") -> None:
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO keywords(category, term, user_added) VALUES(?,?,1)",
        (category, term.strip()),
    )
    conn.commit()
    conn.close()


def get_all_keywords() -> dict:
    conn = get_conn()
    rows = conn.execute("SELECT category, term, user_added FROM keywords").fetchall()
    conn.close()
    out = {}
    for r in rows:
        out.setdefault(r["category"], []).append(r["term"])
    return out


def get_keyword_terms(user_only: bool = False) -> list:
    conn = get_conn()
    if user_only:
        rows = conn.execute("SELECT term FROM keywords WHERE user_added=1").fetchall()
    else:
        rows = conn.execute("SELECT term FROM keywords").fetchall()
    conn.close()
    return [r["term"] for r in rows]


# ---------------------------------------------------------------------------
# 抓取记录
# ---------------------------------------------------------------------------
def log_crawl_run(source_id: str, fetched: int, status: str, total: int = 0,
                  duration_ms: int = 0, error: str = "", started_at: str = None,
                  finished_at: str = None) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO crawl_runs(started_at, finished_at, source_id, fetched, status, total, duration_ms, error) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (started_at or datetime.now().isoformat(timespec="seconds"),
         finished_at or datetime.now().isoformat(timespec="seconds"),
         source_id, fetched, status, total, duration_ms, error),
    )
    conn.commit()
    conn.close()
