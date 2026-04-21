import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || 'http://localhost:8000',
  timeout: 30000,
});

export interface Indicator {
  standard_code: string;
  standard_name: string;
  category: string;
  value: string | number | null;
  unit: string;
  reference_range: string;
  ref_min: number | null;
  ref_max: number | null;
  is_abnormal: boolean | null;
  abnormal_direction: string | null;
}

export interface ExamSummary {
  total_indicators: number;
  abnormal_count: number;
  categories: string[];
}

export interface ExamResponse {
  study_id: string;
  patient_name: string;
  gender: string;
  exam_time: string;
  package_name: string;
  summary: ExamSummary;
  indicators: Indicator[];
}

export interface ExamListItem {
  study_id: string;
  exam_time: string;
  package_name: string;
  abnormal_count: number;
}

export interface PatientExamsResponse {
  patient_id: string;
  exam_count: number;
  exams: ExamListItem[];
}

export interface ComparisonItem {
  standard_code: string;
  standard_name: string;
  category: string;
  unit: string;
  values: Record<string, number | string | null>;
  trend: string;
  ref_min: number | null;
  ref_max: number | null;
}

export interface ComparisonResponse {
  patient_id: string;
  mode: string;
  exam_dates: string[];
  comparisons: ComparisonItem[];
}

export interface QuadrantAdvice {
  summary: string;
  action: string;
  urgency: string;
  details: string[];
}

export interface QuadrantItem {
  standard_name: string;
  standard_code: string;
  category: string;
  deviation: number;
  abs_deviation: number;
  direction: string;
  risk_weight: number;
  quadrant: string;
  value: number | null;
  unit: string;
  ref_min: number | null;
  ref_max: number | null;
  advice: QuadrantAdvice;
}

export interface HealthScore {
  score: number;
  level: string;
  color: string;
}

export interface QuadrantResponse {
  study_id: string;
  health_score: HealthScore;
  quadrants: Record<string, QuadrantItem[]>;
  stats: {
    urgent_count: number;
    watch_count: number;
    mild_count: number;
    normal_count: number;
    total: number;
  };
  top_concerns: QuadrantItem[];
  disclaimer: string;
}

export interface SystemScore {
  system: string;
  key: string;
  score: number;
  status: string;
  trend: string;
  abnormal_count: number;
  worst_indicator: string;
  key_findings: string[];
}

export interface DerivedIndicator {
  code: string;
  name: string;
  value: number;
  ref_min: number | null;
  ref_max: number | null;
  status: string;
  direction: string;
  clinical: string;
}

export interface HistoryPoint {
  date: string;
  value: number;
}

export interface TopRisk {
  code: string;
  name: string;
  category: string;
  value: number | null;
  unit: string;
  trend_type: string;
  predicted_6m: number | null;
  ci_lower: number | null;
  ci_upper: number | null;
  consecutive_abnormal: number;
  risk_score: number;
  slope_direction: string;
  history: HistoryPoint[];
}

export interface IndicatorFeature {
  code: string;
  name: string;
  category: string;
  latest_value: number | null;
  previous_value: number | null;
  change_rate: number | null;
  is_abnormal: boolean;
  trend: string;
  risk_level: string;
}

export interface FeaturesResponse {
  patient_id: string;
  exam_count: number;
  time_span: string;
  overall_score: number;
  overall_level: string;
  overall_color: string;
  summary: {
    total_indicators: number;
    abnormal_count: number;
    worsening_count: number;
    improving_count: number;
    overall_trend: string;
  };
  system_scores: SystemScore[];
  derived_indicators: DerivedIndicator[];
  top_risks: TopRisk[];
  positive_changes: string[];
  indicators: IndicatorFeature[];
  disclaimer: string;
}

export const fetchExam = (studyId: string) =>
  api.get<ExamResponse>(`/api/v1/exam/${studyId}`).then(r => r.data);

export const fetchPatientExams = (sfzh: string) =>
  api.get<PatientExamsResponse>(`/api/v1/patient/${sfzh}/exams`).then(r => r.data);

export const fetchComparison = (sfzh: string, category?: string) =>
  api.get<ComparisonResponse>(`/api/v1/patient/${sfzh}/comparison`, { params: category ? { category } : {} }).then(r => r.data);

export const fetchTextComparison = (sfzh: string, category?: string) =>
  api.get<ComparisonResponse>(`/api/v1/patient/${sfzh}/comparison`, { params: { mode: 'text', ...(category ? { category } : {}) } }).then(r => r.data);

export const fetchQuadrant = (studyId: string) =>
  api.get<QuadrantResponse>(`/api/v1/exam/${studyId}/quadrant`).then(r => r.data);

export const fetchFeatures = (sfzh: string) =>
  api.get<FeaturesResponse>(`/api/v1/patient/${sfzh}/features`).then(r => r.data);

export default api;
