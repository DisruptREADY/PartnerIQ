"""FRED fetcher — Federal Reserve Economic Data (St. Louis Fed).

Supports MSA-level GDP and House Price Index, state-level GDP and HPI,
and county-level building permits (Census-sourced).
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

from ..config import FRED_API_KEY, INDICATORS
from ..utils import request_with_retry, STATE_ABBR_TO_FIPS

log = logging.getLogger("data_portal")

FRED_API_URL = "https://api.stlouisfed.org/fred/series/observations"
MAX_FRED_WORKERS = 8  # FRED allows 120 req/min; 8 concurrent is safe

# Reverse mapping: FIPS → state abbreviation
FIPS_TO_STATE_ABBR = {v: k for k, v in STATE_ABBR_TO_FIPS.items()}


def _build_series_id(meta: Dict[str, Any], geo_id: str, geo_type: str) -> str | None:
    """Build a FRED series ID from indicator metadata and geography."""
    patterns = meta.get("fred_series", {})
    pattern = patterns.get(geo_type)
    if not pattern:
        return None

    if geo_type == "msa":
        return pattern.format(cbsa=geo_id)
    elif geo_type == "state":
        abbr = FIPS_TO_STATE_ABBR.get(geo_id)
        if not abbr:
            return None
        return pattern.format(state_abbr=abbr)
    elif geo_type == "county":
        # County FIPS: our 5-digit (e.g. "22033"), FRED needs 6-digit zero-padded ("022033")
        fips6 = geo_id.zfill(6)
        return pattern.format(state_fips=geo_id[:2], county_fips=geo_id[2:], fips=geo_id, fips6=fips6)
    return None


def _fetch_one_fred_series(
    series_id: str,
    ind_key: str,
    geo_id: str,
    meta: dict,
    years: List[int],
    api_key: str,
    obs_start: str,
    obs_end: str,
    geo_type: str,
) -> List[Dict[str, Any]]:
    """Fetch one FRED series. Thread-safe."""
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "frequency": "a",  # annual — FRED auto-aggregates sub-annual series (e.g. quarterly HPI)
        "observation_start": obs_start,
        "observation_end": obs_end,
    }

    try:
        resp = requests.get(FRED_API_URL, params=params, timeout=30)
        data = resp.json()
    except requests.RequestException as e:
        log.warning("FRED %s request failed: %s", series_id, e)
        return []
    except (ValueError, KeyError) as e:
        log.warning("FRED %s bad response: %s", series_id, e)
        return []

    if "error_message" in data:
        log.warning("FRED %s: %s", series_id, data["error_message"])
        return []

    records: List[Dict[str, Any]] = []
    for obs in data.get("observations", []):
        val_str = obs.get("value", "").strip()
        if val_str == "." or val_str == "":
            continue
        try:
            value = float(val_str)
        except ValueError:
            continue

        # FRED dates are "YYYY-01-01" for annual
        try:
            yr = int(obs["date"][:4])
        except (ValueError, KeyError):
            continue

        if yr not in years:
            continue

        # Apply per-geo-type divisor (e.g., county GDP thousands → millions)
        divisor = meta.get("fred_divisor", {}).get(geo_type)
        if divisor:
            value = value / divisor

        records.append({
            "CBSA": geo_id,
            "Year": yr,
            ind_key: value,
        })

    return records


def _fetch_fred_sync(
    geos: Dict[str, str],
    indicator_keys: List[str],
    years: List[int],
    api_key: str,
    geo_type: str = "msa",
) -> pd.DataFrame:
    """Fetch FRED series observations for given geos/indicators/years."""
    fred_keys = {
        k: INDICATORS[k]
        for k in indicator_keys
        if INDICATORS.get(k, {}).get("source") == "fred"
    }
    if not fred_keys:
        return pd.DataFrame(columns=["CBSA", "Year"])

    if not api_key:
        log.warning("FRED_API_KEY not set — skipping FRED fetch")
        return pd.DataFrame(columns=["CBSA", "Year"])

    min_year = min(years)
    max_year = max(years)
    obs_start = f"{min_year}-01-01"
    obs_end = f"{max_year}-12-31"

    # Build all (series_id, ind_key, geo_id) tasks upfront
    tasks = []
    for ind_key, meta in fred_keys.items():
        for geo_id in geos:
            series_id = _build_series_id(meta, geo_id, geo_type)
            if series_id:
                tasks.append((series_id, ind_key, geo_id, meta))

    if not tasks:
        return pd.DataFrame(columns=["CBSA", "Year"])

    # Run all API calls concurrently
    all_records: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(MAX_FRED_WORKERS, len(tasks))) as pool:
        futures = {
            pool.submit(
                _fetch_one_fred_series,
                series_id, ind_key, geo_id, meta, years, api_key,
                obs_start, obs_end, geo_type,
            ): series_id
            for series_id, ind_key, geo_id, meta in tasks
        }
        for future in as_completed(futures):
            all_records.extend(future.result())

    if not all_records:
        return pd.DataFrame(columns=["CBSA", "Year"])

    df = pd.DataFrame(all_records)
    df["CBSA"] = df["CBSA"].astype(str)
    indicator_cols = [c for c in df.columns if c not in ("CBSA", "Year")]
    df = df.groupby(["CBSA", "Year"], as_index=False)[indicator_cols].first()
    return df


async def fetch_fred(
    geos: Dict[str, str],
    indicator_keys: List[str],
    years: List[int],
    geo_type: str = "msa",
) -> pd.DataFrame:
    """Async wrapper around sync FRED fetch."""
    return await asyncio.to_thread(
        _fetch_fred_sync, geos, indicator_keys, years, FRED_API_KEY, geo_type
    )
