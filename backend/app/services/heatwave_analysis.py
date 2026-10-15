from datetime import date

import pandas as pd

from app.services.weather import fetch_daily_weather
from app.services.data_quality import clean_daily_weather
from app.services.baseline import calculate_heatwave_baseline
from app.services.heatwave import detect_heatwaves


from app.services.baseline_cache import (
    get_cached_baseline,
    save_cached_baseline,
)

DEFAULT_MODEL = "era5_land"
DEFAULT_BASELINE_START = date(1991, 1, 1)
DEFAULT_BASELINE_END = date(2020, 12, 31)
EVENT_CONTEXT_DAYS = 30


def _parse_date(value, field_name: str) -> date:
    """Accept date objects or ISO-formatted YYYY-MM-DD strings."""
    if isinstance(value, date):
        return value

    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        raise ValueError(
            f"{field_name} must be a valid YYYY-MM-DD date"
        ) from None


def _validate_coordinates(latitude: float, longitude: float) -> None:
    if not -90 <= latitude <= 90:
        raise ValueError("latitude must be between -90 and 90")

    if not -180 <= longitude <= 180:
        raise ValueError("longitude must be between -180 and 180")


def _validate_baseline(baseline: dict) -> None:
    """Reject incomplete or invalid climatological thresholds."""
    if not isinstance(baseline, dict):
        raise ValueError("Baseline must be a dictionary")
    
    if not isinstance(baseline.get("thresholds"), pd.DataFrame):
        raise ValueError("Baseline thresholds must be a pandas DataFrame")
    
    if not isinstance(baseline.get("metadata"), dict):
        raise ValueError("Baseline metadata must be a dictionary")

    thresholds = baseline.get("thresholds")

    required_columns = {"month_day", "p90_c", "p95_c", "status"}

    if not required_columns.issubset(thresholds.columns):
        raise ValueError("Baseline is missing required threshold columns")

    if len(thresholds) != 366:
        raise ValueError(
            "The baseline must contain 366 valid daily heat thresholds. "
            "Check baseline coverage and data quality."
        )

    if (
        not thresholds["status"].eq("valid").all()
        or thresholds["month_day"].nunique() != 366
        or thresholds[["p90_c", "p95_c"]].isna().any().any()
        or not thresholds[["p90_c", "p95_c"]].apply(
            lambda column: column.map(
                lambda value: isinstance(value, (int, float))
                and pd.notna(value)
            )
        ).all().all()
        or (thresholds["p90_c"] > thresholds["p95_c"]).any()
    ):
        raise ValueError(
            "The baseline must contain 366 valid daily heat thresholds. "
            "Check baseline coverage and data quality."
        )


