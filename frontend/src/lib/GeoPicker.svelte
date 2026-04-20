<script>
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { selectedGeos, selectedGeoType, highlightGeo, pendingUrlGeoIds, urlRestoreReady } from '../stores.js';

  let allGeos = [];
  let searchText = '';
  let debouncedSearchText = '';
  let showDropdown = false;
  let loadingGeos = true;
  let stateFilter = '';
  let allStates = [];

  // Debounce search input (300ms)
  let searchTimer;
  $: {
    clearTimeout(searchTimer);
    const val = searchText;
    searchTimer = setTimeout(() => { debouncedSearchText = val; }, 300);
  }

  // 40 peer metros (Baton Rouge comparison set — from acs_40m.py)
  const PEER_CBSAS = [
    '12260','11700','12940','13140','13820','15180','15980','16700',
    '16860','17900','18580','19660','22220','24860','26620','26900',
    '27140','27260','28660','28940','29180','29460','30460','30780',
    '31140','32580','32820','33660','34980','35380','35840','36420',
    '37340','37860','38940','43340','44180','46140','48620','49180'
  ];

  onMount(() => {
    fetchGeos($selectedGeoType);
  });

  async function fetchGeos(geoType) {
    loadingGeos = true;
    allGeos = [];
    try {
      const resp = await fetch(`/api/geographies?type=${geoType}`);
      const data = await resp.json();
      allGeos = data;

      if (geoType === 'county' || geoType === 'place') {
        // County: "Autauga County, Alabama" — state is last part after comma
        // Place: "Birmingham city, Alabama" — same pattern
        const states = new Set();
        data.forEach(g => {
          const parts = g.name.split(',');
          if (parts.length >= 2) {
            states.add(parts[parts.length - 1].trim());
          }
        });
        allStates = [...states].sort();
      } else if (geoType === 'msa' || geoType === 'micro') {
        // MSA: "Memphis, TN-MS-AR Metro Area"
        // Micro: "Abilene, TX Micro Area"
        const states = new Set();
        data.forEach(g => {
          const match = g.name.match(/,\s*([A-Z]{2}(?:-[A-Z]{2})*)/);
          if (match) {
            match[1].split('-').forEach(s => states.add(s));
          }
        });
        allStates = [...states].sort();
      }

      // Resolve pending geo IDs from URL sharing
      const pending = get(pendingUrlGeoIds);
      if (pending && pending.length > 0) {
        const matched = data.filter(g => pending.includes(g.id));
        if (matched.length > 0) {
          selectedGeos.set(matched);
        }
        pendingUrlGeoIds.set(null);
        urlRestoreReady.set(true);
      }
    } catch (e) {
      console.error('Failed to load geographies:', e);
    } finally {
      loadingGeos = false;
    }
  }

  function switchGeoType(type) {
    selectedGeoType.set(type);
    selectedGeos.set([]);
    stateFilter = '';
    searchText = '';
    allStates = [];
    fetchGeos(type);
  }

  // For states/counties: filter dropdown list based on typing + state filter
  // Full list for <select> dropdown (no cap)
  $: selectList = (() => {
    let pool = allGeos;

    if (($selectedGeoType === 'county' || $selectedGeoType === 'place') && stateFilter) {
      pool = pool.filter(g => g.name.endsWith(', ' + stateFilter));
    }

    // Exclude already-selected
    const selectedIds = new Set($selectedGeos.map(g => g.id));
    pool = pool.filter(g => !selectedIds.has(g.id));

    return pool;
  })();

  // Capped list for search autocomplete (uses debounced text for performance)
  $: filtered = (() => {
    if ($selectedGeoType === 'msa' || $selectedGeoType === 'micro') {
      if (debouncedSearchText.length === 0 && !stateFilter) return [];
      const selectedIds = new Set($selectedGeos.map(g => g.id));
      let pool = allGeos.filter(m => !selectedIds.has(m.id));
      if (stateFilter) {
        pool = pool.filter(m => metroMatchesState(m.name, stateFilter));
      }
      if (debouncedSearchText.length > 0) {
        const q = debouncedSearchText.toLowerCase();
        pool = pool.filter(m => m.name.toLowerCase().includes(q) || m.id.includes(debouncedSearchText));
      }
      return pool.slice(0, 30);
    }
    // For states/counties/places: filter by search text, cap at 30
    let pool = selectList;
    if (debouncedSearchText.length > 0) {
      const q = debouncedSearchText.toLowerCase();
      pool = pool.filter(m =>
        m.name.toLowerCase().includes(q) || m.id.includes(debouncedSearchText)
      );
    }
    return pool.slice(0, 30);
  })();

  // For states/counties: show dropdown on focus even without typing
  $: showResults = (() => {
    if ($selectedGeoType === 'msa' || $selectedGeoType === 'micro') {
      return showDropdown && filtered.length > 0;
    }
    return showDropdown && (filtered.length > 0 || searchText.length > 0);
  })();

  // Show MSA dropdown automatically when state filter changes
  $: if (($selectedGeoType === 'msa' || $selectedGeoType === 'micro') && stateFilter) showDropdown = true;

  function addGeo(geo) {
    selectedGeos.update(geos => {
      if (geos.find(g => g.id === geo.id)) return geos;
      return [...geos, geo];
    });
    searchText = '';
    if ($selectedGeoType === 'msa' || $selectedGeoType === 'micro') showDropdown = false;
  }

  function removeGeo(id) {
    selectedGeos.update(geos => geos.filter(g => g.id !== id));
    // If removing the highlighted geo, clear highlight
    if ($highlightGeo === id) {
      highlightGeo.set(null);
    }
  }

  function metroMatchesState(name, stateAbbr) {
    const match = name.match(/,\s*([A-Z]{2}(?:-[A-Z]{2})*)/);
    if (!match) return false;
    return match[1].split('-').includes(stateAbbr);
  }

  function addAllInState() {
    if (!stateFilter) return;
    selectedGeos.update(geos => {
      const existing = new Set(geos.map(g => g.id));
      const newGeos = allGeos.filter(
        m => metroMatchesState(m.name, stateFilter) && !existing.has(m.id)
      );
      return [...geos, ...newGeos];
    });
  }

  // Count metros in selected state (for button label)
  $: metrosInState = (() => {
    if (($selectedGeoType !== 'msa' && $selectedGeoType !== 'micro') || !stateFilter) return 0;
    return allGeos.filter(m => metroMatchesState(m.name, stateFilter)).length;
  })();

  function addPeerMetros() {
    selectedGeos.update(geos => {
      const existing = new Set(geos.map(g => g.id));
      const newGeos = allGeos.filter(
        m => PEER_CBSAS.includes(m.id) && !existing.has(m.id)
      );
      return [...geos, ...newGeos];
    });
  }

  function clearAll() {
    selectedGeos.set([]);
    highlightGeo.set(null);
  }

  function handleInputFocus() {
    showDropdown = true;
  }

  function handleInputBlur() {
    setTimeout(() => { showDropdown = false; }, 200);
  }

  function toggleHighlight(id) {
    // Toggle: if already highlighted, unhighlight; otherwise set
    if ($highlightGeo === id) {
      highlightGeo.set(null);
    } else {
      highlightGeo.set(id);
    }
  }

  function shortName(name) {
    if ($selectedGeoType === 'msa' || $selectedGeoType === 'micro') return name.split(',')[0];
    if ($selectedGeoType === 'county' || $selectedGeoType === 'place') return name.split(',')[0];
    return name;
  }

  // Add from dropdown select (for states/counties)
  function handleSelectChange(e) {
    const id = e.target.value;
    if (!id) return;
    const geo = allGeos.find(g => g.id === id);
    if (geo) addGeo(geo);
    e.target.value = '';
  }
