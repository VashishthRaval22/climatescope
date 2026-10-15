
import pandas as pd
import pytest

from app.services.heatwave import (
    detect_heatwaves,
    get_overflow_days_next_year,
)


def make_weather(start_date, temperatures, imputed=None):
    """Build daily weather test data."""
    dates = pd.date_range(start_date, periods=len(temperatures), freq="D")

    return pd.DataFrame({
        "date": dates,
        "temperature_max_c": temperatures,
        "is_imputed": imputed if imputed is not None else [False] * len(temperatures),
    })


def make_thresholds(p90=30.0, p95=35.0):
    """Create valid thresholds for all 366 calendar days."""
    dates = pd.date_range("2000-01-01", "2000-12-31", freq="D")

    return pd.DataFrame({
        "month_day": dates.strftime("%m-%d"),
        "p90_c": p90,
        "p95_c": p95,
        "status": "valid",
    })


def test_three_consecutive_p90_days_produce_heatwave():
    weather = make_weather("2024-01-01", [31, 32, 33])
    events = detect_heatwaves(weather, make_thresholds())

    assert len(events) == 1
    assert events[0]["duration_days"] == 3
    assert events[0]["is_extreme"] is False


def test_two_consecutive_p90_days_do_not_produce_heatwave():
    weather = make_weather("2024-01-01", [31, 32])
    events = detect_heatwaves(weather, make_thresholds())

    assert events == []


def test_three_consecutive_p95_days_classify_episode_as_extreme():
    weather = make_weather("2024-01-01", [36, 37, 38])
    events = detect_heatwaves(weather, make_thresholds())

    assert len(events) == 1
    assert events[0]["is_extreme"] is True
    assert events[0]["extreme_periods"][0]["duration_days"] == 3


def test_short_p95_streak_does_not_classify_episode_as_extreme():
    weather = make_weather("2024-01-01", [36, 37, 31])
    events = detect_heatwaves(weather, make_thresholds())

    assert len(events) == 1
    assert events[0]["is_extreme"] is False


def test_imputed_qualifying_day_continues_streak_and_flags_event():
    weather = make_weather(
        "2024-01-01",
        [31, 32, 33],
        imputed=[False, True, False],
    )
    events = detect_heatwaves(weather, make_thresholds())

    assert len(events) == 1
    assert events[0]["contains_imputed_data"] is True
    assert events[0]["imputed_days"] == 1
    assert events[0]["data_quality"] == "estimated"


def test_unresolved_missing_day_breaks_streak():
    weather = make_weather("2024-01-01", [31, float("nan"), 32, 33])
    events = detect_heatwaves(weather, make_thresholds())

    assert events == []


def test_february_29_uses_its_own_threshold():
    weather = make_weather("2024-02-28", [31, 31, 31])
    thresholds = make_thresholds()

    # February 28 and March 1 use P90 = 30°C.
    # February 29 has its own P90 threshold of 32°C.
    thresholds.loc[
        thresholds["month_day"] == "02-29", "p90_c"
    ] = 32

    events = detect_heatwaves(weather, thresholds)

    # Feb 28 and Mar 1 qualify, but Feb 29 does not.
    # The higher leap-day threshold breaks the streak.
    assert events == []

def test_february_29_can_contribute_to_heatwave():
    weather = make_weather("2024-02-28", [31, 33, 31])
    thresholds = make_thresholds()

    thresholds.loc[
        thresholds["month_day"] == "02-29", "p90_c"
    ] = 32

    events = detect_heatwaves(weather, thresholds)

    assert len(events) == 1
    assert events[0]["start_date"] == "2024-02-28"
    assert events[0]["end_date"] == "2024-03-01"
    assert events[0]["duration_days"] == 3

def test_calendar_gap_does_not_lose_first_day_after_gap():
    weather = make_weather("2024-01-01", [31, 32, 33, 34])
    weather = weather.drop(index=2).reset_index(drop=True)

    events = detect_heatwaves(weather, make_thresholds())

    assert len(events) == 0


def test_invalid_minimum_streak_length_is_rejected():
    weather = make_weather("2024-01-01", [31, 32, 33])

    with pytest.raises(ValueError, match="must be positive"):
        detect_heatwaves(
            weather,
            make_thresholds(),
            min_heatwave_days=0,
        )


# Event-year and cross-year overflow tests

def test_same_year_event_has_zero_overflow():
    weather = make_weather("2024-01-10", [31, 32, 33])
    events = detect_heatwaves(weather, make_thresholds())

    assert len(events) == 1
    assert events[0]["event_year"] == 2024
    assert events[0]["overflow_days_next_year"] == 0


def test_cross_year_event_is_assigned_to_start_year():
    weather = make_weather("2023-12-30", [31, 32, 33, 34, 36])
    events = detect_heatwaves(weather, make_thresholds())

    assert len(events) == 1
    event = events[0]

    assert event["start_date"] == "2023-12-30"
    assert event["end_date"] == "2024-01-03"
    assert event["duration_days"] == 5
    assert event["event_year"] == 2023
    assert event["overflow_days_next_year"] == 3


def test_one_day_overflow_across_year_boundary():
    weather = make_weather("2024-12-31", [31, 32])
    events = detect_heatwaves(weather, make_thresholds())

    assert len(events) == 0  # Only two qualifying days; no heatwave.


def test_overflow_helper_counts_one_day_in_next_year():
    from datetime import date

    assert get_overflow_days_next_year(
        date(2024, 12, 31),
        date(2025, 1, 1),
    ) == 1


def test_overflow_helper_returns_zero_for_same_year():
    from datetime import date

    assert get_overflow_days_next_year(
        date(2024, 2, 28),
        date(2024, 3, 2),
    ) == 0


def test_overflow_helper_rejects_reversed_dates():
    from datetime import date

    with pytest.raises(ValueError, match="start_date cannot be after end_date"):
        get_overflow_days_next_year(
            date(2024, 1, 2),
            date(2024, 1, 1),
        )
