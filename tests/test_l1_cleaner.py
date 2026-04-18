from __future__ import annotations

from src.dict_manager import DictManager
from src.l1_rule_cleaner import L1RuleCleaner


def build_cleaner() -> L1RuleCleaner:
    manager = DictManager("data/standard_dict.csv", "data/alias_dict.csv")
    return L1RuleCleaner(manager)


def test_strip_whitespace() -> None:
    cleaner = build_cleaner()
    assert cleaner._strip("  血糖\t") == "血糖"


def test_strip_tabs_newlines() -> None:
    cleaner = build_cleaner()
    assert cleaner._strip("\n\t总胆固醇 \r") == "总胆固醇"


def test_remove_star_prefix() -> None:
    cleaner = build_cleaner()
    assert cleaner._remove_star_prefix("★甲胎蛋白(AFP)") == "甲胎蛋白(AFP)"


def test_remove_star_with_space() -> None:
    cleaner = build_cleaner()
    assert cleaner._remove_star_prefix("★ 甲胎蛋白") == "甲胎蛋白"


def test_no_star() -> None:
    cleaner = build_cleaner()
    assert cleaner._remove_star_prefix("甲胎蛋白") == "甲胎蛋白"


def test_fullwidth_brackets() -> None:
    cleaner = build_cleaner()
    assert cleaner._fullwidth_to_halfwidth("血红蛋白（HGB）") == "血红蛋白(HGB)"


def test_mixed_brackets() -> None:
    cleaner = build_cleaner()
    assert cleaner._fullwidth_to_halfwidth("★类风湿因子(RF）") == "★类风湿因子(RF)"


def test_fullwidth_colon() -> None:
    cleaner = build_cleaner()
    assert cleaner._fullwidth_to_halfwidth("参考值：正常") == "参考值:正常"


def test_fullwidth_numbers() -> None:
    cleaner = build_cleaner()
    assert cleaner._fullwidth_to_halfwidth("０１２") == "012"


def test_extract_english_abbr() -> None:
    cleaner = build_cleaner()
    assert cleaner._extract_abbreviation_from_brackets("总胆固醇(TC)") == ("总胆固醇", "TC")


def test_extract_complex_abbr() -> None:
    cleaner = build_cleaner()
    assert cleaner._extract_abbreviation_from_brackets("D-二聚体(D-Dimer)") == ("D-二聚体", "D-Dimer")


def test_extract_with_dot() -> None:
    cleaner = build_cleaner()
    assert cleaner._extract_abbreviation_from_brackets("国际标准化比值(PT.INR)") == ("国际标准化比值", "PT.INR")


def test_extract_with_beta() -> None:
    cleaner = build_cleaner()
    assert cleaner._extract_abbreviation_from_brackets("β-人绒毛膜促性腺激素(β-HCG)") == ("β-人绒毛膜促性腺激素", "β-HCG")


def test_no_extract_chinese_in_brackets() -> None:
    cleaner = build_cleaner()
    assert cleaner._extract_abbreviation_from_brackets("鱼(鳕鱼)特异性IgG抗体") == ("鱼(鳕鱼)特异性IgG抗体", None)


def test_no_extract_hpv_type() -> None:
    cleaner = build_cleaner()
    assert cleaner._extract_abbreviation_from_brackets("HPV16(高危)") == ("HPV16(高危)", None)


def test_extract_with_roman() -> None:
    cleaner = build_cleaner()
    assert cleaner._extract_abbreviation_from_brackets("抗凝血酶活性测定(AT Ⅲ)") == ("抗凝血酶活性测定", "AT Ⅲ")


def test_remove_trailing_dot() -> None:
    cleaner = build_cleaner()
    assert cleaner._remove_trailing_punctuation("血脂.") == "血脂"


def test_remove_trailing_comma() -> None:
    cleaner = build_cleaner()
    assert cleaner._remove_trailing_punctuation("血糖,") == "血糖"


def test_preserve_internal_hyphen() -> None:
    cleaner = build_cleaner()
    assert cleaner._remove_trailing_punctuation("D-二聚体") == "D-二聚体"


def test_remove_chinese_internal_space() -> None:
    cleaner = build_cleaner()
    assert cleaner._remove_internal_spaces("血 糖") == "血糖"


def test_preserve_english_space() -> None:
    cleaner = build_cleaner()
    assert cleaner._remove_internal_spaces("25-OH VitD") == "25-OH VitD"


def test_multiple_chinese_spaces() -> None:
    cleaner = build_cleaner()
    assert cleaner._remove_internal_spaces("血 红 蛋 白") == "血红蛋白"


def test_clean_removes_unit_suffix_in_brackets() -> None:
    cleaner = build_cleaner()
    result = cleaner.clean("总胆固醇(mmol/L)")

    assert result.cleaned == "总胆固醇"
    assert result.abbreviation is None
    assert result.standard_code == "040201"


def test_clean_full_pipeline_star_brackets() -> None:
    cleaner = build_cleaner()
    result = cleaner.clean("★甲胎蛋白(AFP)")

    assert result.cleaned == "甲胎蛋白"
    assert result.abbreviation == "AFP"
    assert result.standard_name == "甲胎蛋白"
    assert result.standard_code == "040702"
    assert result.match_source == "alias_exact"
    assert result.confidence == 1.0


def test_clean_full_pipeline_mixed_brackets() -> None:
    cleaner = build_cleaner()
    result = cleaner.clean("★类风湿因子(RF）")

    assert result.cleaned == "类风湿因子"
    assert result.abbreviation == "RF"
    assert result.standard_name == "类风湿因子"
    assert result.standard_code == "050801"


def test_clean_lookup_hit() -> None:
    cleaner = build_cleaner()
    result = cleaner.clean("总胆固醇(TC)")

    assert result.standard_name == "总胆固醇"
    assert result.standard_code == "040201"
    assert result.match_source == "alias_exact"


def test_clean_lookup_miss() -> None:
    cleaner = build_cleaner()
    result = cleaner.clean("某某新检测项")

    assert result.standard_name is None
    assert result.standard_code is None
    assert result.match_source == "unmatched"
    assert result.confidence == 0.0


def test_clean_hpv_keeps_chinese_bracket() -> None:
    cleaner = build_cleaner()
    result = cleaner.clean("HPV16(高危)")

    assert result.cleaned == "HPV16(高危)"
    assert result.abbreviation is None


def test_clean_major_item_name_h_prefix() -> None:
    cleaner = build_cleaner()
    assert cleaner.clean_major_item_name("H-血脂七项") == "血脂七项"


def test_clean_major_item_name_fullwidth() -> None:
    cleaner = build_cleaner()
    assert cleaner.clean_major_item_name("H-人乳头瘤病毒（HPV）核酸检测（17加6）") == "人乳头瘤病毒(HPV)核酸检测(17加6)"
