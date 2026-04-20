<script>
  import { onMount, onDestroy } from 'svelte';
  import 'maplibre-gl/dist/maplibre-gl.css';

  /** @type {typeof import('maplibre-gl').default} */
  let maplibregl;

  export let geoId = null;
  export let geoType = 'msa';

  const BASEMAP = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';

  const GEOJSON_URLS = {
    state: '/geo/states.geojson',
    msa: '/geo/cbsas.geojson',
    micro: '/geo/cbsas.geojson',
    county: '/geo/counties.geojson',
  };

  let mapContainer;
  let map = null;
  let geojsonCache = {};
  let currentLayer = null;

  function getGeojsonUrl(type) {
    return GEOJSON_URLS[type] || GEOJSON_URLS.msa;
  }

  async function loadGeojson(type) {
    const url = getGeojsonUrl(type);
    if (geojsonCache[url]) return geojsonCache[url];
    const resp = await fetch(url);
    if (!resp.ok) return null;
    const data = await resp.json();
    geojsonCache[url] = data;
    return data;
  }

  function computeBounds(feature) {
    // Compute bounding box from feature geometry
    let minLng = Infinity, minLat = Infinity, maxLng = -Infinity, maxLat = -Infinity;

    function processCoords(coords) {
      if (typeof coords[0] === 'number') {
        // It's a single coordinate [lng, lat]
        if (coords[0] < minLng) minLng = coords[0];
        if (coords[0] > maxLng) maxLng = coords[0];
        if (coords[1] < minLat) minLat = coords[1];
        if (coords[1] > maxLat) maxLat = coords[1];
      } else {
        coords.forEach(c => processCoords(c));
      }
    }

    processCoords(feature.geometry.coordinates);
    return [[minLng, minLat], [maxLng, maxLat]];
  }

  async function renderMap() {
    if (!map || !geoId || !geoType) return;

    const geojson = await loadGeojson(geoType);
    if (!geojson) return;

    // Find the selected feature
    const selectedFeature = geojson.features.find(f => f.properties.GEOID === geoId);

    // Clean up previous layers/sources
    if (currentLayer) {
      if (map.getLayer('selected-fill')) map.removeLayer('selected-fill');
      if (map.getLayer('selected-outline')) map.removeLayer('selected-outline');
      if (map.getLayer('context-outlines')) map.removeLayer('context-outlines');
      if (map.getSource('geo-data')) map.removeSource('geo-data');
      currentLayer = null;
    }

    // Add all features as context outlines
    map.addSource('geo-data', {
      type: 'geojson',
      data: geojson,
    });

    // Light outlines for all features (context)
    map.addLayer({
      id: 'context-outlines',
      type: 'line',
      source: 'geo-data',
      paint: {
        'line-color': '#c8d0da',
        'line-width': 0.5,
      },
    });

    // Highlighted fill for selected feature
    map.addLayer({
      id: 'selected-fill',
      type: 'fill',
      source: 'geo-data',
      paint: {
        'fill-color': '#0E78BE',
        'fill-opacity': 0.35,
      },
      filter: ['==', ['get', 'GEOID'], geoId],
    });

    // Bold outline for selected feature
    map.addLayer({
      id: 'selected-outline',
      type: 'line',
      source: 'geo-data',
      paint: {
        'line-color': '#15123E',
        'line-width': 2.5,
      },
      filter: ['==', ['get', 'GEOID'], geoId],
    });

    currentLayer = true;

    // Fit bounds to the selected feature
    if (selectedFeature) {
      const bounds = computeBounds(selectedFeature);
      map.fitBounds(bounds, {
        padding: { top: 50, bottom: 50, left: 50, right: 50 },
        maxZoom: 9,
        duration: 800,
      });
    }
  }

  onMount(async () => {
    maplibregl = (await import('maplibre-gl')).default;

    map = new maplibregl.Map({
      container: mapContainer,
      style: BASEMAP,
      center: [-95.7, 37.1],
      zoom: 3.2,
      attributionControl: false,
      interactive: false,    // read-only locator — no pan/zoom
    });

    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');

    map.on('load', () => {
      renderMap();
    });
  });

  onDestroy(() => {
    if (map) {
      map.remove();
      map = null;
    }
  });

  // Re-render when geoId or geoType changes
  $: if (map && map.loaded() && geoId) {
    renderMap();
  }
</script>

<div class="dashboard-map">
  <div class="map-container" bind:this={mapContainer}></div>
</div>

<style>
  .dashboard-map {
    overflow: hidden;
    height: 100%;
    min-height: 220px;
  }

  .map-container {
    width: 100%;
    height: 100%;
    min-height: 220px;
  }

  /* Override MapLibre attribution for cleaner look */
  .dashboard-map :global(.maplibregl-ctrl-attrib) {
    font-size: 9px;
    background: rgba(255,255,255,0.65);
    padding: 1px 4px;
    border-radius: 3px;
  }

  @media (max-width: 640px) {
    .dashboard-map,
    .map-container {
      min-height: 180px;
    }
  }
</style>
