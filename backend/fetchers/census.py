"""Census ACS fetcher — supports multi-variable indicators and variable batching."""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

from ..config import CENSUS_API_KEY, INDICATORS
from ..utils import request_with_retry

log = logging.getLogger("data_portal")

MAX_VARS_PER_CALL = 45  # Census API allows ~50 variables per call; leave margin
MAX_CENSUS_WORKERS = 6  # Concurrent Census API calls (respectful to rate limits)
TARGETED_GEO_THRESHOLD = 10  # Use specific FIPS codes instead of wildcards below this


def _build_census_geo_params(
    geo_type: str, geos: Dict[str, str],
) -> List[Dict[str, str]]:
    """Build Census API geography parameters.

    For small requests (≤ TARGETED_GEO_THRESHOLD geos), generates targeted
    queries using specific FIPS codes.  For large requests, uses wildcards
    and filters in Python.  Returns a list of param dicts — usually one,
    but county/place may split across state groups.
    """
    if len(geos) > TARGETED_GEO_THRESHOLD:
        # Wildcard: fetch all, filter in Python
        if geo_type in ("msa", "micro"):
            return [{"for": "metropolitan statistical area/micropolitan statistical area:*"}]
        elif geo_type == "state":
            return [{"for": "state:*"}]
        elif geo_type == "county":
            return [{"for": "county:*"}]
        elif geo_type == "place":
            return [{"for": "place:*"}]

    # Targeted queries with specific FIPS codes
    if geo_type in ("msa", "micro"):
        ids = ",".join(sorted(geos.keys()))
        return [{"for": f"metropolitan statistical area/micropolitan statistical area:{ids}"}]

    if geo_type == "state":
        ids = ",".join(sorted(geos.keys()))
        return [{"for": f"state:{ids}"}]

    if geo_type == "county":
        # Group counties by state FIPS (first 2 digits)
        by_state: Dict[str, List[str]] = {}
        for fips in geos:
            by_state.setdefault(fips[:2], []).append(fips[2:])
        return [
            {"for": f"county:{','.join(cos)}", "in": f"state:{st}"}
            for st, cos in sorted(by_state.items())
        ]

    if geo_type == "place":
        # Group places by state FIPS (first 2 digits)
        by_state: Dict[str, List[str]] = {}
        for fips in geos:
            by_state.setdefault(fips[:2], []).append(fips[2:])
        return [
            {"for": f"place:{','.join(pls)}", "in": f"state:{st}"}
            for st, pls in sorted(by_state.items())
        ]

    return [{"for": "state:*"}]  # fallback


def _census_variables_for_indicators(
    indicator_keys: List[str],
) -> Dict[str, List[str]]:
    """Collect all Census variables needed, grouped by dataset.

    Returns {dataset: [var_code, ...]}.  Variables are deduplicated.
    """
    by_ds: Dict[str, set] = {}
    for key in indicator_keys:
        meta = INDICATORS.get(key)
        if not meta or meta["source"] != "census":
            continue
        ds = meta["dataset"]
        by_ds.setdefault(ds, set())
        for var in meta["variables"]:
            by_ds[ds].add(var)
    return {ds: sorted(vars) for ds, vars in by_ds.items()}


def _fetch_one_census_call(
    ds: str,
    year: int,
    var_batch: List[str],
    geo_params: Dict[str, str],
    geo_type: str,
    geos: Dict[str, str],
    api_key: Optional[str],
) -> List[Dict[str, Any]]:
    """Fetch one (dataset, year, variable-batch) from Census API. Thread-safe."""
    url = f"https://api.census.gov/data/{year}/acs/{ds}"
    params: Dict[str, str] = {"get": ",".join(["NAME"] + var_batch)}
    params.update(geo_params)  # "for" and optionally "in"
    if api_key:
        params["key"] = api_key

    try:
        resp = request_with_retry("GET", url, params=params)
        data = resp.json()
    except requests.RequestException as e:
        log.error("Census %s %d (%s) request failed: %s", ds, year, geo_type, e)
        return []
    except (ValueError, KeyError) as e:
        log.error("Census %s %d (%s) bad response: %s", ds, year, geo_type, e)
        return []

    if not isinstance(data, list) or len(data) < 2:
        log.warning("Census %s %d (%s): unexpected response shape", ds, year, geo_type)
        return []

    header, *rows = data
    records: List[Dict[str, Any]] = []

    for row in rows:
        # Extract geo ID
        if geo_type == "county":
            state_col = header.index("state")
            county_col = header.index("county")
            geo_id = row[state_col] + row[county_col]
        elif geo_type == "place":
            state_col = header.index("state")
            place_col = header.index("place")
            geo_id = row[state_col] + row[place_col]
        else:
            id_col_name = "metropolitan statistical area/micropolitan statistical area" if geo_type in ("msa", "micro") else "state"
            id_col = header.index(id_col_name)
            geo_id = row[id_col]

        if geos and geo_id not in geos:
            continue

        record: Dict[str, Any] = {"CBSA": geo_id, "Year": year}
        for var_code in var_batch:
            try:
                col_idx = header.index(var_code)
                raw = row[col_idx]
                val = float(raw) if raw is not None else None
                # Census API sentinel values: -666666666 (not available),
                # -999999999 (suppressed), -888888888 (not applicable), etc.
                if val is not None and val < -1_000_000:
                    val = None
                record[var_code] = val
            except (ValueError, TypeError, IndexError):
                record[var_code] = None
        records.append(record)

    return records


