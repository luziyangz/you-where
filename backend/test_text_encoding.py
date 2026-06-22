# -*- coding: utf-8 -*-
"""文本编码与乱码检测"""

from service.text_encoding import (
    decode_text_bytes,
    decode_uploaded_txt_bytes,
    finalize_chinese_plaintext,
    is_likely_garbled,
    is_likely_traditional_chinese,
    try_repair_mojibake,
)


def test_decode_utf8_chinese():
    raw = "第一章\n\n你好，世界。".encode("utf-8")
    text = decode_text_bytes(raw, prefer_chinese=True)
    assert "你好" in text
    assert not is_likely_garbled(text)


def test_decode_gbk_chinese():
    raw = "第二章\n\n红楼梦节选。".encode("gbk")
    text = decode_text_bytes(raw, prefer_chinese=True)
    assert "红楼梦" in text
    assert not is_likely_garbled(text)


def test_decode_gbk_with_charset_header():
    raw = "第三节内容。".encode("gb18030")
    text = decode_text_bytes(raw, content_type="text/plain; charset=gb2312", prefer_chinese=True)
    assert "第三节" in text


def test_repair_utf8_misread_as_latin1():
    original = "测试导入正文。".encode("utf-8")
    broken = original.decode("latin-1")
    repaired = try_repair_mojibake(broken, prefer_chinese=True)
    assert repaired is not None
    assert "测试" in repaired


def test_upload_gbk_file():
    body = "\u7b2c\u4e09\u7ae0\n\n" + "\u5bfc\u5165\u5c0f\u8bf4\u6b63\u6587\u3002" * 20
    text = decode_uploaded_txt_bytes(body.encode("gbk"), prefer_chinese=True)
    assert "\u5bfc\u5165\u5c0f\u8bf4" in text


def test_english_gutenberg_utf8():
    raw = "Chapter 1\n\nIt was a bright cold day.".encode("utf-8")
    text = decode_text_bytes(raw, prefer_chinese=False)
    assert "Chapter" in text
    assert not is_likely_garbled(text, prefer_chinese=False)


def test_finalize_traditional_to_simplified():
    trad = ("\u570b\u5b78\u81fa\u7063\uff0c\u9019\u88e1\u662f\u7e41\u9ad4\u6e2c\u8a66\u3002" * 8).strip()
    assert is_likely_traditional_chinese(trad)
    simp = finalize_chinese_plaintext(trad, language="zh")
    assert "\u56fd" in simp
    assert "\u53f0" in simp
    assert "\u570b" in trad
