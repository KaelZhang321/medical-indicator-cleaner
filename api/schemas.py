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
    trend: str = ""
    risk_level: str = ""


class SystemScore(BaseModel):
    system: str
    key: str = ""
    score: int = 100
    status: str = "正常"
    trend: str = "稳定"
    abnormal_count: int = 0
    worst_indicator: str = ""
    key_findings: list[str] = []


class DerivedIndicator(BaseModel):
    code: str
    name: str
    value: float
    ref_min: float | None = None
    ref_max: float | None = None
    status: str = "正常"
    direction: str = "normal"
    clinical: str = ""


class HistoryPoint(BaseModel):
    date: str
    value: float


class TopRisk(BaseModel):
    code: str
    name: str
    category: str = ""
    value: float | None = None
    unit: str = ""
    trend_type: str = ""
    predicted_6m: float | None = None
    ci_lower: float | None = None
    ci_upper: float | None = None
    consecutive_abnormal: int = 0
    risk_score: int = 0
    slope_direction: str = ""
    history: list[HistoryPoint] = []


class FeaturesSummary(BaseModel):
    total_indicators: int = 0
    abnormal_count: int = 0
    worsening_count: int = 0
    improving_count: int = 0
    new_abnormal_count: int = 0
    stable_abnormal_count: int = 0
    overall_trend: str = ""


class FeaturesResponse(BaseModel):
    patient_id: str
    exam_count: int
    time_span: str = ""
    overall_score: int = 100
    overall_level: str = "优秀"
    overall_color: str = "#52c41a"
    summary: FeaturesSummary
    system_scores: list[SystemScore] = []
    derived_indicators: list[DerivedIndicator] = []
    top_risks: list[TopRisk] = []
    positive_changes: list[str] = []
    indicators: list[IndicatorFeature]
    features: dict[str, float | int | None] = {}
    disclaimer: str = ""
    features: dict[str, float | int | None]
