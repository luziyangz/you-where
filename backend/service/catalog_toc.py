# -*- coding: utf-8 -*-
"""从书城正文全文自动生成目录条目（基于行首标题样式启发式匹配）。"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# （pattern, kind）：kind 仅用于选取标题清洗方式
_HEADING_LINE_RES: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"^#{1,3}\s*(.+)$"), "md"),
    (re.compile(r"^第\d{1,6}[章节回卷部篇]\s*.{0,100}$"), "zh"),
    (re.compile(r"^第[0-9一二三四五六七八九十百千万〇○零]{1,12}[章节回卷部篇]\s*.{0,100}$"), "zh"),
    (re.compile(r"^(序章|楔子|前言|序言|引子|尾声|后记|附录)[　\s]{0,3}.{0,80}$"), "zh"),
    (re.compile(r"^卷[一二三四五六七八九十0-9〇○零]{1,6}[　\s].{0,60}$"), "zh"),
    (re.compile(r"^(Chapter|CHAPTER)\s+[0-9IVXLC]{1,12}\b\s*.{0,100}$", re.I), "en"),
]


def _normalize_title(raw: str, kind: str) -> str:
    s = re.sub(r"\s+", " ", raw.strip())
    if kind == "md":
        s = re.sub(r"^#+\s*", "", s)
    return s[:120] if s else ""


def _looks_like_prose_noise(line: str) -> bool:
    """过滤明显不像标题的长句。"""
    if len(line) > 96:
        return True
    if line.count("，") >= 5:
        return True
    if line.count("。") >= 2:
        return True
    return False


def generate_catalog_toc(
    content_text: str,
    page_size_chars: int,
    *,
    max_entries: int = 500,
) -> List[Dict[str, Any]]:
    """
    按与 read_page 相同的分页规则（固定字符窗口）估算每条目录的起始页。
    返回 [{"title": str, "page": int}, ...]
    """
    ps = max(1, int(page_size_chars or 1200))
    text = content_text or ""
    entries: List[Dict[str, Any]] = []
    start = 0
    n = len(text)

    while start < n:
        end = text.find("\n", start)
        if end == -1:
            raw_line = text[start:]
            next_start = n
        else:
            raw_line = text[start:end]
            next_start = end + 1

        stripped = raw_line.strip()
        if stripped and not _looks_like_prose_noise(stripped):
            title_out = ""
            for cre, kind in _HEADING_LINE_RES:
                m = cre.match(stripped)
                if not m:
                    continue
                if kind == "md":
                    title_out = _normalize_title(m.group(1), kind)
                else:
                    title_out = _normalize_title(stripped, kind)
                break
            if title_out:
                page = start // ps + 1
                dup = entries and entries[-1]["title"] == title_out and entries[-1]["page"] == page
                if not dup:
                    entries.append({"title": title_out, "page": page})
                    if len(entries) >= max_entries:
                        break

        start = next_start

    return entries
