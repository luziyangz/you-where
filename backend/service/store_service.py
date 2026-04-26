from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from sqlalchemy.orm import Session

from common.errors import ApiError
from common.models import CatalogBook
from repo import store_repo


GUTENDEX_BASE_URL = "https://gutendex.com"
STORE_PAGE_SIZE = 20
GUTENDEX_FAILURE_THRESHOLD = 3
GUTENDEX_CIRCUIT_COOLDOWN_SECONDS = 60
STORE_ENABLE_NETWORK = os.getenv("STORE_ENABLE_NETWORK", "0") == "1"
logger = logging.getLogger("youzainaye.v2.store")
_gutendex_failure_count = 0
_gutendex_block_until = 0.0

STORE_CATEGORIES = [
    {"key": "all", "name": "全部"},
    {"key": "foreign_classics", "name": "国外名著"},
    {"key": "history", "name": "历史"},
    {"key": "xin_xue", "name": "心学"},
    {"key": "mysticism", "name": "玄学术数"},
    {"key": "medicine", "name": "中医经络"},
    {"key": "classics", "name": "国学经典"},
]

DEFAULT_STORE_BOOKS = [
    {
        "catalog_id": "builtin_lunyu",
        "title": "论语（节选）",
        "author": "孔子及其弟子",
        "language": "zh",
        "detail_url": "https://zh.wikisource.org/wiki/%E8%AB%96%E8%AA%9E",
        "intro": "《论语》记录了孔子及其弟子的言行，围绕学习、修身与处世展开，文字简练却富有启发。",
        "quality_reviews": [
            {"reviewer": "豆瓣读者A", "rating": 4.8, "content": "章节短小，适合碎片化共读，每次都能引发讨论。"},
            {"reviewer": "经典共读社", "rating": 4.7, "content": "对“学”与“仁”的表达非常克制，越读越有层次。"},
        ],
        "content": (
            "学而时习之，不亦说乎？有朋自远方来，不亦乐乎？人不知而不愠，不亦君子乎。"
            "知之者不如好之者，好之者不如乐之者。三人行，必有我师焉。择其善者而从之，其不善者而改之。"
            "君子和而不同，小人同而不和。"
        ),
    },
    {
        "catalog_id": "builtin_tao_te_ching",
        "title": "道德经（节选）",
        "author": "老子",
        "language": "zh",
        "detail_url": "https://zh.wikisource.org/wiki/%E9%81%93%E5%BE%B7%E7%B6%93",
        "intro": "《道德经》以简短篇章讨论“道”与“德”，强调顺势而为、返璞归真，是共读中常见的哲思文本。",
        "quality_reviews": [
            {"reviewer": "古典阅读小组", "rating": 4.9, "content": "句子短但意味深长，很适合双人慢读和复盘。"},
            {"reviewer": "读书博主M", "rating": 4.6, "content": "每章都能关联现实决策，讨论空间很大。"},
        ],
        "content": (
            "道可道，非常道；名可名，非常名。无名天地之始，有名万物之母。"
            "上善若水。水善利万物而不争，处众人之所恶，故几于道。"
            "合抱之木，生于毫末；九层之台，起于累土；千里之行，始于足下。"
        ),
    },
    {
        "catalog_id": "builtin_dream_red_chamber",
        "title": "红楼梦（节选）",
        "author": "曹雪芹",
        "language": "zh",
        "detail_url": "https://zh.wikisource.org/wiki/%E7%B4%85%E6%A8%93%E5%A4%A2",
        "intro": "《红楼梦》通过贾府兴衰描摹人物群像与情感世界，语言细腻，人物关系复杂，适合阶段性共读。",
        "quality_reviews": [
            {"reviewer": "文学爱好者K", "rating": 4.9, "content": "人物塑造极其立体，越讨论越能发现细节。"},
            {"reviewer": "高校课程书单", "rating": 4.8, "content": "兼具故事性与文学性，适合作为长期共读文本。"},
        ],
        "content": (
            "满纸荒唐言，一把辛酸泪。都云作者痴，谁解其中味。"
            "假作真时真亦假，无为有处有还无。"
            "世事洞明皆学问，人情练达即文章。"
        ),
    },
]


