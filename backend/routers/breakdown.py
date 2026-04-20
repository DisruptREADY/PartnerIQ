"""Breakdown router — full industry and occupation breakdowns for selected geos."""
import logging
import time
from typing import Any, Dict, List, Optional

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import BLS_API_KEY
from ..fetchers.oews import SOC_MAJOR_GROUPS, fetch_oews
from ..routers.geography import get_metros
from ..utils import build_cbsa_to_state_fips, request_with_retry

log = logging.getLogger("data_portal")
router = APIRouter()

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# CES supersectors — code (8-digit industry) -> label
# Includes Total Nonfarm (00000000) as denominator for share calculations
CES_INDUSTRIES: Dict[str, str] = {
    "00000000": "Total Nonfarm",
    "10000000": "Mining & Logging",
    "20000000": "Construction",
    "30000000": "Manufacturing",
    "40000000": "Trade, Transportation & Utilities",
    "41000000": "Wholesale Trade",
    "42000000": "Retail Trade",
    "43000000": "Transportation, Warehousing & Utilities",
    "50000000": "Information",
    "55000000": "Financial Activities",
    "60000000": "Professional & Business Services",
    "65000000": "Education & Health Services",
    "70000000": "Leisure & Hospitality",
    "80000000": "Other Services",
    "90000000": "Government",
}

# Simple in-memory caches
_industry_cache: Dict[str, Any] = {}
_occupation_cache: Dict[str, Any] = {}


class IndustryRequest(BaseModel):
    geo_ids: List[str]
    years: Optional[List[int]] = None


class OccupationRequest(BaseModel):
    geo_ids: List[str]


@router.get("/breakdown/industries")
async def list_industries():
    """Return available CES industry supersectors."""
    return [
        {"code": code, "label": label}
        for code, label in CES_INDUSTRIES.items()
    ]


@router.get("/breakdown/occupations")
async def list_occupations():
    """Return available SOC major occupation groups."""
    return [
        {"code": code, "label": label}
        for code, label in SOC_MAJOR_GROUPS.items()
    ]


