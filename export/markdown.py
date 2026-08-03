"""将筛选结果导出为 Markdown 文档（含摘要 / 标签 / 评论）。"""
from __future__ import annotations

from datetime import datetime

from store import db

_SENT_LABEL = {"pos": "😊 正面", "neg": "😟 负面", "neu": "😐 中性"}


def export_markdown(articles: list, title: str = "体育新闻精选", with_comments: bool = True) -> str:
    lines = [f"# {title}", "", f"> 导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}　共 {len(articles)} 条", ""]
    # 标签云汇总
    tags = {}
    for a in articles:
        for t in (a.sport_tags or []):
            tags[t] = tags.get(t, 0) + 1
    if tags:
        top = sorted(tags.items(), key=lambda x: -x[1])[:12]
        lines.append("**热门运动：** " + " · ".join(f"{k}({v})" for k, v in top))
        lines.append("")
    for i, a in enumerate(articles, 1):
        ts = a.published_at.strftime("%Y-%m-%d %H:%M") if a.published_at else "未知时间"
        lines.append(f"## {i}. {a.title}")
        meta = [f"来源：{a.source_name}", f"时间：{ts}"]
        if a.sport_tags:
            meta.append("运动：" + "、".join(a.sport_tags))
        if a.sentiment:
            meta.append("情感：" + _SENT_LABEL.get(a.sentiment, a.sentiment))
        lines.append(" | ".join(meta))
        lines.append("")
        if a.summary:
            lines.append(f"> **摘要**：{a.summary}")
            lines.append("")
        if a.entity_tags:
            lines.append("**相关**：" + "、".join(a.entity_tags))
            lines.append("")
        body = a.content or ""
        if body:
            lines.append(body[:1500] + ("…" if len(body) > 1500 else ""))
            lines.append("")
        lines.append(f"[查看原文]({a.url})")
        if with_comments and a.id:
            comments = db.get_comments(a.id)
            if comments:
                lines.append("")
                lines.append(f"**💬 评论（{len(comments)}）**")
                for c in comments[:15]:
                    lines.append(f"- {c.content} — _{c.author} · 👍{c.likes}_")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)