</script>

<div class="geo-picker">
  <h3>Geographies</h3>

  <div class="geo-tabs">
    <button class="tab" class:active={$selectedGeoType === 'msa'} on:click={() => switchGeoType('msa')}>Metros</button>
    <button class="tab" class:active={$selectedGeoType === 'state'} on:click={() => switchGeoType('state')}>States</button>
    <button class="tab" class:active={$selectedGeoType === 'county'} on:click={() => switchGeoType('county')}>Counties</button>
    <button class="tab" class:active={$selectedGeoType === 'micro'} on:click={() => switchGeoType('micro')}>Micros</button>
    <button class="tab" class:active={$selectedGeoType === 'place'} on:click={() => switchGeoType('place')}>Places</button>
  </div>

  {#if $selectedGeoType === 'county' || $selectedGeoType === 'msa' || $selectedGeoType === 'micro' || $selectedGeoType === 'place'}
    <label class="state-filter-label">
      <select class="state-filter" bind:value={stateFilter}>
        <option value="">{($selectedGeoType === 'msa' || $selectedGeoType === 'micro') ? 'Filter by state' : 'All states'}</option>
        {#each allStates as st}
          <option value={st}>{st}</option>
        {/each}
      </select>
    </label>
  {/if}

  {#if $selectedGeoType === 'state' || $selectedGeoType === 'county' || $selectedGeoType === 'place'}
    <!-- Combo: dropdown select + text search -->
    <div class="combo-picker">
      <label class="select-label">
        <select class="geo-select" on:change={handleSelectChange} disabled={loadingGeos}>
          <option value="">
            {loadingGeos ? 'Loading...' : `— Select ${$selectedGeoType === 'state' ? 'a state' : $selectedGeoType === 'county' ? 'a county' : 'a place'} —`}
          </option>
          {#each selectList as geo}
            <option value={geo.id}>{geo.name}</option>
          {/each}
        </select>
      </label>
      <div class="or-divider">or type to search</div>
    </div>
  {/if}

  <div class="search-wrapper">
    <input
      type="text"
      placeholder={loadingGeos ? "Loading..." : `Search ${$selectedGeoType === 'msa' ? 'metros' : $selectedGeoType === 'state' ? 'states' : $selectedGeoType === 'county' ? 'counties' : $selectedGeoType === 'micro' ? 'micros' : 'places'}...`}
      bind:value={searchText}
      on:input={() => { showDropdown = true; }}
      on:focus={handleInputFocus}
      on:blur={handleInputBlur}
      disabled={loadingGeos}
      role="combobox"
      aria-expanded={showResults}
      aria-controls="geo-dropdown"
      aria-autocomplete="list"
    />
    {#if showResults && filtered.length > 0}
      <ul class="dropdown" id="geo-dropdown" role="listbox">
        {#each filtered as geo}
          <li role="option" aria-selected="false" on:mousedown={() => addGeo(geo)}>
            <span class="geo-name">{geo.name}</span>
            <span class="geo-code">{geo.id}</span>
          </li>
        {/each}
      </ul>
    {/if}
  </div>

  <div class="quick-actions">
    {#if $selectedGeoType === 'msa'}
      {#if stateFilter}
        <button class="btn-small" on:click={addAllInState} disabled={loadingGeos}>
          + All {stateFilter} Metros ({metrosInState})
        </button>
      {/if}
      <button class="btn-small" on:click={addPeerMetros} disabled={loadingGeos}>
        + 40 Peer Metros
      </button>
    {/if}
    {#if $selectedGeoType === 'micro' && stateFilter}
      <button class="btn-small" on:click={addAllInState} disabled={loadingGeos}>
        + All {stateFilter} Micros ({metrosInState})
      </button>
    {/if}
    <button class="btn-small btn-clear" on:click={clearAll}>Clear All</button>
  </div>

  <div class="chips">
    {#each $selectedGeos as geo}
      <span
        class="chip"
        class:highlight={geo.id === $highlightGeo}
        role="button"
        tabindex="0"
        on:contextmenu|preventDefault={() => toggleHighlight(geo.id)}
        on:dblclick={() => toggleHighlight(geo.id)}
        on:keydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleHighlight(geo.id); } }}
        title={geo.id === $highlightGeo ? 'Double-click or right-click to remove highlight' : 'Double-click or right-click to highlight'}
      >
        {shortName(geo.name)}
        <button class="chip-remove" aria-label="Remove {shortName(geo.name)}" on:click={() => removeGeo(geo.id)}>&times;</button>
      </span>
    {/each}
  </div>

  {#if $selectedGeos.length > 0}
    <div class="count">
      {$selectedGeos.length} selected
      {#if $highlightGeo}
        <button class="clear-highlight" on:click={() => highlightGeo.set(null)}>Clear highlight</button>
      {/if}
    </div>
  {/if}
</div>

<style>
  .geo-picker { margin-bottom: 1rem; }
  h3 {
    margin: 0 0 0.5rem;
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted);
    font-weight: 600;
  }

  .geo-tabs { display: flex; gap: 0; margin-bottom: 0.5rem; }
  .tab {
    flex: 1;
    padding: 0.35rem 0.25rem;
    font-size: 0.7rem;
    font-weight: 500;
    border: 1px solid var(--border-medium);
    background: var(--bg-card);
    color: var(--text-secondary);
    cursor: pointer;
    min-height: var(--touch-min);
    transition: all var(--transition-fast);
    font-family: var(--font-body);
    letter-spacing: 0.03em;
    text-transform: uppercase;
  }
  .tab:first-child { border-radius: var(--radius-sm) 0 0 var(--radius-sm); }
  .tab:last-child { border-radius: 0 var(--radius-sm) var(--radius-sm) 0; }
  .tab:not(:first-child) { border-left: none; }
  .tab.active { background: var(--accent-primary); color: var(--text-on-dark); border-color: var(--accent-primary); font-weight: 600; box-shadow: 0 2px 8px rgba(14,120,190,0.2); }
  .tab:hover:not(.active) { background: var(--bg-hover); color: var(--accent-primary); border-color: var(--accent-primary); }

  .state-filter-label { display: block; margin-bottom: 0.4rem; }
  .state-filter {
    width: 100%;
    padding: 0.35rem 0.5rem;
    border: 1px solid var(--border-medium);
    border-radius: var(--radius-sm);
    font-size: 0.82rem;
    box-sizing: border-box;
    min-height: var(--touch-min);
    transition: border-color var(--transition-fast);
  }
  .state-filter:focus { border-color: var(--accent-primary); outline: none; }

  .combo-picker { margin-bottom: 0.4rem; }
  .select-label { display: block; }
  .geo-select {
    width: 100%;
    padding: 0.4rem 0.5rem;
    border: 1px solid var(--border-medium);
    border-radius: var(--radius-sm);
    font-size: 0.82rem;
    box-sizing: border-box;
    min-height: var(--touch-min);
    transition: border-color var(--transition-fast);
  }
  .geo-select:focus { border-color: var(--accent-primary); outline: none; }
  .or-divider {
    text-align: center;
    font-size: 0.66rem;
    color: var(--text-muted);
    margin: 0.25rem 0;
    letter-spacing: 0.02em;
  }

  .search-wrapper { position: relative; }
  input {
    width: 100%;
    padding: 0.5rem 0.6rem;
    border: 1px solid var(--border-medium);
    border-radius: var(--radius-sm);
    font-size: 0.85rem;
    box-sizing: border-box;
    min-height: var(--touch-min);
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  }
  input:focus { outline: none; border-color: var(--accent-primary); box-shadow: 0 0 0 3px rgba(14,120,190,0.1); }
  .dropdown {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    background: var(--bg-card);
    border: 1px solid var(--border-medium);
    border-top: none;
    border-radius: 0 0 var(--radius-md) var(--radius-md);
    max-height: 200px;
    overflow-y: auto;
    z-index: 100;
    list-style: none;
    margin: 0;
    padding: 0;
    box-shadow: 0 8px 24px rgba(21,18,62,0.12), 0 2px 6px rgba(0,0,0,0.06);
    animation: dropdownReveal 0.2s ease;
  }

  @keyframes dropdownReveal {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .dropdown li {
    padding: 0.45rem 0.6rem;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.82rem;
    transition: background var(--transition-fast);
    border-bottom: 1px solid var(--border-light);
  }
  .dropdown li:last-child { border-bottom: none; }
  .dropdown li:hover { background: var(--bg-hover); }
  .geo-code { color: var(--text-muted); font-size: 0.7rem; font-variant-numeric: tabular-nums; }
  .quick-actions { display: flex; gap: 0.4rem; margin: 0.5rem 0; flex-wrap: wrap; }
  .btn-small {
    padding: 0.3rem 0.65rem;
    font-size: 0.68rem;
    font-weight: 600;
    border: 1px solid var(--border-medium);
    background: var(--bg-card);
    color: var(--text-secondary);
    border-radius: var(--radius-sm);
    cursor: pointer;
    min-height: var(--touch-min);
    transition: all var(--transition-fast);
    font-family: var(--font-body);
    letter-spacing: 0.02em;
  }
  .btn-small:hover { background: var(--accent-primary); color: var(--text-on-dark); border-color: var(--accent-primary); transform: translateY(-1px); }
  .btn-small:active { transform: translateY(0); }
  .btn-small:disabled { opacity: 0.5; cursor: default; transform: none; }
  .btn-clear { border-color: var(--text-muted); color: var(--text-muted); }
  .btn-clear:hover { background: var(--text-muted); color: var(--text-on-dark); border-color: var(--text-muted); }
  .chips { display: flex; flex-wrap: wrap; gap: 0.3rem; margin-top: 0.5rem; }
  .chip {
    display: inline-flex;
    align-items: center;
    padding: 0.22rem 0.55rem;
    background: var(--bg-selected);
    border-radius: var(--radius-lg);
    font-size: 0.73rem;
    color: var(--text-primary);
    cursor: default;
    transition: all 0.2s ease;
    border: 1px solid transparent;
    animation: scaleIn 0.25s ease;
  }
  .chip:hover { border-color: var(--border-medium); transform: translateY(-1px); box-shadow: 0 2px 6px rgba(0,0,0,0.06); }
  .chip.highlight { background: var(--highlight-bg); font-weight: 600; color: var(--highlight-text); border-color: var(--highlight-bg-hover); box-shadow: 0 0 0 2px rgba(253,230,138,0.3); }
  .chip-remove {
    margin-left: 0.3rem;
    background: none;
    border: none;
    cursor: pointer;
    font-size: 0.9rem;
    color: var(--text-muted);
    padding: 0;
    line-height: 1;
    transition: color var(--transition-fast);
  }
  .chip-remove:hover { color: var(--negative); }
  .count {
    font-size: 0.72rem;
    color: var(--text-muted);
    margin-top: 0.3rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: 500;
  }
  .clear-highlight {
    background: none;
    border: none;
    color: var(--accent-primary);
    font-size: 0.68rem;
    cursor: pointer;
    text-decoration: underline;
    padding: 0;
    transition: color var(--transition-fast);
  }
  .clear-highlight:hover { color: var(--color-southern-sky); }

  @media (max-width: 640px) {
    .search-wrapper input { width: 100%; font-size: 16px; } /* prevent iOS zoom */
  }
</style>
