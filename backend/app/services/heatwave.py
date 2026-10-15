
from datetime import date

import numpy as np
import pandas as pd


TEMPERATURE_COLUMN = "temperature_max_c"
MIN_HEATWAVE_DAYS = 3
MIN_EXTREME_DAYS = 3


def _validate_daily_data(cleaned_data: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize cleaned daily weather data."""
    required = {"date", TEMPERATURE_COLUMN}
    missing = required - set(cleaned_data.columns)

    if missing:
        raise ValueError(
            f"Missing weather columns: {sorted(missing)}"
        )

    data = cleaned_data.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")

    if data["date"].isna().any():
        raise ValueError("Weather data contains invalid dates")

    if data["date"].dt.tz is not None:
        data["date"] = (
            data["date"].dt.tz_convert("UTC").dt.tz_localize(None)
        )

    data["date"] = data["date"].dt.normalize()

    if data["date"].duplicated().any():
        raise ValueError("Weather data contains duplicate dates")

    data = data.sort_values("date").reset_index(drop=True)

    # A missing flag means the supplied reading is observed.
    if "is_imputed" not in data.columns:
        data["is_imputed"] = False

    if data["is_imputed"].isna().any():
        raise ValueError("is_imputed cannot contain missing values")

    data["is_imputed"] = data["is_imputed"].astype(bool)

    data[TEMPERATURE_COLUMN] = pd.to_numeric(
        data[TEMPERATURE_COLUMN],
        errors="coerce",
    )

    # Treat non-finite values as missing, not as valid temperatures.
    finite = np.isfinite(data[TEMPERATURE_COLUMN])
    data.loc[~finite, TEMPERATURE_COLUMN] = np.nan

    return data


def _validate_thresholds(thresholds: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize the calendar-day baseline thresholds."""
    required = {"month_day", "p90_c", "p95_c", "status"}
    missing = required - set(thresholds.columns)

    if missing:
        raise ValueError(
            f"Missing threshold columns: {sorted(missing)}"
        )

    result = thresholds.copy()

    if result["month_day"].duplicated().any():
        raise ValueError("Thresholds contain duplicate calendar days")

    # Validate MM-DD labels, including February 29.
    def validate_month_day(value):
        try:
            parsed = pd.to_datetime(
                f"2000-{value}",
                format="%Y-%m-%d",
                errors="raise",
            )
            return parsed.strftime("%m-%d")
        except (TypeError, ValueError):
            raise ValueError(
                f"Invalid month_day threshold value: {value!r}"
            ) from None

    result["month_day"] = result["month_day"].map(validate_month_day)

    result["p90_c"] = pd.to_numeric(result["p90_c"], errors="coerce")
    result["p95_c"] = pd.to_numeric(result["p95_c"], errors="coerce")

    for column in ("p90_c", "p95_c"):
        result.loc[~np.isfinite(result[column]), column] = np.nan

    valid = result["status"].eq("valid")

    # Only valid baseline rows can be used for detection.
    result.loc[~valid, ["p90_c", "p95_c"]] = np.nan

    invalid_order = (
        valid
        & result["p90_c"].notna()
        & result["p95_c"].notna()
        & (result["p95_c"] < result["p90_c"])
    )
    if invalid_order.any():
        raise ValueError("P95 thresholds cannot be below P90 thresholds")

    return result[["month_day", "p90_c", "p95_c", "status"]]


def _find_runs(
    mask: list[bool],
    dates: list | None = None,
) -> list[tuple[int, int]]:
    """Find consecutive qualifying runs, respecting calendar gaps."""
    runs = []
    start = None

    for index, qualifies in enumerate(mask):
        has_date_gap = (
            dates is not None
            and index > 0
            and (dates[index] - dates[index - 1]).days != 1
        )

        if has_date_gap and start is not None:
            runs.append((start, index - 1))
            start = None

        if qualifies:
            if start is None:
                start = index
        elif start is not None:
            runs.append((start, index - 1))
            start = None

    if start is not None:
        runs.append((start, len(mask) - 1))

    return runs

def get_overflow_days_next_year(
    start_date: date,
    end_date: date,
) -> int:
    """Count event days in the year after the event's start year."""
    if start_date > end_date:
        raise ValueError("start_date cannot be after end_date")

    if start_date.year == end_date.year:
        return 0

    next_year_start = date(start_date.year + 1, 1, 1)
    return (end_date - next_year_start).days + 1

def detect_heatwaves(
    cleaned_data: pd.DataFrame,
    thresholds: pd.DataFrame,
    min_heatwave_days: int = MIN_HEATWAVE_DAYS,
    min_extreme_days: int = MIN_EXTREME_DAYS,
) -> list[dict]:
    """
    Detect P90 heatwave episodes and classify P95 extreme periods.

    Rules:
    - A heatwave requires at least min_heatwave_days consecutive
      days with maximum temperature >= the daily P90 threshold.
    - An episode is extreme if it contains at least one run of
      min_extreme_days consecutive days >= the daily P95 threshold.
    - Imputed temperatures may contribute to streaks but are flagged.
    - Missing temperatures or invalid thresholds break a streak.
    - Each heatwave episode is returned once; extreme periods are
      recorded as nested metadata rather than duplicate events.

    Returns:
        A list of event dictionaries, ordered by start date.
    """
    if min_heatwave_days < 1 or min_extreme_days < 1:
        raise ValueError("Minimum streak lengths must be positive")

    weather = _validate_daily_data(cleaned_data)
    baseline = _validate_thresholds(thresholds)

    if weather.empty:
        return []

    # Join each observation to its calendar-day climatological threshold.
    weather["month_day"] = weather["date"].dt.strftime("%m-%d")

    # February 29 has its own baseline row, calculated by baseline.py.
    weather = weather.merge(
        baseline,
        on="month_day",
        how="left",
        validate="many_to_one",
    )

    # Missing/invalid thresholds and missing temperatures cannot qualify.
    valid_threshold = (
        weather["status"].eq("valid")
        & weather["p90_c"].notna()
        & weather["p95_c"].notna()
    )
    observed_temperature = weather[TEMPERATURE_COLUMN].notna()

    p90_qualifies = (
        valid_threshold
        & observed_temperature
        & (weather[TEMPERATURE_COLUMN] >= weather["p90_c"])
    )
    p95_qualifies = (
        valid_threshold
        & observed_temperature
        & (weather[TEMPERATURE_COLUMN] >= weather["p95_c"])
    )

    # Do not accidentally join consecutive rows across a gap in dates.
    date_diffs = weather["date"].diff().dt.days
    consecutive_calendar_day = date_diffs.eq(1)
    if len(weather):
        consecutive_calendar_day.iloc[0] = True

    # A date gap breaks both streaks. The cleaning stage normally
    # supplies every date between the first and last observation.
    p90_mask = p90_qualifies.tolist()

    # Explicitly split runs at any missing/invalid/non-P90 day.
    episode_runs = _find_runs(
        p90_mask,
        weather["date"].tolist(),
    )

    events = []

    for start_index, end_index in episode_runs:
        episode = weather.iloc[start_index:end_index + 1].copy()

        # The P90 mask can include a date gap only if malformed input
        # omitted calendar days. Reject such runs defensively.
        if (
            len(episode) < min_heatwave_days
            or not episode["date"].diff().dropna().eq(
                pd.Timedelta(days=1)
            ).all()
        ):
            continue

        if not p90_qualifies.iloc[start_index:end_index + 1].all():
            continue

        episode_p95 = p95_qualifies.iloc[
            start_index:end_index + 1
        ].tolist()

        # Find P95 runs within the P90 episode.
        p95_runs = [
            (start_index + run_start, start_index + run_end)
            for run_start, run_end in _find_runs(episode_p95)
            if run_end - run_start + 1 >= min_extreme_days
        ]

        extreme_periods = []
        for extreme_start, extreme_end in p95_runs:
            extreme_periods.append({
                "start_date": weather.iloc[extreme_start][
                    "date"
                ].date().isoformat(),
                "end_date": weather.iloc[extreme_end][
                    "date"
                ].date().isoformat(),
                "duration_days": extreme_end - extreme_start + 1,
                "peak_temperature_c": round(
                    float(
                        weather.iloc[
                            extreme_start:extreme_end + 1
                        ][TEMPERATURE_COLUMN].max()
                    ),
                    2,
                ),
            })

        imputed = episode["is_imputed"].astype(bool)
        imputed_days = int(imputed.sum())
        temperatures = episode[TEMPERATURE_COLUMN]

        event_start_date = episode["date"].iloc[0].date()
        event_end_date = episode["date"].iloc[-1].date()

        events.append({
            "start_date": event_start_date.isoformat(),
            "end_date": event_end_date.isoformat(),
            "duration_days": len(episode),
            "event_year": event_start_date.year,
            "overflow_days_next_year": get_overflow_days_next_year(
                event_start_date,
                event_end_date,
            ),
            "peak_temperature_c": round(
                float(temperatures.max()), 2
            ),
            "mean_temperature_c": round(
                float(temperatures.mean()), 2
            ),
            "contains_imputed_data": imputed_days > 0,
            "imputed_days": imputed_days,
            "data_quality": (
                "estimated" if imputed_days else "observed"
            ),
            "is_extreme": len(extreme_periods) > 0,
            "extreme_periods": extreme_periods,
        })

    return events
