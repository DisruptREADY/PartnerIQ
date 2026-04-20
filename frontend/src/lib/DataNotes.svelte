<script>
  import { results, selectedIndicators, indicatorsMeta, acsDataset } from '../stores.js';

  export let alwaysShow = false;

  let expanded = false;

  $: hasResults = $results?.rows?.length > 0;

  $: selectedMeta = $indicatorsMeta.filter(m => $selectedIndicators.includes(m.key));

  // Source descriptions — dynamic based on ACS dataset choice
  $: sourceInfo = {
    census: {
      name: $acsDataset === 'acs5' ? 'Census Bureau ACS 5-Year Estimates' : 'Census Bureau ACS 1-Year Estimates',
      url: 'https://data.census.gov',
      notes: $acsDataset === 'acs5'
        ? 'American Community Survey 5-year estimates. Covers all geographies including small areas. Represents a rolling 5-year period. Latest available: 2023.'
        : 'American Community Survey 1-year estimates. Covers areas with 65,000+ population only. Not available for 2020 due to COVID-19 data collection disruption. Latest available: 2024.',
      methodology: $acsDataset === 'acs5'
        ? 'Data is fetched from the Census Bureau API for each selected year. Multi-variable indicators (e.g., educational attainment buckets) are summed from their component variables. 5-year estimates represent data collected over a 5-year period ending in the reported year.'
        : 'Data is fetched from the Census Bureau API for each selected year. Multi-variable indicators (e.g., educational attainment buckets) are summed from their component variables. 1-year estimates reflect a single calendar year of data collection.',
    },
    derived: {
      name: 'Derived from Census ACS',
      url: 'https://data.census.gov',
      notes: 'Computed from multiple Census ACS variables. Inherits the ACS estimate type selected above (1-year or 5-year).',
      methodology: 'Poverty rate = (population below poverty / population for whom status is determined) x 100. In-migration = movers from different state + movers from different county within same state. Interstate in-migration = movers from different state only (B07001_065E). GDP per capita = (GDP in millions x 1,000,000) / total population.',
    },
    bls: {
      name: 'Bureau of Labor Statistics',
      url: 'https://www.bls.gov/data/',
      notes: 'Current Employment Statistics (CES) for nonfarm payroll jobs. Local Area Unemployment Statistics (LAUS) for unemployment rate.',
      methodology: 'Annual average (M13 period) is used when available. When the annual average has not yet been published (typically for the current or most recent year), the most recent monthly value is used as a fallback. Nonfarm jobs are reported in thousands. State-level series use SMS/LASST prefixes; MSA-level uses SMU/LAUMT; county-level uses LAUCN.',
    },
    bea: {
      name: 'Bureau of Economic Analysis',
      url: 'https://www.bea.gov/data',
      notes: 'Regional economic accounts from the U.S. Department of Commerce.',
      methodology: 'Regional Price Parities (RPP/MARPP table) are available at MSA level only and measure price differences across regions relative to the national average (100 = national). GDP uses SAGDP2 (state) and CAGDP2 (county) tables. County GDP is reported in thousands by BEA and converted to millions for display consistency. BEA data typically lags 1-2 years behind the current year.',
    },
    oews: {
      name: 'BLS Occupational Employment and Wage Statistics (OEWS)',
      url: 'https://www.bls.gov/oes/',
      notes: 'Annual survey of employment and wages by SOC major occupation group. Data is available for the latest year only (currently 2024) — no historical time-series.',
      methodology: 'Employment counts and annual median wages are fetched by SOC major group (22 categories). Series use the OEUM prefix with MSA area codes. OEWS data uses the A01 (annual) period code. Because OEWS is an annual point-in-time survey, only the most recent year is available via the BLS API.',
    },
    fred: {
      name: 'Federal Reserve Economic Data (FRED)',
      url: 'https://fred.stlouisfed.org',
      notes: 'St. Louis Fed data aggregation service. Hosts data originally sourced from multiple agencies.',
      methodology: 'MSA GDP (NGMP series) is sourced from BEA via FRED. House Price Index (FHFA All-Transactions HPI) measures average price changes in repeat sales or refinancings — not dollar values. Building permits (BPPRIV series) count new private housing structures authorized, originally sourced from the Census Bureau Building Permits Survey. Monthly series are aggregated to annual frequency by FRED. State/county building permits use state abbreviation or 6-digit FIPS codes.',
    },
    qcew: {
      name: 'BLS Quarterly Census of Employment and Wages (QCEW)',
      url: 'https://data.bls.gov/cew/',
      notes: 'Administrative records from the unemployment insurance (UI) system. Covers virtually all employers. Available at county, MSA, and state levels. Data available from 2014 onward.',
      methodology: 'Annual average employment level is extracted from the QCEW API for the "Total, All Industries" row (all ownerships). QCEW employment counts are actual job counts (not thousands like CES nonfarm payroll). QCEW uses UI administrative records rather than employer surveys, so counts may differ from CES nonfarm payroll figures. QCEW data typically lags 6-9 months.',
    },
  };

  // Deduplicate sources that appear in selected indicators
  $: activeSources = (() => {
    const sources = new Set();
    for (const m of selectedMeta) {
      // Map display_source back to internal source key
      if (m.source === 'ACS' || m.source === 'census') sources.add('census');
      else if (m.source === 'BLS' || m.source === 'bls') sources.add('bls');
      else if (m.source === 'BEA' || m.source === 'bea') sources.add('bea');
      else if (m.source === 'FRED' || m.source === 'fred') sources.add('fred');
      else if (m.source === 'QCEW' || m.source === 'qcew') sources.add('qcew');
      else if (m.source === 'derived') sources.add('derived');
      else sources.add(m.source);
    }
    return sources;
  })();
