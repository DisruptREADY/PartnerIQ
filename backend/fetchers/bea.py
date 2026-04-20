"""BEA fetcher — supports MSA, state, county, and micro geographies."""
import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

import pandas as pd
import requests

from ..config import BEA_API_KEY, INDICATORS
from ..utils import request_with_retry

MAX_BEA_WORKERS = 4  # BEA rate limits are stricter; keep concurrency moderate

log = logging.getLogger("data_portal")

BEA_API_URL = "https://apps.bea.gov/api/data/"

# GeoFips parameter per geo_type
BEA_GEO_FIPS = {
    "msa": "MSA",
    "state": "STATE",
    "county": "COUNTY",
}


def _parse_bea_value(raw_val) -> float | None:
    """Parse a BEA DataValue into a float, or None if invalid."""
    if isinstance(raw_val, str):
        raw_val = raw_val.replace(",", "").strip()
        if raw_val.startswith("(") or raw_val == "" or raw_val == "...":
            return None
    try:
        return float(raw_val)
    except (ValueError, TypeError):
        return None


def _fetch_bea_sync(
    geos: Dict[str, str],
    indicator_keys: List[str],
    years: List[int],
    api_key: str,
    geo_type: str = "msa",
) -> pd.DataFrame:
    """Fetch BEA Regional data for given geos/indicators/years."""
    bea_keys = {
        k: INDICATORS[k]
        for k in indicator_keys
        if INDICATORS.get(k, {}).get("source") == "bea"
    }
    if not bea_keys:
        return pd.DataFrame(columns=["CBSA", "Year"])

    if not api_key:
        log.warning("BEA_API_KEY not set — skipping BEA fetch")
        return pd.DataFrame(columns=["CBSA", "Year"])

    # For MSAs/micros, split indicators: some need county aggregation (e.g., GDP),
    # others can be fetched directly (e.g., RPP).
    if geo_type in ("msa", "micro"):
        agg_keys = {k: v for k, v in bea_keys.items() if v.get("county_agg")}
        direct_keys = {k: v for k, v in bea_keys.items() if not v.get("county_agg")}

        frames = []
        if agg_keys:
            agg_df = _fetch_bea_county_agg_sync(geos, agg_keys, years, api_key)
            if not agg_df.empty:
                frames.append(agg_df)
        if direct_keys and geo_type == "msa":
            direct_df = _fetch_bea_direct_sync(geos, direct_keys, years, api_key, geo_type)
            if not direct_df.empty:
                frames.append(direct_df)

        if not frames:
            return pd.DataFrame(columns=["CBSA", "Year"])
        if len(frames) == 1:
            return frames[0]
        merged = frames[0]
        for other in frames[1:]:
            merged = merged.merge(other, on=["CBSA", "Year"], how="outer")
        return merged

    return _fetch_bea_direct_sync(geos, bea_keys, years, api_key, geo_type)


def _fetch_bea_direct_sync(
    geos: Dict[str, str],
    bea_keys: Dict[str, dict],
    years: List[int],
    api_key: str,
    geo_type: str,
) -> pd.DataFrame:
    """Fetch BEA Regional data directly using the GeoFips level parameter."""
    geo_fips_param = BEA_GEO_FIPS.get(geo_type, "MSA")
    all_records: List[Dict[str, Any]] = []
    year_str = ",".join(str(y) for y in years)

    # BEA uses 5-digit FIPS for states (e.g., "22000") and counties ("01001"),
    # while our app uses 2-digit state FIPS ("22") and 5-digit county FIPS.
    if geo_type == "state":
        bea_to_internal = {f"{fips}000": fips for fips in geos}
    else:
        bea_to_internal = {fips: fips for fips in geos}

    def _fetch_one_direct(ind_key, meta):
        """Fetch one BEA indicator directly. Thread-safe."""
        table_cfg = meta["table"]
        if isinstance(table_cfg, dict):
            table = table_cfg.get(geo_type)
            if not table:
                log.warning("BEA %s: no table for geo_type=%s", ind_key, geo_type)
                return []
        else:
            table = table_cfg
        line_code = meta["line"]

        params: Dict[str, str] = {
            "UserID": api_key,
            "method": "GetData",
            "datasetname": "Regional",
            "TableName": table,
            "LineCode": str(line_code),
            "GeoFips": geo_fips_param,
            "Year": year_str,
            "ResultFormat": "JSON",
        }

        try:
            resp = request_with_retry("GET", BEA_API_URL, params=params)
            resp_json = resp.json()
        except requests.RequestException as e:
            log.warning("BEA %s (%s) request failed: %s", table, geo_type, e)
            return []
        except (ValueError, KeyError) as e:
            log.warning("BEA %s (%s) bad response: %s", table, geo_type, e)
            return []

        beaapi = resp_json.get("BEAAPI", {})
        results = beaapi.get("Results", {})
        data_rows = results.get("Data", [])

        if not data_rows:
            log.warning("BEA %s (%s) returned no data rows.", table, geo_type)
            return []

        records = []
        for row in data_rows:
            geo_fips = row.get("GeoFips", "").strip()
            internal_id = bea_to_internal.get(geo_fips)
            if not internal_id:
                continue

            try:
                yr = int(row.get("TimePeriod", "0"))
            except ValueError:
                continue
            if yr not in years:
                continue

            value = _parse_bea_value(row.get("DataValue", ""))
            if value is None:
                continue

            divisor_cfg = meta.get("divisor", {})
            if isinstance(divisor_cfg, dict):
                divisor = divisor_cfg.get(geo_type, 1)
            else:
                divisor = divisor_cfg or 1
            if divisor != 1:
                value = value / divisor

            records.append({
                "CBSA": internal_id,
                "Year": yr,
                ind_key: value,
            })
        return records

    items = list(bea_keys.items())
    with ThreadPoolExecutor(max_workers=min(MAX_BEA_WORKERS, len(items))) as pool:
        futures = {pool.submit(_fetch_one_direct, k, m): k for k, m in items}
        for future in as_completed(futures):
            all_records.extend(future.result())

    if not all_records:
        return pd.DataFrame(columns=["CBSA", "Year"])

    df = pd.DataFrame(all_records)
    df["CBSA"] = df["CBSA"].astype(str)
    indicator_cols = [c for c in df.columns if c not in ("CBSA", "Year")]
    df = df.groupby(["CBSA", "Year"], as_index=False)[indicator_cols].first()
    return df


