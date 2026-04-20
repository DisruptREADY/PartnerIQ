<script>
  import { onMount, onDestroy } from 'svelte';
  import { get } from 'svelte/store';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import {
    selectedGeos, selectedGeoType, selectedIndicators,
    results, columnsData
  } from '../stores.js';

  /** @type {typeof import('maplibre-gl').default} */
  let maplibregl;

  const BASEMAP = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';

  // Sequential blue scale — 5 stops (brand-aligned)
  const COLOR_SCALE = ['#e8f0fe', '#a8ccec', '#5DA7DC', '#0E78BE', '#15123E'];

  // GeoJSON endpoints by geo type
  const GEOJSON_URLS = {
    state: '/geo/states.geojson',
    msa: '/geo/cbsas.geojson',
    micro: '/geo/cbsas.geojson',
    county: '/geo/counties.geojson',
    place: '/geo/counties.geojson',  // fallback
  };

  // ID property name expected in GeoJSON features
  const GEO_ID_PROP = {
    state: 'GEOID',
    msa: 'GEOID',
    micro: 'GEOID',
    county: 'GEOID',
    place: 'GEOID',
  };

  const NAME_PROP = {
    state: 'NAME',
    msa: 'NAME',
    micro: 'NAME',
    county: 'NAME',
    place: 'NAME',
  };

  let mapContainer;
  let map = null;
  let tooltip = null;
  let geojsonData = null;
  let loadError = '';
  let legendMin = '';
  let legendMedian = '';
  let legendMax = '';
  let currentSourceId = 'choropleth-source';
  let currentLayerId = 'choropleth-fill';
  let outlineLayerId = 'choropleth-outline';
  let highlightLayerId = 'choropleth-highlight';

  // User-selected indicator for the map (defaults to first selected)
  let mapIndicatorKey = null;

  // Available indicators to display on map (only those in pulled data)
  $: mapIndicatorOptions = ($columnsData || []).filter(c =>
    $selectedIndicators.includes(c.key)
  );

  // Auto-select first indicator if nothing selected yet or current selection is removed
  $: {
    if (mapIndicatorOptions.length > 0) {
      if (!mapIndicatorKey || !mapIndicatorOptions.find(o => o.key === mapIndicatorKey)) {
        mapIndicatorKey = mapIndicatorOptions[0].key;
      }
    }
  }

  // Reactive: extract the indicator key from user selection
  $: indicatorKey = mapIndicatorKey;

  $: indicatorMeta = (() => {
    if (!indicatorKey || !$columnsData) return null;
    return $columnsData.find(c => c.key === indicatorKey) || null;
  })();

  $: latestYear = (() => {
    if (!$results || !$results.rows || $results.rows.length === 0) return null;
    const years = $results.rows.map(r => r.Year).filter(y => y != null);
    return years.length > 0 ? Math.max(...years) : null;
  })();

  // Build a lookup: geo_id -> value for the first indicator at the latest year
  $: valueMap = (() => {
    const m = {};
    if (!$results || !$results.rows || !indicatorKey || latestYear == null) return m;
    for (const row of $results.rows) {
      if (row.Year !== latestYear) continue;
      const id = row.CBSA;
      const val = row[indicatorKey];
      if (id != null && val != null) {
        m[String(id)] = val;
      }
    }
    return m;
  })();

  // Selected geo IDs as a Set for quick lookups
  $: selectedIdSet = new Set(($selectedGeos || []).map(g => g.id));

  // When geoType or valueMap changes, update the map layers
  $: if (map && map.isStyleLoaded()) {
    void $selectedGeoType;
    void valueMap;
    void selectedIdSet;
    updateChoropleth();
  }

  function formatValue(val, meta) {
    if (val == null) return 'N/A';
    const fmt = meta?.fmt || '';
    if (fmt === '$') return '$' + Number(val).toLocaleString(undefined, { maximumFractionDigits: 0 });
    if (fmt === '$M') return '$' + Number(val).toLocaleString(undefined, { maximumFractionDigits: 1 }) + 'M';
    if (fmt === '%') return Number(val).toFixed(1) + '%';
    if (fmt === '.1') return Number(val).toFixed(1);
    if (fmt === ',') return Number(val).toLocaleString(undefined, { maximumFractionDigits: 0 });
    if (fmt === ',k') return Number(val).toLocaleString(undefined, { maximumFractionDigits: 1 }) + 'K';
    return Number(val).toLocaleString(undefined, { maximumFractionDigits: 2 });
  }

  function computeStops(values) {
    if (!values.length) return null;
    const sorted = [...values].sort((a, b) => a - b);
    const min = sorted[0];
    const max = sorted[sorted.length - 1];
    if (min === max) return null;

    const median = sorted[Math.floor(sorted.length / 2)];
    // 5 quantile breakpoints
    const breaks = [];
    for (let i = 0; i < 5; i++) {
      const idx = Math.min(Math.floor((i / 4) * (sorted.length - 1)), sorted.length - 1);
      breaks.push(sorted[idx]);
    }

    return { breaks, min, max, median };
  }

  async function loadGeoJSON(geoType) {
    const url = GEOJSON_URLS[geoType] || GEOJSON_URLS.state;
    try {
      const resp = await fetch(url);
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
      }
      const data = await resp.json();
      geojsonData = data;
      loadError = '';
      return data;
    } catch (e) {
      loadError = `Could not load map boundaries (${url}). ${e.message}`;
      geojsonData = null;
      return null;
    }
  }

  function updateChoropleth() {
    if (!map || !geojsonData) return;

    const geoType = get(selectedGeoType);
    const idProp = GEO_ID_PROP[geoType] || 'GEOID';
    const nameProp = NAME_PROP[geoType] || 'NAME';

    // Collect numeric values for color scale
    const values = Object.values(valueMap).filter(v => typeof v === 'number' && isFinite(v));
    const stops = computeStops(values);

    // Remove existing layers and source
    if (map.getLayer(highlightLayerId)) map.removeLayer(highlightLayerId);
    if (map.getLayer(outlineLayerId)) map.removeLayer(outlineLayerId);
    if (map.getLayer(currentLayerId)) map.removeLayer(currentLayerId);
    if (map.getSource(currentSourceId)) map.removeSource(currentSourceId);

    map.addSource(currentSourceId, {
      type: 'geojson',
      data: geojsonData,
      promoteId: idProp,
    });

    // Build fill-color expression
    let fillColor = '#e0e0e0'; // default gray for no data
    if (stops && stops.breaks.length === 5) {
      fillColor = [
        'step',
        ['coalesce', ['feature-state', 'value'], -999999],
        '#e0e0e0',       // below first break (no data)
        stops.breaks[0], COLOR_SCALE[0],
        stops.breaks[1], COLOR_SCALE[1],
        stops.breaks[2], COLOR_SCALE[2],
        stops.breaks[3], COLOR_SCALE[3],
        stops.breaks[4], COLOR_SCALE[4],
      ];
    }

    // Choropleth fill layer
    map.addLayer({
      id: currentLayerId,
      type: 'fill',
      source: currentSourceId,
      paint: {
        'fill-color': fillColor,
        'fill-opacity': 0.75,
      },
    });

    // Outline layer
    map.addLayer({
      id: outlineLayerId,
      type: 'line',
      source: currentSourceId,
      paint: {
        'line-color': '#ABB9C6',
        'line-width': 0.5,
      },
    });

    // Highlight layer for selected geos
    map.addLayer({
      id: highlightLayerId,
      type: 'line',
      source: currentSourceId,
      paint: {
        'line-color': '#15123E',
        'line-width': 2.5,
      },
      filter: ['in', ['get', idProp], ['literal', [...selectedIdSet]]],
    });

    // Set feature state for values — batch in rAF for performance
    requestAnimationFrame(() => {
      if (!map || !map.getSource(currentSourceId)) return;
      for (const feature of geojsonData.features || []) {
        const fid = feature.properties?.[idProp];
        if (fid != null) {
          const val = valueMap[String(fid)];
          map.setFeatureState(
            { source: currentSourceId, id: fid },
            { value: val ?? -999999 }
          );
        }
      }
    });

    // Update legend
    if (stops) {
      legendMin = formatValue(stops.min, indicatorMeta);
      legendMedian = formatValue(stops.median, indicatorMeta);
      legendMax = formatValue(stops.max, indicatorMeta);
    } else {
      legendMin = '';
      legendMedian = '';
      legendMax = '';
    }
  }

  function handleClick(e) {
    if (!geojsonData || !map) return;
    const geoType = get(selectedGeoType);
    const idProp = GEO_ID_PROP[geoType] || 'GEOID';

    const features = map.queryRenderedFeatures(e.point, { layers: [currentLayerId] });
    if (!features.length) return;

    const feature = features[0];
    const fid = feature.properties?.[idProp];
    if (!fid) return;

    const fidStr = String(fid);
    const currentGeos = get(selectedGeos);
    const existing = currentGeos.find(g => g.id === fidStr);

    if (existing) {
      // Remove from selection
      selectedGeos.set(currentGeos.filter(g => g.id !== fidStr));
    } else {
      // Add to selection — use feature name if available
      const namePropKey = NAME_PROP[geoType] || 'NAME';
      const name = feature.properties?.[namePropKey] || fidStr;
      selectedGeos.set([...currentGeos, { id: fidStr, name, type: geoType }]);
    }
  }

  let hoveredFeatureId = null;
  let mouseMoveTimer = null;

  function handleMouseMove(e) {
    // Throttle mousemove via rAF to avoid excessive queryRenderedFeatures calls
    if (mouseMoveTimer) return;
    mouseMoveTimer = requestAnimationFrame(() => {
      mouseMoveTimer = null;
      _handleMouseMoveInner(e);
    });
  }

  function _handleMouseMoveInner(e) {
    if (!map) return;
    const geoType = get(selectedGeoType);
    const idProp = GEO_ID_PROP[geoType] || 'GEOID';
    const namePropKey = NAME_PROP[geoType] || 'NAME';

    const features = map.queryRenderedFeatures(e.point, { layers: [currentLayerId] });

    if (!features.length) {
      if (tooltip) tooltip.remove();
      map.getCanvas().style.cursor = '';
      hoveredFeatureId = null;
      return;
    }

    map.getCanvas().style.cursor = 'pointer';
    const feature = features[0];
    const fid = feature.properties?.[idProp];
    const name = feature.properties?.[namePropKey] || fid || 'Unknown';
    const val = fid ? valueMap[String(fid)] : null;
    const formatted = formatValue(val, indicatorMeta);
    const indicatorLabel = indicatorMeta?.label || indicatorKey || '';

    hoveredFeatureId = fid;

    const html = `<strong>${name}</strong><br/>${indicatorLabel}: ${formatted}`;

    if (tooltip) {
      tooltip.setLngLat(e.lngLat).setHTML(html);
    } else {
      tooltip = new maplibregl.Popup({
        closeButton: false,
        closeOnClick: false,
        className: 'map-tooltip',
      })
        .setLngLat(e.lngLat)
        .setHTML(html)
        .addTo(map);
    }
  }

  function handleMouseLeave() {
    if (tooltip) {
      tooltip.remove();
      tooltip = null;
    }
    if (map) {
      map.getCanvas().style.cursor = '';
    }
    hoveredFeatureId = null;
  }

  // Track the last loaded geoType to reload GeoJSON when it changes
  let lastGeoType = null;

  async function initOrUpdateGeo(geoType) {
    if (!map) return;
    if (geoType !== lastGeoType) {
      lastGeoType = geoType;
      await loadGeoJSON(geoType);
      if (geojsonData && map.isStyleLoaded()) {
        updateChoropleth();
      }
    } else {
      updateChoropleth();
    }
  }

  // React to geoType changes
  $: if (map) {
    initOrUpdateGeo($selectedGeoType);
  }

  // React to data / selection changes (when geoType hasn't changed)
  $: if (map && geojsonData) {
    void valueMap;
    void selectedIdSet;
    updateChoropleth();
  }

  onMount(async () => {
    maplibregl = (await import('maplibre-gl')).default;

    map = new maplibregl.Map({
      container: mapContainer,
      style: BASEMAP,
      center: [-98.5, 39.8],  // center of CONUS
      zoom: 3.5,
      attributionControl: true,
    });

    map.addControl(new maplibregl.NavigationControl(), 'top-right');

    map.on('load', async () => {
      const geoType = get(selectedGeoType);
      lastGeoType = geoType;
      await loadGeoJSON(geoType);
      if (geojsonData) {
        updateChoropleth();
      }
    });

    map.on('click', handleClick);
    map.on('mousemove', handleMouseMove);
    map.on('mouseleave', currentLayerId, handleMouseLeave);
  });

  onDestroy(() => {
    if (tooltip) {
      tooltip.remove();
      tooltip = null;
    }
    if (map) {
      map.remove();
      map = null;
    }
  });