</script>

{#if alwaysShow || hasResults}
  <div class="data-notes" class:standalone={alwaysShow}>
    {#if !alwaysShow}
      <button class="toggle" on:click={() => expanded = !expanded}>
        {expanded ? 'Hide' : 'Show'} Data Sources & Methodology
      </button>
    {/if}

    {#if alwaysShow || expanded}
      <div class="notes-content">
        {#if alwaysShow}
          <h3 class="page-title">Data Sources & Methodology</h3>
        {:else}
          <h4>Data Sources</h4>
        {/if}

        {#if alwaysShow}
          <!-- Show all sources when viewing standalone -->
          {#each Object.entries(sourceInfo) as [key, info]}
            <div class="source">
              <strong><a href={info.url} target="_blank" rel="noopener">{info.name}</a></strong>
              <p>{info.notes}</p>
              <p class="methodology">{info.methodology}</p>
            </div>
          {/each}
        {:else}
          <!-- Show only active sources when viewing after data pull -->
          {#each Object.entries(sourceInfo) as [key, info]}
            {#if activeSources.has(key)}
              <div class="source">
                <strong><a href={info.url} target="_blank" rel="noopener">{info.name}</a></strong>
                <p>{info.notes}</p>
                <p class="methodology">{info.methodology}</p>
              </div>
            {/if}
          {/each}
        {/if}

        {#if selectedMeta.length > 0 && !alwaysShow}
          <h4>Selected Indicators</h4>
          <table>
            <thead>
              <tr>
                <th>Indicator</th>
                <th>Source</th>
                <th>Change Type</th>
                <th>Direction</th>
              </tr>
            </thead>
            <tbody>
              {#each selectedMeta as m}
                <tr>
                  <td>{m.label}</td>
                  <td>{m.source.toUpperCase()}</td>
                  <td>{m.change_type === 'pp' ? 'Percentage point' : 'Percent'}</td>
                  <td>
                    {#if m.higher_is === 'better'}
                      Higher = better
                    {:else if m.higher_is === 'worse'}
                      Lower = better
                    {:else}
                      Neutral
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}

        <h4>General Methodology</h4>
        <ul>
          <li><strong>YoY Changes:</strong> Percent change = ((current - prior) / |prior|) x 100. Percentage point change = current - prior.</li>
          <li><strong>Year availability:</strong> Each data source has different year coverage. When multiple indicators are selected, all available years are shown. If a specific indicator lacks data for a selected year, that cell will be blank.</li>
          <li><strong>ACS Estimate Type:</strong> The 1-year / 5-year toggle in the sidebar affects only Census ACS indicators. BLS, BEA, and FRED data are unaffected by this setting.</li>
          <li><strong>2020 gap (ACS 1-year):</strong> The Census Bureau did not release standard ACS 1-year estimates for 2020 due to low response rates during the COVID-19 pandemic. ACS 5-year estimates include 2020.</li>
        </ul>
      </div>
    {/if}
  </div>
{/if}

<style>
  .data-notes {
    margin-top: 1rem;
    border-top: 1px solid #ddd;
    padding-top: 0.5rem;
  }
  .data-notes.standalone {
    margin-top: 0;
    border-top: none;
    padding-top: 0;
  }

  .page-title {
    font-size: 1.1rem;
    color: #1f4e79;
    margin: 0 0 0.75rem;
  }

  .toggle {
    background: none;
    border: none;
    color: #1f4e79;
    font-size: 0.78rem;
    cursor: pointer;
    text-decoration: underline;
    padding: 0;
  }

  .notes-content {
    margin-top: 0.5rem;
    font-size: 0.78rem;
    color: #555;
  }

  h4 {
    font-size: 0.82rem;
    color: #1f4e79;
    margin: 0.75rem 0 0.3rem;
  }

  .source {
    margin-bottom: 0.6rem;
    padding-left: 0.5rem;
    border-left: 2px solid #1f4e79;
  }
  .source strong { font-size: 0.8rem; }
  .source a { color: #1f4e79; text-decoration: none; }
  .source a:hover { text-decoration: underline; }
  .source p { margin: 0.2rem 0; font-size: 0.75rem; }
  .source .methodology { color: #777; }

  table { border-collapse: collapse; width: 100%; margin: 0.5rem 0; }
  th {
    background: #f0f0f0;
    padding: 0.3rem 0.5rem;
    text-align: left;
    font-size: 0.75rem;
    border: 1px solid #ddd;
  }
  td {
    padding: 0.3rem 0.5rem;
    border: 1px solid #ddd;
    font-size: 0.75rem;
  }

  ul { padding-left: 1.2rem; }
  li { margin-bottom: 0.3rem; font-size: 0.75rem; line-height: 1.4; }
</style>
