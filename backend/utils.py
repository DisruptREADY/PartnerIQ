"""Shared utilities: HTTP retry, CBSA-to-state-FIPS, derived indicators, YoY, ranks."""
import logging
import math
import time
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import requests

log = logging.getLogger("data_portal")

_EARTH_RADIUS_MILES = 3958.8


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles between two (lat, lon) points."""
    lat1, lon1, lat2, lon2 = (math.radians(v) for v in (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


STATE_ABBR_TO_FIPS: Dict[str, str] = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
    "CO": "08", "CT": "09", "DE": "10", "DC": "11", "FL": "12",
    "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18",
    "IA": "19", "KS": "20", "KY": "21", "LA": "22", "MA": "25",
    "MD": "24", "ME": "23", "MI": "26", "MN": "27", "MS": "28",
    "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "PR": "72",
    "RI": "44", "SC": "45", "SD": "46", "TN": "47", "TX": "48",
    "UT": "49", "VT": "50", "VA": "51", "WA": "53", "WV": "54",
    "WI": "55", "WY": "56",
}

FIPS_TO_STATE_ABBR: Dict[str, str] = {v: k for k, v in STATE_ABBR_TO_FIPS.items()}


def request_with_retry(
    method: str,
    url: str,
    retries: int = 3,
    sleep_s: float = 1.0,
    **kwargs,
) -> requests.Response:
    """HTTP request with exponential backoff."""
    kwargs.setdefault("timeout", 60)
    last_err: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            last_err = e
            if attempt < retries:
                wait = sleep_s * attempt
                log.warning(
                    "Attempt %d/%d failed for %s — retrying in %.1fs: %s",
                    attempt, retries, url[:80], wait, e,
                )
                time.sleep(wait)
    raise last_err


def build_cbsa_to_state_fips(metros: Dict[str, str]) -> Dict[str, str]:
    """Parse the principal state from metro name → {cbsa: state_fips}.

    BLS series IDs require a 2-digit state FIPS prefix. Extracts the first
    state abbreviation from the metro name (e.g., "Memphis, TN-MS-AR" -> "47").
    """
    mapping: Dict[str, str] = {}
    for cbsa, name in metros.items():
        parts = name.rsplit(",", 1)
        if len(parts) < 2:
            continue
        state_part = parts[1].strip()
        state_part = state_part.replace(" Metro Area", "").replace(" Micro Area", "").strip()
        first_state = state_part.split("-")[0].strip()
        fips = STATE_ABBR_TO_FIPS.get(first_state)
        if fips:
            mapping[cbsa] = fips
    return mapping


def compute_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived indicators: poverty_rate, gdp_per_capita, migration, edu_bachelors_plus_pct."""
    if "poverty_denominator" in df.columns and "poverty_below" in df.columns:
        denom = df["poverty_denominator"].replace({0: pd.NA})
        df["poverty_rate"] = (df["poverty_below"] / denom) * 100.0

    if "gdp" in df.columns and "population" in df.columns:
        pop = df["population"].replace({0: pd.NA})
        df["gdp_per_capita"] = (df["gdp"] * 1_000_000) / pop

    state_col = "migration_from_state"
    county_col = "migration_from_county"
    if state_col in df.columns and county_col in df.columns:
        df["in_migration"] = df[state_col].fillna(0) + df[county_col].fillna(0)
        both_null = df[state_col].isna() & df[county_col].isna()
        df.loc[both_null, "in_migration"] = pd.NA

    if state_col in df.columns:
        df["interstate_in_migration"] = df[state_col]

    to_state = "migration_to_state"
    to_county = "migration_to_county"
    if to_state in df.columns and to_county in df.columns:
        df["out_migration"] = df[to_state].fillna(0) + df[to_county].fillna(0)
        both_null = df[to_state].isna() & df[to_county].isna()
        df.loc[both_null, "out_migration"] = pd.NA

    if "in_migration" in df.columns and "out_migration" in df.columns:
        df["net_domestic_migration"] = df["in_migration"] - df["out_migration"]
        both_null = df["in_migration"].isna() & df["out_migration"].isna()
        df.loc[both_null, "net_domestic_migration"] = pd.NA

    if "edu_bachelors_plus" in df.columns and "pop_25_plus" in df.columns:
        denom = df["pop_25_plus"].replace({0: pd.NA})
        df["edu_bachelors_plus_pct"] = (df["edu_bachelors_plus"] / denom) * 100.0

    return df


def compute_yoy_changes(
    df: pd.DataFrame,
    indicators_meta: Dict[str, Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Compute year-over-year changes for each indicator.

    Returns {indicator_key: [{cbsa, year, prior_year, change, change_type}, ...]}.
    Uses change_type from indicator config: 'pct' for percentage change, 'pp' for
    percentage-point change.
    """
    yoy: Dict[str, List[Dict[str, Any]]] = {}

    if "CBSA" not in df.columns or "Year" not in df.columns:
        return yoy

    sorted_df = df.sort_values(["CBSA", "Year"])

    for ind_key, meta in indicators_meta.items():
        if ind_key not in df.columns:
            continue
        change_type = meta.get("change_type", "pct")
        records: List[Dict[str, Any]] = []

        for cbsa, group in sorted_df.groupby("CBSA"):
            group = group.sort_values("Year")
            years = group["Year"].values
            vals = group[ind_key].values

            for i in range(1, len(years)):
                cur = vals[i]
                prev = vals[i - 1]
                if cur is None or prev is None:
                    continue
                if isinstance(cur, float) and (np.isnan(cur) or np.isinf(cur)):
                    continue
                if isinstance(prev, float) and (np.isnan(prev) or np.isinf(prev)):
                    continue

                if change_type == "pp":
                    change = float(cur) - float(prev)
                else:  # pct
                    if float(prev) == 0:
                        continue
                    change = ((float(cur) - float(prev)) / abs(float(prev))) * 100.0

                records.append({
                    "cbsa": str(cbsa),
                    "year": int(years[i]),
                    "prior_year": int(years[i - 1]),
                    "change": round(change, 2),
                    "change_type": change_type,
                })

        yoy[ind_key] = records

    return yoy
