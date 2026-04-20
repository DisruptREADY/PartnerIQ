<script>
  import { results, highlightGeo, selectedGeoType } from '../stores.js';

  let geoA = '';
  let geoB = '';

  $: columns = $results?.columns || [];
  $: rows = $results?.rows || [];
  $: indicatorCols = columns.filter(c => c.source);

  // Get unique geos
  $: geos = [...new Map(rows.map(r => [r.CBSA, r.Metro || r.CBSA])).entries()];

  // Reset selections when data changes
  let prevResultsRef = null;
  $: if ($results !== prevResultsRef) {
    prevResultsRef = $results;
    geoA = '';
    geoB = '';
    comparisonYear = null;
  }

  // Auto-select: highlight geo as A, first other as B
  $: if (geos.length >= 2 && !geoA) {
    const hl = geos.find(([id]) => id === $highlightGeo);
    geoA = hl ? hl[0] : geos[0][0];
    geoB = geos.find(([id]) => id !== geoA)?.[0] || geos[1][0];
  }

  // Available years and selected comparison year
  $: allYears = [...new Set(rows.map(r => r.Year).filter(Boolean))].sort();
  let comparisonYear = null;
  $: if (allYears.length > 0 && (!comparisonYear || !allYears.includes(comparisonYear))) {
    comparisonYear = allYears[allYears.length - 1];
  }

  $: rowA = rows.find(r => r.CBSA === geoA && r.Year === comparisonYear);
  $: rowB = rows.find(r => r.CBSA === geoB && r.Year === comparisonYear);
  $: nameA = geos.find(([id]) => id === geoA)?.[1]?.split(',')[0] || geoA;
  $: nameB = geos.find(([id]) => id === geoB)?.[1]?.split(',')[0] || geoB;

  // Dynamic label based on geo type
  $: geoLabel = $selectedGeoType === 'state' ? 'State'
    : $selectedGeoType === 'county' ? 'County'
    : $selectedGeoType === 'micro' ? 'Micro'
    : $selectedGeoType === 'place' ? 'Place'
    : 'Metro';

  function formatVal(val, col) {
    if (val == null) return 'N/A';
    if (typeof val !== 'number') return val;
    const fmt = col.fmt || '';
    if (fmt.includes('%')) return val.toFixed(1) + '%';
    if (fmt.includes('$') && fmt.includes('#,##0')) return '$' + val.toLocaleString('en-US', { maximumFractionDigits: 0 });
    if (fmt === '#,##0.0') return val.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    if (fmt === '#,##0') return val.toLocaleString('en-US', { maximumFractionDigits: 0 });
    if (fmt === '0.0') return val.toFixed(1);
    return val.toLocaleString('en-US');
  }

  function diff(a, b) {
    if (a == null || b == null) return null;
    return a - b;
  }

  function formatDiff(d, col) {
    if (d == null) return '';
    const prefix = d > 0 ? '+' : '';
    const fmt = col.fmt || '';
    if (fmt.includes('%')) return prefix + d.toFixed(1) + '%';
    if (fmt.includes('$') && fmt.includes('#,##0')) return prefix + '$' + Math.round(d).toLocaleString('en-US');
    if (fmt === '#,##0.0') return prefix + d.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    if (fmt === '#,##0') return prefix + Math.round(d).toLocaleString('en-US');
    return prefix + d.toFixed(1);
  }

  // Diff coloring that respects higher_is semantics
  function diffClass(d, col) {
    if (d == null || d === 0) return '';
    const higherIs = col.higher_is || 'neutral';
    if (higherIs === 'neutral') return d > 0 ? 'diff-neutral-pos' : 'diff-neutral-neg';
    if (higherIs === 'better') return d > 0 ? 'diff-good' : 'diff-bad';
    if (higherIs === 'worse') return d > 0 ? 'diff-bad' : 'diff-good';
    return '';
  }
</script>

