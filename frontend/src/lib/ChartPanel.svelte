<script>
  import { onDestroy } from 'svelte';
  import { results, highlightGeo } from '../stores.js';
  import { Chart } from './chartDefaults.js';

  let canvasEl;
  let chart = null;
  let chartType = 'bar'; // 'bar' | 'line'
  let selectedIndicator = '';
  let selectedChartYears = []; // user-selected years for charting

  // Brand chart palette
  const CHART_COLORS = [
    '#0E78BE', '#EC9952', '#66AD6E', '#6A3A84', '#C7335E',
    '#5DA7DC', '#0B7D5A', '#ABB9C6', '#15123E', '#B31828',
  ];

  $: columns = $results?.columns || [];
  $: rows = $results?.rows || [];
  $: indicatorCols = columns.filter(c => c.source);

  // All years available in the data
  $: allYears = [...new Set(rows.map(r => r.Year))].sort();

  // Reset and auto-select indicator when data changes
  let prevResultsRef = null;
  $: if ($results !== prevResultsRef) {
    prevResultsRef = $results;
    const cols = ($results?.columns || []).filter(c => c.source);
    if (cols.length > 0 && (!selectedIndicator || !cols.find(c => c.key === selectedIndicator))) {
      selectedIndicator = cols[0].key;
    }
    selectedChartYears = [];
  }

  // Default year selection: latest year for bar, all years for line
  $: if (allYears.length > 0 && selectedChartYears.length === 0) {
    selectedChartYears = chartType === 'bar'
      ? [allYears[allYears.length - 1]]
      : [...allYears];
  }

  $: selectedColMeta = columns.find(c => c.key === selectedIndicator);

  // Debounce chart renders to avoid thrashing during rapid state changes
  let renderTimer;
  $: if (canvasEl && rows.length > 0 && selectedIndicator && selectedChartYears.length > 0) {
    clearTimeout(renderTimer);
    renderTimer = setTimeout(() => renderChart(), 300);
  }

  function toggleYear(year) {
    if (selectedChartYears.includes(year)) {
      if (selectedChartYears.length > 1) {
        selectedChartYears = selectedChartYears.filter(y => y !== year);
      }
    } else {
      selectedChartYears = [...selectedChartYears, year].sort();
    }
  }

  function selectAllYears() {
    selectedChartYears = [...allYears];
  }

  function selectLatestYear() {
    selectedChartYears = [allYears[allYears.length - 1]];
  }

  function renderChart() {
    if (chart) chart.destroy();
    if (!canvasEl || !selectedIndicator) return;

    const ctx = canvasEl.getContext('2d');

    if (chartType === 'bar') {
      renderBarChart(ctx);
    } else {
      renderLineChart(ctx);
    }
  }

  // Create gradient for bar chart fills
  function createBarGradient(ctx, color) {
    const gradient = ctx.createLinearGradient(0, 0, 0, ctx.canvas.height);
    gradient.addColorStop(0, color);
    gradient.addColorStop(1, color + '88');
    return gradient;
  }

  function renderBarChart(ctx) {
    const yearsToShow = selectedChartYears.length > 0 ? selectedChartYears : [allYears[allYears.length - 1]];

    if (yearsToShow.length === 1) {
      // Single year: simple bar chart with gradient fills
      const latestYear = yearsToShow[0];
      const yearRows = rows.filter(r => r.Year === latestYear && r[selectedIndicator] != null);
      yearRows.sort((a, b) => (b[selectedIndicator] || 0) - (a[selectedIndicator] || 0));

      const labels = yearRows.map(r => r.Metro ? r.Metro.split(',')[0] : r.CBSA);
      const data = yearRows.map(r => r[selectedIndicator]);
      const HIGHLIGHT_COLOR = '#fde68a';
      const gradient = createBarGradient(ctx, CHART_COLORS[0]);
      const bgColors = yearRows.map(r =>
        r.CBSA === $highlightGeo ? HIGHLIGHT_COLOR : gradient
      );

      chart = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets: [{
          label: selectedColMeta?.label || selectedIndicator,
          data,
          backgroundColor: bgColors,
          borderWidth: 0,
          borderRadius: 3,
          borderSkipped: false,
        }] },
        options: {
          responsive: true, maintainAspectRatio: false,
          animation: { duration: 800, easing: 'easeOutQuart' },
          plugins: {
            legend: { display: false },
            title: { display: true, text: `${selectedColMeta?.label || selectedIndicator} — ${latestYear}`, font: { size: 14 } },
          },
          scales: { x: { ticks: { maxRotation: 45, font: { size: 10 } } }, y: { beginAtZero: true } },
        },
      });
    } else {
      // Multiple years: grouped bar chart
      const geos = [...new Map(rows.map(r => [r.CBSA, r.Metro || r.CBSA])).entries()];
      const labels = geos.map(([_, name]) => name ? name.split(',')[0] : _);

      const datasets = yearsToShow.map((year, i) => ({
        label: String(year),
        data: geos.map(([cbsa]) => {
          const match = rows.find(r => r.CBSA === cbsa && r.Year === year);
          return match ? match[selectedIndicator] : null;
        }),
        backgroundColor: CHART_COLORS[i % CHART_COLORS.length],
        borderWidth: 0,
        borderRadius: 3,
        borderSkipped: false,
      }));

      chart = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets },
        options: {
          responsive: true, maintainAspectRatio: false,
          animation: { duration: 800, easing: 'easeOutQuart' },
          plugins: {
            title: { display: true, text: selectedColMeta?.label || selectedIndicator, font: { size: 14 } },
            legend: { display: true, position: 'bottom', labels: { font: { size: 10 }, boxWidth: 12, usePointStyle: true, pointStyle: 'circle' } },
          },
          scales: { x: { ticks: { maxRotation: 45, font: { size: 10 } } }, y: { beginAtZero: true } },
        },
      });
    }
  }

  function renderLineChart(ctx) {
    const yearsToShow = selectedChartYears.length > 0 ? selectedChartYears : allYears;
    const geos = [...new Map(rows.map(r => [r.CBSA, r.Metro || r.CBSA])).entries()];

    const datasets = geos.map(([cbsa, name], i) => {
      const geoRows = rows.filter(r => r.CBSA === cbsa);
      const data = yearsToShow.map(y => {
        const match = geoRows.find(r => r.Year === y);
        return match ? match[selectedIndicator] : null;
      });

      const isHighlight = cbsa === $highlightGeo;
      const HIGHLIGHT_LINE = '#eab308';
      const color = isHighlight ? HIGHLIGHT_LINE : CHART_COLORS[i % CHART_COLORS.length];

      // Gradient fill for highlighted or single-geo line charts
      let bgColor;
      if (geos.length <= 3) {
        const gradient = ctx.createLinearGradient(0, 0, 0, ctx.canvas.height);
        gradient.addColorStop(0, color + '25');
        gradient.addColorStop(1, color + '02');
        bgColor = gradient;
      } else {
        bgColor = 'transparent';
      }

      return {
        label: name ? name.split(',')[0] : cbsa,
        data,
        borderColor: color,
        backgroundColor: bgColor,
        fill: geos.length <= 3,
        borderWidth: isHighlight ? 3 : 2,
        pointRadius: isHighlight ? 5 : 3,
        pointHoverRadius: isHighlight ? 7 : 5,
        pointBackgroundColor: color,
        pointBorderColor: '#fff',
        pointBorderWidth: 1.5,
        tension: 0.25,
        spanGaps: true,
      };
    });

    chart = new Chart(ctx, {
      type: 'line',
      data: { labels: yearsToShow, datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        animation: { duration: 1000, easing: 'easeOutQuart' },
        interaction: { mode: 'index', intersect: false },
        plugins: {
          title: { display: true, text: selectedColMeta?.label || selectedIndicator, font: { size: 14 } },
          legend: { display: geos.length <= 15, position: 'bottom', labels: { font: { size: 10 }, boxWidth: 12, usePointStyle: true, pointStyle: 'circle' } },
        },
        scales: { y: { beginAtZero: false } },
      },
    });
  }

  function saveChart() {
    if (!chart) return;
    const url = chart.toBase64Image();
    const a = document.createElement('a');
    a.href = url;
    a.download = `chart_${selectedIndicator}.png`;
    a.click();
  }

  onDestroy(() => {
    if (chart) chart.destroy();
  });
