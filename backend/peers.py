"""Peer finder service — data assembly, caching, and similarity scoring.

Fetches demographic/economic data for ALL geographies of a given type at once
(wildcard Census calls), computes derived metrics, and scores similarity to a
target geography using weighted distance.
"""
import io
import logging
import re
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .config import CENSUS_API_KEY
from .utils import haversine_miles, request_with_retry, FIPS_TO_STATE_ABBR

log = logging.getLogger("data_portal")

# ---------------------------------------------------------------------------
# Dimension definitions
# ---------------------------------------------------------------------------

DIMENSIONS = {
    "pop":       {"col": "population",        "label": "Population",             "geo_types": None},
    "income":    {"col": "median_hh_income",   "label": "Median Household Income","geo_types": None},
    "poverty":   {"col": "poverty_rate",       "label": "Poverty Rate",           "geo_types": None},
    "education": {"col": "bachelors_pct",      "label": "% Bachelor's Degree+",   "geo_types": None},
    "home":      {"col": "median_home_value",  "label": "Median Home Value",      "geo_types": None},
    "rent":      {"col": "median_rent",        "label": "Median Gross Rent",      "geo_types": None},
    "unemp":     {"col": "unemployment_rate",  "label": "Unemployment Rate",      "geo_types": None},
    "growth":    {"col": "pop_growth_pct",     "label": "5-Year Pop Growth %",    "geo_types": None},
    "city":      {"col": "city_pop",           "label": "Principal City Pop",     "geo_types": {"msa"}},
    "4yr":       {"col": "n_4year",            "label": "4-Year Institutions",    "geo_types": {"msa", "county"}},
    "2yr":       {"col": "n_2year",            "label": "2-Year Institutions",    "geo_types": {"msa", "county"}},
    "drive":     {"col": "drive_hours",        "label": "Drive to Large Metro",   "geo_types": {"msa", "county", "micro"}},
}

# Weight profiles — values must be > 0 for selected dimensions
WEIGHT_PROFILES = {
    "balanced": {
        "pop": 2, "income": 1.5, "poverty": 1, "education": 1.5,
        "home": 1, "rent": 1, "unemp": 1, "growth": 1,
        "city": 0.5, "4yr": 0.5, "2yr": 0.5, "drive": 0.5,
    },
    "economic": {
        "pop": 1, "income": 3, "poverty": 2, "education": 1,
        "home": 2, "rent": 2, "unemp": 2, "growth": 1.5,
        "city": 0.5, "4yr": 0.5, "2yr": 0.5, "drive": 0.5,
    },
    "demographic": {
        "pop": 3, "income": 1, "poverty": 1.5, "education": 2,
        "home": 0.5, "rent": 0.5, "unemp": 1, "growth": 2,
        "city": 1, "4yr": 1, "2yr": 1, "drive": 0.5,
    },
    "geographic": {
        "pop": 2, "income": 1, "poverty": 0.5, "education": 0.5,
        "home": 0.5, "rent": 0.5, "unemp": 0.5, "growth": 1,
        "city": 1.5, "4yr": 1, "2yr": 1, "drive": 3,
    },
}

# ---------------------------------------------------------------------------
# Data fetching helpers
# ---------------------------------------------------------------------------

# Census variable codes for peer demographics
_CENSUS_VARS = [
    "B01003_001E",  # population
    "B19013_001E",  # median hh income
    "B17001_001E",  # poverty universe
    "B17001_002E",  # poverty below
    "B15003_001E",  # pop 25+
    "B15003_022E",  # bachelor's
    "B15003_023E",  # master's
    "B15003_024E",  # professional
    "B15003_025E",  # doctorate
    "B25077_001E",  # median home value
    "B25064_001E",  # median gross rent
    "B23025_003E",  # civilian labor force
    "B23025_005E",  # unemployed
]

# Large metros (500k+) for drive-time calculation — hardcoded pop thresholds
# aren't needed since we compute them from the data itself.
_POP_LARGE_METRO = 500_000


def _census_geo_clause(geo_type: str) -> str:
    """Return the Census API 'for' clause for wildcard geography."""
    if geo_type in ("msa", "micro"):
        return "metropolitan statistical area/micropolitan statistical area:*"
    if geo_type == "state":
        return "state:*"
    if geo_type == "county":
        return "county:*"
    if geo_type == "place":
        return "place:*"
    raise ValueError(f"Unsupported geo_type: {geo_type}")


