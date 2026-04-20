<script>
  export let data = {};
  export let title = 'Age Distribution';

  // Ordered age bucket keys and their display labels
  const AGE_BUCKETS = [
    { key: 'pop_under_5',  label: 'Under 5' },
    { key: 'pop_5_to_9',   label: '5–9' },
    { key: 'pop_10_to_14', label: '10–14' },
    { key: 'pop_15_to_19', label: '15–19' },
    { key: 'pop_20_to_24', label: '20–24' },
    { key: 'pop_25_to_34', label: '25–34' },
    { key: 'pop_35_to_44', label: '35–44' },
    { key: 'pop_45_to_54', label: '45–54' },
    { key: 'pop_55_to_59', label: '55–59' },
    { key: 'pop_60_to_64', label: '60–64' },
    { key: 'pop_65_to_74', label: '65–74' },
    { key: 'pop_75_to_84', label: '75–84' },
    { key: 'pop_85_plus',  label: '85+' },
  ];

  $: buckets = AGE_BUCKETS.map((b) => ({
    ...b,
    value: data[b.key] ?? null,
  }));

  $: maxVal = Math.max(...buckets.map(b => b.value || 0), 1);

  function formatNum(v) {
    if (v == null) return '—';
    return Number(v).toLocaleString('en-US');
  }

</script>

<div class="pyramid">
  <div class="pyramid-title">{title}</div>
  <div class="bars-container">
    {#each buckets as bucket, i}
      <div class="bar-row" style="animation-delay: {0.05 + i * 0.04}s">
        <div class="bar-label">{bucket.label}</div>
        <div class="bar-track">
          <div
            class="bar-fill"
            style="width: {bucket.value ? (bucket.value / maxVal * 100) : 0}%;"
            title="{bucket.label}: {formatNum(bucket.value)}"
          ></div>
        </div>
        <div class="bar-value">{formatNum(bucket.value)}</div>
      </div>
    {/each}
  </div>
</div>

<style>
  .pyramid {
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
  .pyramid:hover {
    box-shadow: 0 6px 20px rgba(21,18,62,0.08);
    transform: translateY(-2px);
  }

  .pyramid-title {
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 0.65rem;
    text-align: center;
  }

  .bars-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 3px;
    overflow: hidden;
  }

  .bar-row {
    display: flex;
    align-items: center;
    gap: 0.45rem;
  }

  .bar-label {
    width: 52px;
    min-width: 52px;
    text-align: right;
    font-size: 0.68rem;
    color: var(--text-secondary);
    white-space: nowrap;
    font-weight: 500;
  }

  .bar-track {
    flex: 1;
    height: 16px;
    background: var(--bg-muted);
    border-radius: 3px;
    overflow: hidden;
  }

  .bar-row {
    opacity: 0;
    animation: fadeInUp 0.4s ease forwards;
  }

  .bar-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94);
    min-width: 1px;
    background: linear-gradient(90deg, var(--color-iris) 0%, var(--color-iris-light, #8b5fa8) 100%);
    position: relative;
  }
  .bar-fill::after {
    content: '';
    position: absolute;
    top: 0;
    right: 0;
    width: 2px;
    height: 100%;
    background: rgba(255,255,255,0.4);
    border-radius: 0 3px 3px 0;
  }

  .bar-value {
    width: 58px;
    min-width: 58px;
    text-align: right;
    font-size: 0.66rem;
    color: var(--text-muted);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }

  @media (max-width: 640px) {
    .pyramid {
      min-height: 240px;
    }

    .bar-label {
      width: 42px;
      min-width: 42px;
      font-size: 0.6rem;
    }

    .bar-value {
      width: 48px;
      min-width: 48px;
      font-size: 0.58rem;
    }
  }
</style>