</script>

<div class="chart-panel">
  <div class="chart-controls">
    <label class="sr-only" for="chart-indicator">Select indicator</label>
    <select id="chart-indicator" bind:value={selectedIndicator} on:change={renderChart}>
      {#each indicatorCols as col}
        <option value={col.key}>{col.label}</option>
      {/each}
    </select>

    <div class="chart-type-toggle">
      <button class:active={chartType === 'bar'} on:click={() => { chartType = 'bar'; selectedChartYears = [allYears[allYears.length - 1]]; renderChart(); }}>Bar</button>
      <button class:active={chartType === 'line'} on:click={() => { chartType = 'line'; selectedChartYears = [...allYears]; renderChart(); }}>Line</button>
    </div>

    <button class="save-btn" on:click={saveChart}>Save PNG</button>
  </div>

  <!-- Year selector pills -->
  {#if allYears.length > 1}
    <div class="year-pills">
      <span class="year-pills-label">Years:</span>
      {#each allYears as year}
        <button
          class="year-pill"
          class:selected={selectedChartYears.includes(year)}
          on:click={() => toggleYear(year)}
        >
          {year}
        </button>
      {/each}
      <button class="year-pill-action" on:click={selectAllYears}>All</button>
      <button class="year-pill-action" on:click={selectLatestYear}>Latest</button>
    </div>
  {/if}

  <div class="chart-container">
    <!-- svelte-ignore a11y_no_interactive_element_to_noninteractive_role -->
    <canvas bind:this={canvasEl} role="img" aria-label="{selectedColMeta?.label || selectedIndicator} chart"></canvas>
  </div>
</div>

<style>
  .chart-panel { padding: 0.5rem 0; }

  .chart-controls {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    margin-bottom: 0.5rem;
    flex-wrap: wrap;
  }

  select {
    padding: 0.35rem 0.5rem;
    font-size: 0.82rem;
    border: 1px solid var(--border-medium);
    border-radius: var(--radius-sm);
    max-width: 280px;
    transition: border-color var(--transition-fast);
  }
  select:focus { border-color: var(--accent-primary); outline: none; }

  .chart-type-toggle {
    display: flex;
    gap: 0;
  }
  .chart-type-toggle button {
    padding: 0.35rem 0.75rem;
    font-size: 0.72rem;
    font-weight: 500;
    border: 1px solid var(--border-medium);
    background: var(--bg-card);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all var(--transition-fast);
    font-family: var(--font-body);
    letter-spacing: 0.02em;
  }
  .chart-type-toggle button:first-child { border-radius: var(--radius-sm) 0 0 var(--radius-sm); }
  .chart-type-toggle button:last-child { border-radius: 0 var(--radius-sm) var(--radius-sm) 0; border-left: none; }
  .chart-type-toggle button.active { background: var(--accent-primary); color: var(--text-on-dark); border-color: var(--accent-primary); font-weight: 600; }
  .chart-type-toggle button:hover:not(.active) { background: var(--bg-hover); color: var(--accent-primary); border-color: var(--accent-primary); }

  .save-btn {
    padding: 0.32rem 0.7rem;
    font-size: 0.7rem;
    font-weight: 600;
    border: 1px solid var(--positive);
    background: var(--positive);
    color: var(--text-on-dark);
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all var(--transition-fast);
    font-family: var(--font-body);
    letter-spacing: 0.03em;
    text-transform: uppercase;
  }
  .save-btn:hover { opacity: 0.85; transform: translateY(-1px); }
  .save-btn:active { transform: translateY(0); }

  .year-pills {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    margin-bottom: 0.5rem;
    flex-wrap: wrap;
  }
  .year-pills-label {
    font-size: 0.7rem;
    color: var(--text-muted);
    margin-right: 0.25rem;
    font-weight: 500;
    letter-spacing: 0.02em;
  }
  .year-pill {
    padding: 0.18rem 0.5rem;
    font-size: 0.72rem;
    font-weight: 500;
    border: 1px solid var(--border-medium);
    background: var(--bg-card);
    color: var(--text-secondary);
    border-radius: 12px;
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  .year-pill.selected {
    background: var(--accent-primary);
    color: var(--text-on-dark);
    border-color: var(--accent-primary);
    font-weight: 600;
  }
  .year-pill:hover:not(.selected) { background: var(--bg-hover); border-color: var(--accent-primary); }
  .year-pill-action {
    padding: 0.15rem 0.4rem;
    font-size: 0.66rem;
    font-weight: 500;
    border: 1px dashed var(--border-medium);
    background: transparent;
    color: var(--text-muted);
    border-radius: 12px;
    cursor: pointer;
    margin-left: 0.25rem;
    transition: all var(--transition-fast);
  }
  .year-pill-action:hover { background: var(--bg-hover); color: var(--text-primary); border-color: var(--text-muted); }

  .chart-container {
    position: relative;
    height: 400px;
    width: 100%;
    background: var(--bg-card);
    border: 1px solid var(--border-light);
    border-radius: var(--radius-md);
    padding: 0.75rem;
    box-shadow: var(--shadow-card);
    animation: fadeIn 0.4s ease;
  }

  @media (max-width: 640px) {
    .chart-container { height: 250px; }
  }

  :global(.sr-only) {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }
</style>
