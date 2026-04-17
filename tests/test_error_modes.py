from __future__ import annotations

import json
from pathlib import Path

from src.pipeline import StandardizationPipeline


def bad_json_payload() -> dict:
    return {
        "data": {
            "studyId": "study-002",
            "examTime": "2025-12-12 08:01:20",
            "packageName": "异常套餐",
            "departments": [
                {
                    "departmentCode": "HY",
                    "departmentName": "化验室",
                    "sourceTable": "ods_tj_hyb",
                    "items": [
                        {
                            "majorItemCode": "100",
                            "majorItemName": "H-血脂",
                            "itemCode": "0401",
                            "itemName": ["坏数据"],
                            "itemNameEn": "",
                            "resultValue": "1.0",
                            "unit": "mmol/L",
                            "referenceRange": "0-5",
                            "abnormalFlag": "0",
                        }
                    ],
                }
            ],
        }
    }


def test_pipeline_lenient_mode_skips_bad_record(tmp_path: Path) -> None:
    input_path = tmp_path / "bad.json"
    input_path.write_text(json.dumps(bad_json_payload(), ensure_ascii=False), encoding="utf-8")

    pipeline = StandardizationPipeline(config_path="config/settings.yaml", output_dir=str(tmp_path), strict=False)
    classified = pipeline.run(str(input_path))

    assert classified["stats"]["total"] == 0
