<script>
  import { onMount } from 'svelte';
  import { dashboardGeo, selectedGeoType } from '../stores.js';
  import KPICard from './KPICard.svelte';
  import TrendChart from './TrendChart.svelte';
  import PopulationPyramid from './PopulationPyramid.svelte';
  import DashboardMap from './DashboardMap.svelte';

  // All curated indicators for the dashboard
  const DASHBOARD_INDICATORS = [
    'population', 'median_hh_income', 'unemployment_rate', 'poverty_rate',
    'nonfarm_jobs', 'labor_force_participation', 'gdp_per_capita', 'median_rent',
    'median_home_value', 'homeownership_rate', 'median_age',
    'edu_less_than_hs', 'edu_hs_graduate', 'edu_some_college', 'edu_associates', 'edu_bachelors', 'edu_masters', 'edu_professional', 'edu_doctorate',
    'pop_under_5', 'pop_5_to_9', 'pop_10_to_14', 'pop_15_to_19', 'pop_20_to_24',
    'pop_25_to_34', 'pop_35_to_44', 'pop_45_to_54', 'pop_55_to_59', 'pop_60_to_64',
    'pop_65_to_74', 'pop_75_to_84', 'pop_85_plus',
  ];

  // Last 5 available years (skipping 2020 — ACS 1-year not published that year)
  const DASHBOARD_YEARS = [2019, 2021, 2022, 2023, 2024];

  // Geo type tabs
  const GEO_TYPES = [
    { key: 'msa', label: 'MSA' },
    { key: 'state', label: 'State' },
    { key: 'county', label: 'County' },
  ];

  let geoType = $selectedGeoType || 'msa';
  let allGeos = [];
  let allStates = [];
  let loadingGeos = true;
  let searchText = '';
  let stateFilter = '';
  let showDropdown = false;
  let selectedGeoObj = null;  // {id, name}

  let loading = false;
  let errorMsg = null;

  // Data storage
  let rawRows = [];
  let columns = [];
  let yoyData = {};
  let warnings = [];

  // Fetch geographies for current geo type
  async function fetchGeos(type) {
    loadingGeos = true;
    allGeos = [];
    allStates = [];
    try {
      const resp = await fetch(`/api/geographies?type=${type}`);
      if (resp.ok) {
        allGeos = await resp.json();
        // Extract state list for filtering
        if (type === 'county') {
          const states = new Set();
          allGeos.forEach(g => {
            const parts = g.name.split(',');
            if (parts.length >= 2) states.add(parts[parts.length - 1].trim());
          });
          allStates = [...states].sort();
        } else if (type === 'msa') {
          const states = new Set();
          allGeos.forEach(g => {
            const match = g.name.match(/,\s*([A-Z]{2}(?:-[A-Z]{2})*)/);
            if (match) match[1].split('-').forEach(s => states.add(s));
          });
          allStates = [...states].sort();
        }
      }
    } catch (e) {
      console.error('Failed to load geographies:', e);
    } finally {
      loadingGeos = false;
    }
  }

  function switchGeoType(type) {
    geoType = type;
    selectedGeoType.set(type);
    selectedGeoObj = null;
    dashboardGeo.set(null);
    searchText = '';
    stateFilter = '';
    rawRows = [];
    columns = [];
    yoyData = {};
    fetchGeos(type);
  }

  function metroMatchesState(name, stateAbbr) {
    const match = name.match(/,\s*([A-Z]{2}(?:-[A-Z]{2})*)/);
    if (!match) return false;
    return match[1].split('-').includes(stateAbbr);
  }

  // Filtered geo list: state filter + search text
  $: filtered = (() => {
    let pool = allGeos;
    if (stateFilter) {
      if (geoType === 'county') {
        pool = pool.filter(g => g.name.endsWith(', ' + stateFilter));
      } else if (geoType === 'msa') {
        pool = pool.filter(g => metroMatchesState(g.name, stateFilter));
      }
    }
    if (searchText.length > 0) {
      const q = searchText.toLowerCase();
      pool = pool.filter(g => g.name.toLowerCase().includes(q) || g.id.includes(searchText));
    }
    return pool.slice(0, 50);
  })();

  // Show dropdown: on focus for states/counties always; for MSAs when searching or state-filtered
  $: showResults = (() => {
    if (!showDropdown) return false;
    if (geoType === 'state') return filtered.length > 0;
    if (geoType === 'msa') return (searchText.length > 0 || stateFilter) && filtered.length > 0;
    if (geoType === 'county') return (searchText.length > 0 || stateFilter) && filtered.length > 0;
    return filtered.length > 0;
  })();

  // Auto-show dropdown when state filter changes
  $: if (stateFilter) showDropdown = true;

  function selectGeo(geo) {
    selectedGeoObj = geo;
    dashboardGeo.set(geo.id);
    searchText = '';
    showDropdown = false;
    fetchDashboardData(geo);
  }

  function handleBlur() {
    setTimeout(() => { showDropdown = false; }, 200);
  }

  // Fetch curated data for selected geo
  let dashController = null;
  async function fetchDashboardData(geo) {
    // Abort any in-flight request
    if (dashController) dashController.abort();
    dashController = new AbortController();
    const { signal } = dashController;

    loading = true;
    errorMsg = null;
    rawRows = [];
    columns = [];
    yoyData = {};
    warnings = [];

    try {
      const body = {
        geo_ids: [geo.id],
        indicators: DASHBOARD_INDICATORS,
        years: DASHBOARD_YEARS,
        geo_type: geoType,
        acs_dataset: 'acs1',
      };

      const resp = await fetch('/api/data', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal,
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${resp.status}`);
      }

      const data = await resp.json();
      rawRows = data.rows || [];
      columns = data.columns || [];
      yoyData = data.yoy || {};
      warnings = data.warnings || [];
    } catch (e) {
      if (e.name === 'AbortError') return;
      errorMsg = e.message;
    } finally {
      loading = false;
    }
  }

  // On mount: fetch geos (no auto-selection — start with a blank slate)
  onMount(async () => {
    dashboardGeo.set(null);
    await fetchGeos(geoType);
  });

  // --- Derived data helpers ---

  // Sort rawRows by year ascending once; all helpers read from this
  $: sortedAsc = [...rawRows].sort((a, b) => a.Year - b.Year);

  // Build a lookup: indicator key -> { value, year } for the latest non-null entry
  $: latestByKey = (() => {
    const map = {};
    // Walk ascending so later years overwrite earlier ones
    for (const row of sortedAsc) {
      for (const key of Object.keys(row)) {
        if (key === 'Year' || key === 'GeoName' || key === 'GeoFIPS') continue;
        if (row[key] != null) {
          map[key] = { value: row[key], year: row.Year };
        }
      }
    }
    return map;
  })();

  // Get latest year's value for an indicator
  function latestValue(key) {
    return latestByKey[key]?.value ?? null;
  }

  // Get latest year number for an indicator
  function latestYear(key) {
    return latestByKey[key]?.year ?? null;
  }

  // Get sparkline data: values sorted by year
  function sparkline(key) {
    return sortedAsc.map(r => r[key] ?? null);
  }

  // Get YoY change for an indicator
  // API yoyData structure: { indicator_key: [ {cbsa, year, prior_year, change, change_type} ] }
  function yoyChange(key) {
    if (!selectedGeoObj || !yoyData[key]) return null;
    const changes = yoyData[key];
    if (!Array.isArray(changes)) return null;

    // Find the latest year's change for this geo
    const geoChanges = changes
      .filter(c => c.cbsa === selectedGeoObj.id)
      .sort((a, b) => b.year - a.year);

    if (geoChanges.length === 0) return null;
    return geoChanges[0].change ?? null;
  }

  // Get column metadata
  function getColMeta(key) {
    return columns.find(c => c.key === key) || {};
  }

  // Build trend datasets for a set of indicator keys
  function buildTrendDatasets(keys, colors) {
    return keys.map((key, i) => {
      const meta = getColMeta(key);
      return {
        label: meta.label || key,
        data: sortedAsc
          .filter(r => r[key] != null)
          .map(r => ({ year: r.Year, value: r[key] })),
        color: colors[i % colors.length],
      };
    });
  }

  // --- KPI card configs ---
  const KPI_CONFIG = [
    { key: 'population',               label: 'Population',        fmt: '#,##0',   higherIs: 'neutral',  changeType: 'pct' },
    { key: 'median_hh_income',         label: 'Median HH Income',  fmt: '$#,##0',  higherIs: 'better',   changeType: 'pct' },
    { key: 'unemployment_rate',        label: 'Unemployment Rate',  fmt: '0.0%',    higherIs: 'worse',    changeType: 'pp' },
    { key: 'poverty_rate',             label: 'Poverty Rate',       fmt: '0.0%',    higherIs: 'worse',    changeType: 'pp' },
    { key: 'nonfarm_jobs',             label: 'Nonfarm Jobs (K)',   fmt: '#,##0.0', higherIs: 'better',   changeType: 'pct' },
    { key: 'labor_force_participation',label: 'LFPR',               fmt: '0.0%',    higherIs: 'better',   changeType: 'pp' },
    { key: 'gdp_per_capita',           label: 'GDP per Capita',     fmt: '$#,##0',  higherIs: 'better',   changeType: 'pct' },
    { key: 'median_rent',              label: 'Median Rent',        fmt: '$#,##0',  higherIs: 'neutral',  changeType: 'pct' },
  ];

  // --- Chart data ---
  $: econTrendDatasets = rawRows.length > 0 ? buildTrendDatasets(
    ['median_hh_income', 'gdp_per_capita'],
    ['#0E78BE', '#66AD6E']
  ) : [];

  $: jobsDatasets = rawRows.length > 0 ? buildTrendDatasets(
    ['nonfarm_jobs'],
    ['#0E78BE']
  ) : [];

  $: homeValueDatasets = rawRows.length > 0 ? buildTrendDatasets(
    ['median_home_value'],
    ['#6A3A84']
  ) : [];

  $: rentDatasets = rawRows.length > 0 ? buildTrendDatasets(
    ['median_rent'],
    ['#EC9952']
  ) : [];

  // Education horizontal bar data
  $: eduData = (() => {
    if (rawRows.length === 0) return [];
    const keys = ['edu_less_than_hs', 'edu_hs_graduate', 'edu_some_college', 'edu_associates', 'edu_bachelors', 'edu_masters', 'edu_professional', 'edu_doctorate'];
    const labels = ['Less than HS', 'HS / GED', 'Some College', "Associate's", "Bachelor's", "Master's", 'Professional', 'Doctorate'];
    return keys.map((key, i) => ({
      label: labels[i],
      value: latestValue(key),
    }));
  })();

  $: eduMaxVal = Math.max(...eduData.map(d => d.value || 0), 1);

  // Age pyramid data
  // Explicit rawRows reference so Svelte tracks the dependency
  $: ageData = (() => {
    const rows = rawRows;
    if (!rows.length) return {};
    const obj = {};
    const ageKeys = [
      'pop_under_5', 'pop_5_to_9', 'pop_10_to_14', 'pop_15_to_19', 'pop_20_to_24',
      'pop_25_to_34', 'pop_35_to_44', 'pop_45_to_54', 'pop_55_to_59', 'pop_60_to_64',
      'pop_65_to_74', 'pop_75_to_84', 'pop_85_plus',
    ];
    ageKeys.forEach(k => { obj[k] = latestValue(k); });
    return obj;
  })();

  function shortName(name) {
    if (!name) return '';
    return name.split(',')[0];
  }

  function formatNum(v) {
    if (v == null) return '—';
    return Number(v).toLocaleString('en-US');
  }
</script>

<div class="dashboard" id="main-content">
  <!-- Geo Selector -->
  <div class="geo-selector">
    <div class="selector-header">
      <span class="selector-label">Explore a Region</span>
      <div class="geo-tabs">
        {#each GEO_TYPES as gt}
          <button
            class="geo-tab"
            class:active={geoType === gt.key}
            on:click={() => switchGeoType(gt.key)}
          >
            {gt.label}
          </button>
        {/each}
      </div>
    </div>

    <div class="search-area">
      {#if allStates.length > 0}
        <div class="state-filter">
          <select bind:value={stateFilter}>
            <option value="">All states</option>
            {#each allStates as st}
              <option value={st}>{st}</option>
            {/each}
          </select>
        </div>
      {/if}

      <div class="search-wrapper">
        <input
          type="text"
          placeholder={loadingGeos ? 'Loading...' : `Search ${geoType === 'msa' ? 'metros' : geoType === 'state' ? 'states' : 'counties'}...`}
          bind:value={searchText}
          on:input={() => { showDropdown = true; }}
          on:focus={() => { showDropdown = true; }}
          on:blur={handleBlur}
          disabled={loadingGeos}
          role="combobox"
          aria-expanded={showResults}
          aria-controls="dash-geo-dropdown"
          aria-autocomplete="list"
        />
        {#if showResults}
          <ul class="dropdown" id="dash-geo-dropdown" role="listbox">
            {#each filtered as geo}
              <li role="option" aria-selected="false" on:mousedown={() => selectGeo(geo)}>
                <span class="geo-name">{geo.name}</span>
                <span class="geo-code">{geo.id}</span>
              </li>
            {/each}
            {#if filtered.length === 50}
              <li class="more-note">Showing first 50 — type to narrow results</li>
            {/if}
          </ul>
        {/if}
      </div>

      {#if selectedGeoObj}
        <div class="selected-geo-badge">
          <span class="badge-name">{selectedGeoObj.name}</span>
          <button class="badge-clear" on:click={() => { selectedGeoObj = null; dashboardGeo.set(null); rawRows = []; columns = []; }} aria-label="Clear selection">&times;</button>
        </div>
      {/if}
    </div>
  </div>

  <!-- Content Area -->
  {#if loading}
    <div class="status">
      <div class="spinner"></div>
      <p>Fetching dashboard data...</p>
    </div>
  {:else if errorMsg}
    <div class="status error-box">
      <p>Error: {errorMsg}</p>
      {#if selectedGeoObj}
        <button class="retry-btn" on:click={() => fetchDashboardData(selectedGeoObj)}>Retry</button>
      {/if}
    </div>
  {:else if rawRows.length > 0 && selectedGeoObj}
    <!-- Warnings -->
    {#if warnings.length > 0}
      <div class="warnings">
        {#each warnings as w}
          <p class="warning-item">{w}</p>
        {/each}
      </div>
    {/if}

    <!-- Hero Banner: Region info + Map -->
    <div class="hero-banner">
      <div class="hero-info">
        <h2>{selectedGeoObj.name}</h2>
        <span class="year-range">Regional Economic Profile</span>
        <span class="hero-subtitle">{DASHBOARD_YEARS[0]}–{DASHBOARD_YEARS[DASHBOARD_YEARS.length - 1]} · Federal data across multiple sources</span>
      </div>
      <div class="hero-map">
        <DashboardMap geoId={selectedGeoObj?.id} geoType={geoType} />
      </div>
    </div>

    <!-- Section: Key Metrics -->
    <div class="section" style="animation-delay: 0.15s">
      <div class="section-header">
        <span class="section-title">Key Metrics</span>
        <span class="section-subtitle">Latest available year with year-over-year change</span>
      </div>
      <div class="kpi-grid">
        {#each KPI_CONFIG as kpi, i}
          <KPICard
            label={kpi.label}
            value={latestValue(kpi.key)}
            change={yoyChange(kpi.key)}
            changeType={kpi.changeType}
            higherIs={kpi.higherIs}
            fmt={kpi.fmt}
            sparklineData={sparkline(kpi.key)}
            index={i}
          />
        {/each}
      </div>
    </div>

    <!-- Section: Economic Trends -->
    <div class="section" style="animation-delay: 0.3s">
      <div class="section-header">
        <span class="section-title">Economic Overview</span>
      </div>
      <div class="charts-row">
        <div class="chart-cell">
          <TrendChart
            title="Income & GDP per Capita"
            datasets={econTrendDatasets}
            fmt="$#,##0"
          />
        </div>
        <div class="chart-cell">
          <TrendChart
            title="Nonfarm Employment (thousands)"
            datasets={jobsDatasets}
            fmt="#,##0.0"
          />
        </div>
      </div>
    </div>

    <!-- Section: Housing -->
    <div class="section" style="animation-delay: 0.45s">
      <div class="section-header">
        <span class="section-title">Housing</span>
      </div>
      <div class="charts-row">
        <div class="chart-cell">
          <TrendChart
            title="Median Home Value"
            datasets={homeValueDatasets}
            fmt="$#,##0"
          />
        </div>
        <div class="chart-cell">
          <TrendChart
            title="Median Gross Rent"
            datasets={rentDatasets}
            fmt="$#,##0"
          />
        </div>
      </div>
    </div>

    <!-- Section: Demographics -->
    <div class="section" style="animation-delay: 0.6s">
      <div class="section-header">
        <span class="section-title">Demographics</span>
      </div>
      <div class="charts-row">
        <div class="chart-cell">
          <div class="edu-chart">
            <div class="edu-title">Educational Attainment (25+)</div>
            <div class="edu-bars">
              {#each eduData as ed, i}
                <div class="edu-row">
                  <div class="edu-label">{ed.label}</div>
                  <div class="edu-track">
                    <div
                      class="edu-fill"
                      style="width: {ed.value ? (ed.value / eduMaxVal * 100) : 0}%;"
                    ></div>
                  </div>
                  <div class="edu-value">{formatNum(ed.value)}</div>
                </div>
              {/each}
            </div>
          </div>
        </div>
        <div class="chart-cell">
          <PopulationPyramid data={ageData} title="Age Distribution" />
        </div>
      </div>
    </div>

  {:else}
    <div class="status empty">
      <div class="empty-icon">
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="4" y="12" width="40" height="28" rx="4" stroke="var(--border-medium)" stroke-width="2" fill="none"/>
          <line x1="4" y1="20" x2="44" y2="20" stroke="var(--border-medium)" stroke-width="2"/>
          <rect x="10" y="25" width="10" height="3" rx="1.5" fill="var(--border-medium)"/>
          <rect x="10" y="31" width="16" height="3" rx="1.5" fill="var(--border-light)"/>
          <circle cx="36" cy="30" r="4" stroke="var(--accent-primary)" stroke-width="2" fill="none"/>
          <line x1="39" y1="33" x2="42" y2="36" stroke="var(--accent-primary)" stroke-width="2" stroke-linecap="round"/>
        </svg>
      </div>
      <p class="empty-title">Select a region to explore</p>
      <p class="empty-hint">Search for a metro area, state, or county above to view its economic dashboard with key metrics, trends, and demographic breakdowns.</p>
    </div>
  {/if}
</div>

<style>
  .dashboard {
    padding: 0 1.25rem 2.5rem;
    max-width: 1200px;
    margin: 0 auto;
  }

  /* ── Geo Selector ── */
  .geo-selector {
    background: var(--bg-card);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-card);
    padding: 1rem 1.25rem;
    margin-bottom: 1.5rem;
    border: 1px solid var(--border-light);
  }

  .selector-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .selector-label {
    font-family: var(--font-primary);
    font-size: 0.95rem;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.01em;
  }

  .geo-tabs {
    display: flex;
    gap: 0;
  }

  .geo-tab {
    padding: 0.4rem 1.1rem;
    font-size: 0.72rem;
    font-weight: 500;
    border: 1px solid var(--border-medium);
    background: var(--bg-card);
    color: var(--text-secondary);
    cursor: pointer;
    min-height: var(--touch-min);
    font-family: var(--font-body);
    transition: all var(--transition-fast);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .geo-tab:first-child { border-radius: var(--radius-sm) 0 0 var(--radius-sm); }
  .geo-tab:last-child { border-radius: 0 var(--radius-sm) var(--radius-sm) 0; }
  .geo-tab:not(:first-child) { border-left: none; }
  .geo-tab:hover:not(.active) { border-color: var(--accent-primary); color: var(--accent-primary); background: var(--bg-hover); }
  .geo-tab.active { background: var(--accent-primary); color: var(--text-on-dark); border-color: var(--accent-primary); font-weight: 600; }

  .search-area {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .search-wrapper {
    position: relative;
    flex: 1;
    min-width: 200px;
  }

  .search-wrapper input {
    width: 100%;
    padding: 0.55rem 0.85rem;
    border: 1px solid var(--border-medium);
    border-radius: var(--radius-sm);
    font-size: 0.85rem;
    box-sizing: border-box;
    min-height: var(--touch-min);
    font-family: inherit;
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  }
  .search-wrapper input:focus {
    outline: none;
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 3px rgba(14,120,190,0.1);
  }

  .dropdown {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    background: var(--bg-card);
    border: 1px solid var(--border-medium);
    border-top: none;
    border-radius: 0 0 var(--radius-md) var(--radius-md);
    max-height: 260px;
    overflow-y: auto;
    z-index: 100;
    list-style: none;
    margin: 0;
    padding: 0;
    box-shadow: var(--shadow-elevated);
  }
  .dropdown li {
    padding: 0.55rem 0.85rem;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    font-size: 0.82rem;
    border-bottom: 1px solid var(--border-light);
    transition: background var(--transition-fast);
  }
  .dropdown li:last-child { border-bottom: none; }
  .dropdown li:hover { background: var(--bg-hover); }
  .geo-code { color: var(--text-muted); font-size: 0.72rem; font-variant-numeric: tabular-nums; }
  .more-note { padding: 0.45rem 0.85rem; font-size: 0.72rem; color: var(--text-muted); font-style: italic; cursor: default; }

  .state-filter select {
    padding: 0.45rem 0.6rem;
    border: 1px solid var(--border-medium);
    border-radius: var(--radius-sm);
    font-size: 0.82rem;
    min-height: var(--touch-min);
    font-family: inherit;
    background: var(--bg-card);
    transition: border-color var(--transition-fast);
  }
  .state-filter select:focus { border-color: var(--accent-primary); outline: none; }

  .selected-geo-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    padding: 0.4rem 0.75rem;
    background: var(--bg-selected);
    border: 1px solid var(--accent-hover);
    border-radius: var(--radius-xl);
    font-size: 0.8rem;
    color: var(--text-primary);
    white-space: nowrap;
    font-weight: 500;
  }
  .badge-clear {
    background: none;
    border: none;
    cursor: pointer;
    font-size: 1.05rem;
    color: var(--text-muted);
    padding: 0;
    line-height: 1;
    transition: color var(--transition-fast);
  }
  .badge-clear:hover { color: var(--negative); }

  /* ── Hero Banner ── */
  .hero-banner {
    display: grid;
    grid-template-columns: 1fr 1fr;
    border-radius: var(--radius-lg);
    overflow: hidden;
    margin-bottom: 1.75rem;
    box-shadow: 0 6px 28px rgba(21,18,62,0.14), 0 2px 8px rgba(0,0,0,0.06);
    min-height: 220px;
    opacity: 0;
    animation: fadeInUp 0.5s ease 0.1s forwards;
  }

  .hero-info {
    background: linear-gradient(135deg, var(--color-riviere) 0%, var(--color-riviere-dark) 60%, #0c1a3a 100%);
    padding: 2rem 2rem;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 0.5rem;
    position: relative;
    overflow: hidden;
  }

  /* Subtle geometric accent in hero */
  .hero-info::before {
    content: '';
    position: absolute;
    top: -30%;
    right: -20%;
    width: 60%;
    height: 160%;
    background: radial-gradient(ellipse, rgba(14,120,190,0.12) 0%, transparent 65%);
    pointer-events: none;
  }

  .hero-info h2 {
    margin: 0;
    font-size: 1.55rem;
    font-weight: 800;
    color: var(--text-on-dark);
    letter-spacing: -0.02em;
    font-family: var(--font-primary);
    line-height: 1.2;
  }

  .year-range {
    font-size: 0.7rem;
    color: var(--color-southern-sky);
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .hero-subtitle {
    font-size: 0.68rem;
    color: var(--color-steel);
    font-weight: 400;
    letter-spacing: 0.02em;
    opacity: 0.75;
  }

  .hero-map {
    min-height: 220px;
  }

  /* ── Section Structure ── */
  .section {
    margin-bottom: 2rem;
    opacity: 0;
    animation: fadeInUp 0.5s ease forwards;
  }

  .section-header {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    margin-bottom: 0.85rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid var(--border-light);
    position: relative;
  }

  /* Active accent bar under section title */
  .section-header::after {
    content: '';
    position: absolute;
    bottom: -2px;
    left: 0;
    width: 40px;
    height: 2px;
    background: var(--accent-primary);
    border-radius: 1px;
  }

  .section-title {
    font-family: var(--font-primary);
    font-size: 0.92rem;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.01em;
  }

  .section-subtitle {
    font-size: 0.68rem;
    color: var(--text-muted);
    font-weight: 400;
    letter-spacing: 0.02em;
  }

  /* ── KPI Grid ── */
  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.85rem;
  }

  /* ── Chart Rows ── */
  .charts-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.85rem;
  }

  .chart-cell {
    min-width: 0;
  }

  /* ── Education Chart ── */
  .edu-chart {
    background: var(--bg-card);
    border: 1px solid var(--border-light);
    border-radius: var(--radius-md);
    padding: 0.85rem 1rem;
    box-shadow: var(--shadow-card);
    height: 100%;
    min-height: 260px;
    display: flex;
    flex-direction: column;
  }

  .edu-title {
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 0.85rem;
    text-align: center;
  }

  .edu-bars {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: space-around;
    gap: 6px;
  }

  .edu-row {
    display: flex;
    align-items: center;
    gap: 0.55rem;
  }

  .edu-label {
    width: 92px;
    min-width: 92px;
    text-align: right;
    font-size: 0.72rem;
    color: var(--text-secondary);
    white-space: nowrap;
    font-weight: 500;
  }

  .edu-track {
    flex: 1;
    height: 20px;
    background: var(--bg-muted);
    border-radius: 4px;
    overflow: hidden;
  }

  .edu-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.8s cubic-bezier(0.25, 0.46, 0.45, 0.94);
    min-width: 1px;
    background: linear-gradient(90deg, var(--accent-primary), var(--color-southern-sky));
    position: relative;
  }

  .edu-fill::after {
    content: '';
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    width: 2px;
    background: rgba(255,255,255,0.4);
    border-radius: 0 4px 4px 0;
  }

  .edu-value {
    width: 60px;
    min-width: 60px;
    text-align: right;
    font-size: 0.7rem;
    color: var(--text-muted);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }

  /* ── Status / Loading ── */
  .status {
    text-align: center;
    padding: 4rem 1.5rem;
    color: var(--text-muted);
  }
  .status p { font-size: 0.9rem; }
  .error-box { color: var(--negative); }
  .retry-btn {
    margin-top: 0.75rem;
    padding: 0.5rem 1.5rem;
    font-size: 0.82rem;
    font-weight: 600;
    border: 1px solid var(--accent-primary);
    background: var(--accent-primary);
    color: var(--text-on-dark);
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-family: var(--font-body);
    transition: all var(--transition-fast);
  }
  .retry-btn:hover { background: var(--color-southern-sky); border-color: var(--color-southern-sky); }

  .empty {
    padding: 5rem 2rem;
  }
  .empty-icon {
    margin-bottom: 1.25rem;
    opacity: 0.6;
  }
  .empty-title {
    font-family: var(--font-primary);
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0 0 0.5rem;
  }
  .empty-hint {
    font-size: 0.82rem;
    color: var(--text-muted);
    max-width: 480px;
    margin: 0 auto;
    line-height: 1.55;
  }

  .spinner {
    width: 30px;
    height: 30px;
    border: 3px solid var(--border-default);
    border-top-color: var(--accent-primary);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 0 auto 1rem;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .warnings {
    background: var(--warning-bg);
    border: 1px solid var(--warning-border);
    border-radius: var(--radius-sm);
    padding: 0.55rem 0.85rem;
    margin-bottom: 1rem;
  }
  .warning-item { font-size: 0.78rem; color: var(--warning-text); margin: 0.2rem 0; }

  /* ── Mobile ── */
  @media (max-width: 640px) {
    .dashboard {
      padding: 0 0.5rem 1.5rem;
    }

    .selector-header {
      flex-direction: column;
      gap: 0.5rem;
      align-items: flex-start;
    }

    .geo-tab { padding: 0.4rem 0.65rem; font-size: 0.68rem; }

    .kpi-grid {
      grid-template-columns: repeat(2, 1fr);
      gap: 0.5rem;
    }

    .charts-row {
      grid-template-columns: 1fr;
    }

    .hero-banner { grid-template-columns: 1fr; min-height: auto; }
    .hero-info { padding: 1.25rem 1.15rem; }
    .hero-info h2 { font-size: 1.15rem; }
    .hero-map { min-height: 180px; }

    .search-wrapper input { font-size: 16px; } /* prevent iOS zoom */

    .edu-label {
      width: 70px;
      min-width: 70px;
      font-size: 0.65rem;
    }

    .section { margin-bottom: 1.5rem; }
    .section-header { flex-direction: column; gap: 0.2rem; }
  }

  /* ── Tablet ── */
  @media (min-width: 641px) and (max-width: 1024px) {
    .kpi-grid {
      grid-template-columns: repeat(4, 1fr);
    }
  }
</style>
