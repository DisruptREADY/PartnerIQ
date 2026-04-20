"""Data router — orchestrates fetchers and returns merged results."""
import asyncio
import logging
import math
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..config import (
    INDICATORS, CENSUS_YEARS, CENSUS_5YR_YEARS, BLS_YEARS, BEA_YEARS, FRED_YEARS,
    PEP_YEARS, QCEW_YEARS,
)
from ..fetchers.census import fetch_census
from ..fetchers.bls import fetch_bls
from ..fetchers.bea import fetch_bea
from ..fetchers.fred import fetch_fred
from ..routers.geography import get_metros
from ..utils import build_cbsa_to_state_fips, compute_derived, compute_yoy_changes
from ..cache import get_cached, set_cached
from ..coli import get_coli_data
from ..cpi import get_cpi_table

log = logging.getLogger("data_portal")
router = APIRouter()

SOURCE_YEARS = {
    "census": CENSUS_YEARS,
    "bls": BLS_YEARS,
    "bea": BEA_YEARS,
    "fred": FRED_YEARS,
    "pep": PEP_YEARS,
    "qcew": QCEW_YEARS,
    "derived": CENSUS_YEARS,
}


class DataRequest(BaseModel):
    cbsas: List[str] = []
    geo_ids: List[str] = []
    indicators: List[str]
    years: List[int]
    geo_type: str = "msa"
    acs_dataset: str = "acs1"  # "acs1" or "acs5"
    coli_adjust: bool = False
    inflation_adjust: bool = False
    inflation_base_year: Optional[int] = None


def _is_monetary(fmt: str) -> bool:
    """Check if an indicator format represents monetary values."""
    return fmt.startswith("$") if fmt else False