@router.post("/breakdown/industry")
async def industry_breakdown(req: IndustryRequest):
    """Fetch CES industry employment for all supersectors across selected geos."""
    if not req.geo_ids:
        raise HTTPException(400, "No geographies selected.")

    years = req.years or [2024]
    cache_key = f"{','.join(sorted(req.geo_ids))}|{','.join(map(str, sorted(years)))}"
    if cache_key in _industry_cache:
        return _industry_cache[cache_key]

    all_metros = get_metros()
    geos = {g: all_metros.get(g, g) for g in req.geo_ids}
    cbsa_to_state = build_cbsa_to_state_fips(all_metros)

    # Combined Mining, Logging & Construction — used as fallback when BLS
    # doesn't publish separate Mining/Logging and Construction series
    COMBINED_MINING_CONSTRUCTION = "15000000"

    # Build series IDs: SMU{state2}{cbsa5}{industry8}{datatype01}
    series_map: Dict[str, Dict[str, str]] = {}  # series_id -> {geo_id, industry_code}
    for geo_id in req.geo_ids:
        state_fips = cbsa_to_state.get(geo_id)
        if not state_fips:
            log.warning("Industry breakdown: no state FIPS for geo %s", geo_id)
            continue
        for ind_code in list(CES_INDUSTRIES) + [COMBINED_MINING_CONSTRUCTION]:
            sid = f"SMU{state_fips}{geo_id}{ind_code}01"
            series_map[sid] = {"geo_id": geo_id, "industry_code": ind_code}

    series_ids = list(series_map.keys())
    log.info("Industry breakdown: %d series for %d geos", len(series_ids), len(req.geo_ids))

    start_year = str(min(years))
    end_year = str(max(years))
    data: List[Dict[str, Any]] = []

    for batch_start in range(0, len(series_ids), 50):
        batch = series_ids[batch_start: batch_start + 50]
        payload = {
            "seriesid": batch,
            "startyear": start_year,
            "endyear": end_year,
            "registrationkey": BLS_API_KEY,
        }

        try:
            resp = request_with_retry("POST", BLS_API_URL, json=payload)
            resp_json = resp.json()
        except requests.RequestException as e:
            log.warning("Industry breakdown batch failed: %s", e)
            continue
        except (ValueError, KeyError) as e:
            log.warning("Industry breakdown bad response: %s", e)
            continue

        status = resp_json.get("status", "")
        if status != "REQUEST_SUCCEEDED":
            msg = resp_json.get("message", [""])[0] if resp_json.get("message") else ""
            log.warning("Industry breakdown BLS status: %s — %s", status, msg)

        for series in resp_json.get("Results", {}).get("series", []):
            sid = series.get("seriesID", "")
            meta = series_map.get(sid)
            if not meta:
                continue

            by_year: Dict[int, float] = {}
            for dp in series.get("data", []):
                try:
                    yr = int(dp["year"])
                except (ValueError, KeyError):
                    continue
                if yr not in years:
                    continue

                # Prefer M13 (annual average), fallback to latest monthly
                period = dp.get("period", "")
                if period == "M13":
                    try:
                        by_year[yr] = float(dp["value"])
                    except (ValueError, TypeError):
                        pass
                elif period.startswith("M") and yr not in by_year:
                    try:
                        by_year[yr] = float(dp["value"])
                    except (ValueError, TypeError):
                        pass

            for yr, val in by_year.items():
                data.append({
                    "geo_id": meta["geo_id"],
                    "year": yr,
                    "industry_code": meta["industry_code"],
                    "value": val,
                })

        time.sleep(0.5)

    # Fallback: if mining (10000000) and construction (20000000) are both
    # missing but combined mining/logging/construction (15000000) has data,
    # use the combined value as the construction figure.
    fallback_geos: List[str] = []
    for geo_id in req.geo_ids:
        for yr in years:
            has_mining = any(
                d["geo_id"] == geo_id and d["industry_code"] == "10000000" and d["year"] == yr
                for d in data
            )
            has_construction = any(
                d["geo_id"] == geo_id and d["industry_code"] == "20000000" and d["year"] == yr
                for d in data
            )
            combined_val = next(
                (d["value"] for d in data
                 if d["geo_id"] == geo_id and d["industry_code"] == COMBINED_MINING_CONSTRUCTION and d["year"] == yr),
                None,
            )
            if not has_mining and not has_construction and combined_val is not None:
                data.append({
                    "geo_id": geo_id,
                    "year": yr,
                    "industry_code": "20000000",
                    "value": combined_val,
                })
                if geo_id not in fallback_geos:
                    fallback_geos.append(geo_id)

    # Remove the combined series from data — it's not a display industry
    data = [d for d in data if d["industry_code"] != COMBINED_MINING_CONSTRUCTION]

    warnings = []
    if not data:
        warnings.append("No industry data returned — the BLS API may be temporarily unavailable.")

    result = {
        "industries": [{"code": c, "label": l} for c, l in CES_INDUSTRIES.items()],
        "geos": [{"id": g, "name": geos.get(g, g)} for g in req.geo_ids],
        "years": sorted(years),
        "data": data,
        "fallback_geos": fallback_geos,
        "warnings": warnings,
    }

    _industry_cache[cache_key] = result
    return result


@router.post("/breakdown/occupation")
async def occupation_breakdown(req: OccupationRequest):
    """Fetch OEWS occupation employment and wages for selected geos."""
    if not req.geo_ids:
        raise HTTPException(400, "No geographies selected.")

    cache_key = ",".join(sorted(req.geo_ids))
    if cache_key in _occupation_cache:
        return _occupation_cache[cache_key]

    all_metros = get_metros()
    geos = {g: all_metros.get(g, g) for g in req.geo_ids}

    oews_result = await fetch_oews(req.geo_ids)

    warnings = list(oews_result.get("warnings", []))
    warnings.append("OEWS data is available for the latest year only (currently 2024).")

    result = {
        "occupations": [{"code": c, "label": l} for c, l in SOC_MAJOR_GROUPS.items()],
        "geos": [{"id": g, "name": geos.get(g, g)} for g in req.geo_ids],
        "year": oews_result["year"],
        "data": oews_result["data"],
        "warnings": warnings,
    }

    _occupation_cache[cache_key] = result
    return result
