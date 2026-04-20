"""Pydantic response models for the API."""
from __future__ import annotations

from pydantic import BaseModel


class IndicatorResult(BaseModel):
    standard_code: str
    standard_name: str
    category: str
    value: float | str | None = None
    unit: str = ""
    reference_range: str = ""
    ref_min: float | None = None
    ref_max: float | None = None
    is_abnormal: bool | None = None
    abnormal_direction: str | None = None


class ExamSummary(BaseModel):
    total_indicators: int
    abnormal_count: int
    categories: list[str]


class ExamResponse(BaseModel):
    study_id: str
    patient_name: str = ""
    gender: str = ""
    exam_time: str = ""
    package_name: str = ""
    summary: ExamSummary
    indicators: list[IndicatorResult]


class ExamListItem(BaseModel):
    study_id: str
    exam_time: str = ""
    package_name: str = ""
    abnormal_count: int = 0


class PatientExamsResponse(BaseModel):
    patient_id: str
    exam_count: int
    exams: list[ExamListItem]


class ComparisonItem(BaseModel):
    standard_code: str
    standard_name: str
    category: str
    unit: str = ""
    values: dict[str, float | str | None]
    trend: str = ""
    ref_min: float | None = None
    ref_max: float | None = None


class ComparisonResponse(BaseModel):
    patient_id: str
    mode: str = "numeric"
    exam_dates: list[str]
    comparisons: list[ComparisonItem]


class QuadrantAdvice(BaseModel):
    summary: str = ""
    action: str = ""
    urgency: str = "routine"
    details: list[str] = []


class QuadrantItem(BaseModel):
    standard_name: str
    standard_code: str = ""
    category: str = ""
    deviation: float = 0.0
    abs_deviation: float = 0.0
    direction: str = "normal"
    risk_weight: float = 0.0
    quadrant: str = "正常范围"
    value: float | None = None
    unit: str = ""
    ref_min: float | None = None
    ref_max: float | None = None
    advice: QuadrantAdvice = QuadrantAdvice()


class HealthScore(BaseModel):
    score: int = 100
    level: str = "优秀"
    color: str = "#52c41a"


class QuadrantStats(BaseModel):
    urgent_count: int = 0
    watch_count: int = 0
    mild_count: int = 0
    normal_count: int = 0
    total: int = 0


class QuadrantResponse(BaseModel):
    study_id: str
    health_score: HealthScore = HealthScore()
    quadrants: dict[str, list[QuadrantItem]]
    stats: QuadrantStats
    top_concerns: list[QuadrantItem] = []
    disclaimer: str = ""


class IndicatorFeature(BaseModel):
    code: str
    name: str
    category: str
    latest_value: float | None = None
    previous_value: float | None = None
    change_rate: float | None = None
    is_abnormal: bool = False
    trend: str = ""  # 上升/下降/稳定
    risk_level: str = ""  # 恶化/改善/稳定/新增异常


class FeaturesSummary(BaseModel):
    total_indicators: int = 0
    abnormal_count: int = 0
    worsening_count: int = 0
    improving_count: int = 0
    new_abnormal_count: int = 0
    stable_abnormal_count: int = 0
    overall_trend: str = ""  # 整体好转/整体恶化/基本稳定


class FeaturesResponse(BaseModel):
    patient_id: str
    exam_count: int
    summary: FeaturesSummary
    indicators: list[IndicatorFeature]
    features: dict[str, float | int | None]