def _fetch_census_sync(
    geos: Dict[str, str],
    indicator_keys: List[str],
    years: List[int],
    api_key: Optional[str] = None,
    geo_type: str = "msa",
    acs_dataset: str = "acs1",
) -> pd.DataFrame:
    """Bulk-fetch Census ACS indicators with variable batching and multi-var sum.

    All (dataset, year, variable-batch) calls are parallelized via a thread pool
    since each Census ACS year is a separate API endpoint.
    """
    by_ds = _census_variables_for_indicators(indicator_keys)
    if not by_ds:
        return pd.DataFrame(columns=["CBSA", "Year"])

    geo_params_list = _build_census_geo_params(geo_type, geos)
    all_frames: List[Dict[str, Any]] = []

    # Build list of all (ds, year, var_batch, geo_params) tasks
    tasks: List[Tuple[str, int, List[str], Dict[str, str]]] = []
    for ds, all_vars in by_ds.items():
        # Swap acs1 → acs5 if user selected 5-year estimates
        if acs_dataset == "acs5":
            ds = ds.replace("acs1", "acs5")

        # Batch variables to stay under Census API limit
        var_batches = [
            all_vars[i:i + MAX_VARS_PER_CALL]
            for i in range(0, len(all_vars), MAX_VARS_PER_CALL)
        ]

        for var_batch in var_batches:
            for year in years:
                for geo_params in geo_params_list:
                    tasks.append((ds, year, var_batch, geo_params))

    # Run all API calls concurrently
    with ThreadPoolExecutor(max_workers=min(MAX_CENSUS_WORKERS, len(tasks))) as pool:
        futures = {
            pool.submit(
                _fetch_one_census_call,
                ds, year, var_batch, geo_params, geo_type, geos, api_key,
            ): (ds, year)
            for ds, year, var_batch, geo_params in tasks
        }
        for future in as_completed(futures):
            records = future.result()
            all_frames.extend(records)

    if not all_frames:
        return pd.DataFrame(columns=["CBSA", "Year"])

    df = pd.DataFrame(all_frames)
    df["CBSA"] = df["CBSA"].astype(str)

    # Merge rows from different variable batches (same CBSA+Year may appear multiple times)
    groupby_cols = ["CBSA", "Year"]
    var_cols = [c for c in df.columns if c not in groupby_cols]
    df = df.groupby(groupby_cols, as_index=False)[var_cols].first()

    # Build indicator columns from raw variable columns
    for key in indicator_keys:
        meta = INDICATORS.get(key)
        if not meta or meta["source"] != "census":
            continue
        vars_list = meta["variables"]
        present = [v for v in vars_list if v in df.columns]
        if not present:
            continue
        if len(present) == 1:
            df[key] = df[present[0]]
        else:
            # Sum multiple variables; min_count=1 means NaN only if ALL are NaN
            df[key] = df[present].sum(axis=1, min_count=1)

    # Drop raw variable columns (keep only indicator keys + CBSA/Year)
    all_raw_vars = set()
    for key in indicator_keys:
        meta = INDICATORS.get(key)
        if meta and meta["source"] == "census":
            all_raw_vars.update(meta["variables"])
    df = df.drop(columns=[v for v in all_raw_vars if v in df.columns], errors="ignore")

    return df


async def fetch_census(
    geos: Dict[str, str],
    indicator_keys: List[str],
    years: List[int],
    geo_type: str = "msa",
    acs_dataset: str = "acs1",
) -> pd.DataFrame:
    """Async wrapper around sync Census fetch."""
    return await asyncio.to_thread(
        _fetch_census_sync, geos, indicator_keys, years, CENSUS_API_KEY, geo_type, acs_dataset
    )
