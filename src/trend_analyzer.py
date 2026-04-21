"""Time-series trend analysis with Bayesian confidence, Bootstrap intervals, and LOESS."""
from __future__ import annotations

import math
import random
from datetime import datetime
from typing import Any


class TrendAnalyzer:
    """Analyze multi-exam time series with statistical rigor."""

    def __init__(self, bootstrap_iterations: int = 500, loess_threshold: int = 10) -> None:
        self.bootstrap_iterations = bootstrap_iterations
        self.loess_threshold = loess_threshold  # Use LOESS when n >= this

    def analyze(
        self,
        values: list[tuple[str, float]],
        ref_min: float | None = None,
        ref_max: float | None = None,
    ) -> dict[str, Any]:
        """Full trend analysis with enhanced prediction intervals."""
        if len(values) < 2:
            return self._single_point(values, ref_min, ref_max)

        dates = [self._parse_date(v[0]) for v in values]
        nums = [v[1] for v in values]
        base = dates[0]
        days = [(d - base).days for d in dates]
        total_days = max(days[-1], 1)
        n = len(values)

        # --- Core regression ---
        slope_per_day, intercept = self._linear_regression(days, nums)
        slope_per_year = slope_per_day * 365.25

        # --- Acceleration ---
        acceleration = 0.0
        if n >= 4:
            mid = n // 2
            s1, _ = self._linear_regression(days[:mid], nums[:mid])
            s2, _ = self._linear_regression(days[mid:], nums[mid:])
            acceleration = s2 - s1

        # --- Volatility ---
        mean_val = sum(nums) / n
        std_val = (sum((v - mean_val) ** 2 for v in nums) / n) ** 0.5 if n > 0 else 0.0
        volatility = round(std_val / abs(mean_val), 3) if mean_val != 0 else 0.0

        # --- Latest vs avg ---
        latest_vs_avg = round((nums[-1] - mean_val) / abs(mean_val), 3) if mean_val != 0 else 0.0

        # --- Consecutive abnormal ---
        consecutive_abnormal = 0
        if ref_min is not None and ref_max is not None:
            for v in reversed(nums):
                if v < ref_min or v > ref_max:
                    consecutive_abnormal += 1
                else:
                    break

        # --- 6-month prediction ---
        predict_days = days[-1] + 180

        # Use LOESS for 10+ points, linear for fewer
        if n >= self.loess_threshold:
            predicted_6m = round(self._loess_predict(days, nums, predict_days), 2)
            fit_method = "loess"
        else:
            predicted_6m = round(intercept + slope_per_day * predict_days, 2)
            fit_method = "linear"

        # --- Bayesian confidence interval (t-distribution based) ---
        ci_lower, ci_upper, confidence = self._bayesian_prediction_interval(
            days, nums, slope_per_day, intercept, predict_days
        )

        # --- Bootstrap prediction interval ---
        boot_lower, boot_upper, boot_median = self._bootstrap_prediction_interval(
            days, nums, predict_days
        )

        # --- Slope direction ---
        rel_threshold = abs(mean_val) * 0.01 if mean_val != 0 else 0.01
        if abs(slope_per_year) < rel_threshold:
            slope_direction = "稳定"
        elif slope_per_year > 0:
            slope_direction = "上升"
        else:
            slope_direction = "下降"

        # --- Trend type ---
        trend_type = self._classify_trend(
            slope_per_day, acceleration, volatility, consecutive_abnormal,
            ref_min, ref_max, nums, mean_val,
        )

        return {
            "data_points": n,
            "time_span_days": total_days,
            "fit_method": fit_method,
            "slope_per_year": round(slope_per_year, 3),
            "slope_direction": slope_direction,
            "acceleration": round(acceleration, 6),
            "trend_type": trend_type,
            "volatility": volatility,
            "latest_vs_avg": latest_vs_avg,
            "consecutive_abnormal": consecutive_abnormal,
            "predicted_6m": predicted_6m,
            "confidence": confidence,
            # Bayesian interval (parametric, t-distribution)
            "ci_lower": round(ci_lower, 2),
            "ci_upper": round(ci_upper, 2),
            # Bootstrap interval (non-parametric)
            "boot_lower": round(boot_lower, 2),
            "boot_upper": round(boot_upper, 2),
            "boot_median": round(boot_median, 2),
            "latest_value": nums[-1],
            "previous_value": nums[-2] if n >= 2 else None,
        }

    # ------------------------------------------------------------------
    # Bayesian / t-distribution prediction interval
    # ------------------------------------------------------------------

    def _bayesian_prediction_interval(
        self,
        x: list[int | float],
        y: list[float],
        slope: float,
        intercept: float,
        x_pred: float,
        alpha: float = 0.1,  # 90% interval
    ) -> tuple[float, float, float]:
        """Compute prediction interval using t-distribution.

        Returns (lower, upper, confidence_score).
        """
        n = len(x)
        if n < 3:
            y_pred = intercept + slope * x_pred
            return (y_pred * 0.8, y_pred * 1.2, 0.15)

        # Residuals
        residuals = [yi - (intercept + slope * xi) for xi, yi in zip(x, y)]
        sse = sum(r * r for r in residuals)
        mse = sse / (n - 2)
        se = mse ** 0.5

        # Prediction standard error at x_pred
        x_mean = sum(x) / n
        ss_xx = sum((xi - x_mean) ** 2 for xi in x)
        if ss_xx == 0:
            y_pred = intercept + slope * x_pred
            return (y_pred - 2 * se, y_pred + 2 * se, 0.2)

        se_pred = se * (1 + 1 / n + (x_pred - x_mean) ** 2 / ss_xx) ** 0.5

        # t-value approximation for 90% interval (two-tailed)
        # For small n, use wider intervals
        t_values = {3: 2.920, 4: 2.353, 5: 2.132, 6: 2.015, 7: 1.943,
                    8: 1.895, 10: 1.833, 15: 1.761, 20: 1.729, 30: 1.699}
        df = n - 2
        t_val = 1.645  # large sample default
        for k in sorted(t_values.keys()):
            if df <= k:
                t_val = t_values[k]
                break

        y_pred = intercept + slope * x_pred
        margin = t_val * se_pred
        ci_lower = y_pred - margin
        ci_upper = y_pred + margin

        # Confidence score: based on interval width relative to prediction
        if abs(y_pred) > 0:
            relative_width = (ci_upper - ci_lower) / abs(y_pred)
            confidence = max(0.1, min(0.99, round(1.0 - relative_width / 2, 2)))
        else:
            confidence = 0.3

        return (ci_lower, ci_upper, confidence)

    # ------------------------------------------------------------------
    # Bootstrap prediction interval
    # ------------------------------------------------------------------

    def _bootstrap_prediction_interval(
        self,
        x: list[int | float],
        y: list[float],
        x_pred: float,
        percentile_low: float = 5.0,
        percentile_high: float = 95.0,
    ) -> tuple[float, float, float]:
        """Non-parametric bootstrap prediction interval.

        Resamples residuals and re-fits regression to estimate prediction distribution.
        Returns (lower, upper, median).
        """
        n = len(x)
        if n < 3:
            slope, intercept = self._linear_regression(x, y)
            y_pred = intercept + slope * x_pred
            return (y_pred * 0.8, y_pred * 1.2, y_pred)

        # Original fit
        slope, intercept = self._linear_regression(x, y)
        residuals = [yi - (intercept + slope * xi) for xi, yi in zip(x, y)]

        # Bootstrap: resample residuals, refit, predict
        predictions: list[float] = []
        rng = random.Random(42)  # deterministic for reproducibility
        for _ in range(self.bootstrap_iterations):
            # Resample residuals with replacement
            boot_residuals = [rng.choice(residuals) for _ in range(n)]
            # Create bootstrapped y values
            boot_y = [intercept + slope * xi + ri for xi, ri in zip(x, boot_residuals)]
            # Refit
            boot_slope, boot_intercept = self._linear_regression(x, boot_y)
            # Predict + add random residual for prediction interval (not just confidence)
            noise = rng.choice(residuals)
            predictions.append(boot_intercept + boot_slope * x_pred + noise)

        predictions.sort()
        idx_low = max(0, int(len(predictions) * percentile_low / 100))
        idx_high = min(len(predictions) - 1, int(len(predictions) * percentile_high / 100))
        idx_mid = len(predictions) // 2

        return (predictions[idx_low], predictions[idx_high], predictions[idx_mid])

    # ------------------------------------------------------------------
    # LOESS (locally weighted scatterplot smoothing)
    # ------------------------------------------------------------------

    def _loess_predict(
        self,
        x: list[int | float],
        y: list[float],
        x_pred: float,
        frac: float = 0.6,
    ) -> float:
        """Simple LOESS prediction using tricube kernel weighted regression.

        For extrapolation beyond the data range, uses the local slope at the boundary.
        """
        n = len(x)
        span = max(3, int(n * frac))

        # Find nearest points to x_pred
        distances = [(abs(xi - x_pred), i) for i, xi in enumerate(x)]
        distances.sort()
        neighbors = [i for _, i in distances[:span]]

        # Tricube kernel weights
        max_dist = max(abs(x[i] - x_pred) for i in neighbors)
        if max_dist == 0:
            max_dist = 1.0

        weights = []
        for i in neighbors:
            u = abs(x[i] - x_pred) / (max_dist * 1.001)
            w = (1 - u ** 3) ** 3 if u < 1 else 0.0
            weights.append(w)

        # Weighted linear regression
        x_sub = [x[i] for i in neighbors]
        y_sub = [y[i] for i in neighbors]

        sum_w = sum(weights)
        if sum_w == 0:
            return y[-1]  # fallback

        sum_wx = sum(w * xi for w, xi in zip(weights, x_sub))
        sum_wy = sum(w * yi for w, yi in zip(weights, y_sub))
        sum_wxy = sum(w * xi * yi for w, xi, yi in zip(weights, x_sub, y_sub))
        sum_wxx = sum(w * xi * xi for w, xi in zip(weights, x_sub))

        x_mean_w = sum_wx / sum_w
        denom = sum_wxx - sum_wx * x_mean_w
        if abs(denom) < 1e-10:
            return sum_wy / sum_w

        slope_w = (sum_wxy - sum_wx * sum_wy / sum_w) / denom
        intercept_w = (sum_wy - slope_w * sum_wx) / sum_w

        return intercept_w + slope_w * x_pred

    # ------------------------------------------------------------------
    # Core utilities (unchanged)
    # ------------------------------------------------------------------

    def _classify_trend(
        self, slope: float, acceleration: float, volatility: float,
        consecutive_abnormal: int, ref_min: float | None, ref_max: float | None,
        nums: list[float], mean_val: float,
    ) -> str:
        """Classify the trend into one of 6 types."""
        threshold = abs(mean_val) * 0.005 if mean_val != 0 else 0.001

        is_worsening = False
        if ref_max is not None and slope > threshold and nums[-1] > ref_max * 0.9:
            is_worsening = True
        if ref_min is not None and slope < -threshold and nums[-1] < ref_min * 1.1:
            is_worsening = True

        if volatility > 0.15:
            return "波动不定"
        if is_worsening:
            return "加速恶化" if acceleration > 0 else "减速恶化"

        is_improving = False
        if ref_max is not None and slope < -threshold and nums[-1] > ref_max * 0.8:
            is_improving = True
        if ref_min is not None and slope > threshold and nums[-1] < ref_min * 1.2:
            is_improving = True

        if len(nums) >= 3:
            recent = nums[-1] - nums[-2]
            prev = nums[-2] - nums[-3]
            if (recent > 0 and prev < 0) or (recent < 0 and prev > 0):
                if is_improving or consecutive_abnormal == 0:
                    return "拐点改善"

        if is_improving:
            return "持续改善"
        return "稳定"

    @staticmethod
    def _linear_regression(x: list[int | float], y: list[float]) -> tuple[float, float]:
        """Linear regression returning (slope, intercept)."""
        n = len(x)
        if n < 2:
            return (0.0, y[0] if y else 0.0)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_xx = sum(xi * xi for xi in x)
        denom = n * sum_xx - sum_x * sum_x
        if denom == 0:
            return (0.0, sum_y / n)
        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n
        return (slope, intercept)

    @staticmethod
    def _linear_slope(x: list[int | float], y: list[float]) -> float:
        """Simple linear regression slope (backward compat)."""
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
        clean = str(date_str).strip()[:10]
        try:
            return datetime.strptime(clean, "%Y-%m-%d")
        except ValueError:
            try:
                return datetime.strptime(clean, "%Y/%m/%d")
            except ValueError:
                return datetime(2000, 1, 1)

    def _single_point(self, values: list[tuple[str, float]], ref_min: float | None, ref_max: float | None) -> dict[str, Any]:
        val = values[0][1] if values else 0.0
        is_abnormal = False
        if ref_min is not None and val < ref_min:
            is_abnormal = True
        if ref_max is not None and val > ref_max:
            is_abnormal = True

        return {
            "data_points": len(values),
            "time_span_days": 0,
            "fit_method": "none",
            "slope_per_year": 0.0,
            "slope_direction": "稳定",
            "acceleration": 0.0,
            "trend_type": "数据不足",
            "volatility": 0.0,
            "latest_vs_avg": 0.0,
            "consecutive_abnormal": 1 if is_abnormal else 0,
            "predicted_6m": val,
            "confidence": 0.1,
            "ci_lower": val * 0.8,
            "ci_upper": val * 1.2,
            "boot_lower": val * 0.8,
            "boot_upper": val * 1.2,
            "boot_median": val,
            "latest_value": val,
            "previous_value": None,
        }
