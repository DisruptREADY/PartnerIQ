<script>
  import { onMount } from 'svelte';
  import {
    peerGeoType, peerTarget, peerDimensions,
    peerWeightProfile, peerResults,
    selectedGeos, selectedGeoType, currentView
  } from '../stores.js';
  import { apiFetch } from './api.js';

  const GEO_TYPES = [
    { value: 'msa', label: 'MSA' },
    { value: 'state', label: 'State' },
    { value: 'county', label: 'County' },
    { value: 'micro', label: 'Micro' },
    { value: 'place', label: 'Place' },
  ];

  const PROFILES = [
    { value: 'balanced', label: 'Balanced' },
    { value: 'economic', label: 'Economic' },
    { value: 'demographic', label: 'Demographic' },
    { value: 'geographic', label: 'Geographic' },
  ];

  let availableDimensions = [];
  let geoOptions = [];
  let searchQuery = '';
  let filteredGeos = [];
  let showDropdown = false;
  let loading = false;
  let buildingMessage = '';
  let errorMsg = '';

  // Fetch dimensions when geo type changes
  async function loadDimensions(geoType) {
    try {
      const resp = await apiFetch(`/api/peers/dimensions?geo_type=${geoType}`);
      if (resp.ok) {
        const data = await resp.json();
        availableDimensions = data.dimensions || [];
        // Default: all checked
        $peerDimensions = availableDimensions.map(d => d.key);
      }
    } catch {}
  }

  // Fetch geography list
  async function loadGeos(geoType) {
    try {
      const resp = await apiFetch(`/api/geographies?type=${geoType}`);
      if (resp.ok) {
        geoOptions = await resp.json();
      }
    } catch {}
  }

  onMount(() => {
    loadDimensions($peerGeoType);
    loadGeos($peerGeoType);
  });

  function switchGeoType(type) {
    $peerGeoType = type;
    $peerTarget = null;
    searchQuery = '';
    $peerResults = null;
    loadDimensions(type);
    loadGeos(type);
  }

  $: {
    if (searchQuery.length >= 2) {
      const q = searchQuery.toLowerCase();
      filteredGeos = geoOptions.filter(g => g.name.toLowerCase().includes(q)).slice(0, 15);
      showDropdown = true;
    } else {
      filteredGeos = [];
      showDropdown = false;
    }
  }

  function selectGeo(geo) {
    $peerTarget = geo;
    searchQuery = geo.name;
    showDropdown = false;
  }

  function toggleDimension(key) {
    if ($peerDimensions.includes(key)) {
      $peerDimensions = $peerDimensions.filter(d => d !== key);
    } else {
      $peerDimensions = [...$peerDimensions, key];
    }
  }

  function selectAllDimensions() {
    $peerDimensions = availableDimensions.map(d => d.key);
  }

  function clearAllDimensions() {
    $peerDimensions = [];
  }

  async function findPeers() {
    if (!$peerTarget || $peerDimensions.length === 0) return;

    loading = true;
    errorMsg = '';
    buildingMessage = '';

    // Check status first
    try {
      const statusResp = await apiFetch(`/api/peers/status?geo_type=${$peerGeoType}&year=2024`);
      if (statusResp.ok) {
        const status = await statusResp.json();
        if (!status.ready) {
          buildingMessage = 'Building peer database... this may take 30\u201360 seconds on first request.';
        }
      }
    } catch {}

    try {
      const resp = await apiFetch('/api/peers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          geo_type: $peerGeoType,
          target_id: $peerTarget.id,
          dimensions: $peerDimensions,
          weight_profile: $peerWeightProfile,
          year: 2024,
          limit: 40,
        }),
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${resp.status}`);
      }

      const data = await resp.json();
      if (data.error) {
        errorMsg = data.error;
        $peerResults = null;
      } else {
        $peerResults = data;
      }
    } catch (e) {
      errorMsg = e.message;
      $peerResults = null;
    } finally {
      loading = false;
      buildingMessage = '';
    }
  }

  function loadIntoDataPull(count) {
    if (!$peerResults) return;
    const target = $peerResults.target;
    const peers = $peerResults.peers.slice(0, count);

    const geos = [
      { id: target.geo_id, name: target.geo_name, type: $peerGeoType },
      ...peers.map(p => ({ id: p.geo_id, name: p.geo_name, type: $peerGeoType })),
    ];

    selectedGeos.set(geos);
    selectedGeoType.set($peerGeoType);
    currentView.set('data');
  }

  function scoreColor(score) {
    // Lower = greener; 0-5 = green, 5-15 = yellow, 15+ = red
    if (score <= 5) return 'var(--positive, #2e7d32)';
    if (score <= 15) return 'var(--warning-text, #b8860b)';
    return 'var(--negative, #c62828)';
  }

  function formatValue(key, val) {
    if (val == null) return '\u2014';
    if (key === 'pop' || key === 'city') return Math.round(val).toLocaleString();
    if (key === 'income' || key === 'home' || key === 'rent') return '$' + Math.round(val).toLocaleString();
    if (key === '4yr' || key === '2yr') return Math.round(val).toLocaleString();
    if (key === 'drive') return val.toFixed(1) + 'h';
    if (key === 'poverty' || key === 'education' || key === 'unemp' || key === 'growth') return val.toFixed(1) + '%';
    return String(val);
  }
</script>

<div class="peer-finder" id="main-content">
  <div class="pf-header">
    <h2>Peer Finder</h2>
    <p class="pf-subtitle">Find geographies similar to your target across demographic and economic dimensions</p>
  </div>

  <div class="pf-config">
    <!-- Geo type tabs -->
    <div class="pf-geo-tabs" role="tablist">
      {#each GEO_TYPES as gt}
        <button
          class="pf-tab"
          class:active={$peerGeoType === gt.value}
          on:click={() => switchGeoType(gt.value)}
          role="tab"
          aria-selected={$peerGeoType === gt.value}
        >{gt.label}</button>
      {/each}
    </div>

    <!-- Target search -->
    <div class="pf-search-section">
      <label class="pf-label">Target Geography</label>
      <div class="pf-search-wrap">
        <input
          type="text"
          class="pf-search-input"
          placeholder="Search for a geography..."
          bind:value={searchQuery}
          on:focus={() => { if (filteredGeos.length > 0) showDropdown = true; }}
          on:blur={() => setTimeout(() => { showDropdown = false; }, 200)}
        />
        {#if showDropdown && filteredGeos.length > 0}
          <ul class="pf-dropdown">
            {#each filteredGeos as geo}
              <li>
                <button class="pf-dropdown-item" on:mousedown|preventDefault={() => selectGeo(geo)}>
                  {geo.name}
                </button>
              </li>
            {/each}
          </ul>
        {/if}
      </div>
      {#if $peerTarget}
        <div class="pf-selected-target">
          <span class="pf-target-chip">{$peerTarget.name}</span>
        </div>
      {/if}
    </div>

    <!-- Dimensions -->
    <div class="pf-dims-section">
      <div class="pf-dims-header">
        <label class="pf-label">Dimensions</label>
        <div class="pf-dims-actions">
          <button class="pf-link-btn" on:click={selectAllDimensions}>All</button>
          <button class="pf-link-btn" on:click={clearAllDimensions}>None</button>
        </div>
      </div>
      <div class="pf-dims-grid">
        {#each availableDimensions as dim}
          <label class="pf-dim-check">
            <input type="checkbox" checked={$peerDimensions.includes(dim.key)} on:change={() => toggleDimension(dim.key)} />
            <span>{dim.label}</span>
          </label>
        {/each}
      </div>
    </div>

    <div class="pf-divider"></div>

    <!-- Weight profile + Find button -->
    <div class="pf-bottom-row">
      <div class="pf-profile-wrap">
        <label class="pf-label">Weight Profile</label>
        <select class="pf-select" bind:value={$peerWeightProfile}>
          {#each PROFILES as p}
            <option value={p.value}>{p.label}</option>
          {/each}
        </select>
      </div>
      <button
        class="pf-find-btn"
        on:click={findPeers}
        disabled={!$peerTarget || $peerDimensions.length === 0 || loading}
      >
        {#if loading}Searching...{:else}Find Peers{/if}
      </button>
    </div>
  </div>

  <!-- Loading -->
  {#if loading}
    <div class="pf-loading">
      <div class="spinner"></div>
      <p>{buildingMessage || 'Finding similar geographies...'}</p>
    </div>
  {:else if errorMsg}
    <div class="pf-error">
      <p>{errorMsg}</p>
    </div>
  {:else if $peerResults}
    <!-- Results -->
    <div class="pf-results">
      <!-- Target summary -->
      <div class="pf-target-card">
        <h3>Target: {$peerResults.target.geo_name}</h3>
        <div class="pf-target-values">
          {#each $peerResults.dimensions as dim}
            {#if $peerResults.target.values[dim.key] != null}
              <div class="pf-kv">
                <span class="pf-kv-label">{dim.label}</span>
                <span class="pf-kv-value">{formatValue(dim.key, $peerResults.target.values[dim.key])}</span>
              </div>
            {/if}
          {/each}
        </div>
      </div>

      {#if $peerResults.warnings && $peerResults.warnings.length > 0}
        <div class="pf-warnings">
          {#each $peerResults.warnings as w}
            <p>{w}</p>
          {/each}
        </div>
      {/if}

      <!-- Load into Data Pull bar -->
      <div class="pf-load-bar">
        <span class="pf-load-label">Load into Data Pull:</span>
        {#each [5, 10, 15, 20, 40] as n}
          <button class="pf-load-btn" on:click={() => loadIntoDataPull(n)} disabled={$peerResults.peers.length < 1}>
            Top {n}
          </button>
        {/each}
      </div>

      <!-- Results table -->
      <div class="pf-table-wrap">
        <table class="pf-table">
          <thead>
            <tr>
              <th class="pf-th-rank">#</th>
              <th class="pf-th-name">Geography</th>
              <th class="pf-th-score">Score</th>
              {#each $peerResults.dimensions as dim}
                <th class="pf-th-dim">{dim.label}</th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each $peerResults.peers as peer}
              <tr>
                <td class="pf-td-rank">{peer.rank}</td>
                <td class="pf-td-name">{peer.geo_name}</td>
                <td class="pf-td-score">
                  <div class="pf-score-cell">
                    <span class="pf-score-badge" style="background: {scoreColor(peer.similarity)}">
                      {peer.similarity.toFixed(1)}
                    </span>
                    <div class="pf-score-bar">
                      <div class="pf-score-bar-fill" style="width: {Math.max(4, 100 - peer.similarity * 2)}%; background: {scoreColor(peer.similarity)};"></div>
                    </div>
                  </div>
                </td>
                {#each $peerResults.dimensions as dim}
                  <td class="pf-td-dim">{formatValue(dim.key, peer.values[dim.key])}</td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {:else}
    <div class="pf-empty">
      <div class="pf-empty-icon">
        <svg width="52" height="52" viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="22" cy="22" r="16" stroke="var(--border-medium)" stroke-width="2" fill="none"/>
          <line x1="33.5" y1="33.5" x2="46" y2="46" stroke="var(--border-medium)" stroke-width="2.5" stroke-linecap="round"/>
          <circle cx="22" cy="22" r="6" stroke="var(--border-medium)" stroke-width="1.5" fill="none" stroke-dasharray="3 3"/>
          <circle cx="16" cy="18" r="2" fill="var(--border-medium)"/>
          <circle cx="26" cy="20" r="2" fill="var(--border-medium)"/>
          <circle cx="20" cy="27" r="2" fill="var(--border-medium)"/>
        </svg>
      </div>
      <p>Select a target geography and dimensions, then click <strong>Find Peers</strong>.</p>
    </div>
  {/if}
</div>

<style>
  .peer-finder {
    padding: 0 1.25rem 2rem;
  }

  .pf-header {
    text-align: center;
    padding: 1.75rem 1.5rem 1.25rem;
    margin: 0 -1.25rem 1.25rem;
    background: linear-gradient(135deg, var(--color-riviere) 0%, var(--color-riviere-dark) 100%);
    border-radius: 0 0 var(--radius-lg) var(--radius-lg);
    animation: fadeInDown 0.4s ease both;
  }
  .pf-header h2 {
    font-size: 1.5rem;
    font-weight: 700;
    margin: 0;
    color: var(--text-on-dark);
  }
  .pf-subtitle {
    font-size: 0.82rem;
    color: var(--color-southern-sky);
    margin: 0.3rem 0 0;
  }

  .pf-config {
    max-width: 800px;
    margin: 0 auto;
    background: var(--bg-card);
    border: 1px solid var(--border-light);
    border-radius: var(--radius-md);
    padding: 1.25rem 1.5rem;
    box-shadow: var(--shadow-card);
    animation: fadeIn 0.5s ease both;
    animation-delay: 0.1s;
  }

  /* Divider between dimensions and bottom row */
  .pf-divider {
    height: 1px;
    background: var(--border-light);
    margin: 0.25rem 0 1rem;
  }

  /* Geo type tabs */
  .pf-geo-tabs {
    display: flex;
    gap: 0.25rem;
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }
  .pf-tab {
    padding: 0.4rem 1rem;
    font-size: 0.76rem;
    font-weight: 500;
    border: 1px solid var(--border-medium);
    background: var(--bg-card);
    color: var(--text-secondary);
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all 0.15s ease;
    font-family: var(--font-body);
    letter-spacing: 0.02em;
  }
  .pf-tab:hover { border-color: var(--accent-primary); color: var(--accent-primary); }
  .pf-tab.active {
    background: var(--accent-primary);
    color: var(--text-on-dark);
    border-color: var(--accent-primary);
    font-weight: 600;
    box-shadow: 0 2px 8px rgba(14,120,190,0.2);
  }

  /* Search */
  .pf-label {
    display: block;
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.35rem;
  }
  .pf-search-section { margin-bottom: 1rem; }
  .pf-search-wrap { position: relative; }
  .pf-search-input {
    width: 100%;
    padding: 0.5rem 0.75rem;
    font-size: 0.82rem;
    border: 1px solid var(--border-default);
    border-radius: var(--radius-sm);
    font-family: inherit;
    background: var(--bg-primary);
    color: var(--text-primary);
  }
  .pf-search-input:focus { outline: none; border-color: var(--accent-primary); box-shadow: 0 0 0 2px rgba(14,120,190,0.15); }

  .pf-dropdown {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    background: var(--bg-card);
    border: 1px solid var(--border-default);
    border-radius: 0 0 var(--radius-sm) var(--radius-sm);
    box-shadow: var(--shadow-elevated);
    list-style: none;
    margin: 0;
    padding: 0;
    z-index: 100;
    max-height: 280px;
    overflow-y: auto;
    animation: dropdownReveal 0.15s ease both;
  }
  @keyframes dropdownReveal {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .pf-dropdown li { border-bottom: 1px solid var(--border-light); }
  .pf-dropdown li:last-child { border-bottom: none; }
  .pf-dropdown-item {
    width: 100%;
    padding: 0.5rem 0.75rem;
    font-size: 0.8rem;
    text-align: left;
    background: none;
    border: none;
    cursor: pointer;
    color: var(--text-primary);
    font-family: inherit;
    transition: background 0.1s ease;
  }
  .pf-dropdown-item:hover { background: var(--bg-hover); }

  .pf-selected-target { margin-top: 0.4rem; }
  .pf-target-chip {
    display: inline-block;
    padding: 0.25rem 0.65rem;
    font-size: 0.75rem;
    font-weight: 600;
    background: linear-gradient(135deg, var(--bg-hover) 0%, #dceaf8 100%);
    color: var(--accent-primary);
    border-radius: var(--radius-sm);
  }

  /* Dimensions */
  .pf-dims-section { margin-bottom: 1rem; }
  .pf-dims-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.35rem;
  }
  .pf-dims-header .pf-label { margin-bottom: 0; }
  .pf-dims-actions { display: flex; gap: 0.5rem; }
  .pf-link-btn {
    background: none;
    border: none;
    color: var(--accent-primary);
    font-size: 0.72rem;
    font-weight: 600;
    cursor: pointer;
    text-decoration: underline;
    font-family: inherit;
    padding: 0;
  }
  .pf-link-btn:hover { opacity: 0.7; }

  .pf-dims-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 0.3rem 1rem;
  }
  .pf-dim-check {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.78rem;
    color: var(--text-secondary);
    cursor: pointer;
    padding: 0.15rem 0.25rem;
    border-radius: var(--radius-sm);
    transition: background var(--transition-fast);
  }
  .pf-dim-check:hover { background: var(--bg-hover); }
  .pf-dim-check input { margin: 0; accent-color: var(--accent-primary); }

  /* Bottom row */
  .pf-bottom-row {
    display: flex;
    gap: 1rem;
    align-items: flex-end;
    flex-wrap: wrap;
  }
  .pf-profile-wrap { flex: 0 0 auto; }
  .pf-select {
    padding: 0.45rem 0.65rem;
    font-size: 0.8rem;
    border: 1px solid var(--border-default);
    border-radius: var(--radius-sm);
    font-family: inherit;
    background: var(--bg-primary);
    color: var(--text-primary);
  }

  .pf-find-btn {
    flex: 1;
    min-width: 160px;
    padding: 0.6rem 1.5rem;
    font-size: 0.82rem;
    font-weight: 600;
    background: linear-gradient(135deg, var(--accent-primary) 0%, #0a6aaa 100%);
    color: var(--text-on-dark);
    border: none;
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all 0.2s ease;
    font-family: var(--font-body);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .pf-find-btn:hover:not(:disabled) {
    background: linear-gradient(135deg, #0a6aaa 0%, var(--color-riviere) 100%);
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(14,120,190,0.3);
  }
  .pf-find-btn:disabled { opacity: 0.5; cursor: not-allowed; }

  /* Loading & status */
  .pf-loading {
    text-align: center;
    padding: 3rem 1rem;
    color: var(--text-muted);
    animation: fadeIn 0.3s ease both;
  }
  .pf-loading .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid var(--border-light);
    border-top-color: var(--accent-primary);
    border-right-color: var(--color-southern-sky);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 0 auto 1rem;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .pf-error {
    text-align: center;
    padding: 2rem 1rem;
    color: var(--negative, #c62828);
    font-size: 0.85rem;
    animation: fadeIn 0.3s ease both;
  }

  .pf-empty {
    text-align: center;
    padding: 4rem 1rem;
    color: var(--text-muted);
    font-size: 0.85rem;
    animation: fadeIn 0.5s ease both;
    animation-delay: 0.2s;
  }
  .pf-empty-icon {
    margin-bottom: 1.25rem;
    opacity: 0.5;
    animation: float 3s ease-in-out infinite;
  }

  /* Results */
  .pf-results {
    max-width: 1200px;
    margin: 1.25rem auto 0;
    animation: fadeInUp 0.4s ease both;
  }

  .pf-target-card {
    background: var(--bg-card);
    border: 1px solid var(--border-light);
    border-left: 3px solid var(--accent-primary);
    border-top: none;
    border-radius: var(--radius-md);
    padding: 1rem 1.25rem;
    margin-bottom: 1rem;
    box-shadow: var(--shadow-card);
  }
  .pf-target-card h3 {
    font-size: 1rem;
    font-weight: 700;
    margin: 0 0 0.65rem;
    color: var(--text-primary);
  }
  .pf-target-values {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 1.5rem;
  }
  .pf-kv { display: flex; flex-direction: column; gap: 0.1rem; }
  .pf-kv-label { font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; font-weight: 500; }
  .pf-kv-value { font-size: 0.9rem; font-weight: 700; color: var(--text-primary); }

  .pf-warnings {
    background: var(--warning-bg);
    border: 1px solid var(--warning-border);
    border-radius: var(--radius-sm);
    padding: 0.5rem 0.75rem;
    margin-bottom: 0.75rem;
  }
  .pf-warnings p { font-size: 0.78rem; color: var(--warning-text); margin: 0.15rem 0; }

  /* Load bar */
  .pf-load-bar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.6rem 0;
    margin-bottom: 0.5rem;
    flex-wrap: wrap;
    animation: fadeIn 0.3s ease both;
    animation-delay: 0.15s;
  }
  .pf-load-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--text-secondary);
  }
  .pf-load-btn {
    padding: 0.3rem 0.7rem;
    font-size: 0.72rem;
    font-weight: 600;
    border: 1px solid var(--accent-primary);
    background: var(--bg-card);
    color: var(--accent-primary);
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all 0.2s ease;
    font-family: var(--font-body);
  }
  .pf-load-btn:hover:not(:disabled) {
    background: var(--accent-primary);
    color: var(--text-on-dark);
    box-shadow: 0 2px 8px rgba(14,120,190,0.2);
    transform: translateY(-1px);
  }
  .pf-load-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  /* Table */
  .pf-table-wrap {
    overflow-x: auto;
    border: 1px solid var(--border-light);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-card);
    animation: fadeIn 0.4s ease both;
    animation-delay: 0.2s;
  }
  .pf-table-wrap::-webkit-scrollbar {
    height: 6px;
  }
  .pf-table-wrap::-webkit-scrollbar-track {
    background: var(--bg-primary);
    border-radius: 3px;
  }
  .pf-table-wrap::-webkit-scrollbar-thumb {
    background: var(--color-steel);
    border-radius: 3px;
  }
  .pf-table-wrap::-webkit-scrollbar-thumb:hover {
    background: var(--text-muted);
  }
  .pf-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78rem;
    background: var(--bg-card);
  }
  .pf-table th {
    padding: 0.55rem 0.65rem;
    text-align: left;
    font-size: 0.68rem;
    font-weight: 600;
    color: var(--text-on-dark);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-bottom: 2px solid var(--border-medium);
    background: var(--color-riviere);
    white-space: nowrap;
    position: sticky;
    top: 0;
    z-index: 1;
  }
  .pf-table td {
    padding: 0.45rem 0.65rem;
    border-bottom: 1px solid var(--border-light);
    white-space: nowrap;
    transition: background 0.15s ease;
  }
  .pf-table tbody tr:nth-child(even) td { background: var(--bg-muted); }
  .pf-table tbody tr:hover td { background: var(--bg-hover); }

  .pf-th-rank, .pf-td-rank { width: 36px; text-align: center; color: var(--text-muted); }
  .pf-table th.pf-th-rank { color: var(--color-steel); }
  .pf-th-name { min-width: 200px; }
  .pf-td-name { font-weight: 500; color: var(--text-primary); }
  .pf-th-score, .pf-td-score { text-align: center; }
  .pf-th-dim, .pf-td-dim { text-align: right; }

  .pf-score-cell {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    justify-content: center;
  }
  .pf-score-badge {
    font-weight: 700;
    font-size: 0.72rem;
    color: var(--text-on-dark);
    padding: 0.1rem 0.45rem;
    border-radius: 10px;
    line-height: 1.3;
    min-width: 34px;
    text-align: center;
  }
  .pf-score-bar {
    width: 40px;
    height: 5px;
    background: var(--border-light);
    border-radius: 3px;
    overflow: hidden;
  }
  .pf-score-bar-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.4s ease;
  }

  /* Responsive */
  @media (max-width: 640px) {
    .peer-finder { padding: 0 0.5rem 1.5rem; }
    .pf-header { margin: 0 -0.5rem 1.25rem; }
    .pf-config { padding: 1rem; }
    .pf-dims-grid { grid-template-columns: 1fr 1fr; }
    .pf-bottom-row { flex-direction: column; align-items: stretch; }
    .pf-find-btn { min-width: unset; }
    .pf-target-values { gap: 0.4rem 1rem; }
    .pf-score-bar { display: none; }
  }
</style>