<div class="comparison">
  <div class="selectors">
    <div class="selector">
      <label>{geoLabel} A:
        <select bind:value={geoA}>
          {#each geos as [id, name]}
            <option value={id}>{name ? name.split(',')[0] : id}</option>
          {/each}
        </select>
      </label>
    </div>
    <span class="vs-badge">VS</span>
    <div class="selector">
      <label>{geoLabel} B:
        <select bind:value={geoB}>
          {#each geos as [id, name]}
            <option value={id}>{name ? name.split(',')[0] : id}</option>
          {/each}
        </select>
      </label>
    </div>
    {#if allYears.length > 1}
      <div class="selector">
        <label>Year:
          <select bind:value={comparisonYear}>
            {#each allYears as yr}
              <option value={yr}>{yr}</option>
            {/each}
          </select>
        </label>
      </div>
    {/if}
  </div>

  {#if rowA && rowB}
    <p class="year-note">Comparing year: {comparisonYear}</p>
    <table>
      <thead>
        <tr>
          <th>Indicator</th>
          <th class="val-col">{nameA}</th>
          <th class="val-col">{nameB}</th>
          <th class="val-col">Difference (A-B)</th>
        </tr>
      </thead>
      <tbody>
        {#each indicatorCols as col}
          {@const valA = rowA[col.key]}
          {@const valB = rowB[col.key]}
          {@const d = diff(valA, valB)}
          <tr>
            <td class="ind-name">{col.label}</td>
            <td class="val">{formatVal(valA, col)}</td>
            <td class="val">{formatVal(valB, col)}</td>
            <td class="val diff {diffClass(d, col)}">
              {formatDiff(d, col)}
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {:else}
    <p class="no-data">Select two geographies to compare.</p>
  {/if}
</div>

<style>
  .comparison {
    padding: 0.5rem 0;
    animation: fadeIn 0.3s ease;
  }

  .selectors {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1rem;
    flex-wrap: wrap;
    background: var(--bg-muted);
    padding: 0.85rem 1rem;
    border-radius: var(--radius-md);
    border: 1px solid var(--border-light);
  }
  .selector { display: flex; align-items: center; gap: 0.4rem; }
  .selector label { font-size: 0.8rem; font-weight: 600; color: var(--text-secondary); }
  .selector select {
    padding: 0.35rem 0.5rem;
    font-size: 0.82rem;
    border: 1px solid var(--border-medium);
    border-radius: var(--radius-sm);
    font-family: inherit;
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
    background: var(--bg-card);
  }
  .selector select:focus { border-color: var(--accent-primary); outline: none; box-shadow: 0 0 0 3px rgba(14,120,190,0.1); }
  .vs-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--accent-primary) 0%, var(--color-southern-sky) 100%);
    color: var(--text-on-dark);
    font-size: 0.6rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    flex-shrink: 0;
    box-shadow: 0 2px 8px rgba(14,120,190,0.2);
  }

  .year-note { font-size: 0.76rem; color: var(--text-muted); margin-bottom: 0.5rem; font-weight: 500; }

  table {
    border-collapse: separate;
    border-spacing: 0;
    width: 100%;
    font-size: 0.82rem;
    border-radius: var(--radius-md);
    overflow: hidden;
    border: 1px solid var(--border-default);
    box-shadow: 0 1px 4px rgba(21,18,62,0.06);
    animation: fadeInUp 0.4s ease;
  }
  th {
    background: var(--color-riviere);
    color: var(--text-on-dark);
    padding: 0.5rem 0.65rem;
    text-align: left;
    font-weight: 600;
    font-size: 0.76rem;
    border: none;
    border-bottom: 2px solid rgba(14,120,190,0.3);
    border-right: 1px solid rgba(255,255,255,0.1);
  }
  th:last-child { border-right: none; }
  th.val-col { text-align: right; }
  td {
    padding: 0.42rem 0.65rem;
    border-bottom: 1px solid var(--border-light);
    border-right: 1px solid var(--border-light);
    background: var(--bg-card);
    transition: background var(--transition-fast);
  }
  td:last-child { border-right: none; }
  td.ind-name { font-weight: 500; color: var(--text-primary); }
  td.val { text-align: right; font-variant-numeric: tabular-nums; }
  td.diff-good { color: var(--positive); background: color-mix(in srgb, var(--positive) 14%, white) !important; font-weight: 600; }
  td.diff-bad { color: var(--negative); background: color-mix(in srgb, var(--negative) 14%, white) !important; font-weight: 600; }
  td.diff-neutral-pos { color: var(--text-secondary); background: color-mix(in srgb, var(--accent-primary) 8%, white); }
  td.diff-neutral-neg { color: var(--text-secondary); background: color-mix(in srgb, var(--accent-primary) 8%, white); }
  tr:nth-child(even) td { background: var(--bg-muted); }
  tr:hover td { background: var(--bg-hover); }
  .no-data { color: var(--text-muted); font-size: 0.85rem; text-align: center; padding: 2rem 0; }
</style>
