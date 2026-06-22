"""
共读评价生成：基于真实评分（豆瓣 / 热度映射）与分类、书目特征生成差异化文案。
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional, Sequence

from common.models import CatalogBook

# 分类 → 共读评价话术池（每本书按 catalog_id 稳定选取，避免全书雷同）
_CATEGORY_REVIEW_POOLS: Dict[str, List[str]] = {
    "fiction": [
        "章回结构清晰，适合按周约定进度，方便和伙伴对齐人物关系变化。",
        "叙事张力足，讨论时容易从情节转折延伸到价值判断。",
        "篇幅较长但回目独立，适合拆成阶段目标共读。",
        "人物动机饱满，适合一人主读、一人做人物笔记的对读方式。",
    ],
    "classical": [
        "篇章短小，适合每日共读一段并交换注解理解。",
        "义理密度高，适合先读原文再讨论现实映射。",
        "文本稳定，适合作为长期共读的基础书目。",
        "名句集中，适合摘句共读并各自阐释。",
    ],
    "poetry": [
        "以短章为主，适合每天共读数首并分享意象感受。",
        "诗话体例便于跳跃阅读，讨论时可聚焦单条观点。",
        "语言凝练，适合朗读式共读并比较不同版本理解。",
        "名篇集中，适合按主题（送别、山水、咏物）分周推进。",
    ],
    "world_fiction": [
        "经典叙事完整，适合跨文化视角讨论人物与时代背景。",
        "情节推进明确，适合英文原著或译本对照共读。",
        "主题普世，便于从个人经验出发交流读后感受。",
        "结构完整，适合按幕或章节设定共读里程碑。",
    ],
    "literature": [
        "现实感强，适合结合生活经验做开放式讨论。",
        "人物心理刻画细，适合聚焦关键场景共读复盘。",
        "当代语境亲切，容易形成观点碰撞但篇幅可控。",
        "叙事节奏适中，适合两周一个情节单元推进。",
    ],
    "history": [
        "以史实线索为主，适合按时间线共读并做阶段小结。",
        "人物传记段落独立，适合轮流选篇共读。",
        "因果链条长，适合共读时记录「事件—决策—后果」。",
        "史料叙事强，适合一人读原文、一人补充背景知识。",
    ],
    "philosophy": [
        "命题集中，适合每次共读围绕一个概念深入讨论。",
        "短章多、跳跃小，适合慢读并写共读札记。",
        "思辨性强，适合对照自身选择做反思型共读。",
        "文本可反复咀嚼，适合多轮重读同一章节。",
    ],
    "medicine": [
        "概念条目化，适合共读时整理术语表与示意图。",
        "篇章主题明确，适合按篇目分工阅读后互相讲解。",
        "偏文献阅读，适合强调「理解概念」而非医疗建议。",
        "经典结构稳定，适合作为传统文化主题的共读材料。",
    ],
}

_REVIEWER_POOL = [
    "豆瓣读书会",
    "共读节奏官",
    "阅读伴侣小组",
    "书房荐书官",
    "公版书友",
]

_SOURCE_LABEL = {
    "manifest": "豆瓣参考",
    "project_gutenberg": "公版热度",
    "gutendex": "读者热度",
    "user_txt": "导入书目",
    "user_url": "链接书目",
    "builtin": "导读共读",
}


def quality_level_by_rating(rating: float) -> str:
    if rating >= 9.0:
        return "神作"
    if rating >= 8.5:
        return "力荐"
    if rating >= 8.0:
        return "优秀"
    if rating >= 7.0:
        return "推荐"
    if rating >= 6.0:
        return "可读"
    return "选读"


def _stable_index(seed: str, modulo: int) -> int:
    if modulo <= 0:
        return 0
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo


def parse_rating_value(raw: Optional[str]) -> Optional[float]:
    text = (raw or "").strip()
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    if value > 10.0:
        value = value / 10.0
    return max(1.0, min(10.0, round(value, 1)))


def resolve_primary_rating(
    book: CatalogBook,
    *,
    meta_douban: str = "",
    has_local_text: bool = False,
) -> tuple[float, str]:
    """
    解析主评分与来源说明。
    返回 (分数, 来源标签)。
    """
    for raw in (
        getattr(book, "douban_rating", None),
        meta_douban,
    ):
        parsed = parse_rating_value(str(raw or ""))
        if parsed is not None:
            label = _SOURCE_LABEL.get(book.source, "综合参考")
            if book.source == "manifest":
                label = "豆瓣参考"
            return parsed, label

    # 无豆瓣分：按来源与是否可全文略作区分（仍保持稳定，非随机）
    seed = book.catalog_id or book.title
    base = 7.2 + (_stable_index(seed, 8) * 0.15)
    if has_local_text:
        base = min(9.2, base + 0.35)
    if book.source in {"project_gutenberg", "gutendex"}:
        base = min(9.0, base + 0.2)
    return round(base, 1), _SOURCE_LABEL.get(book.source, "共读参考")


def _pick_pool_line(category: str, catalog_id: str, title: str) -> str:
    pool = _CATEGORY_REVIEW_POOLS.get(category) or _CATEGORY_REVIEW_POOLS["literature"]
    idx = _stable_index(f"{catalog_id}:{category}", len(pool))
    line = pool[idx]
    short_title = (title or "").strip()
    if short_title and len(short_title) <= 12 and _stable_index(catalog_id, 3) == 0:
        return f"《{short_title}》{line}"
    return line


def _score_comment(score: float, label: str) -> str:
    if score >= 9.0:
        tier = "口碑极高"
    elif score >= 8.5:
        tier = "评价很好"
    elif score >= 8.0:
        tier = "整体靠谱"
    elif score >= 7.0:
        tier = "值得一读"
    else:
        tier = "适合选读"
    return f"{label} {score:.1f} 分，{tier}。"


def build_quality_reviews(
    book: CatalogBook,
    *,
    store_category: str,
    meta: Optional[Dict[str, Any]] = None,
    builtin_reviews: Optional[Sequence[Dict[str, Any]]] = None,
    has_local_text: bool = False,
) -> List[Dict[str, Any]]:
    """
    生成 1～2 条共读评价。builtin 书目优先使用手工配置；其余按评分+分类生成。
    """
    if builtin_reviews:
        out: List[Dict[str, Any]] = []
        for row in builtin_reviews:
            if not isinstance(row, dict):
                continue
            item = dict(row)
            rating = parse_rating_value(str(item.get("rating") or "")) or 4.5
            # 导读书目历史数据为 5 分制，与豆瓣 10 分制对齐展示
            if rating <= 5.0:
                rating = round(rating * 2, 1)
            item["rating"] = rating
            item["quality_level"] = quality_level_by_rating(float(rating))
            out.append(item)
        return out[:3]

    meta = meta or {}
    primary, label = resolve_primary_rating(
        book,
        meta_douban=str(meta.get("douban_rating") or ""),
        has_local_text=has_local_text,
    )

    catalog_id = book.catalog_id or ""
    title = book.title or ""
    category = store_category or "literature"

    # 第二条评分在主分附近小幅波动（由书目 id 决定，稳定且不完全相同）
    delta = (_stable_index(f"{catalog_id}:delta", 5) - 2) * 0.1
    secondary = max(1.0, min(10.0, round(primary + delta, 1)))

    reviewer_a = _REVIEWER_POOL[_stable_index(f"{catalog_id}:a", len(_REVIEWER_POOL))]
    reviewer_b = _REVIEWER_POOL[_stable_index(f"{catalog_id}:b", len(_REVIEWER_POOL))]
    if reviewer_a == reviewer_b:
        reviewer_b = _REVIEWER_POOL[(_stable_index(f"{catalog_id}:b2", len(_REVIEWER_POOL)) + 1) % len(_REVIEWER_POOL)]

    line_a = _pick_pool_line(category, catalog_id, title)
    line_b = _pick_pool_line(category, f"{catalog_id}:b", title)

    reviews = [
        {
            "reviewer": reviewer_a,
            "rating": primary,
            "content": _score_comment(primary, label) + line_a,
            "quality_level": quality_level_by_rating(primary),
            "rating_source": label,
        },
        {
            "reviewer": reviewer_b,
            "rating": secondary,
            "content": line_b,
            "quality_level": quality_level_by_rating(secondary),
            "rating_source": "共读体验",
        },
    ]
    return reviews


def format_top_review(reviews: List[Dict[str, Any]], max_len: int = 48) -> str:
    """书城列表摘要：评分 + 一句差异化理由。"""
    if not reviews:
        return ""
    first = reviews[0]
    rating = first.get("rating")
    content = str(first.get("content") or "").strip()
    # 去掉重复的「豆瓣参考 9.x 分，口碑极高。」前缀在列表里过长时，保留后半句
    if "。" in content and len(content) > 28:
        parts = content.split("。", 1)
        if len(parts) > 1 and parts[1].strip():
            snippet = parts[1].strip()
        else:
            snippet = content
    else:
        snippet = content
    if rating is not None:
        head = f"{float(rating):.1f}分"
        text = f"{head} · {snippet}" if snippet else head
    else:
        text = snippet
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 1].rstrip()}…"
