"""Peer finder API router — find similar geographies."""
import asyncio
import logging
from typing import List

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..peers import (
    get_dimensions_for_geo_type,
    get_peer_data,
    is_cached,
    rank_peers,
)

log = logging.getLogger("data_portal")
router = APIRouter()

_VALID_GEO_TYPES = {"msa", "county", "state", "micro", "place"}
_VALID_PROFILES = {"balanced", "economic", "demographic", "geographic"}


class PeerRequest(BaseModel):
    geo_type: str = "msa"
    target_id: str
    dimensions: List[str]
    weight_profile: str = "balanced"
    year: int = 2024
    limit: int = 40


@router.get("/peers/dimensions")
async def peer_dimensions(
    geo_type: str = Query("msa", pattern="^(msa|county|state|micro|place)$"),
):
    """Return available dimensions for a geo type."""
    dims = get_dimensions_for_geo_type(geo_type)
    return {"geo_type": geo_type, "dimensions": dims}


@router.get("/peers/status")
async def peer_status(
    geo_type: str = Query("msa", pattern="^(msa|county|state|micro|place)$"),
    year: int = Query(2024),
):
    """Check if peer data is already cached (ready for instant results)."""
    return {"ready": is_cached(geo_type, year)}


@router.post("/peers")
async def find_peers(req: PeerRequest):
    """Find similar geographies to a target."""
    if req.geo_type not in _VALID_GEO_TYPES:
        return {"error": f"Invalid geo_type: {req.geo_type}"}
    if req.weight_profile not in _VALID_PROFILES:
        return {"error": f"Invalid weight_profile: {req.weight_profile}"}
    if not req.dimensions:
        return {"error": "At least one dimension is required."}

    # Fetch peer data (may be slow on first call)
    df = await asyncio.to_thread(get_peer_data, req.geo_type, req.year)

    if df.empty:
        return {"error": "Failed to fetch peer data. Please try again."}

    # Score and rank
    target_info, peers, warnings = rank_peers(
        df, req.target_id, req.dimensions, req.weight_profile,
    )

    if target_info is None:
        return {"error": warnings[0] if warnings else "Target not found."}

    # Apply limit
    peers = peers[:req.limit]

    # Build dimensions metadata for response
    dims_meta = []
    available = get_dimensions_for_geo_type(req.geo_type)
    avail_map = {d["key"]: d for d in available}
    for dk in req.dimensions:
        if dk in avail_map:
            dims_meta.append(avail_map[dk])

    return {
        "target": target_info,
        "peers": peers,
        "dimensions": dims_meta,
        "weight_profile": req.weight_profile,
        "warnings": warnings,
    }
