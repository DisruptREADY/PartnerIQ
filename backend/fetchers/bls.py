"""BLS fetcher — supports MSA, state, and county geographies."""
import asyncio
import logging
import time
from typing import Any, Dict, List

import pandas as pd
import requests

from ..config import BLS_API_KEY, INDICATORS
from ..utils import request_with_retry

log = logging.getLogger("data_portal")

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# Series ID patterns per geo_type
# MSA: SMU{state2}{cbsa5}{suffix} for CES, LAUMT{state2}{cbsa5}{suffix} for LAU
# State: SMU{state2}000000000000001 for CES, LASST{state2}0000000000003 for LAU
# County: LAUCN{fips5}0000000{suffix} for LAU (no CES at county level)
BLS_SERIES_PATTERNS = {
    "msa": {
        "nonfarm_jobs": lambda state, geo_id: f"SMU{state}{geo_id}0000000001",
        "unemployment_rate": lambda state, geo_id: f"LAUMT{state}{geo_id}00000003",
        # CES supersector series — All Employees (datatype 01)
        "ind_mining_logging": lambda state, geo_id: f"SMU{state}{geo_id}1000000001",
        "ind_construction": lambda state, geo_id: f"SMU{state}{geo_id}2000000001",
        # Combined Mining, Logging & Construction — fallback when separate series unavailable
        "_ind_mining_construction_combined": lambda state, geo_id: f"SMU{state}{geo_id}1500000001",
        "ind_manufacturing": lambda state, geo_id: f"SMU{state}{geo_id}3000000001",
        "ind_trade_transport_util": lambda state, geo_id: f"SMU{state}{geo_id}4000000001",
        "ind_wholesale_trade": lambda state, geo_id: f"SMU{state}{geo_id}4100000001",
        "ind_retail_trade": lambda state, geo_id: f"SMU{state}{geo_id}4200000001",
        "ind_transport_warehouse_util": lambda state, geo_id: f"SMU{state}{geo_id}4300000001",
        "ind_information": lambda state, geo_id: f"SMU{state}{geo_id}5000000001",
        "ind_financial": lambda state, geo_id: f"SMU{state}{geo_id}5500000001",
        "ind_prof_business": lambda state, geo_id: f"SMU{state}{geo_id}6000000001",
        "ind_edu_health": lambda state, geo_id: f"SMU{state}{geo_id}6500000001",
        "ind_leisure_hospitality": lambda state, geo_id: f"SMU{state}{geo_id}7000000001",
        "ind_other_services": lambda state, geo_id: f"SMU{state}{geo_id}8000000001",
        "ind_government": lambda state, geo_id: f"SMU{state}{geo_id}9000000001",
    },
    "state": {
        "nonfarm_jobs": lambda state, geo_id: f"SMU{geo_id}000000000000001",
        "unemployment_rate": lambda state, geo_id: f"LASST{geo_id}0000000000003",
    },
    "county": {
        "unemployment_rate": lambda state, geo_id: f"LAUCN{geo_id}0000000000003",
    },
}


def _build_bls_series_ids(
    geos: Dict[str, str],
    cbsa_to_state: Dict[str, str],
    indicator_key: str,
    geo_type: str = "msa",
) -> Dict[str, str]:
    """Build BLS series IDs for all geos for a given indicator.

    Returns {series_id: geo_id}.
    """
    patterns = BLS_SERIES_PATTERNS.get(geo_type, {})
    builder = patterns.get(indicator_key)
    if not builder:
        return {}

    series_map: Dict[str, str] = {}
    for geo_id in geos:
        if geo_type == "msa":
            state_fips = cbsa_to_state.get(geo_id)
            if not state_fips:
                continue
            series_id = builder(state_fips, geo_id)
        elif geo_type == "state":
            series_id = builder(geo_id, geo_id)
        elif geo_type == "county":
            series_id = builder(None, geo_id)
        else:
            continue
        series_map[series_id] = geo_id
    return series_map


