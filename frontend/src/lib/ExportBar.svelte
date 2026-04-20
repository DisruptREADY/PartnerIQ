<script>
  import { results, selectedGeos, selectedIndicators, selectedYears, selectedGeoType, acsDataset, coliAdjust, inflationAdjust, inflationBaseYear } from '../stores.js';

  $: columns = $results?.columns || [];
  $: rows = $results?.rows || [];
  $: hasData = rows.length > 0;

  function downloadCSV() {
    if (!hasData) return;
    const header = columns.map(c => {
      const lbl = c.label || '';
      if (lbl.includes(',') || lbl.includes('"')) {
        return '"' + lbl.replace(/"/g, '""') + '"';
      }
      return lbl;
    }).join(',');
    const body = rows.map(row =>
      columns.map(c => {
        const val = row[c.key];
        if (val == null) return '';
        if (typeof val === 'string' && (val.includes(',') || val.includes('"'))) {
          return '"' + val.replace(/"/g, '""') + '"';
        }
        return val;
      }).join(',')
    ).join('\n');

    const csv = header + '\n' + body;
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'data_portal_export.csv';
    a.click();
    URL.revokeObjectURL(url);
  }

  function copyToClipboard() {
    if (!hasData) return;
    const header = columns.map(c => c.label).join('\t');
    const body = rows.map(row =>
      columns.map(c => {
        const val = row[c.key];
        return val == null ? '' : val;
      }).join('\t')
    ).join('\n');

    navigator.clipboard.writeText(header + '\n' + body);
    copied = true;
    setTimeout(() => { copied = false; }, 2000);
  }

  let exporting = false;

  async function downloadExcel() {
    if (!hasData) return;
    exporting = true;
    try {
      const resp = await fetch('/api/export/xlsx', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          geo_ids: $selectedGeos.map(g => g.id || g.cbsa),
          indicators: $selectedIndicators,
          years: $selectedYears,
          geo_type: $selectedGeoType,
          acs_dataset: $acsDataset,
          coli_adjust: $coliAdjust,
          inflation_adjust: $inflationAdjust,
          inflation_base_year: $inflationBaseYear,
        }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        const detail = typeof err.detail === 'string' ? err.detail : 'Excel export failed';
        alert(detail);
        return;
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'data_portal_export.xlsx';
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert('Excel export failed: ' + e.message);
    } finally {
      exporting = false;
    }
  }

  let copied = false;
</script>

{#if hasData}
  <div class="export-bar">
    <span class="row-count">{rows.length} rows x {columns.length} cols</span>
    <div class="actions">
      <button class="btn" on:click={downloadCSV}>CSV</button>
      <button class="btn" on:click={downloadExcel} disabled={exporting}>
        {exporting ? 'Exporting...' : 'Excel'}
      </button>
      <button class="btn" on:click={copyToClipboard}>
        {copied ? 'Copied!' : 'Copy'}
      </button>
    </div>
  </div>
{/if}

<style>
  .export-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.6rem 0.75rem;
    border-top: 1px solid var(--border-light);
    margin-top: 0.5rem;
    background: var(--bg-muted);
    border-radius: var(--radius-sm);
    animation: fadeIn 0.3s ease;
  }
  .row-count {
    font-size: 0.76rem;
    color: var(--text-muted);
    font-weight: 500;
    letter-spacing: 0.01em;
  }
  .actions { display: flex; gap: 0.35rem; }
  .btn {
    padding: 0.38rem 0.85rem;
    font-size: 0.72rem;
    font-weight: 600;
    border: 1px solid var(--accent-primary);
    background: var(--accent-primary);
    color: var(--text-on-dark);
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all var(--transition-fast);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    font-family: var(--font-body);
  }
  .btn:hover { background: var(--color-southern-sky); border-color: var(--color-southern-sky); transform: translateY(-1px); box-shadow: 0 2px 6px rgba(14,120,190,0.2); }
  .btn:active { transform: translateY(0); box-shadow: none; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

  @media (max-width: 640px) {
    .export-bar { flex-wrap: wrap; gap: 0.5rem; padding: 0.5rem; }
    .actions { flex-wrap: wrap; }
  }
</style>
