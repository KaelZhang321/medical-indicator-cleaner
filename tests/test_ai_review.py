from __future__ import annotations

import json

import pandas as pd

from src.ai_review import AIReviewProcessor, ArkChatClient


class FakeArkClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.prompts: list[list[dict[str, str]]] = []

    def is_configured(self) -> bool:
        return True

    def complete_json(self, messages: list[dict[str, str]]) -> dict:
        self.prompts.append(messages)
        return self.payload


def candidate_record() -> dict:
    return {
        "original_name": "胆固醇偏写",
        "cleaned_name": "胆固醇偏写",
        "abbreviation": "",
        "standard_name": "总胆固醇",
        "standard_code": "HY-BZ-001",
        "category": "血脂",
        "confidence": 0.91,
        "match_source": "l2_embedding",
        "top_candidates": [
            {
                "standard_code": "HY-BZ-001",
                "standard_name": "总胆固醇",
                "category": "血脂",
                "score": 0.91,
            }
        ],
    }


def standard_dict() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"code": "HY-BZ-001", "standard_name": "总胆固醇", "category": "血脂"},
            {"code": "HY-BZ-002", "standard_name": "甘油三酯", "category": "血脂"},
        ]
    )


def test_ark_client_not_configured_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ARK_API_KEY", raising=False)

    client = ArkChatClient(model="doubao-seed-2-0-pro-260215")

    assert client.is_configured() is False


def test_ai_review_auto_maps_clear_candidate() -> None:
    processor = AIReviewProcessor(
        enabled=True,
        client=FakeArkClient(
            {
                "action": "auto_map",
                "standard_code": "HY-BZ-001",
                "standard_name": "总胆固醇",
                "category": "血脂",
                "confidence": 0.97,
                "reason": "胆固醇偏写语义明确对应总胆固醇",
            }
        ),
        standard_dict=standard_dict(),
    )

    reviewed = processor.review([candidate_record()])

    assert reviewed[0]["standard_code"] == "HY-BZ-001"
    assert reviewed[0]["confidence"] == 0.97
    assert reviewed[0]["match_source"] == "ai_review"
    assert reviewed[0]["ai_review"]["reason"] == "胆固醇偏写语义明确对应总胆固醇"


def test_ai_review_uncertain_keeps_for_human_review() -> None:
    processor = AIReviewProcessor(
        enabled=True,
        client=FakeArkClient(
            {
                "action": "human_review",
                "confidence": 0.3,
                "reason": "候选不足，无法可靠判断",
            }
        ),
        standard_dict=standard_dict(),
    )

    reviewed = processor.review([candidate_record()])

    assert reviewed[0]["standard_code"] == ""
    assert reviewed[0]["confidence"] == 0.0
    assert reviewed[0]["match_source"] == "ai_review_uncertain"
    assert reviewed[0]["ai_review"]["reason"] == "候选不足，无法可靠判断"


def test_ai_review_disabled_returns_records_unchanged() -> None:
    original = candidate_record()
    processor = AIReviewProcessor(
        enabled=False,
        client=FakeArkClient({"action": "auto_map"}),
        standard_dict=standard_dict(),
    )

    reviewed = processor.review([original])

    assert reviewed == [original]
