from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.services.heatwave_analysis import analyze_heatwaves
from app.services.trends import (
    add_lowess_smoothing,
    aggregate_yearly_trends,
    build_trend_analysis,
)


app = FastAPI(
    title="Climate Hazard Trend Analyzer",
    description=(
        "Analyze historical heatwave episodes using "
        "location-specific climatological thresholds."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://climatescope-pi.vercel.app",
        "https://climatescope-8b91mpkni-vashi1.vercel.app",
    ],
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/v1/heatwaves")
def get_heatwaves(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    start_date: date = Query(...),
    end_date: date = Query(...),
):
    if start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail="start_date cannot be after end_date",
        )

    try:
        return analyze_heatwaves(
            latitude=latitude,
            longitude=longitude,
            start_date=start_date,
            end_date=end_date,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        # Log the full exception server-side in production.
        raise HTTPException(
            status_code=502,
            detail="Heatwave analysis failed. Please try again later.",
        ) from exc


@app.get("/api/v1/heatwaves/trends")
def get_heatwave_trends(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    start_year: int = Query(..., ge=1900, le=2100),
    end_year: int = Query(..., ge=1900, le=2100),
):
    """Return annual heatwave trends for a location and year range."""
    if start_year > end_year:
        raise HTTPException(
            status_code=422,
            detail="start_year cannot be after end_year",
        )

    try:
        analysis = analyze_heatwaves(
            latitude=latitude,
            longitude=longitude,
            start_date=date(start_year, 1, 1),
            end_date=date(end_year, 12, 31),
        )

        trends = aggregate_yearly_trends(
            events=analysis["events"],
            start_year=start_year,
            end_year=end_year,
        )

        trends = add_lowess_smoothing(
            trends,
            metric="total_heatwave_days",
            frac=0.3,
        )

        trend_analysis = build_trend_analysis(trends)

        return {
            "location": analysis["location"],
            "start_year": start_year,
            "end_year": end_year,
            "methodology": {
                "event_attribution": "event_start_year",
                "duration_attribution": "full_event_to_start_year",
                "overflow_field": "overflow_days_next_year",
            },
            "trends": trends,
            "trend_analysis": trend_analysis,
        }

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc
    except Exception:
        raise HTTPException(
            status_code=502,
            detail="Unable to calculate heatwave trends",
        ) from None
