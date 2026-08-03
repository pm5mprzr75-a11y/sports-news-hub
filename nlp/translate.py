"""外文体育新闻一键中文翻译（尽力而为）。

使用 deep-translator 的 Google 翻译端点；若运行环境无法访问或缺少依赖，
则优雅降级（返回原文并附说明），不影响其它功能。
"""
from __future__ import annotations

from nlp.textproc import has_chinese

try:
    from deep_translator import GoogleTranslator  # type: ignore
    _HAS_TRANSLATOR = True
except Exception:  # pragma: no cover
    GoogleTranslator = None
    _HAS_TRANSLATOR = False

# 简单会话内缓存，避免重复翻译同一段
_CACHE: dict = {}


def translate_to_zh(text: str, source: str = "auto") -> dict:
    """翻译为简体中文。返回 {'text', 'ok', 'note'}。"""
    text = (text or "").strip()
    if not text:
        return {"text": "", "ok": False, "note": "空内容"}
    # 已是中文就不翻
    if has_chinese(text) and source == "auto":
        return {"text": text, "ok": True, "note": "原文为中文，无需翻译"}
    key = (source, text[:200])
    if key in _CACHE:
        return _CACHE[key]
    if not _HAS_TRANSLATOR:
        result = {"text": text, "ok": False, "note": "翻译引擎未安装（云端将自动可用）"}
        _CACHE[key] = result
        return result
    try:
        out = GoogleTranslator(source=source, target="zh-CN").translate(text)
        result = {"text": out or text, "ok": True, "note": "已翻译"}
    except Exception as e:  # 超时 / 网络阻断
        result = {"text": text, "ok": False, "note": f"翻译失败：{str(e)[:80]}"}
    _CACHE[key] = result
    return result


if __name__ == "__main__":
    print(translate_to_zh("Lakers defeat Celtics in overtime thriller"))
    print(translate_to_zh("湖人队战胜凯尔特人"))
