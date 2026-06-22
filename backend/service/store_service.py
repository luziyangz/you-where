from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import ipaddress
import json
import logging
import math
import os
import re
import secrets
import socket
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode, urlparse
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from pathlib import Path

from sqlalchemy import or_
from sqlalchemy.orm import Session

from common.errors import ApiError
from common.models import CatalogBook
from repo import reading_repo
from repo import store_repo
from common.reading_enums import BOOK_STATUS_FINISHED, BOOK_STATUS_READING, BOOK_STATUS_SWITCHED
from service import reading_service
from service.catalog_toc import generate_catalog_toc
from service.text_encoding import (
    decode_text_bytes,
    decode_uploaded_txt_bytes,
    finalize_chinese_plaintext,
    is_likely_garbled,
    is_likely_traditional_chinese,
    normalize_imported_text,
    prefer_chinese_for_language,
)
from service.store_reviews import build_quality_reviews, format_top_review, quality_level_by_rating
from service.store_categories import (
    LEGACY_CATEGORY_MAP,
    STORE_CATEGORIES,
    category_label,
    classify_book,
    is_valid_category_key,
    normalize_category_key,
    remap_legacy_store_category,
)


GUTENDEX_BASE_URL = "https://gutendex.com"
STORE_PAGE_SIZE = 20
# 单用户单本书城书目允许的最大摘抄条数（划重点 + 随感）
MAX_CATALOG_READER_MARKS = 500
GUTENDEX_FAILURE_THRESHOLD = 3
GUTENDEX_CIRCUIT_COOLDOWN_SECONDS = 60
# 国内访问 gutendex.com 常需 5–10s+，默认 8s 易触发 read timeout
GUTENDEX_FETCH_TIMEOUT_SECONDS = max(8, int(os.getenv("GUTENDEX_FETCH_TIMEOUT", "20")))
STORE_ENABLE_NETWORK = os.getenv("STORE_ENABLE_NETWORK", "0") == "1"
logger = logging.getLogger("youzainaye.v2.store")
_gutendex_failure_count = 0
_gutendex_block_until = 0.0
_gutendex_remote_page = 1
GUTENDEX_ZH_SYNC_MAX_PAGES = max(1, int(os.getenv("GUTENDEX_ZH_SYNC_MAX_PAGES", "30")))
_gutendex_zh_sync_done = False

MAX_REMOTE_TEXT_BYTES = 5 * 1024 * 1024
MAX_USER_UPLOAD_BYTES = 12 * 1024 * 1024
DEFAULT_PAGE_CHARS = 1200
MIN_IMPORTED_TEXT_CHARS = 300

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
        "category": "classical",
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
        "category": "philosophy",
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
        "category": "fiction",
    },
]


