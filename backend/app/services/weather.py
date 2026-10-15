
from datetime import date

import httpx
import numpy as np
import pandas as pd


OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

SUPPORTED_MODELS = {"era5", "era5_land"}


def fetch_daily_weather(
    latitude: float,
    longitude: float,
    start_date: date,
    end_date: date,
    model: str = "era5_land",
) -> pd.DataFrame:
    """
    Fetch historical daily maximum temperature from Open-Meteo.

    Returns:
        date: calendar date
        temperature_max_c: daily maximum temperature in Celsius

    Missing calendar dates and missing/non-finite temperatures are
    preserved for the downstream data-quality layer.
    """
    if not np.isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90")

    if not np.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180")

    if (
        not isinstance(start_date, date)
        or isinstance(start_date, pd.Timestamp)
        or not isinstance(end_date, date)
        or isinstance(end_date, pd.Timestamp)
    ):
        raise TypeError("start_date and end_date must be datetime.date values")

    if start_date > end_date:
        raise ValueError("start_date cannot be after end_date")

    if model not in SUPPORTED_MODELS:
        raise ValueError(
            f"Unsupported model '{model}'. "
            f"Choose one of: {sorted(SUPPORTED_MODELS)}"
        )

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "daily": "temperature_2m_max",
        "timezone": "UTC",
        "temperature_unit": "celsius",
        "models": model,
    }

    try:
        response = httpx.get(
            OPEN_METEO_ARCHIVE_URL,
            params=params,
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()

    except httpx.TimeoutException as exc:
        raise RuntimeError("Open-Meteo request timed out") from exc

    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Open-Meteo returned HTTP {exc.response.status_code}"
        ) from exc

    except httpx.RequestError as exc:
        raise RuntimeError("Could not connect to Open-Meteo") from exc

    except ValueError as exc:
        raise RuntimeError("Open-Meteo returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Open-Meteo returned an invalid response structure")

    if payload.get("error"):
        reason = payload.get("reason", "Unknown API error")
        raise RuntimeError(f"Open-Meteo API error: {reason}")

    daily = payload.get("daily")
    daily_units = payload.get("daily_units")

    if not isinstance(daily, dict):
        raise RuntimeError("Open-Meteo response has no daily data")

    if not isinstance(daily_units, dict):
        raise RuntimeError("Open-Meteo response has no daily unit metadata")

    if daily_units.get("temperature_2m_max") != "°C":
        raise RuntimeError(
            "Unexpected temperature unit; expected Celsius (°C)"
        )

    dates = daily.get("time")
    temperatures = daily.get("temperature_2m_max")

    if not isinstance(dates, list) or not isinstance(temperatures, list):
        raise RuntimeError("Open-Meteo response is missing required fields")

    if len(dates) != len(temperatures):
        raise RuntimeError("Weather response arrays have different lengths")

    try:
        parsed_dates = pd.to_datetime(dates, errors="raise")

        numeric_temperatures = pd.to_numeric(
            pd.Series(temperatures),
            errors="coerce",
        )

        data = pd.DataFrame({
            "date": parsed_dates,
            "temperature_max_c": numeric_temperatures.to_numpy(),
        })

    except (ValueError, TypeError, OverflowError) as exc:
        raise RuntimeError("Weather response contains invalid data") from exc

    if data["date"].isna().any():
        raise RuntimeError("Weather response contains invalid dates")

    if data["date"].dt.tz is not None:
        raise RuntimeError("Expected timezone-naive daily calendar dates")

    if not data["date"].eq(data["date"].dt.normalize()).all():
        raise RuntimeError("Response contains timestamps instead of daily dates")

    if data["date"].duplicated().any():
        raise RuntimeError("Weather response contains duplicate dates")

    # Do not silently accept observations outside the requested range.
    if (
        (data["date"] < pd.Timestamp(start_date)).any()
        or (data["date"] > pd.Timestamp(end_date)).any()
    ):
        raise RuntimeError(
            "Open-Meteo returned dates outside the requested range"
        )

    data = data.sort_values("date").set_index("date")

    # Insert missing calendar dates without filling their temperatures.
    expected_dates = pd.date_range(
        start=start_date,
        end=end_date,
        freq="D",
        name="date",
    )

    data = data.reindex(expected_dates)

    values = data["temperature_max_c"].to_numpy(dtype=float)
    data.loc[~np.isfinite(values), "temperature_max_c"] = np.nan

    return data.rename_axis("date").reset_index()
