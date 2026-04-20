<script>
  import { results, yoyData, displayMode, highlightGeo } from '../stores.js';

  let sortKey = null;
  let sortAsc = true;

  // Cell selection state
  let selectedCells = new Set();   // Set of "CBSA:Year:colKey" strings
  let anchorCell = null;           // { rowIdx: number, colIdx: number } for Shift+Click ranges
  let isDragging = false;          // true while mouse is held down for drag-select

  $: columns = $results?.columns || [];
  $: rawRows = $results?.rows || [];
  $: yoy = $yoyData;
  $: mode = $displayMode;

  // Lookup map for stable cell ID resolution (avoids O(n) find and type coercion issues)
  $: rowLookup = (() => {
    const map = new Map();
    for (const r of rawRows) {
      map.set(`${r.CBSA}:${r.Year}`, r);
    }
    return map;
  })();

  // Clear selection when data or display mode changes
  $: if ($results || $displayMode) {
    selectedCells = new Set();
    anchorCell = null;
  }

  // Indicator columns (have source/fmt metadata)
  $: indicatorCols = columns.filter(c => c.source);

  // Build display columns based on mode
  $: displayColumns = (() => {
    const base = columns.filter(c => !c.source); // CBSA, Metro, Year
    const indCols = [];
    for (const col of indicatorCols) {
      if (mode === 'raw' || mode === 'both') {
        indCols.push(col);
      }
      if (mode === 'yoy' || mode === 'both') {
        indCols.push({
          key: `${col.key}_yoy`,
          label: `${col.label} YoY`,
          source: col.source,
          fmt: col.change_type === 'pp' ? 'pp' : 'pct',
          higher_is: col.higher_is,
          change_type: col.change_type,
          isYoy: true,
          parentKey: col.key,
        });
      }
    }
    return [...base, ...indCols];
  })();

  // Build a lookup for YoY changes: {indicator: {cbsa: {year: change}}}
  $: yoyLookup = (() => {
    const lookup = {};
    for (const [ind, changes] of Object.entries(yoy)) {
      lookup[ind] = {};
      for (const ch of changes) {
        if (!lookup[ind][ch.cbsa]) lookup[ind][ch.cbsa] = {};
        lookup[ind][ch.cbsa][ch.year] = ch;
      }
    }
    return lookup;
  })();

  $: rows = sortKey
    ? [...rawRows].sort((a, b) => {
        let va, vb;
        if (sortKey.endsWith('_yoy')) {
          const parentKey = sortKey.replace('_yoy', '');
          va = getYoyValue(a, parentKey);
          vb = getYoyValue(b, parentKey);
        } else {
          va = a[sortKey];
          vb = b[sortKey];
        }
        if (va == null && vb == null) return 0;
        if (va == null) return 1;
        if (vb == null) return -1;
        if (typeof va === 'number' && typeof vb === 'number') {
          return sortAsc ? va - vb : vb - va;
        }
        const sa = String(va), sb = String(vb);
        return sortAsc ? sa.localeCompare(sb) : sb.localeCompare(sa);
      })
    : rawRows;

  function getYoyValue(row, parentKey) {
    const cbsa = row.CBSA;
    const year = row.Year;
    return yoyLookup[parentKey]?.[cbsa]?.[year]?.change ?? null;
  }

  function toggleSort(key) {
    if (sortKey === key) {
      sortAsc = !sortAsc;
    } else {
      sortKey = key;
      sortAsc = true;
    }
  }

  function formatValue(val, col) {
    if (val == null) return 'N/A';
    if (typeof val !== 'number') return val;
    const key = col.key || '';
    // Year and ID columns should never be comma-formatted
    if (key === 'Year' || key === 'CBSA') return String(val);
    const fmt = col.fmt || '';
    if (fmt.includes('%')) return val.toFixed(1) + '%';
    if (fmt.includes('$') && fmt.includes('#,##0')) return '$' + val.toLocaleString('en-US', { maximumFractionDigits: 0 });
    if (fmt === '#,##0.0') return val.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    if (fmt === '#,##0') return val.toLocaleString('en-US', { maximumFractionDigits: 0 });
    if (fmt === '0.0') return val.toFixed(1);
    return typeof val === 'number' ? val.toLocaleString('en-US') : val;
  }

  function formatYoyValue(change, changeType) {
    if (change == null) return '';
    const prefix = change > 0 ? '+' : '';
    if (changeType === 'pp') {
      return `${prefix}${change.toFixed(2)} pp`;
    }
    return `${prefix}${change.toFixed(1)}%`;
  }

  function yoyColor(change, higher_is) {
    if (change == null || higher_is === 'neutral') return '';
    const isGood = (higher_is === 'better' && change > 0) || (higher_is === 'worse' && change < 0);
    const isBad = (higher_is === 'better' && change < 0) || (higher_is === 'worse' && change > 0);
    if (isGood) return 'good-change';
    if (isBad) return 'bad-change';
    return '';
  }

  function sortIndicator(key) {
    if (sortKey !== key) return '';
    return sortAsc ? ' \u25B2' : ' \u25BC';
  }

  function cellId(row, colKey) {
    return `${row.CBSA}:${row.Year}:${colKey}`;
  }

  function selectRange(fromRow, fromCol, toRow, toCol) {
    const minRow = Math.min(fromRow, toRow);
    const maxRow = Math.max(fromRow, toRow);
    const minCol = Math.min(fromCol, toCol);
    const maxCol = Math.max(fromCol, toCol);

    const rangeSet = new Set();
    for (let r = minRow; r <= maxRow; r++) {
      for (let c = minCol; c <= maxCol; c++) {
        const rangeCol = displayColumns[c];
        if (!rangeCol?.source) continue;
        const rangeRow = rows[r];
        if (!rangeRow) continue;
        rangeSet.add(cellId(rangeRow, rangeCol.key));
      }
    }
    return rangeSet;
  }

  function handleCellClick(event, row, col, rowIdx, colIdx) {
    // Clicking a non-selectable column clears the selection
    if (!col.source) {
      clearSelection();
      return;
    }

    const id = cellId(row, col.key);

    if (event.shiftKey && anchorCell) {
      // Shift+Click: select rectangular range, replacing previous selection
      selectedCells = selectRange(anchorCell.rowIdx, anchorCell.colIdx, rowIdx, colIdx);
      // Keep anchorCell unchanged for further Shift+Clicks
    } else if (event.ctrlKey || event.metaKey) {
      // Ctrl+Click: toggle individual cell
      const next = new Set(selectedCells);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      selectedCells = next;
      anchorCell = { rowIdx, colIdx };
    } else {
      // Plain click: select single cell, clear previous
      selectedCells = new Set([id]);
      anchorCell = { rowIdx, colIdx };
    }
  }

  // Drag selection: mousedown starts, mousemove extends, mouseup ends
  function handleCellMousedown(event, row, col, rowIdx, colIdx) {
    if (!col.source || event.button !== 0) return;
    isDragging = true;
    anchorCell = { rowIdx, colIdx };
    if (!(event.ctrlKey || event.metaKey)) {
      selectedCells = new Set([cellId(row, col.key)]);
    }
    // Prevent text selection while dragging
    event.preventDefault();
  }

  function handleCellMouseenter(event, row, col, rowIdx, colIdx) {
    if (!isDragging || !anchorCell || !col.source) return;
    selectedCells = selectRange(anchorCell.rowIdx, anchorCell.colIdx, rowIdx, colIdx);
  }

  function handleMouseup() {
    isDragging = false;
  }

  function clearSelection() {
    selectedCells = new Set();
    anchorCell = null;
    isDragging = false;
  }

  function handleKeydown(event) {
    if (event.key === 'Escape') {
      clearSelection();
    }
  }

  // Compute stats from selected cells
  $: selectionStats = (() => {
    if (selectedCells.size === 0) return null;

    // Extract values and column keys from selected cells
    const entries = [];
    for (const id of selectedCells) {
      const [cbsa, yearStr, ...colParts] = id.split(':');
      const colKey = colParts.join(':'); // rejoin in case colKey contains ':'
      const row = rowLookup.get(`${cbsa}:${yearStr}`);
      if (!row) continue;

      // Get the value
      let val;
      if (colKey.endsWith('_yoy')) {
        const parentKey = colKey.slice(0, -4);
        val = getYoyValue(row, parentKey);
      } else {
        val = row[colKey];
      }

      if (val != null && typeof val === 'number') {
        const col = displayColumns.find(c => c.key === colKey) || null;
        entries.push({ val, colKey, col });
      }
    }

    if (entries.length === 0) return null;

    // Check if all selected cells share the same format (e.g., all #,##0 counts, all 0.0%, etc.)
    // This allows stats across different indicators of the same type (e.g., Bachelor's + Associate's)
    const fmts = new Set(entries.map(e => e.col?.isYoy ? (e.col.change_type === 'pp' ? 'pp' : 'pct') : (e.col?.fmt || '')));
    const isCompatible = fmts.size === 1;
    // Use the first entry's column for formatting when compatible
    const col = isCompatible ? entries[0].col : null;
    // Show label only when all cells from one indicator
    const uniqueColKeys = new Set(entries.map(e => e.colKey));
    const label = uniqueColKeys.size === 1 ? col?.label : null;

    const values = entries.map(e => e.val);
    const count = values.length;
    const sum = values.reduce((a, b) => a + b, 0);
    const avg = sum / count;
    let min = values[0], max = values[0];
    for (let i = 1; i < values.length; i++) {
      if (values[i] < min) min = values[i];
      if (values[i] > max) max = values[i];
    }

    return { count, sum, avg, min, max, isCompatible, col, label };
  })();

  function formatStat(value, col) {
    if (!col) return value.toLocaleString('en-US');
    if (col.isYoy) {
      return formatYoyValue(value, col.change_type);
    }
    return formatValue(value, col);
  }