@router.post("/data")
async def fetch_data(req: DataRequest):
    """Fetch selected data: routes indicators to correct fetcher, merges results."""
    geo_ids = req.geo_ids or req.cbsas
    if not geo_ids:
        raise HTTPException(400, "No geographies selected.")
    if not req.indicators:
        raise HTTPException(400, "No indicators selected.")
    if not req.years:
        raise HTTPException(400, "No years selected.")

    # Build cache key including adjustment params
    cache_extra = ""
    if req.coli_adjust:
        cache_extra += "_coli"
    if req.inflation_adjust and req.inflation_base_year:
        cache_extra += f"_infl{req.inflation_base_year}"

    # Check cache first
    cached = get_cached(geo_ids, req.indicators, req.years, req.geo_type,
                        req.acs_dataset + cache_extra)
    if cached:
        return cached

    # Build source-year map dynamically based on ACS dataset choice
    census_years = CENSUS_5YR_YEARS if req.acs_dataset == "acs5" else CENSUS_YEARS
    source_years = {
        "census": census_years,
        "bls": BLS_YEARS,
        "bea": BEA_YEARS,
        "fred": FRED_YEARS,
        "pep": PEP_YEARS,
        "qcew": QCEW_YEARS,
        "coli": list(range(2010, 2026)),  # static data, any year is valid
        "derived": census_years,
    }

    # Year validation per source — warn about excluded years
    warnings = []
    for ind_key in req.indicators:
        meta = INDICATORS.get(ind_key)
        if not meta:
            continue
        source = meta["source"]
        available = set(source_years.get(source, []))
        excluded = [y for y in req.years if y not in available]
        if excluded:
            warnings.append(
                f"{meta['label']} ({source}): no data for year(s) {', '.join(map(str, sorted(excluded)))}"
            )

    if req.geo_type == "msa":
        all_metros = get_metros()
        geos = {c: all_metros[c] for c in geo_ids if c in all_metros}
        if not geos:
            raise HTTPException(400, "None of the selected CBSAs were found.")
    elif req.geo_type == "micro":
        from ..routers.geography import get_micros
        all_micros = get_micros()
        geos = {c: all_micros[c] for c in geo_ids if c in all_micros}
        if not geos:
            raise HTTPException(400, "None of the selected micropolitan areas were found.")
    elif req.geo_type == "state":
        from ..routers.geography import get_states
        all_states = get_states()
        geos = {s: all_states[s] for s in geo_ids if s in all_states}
        if not geos:
            raise HTTPException(400, "None of the selected states were found.")
    elif req.geo_type == "county":
        from ..routers.geography import get_counties
        all_counties = get_counties()
        geos = {c: all_counties[c] for c in geo_ids if c in all_counties}
        if not geos:
            raise HTTPException(400, "None of the selected counties were found.")
    elif req.geo_type == "place":
        from ..routers.geography import get_places
        all_places = get_places()
        geos = {p: all_places[p] for p in geo_ids if p in all_places}
        if not geos:
            raise HTTPException(400, "None of the selected places were found.")
    else:
        raise HTTPException(400, f"Unsupported geo_type: {req.geo_type}")

    # Expand derived indicators to include their required components (recursive)
    expanded = set(req.indicators)
    queue = list(req.indicators)
    while queue:
        ind_key = queue.pop()
        meta = INDICATORS.get(ind_key)
        if meta and meta["source"] == "derived":
            for dep in meta.get("requires", []):
                if dep not in expanded:
                    expanded.add(dep)
                    queue.append(dep)
    all_keys = list(expanded)

    # Filter indicators by geo_type support
    supported_keys = []
    for k in all_keys:
        meta = INDICATORS.get(k)
        if not meta:
            continue
        geo_types = meta.get("geo_types")
        if geo_types and req.geo_type not in geo_types:
            continue
        supported_keys.append(k)
    all_keys = supported_keys

    # Route indicators to fetchers by source
    census_keys = [k for k in all_keys if INDICATORS.get(k, {}).get("source") == "census"]
    bls_keys = [k for k in all_keys if INDICATORS.get(k, {}).get("source") == "bls"]
    bea_keys = [k for k in all_keys if INDICATORS.get(k, {}).get("source") == "bea"]
    fred_keys = [k for k in all_keys if INDICATORS.get(k, {}).get("source") == "fred"]
    pep_keys = [k for k in all_keys if INDICATORS.get(k, {}).get("source") == "pep"]
    qcew_keys = [k for k in all_keys if INDICATORS.get(k, {}).get("source") == "qcew"]

    # Build coroutines for parallel execution
    fetch_tasks = []
    task_labels = []

    if census_keys:
        fetch_tasks.append(fetch_census(geos, census_keys, req.years, geo_type=req.geo_type, acs_dataset=req.acs_dataset))
        task_labels.append("Census ACS")

    if bls_keys:
        if req.geo_type == "msa":
            all_for_state = get_metros()
        elif req.geo_type == "micro":
            from ..routers.geography import get_micros
            all_for_state = get_micros()
        else:
            all_for_state = geos
        cbsa_to_state = build_cbsa_to_state_fips(all_for_state)
        fetch_tasks.append(fetch_bls(geos, cbsa_to_state, bls_keys, req.years, geo_type=req.geo_type))
        task_labels.append("BLS")

    if bea_keys:
        fetch_tasks.append(fetch_bea(geos, bea_keys, req.years, geo_type=req.geo_type))
        task_labels.append("BEA")

    if fred_keys:
        fetch_tasks.append(fetch_fred(geos, fred_keys, req.years, geo_type=req.geo_type))
        task_labels.append("FRED")

    if pep_keys:
        from ..fetchers.pep import fetch_pep
        fetch_tasks.append(fetch_pep(geos, pep_keys, req.years, geo_type=req.geo_type))
        task_labels.append("Census PEP")

    if qcew_keys:
        from ..fetchers.qcew import fetch_qcew
        fetch_tasks.append(fetch_qcew(geos, req.years, geo_type=req.geo_type))
        task_labels.append("BLS QCEW")

    # Run all fetchers concurrently — one failure won't cancel others
    fetch_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

    frames: List[pd.DataFrame] = []
    for result, label in zip(fetch_results, task_labels):
        if isinstance(result, Exception):
            log.error("%s fetcher failed: %s", label, result)
            warnings.append(f"{label} returned no data — the API may be temporarily unavailable.")
        elif not result.empty:
            frames.append(result)
        else:
            warnings.append(f"{label} returned no data — the API may be temporarily unavailable.")

    # Handle COLI source (static data, not year-based)
    coli_keys = [k for k in all_keys if INDICATORS.get(k, {}).get("source") == "coli"]
    if coli_keys and req.geo_type == "msa":
        coli_data = get_coli_data()
        coli_rows = []
        for geo_id in geo_ids:
            coli_entry = coli_data.get(geo_id)
            if coli_entry:
                for year in req.years:
                    row = {"CBSA": geo_id, "Year": year}
                    if "coli_composite" in coli_keys:
                        row["coli_composite"] = coli_entry.get("composite")
                    coli_rows.append(row)
        if coli_rows:
            df = pd.DataFrame(coli_rows)
            df["CBSA"] = df["CBSA"].astype(str)
            frames.append(df)

    if not frames:
        if warnings:
            warnings.insert(0, "All data sources failed or returned empty results.")
        result = {"columns": [], "rows": [], "yoy": {}, "warnings": warnings}
        # Don't cache failures — they should be retried
        return JSONResponse(content=result, status_code=503 if warnings else 200)

    # Merge all source DataFrames
    merged = frames[0]
    for other in frames[1:]:
        merged = merged.merge(other, on=["CBSA", "Year"], how="outer")

    # Compute derived indicators
    merged = compute_derived(merged)

    # Apply COLI adjustment (MSA only, monetary indicators) — vectorized
    if req.coli_adjust and req.geo_type == "msa":
        coli_data = get_coli_data()
        monetary_cols = [k for k in merged.columns if k in INDICATORS and _is_monetary(INDICATORS[k].get("fmt", ""))]
        if monetary_cols:
            coli_factors = merged["CBSA"].map(
                lambda cbsa: (coli_data.get(str(cbsa), {}).get("composite") or 0) / 100.0
            )
            valid = coli_factors > 0
            for col in monetary_cols:
                mask = valid & merged[col].notna()
                merged.loc[mask, col] = merged.loc[mask, col] / coli_factors[mask]
            # Warn about metros missing COLI coverage
            missing_coli = sorted({
                geos.get(cbsa, cbsa)
                for cbsa in merged.loc[~valid, "CBSA"].unique()
                if cbsa in geos
            })
            if missing_coli:
                warnings.append(
                    f"COLI adjustment not applied to {len(missing_coli)} metro(s) without coverage: "
                    + ", ".join(missing_coli[:5])
                    + ("..." if len(missing_coli) > 5 else "")
                )

    # Apply inflation adjustment (monetary indicators) — vectorized
    if req.inflation_adjust and req.inflation_base_year:
        cpi_table = get_cpi_table()
        base_cpi = cpi_table.get(req.inflation_base_year)
        if base_cpi:
            monetary_cols = [k for k in merged.columns if k in INDICATORS and _is_monetary(INDICATORS[k].get("fmt", ""))]
            cpi_factors = merged["Year"].map(
                lambda yr: base_cpi / cpi_table.get(int(yr), 1) if cpi_table.get(int(yr)) else 0
            )
            valid = cpi_factors > 0
            for col in monetary_cols:
                mask = valid & merged[col].notna()
                merged.loc[mask, col] = merged.loc[mask, col] * cpi_factors[mask]
        else:
            warnings.append(f"CPI data not available for base year {req.inflation_base_year}")

    # Add geo name
    merged["Metro"] = merged["CBSA"].map(geos)

    # Select only requested indicator columns (drop hidden internal ones)
    output_cols = ["CBSA", "Metro", "Year"] + [
        k for k in req.indicators if k in merged.columns
    ]
    result_df = merged[[c for c in output_cols if c in merged.columns]]
    result_df = result_df.sort_values(["Year", "Metro"], na_position="last")

    # Geo-type-aware labels for identifier columns
    geo_col_labels = {
        "msa": {"CBSA": "CBSA", "Metro": "Metro"},
        "micro": {"CBSA": "CBSA", "Metro": "Micro"},
        "state": {"CBSA": "FIPS", "Metro": "State"},
        "county": {"CBSA": "FIPS", "Metro": "County"},
        "place": {"CBSA": "FIPS", "Metro": "Place"},
    }.get(req.geo_type, {})

    # Build column metadata with enriched fields
    indicators_meta = {}
    columns = []
    for col in result_df.columns:
        meta = INDICATORS.get(col)
        if meta:
            label = meta["label"]
            # Add adjustment suffixes to labels
            if _is_monetary(meta.get("fmt", "")):
                if req.coli_adjust and req.geo_type == "msa":
                    label += " (COLI-adjusted)"
                if req.inflation_adjust and req.inflation_base_year:
                    label += f" ({req.inflation_base_year}$)"
            columns.append({
                "key": col,
                "label": label,
                "source": meta.get("display_source", meta["source"]),
                "fmt": meta.get("fmt", ""),
                "higher_is": meta.get("higher_is", "neutral"),
                "change_type": meta.get("change_type", "pct"),
            })
            indicators_meta[col] = meta
        else:
            columns.append({"key": col, "label": geo_col_labels.get(col, col)})

    # Compute YoY changes
    yoy = compute_yoy_changes(result_df, indicators_meta)

    # Convert to row dicts, replacing NaN with None for JSON serialization
    rows = result_df.to_dict(orient="records")
    for row in rows:
        for k, v in row.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                row[k] = None

    response = {
        "columns": columns,
        "rows": rows,
        "yoy": yoy,
        "warnings": warnings,
    }

    # Cache the response
    set_cached(geo_ids, req.indicators, req.years, response, req.geo_type,
               req.acs_dataset + cache_extra)

    return JSONResponse(
        content=response,
        headers={"Cache-Control": "public, max-age=3600"},
    )