def _fetch_bls_sync(
    geos: Dict[str, str],
    cbsa_to_state: Dict[str, str],
    indicator_keys: List[str],
    years: List[int],
    api_key: str,
    geo_type: str = "msa",
) -> pd.DataFrame:
    """Fetch BLS data for given geos/indicators/years, batched 50 per POST.

    All series across all indicators are collected upfront and batched
    together, reducing total API calls and sleep time.
    """
    bls_keys = [k for k in indicator_keys if INDICATORS.get(k, {}).get("source") == "bls"]
    if not bls_keys:
        return pd.DataFrame(columns=["CBSA", "Year"])

    # If mining or construction requested, also fetch combined series as fallback
    need_combined_fallback = geo_type == "msa" and (
        "ind_mining_logging" in bls_keys or "ind_construction" in bls_keys
    )
    fetch_keys = list(bls_keys)
    if need_combined_fallback and "_ind_mining_construction_combined" not in fetch_keys:
        fetch_keys.append("_ind_mining_construction_combined")

    all_records: List[Dict[str, Any]] = []
    start_year = str(min(years))
    end_year = str(max(years))

    # Build ALL series IDs across all indicators upfront
    # Maps series_id → (geo_id, ind_key)
    combined_map: Dict[str, tuple] = {}
    for ind_key in fetch_keys:
        series_map = _build_bls_series_ids(geos, cbsa_to_state, ind_key, geo_type)
        if not series_map:
            log.info("BLS %s: no series available for geo_type=%s", ind_key, geo_type)
            continue
        for sid, geo_id in series_map.items():
            combined_map[sid] = (geo_id, ind_key)

    if not combined_map:
        return pd.DataFrame(columns=["CBSA", "Year"])

    series_ids = list(combined_map.keys())
    log.info("BLS (%s): %d total series across %d indicators", geo_type, len(series_ids), len(bls_keys))

    for batch_start in range(0, len(series_ids), 50):
        batch = series_ids[batch_start : batch_start + 50]
        payload = {
            "seriesid": batch,
            "startyear": start_year,
            "endyear": end_year,
            "registrationkey": api_key,
        }

        try:
            resp = request_with_retry("POST", BLS_API_URL, json=payload)
            resp_json = resp.json()
        except requests.RequestException as e:
            log.warning("BLS batch request failed: %s", e)
            continue
        except (ValueError, KeyError) as e:
            log.warning("BLS batch bad response: %s", e)
            continue

        status = resp_json.get("status", "")
        if status != "REQUEST_SUCCEEDED":
            msg = resp_json.get("message", [""])[0] if resp_json.get("message") else ""
            log.warning("BLS status: %s — message: %s", status, msg)

        results = resp_json.get("Results", {})
        for series in results.get("series", []):
            sid = series.get("seriesID", "")
            entry = combined_map.get(sid)
            if not entry:
                continue
            geo_id, ind_key = entry

            data_points = series.get("data", [])
            if not data_points:
                continue

            by_year: Dict[int, List] = {}
            for dp in data_points:
                try:
                    yr = int(dp["year"])
                except (ValueError, KeyError):
                    continue
                if yr in years:
                    by_year.setdefault(yr, []).append(dp)

            for yr, points in by_year.items():
                value = None
                m13 = [p for p in points if p.get("period") == "M13"]
                if m13:
                    value = m13[0].get("value")
                else:
                    monthly = sorted(
                        [p for p in points if p.get("period", "").startswith("M")],
                        key=lambda p: p.get("period", ""),
                        reverse=True,
                    )
                    if monthly:
                        value = monthly[0].get("value")

                if value is not None:
                    try:
                        value = float(value)
                    except (ValueError, TypeError):
                        continue
                    all_records.append({
                        "CBSA": geo_id,
                        "Year": yr,
                        ind_key: value,
                    })

        if batch_start + 50 < len(series_ids):
            time.sleep(0.5)  # Rate limit only between batches, not after last

    # Fallback: if mining and/or construction were requested but missing for a geo+year,
    # and the combined series has data, use combined value as construction fallback
    if need_combined_fallback and all_records:
        from collections import defaultdict
        combined_vals = defaultdict(dict)  # {(geo, year): value}
        for rec in all_records:
            if "_ind_mining_construction_combined" in rec:
                combined_vals[(rec["CBSA"], rec["Year"])] = rec["_ind_mining_construction_combined"]

        # Index existing mining/construction values by (geo, year)
        has_mining = set()
        has_construction = set()
        for rec in all_records:
            key = (rec["CBSA"], rec["Year"])
            if rec.get("ind_mining_logging") is not None:
                has_mining.add(key)
            if rec.get("ind_construction") is not None:
                has_construction.add(key)

        for (geo_id, yr), cval in combined_vals.items():
            key = (geo_id, yr)
            if key not in has_mining and key not in has_construction:
                if "ind_construction" in bls_keys:
                    all_records.append({
                        "CBSA": geo_id, "Year": yr, "ind_construction": cval,
                    })
                    log.info("BLS fallback: using combined mining/construction for %s %d", geo_id, yr)

        # Strip the internal combined column from all records
        for rec in all_records:
            rec.pop("_ind_mining_construction_combined", None)

    if not all_records:
        return pd.DataFrame(columns=["CBSA", "Year"])

    df = pd.DataFrame(all_records)
    df["CBSA"] = df["CBSA"].astype(str)
    indicator_cols = [c for c in df.columns if c not in ("CBSA", "Year")]
    df = df.groupby(["CBSA", "Year"], as_index=False)[indicator_cols].first()
    return df


async def fetch_bls(
    geos: Dict[str, str],
    cbsa_to_state: Dict[str, str],
    indicator_keys: List[str],
    years: List[int],
    geo_type: str = "msa",
) -> pd.DataFrame:
    """Async wrapper around sync BLS fetch."""
    return await asyncio.to_thread(
        _fetch_bls_sync, geos, cbsa_to_state, indicator_keys, years, BLS_API_KEY, geo_type
    )
