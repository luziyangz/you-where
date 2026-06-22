# -*- coding: utf-8 -*-

from common.models import CatalogBook
from service.store_reviews import build_quality_reviews, format_top_review, resolve_primary_rating


def _book(**kwargs) -> CatalogBook:
    defaults = dict(
        catalog_id="pg_23962",
        source="project_gutenberg",
        source_book_id="23962",
        title="西游记",
        author="吴承恩",
        language="zh",
        cover_url="",
        detail_url="",
        text_url="http://example.com",
        douban_rating="9.3",
        created_at="Z",
        updated_at="Z",
    )
    defaults.update(kwargs)
    return CatalogBook(**defaults)


def test_douban_rating_used_for_primary():
    book = _book()
    score, label = resolve_primary_rating(book, has_local_text=True)
    assert score == 9.3
    assert label == "公版热度"


def test_reviews_differ_by_catalog_id():
    a = build_quality_reviews(_book(catalog_id="pg_23962"), store_category="fiction", has_local_text=True)
    b = build_quality_reviews(_book(catalog_id="pg_24264", title="红楼梦"), store_category="fiction", has_local_text=True)
    assert a[0]["content"] != b[0]["content"]
    assert a[0]["rating"] == 9.3
    assert a[1]["content"] != a[0]["content"]


def test_top_review_includes_score():
    reviews = build_quality_reviews(_book(), store_category="fiction", has_local_text=True)
    top = format_top_review(reviews)
    assert "9.3" in top
    assert "分" in top
