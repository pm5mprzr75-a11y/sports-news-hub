"""数据模型定义。"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Article:
    source_id: str
    source_name: str
    title: str
    url: str
    author: str = ""
    published_at: Optional[datetime] = None
    summary: str = ""
    content: str = ""
    category_tags: list = field(default_factory=list)
    matched_keywords: list = field(default_factory=list)
    sport_tags: list = field(default_factory=list)
    entity_tags: list = field(default_factory=list)
    lang: str = "zh"
    comment_adapter: Optional[str] = None
    # 运行时填充
    id: Optional[int] = None
    has_comments: bool = False
    comment_count: int = 0
    fetched_at: Optional[datetime] = None

    def text(self) -> str:
        return f"{self.title} {self.summary} {self.content}"


@dataclass
class Comment:
    article_id: int
    author: str
    content: str
    published_at: Optional[datetime] = None
    likes: int = 0
    source: str = ""
    fetched_at: Optional[datetime] = None
    id: Optional[int] = None