def _acs_dataset(geo_type: str) -> str:
    """ACS 1-year for MSA/micro, 5-year for county/state/place."""
    if geo_type in ("msa", "micro"):
        return "acs1"
    return "acs5"


def _acs_year(geo_type: str, year: int) -> int:
    """Adjust year for dataset availability. ACS5 latest = year-1 typically."""
    if geo_type in ("msa", "micro"):
        # ACS 1-year: no 2020
        return year if year != 2020 else 2019
    # ACS 5-year: latest is usually year - 1
    return min(year, 2023)


def _fetch_all_demographics(geo_type: str, year: int) -> pd.DataFrame:
    """Fetch demographic variables for ALL geographies of a type at once."""
    ds = _acs_dataset(geo_type)
    yr = _acs_year(geo_type, year)
    url = f"https://api.census.gov/data/{yr}/acs/{ds}"

    params = {
        "get": ",".join(["NAME"] + _CENSUS_VARS),
        "for": _census_geo_clause(geo_type),
    }
    if CENSUS_API_KEY:
        params["key"] = CENSUS_API_KEY

    # For county, Census requires 'in=state:*'
    if geo_type == "county":
        params["in"] = "state:*"
    if geo_type == "place":
        params["in"] = "state:*"

    log.info("Peer finder: fetching demographics for %s from ACS %s %d ...", geo_type, ds, yr)
    try:
        resp = request_with_retry("GET", url, params=params, timeout=120)
        data = resp.json()
    except Exception as e:
        log.error("Peer finder demographics fetch failed: %s", e)
        return pd.DataFrame()

    if not isinstance(data, list) or len(data) < 2:
        log.warning("Peer finder: empty demographics response for %s", geo_type)
        return pd.DataFrame()

    header, *rows = data

    records = []
    for row in rows:
        d = dict(zip(header, row))

        # Build geo_id
        if geo_type in ("msa", "micro"):
            geo_id = d.get("metropolitan statistical area/micropolitan statistical area", "")
        elif geo_type == "state":
            geo_id = d.get("state", "")
        elif geo_type == "county":
            geo_id = d.get("state", "") + d.get("county", "")
        elif geo_type == "place":
            geo_id = d.get("state", "") + d.get("place", "")
        else:
            continue

        # Filter metros vs micros
        name = d.get("NAME", "")
        if geo_type == "msa" and "Metro" not in name:
            continue
        if geo_type == "micro" and "Micro" not in name:
            continue

        def _float(key):
            v = d.get(key)
            if v is None or v == "" or v == "null":
                return None
            try:
                val = float(v)
                return val if val >= 0 else None
            except (ValueError, TypeError):
                return None

        pop = _float("B01003_001E")
        pov_univ = _float("B17001_001E")
        pov_below = _float("B17001_002E")
        pop25 = _float("B15003_001E")
        bach = sum(filter(None, [_float(f"B15003_0{c}E") for c in ("22", "23", "24", "25")]))
        clf = _float("B23025_003E")
        unemp_count = _float("B23025_005E")

        poverty_rate = (pov_below / pov_univ * 100) if pov_univ and pov_below is not None else None
        bachelors_pct = (bach / pop25 * 100) if pop25 and bach else None
        unemployment_rate = (unemp_count / clf * 100) if clf and unemp_count is not None else None

        records.append({
            "geo_id": geo_id,
            "geo_name": name,
            "population": pop,
            "median_hh_income": _float("B19013_001E"),
            "poverty_rate": round(poverty_rate, 1) if poverty_rate is not None else None,
            "bachelors_pct": round(bachelors_pct, 1) if bachelors_pct is not None else None,
            "median_home_value": _float("B25077_001E"),
            "median_rent": _float("B25064_001E"),
            "unemployment_rate": round(unemployment_rate, 1) if unemployment_rate is not None else None,
        })

    df = pd.DataFrame(records)
    log.info("Peer finder: got %d %s records with demographics.", len(df), geo_type)
    return df


