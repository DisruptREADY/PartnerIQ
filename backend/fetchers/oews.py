"""OEWS (Occupational Employment and Wage Statistics) fetcher.

Fetches employment and median wage data by SOC major occupation group
from the BLS OEWS survey. Data is annual-only (latest year available).
"""
import asyncio
import logging
import time
from typing import Any, Dict, List

import requests

from ..config import BLS_API_KEY
from ..utils import request_with_retry

log = logging.getLogger("data_portal")

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# 22 SOC major occupation groups
SOC_MAJOR_GROUPS: Dict[str, str] = {
    "110000": "Management",
    "130000": "Business and Financial Operations",
    "150000": "Computer and Mathematical",
    "170000": "Architecture and Engineering",
    "190000": "Life, Physical, and Social Science",
    "210000": "Community and Social Service",
    "230000": "Legal",
    "250000": "Educational Instruction and Library",
    "270000": "Arts, Design, Entertainment, Sports, and Media",
    "290000": "Healthcare Practitioners and Technical",
    "310000": "Healthcare Support",
    "330000": "Protective Service",
    "350000": "Food Preparation and Serving Related",
    "370000": "Building and Grounds Cleaning and Maintenance",
    "390000": "Personal Care and Service",
    "410000": "Sales and Related",
    "430000": "Office and Administrative Support",
    "450000": "Farming, Fishing, and Forestry",
    "470000": "Construction and Extraction",
    "490000": "Installation, Maintenance, and Repair",
    "510000": "Production",
    "530000": "Transportation and Material Moving",
}


def _build_oews_series(geo_id: str, soc_code: str, datatype: str) -> str:
    """Build OEWS series ID for an MSA.

    Format: OE + U + M + area(7) + industry(6) + occupation(6) + datatype(2) = 25 chars
    area = 7-digit zero-padded CBSA code (e.g., "0012940")
    industry = "000000" for cross-industry
    occupation = 6-digit SOC code (e.g., "110000")
    datatype: "01" = employment, "04" = annual median wage
    """
    area7 = geo_id.zfill(7)
    return f"OEUM{area7}000000{soc_code}{datatype}"


def _fetch_oews_sync(
    geo_ids: List[str],
    api_key: str,
) -> Dict[str, Any]:
    """Fetch OEWS employment and median wage for all major SOC groups.

    Returns dict with 'year', 'data' list, and 'warnings' list.
    """
    all_series: Dict[str, Dict[str, str]] = {}  # series_id -> {geo_id, soc_code, metric}

    for geo_id in geo_ids:
        for soc_code in SOC_MAJOR_GROUPS:
            # Employment (datatype 01)
            emp_sid = _build_oews_series(geo_id, soc_code, "01")
            all_series[emp_sid] = {"geo_id": geo_id, "soc_code": soc_code, "metric": "employment"}
            # Annual median wage (datatype 04)
            wage_sid = _build_oews_series(geo_id, soc_code, "04")
            all_series[wage_sid] = {"geo_id": geo_id, "soc_code": soc_code, "metric": "median_wage"}

    series_ids = list(all_series.keys())
    log.info("OEWS: %d series to fetch for %d geos", len(series_ids), len(geo_ids))

    # Results keyed by (geo_id, soc_code) -> {employment, median_wage, year}
    results: Dict[tuple, Dict[str, Any]] = {}
    year_seen = None
    warnings: List[str] = []

    for batch_start in range(0, len(series_ids), 50):
        batch = series_ids[batch_start: batch_start + 50]
        payload = {
            "seriesid": batch,
            "startyear": "2022",
            "endyear": "2025",
            "registrationkey": api_key,
        }

        try:
            resp = request_with_retry("POST", BLS_API_URL, json=payload)
            resp_json = resp.json()
        except requests.RequestException as e:
            log.warning("OEWS batch request failed: %s", e)
            continue
        except (ValueError, KeyError) as e:
            log.warning("OEWS batch bad response: %s", e)
            continue

        status = resp_json.get("status", "")
        if status != "REQUEST_SUCCEEDED":
            msg = resp_json.get("message", [""])[0] if resp_json.get("message") else ""
            log.warning("OEWS BLS status: %s — %s", status, msg)
        else:
            series_count = len(resp_json.get("Results", {}).get("series", []))
            log.debug("OEWS batch OK: %d series returned (requested %d)", series_count, len(batch))

        for series in resp_json.get("Results", {}).get("series", []):
            sid = series.get("seriesID", "")
            meta = all_series.get(sid)
            if not meta:
                continue

            for dp in series.get("data", []):
                period = dp.get("period", "")
                # OEWS uses A01 (annual) period
                if period != "A01":
                    continue

                try:
                    value = float(dp["value"])
                    yr = int(dp["year"])
                except (ValueError, KeyError, TypeError):
                    continue

                if year_seen is None:
                    year_seen = yr

                key = (meta["geo_id"], meta["soc_code"])
                if key not in results:
                    results[key] = {"year": yr}
                results[key][meta["metric"]] = value

        time.sleep(0.5)

    # Convert to flat list
    data_list = []
    for (geo_id, soc_code), vals in results.items():
        data_list.append({
            "geo_id": geo_id,
            "occ_code": soc_code,
            "employment": vals.get("employment"),
            "median_wage": vals.get("median_wage"),
        })

    if not data_list:
        warnings.append("No OEWS data returned — the BLS API may be temporarily unavailable.")

    return {
        "year": year_seen or 2024,
        "data": data_list,
        "warnings": warnings,
    }


async def fetch_oews(
    geo_ids: List[str],
) -> Dict[str, Any]:
    """Async wrapper around sync OEWS fetch."""
    return await asyncio.to_thread(_fetch_oews_sync, geo_ids, BLS_API_KEY)
