"""评论抓取调度：按 article.comment_adapter 分发。best-effort，失败返回 []。"""
from crawlers.comments.hupu import fetch_hupu_comments
from crawlers.comments.netease import fetch_netease_comments
from crawlers.tieba_adapter import fetch_tieba_comments
from crawlers.weibo_adapter import fetch_weibo_comments
from store.models import Comment

DISPATCH = {
    "netease": fetch_netease_comments,
    "hupu": fetch_hupu_comments,
    "weibo": fetch_weibo_comments,
    "tieba": fetch_tieba_comments,
}


def fetch_comments(article) -> list:
    fn = DISPATCH.get(getattr(article, "comment_adapter", None))
    if not fn:
        return []
    try:
        return fn(article)
    except Exception:
        return []
