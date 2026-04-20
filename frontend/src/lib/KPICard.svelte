<script>
  import { onMount, afterUpdate } from 'svelte';

  export let label = '';
  export let value = null;
  export let change = null;
  export let changeType = 'pct';
  export let higherIs = 'neutral';
  export let fmt = '#,##0';
  export let sparklineData = [];
  export let onClick = null;
  export let index = 0; // For staggered entrance

  let canvasEl;
  let displayValue = null;
  let prevValue = null;

  function formatValue(v, fmtStr) {
    if (v == null) return '—';
    const isDollar = fmtStr.startsWith('$');
    const isPercent = fmtStr.endsWith('%');
    const cleaned = fmtStr.replace('$', '').replace('%', '');
    let decimals = 0;
    const dotIdx = cleaned.indexOf('.');
    if (dotIdx >= 0) decimals = cleaned.length - dotIdx - 1;
    const num = Number(v);
    if (isNaN(num)) return '—';
    const hasComma = cleaned.includes(',');
    let formatted;
    if (hasComma) {
      formatted = num.toLocaleString('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      });
    } else {
      formatted = num.toFixed(decimals);
    }
    if (isDollar) formatted = '$' + formatted;
    if (isPercent) formatted = formatted + '%';
    return formatted;
  }

  function formatChange(val) {
    if (val == null) return '';
    const num = Number(val);
    if (isNaN(num)) return '';
    const sign = num > 0 ? '+' : '';
    if (changeType === 'pp') return sign + num.toFixed(1) + ' pp';
    return sign + num.toFixed(1) + '%';
  }

  // Animate number counting up
  function animateValue(target, duration) {
    if (target == null || isNaN(Number(target))) {
      displayValue = target;
      return;
    }
    const end = Number(target);
    const start = 0;
    const startTime = performance.now();
    function tick(now) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      displayValue = start + (end - start) * eased;
      if (progress < 1) requestAnimationFrame(tick);
      else displayValue = end;
    }
    requestAnimationFrame(tick);
  }

  // Trigger animation when value changes (including geo switches)
  $: if (value != null && value !== prevValue) {
    prevValue = value;
    animateValue(value, 1200);
  }

  $: isPositive = change != null && change > 0;
  $: isNegative = change != null && change < 0;
  $: arrowChar = isPositive ? '\u25B2' : isNegative ? '\u25BC' : '';
  $: changeColor = (() => {
    if (change == null || change === 0) return 'var(--text-muted)';
    if (higherIs === 'better') return isPositive ? 'var(--positive)' : 'var(--negative)';
    if (higherIs === 'worse') return isPositive ? 'var(--negative)' : 'var(--positive)';
    return 'var(--text-secondary)';
  })();

  function drawSparkline() {
    if (!canvasEl || !sparklineData || sparklineData.length < 2) return;
    const ctx = canvasEl.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    canvasEl.width = 72 * dpr;
    canvasEl.height = 32 * dpr;
    canvasEl.style.width = '72px';
    canvasEl.style.height = '32px';
    ctx.scale(dpr, dpr);

    const vals = sparklineData.filter(v => v != null);
    if (vals.length < 2) return;

    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const range = max - min || 1;
    const padding = 2;
    const plotW = 72 - padding * 2;
    const plotH = 32 - padding * 2;

    ctx.clearRect(0, 0, 72, 32);

    // Build points array
    const points = [];
    let pointIdx = 0;
    for (let i = 0; i < sparklineData.length; i++) {
      if (sparklineData[i] == null) continue;
      const x = padding + (pointIdx / (vals.length - 1)) * plotW;
      const y = padding + plotH - ((sparklineData[i] - min) / range) * plotH;
      points.push({ x, y });
      pointIdx++;
    }

    // Gradient fill under line
    const gradient = ctx.createLinearGradient(0, 0, 0, 32);
    gradient.addColorStop(0, 'rgba(14, 120, 190, 0.12)');
    gradient.addColorStop(1, 'rgba(14, 120, 190, 0.01)');

    ctx.beginPath();
    points.forEach((p, i) => {
      if (i === 0) ctx.moveTo(p.x, p.y);
      else ctx.lineTo(p.x, p.y);
    });
    ctx.lineTo(padding + plotW, padding + plotH);
    ctx.lineTo(padding, padding + plotH);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Draw line with rounded joins
    ctx.beginPath();
    points.forEach((p, i) => {
      if (i === 0) ctx.moveTo(p.x, p.y);
      else ctx.lineTo(p.x, p.y);
    });
    ctx.strokeStyle = '#0E78BE';
    ctx.lineWidth = 1.5;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.stroke();

    // End dot
    if (points.length > 0) {
      const last = points[points.length - 1];
      ctx.beginPath();
      ctx.arc(last.x, last.y, 2.5, 0, Math.PI * 2);
      ctx.fillStyle = '#0E78BE';
      ctx.fill();
      // Glow ring
      ctx.beginPath();
      ctx.arc(last.x, last.y, 4.5, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(14, 120, 190, 0.2)';
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  }

  let prevSparklineJSON = '';
  function drawSparklineIfChanged() {
    const json = JSON.stringify(sparklineData);
    if (json !== prevSparklineJSON) {
      prevSparklineJSON = json;
      drawSparkline();
    }
  }

  onMount(() => drawSparkline());
  afterUpdate(() => drawSparklineIfChanged());
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="kpi-card"
  class:clickable={!!onClick}
  style="animation-delay: {0.08 + index * 0.07}s"
  on:click={onClick}
>
  <div class="kpi-top">
    <div class="kpi-label">{label}</div>
    {#if sparklineData && sparklineData.filter(v => v != null).length >= 2}
      <canvas bind:this={canvasEl} class="sparkline" width="72" height="32"></canvas>
    {/if}
  </div>
  <div class="kpi-value">{formatValue(displayValue ?? value, fmt)}</div>
  <div class="kpi-change" style="color: {changeColor}">
    {#if arrowChar}
      <span class="arrow" class:up={isPositive} class:down={isNegative}>{arrowChar}</span>
    {/if}
    <span>{formatChange(change)}</span>
    {#if change != null}
      <span class="yoy-label">YoY</span>
    {/if}
  </div>
</div>

<style>
  .kpi-card {
    background: var(--bg-card);
    border: 1px solid var(--border-light);
    border-radius: var(--radius-md);
    padding: 1.1rem 1.15rem 0.9rem;
    box-shadow: var(--shadow-card);
    transition: box-shadow 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94),
                transform 0.3s cubic-bezier(0.25, 0.46, 0.45, 0.94),
                border-color 0.3s ease;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    min-width: 0;
    position: relative;
    overflow: hidden;
    opacity: 0;
    animation: fadeInUp 0.5s ease forwards;
  }

  /* Top accent — gradient line */
  .kpi-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--accent-primary) 0%, var(--color-southern-sky) 100%);
  }

  .kpi-card:hover {
    box-shadow: 0 8px 24px rgba(21,18,62,0.1), 0 2px 8px rgba(14,120,190,0.06);
    transform: translateY(-4px);
    border-color: var(--border-medium);
  }

  .kpi-card.clickable { cursor: pointer; }

  .kpi-top {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .kpi-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted);
    line-height: 1.25;
    font-weight: 600;
    font-family: var(--font-body);
  }

  .sparkline { flex-shrink: 0; }

  .kpi-value {
    font-size: 1.45rem;
    font-weight: 800;
    color: var(--text-primary);
    line-height: 1.2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    letter-spacing: -0.02em;
    font-family: var(--font-primary);
    font-variant-numeric: tabular-nums;
  }

  .kpi-change {
    font-size: 0.73rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 0.2rem;
    margin-top: 0.15rem;
  }

  .arrow {
    font-size: 0.5rem;
    display: inline-flex;
  }

  .arrow.up {
    animation: slideUp 0.4s ease 0.8s both;
  }

  .arrow.down {
    animation: slideDown 0.4s ease 0.8s both;
  }

  @keyframes slideUp {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  @keyframes slideDown {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .yoy-label {
    font-size: 0.6rem;
    font-weight: 400;
    opacity: 0.55;
    margin-left: 0.15rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  @media (max-width: 640px) {
    .kpi-value { font-size: 1.15rem; }
    .kpi-label { font-size: 0.62rem; }
    .kpi-card { padding: 0.85rem 0.9rem 0.7rem; }
  }
</style>
