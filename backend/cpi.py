"""CPI-U (Consumer Price Index for All Urban Consumers) data for inflation adjustment.

Fetches annual average CPI-U from FRED series CPIAUCSL.
Used to convert nominal dollar values to real (constant-year) dollars.
"""
import logging
import time
from typing import Dict, Optional

from .config import FRED_API_KEY
from .utils import request_with_retry

log = logging.getLogger("data_portal")

_cpi_cache: Optional[Dict[int, float]] = None
_cpi_cache_ts: float = 0
CPI_CACHE_TTL = 86400  # 24 hours


def _fetch_cpi_from_fred() -> Dict[int, float]:
    """Fetch CPI-U annual averages from FRED."""
    if not FRED_API_KEY:
        log.warning("FRED_API_KEY not set; CPI data unavailable")
        return {}

    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": "CPIAUCSL",
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "frequency": "a",  # annual average
        "observation_start": "2005-01-01",
        "observation_end": "2025-12-31",
    }

    try:
        resp = request_with_retry("GET", url, params=params)
        data = resp.json()
    except Exception as e:
        log.error("Failed to fetch CPI data from FRED: %s", e)
        return {}

    observations = data.get("observations", [])
    cpi_table: Dict[int, float] = {}
    for obs in observations:
        try:
            year = int(obs["date"][:4])
            value = float(obs["value"])
            cpi_table[year] = value
        except (ValueError, KeyError, TypeError):
            continue

    log.info("Loaded CPI data for %d years (%s-%s)",
             len(cpi_table),
             min(cpi_table.keys()) if cpi_table else "?",
             max(cpi_table.keys()) if cpi_table else "?")
    return cpi_table


def get_cpi_table() -> Dict[int, float]:
    """Get CPI lookup table {year: cpi_value} with caching."""
    global _cpi_cache, _cpi_cache_ts
    now = time.time()
    if _cpi_cache is not None and (now - _cpi_cache_ts) < CPI_CACHE_TTL:
        return _cpi_cache

    table = _fetch_cpi_from_fred()
    if table:
        _cpi_cache = table
        _cpi_cache_ts = now
    return table or {}


def adjust_for_inflation(value: float, data_year: int, base_year: int) -> Optional[float]:
    """Adjust a nominal dollar value to constant base_year dollars.

    Formula: real_value = nominal_value * (CPI[base_year] / CPI[data_year])
    """
    cpi = get_cpi_table()
    if data_year not in cpi or base_year not in cpi:
        return None
    if cpi[data_year] <= 0:
        return None
    return value * (cpi[base_year] / cpi[data_year])
