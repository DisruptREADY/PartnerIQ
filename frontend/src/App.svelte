<script>
  import { onMount } from 'svelte';
  import './lib/theme.css';
  import GeoPicker from './lib/GeoPicker.svelte';
  import IndicatorPanel from './lib/IndicatorPanel.svelte';
  import YearPicker from './lib/YearPicker.svelte';
  import DataTable from './lib/DataTable.svelte';
  import ExportBar from './lib/ExportBar.svelte';
  import ChartPanel from './lib/ChartPanel.svelte';
  import ComparisonView from './lib/ComparisonView.svelte';
  import IndustryBreakdown from './lib/IndustryBreakdown.svelte';
  import OccupationBreakdown from './lib/OccupationBreakdown.svelte';
  import DataNotes from './lib/DataNotes.svelte';
  import LoginPage from './lib/LoginPage.svelte';
  import { initAuth, authReady, isAuthenticated, authUser, logout, getToken } from './lib/auth.js';
  import { API_BASE, apiFetch } from './lib/api.js';
  import {
    selectedGeos, selectedIndicators, selectedYears, selectedGeoType,
    acsDataset, coliAdjust, inflationAdjust, inflationBaseYear,
    results, yoyData, columnsData, warningsData,
    displayMode, viewMode, currentView,
    loading, error, highlightGeo,
    initFromUrl, encodeStateToUrl, urlRestoreReady
  } from './stores.js';

  // Lazy-load heavy components
  let LandingPage = null;
  let Dashboard = null;
  let MapView = null;
  let PeerFinder = null;
  import('./lib/LandingPage.svelte').then(m => LandingPage = m.default).catch(e => console.error('Failed to load LandingPage:', e));
  import('./lib/Dashboard.svelte').then(m => Dashboard = m.default).catch(e => console.error('Failed to load Dashboard:', e));
  import('./lib/MapView.svelte').then(m => MapView = m.default).catch(e => console.error('Failed to load MapView:', e));
  import('./lib/PeerFinder.svelte').then(m => PeerFinder = m.default).catch(e => console.error('Failed to load PeerFinder:', e));

  // Initialise Auth0 on mount
  onMount(() => { initAuth(); });

  // Restore selections from URL params (runs before components mount)
  initFromUrl();

  // Auto-fetch when URL restore completes (GeoPicker resolved pending geos)
  let autoFetched = false;
  $: if ($urlRestoreReady && !autoFetched && $isAuthenticated) {
    autoFetched = true;
    fetchData();
  }

  $: canFetch = $selectedGeos.length > 0 && $selectedIndicators.length > 0 && $selectedYears.length > 0;

  // Derived user display
  $: userName = $authUser?.name || $authUser?.email || 'User';
  $: userInitials = userName.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
  $: userPicture = $authUser?.picture || null;

  let jobMessage = '';
  let mobileMenuOpen = false;
  let fetchController = null;
  let showUserMenu = false;

  async function fetchData() {
    if (!canFetch) return;

    // Abort any in-flight request to prevent stale data
    if (fetchController) fetchController.abort();
    fetchController = new AbortController();
    const { signal } = fetchController;

    loading.set(true);
    error.set(null);
    results.set(null);
    yoyData.set({});
    warningsData.set([]);
    jobMessage = 'Sending request...';

    try {
      const token = await getToken();
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const body = {
        geo_ids: $selectedGeos.map(g => g.id || g.cbsa),
        indicators: $selectedIndicators,
        years: $selectedYears,
        geo_type: $selectedGeoType,
        acs_dataset: $acsDataset,
      };
      if ($coliAdjust) body.coli_adjust = true;
      if ($inflationAdjust && $inflationBaseYear) {
        body.inflation_adjust = true;
        body.inflation_base_year = $inflationBaseYear;
      }

      const resp = await fetch(`${API_BASE}/api/data`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
        signal,
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${resp.status}`);
      }

      const data = await resp.json();
      results.set({ columns: data.columns, rows: data.rows });
      columnsData.set(data.columns || []);
      yoyData.set(data.yoy || {});
      warningsData.set(data.warnings || []);
    } catch (e) {
      if (e.name === 'AbortError') {
        // Superseded by a newer request — don't touch loading state;
        // the new request's finally block will handle it.
        return;
      }
      error.set(e.message);
    } finally {
      // Only clear loading if this controller wasn't aborted (i.e., it's still current)
      if (fetchController && !fetchController.signal.aborted) {
        loading.set(false);
        jobMessage = '';
      }
    }
  }

  let showMethodology = false;
  let shareCopied = false;

  function shareUrl() {
    const url = encodeStateToUrl();
    navigator.clipboard.writeText(url).then(() => {
      window.history.replaceState(null, '', url);
      shareCopied = true;
      setTimeout(() => { shareCopied = false; }, 2500);
    });
  }

  function toggleMobileMenu() {
    mobileMenuOpen = !mobileMenuOpen;
  }

  function closeMobileMenu() {
    mobileMenuOpen = false;
  }

  function navigateTo(view) {
    currentView.set(view);
    showMethodology = false;
  }

  function resetAll() {
    // Abort any in-flight request
    if (fetchController) fetchController.abort();
    // Clear all selections
    selectedGeos.set([]);
    selectedIndicators.set([]);
    selectedYears.set([2023, 2024]);
    selectedGeoType.set('msa');
    acsDataset.set('acs1');
    coliAdjust.set(false);
    inflationAdjust.set(false);
    inflationBaseYear.set(null);
    // Clear results
    results.set(null);
    yoyData.set({});
    columnsData.set([]);
    warningsData.set([]);
    error.set(null);
    loading.set(false);
    // Reset display
    displayMode.set('raw');
    viewMode.set('table');
    showMethodology = false;
    jobMessage = '';
    // Clear URL params
    window.history.replaceState(null, '', window.location.pathname);
    // Navigate to data view
    currentView.set('data');
  }

  // CPI table for inflation base year dropdown
  let cpiYears = [];
  apiFetch('/api/cpi').then(r => r.ok ? r.json() : {}).then(data => {
    if (data && data.years) cpiYears = data.years;
  }).catch(() => {});
</script>

<!-- Auth loading splash -->
{#if !$authReady}
  <div class="auth-splash">
    <div class="auth-splash-inner">
      <div class="logo-mark splash-mark">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path d="M4 10h5M11 5v10M15 7.5a2.5 2.5 0 010 5" stroke="white" stroke-width="2" stroke-linecap="round"/>
        </svg>
      </div>
      <div class="spinner splash-spin"></div>
    </div>
  </div>
{:else if !$isAuthenticated}
  <LoginPage />
{:else}

<div class="app">
  <a class="skip-link" href="#main-content">Skip to main content</a>

  <!-- Topbar -->
  <header class="topbar">
    <div class="topbar-left">
      <button class="hamburger" on:click={toggleMobileMenu} aria-label="Toggle menu">
        <span class="hamburger-line" class:open={mobileMenuOpen}></span>
        <span class="hamburger-line" class:open={mobileMenuOpen}></span>
        <span class="hamburger-line" class:open={mobileMenuOpen}></span>
      </button>
      <!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
      <div class="logo" on:click={() => navigateTo('landing')}>
        <div class="logo-mark">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M3 8h4M9 4v8M12 6a2 2 0 010 4" stroke="white" stroke-width="1.8" stroke-linecap="round"/>
          </svg>
        </div>
        <span>Partner<span class="logo-text-iq">IQ</span></span>
      </div>
      <nav class="nav-links">
        <button class="nav-link" class:active={$currentView === 'landing'} on:click={() => navigateTo('landing')}>Home</button>
        <button class="nav-link" class:active={$currentView === 'dashboard'} on:click={() => navigateTo('dashboard')}>Dashboard</button>
        <button class="nav-link" class:active={$currentView === 'data'} on:click={() => navigateTo('data')}>Explorer</button>
        <button class="nav-link" class:active={$currentView === 'peers'} on:click={() => navigateTo('peers')}>Peer Finder</button>
        <button class="nav-link" class:active={showMethodology} on:click={() => { if ($currentView !== 'data') { currentView.set('data'); showMethodology = true; } else { showMethodology = !showMethodology; } }}>Methodology</button>
      </nav>
    </div>
    <div class="topbar-right">
      <div class="chamber-badge">Chamber Portal</div>
      <!-- User avatar + dropdown -->
      <!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
      <div class="avatar-wrap" on:click={() => showUserMenu = !showUserMenu}>
        {#if userPicture}
          <img class="avatar avatar-img" src={userPicture} alt={userName} />
        {:else}
          <div class="avatar">{userInitials}</div>
        {/if}
        {#if showUserMenu}
          <!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
          <div class="user-menu" on:click|stopPropagation>
            <div class="user-menu-name">{userName}</div>
            <div class="user-menu-email">{$authUser?.email || ''}</div>
            <hr class="user-menu-divider" />
            <button class="user-menu-btn" on:click={logout}>Sign Out</button>
          </div>
        {/if}
      </div>
    </div>
  </header>

  <!-- Mobile overlay backdrop (all views) -->
  {#if mobileMenuOpen}
    <!-- svelte-ignore a11y_no_static_element_interactions a11y_click_events_have_key_events -->
    <div class="sidebar-backdrop" role="presentation" on:click={closeMobileMenu}></div>
  {/if}

  <!-- Mobile nav drawer for landing/dashboard/peers (data pull uses its sidebar instead) -->
  {#if mobileMenuOpen && $currentView !== 'data'}
    <aside class="mobile-nav-drawer" aria-label="Navigation">
      <button class="mobile-nav-item" class:active={$currentView === 'landing'} on:click={() => { navigateTo('landing'); closeMobileMenu(); }}>Home</button>
      <button class="mobile-nav-item" class:active={$currentView === 'data'} on:click={() => { navigateTo('data'); closeMobileMenu(); }}>Data Pull</button>
      <button class="mobile-nav-item" class:active={$currentView === 'dashboard'} on:click={() => { navigateTo('dashboard'); closeMobileMenu(); }}>Dashboard</button>
      <button class="mobile-nav-item" class:active={$currentView === 'peers'} on:click={() => { navigateTo('peers'); closeMobileMenu(); }}>Peer Finder</button>
    </aside>
  {/if}

  <!-- Main Content -->
  {#if $currentView === 'landing'}
    {#if LandingPage}
      <svelte:component this={LandingPage} on:navigate={(e) => navigateTo(e.detail)} />
    {:else}
      <div class="view-loading"><div class="spinner"></div></div>
    {/if}
  {:else if $currentView === 'dashboard'}
    {#if Dashboard}
      <svelte:component this={Dashboard} />
    {:else}
      <div class="view-loading"><div class="spinner"></div></div>
    {/if}
  {:else if $currentView === 'peers'}
    {#if PeerFinder}
      <svelte:component this={PeerFinder} />
    {:else}
      <div class="view-loading"><div class="spinner"></div></div>
    {/if}
  {:else}
    <!-- Data Pull View -->
    <div class="layout">
      <aside class="sidebar" class:mobile-open={mobileMenuOpen}>
        <!-- Mobile navigation links (visible only on mobile, at top of sidebar) -->
        <nav class="sidebar-mobile-nav" aria-label="Navigation">
          <button class="mobile-nav-item" class:active={$currentView === 'landing'} on:click={() => { navigateTo('landing'); closeMobileMenu(); }}>Home</button>
          <button class="mobile-nav-item" class:active={$currentView === 'data'} on:click={() => { navigateTo('data'); closeMobileMenu(); }}>Data Pull</button>
          <button class="mobile-nav-item" class:active={$currentView === 'dashboard'} on:click={() => { navigateTo('dashboard'); closeMobileMenu(); }}>Dashboard</button>
          <button class="mobile-nav-item" class:active={$currentView === 'peers'} on:click={() => { navigateTo('peers'); closeMobileMenu(); }}>Peer Finder</button>
          <div class="sidebar-mobile-divider"></div>
        </nav>

        <GeoPicker />
        <IndicatorPanel />
        <YearPicker />

        <!-- COLI Toggle (MSA only) -->
        {#if $selectedGeoType === 'msa'}
          <div class="adjust-section">
            <label class="adjust-toggle">
              <input type="checkbox" bind:checked={$coliAdjust} />
              <span>COLI Adjust</span>
            </label>
          </div>
        {/if}

        <!-- Inflation Adjuster -->
        <div class="adjust-section">
          <label class="adjust-toggle">
            <input type="checkbox" bind:checked={$inflationAdjust} />
            <span>Inflation Adjust</span>
          </label>
          {#if $inflationAdjust}
            <select class="base-year-select" bind:value={$inflationBaseYear}>
              <option value={null}>Base year...</option>
              {#each cpiYears as yr}
                <option value={yr}>{yr}</option>
              {/each}
              {#if cpiYears.length === 0}
                <option value={2024}>2024</option>
                <option value={2023}>2023</option>
              {/if}
            </select>
          {/if}
        </div>

        <button class="fetch-btn" on:click={() => { fetchData(); closeMobileMenu(); }} disabled={!canFetch || $loading}>
          {#if $loading}
            Fetching...
          {:else}
            Fetch Data
          {/if}
        </button>

        <button class="reset-btn" on:click={resetAll}>Reset All</button>
      </aside>

      <main class="content" id="main-content">
        {#if showMethodology}
          <DataNotes alwaysShow={true} />
        {:else if $viewMode === 'industry'}
          <div class="toolbar">
            <div class="view-toggles" role="tablist">
              <button class="toggle-btn" on:click={() => viewMode.set('table')} role="tab" aria-selected={false}>Table</button>
              <button class="toggle-btn" on:click={() => viewMode.set('chart')} role="tab" aria-selected={false}>Chart</button>
              <button class="toggle-btn" on:click={() => viewMode.set('split')} role="tab" aria-selected={false}>Split</button>
              <button class="toggle-btn" on:click={() => viewMode.set('compare')} role="tab" aria-selected={false}>Compare</button>
              <span class="tab-divider"></span>
              <button class="toggle-btn active" role="tab" aria-selected={true} disabled={$selectedGeoType !== 'msa'} title={$selectedGeoType !== 'msa' ? 'Available for metros only' : ''}>Industry</button>
              <button class="toggle-btn" on:click={() => viewMode.set('occupation')} role="tab" aria-selected={false} disabled={$selectedGeoType !== 'msa'} title={$selectedGeoType !== 'msa' ? 'Available for metros only' : ''}>Occupation</button>
            </div>
          </div>
          <div role="tabpanel" aria-label="Industry breakdown view">
            <IndustryBreakdown />
          </div>
        {:else if $viewMode === 'occupation'}
          <div class="toolbar">
            <div class="view-toggles" role="tablist">
              <button class="toggle-btn" on:click={() => viewMode.set('table')} role="tab" aria-selected={false}>Table</button>
              <button class="toggle-btn" on:click={() => viewMode.set('chart')} role="tab" aria-selected={false}>Chart</button>
              <button class="toggle-btn" on:click={() => viewMode.set('split')} role="tab" aria-selected={false}>Split</button>
              <button class="toggle-btn" on:click={() => viewMode.set('compare')} role="tab" aria-selected={false}>Compare</button>
              <span class="tab-divider"></span>
              <button class="toggle-btn" on:click={() => viewMode.set('industry')} role="tab" aria-selected={false} disabled={$selectedGeoType !== 'msa'} title={$selectedGeoType !== 'msa' ? 'Available for metros only' : ''}>Industry</button>
              <button class="toggle-btn active" role="tab" aria-selected={true} disabled={$selectedGeoType !== 'msa'} title={$selectedGeoType !== 'msa' ? 'Available for metros only' : ''}>Occupation</button>
            </div>
          </div>
          <div role="tabpanel" aria-label="Occupation breakdown view">
            <OccupationBreakdown />
          </div>
        {:else if $loading}
          <div class="status">
            <div class="progress-container">
              <div class="spinner"></div>
              <p>{jobMessage || 'Fetching data from APIs... this may take a moment.'}</p>
            </div>
          </div>
        {:else if $error}
          <div class="status error-box">
            <p>Error: {$error}</p>
            <button class="retry-btn" on:click={fetchData}>Retry</button>
          </div>
        {:else if $results}
          {#if $warningsData.length > 0}
            <div class="warnings">
              {#each $warningsData as w}
                <p class="warning-item">{w}</p>
              {/each}
            </div>
          {/if}

          <div class="toolbar">
            <div class="view-toggles" role="tablist">
              <button class="toggle-btn" class:active={$viewMode === 'table'} on:click={() => viewMode.set('table')} role="tab" aria-selected={$viewMode === 'table'}>Table</button>
              <button class="toggle-btn" class:active={$viewMode === 'chart'} on:click={() => viewMode.set('chart')} role="tab" aria-selected={$viewMode === 'chart'}>Chart</button>
              <button class="toggle-btn" class:active={$viewMode === 'split'} on:click={() => viewMode.set('split')} role="tab" aria-selected={$viewMode === 'split'}>Split</button>
              <button class="toggle-btn" class:active={$viewMode === 'compare'} on:click={() => viewMode.set('compare')} role="tab" aria-selected={$viewMode === 'compare'}>Compare</button>
              {#if MapView}
                <button class="toggle-btn" class:active={$viewMode === 'map'} on:click={() => viewMode.set('map')} role="tab" aria-selected={$viewMode === 'map'}>Map</button>
              {/if}
              <span class="tab-divider"></span>
              <button class="toggle-btn" on:click={() => viewMode.set('industry')} role="tab" aria-selected={false} disabled={$selectedGeoType !== 'msa'} title={$selectedGeoType !== 'msa' ? 'Available for metros only' : ''}>Industry</button>
              <button class="toggle-btn" on:click={() => viewMode.set('occupation')} role="tab" aria-selected={false} disabled={$selectedGeoType !== 'msa'} title={$selectedGeoType !== 'msa' ? 'Available for metros only' : ''}>Occupation</button>
            </div>
            <div class="toolbar-right">
              {#if $viewMode === 'table' || $viewMode === 'split'}
                <div class="display-toggles">
                  <button class="toggle-btn small" class:active={$displayMode === 'raw'} on:click={() => displayMode.set('raw')}>Values</button>
                  <button class="toggle-btn small" class:active={$displayMode === 'yoy'} on:click={() => displayMode.set('yoy')}>YoY</button>
                  <button class="toggle-btn small" class:active={$displayMode === 'both'} on:click={() => displayMode.set('both')}>Both</button>
                </div>
              {/if}
              <button class="share-btn" on:click={shareUrl}>
                {shareCopied ? 'Link Copied!' : 'Share'}
              </button>
            </div>
          </div>

          {#if $viewMode === 'table'}
            <div role="tabpanel" aria-label="Table view">
              <ExportBar />
              <DataTable />
            </div>
          {:else if $viewMode === 'chart'}
            <div role="tabpanel" aria-label="Chart view">
              <ChartPanel />
            </div>
          {:else if $viewMode === 'split'}
            <div role="tabpanel" aria-label="Split view">
              <div class="split-view">
                <div class="split-top">
                  <ExportBar />
                  <DataTable />
                </div>
                <div class="split-bottom">
                  <ChartPanel />
                </div>
              </div>
            </div>
          {:else if $viewMode === 'compare'}
            <div role="tabpanel" aria-label="Compare view">
              <ComparisonView />
            </div>
          {:else if $viewMode === 'map' && MapView}
            <div role="tabpanel" aria-label="Map view">
              <svelte:component this={MapView} />
            </div>
          {/if}

        {:else}
          <div class="toolbar">
            <div class="view-toggles" role="tablist">
              <button class="toggle-btn" disabled>Table</button>
              <button class="toggle-btn" disabled>Chart</button>
              <button class="toggle-btn" disabled>Split</button>
              <button class="toggle-btn" disabled>Compare</button>
              <span class="tab-divider"></span>
              <button class="toggle-btn" on:click={() => viewMode.set('industry')} disabled={$selectedGeoType !== 'msa'} title={$selectedGeoType !== 'msa' ? 'Available for metros only' : ''}>Industry</button>
              <button class="toggle-btn" on:click={() => viewMode.set('occupation')} disabled={$selectedGeoType !== 'msa'} title={$selectedGeoType !== 'msa' ? 'Available for metros only' : ''}>Occupation</button>
            </div>
          </div>
          <div class="status empty">
            <div class="empty-icon">
              <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="6" y="10" width="36" height="28" rx="3" stroke="var(--border-medium)" stroke-width="2" fill="none"/>
                <line x1="6" y1="18" x2="42" y2="18" stroke="var(--border-medium)" stroke-width="2"/>
                <rect x="12" y="23" width="8" height="10" rx="1" fill="var(--accent-primary)" opacity="0.2"/>
                <rect x="24" y="26" width="8" height="7" rx="1" fill="var(--accent-primary)" opacity="0.35"/>
                <circle cx="40" cy="8" r="6" fill="var(--accent-primary)" opacity="0.12"/>
                <path d="M38 8L40 10L43 6" stroke="var(--accent-primary)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
            <p>Select geographies, indicators, and years, then click <strong>Fetch Data</strong>.</p>
            <p class="hint">Or click <strong>Industry</strong> / <strong>Occupation</strong> above for breakdown views (requires geographies selected).</p>
            <p class="hint">Tip: Right-click or double-click a geography chip to highlight it in the table.</p>
          </div>
        {/if}
      </main>
    </div>
  {/if}
</div>

{/if}

<style>
  :global(body) {
    margin: 0;
    font-family: var(--font-body, var(--font-stack, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif));
    background: var(--bg-primary);
    color: var(--text-primary);
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    line-height: 1.5;
  }

  :global(*, *::before, *::after) { box-sizing: border-box; }

  :global(h1, h2, h3) {
    font-family: var(--font-primary);
    color: var(--text-primary);
  }

  :global(:focus-visible) {
    outline: 2px solid var(--accent-primary);
    outline-offset: 2px;
  }

  /* ── Auth loading splash ── */
  .auth-splash {
    min-height: 100vh;
    background: var(--color-riviere);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .auth-splash-inner {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20px;
  }
  .splash-mark {
    width: 48px;
    height: 48px;
    border-radius: 12px;
    background: linear-gradient(135deg, var(--color-horizon), var(--color-southern-sky));
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .splash-spin {
    width: 28px;
    height: 28px;
    border: 2px solid rgba(255,255,255,0.2);
    border-top-color: var(--color-southern-sky);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }

  /* ── User menu ── */
  .avatar-wrap {
    position: relative;
    cursor: pointer;
  }
  .avatar-img {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    object-fit: cover;
    border: 2px solid rgba(255,255,255,0.25);
  }
  .user-menu {
    position: absolute;
    top: calc(100% + 10px);
    right: 0;
    background: white;
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-elevated);
    min-width: 200px;
    padding: 12px 0 8px;
    z-index: 200;
    animation: scaleIn 0.15s ease;
  }
  .user-menu-name {
    padding: 0 16px;
    font-size: 13.5px;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .user-menu-email {
    padding: 2px 16px 0;
    font-size: 12px;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .user-menu-divider {
    border: none;
    border-top: 1px solid var(--border-light);
    margin: 10px 0 6px;
  }
  .user-menu-btn {
    width: 100%;
    padding: 8px 16px;
    text-align: left;
    background: none;
    border: none;
    font-size: 13px;
    font-family: var(--font-body);
    color: var(--color-rouge);
    cursor: pointer;
    transition: background 0.15s;
  }
  .user-menu-btn:hover { background: #fff4f4; }

  .app { max-width: 1440px; margin: 0 auto; padding: 0; }

  .skip-link {
    position: absolute;
    left: -9999px;
    top: auto;
    width: 1px;
    height: 1px;
    overflow: hidden;
    z-index: 1000;
    padding: 0.5rem 1rem;
    background: var(--bg-header);
    color: var(--text-on-dark);
    text-decoration: none;
    font-size: 0.85rem;
    border-radius: 0 0 var(--radius-sm) var(--radius-sm);
  }
  .skip-link:focus {
    position: fixed;
    left: 1rem;
    top: 0;
    width: auto;
    height: auto;
  }

  /* Topbar */
  .topbar {
    background: var(--color-riviere);
    color: white;
    padding: 0 32px;
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 100;
    margin-bottom: 0;
  }

  .topbar::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--color-horizon), var(--color-southern-sky), var(--color-geaux));
  }

  .topbar-left {
    display: flex;
    align-items: center;
    gap: 28px;
  }

  .logo {
    font-family: var(--font-primary);
    font-size: 18px;
    font-weight: bold;
    letter-spacing: 0.2px;
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    color: white;
    user-select: none;
  }

  .logo-mark {
    width: 30px;
    height: 30px;
    background: linear-gradient(135deg, var(--color-horizon), var(--color-southern-sky));
    border-radius: 7px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .logo-text-iq { color: var(--color-southern-sky); }

  .nav-links {
    display: flex;
    gap: 2px;
  }

  .nav-link {
    padding: 7px 14px;
    border-radius: var(--radius-sm);
    font-size: 13.5px;
    font-weight: 500;
    color: rgba(255,255,255,0.55);
    cursor: pointer;
    transition: all 0.2s;
    background: none;
    border: none;
    font-family: var(--font-body);
  }
  .nav-link:hover { color: rgba(255,255,255,0.85); background: rgba(255,255,255,0.06); }
  .nav-link.active {
    color: white;
    background: rgba(255,255,255,0.1);
    box-shadow: 0 0 8px rgba(93,167,220,0.15);
  }

  .topbar-right {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .chamber-badge {
    font-size: 12.5px;
    font-family: var(--font-body);
    color: rgba(255,255,255,0.5);
    padding: 4px 14px;
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 100px;
  }

  .avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--color-horizon), var(--color-southern-sky));
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12.5px;
    font-weight: bold;
    color: white;
    cursor: pointer;
    font-family: var(--font-primary);
    flex-shrink: 0;
  }

  /* Hamburger (mobile only) */
  .hamburger {
    display: none;
    flex-direction: column;
    gap: 5px;
    background: none;
    border: none;
    cursor: pointer;
    padding: 6px;
  }
  .hamburger-line {
    display: block;
    width: 22px;
    height: 2px;
    background: var(--text-on-dark);
    border-radius: 2px;
    transition: transform 0.25s ease, opacity 0.2s ease;
  }
  .hamburger-line.open:nth-child(1) { transform: rotate(45deg) translate(5px, 5px); }
  .hamburger-line.open:nth-child(2) { opacity: 0; }
  .hamburger-line.open:nth-child(3) { transform: rotate(-45deg) translate(5px, -5px); }

  /* Layout */
  .layout {
    display: flex;
    gap: 1.25rem;
    align-items: flex-start;
    padding: 1.25rem 1.25rem 1.5rem;
  }

  .sidebar-backdrop {
    display: none;
  }

  .sidebar {
    width: 340px;
    min-width: 340px;
    background: var(--bg-card);
    padding: 1.1rem 1.25rem;
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-card);
    position: sticky;
    top: calc(56px + 1rem);
    max-height: calc(100vh - 56px - 2rem);
    overflow-y: auto;
    border: 1px solid var(--border-light);
    animation: fadeIn 0.3s ease;
  }

  /* Custom scrollbar for sidebar */
  .sidebar::-webkit-scrollbar { width: 5px; }
  .sidebar::-webkit-scrollbar-track { background: transparent; }
  .sidebar::-webkit-scrollbar-thumb { background: var(--border-medium); border-radius: 4px; }
  .sidebar::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

  .content {
    flex: 1;
    min-width: 0;
    background: var(--bg-card);
    padding: 1.25rem;
    border-radius: var(--radius-md);
    box-shadow: var(--shadow-card);
    border: 1px solid var(--border-light);
    animation: fadeIn 0.3s ease;
  }

  .fetch-btn {
    width: 100%;
    padding: 0.7rem;
    margin-top: 0.85rem;
    background: linear-gradient(135deg, var(--accent-primary) 0%, #0a6aaa 100%);
    color: var(--text-on-dark);
    border: none;
    border-radius: var(--radius-sm);
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    transition: all var(--transition-fast);
    font-family: var(--font-body);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .fetch-btn:hover:not(:disabled) { background: linear-gradient(135deg, #0a6aaa 0%, var(--color-riviere) 100%); transform: translateY(-2px); box-shadow: 0 6px 20px rgba(14,120,190,0.3); }
  .fetch-btn:active:not(:disabled) { transform: translateY(0); }
  .fetch-btn:disabled { opacity: 0.5; cursor: not-allowed; }

  .reset-btn {
    width: 100%;
    padding: 0.5rem;
    margin-top: 0.5rem;
    background: transparent;
    color: var(--text-muted);
    border: 1px solid var(--border-medium);
    border-radius: var(--radius-sm);
    font-size: 0.75rem;
    font-weight: 500;
    cursor: pointer;
    transition: all var(--transition-fast);
    font-family: var(--font-body);
    letter-spacing: 0.03em;
  }
  .reset-btn:hover { color: var(--negative); border-color: var(--negative); background: rgba(200,50,50,0.05); }

  /* Adjustment controls */
  .adjust-section {
    margin-top: 0.6rem;
    padding: 0.5rem 0;
    border-top: 1px solid var(--border-light);
  }
  .adjust-toggle {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    font-size: 0.78rem;
    color: var(--text-secondary);
    cursor: pointer;
  }
  .adjust-toggle input { margin: 0; accent-color: var(--accent-primary); }
  .base-year-select {
    margin-top: 0.35rem;
    width: 100%;
    padding: 0.3rem 0.45rem;
    font-size: 0.75rem;
    border: 1px solid var(--border-default);
    border-radius: var(--radius-sm);
    font-family: inherit;
  }

  /* Status */
  .status { text-align: center; padding: 3.5rem 1.5rem; color: var(--text-muted); }
  .status p { font-size: 0.9rem; line-height: 1.6; }
  .error-box { color: var(--negative); }
  .empty { color: var(--text-muted); animation: fadeIn 0.4s ease; }
  .empty-icon { margin-bottom: 0.75rem; opacity: 0.7; }
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

  .progress-container { text-align: center; animation: fadeIn 0.3s ease; }
  .spinner {
    width: 36px;
    height: 36px;
    border: 3px solid var(--border-light);
    border-top-color: var(--accent-primary);
    border-right-color: var(--color-southern-sky);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    margin: 0 auto 1rem;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .warnings {
    background: var(--warning-bg);
    border: 1px solid var(--warning-border);
    border-radius: var(--radius-sm);
    padding: 0.6rem 0.85rem;
    margin-bottom: 0.85rem;
  }
  .warning-item { font-size: 0.78rem; color: var(--warning-text); margin: 0.2rem 0; }

  /* Toolbar */
  .toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.6rem 0;
    margin-bottom: 0.6rem;
    border-bottom: 1px solid var(--border-light);
    flex-wrap: wrap;
    gap: 0.5rem;
  }
  .toolbar-right {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .view-toggles, .display-toggles {
    display: flex;
    gap: 0.2rem;
    flex-wrap: wrap;
  }

  .share-btn {
    padding: 0.38rem 0.85rem;
    font-size: 0.72rem;
    font-weight: 600;
    border: 1px solid var(--accent-primary);
    background: var(--bg-card);
    color: var(--accent-primary);
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all var(--transition-fast);
    font-family: var(--font-body);
    letter-spacing: 0.03em;
    text-transform: uppercase;
  }
  .share-btn:hover { background: var(--accent-primary); color: var(--text-on-dark); transform: translateY(-1px); }
  .share-btn:active { transform: translateY(0); }

  .toggle-btn {
    padding: 0.4rem 0.85rem;
    font-size: 0.74rem;
    font-weight: 500;
    border: 1px solid var(--border-medium);
    background: var(--bg-card);
    color: var(--text-secondary);
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all var(--transition-fast);
    font-family: var(--font-body);
    letter-spacing: 0.02em;
  }
  .toggle-btn.small { font-size: 0.7rem; padding: 0.3rem 0.6rem; }
  .toggle-btn:hover:not(:disabled) { border-color: var(--accent-primary); color: var(--accent-primary); background: var(--bg-hover); }
  .toggle-btn.active { background: var(--accent-primary); color: var(--text-on-dark); border-color: var(--accent-primary); font-weight: 600; }
  .toggle-btn:disabled { opacity: 0.35; cursor: not-allowed; }

  .tab-divider {
    width: 1px;
    height: 1.2rem;
    background: var(--border-medium);
    margin: 0 0.3rem;
    align-self: center;
  }

  .hint { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.5rem; }

  .view-loading { display: flex; justify-content: center; align-items: center; min-height: 300px; }
  .split-view { display: flex; flex-direction: column; gap: 1rem; }
  .split-top { max-height: 50vh; overflow-y: auto; }

  /* Mobile navigation elements (hidden on desktop) */
  .sidebar-mobile-nav, .mobile-nav-drawer { display: none; }

  /* Mobile responsive */
  @media (max-width: 640px) {
    .hamburger { display: flex; }
    .header-nav { display: none; }

    .sidebar-mobile-nav {
      display: flex;
      flex-direction: column;
      gap: 0.2rem;
      margin-bottom: 0.75rem;
    }
    .sidebar-mobile-divider {
      height: 1px;
      background: var(--border-light);
      margin: 0.5rem 0 0.25rem;
    }
    .mobile-nav-drawer {
      display: flex;
      flex-direction: column;
      position: fixed;
      left: 0;
      top: 0;
      height: 100vh;
      width: 300px;
      z-index: 200;
      background: var(--bg-card);
      padding: 1.5rem 1.25rem;
      box-shadow: var(--shadow-elevated);
      gap: 0.25rem;
    }
    .mobile-nav-item {
      padding: 0.65rem 1rem;
      font-size: 0.85rem;
      font-weight: 500;
      border: none;
      background: transparent;
      color: var(--text-primary);
      text-align: left;
      cursor: pointer;
      border-radius: var(--radius-sm);
      font-family: var(--font-body);
      transition: background var(--transition-fast);
    }
    .mobile-nav-item:hover { background: var(--bg-hover); }
    .mobile-nav-item.active {
      background: var(--accent-primary);
      color: var(--text-on-dark);
      font-weight: 600;
    }
    .topbar { padding: 0 16px; }

    .layout {
      flex-direction: column;
      padding: 0 0.5rem 0.75rem;
    }

    .sidebar {
      position: fixed;
      left: 0;
      top: 0;
      height: 100vh;
      width: 300px;
      min-width: unset;
      z-index: 200;
      border-radius: 0;
      box-shadow: 6px 0 30px rgba(21,18,62,0.2);
      max-height: 100vh;
      border: none;
      transform: translateX(-100%);
      transition: transform 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
      animation: none;
    }
    .sidebar.mobile-open { transform: translateX(0); }

    .sidebar-backdrop {
      display: block;
      position: fixed;
      inset: 0;
      background: rgba(21,18,62,0.5);
      z-index: 150;
      backdrop-filter: blur(3px);
      animation: fadeIn 0.2s ease;
    }

    .content {
      border-radius: var(--radius-sm);
      padding: 0.85rem;
      border: none;
    }

    .view-toggles { gap: 0.15rem; }
    .toggle-btn { padding: 0.3rem 0.5rem; font-size: 0.7rem; }
  }

  /* Tablet */
  @media (min-width: 641px) and (max-width: 1024px) {
    .sidebar { width: 300px; min-width: 300px; }
  }

  /* Desktop */
  @media (min-width: 1025px) {
    .topbar { border-radius: 0; }
  }
</style>
