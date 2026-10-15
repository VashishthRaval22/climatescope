
from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest
from pymongo.errors import PyMongoError

from app.services import baseline_cache as cache


@pytest.fixture
def cache_args():
    return {
        "latitude": 19.076,
        "longitude": 72.8777,
        "model": "era5_land",
        "baseline_start": date(1991, 1, 1),
        "baseline_end": date(2020, 12, 31),
    }


@pytest.fixture
def sample_baseline():
    return {
        "metadata": {
            "model": "era5_land",
            "valid_threshold_days": 366,
        },
        "thresholds": pd.DataFrame({
            "month_day": ["01-01", "01-02"],
            "p90_c": [30.0, 31.0],
            "p95_c": [35.0, 36.0],
            "status": ["valid", "valid"],
        }),
    }


@pytest.fixture
def sample_quality():
    return {
        "requested_days": 10958,
        "imputed_days": 0,
        "analysis_ready": True,
    }


def test_cache_hit_returns_baseline_and_quality(
    monkeypatch, cache_args, sample_baseline, sample_quality
):
    collection = MagicMock()
    collection.find_one.return_value = {
        "_id": "test-cache-key",
        "metadata": sample_baseline["metadata"],
        "thresholds": sample_baseline["thresholds"].to_dict(
            orient="records"
        ),
        "baseline_quality": sample_quality,
    }
    monkeypatch.setattr(
        cache,
        "get_database",
        lambda: {cache.COLLECTION_NAME: collection},
    )

    result = cache.get_cached_baseline(**cache_args)

    assert result is not None
    baseline, quality = result

    assert baseline["metadata"] == sample_baseline["metadata"]
    pd.testing.assert_frame_equal(
        baseline["thresholds"],
        sample_baseline["thresholds"],
    )
    assert quality == sample_quality
    collection.find_one.assert_called_once()


def test_cache_miss_returns_none(monkeypatch, cache_args):
    collection = MagicMock()
    collection.find_one.return_value = None
    monkeypatch.setattr(
        cache,
        "get_database",
        lambda: {cache.COLLECTION_NAME: collection},
    )

    result = cache.get_cached_baseline(**cache_args)

    assert result is None
    collection.find_one.assert_called_once()


def test_database_read_failure_returns_none(
    monkeypatch, cache_args
):
    collection = MagicMock()
    collection.find_one.side_effect = PyMongoError(
        "simulated database failure"
    )
    monkeypatch.setattr(
        cache,
        "get_database",
        lambda: {cache.COLLECTION_NAME: collection},
    )

    result = cache.get_cached_baseline(**cache_args)

    assert result is None


@pytest.mark.parametrize(
    "document",
    [
        {},
        {"metadata": {}, "thresholds": []},
        {
            "metadata": {},
            "thresholds": "invalid",
            "baseline_quality": {},
        },
    ],
)
def test_malformed_cache_record_returns_none(
    monkeypatch, cache_args, document
):
    collection = MagicMock()
    collection.find_one.return_value = document
    monkeypatch.setattr(
        cache,
        "get_database",
        lambda: {cache.COLLECTION_NAME: collection},
    )

    result = cache.get_cached_baseline(**cache_args)

    assert result is None


def test_save_baseline_writes_document(
    monkeypatch, cache_args, sample_baseline, sample_quality
):
    collection = MagicMock()
    monkeypatch.setattr(
        cache,
        "get_database",
        lambda: {cache.COLLECTION_NAME: collection},
    )

    cache.save_cached_baseline(
        **cache_args,
        baseline=sample_baseline,
        baseline_quality=sample_quality,
    )

    collection.replace_one.assert_called_once()

    query, document = collection.replace_one.call_args.args

    assert query == {"_id": document["_id"]}
    assert document["metadata"] == sample_baseline["metadata"]
    assert document["baseline_quality"] == sample_quality
    assert document["thresholds"] == sample_baseline[
        "thresholds"
    ].to_dict(orient="records")

    assert collection.replace_one.call_args.kwargs["upsert"] is True


def test_save_converts_nan_values_to_none(
    monkeypatch, cache_args, sample_quality
):
    collection = MagicMock()
    monkeypatch.setattr(
        cache,
        "get_database",
        lambda: {cache.COLLECTION_NAME: collection},
    )

    baseline = {
        "metadata": {"model": "era5_land"},
        "thresholds": pd.DataFrame({
            "month_day": ["01-01"],
            "p90_c": [float("nan")],
            "p95_c": [35.0],
            "status": ["invalid"],
        }),
    }

    cache.save_cached_baseline(
        **cache_args,
        baseline=baseline,
        baseline_quality=sample_quality,
    )

    document = collection.replace_one.call_args.args[1]

    assert document["thresholds"][0]["p90_c"] is None


def test_database_write_failure_does_not_raise(
    monkeypatch, cache_args, sample_baseline, sample_quality
):
    collection = MagicMock()
    collection.replace_one.side_effect = PyMongoError(
        "simulated database failure"
    )
    monkeypatch.setattr(
        cache,
        "get_database",
        lambda: {cache.COLLECTION_NAME: collection},
    )

    # A cache write failure should not fail the climate analysis.
    cache.save_cached_baseline(
        **cache_args,
        baseline=sample_baseline,
        baseline_quality=sample_quality,
    )
