<script>
  import { onMount } from 'svelte';
  import { selectedIndicators, selectedGeoType, indicatorsMeta } from '../stores.js';

  let allIndicators = [];
  let categoryOrder = [];
  let loadingIndicators = true;
  let expandedCategories = {};
  let searchText = '';
  let debouncedSearchText = '';

  // Debounce search input (300ms)
  let searchTimer;
  $: {
    clearTimeout(searchTimer);
    const val = searchText;
    searchTimer = setTimeout(() => { debouncedSearchText = val; }, 300);
  }

  onMount(async () => {
    try {
      const [indResp, catResp] = await Promise.all([
        fetch('/api/indicators'),
        fetch('/api/indicators/categories'),
      ]);
      allIndicators = await indResp.json();
      categoryOrder = await catResp.json();
      indicatorsMeta.set(allIndicators);
      // Start with all categories collapsed
      for (const cat of categoryOrder) {
        expandedCategories[cat] = false;
      }
    } catch (e) {
      console.error('Failed to load indicators:', e);
    } finally {
      loadingIndicators = false;
    }
  });

  function isAvailable(ind) {
    if (!ind.geo_types) return true;
    return ind.geo_types.includes($selectedGeoType);
  }

  // Are we actively searching? (uses debounced text for performance)
  $: isSearching = debouncedSearchText.trim().length > 0;
  $: searchQuery = debouncedSearchText.trim().toLowerCase();

  $: grouped = (() => {
    // Reference $selectedGeoType so Svelte re-renders when geo tab changes
    const _geoType = $selectedGeoType;
    const map = {};
    for (const ind of allIndicators) {
      // Filter by search query if active
      if (isSearching && !ind.label.toLowerCase().includes(searchQuery) && !ind.key.toLowerCase().includes(searchQuery)) continue;
      const cat = ind.category;
      if (!map[cat]) map[cat] = [];
      map[cat].push(ind);
    }
    const ordered = [];
    for (const cat of categoryOrder) {
      if (map[cat]) ordered.push([cat, map[cat]]);
    }
    for (const [cat, items] of Object.entries(map)) {
      if (!categoryOrder.includes(cat)) ordered.push([cat, items]);
    }
    return ordered;
  })();

  // Remove selected indicators that are unavailable for this geo_type
  // Guard: don't filter until indicators have loaded (otherwise URL-restored selections get wiped)
  $: {
    if (allIndicators.length > 0) {
      const current = $selectedIndicators;
      const valid = current.filter(k => {
        const ind = allIndicators.find(i => i.key === k);
        return ind ? isAvailable(ind) : false;
      });
      if (valid.length !== current.length) {
        selectedIndicators.set(valid);
      }
    }
  }

  // Count selected per category
  $: selectedCountByCategory = (() => {
    const counts = {};
    for (const [cat, items] of grouped) {
      counts[cat] = items.filter(i => $selectedIndicators.includes(i.key)).length;
    }
    return counts;
  })();

  function toggle(key) {
    selectedIndicators.update(sel => {
      if (sel.includes(key)) return sel.filter(k => k !== key);
      return [...sel, key];
    });
  }

  function selectAllGroup(cat, items) {
    const available = items.filter(i => isAvailable(i));
    const keys = available.map(i => i.key);
    selectedIndicators.update(sel => {
      const existing = new Set(sel);
      const allSelected = keys.every(k => existing.has(k));
      if (allSelected) {
        return sel.filter(k => !keys.includes(k));
      }
      keys.forEach(k => existing.add(k));
      return [...existing];
    });
  }

  function toggleCategory(cat) {
    expandedCategories[cat] = !expandedCategories[cat];
    expandedCategories = expandedCategories; // trigger reactivity
  }

  const sourceBadgeColor = {
    'census': 'var(--accent-primary)',
    'derived': 'var(--accent-primary)',
    'bls': 'var(--color-geaux)',
    'bea': 'var(--color-file)',
    'fred': 'var(--color-iris)',
    'qcew': 'var(--color-geaux)',
  };

  function sourceLabel(source) {
    if (source === 'census' || source === 'derived') return 'ACS';
    if (source === 'fred') return 'FRED';
    if (source === 'qcew') return 'QCEW';
    return source.toUpperCase();
  }
</script>

