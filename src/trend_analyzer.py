"""Time-series trend analysis for longitudinal exam indicators."""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any


class TrendAnalyzer:
    """Analyze multi-exam time series for a single indicator."""

    def analyze(
        self,
        values: list[tuple[str, float]],
        ref_min: float | None = None,
        ref_max: float | None = None,
    ) -> dict[str, Any]:
        """Analyze a time series of (date_str, value) pairs.

        Args:
            values: [(date_str, numeric_value), ...] sorted by date ascending
            ref_min: reference range lower bound
            ref_max: reference range upper bound

        Returns:
            Trend analysis dict with slope, trend_type, prediction, etc.
        """
        if len(values) < 2:
            return self._single_point(values, ref_min, ref_max)

        # Convert dates to days-since-first for regression
        dates = [self._parse_date(v[0]) for v in values]
        nums = [v[1] for v in values]
        base = dates[0]
        days = [(d - base).days for d in dates]
        total_days = max(days[-1], 1)

        # Linear regression: slope per year
        slope_per_day = self._linear_slope(days, nums)
        slope_per_year = slope_per_day * 365.25

        # Acceleration (second derivative): compare slope of first half vs second half
        acceleration = 0.0
        if len(values) >= 4:
            mid = len(values) // 2
            slope1 = self._linear_slope(days[:mid], nums[:mid])
            slope2 = self._linear_slope(days[mid:], nums[mid:])
            acceleration = slope2 - slope1

        # Volatility: coefficient of variation
        mean_val = sum(nums) / len(nums)
        if mean_val != 0:
            std_val = (sum((v - mean_val) ** 2 for v in nums) / len(nums)) ** 0.5
            volatility = round(std_val / abs(mean_val), 3)
        else:
            volatility = 0.0

        # Latest vs historical average
        latest_vs_avg = round((nums[-1] - mean_val) / abs(mean_val), 3) if mean_val != 0 else 0.0

        # Consecutive abnormal count (from latest backwards)
        consecutive_abnormal = 0
        if ref_min is not None and ref_max is not None:
            for v in reversed(nums):
                if v < ref_min or v > ref_max:
                    consecutive_abnormal += 1
                else:
                    break

        # 6-month prediction
        predict_days = days[-1] + 180
        predicted_6m = round(nums[0] + slope_per_day * predict_days, 2)

        # Prediction confidence (higher with more data points and lower volatility)
        confidence = min(1.0, round(len(values) / 5 * (1 - min(volatility, 1.0)), 2))
        confidence = max(0.1, confidence)

        # Determine slope direction
        if abs(slope_per_year) < 0.01 * abs(mean_val) if mean_val != 0 else abs(slope_per_year) < 0.01:
            slope_direction = "稳定"
        elif slope_per_year > 0:
            slope_direction = "上升"
        else:
            slope_direction = "下降"

        # Determine trend type
        trend_type = self._classify_trend(
            slope_per_day, acceleration, volatility, consecutive_abnormal,
            ref_min, ref_max, nums, mean_val,
        )

        return {
            "data_points": len(values),
            "time_span_days": total_days,
            "slope_per_year": round(slope_per_year, 3),
            "slope_direction": slope_direction,
            "acceleration": round(acceleration, 6),
            "trend_type": trend_type,
            "volatility": volatility,
            "latest_vs_avg": latest_vs_avg,
            "consecutive_abnormal": consecutive_abnormal,
            "predicted_6m": predicted_6m,
            "confidence": confidence,
            "latest_value": nums[-1],
            "previous_value": nums[-2] if len(nums) >= 2 else None,
        }

    def _classify_trend(
        self,
        slope: float,
        acceleration: float,
        volatility: float,
        consecutive_abnormal: int,
        ref_min: float | None,
        ref_max: float | None,
        nums: list[float],
        mean_val: float,
    ) -> str:
        """Classify the trend into one of 6 types."""
        threshold = abs(mean_val) * 0.005 if mean_val != 0 else 0.001

        # Check if moving away from normal (worsening)
        is_worsening = False
        if ref_max is not None and slope > threshold and nums[-1] > ref_max * 0.9:
            is_worsening = True
        if ref_min is not None and slope < -threshold and nums[-1] < ref_min * 1.1:
            is_worsening = True

        # High volatility
        if volatility > 0.15:
            return "波动不定"

        if is_worsening:
            if acceleration > 0:
                return "加速恶化"
            else:
                return "减速恶化"

        # Check improvement direction
        is_improving = False
        if ref_max is not None and slope < -threshold and nums[-1] > ref_max * 0.8:
            is_improving = True
        if ref_min is not None and slope > threshold and nums[-1] < ref_min * 1.2:
            is_improving = True

        # Check for reversal (turning point)
        if len(nums) >= 3:
            recent_slope = nums[-1] - nums[-2]
            prev_slope = nums[-2] - nums[-3]
            if (recent_slope > 0 and prev_slope < 0) or (recent_slope < 0 and prev_slope > 0):
                if is_improving or consecutive_abnormal == 0:
                    return "拐点改善"

        if is_improving:
            return "持续改善"

        return "稳定"

    @staticmethod
    def _linear_slope(x: list[int | float], y: list[float]) -> float:
        """Simple linear regression slope."""
        n = len(x)
        if n < 2:
            return 0.0
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_xx = sum(xi * xi for xi in x)
        denom = n * sum_xx - sum_x * sum_x
        if denom == 0:
            return 0.0
        return (n * sum_xy - sum_x * sum_y) / denom

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        """Parse date string, handling various formats."""
        clean = str(date_str).strip()[:10]
        try:
            return datetime.strptime(clean, "%Y-%m-%d")
        except ValueError:
            try:
                return datetime.strptime(clean, "%Y/%m/%d")
            except ValueError:
                return datetime(2000, 1, 1)

    def _single_point(self, values: list[tuple[str, float]], ref_min: float | None, ref_max: float | None) -> dict[str, Any]:
        """Return baseline result for single data point."""
        val = values[0][1] if values else 0.0
        is_abnormal = False
        if ref_min is not None and val < ref_min:
            is_abnormal = True
        if ref_max is not None and val > ref_max:
            is_abnormal = True

        return {
            "data_points": len(values),
            "time_span_days": 0,
            "slope_per_year": 0.0,
            "slope_direction": "稳定",
            "acceleration": 0.0,
            "trend_type": "数据不足",
            "volatility": 0.0,
            "latest_vs_avg": 0.0,
            "consecutive_abnormal": 1 if is_abnormal else 0,
            "predicted_6m": val,
            "confidence": 0.1,
            "latest_value": val,
            "previous_value": None,
        }
