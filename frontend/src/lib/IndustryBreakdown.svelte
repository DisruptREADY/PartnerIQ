<script>
  import { onDestroy } from 'svelte';
  import { selectedGeos, highlightGeo } from '../stores.js';
  import { Chart } from './chartDefaults.js';

  let loading = false;
  let errorMsg = null;
  let data = null;

  let selectedYear = null;
  let displayAs = 'count'; // 'count' | 'share'
  let showChart = true;
  let chartGeo = ''; // geo_id for chart focus
  let sortCol = null;
  let sortDir = 'desc';

  let canvasEl;
  let chart = null;

  // Re-fetch when geos change
  let lastGeoKey = '';
  $: {
    const key = $selectedGeos.map(g => g.id).sort().join(',');
    if (key && key !== lastGeoKey) {
      lastGeoKey = key;
      fetchIndustryData();
    }
  }

  $: years = data?.years || [];
  $: if (years.length && !selectedYear) selectedYear = years[years.length - 1];
  $: geos = data?.geos || [];
  $: industries = (data?.industries || []).filter(i => i.code !== '00000000');
  $: allIndustries = data?.industries || [];
  $: rawData = data?.data || [];
  $: warnings = data?.warnings || [];
  $: fallbackGeos = data?.fallback_geos || [];
  $: fallbackGeoNames = fallbackGeos
    .map(id => geos.find(g => g.id === id)?.name?.split(',')[0])
    .filter(Boolean);

  // Auto-select first geo for chart
  $: if (geos.length && !chartGeo) chartGeo = geos[0].id;

  // Lookup helpers
  function getValue(geoId, indCode, yr) {
    return rawData.find(d => d.geo_id === geoId && d.industry_code === indCode && d.year === yr)?.value;
  }

  function getTotalNonfarm(geoId, yr) {
    return getValue(geoId, '00000000', yr);
  }

  function getDisplayValue(geoId, indCode, yr) {
    const val = getValue(geoId, indCode, yr);
    if (val == null) return null;
    if (displayAs === 'share') {
      const total = getTotalNonfarm(geoId, yr);
      if (!total) return null;
      return ((val / total) * 100).toFixed(1);
    }
    return val.toFixed(1);
  }

  // Sorting
  function sortBy(colId) {
    if (sortCol === colId) {
      sortDir = sortDir === 'asc' ? 'desc' : 'asc';
    } else {
      sortCol = colId;
      sortDir = 'desc';
    }
  }

  $: sortedIndustries = (() => {
    if (!sortCol || !selectedYear) return industries;
    const copy = [...industries];
    copy.sort((a, b) => {
      const va = parseFloat(getDisplayValue(sortCol, a.code, selectedYear)) || 0;
      const vb = parseFloat(getDisplayValue(sortCol, b.code, selectedYear)) || 0;
      return sortDir === 'asc' ? va - vb : vb - va;
    });
    return copy;
  })();

  let indController = null;
  async function fetchIndustryData() {
    if ($selectedGeos.length === 0) return;
    if (indController) indController.abort();
    indController = new AbortController();
    const { signal } = indController;

    loading = true;
    errorMsg = null;
    data = null;
    selectedYear = null;
    chartGeo = '';

    try {
      const resp = await fetch('/api/breakdown/industry', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          geo_ids: $selectedGeos.map(g => g.id),
        }),
        signal,
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${resp.status}`);
      }
      data = await resp.json();
    } catch (e) {
      if (e.name === 'AbortError') return;
      errorMsg = e.message;
    } finally {
      loading = false;
    }
  }

  // Chart rendering
  $: if (canvasEl && data && selectedYear && chartGeo && showChart) {
    renderChart();
  }

  function renderChart() {
    if (chart) chart.destroy();
    if (!canvasEl || !data || !selectedYear) return;

    const ctx = canvasEl.getContext('2d');
    const inds = industries;
    const labels = inds.map(i => i.label);
    const values = inds.map(i => {
      if (displayAs === 'share') {
        return parseFloat(getDisplayValue(chartGeo, i.code, selectedYear)) || 0;
      }
      return getValue(chartGeo, i.code, selectedYear) || 0;
    });

    const isHighlight = chartGeo === $highlightGeo;
    const bgColor = isHighlight ? '#fde68a' : '#0E78BE';
    const borderColor = isHighlight ? '#eab308' : '#0a6aaa';

    const geoName = geos.find(g => g.id === chartGeo)?.name?.split(',')[0] || chartGeo;

    chart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: geoName,
          data: values,
          backgroundColor: bgColor,
          borderColor: borderColor,
          borderWidth: 1,
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          title: {
            display: true,
            text: `${geoName} — Industry Employment ${displayAs === 'share' ? '(% of Total)' : '(thousands)'} — ${selectedYear}`,
            font: { size: 13 },
          },
        },
        scales: {
          x: { beginAtZero: true },
          y: { ticks: { font: { size: 11 } } },
        },
      },
    });
  }

  function saveChart() {
    if (!chart) return;
    const url = chart.toBase64Image();
    const a = document.createElement('a');
    a.href = url;
    a.download = `industry_breakdown_${chartGeo}_${selectedYear}.png`;
    a.click();
  }

  onDestroy(() => {
    if (chart) chart.destroy();
  });
</script>

<div class="breakdown">
  {#if $selectedGeos.length === 0}
    <div class="empty">Select geographies in the sidebar to view industry breakdowns.</div>
  {:else if loading}
    <div class="loading">
      <div class="spinner"></div>
      <p>Fetching industry data from BLS...</p>
    </div>
  {:else if errorMsg}
    <div class="error">Error: {errorMsg}</div>
  {:else if data}
    {#if warnings.length > 0}
      <div class="warnings">
        {#each warnings as w}
          <p class="warning-item">{w}</p>
        {/each}
      </div>
    {/if}

    {#if fallbackGeoNames.length > 0}
      <div class="info-note">
        BLS does not publish separate Mining &amp; Logging data for {fallbackGeoNames.join(', ')}.
        The Construction figure for {fallbackGeoNames.length === 1 ? 'that area' : 'those areas'} includes the combined Mining, Logging &amp; Construction total.
      </div>
    {/if}

    <div class="controls">
      {#if years.length > 1}
        <label>
          Year:
          <select bind:value={selectedYear} on:change={renderChart}>
            {#each years as y}
              <option value={y}>{y}</option>
            {/each}
          </select>
        </label>
      {/if}

      <div class="toggle-group">
        <button class:active={displayAs === 'count'} on:click={() => { displayAs = 'count'; }}>Count</button>
        <button class:active={displayAs === 'share'} on:click={() => { displayAs = 'share'; }}>Share %</button>
      </div>

      <div class="toggle-group">
        <button class:active={showChart} on:click={() => showChart = true}>Chart</button>
        <button class:active={!showChart} on:click={() => showChart = false}>Table Only</button>
      </div>

      {#if showChart && geos.length > 0}
        <label>
          Chart geo:
          <select bind:value={chartGeo} on:change={renderChart}>
            {#each geos as g}
              <option value={g.id}>{g.name.split(',')[0]}</option>
            {/each}
          </select>
        </label>
        <button class="save-btn" on:click={saveChart}>Save PNG</button>
      {/if}
    </div>

    {#if showChart}
      <div class="chart-container">
        <!-- svelte-ignore a11y_no_interactive_element_to_noninteractive_role -->
        <canvas bind:this={canvasEl} role="img" aria-label="Industry breakdown chart"></canvas>
      </div>
    {/if}

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th class="sticky-col">Industry</th>
            {#each geos as g}
              <th
                class:highlight={g.id === $highlightGeo}
                class="sortable"
                on:click={() => sortBy(g.id)}
              >
                {g.name.split(',')[0]}
                {#if sortCol === g.id}{sortDir === 'asc' ? ' ↑' : ' ↓'}{/if}
              </th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each sortedIndustries as ind}
            <tr>
              <td class="sticky-col">{ind.label}</td>
              {#each geos as g}
                <td class:highlight={g.id === $highlightGeo}>
                  {#if ind.code === '10000000' && fallbackGeos.includes(g.id)}
                    <span class="na-cell" title="Combined with Construction">N/A</span>
                  {:else if getDisplayValue(g.id, ind.code, selectedYear) != null}
                    {getDisplayValue(g.id, ind.code, selectedYear)}{displayAs === 'share' ? '%' : ''}
                  {:else}
                    —
                  {/if}
                </td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .breakdown { padding: 0.5rem 0; }

  .empty, .loading, .error { text-align: center; padding: 2rem; color: var(--text-muted); }
  .error { color: var(--negative); font-weight: 500; }

  .spinner {
    width: 24px; height: 24px;
    border: 3px solid var(--border-default); border-top-color: var(--accent-primary);
    border-radius: 50%; animation: spin 0.8s linear infinite;
    margin: 0 auto 0.75rem;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .warnings {
    background: var(--warning-bg); border: 1px solid var(--warning-border);
    border-radius: var(--radius-sm); padding: 0.4rem 0.6rem; margin-bottom: 0.75rem;
  }
  .warning-item { font-size: 0.75rem; color: var(--warning-text); margin: 0.15rem 0; }

  .controls {
    display: flex; gap: 0.65rem; align-items: center;
    flex-wrap: wrap; margin-bottom: 0.75rem;
    padding: 0.5rem 0; border-bottom: 1px solid var(--border-light);
  }
  .controls label { font-size: 0.76rem; color: var(--text-secondary); font-weight: 500; }
  .controls select {
    padding: 0.25rem 0.4rem; font-size: 0.76rem;
    border: 1px solid var(--border-medium); border-radius: var(--radius-sm);
    transition: border-color var(--transition-fast);
  }
  .controls select:focus { border-color: var(--accent-primary); outline: none; }

  .toggle-group { display: flex; gap: 0; }
  .toggle-group button {
    padding: 0.3rem 0.65rem; font-size: 0.7rem; font-weight: 500;
    border: 1px solid var(--border-medium); background: var(--bg-card); color: var(--text-secondary); cursor: pointer;
    transition: all var(--transition-fast); font-family: var(--font-body); letter-spacing: 0.02em;
  }
  .toggle-group button:first-child { border-radius: var(--radius-sm) 0 0 var(--radius-sm); }
  .toggle-group button:last-child { border-radius: 0 var(--radius-sm) var(--radius-sm) 0; border-left: none; }
  .toggle-group button.active { background: var(--accent-primary); color: var(--text-on-dark); border-color: var(--accent-primary); font-weight: 600; }
  .toggle-group button:hover:not(.active) { background: var(--bg-hover); color: var(--accent-primary); border-color: var(--accent-primary); }

  .save-btn {
    padding: 0.3rem 0.65rem; font-size: 0.68rem; font-weight: 600;
    border: 1px solid var(--positive); background: var(--positive); color: var(--text-on-dark);
    border-radius: var(--radius-sm); cursor: pointer; font-family: var(--font-body); letter-spacing: 0.03em; text-transform: uppercase;
    transition: all var(--transition-fast);
  }
  .save-btn:hover { opacity: 0.85; transform: translateY(-1px); }
  .save-btn:active { transform: translateY(0); }

  .chart-container {
    position: relative; height: 450px; width: 100%; margin-bottom: 1rem;
    background: var(--bg-card);
    border: 1px solid var(--border-light);
    border-radius: var(--radius-md);
    padding: 0.5rem;
    box-shadow: var(--shadow-card);
  }

  .table-wrap {
    overflow-x: auto;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-default);
  }
  table { border-collapse: separate; border-spacing: 0; width: 100%; font-size: 0.78rem; }
  th {
    padding: 0.4rem 0.5rem;
    text-align: right;
    white-space: nowrap;
    background: var(--color-riviere);
    color: var(--text-on-dark);
    font-weight: 600;
    font-size: 0.74rem;
    position: sticky;
    top: 0;
    z-index: 1;
    border: none;
    border-bottom: 2px solid rgba(14,120,190,0.3);
    border-right: 1px solid rgba(255,255,255,0.1);
  }
  th:last-child { border-right: none; }
  td {
    padding: 0.38rem 0.5rem;
    text-align: right;
    white-space: nowrap;
    border-bottom: 1px solid var(--border-light);
    border-right: 1px solid var(--border-light);
    background: var(--bg-card);
    transition: background var(--transition-fast);
  }
  td:last-child { border-right: none; }
  .sticky-col { text-align: left; position: sticky; left: 0; z-index: 2; min-width: 180px; }
  th.sticky-col { background: var(--color-riviere); z-index: 3; }
  td.sticky-col { background: var(--bg-card); }
  tr:nth-child(even) td { background: var(--bg-muted); }
  tr:hover td { background: var(--bg-hover); }
  .highlight { background: var(--highlight-bg) !important; }
  .sortable { cursor: pointer; }
  .sortable:hover { background: var(--color-riviere-dark) !important; }

  .info-note {
    background: #eff6ff; border: 1px solid #bfdbfe;
    border-radius: var(--radius-sm); padding: 0.4rem 0.6rem; margin-bottom: 0.75rem;
    font-size: 0.75rem; color: #1e40af; line-height: 1.4;
  }
  .na-cell { color: var(--text-muted); font-style: italic; }
</style>