def _fetch_prior_population(geo_type: str, year: int) -> Dict[str, float]:
    """Fetch population 5 years prior for growth calculation."""
    prior_year = year - 5
    ds = _acs_dataset(geo_type)
    yr = _acs_year(geo_type, prior_year)
    url = f"https://api.census.gov/data/{yr}/acs/{ds}"

    params = {
        "get": "B01003_001E",
        "for": _census_geo_clause(geo_type),
    }
    if CENSUS_API_KEY:
        params["key"] = CENSUS_API_KEY
    if geo_type in ("county", "place"):
        params["in"] = "state:*"

    log.info("Peer finder: fetching prior population (%s %d) ...", ds, yr)
    try:
        resp = request_with_retry("GET", url, params=params, timeout=120)
        data = resp.json()
    except Exception as e:
        log.error("Peer finder prior population fetch failed: %s", e)
        return {}

    if not isinstance(data, list) or len(data) < 2:
        return {}

    header, *rows = data
    result = {}
    for row in rows:
        d = dict(zip(header, row))
        if geo_type in ("msa", "micro"):
            gid = d.get("metropolitan statistical area/micropolitan statistical area", "")
        elif geo_type == "state":
            gid = d.get("state", "")
        elif geo_type == "county":
            gid = d.get("state", "") + d.get("county", "")
        elif geo_type == "place":
            gid = d.get("state", "") + d.get("place", "")
        else:
            continue
        try:
            val = float(d.get("B01003_001E", 0))
            if val > 0:
                result[gid] = val
        except (ValueError, TypeError):
            pass

    return result


def _fetch_gazetteer_coords(geo_type: str) -> Dict[str, Tuple[float, float]]:
    """Download Census gazetteer for lat/lon coordinates.

    Returns {geo_id: (lat, lon)}.
    """
    # Gazetteer files by type
    if geo_type in ("msa", "micro"):
        gaz_url = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_cbsa_national.zip"
    elif geo_type == "county":
        gaz_url = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_counties_national.zip"
    elif geo_type == "state":
        # No gazetteer for states; use hardcoded centroids
        return _state_centroids()
    elif geo_type == "place":
        gaz_url = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_place_national.zip"
    else:
        return {}

    log.info("Peer finder: downloading gazetteer for %s ...", geo_type)
    try:
        resp = request_with_retry("GET", gaz_url, timeout=60)
    except Exception as e:
        log.error("Peer finder gazetteer download failed: %s", e)
        return {}

    coords = {}
    try:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            for name in zf.namelist():
                if name.endswith(".txt"):
                    with zf.open(name) as f:
                        df = pd.read_csv(f, sep="\t", dtype=str, encoding="latin-1")
                    # Column names vary by file type
                    df.columns = [c.strip() for c in df.columns]

                    if geo_type in ("msa", "micro"):
                        id_col = "GEOID"
                    elif geo_type == "county":
                        id_col = "GEOID"
                    elif geo_type == "place":
                        id_col = "GEOID"
                    else:
                        continue

                    lat_col = [c for c in df.columns if "LAT" in c.upper()][0] if any("LAT" in c.upper() for c in df.columns) else None
                    lon_col = [c for c in df.columns if "LONG" in c.upper()][0] if any("LONG" in c.upper() for c in df.columns) else None

                    if not lat_col or not lon_col or id_col not in df.columns:
                        log.warning("Peer finder: gazetteer columns not found. Available: %s", df.columns.tolist())
                        continue

                    for _, row in df.iterrows():
                        try:
                            gid = str(row[id_col]).strip()
                            lat = float(row[lat_col])
                            lon = float(row[lon_col])
                            coords[gid] = (lat, lon)
                        except (ValueError, TypeError):
                            continue
    except Exception as e:
        log.error("Peer finder gazetteer parse failed: %s", e)

    log.info("Peer finder: got %d coordinates from gazetteer.", len(coords))
    return coords


def _state_centroids() -> Dict[str, Tuple[float, float]]:
    """Approximate state centroids (lat, lon)."""
    return {
        "01": (32.7, -86.7), "02": (64.0, -153.0), "04": (34.3, -111.7),
        "05": (34.8, -92.2), "06": (37.2, -119.5), "08": (39.0, -105.5),
        "09": (41.6, -72.7), "10": (39.0, -75.5), "11": (38.9, -77.0),
        "12": (28.6, -82.4), "13": (32.7, -83.4), "15": (20.8, -156.3),
        "16": (44.4, -114.6), "17": (40.0, -89.2), "18": (39.8, -86.2),
        "19": (42.0, -93.5), "20": (38.5, -98.3), "21": (37.5, -85.3),
        "22": (31.0, -91.8), "23": (45.4, -69.2), "24": (39.0, -76.7),
        "25": (42.2, -71.8), "26": (44.3, -85.4), "27": (46.3, -94.3),
        "28": (32.7, -89.7), "29": (38.4, -92.5), "30": (47.1, -109.6),
        "31": (41.5, -99.8), "32": (39.3, -116.6), "33": (43.7, -71.6),
        "34": (40.1, -74.7), "35": (34.4, -106.1), "36": (42.9, -75.5),
        "37": (35.6, -79.4), "38": (47.5, -100.5), "39": (40.4, -82.8),
        "40": (35.6, -97.5), "41": (44.0, -120.5), "42": (40.9, -77.8),
        "44": (41.7, -71.5), "45": (33.9, -80.9), "46": (44.4, -100.2),
        "47": (35.9, -86.4), "48": (31.5, -99.3), "49": (39.3, -111.7),
        "50": (44.1, -72.6), "51": (37.5, -78.9), "53": (47.4, -120.5),
        "54": (38.6, -80.6), "55": (44.6, -89.7), "56": (43.0, -107.6),
        "72": (18.2, -66.4),
    }


