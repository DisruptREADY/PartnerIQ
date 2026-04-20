<script>
  import { selectedYears, selectedIndicators, indicatorsMeta, acsDataset } from '../stores.js';

  // All possible years (union of all sources)
  const ALL_YEARS = [];
  for (let y = 2010; y <= 2026; y++) ALL_YEARS.push(y);

  // Compute unavailable years from selected indicators' metadata
  $: unavailableYears = (() => {
    const meta = $indicatorsMeta;
    const selected = $selectedIndicators;
    const ds = $acsDataset;
    if (!meta.length || !selected.length) return new Set();

    const blocked = new Set();
    for (const key of selected) {
      const ind = meta.find(m => m.key === key);
      if (!ind) continue;
      // Use 5yr years if acs5 selected, otherwise default available_years
      const avail = ds === 'acs5' && ind.available_years_5yr?.length
        ? ind.available_years_5yr
        : ind.available_years;
      if (!avail || !avail.length) continue;
      const availSet = new Set(avail);
      for (const y of ALL_YEARS) {
        if (!availSet.has(y)) blocked.add(y);
      }
    }
    return blocked;
  })();

  function toggle(year) {
    selectedYears.update(yrs => {
      if (yrs.includes(year)) return yrs.filter(y => y !== year);
      return [...yrs, year].sort();
    });
  }

  function selectRange(start, end) {
    const range = [];
    for (let y = start; y <= end; y++) {
      if (!unavailableYears.has(y)) range.push(y);
    }
    selectedYears.set(range);
  }

  // Deselect any currently-selected years that became unavailable
  $: {
    if (unavailableYears.size > 0) {
      const current = $selectedYears;
      const valid = current.filter(y => !unavailableYears.has(y));
      if (valid.length !== current.length) {
        selectedYears.set(valid);
      }
    }
  }
</script>

<div class="year-picker">
  <h3>Years</h3>

  <div class="quick-ranges">
    <button class="btn-small" on:click={() => selectRange(2024, 2026)}>2024-26</button>
    <button class="btn-small" on:click={() => selectRange(2021, 2026)}>Last 5yr</button>
    <button class="btn-small" on:click={() => selectRange(2010, 2026)}>All</button>
  </div>

  <div class="year-grid">
    {#each ALL_YEARS as year}
      {@const disabled = unavailableYears.has(year)}
      <label class="year-box" class:disabled class:selected={$selectedYears.includes(year)}>
        <input
          type="checkbox"
          checked={$selectedYears.includes(year)}
          disabled={disabled}
          on:change={() => toggle(year)}
        />
        {year}
        {#if disabled}
          <span class="no-acs" title="Not available for all selected indicators">*</span>
        {/if}
      </label>
    {/each}
  </div>

  {#if unavailableYears.size > 0}
    <p class="note">* Not available for all selected indicators</p>
  {/if}
</div>

<style>
  .year-picker { margin-bottom: 1rem; }
  h3 { margin: 0 0 0.5rem; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.05em; color: #555; }
  .quick-ranges { display: flex; gap: 0.4rem; margin-bottom: 0.5rem; }
  .btn-small {
    padding: 0.25rem 0.5rem;
    font-size: 0.72rem;
    border: 1px solid #1f4e79;
    background: white;
    color: #1f4e79;
    border-radius: 3px;
    cursor: pointer;
  }
  .btn-small:hover { background: #1f4e79; color: white; }
  .year-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.2rem; }
  .year-box {
    display: flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.2rem 0.3rem;
    font-size: 0.8rem;
    cursor: pointer;
    border-radius: 3px;
  }
  .year-box.selected { background: #e8f0fe; }
  .year-box.disabled { opacity: 0.4; cursor: not-allowed; }
  .year-box input { margin: 0; cursor: pointer; }
  .no-acs { color: #c00; font-size: 0.7rem; }
  .note { font-size: 0.7rem; color: #888; margin-top: 0.3rem; font-style: italic; }
</style>
