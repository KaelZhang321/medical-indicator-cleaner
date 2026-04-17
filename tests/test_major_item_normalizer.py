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


def test_lookup_major_item_real_sample_catalogs() -> None:
    normalizer = MajorItemNormalizer("data/major_item_dict.csv")

    assert normalizer.lookup("H-凝血功能五项检查")["major_item_standard_name"] == "凝血功能"
    assert normalizer.lookup("H-女性激素八项")["major_item_standard_name"] == "女性激素"
    assert normalizer.lookup("H-女性肿瘤标志物全项")["major_item_standard_name"] == "女性肿瘤标志物"
    assert normalizer.lookup("H-尿常规")["major_item_standard_name"] == "尿常规"
    assert normalizer.lookup("H-尿微量白蛋白三项")["major_item_standard_name"] == "尿微量白蛋白三项"
    assert normalizer.lookup("H-甲功五项TPO")["major_item_standard_name"] == "甲功五项"
    assert normalizer.lookup("H-白带常规")["major_item_standard_name"] == "白带常规"
    assert normalizer.lookup("H-血型鉴定")["major_item_standard_name"] == "血型鉴定"