DEFAULT_STORE_BOOKS.extend(
    [
        {
            "catalog_id": "builtin_pride_prejudice",
            "category": "foreign_classics",
            "title": "傲慢与偏见（导读节选）",
            "author": "简·奥斯汀",
            "language": "zh",
            "detail_url": "https://www.gutenberg.org/ebooks/1342",
            "intro": "英国现实主义小说代表作，围绕伊丽莎白与达西的误解、判断和成长展开，适合双人讨论人物关系与婚恋观。",
            "quality_reviews": [
                {"reviewer": "世界名著共读组", "rating": 4.8, "content": "人物对话密度高，适合按章节讨论偏见如何形成与被修正。"},
                {"reviewer": "文学导读编辑", "rating": 4.6, "content": "情节推进清晰，读者很容易在价值判断上形成交流。"},
            ],
            "content": "本书关注家庭、阶层、婚姻与个人判断。共读时可记录每次人物态度变化，并比较第一次印象与后续事实之间的落差。",
        },
        {
            "catalog_id": "builtin_monte_cristo",
            "category": "foreign_classics",
            "title": "基督山伯爵（导读节选）",
            "author": "大仲马",
            "language": "zh",
            "detail_url": "https://www.gutenberg.org/ebooks/1184",
            "intro": "法国通俗文学经典，以复仇、身份重建与正义边界为核心，适合长线共读和阶段复盘。",
            "quality_reviews": [
                {"reviewer": "长篇小说读书会", "rating": 4.7, "content": "情节张力强，适合设定每周进度并讨论人物选择的代价。"},
                {"reviewer": "共读体验组", "rating": 4.5, "content": "角色线丰富，伙伴之间可分别追踪不同人物线索。"},
            ],
            "content": "故事从冤屈、囚禁与重生展开。共读建议按人物线建立笔记：谁推动了事件，谁承担了后果，正义与报复的界线在哪里。",
        },
        {
            "catalog_id": "builtin_shiji",
            "category": "history",
            "title": "史记（节选）",
            "author": "司马迁",
            "language": "zh",
            "detail_url": "https://zh.wikisource.org/wiki/%E5%8F%B2%E8%A8%98",
            "intro": "纪传体通史开创之作，人物传记与历史判断并重，适合围绕人物命运和时代结构做共读。",
            "quality_reviews": [
                {"reviewer": "历史共读社", "rating": 4.9, "content": "人物叙事强，读完一篇即可形成讨论。"},
                {"reviewer": "古籍导读员", "rating": 4.7, "content": "适合从列传切入，再回看制度与时代背景。"},
            ],
            "content": "太史公曰：究天人之际，通古今之变，成一家之言。共读时可选择本纪、世家、列传分线推进，记录人物抉择与历史评价。",
        },
        {
            "catalog_id": "builtin_zizhi_tongjian",
            "category": "history",
            "title": "资治通鉴（节选）",
            "author": "司马光",
            "language": "zh",
            "detail_url": "https://zh.wikisource.org/wiki/%E8%B3%87%E6%B2%BB%E9%80%9A%E9%91%91",
            "intro": "编年体通史代表作，强调历史事件之间的因果链，适合以时间线方式推进共读。",
            "quality_reviews": [
                {"reviewer": "历史方法读书会", "rating": 4.8, "content": "非常适合训练因果分析和复盘能力。"},
                {"reviewer": "策略阅读组", "rating": 4.6, "content": "每段都可以引出管理、决策与风险判断。"},
            ],
            "content": "臣光曰：鉴前世之兴衰，考当今之得失。共读时建议按年份梳理事件，并标记关键人物的决策点。",
        },
        {
            "catalog_id": "builtin_chuanxilu",
            "category": "xin_xue",
            "title": "传习录（节选）",
            "author": "王阳明及门人",
            "language": "zh",
            "detail_url": "https://zh.wikisource.org/wiki/%E5%82%B3%E7%BF%92%E9%8C%84",
            "intro": "阳明心学核心文本，围绕知行合一、致良知展开，适合边读边对照日常行动。",
            "quality_reviews": [
                {"reviewer": "心学共修组", "rating": 4.8, "content": "短句密度高，适合每天读一段并写实践反馈。"},
                {"reviewer": "行动复盘员", "rating": 4.6, "content": "能把阅读自然引到生活选择和行动修正上。"},
            ],
            "content": "知是行之始，行是知之成。共读时可将每段拆成观点、例子、今日行动三栏，避免只停留在概念理解。",
        },
        {
            "catalog_id": "builtin_daxuewen",
            "category": "xin_xue",
            "title": "大学问（节选）",
            "author": "王阳明",
            "language": "zh",
            "detail_url": "https://zh.wikisource.org/wiki/%E5%A4%A7%E5%AD%B8%E5%95%8F",
            "intro": "阳明晚年重要文本，解释明德、亲民与万物一体，适合作为心学主题的进阶共读。",
            "quality_reviews": [
                {"reviewer": "国学研读小组", "rating": 4.6, "content": "篇幅不长但概念集中，适合慢读和反复讨论。"},
                {"reviewer": "双人共读体验", "rating": 4.5, "content": "两人可以围绕同一段写下不同生活解释。"},
            ],
            "content": "大人者，以天地万物为一体者也。共读时重点记录概念之间的连接：明德、亲民、止于至善如何落到具体行动。",
        },
        {
            "catalog_id": "builtin_tarot_key",
            "category": "mysticism",
            "title": "塔罗图钥（导读节选）",
            "author": "A. E. Waite",
            "language": "zh",
            "detail_url": "https://www.gutenberg.org/ebooks/43548",
            "intro": "The Pictorial Key to the Tarot 的中文导读条目，适合了解塔罗牌结构、象征体系与解读边界。",
            "quality_reviews": [
                {"reviewer": "象征学读书会", "rating": 4.5, "content": "适合把牌义当作象征文本阅读，而不是机械占断。"},
                {"reviewer": "主题探索组", "rating": 4.4, "content": "分类清楚，适合作为塔罗主题入门共读。"},
            ],
            "content": "塔罗牌可分为大阿尔卡那与小阿尔卡那。共读建议记录每张牌的图像元素、关键词和可能的心理投射，不做确定性承诺。",
        },
        {
            "catalog_id": "builtin_ziweidoushu",
            "category": "mysticism",
            "title": "紫微斗数全书（导读节选）",
            "author": "陈希夷（托名）",
            "language": "zh",
            "detail_url": "https://zh.wikisource.org/wiki/%E7%B4%AB%E5%BE%AE%E6%96%97%E6%95%B8%E5%85%A8%E6%9B%B8",
            "intro": "传统术数文本，适合作为历史文化与术数术语的主题阅读，不替代现实决策。",
            "quality_reviews": [
                {"reviewer": "传统文化读书会", "rating": 4.4, "content": "术语密集，适合两人互相整理词表和结构图。"},
                {"reviewer": "文化史观察员", "rating": 4.3, "content": "作为传统知识体系材料阅读，比直接断事更稳妥。"},
            ],
            "content": "紫微斗数文本包含星曜、宫位、格局等术语。共读应以文化理解和术语整理为主，避免将结果作为现实决策依据。",
        },
        {
            "catalog_id": "builtin_meihua_yishu",
            "category": "mysticism",
            "title": "梅花易数（节选）",
            "author": "邵雍（托名）",
            "language": "zh",
            "detail_url": "https://zh.wikisource.org/wiki/%E6%A2%85%E8%8A%B1%E6%98%93%E6%95%B8",
            "intro": "易学术数类文本，适合从象、数、理的角度了解传统思维结构。",
            "quality_reviews": [
                {"reviewer": "易学文本共读", "rating": 4.4, "content": "可用于理解古人如何组织象征与推演。"},
                {"reviewer": "术数导读组", "rating": 4.3, "content": "建议配合术语表阅读，讨论更聚焦。"},
            ],
            "content": "梅花易数以象数推演为特色。共读时可记录起卦方式、象意解释和文本逻辑，不把阅读结果当成确定预测。",
        },
        {
            "catalog_id": "builtin_qijing_bamai",
            "category": "medicine",
            "title": "奇经八脉考（节选）",
            "author": "李时珍",
            "language": "zh",
            "detail_url": "https://zh.wikisource.org/wiki/%E5%A5%87%E7%B6%93%E5%85%AB%E8%84%88%E8%80%83",
            "intro": "中医经络类经典文本，围绕任督冲带等奇经八脉展开，适合做传统医学史与概念阅读。",
            "quality_reviews": [
                {"reviewer": "中医经典研读组", "rating": 4.6, "content": "概念明确，适合一边读一边画经脉关系图。"},
                {"reviewer": "医学史读者", "rating": 4.4, "content": "作为传统医学文献阅读价值高，但不替代医疗建议。"},
            ],
            "content": "奇经八脉包括任、督、冲、带、阴跷、阳跷、阴维、阳维。共读时建议整理概念来源、经脉关系和后世解释。",
        },
        {
            "catalog_id": "builtin_huangdi_neijing",
            "category": "medicine",
            "title": "黄帝内经·素问（节选）",
            "author": "佚名",
            "language": "zh",
            "detail_url": "https://zh.wikisource.org/wiki/%E9%BB%83%E5%B8%9D%E5%85%A7%E7%B6%93/%E7%B4%A0%E5%95%8F",
            "intro": "中医基础经典之一，适合从养生观、阴阳五行和医学史角度做主题共读。",
            "quality_reviews": [
                {"reviewer": "经典医学读书会", "rating": 4.7, "content": "主题丰富，适合按篇章拆分并做概念卡片。"},
                {"reviewer": "传统文化编辑", "rating": 4.5, "content": "可与现代健康知识区分阅读，避免误用。"},
            ],
            "content": "上古之人，其知道者，法于阴阳，和于术数。共读时应区分历史文献、文化观念和现代医学证据。",
        },
    ]
)


