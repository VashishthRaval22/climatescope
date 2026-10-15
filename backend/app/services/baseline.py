
from datetime import date, datetime

import numpy as np
import pandas as pd


TEMPERATURE_COLUMN = "temperature_max_c"

DEFAULT_BASELINE_START = date(1991, 1, 1)
DEFAULT_BASELINE_END = date(2020, 12, 31)

SUPPORTED_MODELS = {"era5", "era5_land"}


def calculate_heatwave_baseline(
    historical_df: pd.DataFrame,
    latitude: float,
    longitude: float,
    model: str = "era5_land",
    baseline_start: date = DEFAULT_BASELINE_START,
    baseline_end: date = DEFAULT_BASELINE_END,
    window_days: int = 5,
    min_observations: int = 100,
) -> dict:
    """
    Calculate fixed calendar-day P90/P95 temperature thresholds.

    Input columns:
        date
        temperature_max_c
        is_imputed (optional)

    The climatological calendar contains 365 days. February 29 is
    excluded from percentile samples and receives thresholds equal
    to the average of February 28 and March 1 thresholds.

    Imputed observations are excluded from baseline calculations
    when an is_imputed column is supplied.

    Returns:
        {
            "metadata": {...},
            "thresholds": DataFrame
        }
    """
    if model not in SUPPORTED_MODELS:
        raise ValueError(
            f"Unsupported model '{model}'. "
            f"Choose one of: {sorted(SUPPORTED_MODELS)}"
        )

    if not np.isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90")

    if not np.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180")

    if baseline_start > baseline_end:
        raise ValueError("baseline_start cannot be after baseline_end")

    if window_days < 1 or window_days % 2 == 0:
        raise ValueError("window_days must be a positive odd integer")

    if min_observations < 1:
        raise ValueError("min_observations must be at least 1")

    required_columns = {"date", TEMPERATURE_COLUMN}
    missing_columns = required_columns - set(historical_df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    data = historical_df.copy()

    data["date"] = pd.to_datetime(data["date"], errors="coerce")

    if data["date"].isna().any():
        raise ValueError("Historical data contains invalid dates")

    if data["date"].dt.tz is not None:
        data["date"] = (
            data["date"].dt.tz_convert("UTC").dt.tz_localize(None)
        )

    if not data["date"].eq(data["date"].dt.normalize()).all():
        raise ValueError("Historical data must contain daily dates")

    data["date"] = data["date"].dt.normalize()

    if data["date"].duplicated().any():
        raise ValueError("Historical data contains duplicate dates")

    data = data.sort_values("date")

    start_timestamp = pd.Timestamp(baseline_start)
    end_timestamp = pd.Timestamp(baseline_end)

    if (
        (data["date"] < start_timestamp).any()
        or (data["date"] > end_timestamp).any()
    ):
        raise ValueError("Input contains dates outside the baseline period")

    expected_dates = pd.date_range(
        start=start_timestamp,
        end=end_timestamp,
        freq="D",
    )

    # Reindex so absent calendar dates are counted as missing.
    data = data.set_index("date").reindex(expected_dates)
    data.index.name = "date"

    temperatures = pd.to_numeric(
        data[TEMPERATURE_COLUMN],
        errors="coerce",
    ).astype(float)

    temperatures = temperatures.where(np.isfinite(temperatures))

    # Imputed values are useful for some event analyses, but should not
    # silently contribute to climatological percentile estimation.
    if "is_imputed" in data.columns:
        is_imputed = data["is_imputed"].fillna(False).astype(bool)
        temperatures = temperatures.mask(is_imputed)

    # Map all non-leap dates to a fixed 365-day climatological calendar.
    # February 29 has no independent climatological day.
    month_day_to_ordinal = {}
    for ordinal in range(1, 366):
        reference_date = date(2001, 1, 1) + pd.Timedelta(days=ordinal - 1)
        month_day_to_ordinal[
            (reference_date.month, reference_date.day)
        ] = ordinal

    sample_dates = temperatures.index
    sample_ordinals = []

    for timestamp in sample_dates:
        month_day = (timestamp.month, timestamp.day)

        if month_day == (2, 29):
            sample_ordinals.append(np.nan)
        else:
            sample_ordinals.append(month_day_to_ordinal[month_day])

    sample_ordinals = np.asarray(sample_ordinals, dtype=float)
    temperature_values = temperatures.to_numpy(dtype=float)

    half_window = window_days // 2
    thresholds = []

    for target_ordinal in range(1, 366):
        # Circular distance lets January and December windows wrap around.
        distances = np.abs(sample_ordinals - target_ordinal)
        distances = np.minimum(distances, 365 - distances)

        in_window = distances <= half_window
        valid_mask = (
            in_window
            & np.isfinite(temperature_values)
        )

        samples = temperature_values[valid_mask]
        sample_count = int(len(samples))

        if sample_count < min_observations:
            p90 = np.nan
            p95 = np.nan
            status = "insufficient_data"
        else:
            p90 = float(np.percentile(samples, 90))
            p95 = float(np.percentile(samples, 95))
            status = "valid"

        reference_date = date(2001, 1, 1) + pd.Timedelta(
            days=target_ordinal - 1
        )

        thresholds.append({
            "month_day": reference_date.strftime("%m-%d"),
            "p90_c": p90,
            "p95_c": p95,
            "sample_count": sample_count,
            "status": status,
        })

    threshold_df = pd.DataFrame(thresholds)

    # Derive February 29 from its neighboring calendar-day thresholds.
    feb28 = threshold_df.loc[
        threshold_df["month_day"] == "02-28"
    ].iloc[0]

    mar01 = threshold_df.loc[
        threshold_df["month_day"] == "03-01"
    ].iloc[0]

    leap_valid = (
        feb28["status"] == "valid"
        and mar01["status"] == "valid"
    )

    leap_row = {
        "month_day": "02-29",
        "p90_c": (
            (feb28["p90_c"] + mar01["p90_c"]) / 2
            if leap_valid else np.nan
        ),
        "p95_c": (
            (feb28["p95_c"] + mar01["p95_c"]) / 2
            if leap_valid else np.nan
        ),
        "sample_count": 0,
        "status": "valid" if leap_valid else "insufficient_data",
    }

    threshold_df = pd.concat(
        [
            threshold_df,
            pd.DataFrame([leap_row]),
        ],
        ignore_index=True,
    ).sort_values("month_day").reset_index(drop=True)

    metadata = {
        "latitude": float(latitude),
        "longitude": float(longitude),
        "model": model,
        "baseline_start": baseline_start.isoformat(),
        "baseline_end": baseline_end.isoformat(),
        "window_days": window_days,
        "percentiles": [90, 95],
        "min_observations": min_observations,
        "temperature_unit": "celsius",
        "method_version": "1.0",
        "valid_threshold_days": int(
            (threshold_df["status"] == "valid").sum()
        ),
        "total_threshold_days": len(threshold_df),
    }

    return {
        "metadata": metadata,
        "thresholds": threshold_df,
    }
