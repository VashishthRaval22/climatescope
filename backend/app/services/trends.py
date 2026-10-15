
from collections import defaultdict
from statistics import median
from typing import Any

import numpy as np
from statsmodels.nonparametric.smoothers_lowess import lowess


def aggregate_yearly_trends(
    events: list[dict],
    start_year: int,
    end_year: int,
) -> list[dict]:
    """
    Aggregate heatwave events by the calendar year they started.

    Cross-year events remain a single event and are attributed entirely
    to their start year. Their overflow days are reported separately.

    Annual duration metrics therefore represent event-attributed
    duration, not heatwave days physically occurring in each year.
    """
    if start_year > end_year:
        raise ValueError("start_year cannot be after end_year")

    if not isinstance(start_year, int) or isinstance(start_year, bool):
        raise ValueError("start_year must be an integer")

    if not isinstance(end_year, int) or isinstance(end_year, bool):
        raise ValueError("end_year must be an integer")

    yearly = {
        year: {
            "year": year,
            "heatwave_events": 0,
            "extreme_heatwave_events": 0,
            "total_heatwave_days": 0,
            "longest_heatwave_days": 0,
            "overflow_days_next_year": 0,
            "peak_temperature_c": None,
        }
        for year in range(start_year, end_year + 1)
    }

    for event in events:
        event_year = event.get("event_year")

        if event_year is None:
            raise ValueError("Each event must contain event_year")

        if not isinstance(event_year, int) or isinstance(event_year, bool):
            raise ValueError("event_year must be an integer")

        # Events outside the requested range are excluded.
        if event_year not in yearly:
            continue

        duration = event.get("duration_days")
        overflow = event.get("overflow_days_next_year", 0)
        peak = event.get("peak_temperature_c")

        if not isinstance(duration, int) or isinstance(duration, bool) or duration < 1:
            raise ValueError("duration_days must be a positive integer")

        if not isinstance(overflow, int) or isinstance(overflow, bool) or overflow < 0:
            raise ValueError("overflow_days_next_year must be a non-negative integer")

        if overflow >= duration:
            raise ValueError(
                "overflow_days_next_year must be less than duration_days"
            )

        if peak is not None:
            if isinstance(peak, bool) or not isinstance(peak, (int, float)):
                raise ValueError("peak_temperature_c must be numeric or None")

        row = yearly[event_year]
        row["heatwave_events"] += 1
        row["extreme_heatwave_events"] += int(bool(event.get("is_extreme", False)))
        row["total_heatwave_days"] += duration
        row["longest_heatwave_days"] = max(
            row["longest_heatwave_days"], duration
        )
        row["overflow_days_next_year"] += overflow

        if peak is not None:
            current_peak = row["peak_temperature_c"]
            row["peak_temperature_c"] = (
                float(peak)
                if current_peak is None
                else max(current_peak, float(peak))
            )

    return list(yearly.values())


def _validate_annual_series(
    trends: list[dict],
    metric: str,
) -> tuple[list[int], list[float]]:
    """Extract valid annual observations; zero is valid, None means missing."""
    years = []
    values = []

    for row in sorted(trends, key=lambda item: item["year"]):
        year = row.get("year")
        value = row.get(metric)

        if not isinstance(year, int) or isinstance(year, bool):
            raise ValueError("Each trend row must contain an integer year")

        if value is None:
            continue

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{metric} must be numeric or None")

        if not np.isfinite(value):
            continue

        years.append(year)
        values.append(float(value))

    return years, values


def calculate_theil_sen_slope(
    trends: list[dict],
    metric: str = "total_heatwave_days",
) -> dict[str, Any]:
    """Return a robust descriptive slope in metric units per decade."""
    years, values = _validate_annual_series(trends, metric)

    result = {
        "metric": metric,
        "method": "theil_sen",
        "unit": (
            "days_per_decade"
            if metric == "total_heatwave_days"
            else "events_per_decade"
        ),
        "n_years": len(years),
        "start_year": years[0] if years else None,
        "end_year": years[-1] if years else None,
        "slope_per_decade": None,
        "direction": "insufficient_data",
        "interpretation": None,
    }

    if len(years) < 2:
        result["interpretation"] = (
            "At least two valid annual observations are required."
        )
        return result

    slopes = [
        (values[j] - values[i]) / (years[j] - years[i]) * 10
        for i in range(len(years) - 1)
        for j in range(i + 1, len(years))
        if years[j] != years[i]
    ]

    if not slopes:
        result["interpretation"] = (
            "At least two distinct years are required."
        )
        return result

    slope = float(median(slopes))
    result["slope_per_decade"] = round(slope, 4)
    result["direction"] = (
        "increasing" if slope > 0
        else "decreasing" if slope < 0
        else "stable"
    )
    result["interpretation"] = (
        f"Estimated {metric.replace('_', ' ')} trend: "
        f"{slope:+.2f} per decade over {years[0]}–{years[-1]}."
    )

    return result


def add_lowess_smoothing(
    trends: list[dict],
    metric: str = "total_heatwave_days",
    frac: float = 0.3,
) -> list[dict]:
    """Add a LOWESS-smoothed series without changing observed values."""
    if not 0 < frac <= 1:
        raise ValueError("frac must be greater than 0 and at most 1")

    result = [
        dict(row)
        for row in sorted(trends, key=lambda item: item["year"])
    ]
    output_key = f"{metric}_lowess"

    for row in result:
        row[output_key] = None

    valid = []

    for index, row in enumerate(result):
        value = row.get(metric)

        if value is None:
            continue

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{metric} must be numeric or None")

        if np.isfinite(value):
            valid.append((index, float(row["year"]), float(value)))

    if len(valid) < 3:
        return result

    years = np.array([item[1] for item in valid], dtype=float)
    values = np.array([item[2] for item in valid], dtype=float)
    effective_frac = max(frac, min(1.0, 3.0 / len(valid)))

    smoothed = lowess(
        values,
        years,
        frac=effective_frac,
        it=1,
        return_sorted=False,
    )

    for (index, _, _), smooth_value in zip(valid, smoothed):
        result[index][output_key] = round(float(smooth_value), 4)

    return result


def build_trend_analysis(trends: list[dict]) -> dict[str, Any]:
    """Build headline trend metadata for the API response."""
    return {
        "headline": calculate_theil_sen_slope(
            trends,
            metric="total_heatwave_days",
        ),
        "methodology": {
            "slope_estimator": "Theil–Sen estimator",
            "smoothing": "LOWESS",
            "lowess_fraction": 0.3,
            "statistical_significance_tested": False,
            "notes": [
                "The slope is descriptive, not a significance test.",
                "LOWESS visualizes local variation; it does not prove acceleration.",
                (
                    "Cross-year events are attributed to their start year; "
                    "overflow days are reported separately."
                ),
            ],
        },
    }

