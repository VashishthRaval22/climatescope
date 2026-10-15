
import logging
from datetime import date

import pandas as pd
from pymongo.errors import PyMongoError

from app.database import get_database

logger = logging.getLogger(__name__)

COLLECTION_NAME = "heatwave_baselines"
METHOD_VERSION = "1.0"
WINDOW_DAYS = 5
MIN_OBSERVATIONS = 100
PERCENTILES = [90, 95]


def _make_cache_key(
    latitude: float,
    longitude: float,
    model: str,
    baseline_start: date,
    baseline_end: date,
) -> str:
    """Create a stable key for a specific baseline configuration."""
    parts = [
        f"lat={latitude:.5f}",
        f"lon={longitude:.5f}",
        f"model={model}",
        f"start={baseline_start.isoformat()}",
        f"end={baseline_end.isoformat()}",
        f"window={WINDOW_DAYS}",
        f"min_obs={MIN_OBSERVATIONS}",
        f"percentiles={','.join(map(str, PERCENTILES))}",
        f"method={METHOD_VERSION}",
    ]
    return "|".join(parts)


def get_cached_baseline(
    latitude: float,
    longitude: float,
    model: str,
    baseline_start: date,
    baseline_end: date,
) -> tuple[dict, dict] | None:
    """Return the cached baseline and quality report, if available."""
    cache_key = _make_cache_key(
        latitude,
        longitude,
        model,
        baseline_start,
        baseline_end,
    )

    try:
        baseline_collection = get_database()[COLLECTION_NAME]
        document = baseline_collection.find_one(
            {"_id": cache_key}
        )

        if document is None:
            print("[BASELINE CACHE] MISS")
            return None
        
        print("[BASELINE CACHE] HIT")
    except PyMongoError:
        logger.warning(
            "MongoDB baseline cache read failed; recalculating baseline",
            exc_info=True,
        )
        return None

    if document is None:
        return None

    try:
        thresholds = pd.DataFrame(document["thresholds"])
        metadata = document["metadata"]
        quality = document["baseline_quality"]

        baseline = {
            "metadata": metadata,
            "thresholds": thresholds,
        }
        return baseline, quality

    except (KeyError, TypeError, ValueError):
        logger.warning(
            "Invalid cached baseline; recalculating baseline"
        )
        return None


def save_cached_baseline(
    latitude: float,
    longitude: float,
    model: str,
    baseline_start: date,
    baseline_end: date,
    baseline: dict,
    baseline_quality: dict,
) -> None:
    """Persist calculated thresholds and quality metadata."""
    cache_key = _make_cache_key(
        latitude,
        longitude,
        model,
        baseline_start,
        baseline_end,
    )

    thresholds = baseline["thresholds"].copy()

    # MongoDB BSON does not support pandas NaN values reliably.
    thresholds = thresholds.astype(object).where(
        pd.notna(thresholds),
        None,
    )

    document = {
        "_id": cache_key,
        "metadata": baseline["metadata"],
        "thresholds": thresholds.to_dict(orient="records"),
        "baseline_quality": baseline_quality,
    }

    try:
        baseline_collection = get_database()[COLLECTION_NAME]
        baseline_collection.replace_one(
            {"_id": cache_key},
            document,
            upsert=True,
        )
    except PyMongoError:
        # Caching is an optimization; a write failure should not
        # make an otherwise successful analysis fail.
        logger.warning(
            "Could not save baseline to MongoDB cache",
            exc_info=True,
        )