def analyze_heatwaves(
    latitude: float,
    longitude: float,
    start_date: date | str,
    end_date: date | str,
    model: str = DEFAULT_MODEL,
    baseline_start: date | str = DEFAULT_BASELINE_START,
    baseline_end: date | str = DEFAULT_BASELINE_END,
    max_gap_days: int = 2,
) -> dict:
    """
    Run heatwave analysis for a location and date range.
    
    Workflow:
    1. Load a cached historical baseline, or calculate it on a cache miss.
    2. Validate all 366 daily P90/P95 thresholds.
    3. Fetch and clean the requested analysis-period weather.
    4. Detect heatwave episodes and extreme periods.
    """
    _validate_coordinates(latitude, longitude)

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date")
    baseline_start = _parse_date(baseline_start, "baseline_start")
    baseline_end = _parse_date(baseline_end, "baseline_end")

    if start > end:
        raise ValueError("start_date cannot be after end_date")

    if baseline_start > baseline_end:
        raise ValueError(
            "baseline_start cannot be after baseline_end"
        )

    if max_gap_days < 0:
        raise ValueError("max_gap_days cannot be negative")


    # Step 1: Reuse a cached baseline when possible.
    cached = get_cached_baseline(
        latitude=latitude,
        longitude=longitude,
        model=model,
        baseline_start=baseline_start,
        baseline_end=baseline_end,
    )

    if cached is not None:
        baseline, baseline_quality = cached

    else:
        # Cache miss: fetch and clean the historical data.
        raw_baseline = fetch_daily_weather(
            latitude=latitude,
            longitude=longitude,
            start_date=baseline_start,
            end_date=baseline_end,
            model=model,
        )

        cleaned_baseline, baseline_quality = clean_daily_weather(
            raw_baseline,
            max_gap_days=max_gap_days,
        )

        baseline = calculate_heatwave_baseline(
            historical_df=cleaned_baseline,
            latitude=latitude,
            longitude=longitude,
            model=model,
            baseline_start=baseline_start,
            baseline_end=baseline_end,
        )

        # Validate before saving to MongoDB.
        _validate_baseline(baseline)

        # Save the baseline for future requests.
        save_cached_baseline(
            latitude=latitude,
            longitude=longitude,
            model=model,
            baseline_start=baseline_start,
            baseline_end=baseline_end,
            baseline=baseline,
            baseline_quality=baseline_quality,
        )

    # Validate both cached and newly calculated baselines.
    _validate_baseline(baseline)
    
    thresholds = baseline["thresholds"]
    baseline_metadata = baseline["metadata"]


    # Step 3: Fetch context around the requested period so that
    # heatwaves crossing the selected dates can be detected.
    from datetime import timedelta

    context_start = start - timedelta(days=EVENT_CONTEXT_DAYS)
    context_end = end + timedelta(days=EVENT_CONTEXT_DAYS)

    raw_weather = fetch_daily_weather(
        latitude=latitude,
        longitude=longitude,
        start_date=context_start,
        end_date=context_end,
        model=model,
    )

    cleaned_weather, _ = clean_daily_weather(
        raw_weather,
        max_gap_days=max_gap_days,
    )

    # Calculate data quality for the requested dates only.
    raw_dates = pd.to_datetime(raw_weather["date"])
    requested_raw_weather = raw_weather.loc[
        (raw_dates >= pd.Timestamp(start))
        & (raw_dates <= pd.Timestamp(end))
    ].copy()

    _, analysis_quality = clean_daily_weather(
        requested_raw_weather,
        max_gap_days=max_gap_days,
    )

    # Detect complete episodes in the wider context.
    all_events = detect_heatwaves(
        cleaned_data=cleaned_weather,
        thresholds=thresholds,
    )

    # Keep events that overlap the requested period, preserving
    # their actual start/end dates from the context analysis.
    events = []

    for original_event in all_events:
        event = original_event.copy()
        event_start = date.fromisoformat(event["start_date"])
        event_end = date.fromisoformat(event["end_date"])

        if event_end < start or event_start > end:
            continue

        event["start_boundary_unresolved"] = (
            event_start == context_start
        )
        event["end_boundary_unresolved"] = (
            event_end == context_end
        )
        event["boundary_status"] = (
            "unresolved"
            if (
                event["start_boundary_unresolved"]
                or event["end_boundary_unresolved"]
            )
            else "complete"
        )

        # Number of event days actually inside the requested range.
        overlap_start = max(event_start, start)
        overlap_end = min(event_end, end)
        event["days_in_requested_period"] = (
            overlap_end - overlap_start
        ).days + 1

        # Explicitly identify an event that began before the
        # requested period; this is not the same as overflow.
        event["starts_before_requested_period"] = event_start < start
        event["ends_after_requested_period"] = event_end > end

        events.append(event)

    extreme_events = [
        event for event in events if event["is_extreme"]
    ]

    # Return JSON-friendly values for the future FastAPI endpoint.
    return {
        "location": {
            "latitude": float(latitude),
            "longitude": float(longitude),
        },
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "summary": {
            "total_heatwave_events": len(events),
            "extreme_heatwave_events": len(extreme_events),
            "total_heatwave_days": sum(
                event["days_in_requested_period"] for event in events
            ),
            "events_containing_imputed_data": sum(
                event["contains_imputed_data"] for event in events
            ),
        },
        "baseline": baseline_metadata,
        "data_quality": {
            "baseline": baseline_quality,
            "analysis_period": analysis_quality,
        },
        "events": events,
    }