</script>

{#if $results}
  <div class="table-wrapper" on:keydown={handleKeydown} on:click={(e) => { if (e.target === e.currentTarget) clearSelection(); }} on:mouseup={handleMouseup} on:mouseleave={handleMouseup} tabindex="-1">
    <table>
      <thead>
        <tr>
          {#each displayColumns as col}
            <th
              on:click={() => toggleSort(col.key)}
              on:keydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleSort(col.key); } }}
              class:sortable={true}
              class:yoy-col={col.isYoy}
              tabindex="0"
              role="columnheader"
              aria-sort={sortKey === col.key ? (sortAsc ? 'ascending' : 'descending') : 'none'}
            >
              {col.label}{sortIndicator(col.key)}
            </th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each rows as row, i}
          <tr class:highlight={row.CBSA === $highlightGeo} class:alt={i % 2 === 1}>
            {#each displayColumns as col, j}
              {#if col.isYoy}
                {@const change = getYoyValue(row, col.parentKey)}
                <td
                  class="numeric yoy-cell {yoyColor(change, col.higher_is)}"
                  class:selectable={true}
                  class:cell-selected={selectedCells.has(cellId(row, col.key))}
                  on:click={(e) => handleCellClick(e, row, col, i, j)}
                  on:mousedown={(e) => handleCellMousedown(e, row, col, i, j)}
                  on:mouseenter={(e) => handleCellMouseenter(e, row, col, i, j)}
                  aria-selected={selectedCells.has(cellId(row, col.key))}
                >
                  {formatYoyValue(change, col.change_type)}
                </td>
              {:else}
                <td
                  class:na={row[col.key] == null}
                  class:numeric={typeof row[col.key] === 'number'}
                  class:selectable={!!col.source}
                  class:cell-selected={col.source && selectedCells.has(cellId(row, col.key))}
                  on:click={(e) => handleCellClick(e, row, col, i, j)}
                  on:mousedown={(e) => handleCellMousedown(e, row, col, i, j)}
                  on:mouseenter={(e) => handleCellMouseenter(e, row, col, i, j)}
                  aria-selected={col.source ? selectedCells.has(cellId(row, col.key)) : undefined}
                >
                  {formatValue(row[col.key], col)}
                </td>
              {/if}
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
    {#if selectionStats}
      <div class="stats-bar">
        {#if selectionStats.label}
          <span class="stats-indicator">{selectionStats.label}</span>
        {/if}
        <span class="stat"><strong>Count:</strong> {selectionStats.count}</span>
        {#if selectionStats.isCompatible}
          <span class="stat"><strong>Sum:</strong> {formatStat(selectionStats.sum, selectionStats.col)}</span>
          <span class="stat"><strong>Avg:</strong> {formatStat(selectionStats.avg, selectionStats.col)}</span>
          <span class="stat"><strong>Min:</strong> {formatStat(selectionStats.min, selectionStats.col)}</span>
          <span class="stat"><strong>Max:</strong> {formatStat(selectionStats.max, selectionStats.col)}</span>
        {:else}
          <span class="stat muted">Select cells with same format</span>
        {/if}
      </div>
    {/if}
  </div>
{/if}

<style>
  .table-wrapper {
    overflow-x: auto;
    max-height: 70vh;
    overflow-y: auto;
    position: relative;
    -webkit-overflow-scrolling: touch;
    border-radius: var(--radius-md);
    border: 1px solid var(--border-default);
    animation: fadeIn 0.3s ease;
    box-shadow: 0 1px 4px rgba(21,18,62,0.06);
  }

  /* Custom scrollbar */
  .table-wrapper::-webkit-scrollbar { width: 6px; height: 6px; }
  .table-wrapper::-webkit-scrollbar-track { background: var(--bg-muted); }
  .table-wrapper::-webkit-scrollbar-thumb { background: var(--border-medium); border-radius: 3px; }
  .table-wrapper::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
  table { border-collapse: separate; border-spacing: 0; width: 100%; font-size: 0.82rem; }
  th {
    position: sticky;
    top: 0;
    background: var(--color-riviere);
    color: var(--text-on-dark);
    padding: 0.55rem 0.65rem;
    text-align: left;
    cursor: pointer;
    white-space: nowrap;
    font-weight: 600;
    font-size: 0.76rem;
    border: none;
    border-bottom: 2px solid rgba(14,120,190,0.3);
    border-right: 1px solid rgba(255,255,255,0.1);
    user-select: none;
    z-index: 2;
    letter-spacing: 0.01em;
  }
  th:last-child { border-right: none; }
  th.yoy-col { background: var(--color-riviere-dark); }
  th:hover { background: var(--color-riviere-dark); }
  td {
    padding: 0.4rem 0.65rem;
    border-bottom: 1px solid var(--border-light);
    border-right: 1px solid var(--border-light);
    white-space: nowrap;
    background: var(--bg-card);
    transition: background var(--transition-fast);
  }
  td:last-child { border-right: none; }
  td.numeric { text-align: right; font-variant-numeric: tabular-nums; }
  td.na { color: var(--text-muted); font-style: italic; }
  tr.alt td { background: var(--bg-muted); }
  tr.highlight td { background: var(--highlight-bg); font-weight: 600; }
  tr:hover td { background: var(--bg-hover); }
  tr.highlight:hover td { background: var(--highlight-bg-hover); }

  /* Frozen first two columns */
  th:nth-child(-n+2) { position: sticky; z-index: 4; }
  td:nth-child(-n+2) { position: sticky; z-index: 1; }
  th:nth-child(1), td:nth-child(1) { left: 0; min-width: 65px; max-width: 65px; }
  th:nth-child(2), td:nth-child(2) {
    left: 65px;
    min-width: 170px;
    border-right: 2px solid var(--border-medium);
  }

  .yoy-cell { font-size: 0.78rem; }
  .good-change { background: color-mix(in srgb, var(--positive) 14%, white) !important; color: var(--positive); font-weight: 600; }
  .bad-change { background: color-mix(in srgb, var(--negative) 14%, white) !important; color: var(--negative); font-weight: 600; }

  /* Cell selection */
  td.selectable { cursor: cell; user-select: none; }
  td.cell-selected {
    background: var(--selection-bg, #cde4f7) !important;
    outline: 2px solid var(--selection-border, #1f4e79);
    outline-offset: -2px;
    position: relative;
    z-index: 1;
  }
  tr.highlight td.cell-selected { background: var(--selection-bg, #cde4f7) !important; }

  /* Stats bar */
  .stats-bar {
    position: sticky;
    bottom: 0;
    left: 0;
    right: 0;
    background: var(--color-riviere);
    color: var(--text-on-dark);
    padding: 0.5rem 0.75rem;
    font-size: 0.78rem;
    display: flex;
    gap: 1.5rem;
    align-items: center;
    border-top: 2px solid var(--highlight-bg);
    z-index: 3;
    animation: statsSlideUp 0.15s ease-out;
  }
  .stats-indicator {
    opacity: 0.7;
    font-size: 0.72rem;
    font-style: italic;
  }
  .stat strong { font-weight: 600; }
  .stat.muted { opacity: 0.6; font-style: italic; }

  @keyframes statsSlideUp {
    from { transform: translateY(100%); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
  }

  @media (max-width: 640px) {
    .table-wrapper { max-height: 60vh; }
  }
</style>
