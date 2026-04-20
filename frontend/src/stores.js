import { writable, get } from 'svelte/store';

/**
 * Create a writable store that persists to localStorage.
 */
function persistentWritable(key, defaultValue) {
  let initial = defaultValue;
  try {
    const stored = localStorage.getItem(key);
    if (stored !== null) {
      initial = JSON.parse(stored);
    }
  } catch {}

  const store = writable(initial);

  store.subscribe(value => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {}
  });

  return store;
}

// App-level view: 'landing' | 'data' | 'dashboard' | 'peers'
export const currentView = writable('landing');

// Selections — start fresh each session (blank slate)
export const selectedGeos = writable([]);
export const selectedIndicators = writable([]);
export const selectedYears = writable([2023, 2024]);
export const selectedGeoType = writable('msa');
export const acsDataset = writable('acs1'); // 'acs1' or 'acs5'

// COLI & Inflation adjustments
export const coliAdjust = writable(false);
export const inflationAdjust = writable(false);
export const inflationBaseYear = writable(null);

// Results and derived data
export const results = writable(null);
export const yoyData = writable({});
export const columnsData = writable([]);
export const warningsData = writable([]);

// Display mode
export const displayMode = writable('raw'); // 'raw' | 'yoy' | 'both'
export const viewMode = writable('table');  // 'table' | 'chart' | 'split' | 'compare' | 'map' | 'industry' | 'occupation'

// UI state
export const loading = writable(false);
export const error = writable(null);

// Highlight metro — configurable, persisted (null = no highlight)
export const highlightGeo = persistentWritable('dp_highlightGeo', null);

// Indicator metadata (shared across components)
export const indicatorsMeta = writable([]);

// URL sharing — pending geo IDs to resolve after GeoPicker loads
export const pendingUrlGeoIds = writable(null);
// Signals that URL restore is complete and auto-fetch should fire
export const urlRestoreReady = writable(false);

// Dashboard geo (single geography for dashboard view)
export const dashboardGeo = persistentWritable('dp_dashboardGeo', null);

// Peer finder stores
export const peerGeoType = writable('msa');
export const peerTarget = writable(null);
export const peerDimensions = writable([]);
export const peerWeightProfile = writable('balanced');
export const peerResults = writable(null);

/**
 * Read URL search params and populate stores.
 * Call once on app mount.
 */
export function initFromUrl() {
  const params = new URLSearchParams(window.location.search);
  if (params.toString() === '') return false;

  // View mode
  const v = params.get('v');
  if (v && ['data', 'dashboard', 'peers'].includes(v)) {
    currentView.set(v);
  } else {
    // If URL has data params, go straight to data view
    currentView.set('data');
  }

  const t = params.get('t');
  if (t && ['msa', 'state', 'county', 'micro', 'place'].includes(t)) selectedGeoType.set(t);

  const d = params.get('d');
  if (d && ['acs1', 'acs5'].includes(d)) acsDataset.set(d);

  const y = params.get('y');
  if (y) {
    const years = y.split(',').map(Number).filter(n => !isNaN(n) && n >= 2010 && n <= 2030);
    if (years.length) selectedYears.set(years.sort());
  }

  const i = params.get('i');
  if (i) selectedIndicators.set(i.split(',').filter(Boolean));

  const g = params.get('g');
  if (g) {
    pendingUrlGeoIds.set(g.split(',').filter(Boolean));
  } else {
    // No geos in URL — mark restore ready immediately
    urlRestoreReady.set(true);
  }

  // COLI
  if (params.get('coli') === '1') coliAdjust.set(true);

  // Inflation
  const infl = params.get('infl');
  if (infl) {
    inflationAdjust.set(true);
    inflationBaseYear.set(parseInt(infl, 10));
  }

  // Dashboard geo
  const dg = params.get('dg');
  if (dg) dashboardGeo.set(dg);

  return true; // had URL params
}

/**
 * Encode current selections into a shareable URL.
 */
export function encodeStateToUrl() {
  const params = new URLSearchParams();
  const view = get(currentView);
  const geos = get(selectedGeos);
  const inds = get(selectedIndicators);
  const years = get(selectedYears);
  const geoType = get(selectedGeoType);
  const ds = get(acsDataset);

  if (view !== 'landing') params.set('v', view);

  if (view === 'data') {
    if (geos.length) params.set('g', geos.map(g => g.id).join(','));
    if (inds.length) params.set('i', inds.join(','));
    if (years.length) params.set('y', years.join(','));
    if (geoType !== 'msa') params.set('t', geoType);
    if (ds !== 'acs1') params.set('d', ds);

    if (get(coliAdjust)) params.set('coli', '1');
    const inflBase = get(inflationBaseYear);
    if (get(inflationAdjust) && inflBase) params.set('infl', String(inflBase));
  }

  if (view === 'dashboard') {
    const dg = get(dashboardGeo);
    if (dg) params.set('dg', dg);
  }

  const qs = params.toString();
  return window.location.origin + window.location.pathname + (qs ? '?' + qs : '');
}