def _fetch_ipeds_institutions(geo_type: str) -> Dict[str, Dict[str, int]]:
    """Count 4-year and 2-year institutions per geography using IPEDS HD file.

    Returns {geo_id: {"n_4year": int, "n_2year": int}}.
    """
    # IPEDS HD2023 (latest complete) — institutional characteristics
    ipeds_url = "https://nces.ed.gov/ipeds/datacenter/data/HD2023.zip"

    log.info("Peer finder: downloading IPEDS HD2023 ...")
    try:
        resp = request_with_retry("GET", ipeds_url, timeout=90)
    except Exception as e:
        log.error("Peer finder IPEDS download failed: %s", e)
        return {}

    try:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            csv_name = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]
            with zf.open(csv_name) as f:
                df = pd.read_csv(f, encoding="latin-1", dtype=str, low_memory=False)
    except Exception as e:
        log.error("Peer finder IPEDS parse failed: %s", e)
        return {}

    # ICLEVEL: 1=4-year, 2=2-year, 3=less-than-2-year
    # CBSA: CBSA code (for MSA/micro mapping)
    # COUNTYCD: 5-digit county FIPS
    # STABBR: state abbreviation
    # Filter to degree-granting, currently operating
    df = df[df.get("CYACTIVE", "1") != "2"]  # not closed

    results: Dict[str, Dict[str, int]] = {}

    if geo_type in ("msa", "micro"):
        id_col = "CBSA"
    elif geo_type == "county":
        id_col = "COUNTYCD"
    elif geo_type == "state":
        id_col = "STABBR"
    else:
        return {}

    if id_col not in df.columns or "ICLEVEL" not in df.columns:
        log.warning("Peer finder: IPEDS missing expected columns. Available: %s", df.columns[:20].tolist())
        return {}

    for _, row in df.iterrows():
        gid = str(row.get(id_col, "")).strip()
        if not gid or gid == "nan" or gid == "-2":
            continue

        # Convert state abbreviation to FIPS for state geo_type
        if geo_type == "state":
            from .utils import STATE_ABBR_TO_FIPS
            gid = STATE_ABBR_TO_FIPS.get(gid, "")
            if not gid:
                continue

        level = str(row.get("ICLEVEL", "")).strip()
        if gid not in results:
            results[gid] = {"n_4year": 0, "n_2year": 0}
        if level == "1":
            results[gid]["n_4year"] += 1
        elif level == "2":
            results[gid]["n_2year"] += 1

    log.info("Peer finder: counted institutions for %d geographies.", len(results))
    return results


def _fetch_place_populations(year: int) -> Dict[str, float]:
    """Fetch principal city population for MSAs.

    Returns {cbsa_code: city_population} by matching the first city name
    in the MSA name to Census place data.
    """
    # This is expensive — fetch places for all states
    yr = _acs_year("place", year)
    ds = "acs5"
    base_url = f"https://api.census.gov/data/{yr}/acs/{ds}"

    params = {
        "get": "NAME,B01003_001E",
        "for": "place:*",
        "in": "state:*",
    }
    if CENSUS_API_KEY:
        params["key"] = CENSUS_API_KEY

    log.info("Peer finder: fetching all place populations (%s %d) ...", ds, yr)
    try:
        resp = request_with_retry("GET", base_url, params=params, timeout=120)
        data = resp.json()
    except Exception as e:
        log.error("Peer finder place population fetch failed: %s", e)
        return {}

    if not isinstance(data, list) or len(data) < 2:
        return {}

    header, *rows = data

    # Build {normalized_name: population}
    place_pops: Dict[str, float] = {}
    for row in rows:
        d = dict(zip(header, row))
        name = d.get("NAME", "")
        # Normalize: "Baton Rouge city, Louisiana" → "baton rouge"
        city_name = name.split(",")[0].strip()
        # Remove suffixes like "city", "town", "village", "CDP"
        city_name = re.sub(r"\s+(city|town|village|CDP|borough|municipality)$", "", city_name, flags=re.IGNORECASE)
        city_name = city_name.lower().strip()
        try:
            pop = float(d.get("B01003_001E", 0))
            if pop > 0:
                # Keep largest if duplicate names
                if city_name not in place_pops or pop > place_pops[city_name]:
                    place_pops[city_name] = pop
        except (ValueError, TypeError):
            pass

    return place_pops