DEFAULT_STORE_BOOKS.extend(
    [
        {
            "catalog_id": "builtin_pride_prejudice",
            "category": "world_fiction",
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
            "category": "world_fiction",
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
            "category": "philosophy",
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
            "category": "philosophy",
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
            "category": "philosophy",
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
            "category": "philosophy",
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
            "category": "philosophy",
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
    "builtin_lunyu": "classical",
    "builtin_tao_te_ching": "philosophy",
    "builtin_dream_red_chamber": "fiction",
}

def _pg_book(
    book_id: str,
    title: str,
    author: str,
    *,
    category: str = "fiction",
    intro: str = "",
    douban_rating: str = "",
) -> Dict[str, Any]:
    """构造 Project Gutenberg 中文公版书条目（站内全文来源）。"""
    return {
        "catalog_id": f"pg_{book_id}",
        "source_book_id": book_id,
        "title": title,
        "author": author,
        "language": "zh",
        "category": category,
        "detail_url": f"https://www.gutenberg.org/ebooks/{book_id}",
        "text_url": f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt",
        "intro": intro,
        "douban_rating": douban_rating,
    }


def _load_public_domain_catalog_books() -> list[Dict[str, Any]]:
    """从 data/public_domain_books.json 加载公版全书清单，便于扩充而不改代码。"""
    data_path = Path(__file__).resolve().parents[1] / "data" / "public_domain_books.json"
    if not data_path.exists():
        return []
    try:
        payload = json.loads(data_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("读取公版书目清单失败 %s: %s", data_path, exc)
        return []
    rows = payload.get("books") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    items: list[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        book_id = str(row.get("book_id") or "").strip()
        title = str(row.get("title") or "").strip()
        if not book_id or not title:
            continue
        items.append(
            _pg_book(
                book_id,
                title,
                str(row.get("author") or "佚名").strip(),
                category=str(row.get("category") or "fiction"),
                intro=str(row.get("intro") or "").strip(),
                douban_rating=str(row.get("douban_rating") or "").strip(),
            )
        )
    return items


PUBLIC_DOMAIN_CATALOG_BOOKS = _load_public_domain_catalog_books()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def seed_default_store_books(db: Session, force: bool = False, update_public_domain: bool = False) -> int:
    if force:
        store_repo.clear_catalog(db)
        existing_ids = set()
        seed_builtin = True
    else:
        existing_ids = set(store_repo.list_catalog_ids(db))
        default_ids = {str(item["catalog_id"]) for item in DEFAULT_STORE_BOOKS}
        seed_builtin = True
        # 已有 pg_* / manifest 等书目时仍须 upsert 公版清单（JSON 扩容后增量入库）
        if existing_ids and not (existing_ids & default_ids):
            if not all(str(catalog_id).startswith("gutendex_") for catalog_id in existing_ids):
                seed_builtin = False

    now = utc_now()
    page_size_chars = 600
    inserted = 0
    if seed_builtin:
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

    for item in PUBLIC_DOMAIN_CATALOG_BOOKS:
        is_new = item["catalog_id"] not in existing_ids
        if not is_new and not force and not update_public_domain:
            continue
        row = store_repo.upsert_catalog_book(
            db,
            {
                "catalog_id": item["catalog_id"],
                "source": "project_gutenberg",
                "source_book_id": item["source_book_id"],
                "title": item["title"],
                "author": item["author"],
                "language": item["language"],
                "cover_url": "",
                "detail_url": item["detail_url"],
                "text_url": item["text_url"],
                "now": now,
                "douban_rating": str(item.get("douban_rating") or "").strip() or None,
                "store_category": str(item.get("category") or "fiction"),
            },
        )
        rating = str(item.get("douban_rating") or "").strip()
        if row and rating:
            row.douban_rating = rating[:16]
        if item["catalog_id"] not in existing_ids:
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
    return _fetch_json(
        f"{GUTENDEX_BASE_URL}/books/?{urlencode(query_params)}",
        timeout_seconds=GUTENDEX_FETCH_TIMEOUT_SECONDS,
    )


def _gutendex_list_popular(page: int = 1) -> Dict[str, Any]:
    query_params = {}
    if page > 1:
        query_params["page"] = page
    suffix = f"?{urlencode(query_params)}" if query_params else ""
    return _fetch_json(
        f"{GUTENDEX_BASE_URL}/books/{suffix}",
        timeout_seconds=GUTENDEX_FETCH_TIMEOUT_SECONDS,
    )


def _gutendex_list_chinese(page: int = 1) -> Dict[str, Any]:
    query_params = {"languages": "zh"}
    if page > 1:
        query_params["page"] = page
    return _fetch_json(
        f"{GUTENDEX_BASE_URL}/books/?{urlencode(query_params)}",
        timeout_seconds=GUTENDEX_FETCH_TIMEOUT_SECONDS,
    )


def sync_gutendex_chinese_catalog(
    db: Session,
    *,
    max_pages: Optional[int] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    从 Gutendex 批量导入 languages=zh 书目元数据（含 text_url），扩充书城。
    部署时可后台执行；force=True 时忽略「已同步」标记。
    """
    global _gutendex_zh_sync_done
    if not STORE_ENABLE_NETWORK:
        return {"ok": 0, "skipped": True, "reason": "STORE_ENABLE_NETWORK=0"}
    if _gutendex_zh_sync_done and not force:
        return {"ok": 0, "skipped": True, "reason": "already_synced"}
    if _is_gutendex_circuit_open():
        return {"ok": 0, "skipped": True, "reason": "circuit_open"}

    limit = max_pages if max_pages is not None else GUTENDEX_ZH_SYNC_MAX_PAGES
    limit = max(1, min(200, int(limit)))
    ok = 0
    failed_pages = 0
    for page in range(1, limit + 1):
        try:
            payload = _gutendex_list_chinese(page=page)
            rows = payload.get("results") or []
            if not rows:
                break
            for item in rows:
                langs = item.get("languages") if isinstance(item.get("languages"), list) else []
                if langs and "zh" not in [str(x).lower() for x in langs]:
                    continue
                if _upsert_catalog_book_from_gutendex(db, item):
                    ok += 1
            db.commit()
            _record_gutendex_success()
            if not payload.get("next"):
                break
        except Exception as exc:
            db.rollback()
            failed_pages += 1
            _record_gutendex_failure()
            logger.warning("Gutendex 中文书目同步第 %s 页失败: %s", page, exc)
            if failed_pages >= 2:
                break
    _gutendex_zh_sync_done = True
    return {"ok": ok, "failed_pages": failed_pages, "max_pages": limit}


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


def catalog_allows_placeholder_pair(book: CatalogBook) -> bool:
    """无本地正文时是否仍允许加入共读（外链书、书单卡片）。"""
    pp = getattr(book, "placeholder_pages", None)
    if pp is not None and int(pp) > 0:
        return True
    src = (book.source or "").strip()
    return src in ("manifest", "user_link")


def _viewer_can_access_pair_catalog(db: Optional[Session], catalog_id: str, viewer_user_id: Optional[str]) -> bool:
    if not db or not viewer_user_id or not catalog_id:
        return False
    pair = reading_repo.get_active_pair(db, viewer_user_id)
    if not pair:
        return False
    pair_book = reading_repo.get_pair_book_by_catalog_id(db, pair.pair_id, catalog_id)
    return bool(pair_book)


def assert_can_access_catalog(book: CatalogBook, viewer_user_id: Optional[str], db: Optional[Session] = None) -> None:
    """用户自建书目仅本人或已加入该书目的共读伙伴可读详情与正文。"""
    owner = getattr(book, "owner_user_id", None)
    if owner:
        if not viewer_user_id:
            raise ApiError(40303, "无权访问该书籍", 403)
        if viewer_user_id != owner and not _viewer_can_access_pair_catalog(db, book.catalog_id, viewer_user_id):
            raise ApiError(40303, "无权访问该书籍", 403)


def _viewer_can_access_catalog(book: CatalogBook, viewer_user_id: Optional[str], db: Optional[Session] = None) -> bool:
    owner = getattr(book, "owner_user_id", None)
    if not owner:
        return True
    return bool(viewer_user_id and (viewer_user_id == owner or _viewer_can_access_pair_catalog(db, book.catalog_id, viewer_user_id)))


def _fetch_url_bytes(url: str, limit: int) -> bytes:
    req = UrlRequest(url, headers={"User-Agent": "YouWhereReader/1.0"})
    with urlopen(req, timeout=45) as resp:
        return resp.read(limit + 1)


def _fetch_url_payload(url: str, limit: int) -> tuple[bytes, str]:
    req = UrlRequest(url, headers={"User-Agent": "YouWhereReader/1.0"})
    with urlopen(req, timeout=45) as resp:
        content_type = str(resp.headers.get("Content-Type") or "")
        return resp.read(limit + 1), content_type


def _gutenberg_https_cache_url(url: str) -> str:
    parsed = urlparse(url)
    match = re.search(r"/ebooks/(\d+)(?:\.txt(?:\.utf-8)?)?$", parsed.path or "")
    if not match:
        match = re.search(r"/cache/epub/(\d+)/pg\d+\.txt$", parsed.path or "")
    if not match:
        return ""
    book_id = match.group(1)
    return f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt"


def _plain_text_candidate_urls(url: str) -> list[str]:
    candidates: list[str] = []
    cache_url = _gutenberg_https_cache_url(url)
    if cache_url:
        candidates.append(cache_url)
    candidates.append(url)
    deduped: list[str] = []
    for item in candidates:
        if item and item not in deduped:
            deduped.append(item)
    return deduped


def _decode_remote_bytes(raw: bytes, *, content_type: str = "", language: str = "") -> str:
    """远程正文解码；中文书优先可读汉字，避免 latin-1 误解析。"""
    prefer = prefer_chinese_for_language(language)
    try:
        return decode_text_bytes(raw, content_type=content_type, prefer_chinese=prefer, min_quality=0.0)
    except ValueError:
        if prefer:
            try:
                return decode_text_bytes(raw, content_type=content_type, prefer_chinese=False, min_quality=0.0)
            except ValueError:
                return ""
        return ""


class _ReadableHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        tag_name = tag.lower()
        if tag_name in {"script", "style", "noscript", "svg", "canvas"}:
            self._skip_depth += 1
            return
        if tag_name in {"p", "br", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "tr"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag_name = tag.lower()
        if tag_name in {"script", "style", "noscript", "svg", "canvas"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag_name in {"p", "div", "section", "article", "li", "h1", "h2", "h3", "h4", "tr"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = (data or "").strip()
        if text:
            self._parts.append(text)

    def text(self) -> str:
        return "\n".join(self._parts)


def _normalize_imported_text(text: str) -> str:
    return normalize_imported_text(text)


def _finalize_plaintext_for_book(text: str, book: CatalogBook) -> str:
    """按书目语言规范化正文（中文统一简体）。"""
    return finalize_chinese_plaintext(text, language=book.language or "")


def _ensure_content_simplified_if_needed(db: Session, book: CatalogBook, content) -> None:
    """已缓存繁体正文时一次性转简体并重新分页。"""
    lang = book.language or ""
    if not prefer_chinese_for_language(lang):
        return
    raw = content.content_text or ""
    if not is_likely_traditional_chinese(raw):
        return
    new_text = finalize_chinese_plaintext(raw, language=lang)
    if new_text == raw:
        return
    page_size = int(content.page_size_chars or DEFAULT_PAGE_CHARS)
    total_pages = max(1, (len(new_text) + page_size - 1) // page_size)
    store_repo.upsert_catalog_content(
        db,
        catalog_id=book.catalog_id,
        content_text=new_text,
        page_size_chars=page_size,
        total_pages=total_pages,
        now=utc_now(),
    )
    db.flush()


def _html_to_readable_text(html: str) -> str:
    parser = _ReadableHtmlParser()
    parser.feed(html)
    parser.close()
    return _normalize_imported_text(parser.text())


def _strip_gutenberg_boilerplate(text: str) -> str:
    value = text or ""
    start_match = re.search(r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", value, flags=re.I | re.S)
    if start_match:
        value = value[start_match.end():]
    end_match = re.search(r"\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*", value, flags=re.I | re.S)
    if end_match:
        value = value[:end_match.start()]
    return _normalize_imported_text(value)


def _is_private_hostname(hostname: str) -> bool:
    host = (hostname or "").strip().strip("[]")
    if not host:
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return True
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return True
    return False


def _validate_public_import_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ApiError(40096, "请填写以 http(s) 开头的阅读链接", 400)
    if parsed.username or parsed.password:
        raise ApiError(40097, "阅读链接不能包含账号密码", 400)
    if _is_private_hostname(parsed.hostname):
        raise ApiError(40098, "阅读链接必须是公网可访问地址", 400)


def _extract_remote_readable_text(url: str) -> Optional[str]:
    raw, content_type = _fetch_url_payload(url, MAX_REMOTE_TEXT_BYTES)
    if len(raw) > MAX_REMOTE_TEXT_BYTES:
        raise ApiError(40099, "远程正文过大（上限约 5MB）", 400)
    decoded = _decode_remote_bytes(raw, content_type=content_type, language="zh")
    if not decoded.strip():
        return None
    content_type_l = content_type.lower()
    path_l = urlparse(url).path.lower()
    if "text/html" in content_type_l or path_l.endswith((".html", ".htm")):
        text = _html_to_readable_text(decoded)
    else:
        text = _strip_gutenberg_boilerplate(decoded)
    if len(text.strip()) < MIN_IMPORTED_TEXT_CHARS:
        return None
    return finalize_chinese_plaintext(text, language="zh")


def _add_user_url_book_with_content(
    db: Session,
    *,
    catalog_id: str,
    user_id: str,
    title: str,
    author: str,
    url: str,
    text: str,
    now: str,
) -> int:
    page_size = DEFAULT_PAGE_CHARS
    total_pages = max(1, (len(text) + page_size - 1) // page_size)
    store_repo.add_catalog_book_with_content(
        db,
        catalog_id=catalog_id,
        source="user_url",
        source_book_id=catalog_id,
        title=title[:200],
        author=author[:200],
        language="zh",
        cover_url="",
        detail_url=url,
        text_url=url,
        content_text=text,
        page_size_chars=page_size,
        total_pages=total_pages,
        now=now,
        owner_user_id=user_id,
        douban_rating=None,
        placeholder_pages=None,
    )
    return total_pages


def fetch_plain_catalog_from_url(db: Session, book: CatalogBook) -> bool:
    """从 text_url 拉取全文（如 Project Gutenberg 纯文本），写入 catalog_contents。"""
    url = (book.text_url or "").strip()
    if not url.startswith(("http://", "https://")):
        return False
    existing = store_repo.get_catalog_content(db, book.catalog_id)
    if existing:
        prefer_zh = prefer_chinese_for_language(book.language or "")
        if not is_likely_garbled(existing.content_text or "", prefer_chinese=prefer_zh):
            return True
        logger.warning("检测到疑似乱码缓存，将重新拉取正文 %s", book.catalog_id)
        store_repo.delete_catalog_content(db, book.catalog_id)
    last_error = None
    text = ""
    for candidate_url in _plain_text_candidate_urls(url):
        try:
            raw, content_type = _fetch_url_payload(candidate_url, MAX_REMOTE_TEXT_BYTES)
        except Exception as exc:
            last_error = exc
            logger.warning("拉取书城正文失败 %s: %s", candidate_url, exc)
            continue
        if len(raw) > MAX_REMOTE_TEXT_BYTES:
            logger.warning("拉取书城正文过大 %s", candidate_url)
            continue
        decoded = _decode_remote_bytes(raw, content_type=content_type, language=book.language or "")
        text = _finalize_plaintext_for_book(_strip_gutenberg_boilerplate(decoded), book)
        if len(text.strip()) >= 80:
            break
        logger.warning("拉取书城正文过短 %s", candidate_url)
        text = ""
    if not text:
        if last_error:
            logger.warning("书城正文全部候选地址拉取失败 %s: %s", url, last_error)
        return False
    text = _finalize_plaintext_for_book(text, book)
    page_size = DEFAULT_PAGE_CHARS
    total_pages = max(1, (len(text) + page_size - 1) // page_size)
    store_repo.upsert_catalog_content(
        db,
        catalog_id=book.catalog_id,
        content_text=text,
        page_size_chars=page_size,
        total_pages=total_pages,
        now=utc_now(),
    )
    return True


def hydrate_catalog_if_needed(db: Session, book: CatalogBook) -> None:
    """共读或阅读前尝试补全正文；若已缓存但疑似乱码会重新拉取。"""
    if book.source not in {"gutendex", "project_gutenberg", "user_url"}:
        content = store_repo.get_catalog_content(db, book.catalog_id)
        if content:
            _ensure_content_simplified_if_needed(db, book, content)
        return
    fetch_plain_catalog_from_url(db, book)
    content = store_repo.get_catalog_content(db, book.catalog_id)
    if content:
        _ensure_content_simplified_if_needed(db, book, content)


def decode_uploaded_txt(raw: bytes) -> str:
    if len(raw) > MAX_USER_UPLOAD_BYTES:
        raise ApiError(40094, "TXT 文件过大（上限约 12MB）", 400)
    try:
        return finalize_chinese_plaintext(decode_uploaded_txt_bytes(raw, prefer_chinese=True), language="zh")
    except ValueError as exc:
        raise ApiError(40091, str(exc), 400) from exc


def import_user_txt_book(db: Session, user_id: str, title: str, author: str, raw: bytes) -> Dict[str, Any]:
    title_clean = (title or "").strip()
    if not title_clean:
        raise ApiError(40072, "书名不能为空", 400)
    text = decode_uploaded_txt(raw)
    if len(text.strip()) < 120:
        raise ApiError(40095, "正文过短", 400)
    cid = f"utxt_{secrets.token_hex(10)}"
    now = utc_now()
    page_size = DEFAULT_PAGE_CHARS
    total_pages = max(1, (len(text) + page_size - 1) // page_size)
    store_repo.add_catalog_book_with_content(
        db,
        catalog_id=cid,
        source="user_txt",
        source_book_id=cid,
        title=title_clean[:200],
        author=(author or "").strip()[:200],
        language="zh",
        cover_url="",
        detail_url="",
        text_url=f"upload://{cid}",
        content_text=text,
        page_size_chars=page_size,
        total_pages=total_pages,
        now=now,
        owner_user_id=user_id,
        douban_rating=None,
        placeholder_pages=None,
    )
    db.commit()
    return {"catalog_id": cid, "title": title_clean, "total_pages": total_pages}


def import_user_read_url_book(
    db: Session,
    user_id: str,
    title: str,
    author: str,
    read_url: str,
    estimated_pages: Optional[int] = None,
) -> Dict[str, Any]:
    title_clean = (title or "").strip()
    url = (read_url or "").strip()
    if not title_clean:
        raise ApiError(40072, "书名不能为空", 400)
    _validate_public_import_url(url)
    cid = f"ulink_{secrets.token_hex(10)}"
    now = utc_now()
    try:
        text = _extract_remote_readable_text(url)
    except ApiError:
        raise
    except Exception as exc:
        logger.warning("导入远程正文失败 %s: %s", url, exc)
        text = None

    author_clean = (author or "").strip()
    if text:
        total_pages = _add_user_url_book_with_content(
            db,
            catalog_id=cid,
            user_id=user_id,
            title=title_clean,
            author=author_clean,
            url=url,
            text=text,
            now=now,
        )
        db.commit()
        return {
            "catalog_id": cid,
            "title": title_clean,
            "total_pages": total_pages,
            "import_mode": "remote_text",
        }

    pp = int(estimated_pages) if estimated_pages is not None and int(estimated_pages) > 0 else 400
    db.add(
        CatalogBook(
            catalog_id=cid,
            source="user_link",
            source_book_id=cid,
            title=title_clean[:200],
            author=author_clean[:200],
            language="zh",
            cover_url="",
            detail_url=url,
            text_url=url,
            owner_user_id=user_id,
            douban_rating=None,
            placeholder_pages=pp,
            created_at=now,
            updated_at=now,
        )
    )
    db.commit()
    return {"catalog_id": cid, "title": title_clean, "placeholder_pages": pp, "import_mode": "external_link"}


def _lazy_gutendex_readable(row: CatalogBook, has_local: bool) -> bool:
    if has_local:
        return False
    url = (row.text_url or "").strip()
    return row.source in {"gutendex", "project_gutenberg", "user_url"} and url.startswith(("http://", "https://"))


def _external_link_for_row(row: CatalogBook, has_local: bool, lazy_gutendex: bool) -> str:
    if has_local or lazy_gutendex:
        return ""
    url = (row.text_url or "").strip()
    if url.startswith(("http://", "https://")):
        return url
    detail = (row.detail_url or "").strip()
    if detail.startswith(("http://", "https://")):
        return detail
    return ""


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
    return quality_level_by_rating(rating)


def _default_book_meta(catalog_id: str) -> Dict[str, Any]:
    for item in DEFAULT_STORE_BOOKS:
        if item.get("catalog_id") == catalog_id:
            return item
    for item in PUBLIC_DOMAIN_CATALOG_BOOKS:
        if item.get("catalog_id") == catalog_id:
            return item
    return {}


def _category_label(category_key: str) -> str:
    return category_label(category_key)


def _rating_from_download_count(download_count: int) -> str:
    """将 Gutendex 下载量映射为展示评分（约 4.0–9.5）。"""
    dc = max(0, int(download_count or 0))
    score = min(9.5, 4.0 + math.log10(dc + 1) * 0.85)
    return f"{score:.1f}"


def _infer_store_category(
    catalog_id: str,
    source: str,
    language: str,
    *,
    title: str = "",
    author: str = "",
    subjects: Optional[list] = None,
) -> str:
    meta = _default_book_meta(catalog_id)
    return classify_book(
        catalog_id=catalog_id,
        title=title or str(meta.get("title") or ""),
        author=author,
        language=language,
        source=source,
        meta_category=str(meta.get("category") or DEFAULT_CATEGORY_FALLBACKS.get(catalog_id) or ""),
        subjects=subjects,
    )


def _category_for_row(row: CatalogBook) -> str:
    stored = remap_legacy_store_category(getattr(row, "store_category", None))
    if stored:
        return stored
    return _infer_store_category(
        row.catalog_id,
        row.source,
        row.language or "",
        title=row.title or "",
        author=row.author or "",
    )


def _category_for_catalog_id(catalog_id: str) -> str:
    meta = _default_book_meta(catalog_id)
    return classify_book(
        catalog_id=catalog_id,
        title=str(meta.get("title") or ""),
        author=str(meta.get("author") or ""),
        language=str(meta.get("language") or "zh"),
        source="project_gutenberg" if str(catalog_id).startswith("pg_") else "",
        meta_category=str(meta.get("category") or DEFAULT_CATEGORY_FALLBACKS.get(catalog_id) or ""),
    )


def _backfill_catalog_store_metadata(db: Session) -> None:
    """补全或迁移分类/评分（含旧版 store_category key）。"""
    rows = (
        db.query(CatalogBook)
        .filter(
            or_(
                CatalogBook.store_category.is_(None),
                CatalogBook.douban_rating.is_(None),
                CatalogBook.store_category.in_(list(LEGACY_CATEGORY_MAP.keys())),
            )
        )
        .limit(300)
        .all()
    )
    if not rows:
        return
    changed = False
    for row in rows:
        meta = _default_book_meta(row.catalog_id)
        mapped = remap_legacy_store_category(row.store_category)
        new_cat = classify_book(
            catalog_id=row.catalog_id,
            title=row.title or "",
            author=row.author or "",
            language=row.language or "",
            source=row.source,
            meta_category=str(meta.get("category") or DEFAULT_CATEGORY_FALLBACKS.get(row.catalog_id) or ""),
        )
        if mapped != new_cat or row.store_category in LEGACY_CATEGORY_MAP or not row.store_category:
            row.store_category = new_cat
            changed = True
        if not (row.douban_rating or "").strip():
            rating = str(meta.get("douban_rating") or "").strip()
            if rating:
                row.douban_rating = rating[:16]
                changed = True
            elif row.source == "gutendex":
                row.douban_rating = _rating_from_download_count(0)
                changed = True
    if changed:
        db.commit()


def _normalize_category(category: Optional[str]) -> str:
    key = normalize_category_key(category)
    if not is_valid_category_key(key):
        raise ApiError(40085, "书城分类不存在", 400)
    return key


def _catalog_ids_for_category(category_key: str) -> Optional[list[str]]:
    if category_key == "all":
        return None
    return [
        str(item["catalog_id"])
        for item in [*DEFAULT_STORE_BOOKS, *PUBLIC_DOMAIN_CATALOG_BOOKS]
        if str(item.get("category") or DEFAULT_CATEGORY_FALLBACKS.get(str(item["catalog_id"])) or "") == category_key
    ]


def _build_intro(book: CatalogBook) -> str:
    if book.source == "builtin":
        for item in DEFAULT_STORE_BOOKS:
            if item.get("catalog_id") == book.catalog_id:
                return str(item.get("intro") or "").strip()
    if book.source == "project_gutenberg":
        meta = _default_book_meta(book.catalog_id)
        if meta.get("intro"):
            return str(meta["intro"]).strip()
        return (
            f"《{book.title}》为 Project Gutenberg 公版全书，可在小程序内分页阅读、划线和加入共读。"
            "若正文尚未缓存，首次打开时会自动下载全文到站内。"
        )
    if book.source == "manifest":
        rating = (getattr(book, "douban_rating", None) or "").strip()
        score = f"豆瓣参考分 {rating}。" if rating else ""
        return (
            f"《{book.title}》收录于共读扩展书单，优先推荐使用正版纸书或授权电子版。"
            f"{score}站内若无全文，可用书房「导入 TXT」或「阅读链接」补齐。"
        ).strip()
    author = (book.author or "佚名").strip()
    language = (book.language or "未知语种").strip()
    base = f"《{book.title}》作者为{author}，当前收录语种为{language}。"
    if book.text_url:
        base += "该书可在线阅读，适合作为共读候选。"
    else:
        base += "当前暂无正文缓存，可先查看信息并等待后续补全。"
    return base


def _build_quality_reviews(book: CatalogBook, *, has_local_text: bool = False) -> list[Dict[str, Any]]:
    builtin_rows = None
    if book.source == "builtin":
        for item in DEFAULT_STORE_BOOKS:
            if item.get("catalog_id") == book.catalog_id:
                rows = item.get("quality_reviews")
                if isinstance(rows, list):
                    builtin_rows = rows
                break
    meta = _default_book_meta(book.catalog_id)
    return build_quality_reviews(
        book,
        store_category=_category_for_row(book),
        meta=meta,
        builtin_reviews=builtin_rows,
        has_local_text=has_local_text,
    )


def _book_summary_item(row: CatalogBook, has_local_text: bool) -> Dict[str, Any]:
    lazy = _lazy_gutendex_readable(row, has_local_text)
    ext_url = _external_link_for_row(row, has_local_text, lazy)
    reviews = _build_quality_reviews(row, has_local_text=has_local_text)
    top_review = format_top_review(reviews)
    category = _category_for_row(row)
    rating = getattr(row, "douban_rating", None) or ""
    primary_rating = reviews[0].get("rating") if reviews else None
    return {
        "catalog_id": row.catalog_id,
        "title": row.title,
        "author": row.author,
        "language": row.language,
        "cover_url": row.cover_url,
        "has_text": has_local_text or lazy,
        "has_local_text": has_local_text,
        "douban_rating": rating,
        "external_read_url": ext_url,
        "category": category,
        "category_label": _category_label(category),
        "intro": _trim_text(_build_intro(row), 80),
        "review_count": len(reviews),
        "top_review": top_review,
        "review_rating": primary_rating,
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
    catalog_id = f"gutendex_{source_book_id}"
    subjects = item.get("subjects") if isinstance(item.get("subjects"), list) else []
    store_category = classify_book(
        catalog_id=catalog_id,
        title=title,
        author=author_name,
        language=language,
        source="gutendex",
        subjects=subjects,
    )
    download_count = int(item.get("download_count") or 0)
    return {
        "catalog_id": catalog_id,
        "source": "gutendex",
        "source_book_id": source_book_id,
        "title": title,
        "author": author_name,
        "language": language,
        "cover_url": str(formats.get("image/jpeg") or "").strip(),
        "detail_url": f"{GUTENDEX_BASE_URL}/books/{source_book_id}",
        "text_url": _pick_text_url(formats),
        "store_category": store_category,
        "douban_rating": _rating_from_download_count(download_count),
        "now": utc_now(),
    }


def _upsert_catalog_book_from_gutendex(db: Session, item: Dict[str, Any]) -> Optional[CatalogBook]:
    values = _gutendex_values(item)
    if not values:
        return None
    return store_repo.upsert_catalog_book(db, values)


def _list_books_query_params(db: Session, category_key: str) -> tuple[Optional[list[str]], Optional[str], Optional[list[str]]]:
    """返回 (catalog_ids, store_category, excluded_sources)。"""
    excluded_sources = ["builtin"] if category_key == "all" else None
    store_category = category_key if category_key != "all" else None
    catalog_ids = None
    if category_key == "all" and not STORE_ENABLE_NETWORK:
        default_ids = {str(item["catalog_id"]) for item in PUBLIC_DOMAIN_CATALOG_BOOKS}
        existing_ids = set(store_repo.list_catalog_ids(db))
        if existing_ids & default_ids:
            catalog_ids = list(default_ids)
    return catalog_ids, store_category, excluded_sources


def _sync_gutendex_if_needed(
    db: Session,
    q: str,
    category_key: str,
    page: int,
    total: int,
    catalog_ids: Optional[list[str]],
    store_category: Optional[str],
    excluded_sources: Optional[list[str]],
    viewer_user_id: Optional[str],
) -> tuple[int, bool, bool]:
    """本地书目不足以翻页时拉取 Gutendex 下一页。返回 (synced_count, network_error, network_skipped)。"""
    global _gutendex_remote_page
    network_synced_count = 0
    network_error = False
    network_skipped = not STORE_ENABLE_NETWORK
    if not STORE_ENABLE_NETWORK or category_key != "all" or q:
        return network_synced_count, network_error, network_skipped
    if page * STORE_PAGE_SIZE < total:
        return network_synced_count, network_error, network_skipped
    if _is_gutendex_circuit_open():
        network_skipped = True
        return network_synced_count, network_error, network_skipped
    network_skipped = False
    try:
        payload = _gutendex_list_popular(page=_gutendex_remote_page)
        before_count = store_repo.count_catalog_books_filtered(
            db, q, catalog_ids=catalog_ids, viewer_user_id=viewer_user_id,
            excluded_sources=excluded_sources, store_category=store_category,
        )
        for item in payload.get("results") or []:
            _upsert_catalog_book_from_gutendex(db, item)
        db.commit()
        _record_gutendex_success()
        after_count = store_repo.count_catalog_books_filtered(
            db, q, catalog_ids=catalog_ids, viewer_user_id=viewer_user_id,
            excluded_sources=excluded_sources, store_category=store_category,
        )
        network_synced_count = max(0, int(after_count - before_count))
        if payload.get("next"):
            _gutendex_remote_page += 1
        else:
            _gutendex_remote_page = 1
    except Exception as exc:
        db.rollback()
        network_error = True
        _record_gutendex_failure()
        logger.warning("Gutendex sync failed: %s", exc)
    return network_synced_count, network_error, network_skipped


def list_books(
    db: Session,
    query: Optional[str] = None,
    page: int = 1,
    category: Optional[str] = None,
    viewer_user_id: Optional[str] = None,
) -> Dict[str, Any]:
    if page < 1 or page > 50:
        raise ApiError(40082, "page 范围不合法", 400)
    seeded_count = seed_default_store_books(db)
    q = (query or "").strip()
    category_key = _normalize_category(category)
    if STORE_ENABLE_NETWORK and category_key == "all" and not q:
        sync_gutendex_chinese_catalog(db, max_pages=min(3, GUTENDEX_ZH_SYNC_MAX_PAGES))
    _backfill_catalog_store_metadata(db)
    catalog_ids, store_category, excluded_sources = _list_books_query_params(db, category_key)

    total = store_repo.count_catalog_books_filtered(
        db, q, catalog_ids=catalog_ids, viewer_user_id=viewer_user_id,
        excluded_sources=excluded_sources, store_category=store_category,
    )
    network_synced_count, network_error, network_skipped = _sync_gutendex_if_needed(
        db, q, category_key, page, total, catalog_ids, store_category, excluded_sources, viewer_user_id,
    )
    if network_synced_count:
        total = store_repo.count_catalog_books_filtered(
            db, q, catalog_ids=catalog_ids, viewer_user_id=viewer_user_id,
            excluded_sources=excluded_sources, store_category=store_category,
        )

    rows = store_repo.list_catalog_books(
        db,
        q,
        page,
        STORE_PAGE_SIZE,
        catalog_ids=catalog_ids,
        viewer_user_id=viewer_user_id,
        excluded_sources=excluded_sources,
        store_category=store_category,
    )
    if STORE_ENABLE_NETWORK and category_key == "all" and q and len(rows) < STORE_PAGE_SIZE:
        if _is_gutendex_circuit_open():
            network_skipped = True
        else:
            try:
                payload = _gutendex_search_books(q, page=page)
                for item in payload.get("results") or []:
                    _upsert_catalog_book_from_gutendex(db, item)
                db.commit()
                _record_gutendex_success()
                rows = store_repo.list_catalog_books(
                    db, q, page, STORE_PAGE_SIZE, catalog_ids=catalog_ids,
                    viewer_user_id=viewer_user_id, excluded_sources=excluded_sources,
                    store_category=store_category,
                )
                total = store_repo.count_catalog_books_filtered(
                    db, q, catalog_ids=catalog_ids, viewer_user_id=viewer_user_id,
                    excluded_sources=excluded_sources, store_category=store_category,
                )
            except Exception as exc:
                db.rollback()
                network_error = True
                _record_gutendex_failure()
                logger.warning("Gutendex search sync failed: %s", exc)

    ids = [r.catalog_id for r in rows]
    with_content = store_repo.catalog_ids_having_content(db, ids)
    indexed_rows = list(enumerate(rows))
    indexed_rows.sort(
        key=lambda pair: (
            0 if pair[1].catalog_id in with_content else 1,
            0 if pair[1].source == "project_gutenberg" else 1,
            pair[0],
        )
    )
    rows_sorted = [row for _, row in indexed_rows]
    has_more = page * STORE_PAGE_SIZE < total
    return {
        "books": [_book_summary_item(r, r.catalog_id in with_content) for r in rows_sorted],
        "page": page,
        "page_size": STORE_PAGE_SIZE,
        "has_more": has_more,
        "total": total,
        "category": category_key,
        "categories": STORE_CATEGORIES,
        "seeded_count": seeded_count,
        "network_synced_count": network_synced_count,
        "network_error": network_error,
        "network_skipped": network_skipped,
    }


def list_my_shelf(db: Session, user_id: str, tab: Optional[str] = None, page: int = 1) -> Dict[str, Any]:
    """登录用户书架：收藏列表或最近阅读（按进度更新时间）。"""
    if page < 1 or page > 50:
        raise ApiError(40082, "page 范围不合法", 400)
    tab_key = (tab or "recent").strip().lower()
    if tab_key not in ("favorites", "recent"):
        raise ApiError(40086, "tab 须为 favorites 或 recent", 400)

    progress_by_id: Dict[str, int] = {}
    if tab_key == "favorites":
        slice_rows = store_repo.list_catalog_favorites_page(db, user_id, page, STORE_PAGE_SIZE)
        has_more = len(slice_rows) > STORE_PAGE_SIZE
        slice_rows = slice_rows[:STORE_PAGE_SIZE]
        catalog_ids = [r.catalog_id for r in slice_rows]
    else:
        prog_rows = store_repo.list_catalog_read_progress_page(db, user_id, page, STORE_PAGE_SIZE)
        has_more = len(prog_rows) > STORE_PAGE_SIZE
        prog_rows = prog_rows[:STORE_PAGE_SIZE]
        catalog_ids = [r.catalog_id for r in prog_rows]
        progress_by_id = {r.catalog_id: int(r.last_page or 1) for r in prog_rows}

    with_content = store_repo.catalog_ids_having_content(db, catalog_ids)
    books_out: list[Dict[str, Any]] = []
    for cid in catalog_ids:
        row = store_repo.get_catalog_book(db, cid)
        if not row or not _viewer_can_access_catalog(row, user_id, db):
            continue
        item = _book_summary_item(row, row.catalog_id in with_content)
        if tab_key == "recent":
            content = store_repo.get_catalog_content(db, cid)
            total_pages = int(content.total_pages or 0) if content else None
            item["reading_progress_page"] = resolve_user_catalog_last_page(
                db, user_id, cid, total_pages=total_pages, sync_if_drift=False
            )
        books_out.append(item)

    return {
        "books": books_out,
        "tab": tab_key,
        "page": page,
        "page_size": STORE_PAGE_SIZE,
        "has_more": has_more,
    }


def add_book_favorite(db: Session, user_id: str, catalog_id: str) -> Dict[str, Any]:
    row = store_repo.get_catalog_book(db, catalog_id)
    if not row:
        raise ApiError(40421, "书籍不存在", 404)
    assert_can_access_catalog(row, user_id, db)
    store_repo.add_catalog_favorite(db, user_id, catalog_id, utc_now())
    db.commit()
    return {"favorited": True}


def remove_book_favorite(db: Session, user_id: str, catalog_id: str) -> Dict[str, Any]:
    store_repo.remove_catalog_favorite(db, user_id, catalog_id)
    db.commit()
    return {"favorited": False}


def _pair_can_rejoin_catalog(db: Session, pair, viewer_user_id: str) -> bool:
    """是否可再次发起共读申请（无阻塞中的换书/加入申请）。"""
    try:
        reading_service._assert_no_blocking_switch_request(db, pair.pair_id, viewer_user_id)
    except Exception:
        return False
    return True


def _attach_read_action_fields(ui: Dict[str, Any], *, reading_progress_page: Optional[int]) -> Dict[str, Any]:
    """根据共读状态生成阅读按钮文案（开始 / 继续 / 自己重读）。"""
    progress = int(reading_progress_page or 0)
    if ui.get("pair_both_finished") or ui.get("pair_book_status") in {BOOK_STATUS_FINISHED, BOOK_STATUS_SWITCHED}:
        if progress > 1:
            return {
                **ui,
                "read_action": "continue",
                "read_action_label": "继续阅读",
                "read_action_sub": "个人进度续读",
            }
        return {
            **ui,
            "read_action": "reread",
            "read_action_label": "自己重读",
            "read_action_sub": "从第 1 页开始，个人进度",
        }
    if ui.get("is_current_pair_book") or (ui.get("in_pair_catalog") and ui.get("pair_book_status") == BOOK_STATUS_READING):
        if progress > 1:
            return {
                **ui,
                "read_action": "continue",
                "read_action_label": "继续阅读",
                "read_action_sub": "回到当前共读",
            }
        return {
            **ui,
            "read_action": "start",
            "read_action_label": "开始阅读",
            "read_action_sub": "先翻几页",
        }
    if progress > 1:
        return {
            **ui,
            "read_action": "continue",
            "read_action_label": "继续阅读",
            "read_action_sub": "从上次进度继续",
        }
    return {
        **ui,
        "read_action": "start",
        "read_action_label": "开始阅读",
        "read_action_sub": "先翻几页",
    }


def _pair_catalog_ui_state(
    db: Session,
    viewer_user_id: Optional[str],
    catalog_id: str,
    row: CatalogBook,
    *,
    has_local: bool,
    lazy: bool,
) -> Dict[str, Any]:
    """详情页共读按钮：是否已在共读目录、展示文案与可执行动作。"""
    readable = bool(has_local or lazy or catalog_allows_placeholder_pair(row))
    base = {
        "in_pair_catalog": False,
        "pair_book_id": None,
        "pair_book_status": None,
        "pair_both_finished": False,
        "is_current_pair_book": False,
        "pair_action": "none",
        "pair_action_label": "无正文",
        "pair_action_sub": "",
        "can_add_to_pair": False,
        "read_action": "start",
        "read_action_label": "开始阅读",
        "read_action_sub": "先翻几页",
    }
    if not readable:
        return base
    if not viewer_user_id:
        return {
            **base,
            "pair_action": "add",
            "pair_action_label": "加入共读",
            "pair_action_sub": "放进书桌",
            "can_add_to_pair": True,
        }

    pair = reading_repo.get_active_pair(db, viewer_user_id)
    if not pair:
        return {
            **base,
            "pair_action": "add",
            "pair_action_label": "加入共读",
            "pair_action_sub": "需先绑定伙伴",
            "can_add_to_pair": True,
        }

    existing = reading_repo.get_pair_book_by_catalog_id(db, pair.pair_id, catalog_id)
    current = reading_repo.get_current_book(db, pair.pair_id)
    if existing:
        is_current = bool(current and current.book_id == existing.book_id)
        if existing.status == BOOK_STATUS_READING:
            ui = {
                "in_pair_catalog": True,
                "pair_book_id": existing.book_id,
                "pair_book_status": existing.status,
                "pair_both_finished": False,
                "is_current_pair_book": is_current,
                "pair_action": "view",
                "pair_action_label": "看进度",
                "pair_action_sub": "已在共读",
                "can_add_to_pair": True,
            }
            return ui
        # 已读完或中途换书：支持个人重读 + 再次申请共读
        both_finished = existing.status == BOOK_STATUS_FINISHED and reading_service.book_is_truly_finished(db, existing)
        can_rejoin = _pair_can_rejoin_catalog(db, pair, viewer_user_id)
        if current and current.status == BOOK_STATUS_READING and not is_current:
            return {
                "in_pair_catalog": True,
                "pair_book_id": existing.book_id,
                "pair_book_status": existing.status,
                "pair_both_finished": both_finished,
                "is_current_pair_book": False,
                "pair_action": "switch",
                "pair_action_label": "再次共读",
                "pair_action_sub": "需伙伴同意并换书",
                "can_add_to_pair": can_rejoin,
            }
        return {
            "in_pair_catalog": True,
            "pair_book_id": existing.book_id,
            "pair_book_status": existing.status,
            "pair_both_finished": both_finished,
            "is_current_pair_book": False,
            "pair_action": "rejoin" if can_rejoin else "in_catalog",
            "pair_action_label": "重新共读" if can_rejoin else ("已读完" if both_finished else "已共读"),
            "pair_action_sub": "需伙伴同意" if can_rejoin else ("双方已到末页" if both_finished else "进度可查"),
            "can_add_to_pair": can_rejoin,
        }

    switch_state = reading_service.get_book_switch_state(db, pair, viewer_user_id)
    incoming = switch_state.get("incoming")
    outgoing = switch_state.get("outgoing")
    if incoming:
        return {
            **base,
            "pair_action": "switch_review",
            "pair_action_label": "待处理",
            "pair_action_sub": "伙伴换书",
            "can_add_to_pair": False,
            "book_switch_incoming": incoming,
        }
    if outgoing:
        if (outgoing.get("catalog_id") or "") == catalog_id:
            return {
                **base,
                "pair_action": "switch_pending",
                "pair_action_label": "待同意",
                "pair_action_sub": "已申请",
                "can_add_to_pair": False,
                "book_switch_outgoing": outgoing,
            }
        return {
            **base,
            "pair_action": "switch_pending",
            "pair_action_label": "申请中",
            "pair_action_sub": "等待伙伴",
            "can_add_to_pair": False,
            "book_switch_outgoing": outgoing,
        }

    if current and current.status == "reading":
        return {
            **base,
            "pair_action": "switch",
            "pair_action_label": "申请换书",
            "pair_action_sub": "需伙伴同意",
            "can_add_to_pair": True,
        }

    return {
        **base,
        "pair_action": "add",
        "pair_action_label": "加入共读",
        "pair_action_sub": "放进书桌",
        "can_add_to_pair": True,
    }


def get_book(db: Session, catalog_id: str, viewer_user_id: Optional[str] = None) -> Dict[str, Any]:
    row = store_repo.get_catalog_book(db, catalog_id)
    if not row:
        raise ApiError(40421, "书籍不存在", 404)
    assert_can_access_catalog(row, viewer_user_id, db)
    content = store_repo.get_catalog_content(db, catalog_id)
    has_local = content is not None
    lazy = _lazy_gutendex_readable(row, has_local)
    ext_url = _external_link_for_row(row, has_local, lazy)
    reader_mode = "pager" if (has_local or lazy) else ("external" if ext_url else "none")
    pair_ui = _pair_catalog_ui_state(db, viewer_user_id, catalog_id, row, has_local=has_local, lazy=lazy)
    category = _category_for_row(row)
    total_pages_val = int(content.total_pages) if content else None
    if total_pages_val is None and getattr(row, "placeholder_pages", None):
        total_pages_val = int(row.placeholder_pages or 0) or None
    rating = getattr(row, "douban_rating", None) or ""
    reading_progress_page = None
    if viewer_user_id and (has_local or lazy):
        reading_progress_page = resolve_user_catalog_last_page(
            db,
            viewer_user_id,
            catalog_id,
            total_pages=total_pages_val,
            sync_if_drift=False,
        )
    is_favorited = False
    if viewer_user_id:
        is_favorited = store_repo.is_catalog_favorited(db, viewer_user_id, catalog_id)
    pair_ui = _attach_read_action_fields(pair_ui, reading_progress_page=reading_progress_page)
    return {
        "book": {
            "catalog_id": row.catalog_id,
            "title": row.title,
            "author": row.author,
            "language": row.language,
            "cover_url": row.cover_url,
            "has_text": has_local or lazy,
            "has_local_text": has_local,
            "reader_mode": reader_mode,
            "external_read_url": ext_url,
            "can_add_to_pair": pair_ui["can_add_to_pair"],
            "in_pair_catalog": pair_ui["in_pair_catalog"],
            "pair_book_id": pair_ui["pair_book_id"],
            "pair_book_status": pair_ui["pair_book_status"],
            "is_current_pair_book": pair_ui["is_current_pair_book"],
            "pair_action": pair_ui["pair_action"],
            "pair_action_label": pair_ui["pair_action_label"],
            "pair_action_sub": pair_ui["pair_action_sub"],
            "book_switch_incoming": pair_ui.get("book_switch_incoming"),
            "book_switch_outgoing": pair_ui.get("book_switch_outgoing"),
            "pair_both_finished": pair_ui.get("pair_both_finished", False),
            "read_action": pair_ui.get("read_action", "start"),
            "read_action_label": pair_ui.get("read_action_label", "开始阅读"),
            "read_action_sub": pair_ui.get("read_action_sub", "先翻几页"),
            "douban_rating": rating,
            "reading_progress_page": reading_progress_page,
            "is_favorited": is_favorited,
            "category": category,
            "category_label": _category_label(category),
            "total_pages": total_pages_val,
            "intro": _build_intro(row),
            "quality_reviews": _build_quality_reviews(row, has_local_text=has_local),
            "detail_url": (row.detail_url or "").strip(),
        }
    }


def get_catalog_toc(db: Session, catalog_id: str, reader_user_id: Optional[str] = None) -> Dict[str, Any]:
    """全文扫描生成目录。目录是增强能力，失败时返回空列表，不能影响阅读主链路。"""
    book = store_repo.get_catalog_book(db, catalog_id)
    if not book:
        raise ApiError(40421, "书籍不存在", 404)
    assert_can_access_catalog(book, reader_user_id, db)
    try:
        hydrate_catalog_if_needed(db, book)
        db.flush()
    except Exception as exc:
        logger.warning("目录生成前补全文失败 %s: %s", catalog_id, exc)
        db.rollback()
    content = store_repo.get_catalog_content(db, catalog_id)
    if not content:
        return {
            "catalog_id": catalog_id,
            "page_size_chars": DEFAULT_PAGE_CHARS,
            "total_pages": None,
            "chapters": [],
            "chapter_count": 0,
        }
    page_size = int(content.page_size_chars or 1200)
    text = content.content_text or ""
    try:
        chapters = generate_catalog_toc(text, page_size)
    except Exception as exc:
        logger.warning("目录生成失败 %s: %s", catalog_id, exc)
        chapters = []
    return {
        "catalog_id": catalog_id,
        "page_size_chars": page_size,
        "total_pages": int(content.total_pages or 1),
        "chapters": chapters,
        "chapter_count": len(chapters),
    }


def read_page(db: Session, catalog_id: str, page: int = 1, reader_user_id: Optional[str] = None) -> Dict[str, Any]:
    if page < 1:
        raise ApiError(40083, "page 不能小于 1", 400)
    book = store_repo.get_catalog_book(db, catalog_id)
    if not book:
        raise ApiError(40421, "书籍不存在", 404)
    assert_can_access_catalog(book, reader_user_id, db)
    hydrate_catalog_if_needed(db, book)
    db.flush()
    content = store_repo.get_catalog_content(db, catalog_id)
    if not content:
        raise ApiError(40422, "正文不存在", 404)
    _ensure_content_simplified_if_needed(db, book, content)
    db.refresh(content)
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


def _current_pair_book_for_catalog(db: Session, user_id: Optional[str], catalog_id: str):
    if not user_id or not catalog_id:
        return None
    pair = reading_repo.get_active_pair(db, user_id)
    if not pair:
        return None
    current = reading_repo.get_current_book(db, pair.pair_id)
    if not current:
        return None
    if str(getattr(current, "catalog_id", "") or "") != str(catalog_id):
        return None
    return current


def resolve_user_catalog_last_page(
    db: Session,
    user_id: str,
    catalog_id: str,
    *,
    total_pages: Optional[int] = None,
    sync_if_drift: bool = False,
) -> int:
    """
    统一解析用户在某书目的续读页码。
    共读进行中：取 max(书城 catalog 进度, 共读 book 进度, 日记 entry 最高页)。
    非当前共读书：仅 catalog 个人进度。
    """
    catalog_last = store_repo.get_catalog_read_progress(db, user_id, catalog_id)
    catalog_int = int(catalog_last) if catalog_last is not None else 0

    pair_book = _current_pair_book_for_catalog(db, user_id, catalog_id)
    book_int = 0
    entry_int = 0
    if pair_book:
        book_last = reading_repo.get_book_read_progress(db, user_id, pair_book.book_id)
        book_int = int(book_last) if book_last is not None else 0
        entry_int = int(reading_repo.get_user_max_page(db, pair_book.book_id, user_id) or 0)
        # 当前共读书：仅以本次 book 进度为准，避免换绑/新开共读继承旧 catalog 页码
        last = max(1, book_int, entry_int)
    else:
        # 个人阅读或未在共读此书：使用书城 catalog 个人进度
        last = max(1, catalog_int)
    if total_pages and int(total_pages) > 0:
        last = min(last, int(total_pages))

    if sync_if_drift:
        now = utc_now()
        has_real_progress = last > 1 or book_int > 0 or entry_int > 0
        if pair_book:
            if has_real_progress and book_int != last:
                reading_repo.upsert_book_read_progress(db, user_id, pair_book.book_id, last, now)
            # 共读中仅上浮 catalog，避免新 book 把历史个人进度冲掉
            if has_real_progress and last > catalog_int:
                store_repo.upsert_catalog_read_progress(db, user_id, catalog_id, last, now)
        elif catalog_int != last:
            store_repo.upsert_catalog_read_progress(db, user_id, catalog_id, last, now)
        db.commit()

    return last


def get_catalog_reading_progress(db: Session, user_id: str, catalog_id: str) -> Dict[str, Any]:
    book = store_repo.get_catalog_book(db, catalog_id)
    if not book:
        raise ApiError(40421, "书籍不存在", 404)
    assert_can_access_catalog(book, user_id, db)
    content = store_repo.get_catalog_content(db, catalog_id)
    if not content:
        return {"last_page": 1, "total_pages": None}
    total_pages = int(content.total_pages or 1)
    last = resolve_user_catalog_last_page(
        db, user_id, catalog_id, total_pages=total_pages, sync_if_drift=True
    )
    return {"last_page": last, "total_pages": total_pages}


def put_catalog_reading_progress(db: Session, user_id: str, catalog_id: str, page: int) -> Dict[str, Any]:
    book = store_repo.get_catalog_book(db, catalog_id)
    if not book:
        raise ApiError(40421, "书籍不存在", 404)
    assert_can_access_catalog(book, user_id, db)
    hydrate_catalog_if_needed(db, book)
    db.flush()
    content = store_repo.get_catalog_content(db, catalog_id)
    if not content:
        raise ApiError(40422, "暂无正文，无法记录进度", 400)
    total_pages = int(content.total_pages or 1)
    safe_page = max(1, min(int(page), total_pages))
    pair_book = _current_pair_book_for_catalog(db, user_id, catalog_id)
    if pair_book:
        reading_repo.upsert_book_read_progress(db, user_id, pair_book.book_id, safe_page, utc_now())
    store_repo.upsert_catalog_read_progress(db, user_id, catalog_id, safe_page, utc_now())
    db.commit()
    return {"last_page": safe_page, "total_pages": total_pages}


def list_catalog_reader_marks(db: Session, user_id: str, catalog_id: str) -> Dict[str, Any]:
    book = store_repo.get_catalog_book(db, catalog_id)
    if not book:
        raise ApiError(40421, "书籍不存在", 404)
    assert_can_access_catalog(book, user_id, db)
    rows = store_repo.list_catalog_reader_marks(db, user_id, catalog_id)
    return {
        "marks": [
            {
                "page": int(r.page),
                "para_index": int(r.para_index),
                "style": str(r.style or "marker"),
                "note": str(r.note or ""),
                "text_snap": str(r.text_snap or ""),
            }
            for r in rows
        ]
    }


def upsert_catalog_reader_mark(
    db: Session,
    user_id: str,
    catalog_id: str,
    page: int,
    para_index: int,
    style: str,
    note: str,
    text_snap: str,
) -> Dict[str, Any]:
    book = store_repo.get_catalog_book(db, catalog_id)
    if not book:
        raise ApiError(40421, "书籍不存在", 404)
    assert_can_access_catalog(book, user_id, db)
    hydrate_catalog_if_needed(db, book)
    db.flush()
    content = store_repo.get_catalog_content(db, catalog_id)
    if not content:
        raise ApiError(40422, "正文不存在", 400)
    total_pages = int(content.total_pages or 1)
    if page < 1 or page > total_pages:
        raise ApiError(40084, "page 超出正文范围", 400)
    if para_index < 0 or para_index > 50000:
        raise ApiError(40087, "段落序号不合法", 400)
    raw_style = (style or "marker").strip()
    style_key = "underline" if raw_style == "underline" else "marker"
    note_s = (note or "").strip()[:500]
    snap_s = (text_snap or "").strip()[:512]

    existed = store_repo.get_catalog_reader_mark(db, user_id, catalog_id, page, para_index)
    if not existed and store_repo.count_catalog_reader_marks(db, user_id, catalog_id) >= MAX_CATALOG_READER_MARKS:
        raise ApiError(40088, "本书摘抄条数已达上限，可先整理摘抄本", 400)

    store_repo.upsert_catalog_reader_mark(
        db, user_id, catalog_id, page, para_index, style_key, note_s, snap_s, utc_now()
    )
    db.commit()
    return {"ok": True}


def delete_catalog_reader_mark(db: Session, user_id: str, catalog_id: str, page: int, para_index: int) -> Dict[str, Any]:
    book = store_repo.get_catalog_book(db, catalog_id)
    if not book:
        raise ApiError(40421, "书籍不存在", 404)
    assert_can_access_catalog(book, user_id, db)
    store_repo.delete_catalog_reader_mark(db, user_id, catalog_id, page, para_index)
    db.commit()
    return {"ok": True}
