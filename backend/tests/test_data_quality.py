
import numpy as np
import pandas as pd
import pytest

from app.services.data_quality import clean_daily_weather


def make_data(temperatures):
    return pd.DataFrame({
        "date": pd.date_range("2020-01-01", periods=len(temperatures)),
        "temperature_max_c": temperatures,
    })


def test_interpolates_one_missing_day():
    data = make_data([30.0, np.nan, 34.0])

    cleaned, report = clean_daily_weather(data)

    assert cleaned["temperature_max_c"].tolist() == [30.0, 32.0, 34.0]
    assert cleaned["is_imputed"].tolist() == [False, True, False]
    assert report["imputed_days"] == 1
    assert report["source_completeness_percent"] < 100


def test_interpolates_two_consecutive_missing_days():
    data = make_data([30.0, np.nan, np.nan, 36.0])

    cleaned, report = clean_daily_weather(data)

    assert cleaned["temperature_max_c"].tolist() == [
        30.0, 32.0, 34.0, 36.0
    ]
    assert report["imputed_days"] == 2


def test_does_not_interpolate_long_gap():
    data = make_data([30.0, np.nan, np.nan, np.nan, 38.0])

    cleaned, report = clean_daily_weather(data)

    assert cleaned["temperature_max_c"].iloc[1:4].isna().all()
    assert report["imputed_days"] == 0
    assert report["remaining_missing_days"] == 3
    assert report["analysis_ready"] is False


def test_does_not_interpolate_edge_gaps():
    data = make_data([np.nan, 30.0, 32.0, np.nan])

    cleaned, report = clean_daily_weather(data)

    assert pd.isna(cleaned["temperature_max_c"].iloc[0])
    assert pd.isna(cleaned["temperature_max_c"].iloc[3])
    assert report["imputed_days"] == 0


def test_invalid_sentinel_becomes_missing():
    data = make_data([30.0, -999.0, 34.0])

    cleaned, report = clean_daily_weather(data)

    assert cleaned["temperature_max_c"].iloc[1] == 32.0
    assert cleaned["is_imputed"].iloc[1]
    assert report["sentinel_values"] == 1


def test_duplicate_dates_are_rejected():
    data = pd.DataFrame({
        "date": ["2020-01-01", "2020-01-01"],
        "temperature_max_c": [30.0, 31.0],
    })

    with pytest.raises(ValueError, match="Duplicate dates"):
        clean_daily_weather(data)
