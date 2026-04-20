"""COLI (Cost of Living Index) data loader.

Loads COLI Q3 2025 data from Excel, maps proprietary city codes to CBSA codes.
COLI city code format: 10-digit (zero-padded), digits [2:7] = CBSA code.
For metros with multiple COLI sub-areas, averages the composite indices.
"""
import logging
import os
from pathlib import Path
from typing import Dict, Optional

log = logging.getLogger("data_portal")

# Column keys in order
COLI_CATEGORIES = [
    "composite", "grocery", "housing", "utilities",
    "transportation", "healthcare", "misc",
]

# Module-level cache
_coli_data: Optional[Dict[str, Dict[str, float]]] = None


def _load_coli() -> Dict[str, Dict[str, float]]:
    """Load COLI data from Excel file, map to CBSA codes."""
    try:
        import openpyxl
    except ImportError:
        log.error("openpyxl required for COLI data")
        return {}

    xlsx_path = Path(__file__).parent.parent / "COLI Data (Q3 2025)" / "COLI 2025 Q3.xlsx"
    if not xlsx_path.exists():
        log.warning("COLI data file not found: %s", xlsx_path)
        return {}

    log.info("Loading COLI data from %s", xlsx_path)
    wb = openpyxl.load_workbook(str(xlsx_path), read_only=True, data_only=True)
    ws = wb["2025 Q3 Index"]

    # Accumulate values per CBSA for averaging
    cbsa_values: Dict[str, list] = {}  # cbsa -> list of {category: value}

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i < 5:  # skip header rows
            continue

        city_code = row[0]
        if city_code is None:
            continue

        # Extract CBSA from city code: zero-pad to 10, take digits [2:7]
        try:
            code_str = str(int(city_code)).zfill(10)
        except (ValueError, TypeError):
            continue
        if len(code_str) < 7:
            continue
        cbsa = code_str[2:7]

        # Read the 7 index values
        try:
            values = {}
            for j, cat in enumerate(COLI_CATEGORIES):
                val = row[4 + j]
                if val is not None:
                    values[cat] = float(val)
        except (TypeError, ValueError):
            continue

        if not values.get("composite"):
            continue

        if cbsa not in cbsa_values:
            cbsa_values[cbsa] = []
        cbsa_values[cbsa].append(values)

    wb.close()

    # Average across sub-areas for each CBSA
    result: Dict[str, Dict[str, float]] = {}
    for cbsa, entries in cbsa_values.items():
        averaged = {}
        for cat in COLI_CATEGORIES:
            vals = [e[cat] for e in entries if cat in e]
            if vals:
                averaged[cat] = round(sum(vals) / len(vals), 1)
        if averaged.get("composite"):
            result[cbsa] = averaged

    log.info("Loaded COLI data for %d CBSAs", len(result))
    return result


def get_coli_data() -> Dict[str, Dict[str, float]]:
    """Get COLI data with lazy loading and caching."""
    global _coli_data
    if _coli_data is None:
        _coli_data = _load_coli()
    return _coli_data


def get_coli_composite(cbsa: str) -> Optional[float]:
    """Get COLI composite index for a CBSA. Returns None if not available."""
    data = get_coli_data()
    entry = data.get(cbsa)
    return entry["composite"] if entry else None
