"""Indicators router — available indicator metadata."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..config import (
    INDICATORS, CENSUS_YEARS, CENSUS_5YR_YEARS, BLS_YEARS, BEA_YEARS, FRED_YEARS,
    PEP_YEARS, QCEW_YEARS, CATEGORY_ORDER,
)

router = APIRouter()

# Cache-Control for stable metadata endpoints (1 hour)
_CACHE_HEADERS = {"Cache-Control": "public, max-age=3600"}

YEAR_RANGES = {
    "census": CENSUS_YEARS,
    "bls": BLS_YEARS,
    "bea": BEA_YEARS,
    "fred": FRED_YEARS,
    "pep": PEP_YEARS,
    "qcew": QCEW_YEARS,
    "coli": [],  # static data, no year range
    "derived": CENSUS_YEARS,
}

YEAR_RANGES_5YR = {
    "census": CENSUS_5YR_YEARS,
    "bls": BLS_YEARS,
    "bea": BEA_YEARS,
    "fred": FRED_YEARS,
    "pep": PEP_YEARS,
    "qcew": QCEW_YEARS,
    "coli": [],
    "derived": CENSUS_5YR_YEARS,
}


@router.get("/indicators")
async def list_indicators():
    """Return indicator metadata with category and geo_type info."""
    result = []
    for key, meta in INDICATORS.items():
        if meta.get("hidden"):
            continue
        source = meta["source"]
        display_source = meta.get("display_source", source)
        entry = {
            "key": key,
            "label": meta["label"],
            "source": display_source,
            "category": meta["category"],
            "higher_is": meta.get("higher_is", "neutral"),
            "change_type": meta.get("change_type", "pct"),
            "available_years": YEAR_RANGES.get(source, []),
            "available_years_5yr": YEAR_RANGES_5YR.get(source, []),
            "geo_types": meta.get("geo_types"),
        }
        if "available_years_by_geo" in meta:
            entry["available_years_by_geo"] = meta["available_years_by_geo"]
        result.append(entry)
    return JSONResponse(content=result, headers=_CACHE_HEADERS)


@router.get("/indicators/categories")
async def list_categories():
    """Return ordered category list."""
    return JSONResponse(content=CATEGORY_ORDER, headers=_CACHE_HEADERS)