def _match_principal_city(metro_name: str, place_pops: Dict[str, float]) -> Optional[float]:
    """Extract principal city name from MSA name and look up population."""
    # "Baton Rouge, LA Metro Area" → "Baton Rouge"
    # "Dallas-Fort Worth-Arlington, TX Metro Area" → "Dallas"
    city_part = metro_name.split(",")[0].strip()
    first_city = city_part.split("-")[0].strip().lower()
    return place_pops.get(first_city)


def _compute_drive_times(
    df: pd.DataFrame,
    coords: Dict[str, Tuple[float, float]],
) -> pd.Series:
    """Compute estimated drive hours to nearest 500k+ metro for each geography."""
    # Identify large metros (500k+ pop)
    large = df[df["population"].fillna(0) >= _POP_LARGE_METRO]
    large_coords = []
    for gid in large["geo_id"]:
        if gid in coords:
            large_coords.append((gid, coords[gid]))

    if not large_coords:
        return pd.Series(dtype=float, index=df.index)

    def _nearest_drive(geo_id):
        if geo_id not in coords:
            return None
        lat1, lon1 = coords[geo_id]
        min_hours = float("inf")
        for lg_id, (lat2, lon2) in large_coords:
            if lg_id == geo_id:
                continue
            miles = haversine_miles(lat1, lon1, lat2, lon2)
            # Road factor 1.3, average 60 mph
            hours = (miles * 1.3) / 60.0
            if hours < min_hours:
                min_hours = hours
        return round(min_hours, 1) if min_hours < float("inf") else None

    return df["geo_id"].map(_nearest_drive)


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def assemble_peer_data(geo_type: str, year: int) -> pd.DataFrame:
    """Orchestrate all data fetches into a single peer DataFrame."""
    log.info("Peer finder: assembling data for %s year=%d ...", geo_type, year)

    # Run independent fetches in parallel
    with ThreadPoolExecutor(max_workers=4) as pool:
        f_demo = pool.submit(_fetch_all_demographics, geo_type, year)
        f_prior = pool.submit(_fetch_prior_population, geo_type, year)
        f_coords = pool.submit(_fetch_gazetteer_coords, geo_type)

        # Only fetch IPEDS for types that support it
        f_ipeds = None
        if geo_type in ("msa", "county", "state"):
            f_ipeds = pool.submit(_fetch_ipeds_institutions, geo_type)

        # Only fetch place pops for MSA
        f_places = None
        if geo_type == "msa":
            f_places = pool.submit(_fetch_place_populations, year)

    df = f_demo.result()
    if df.empty:
        return df

    # Merge prior population → growth %
    prior_pop = f_prior.result()
    if prior_pop:
        df["pop_growth_pct"] = df.apply(
            lambda r: round(((r["population"] - prior_pop[r["geo_id"]]) / prior_pop[r["geo_id"]]) * 100, 1)
            if r["geo_id"] in prior_pop and prior_pop[r["geo_id"]] > 0 and r["population"] is not None
            else None,
            axis=1,
        )
    else:
        df["pop_growth_pct"] = None

    # Merge coordinates
    coords = f_coords.result()

    # Merge IPEDS
    if f_ipeds:
        ipeds = f_ipeds.result()
        df["n_4year"] = df["geo_id"].map(lambda g: ipeds.get(g, {}).get("n_4year"))
        df["n_2year"] = df["geo_id"].map(lambda g: ipeds.get(g, {}).get("n_2year"))
    else:
        df["n_4year"] = None
        df["n_2year"] = None

    # Merge principal city population (MSA only)
    if f_places and geo_type == "msa":
        place_pops = f_places.result()
        df["city_pop"] = df["geo_name"].map(lambda n: _match_principal_city(n, place_pops))
    else:
        df["city_pop"] = None

    # Compute drive times
    if geo_type in ("msa", "county", "micro"):
        df["drive_hours"] = _compute_drive_times(df, coords)
    else:
        df["drive_hours"] = None

    log.info("Peer finder: assembled %d %s records.", len(df), geo_type)
    return df


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

