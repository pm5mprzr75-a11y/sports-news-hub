"""体育新闻聚合 · 筛选 · 评论 · 导出  Web 应用（Streamlit）。"""
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from crawlers import registry  # noqa: E402
from crawlers.comments import fetch_comments  # noqa: E402
from export import excel as ex  # noqa: E402
from export import pdf as pdf_mod  # noqa: E402
from nlp.keyword_matcher import KeywordMatcher  # noqa: E402
from store import db  # noqa: E402

st.set_page_config(page_title="体育新闻聚合器", layout="wide")
DB = db


def ensure_init():
    DB.init_db()
    DB.load_preset_keywords(registry.load_keyword_dict())


def chip(text, color="#1F4E78"):
    return f'<span style="background:{color};color:#fff;padding:1px 7px;border-radius:10px;font-size:11px;margin-right:4px;">{text}</span>'


def main():
    ensure_init()
    matcher = KeywordMatcher()

    st.title("🏟️ 体育新闻聚合 · 筛选 · 评论")
    st.caption("抓取主流体育媒体近 7 天内容，按体育产业关键词筛选，支持评论查看与报告导出。")

    with st.sidebar:
        st.header("🔎 筛选条件")
        days = st.selectbox("时间范围", [1, 3, 7, 14, 30], index=2,
                            format_func=lambda x: f"近 {x} 天")
        all_sources = registry.load_sources()
        src_options = {s["id"]: s["name"] for s in all_sources}
        sources = st.multiselect("来源", options=list(src_options.keys()),
                                 format_func=lambda x: src_options[x], default=list(src_options.keys()))
        categories = matcher.categories()
        sel_cats = st.multiselect("关键词分类", options=categories, default=[])
        sports = matcher.sports()
        sel_sports = st.multiselect("🏀 运动项目", options=sports, default=[],
                                    help="按运动项目筛选（篮球/足球/跑步/健身/电竞…），社交平台内容按此维度检索")
        # 二级标签（联赛/球队/明星）分组筛选
        ent_by_sport = matcher.entities_by_sport()
        ent_lookup = {}
        ent_options = []
        for sp, ents in ent_by_sport.items():
            for e in ents:
                disp = f"{sp} › {e}"
                ent_options.append(disp)
                ent_lookup[disp] = e
        sel_entity_disp = st.multiselect("🎯 二级标签（联赛/球队/明星）", options=ent_options, default=[],
                                         help="在运动项目下进一步精确到联赛 / 球队 / 明星，如 篮球 › 湖人")
        sel_entities = [ent_lookup[d] for d in sel_entity_disp]
        text = st.text_input("关键词搜索（标题/正文，支持中文）", "")
        only_comments = st.checkbox("仅看有评论")
        show_overview = st.checkbox("📊 显示数据总览", value=True)

        st.divider()
        st.subheader("➕ 自定义关键词")
        new_kw = st.text_input("输入关键词后点添加（归入「自定义」分类）", "")
        if st.button("添加自定义关键词", use_container_width=True) and new_kw.strip():
            DB.add_custom_keyword(new_kw.strip())
            matcher.reload()
            st.success(f"已添加：{new_kw.strip()}")
            st.rerun()
        if st.button("重新打标全部文章", use_container_width=True):
            with st.spinner("重新打标中…"):
                registry.retag_all()
            st.success("已用最新关键词重新打标")
            st.rerun()

        st.divider()
        if st.button("🔄 重新抓取（近 %d 天）" % days, use_container_width=True):
            with st.spinner("正在抓取各媒体，请稍候（首次可能需数分钟）…"):
                report = registry.run_crawl(days=days)
            ok = sum(1 for v in report.values() if v["status"] == "ok")
            st.success(f"抓取完成：{ok}/{len(report)} 个源成功")
            st.rerun()

    # ---- 查询 ----
    articles = DB.query_articles(days=days, sources=sources or None,
                                 categories=sel_cats or None,
                                 sports=sel_sports or None,
                                 entities=sel_entities or None, text=text,
                                 only_comments=only_comments, limit=600)

    # ---- 数据总览面板 ----
    if show_overview:
        ov = DB.get_overview()
        src_status = DB.get_sources_status()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("文章总数", ov["total"])
        m2.metric("来源数", len(src_status))
        m3.metric("有评论文章", ov["with_comments"])
        m4.metric("评论总数", ov["comments_total"])
        last = DB.get_last_crawl()
        if last:
            st.caption(f"⏱️ 上次抓取：{last.get('started_at','?')}　状态：{last.get('status')}　新增：{last.get('fetched')} 条")
        else:
            st.caption("⏱️ 尚未抓取过（点击左侧「重新抓取」按钮，或等待每日定时任务）")
        oa, ob = st.columns(2)
        with oa:
            st.subheader("🏀 按运动项目")
            if ov["sports"]:
                st.bar_chart(ov["sports"])
            else:
                st.caption("暂无数据")
        with ob:
            st.subheader("🎯 按二级标签（联赛/球队/明星）")
            if ov["entities"]:
                st.bar_chart(ov["entities"])
            else:
                st.caption("暂无数据")
        with st.expander("📑 来源 / 分类分布明细"):
            st.write("**按来源**")
            st.bar_chart({s["source_name"]: s["cnt"] for s in src_status})
            if ov["categories"]:
                st.write("**按产业分类**")
                st.bar_chart(ov["categories"])
        st.divider()

    st.write(f"**命中 {len(articles)} 条**　|　"
             f"来源覆盖：{len(set(a.source_id for a in articles))} 个")

    if not articles:
        st.info("当前筛选无结果。可放宽时间范围/来源，或点击左侧「重新抓取」。"
                "若刚部署，请先抓取数据。")
        return

    # 列表 + 详情
    for a in articles:
        time_str = a.published_at.strftime("%m-%d %H:%M") if a.published_at else "未知"
        head = f"**{a.title}**"
        with st.expander(f"{head}  \n`{a.source_name}` · {time_str} · 💬{a.comment_count}"):
            if a.category_tags:
                st.markdown("".join(chip(c) for c in a.category_tags), unsafe_allow_html=True)
            if a.sport_tags:
                st.markdown("".join(chip(s, color="#C0504D") for s in a.sport_tags),
                            unsafe_allow_html=True)
            if a.entity_tags:
                st.markdown("".join(chip(e, color="#806000") for e in a.entity_tags),
                            unsafe_allow_html=True)
            if a.summary:
                st.write(a.summary)
            body = a.content or a.summary
            if body and len(body) > 200:
                st.write(body[:800] + ("…" if len(body) > 800 else ""))
            st.markdown(f"[查看原文]({a.url})", unsafe_allow_html=True)

            # 评论
            st.divider()
            st.write("💬 **评论**")
            comments = DB.get_comments(a.id) if a.id else []
            if comments:
                for c in comments[:30]:
                    cs = c.published_at.strftime("%m-%d %H:%M") if c.published_at else ""
                    st.markdown(f"> {c.content}  \n> *— {c.author} · 👍{c.likes} · {cs}*")
            elif a.comment_adapter:
                if st.button(f"抓取本条评论（{a.comment_adapter}）", key=f"c_{a.id}"):
                    with st.spinner("抓取评论中…"):
                        cs = fetch_comments(a)
                        if cs:
                            for c in cs:
                                c.article_id = a.id
                            DB.insert_comments(cs, a.id)
                    st.rerun()
                else:
                    st.caption("暂无评论 / 尚未抓取")
            else:
                st.caption("该来源暂不支持评论抓取")

    # ---- 导出 ----
    st.divider()
    st.subheader("📤 导出当前筛选结果")
    st.caption("Excel/PDF 已包含「评论明细」；也可单独导出评论 Excel/CSV。")
    c1, c2, c3 = st.columns(3)
    if c1.button("导出 Excel（含评论）", use_container_width=True):
        p = ex.export_excel(articles, "sports_news.xlsx")
        st.success(f"已生成：{p}")
    if c2.button("导出 CSV", use_container_width=True):
        p = ex.export_csv(articles, "sports_news.csv")
        st.success(f"已生成：{p}")
    if c3.button("导出 PDF（含评论）", use_container_width=True):
        p = pdf_mod.export_pdf(articles, "sports_news.pdf")
        st.success(f"已生成：{p}")

    st.subheader("💬 单独导出评论")
    cc1, cc2 = st.columns(2)
    if cc1.button("导出评论 Excel", use_container_width=True):
        p = ex.export_comments_excel(articles, "sports_comments.xlsx")
        st.success(f"已生成：{p}")
    if cc2.button("导出评论 CSV", use_container_width=True):
        p = ex.export_comments_csv(articles, "sports_comments.csv")
        st.success(f"已生成：{p}")

    st.caption("导出文件位于项目 exports/ 目录；也可在终端用 `python scheduler/run_crawl.py` 定时抓取。")


if __name__ == "__main__":
    main()
