from __future__ import annotations

from src.major_item_normalizer import MajorItemNormalizer


def test_lookup_major_item_standard_name() -> None:
    normalizer = MajorItemNormalizer("data/major_item_dict.csv")

    result = normalizer.lookup("H-血脂七项")

    assert result == {
        "major_item_standard_code": "PKG-BZ",
        "major_item_standard_name": "血脂七项",
        "major_item_category": "生化检查",
    }


def test_lookup_major_item_with_fullwidth_brackets() -> None:
    normalizer = MajorItemNormalizer("data/major_item_dict.csv")

    result = normalizer.lookup("H-人乳头瘤病毒（HPV）核酸检测（17加6）")

    assert result["major_item_standard_name"] == "HPV核酸检测"


def test_lookup_major_item_not_found() -> None:
    normalizer = MajorItemNormalizer("data/major_item_dict.csv")

    assert normalizer.lookup("H-未知套餐") is None
