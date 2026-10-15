import json
import time

from app.services.heatwave_analysis import analyze_heatwaves


def main():
    started = time.perf_counter()

    result = analyze_heatwaves(
        latitude=19.076,
        longitude=72.8777,
        start_date="2024-01-01",
        end_date="2024-01-31",
        model="era5_land",
    )

    # Verify the complete response can be serialized for a JSON API.
    serialized = json.dumps(result, allow_nan=False)
    parsed = json.loads(serialized)

    print("\nEND-TO-END ANALYSIS PASSED")
    print(f"Execution time: {time.perf_counter() - started:.2f}s")

    print("\nSUMMARY")
    print(json.dumps(parsed["summary"], indent=2))

    print("\nDATA QUALITY")
    print(json.dumps(parsed["data_quality"], indent=2))

    print("\nBASELINE")
    print(json.dumps(parsed["baseline"], indent=2))

    print("\nHEATWAVE EVENTS")
    print(json.dumps(parsed["events"], indent=2))

    print("\nJSON serialization: passed")


if __name__ == "__main__":
    main()
