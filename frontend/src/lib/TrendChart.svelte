<script>
  import { onMount, onDestroy, afterUpdate } from 'svelte';
  import { Chart } from './chartDefaults.js';

  export let title = '';
  export let datasets = [];  // [{label, data: [{year, value}], color}]
  export let fmt = '#,##0';

  let canvasEl;
  let chart = null;

  /**
   * Format tooltip values using the fmt string.
   */
  function formatTooltip(val) {
    if (val == null) return '—';
    const isDollar = fmt.startsWith('$');
    const isPercent = fmt.endsWith('%');
    const cleaned = fmt.replace('$', '').replace('%', '');
    let decimals = 0;
    const dotIdx = cleaned.indexOf('.');
    if (dotIdx >= 0) decimals = cleaned.length - dotIdx - 1;

    const num = Number(val);
    if (isNaN(num)) return '—';

    const hasComma = cleaned.includes(',');
    let formatted;
    if (hasComma) {
      formatted = num.toLocaleString('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      });
    } else {
      formatted = num.toFixed(decimals);
    }

    if (isDollar) formatted = '$' + formatted;
    if (isPercent) formatted = formatted + '%';
    return formatted;
  }

  function renderChart() {
    if (chart) chart.destroy();
    if (!canvasEl || !datasets || datasets.length === 0) return;

    // Collect all unique years across datasets
    const allYears = new Set();
    datasets.forEach(ds => {
      if (ds.data) {
        ds.data.forEach(d => allYears.add(d.year));
      }
    });
    const labels = [...allYears].sort();

    const chartDatasets = datasets.map((ds, idx) => {
      const dataByYear = {};
      if (ds.data) {
        ds.data.forEach(d => { dataByYear[d.year] = d.value; });
      }
      const color = ds.color || '#0E78BE';
      return {
        label: ds.label,
        data: labels.map(y => dataByYear[y] ?? null),
        borderColor: color,
        backgroundColor: color + '20',
        borderWidth: 2.5,
        pointRadius: 4,
        pointHoverRadius: 7,
        pointBackgroundColor: '#fff',
        pointBorderColor: color,
        pointBorderWidth: 2,
        tension: 0.3,
        spanGaps: true,
        fill: datasets.length <= 3 ? 'origin' : false,
      };
    });

    const ctx = canvasEl.getContext('2d');
    chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: chartDatasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          duration: 1000,
          easing: 'easeOutQuart',
        },
        plugins: {
          title: {
            display: !!title,
            text: title,
            font: { size: 13, weight: '600' },
            color: '#1a1a2e',
            padding: { bottom: 8 },
          },
          legend: {
            display: datasets.length > 1,
            position: 'bottom',
            labels: {
              font: { size: 10 },
              boxWidth: 12,
              padding: 8,
              usePointStyle: true,
              pointStyle: 'circle',
            },
          },
          tooltip: {
            backgroundColor: 'rgba(21,18,62,0.92)',
            titleFont: { weight: '600' },
            bodyFont: { size: 12 },
            padding: 10,
            cornerRadius: 6,
            callbacks: {
              label: function(context) {
                return context.dataset.label + ': ' + formatTooltip(context.parsed.y);
              },
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { font: { size: 10 }, color: '#8a8aa0' },
          },
          y: {
            grid: { color: '#eef0f4', lineWidth: 1 },
            ticks: {
              font: { size: 10 },
              color: '#8a8aa0',
              callback: function(val) { return formatTooltip(val); },
              maxTicksLimit: 5,
            },
            beginAtZero: false,
          },
        },
        interaction: {
          mode: 'index',
          intersect: false,
        },
      },
    });
  }

  $: if (canvasEl && datasets) {
    renderChart();
  }

  onDestroy(() => {
    if (chart) chart.destroy();
  });
</script>

<div class="trend-chart">
  <div class="chart-container">
    <!-- svelte-ignore a11y_no_interactive_element_to_noninteractive_role -->
    <canvas bind:this={canvasEl} role="img" aria-label="{title} chart"></canvas>
  </div>
</div>

<style>
  .trend-chart {
    background: var(--bg-card);
    border: 1px solid var(--border-light);
    border-radius: var(--radius-md);
    padding: 0.85rem 1rem;
    box-shadow: var(--shadow-card);
    height: 100%;
    min-height: 260px;
    display: flex;
    flex-direction: column;
    animation: fadeIn 0.4s ease;
    transition: box-shadow 0.3s ease, transform 0.3s ease;
  }
  .trend-chart:hover {
    box-shadow: 0 6px 20px rgba(21,18,62,0.08);
    transform: translateY(-2px);
  }

  .chart-container {
    position: relative;
    flex: 1;
    width: 100%;
    min-height: 0;
  }

  @media (max-width: 640px) {
    .trend-chart { min-height: 220px; }
  }
</style>
