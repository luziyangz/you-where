"""书城分类规则单元测试"""

from service.store_categories import (
    LEGACY_CATEGORY_MAP,
    classify_book,
    normalize_category_key,
)


def test_legacy_category_alias():
    assert normalize_category_key("foreign_classics") == "world_fiction"
    assert normalize_category_key("xin_xue") == "philosophy"


def test_public_domain_novels_are_fiction():
    assert classify_book(title="西游记", language="zh", source="project_gutenberg", meta_category="fiction") == "fiction"
    assert classify_book(title="红楼梦", language="zh", source="project_gutenberg") == "fiction"


def test_classical_and_poetry():
    assert classify_book(title="论语", language="zh", meta_category="classical") == "classical"
    assert classify_book(title="李太白集", language="zh") == "poetry"
    assert classify_book(title="随园诗话", language="zh", meta_category="poetry") == "poetry"


def test_manifest_modern_literature():
    assert classify_book(catalog_id="manifest_db_huozhe", title="活着", author="余华", source="manifest") == "literature"
    assert classify_book(catalog_id="manifest_db_santi", title="三体", author="刘慈欣", source="manifest") == "fiction"
    assert classify_book(title="白夜行", author="东野圭吾", source="manifest") == "world_fiction"


def test_gutendex_english_default_world_fiction():
    assert (
        classify_book(
            title="Dracula",
            author="Stoker, Bram",
            language="en",
            source="gutendex",
            subjects=["Horror", "Gothic fiction"],
        )
        == "world_fiction"
    )
