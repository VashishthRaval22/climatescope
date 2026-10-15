import pandas as pd
import pytest
from datetime import date, timedelta

from app.services import heatwave_analysis as analysis


def test_analysis_orchestrates_services(monkeypatch):
    fetch_calls = []

    def fake_fetch(**kwargs):
        fetch_calls.append(kwargs)
        return pd.DataFrame({
            "date": pd.to_datetime([
                "2024-01-01",
                "2024-01-02",
                "2024-01-03",
            ]),
            "temperature_max_c": [32.0, 36.0, 37.0],
        })

    def fake_clean(raw_data, max_gap_days=2):
        cleaned = raw_data.copy()
        cleaned["is_imputed"] = False
        return cleaned, {
            "requested_days": len(cleaned),
            "imputed_days": 0,
            "analysis_ready": True,
        }

    calendar_dates = [
        date(2001, 1, 1) + timedelta(days=i)
        for i in range(365)
    ]

    month_days = [
        current.strftime("%m-%d")
        for current in calendar_dates
    ]
    month_days.append("02-29")

    thresholds = pd.DataFrame({
        "month_day": month_days,
        "p90_c": [30.0] * 366,
        "p95_c": [35.0] * 366,
        "status": ["valid"] * 366,
    })

    def fake_baseline(**kwargs):
        return {
            "metadata": {
                "model": kwargs["model"],
                "valid_threshold_days": 366,
            },
            "thresholds": thresholds,
        }

    fake_event = {
        "start_date": "2024-01-01",
        "end_date": "2024-01-03",
        "duration_days": 3,
        "peak_temperature_c": 37.0,
        "mean_temperature_c": 35.0,
        "contains_imputed_data": False,
        "imputed_days": 0,
        "data_quality": "observed",
        "is_extreme": True,
        "extreme_periods": [],
    }

    monkeypatch.setattr(analysis, "fetch_daily_weather", fake_fetch)
    monkeypatch.setattr(analysis, "clean_daily_weather", fake_clean)
    monkeypatch.setattr(
        analysis, "calculate_heatwave_baseline", fake_baseline
    )
    monkeypatch.setattr(
        analysis, "detect_heatwaves", lambda **kwargs: [fake_event]
    )

    monkeypatch.setattr(
        analysis,
        "get_cached_baseline",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        analysis,
        "save_cached_baseline",
        lambda **kwargs: None,
    )

    result = analysis.analyze_heatwaves(
        latitude=19.076,
        longitude=72.8777,
        start_date="2024-01-01",
        end_date="2024-01-03",
    )

    assert len(fetch_calls) == 2
    assert result["start_date"] == "2024-01-01"
    assert result["end_date"] == "2024-01-03"

    assert result["location"]["latitude"] == 19.076
    assert result["location"]["longitude"] == 72.8777

    assert result["summary"]["total_heatwave_events"] == 1
    assert result["summary"]["extreme_heatwave_events"] == 1

    assert len(result["events"]) == 1
    # assert result["events"][0]["start_date"] == "2024-01-01"
    # assert result["summary"]["total_heatwave_events"] == 1
    # assert result["summary"]["extreme_heatwave_events"] == 1

    event = result["events"][0]

    assert event["start_date"] == "2024-01-01"
    assert event["end_date"] == "2024-01-03"
    assert event["duration_days"] == 3
    assert event["days_in_requested_period"] == 3
    assert event["starts_before_requested_period"] is False
    assert event["ends_after_requested_period"] is False
    assert event["boundary_status"] == "complete"
    assert result["data_quality"]["analysis_period"]["analysis_ready"]


def test_invalid_coordinates_are_rejected_before_fetch(monkeypatch):
    def unexpected_fetch(**kwargs):
        pytest.fail("Weather API should not be called")

    monkeypatch.setattr(
        analysis, "fetch_daily_weather", unexpected_fetch
    )

    with pytest.raises(ValueError, match="latitude"):
        analysis.analyze_heatwaves(
            latitude=100,
            longitude=75,
            start_date="2024-01-01",
            end_date="2024-01-03",
        )


def test_start_date_after_end_date_is_rejected(monkeypatch):
    def unexpected_fetch(**kwargs):
        pytest.fail("Weather API should not be called")

    monkeypatch.setattr(
        analysis, "fetch_daily_weather", unexpected_fetch
    )

    with pytest.raises(ValueError, match="cannot be after"):
        analysis.analyze_heatwaves(
            latitude=19.076,
            longitude=72.8777,
            start_date=date(2024, 2, 1),
            end_date=date(2024, 1, 1),
        )
