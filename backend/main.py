"""FastAPI app — Data Portal backend."""
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import geography, indicators, data, export, breakdown, peers
from .cache import clear_cache, cache_stats
from .jobs import get_job
from .cpi import get_cpi_table
from .coli import get_coli_data

logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)

log = logging.getLogger("data_portal")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warm geography caches and static data on startup."""
    log.info("Pre-warming caches ...")
    await asyncio.gather(
        asyncio.to_thread(geography.get_metros),
        asyncio.to_thread(geography.get_micros),
        asyncio.to_thread(geography.get_states),
        asyncio.to_thread(geography.get_counties),
        asyncio.to_thread(geography.get_places),
        asyncio.to_thread(geography.get_cbsa_county_map),
        asyncio.to_thread(get_cpi_table),
        asyncio.to_thread(get_coli_data),
    )
    log.info("Caches ready.")
    yield


app = FastAPI(title="Data Portal API", version="2.0.0", lifespan=lifespan)

app.add_middleware(GZipMiddleware, minimum_size=1000)  # Compress responses > 1KB

_default_origins = [
    "http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:5176",
    "http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://127.0.0.1:5175", "http://127.0.0.1:5176",
]
_cors_origins = os.getenv("ALLOWED_ORIGINS", "").split(",") if os.getenv("ALLOWED_ORIGINS") else _default_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(geography.router, prefix="/api")
app.include_router(indicators.router, prefix="/api")
app.include_router(data.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(breakdown.router, prefix="/api")
app.include_router(peers.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/cpi")
async def api_cpi():
    """Return CPI-U annual averages for inflation adjustment."""
    from fastapi.responses import JSONResponse
    table = get_cpi_table()
    return JSONResponse(
        content={"years": sorted(table.keys()), "values": table},
        headers={"Cache-Control": "public, max-age=86400"},  # 24 hours
    )


@app.get("/api/coli")
async def api_coli():
    """Return COLI data by CBSA."""
    data = get_coli_data()
    return {"count": len(data), "data": data}


@app.get("/api/cache/clear")
async def api_clear_cache():
    clear_cache()
    return {"status": "cleared"}


@app.get("/api/cache/stats")
async def api_cache_stats():
    return cache_stats()


@app.get("/api/jobs/{job_id}")
async def api_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    # Don't send full result in status poll — client should fetch from /api/data
    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"],
        "error": job.get("error"),
        "has_result": job["result"] is not None,
    }


# In production, serve the built Svelte frontend as static files.
# The frontend is built to ../frontend/dist by `npm run build`.
_static_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _static_dir.is_dir():
    from starlette.middleware import Middleware
    from fastapi.responses import FileResponse

    # Serve hashed static assets with long-lived cache headers
    class CachedStaticFiles(StaticFiles):
        """StaticFiles subclass that adds Cache-Control for immutable hashed assets."""
        async def get_response(self, path, scope):
            response = await super().get_response(path, scope)
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return response

    app.mount("/assets", CachedStaticFiles(directory=_static_dir / "assets"), name="assets")

    # Serve GeoJSON/static data with moderate caching
    _geo_dir = _static_dir / "geo"
    if _geo_dir.is_dir():
        app.mount("/geo", CachedStaticFiles(directory=_geo_dir), name="geo")

    # Catch-all: serve index.html for any non-API route (SPA client-side routing)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Try to serve the exact file first (e.g. favicon.ico)
        file_path = _static_dir / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_static_dir / "index.html")

# Lambda handler (used by AWS Lambda + API Gateway)
try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    pass