</script>

<div class="map-wrapper">
  {#if mapIndicatorOptions.length > 1}
    <div class="map-indicator-selector">
      <select bind:value={mapIndicatorKey}>
        {#each mapIndicatorOptions as opt}
          <option value={opt.key}>{opt.label}</option>
        {/each}
      </select>
    </div>
  {/if}

  {#if loadError}
    <div class="map-error">
      <p>{loadError}</p>
      <p class="hint">Map boundaries are not yet available for this geography type. Data table and chart views are still fully functional.</p>
    </div>
  {/if}

  <div class="map-container" bind:this={mapContainer}></div>

  {#if indicatorMeta && legendMin}
    <div class="legend" role="img" aria-label="Color legend showing value range from {legendMin} to {legendMax}">
      <div class="legend-title">{indicatorMeta.label}{latestYear ? ` (${latestYear})` : ''}</div>
      <div class="legend-bar">
        {#each COLOR_SCALE as color}
          <span class="legend-swatch" style="background:{color}"></span>
        {/each}
      </div>
      <div class="legend-labels">
        <span>{legendMin}</span>
        <span>{legendMedian}</span>
        <span>{legendMax}</span>
      </div>
    </div>
  {/if}
</div>

<style>
  .map-wrapper {
    position: relative;
    width: 100%;
    height: 400px;
    border-radius: var(--radius-md);
    overflow: hidden;
    border: 1px solid var(--border-default);
    background: var(--bg-muted);
  }

  .map-indicator-selector {
    position: absolute;
    top: 10px;
    left: 10px;
    z-index: 5;
  }
  .map-indicator-selector select {
    padding: 0.35rem 0.5rem;
    font-size: 0.75rem;
    font-family: inherit;
    border: 1px solid var(--border-medium);
    border-radius: var(--radius-sm);
    background: var(--bg-card);
    color: var(--text-primary);
    box-shadow: var(--shadow-card);
    cursor: pointer;
    max-width: 220px;
  }
  .map-indicator-selector select:focus { outline: none; border-color: var(--accent-primary); }

  .map-container {
    width: 100%;
    height: 100%;
  }

  .map-error {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: var(--bg-muted);
    z-index: 10;
    padding: 2rem;
    text-align: center;
  }

  .map-error p {
    margin: 0.3rem 0;
    color: var(--text-secondary);
    font-size: 0.88rem;
  }

  .map-error .hint {
    color: var(--text-muted);
    font-size: 0.78rem;
  }

  .legend {
    position: absolute;
    bottom: 24px;
    right: 12px;
    background: var(--bg-card);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-sm);
    padding: 0.5rem 0.65rem;
    box-shadow: var(--shadow-card);
    z-index: 5;
    min-width: 140px;
    max-width: 200px;
  }

  .legend-title {
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 0.3rem;
    line-height: 1.2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .legend-bar {
    display: flex;
    height: 12px;
    border-radius: 2px;
    overflow: hidden;
  }

  .legend-swatch {
    flex: 1;
  }

  .legend-labels {
    display: flex;
    justify-content: space-between;
    font-size: 0.62rem;
    color: var(--text-muted);
    margin-top: 0.15rem;
  }

  /* MapLibre tooltip override */
  :global(.map-tooltip .maplibregl-popup-content) {
    padding: 0.4rem 0.6rem;
    font-size: 0.78rem;
    font-family: var(--font-stack);
    color: var(--text-primary);
    background: var(--bg-card);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-sm);
    box-shadow: var(--shadow-elevated);
    max-width: 260px;
  }

  :global(.map-tooltip .maplibregl-popup-tip) {
    border-top-color: var(--bg-card);
  }

  @media (max-width: 640px) {
    .map-wrapper {
      height: 250px;
    }

    .legend {
      bottom: 8px;
      right: 8px;
      padding: 0.35rem 0.5rem;
      min-width: 110px;
    }

    .legend-title {
      font-size: 0.62rem;
    }

    .legend-labels {
      font-size: 0.55rem;
    }
  }
</style>
