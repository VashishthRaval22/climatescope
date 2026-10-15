
import pytest

from app.services.trends import (
    add_lowess_smoothing,
    aggregate_yearly_trends,
    build_trend_analysis,
    calculate_theil_sen_slope,
)


# ---------------------------------------------------------------------------
# aggregate_yearly_trends
# ---------------------------------------------------------------------------


def test_aggregate_yearly_trends_aggregates_events_by_start_year():
    events = [
        {
            "event_year": 2020,
            "duration_days": 3,
            "severity": "Moderate",
            "overflow_days_next_year": 1,
            "peak_temperature_c": 42.0,
        },
        {
            "event_year": 2020,
            "duration_days": 5,
            "severity": "Extreme",
            "is_extreme": True,
            "overflow_days_next_year": 2,
            "peak_temperature_c": 45.0,
        },
        {
            "event_year": 2021,
            "duration_days": 4,
            "severity": "Moderate",
            "overflow_days_next_year": 0,
            "peak_temperature_c": 43.0,
        },
    ]

    result = aggregate_yearly_trends(events, 2020, 2021)

    assert len(result) == 2

    assert result[0]["year"] == 2020
    assert result[0]["heatwave_events"] == 2
    assert result[0]["extreme_heatwave_events"] == 1
    assert result[0]["total_heatwave_days"] == 8
    assert result[0]["longest_heatwave_days"] == 5
    assert result[0]["overflow_days_next_year"] == 3
    assert result[0]["peak_temperature_c"] == 45.0

    assert result[1]["year"] == 2021
    assert result[1]["heatwave_events"] == 1
    assert result[1]["extreme_heatwave_events"] == 0
    assert result[1]["total_heatwave_days"] == 4
    assert result[1]["longest_heatwave_days"] == 4
    assert result[1]["overflow_days_next_year"] == 0
    assert result[1]["peak_temperature_c"] == 43.0


def test_aggregate_yearly_trends_includes_years_without_events():
    events = [
        {
            "event_year": 2020,
            "duration_days": 3,
            "severity": "Moderate",
            "overflow_days_next_year": 0,
            "peak_temperature_c": 40.0,
        }
    ]

    result = aggregate_yearly_trends(events, 2020, 2022)

    assert [row["year"] for row in result] == [2020, 2021, 2022]
    assert result[0]["heatwave_events"] == 1
    assert result[1]["heatwave_events"] == 0
    assert result[2]["heatwave_events"] == 0
    assert result[1]["total_heatwave_days"] == 0
    assert result[2]["total_heatwave_days"] == 0


def test_aggregate_yearly_trends_filters_events_outside_requested_range():
    events = [
        {
            "event_year": 2019,
            "duration_days": 2,
            "severity": "Moderate",
            "overflow_days_next_year": 0,
            "peak_temperature_c": 39.0,
        },
        {
            "event_year": 2020,
            "duration_days": 3,
            "severity": "Moderate",
            "overflow_days_next_year": 0,
            "peak_temperature_c": 41.0,
        },
        {
            "event_year": 2022,
            "duration_days": 4,
            "severity": "Extreme",
            "overflow_days_next_year": 0,
            "peak_temperature_c": 44.0,
        },
    ]

    result = aggregate_yearly_trends(events, 2020, 2021)

    assert [row["year"] for row in result] == [2020, 2021]
    assert result[0]["heatwave_events"] == 1
    assert result[1]["heatwave_events"] == 0

def test_aggregate_yearly_trends_rejects_reversed_year_range():
    with pytest.raises(
        ValueError,
        match="start_year cannot be after end_year",
    ):
        aggregate_yearly_trends([], 2022, 2020)


def test_aggregate_yearly_trends_rejects_missing_event_year():
    events = [
        {
            "duration_days": 3,
            "severity": "Moderate",
            "overflow_days_next_year": 0,
            "peak_temperature_c": 40.0,
        }
    ]

    with pytest.raises((KeyError, ValueError)):
        aggregate_yearly_trends(events, 2020, 2021)


def test_aggregate_yearly_trends_rejects_invalid_duration():
    events = [
        {
            "event_year": 2020,
            "duration_days": -1,
            "severity": "Moderate",
            "overflow_days_next_year": 0,
            "peak_temperature_c": 40.0,
        }
    ]

    with pytest.raises(ValueError):
        aggregate_yearly_trends(events, 2020, 2021)


def test_aggregate_yearly_trends_rejects_invalid_overflow_days():
    events = [
        {
            "event_year": 2020,
            "duration_days": 3,
            "severity": "Moderate",
            "overflow_days_next_year": -1,
            "peak_temperature_c": 40.0,
        }
    ]

    with pytest.raises(ValueError):
        aggregate_yearly_trends(events, 2020, 2021)


# ---------------------------------------------------------------------------
# calculate_theil_sen_slope
# ---------------------------------------------------------------------------


def test_theil_sen_calculates_increasing_days_per_decade():
    trends = [
        {"year": 2000, "total_heatwave_days": 0},
        {"year": 2001, "total_heatwave_days": 1},
        {"year": 2002, "total_heatwave_days": 2},
        {"year": 2003, "total_heatwave_days": 3},
    ]

    result = calculate_theil_sen_slope(
        trends, metric="total_heatwave_days"
    )

    assert result["slope_per_decade"] == pytest.approx(10.0)
    assert result["direction"] == "increasing"
    assert result["n_years"] == 4


