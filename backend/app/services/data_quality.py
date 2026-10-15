
import numpy as np
import pandas as pd


TEMPERATURE_COLUMN = "temperature_max_c"

# Broad sanity limits, not regional climate thresholds.
MIN_PLAUSIBLE_TEMP_C = -90.0
MAX_PLAUSIBLE_TEMP_C = 65.0

SENTINEL_VALUES = {-999.0, 999.0, 9999.0, -9999.0}


def clean_daily_weather(
    raw_data: pd.DataFrame,
    max_gap_days: int = 2,
) -> tuple[pd.DataFrame, dict]:
    """
    Validate daily maximum temperatures and interpolate only short,
    internal gaps.

    Required input columns:
        date
        temperature_max_c

    Returns:
        cleaned_data: date, temperature_max_c, is_imputed
        quality_report: counts and completeness information

    Imputed values are estimates, not source observations.
    """
    if max_gap_days < 0:
        raise ValueError("max_gap_days cannot be negative")

    required_columns = {"date", TEMPERATURE_COLUMN}
    missing_columns = required_columns - set(raw_data.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    data = raw_data[["date", TEMPERATURE_COLUMN]].copy()

    # Parse dates and reject invalid dates rather than silently dropping them.
    data["date"] = pd.to_datetime(data["date"], errors="coerce")

    if data["date"].isna().any():
        raise ValueError("Input contains invalid dates")

    # Daily observations must represent calendar days, not timestamps.
    if data["date"].dt.tz is not None:
        data["date"] = (
            data["date"].dt.tz_convert("UTC").dt.tz_localize(None)
        )

    data["date"] = data["date"].dt.normalize()

    if data["date"].duplicated().any():
        raise ValueError("Duplicate dates must be resolved before cleaning")

    data = data.sort_values("date").set_index("date")

    if data.empty:
        raise ValueError("No weather observations supplied")

    # Ensure every calendar day is represented.
    expected_dates = pd.date_range(
        data.index.min(),
        data.index.max(),
        freq="D",
        name="date",
    )
    requested_days = len(expected_dates)
    missing_calendar_dates = int(
        len(expected_dates.difference(data.index))
    )

    data = data.reindex(expected_dates)

    original_values = data[TEMPERATURE_COLUMN]
    numeric_values = pd.to_numeric(original_values, errors="coerce")

    # Count supplied non-empty values that could not be parsed numerically.
    non_numeric = (
        original_values.notna() & numeric_values.isna()
    )

    numeric_values = numeric_values.astype(float)

    sentinel_mask = numeric_values.isin(SENTINEL_VALUES)
    non_finite_mask = (
        numeric_values.notna() & ~np.isfinite(numeric_values)
    )
    physical_mask = (
        numeric_values.notna()
        & np.isfinite(numeric_values)
        & ~sentinel_mask
        & (
            (numeric_values < MIN_PLAUSIBLE_TEMP_C)
            | (numeric_values > MAX_PLAUSIBLE_TEMP_C)
        )
    )

    invalid_mask = (
        sentinel_mask | non_finite_mask | physical_mask
    )

    # Replace invalid readings with missing values before interpolation.
    values = numeric_values.mask(invalid_mask)

    raw_missing_count = int(values.isna().sum())
    invalid_count = int(invalid_mask.sum())

    # Find complete missing runs. Only interpolate a whole run if it is
    # internal and its length does not exceed max_gap_days.
    missing = values.isna()
    group_ids = missing.ne(missing.shift(fill_value=False)).cumsum()
    run_lengths = missing.groupby(group_ids).transform("sum")

    eligible = (
        missing
        & run_lengths.le(max_gap_days)
        & values.notna().cummax()
        & values.notna()[::-1].cummax()[::-1]
    )

    # Interpolate only eligible missing dates. Long gaps and edge gaps
    # remain missing. Use time-based linear interpolation.
    interpolated = values.interpolate(
        method="time",
        limit_area="inside",
    )

    cleaned_values = values.where(~eligible, interpolated)
    is_imputed = values.isna() & cleaned_values.notna()

    result = pd.DataFrame({
        "date": cleaned_values.index,
        TEMPERATURE_COLUMN: cleaned_values.to_numpy(),
        "is_imputed": is_imputed.to_numpy(),
    })

    remaining_missing = int(result[TEMPERATURE_COLUMN].isna().sum())
    imputed_count = int(result["is_imputed"].sum())

    # Completeness is based on original usable observations, before
    # interpolation, so estimates do not inflate source-data coverage.
    observed_count = requested_days - raw_missing_count
    completeness = (
        100.0 * observed_count / requested_days
        if requested_days
        else 0.0
    )

    quality_report = {
        "requested_days": requested_days,
        "missing_calendar_dates": missing_calendar_dates,
        "non_numeric_values": int(non_numeric.sum()),
        "sentinel_values": int(sentinel_mask.sum()),
        "non_finite_values": int(non_finite_mask.sum()),
        "physically_implausible_values": int(physical_mask.sum()),
        "unusable_days_before_imputation": raw_missing_count,
        "imputed_days": imputed_count,
        "remaining_missing_days": remaining_missing,
        "source_completeness_percent": round(completeness, 2),
        "analysis_ready": remaining_missing == 0,
    }

    return result.reset_index(drop=True), quality_report