def _fetch_bea_county_agg_sync(
    geos: Dict[str, str],
    bea_keys: Dict[str, dict],
    years: List[int],
    api_key: str,
) -> pd.DataFrame:
    """Fetch BEA data for MSAs/micros by aggregating county-level data.

    BEA dropped direct MSA-level GDP from the Regional API. This function
    looks up which counties belong to each selected CBSA (metro or micro),
    fetches county-level data, and sums to the CBSA level.
    """
    from ..routers.geography import get_cbsa_county_map

    cbsa_county_map = get_cbsa_county_map()
    if not cbsa_county_map:
        log.warning("BEA county aggregation: could not load CBSA → county mapping")
        return pd.DataFrame(columns=["CBSA", "Year"])

    # Collect all county FIPS needed for the selected CBSAs
    cbsa_to_counties: Dict[str, List[str]] = {}
    all_county_fips: set = set()
    for cbsa_id in geos:
        counties = cbsa_county_map.get(cbsa_id, [])
        if counties:
            cbsa_to_counties[cbsa_id] = counties
            all_county_fips.update(counties)
        else:
            log.warning("BEA county aggregation: no counties found for CBSA %s", cbsa_id)

    if not all_county_fips:
        return pd.DataFrame(columns=["CBSA", "Year"])

    # Build reverse mapping: county_fips → cbsa_id
    county_to_cbsa: Dict[str, str] = {}
    for cbsa_id, counties in cbsa_to_counties.items():
        for cfips in counties:
            county_to_cbsa[cfips] = cbsa_id

    all_records: List[Dict[str, Any]] = []
    year_str = ",".join(str(y) for y in years)

    def _fetch_one_county_agg(ind_key, meta):
        """Fetch one BEA indicator via county aggregation. Thread-safe."""
        table_cfg = meta["table"]
        if isinstance(table_cfg, dict):
            table = table_cfg.get("county")
            if not table:
                log.warning("BEA %s: no county table for CBSA aggregation", ind_key)
                return []
        else:
            table = table_cfg
        line_code = meta["line"]

        params: Dict[str, str] = {
            "UserID": api_key,
            "method": "GetData",
            "datasetname": "Regional",
            "TableName": table,
            "LineCode": str(line_code),
            "GeoFips": "COUNTY",
            "Year": year_str,
            "ResultFormat": "JSON",
        }

        try:
            resp = request_with_retry("GET", BEA_API_URL, params=params)
            resp_json = resp.json()
        except requests.RequestException as e:
            log.warning("BEA %s (county aggregation) request failed: %s", table, e)
            return []
        except (ValueError, KeyError) as e:
            log.warning("BEA %s (county aggregation) bad response: %s", table, e)
            return []

        beaapi = resp_json.get("BEAAPI", {})
        results = beaapi.get("Results", {})
        data_rows = results.get("Data", [])

        if not data_rows:
            log.warning("BEA %s (county aggregation) returned no data rows.", table)
            return []

        cbsa_sums: Dict[tuple, float] = {}
        for row in data_rows:
            county_fips = row.get("GeoFips", "").strip()
            cbsa_id = county_to_cbsa.get(county_fips)
            if not cbsa_id:
                continue

            try:
                yr = int(row.get("TimePeriod", "0"))
            except ValueError:
                continue
            if yr not in years:
                continue

            value = _parse_bea_value(row.get("DataValue", ""))
            if value is None:
                continue

            divisor_cfg = meta.get("divisor", {})
            if isinstance(divisor_cfg, dict):
                divisor = divisor_cfg.get("county", 1)
            else:
                divisor = divisor_cfg or 1
            if divisor != 1:
                value = value / divisor

            key = (cbsa_id, yr)
            cbsa_sums[key] = cbsa_sums.get(key, 0.0) + value

        records = []
        for (cbsa_id, yr), total in cbsa_sums.items():
            records.append({
                "CBSA": cbsa_id,
                "Year": yr,
                ind_key: total,
            })
        return records

    items = list(bea_keys.items())
    with ThreadPoolExecutor(max_workers=min(MAX_BEA_WORKERS, len(items))) as pool:
        futures = {pool.submit(_fetch_one_county_agg, k, m): k for k, m in items}
        for future in as_completed(futures):
            all_records.extend(future.result())

    if not all_records:
        return pd.DataFrame(columns=["CBSA", "Year"])

    df = pd.DataFrame(all_records)
    df["CBSA"] = df["CBSA"].astype(str)
    indicator_cols = [c for c in df.columns if c not in ("CBSA", "Year")]
    df = df.groupby(["CBSA", "Year"], as_index=False)[indicator_cols].first()
    return df


async def fetch_bea(
    geos: Dict[str, str],
    indicator_keys: List[str],
    years: List[int],
    geo_type: str = "msa",
) -> pd.DataFrame:
    """Async wrapper around sync BEA fetch."""
    return await asyncio.to_thread(
        _fetch_bea_sync, geos, indicator_keys, years, BEA_API_KEY, geo_type
    )