def test_theil_sen_calculates_decreasing_trend():
    trends = [
        {"year": 2000, "total_heatwave_days": 10},
        {"year": 2001, "total_heatwave_days": 8},
        {"year": 2002, "total_heatwave_days": 6},
        {"year": 2003, "total_heatwave_days": 4},
    ]

    result = calculate_theil_sen_slope(
        trends, metric="total_heatwave_days"
    )

    assert result["slope_per_decade"] == pytest.approx(-20.0)
    assert result["direction"] == "decreasing"


def test_theil_sen_returns_stable_for_constant_values():
    trends = [
        {"year": 2000, "total_heatwave_days": 5},
        {"year": 2001, "total_heatwave_days": 5},
        {"year": 2002, "total_heatwave_days": 5},
    ]

    result = calculate_theil_sen_slope(
        trends, metric="total_heatwave_days"
    )

    assert result["slope_per_decade"] == pytest.approx(0.0)
    assert result["direction"] == "stable"


def test_theil_sen_includes_genuine_zero_event_years():
    trends = [
        {"year": 2000, "total_heatwave_days": 0},
        {"year": 2001, "total_heatwave_days": 0},
        {"year": 2002, "total_heatwave_days": 10},
        {"year": 2003, "total_heatwave_days": 0},
    ]

    result = calculate_theil_sen_slope(
        trends, metric="total_heatwave_days"
    )

    assert result["n_years"] == 4
    assert result["slope_per_decade"] is not None


def test_theil_sen_handles_missing_metric_values():
    trends = [
        {"year": 2000, "total_heatwave_days": 0},
        {"year": 2001, "total_heatwave_days": None},
        {"year": 2002, "total_heatwave_days": 4},
        {"year": 2003, "total_heatwave_days": 6},
    ]

    result = calculate_theil_sen_slope(
        trends, metric="total_heatwave_days"
    )

    assert result["n_years"] == 3
    assert result["slope_per_decade"] is not None


def test_theil_sen_returns_insufficient_data_for_one_observation():
    trends = [{"year": 2000, "total_heatwave_days": 5}]

    result = calculate_theil_sen_slope(
        trends, metric="total_heatwave_days"
    )

    assert result["slope_per_decade"] is None
    assert result["n_years"] == 1


# ---------------------------------------------------------------------------
# add_lowess_smoothing
# ---------------------------------------------------------------------------


def test_lowess_adds_smoothed_values_without_removing_original_data():
    trends = [
        {"year": 2000, "total_heatwave_days": 1},
        {"year": 2001, "total_heatwave_days": 3},
        {"year": 2002, "total_heatwave_days": 2},
        {"year": 2003, "total_heatwave_days": 6},
        {"year": 2004, "total_heatwave_days": 5},
    ]

    result = add_lowess_smoothing(
        trends, metric="total_heatwave_days", frac=0.6
    )

    assert len(result) == len(trends)

    for original, smoothed in zip(trends, result):
        assert smoothed["year"] == original["year"]
        assert smoothed["total_heatwave_days"] == original["total_heatwave_days"]
        assert "total_heatwave_days_lowess" in smoothed

    assert all(
        row["total_heatwave_days_lowess"] is not None for row in result
    )


def test_lowess_preserves_zero_values():
    trends = [
        {"year": 2000, "total_heatwave_days": 0},
        {"year": 2001, "total_heatwave_days": 0},
        {"year": 2002, "total_heatwave_days": 5},
        {"year": 2003, "total_heatwave_days": 0},
        {"year": 2004, "total_heatwave_days": 2},
    ]

    result = add_lowess_smoothing(
        trends, metric="total_heatwave_days", frac=0.6
    )

    assert [row["total_heatwave_days"] for row in result] == [0, 0, 5, 0, 2]
    assert all(
        row["total_heatwave_days_lowess"] is not None for row in result
    )


def test_lowess_returns_none_when_insufficient_valid_observations():
    trends = [
        {"year": 2000, "total_heatwave_days": 1},
        {"year": 2001, "total_heatwave_days": None},
        {"year": 2002, "total_heatwave_days": 3},
    ]

    result = add_lowess_smoothing(
        trends, metric="total_heatwave_days", frac=0.6
    )

    assert all(row["total_heatwave_days_lowess"] is None for row in result)


def test_lowess_rejects_invalid_fraction():
    trends = [
        {"year": 2000, "total_heatwave_days": 1},
        {"year": 2001, "total_heatwave_days": 2},
        {"year": 2002, "total_heatwave_days": 3},
    ]

    with pytest.raises(ValueError):
        add_lowess_smoothing(
            trends, metric="total_heatwave_days", frac=0
        )

    with pytest.raises(ValueError):
        add_lowess_smoothing(
            trends, metric="total_heatwave_days", frac=1.1
        )


# ---------------------------------------------------------------------------
# build_trend_analysis
# ---------------------------------------------------------------------------


def test_build_trend_analysis_returns_slope_and_methodology():
    trends = [
        {"year": 2000, "total_heatwave_days": 0},
        {"year": 2001, "total_heatwave_days": 1},
        {"year": 2002, "total_heatwave_days": 2},
        {"year": 2003, "total_heatwave_days": 3},
    ]

    result = build_trend_analysis(trends)

    assert "headline" in result
    assert result["headline"]["slope_per_decade"] == pytest.approx(10.0)
    assert result["headline"]["direction"] == "increasing"

    assert "methodology" in result
    assert result["methodology"]["statistical_significance_tested"] is False


def test_build_trend_analysis_does_not_claim_statistical_significance():
    trends = [
        {"year": 2000, "total_heatwave_days": 1},
        {"year": 2001, "total_heatwave_days": 2},
        {"year": 2002, "total_heatwave_days": 3},
    ]

    result = build_trend_analysis(trends)

    assert result["methodology"]["statistical_significance_tested"] is False
