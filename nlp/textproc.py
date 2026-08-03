"""智能文本处理：情感分析、摘要生成、关键词提取。

全部依赖均为「尽力而为」——若运行环境缺少 jieba / snownlp，会自动降级为
轻量规则实现，保证应用始终可用。
"""
from __future__ import annotations

import re

# ---- 依赖探测（优雅降级） ----
try:
    from snownlp import SnowNLP  # type: ignore
    _HAS_SNOWNLP = True
except Exception:  # pragma: no cover
    SnowNLP = None
    _HAS_SNOWNLP = False

try:
    import jieba  # type: ignore
    import jieba.analyse  # type: ignore
    _HAS_JIEBA = True
except Exception:  # pragma: no cover
    jieba = None
    _HAS_JIEBA = False


_ZH_RE = re.compile(r"[一-鿿]")
_WS_RE = re.compile(r"\s+")

# 体育领域停用词（过滤无信息量的高频词）
_STOPWORDS = set(
    "的 了 在 是 和 与 及 也 都 就 而 等 对 为 中 上 下 后 前 他 她 它 我们 你们 他们 "
    "球队 比赛 赛季 球员 教练 主场 客场 联赛 冠军 比分 胜利 失败 击败 战胜 获得 表示 "
    "今天 昨天 目前 已经 进行 举行 来自 新浪 体育 网易 搜狐 腾讯 直播 报道 讯 图 视频"
    "a an the of to in on for and or with is are was were be been".split()
)


def has_chinese(text: str) -> bool:
    return bool(_ZH_RE.search(text or ""))


def _sentences(text: str) -> list:
    """按中英文标点切句。"""
    if not text:
        return []
    parts = re.split(r"[。！？!?\.\n]+", text)
    return [p.strip() for p in parts if len(p.strip()) >= 6]


def summarize(text: str, max_sentences: int = 3) -> str:
    """抽取式摘要：优先用 SnowNLP，降级为前几句。"""
    text = (text or "").strip()
    text = _WS_RE.sub(" ", text)
    if not text:
        return ""
    sents = _sentences(text)
    if not sents:
        return text[:120]
    if len(sents) <= max_sentences:
        return "。".join(sents) + ("。" if not text.endswith(("。", "！", "？", ".", "!", "?")) else "")
    if _HAS_SNOWNLP:
        try:
            top = SnowNLP(text).summary(max_sentences)
            if top:
                return "。".join(top) + "。"
        except Exception:
            pass
    # 降级：取前 max_sentences 句
    return "。".join(sents[:max_sentences]) + "。"


def sentiment(text: str) -> dict:
    """返回 {'label': 'pos'|'neg'|'neu', 'score': 0~1}。"""
    text = (text or "").strip()
    if not text or len(text) < 8:
        return {"label": "neu", "score": 0.5}
    if _HAS_SNOWNLP:
        try:
            s = SnowNLP(text).sentiments
            if s >= 0.6:
                return {"label": "pos", "score": round(s, 3)}
            if s <= 0.4:
                return {"label": "neg", "score": round(s, 3)}
            return {"label": "neu", "score": round(s, 3)}
        except Exception:
            pass
    # 降级：基于正负向词典
    pos_w = ["胜", "赢", "夺冠", "晋级", "突破", "纪录", "精彩", "惊喜", "出色", "成功", "利好", "签约", "登顶"]
    neg_w = ["负", "输", "降级", "出局", "失利", "伤", "停赛", "争议", "罚款", "禁赛", "惨败", "低迷", "危机", "下课"]
    score = 0.5
    for w in pos_w:
        if w in text:
            score += 0.08
    for w in neg_w:
        if w in text:
            score -= 0.08
    score = max(0.0, min(1.0, score))
    if score >= 0.6:
        return {"label": "pos", "score": round(score, 3)}
    if score <= 0.4:
        return {"label": "neg", "score": round(score, 3)}
    return {"label": "neu", "score": round(score, 3)}


def keywords(text: str, top_k: int = 8) -> list:
    """提取关键词（名词为主），降级为分词后高频词。"""
    text = (text or "").strip()
    if not text:
        return []
    if _HAS_JIEBA:
        try:
            tags = jieba.analyse.extract_tags(text, topK=top_k, withWeight=False,
                                             allowPOS=("n", "nr", "nz", "ns", "nt", "vn", "v", "eng"))
            tags = [t for t in tags if t not in _STOPWORDS and len(t) > 1]
            if tags:
                return tags[:top_k]
        except Exception:
            pass
    # 降级：jieba 纯分词 + 词频
    if _HAS_JIEBA:
        words = [w for w in jieba.lcut(text) if len(w) > 1 and w not in _STOPWORDS
                 and not re.fullmatch(r"[一-鿿a-zA-Z0-9]", w)]
    else:
        words = [w for w in re.findall(r"[A-Za-z]{3,}|[一-鿿]{2,}", text) if w not in _STOPWORDS]
    from collections import Counter
    freq = Counter(words)
    return [w for w, _ in freq.most_common(top_k)]


def analyze(text: str) -> dict:
    """一站式分析：摘要 + 情感 + 关键词。"""
    return {
        "summary": summarize(text),
        "sentiment": sentiment(text),
        "keywords": keywords(text),
    }


if __name__ == "__main__":
    sample = ("中国男篮在昨晚的比赛中以98比89击败日本队，时隔多年重新登顶亚洲杯。"
              "球员胡明轩砍下27分表现惊艳，赛后他表示球队状态正佳。不过主力中锋受伤离场令人担忧。")
    print("HAS_SNOWNLP", _HAS_SNOWNLP, "HAS_JIEBA", _HAS_JIEBA)
    import json
    print(json.dumps(analyze(sample), ensure_ascii=False, indent=2))
