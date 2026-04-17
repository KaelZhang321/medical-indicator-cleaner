from __future__ import annotations

from src.result_parser import ResultParser


def test_parse_simple_numeric() -> None:
    parser = ResultParser()

    result = parser.parse("1.74", existing_unit="IU/mL")

    assert result == {
        "numeric_value": 1.74,
        "text_value": None,
        "unit": "IU/mL",
        "qualifier": None,
        "judgment": None,
        "ref_in_value": None,
    }


def test_parse_with_unit_in_value() -> None:
    parser = ResultParser()

    result = parser.parse("28.2kg")

    assert result == {
        "numeric_value": 28.2,
        "text_value": None,
        "unit": "kg",
        "qualifier": None,
        "judgment": None,
        "ref_in_value": None,
    }


def test_parse_with_unit_and_ref_and_judgment() -> None:
    parser = ResultParser()

    result = parser.parse("7.4kg  (7.7-9.4)   偏低")

    assert result == {
        "numeric_value": 7.4,
        "text_value": None,
        "unit": "kg",
        "qualifier": None,
        "judgment": "偏低",
        "ref_in_value": "7.7-9.4",
    }


def test_parse_percent_with_ref() -> None:
    parser = ResultParser()

    result = parser.parse("31.8%(18.0-28.0) 偏高")

    assert result == {
        "numeric_value": 31.8,
        "text_value": None,
        "unit": "%",
        "qualifier": None,
        "judgment": "偏高",
        "ref_in_value": "18.0-28.0",
    }


def test_parse_qualifier_less_than() -> None:
    parser = ResultParser()

    result = parser.parse("< 2.30")

    assert result == {
        "numeric_value": 2.30,
        "text_value": None,
        "unit": "",
        "qualifier": "<",
        "judgment": None,
        "ref_in_value": None,
    }


def test_parse_qualifier_no_space() -> None:
    parser = ResultParser()

    result = parser.parse("<0.0250")

    assert result == {
        "numeric_value": 0.025,
        "text_value": None,
        "unit": "",
        "qualifier": "<",
        "judgment": None,
        "ref_in_value": None,
    }


def test_parse_qualitative_with_numeric() -> None:
    parser = ResultParser()

    result = parser.parse("0.07（阴性 -）")

    assert result == {
        "numeric_value": 0.07,
        "text_value": "阴性",
        "unit": "",
        "qualifier": None,
        "judgment": None,
        "ref_in_value": None,
    }


def test_parse_comma_separated() -> None:
    parser = ResultParser()

    result = parser.parse("80.8,正常")

    assert result == {
        "numeric_value": 80.8,
        "text_value": None,
        "unit": "",
        "qualifier": None,
        "judgment": "正常",
        "ref_in_value": None,
    }


def test_parse_pure_qualitative() -> None:
    parser = ResultParser()

    result = parser.parse("阳性（+）")

    assert result == {
        "numeric_value": None,
        "text_value": "阳性",
        "unit": "",
        "qualifier": None,
        "judgment": None,
        "ref_in_value": None,
    }


def test_parse_text_type() -> None:
    parser = ResultParser()

    result = parser.parse("O型")

    assert result == {
        "numeric_value": None,
        "text_value": "O型",
        "unit": "",
        "qualifier": None,
        "judgment": None,
        "ref_in_value": None,
    }


def test_parse_text_clean() -> None:
    parser = ResultParser()

    result = parser.parse("清亮")

    assert result == {
        "numeric_value": None,
        "text_value": "清亮",
        "unit": "",
        "qualifier": None,
        "judgment": None,
        "ref_in_value": None,
    }


def test_parse_level() -> None:
    parser = ResultParser()

    result = parser.parse("0 级")

    assert result == {
        "numeric_value": None,
        "text_value": "0级",
        "unit": "",
        "qualifier": None,
        "judgment": None,
        "ref_in_value": None,
    }


def test_parse_numeric_with_trailing_text() -> None:
    parser = ResultParser()

    result = parser.parse("0      阴性-")

    assert result == {
        "numeric_value": 0.0,
        "text_value": "阴性",
        "unit": "",
        "qualifier": None,
        "judgment": None,
        "ref_in_value": None,
    }


def test_parse_none() -> None:
    parser = ResultParser()

    result = parser.parse(None)

    assert result == {
        "numeric_value": None,
        "text_value": None,
        "unit": "",
        "qualifier": None,
        "judgment": None,
        "ref_in_value": None,
    }


def test_parse_empty_string() -> None:
    parser = ResultParser()

    result = parser.parse("")

    assert result == {
        "numeric_value": None,
        "text_value": None,
        "unit": "",
        "qualifier": None,
        "judgment": None,
        "ref_in_value": None,
    }


def test_parse_existing_unit_priority() -> None:
    parser = ResultParser()

    result = parser.parse("1198kcal", existing_unit="kJ")

    assert result == {
        "numeric_value": 1198.0,
        "text_value": None,
        "unit": "kJ",
        "qualifier": None,
        "judgment": None,
        "ref_in_value": None,
    }


def test_parse_kcal() -> None:
    parser = ResultParser()

    result = parser.parse("1198kcal")

    assert result == {
        "numeric_value": 1198.0,
        "text_value": None,
        "unit": "kcal",
        "qualifier": None,
        "judgment": None,
        "ref_in_value": None,
    }


def test_parse_kg_per_sqm() -> None:
    parser = ResultParser()

    result = parser.parse("21.0kg/平方米")

    assert result == {
        "numeric_value": 21.0,
        "text_value": None,
        "unit": "kg/平方米",
        "qualifier": None,
        "judgment": None,
        "ref_in_value": None,
    }


def test_parse_reference_range_simple() -> None:
    parser = ResultParser()

    result = parser.parse_reference_range("0.00-5.800")

    assert result == {
        "ref_min": 0.0,
        "ref_max": 5.8,
        "ref_text": None,
        "ref_conditions": [],
        "is_simple_range": True,
    }


def test_parse_reference_range_less_than() -> None:
    parser = ResultParser()

    result = parser.parse_reference_range("<1.0")

    assert result["ref_min"] is None
    assert result["ref_max"] == 1.0
    assert result["is_simple_range"] is True


def test_parse_reference_range_text() -> None:
    parser = ResultParser()

    result = parser.parse_reference_range("阴性（-）")

    assert result["ref_text"] == "阴性"
    assert result["is_simple_range"] is False


def test_parse_reference_range_conditions() -> None:
    parser = ResultParser()

    result = parser.parse_reference_range("卵泡期:0.057-0.893；排卵期：0.121-12.0")

    assert result["is_simple_range"] is False
    assert result["ref_conditions"] == [
        {"condition": "卵泡期", "ref_min": 0.057, "ref_max": 0.893},
        {"condition": "排卵期", "ref_min": 0.121, "ref_max": 12.0},
    ]
