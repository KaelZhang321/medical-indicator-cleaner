from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.data_enrichment.llm_generator import LLMGenerator
from scripts.data_enrichment.merger import DataMerger


class FakeClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.calls = 0

    def is_configured(self) -> bool:
        return True

    def complete_json(self, _messages):
        response = self.responses[self.calls]
        self.calls += 1
        return response


def sample_standard_dict() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "code": "HY-BZ-001",
                "standard_name": "总胆固醇",
                "abbreviation": "TC",
                "aliases": "胆固醇;CHOL",
                "category": "血脂",
                "common_unit": "mmol/L",
                "result_type": "numeric",
            },
            {
                "code": "HY-XT-001",
                "standard_name": "空腹血糖",
                "abbreviation": "FPG",
                "aliases": "血糖;GLU",
                "category": "血糖",
                "common_unit": "mmol/L",
                "result_type": "numeric",
            },
        ]
    )


def test_generate_aliases_incremental_save(tmp_path: Path) -> None:
    output = tmp_path / "llm_aliases.json"
    generator = LLMGenerator(model="fake", delay=0, client=FakeClient([{"aliases": ["总胆"]}, {"aliases": ["空腹葡萄糖"]}]))

    result = generator.generate_aliases(sample_standard_dict(), str(output))

    assert result["HY-BZ-001"] == ["总胆"]
    assert result["HY-XT-001"] == ["空腹葡萄糖"]
    assert json.loads(output.read_text(encoding="utf-8"))["HY-XT-001"] == ["空腹葡萄糖"]


def test_generate_aliases_resume_skips_existing(tmp_path: Path) -> None:
    output = tmp_path / "llm_aliases.json"
    output.write_text(json.dumps({"HY-BZ-001": ["总胆"]}, ensure_ascii=False), encoding="utf-8")
    client = FakeClient([{"aliases": ["空腹葡萄糖"]}])
    generator = LLMGenerator(model="fake", delay=0, client=client)

    result = generator.generate_aliases(sample_standard_dict(), str(output))

    assert client.calls == 1
    assert result["HY-BZ-001"] == ["总胆"]
    assert result["HY-XT-001"] == ["空腹葡萄糖"]


def test_generate_risk_weights_include_category(tmp_path: Path) -> None:
    output = tmp_path / "llm_risk.json"
    generator = LLMGenerator(
        model="fake",
        delay=0,
        client=FakeClient(
            [
                {"risk_weight": 0.6, "risk_category": "warning", "reason": "血脂异常"},
                {"risk_weight": 0.8, "risk_category": "critical", "reason": "血糖异常"},
            ]
        ),
    )

    result = generator.generate_risk_weights(sample_standard_dict(), str(output))

    assert result[0]["standard_code"] == "HY-BZ-001"
    assert result[1]["standard_code"] == "HY-XT-001"


def test_merge_new_indicators_keeps_category() -> None:
    merger = DataMerger()
    merged = merger.merge_new_indicators(
        [
            {
                "standard_name": "餐后2小时血糖",
                "abbreviation": "2hPG",
                "aliases": "餐后血糖",
                "category": "血糖",
                "common_unit": "mmol/L",
                "result_type": "numeric",
            }
        ],
        sample_standard_dict(),
    )

    row = merged.loc[merged["standard_name"] == "餐后2小时血糖"].iloc[0]
    assert row["category"] == "血糖"
    assert row["result_type"] == "numeric"
