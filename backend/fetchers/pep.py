"""Census Population Estimates Program (PEP) fetcher.

Fetches annual population estimates, births, deaths, and migration components.

API structure:
  - Vintage 2023 /pep/charv: population estimates 2020-2023 (states, metros, counties)
  - Vintage 2019 /pep/components: births, deaths, migration 2010-2019 (metros, states, counties)
"""
import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

import pandas as pd

from ..config import INDICATORS, CENSUS_API_KEY
from ..utils import request_with_retry

MAX_PEP_WORKERS = 6  # Concurrent Census API calls

log = logging.getLogger("data_portal")

# PEP geo parameter formats by geo type
GEO_PARAMS = {
    "msa": lambda geo_id: {
        "for": f"metropolitan statistical area/micropolitan statistical area:{geo_id}",
    },
    "micro": lambda geo_id: {
        "for": f"metropolitan statistical area/micropolitan statistical area:{geo_id}",
    },
    "state": lambda geo_id: {"for": f"state:{geo_id}"},
    "county": lambda geo_id: {
        "for": f"county:{geo_id[2:]}",
        "in": f"state:{geo_id[:2]}",
    },
}

# Vintage 2019 components: PERIOD_CODE -> year mapping
# 1=Apr-Jul 2010, 2=Jul2010-Jul2011, ..., 10=Jul2018-Jul2019
PERIOD_TO_YEAR = {str(i): 2009 + i for i in range(1, 11)}  # "1"->2010 ... "10"->2019

# Vintage 2023 charv: YEAR field directly maps to calendar year (2020-2023)
CHARV_YEARS = {2020, 2021, 2022, 2023}

# Component variables available in 2019 vintage
COMPONENT_VARS = {"BIRTHS", "DEATHS", "DOMESTICMIG", "INTERNATIONALMIG", "NATURALINC"}

# PEP API variable aliases: our config uses "NATURALCHG" (natural change) but the
# vintage 2019 components API returns it as "NATURALINC" (natural increase).
VAR_ALIASES = {"NATURALCHG": "NATURALINC"}


def _fetch_population(
    geos: Dict[str, str],
    years: List[int],
    geo_type: str,
) -> List[dict]:
    """Fetch population from vintage 2023 charv endpoint (years 2020-2023)."""
    wanted = [y for y in years if y in CHARV_YEARS]
    if not wanted:
        return []

    rows = []
    # Fetch all geos at once with wildcard, then filter
    url = "https://api.census.gov/data/2023/pep/charv"
    geo_ids_set = set(geos.keys())

    # For state, we can use wildcard; for metro/county we fetch individually
    if geo_type == "state":
        params = {"get": "NAME,POP,YEAR", "for": "state:*"}
        if CENSUS_API_KEY:
            params["key"] = CENSUS_API_KEY
        try:
            resp = request_with_retry("GET", url, params=params)
            data = resp.json()
            if isinstance(data, list) and len(data) >= 2:
                header = data[0]
                for row_data in data[1:]:
                    rd = dict(zip(header, row_data))
                    state_fips = rd.get("state", "")
                    year = int(rd.get("YEAR", 0))
                    if state_fips in geo_ids_set and year in wanted:
                        try:
                            rows.append({
                                "CBSA": state_fips,
                                "Year": year,
                                "pep_population": float(rd["POP"]),
                            })
                        except (ValueError, TypeError):
                            pass
        except Exception as e:
            log.warning("PEP charv state fetch failed: %s", e)
    else:
        def _fetch_one_pop(geo_id):
            """Fetch population for a single geo. Thread-safe."""
            _params = {"get": "NAME,POP,YEAR"}
            _params.update(GEO_PARAMS[geo_type](geo_id))
            if CENSUS_API_KEY:
                _params["key"] = CENSUS_API_KEY
            _rows = []
            try:
                resp = request_with_retry("GET", url, params=_params)
                data = resp.json()
                if isinstance(data, list) and len(data) >= 2:
                    header = data[0]
                    seen_years = set()
                    for row_data in data[1:]:
                        rd = dict(zip(header, row_data))
                        year = int(rd.get("YEAR", 0))
                        if year in wanted and year not in seen_years:
                            seen_years.add(year)
                            try:
                                _rows.append({
                                    "CBSA": geo_id,
                                    "Year": year,
                                    "pep_population": float(rd["POP"]),
                                })
                            except (ValueError, TypeError):
                                pass
            except Exception as e:
                log.warning("PEP charv fetch failed for %s: %s", geo_id, e)
            return _rows

        geo_list = list(geos.keys())
        with ThreadPoolExecutor(max_workers=min(MAX_PEP_WORKERS, len(geo_list))) as pool:
            futures = {pool.submit(_fetch_one_pop, gid): gid for gid in geo_list}
            for future in as_completed(futures):
                rows.extend(future.result())

    return rows