DEFAULT_CATEGORY_FALLBACKS = {
    "builtin_lunyu": "classics",
    "builtin_tao_te_ching": "classics",
    "builtin_dream_red_chamber": "classics",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def seed_default_store_books(db: Session, force: bool = False) -> int:
    if force:
        store_repo.clear_catalog(db)
        existing_ids = set()
    else:
        existing_ids = set(store_repo.list_catalog_ids(db))
        default_ids = {str(item["catalog_id"]) for item in DEFAULT_STORE_BOOKS}
        if existing_ids and not (existing_ids & default_ids):
            if not all(str(catalog_id).startswith("gutendex_") for catalog_id in existing_ids):
                return 0

    now = utc_now()
    page_size_chars = 600
    inserted = 0
    for item in DEFAULT_STORE_BOOKS:
        if item["catalog_id"] in existing_ids:
            continue
        text = item["content"] * 20
        total_pages = max(1, (len(text) + page_size_chars - 1) // page_size_chars)
        store_repo.add_catalog_book_with_content(
            db,
            catalog_id=item["catalog_id"],
            source="builtin",
            source_book_id=item["catalog_id"],
            title=item["title"],
            author=item["author"],
            language=item["language"],
            cover_url="",
            detail_url=item["detail_url"],
            text_url=f"builtin://{item['catalog_id']}",
            content_text=text,
            page_size_chars=page_size_chars,
            total_pages=total_pages,
            now=now,
        )
        inserted += 1
    db.commit()
    return inserted


def _fetch_json(url: str, timeout_seconds: int = 8) -> Dict[str, Any]:
    req = UrlRequest(url, headers={"User-Agent": "todo-mini/1.0"})
    with urlopen(req, timeout=timeout_seconds) as resp:
        data = resp.read()
    payload = json.loads(data.decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def _gutendex_search_books(query: str, page: int = 1) -> Dict[str, Any]:
    query_params = {"search": query}
    if page > 1:
        query_params["page"] = page
    return _fetch_json(f"{GUTENDEX_BASE_URL}/books/?{urlencode(query_params)}")


def _gutendex_list_popular(page: int = 1) -> Dict[str, Any]:
    query_params = {}
    if page > 1:
        query_params["page"] = page
    suffix = f"?{urlencode(query_params)}" if query_params else ""
    return _fetch_json(f"{GUTENDEX_BASE_URL}/books/{suffix}")


def _is_gutendex_circuit_open() -> bool:
    return time.monotonic() < _gutendex_block_until


def _record_gutendex_success() -> None:
    global _gutendex_block_until, _gutendex_failure_count
    _gutendex_failure_count = 0
    _gutendex_block_until = 0.0


def _record_gutendex_failure() -> None:
    global _gutendex_block_until, _gutendex_failure_count
    _gutendex_failure_count += 1
    if _gutendex_failure_count >= GUTENDEX_FAILURE_THRESHOLD:
        _gutendex_block_until = time.monotonic() + GUTENDEX_CIRCUIT_COOLDOWN_SECONDS


def _pick_text_url(formats: Dict[str, str]) -> str:
    if not isinstance(formats, dict):
        return ""
    candidates = ["text/plain; charset=utf-8", "text/plain; charset=us-ascii", "text/plain"]
    for key in candidates:
        url = formats.get(key)
        if isinstance(url, str) and url:
            return url
    for key, url in formats.items():
        if isinstance(key, str) and key.startswith("text/plain") and isinstance(url, str) and url:
            return url
    return ""


def _trim_text(value: str, limit: int) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _quality_level_by_rating(rating: float) -> str:
    if rating >= 4.6:
        return "优秀"
    if rating >= 4.3:
        return "推荐"
    return "可读"


def _default_book_meta(catalog_id: str) -> Dict[str, Any]:
    for item in DEFAULT_STORE_BOOKS:
        if item.get("catalog_id") == catalog_id:
            return item
    return {}


def _category_label(category_key: str) -> str:
    for item in STORE_CATEGORIES:
        if item["key"] == category_key:
            return item["name"]
    return "其他"


def _category_for_catalog_id(catalog_id: str) -> str:
    meta = _default_book_meta(catalog_id)
    return str(meta.get("category") or DEFAULT_CATEGORY_FALLBACKS.get(catalog_id) or "imported")


def _normalize_category(category: Optional[str]) -> str:
    key = (category or "all").strip() or "all"
    valid = {item["key"] for item in STORE_CATEGORIES}
    if key not in valid:
        raise ApiError(40085, "书城分类不存在", 400)
    return key


def _catalog_ids_for_category(category_key: str) -> Optional[list[str]]:
    if category_key == "all":
        return None
    return [
        str(item["catalog_id"])
        for item in DEFAULT_STORE_BOOKS
        if str(item.get("category") or DEFAULT_CATEGORY_FALLBACKS.get(str(item["catalog_id"])) or "") == category_key
    ]


def _build_intro(book: CatalogBook) -> str:
    if book.source == "builtin":
        for item in DEFAULT_STORE_BOOKS:
            if item.get("catalog_id") == book.catalog_id:
                return str(item.get("intro") or "").strip()
    author = (book.author or "佚名").strip()
    language = (book.language or "未知语种").strip()
    base = f"《{book.title}》作者为{author}，当前收录语种为{language}。"
    if book.text_url:
        base += "该书可在线阅读，适合作为共读候选。"
    else:
        base += "当前暂无正文缓存，可先查看信息并等待后续补全。"
    return base


def _build_quality_reviews(book: CatalogBook) -> list[Dict[str, Any]]:
    if book.source == "builtin":
        for item in DEFAULT_STORE_BOOKS:
            if item.get("catalog_id") == book.catalog_id:
                rows = item.get("quality_reviews")
                if isinstance(rows, list):
                    return rows
    base_reviews = [
        {
            "reviewer": "共读社区书评",
            "rating": 4.7 if book.text_url else 4.4,
            "content": "文本表达稳定，章节节奏适合按周推进讨论。",
        },
        {
            "reviewer": "阅读体验组",
            "rating": 4.6 if (book.language or "").lower().startswith("zh") else 4.5,
            "content": "主题清晰，便于围绕人物、观点或结构开展共读。",
        },
    ]
    for row in base_reviews:
        row["quality_level"] = _quality_level_by_rating(float(row["rating"]))
    return base_reviews


def _book_summary_item(row: CatalogBook) -> Dict[str, Any]:
    reviews = _build_quality_reviews(row)
    top_review = reviews[0].get("content") if reviews else ""
    category = _category_for_catalog_id(row.catalog_id)
    return {
        "catalog_id": row.catalog_id,
        "title": row.title,
        "author": row.author,
        "language": row.language,
        "cover_url": row.cover_url,
        "has_text": bool(row.text_url),
        "category": category,
        "category_label": _category_label(category),
        "intro": _trim_text(_build_intro(row), 80),
        "review_count": len(reviews),
        "top_review": _trim_text(str(top_review or ""), 42),
    }


def _gutendex_values(item: Dict[str, Any]) -> Optional[Dict[str, str]]:
    if not isinstance(item, dict):
        return None
    source_book_id = str(item.get("id") or "").strip()
    if not source_book_id:
        return None
    title = (item.get("title") or "").strip()
    if not title:
        return None
    authors = item.get("authors") if isinstance(item.get("authors"), list) else []
    author_name = ""
    if authors and isinstance(authors[0], dict):
        author_name = str(authors[0].get("name") or "").strip()
    languages = item.get("languages") if isinstance(item.get("languages"), list) else []
    language = str(languages[0] or "").strip() if languages else ""
    formats = item.get("formats") if isinstance(item.get("formats"), dict) else {}
    return {
        "catalog_id": f"gutendex_{source_book_id}",
        "source": "gutendex",
        "source_book_id": source_book_id,
        "title": title,
        "author": author_name,
        "language": language,
        "cover_url": str(formats.get("image/jpeg") or "").strip(),
        "detail_url": f"{GUTENDEX_BASE_URL}/books/{source_book_id}",
        "text_url": _pick_text_url(formats),
        "now": utc_now(),
    }


def _upsert_catalog_book_from_gutendex(db: Session, item: Dict[str, Any]) -> Optional[CatalogBook]:
    values = _gutendex_values(item)
    if not values:
        return None
    return store_repo.upsert_catalog_book(db, values)


def list_books(db: Session, query: Optional[str] = None, page: int = 1, category: Optional[str] = None) -> Dict[str, Any]:
    if page < 1 or page > 50:
        raise ApiError(40082, "page 范围不合法", 400)
    seeded_count = seed_default_store_books(db)
    q = (query or "").strip()
    category_key = _normalize_category(category)
    category_catalog_ids = _catalog_ids_for_category(category_key)
    if category_catalog_ids is None and not STORE_ENABLE_NETWORK:
        default_ids = {str(item["catalog_id"]) for item in DEFAULT_STORE_BOOKS}
        existing_ids = set(store_repo.list_catalog_ids(db))
        if existing_ids & default_ids:
            category_catalog_ids = list(default_ids)
    rows = store_repo.list_catalog_books(db, q, page, STORE_PAGE_SIZE, catalog_ids=category_catalog_ids)
    network_synced_count = 0
    network_error = False
    network_skipped = not STORE_ENABLE_NETWORK
    if STORE_ENABLE_NETWORK and category_key == "all" and len(rows) < STORE_PAGE_SIZE:
        if _is_gutendex_circuit_open():
            network_skipped = True
        else:
            network_skipped = False
            try:
                payload = _gutendex_search_books(q, page=page) if q else _gutendex_list_popular(page=page)
                before_count = store_repo.count_catalog_books(db)
                for item in payload.get("results") or []:
                    _upsert_catalog_book_from_gutendex(db, item)
                db.commit()
                _record_gutendex_success()
                after_count = store_repo.count_catalog_books(db)
                network_synced_count = max(0, int(after_count - before_count))
                rows = store_repo.list_catalog_books(db, q, page, STORE_PAGE_SIZE)
            except Exception as exc:
                db.rollback()
                network_error = True
                _record_gutendex_failure()
                logger.warning("Gutendex sync failed: %s", exc)
    return {
        "books": [_book_summary_item(row) for row in rows],
        "page": page,
        "page_size": STORE_PAGE_SIZE,
        "has_more": len(rows) >= STORE_PAGE_SIZE,
        "category": category_key,
        "categories": STORE_CATEGORIES,
        "seeded_count": seeded_count,
        "network_synced_count": network_synced_count,
        "network_error": network_error,
        "network_skipped": network_skipped,
    }


def get_book(db: Session, catalog_id: str) -> Dict[str, Any]:
    row = store_repo.get_catalog_book(db, catalog_id)
    if not row:
        raise ApiError(40421, "书籍不存在", 404)
    content = store_repo.get_catalog_content(db, catalog_id)
    category = _category_for_catalog_id(row.catalog_id)
    return {
        "book": {
            "catalog_id": row.catalog_id,
            "title": row.title,
            "author": row.author,
            "language": row.language,
            "cover_url": row.cover_url,
            "has_text": bool(content),
            "category": category,
            "category_label": _category_label(category),
            "total_pages": int(content.total_pages) if content else None,
            "intro": _build_intro(row),
            "quality_reviews": _build_quality_reviews(row),
        }
    }


def read_page(db: Session, catalog_id: str, page: int = 1) -> Dict[str, Any]:
    if page < 1:
        raise ApiError(40083, "page 不能小于 1", 400)
    book = store_repo.get_catalog_book(db, catalog_id)
    if not book:
        raise ApiError(40421, "书籍不存在", 404)
    content = store_repo.get_catalog_content(db, catalog_id)
    if not content:
        raise ApiError(40422, "正文不存在", 404)
    total_pages = int(content.total_pages or 1)
    if page > total_pages:
        raise ApiError(40084, "page 不能超过总页数", 400)
    page_size = int(content.page_size_chars or 1200)
    text = content.content_text or ""
    start = (page - 1) * page_size
    end = min(len(text), start + page_size)
    return {
        "catalog_id": catalog_id,
        "title": book.title,
        "author": book.author,
        "page": page,
        "total_pages": total_pages,
        "page_size_chars": page_size,
        "content": text[start:end],
    }
