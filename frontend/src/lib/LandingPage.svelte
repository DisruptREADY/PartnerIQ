<script>
  import { createEventDispatcher, onMount } from 'svelte';

  const dispatch = createEventDispatcher();

  let metroCount = 380;
  let indicatorCount = 70;
  let sourceCount = 7;
  let metroTarget = 380;
  let indicatorTarget = 70;
  let mounted = false;

  // Animated counter
  function animateCount(start, end, duration, cb) {
    const startTime = performance.now();
    function tick(now) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      cb(Math.round(start + (end - start) * eased));
      if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  onMount(async () => {
    mounted = true;

    try {
      const [geoResp, indResp] = await Promise.all([
        fetch('/api/geographies?type=msa'),
        fetch('/api/indicators'),
      ]);
      if (geoResp.ok) {
        const geos = await geoResp.json();
        const usGeos = geos.filter(g => !/, (PR|GU|VI|AS|MP)\b/.test(g.name));
        metroTarget = Math.floor(usGeos.length / 10) * 10;
      }
      if (indResp.ok) {
        const inds = await indResp.json();
        indicatorTarget = Math.floor(inds.length / 10) * 10;
      }
    } catch {}

    // Animate the numbers up from 0
    animateCount(0, metroTarget, 1600, v => { metroCount = v; });
    setTimeout(() => animateCount(0, indicatorTarget, 1400, v => { indicatorCount = v; }), 200);
    setTimeout(() => animateCount(0, sourceCount, 800, v => { sourceCount = v; }), 400);
  });

  const cards = [
    {
      title: 'Explore a Region',
      desc: 'At-a-glance overview with KPIs, charts, and trends for any metro, state, or county',
      cta: 'Open Dashboard',
      view: 'dashboard',
      icon: 'dashboard',
    },
    {
      title: 'Pull Data',
      desc: 'Multi-geo, multi-indicator bulk data tool with table, chart, compare, and export views',
      cta: 'Start Pulling',
      view: 'data',
      icon: 'chart',
    },
    {
      title: 'Find Peers',
      desc: 'Discover similar regions using weighted similarity scoring across demographic and economic dimensions',
      cta: 'Find Peers',
      view: 'peers',
      icon: 'peers',
    },
  ];
</script>

<div class="landing" class:mounted>
  <section class="hero">
    <!-- Animated grid pattern background -->
    <div class="hero-grid" aria-hidden="true">
      {#each Array(48) as _, i}
        <div class="grid-cell" style="animation-delay: {(i % 8) * 0.15 + Math.floor(i / 8) * 0.1}s"></div>
      {/each}
    </div>

    <!-- Radial glow accents -->
    <div class="hero-glow hero-glow-1" aria-hidden="true"></div>
    <div class="hero-glow hero-glow-2" aria-hidden="true"></div>

    <!-- Grain texture overlay -->
    <div class="hero-grain" aria-hidden="true"></div>

    <div class="hero-inner">
      <div class="hero-badge">Federal Data Explorer</div>
      <h2 class="hero-title">Data Portal</h2>
      <p class="hero-tagline">Regional economic data at your fingertips</p>
      <p class="hero-sub">Explore metros, states, counties, and more with data from Census, BLS, BEA, and FRED.</p>
    </div>
  </section>

  <section class="cards-section">
    <div class="cards-grid">
      {#each cards as card, i}
        <button
          class="route-card"
          style="animation-delay: {0.15 + i * 0.1}s"
          on:click={() => dispatch('navigate', card.view)}
        >
          <div class="card-icon-wrap">
            {#if card.icon === 'dashboard'}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" width="28" height="28">
                <rect x="3" y="3" width="7" height="7" rx="1.5" />
                <rect x="14" y="3" width="7" height="4" rx="1.5" />
                <rect x="14" y="10" width="7" height="11" rx="1.5" />
                <rect x="3" y="13" width="7" height="8" rx="1.5" />
              </svg>
            {:else if card.icon === 'chart'}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" width="28" height="28">
                <path d="M3 3v18h18" />
                <path d="M7 16l4-8 4 5 5-10" />
              </svg>
            {:else}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" width="28" height="28">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                <path d="M16 3.13a4 4 0 0 1 0 7.75" />
              </svg>
            {/if}
          </div>

          <div class="card-accent" aria-hidden="true"></div>

          <h3 class="card-title">{card.title}</h3>
          <p class="card-desc">{card.desc}</p>
          <span class="card-cta">
            {card.cta}
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M5 12h14M12 5l7 7-7 7"/>
            </svg>
          </span>
        </button>
      {/each}
    </div>
  </section>

  <div class="stats-strip">
    <div class="stat-item">
      <span class="stat-number">{metroCount}+</span>
      <span class="stat-label">metros</span>
    </div>
    <div class="stat-divider"></div>
    <div class="stat-item">
      <span class="stat-number">{indicatorCount}+</span>
      <span class="stat-label">indicators</span>
    </div>
    <div class="stat-divider"></div>
    <div class="stat-item">
      <span class="stat-number">{sourceCount}</span>
      <span class="stat-label">data sources</span>
    </div>
  </div>
</div>

<style>
  .landing { padding: 0; }

  /* ── Hero ── */
  .hero {
    background: linear-gradient(160deg, var(--color-riviere) 0%, var(--color-riviere-dark) 40%, #0c1a3a 100%);
    color: var(--text-on-dark);
    text-align: center;
    padding: 5rem 2rem 4rem;
    margin: 0 1.25rem;
    border-radius: var(--radius-lg);
    position: relative;
    overflow: hidden;
  }

  /* Animated grid pattern */
  .hero-grid {
    position: absolute;
    inset: 0;
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    grid-template-rows: repeat(6, 1fr);
    gap: 1px;
    opacity: 0;
    animation: fadeIn 1.5s ease 0.3s forwards;
  }

  .grid-cell {
    border: 1px solid rgba(93,167,220,0.04);
    opacity: 0;
    animation: gridCellReveal 0.8s ease forwards;
  }

  .grid-cell:hover {
    background: rgba(93,167,220,0.06);
    transition: background 0.3s ease;
  }

  @keyframes gridCellReveal {
    from { opacity: 0; border-color: rgba(93,167,220,0); }
    to { opacity: 1; border-color: rgba(93,167,220,0.04); }
  }

  /* Radial glow accents */
  .hero-glow {
    position: absolute;
    border-radius: 50%;
    pointer-events: none;
    filter: blur(80px);
  }

  .hero-glow-1 {
    top: -30%;
    right: -15%;
    width: 50%;
    height: 120%;
    background: radial-gradient(ellipse, rgba(14,120,190,0.15) 0%, transparent 65%);
    animation: float 8s ease-in-out infinite;
  }

  .hero-glow-2 {
    bottom: -40%;
    left: -10%;
    width: 45%;
    height: 100%;
    background: radial-gradient(ellipse, rgba(106,58,132,0.1) 0%, transparent 65%);
    animation: float 10s ease-in-out infinite reverse;
  }

  /* Grain texture */
  .hero-grain {
    position: absolute;
    inset: -50%;
    width: 200%;
    height: 200%;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.03'/%3E%3C/svg%3E");
    pointer-events: none;
    animation: grain 4s steps(6) infinite;
  }

  .hero-inner {
    position: relative;
    z-index: 1;
    max-width: 600px;
    margin: 0 auto;
  }

  .hero-badge {
    display: inline-block;
    padding: 0.3rem 0.9rem;
    font-size: 0.62rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--color-southern-sky);
    border: 1px solid rgba(93,167,220,0.3);
    border-radius: 20px;
    margin-bottom: 1.2rem;
    background: rgba(93,167,220,0.06);
    opacity: 0;
    animation: fadeInDown 0.6s ease 0.2s forwards;
  }

  .hero-title {
    font-size: 2.8rem;
    font-weight: 800;
    margin: 0 0 0.6rem;
    letter-spacing: -0.04em;
    line-height: 1.05;
    opacity: 0;
    animation: fadeInUp 0.7s ease 0.35s forwards;
  }

  .hero-tagline {
    font-size: 1.15rem;
    margin: 0 0 0.85rem;
    opacity: 0;
    font-weight: 400;
    animation: fadeIn 0.8s ease 0.55s forwards;
  }

  .hero-sub {
    font-size: 0.82rem;
    margin: 0;
    opacity: 0;
    font-weight: 300;
    line-height: 1.6;
    color: var(--color-steel);
    animation: fadeIn 0.8s ease 0.7s forwards;
  }

  /* ── Cards ── */
  .cards-section { padding: 2.25rem 1.25rem 1rem; }

  .cards-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.25rem;
    max-width: 960px;
    margin: 0 auto;
  }

  .route-card {
    background: var(--bg-card);
    border: 1px solid var(--border-light);
    border-radius: var(--radius-lg);
    padding: 2rem 1.75rem 1.75rem;
    text-align: center;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94);
    box-shadow: var(--shadow-card);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.75rem;
    font-family: inherit;
    width: 100%;
    position: relative;
    overflow: hidden;
    opacity: 0;
    animation: fadeInUp 0.55s ease forwards;
  }

  .route-card:hover {
    box-shadow: 0 8px 30px rgba(21,18,62,0.12), 0 4px 12px rgba(14,120,190,0.08);
    transform: translateY(-5px);
    border-color: var(--accent-primary);
  }

  .route-card:focus-visible {
    outline: 2px solid var(--accent-primary);
    outline-offset: 2px;
  }

  /* Decorative accent line at top of card */
  .card-accent {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--accent-primary), var(--color-southern-sky));
    transform: scaleX(0);
    transform-origin: left;
    transition: transform 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
  }

  .route-card:hover .card-accent {
    transform: scaleX(1);
  }

  .card-icon-wrap {
    width: 56px;
    height: 56px;
    border-radius: 14px;
    background: linear-gradient(135deg, var(--bg-hover) 0%, #dceaf8 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--accent-primary);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
  }

  .route-card:hover .card-icon-wrap {
    transform: scale(1.08);
    box-shadow: 0 4px 16px rgba(14,120,190,0.12);
  }

  .card-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0;
    letter-spacing: -0.01em;
  }

  .card-desc {
    font-size: 0.82rem;
    color: var(--text-secondary);
    margin: 0;
    line-height: 1.55;
  }

  .card-cta {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    margin-top: 0.75rem;
    padding: 0.45rem 1.3rem;
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--accent-primary);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    border: 1px solid var(--accent-primary);
    border-radius: var(--radius-sm);
    transition: all 0.25s ease;
  }

  .card-cta svg {
    transition: transform 0.25s ease;
  }

  .route-card:hover .card-cta {
    background: var(--accent-primary);
    color: var(--text-on-dark);
    text-decoration: none;
  }

  .route-card:hover .card-cta svg {
    transform: translateX(3px);
  }

  /* ── Stats strip ── */
  .stats-strip {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 2.5rem;
    padding: 1.75rem 1.25rem 2.75rem;
    opacity: 0;
  }

  .mounted .stats-strip {
    animation: fadeInUp 0.6s ease 0.6s forwards;
  }

  .stat-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.2rem;
  }

  .stat-number {
    font-size: 1.65rem;
    font-weight: 800;
    color: var(--color-riviere);
    letter-spacing: -0.03em;
    font-variant-numeric: tabular-nums;
  }

  .stat-label {
    font-size: 0.72rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 500;
  }

  .stat-divider {
    width: 1px;
    height: 36px;
    background: linear-gradient(to bottom, transparent, var(--border-medium), transparent);
  }

  /* ── Responsive ── */
  @media (max-width: 640px) {
    .hero {
      padding: 3.5rem 1.25rem 2.75rem;
      margin: 0 0.5rem;
    }
    .hero-title { font-size: 2rem; }
    .hero-tagline { font-size: 0.95rem; }
    .hero-grid { grid-template-columns: repeat(4, 1fr); grid-template-rows: repeat(4, 1fr); }

    .cards-section { padding: 1.5rem 0.5rem 1rem; }
    .cards-grid { grid-template-columns: 1fr; gap: 1rem; }
    .route-card { padding: 1.5rem 1.25rem; }

    .stats-strip { gap: 1.25rem; padding: 1rem 0.5rem 2rem; }
    .stat-number { font-size: 1.3rem; }
  }
</style>
