"""One-time script to generate simplified GeoJSON boundary files for the map feature.

Requires: geopandas, shapely, pygris
Output: frontend/public/geo/{states,cbsas,counties}.geojson

Usage:
    python scripts/generate_geojson.py
"""
import os
import sys
from pathlib import Path

try:
    import geopandas as gpd
    from shapely.geometry import mapping
except ImportError:
    print("ERROR: geopandas and shapely required. Install with: pip install geopandas shapely pygris")
    sys.exit(1)

try:
    import pygris
except ImportError:
    print("ERROR: pygris required. Install with: pip install pygris")
    sys.exit(1)


OUTPUT_DIR = Path(__file__).parent.parent / "frontend" / "public" / "geo"
TOLERANCE = 0.005  # simplification tolerance in degrees (~500m)


def generate_states():
    """Generate simplified state boundaries."""
    print("Downloading state boundaries...")
    gdf = pygris.states(year=2023)
    gdf = gdf.to_crs("EPSG:4326")
    gdf = gdf[["GEOID", "NAME", "geometry"]].copy()
    gdf["geometry"] = gdf["geometry"].simplify(TOLERANCE, preserve_topology=True)
    out = OUTPUT_DIR / "states.geojson"
    gdf.to_file(out, driver="GeoJSON")
    size_kb = out.stat().st_size / 1024
    print(f"  -> {out} ({size_kb:.0f} KB, {len(gdf)} features)")


def generate_cbsas():
    """Generate simplified CBSA (metro/micro) boundaries."""
    print("Downloading CBSA boundaries...")
    gdf = pygris.core_based_statistical_areas(year=2023)
    gdf = gdf.to_crs("EPSG:4326")
    gdf = gdf[["GEOID", "NAME", "geometry"]].copy()
    gdf["geometry"] = gdf["geometry"].simplify(TOLERANCE, preserve_topology=True)
    out = OUTPUT_DIR / "cbsas.geojson"
    gdf.to_file(out, driver="GeoJSON")
    size_kb = out.stat().st_size / 1024
    print(f"  -> {out} ({size_kb:.0f} KB, {len(gdf)} features)")


def generate_counties():
    """Generate simplified county boundaries."""
    print("Downloading county boundaries...")
    gdf = pygris.counties(year=2023)
    gdf = gdf.to_crs("EPSG:4326")
    gdf = gdf[["GEOID", "NAME", "geometry"]].copy()
    gdf["geometry"] = gdf["geometry"].simplify(TOLERANCE, preserve_topology=True)
    out = OUTPUT_DIR / "counties.geojson"
    gdf.to_file(out, driver="GeoJSON")
    size_kb = out.stat().st_size / 1024
    print(f"  -> {out} ({size_kb:.0f} KB, {len(gdf)} features)")


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generate_states()
    generate_cbsas()
    generate_counties()
    print("\nDone! GeoJSON files ready for the map feature.")