_cache: Dict[Tuple[str, int], Dict[str, Any]] = {}
_CACHE_TTL = 6 * 3600  # 6 hours


def get_peer_data(geo_type: str, year: int) -> pd.DataFrame:
    """Get peer data with caching."""
    key = (geo_type, year)
    now = time.time()
    cached = _cache.get(key)
    if cached and (now - cached["ts"]) < _CACHE_TTL:
        return cached["df"]

    df = assemble_peer_data(geo_type, year)
    if not df.empty:
        _cache[key] = {"df": df, "ts": now}
    return df


def is_cached(geo_type: str, year: int) -> bool:
    """Check if peer data is already cached."""
    key = (geo_type, year)
    cached = _cache.get(key)
    if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
        return True
    return False


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def get_dimensions_for_geo_type(geo_type: str) -> List[Dict[str, str]]:
    """Return available dimensions for a geo type."""
    result = []
    for key, dim in DIMENSIONS.items():
        if dim["geo_types"] is None or geo_type in dim["geo_types"]:
            result.append({"key": key, "label": dim["label"]})
    return result


def rank_peers(
    df: pd.DataFrame,
    target_id: str,
    dimensions: List[str],
    weight_profile: str = "balanced",
) -> Tuple[Optional[Dict], List[Dict], List[str]]:
    """Score and rank peers by similarity to target.

    Returns (target_info, peers_list, warnings).
    """
    warnings = []
    weights = WEIGHT_PROFILES.get(weight_profile, WEIGHT_PROFILES["balanced"])

    if target_id not in df["geo_id"].values:
        return None, [], [f"Target geography {target_id} not found in dataset."]

    target_row = df[df["geo_id"] == target_id].iloc[0]

    # Build target values dict
    target_values = {}
    for dim_key in dimensions:
        dim = DIMENSIONS.get(dim_key)
        if not dim:
            continue
        col = dim["col"]
        val = target_row.get(col)
        if val is not None and not (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
            target_values[dim_key] = float(val)

    # Filter out dimensions where target has no data
    active_dims = [d for d in dimensions if d in target_values]
    if not active_dims:
        return None, [], ["Target has no valid data for selected dimensions."]

    dropped = set(dimensions) - set(active_dims)
    if dropped:
        labels = [DIMENSIONS[d]["label"] for d in dropped if d in DIMENSIONS]
        warnings.append(f"Dimensions excluded (no target data): {', '.join(labels)}")

    # Score all non-target rows
    others = df[df["geo_id"] != target_id].copy()

    def _score(row):
        total_weight = 0
        weighted_diff = 0
        for dim_key in active_dims:
            col = DIMENSIONS[dim_key]["col"]
            val = row.get(col)
            if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
                continue
            target_val = target_values[dim_key]
            if target_val == 0:
                # Avoid division by zero — use absolute diff
                diff = abs(float(val))
            else:
                diff = abs(float(val) - target_val) / abs(target_val)
            w = weights.get(dim_key, 1)
            weighted_diff += diff * w
            total_weight += w
        if total_weight == 0:
            return None
        return round((weighted_diff / total_weight) * 100, 2)

    others["similarity"] = others.apply(_score, axis=1)
    others = others.dropna(subset=["similarity"])
    others = others.sort_values("similarity")

    # Build target info
    target_info = {
        "geo_id": target_id,
        "geo_name": target_row["geo_name"],
        "values": {},
    }
    for dim_key in active_dims:
        col = DIMENSIONS[dim_key]["col"]
        val = target_row.get(col)
        if val is not None and not (isinstance(val, float) and np.isnan(val)):
            target_info["values"][dim_key] = float(val)

    # Build peers list
    peers = []
    for rank, (_, row) in enumerate(others.iterrows(), 1):
        peer = {
            "rank": rank,
            "geo_id": row["geo_id"],
            "geo_name": row["geo_name"],
            "similarity": row["similarity"],
            "values": {},
        }
        for dim_key in active_dims:
            col = DIMENSIONS[dim_key]["col"]
            val = row.get(col)
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                peer["values"][dim_key] = float(val)
        peers.append(peer)

    return target_info, peers, warnings