<div class="indicator-panel">
  <h3>Indicators</h3>

  {#if loadingIndicators}
    <p class="loading-text">Loading...</p>
  {:else}
    <div class="search-box">
      <input
        type="text"
        placeholder="Search indicators..."
        bind:value={searchText}
      />
      {#if searchText}
        <button class="search-clear" on:click={() => { searchText = ''; }} aria-label="Clear search">&times;</button>
      {/if}
    </div>
    {#each grouped as [category, items]}
      {@const availableCount = items.filter(i => isAvailable(i)).length}
      {@const selectedCount = selectedCountByCategory[category] || 0}
      <div class="group">
        <button
          class="group-header"
          on:click={() => toggleCategory(category)}
          class:has-selected={selectedCount > 0}
          aria-expanded={expandedCategories[category] || false}
        >
          <span class="expand-icon">{(expandedCategories[category] || isSearching) ? '\u25BC' : '\u25B6'}</span>
          <span class="cat-name">{category}</span>
          <span class="cat-count">
            {#if selectedCount > 0}
              <span class="selected-badge">{selectedCount}</span>
            {/if}
            <span class="total-count">{items.length}</span>
          </span>
        </button>

        {#if expandedCategories[category] || isSearching}
          <div class="group-body">
            <button class="select-all" on:click|stopPropagation={() => selectAllGroup(category, items)}>
              {items.filter(i => isAvailable(i)).every(i => $selectedIndicators.includes(i.key)) ? 'Deselect all' : 'Select all'}
            </button>
            {#each items as ind}
              {@const available = isAvailable(ind)}
              <label
                class="checkbox-row"
                class:disabled={!available}
                title={available ? ind.key : `Not available for ${$selectedGeoType === 'msa' ? 'metros' : $selectedGeoType === 'state' ? 'states' : $selectedGeoType === 'county' ? 'counties' : $selectedGeoType === 'micro' ? 'micros' : 'places'}`}
              >
                <input
                  type="checkbox"
                  checked={$selectedIndicators.includes(ind.key)}
                  disabled={!available}
                  on:change={() => toggle(ind.key)}
                />
                <span class="ind-label">{ind.label}</span>
                <span class="source-tag" style="background: {sourceBadgeColor[ind.source] || '#666'}">{sourceLabel(ind.source)}</span>
              </label>
            {/each}
          </div>
        {/if}
      </div>
    {/each}
  {/if}
</div>

<style>
  .indicator-panel { margin-bottom: 1rem; }
  h3 {
    margin: 0 0 0.5rem;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted);
    font-weight: 600;
  }
  .loading-text { font-size: 0.8rem; color: var(--text-muted); }

  .search-box {
    position: relative;
    margin-bottom: 0.5rem;
  }
  .search-box input {
    width: 100%;
    padding: 0.4rem 1.8rem 0.4rem 0.5rem;
    border: 1px solid var(--border-medium);
    border-radius: var(--radius-sm);
    font-size: 0.78rem;
    font-family: inherit;
    box-sizing: border-box;
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  }
  .search-box input:focus { outline: none; border-color: var(--accent-primary); box-shadow: 0 0 0 3px rgba(14,120,190,0.1); }
  .search-box input::placeholder { color: var(--text-muted); }
  .search-clear {
    position: absolute;
    right: 0.35rem;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    cursor: pointer;
    font-size: 1rem;
    color: var(--text-muted);
    padding: 0;
    line-height: 1;
    transition: color var(--transition-fast);
  }
  .search-clear:hover { color: var(--negative); }
  .group { margin-bottom: 0.15rem; }

  .group-header {
    display: flex;
    align-items: center;
    width: 100%;
    padding: 0.38rem 0.4rem;
    border: none;
    border-bottom: 1px solid var(--border-light);
    background: var(--bg-muted);
    cursor: pointer;
    text-align: left;
    gap: 0.3rem;
    border-radius: var(--radius-sm);
    transition: background var(--transition-fast);
  }
  .group-header:hover { background: var(--bg-hover); }
  .group-header.has-selected { background: var(--bg-selected); }

  .expand-icon {
    font-size: 0.6rem;
    color: var(--text-muted);
    width: 0.8rem;
    flex-shrink: 0;
    transition: transform var(--transition-fast);
  }

  .cat-name {
    font-size: 0.74rem;
    font-weight: 700;
    color: var(--color-riviere);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    flex: 1;
  }

  .cat-count {
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  .selected-badge {
    background: var(--accent-primary);
    color: var(--text-on-dark);
    font-size: 0.58rem;
    font-weight: 700;
    padding: 0.08rem 0.3rem;
    border-radius: 8px;
    min-width: 1rem;
    text-align: center;
    animation: scaleIn 0.2s ease;
  }

  .total-count {
    font-size: 0.62rem;
    color: var(--text-muted);
  }

  .group-body {
    padding: 0.15rem 0 0.3rem 0.4rem;
    animation: fadeIn 0.2s ease;
  }

  .select-all {
    background: none;
    border: none;
    color: var(--accent-primary);
    font-size: 0.66rem;
    cursor: pointer;
    text-decoration: underline;
    padding: 0.1rem 0;
    margin-bottom: 0.1rem;
    display: block;
    transition: color var(--transition-fast);
  }
  .select-all:hover { color: var(--color-southern-sky); }

  .checkbox-row {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.15rem 0;
    cursor: pointer;
    font-size: 0.78rem;
    border-radius: var(--radius-sm);
    transition: background var(--transition-fast);
  }
  .checkbox-row:hover:not(.disabled) { background: var(--bg-hover); }
  .checkbox-row.disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }
  .checkbox-row input { margin: 0; cursor: pointer; accent-color: var(--accent-primary); }
  .checkbox-row.disabled input { cursor: not-allowed; }
  .ind-label { color: var(--text-primary); flex: 1; }
  .source-tag {
    padding: 0.06rem 0.28rem;
    border-radius: 3px;
    font-size: 0.58rem;
    color: var(--text-on-dark);
    font-weight: 600;
    flex-shrink: 0;
    letter-spacing: 0.02em;
  }
</style>
