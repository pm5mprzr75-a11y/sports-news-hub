"""体育产业关键词匹配引擎 + 运动项目打标。

两个维度：
- 产业维度：来自 DB keywords 表（config/keywords.yaml 预置 + 用户自定义）
- 运动维度：来自 config/sports.yaml 的运动项目分类
"""
import os

import yaml
from store import db

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
SPORTS_YAML = os.path.join(CONFIG_DIR, "sports.yaml")


class KeywordMatcher:
    def __init__(self):
        self.cat_terms: dict = {}
        self.sport_terms: dict = {}   # {运动名: [关键词...]}
        self.entity_terms: dict = {}  # {运动名: [联赛/球队/明星...]}
        self._entity_to_sport: dict = {}  # {实体: 运动名}
        self.reload()
        self.load_sports()

    # ---------- 产业维度 ----------
    def reload(self) -> None:
        self.cat_terms = db.get_all_keywords()

    def categories(self) -> list:
        return list(self.cat_terms.keys())

    def match(self, text: str):
        """返回 (category_tags, matched_keywords)。"""
        if not text:
            return [], []
        cats, kws = set(), []
        for cat, terms in self.cat_terms.items():
            for t in terms:
                if t and t in text:
                    cats.add(cat)
                    kws.append(t)
        return sorted(cats), kws

    def match_article(self, article) -> tuple:
        return self.match(article.text())

    # ---------- 运动维度 ----------
    def load_sports(self) -> None:
        with open(SPORTS_YAML, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)["sports"]
        self.sport_terms = {s["name"]: [str(x) for x in s.get("keywords", [])] for s in data}
        self.entity_terms = {s["name"]: [str(x) for x in s.get("entities", [])] for s in data}
        self._sport_meta = {s["name"]: s for s in data}
        self._entity_to_sport = {}
        for sport, ents in self.entity_terms.items():
            for e in ents:
                if e:
                    self._entity_to_sport[e] = sport

    def sports(self) -> list:
        """所有运动项目名称（用于筛选器）。"""
        return list(self.sport_terms.keys())

    def sport_tags_for(self, text: str) -> list:
        """按关键词命中返回运动标签（可多标签）。"""
        if not text:
            return []
        tags = []
        for sport, terms in self.sport_terms.items():
            for t in terms:
                if t and str(t).lower() in text.lower():
                    tags.append(sport)
                    break
        return tags

    # ---------- 二级实体维度（联赛/球队/明星） ----------
    def entities_by_sport(self) -> dict:
        """返回 {运动名: [实体...]}，供二级筛选器分组展示。"""
        return {s: ents for s, ents in self.entity_terms.items() if ents}

    def all_entities(self) -> list:
        """所有实体扁平列表。"""
        out = []
        for ents in self.entity_terms.values():
            out += [e for e in ents if e]
        return out

    def entity_tags_for(self, text: str) -> list:
        """按实体命中返回二级标签（联赛/球队/明星，可多标签）。"""
        if not text:
            return []
        tl = text.lower()
        tags = []
        for ent, sport in self._entity_to_sport.items():
            if ent and str(ent).lower() in tl:
                tags.append(ent)
        return tags

    def sport_of_entity(self, entity: str) -> str:
        return self._entity_to_sport.get(entity, "")

    def sport_tieba(self, sport_name: str) -> str:
        """该运动对应的百度贴吧吧名（用于贴吧适配器）。"""
        meta = self._sport_meta.get(sport_name, {})
        return meta.get("tieba", sport_name)
