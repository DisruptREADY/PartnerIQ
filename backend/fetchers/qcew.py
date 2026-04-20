"""QCEW fetcher — county/state/MSA covered employment from BLS QCEW API."""
import asyncio
import io
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

import pandas as pd

from ..config import QCEW_YEARS
from ..utils import request_with_retry

log = logging.getLogger("data_portal")

QCEW_API_BASE = "https://data.bls.gov/cew/data/api"


def _area_code(geo_id: str, geo_type: str) -> str:
    """Convert portal geo_id to QCEW area code."""
    if geo_type == "county":
        return geo_id  # 5-digit FIPS
    elif geo_type == "state":
        return geo_id + "000"  # e.g. "22" → "22000"
    elif geo_type == "msa":
        return "C" + geo_id[:4]  # e.g. "12940" → "C1294"
    raise ValueError(f"QCEW: unsupported geo_type {geo_type}")


def _find_total_row(df: pd.DataFrame) -> pd.Series | None:
    """Find the Total All Industries row (own_code=0, industry_code=10)."""
    row = df[(df["own_code"] == 0) & (df["industry_code"] == "10")]
    if row.empty:
        row = df[(df["own_code"] == 0) & (df["industry_code"] == 10)]
    if row.empty:
        return None
    return row.iloc[0]


def _fetch_one(year: int, area: str) -> float | None:
    """Fetch total employment for one area+year.

    Tries annual average first, then falls back to the most recent quarter
    (using the last available month in that quarter).
    """
    # Try annual average first
    url = f"{QCEW_API_BASE}/{year}/a/area/{area}.csv"
    try:
        resp = request_with_retry("GET", url, retries=2, sleep_s=0.5)
        df = pd.read_csv(io.StringIO(resp.text))
        row = _find_total_row(df)
        if row is not None:
            val = row.get("annual_avg_emplvl")
            if val is not None and not pd.isna(val):
                return int(val)
    except Exception:
        pass  # annual not available, try quarterly

    # Fall back to most recent available quarter
    for qtr in (4, 3, 2, 1):
        url = f"{QCEW_API_BASE}/{year}/{qtr}/area/{area}.csv"
        try:
            resp = request_with_retry("GET", url, retries=1, sleep_s=0.3)
            df = pd.read_csv(io.StringIO(resp.text))
            row = _find_total_row(df)
            if row is None:
                continue
            # Use the last month in the quarter (most recent data point)
            val = row.get("month3_emplvl")
            if val is not None and not pd.isna(val):
                log.info("QCEW %s/%d: using Q%d month3 as fallback", area, year, qtr)
                return int(val)
        except Exception:
            continue

    log.warning("QCEW %s/%d: no annual or quarterly data found", area, year)
    return None


def _fetch_qcew_sync(
    geos: Dict[str, str],
    years: List[int],
    geo_type: str,
) -> pd.DataFrame:
    """Fetch QCEW annual employment for all geos/years, parallelized."""
    valid_years = [y for y in years if y in QCEW_YEARS]
    if not valid_years:
        return pd.DataFrame(columns=["CBSA", "Year"])

    # Build work items: (geo_id, year, area_code)
    work = []
    for geo_id in geos:
        try:
            area = _area_code(geo_id, geo_type)
        except ValueError:
            continue
        for year in valid_years:
            work.append((geo_id, year, area))

    if not work:
        return pd.DataFrame(columns=["CBSA", "Year"])

    log.info("QCEW (%s): fetching %d area-year combinations", geo_type, len(work))

    records: List[Dict[str, Any]] = []
    # Cap concurrency to avoid hammering BLS
    max_workers = min(8, len(work))

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {}
        for geo_id, year, area in work:
            fut = pool.submit(_fetch_one, year, area)
            futures[fut] = (geo_id, year)
            time.sleep(0.05)  # stagger submissions slightly

        for fut in as_completed(futures):
            geo_id, year = futures[fut]
            try:
                val = fut.result()
            except Exception as e:
                log.warning("QCEW %s/%d unexpected error: %s", geo_id, year, e)
                continue
            if val is not None:
                records.append({
                    "CBSA": geo_id,
                    "Year": year,
                    "qcew_employment": val,
                })

    if not records:
        return pd.DataFrame(columns=["CBSA", "Year"])

    df = pd.DataFrame(records)
    df["CBSA"] = df["CBSA"].astype(str)
    return df.sort_values(["CBSA", "Year"]).reset_index(drop=True)


async def fetch_qcew(
    geos: Dict[str, str],
    years: List[int],
    geo_type: str = "county",
) -> pd.DataFrame:
    """Async wrapper around sync QCEW fetch."""
    return await asyncio.to_thread(_fetch_qcew_sync, geos, years, geo_type)
