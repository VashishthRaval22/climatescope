from fastapi.testclient import TestClient

from app import main
from unittest.mock import patch
from datetime import date

client = TestClient(main.app)


def test_invalid_latitude_returns_422():
    response = client.get(
        "/api/v1/heatwaves",
        params={
            "latitude": 91,
            "longitude": 72.8777,
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        },
    )

    assert response.status_code == 422


def test_invalid_longitude_returns_422():
    response = client.get(
        "/api/v1/heatwaves",
        params={
            "latitude": 19.076,
            "longitude": 181,
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        },
    )

    assert response.status_code == 422


def test_reversed_dates_return_422():
    response = client.get(
        "/api/v1/heatwaves",
        params={
            "latitude": 19.076,
            "longitude": 72.8777,
            "start_date": "2024-01-31",
            "end_date": "2024-01-01",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "start_date cannot be after end_date"
    )


def test_analysis_failure_returns_generic_502(monkeypatch):
    def raise_internal_error(**kwargs):
        raise RuntimeError(
            "SECRET_INTERNAL_DETAIL database password or stack trace"
        )

    monkeypatch.setattr(
        main,
        "analyze_heatwaves",
        raise_internal_error,
    )

    response = client.get(
        "/api/v1/heatwaves",
        params={
            "latitude": 19.076,
            "longitude": 72.8777,
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
        },
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": (
            "Heatwave analysis failed. Please try again later."
        )
    }
    assert "SECRET_INTERNAL_DETAIL" not in response.text
    assert "database password" not in response.text

@patch("app.main.aggregate_yearly_trends")
@patch("app.main.analyze_heatwaves")
def test_heatwave_trends_endpoint_returns_annual_data(
    mock_analyze,
    mock_trends,
):
    mock_analyze.return_value = {
        "location": {"latitude": 19.076, "longitude": 72.8777},
        "events": [],
    }
    mock_trends.return_value = [
        {
            "year": 2023,
            "heatwave_events": 0,
            "extreme_heatwave_events": 0,
            "total_heatwave_days": 0,
            "longest_heatwave_days": 0,
            "overflow_days_next_year": 0,
            "peak_temperature_c": None,
        }
    ]

    response = client.get(
        "/api/v1/heatwaves/trends",
        params={
            "latitude": 19.076,
            "longitude": 72.8777,
            "start_year": 2023,
            "end_year": 2023,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["trends"][0]["year"] == 2023
    assert body["methodology"]["event_attribution"] == "event_start_year"
    
    mock_analyze.assert_called_once_with(
        latitude=19.076,
        longitude=72.8777,
        start_date=date(2023, 1, 1),
        end_date=date(2023, 12, 31),
    )
    mock_trends.assert_called_once_with(
        events=[],
        start_year=2023,
        end_year=2023,
    )

def test_reversed_trend_years_return_422():
    response = client.get(
        "/api/v1/heatwaves/trends",
        params={
            "latitude": 19.076,
            "longitude": 72.8777,
            "start_year": 2025,
            "end_year": 2024,
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "start_year cannot be after end_year"
    )
