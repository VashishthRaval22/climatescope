import numpy as np
from datetime import date

from app.services.weather import fetch_daily_weather
from app.services.data_quality import clean_daily_weather
from app.services.baseline import calculate_heatwave_baseline


def main():
    # Step 1: Fetch the 1991–2020 historical baseline data.
    raw_df = fetch_daily_weather(
        latitude=19.076,
        longitude=72.8777,
        start_date=date(1991, 1, 1),
        end_date=date(2020, 12, 31),
        model="era5_land",
    )

    # Step 2: Validate data and interpolate eligible short gaps.
    cleaned_df, quality_report = clean_daily_weather(raw_df)

    print("DATA QUALITY REPORT")
    print(quality_report)

    # Step 3: Calculate the fixed P90/P95 climatological thresholds.
    baseline = calculate_heatwave_baseline(
        cleaned_df,
        latitude=19.076,
        longitude=72.8777,
        model="era5_land",
    )

    # Step 4: Validate the calculated baseline.
    thresholds = baseline["thresholds"]

    valid = thresholds[thresholds["status"] == "valid"]

    assert len(thresholds) == 366
    assert (valid["p95_c"] >= valid["p90_c"]).all()

    feb28 = thresholds.loc[
        thresholds["month_day"] == "02-28"
    ].iloc[0]

    mar01 = thresholds.loc[
        thresholds["month_day"] == "03-01"
    ].iloc[0]

    feb29 = thresholds.loc[
        thresholds["month_day"] == "02-29"
    ].iloc[0]

    assert np.isclose(
        feb29["p90_c"],
        (feb28["p90_c"] + mar01["p90_c"]) / 2,
    )

    assert np.isclose(
        feb29["p95_c"],
        (feb28["p95_c"] + mar01["p95_c"]) / 2,
    )

    print("\nBaseline validation passed.")

    print("\nBASELINE METADATA")
    print(baseline["metadata"])

    print("\nFIRST FIVE THRESHOLDS")
    print(baseline["thresholds"].head())

    print("\nFEBRUARY 29 THRESHOLD")
    print(
        baseline["thresholds"].query("month_day == '02-29'")
    )

    print("\nTHRESHOLD STATUS COUNTS")
    print(baseline["thresholds"]["status"].value_counts())


if __name__ == "__main__":
    main()