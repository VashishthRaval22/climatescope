
import numpy as np
import pandas as pd

from app.services.baseline import calculate_heatwave_baseline


def make_historical_data():
    dates = pd.date_range("1991-01-01", "2020-12-31", freq="D")

    # Deterministic synthetic seasonal temperatures.
    day_of_year = dates.dayofyear.to_numpy()
    temperatures = (
        30
        + 5 * np.sin(2 * np.pi * (day_of_year - 100) / 365.25)
    )

    return pd.DataFrame({
        "date": dates,
        "temperature_max_c": temperatures,
        "is_imputed": False,
    })


def test_baseline_returns_366_calendar_dates():
    result = calculate_heatwave_baseline(
        make_historical_data(),
        latitude=19.076,
        longitude=72.8777,
    )

    thresholds = result["thresholds"]

    assert len(thresholds) == 366
    assert "02-29" in thresholds["month_day"].values
    assert result["metadata"]["model"] == "era5_land"


def test_thresholds_are_ordered():
    result = calculate_heatwave_baseline(
        make_historical_data(),
        latitude=19.076,
        longitude=72.8777,
    )

    thresholds = result["thresholds"]
    valid = thresholds[thresholds["status"] == "valid"]

    assert (valid["p95_c"] >= valid["p90_c"]).all()


def test_imputed_values_are_excluded():
    data = make_historical_data()

    data.loc[0, "is_imputed"] = True

    result = calculate_heatwave_baseline(
        data,
        latitude=19.076,
        longitude=72.8777,
    )

    jan1 = result["thresholds"].query(
        "month_day == '01-01'"
    ).iloc[0]

    # January 1's five-day window includes the imputed observation,
    # which should not contribute to the sample.
    assert jan1["sample_count"] == 149


def test_rejects_duplicate_dates():
    data = make_historical_data()
    data = pd.concat([data, data.iloc[[0]]], ignore_index=True)

    try:
        calculate_heatwave_baseline(
            data,
            latitude=19.076,
            longitude=72.8777,
        )
    except ValueError as exc:
        assert "duplicate dates" in str(exc).lower()
    else:
        raise AssertionError("Expected duplicate dates to be rejected")
