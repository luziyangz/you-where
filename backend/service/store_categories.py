"""
书城分类体系（对齐微信读书频道命名，面向文学作品）。

一级 Tab 与微信读书「分类」栏一致或接近：
  精品小说、古典文学、古代诗词、世界名著、文学、历史、哲学宗教、医学健康
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

# 书城横向分类 Tab（key 写入 catalog_books.store_category）
STORE_CATEGORIES: List[Dict[str, str]] = [
    {"key": "all", "name": "全部"},
    {"key": "fiction", "name": "精品小说"},
    {"key": "classical", "name": "古典文学"},
    {"key": "poetry", "name": "古代诗词"},
    {"key": "world_fiction", "name": "世界名著"},
    {"key": "literature", "name": "文学"},
    {"key": "history", "name": "历史"},
    {"key": "philosophy", "name": "哲学宗教"},
    {"key": "medicine", "name": "医学健康"},
]

VALID_CATEGORY_KEYS = {item["key"] for item in STORE_CATEGORIES}

# 旧版分类 key → 新版（兼容历史数据与前端缓存）
LEGACY_CATEGORY_MAP: Dict[str, str] = {
    "foreign_classics": "world_fiction",
    "classics": "classical",
    "xin_xue": "philosophy",
    "mysticism": "philosophy",
}

# Gutendex / Gutenberg subjects 片段 → 分类
_SUBJECT_HINTS: List[tuple[str, str]] = [
    ("historical fiction", "fiction"),
    ("history", "history"),
    ("poetry", "poetry"),
    ("classics of literature", "classical"),
    ("classic literature", "classical"),
    ("philosophy", "philosophy"),
    ("religion", "philosophy"),
    ("science fiction", "fiction"),
    ("adventure", "fiction"),
    ("romance", "fiction"),
    ("drama", "fiction"),
    ("biography", "history"),
    ("autobiograph", "history"),
    ("medicine", "medicine"),
    ("health", "medicine"),
]

# 中文书名关键词（先匹配更具体的）
_TITLE_RULES_ZH: List[tuple[str, str]] = [
    (r"史记|资治通鉴|汉书|春秋|战国策|通鉴", "history"),
    (r"演义|西游|红楼|水浒|三国|隋唐|封神|聊斋|儒林|镜花缘|通言|明言|警世|喻世", "fiction"),
    (r"诗话|诗选|诗集|词集|太白|杜甫|苏轼|诗词|诗品|词话", "poetry"),
    (r"论语|孟子|大学|中庸|庄子|荀子|韩非|墨子|道德经|老子|易经|周易|易传|传习录|心学|大学问", "philosophy"),
    (r"内经|本草|伤寒|金匮|脉|针灸|经络|医|方论", "medicine"),
    (r"日知录|札记|笔记|随笔", "philosophy"),
    (r"经$|子$|集$", "classical"),
]

# 英文书名 / 作者 粗分（Gutendex）
_TITLE_RULES_EN: List[tuple[str, str]] = [
    (r"\b(poems?|poetry|sonnets?)\b", "poetry"),
    (r"\b(history|historical|chronicle|memoirs?)\b", "history"),
    (r"\b(philosophy|ethics|metaphysics|theology|bible|gospel)\b", "philosophy"),
    (r"\b(novel|romance|adventure|fiction|tale|stories)\b", "world_fiction"),
]


def category_label(category_key: str) -> str:
    key = normalize_category_key(category_key)
    for item in STORE_CATEGORIES:
        if item["key"] == key:
            return item["name"]
    return "其他"


def normalize_category_key(category: Optional[str]) -> str:
    key = (category or "all").strip() or "all"
    if key in LEGACY_CATEGORY_MAP:
        key = LEGACY_CATEGORY_MAP[key]
    return key


def is_valid_category_key(key: str) -> bool:
    return normalize_category_key(key) in VALID_CATEGORY_KEYS


def classify_book(
    *,
    catalog_id: str = "",
    title: str = "",
    author: str = "",
    language: str = "",
    source: str = "",
    meta_category: Optional[str] = None,
    subjects: Optional[Sequence[str]] = None,
) -> str:
    """
    为单本书目推断 store_category。
    优先：书目元数据 category → 主题 subjects → 书名/作者规则 → 语种与来源默认。
    """
    if meta_category:
        mapped = normalize_category_key(meta_category)
        if mapped != "all" and mapped in VALID_CATEGORY_KEYS:
            return mapped

    stored_legacy = (meta_category or "").strip()
    if stored_legacy in LEGACY_CATEGORY_MAP:
        return LEGACY_CATEGORY_MAP[stored_legacy]

    for subj in subjects or []:
        if not isinstance(subj, str):
            continue
        low = subj.lower()
        for hint, cat in _SUBJECT_HINTS:
            if hint in low:
                return cat

    title_text = (title or "").strip()
    author_text = (author or "").strip()
    lang = (language or "").lower()

    if lang.startswith("zh") or re.search(r"[\u4e00-\u9fff]", title_text):
        for pattern, cat in _TITLE_RULES_ZH:
            if re.search(pattern, title_text):
                return cat
    else:
        blob = f"{title_text} {author_text}".lower()
        for pattern, cat in _TITLE_RULES_EN:
            if re.search(pattern, blob, re.I):
                return cat

    # 共读 manifest 当代书单（按作者/书名粗分）
    if source == "manifest" or str(catalog_id).startswith("manifest_"):
        return _classify_manifest_title(title_text, author_text)

    if source == "gutendex":
        return "fiction" if lang.startswith("zh") else "world_fiction"

    if source == "project_gutenberg":
        if lang.startswith("zh"):
            return "fiction"
        return "world_fiction"

    if lang.startswith("zh"):
        return "literature"
    return "world_fiction"


def _classify_manifest_title(title: str, author: str) -> str:
    """豆瓣共读推荐书单：现当代与外国文学分流。"""
    blob = f"{title}{author}"
    if re.search(r"三体|科幻", blob):
        return "fiction"
    if re.search(r"东野|马尔克斯|太宰|圣埃克苏佩里|胡赛尼|海明威|陀思|契诃夫|毛姆|奥斯汀|狄更斯", blob):
        return "world_fiction"
    if re.search(r"史|传|记|通鉴|汉书", title):
        return "history"
    if re.search(r"诗|词", title):
        return "poetry"
    if re.search(r"余华|路遥|钱钟书|麦家|莫言|王安忆|苏童|阿城", author):
        return "literature"
    if re.search(r"活着|围城|平凡|海海|人生|散文|文集", title):
        return "literature"
    return "literature"


def remap_legacy_store_category(stored: Optional[str]) -> Optional[str]:
    """将库内旧分类 key 转为新版；无法识别则返回 None 以便重新推断。"""
    if not stored:
        return None
    key = stored.strip()
    if key in LEGACY_CATEGORY_MAP:
        return LEGACY_CATEGORY_MAP[key]
    if key in VALID_CATEGORY_KEYS and key != "all":
        return key
    return None
