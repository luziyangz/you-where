"""
书城 / 导入 TXT / 远程正文 的编码识别与乱码规避。

策略：
1. 优先 HTTP Content-Type 中的 charset；
2. 对多种常见中文编码试解码，按「中文可读性」打分选最优；
3. 检测典型乱码特征并尝试 latin-1/cp1252 → utf-8/gb18030 修复；
4. 禁止用 latin-1 盲解中文小说（会产生看似成功实则乱码的字符串）。
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

# 常见乱码痕迹（UTF-8 被误当 Latin-1/GBK 等）
_MOJIBAKE_MARKERS = (
    "锟斤拷",
    "ï¿½",
    "Ã",
    "Â",
    "â",
    "€",
    "™",
    "¤",
    "※",
    "瀵",
    "鍙",
    "鏂",
)

# 试解码顺序（中文书目优先）
_ENCODING_CANDIDATES_ZH: Tuple[str, ...] = (
    "utf-8-sig",
    "utf-8",
    "gb18030",
    "gbk",
    "big5",
    "cp936",
)

_ENCODING_CANDIDATES_EN: Tuple[str, ...] = (
    "utf-8-sig",
    "utf-8",
    "cp1252",
    "latin-1",
)


def normalize_imported_text(text: str) -> str:
    """统一换行与空白，便于阅读与分页。"""
    value = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t\f\v]+", " ", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def parse_charset_from_content_type(content_type: str) -> Optional[str]:
    if not content_type:
        return None
    match = re.search(r"charset\s*=\s*['\"]?([a-zA-Z0-9_.-]+)", content_type, re.I)
    if not match:
        return None
    name = match.group(1).strip().lower()
    aliases = {
        "utf8": "utf-8",
        "gb2312": "gb18030",
        "gb_2312": "gb18030",
        "x-gbk": "gbk",
    }
    return aliases.get(name, name)


def _cjk_ratio(text: str, sample_len: int = 12000) -> float:
    sample = (text or "")[:sample_len]
    if not sample:
        return 0.0
    cjk = sum(1 for ch in sample if "\u4e00" <= ch <= "\u9fff" or "\u3400" <= ch <= "\u4dbf")
    return cjk / len(sample)


def _text_quality_score(text: str, *, prefer_chinese: bool) -> float:
    """分数越高表示越像正常可读正文。"""
    sample = (text or "")[:12000]
    if not sample:
        return -100.0
    total = len(sample)
    cjk_ratio = _cjk_ratio(text)
    replacement = sample.count("\ufffd")
    ctrl = sum(1 for ch in sample if ord(ch) < 32 and ch not in "\n\t")
    mojibake_hits = sum(sample.count(marker) for marker in _MOJIBAKE_MARKERS)
    # 连续高位拉丁补充区（常见于 UTF-8 误读）
    latin_mess = len(re.findall(r"[\u00c0-\u00ff]{3,}", sample))

    score = 0.0
    if prefer_chinese:
        score += cjk_ratio * 120.0
        if cjk_ratio < 0.02 and total > 200:
            score -= 40.0
    else:
        ascii_ratio = sum(1 for ch in sample if ord(ch) < 128) / total
        score += ascii_ratio * 80.0
        score += min(cjk_ratio * 40.0, 10.0)

    score -= replacement * 15.0
    score -= ctrl * 2.0
    score -= mojibake_hits * 8.0
    score -= latin_mess * 3.0
    return score


def is_likely_garbled(text: str, *, prefer_chinese: bool = True) -> bool:
    sample = (text or "")[:6000]
    if not sample:
        return True
    if sample.count("\ufffd") >= 3:
        return True
    if any(marker in sample for marker in _MOJIBAKE_MARKERS):
        return True
    if prefer_chinese:
        if len(sample) >= 80 and _cjk_ratio(sample) < 0.01:
            # 长文本几乎无汉字，对中文书目视为异常
            if re.search(r"[\u00c0-\u00ff]{4,}", sample):
                return True
    return _text_quality_score(sample, prefer_chinese=prefer_chinese) < 5.0


def try_repair_mojibake(text: str, *, prefer_chinese: bool) -> Optional[str]:
    """尝试修复「UTF-8/GBK 字节被误当作单字节字符」导致的乱码。"""
    if not text:
        return None
    repairs: List[str] = []
    pairs = (
        ("latin-1", "utf-8"),
        ("cp1252", "utf-8"),
    )
    if prefer_chinese:
        pairs = (
            ("latin-1", "gb18030"),
            ("latin-1", "gbk"),
            ("latin-1", "utf-8"),
            ("cp1252", "utf-8"),
        )
    for enc_in, enc_out in pairs:
        try:
            repaired = text.encode(enc_in).decode(enc_out)
        except (UnicodeDecodeError, UnicodeEncodeError):
            continue
        if repaired and not is_likely_garbled(repaired, prefer_chinese=prefer_chinese):
            repairs.append(repaired)
    if not repairs:
        return None
    return max(repairs, key=lambda t: _text_quality_score(t, prefer_chinese=prefer_chinese))


def _build_encoding_try_list(content_type: str, *, prefer_chinese: bool) -> List[str]:
    seen: List[str] = []
    header_charset = parse_charset_from_content_type(content_type)
    if header_charset:
        seen.append(header_charset)
    for enc in _ENCODING_CANDIDATES_ZH if prefer_chinese else _ENCODING_CANDIDATES_EN:
        if enc not in seen:
            seen.append(enc)
    return seen


def _try_utf8_first(raw: bytes, *, prefer_chinese: bool) -> Optional[str]:
    """UTF-8 严格解码成功且可读时直接采用，避免中文 UTF-8 被 GBK 误读。"""
    for enc in ("utf-8-sig", "utf-8"):
        try:
            text = normalize_imported_text(raw.decode(enc))
        except UnicodeDecodeError:
            continue
        if is_likely_garbled(text, prefer_chinese=prefer_chinese):
            continue
        if prefer_chinese and len(text) >= 80 and _cjk_ratio(text) < 0.02:
            continue
        return text
    return None


def decode_text_bytes(
    raw: bytes,
    *,
    content_type: str = "",
    prefer_chinese: bool = True,
    min_quality: float = 0.0,
) -> str:
    """
    将字节解码为 str，自动选择最合适编码并做乱码修复。
    prefer_chinese=True 时优先保证中文可读（导入小说、公版中文书）。
    """
    if not raw:
        return ""

    header_charset = parse_charset_from_content_type(content_type)
    if header_charset and header_charset.lower().replace("_", "-") in ("utf-8", "utf8"):
        fast = _try_utf8_first(raw, prefer_chinese=prefer_chinese)
        if fast:
            return fast

    fast = _try_utf8_first(raw, prefer_chinese=prefer_chinese)
    if fast and not header_charset:
        return fast

    best_text = ""
    best_score = -1e9

    for enc in _build_encoding_try_list(content_type, prefer_chinese=prefer_chinese):
        try:
            candidate = raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        candidate = normalize_imported_text(candidate)
        score = _text_quality_score(candidate, prefer_chinese=prefer_chinese)
        if score > best_score:
            best_score = score
            best_text = candidate

    if not best_text:
        raise ValueError("文本编码无法识别，请使用 UTF-8 或 GB18030 保存后重新导入")

    if is_likely_garbled(best_text, prefer_chinese=prefer_chinese):
        repaired = try_repair_mojibake(best_text, prefer_chinese=prefer_chinese)
        if repaired:
            rep_score = _text_quality_score(repaired, prefer_chinese=prefer_chinese)
            if rep_score > best_score:
                best_text = normalize_imported_text(repaired)
                best_score = rep_score

    if is_likely_garbled(best_text, prefer_chinese=prefer_chinese) or best_score < min_quality:
        raise ValueError("正文疑似乱码，请用 UTF-8 或 GB18030 编码保存 TXT 后重新导入")

    return best_text


def decode_uploaded_txt_bytes(raw: bytes, *, prefer_chinese: bool = True) -> str:
    """用户上传 TXT：解码并校验非乱码（阈值略低于远程抓取，减少误拒）。"""
    return decode_text_bytes(raw, prefer_chinese=prefer_chinese, min_quality=2.0)


def prefer_chinese_for_language(language: str) -> bool:
    lang = (language or "").strip().lower()
    if not lang:
        return True
    if lang.startswith("zh") or lang in {"chi", "zho", "cmn"}:
        return True
    return False


# 常见繁体用字（用于判断是否需要转简体，避免对已是简体的正文重复转换）
_TRADITIONAL_HINT_CHARS = frozenset(
    "國學會說這裡體臺灣為時們來個們開關門車長見雲電氣頭發東無經進遠選連還過達邊員萬與專業書畫聲聽視覺網際網路機構製造產業經濟貿易環境資訊處裡應該讓認識問題實際現實歷史傳統現代標準規範質量優質關係聯繫聯系聯絡聯系"
)

_opencc_t2s = None


def _get_opencc_t2s():
    global _opencc_t2s
    if _opencc_t2s is None:
        from opencc import OpenCC

        _opencc_t2s = OpenCC("t2s")
    return _opencc_t2s


def is_likely_traditional_chinese(text: str, sample_len: int = 6000) -> bool:
    """抽样判断正文是否以繁体为主（中文书目）。"""
    sample = (text or "")[:sample_len]
    if len(sample) < 12:
        return False
    cjk = sum(1 for ch in sample if "\u4e00" <= ch <= "\u9fff")
    if cjk < 8:
        return False
    trad_hits = sum(1 for ch in sample if ch in _TRADITIONAL_HINT_CHARS)
    if trad_hits >= max(3, int(cjk * 0.008)):
        return True
    # 短样本：繁体字占比高时仍视为繁体
    return cjk >= 8 and (trad_hits / cjk) >= 0.12


def to_simplified_chinese(text: str) -> str:
    """将繁体中文转为简体（OpenCC t2s）。"""
    if not text:
        return text
    try:
        return _get_opencc_t2s().convert(text)
    except Exception:
        return text


def finalize_chinese_plaintext(text: str, *, language: str = "") -> str:
    """中文正文入库前统一为简体，避免书城显示繁体。"""
    value = normalize_imported_text(text or "")
    if not prefer_chinese_for_language(language):
        return value
    if not is_likely_traditional_chinese(value):
        return value
    return normalize_imported_text(to_simplified_chinese(value))
