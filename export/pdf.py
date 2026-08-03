"""导出为 PDF 报告（reportlab，含评论）。"""
import os
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from store import db
from store.models import Article

EXPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports")
os.makedirs(EXPORT_DIR, exist_ok=True)

_styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=_styles["Title"], fontSize=18, spaceAfter=6)
SUB = ParagraphStyle("SUB", parent=_styles["Normal"], fontSize=9, textColor="#666666", spaceAfter=12)
TITLE = ParagraphStyle("TITLE", parent=_styles["Heading3"], fontSize=12, spaceBefore=8, spaceAfter=2, textColor="#1F4E78")
META = ParagraphStyle("META", parent=_styles["Normal"], fontSize=8, textColor="#888888", spaceAfter=2)
CMT = ParagraphStyle("CMT", parent=_styles["Normal"], fontSize=8.5, leading=12, leftIndent=10, textColor="#333333", spaceAfter=1)
BODY = ParagraphStyle("BODY", parent=_styles["Normal"], fontSize=9, leading=13, spaceAfter=10)


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def export_pdf(articles: list, filename: str = "sports_news.pdf", max_items: int = 100) -> str:
    path = os.path.join(EXPORT_DIR, filename)
    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                            leftMargin=1.8 * cm, rightMargin=1.8 * cm)
    story = []
    story.append(Paragraph("体育新闻筛选报告", H1))
    story.append(Paragraph(
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}　|　共 {len(articles)} 条",
        SUB,
    ))
    for i, a in enumerate(articles[:max_items], 1):
        pub = a.published_at.strftime("%Y-%m-%d %H:%M") if a.published_at else "未知时间"
        tags = "、".join(a.category_tags) if a.category_tags else "—"
        story.append(Paragraph(f"{i}. {_esc(a.title)}", TITLE))
        story.append(Paragraph(
            f"来源：{_esc(a.source_name)} ｜ 时间：{pub} ｜ 分类：{_esc(tags)} ｜ 评论：{a.comment_count}",
            META,
        ))
        if a.summary:
            story.append(Paragraph(_esc(a.summary[:300]), BODY))
        # 评论
        if a.id:
            comments = db.get_comments(a.id)
            if comments:
                story.append(Paragraph("💬 评论：", META))
                for c in comments[:10]:
                    ct = c.published_at.strftime("%m-%d %H:%M") if c.published_at else ""
                    story.append(Paragraph(
                        f"· {_esc(c.content)} "
                        f'<font color="#888888">— {_esc(c.author or "")} · 👍{c.likes or 0} · {ct}</font>',
                        CMT,
                    ))
        story.append(Paragraph(f'<font color="#1F4E78">{_esc(a.url)}</font>', META))
        story.append(Spacer(1, 4))
    doc.build(story)
    return path
