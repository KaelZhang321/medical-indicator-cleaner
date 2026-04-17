from __future__ import annotations

import json
import os
from typing import Any


ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"


class ArkChatClient:
    """Volcengine Ark OpenAI-compatible chat client."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str = ARK_BASE_URL,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.getenv("ARK_API_KEY", "")
        self.base_url = base_url.rstrip("/")

    def is_configured(self) -> bool:
        return bool(self.api_key and self.model)

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        if not self.is_configured():
            raise ValueError("Ark client is not configured")

        import re

        import requests

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": 0,
            },
            timeout=30,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        # Extract JSON from response — model may wrap it in markdown code fences
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
        if json_match:
            content = json_match.group(1).strip()
        return json.loads(content)


class AIReviewProcessor:
    """Use an LLM to re-review ambiguous normalization results."""

    def __init__(
        self,
        enabled: bool,
        client: Any,
        standard_dict: Any,
    ) -> None:
        self.enabled = enabled
        self.client = client
        self.standard_dict = standard_dict

    def review(self, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.enabled or not self.client or not self.client.is_configured():
            return results

        reviewed: list[dict[str, Any]] = []
        for result in results:
            if result.get("match_source") in {"alias_exact", "abbr_exact", "ai_review"}:
                reviewed.append(result)
                continue

            reviewed.append(self._review_one(result))
        return reviewed

    def _review_one(self, result: dict[str, Any]) -> dict[str, Any]:
        messages = self._build_messages(result)
        payload = self.client.complete_json(messages)
        action = payload.get("action", "human_review")

        updated = dict(result)
        updated["ai_review"] = {
            "action": action,
            "reason": payload.get("reason", ""),
        }

        if action == "auto_map":
            updated["standard_code"] = payload.get("standard_code", updated.get("standard_code", ""))
            updated["standard_name"] = payload.get("standard_name", updated.get("standard_name", ""))
            updated["category"] = payload.get("category", updated.get("category", ""))
            updated["confidence"] = float(payload.get("confidence") or updated.get("confidence") or 0.0)
            updated["match_source"] = "ai_review"
            return updated

        updated["standard_code"] = ""
        updated["standard_name"] = ""
        updated["category"] = ""
        updated["confidence"] = 0.0
        updated["match_source"] = "ai_review_uncertain"
        return updated

    def _build_messages(self, result: dict[str, Any]) -> list[dict[str, str]]:
        candidate_summary = [
            {
                "standard_code": row.code,
                "standard_name": row.standard_name,
                "category": row.category,
            }
            for row in self.standard_dict.itertuples(index=False)
        ][:200]

        user_payload = {
            "original_name": result.get("original_name", ""),
            "cleaned_name": result.get("cleaned_name", ""),
            "abbreviation": result.get("abbreviation", ""),
            "top_candidates": result.get("top_candidates", []),
            "standard_dict_sample": candidate_summary,
            "instruction": "若可明确映射则返回 auto_map；若仍有歧义则返回 human_review。",
        }
        return [
            {
                "role": "system",
                "content": (
                    "你是医疗体检指标名称标准化审核助手。"
                    "只返回 JSON，字段包括 action, standard_code, standard_name, category, confidence, reason。"
                    "action 只能是 auto_map 或 human_review。"
                ),
            },
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ]
