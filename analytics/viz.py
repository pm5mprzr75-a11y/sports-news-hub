"""数据可视化：柱状/折线（Streamlit 原生）+ 饼图/词云（SVG/HTML，无字体依赖）。"""
from __future__ import annotations

import math
from collections import OrderedDict

import pandas as pd
import streamlit as st

from store import db

# 萌系糖果配色
_PALETTE = [
    "#FF8A65", "#4FC3F7", "#FFD54F", "#81C784", "#BA68C8",
    "#F06292", "#4DB6AC", "#FFB74D", "#7986CB", "#A1887F",
    "#90A4AE", "#E57373", "#9575CD", "#4DD0E1", "#DCE775",
]


def daily_sport_dataframe(days: int = 7, sports: list = None) -> pd.DataFrame:
    """各运动近 N 天日发布量（堆叠柱状图数据源）。"""
    raw = db.get_daily_sport_counts(days, sports)
    dates = sorted({d for sp in raw.values() for d in sp})
    if not dates:
        return pd.DataFrame()
    cols = {}
    for sport, by_date in raw.items():
        cols[sport] = [by_date.get(d, 0) for d in dates]
    df = pd.DataFrame(cols, index=dates)
    df.index.name = "发布日期"
    return df


def daily_total_series(days: int = 7) -> pd.Series:
    raw = db.get_daily_counts(days)
    if not raw:
        return pd.Series(dtype=int)
    s = pd.Series(raw, name="新闻数")
    s.index.name = "发布日期"
    return s.sort_index()


def _arc(cx, cy, r, start_deg, end_deg):
    x1 = cx + r * math.cos(math.radians(start_deg))
    y1 = cy + r * math.sin(math.radians(start_deg))
    x2 = cx + r * math.cos(math.radians(end_deg))
    y2 = cy + r * math.sin(math.radians(end_deg))
    large = 1 if (end_deg - start_deg) > 180 else 0
    return f"M{cx:.1f},{cy:.1f} L{x1:.1f},{y1:.1f} A{r:.1f},{r:.1f} 0 {large},1 {x2:.1f},{y2:.1f} Z"


def pie_svg(data: dict, size: int = 280, title: str = "") -> str:
    """通用 SVG 饼图。data: {label: value}。"""
    data = {k: v for k, v in data.items() if v}
    total = sum(data.values())
    if not total:
        return f'<div style="color:#999;padding:10px;">暂无数据</div>'
    cx = cy = size / 2
    r = size / 2 - 6
    items = list(OrderedDict(sorted(data.items(), key=lambda x: -x[1])).items())
    paths, legend = [], []
    start = 0.0
    for i, (label, val) in enumerate(items):
        frac = val / total
        end = start + frac * 360
        color = _PALETTE[i % len(_PALETTE)]
        paths.append(f'<path d="{_arc(cx, cy, r, start, end)}" fill="{color}" '
                     f'stroke="#fff" stroke-width="1"><title>{label}: {val} ({frac*100:.1f}%)</title></path>')
        pct = f"{frac*100:.1f}%"
        legend.append(f'<div style="display:flex;align-items:center;margin:2px 0;">'
                      f'<span style="display:inline-block;width:12px;height:12px;border-radius:3px;'
                      f'background:{color};margin-right:6px;"></span>'
                      f'<span style="font-size:12px;color:#444;">{label} · {val} · {pct}</span></div>')
        start = end
    svg = (
        f'<div style="display:flex;flex-wrap:wrap;align-items:center;gap:14px;">'
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">{"".join(paths)}'
        f'<circle cx="{cx}" cy="{cy}" r="{r*0.42:.1f}" fill="#fff"></circle>'
        f'<text x="{cx}" y="{cy-4}" text-anchor="middle" font-size="20" fill="#333" font-weight="bold">{total}</text>'
        f'<text x="{cx}" y="{cy+16}" text-anchor="middle" font-size="11" fill="#888">{title}</text>'
        f'</svg>'
        f'<div style="min-width:150px;">{"".join(legend)}</div></div>'
    )
    return svg


def source_pie_svg(days: int = 30) -> str:
    from datetime import datetime, timedelta
    conn = db.get_conn()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    rows = conn.execute(
        "SELECT source_name, COUNT(*) c FROM articles WHERE published_at >= ? GROUP BY source_name ORDER BY c DESC",
        (cutoff,),
    ).fetchall()
    conn.close()
    data = {r["source_name"]: r["c"] for r in rows}
    return pie_svg(data, title="发文总数")


def sentiment_pie_svg(days: int = 30) -> str:
    dist = db.get_sentiment_dist(days)
    label_map = {"pos": "正面 😊", "neg": "负面 😟", "neu": "中性 😐"}
    data = {label_map.get(k, k): v for k, v in dist.items()}
    return pie_svg(data, title="情感分布")


def keyword_wordcloud_html(freq: dict, max_words: int = 45) -> str:
    """关键词词云：HTML spans，字号随词频缩放，糖果配色。"""
    if not freq:
        return '<div style="color:#999;padding:10px;">暂无关键词数据</div>'
    items = list(OrderedDict(sorted(freq.items(), key=lambda x: -x[1])).items())[:max_words]
    maxf = max(f for _, f in items) or 1
    minf = min(f for _, f in items) or 1
    spans = []
    for i, (word, f) in enumerate(items):
        # 字号 14~40px，按区间线性映射
        if maxf == minf:
            size = 22
        else:
            size = 14 + 26 * (f - minf) / (maxf - minf)
        color = _PALETTE[i % len(_PALETTE)]
        rot = (i % 5 - 2) * 2  # 轻微倾斜
        spans.append(
            f'<span title="{word}: {f}" style="display:inline-block;font-size:{size:.0f}px;'
            f'color:{color};font-weight:700;margin:2px 6px;transform:rotate({rot}deg);'
            f'line-height:1.1;cursor:default;">{word}</span>'
        )
    return (
        f'<div style="padding:12px;background:#FFFDF7;border:2px dashed #FFD54F;border-radius:16px;'
        f'line-height:1.4;text-align:center;">{"".join(spans)}</div>'
    )


# ---- 便捷渲染封装 ----
def render_sport_stacked(days, sports):
    df = daily_sport_dataframe(days, sports)
    if df.empty:
        st.caption("暂无数据")
        return
    st.bar_chart(df, use_container_width=True)


def render_heat_line(days):
    s = daily_total_series(days)
    if s.empty:
        st.caption("暂无数据")
        return
    st.line_chart(s, use_container_width=True)
