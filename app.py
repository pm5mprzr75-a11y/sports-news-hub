"""体育新闻聚合器 · 萌系运动风 Web 应用（Streamlit）。

功能：多源抓取 / 关键词+运动+二级标签筛选 / 智能摘要·情感·关键词 / 数据可视化
（发布量柱状·热度折线·来源饼图·情感饼图·词云）/ 收藏·历史·订阅·关键词监控 /
Markdown·Excel·PDF 导出 / 一键翻译 / 卡片式图文 / 爬虫状态面板。
"""
import os
import sys
from datetime import datetime

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analytics import viz  # noqa: E402
from crawlers import registry  # noqa: E402
from crawlers.comments import fetch_comments  # noqa: E402
from components import local_storage as ls  # noqa: E402
from export import excel as ex  # noqa: E402
from export import pdf as pdf_mod  # noqa: E402
from export import markdown as md_mod  # noqa: E402
from nlp import translate as tr  # noqa: E402
from nlp.keyword_matcher import KeywordMatcher  # noqa: E402
from store import db  # noqa: E402

st.set_page_config(page_title="🏟️ 体育情报站", page_icon="🏟️", layout="wide")
DB = db

# ---------------------------------------------------------------------------
# 萌系运动主题 CSS
# ---------------------------------------------------------------------------
THEME_CSS = """
<style>
:root{
  --pitch:#0b2545; --pitch2:#13315c; --accent:#00b4d8; --red:#ef233c;
  --green:#2a9d8f; --gold:#ffd166; --ink:#0b2545;
}
.stApp{background:linear-gradient(180deg,#0b2545 0%,#13315c 100%);}
h1,h2,h3{font-family:"PingFang SC","Microsoft YaHei",sans-serif;}
header[data-testid="stHeader"]{background:transparent;}
.block-container{padding-top:1rem;}
.stMarkdown h1{color:#eaf2ff;}
div[data-testid="stSidebar"]{background:linear-gradient(180deg,#0b2545,#102a4c);}
.stMarkdown{color:#dbe7f3;}
.kicker{font-size:13px;color:#9fb3c8;}
.tag{display:inline-block;background:#1d3a5f;color:#cfe6ff;padding:1px 8px;border-radius:12px;
  font-size:11px;margin:2px 3px 2px 0;border:1px solid #2a4d75;}
.art-card{border:1px solid #2a4d75;border-left:5px solid var(--accent);border-radius:14px;
  background:#ffffff;padding:14px 16px;margin:10px 0;box-shadow:0 4px 16px rgba(0,0,0,.32);}
.art-title{font-size:17px;font-weight:700;color:#0b2545;line-height:1.35;}
.art-meta{font-size:12px;color:#5b6b7c;margin:4px 0 6px;}
.summary-box{background:#eef4fb;border-left:4px solid var(--accent);padding:8px 10px;
  border-radius:8px;font-size:13px;color:#2a3a4a;margin:6px 0;}
.content-box{background:#f7f9fc;border:1px solid #dfe6ee;border-radius:8px;padding:10px 12px;
  font-size:13px;color:#2a3a4a;line-height:1.7;margin:6px 0;max-height:340px;overflow:auto;}
.sent-pos{background:#1b7a4b;color:#fff;} .sent-neg{background:#c1121f;color:#fff;}
.sent-neu{background:#5b6b7c;color:#fff;}
.banner{background:linear-gradient(90deg,#102a4c,#13315c);border:2px solid #00b4d8;
  border-radius:14px;padding:10px 14px;margin:10px 0;color:#cfe6ff;}
.ccard{background:#0f2a4c;border:1px solid #2a4d75;border-radius:10px;padding:8px 10px;
  font-size:13px;color:#dbe7f3;margin:4px 0;}
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)


def ensure_init():
    DB.init_db()
    DB.load_preset_keywords(registry.load_keyword_dict())


def chip(text, color="#1F4E78"):
    return f'<span class="tag" style="background:{color};color:#fff;">{text}</span>'


def sent_chip(label):
    cls = {"pos": "sent-pos", "neg": "sent-neg", "neu": "sent-neu"}.get(label, "sent-neu")
    txt = {"pos": "😊 正面", "neg": "😟 负面", "neu": "😐 中性"}.get(label, label)
    return f'<span class="tag {cls}">{txt}</span>'


SPORT_EMOJI = {
    "篮球": "🏀", "足球": "⚽", "跑步": "🏃", "健身": "💪", "游泳": "🏊", "羽毛球": "🏸",
    "乒乓球": "🏓", "网球": "🎾", "排球": "🏐", "骑行": "🚴", "滑雪": "⛷️", "瑜伽": "🧘",
    "电竞": "🎮", "登山徒步": "🥾", "钓鱼": "🎣", "格斗": "🥊", "台球": "🎱", "马拉松": "🏅",
}


def sport_emoji(name):
    return SPORT_EMOJI.get(name, "🏟️")


# ===========================================================================
def main():
    ensure_init()
    matcher = KeywordMatcher()

    # ---------------- 侧边栏：筛选 + 个性化 ----------------
    with st.sidebar:
        st.markdown("## 🏟️ 筛选台")
        days = st.selectbox("时间范围", [1, 3, 7, 14, 30], index=2,
                            format_func=lambda x: f"近 {x} 天")
        all_sources = registry.load_sources()
        src_options = {s["id"]: s["name"] for s in all_sources}
        sources = st.multiselect("来源", options=list(src_options.keys()),
                                 format_func=lambda x: src_options[x], default=list(src_options.keys()))
        categories = matcher.categories()
        sel_cats = st.multiselect("🏷️ 体育产业分类", options=categories, default=[])
        sports = matcher.sports()
        sel_sports = st.multiselect("🏀 运动项目", options=sports, default=[],
                                    help="按运动项目筛选；社交平台内容按此维度检索")
        ent_by_sport = matcher.entities_by_sport()
        ent_lookup, ent_options = {}, []
        for sp, ents in ent_by_sport.items():
            for e in ents:
                disp = f"{sp} › {e}"
                ent_options.append(disp)
                ent_lookup[disp] = e
        sel_entity_disp = st.multiselect("🎯 二级标签（联赛/球队/明星）", options=ent_options, default=[],
                                         help="运动项目下精确到联赛/球队/明星")
        sel_entities = [ent_lookup[d] for d in sel_entity_disp]
        text = st.text_input("🔍 关键词搜索（标题/正文）", "")
        only_comments = st.checkbox("仅看有评论")
        sel_sent = st.multiselect("情感倾向", options=["pos", "neg", "neu"],
                                  format_func=lambda x: {"pos": "😊 正面", "neg": "😟 负面", "neu": "😐 中性"}[x])

        st.divider()
        st.markdown("## ⭐ 我的订阅")
        apply_sub = st.checkbox("应用订阅作为默认筛选", help="勾选后，下方选择的运动/球队将自动作为筛选条件")
        sub_sports = st.multiselect("订阅运动", options=sports, default=ls.get_subs().get("sports", []))
        sub_entities = ls.get_subs().get("entities", [])
        sub_entities_default = [f"{sp} › {e}" for sp in ent_by_sport for e in ent_by_sport[sp]
                                if e in sub_entities]
        sub_entities_disp = st.multiselect("订阅球队/球星", options=ent_options, default=sub_entities_default)
        if st.button("💾 保存订阅", use_container_width=True):
            ls.set_subs(sub_sports, [ent_lookup.get(d, d.split(" › ")[-1]) for d in sub_entities_disp])
            st.success("订阅已保存（存于本浏览器）")

        st.divider()
        st.markdown("## 🔔 关键词监控")
        mon_raw = st.text_input("输入想监控的词（逗号分隔，如：湖人,梅西,世界杯）",
                                value="、".join(ls.get_monitors()))
        if st.button("保存监控词", use_container_width=True):
            words = [w.strip() for w in mon_raw.replace("，", ",").split(",") if w.strip()]
            ls.set_monitors(words)
            st.success(f"已保存 {len(words)} 个监控词")

        st.divider()
        st.markdown("## ➕ 自定义关键词")
        new_kw = st.text_input("添加关键词（归入「自定义」）", "")
        if st.button("添加", use_container_width=True) and new_kw.strip():
            DB.add_custom_keyword(new_kw.strip())
            matcher.reload()
            st.success(f"已添加：{new_kw.strip()}")
            st.rerun()
        if st.button("🧹 重新打标全部文章", use_container_width=True):
            with st.spinner("重新打标中…"):
                registry.retag_all()
            st.success("已用最新关键词重新打标")
            st.rerun()

        st.divider()
        if st.button(f"🔄 重新抓取（近 {days} 天）", use_container_width=True):
            with st.spinner("抓取各媒体中（首次可能数分钟）…"):
                report = registry.run_crawl(days=days)
            ok = sum(1 for v in report.values() if v["status"] == "ok")
            st.success(f"抓取完成：{ok}/{len(report)} 个源成功")
            st.rerun()

    # 应用订阅默认筛选
    eff_sports = sub_sports if (apply_sub and ls.get_subs().get("sports")) else sel_sports
    eff_entities = [ent_lookup.get(d) for d in sub_entities_disp] if (apply_sub and ls.get_subs().get("entities")) else sel_entities

    # ---------------- 顶部标题 ----------------
    st.markdown("# 🏟️ 体育情报站")
    st.markdown('<p class="kicker">实时聚合主流体育媒体 & 社交平台 · 智能摘要 · 情感分析 · 数据可视化 · 可编辑订阅/监控/关键词 · 一键重新抓取入库</p>',
                unsafe_allow_html=True)

    # ---------------- 关键词监控提醒 ----------------
    monitors = ls.get_monitors()
    if monitors:
        last_ts = ls.get_mon_last_ts()
        from datetime import timedelta
        mcut = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
        conn = DB.get_conn()
        ph = ",".join("?" * len(monitors))
        like_sql = " OR ".join(["(title LIKE ? OR content LIKE ?)"] * len(monitors))
        params = [mcut]
        for w in monitors:
            params += [f"%{w}%", f"%{w}%"]
        rows = conn.execute(
            f"SELECT id,title,url,published_at FROM articles WHERE published_at >= ? AND ({like_sql}) "
            f"ORDER BY published_at DESC LIMIT 50", params
        ).fetchall()
        conn.close()
        # 仅统计晚于上次查看时间的新条目
        new_items = []
        for r in rows:
            if not last_ts or (r["published_at"] or "") > last_ts:
                new_items.append(r)
        if new_items:
            st.markdown(f'<div class="banner">🔔 <b>关键词监控</b>：发现 <b>{len(new_items)}</b> 条与 '
                        f'「{", ".join(monitors)}」相关的新资讯！</div>', unsafe_allow_html=True)
            with st.expander("查看监控命中"):
                for r in new_items[:20]:
                    ts = (r["published_at"] or "")[:16]
                    st.markdown(f"- [{r['title']}]({r['url']}) <span class='kicker'>{ts}</span>",
                                unsafe_allow_html=True)
            if st.button("✅ 标记为已读"):
                ls.set_mon_last_ts(datetime.now().isoformat(timespec="seconds"))
                st.rerun()

    # ---------------- 数据可视化仪表盘 ----------------
    with st.expander("📊 数据可视化仪表盘", expanded=True):
        ov = DB.get_overview()
        src_status = DB.get_sources_status()
        last = DB.get_last_crawl()
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("📰 文章总数", ov["total"])
        m2.metric("📡 来源数", len(src_status))
        m3.metric("💬 有评论", ov["with_comments"])
        m4.metric("🔥 评论总数", ov["comments_total"])
        m5.metric("🏷️ 已打标运动", len(ov["sports"]))
        if last:
            st.caption(f"⏱️ 上次抓取：{last.get('started_at','?')}　状态：{last.get('status')}　"
                       f"新增：{last.get('fetched')} 条　耗时：{(last.get('duration_ms') or 0)//1000}s")

        st.markdown("### 📈 各运动日发布量（堆叠柱状图）")
        viz.render_sport_stacked(days, eff_sports or None)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 🔥 近 7 天新闻热度（折线）")
            viz.render_heat_line(7)
        with c2:
            st.markdown("### 🥧 来源发文占比")
            st.markdown(viz.source_pie_svg(days), unsafe_allow_html=True)

        c3, c4 = st.columns(2)
        with c3:
            st.markdown("### 💗 情感倾向分布")
            st.markdown(viz.sentiment_pie_svg(days), unsafe_allow_html=True)
        with c4:
            st.markdown("### ☁️ 热门关键词词云")
            freq = DB.get_keyword_freq(days, eff_sports or None, top_k=45)
            st.markdown(viz.keyword_wordcloud_html(freq), unsafe_allow_html=True)

    # ---------------- 查询 ----------------
    articles = DB.query_articles(days=days, sources=sources or None,
                                 categories=sel_cats or None,
                                 sports=eff_sports or None,
                                 entities=eff_entities or None, text=text,
                                 only_comments=only_comments,
                                 sentiment=sel_sent or None, limit=600)

    # 收藏 / 历史 快捷面板
    bt, ht = st.columns(2)
    with bt:
        with st.expander(f"⭐ 我的收藏（{len(ls.get_bookmarks())}）"):
            for b in ls.get_bookmarks():
                cA, cB = st.columns([5, 1])
                cA.markdown(f"- [{b['title']}]({b['url']})  \n<span class='kicker'>{b['source']}</span>",
                            unsafe_allow_html=True)
                if cB.button("取消", key=f"delbm_{b['url']}"):
                    ls.remove_bookmark(b["url"])
                    st.rerun()
    with ht:
        with st.expander(f"🕘 浏览历史（{len(ls.get_history())}）"):
            for h in ls.get_history()[:30]:
                st.markdown(f"- [{h['title']}]({h['url']})", unsafe_allow_html=True)

    st.markdown(f"**命中 {len(articles)} 条**　|　来源覆盖：{len(set(a.source_id for a in articles))} 个")

    if not articles:
        st.info("当前筛选无结果。可放宽时间/来源，或点击左侧「重新抓取」。若刚部署，请先抓取数据。")
        st.stop()

    # ---------------- 卡片列表 ----------------
    show_n = min(len(articles), 150)
    if len(articles) > show_n:
        st.caption(f"为保证流畅，展示前 {show_n} 条（共 {len(articles)} 条），可缩小范围查看其余。")
    for a in articles[:show_n]:
        time_str = a.published_at.strftime("%m-%d %H:%M") if a.published_at else "未知"
        with st.container():
            st.markdown('<div class="art-card">', unsafe_allow_html=True)
            col_img, col_body = st.columns([1, 4])
            with col_img:
                if a.image_url:
                    try:
                        st.image(a.image_url, width=140, use_container_width=True)
                    except Exception:
                        st.markdown(f"<div style='font-size:54px;text-align:center;'>{sport_emoji(a.sport_tags[0] if a.sport_tags else '')}</div>",
                                    unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='font-size:54px;text-align:center;padding-top:10px;'>{sport_emoji(a.sport_tags[0] if a.sport_tags else '')}</div>",
                                unsafe_allow_html=True)
            with col_body:
                st.markdown(f'<div class="art-title"><a href="{a.url}" target="_blank">{a.title}</a></div>',
                            unsafe_allow_html=True)
                st.markdown(f'<div class="art-meta">{a.source_name} · {time_str} · 💬{a.comment_count}</div>',
                            unsafe_allow_html=True)
                tags = ""
                for c in (a.category_tags or []):
                    tags += chip(c)
                for s in (a.sport_tags or []):
                    tags += chip(f"{sport_emoji(s)} {s}", "#C0504D")
                for e in (a.entity_tags or []):
                    tags += chip(e, "#806000")
                tags += sent_chip(a.sentiment or "neu")
                st.markdown(tags, unsafe_allow_html=True)
                if a.summary:
                    st.markdown(f'<div class="summary-box">📝 {a.summary}</div>', unsafe_allow_html=True)
                if a.content and len(a.content) > len(a.summary or ""):
                    with st.expander("📖 查看全文"):
                        st.markdown(f'<div class="content-box">{a.content}</div>', unsafe_allow_html=True)
                if a.kw_tags:
                    st.markdown("🔑 " + " ".join(chip(k, "#7E57C2") for k in a.kw_tags[:8]),
                                unsafe_allow_html=True)
            # 操作行
            bcol1, bcol2, bcol3 = st.columns([1, 1, 3])
            bm = ls.is_bookmarked(a.url)
            if bcol1.button("⭐ 取消收藏" if bm else "⭐ 收藏", key=f"bm_{a.id}"):
                if bm:
                    ls.remove_bookmark(a.url)
                else:
                    ls.add_bookmark(a)
                    ls.add_history(a)
                st.rerun()
            if bcol2.button("🌐 翻译", key=f"tr_{a.id}"):
                ls.add_history(a)
                st.session_state.setdefault("tr", {})
                st.session_state["tr"][a.id] = tr.translate_to_zh(a.content or a.summary or a.title)
                st.rerun()
            # 翻译结果
            if st.session_state.get("tr", {}).get(a.id):
                res = st.session_state["tr"][a.id]
                if res["ok"]:
                    st.info("🌐 " + res["text"])
                else:
                    st.warning("🌐 " + res["note"])
            # 评论
            with st.expander(f"💬 评论（{a.comment_count}）"):
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
                    st.caption("该来源暂不支持评论抓取")
            st.markdown("</div>", unsafe_allow_html=True)

    # ---------------- 导出 ----------------
    st.divider()
    st.markdown("## 📤 导出当前筛选结果")
    st.caption("点击后下方出现下载按钮，文件直接下载到你的设备（浏览器默认下载目录）。")
    if "dl" not in st.session_state:
        st.session_state["dl"] = {}

    def _store_dl(key, filename, mime, data: bytes):
        st.session_state["dl"][key] = (data, filename, mime)

    e1, e2, e3, e4 = st.columns(4)
    if e1.button("📊 Excel（含评论）", use_container_width=True):
        p = ex.export_excel(articles, "sports_news.xlsx")
        _store_dl("xlsx", "sports_news.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                  open(p, "rb").read())
    if e2.button("📄 CSV", use_container_width=True):
        p = ex.export_csv(articles, "sports_news.csv")
        _store_dl("csv", "sports_news.csv", "text/csv", open(p, "rb").read())
    if e3.button("📕 PDF（含评论）", use_container_width=True):
        p = pdf_mod.export_pdf(articles, "sports_news.pdf")
        _store_dl("pdf", "sports_news.pdf", "application/pdf", open(p, "rb").read())
    if e4.button("📝 Markdown", use_container_width=True):
        txt = md_mod.export_markdown(articles, title="体育资讯精选")
        _store_dl("md", "sports_news.md", "text/markdown", txt.encode("utf-8"))

    st.markdown("### 💬 单独导出评论")
    cc1, cc2 = st.columns(2)
    if cc1.button("评论 Excel", use_container_width=True):
        p = ex.export_comments_excel(articles, "sports_comments.xlsx")
        _store_dl("cxlsx", "sports_comments.xlsx",
                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", open(p, "rb").read())
    if cc2.button("评论 CSV", use_container_width=True):
        p = ex.export_comments_csv(articles, "sports_comments.csv")
        _store_dl("ccsv", "sports_comments.csv", "text/csv", open(p, "rb").read())

    for key, (data, fname, mime) in st.session_state["dl"].items():
        st.download_button(f"⬇️ 下载 {fname}", data, file_name=fname, mime=mime,
                           key=f"dlbtn_{key}", use_container_width=True)

    # ---------------- 爬虫状态面板 ----------------
    st.divider()
    with st.expander("🛠️ 爬虫状态面板"):
        stats = DB.get_crawl_stats(30)
        s1, s2, s3 = st.columns(3)
        s1.metric("✅ 成功抓取次数", stats["ok"])
        s2.metric("❌ 失败次数", stats["fail"])
        s3.metric("⏱️ 平均耗时", f"{(stats['avg_duration_ms'] or 0)//1000}s")
        rows = []
        for r in stats["runs"]:
            rows.append({
                "时间": (r["started_at"] or "")[:16],
                "来源": r["source_id"],
                "状态": r["status"],
                "入库": r["fetched"],
                "抓取总数": r["total"],
                "耗时(s)": (r["duration_ms"] or 0) // 1000,
                "错误": (r["error"] or "")[:60],
            })
        if rows:
            st.dataframe(rows, use_container_width=True)
        else:
            st.caption("暂无抓取记录")


if __name__ == "__main__":
    main()
