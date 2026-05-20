<script>
  import { login } from './auth.js';
</script>

<div class="login-bg">
  <!-- Animated background grid -->
  <div class="grid" aria-hidden="true">
    {#each Array(64) as _, i}
      <div class="cell" style="animation-delay:{(i % 8) * 0.12 + Math.floor(i/8)*0.08}s"></div>
    {/each}
  </div>

  <div class="glow g1" aria-hidden="true"></div>
  <div class="glow g2" aria-hidden="true"></div>

  <div class="card">
    <!-- Logo -->
    <div class="logo-row">
      <div class="logo-mark">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path d="M4 10h5M11 5v10M15 7.5a2.5 2.5 0 010 5" stroke="white" stroke-width="2" stroke-linecap="round"/>
        </svg>
      </div>
      <span class="logo-text">Partner<span class="iq">IQ</span></span>
    </div>

    <h1 class="headline">Sign in to your chamber</h1>
    <p class="sub">Access your region's live economic intelligence platform.</p>

    <button class="sign-in-btn" on:click={login}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4"/>
        <polyline points="10 17 15 12 10 7"/>
        <line x1="15" y1="12" x2="3" y2="12"/>
      </svg>
      Sign In
    </button>

    <p class="footer-note">
      Powered by <strong>DisruptREADY</strong>
    </p>
  </div>
</div>

<style>
  .login-bg {
    min-height: 100vh;
    background: linear-gradient(160deg, var(--color-riviere) 0%, #0c1028 60%, #0c1a3a 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
  }

  /* animated grid */
  .grid {
    position: absolute;
    inset: 0;
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    grid-template-rows: repeat(8, 1fr);
    pointer-events: none;
  }
  .cell {
    border: 1px solid rgba(93,167,220,0.04);
    opacity: 0;
    animation: cellIn 0.9s ease forwards;
  }
  @keyframes cellIn {
    to { opacity: 1; }
  }

  .glow {
    position: absolute;
    border-radius: 50%;
    filter: blur(90px);
    pointer-events: none;
  }
  .g1 {
    top: -20%; right: -10%;
    width: 55%; height: 120%;
    background: radial-gradient(ellipse, rgba(14,120,190,0.18) 0%, transparent 65%);
    animation: float 9s ease-in-out infinite;
  }
  .g2 {
    bottom: -30%; left: -8%;
    width: 45%; height: 100%;
    background: radial-gradient(ellipse, rgba(106,58,132,0.12) 0%, transparent 65%);
    animation: float 11s ease-in-out infinite reverse;
  }
  @keyframes float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-20px); }
  }

  /* Card */
  .card {
    position: relative;
    z-index: 10;
    background: rgba(255,255,255,0.97);
    border-radius: 20px;
    padding: 48px 44px 36px;
    width: 100%;
    max-width: 400px;
    text-align: center;
    box-shadow: 0 24px 64px rgba(21,18,62,0.28), 0 4px 16px rgba(0,0,0,0.12);
    animation: cardIn 0.6s cubic-bezier(0.22, 1, 0.36, 1) forwards;
    opacity: 0;
    transform: translateY(20px);
  }
  @keyframes cardIn {
    to { opacity: 1; transform: translateY(0); }
  }

  .logo-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    margin-bottom: 28px;
  }
  .logo-mark {
    width: 38px;
    height: 38px;
    border-radius: 9px;
    background: linear-gradient(135deg, var(--color-horizon), var(--color-southern-sky));
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .logo-text {
    font-family: var(--font-primary);
    font-size: 22px;
    font-weight: bold;
    color: var(--color-riviere);
    letter-spacing: 0.2px;
  }
  .iq { color: var(--color-horizon); }

  .headline {
    font-family: var(--font-primary);
    font-size: 20px;
    font-weight: bold;
    color: var(--text-primary);
    margin: 0 0 8px;
    letter-spacing: -0.2px;
  }

  .sub {
    font-size: 14px;
    color: var(--text-muted);
    line-height: 1.55;
    margin: 0 0 28px;
  }

  .sign-in-btn {
    width: 100%;
    padding: 13px 20px;
    background: linear-gradient(135deg, var(--color-riviere), var(--color-horizon));
    color: white;
    border: none;
    border-radius: 10px;
    font-size: 15px;
    font-weight: 600;
    font-family: var(--font-body);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: all 0.2s;
    letter-spacing: 0.2px;
  }
  .sign-in-btn:hover {
    background: linear-gradient(135deg, var(--color-horizon), var(--color-southern-sky));
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(14,120,190,0.3);
  }
  .sign-in-btn:active { transform: translateY(0); }

  .footer-note {
    margin-top: 24px;
    font-size: 12px;
    color: var(--text-muted);
  }
  .footer-note strong { color: var(--text-secondary); }

  @media (max-width: 480px) {
    .card { margin: 16px; padding: 36px 24px 28px; }
  }
</style>
