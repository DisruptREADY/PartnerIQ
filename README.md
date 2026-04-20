# Data Portal — V2.1

A full-stack regional economic data explorer that pulls, visualizes, and exports indicators from federal data sources across multiple U.S. geography levels. Built with FastAPI and Svelte.

**Live deployment:** Hosted on [Render](https://render.com) — pushes to `master` trigger automatic deploys.

---

## Features

### Data Sources

| Source | Agency | Coverage |
|--------|--------|----------|
| **ACS** | Census Bureau | 1-year (2010-2024, excl. 2020) and 5-year (2010-2023) estimates |
| **BLS** | Bureau of Labor Statistics | CES nonfarm jobs, LAUS unemployment, OEWS occupations (2010-2025) |
| **BEA** | Bureau of Economic Analysis | GDP (CAGDP2), Regional Price Parities (2010-2024) |
| **FRED** | Federal Reserve (St. Louis) | House Price Index, building permits (2010-2024) |
| **PEP** | Census Population Estimates | Population, births, deaths, migration (2010-2023) |
| **COLI** | C2ER | Cost of Living Index, Q3 2025 (static file) |
| **CPI** | BLS via FRED | CPI-U annual averages for inflation adjustment |

### Geography Levels

- **Metropolitan Statistical Areas (MSAs)** — ~390 metros
- **Micropolitan Statistical Areas** — ~550 micros
- **States** — 50 states + DC
- **Counties** — ~3,200 counties
- **Census Places** — ~30,000 cities/towns (state-filtered, ACS indicators only)

### 75+ Indicators Across 14 Categories

Demographics, Age, Race/Ethnicity, Income, Poverty, Educational Attainment, Industry, Employment, Housing, Housing Type, Migration, Quality of Life, Cost of Living, Economy

### Views

- **Data Pull** — Multi-geography, multi-indicator table with YoY changes, sortable columns, and ranked values
- **Dashboard** — Single-geography KPI cards with sparklines, trend charts, education/age breakdowns
- **Chart** — Bar and line charts with selectable year ranges
- **Map** — Choropleth map (MapLibre GL) colored by any selected indicator
- **Comparison** — Side-by-side metro comparison cards
- **Industry Breakdown** — BLS CES employment by NAICS sector
- **Occupation Breakdown** — BLS OEWS employment and wages by SOC group

### Data Adjustments

- **COLI adjustment** — Divide monetary indicators by local cost of living (MSAs only)
- **Inflation adjustment** — Convert to constant dollars using CPI-U with selectable base year

### Export

- Copy table to clipboard (CSV format)
- Download as formatted Excel workbook with data, YoY changes, and methodology notes

---

## Tech Stack

### Backend

- **FastAPI** 0.115 — async REST API
- **uvicorn** — ASGI server
- **pandas** — data merging, YoY calculations, ranking
- **requests** — HTTP calls to Census, BLS, BEA, FRED APIs
- **openpyxl** — styled Excel export

### Frontend

- **Svelte** 5 — reactive UI components
- **Vite** 7 — dev server and bundler
- **Chart.js** 4.5 — bar/line charts, sparklines
- **MapLibre GL** 4.7 — vector choropleth maps (CARTO basemap, no API key required)

---

## Project Structure

```
data_portal/
├── backend/
│   ├── main.py              # FastAPI app, static file serving, route mounting
│   ├── config.py            # Indicator registry (75+ indicators), API keys, year ranges
│   ├── cache.py             # In-memory cache with TTL
│   ├── jobs.py              # Long-running fetch job tracking
│   ├── cpi.py               # CPI-U annual averages from FRED
│   ├── coli.py              # COLI Excel loader with CBSA fuzzy-matching
│   ├── utils.py             # Retry logic, derived indicators, YoY computation
│   ├── fetchers/
│   │   ├── census.py        # ACS 1-year and 5-year data
│   │   ├── bls.py           # CES (nonfarm jobs) + LAUS (unemployment)
│   │   ├── bea.py           # CAGDP2 GDP, Regional Price Parities
│   │   ├── fred.py          # HPI, building permits
│   │   ├── oews.py          # Occupational employment and wage statistics
│   │   └── pep.py           # Population Estimates Program
│   └── routers/
│       ├── geography.py     # /api/geographies — metro/micro/state/county/place lists
│       ├── indicators.py    # /api/indicators — metadata, categories, year availability
│       ├── data.py          # /api/data — main fetch endpoint, merges all sources
│       ├── export.py        # /api/export/xlsx — Excel workbook download
│       └── breakdown.py     # /api/breakdown/* — industry and occupation breakdowns
├── frontend/
│   ├── src/
│   │   ├── App.svelte       # Root component: navigation, fetch orchestration
│   │   ├── stores.js        # Svelte stores: selections, results, UI state, URL sync
│   │   ├── lib/
│   │   │   ├── theme.css            # CSS custom properties, brand colors, fonts
│   │   │   ├── LandingPage.svelte   # Welcome page with navigation cards
│   │   │   ├── Dashboard.svelte     # KPI cards, trend charts, age/education breakdowns
│   │   │   ├── KPICard.svelte       # Single metric card with sparkline
│   │   │   ├── TrendChart.svelte    # Small line chart for dashboard sections
│   │   │   ├── PopulationPyramid.svelte  # Age distribution horizontal bars
│   │   │   ├── GeoPicker.svelte     # Geography search, tabs, 40-peers quick-select
│   │   │   ├── IndicatorPanel.svelte # Indicator categories, checkboxes, search bar
│   │   │   ├── YearPicker.svelte    # Year checkboxes, ACS 1yr/5yr toggle, quick ranges
│   │   │   ├── DataTable.svelte     # Sortable results table with highlighting
│   │   │   ├── ChartPanel.svelte    # Chart.js bar/line with year selectors
│   │   │   ├── MapView.svelte       # MapLibre choropleth with indicator dropdown
│   │   │   ├── DashboardMap.svelte  # Embedded dashboard map (single-geo context)
│   │   │   ├── ComparisonView.svelte # Side-by-side geography cards
│   │   │   ├── ExportBar.svelte     # Clipboard copy, Excel download
│   │   │   ├── IndustryBreakdown.svelte   # CES industry employment table + chart
│   │   │   ├── OccupationBreakdown.svelte # OEWS occupation table + chart
│   │   │   ├── chartDefaults.js     # Shared Chart.js config (fonts, tooltips, palette)
│   │   │   └── DataNotes.svelte     # Source descriptions, methodology notes
│   │   └── public/geo/             # GeoJSON boundary files (states, CBSAs, counties)
│   ├── package.json
│   └── vite.config.js       # Dev proxy: /api → localhost:8000
├── build.sh                 # Production build script (pip + npm)
├── render.yaml              # Render.com deployment config
├── requirements.txt         # Python dependencies
└── .gitignore
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- API keys for: Census Bureau, BLS, BEA, FRED

### Environment Variables

Create a `.env` file in the project root (or export these in your shell):

```
CENSUS_API_KEY=your_key
BLS_API_KEY=your_key
BEA_API_KEY=your_key
FRED_API_KEY=your_key
```

API key sources:
- Census: https://api.census.gov/data/key_signup.html
- BLS: https://data.bls.gov/registrationEngine/
- BEA: https://apps.bea.gov/API/signup/
- FRED: https://fred.stlouisfed.org/docs/api/api_key.html

### Development

**Terminal 1 — Backend:**
```bash
cd data_portal
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd data_portal/frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api/*` requests to the backend at port 8000.

### Production Build

```bash
bash build.sh
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

The built frontend is served as static files by FastAPI. No separate web server needed.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/geographies?type=msa` | List geographies by type (msa, micro, state, county, place) |
| GET | `/api/indicators` | All indicator metadata (labels, categories, years, formats) |
| GET | `/api/indicators/categories` | Ordered category list |
| POST | `/api/data` | Fetch indicator data for selected geos, indicators, years |
| GET | `/api/jobs/{job_id}` | Poll long-running fetch status |
| POST | `/api/export/xlsx` | Download formatted Excel workbook |
| GET | `/api/cpi` | CPI-U annual averages |
| GET | `/api/coli` | Cost of Living Index by CBSA |
| POST | `/api/breakdown/industry-data` | CES industry employment breakdown |
| POST | `/api/breakdown/occupation` | OEWS occupation breakdown |
| GET | `/api/cache/stats` | Cache hit/miss statistics |
| GET | `/api/cache/clear` | Clear all cached data |

### POST /api/data — Request Body

```json
{
  "geo_ids": ["12940", "26380"],
  "indicator_keys": ["population", "median_hh_income", "unemployment_rate"],
  "years": [2022, 2023, 2024],
  "geo_type": "msa",
  "acs_dataset": "acs1",
  "include_yoy": true,
  "coli_adjust": false,
  "inflation_adjust": false,
  "inflation_base_year": null
}
```

---

## Deployment

The app deploys to Render as a single Python web service. Configuration is in `render.yaml`:

- **Runtime:** Python 3.11, Node 20
- **Build:** `bash build.sh` (installs Python deps, builds Svelte frontend)
- **Start:** `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- **Environment:** Set the four API keys in Render's environment variable settings

Pushes to the `master` branch on GitHub trigger automatic rebuilds and deploys.

---

## Key Design Decisions

- **No database** — all data is fetched live from federal APIs and cached in memory. This keeps the app stateless and ensures data is always current.
- **Multi-source merge** — the `/api/data` endpoint routes indicator requests to the appropriate fetcher (Census, BLS, BEA, FRED, PEP), fetches in parallel, and merges results into a single table keyed by geography and year.
- **Derived indicators** — poverty rate, GDP per capita, and domestic in-migration rate are computed from raw API values after fetch, not stored separately.
- **ACS dataset toggle** — users choose between ACS 1-year (more current, larger geos only) and 5-year (all geos, more reliable) estimates. The toggle affects only Census ACS indicators.
- **GDP from BEA** — GDP uses the BEA Regional CAGDP2 table (all industry total) rather than FRED series. BEA natively supports MSA, state, and county aggregation levels.
- **URL state sync** — all selections (geos, indicators, years, view mode, adjustments) are encoded in URL query parameters for shareable links.
- **Static COLI** — Cost of Living Index is loaded from a quarterly Excel file (C2ER Q3 2025) and fuzzy-matched to CBSA codes at startup. Updated by replacing the Excel file.