def _fetch_components(
    geos: Dict[str, str],
    indicator_keys: List[str],
    years: List[int],
    geo_type: str,
) -> List[dict]:
    """Fetch births/deaths/migration from vintage 2019 components (years 2010-2019)."""
    # Determine which component variables we need
    needed_vars = set()
    key_to_var = {}
    for key in indicator_keys:
        meta = INDICATORS.get(key, {})
        if meta.get("source") != "pep" or key == "pep_population":
            continue
        for v in meta.get("variables", []):
            api_var = VAR_ALIASES.get(v, v)
            if api_var in COMPONENT_VARS:
                needed_vars.add(api_var)
                key_to_var[key] = api_var

    if not needed_vars:
        return []

    wanted_years = {y for y in years if 2010 <= y <= 2019}
    if not wanted_years:
        return []

    var_list = sorted(needed_vars)
    get_str = ",".join(["NAME", "PERIOD_CODE"] + var_list)
    url = "https://api.census.gov/data/2019/pep/components"

    rows = []

    def _fetch_one_comp(geo_id):
        """Fetch components for a single geo. Thread-safe."""
        _params = {"get": get_str}
        _params.update(GEO_PARAMS[geo_type](geo_id))
        if CENSUS_API_KEY:
            _params["key"] = CENSUS_API_KEY
        _rows = []

        try:
            resp = request_with_retry("GET", url, params=_params)
            data = resp.json()
        except Exception as e:
            log.warning("PEP components fetch failed for %s: %s", geo_id, e)
            return _rows

        if not isinstance(data, list) or len(data) < 2:
            return _rows

        header = data[0]
        for row_data in data[1:]:
            rd = dict(zip(header, row_data))
            period = rd.get("PERIOD_CODE", "")
            year = PERIOD_TO_YEAR.get(period)
            if year is None or year not in wanted_years:
                continue

            result_row = {"CBSA": geo_id, "Year": year}
            for key, api_var in key_to_var.items():
                raw = rd.get(api_var)
                if raw is not None:
                    try:
                        result_row[key] = float(raw)
                    except (ValueError, TypeError):
                        pass

            if len(result_row) > 2:
                _rows.append(result_row)

        return _rows

    geo_list = list(geos.keys())
    with ThreadPoolExecutor(max_workers=min(MAX_PEP_WORKERS, len(geo_list))) as pool:
        futures = {pool.submit(_fetch_one_comp, gid): gid for gid in geo_list}
        for future in as_completed(futures):
            rows.extend(future.result())

    return rows


def _fetch_pep_sync(
    geos: Dict[str, str],
    indicator_keys: List[str],
    years: List[int],
    geo_type: str = "msa",
) -> pd.DataFrame:
    """Fetch PEP data for the given geographies and indicators."""
    if geo_type not in GEO_PARAMS:
        log.warning("PEP: unsupported geo_type %s", geo_type)
        return pd.DataFrame()

    all_rows = []

    # Population estimates (2020-2023 from charv)
    if "pep_population" in indicator_keys:
        pop_rows = _fetch_population(geos, years, geo_type)
        all_rows.extend(pop_rows)

    # Components: births, deaths, migration (2010-2019 from vintage 2019)
    component_keys = [k for k in indicator_keys if k != "pep_population"]
    if component_keys:
        comp_rows = _fetch_components(geos, component_keys, years, geo_type)
        all_rows.extend(comp_rows)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    # Merge rows that have same CBSA+Year (population + components for overlapping years)
    if not df.empty:
        df = df.groupby(["CBSA", "Year"], as_index=False).first()
        df["CBSA"] = df["CBSA"].astype(str)
    return df


async def fetch_pep(
    geos: Dict[str, str],
    indicator_keys: List[str],
    years: List[int],
    geo_type: str = "msa",
) -> pd.DataFrame:
    """Async wrapper around sync PEP fetch."""
    return await asyncio.to_thread(
        _fetch_pep_sync, geos, indicator_keys, years, geo_type
    )
