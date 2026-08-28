# -*- coding: utf-8 -*-
# HTML dashboard admin — costante HTML

# ─── HTML ───────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Robot Trader 2026</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0F172A;color:#e0e0e0;min-height:100vh}

/* TOPBAR */
.topbar{background:#2C5282;border-bottom:3px solid #F6AD55;padding:.9rem 2rem;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100;backdrop-filter:blur(10px)}
.brand{display:flex;align-items:center;gap:.75rem}
.brand-logo{height:36px;width:auto;border-radius:8px;display:block;flex-shrink:0}
.brand-title{color:#F6AD55;font-size:1.15rem;font-weight:700;letter-spacing:.3px}
.brand-sub{font-size:.72rem;opacity:.45;margin-top:.1rem}
.topbar-right{display:flex;align-items:center;gap:1rem}
.clock{font-size:.8rem;opacity:.55;font-variant-numeric:tabular-nums}

/* CONTAINER */
.wrap{max-width:1440px;margin:0 auto;padding:1.5rem}

/* TABS */
.tabs{display:flex;flex-wrap:wrap;background:#0F172A;border-radius:8px;overflow:hidden;border:1px solid #2C5282;margin-bottom:1.5rem}
.tab{flex:1 1 auto;min-width:7rem;padding:.7rem .5rem;text-align:center;cursor:pointer;font-weight:600;font-size:.78rem;transition:all .2s;border-right:1px solid rgba(44,82,130,.4);border-bottom:1px solid rgba(44,82,130,.2);color:rgba(255,255,255,.5);white-space:nowrap}
.tab:last-child{border-right:none}
.tab:hover{background:rgba(44,82,130,.4);color:#F6AD55}
.tab.active{background:#2C5282;color:#F6AD55}

/* PANELS */
.panel{display:none}.panel.active{display:block}

/* SECTION HEADER */
.sec-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:1.2rem;flex-wrap:wrap;gap:.6rem}
.sec-head h2{font-size:1.05rem;color:#F6AD55;font-weight:700}

/* KPI */
.kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:1rem;margin-bottom:1.5rem}
.kpi{background:rgba(44,82,130,.08);border:1px solid rgba(44,82,130,.35);border-radius:10px;padding:1.2rem;text-align:center}
.kpi-label{font-size:.72rem;opacity:.5;text-transform:uppercase;letter-spacing:.5px;margin-bottom:.4rem}
.kpi-val{font-size:2rem;font-weight:700;color:#F6AD55;line-height:1}
.kpi-sub{font-size:.7rem;opacity:.4;margin-top:.35rem}

/* BOXES */
.box{background:rgba(44,82,130,.08);border:1px solid rgba(44,82,130,.35);border-radius:10px;padding:1.2rem;margin-bottom:1rem}
.box h3{color:#F6AD55;margin-bottom:.8rem;font-size:.95rem;font-weight:700}

/* TABLES */
.tbl-wrap{overflow-x:auto;border:1px solid rgba(44,82,130,.4);border-radius:8px;background:rgba(0,0,0,.2)}
table{width:100%;border-collapse:collapse;font-size:.83rem}
th{padding:.7rem .6rem;text-align:left;color:#F6AD55;font-weight:600;background:#2C5282;border-bottom:2px solid #F6AD55;white-space:nowrap}
th.sortable{cursor:pointer;user-select:none;transition:background .15s}
th.sortable:hover{background:#3a6899}
th.sorted-asc::after{content:' ▲';font-size:.7rem;color:#68D391}
th.sorted-desc::after{content:' ▼';font-size:.7rem;color:#FC8181}
th.sortable[draggable]{cursor:grab}
th.col-drag-over{border-left:3px solid #F6AD55!important;background:#2C5282}
td{padding:.52rem .6rem;border-bottom:1px solid rgba(255,255,255,.04)}
tr:hover td{background:rgba(246,173,85,.03)}
.ticker{color:#F6AD55;font-weight:700;font-family:'SF Mono',Consolas,monospace;text-decoration:none}
a.ticker:hover{text-decoration:underline;color:#ffc97a}
.neg{color:#ef4444}

/* BUTTONS */
.btn{padding:.45rem 1rem;border-radius:6px;cursor:pointer;font-weight:600;font-size:.82rem;border:1px solid;transition:all .15s}
.btn-or{background:rgba(246,173,85,.12);border-color:rgba(246,173,85,.45);color:#F6AD55}
.btn-or:hover{background:rgba(246,173,85,.25)}
.btn-gr{background:rgba(34,197,94,.12);border-color:rgba(34,197,94,.45);color:#22c55e}
.btn-gr:hover{background:rgba(34,197,94,.25)}
.btn-re{background:rgba(239,68,68,.12);border-color:rgba(239,68,68,.45);color:#ef4444}
.btn-re:hover{background:rgba(239,68,68,.25)}
.btn:disabled{opacity:.4;cursor:not-allowed}

/* BADGES */
.bdg{display:inline-block;padding:.15rem .5rem;border-radius:4px;font-size:.7rem;font-weight:700;letter-spacing:.5px}
.bdg-basic{background:rgba(156,163,175,.12);color:#9ca3af;border:1px solid rgba(156,163,175,.25)}
.bdg-pro{background:rgba(245,158,11,.12);color:#f59e0b;border:1px solid rgba(245,158,11,.25)}
.bdg-value{background:rgba(99,102,241,.12);color:#818cf8;border:1px solid rgba(99,102,241,.25)}

/* RUN STATUS */
.rs{display:inline-block;padding:.18rem .55rem;border-radius:4px;font-size:.7rem;font-weight:600}
.rs-running{background:rgba(246,173,85,.2);color:#F6AD55;animation:pulse 1.5s infinite}
.rs-completato{background:rgba(34,197,94,.2);color:#22c55e}
.rs-errore,.rs-timeout{background:rgba(239,68,68,.2);color:#ef4444}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
@keyframes pwdPulse{0%,100%{box-shadow:0 0 0 0 rgba(246,173,85,.4)}50%{box-shadow:0 0 0 12px rgba(246,173,85,0)}}

/* MSG */
.msg{padding:.5rem .9rem;border-radius:6px;font-size:.82rem;display:none}
.msg-ok{background:rgba(34,197,94,.12);border:1px solid rgba(34,197,94,.3);color:#22c55e;display:block}
.msg-err{background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.3);color:#ef4444;display:block}

/* ═══════════════════════════════════════
   SERVIZI GRID
═══════════════════════════════════════ */
.sv-matrix{display:grid;grid-template-columns:100px 1fr 1fr 1fr;gap:.8rem;align-items:start}
.sv-tier-head{text-align:center;padding:.65rem;border-radius:8px;font-weight:700;font-size:.88rem;letter-spacing:.8px}
.sv-tier-head.basic{background:rgba(156,163,175,.1);color:#9ca3af;border:1px solid rgba(156,163,175,.2)}
.sv-tier-head.pro{background:rgba(245,158,11,.1);color:#f59e0b;border:1px solid rgba(245,158,11,.2)}
.sv-tier-head.value{background:rgba(99,102,241,.1);color:#818cf8;border:1px solid rgba(99,102,241,.2)}
.sv-asset-lbl{display:flex;align-items:center;justify-content:flex-end;padding-right:.5rem;font-weight:700;font-size:.84rem;color:#F6AD55;min-height:auto}
.sv-extra{margin-top:.8rem;border-top:1px solid rgba(255,255,255,.06);padding-top:.7rem}
.sv-lbl{display:block;font-size:.7rem;color:rgba(255,255,255,.4);text-transform:uppercase;letter-spacing:.5px;margin-bottom:.3rem}
.sv-textarea{width:100%;background:rgba(0,0,0,.3);border:1px solid rgba(255,255,255,.1);border-radius:6px;color:rgba(255,255,255,.85);font-size:.75rem;padding:.45rem .55rem;resize:vertical;font-family:inherit;line-height:1.5;box-sizing:border-box}
.sv-input{width:100%;background:rgba(0,0,0,.3);border:1px solid rgba(255,255,255,.1);border-radius:6px;color:rgba(255,255,255,.85);font-size:.75rem;padding:.38rem .55rem;box-sizing:border-box}
.sv-textarea:focus,.sv-input:focus{outline:none;border-color:rgba(246,173,85,.45)}
.sv-card{background:rgba(0,0,0,.25);border:1px solid rgba(255,255,255,.07);border-radius:10px;padding:1rem;transition:border-color .2s}
.sv-card:hover{border-color:rgba(246,173,85,.2)}
.sv-card.t-basic{border-top:3px solid #9ca3af}
.sv-card.t-pro{border-top:3px solid #f59e0b}
.sv-card.t-value{border-top:3px solid #818cf8}
.price-row{display:flex;align-items:center;gap:.3rem;margin-bottom:.75rem}
.price-eur{font-size:.9rem;opacity:.55}
.price-inp{background:rgba(0,0,0,.35);border:1px solid rgba(246,173,85,.25);color:#F6AD55;font-size:1.5rem;font-weight:700;width:72px;padding:.2rem .3rem;border-radius:5px;text-align:center}
.price-inp:focus{outline:none;border-color:#F6AD55}
.price-mo{font-size:.73rem;opacity:.45}
.status-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:.75rem}
.status-sel{background:rgba(0,0,0,.3);border:1px solid rgba(255,255,255,.1);color:#e0e0e0;padding:.22rem .5rem;border-radius:4px;font-size:.73rem;cursor:pointer}
.param-rows{border-top:1px solid rgba(255,255,255,.06);padding-top:.6rem}
.param-row{display:flex;justify-content:space-between;align-items:center;padding:.28rem 0;border-bottom:1px solid rgba(255,255,255,.04);font-size:.76rem}
.param-row:last-child{border-bottom:none}
.param-lbl{opacity:.6}
.param-inp{background:rgba(0,0,0,.3);border:1px solid rgba(255,255,255,.1);color:#e0e0e0;width:72px;padding:.22rem .4rem;border-radius:4px;text-align:right;font-size:.76rem}
.param-inp:focus{outline:none;border-color:#F6AD55}

/* ═══════════════════════════════════════
   PARAMETRI COMPARISON TABLE
═══════════════════════════════════════ */
.pm-section{margin-bottom:1.2rem}
.pm-section h3{color:#F6AD55;margin-bottom:.7rem;font-size:.97rem;font-weight:700}
.pm-table{width:100%;border-collapse:collapse}
.pm-table th{padding:.65rem 1rem;font-weight:700;font-size:.82rem}
.pm-table th:first-child{text-align:left;color:rgba(255,255,255,.5);font-weight:500}
.pm-table th.th-basic{text-align:center;color:#9ca3af;background:rgba(156,163,175,.07)}
.pm-table th.th-pro{text-align:center;color:#f59e0b;background:rgba(245,158,11,.07)}
.pm-table th.th-value{text-align:center;color:#818cf8;background:rgba(99,102,241,.07)}
.pm-table td{padding:.48rem 1rem;border-bottom:1px solid rgba(255,255,255,.05);font-size:.83rem}
.pm-table td:first-child{opacity:.75}
.pm-table td.tc{text-align:center}
.pm-table tr:hover td{background:rgba(246,173,85,.03)}
.pm-inp{background:rgba(0,0,0,.3);border:1px solid rgba(255,255,255,.1);color:#e0e0e0;width:95px;padding:.3rem .5rem;border-radius:4px;text-align:center;font-size:.83rem}
.pm-inp:focus{outline:none}
.pm-inp.basic:focus{border-color:#9ca3af}
.pm-inp.pro:focus{border-color:#f59e0b}
.pm-inp.value:focus{border-color:#818cf8}

/* LOG */
.log-term{background:#07120a;border:1px solid rgba(34,197,94,.18);border-radius:6px;padding:.8rem;font-family:'SF Mono',Consolas,monospace;font-size:.75rem;color:#88d4a0;height:290px;overflow-y:auto;line-height:1.55;white-space:pre-wrap;word-break:break-all}

.footer{text-align:center;padding:2rem;opacity:.3;font-size:.76rem}

@media(max-width:960px){.sv-matrix{grid-template-columns:70px 1fr 1fr 1fr}}
@media(max-width:700px){.sv-matrix{grid-template-columns:1fr};.sv-asset-lbl{min-height:auto;justify-content:flex-start;padding:.5rem 0};.tabs{flex-wrap:wrap};.tab{width:33.33%}}

/* ── SCREENER TABLES (azioni/etf/fondi) — colonne multiple, scroll orizzontale ── */
#azioni table,#etf table,#fondi table{width:auto;min-width:100%}
#azioni td,#etf td,#fondi td{white-space:nowrap;min-width:60px}
#azioni td:nth-child(2),#etf td:nth-child(2),#fondi td:nth-child(2){min-width:140px;max-width:220px;overflow:hidden;text-overflow:ellipsis}

/* ── DATABASE ── */
.db-tabs{display:flex;gap:.4rem;margin-bottom:1rem;flex-wrap:wrap}
.db-tab{padding:.45rem 1.1rem;border-radius:6px;border:1px solid rgba(44,82,130,.5);background:transparent;color:rgba(255,255,255,.5);cursor:pointer;font-size:.82rem;font-weight:600;transition:all .18s}
.db-tab:hover{border-color:#F6AD55;color:#F6AD55}
.db-tab.active{background:#2C5282;border-color:#2C5282;color:#F6AD55}
.sc-asset-tab,.sc-plan-tab{padding:.35rem .9rem;border-radius:6px;border:1px solid rgba(44,82,130,.5);background:transparent;color:rgba(255,255,255,.5);cursor:pointer;font-size:.8rem;font-weight:600;transition:all .18s}
.sc-asset-tab:hover,.sc-plan-tab:hover{border-color:#F6AD55;color:#F6AD55}
.sc-asset-tab.active{background:#2C5282;border-color:#2C5282;color:#F6AD55}
.sc-plan-tab.active{background:#276749;border-color:#276749;color:#68D391}
.db-panel{display:none}.db-panel.active{display:block}
.db-search{width:100%;box-sizing:border-box;padding:.55rem .9rem;background:rgba(0,0,0,.3);border:1px solid rgba(44,82,130,.5);border-radius:6px;color:#e2e8f0;font-size:.88rem;margin-bottom:.6rem;outline:none}
.db-search:focus{border-color:#F6AD55}
.db-count{font-size:.78rem;color:#64748b;margin-bottom:.8rem}
.db-group{display:inline-block;padding:.15rem .55rem;background:rgba(44,82,130,.25);border-radius:4px;font-size:.75rem;color:#90cdf4}
.btn-yf{display:inline-block;padding:.25rem .65rem;background:#F6AD55;color:#1a202c;border-radius:5px;text-decoration:none;font-weight:700;font-size:.8rem;transition:opacity .15s}
.btn-yf:hover{opacity:.8}
.db-ticker{font-family:'SF Mono',Consolas,monospace;font-size:.83rem;font-weight:600;color:#e2e8f0}
/* SETTORI */
.sett-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:.8rem;margin-bottom:1.6rem}
.sett-card{border-radius:10px;padding:.9rem 1rem;cursor:pointer;transition:transform .15s,box-shadow .15s;border:1px solid rgba(255,255,255,.1)}
.sett-card:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.5)}
.sett-card-emoji{font-size:1.3rem;margin-bottom:.25rem}
.sett-card-nome{font-size:.78rem;font-weight:700;line-height:1.2;margin-bottom:.15rem}
.sett-card-ticker{font-size:.68rem;opacity:.45;margin-bottom:.5rem;font-family:monospace}
.sett-card-prezzo{font-size:.95rem;font-weight:700;margin-bottom:.5rem;font-family:monospace}
.sett-perf-row{display:flex;gap:.3rem;flex-wrap:wrap}
.sett-pill{font-size:.62rem;padding:.12rem .35rem;border-radius:3px;font-weight:700;white-space:nowrap}
.sett-section-title{font-size:.85rem;font-weight:600;opacity:.6;margin:.5rem 0 .8rem;letter-spacing:.04em}
</style>
</head>
<body>

<!-- TOPBAR -->
<div class="topbar">
  <div class="brand">
    <img class="brand-logo" src="data:image/png;base64,__FUERTE_LOGO__" alt="Fuerte Venture Capital">
    <div>
      <div class="brand-title">Robot Trader 2026</div>
      <div class="brand-sub">Fuerte Venture Capital SL</div>
    </div>
  </div>
  <div class="topbar-right">
    <span class="clock" id="clock"></span>
    <button class="btn btn-or" onclick="refreshAll()">↻ Aggiorna</button>
    <a href="/logout" class="btn btn-re" style="text-decoration:none;padding:.4rem .8rem;font-size:.78rem">⏻ Esci</a>
  </div>
</div>

<div class="wrap">
  <!-- TABS -->
  <div class="tabs">
    <div class="tab active" onclick="switchTab(this,'home')">📊 Home</div>
    <div class="tab" onclick="switchTab(this,'analytics')">📈 Analytics</div>
    <div class="tab" onclick="switchTab(this,'servizi')">💼 Servizi</div>
    <div class="tab" onclick="switchTab(this,'parametri')">⚙️ Parametri</div>
    <div class="tab" onclick="switchTab(this,'azioni')">📈 Azioni</div>
    <div class="tab" onclick="switchTab(this,'etf')">📦 ETF</div>
    <div class="tab" onclick="switchTab(this,'fondi')">🏦 Fondi</div>
    <div class="tab" onclick="switchTab(this,'settori')">🌍 Settori</div>
    <div class="tab" onclick="switchTab(this,'crm')">🎯 CRM & Marketing</div>
    <div class="tab" onclick="switchTab(this,'esecuzione')">🚀 Esecuzione</div>
    <div class="tab" onclick="switchTab(this,'database')">🗃️ Database</div>
    <div class="tab" onclick="switchTab(this,'kb')">📚 KB</div>
    <div class="tab" onclick="switchTab(this,'onboarding')">📋 Onboarding</div>
    <div class="tab" onclick="switchTab(this,'fatture')">&#x1F4C4; Fatture</div>
    <div class="tab" onclick="switchTab(this,'emaillog')">&#x1F4E7; Email Log</div>
    <div class="tab" onclick="switchTab(this,'tickerfreq')">&#x1F4CA; Ticker Freq.</div>
    <div class="tab" onclick="switchTab(this,'socialenrich')">&#x1F517; Social Enrich</div>
  </div>

  <!-- ══════════ HOME ══════════ -->
  <div id="home" class="panel active">
    <div class="kpi-row" id="kpi-row">
      <div class="kpi"><div class="kpi-label">📈 Azioni</div><div class="kpi-val">—</div><div class="kpi-sub">Caricamento...</div></div>
      <div class="kpi"><div class="kpi-label">📦 ETF</div><div class="kpi-val">—</div><div class="kpi-sub">Caricamento...</div></div>
      <div class="kpi"><div class="kpi-label">🏦 Fondi</div><div class="kpi-val">—</div><div class="kpi-sub">Caricamento...</div></div>
      <div class="kpi"><div class="kpi-label">💰 Revenue Potenziale</div><div class="kpi-val">—</div><div class="kpi-sub">9 servizi / mese</div></div>
    </div>
    <div class="box">
      <h3>🌍 Mercati Analizzati</h3>
      <div id="mercati-wrap" class="tbl-wrap"><table><tbody><tr><td style="padding:1.5rem;opacity:.5;text-align:center">Caricamento...</td></tr></tbody></table></div>
    </div>
    <div class="box" style="font-size:.85rem;line-height:1.7">
      <strong>⏰ Scheduler:</strong> 23:00 — Lun/Ven — Windows Task Scheduler &nbsp;|&nbsp;
      <strong>📧 Email:</strong> <span id="stat-dest">—</span>
    </div>
    <div class="box" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem">
      <div>
        <div style="font-weight:700;margin-bottom:.25rem">🤖 VERA — Value &amp; Research Assistant</div>
        <div style="font-size:.82rem;color:#aaa" id="kb-status">Caricamento...</div>
      </div>
      <button class="btn btn-gr" onclick="reloadKB()" id="btn-reload-kb">↺ Ricarica KB</button>
    </div>
  </div>

  <!-- ══════════ ANALYTICS ══════════ -->
  <div id="analytics" class="panel">
    <div class="sec-head">
      <h2 style="color:#F6AD55">📈 Business Analytics</h2>
      <button class="btn" onclick="renderAnalytics()" style="font-size:.78rem">↺ Aggiorna</button>
    </div>
    <div id="analytics-content">
      <div style="opacity:.5;padding:2rem;text-align:center">Caricamento...</div>
    </div>
  </div>

  <!-- ══════════ SERVIZI ══════════ -->
  <div id="servizi" class="panel">
    <div class="sec-head">
      <h2>💼 Catalogo Servizi</h2>
      <div style="display:flex;gap:.6rem;align-items:center">
        <span id="sv-msg" class="msg"></span>
        <button class="btn btn-gr" onclick="saveServizi()">💾 Salva Servizi</button>
      </div>
    </div>
    <div class="sv-matrix">
      <div></div>
      <div class="sv-tier-head basic">BASIC</div>
      <div class="sv-tier-head pro">PRO</div>
      <div class="sv-tier-head value">VALUE</div>

      <div class="sv-asset-lbl">📈 AZIONI</div>
      <div id="sv-azioni-basic"></div>
      <div id="sv-azioni-pro"></div>
      <div id="sv-azioni-value"></div>

      <div class="sv-asset-lbl">📦 ETF</div>
      <div id="sv-etf-basic"></div>
      <div id="sv-etf-pro"></div>
      <div id="sv-etf-value"></div>

      <div class="sv-asset-lbl">🏦 FONDI</div>
      <div id="sv-fondi-basic"></div>
      <div id="sv-fondi-pro"></div>
      <div id="sv-fondi-value"></div>
    </div>
  </div>

  <!-- ══════════ PARAMETRI ══════════ -->
  <div id="parametri" class="panel">

    <!-- ── SEZIONE 1: Parametri Screener (parametri.json) ── -->
    <div class="box" style="margin-bottom:1.2rem">
      <div class="sec-head" style="margin-bottom:.8rem">
        <h2>🎛️ Parametri Screener (Globali)</h2>
        <div style="display:flex;gap:.6rem;align-items:center;flex-wrap:wrap">
          <span id="sp-msg" class="msg"></span>
          <button class="btn btn-re" onclick="loadScreenerParams()">↺ Ricarica</button>
          <button class="btn btn-gr" onclick="saveScreenerParams()">💾 Salva Parametri</button>
        </div>
      </div>
      <div id="scr-params-content" style="opacity:.5;font-size:.85rem">Caricamento...</div>
    </div>

    <!-- ── SEZIONE 2: Parametri Tier Servizi (servizi_config.json) ── -->
    <div class="box">
      <div class="sec-head" style="margin-bottom:.8rem">
        <h2>⚙️ Parametri per Tier (Servizi)</h2>
        <div style="display:flex;gap:.6rem;align-items:center;flex-wrap:wrap">
          <span id="pm-msg" class="msg"></span>
          <button class="btn btn-re" onclick="loadServizi()">↺ Annulla</button>
          <button class="btn btn-gr" onclick="saveParametri()">💾 Salva Tier</button>
        </div>
      </div>
      <div id="pm-container"></div>
    </div>

    <!-- ── SEZIONE 3: Pesi Score Bontà ── -->
    <div class="box" style="margin-top:1.2rem">
      <div class="sec-head" style="margin-bottom:.8rem">
        <h2>🎯 Pesi Score Bontà</h2>
        <div style="display:flex;gap:.6rem;align-items:center;flex-wrap:wrap">
          <span id="sc-msg" class="msg"></span>
          <button class="btn btn-re" onclick="resetScoringDefaults()">↺ Reset Default</button>
          <button class="btn btn-gr" onclick="saveScoring()">💾 Salva Pesi</button>
        </div>
      </div>
      <p style="font-size:.8rem;opacity:.55;margin-bottom:1rem">
        Score 0–100: percentile della metrica tra tutti i titoli selezionati per quel piano. Alto = migliore della lista. VALUE usa i pesi PRO.
      </p>
      <!-- Asset tabs -->
      <div style="display:flex;gap:.4rem;margin-bottom:.6rem">
        <button class="sc-asset-tab active" onclick="switchScAsset(this,'azioni')">📈 Azioni</button>
        <button class="sc-asset-tab" onclick="switchScAsset(this,'etf')">📦 ETF</button>
        <button class="sc-asset-tab" onclick="switchScAsset(this,'fondi')">🏦 Fondi</button>
      </div>
      <!-- Plan tabs -->
      <div style="display:flex;gap:.4rem;margin-bottom:1rem">
        <button class="sc-plan-tab active" onclick="switchScPlan(this,'BASIC')">BASIC</button>
        <button class="sc-plan-tab" onclick="switchScPlan(this,'PRO')">PRO</button>
        <button class="sc-plan-tab" onclick="switchScPlan(this,'VALUE')">VALUE</button>
      </div>
      <!-- Weight rows rendered by JS -->
      <div id="sc-metrics"></div>
      <div id="sc-total" style="margin-top:.8rem;font-size:.85rem;font-weight:600;min-height:1.2rem"></div>
    </div>
  </div>

  <!-- ══════════ AZIONI ══════════ -->
  <div id="azioni" class="panel">
    <div class="box" id="azioni-info" style="font-size:.85rem">—</div>
    <div class="tbl-wrap"><table><thead id="azioni-head"></thead><tbody id="azioni-body"><tr><td style="padding:2rem;opacity:.5;text-align:center">Clicca la tab per caricare</td></tr></tbody></table></div>
  </div>

  <!-- ══════════ ETF ══════════ -->
  <div id="etf" class="panel">
    <div class="box" id="etf-info" style="font-size:.85rem">—</div>
    <div class="tbl-wrap"><table><thead id="etf-head"></thead><tbody id="etf-body"><tr><td style="padding:2rem;opacity:.5;text-align:center">Clicca la tab per caricare</td></tr></tbody></table></div>
  </div>

  <!-- ══════════ FONDI ══════════ -->
  <div id="fondi" class="panel">
    <div class="box" id="fondi-info" style="font-size:.85rem">—</div>
    <div class="tbl-wrap"><table><thead id="fondi-head"></thead><tbody id="fondi-body"><tr><td style="padding:2rem;opacity:.5;text-align:center">Clicca la tab per caricare</td></tr></tbody></table></div>
  </div>

  <!-- ══════════ SETTORI ══════════ -->
  <div id="settori" class="panel">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;flex-wrap:wrap;gap:.6rem">
      <h2 style="color:#F6AD55;font-size:1.1rem;font-weight:700">🌍 Analisi Settoriale &amp; Mercati</h2>
      <div style="display:flex;align-items:center;gap:.8rem">
        <span id="sett-ts" style="font-size:.72rem;opacity:.45">—</span>
        <button onclick="loadSettori(true)" style="background:#2C5282;border:none;color:#F6AD55;padding:.3rem .8rem;border-radius:6px;cursor:pointer;font-size:.78rem;font-weight:600">🔄 Aggiorna</button>
      </div>
    </div>
    <!-- Guida lettura dati -->
    <div style="margin-bottom:1.2rem">
      <button onclick="var g=document.getElementById('sett-guide');g.style.display=g.style.display==='none'?'block':'none'" style="background:rgba(44,82,130,.25);border:1px solid rgba(44,82,130,.5);color:#90cdf4;padding:.3rem .85rem;border-radius:6px;cursor:pointer;font-size:.76rem">📖 Come leggere questi dati ▸</button>
      <div id="sett-guide" style="display:none;background:rgba(15,23,42,.85);border:1px solid rgba(44,82,130,.35);border-radius:8px;padding:1.2rem 1.4rem;margin-top:.7rem;font-size:.78rem;line-height:1.75">
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1.2rem 2rem">
          <div><strong style="color:#F6AD55">📊 Periodi temporali</strong><br><span style="opacity:.75">
            <strong>1G</strong> — variazione giornaliera (alta volatilità, poco predittiva)<br>
            <strong>1S</strong> — trend settimanale → utile per timing ingresso/uscita<br>
            <strong>1M</strong> — momentum mensile → <em>il più importante per decisioni tattiche</em><br>
            <strong>3M</strong> — tendenza trimestrale → conferma la direzione<br>
            <strong>1A</strong> — trend strutturale → forza secolare del settore/mercato
          </span></div>
          <div><strong style="color:#F6AD55">🎨 Scala colori card settori</strong><br><span style="opacity:.75">
            <span style="color:#86efac">■</span> Verde scuro → +8%+ mensile (forte momentum)<br>
            <span style="color:#6ee7b7">■</span> Verde medio → tra +4% e +8% mensile<br>
            <span style="color:#a7f3d0">■</span> Verde chiaro → tra 0% e +4% mensile<br>
            <span style="color:#fca5a5">■</span> Rosso chiaro → tra 0% e -4% mensile<br>
            <span style="color:#f87171">■</span> Rosso scuro → oltre -4% mensile (trend negativo)
          </span></div>
          <div><strong style="color:#F6AD55">🚦 Semaforo nazioni</strong><br><span style="opacity:.75">
            🟢 &gt; +2% mensile → mercato in fase rialzista<br>
            🟡 tra −2% e +2% → mercato laterale / neutro<br>
            🔴 &lt; −2% mensile → mercato in fase ribassista<br><br>
            <em>Combina sempre 1M + 3M per evitare falsi segnali</em>
          </span></div>
          <div><strong style="color:#F6AD55">📌 Come usare i dati</strong><br><span style="opacity:.75">
            <strong>Sovrappeso:</strong> 1M, 3M e 1A tutti positivi → momentum confermato<br>
            <strong>Ingresso tattico:</strong> 1G negativo ma 1M e 1A positivi → pullback su trend<br>
            <strong>Attenzione:</strong> 1A positivo, 3M e 1M negativi → possibile inversione<br>
            <strong>Evitare:</strong> 1M, 3M e 1A tutti negativi → trend negativo confermato<br>
            Clicca una card → vedi descrizione settore + ETF/Fondi consigliati
          </span></div>
        </div>
      </div>
    </div>
    <div class="db-tabs" style="margin-bottom:1.4rem">
      <button class="db-tab sett-subtab active" onclick="switchSettTab(this,'sett-gics')">📊 Settori GICS</button>
      <button class="db-tab sett-subtab" onclick="switchSettTab(this,'sett-nazioni')">🌐 Nazioni &amp; Mercati</button>
    </div>
    <div id="sett-loading" style="display:none;text-align:center;padding:3rem;opacity:.6">
      <div style="font-size:2rem;margin-bottom:.6rem">⏳</div>
      <div>Caricamento dati da Yahoo Finance...</div>
      <div style="font-size:.75rem;margin-top:.4rem;opacity:.7">Primo caricamento ~10 secondi</div>
    </div>
    <div id="sett-gics" class="sett-subpanel">
      <div class="sett-section-title">🇺🇸 USA — SPDR Sector ETFs (11 settori GICS)</div>
      <div id="sett-us-grid" class="sett-grid"></div>
      <div class="sett-section-title">🇪🇺 Europa — iShares STOXX Europe 600 Sector ETFs</div>
      <div id="sett-eu-grid" class="sett-grid"></div>
    </div>
    <div id="sett-nazioni" class="sett-subpanel" style="display:none">
      <div id="sett-naz-wrap"></div>
    </div>
  </div>

  <!-- Modal drill-down titoli nel settore -->
  <div id="sett-modal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.75);z-index:9000;overflow-y:auto">
    <div style="background:#1a1a2e;margin:3rem auto 2rem;max-width:920px;border-radius:12px;padding:1.8rem;position:relative;border:1px solid rgba(44,82,130,.5)">
      <button onclick="document.getElementById('sett-modal').style.display='none'" style="position:absolute;top:1rem;right:1rem;background:none;border:none;color:#aaa;font-size:1.5rem;cursor:pointer;line-height:1">✕</button>
      <h3 id="sett-modal-title" style="margin-bottom:.4rem;color:#F6AD55;font-size:1rem"></h3>
      <p id="sett-modal-sub" style="font-size:.75rem;opacity:.5;margin-bottom:1rem"></p>
      <div id="sett-modal-info" style="margin-bottom:1.2rem"></div>
      <div id="sett-modal-body"></div>
    </div>
  </div>

  <!-- ══════════ CRM & MARKETING ══════════ -->
  <div id="crm" class="panel">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;flex-wrap:wrap;gap:.6rem">
      <h2 style="color:#F6AD55;font-size:1.1rem;font-weight:700">🎯 CRM &amp; Marketing</h2>
      <span id="crm-msg" class="msg"></span>
    </div>

    <!-- Sotto-tab CRM -->
    <div class="db-tabs" style="margin-bottom:1.4rem">
      <button class="db-tab crm-subtab active" onclick="switchCrmTab(this,'clienti')">👥 Clienti</button>
      <button class="db-tab crm-subtab" onclick="switchCrmTab(this,'pipeline')">📊 Pipeline</button>
      <button class="db-tab crm-subtab" onclick="switchCrmTab(this,'campagne')">📧 Campagne Email</button>
      <button class="db-tab crm-subtab" onclick="switchCrmTab(this,'social')">📱 Social Media</button>
      <button class="db-tab crm-subtab" onclick="switchCrmTab(this,'prospect')">🎯 Prospect</button>
      <button class="db-tab crm-subtab" onclick="switchCrmTab(this,'calendario')">📅 Calendario</button>
      <button class="db-tab crm-subtab" onclick="switchCrmTab(this,'whatsapp')">💬 WhatsApp</button>
    </div>

    <!-- ─── Clienti ─── -->
    <div id="crm-clienti" class="crm-sub">
      <div class="sec-head">
        <h2>👥 Gestione Clienti</h2>
        <div style="display:flex;gap:.6rem;align-items:center;flex-wrap:wrap">
          <span id="cl-msg" class="msg"></span>
          <button class="btn btn-re" onclick="loadClienti()">↺ Ricarica</button>
          <button class="btn btn-gr" onclick="mostraModalAggiungi()">+ Aggiungi</button>
          <button class="btn" onclick="exportClienti()" style="border-color:rgba(246,173,85,.4);color:#F6AD55">⬇ Esporta CSV</button>
          <label class="btn" style="border-color:rgba(74,144,217,.4);color:#4A90D9;cursor:pointer;margin:0">
            ⬆ Importa CSV
            <input type="file" id="cl-import-file" accept=".csv" onchange="importClienti(this)" style="display:none">
          </label>
        </div>
      </div>
      <div id="cl-stats" style="display:flex;gap:.8rem;flex-wrap:wrap;margin-bottom:1rem"></div>
      <div id="cl-pwd-box" style="display:none;background:rgba(246,173,85,.08);border:2px solid #F6AD55;border-radius:10px;padding:1.2rem 1.4rem;margin-bottom:1rem;animation:pwdPulse 1s ease 2">
        <div style="font-size:.9rem;color:#F6AD55;font-weight:700;margin-bottom:.6rem">🔑 PASSWORD TEMPORANEA — Annotala ora, non verrà mostrata di nuovo!</div>
        <div style="display:flex;align-items:center;gap:.8rem;flex-wrap:wrap">
          <code id="cl-pwd-val" style="font-size:1.3rem;font-family:monospace;color:#fff;background:rgba(0,0,0,.4);padding:.4rem 1rem;border-radius:6px;letter-spacing:2px"></code>
          <button onclick="navigator.clipboard.writeText(document.getElementById('cl-pwd-val').textContent);this.textContent='Copiato ✓'" style="background:#68D391;color:#0a0f1e;border:none;border-radius:6px;padding:.4rem .9rem;font-weight:700;font-size:.82rem;cursor:pointer">Copia</button>
          <button onclick="document.getElementById('cl-pwd-box').style.display='none'" style="background:transparent;border:1px solid rgba(255,255,255,.15);color:#aaa;border-radius:6px;padding:.4rem .7rem;font-size:.78rem;cursor:pointer">✕ Chiudi</button>
        </div>
        <div style="font-size:.75rem;color:#888;margin-top:.5rem">URL accesso: <a href="__BASE_URL__/client-login" target="_blank" style="color:#68D391">__BASE_URL__/client-login</a></div>
      </div>
      <div class="tbl-wrap"><table>
        <thead><tr id="cl-head"></tr></thead>
        <tbody id="cl-body"><tr><td style="padding:2rem;opacity:.5;text-align:center">Caricamento...</td></tr></tbody>
      </table></div>
    </div>

    <!-- ─── Pipeline ─── -->
    <div id="crm-pipeline" class="crm-sub" style="display:none">
      <!-- Header Pipeline -->
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.6rem;margin-bottom:1.2rem">
        <div>
          <h3 style="margin:0;color:#F6AD55;font-size:1rem">📊 Pipeline Commerciale</h3>
          <span id="pipeline-stats-label" style="font-size:.76rem;opacity:.5">—</span>
        </div>
        <div style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap">
          <input id="pipeline-search" type="text" placeholder="Cerca nome, email…"
            oninput="pipelineSearch(this.value)"
            style="background:rgba(0,0,0,.3);border:1px solid rgba(255,255,255,.15);border-radius:7px;padding:.4rem .75rem;color:#e0e0e0;font-size:.82rem;outline:none;width:200px">
          <button class="btn btn-gr" onclick="mostraNuovoLead()">+ Nuovo Lead</button>
          <input type="file" id="apollo-file-input" accept=".csv" style="display:none" onchange="importApolloFile(this)">
          <button onclick="document.getElementById('apollo-file-input').click()" style="background:rgba(10,102,194,.15);border:1px solid rgba(10,102,194,.35);border-radius:6px;color:#60a5fa;padding:.3rem .75rem;font-size:.8rem;cursor:pointer;display:inline-flex;align-items:center;gap:.35rem"><svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zM9 17H6.5v-7H9v7zm-1.3-8a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm9.3 8h-2.5v-3.5c0-.8-.7-1.5-1.5-1.5s-1.5.7-1.5 1.5V17H9v-7h2.5v1a3 3 0 015.5 1.7V17z"/></svg> Import Apollo.io</button>
          <button class="btn btn-re" onclick="loadPipelineData()">↺</button>
          <button class="btn" onclick="exportProspect()" style="border-color:rgba(246,173,85,.4);color:#F6AD55">⬇ Esporta</button>
          <label class="btn" style="border-color:rgba(74,144,217,.4);color:#4A90D9;cursor:pointer;margin:0">
            ⬆ Importa CSV
            <input type="file" id="pipeline-import-file" accept=".csv" onchange="importProspectCSV(this)" style="display:none">
          </label>
        </div>
      </div>
      <div id="pipeline-import-result" style="display:none;background:rgba(104,211,145,.08);border:1px solid rgba(104,211,145,.3);border-radius:8px;padding:.7rem 1rem;margin-bottom:.8rem;font-size:.84rem"></div>
      <!-- Board kanban -->
      <div id="pipeline-board" style="display:flex;gap:.7rem;overflow-x:auto;padding-bottom:.8rem;min-height:400px">
        <div style="opacity:.5;padding:2rem;text-align:center;width:100%">Caricamento...</div>
      </div>
      <!-- Strip Non Interessato + Sospeso -->
      <div id="pipeline-strip" style="margin-top:1rem;display:flex;gap:.8rem;flex-wrap:wrap"></div>
      <!-- Modal Nuovo Lead -->
      <div id="modal-nuovo-lead" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1010;align-items:center;justify-content:center">
        <div style="background:#1a1f2e;border:1px solid rgba(104,211,145,.3);border-radius:14px;padding:2rem;width:100%;max-width:420px;margin:1rem">
          <h3 style="margin-bottom:1.2rem;color:#68D391">+ Nuovo Lead</h3>
          <div style="display:grid;gap:.7rem">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:.6rem">
              <div>
                <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Nome *</div>
                <input id="nl-nome" placeholder="Mario" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.5rem .75rem;color:#e0e0e0;font-size:.88rem;outline:none;box-sizing:border-box">
              </div>
              <div>
                <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Cognome</div>
                <input id="nl-cognome" placeholder="Rossi" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.5rem .75rem;color:#e0e0e0;font-size:.88rem;outline:none;box-sizing:border-box">
              </div>
            </div>
            <div>
              <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Email *</div>
              <input id="nl-email" type="email" placeholder="mario@email.com" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.5rem .75rem;color:#e0e0e0;font-size:.88rem;outline:none;box-sizing:border-box">
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:.6rem">
              <div>
                <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Fonte</div>
                <input id="nl-fonte" placeholder="LinkedIn, Web…" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.5rem .75rem;color:#e0e0e0;font-size:.88rem;outline:none;box-sizing:border-box">
              </div>
              <div>
                <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Interesse</div>
                <select id="nl-interesse" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.15);border-radius:7px;padding:.5rem .75rem;color:#e0e0e0;font-size:.88rem;outline:none">
                  <option>Tutti</option><option>Azioni</option><option>ETF</option><option>Fondi</option><option>WealthOS</option>
                </select>
              </div>
            </div>
          </div>
          <div style="display:flex;gap:.7rem;justify-content:flex-end;margin-top:1.2rem">
            <button class="btn" onclick="document.getElementById('modal-nuovo-lead').style.display='none'" style="background:rgba(255,255,255,.07)">Annulla</button>
            <button class="btn btn-gr" onclick="confermaNuovoLead()">Crea Lead</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ─── Campagne Email ─── -->
    <div id="crm-campagne" class="crm-sub" style="display:none">

      <!-- ── Calendario 4 mesi ───────────────────────────── -->
      <div class="box" style="margin-bottom:1.2rem">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.6rem;margin-bottom:1rem">
          <div>
            <h3 style="margin:0;color:#F6AD55;font-size:1rem">📧 Calendario Campagne — Sett · Ott · Nov · Dic 2026</h3>
            <span style="font-size:.76rem;opacity:.5">250 email/giorno · 30.500 email totali · 4 temi mensili</span>
          </div>
          <div style="display:flex;gap:.5rem;align-items:center">
            <select id="camp-mese-sel" onchange="loadCampagna()" style="background:#0a0f1e;border:1px solid rgba(255,255,255,.15);border-radius:7px;padding:.4rem .7rem;color:#e0e0e0;font-size:.82rem;outline:none">
              <option value="2026-09">Settembre 2026 — SALARY TRAP (IT)</option>
              <option value="2026-10">Ottobre 2026 — WEALTHOS (ES)</option>
              <option value="2026-11">Novembre 2026 — TREND MOBILIARE (EN)</option>
              <option value="2026-12">Dicembre 2026 — WEALTHOS (IT)</option>
            </select>
            <button class="btn btn-re" onclick="loadCampagna()">↺</button>
            <button class="btn" onclick="forzaInvioOggi()" style="background:#276749;color:#68D391;border:none;border-radius:6px;padding:.38rem .8rem;font-size:.8rem;font-weight:600;cursor:pointer">⚡ Forza oggi</button>
          </div>
        </div>

        <!-- KPI mese selezionato -->
        <div id="camp-kpi" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:.6rem;margin-bottom:1rem"></div>

        <!-- Tabella giornaliera -->
        <div class="tbl-wrap">
          <table>
            <thead><tr style="background:#2C5282">
              <th style="padding:.45rem .7rem;text-align:left;font-size:.76rem;white-space:nowrap">Data</th>
              <th style="padding:.45rem .7rem;text-align:center;font-size:.76rem">Sett.</th>
              <th style="padding:.45rem .7rem;text-align:left;font-size:.76rem">Variante</th>
              <th style="padding:.45rem .7rem;text-align:left;font-size:.76rem">Soggetto email</th>
              <th style="padding:.45rem .7rem;text-align:center;font-size:.76rem">Batch</th>
              <th style="padding:.45rem .7rem;text-align:center;font-size:.76rem">Stato</th>
              <th style="padding:.45rem .7rem;text-align:center;font-size:.76rem">Invia</th>
            </tr></thead>
            <tbody id="camp-tbody">
              <tr><td colspan="7" style="padding:2rem;opacity:.4;text-align:center">Caricamento...</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ── Brevo storico + azioni lancio ──────────────── -->
      <div id="campagne-content">
        <div style="opacity:.5;padding:1rem;text-align:center;font-size:.85rem">Caricamento campagne Brevo...</div>
      </div>
    </div>

    <!-- ─── Social Media ─── -->
    <div id="crm-social" class="crm-sub" style="display:none">
      <div id="social-content">
        <div style="opacity:.5;padding:1.5rem;text-align:center">Caricamento draft social...</div>
      </div>
    </div>

    <!-- ─── Prospect ─── -->
    <div id="crm-prospect" class="crm-sub" style="display:none">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.6rem;margin-bottom:1rem">
        <div>
          <h3 style="margin:0;color:#F6AD55;font-size:1rem">🎯 Prospect</h3>
          <span id="prospect-count" style="font-size:.78rem;opacity:.5">—</span>
        </div>
        <div style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap">
          <input id="prospect-search" type="text" placeholder="Cerca nome, email, fonte…"
            oninput="prospectSearch(this.value)"
            style="background:rgba(0,0,0,.3);border:1px solid rgba(255,255,255,.15);border-radius:7px;padding:.4rem .75rem;color:#e0e0e0;font-size:.82rem;outline:none;width:220px">
          <button class="btn btn-re" onclick="loadProspect()">↺ Ricarica</button>
          <button class="btn" onclick="exportProspect()" style="border-color:rgba(246,173,85,.4);color:#F6AD55">⬇ Esporta CSV</button>
        </div>
      </div>
      <div id="prospect-chips" style="margin-bottom:.8rem"></div>
      <div id="prospect-import-result" style="display:none;background:rgba(104,211,145,.08);border:1px solid rgba(104,211,145,.3);border-radius:8px;padding:.7rem 1rem;margin-bottom:.8rem;font-size:.84rem"></div>
      <div class="tbl-wrap"><table>
        <thead><tr style="background:#2C5282">
          <th style="padding:.5rem .8rem;text-align:left;font-size:.8rem">Nome</th>
          <th style="padding:.5rem .8rem;text-align:left;font-size:.8rem">Email</th>
          <th style="padding:.5rem .8rem;text-align:left;font-size:.8rem">Fonte</th>
          <th style="padding:.5rem .8rem;text-align:left;font-size:.8rem">Interesse</th>
          <th style="padding:.5rem .8rem;text-align:left;font-size:.8rem">Stato</th>
          <th style="padding:.5rem .8rem;text-align:left;font-size:.8rem">Ult. Contatto</th>
          <th style="padding:.5rem .8rem;text-align:left;font-size:.8rem">Azioni</th>
        </tr></thead>
        <tbody id="prospect-tbody"><tr><td colspan="7" style="padding:2rem;opacity:.4;text-align:center">Caricamento...</td></tr></tbody>
      </table></div>
    </div>

    <!-- Modal nota prospect -->
    <div id="modal-nota-prospect" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1010;align-items:center;justify-content:center">
      <div style="background:#1a1f2e;border:1px solid rgba(246,173,85,.3);border-radius:14px;padding:2rem;width:100%;max-width:460px;margin:1rem">
        <h3 style="margin-bottom:.3rem;color:#F6AD55">📝 Note Prospect</h3>
        <div id="modal-nota-nome" style="font-size:.82rem;color:#aaa;margin-bottom:1rem"></div>
        <textarea id="modal-nota-testo" rows="4" placeholder="Note sul contatto…"
          style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:8px;padding:.6rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none;resize:vertical;box-sizing:border-box"></textarea>
        <div style="margin-top:.7rem">
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Data ultimo contatto</div>
          <input id="modal-nota-data" type="date" style="background:rgba(0,0,0,.3);border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.4rem .7rem;color:#e0e0e0;font-size:.88rem;outline:none">
        </div>
        <div style="display:flex;gap:.7rem;justify-content:flex-end;margin-top:1.2rem">
          <button class="btn" onclick="document.getElementById('modal-nota-prospect').style.display='none'" style="background:rgba(255,255,255,.07)">Annulla</button>
          <button class="btn btn-gr" onclick="salvaNotaProspect()">Salva</button>
        </div>
      </div>
    </div>

    <!-- ─── Calendario ─── -->
    <div id="crm-calendario" class="crm-sub" style="display:none">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.6rem;margin-bottom:1.2rem">
        <h3 style="margin:0;color:#F6AD55;font-size:1rem">📅 Calendario Editoriale</h3>
        <div style="display:flex;gap:.5rem">
          <button id="cal-prev" class="btn" onclick="calNav(-1)">‹ Prec</button>
          <span id="cal-month-label" style="padding:.4rem 1rem;font-size:.9rem;font-weight:600;color:#F6AD55"></span>
          <button id="cal-next" class="btn" onclick="calNav(1)">Succ ›</button>
        </div>
      </div>
      <div id="calendario-content"></div>
    </div>

    <!-- ─── WhatsApp ─── -->
    <div id="crm-whatsapp" class="crm-sub" style="display:none">
      <div id="whatsapp-content">
        <div style="opacity:.5;padding:1.5rem;text-align:center">Caricamento...</div>
      </div>
    </div>
  </div>

  <!-- Modal Aggiungi Cliente -->
  <div id="modal-aggiungi" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1000;align-items:center;justify-content:center">
    <div style="background:#1a1f2e;border:1px solid rgba(246,173,85,.3);border-radius:14px;padding:2rem;width:100%;max-width:440px;margin:1rem">
      <h3 style="margin-bottom:1.2rem;color:#F6AD55">+ Nuovo Cliente</h3>
      <div style="display:grid;gap:.8rem">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:.7rem">
          <div>
            <div style="font-size:.8rem;color:#888;margin-bottom:.3rem">Nome</div>
            <input id="ag-nome" placeholder="Mario" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:8px;padding:.6rem .9rem;color:#e0e0e0;font-size:.9rem;outline:none">
          </div>
          <div>
            <div style="font-size:.8rem;color:#888;margin-bottom:.3rem">Cognome</div>
            <input id="ag-cognome" placeholder="Rossi" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:8px;padding:.6rem .9rem;color:#e0e0e0;font-size:.9rem;outline:none">
          </div>
        </div>
        <div>
          <div style="font-size:.8rem;color:#888;margin-bottom:.3rem">Email</div>
          <input id="ag-email" type="email" placeholder="mario@email.com" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:8px;padding:.6rem .9rem;color:#e0e0e0;font-size:.9rem;outline:none">
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:.6rem">
          <div>
            <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Piano Azioni</div>
            <select id="ag-azioni" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.5rem;color:#e0e0e0;font-size:.85rem;outline:none">
              <option>NONE</option><option>BASIC</option><option>PRO</option><option>VALUE</option>
            </select>
          </div>
          <div>
            <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Piano ETF</div>
            <select id="ag-etf" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.5rem;color:#e0e0e0;font-size:.85rem;outline:none">
              <option>NONE</option><option>BASIC</option><option>PRO</option><option>VALUE</option>
            </select>
          </div>
          <div>
            <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Piano Fondi</div>
            <select id="ag-fondi" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.5rem;color:#e0e0e0;font-size:.85rem;outline:none">
              <option>NONE</option><option>BASIC</option><option>PRO</option><option>VALUE</option>
            </select>
          </div>
          <div>
            <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Piano Ordini</div>
            <select id="ag-ordini" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.5rem;color:#e0e0e0;font-size:.85rem;outline:none">
              <option>NONE</option><option>BASIC</option><option>PRO</option><option>VALUE</option>
            </select>
          </div>
        </div>
        <div style="margin-top:.6rem">
          <div style="font-size:.78rem;color:#c9a84c;margin-bottom:.3rem">WealthOS</div>
          <select id="ag-wealthos" style="width:100%;background:#0a0f1e;border:1px solid rgba(201,168,76,.3);border-radius:6px;padding:.5rem;color:#e0e0e0;font-size:.85rem;outline:none">
            <option>NONE</option><option>ATTIVO</option><option>SOSPESO</option>
          </select>
        </div>
      </div>
      <div style="display:flex;gap:.7rem;margin-top:1.4rem;justify-content:flex-end">
        <button class="btn" onclick="chiudiModals()" style="background:rgba(255,255,255,.07)">Annulla</button>
        <button class="btn btn-gr" onclick="confermaAggiungi()">Salva</button>
      </div>
    </div>
  </div>

  <!-- Modal Attiva Cliente -->
  <div id="modal-attiva" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1000;align-items:center;justify-content:center">
    <div style="background:#1a1f2e;border:1px solid rgba(104,211,145,.3);border-radius:14px;padding:2rem;width:100%;max-width:460px;margin:1rem">
      <h3 style="margin-bottom:.4rem;color:#68D391">✅ Attiva Cliente</h3>
      <div id="at-info" style="font-size:.85rem;color:#aaa;margin-bottom:1.2rem"></div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:.6rem;margin-bottom:.6rem">
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Piano Azioni</div>
          <select id="at-azioni" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.5rem;color:#e0e0e0;font-size:.85rem;outline:none">
            <option>NONE</option><option>BASIC</option><option>PRO</option><option>VALUE</option>
          </select>
        </div>
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Piano ETF</div>
          <select id="at-etf" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.5rem;color:#e0e0e0;font-size:.85rem;outline:none">
            <option>NONE</option><option>BASIC</option><option>PRO</option><option>VALUE</option>
          </select>
        </div>
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Piano Fondi</div>
          <select id="at-fondi" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.5rem;color:#e0e0e0;font-size:.85rem;outline:none">
            <option>NONE</option><option>BASIC</option><option>PRO</option><option>VALUE</option>
          </select>
        </div>
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Piano Ordini</div>
          <select id="at-ordini" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.5rem;color:#e0e0e0;font-size:.85rem;outline:none">
            <option>NONE</option><option>BASIC</option><option>PRO</option><option>VALUE</option>
          </select>
        </div>
      </div>
      <div style="margin-bottom:1rem">
        <div style="font-size:.78rem;color:#c9a84c;margin-bottom:.3rem">WealthOS</div>
        <select id="at-wealthos" style="width:100%;background:#0a0f1e;border:1px solid rgba(201,168,76,.3);border-radius:6px;padding:.5rem;color:#e0e0e0;font-size:.85rem;outline:none">
          <option>NONE</option><option>ATTIVO</option><option>SOSPESO</option>
        </select>
      </div>
      <div style="font-size:.8rem;color:#888;background:rgba(104,211,145,.05);border-radius:8px;padding:.7rem .9rem;margin-bottom:1rem">
        Verrà generata una password temporanea e inviata via email (se Brevo è configurato).
      </div>
      <div style="display:flex;gap:.7rem;justify-content:flex-end">
        <button class="btn" onclick="chiudiModals()" style="background:rgba(255,255,255,.07)">Annulla</button>
        <button class="btn btn-gr" onclick="confermaAttiva()">Attiva e Invia Credenziali</button>
      </div>
    </div>
  </div>

  <!-- Modal Anagrafica / Dati Fiscali -->
  <div id="modal-anagrafica" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:1000;align-items:center;justify-content:center;overflow-y:auto;padding:1rem">
    <div style="background:#1a1f2e;border:1px solid rgba(179,151,90,.35);border-radius:14px;padding:2rem;width:100%;max-width:560px;margin:auto">
      <h3 style="margin-bottom:.3rem;color:#B3975A">📋 Anagrafica &amp; Dati Fiscali</h3>
      <div style="font-size:.8rem;color:#666;margin-bottom:1.2rem">I dati fiscali sono necessari per la fatturazione.</div>

      <!-- Dati personali -->
      <div style="font-size:.75rem;color:#B3975A;letter-spacing:1px;text-transform:uppercase;margin-bottom:.7rem">Dati Personali</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:.7rem;margin-bottom:.9rem">
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Nome</div>
          <input id="an-nome" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.55rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none">
        </div>
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Cognome</div>
          <input id="an-cognome" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.55rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none">
        </div>
      </div>
      <div style="margin-bottom:.9rem">
        <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Email</div>
        <input id="an-email" readonly style="width:100%;background:rgba(0,0,0,.2);border:1px solid rgba(255,255,255,.07);border-radius:7px;padding:.55rem .8rem;color:#666;font-size:.88rem;outline:none">
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:.7rem;margin-bottom:1.1rem">
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Paese</div>
          <select id="an-paese" onchange="aggiornaPaeseForm()" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.15);border-radius:7px;padding:.55rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none">
            <option value="">— seleziona —</option>
            <option value="IT">🇮🇹 Italia</option>
            <option value="ES">🇪🇸 Spagna</option>
            <option value="FR">🇫🇷 Francia</option>
            <option value="DE">🇩🇪 Germania</option>
            <option value="UK">🇬🇧 Regno Unito</option>
          </select>
        </div>
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Data di nascita</div>
          <input id="an-nascita" type="date" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.55rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none">
        </div>
      </div>

      <!-- Indirizzo -->
      <div style="font-size:.75rem;color:#B3975A;letter-spacing:1px;text-transform:uppercase;margin-bottom:.7rem">Indirizzo</div>
      <div style="margin-bottom:.7rem">
        <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Indirizzo</div>
        <input id="an-indirizzo" placeholder="Via/Calle/Rue..." style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.55rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none">
      </div>
      <div style="display:grid;grid-template-columns:120px 1fr;gap:.7rem;margin-bottom:1.1rem">
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">CAP / Postcode</div>
          <input id="an-cap" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.55rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none">
        </div>
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Città / City</div>
          <input id="an-citta" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.55rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none">
        </div>
      </div>

      <!-- Dati fiscali -->
      <div style="font-size:.75rem;color:#B3975A;letter-spacing:1px;text-transform:uppercase;margin-bottom:.7rem">Dati Fiscali</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:.7rem;margin-bottom:.7rem">
        <div>
          <div id="an-cf-label" style="font-size:.78rem;color:#888;margin-bottom:.3rem">Codice Fiscale / Tax ID</div>
          <input id="an-cf" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.55rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none;font-family:monospace;letter-spacing:1px">
        </div>
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Telefono</div>
          <input id="an-tel" placeholder="+39 333 1234567" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.55rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none">
        </div>
      </div>
      <div id="an-piva-row" style="margin-bottom:1.1rem">
        <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Partita IVA <span style="opacity:.5">(opzionale — solo per professionisti)</span></div>
        <input id="an-piva" placeholder="IT12345678901" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.55rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none;font-family:monospace">
      </div>

      <div style="display:flex;gap:.7rem;justify-content:flex-end">
        <button class="btn" onclick="chiudiModals()" style="background:rgba(255,255,255,.07)">Annulla</button>
        <button class="btn" onclick="salvaAnagrafica()" style="background:#B3975A;color:#0a0f1e;border-color:#B3975A;font-weight:700">Salva Dati Fiscali</button>
      </div>
    </div>
  </div>

  <!-- ══════════ ESECUZIONE ══════════ -->
  <div id="esecuzione" class="panel">
    <div class="box">
      <h3>🚀 Esecuzione Manuale</h3>
      <div style="display:flex;gap:.7rem;flex-wrap:wrap;margin-top:.6rem">
        <button class="btn btn-gr"  id="run-azioni"         onclick="runScreener('azioni')">▶ Azioni</button>
        <button class="btn btn-gr"  id="run-etf"            onclick="runScreener('etf')">▶ ETF</button>
        <button class="btn btn-gr"  id="run-fondi"          onclick="runScreener('fondi')">▶ Fondi</button>
        <button class="btn btn-gr"  id="run-fondi_eu"       onclick="runScreener('fondi_eu')">▶ Fondi EU</button>
        <button class="btn btn-or"  id="run-tutti"          onclick="runScreener('tutti')">▶▶ Tutti</button>
        <button class="btn btn-or"  id="run-orchestrator"   onclick="runScreener('orchestrator')" style="background:rgba(246,173,85,.2)">🚀 Orchestrator + Email</button>
        <button class="btn"         id="run-fondi_eu_fetch" onclick="runScreener('fondi_eu_fetch')" style="background:rgba(99,179,237,.15);border-color:#4a7fb5;color:#90cdf4">🔄 Aggiorna Universo Fondi EU</button>
      </div>
      <div id="run-msg" style="margin-top:.7rem;font-size:.84rem"></div>
    </div>

    <div id="log-box" class="box" style="display:none">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.6rem">
        <h3 id="log-title">📟 Log</h3>
        <div style="display:flex;gap:.5rem;align-items:center">
          <span id="log-badge" class="rs rs-running">running</span>
          <button class="btn" style="padding:.2rem .6rem;font-size:.72rem;border-color:rgba(255,255,255,.12);color:rgba(255,255,255,.4)" onclick="document.getElementById('log-box').style.display='none'">✕</button>
        </div>
      </div>
      <div id="log-term" class="log-term">In attesa output...</div>
      <div id="log-info" style="margin-top:.4rem;font-size:.7rem;opacity:.4">Aggiornamento ogni 2s...</div>
    </div>

    <div class="box" style="font-size:.84rem;line-height:1.7">
      <strong>⏰ Scheduler automatico (lun-ven):</strong><br>
      <span style="opacity:.55">08:00 Social (lun/mer/ven) &nbsp;·&nbsp; 20:30 Aggiorna Universo Fondi EU &nbsp;·&nbsp; 21:00 AZIONI &nbsp;·&nbsp; 21:45 ETF+FONDI+FONDI_EU</span>
    </div>
  </div>

  <!-- ══════════ DATABASE ══════════ -->
  <div id="database" class="panel">
    <div class="box">
      <div class="sec-head" style="margin-bottom:1rem">
        <h2>🗃️ Database Universo Ticker</h2>
        <span id="db-totali" style="font-size:.82rem;color:#90cdf4;opacity:.7">Caricamento...</span>
      </div>
      <div class="db-tabs">
        <button class="db-tab active" id="dbtab-azioni" onclick="switchDbTab(this,'db-azioni')">📈 Azioni</button>
        <button class="db-tab" id="dbtab-etf"    onclick="switchDbTab(this,'db-etf')">📦 ETF</button>
        <button class="db-tab" id="dbtab-fondi"  onclick="switchDbTab(this,'db-fondi')">🏦 Fondi</button>
      </div>
      <input type="text" class="db-search" id="db-search" placeholder="🔍 Cerca ticker o gruppo mercato..." oninput="filterDb()">
      <div style="display:flex;align-items:center;gap:1rem;margin-top:.5rem;flex-wrap:wrap">
        <div class="db-count" id="db-count">—</div>
        <button id="db-load-btn" class="btn btn-or" onclick="loadDbPrices()" style="padding:.35rem 1rem;font-size:.8rem;border-radius:6px;opacity:.85">📊 Carica dati (0 visibili)</button>
        <button id="db-missing-btn" class="btn" onclick="loadMissingDbPrices()" style="padding:.35rem 1rem;font-size:.8rem;border-radius:6px;background:#2C5282;border:1px solid #4a7fb5;color:#90cdf4">🔄 Aggiorna mancanti (<span id="db-missing-count">0</span>)</button>
        <button id="db-dead-btn" class="btn" onclick="verifyDeadTickers()" style="padding:.35rem 1rem;font-size:.8rem;border-radius:6px;background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.4);color:#fca5a5">☠️ Verifica ticker morti</button>
        <button onclick="_resetDbCols(_dbAsset.replace('db-',''))" style="padding:.25rem .7rem;font-size:.75rem;background:transparent;border:1px solid rgba(255,255,255,.2);border-radius:5px;color:#aaa;cursor:pointer" title="Ripristina ordine colonne originale">↺ Reset colonne</button>
      </div>
    </div>

    <div id="db-azioni" class="db-panel active">
      <div class="tbl-wrap">
        <table>
          <thead id="db-head-azioni"></thead>
          <tbody id="db-body-azioni"><tr><td colspan="6" style="padding:2rem;text-align:center;opacity:.4">Clicca la tab per caricare</td></tr></tbody>
        </table>
      </div>
    </div>

    <div id="db-etf" class="db-panel">
      <div class="tbl-wrap">
        <table>
          <thead id="db-head-etf"></thead>
          <tbody id="db-body-etf"></tbody>
        </table>
      </div>
    </div>

    <div id="db-fondi" class="db-panel">
      <div class="tbl-wrap">
        <table>
          <thead id="db-head-fondi"></thead>
          <tbody id="db-body-fondi"></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- ══════════ KB ══════════ -->
  <div id="kb" class="panel">
    <div class="box">
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem;margin-bottom:1rem">
        <h3 style="margin:0">📚 Knowledge Base — File Caricati</h3>
        <div style="display:flex;align-items:center;gap:.8rem;flex-wrap:wrap">
          <span id="kb-status-panel" style="font-size:.82rem;opacity:.7">Caricamento...</span>
          <button class="btn btn-re" id="btn-reload-kb2" onclick="reloadKB2()">↺ Ricarica KB</button>
        </div>
      </div>
      <div id="kb-files-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:.8rem">
        <div style="opacity:.5;grid-column:1/-1;text-align:center;padding:1.5rem">Caricamento file...</div>
      </div>
    </div>
  </div>

  <!-- ══════════ ONBOARDING ══════════ -->
  <div id="onboarding" class="panel">
    <div class="db-tabs" style="margin-bottom:1rem">
      <div class="db-tab active" onclick="switchObTab(this,'ob-interno')">🏢 Onboarding Interno</div>
      <div class="db-tab" onclick="switchObTab(this,'ob-cliente')">👤 Onboarding Cliente</div>
    </div>

    <!-- ONBOARDING INTERNO -->
    <div id="ob-interno" class="db-panel" style="display:block">
      <div class="box">
        <h3>🏢 Onboarding Interno — Guida Operativa Fuerte Venture Capital</h3>
        <p style="opacity:.7;margin-bottom:1.5rem">Guida per il team interno: come usare la dashboard, gestire i clienti, interpretare i report e le procedure operative quotidiane.</p>

        <h4 style="color:var(--accent);margin-top:1.5rem">1. Accesso alla Dashboard Admin</h4>
        <ul>
          <li>URL: <code>/admin</code> — accessibile solo con password admin</li>
          <li>La dashboard è divisa in tab: Home, Servizi, Parametri, Azioni, ETF, Fondi, CRM, Esecuzione, Database, KB, Onboarding</li>
          <li>Il sistema si riavvia tramite <strong>START_SISTEMA_PUBBLICO.bat</strong> su Windows — da usare dopo ogni modifica ai file Python</li>
        </ul>

        <h4 style="color:var(--accent);margin-top:1.5rem">2. Architettura del Sistema</h4>
        <ul>
          <li><strong>Screener Azioni:</strong> universe da <code>ticker_lists_5000.py</code> — aggiornato manualmente</li>
          <li><strong>Screener ETF:</strong> universe da JustETF via scraping — cache in <code>etf_universe_cache.json</code></li>
          <li><strong>Screener Fondi EU:</strong> universe da JustETF — cache in <code>fondi_eu_universe_cache.json</code></li>
          <li><strong>Screener Fondi US:</strong> universe da <code>ticker_lists_5000.py</code></li>
          <li><strong>Dati di mercato:</strong> Yahoo Finance (yfinance) — chiamate in batch durante l'elaborazione</li>
          <li><strong>Email:</strong> Brevo SMTP — configurato in <code>email_notifier.py</code></li>
          <li><strong>Chatbot:</strong> Anthropic Claude API — configurato in <code>chat_service.py</code></li>
        </ul>

        <h4 style="color:var(--accent);margin-top:1.5rem">3. Elaborazione Giornaliera (Lunedì–Venerdì)</h4>
        <ul>
          <li>L'orchestratore lancia gli screener in sequenza: Azioni → ETF → Fondi US → Fondi EU</li>
          <li>Al termine, <code>email_notifier.py</code> invia i report ai clienti attivi per i rispettivi piani</li>
          <li>I report vengono salvati nella cartella <code>REPORTS/</code></li>
          <li>Lo schedulatore è visibile nel tab <strong>Esecuzione</strong> della dashboard</li>
          <li>Orario di invio email: configurabile nel tab <strong>Parametri</strong></li>
        </ul>

        <h4 style="color:var(--accent);margin-top:1.5rem">4. Gestione Clienti (Tab CRM)</h4>
        <ul>
          <li>Aggiungere cliente: bottone "Nuovo Cliente" nel tab Servizi o CRM</li>
          <li>Attivare abbonamento: impostare <em>piano</em> e <em>stato = Attivo</em></li>
          <li>I clienti con stato <strong>Non Attivo</strong> non ricevono report né email di elaborazione</li>
          <li>Ogni cliente ha: email, piano (BASIC/PRO/VALUE), asset (AZIONI/ETF/FONDI), stato, note</li>
          <li>Export clienti: bottone "Esporta CSV" nel tab CRM</li>
        </ul>

        <h4 style="color:var(--accent);margin-top:1.5rem">5. Knowledge Base e Chatbot</h4>
        <ul>
          <li>I file KB si trovano in <code>KNOWLEDGE_BASE/</code> — tutti in formato .md</li>
          <li>Modificare un file KB NON richiede riavvio: usare il bottone <strong>↺ Ricarica KB</strong> nel tab KB</li>
          <li>Il chatbot usa Claude (Anthropic) — la chiave API è in <code>.env</code> o nei parametri</li>
          <li>Le conteggi dell'universo (N. azioni, ETF, fondi) si aggiornano automaticamente al ricaricamento KB</li>
          <li><strong>IMPORTANTE:</strong> non inserire mai soglie di filtro o pesi dello score nei file KB — sono parametri proprietari</li>
        </ul>

        <h4 style="color:var(--accent);margin-top:1.5rem">6. Parametri di Configurazione</h4>
        <ul>
          <li>Tab <strong>Parametri</strong>: orari scheduler, soglie screener, configurazione email</li>
          <li>I parametri vengono salvati in <code>params.json</code></li>
          <li>Modifiche ai parametri di screening hanno effetto dalla prossima elaborazione</li>
        </ul>

        <h4 style="color:var(--accent);margin-top:1.5rem">7. Procedure di Emergenza</h4>
        <ul>
          <li><strong>Sistema down:</strong> verificare che Docker/ngrok siano attivi; riavviare con START_SISTEMA_PUBBLICO.bat</li>
          <li><strong>Email non inviate:</strong> verificare log in tab Esecuzione; controllare credenziali Brevo in params</li>
          <li><strong>Screener bloccato:</strong> controllare connessione internet e limiti API Yahoo Finance</li>
          <li><strong>Chatbot non risponde:</strong> verificare chiave API Anthropic e saldo account</li>
          <li><strong>Cache ETF/Fondi obsoleta:</strong> eseguire manualmente il refresh dal tab ETF o Fondi</li>
        </ul>
      </div>
    </div>

    <!-- ONBOARDING CLIENTE -->
    <div id="ob-cliente" class="db-panel">
      <div class="box">
        <h3>👤 Onboarding Cliente — Flusso di Benvenuto</h3>
        <p style="opacity:.7;margin-bottom:1.5rem">Procedura di attivazione per nuovi abbonati: dalla registrazione alla prima ricezione del report.</p>

        <h4 style="color:var(--accent);margin-top:1.5rem">Fase 1 — Registrazione</h4>
        <ol>
          <li>Il cliente si registra tramite il form sul sito <strong>fuerteventurecapital.com</strong></li>
          <li>Inserisce: nome, email, piano desiderato (BASIC / PRO / VALUE), asset (Azioni / ETF / Fondi)</li>
          <li>Sceglie la lingua del report: IT / ES / EN / FR / DE</li>
          <li>Completa il pagamento (abbonamento mensile o annuale)</li>
        </ol>

        <h4 style="color:var(--accent);margin-top:1.5rem">Fase 2 — Attivazione (lato admin)</h4>
        <ol>
          <li>Ricevuta la conferma di pagamento, aprire il tab <strong>CRM</strong> nella dashboard</li>
          <li>Aggiungere il cliente con i dati forniti, stato = <strong>Attivo</strong></li>
          <li>Il cliente inizierà a ricevere i report dalla prossima elaborazione (lun–ven)</li>
        </ol>

        <h4 style="color:var(--accent);margin-top:1.5rem">Fase 3 — Email di Benvenuto</h4>
        <p>Inviare manualmente (o tramite automazione Brevo) una email di benvenuto che include:</p>
        <ul>
          <li>Conferma del piano attivato e dell'asset scelto</li>
          <li>Spiegazione di cosa riceverà: report giornalieri lun–ven con i top titoli selezionati</li>
          <li>Come leggere il report: descrizione delle colonne (Score, EV/FCF, Sharpe, ecc.)</li>
          <li>Link al chatbot di supporto sul sito</li>
          <li>Contatto email per assistenza: supporto@fuerteventurecapital.com</li>
        </ul>

        <h4 style="color:var(--accent);margin-top:1.5rem">Fase 4 — Come Leggere il Report</h4>
        <p style="margin-bottom:.8rem">Il report è un file <strong>Excel multi-foglio</strong> ricevuto via email. Ogni piano include: <em>Top Selezionati</em> (foglio principale), <em>Azioni/ETF/Fondi Selezionati</em> (dati completi) e <em>Scartati per motivo</em> (solo VALUE). Le colonne variano per asset class — vedi sotto.</p>

        <!-- Colonne comuni a tutti i report -->
        <h5 style="color:#90CDF4;margin:1rem 0 .4rem">🔑 Colonne comuni a tutti i report</h5>
        <div class="tbl-wrap">
          <table>
            <thead><tr><th>Colonna</th><th>Cosa indica</th><th>Come leggerla</th></tr></thead>
            <tbody>
              <tr>
                <td><strong>Score</strong></td>
                <td>Punteggio percentile 0–100 calcolato da Robot Trader ogni sera</td>
                <td><strong>Score 85</strong> = questo strumento supera l'85% di tutti quelli analizzati nella stessa elaborazione. È un ranking <em>relativo</em>: cambia ogni giorno con il mercato. Non confrontare score di giorni diversi.</td>
              </tr>
              <tr>
                <td><strong>Ticker</strong></td>
                <td>Codice identificativo dello strumento sulla borsa di quotazione</td>
                <td>Usare questo codice per cercare lo strumento sul proprio broker (es. <em>AAPL</em> = Apple su NASDAQ, <em>VWCE.DE</em> = Vanguard FTSE All-World su Xetra)</td>
              </tr>
              <tr>
                <td><strong>Nome</strong></td>
                <td>Ragione sociale dell'azienda o nome ufficiale dell'ETF/Fondo</td>
                <td>Nome completo — utile per ricerche su Google Finance, Yahoo Finance o JustETF</td>
              </tr>
              <tr>
                <td><strong>Mercato / Indice</strong></td>
                <td>Borsa di quotazione e indice di appartenenza</td>
                <td>Indica il paese e il segmento di mercato (es. NYSE, Xetra, Borsa Italiana)</td>
              </tr>
              <tr>
                <td><strong>Prezzo</strong></td>
                <td>Prezzo di chiusura nella valuta locale dello strumento</td>
                <td>Prezzo al momento dell'elaborazione notturna — può variare all'apertura del giorno dopo</td>
              </tr>
              <tr>
                <td><strong>Data Dati</strong></td>
                <td>Data dell'ultima rilevazione dei dati</td>
                <td>Conferma che i dati sono aggiornati — utile per verificare in caso di festività o dati mancanti</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Report AZIONI -->
        <h5 style="color:#90CDF4;margin:1.2rem 0 .4rem">📈 Colonne Report AZIONI (PRO / VALUE)</h5>
        <div class="tbl-wrap">
          <table>
            <thead><tr><th>Colonna</th><th>Formula / Definizione</th><th>Interpretazione pratica</th></tr></thead>
            <tbody>
              <tr>
                <td><strong>EV/FCF</strong></td>
                <td>Enterprise Value ÷ Free Cash Flow.<br><small>EV = Market Cap + Debito Netto<br>FCF = Utile Op. − Investimenti</small></td>
                <td>Quanti anni ci vorrebbero per ripagare l'intera azienda con la sola cassa generata. <strong>Più basso = più conveniente.</strong> Un'azienda che genera molta cassa rispetto al suo prezzo è potenzialmente sottovalutata.</td>
              </tr>
              <tr>
                <td><strong>P/B</strong></td>
                <td>Prezzo Azione ÷ Valore Contabile per Azione</td>
                <td>Quanto paga il mercato rispetto al patrimonio netto reale. <strong>P/B &lt; 1</strong> = l'azienda quota sotto il suo valore contabile (possibile occasione). <strong>P/B &gt; 3</strong> = il mercato sconta forte crescita futura.</td>
              </tr>
              <tr>
                <td><strong>ROE</strong></td>
                <td>Utile Netto ÷ Patrimonio Netto × 100</td>
                <td>Quanto rende il capitale degli azionisti. <strong>ROE elevato</strong> = management efficiente. Attenzione: un ROE molto alto può derivare da eccessivo indebitamento — verificare sempre insieme al Net Debt/EBITDA.</td>
              </tr>
              <tr>
                <td><strong>Net Debt/EBITDA</strong></td>
                <td>(Totale Debiti − Liquidità) ÷ EBITDA</td>
                <td>Quanti anni di utile operativo servono per ripagare il debito. <strong>Valore basso</strong> = azienda solida e poco indebitata. <strong>Valore alto</strong> = rischio finanziario elevato. Non applicato a banche e assicurazioni.</td>
              </tr>
              <tr>
                <td><strong>Dividend Yield</strong></td>
                <td>Dividendo Annuo ÷ Prezzo × 100</td>
                <td>Rendimento annuo da dividendo rispetto al prezzo corrente. Colonna più rilevante per il piano <strong>BASIC</strong> — chi cerca reddito passivo immediato guarda questo valore per primo.</td>
              </tr>
              <tr>
                <td><strong>Var 1D %</strong></td>
                <td>Variazione % del prezzo nella seduta corrente</td>
                <td>Segnale di momentum di breve termine. Rilevante soprattutto per il piano <strong>BASIC</strong>. Un titolo che sale il giorno del report potrebbe confermare l'interesse del mercato.</td>
              </tr>
              <tr>
                <td><strong>Perf 1M / 3M / 6M / 1Y %</strong></td>
                <td>Variazione % del prezzo nei periodi indicati</td>
                <td>Storico di performance su più orizzonti. Utile per capire se il titolo è in trend positivo o ha già corso molto. Nel piano <strong>VALUE</strong> queste colonne sono informative — non guidano la selezione.</td>
              </tr>
              <tr>
                <td><strong>Market Cap</strong></td>
                <td>Capitalizzazione totale (Prezzo × Numero Azioni)</td>
                <td>Dimensione dell'azienda. Filtro di liquidità minima — garantisce che il titolo sia negoziabile senza problemi. Blue Chip = grandi cap, Mid Cap = capitalizzazioni medie.</td>
              </tr>
              <tr>
                <td><strong>Settore / Industry</strong></td>
                <td>Classificazione settoriale GICS</td>
                <td>Utile per valutare la concentrazione settoriale del proprio portafoglio. Se si acquistano 5 titoli tutti nello stesso settore, il portafoglio non è diversificato.</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Report ETF -->
        <h5 style="color:#90CDF4;margin:1.2rem 0 .4rem">📦 Colonne Report ETF</h5>
        <div class="tbl-wrap">
          <table>
            <thead><tr><th>Colonna</th><th>Formula / Definizione</th><th>Interpretazione pratica</th></tr></thead>
            <tbody>
              <tr>
                <td><strong>ISIN</strong></td>
                <td>International Securities Identification Number — codice universale a 12 caratteri</td>
                <td>Codice univoco dell'ETF indipendente dalla borsa di quotazione. Usare l'ISIN per cercare l'ETF su JustETF o sul proprio broker europeo senza ambiguità.</td>
              </tr>
              <tr>
                <td><strong>TER</strong></td>
                <td>Total Expense Ratio — costo di gestione annuo in %</td>
                <td>Costo dedotto automaticamente ogni anno dal patrimonio del fondo. <strong>Più basso è meglio</strong>, soprattutto su orizzonti lunghi. ETF passivi tipici: 0.03%–0.50%. Su €100.000 e 20 anni, uno 0.20% in più di TER costa oltre €5.000 in rendimento perso.</td>
              </tr>
              <tr>
                <td><strong>Sharpe Ratio</strong></td>
                <td>(Rendimento − Tasso Risk-Free) ÷ Deviazione Standard</td>
                <td>Rendimento ottenuto per ogni unità di rischio assunto. <strong>Negativo</strong> = rendimento inferiore al risk-free. <strong>&lt; 1</strong> = rendimento non adeguato al rischio. <strong>1–2</strong> = buono. <strong>≥ 2</strong> = eccellente. È la metrica principale di selezione nei piani PRO e VALUE.</td>
              </tr>
              <tr>
                <td><strong>Performance 1Y</strong></td>
                <td>Variazione % del NAV negli ultimi 12 mesi</td>
                <td>Rendimento annuo dell'ETF. Da leggere sempre insieme allo Sharpe: un rendimento alto con Sharpe basso significa che è stato ottenuto con molta volatilità (rischio elevato).</td>
              </tr>
              <tr>
                <td><strong>Perf 3M %</strong></td>
                <td>Variazione % negli ultimi 3 mesi</td>
                <td>Momentum di breve termine. Peso dominante nel piano <strong>BASIC</strong>. Nei piani VALUE il dato trimestrale è quasi irrilevante — un ETF value si valuta su decenni.</td>
              </tr>
              <tr>
                <td><strong>Net Assets (AUM)</strong></td>
                <td>Patrimonio totale gestito dall'ETF</td>
                <td>Indicatore di liquidità e stabilità. ETF con AUM basso rischiano la chiusura o spread bid/ask molto ampi. Robot Trader applica una soglia minima di AUM come prerequisito di accesso all'universo analizzato.</td>
              </tr>
              <tr>
                <td><strong>Replica</strong></td>
                <td>Metodo di replica dell'indice: Fisica completa / Campionamento / Sintetica</td>
                <td>Robot Trader seleziona <strong>solo ETF a replica fisica</strong>. Nessun ETF sintetico (swap) nell'universo analizzato — zero rischio controparte.</td>
              </tr>
              <tr>
                <td><strong>Tipo (ACC)</strong></td>
                <td>Accumulazione vs Distribuzione</td>
                <td>Robot Trader analizza <strong>solo ETF ad accumulazione</strong>: i dividendi vengono reinvestiti automaticamente nel fondo, ottimizzando l'interesse composto ed evitando la doppia tassazione europea.</td>
              </tr>
              <tr>
                <td><strong>Stelle MS</strong></td>
                <td>Rating Morningstar ★ a ★★★★★</td>
                <td>Valutazione Morningstar della performance aggiustata per il rischio rispetto ai fondi comparabili. <strong>5 stelle</strong> = top 10% della categoria. Informativo — non usato come filtro diretto nello score.</td>
              </tr>
              <tr>
                <td><strong>Età (anni)</strong></td>
                <td>Anni di vita dell'ETF dalla data di lancio</td>
                <td>ETF molto giovani (&lt; 3 anni) hanno storico di dati limitato — lo Sharpe su breve storia può essere poco affidabile. I piani PRO e VALUE preferiscono ETF con track record più lungo.</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Report FONDI -->
        <h5 style="color:#90CDF4;margin:1.2rem 0 .4rem">🏦 Colonne Report FONDI (US &amp; EU UCITS)</h5>
        <div class="tbl-wrap">
          <table>
            <thead><tr><th>Colonna</th><th>Formula / Definizione</th><th>Interpretazione pratica</th></tr></thead>
            <tbody>
              <tr>
                <td><strong>TER</strong></td>
                <td>Total Expense Ratio annuo</td>
                <td>Nei fondi a gestione attiva il TER è tipicamente 0.5%–2.5%, più alto rispetto agli ETF. Un TER alto è accettabile solo se il fondo genera alfa reale — cioè rendimento superiore all'indice di riferimento al netto dei costi.</td>
              </tr>
              <tr>
                <td><strong>Sharpe Ratio</strong></td>
                <td>(Rendimento − Tasso Risk-Free) ÷ Deviazione Standard</td>
                <td>Stessa logica degli ETF. Nei fondi è la metrica più importante per distinguere gestori che generano rendimento con disciplina da quelli che semplicemente cavalcano il mercato.</td>
              </tr>
              <tr>
                <td><strong>AUM</strong></td>
                <td>Assets Under Management — patrimonio totale del fondo</td>
                <td>Nei fondi l'AUM sostituisce il Volume come proxy di liquidità. Un fondo con AUM elevato ha più stabilità e rischio di chiusura vicino a zero.</td>
              </tr>
              <tr>
                <td><strong>Performance 1Y</strong></td>
                <td>Variazione % del NAV negli ultimi 12 mesi</td>
                <td>Rendimento annuo del fondo. Da confrontare sempre con il benchmark di riferimento: se il fondo rende il 10% ma il suo indice ha fatto il 15%, il gestore ha <em>distrutto</em> valore nonostante l'apparente buon rendimento.</td>
              </tr>
              <tr>
                <td><strong>Perf 3M %</strong></td>
                <td>Variazione % del NAV negli ultimi 3 mesi</td>
                <td>Momentum recente. Peso alto nel piano <strong>BASIC</strong> per chi cerca rendimento immediato. Nei piani VALUE il trimestrale è rumore — un gestore quality si valuta su cicli completi di mercato (5–10 anni).</td>
              </tr>
              <tr>
                <td><strong>Stelle MS</strong></td>
                <td>Rating Morningstar ★ a ★★★★★</td>
                <td><strong>5 stelle</strong> = top 10% della categoria per performance aggiustata per il rischio. <strong>4 stelle</strong> = top 22.5%. Informativo nel report — il sistema Robot Trader usa il proprio score basato su metriche quantitative.</td>
              </tr>
              <tr>
                <td><strong>Categoria</strong></td>
                <td>Classificazione Morningstar del fondo per stile e asset class</td>
                <td>Utile per capire in quale segmento opera il fondo (es. Large Cap Growth USA, Obbligazionario EUR, Bilanciato). Fondamentale per non duplicare l'esposizione nel portafoglio.</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Fogli Excel e struttura multi-sheet -->
        <h5 style="color:#90CDF4;margin:1.2rem 0 .4rem">📋 Struttura Excel multi-foglio</h5>
        <div class="tbl-wrap">
          <table>
            <thead><tr><th>Foglio</th><th>Contenuto</th><th>Disponibile in</th></tr></thead>
            <tbody>
              <tr><td><strong>Top Selezionati</strong></td><td>I migliori strumenti selezionati, ordinati per Score decrescente. Vista compatta con le colonne più utili.</td><td>Tutti i piani</td></tr>
              <tr><td><strong>Selezionati (completo)</strong></td><td>Tutti gli strumenti che hanno superato i filtri, con tutte le colonne disponibili. Vista analitica completa.</td><td>Tutti i piani</td></tr>
              <tr><td><strong>Scartati per motivo</strong></td><td>Strumenti esclusi, raggruppati per il criterio che non hanno superato (es. EV/FCF, P/B, Sharpe). Utile per capire perché un titolo specifico non è in lista.</td><td>Solo piani PRO e VALUE</td></tr>
              <tr><td><strong>Non Validi</strong></td><td>Strumenti con dati mancanti o insufficienti al momento dell'elaborazione.</td><td>Solo piani VALUE</td></tr>
            </tbody>
          </table>
        </div>
        <p style="font-size:.82rem;opacity:.7;margin-top:.6rem">💡 <strong>Consiglio:</strong> iniziare sempre dal foglio <em>Top Selezionati</em> per una panoramica rapida. Aprire <em>Selezionati (completo)</em> per approfondire un titolo specifico. Usare <em>Scartati</em> per capire perché un proprio titolo di interesse non è in lista.</p>

        <h4 style="color:var(--accent);margin-top:1.5rem">Fase 5 — Supporto e Chatbot</h4>
        <ul>
          <li>Il chatbot Robot Trader è disponibile sul sito 24/7 per rispondere a domande sui mercati, le metriche e il funzionamento del servizio</li>
          <li>Per domande sull'abbonamento o problemi tecnici: email diretta al team</li>
          <li>I report vengono inviati ogni giorno lavorativo — se manca un report, verificare la cartella spam</li>
        </ul>

        <h4 style="color:var(--accent);margin-top:1.5rem">Fase 6 — Profilazione Consigliata</h4>
        <p style="margin-bottom:.5rem">Suggerire al cliente di rispondere al questionario sul profilo investitore. La raccomandazione segue 3 step: <strong>1)</strong> asset class preferita → <strong>2)</strong> orizzonte temporale + esperienza → <strong>3)</strong> segnali chiave nel dialogo.</p>

        <h5 style="color:#90CDF4;margin:1.2rem 0 .4rem">📈 AZIONI</h5>
        <div class="tbl-wrap">
          <table>
            <thead><tr><th>Piano</th><th>Profilo</th><th>Orizzonte</th><th>Chi è</th><th>Segnali tipici</th></tr></thead>
            <tbody>
              <tr>
                <td><strong>BASIC €29</strong></td>
                <td>L'Investitore in Dividendi</td>
                <td>3–12 mesi</td>
                <td>Privato 40–65aa, libero professionista o dipendente con risparmio. Conosce i titoli noti (Enel, Apple, LVMH). Non legge bilanci in profondità.</td>
                <td><em>"voglio dividendi", "cedola", "rendita passiva", "titoli sicuri", "non sono esperto"</em></td>
              </tr>
              <tr>
                <td><strong>PRO €39</strong></td>
                <td>L'Analista Fondamentale Globale</td>
                <td>2–5 anni</td>
                <td>Investitore attivo 35–55aa, sa leggere un conto economico, conosce EV/FCF e ROE. Portafoglio personale €50k–€500k, investe sui mercati esteri.</td>
                <td><em>"analisi fondamentale", "EV/FCF", "sottovalutato", "valore intrinseco", "investo all'estero", "portafoglio €100k"</em></td>
              </tr>
              <tr>
                <td><strong>VALUE €59</strong></td>
                <td>Il Deep Value Investor</td>
                <td>5–15 anni</td>
                <td>Consulente indipendente, gestore patrimoniale, family office. Approccio stile Buffett/Munger. Gestisce patrimoni >€1M o portafogli di terzi. Cerca conviction su poche posizioni.</td>
                <td><em>"Buffett", "Munger", "deep value", "conviction", "patrimonio >€1M", "gestisco portafogli", "family office"</em></td>
              </tr>
            </tbody>
          </table>
        </div>

        <h5 style="color:#90CDF4;margin:1.2rem 0 .4rem">📦 ETF</h5>
        <div class="tbl-wrap">
          <table>
            <thead><tr><th>Piano</th><th>Profilo</th><th>Orizzonte</th><th>Chi è</th><th>Segnali tipici</th></tr></thead>
            <tbody>
              <tr>
                <td><strong>BASIC €29</strong></td>
                <td>Il Risparmiatore sul Trend</td>
                <td>6–18 mesi</td>
                <td>25–45aa, tech-savvy, PAC mensile o somma da investire. Non ha formazione avanzata. Vuole entrare su ETF che stanno già performando bene nel trimestre.</td>
                <td><em>"ETF", "PAC", "accumulo mensile", "quale settore sta andando bene", "momentum", "trend"</em></td>
              </tr>
              <tr>
                <td><strong>PRO €39</strong></td>
                <td>Il Portfolio Manager Attivo</td>
                <td>3–7 anni</td>
                <td>Investitore sofisticato che costruisce portafogli ETF diversificati (8–15 ETF). Conosce lo Sharpe ratio, attento ai costi su medio periodo.</td>
                <td><em>"Sharpe ratio", "portafoglio bilanciato", "8-15 ETF", "risk-adjusted", "costruisco portafoglio per cliente"</em></td>
              </tr>
              <tr>
                <td><strong>VALUE €59</strong></td>
                <td>Il Wealth Manager Istituzionale</td>
                <td>10–30 anni</td>
                <td>Wealth manager, fondo pensione, family office. Sa che frazioni di TER su grandi patrimoni si traducono in €100k+ di costi aggiuntivi in 20 anni. Ogni basis point conta.</td>
                <td><em>"wealth manager", "fondo pensione", "TER minimo", "basis point", "10-20-30 anni", "patrimonio istituzionale"</em></td>
              </tr>
            </tbody>
          </table>
        </div>

        <h5 style="color:#90CDF4;margin:1.2rem 0 .4rem">🏦 FONDI US &amp; FONDI EU UCITS</h5>
        <div class="tbl-wrap">
          <table>
            <thead><tr><th>Piano</th><th>Profilo</th><th>Orizzonte</th><th>Chi è</th><th>Segnali tipici</th></tr></thead>
            <tbody>
              <tr>
                <td><strong>BASIC €29</strong></td>
                <td>Il Cliente della Banca</td>
                <td>6–24 mesi</td>
                <td>Retail 45–70aa, cliente di banca tradizionale (Mediolanum, Fineco, Azimut). Nessun background tecnico, si fida del nome del gestore, guarda la performance recente.</td>
                <td><em>"fondo comune", "Mediolanum", "Fineco", "cosa rende di più adesso", "il mio consulente in banca"</em></td>
              </tr>
              <tr>
                <td><strong>PRO €39</strong></td>
                <td>Il Consulente Finanziario Indipendente</td>
                <td>3–7 anni</td>
                <td>CFI, private banker o advisor che seleziona fondi per portafogli clienti €500k–€5M. Capisce alfa reale vs. beta di mercato. Vuole gestori disciplinati e consistenti.</td>
                <td><em>"CFI", "private banker", "gestisco portafogli clienti", "alfa", "seleziono fondi", "advisor"</em></td>
              </tr>
              <tr>
                <td><strong>VALUE €59</strong></td>
                <td>Il Family Office / Istituzionale</td>
                <td>10–30 anni</td>
                <td>Family office, fondazione, fondo pensione. Patrimoni >€5M. Massimo Sharpe + TER minimo assoluto. Non guarda il trimestre — guarda la qualità del processo nel lungo periodo.</td>
                <td><em>"family office", "fondazione", "fondo pensione", "gestisco >€5M", "TER minimo", "20 anni di orizzonte"</em></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p style="margin-top:.8rem;font-size:.82rem;opacity:.7">💡 <strong>Fondi EU UCITS</strong> vs Fondi US: stessa struttura di profili, ma per investitori europei che preferiscono strumenti regolamentati UE (UCITS/KIID), acquistabili dalla propria banca italiana, spagnola o francese senza problemi fiscali o di distribuzione.</p>

        <h5 style="color:#90CDF4;margin:1.2rem 0 .4rem">🧭 Guida rapida di orientamento</h5>
        <div class="tbl-wrap">
          <table>
            <thead><tr><th>Orizzonte</th><th>Esperienza</th><th>Piano consigliato</th></tr></thead>
            <tbody>
              <tr><td>&lt; 1 anno</td><td>qualsiasi</td><td>BASIC (qualsiasi asset)</td></tr>
              <tr><td>1–3 anni</td><td>bassa / media</td><td>BASIC</td></tr>
              <tr><td>2–5 anni</td><td>media / alta</td><td>PRO</td></tr>
              <tr><td>5–15 anni</td><td>alta / professionale</td><td>VALUE</td></tr>
              <tr><td>&gt; 10 anni</td><td>istituzionale / family office</td><td>VALUE</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>


  <!-- FATTURE -->
  <div id="fatture" class="panel">
    <div class="sec-head">
      <h2>&#x1F4C4; Fatture Emesse</h2>
      <div style="display:flex;gap:.6rem;align-items:center">
        <span id="fat-count" style="font-size:.8rem;color:rgba(255,255,255,.4)"></span>
        <button onclick="loadFatture()" style="background:#2C5282;border:1px solid #F6AD55;color:#F6AD55;padding:.4rem 1rem;border-radius:6px;cursor:pointer;font-size:.8rem;font-weight:600">&#x21BB; Aggiorna</button>
        <button onclick="document.getElementById('modal-fat-manuale').style.display='flex'" style="background:#276749;border:none;color:#68D391;padding:.4rem 1rem;border-radius:6px;cursor:pointer;font-size:.8rem;font-weight:600">+ Nuova Fattura</button>
        <button onclick="resetContatoreFatture()" style="background:#742a2a;border:none;color:#FC8181;padding:.4rem 1rem;border-radius:6px;cursor:pointer;font-size:.8rem;font-weight:600">&#x21BA; Reset Contatore</button>
      </div>
    </div>
    <div class="tbl-wrap">
      <table>
        <thead><tr><th>Numero Fattura</th><th>Data Emissione</th><th style="text-align:right">KB</th><th style="text-align:center">Download</th></tr></thead>
        <tbody id="fat-tbody"><tr><td colspan="4" style="text-align:center;padding:2rem;opacity:.4">Caricamento...</td></tr></tbody>
      </table>
    </div>
    <p style="font-size:.72rem;color:rgba(255,255,255,.3);margin-top:1rem">Fatture in <code>/root/FATTURE/</code> &mdash; invia al commercialista mensilmente.</p>
  </div>

  <!-- Modal Fattura Manuale -->
  <div id="modal-fat-manuale" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:9999;align-items:center;justify-content:center">
    <div style="background:#1e293b;border:1px solid rgba(246,173,85,.3);border-radius:12px;padding:2rem;width:min(520px,94vw);max-height:90vh;overflow-y:auto">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.4rem">
        <h3 style="margin:0;color:#F6AD55;font-size:1rem">&#x1F4C4; Nuova Fattura Manuale</h3>
        <button onclick="document.getElementById('modal-fat-manuale').style.display='none'" style="background:none;border:none;color:rgba(255,255,255,.5);font-size:1.4rem;cursor:pointer">&times;</button>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:.8rem">
        <div style="grid-column:1/-1">
          <label style="font-size:.75rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.3rem">Nome cliente *</label>
          <input id="fm-nome" type="text" placeholder="Mario Rossi" style="width:100%;background:#0f172a;border:1px solid rgba(246,173,85,.25);color:#e2e8f0;padding:.55rem .8rem;border-radius:6px;font-size:.9rem;box-sizing:border-box">
        </div>
        <div style="grid-column:1/-1">
          <label style="font-size:.75rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.3rem">Email cliente *</label>
          <input id="fm-email" type="email" placeholder="cliente@email.com" style="width:100%;background:#0f172a;border:1px solid rgba(246,173,85,.25);color:#e2e8f0;padding:.55rem .8rem;border-radius:6px;font-size:.9rem;box-sizing:border-box">
        </div>
        <div style="grid-column:1/-1">
          <label style="font-size:.75rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.3rem">Descrizione servizio *</label>
          <input id="fm-desc" type="text" placeholder="es. Fuerte Screener - Screener Azioni" style="width:100%;background:#0f172a;border:1px solid rgba(246,173,85,.25);color:#e2e8f0;padding:.55rem .8rem;border-radius:6px;font-size:.9rem;box-sizing:border-box">
        </div>
        <div>
          <label style="font-size:.75rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.3rem">Importo (EUR) *</label>
          <input id="fm-importo" type="number" min="0" step="0.01" placeholder="39.00" style="width:100%;background:#0f172a;border:1px solid rgba(246,173,85,.25);color:#e2e8f0;padding:.55rem .8rem;border-radius:6px;font-size:.9rem;box-sizing:border-box">
        </div>
        <div>
          <label style="font-size:.75rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.3rem">Data fattura</label>
          <input id="fm-data" type="text" placeholder="28/08/2026" style="width:100%;background:#0f172a;border:1px solid rgba(246,173,85,.25);color:#e2e8f0;padding:.55rem .8rem;border-radius:6px;font-size:.9rem;box-sizing:border-box">
        </div>
        <div style="grid-column:1/-1">
          <label style="font-size:.75rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.3rem">Periodo</label>
          <input id="fm-periodo" type="text" placeholder="September 2026" style="width:100%;background:#0f172a;border:1px solid rgba(246,173,85,.25);color:#e2e8f0;padding:.55rem .8rem;border-radius:6px;font-size:.9rem;box-sizing:border-box">
        </div>
        <div>
          <label style="font-size:.75rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.3rem">P.IVA / CF</label>
          <input id="fm-piva" type="text" placeholder="IT12345678901" style="width:100%;background:#0f172a;border:1px solid rgba(246,173,85,.25);color:#e2e8f0;padding:.55rem .8rem;border-radius:6px;font-size:.9rem;box-sizing:border-box">
        </div>
        <div>
          <label style="font-size:.75rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.3rem">Paese</label>
          <input id="fm-paese" type="text" placeholder="IT" style="width:100%;background:#0f172a;border:1px solid rgba(246,173,85,.25);color:#e2e8f0;padding:.55rem .8rem;border-radius:6px;font-size:.9rem;box-sizing:border-box">
        </div>
        <div style="grid-column:1/-1">
          <label style="font-size:.75rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.3rem">Indirizzo</label>
          <input id="fm-indirizzo" type="text" placeholder="Via Roma 1, 20100 Milano" style="width:100%;background:#0f172a;border:1px solid rgba(246,173,85,.25);color:#e2e8f0;padding:.55rem .8rem;border-radius:6px;font-size:.9rem;box-sizing:border-box">
        </div>
      </div>
      <div style="margin-top:1rem;padding:.7rem;background:rgba(39,103,73,.15);border:1px solid rgba(104,211,145,.2);border-radius:6px;display:flex;align-items:center;gap:.7rem">
        <input id="fm-email-flag" type="checkbox" style="width:16px;height:16px;accent-color:#68D391">
        <label for="fm-email-flag" style="color:#68D391;font-size:.85rem;cursor:pointer">Invia fattura via email al cliente</label>
      </div>
      <div id="fm-msg" style="display:none;margin-top:.8rem;padding:.6rem .9rem;border-radius:6px;font-size:.85rem"></div>
      <div style="display:flex;gap:.8rem;margin-top:1.4rem">
        <button onclick="document.getElementById('modal-fat-manuale').style.display='none'" style="flex:1;background:none;border:1px solid rgba(255,255,255,.2);color:rgba(255,255,255,.5);padding:.65rem;border-radius:6px;cursor:pointer;font-size:.88rem">Annulla</button>
        <button onclick="creaFatturaManuale()" style="flex:2;background:#F6AD55;border:none;color:#0f172a;padding:.65rem;border-radius:6px;cursor:pointer;font-size:.88rem;font-weight:700">Genera Fattura PDF</button>
      </div>
    </div>
  </div>

  <div style="text-align:center;padding:1.5rem 2rem;font-size:.74rem;color:rgba(255,255,255,.28);border-top:1px solid rgba(246,173,85,.1);margin-top:2rem">
    <img src="data:image/png;base64,__FUERTE_LOGO__" alt="FVC" style="height:22px;width:auto;border-radius:5px;vertical-align:middle;margin-right:6px;opacity:.6">
    Robot Trader 2026 &mdash; Fuerte Venture Capital SL &middot; CIF B23881691<br>
    Calle Puipana 3, 35640 Villaverde, Las Palmas, España &middot; <a href="mailto:info@fuerteventurecapital.com" style="color:rgba(246,173,85,.5);text-decoration:none">info@fuerteventurecapital.com</a> &middot; <a href="https://www.fuerteventurecapital.com" style="color:rgba(246,173,85,.5);text-decoration:none">www.fuerteventurecapital.com</a><br>
    &copy; 2026 Fuerte Venture Capital SL &mdash; Tutti i diritti riservati
  </div>
</div>

  <!-- ══════════ EMAIL LOG ══════════ -->
  <div id="emaillog" class="panel">
    <h2 style="margin-bottom:1rem;color:#F6AD55">&#x1F4E7; Email Log — Invii Report</h2>
    <div id="elog-stats" style="display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:1rem"></div>
    <div style="display:flex;gap:.5rem;align-items:center;margin-bottom:.8rem;flex-wrap:wrap">
      <select id="elog-filter-type" onchange="elogRender()"
              style="background:#0F172A;border:1px solid #2C5282;color:#e2e8f0;padding:.4rem .7rem;border-radius:6px;font-size:.82rem">
        <option value="">Tutti i tipi</option>
        <option value="AZIONI">AZIONI</option>
        <option value="ETF">ETF</option>
        <option value="FONDI">FONDI</option>
        <option value="FONDI_EU">FONDI_EU</option>
      </select>
      <select id="elog-filter-status" onchange="elogRender()"
              style="background:#0F172A;border:1px solid #2C5282;color:#e2e8f0;padding:.4rem .7rem;border-radius:6px;font-size:.82rem">
        <option value="">Tutti gli stati</option>
        <option value="OK">Solo OK</option>
        <option value="ERR">Solo Errori</option>
      </select>
    </div>
    <div id="elog-table"></div>
  </div>

  <!-- ══════════ TICKER FREQUENCY ══════════ -->
  <div id="tickerfreq" class="panel">
    <h2 style="margin-bottom:1rem;color:#F6AD55">&#x1F4CA; Frequenza Ticker — Stabilita del Segnale</h2>
    <p style="font-size:.82rem;color:#94a3b8;margin-bottom:1rem">
      Quante volte ogni ticker e apparso nel Top N degli ultimi 30 giorni.
      <strong style="color:#68D391">Verde</strong> = molto stabile (5+ giorni).
      <strong style="color:#F6AD55">Giallo</strong> = stabile (3-4 giorni).
    </p>
    <div style="display:flex;gap:.5rem;align-items:center;margin-bottom:.8rem;flex-wrap:wrap">
      <select id="tf-asset" onchange="tfRender()"
              style="background:#0F172A;border:1px solid #2C5282;color:#e2e8f0;padding:.4rem .7rem;border-radius:6px;font-size:.82rem">
        <option value="AZIONI">AZIONI</option>
        <option value="ETF">ETF</option>
        <option value="FONDI">FONDI</option>
        <option value="FONDI_EU">FONDI_EU</option>
      </select>
      <select id="tf-piano" onchange="tfRender()"
              style="background:#0F172A;border:1px solid #2C5282;color:#e2e8f0;padding:.4rem .7rem;border-radius:6px;font-size:.82rem">
        <option value="BASIC">BASIC</option>
        <option value="PRO">PRO</option>
        <option value="VALUE">VALUE</option>
      </select>
      <select id="tf-min" onchange="tfRender()"
              style="background:#0F172A;border:1px solid #2C5282;color:#e2e8f0;padding:.4rem .7rem;border-radius:6px;font-size:.82rem">
        <option value="1">Tutti</option>
        <option value="2">Min 2 gg</option>
        <option value="3" selected>Min 3 gg</option>
        <option value="5">Min 5 gg</option>
      </select>
    </div>
    <div id="tf-table"></div>
  </div>

  <!-- ══════════ SOCIAL ENRICHMENT ══════════ -->
  <div id="socialenrich" class="panel">
    <h2 style="margin-bottom:.5rem;color:#F6AD55">&#x1F517; Social Enrichment — Profili Prospect</h2>
    <p style="font-size:.82rem;color:#94a3b8;margin-bottom:1rem">
      Arricchimento automatico LinkedIn / Instagram / Facebook via DuckDuckGo.
      Job: <strong style="color:#68D391">domenica 02:00</strong> — batch 300 prospect/settimana.
      Priorita: <span style="color:#FC8181">clicker</span> &rarr; <span style="color:#F6AD55">reader</span> &rarr; cold.
    </p>

    <!-- KPI -->
    <div id="se-kpi" style="display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:1.2rem"></div>

    <!-- Filtri -->
    <div style="display:flex;gap:.5rem;align-items:center;margin-bottom:.8rem;flex-wrap:wrap">
      <select id="se-filter-prio" onchange="seRender()"
              style="background:#0F172A;border:1px solid #2C5282;color:#e2e8f0;padding:.4rem .7rem;border-radius:6px;font-size:.82rem">
        <option value="">Tutte le priorita</option>
        <option value="0">Clicker</option>
        <option value="1">Reader</option>
        <option value="2">Cold</option>
      </select>
      <select id="se-filter-platform" onchange="seRender()"
              style="background:#0F172A;border:1px solid #2C5282;color:#e2e8f0;padding:.4rem .7rem;border-radius:6px;font-size:.82rem">
        <option value="">Tutte le piattaforme</option>
        <option value="li">Con LinkedIn</option>
        <option value="ig">Con Instagram</option>
        <option value="fb">Con Facebook</option>
        <option value="none">Nessun profilo trovato</option>
      </select>
      <input id="se-search" type="text" placeholder="Cerca nome / email..."
             oninput="seRender()"
             style="background:#0F172A;border:1px solid #2C5282;color:#e2e8f0;padding:.4rem .7rem;border-radius:6px;font-size:.82rem;width:200px">
      <button onclick="loadSocialEnrich()"
              style="background:#2C5282;color:#fff;border:none;padding:.4rem 1rem;border-radius:6px;cursor:pointer;font-size:.82rem">
        &#x21BA; Ricarica
      </button>
    </div>

    <!-- Tabella -->
    <div id="se-table" style="overflow-x:auto"></div>

    <!-- Modal modifica URL -->
    <div id="se-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:9999;align-items:center;justify-content:center">
      <div style="background:#1E293B;border:1px solid #2C5282;border-radius:12px;padding:1.5rem;width:480px;max-width:95vw">
        <h3 style="color:#F6AD55;margin-bottom:1rem">Modifica URL Social</h3>
        <input id="se-modal-email" type="hidden">
        <div style="margin-bottom:.8rem">
          <label style="font-size:.82rem;color:#94a3b8;display:block;margin-bottom:.3rem">LinkedIn URL</label>
          <input id="se-modal-li" type="url" placeholder="https://linkedin.com/in/..."
                 style="width:100%;background:#0F172A;border:1px solid #2C5282;color:#e2e8f0;padding:.5rem .7rem;border-radius:6px;font-size:.85rem;box-sizing:border-box">
        </div>
        <div style="margin-bottom:.8rem">
          <label style="font-size:.82rem;color:#94a3b8;display:block;margin-bottom:.3rem">Instagram URL</label>
          <input id="se-modal-ig" type="url" placeholder="https://instagram.com/..."
                 style="width:100%;background:#0F172A;border:1px solid #2C5282;color:#e2e8f0;padding:.5rem .7rem;border-radius:6px;font-size:.85rem;box-sizing:border-box">
        </div>
        <div style="margin-bottom:1rem">
          <label style="font-size:.82rem;color:#94a3b8;display:block;margin-bottom:.3rem">Facebook URL</label>
          <input id="se-modal-fb" type="url" placeholder="https://facebook.com/..."
                 style="width:100%;background:#0F172A;border:1px solid #2C5282;color:#e2e8f0;padding:.5rem .7rem;border-radius:6px;font-size:.85rem;box-sizing:border-box">
        </div>
        <div style="display:flex;gap:.5rem;justify-content:flex-end">
          <button onclick="document.getElementById('se-modal').style.display='none'"
                  style="background:#374151;color:#e2e8f0;border:none;padding:.5rem 1.2rem;border-radius:6px;cursor:pointer">
            Annulla
          </button>
          <button onclick="seSaveModal()"
                  style="background:#276749;color:#fff;border:none;padding:.5rem 1.2rem;border-radius:6px;cursor:pointer;font-weight:600">
            Salva
          </button>
        </div>
      </div>
    </div>
  </div>

<script>
// ═══════════════════════════════════════════════
// GLOBALS
// ═══════════════════════════════════════════════
var _sv = null;
var _tableData  = {};   // {tipo: rows[]}
var _tableCols  = {};   // {tipo: cols[]}
var _sortState  = {};   // {tipo: {col: null, dir: -1}}
var _logInt = null;
var _loaded = {};

var ASSETS = ['azioni','etf','fondi','ordini'];
var TIERS  = ['basic','pro','value'];
var ICONS  = {azioni:'📈',etf:'📦',fondi:'🏦'};

var PLABELS = {
  ev_fcf_max:'EV/FCF max', price_book_max:'P/B max',
  roe_min:'ROE min', net_debt_ebitda_max:'ND/EBITDA max',
  ter_max:'TER max (%)', sharpe_min:'Sharpe min',
  volume_min:'Volume/AUM min', performance_1y_min:'Perf 1Y min (%)'
};
var PSTEP = {
  ev_fcf_max:0.5, price_book_max:0.05, roe_min:0.01, net_debt_ebitda_max:0.1,
  ter_max:0.05, sharpe_min:0.05, volume_min:10000, performance_1y_min:0.01
};

// Etichette parametri screener globali (parametri.json)
var SP_LABELS = {
  ev_fcf_max:'EV/FCF max', price_book_max:'P/B max',
  roe_min:'ROE min (%)', net_debt_ebitda_max:'Net Debt/EBITDA max',
  ter_max:'TER max (%)', sharpe_min:'Sharpe min',
  volume_min:'Volume min', performance_1y_min:'Perf 1Y min',
  min_age_years:'Età minima ETF (anni)',
  only_accumulating:'Solo accumulazione (ACC)',
  only_physical:'Solo replica fisica'
};
var SP_STEP = {
  ev_fcf_max:0.5, price_book_max:0.05, roe_min:0.01, net_debt_ebitda_max:0.1,
  ter_max:0.05, sharpe_min:0.05, volume_min:10000, performance_1y_min:0.01,
  min_age_years:1
};

// ─── CLIENTI ─────────────────────────────────────────────────
var _clienti = null;

function loadClienti(){
  fetch('/api/clienti').then(function(r){
    if(!r.ok||r.redirected) throw new Error('Sessione scaduta');
    return r.json();
  }).then(function(data){
    _clienti = data;
    renderClienti();
  }).catch(function(e){showMsg('cl-msg','❌ '+e.message,'err');});
}

function renderClienti(){
  if(!_clienti) return;
  var all = (_clienti.tester||[]).concat(_clienti.clienti||[]);
  var nTester  = (_clienti.tester||[]).length;
  var nClienti = (_clienti.clienti||[]).length;
  var nAttivi  = all.filter(function(c){return c.stato==='ATTIVO';}).length;

  // Stats KPI
  var statsHtml = [
    ['👥 Totale', all.length, '#4A90D9'],
    ['🧪 Tester',  nTester,   '#F6AD55'],
    ['💳 Clienti', nClienti,  '#68D391'],
    ['✅ Attivi',  nAttivi,   '#48BB78'],
  ].map(function(s){
    return '<div style="background:rgba(255,255,255,.05);border-radius:10px;padding:.7rem 1.2rem;min-width:110px;text-align:center">'
         + '<div style="font-size:.75rem;opacity:.55;margin-bottom:.2rem">'+s[0]+'</div>'
         + '<div style="font-size:1.6rem;font-weight:700;color:'+s[2]+'">'+s[1]+'</div></div>';
  }).join('');
  document.getElementById('cl-stats').innerHTML = statsHtml;

  // Aggiorna contatore destinatari email nella home
  var nDest = all.filter(function(c){
    return c.stato !== 'SOSPESO' && (
      (c.piano_azioni && c.piano_azioni !== 'NONE') ||
      (c.piano_etf    && c.piano_etf    !== 'NONE') ||
      (c.piano_fondi  && c.piano_fondi  !== 'NONE')
    );
  }).length + 1; // +1 admin (rioluc63)
  var _sd = document.getElementById('stat-dest');
  if(_sd) _sd.textContent = nDest + ' destinatari';

  // Tabella
  var headers = ['Nome','Email','Paese','Azioni','ETF','Fondi','Ordini','WealthOS','Stato','Registrato','Operazioni'];
  var headHtml = headers.map(function(h){
    return '<th style="background:#2C5282;color:#fff;padding:.5rem .8rem;text-align:left;font-size:.82rem">'+h+'</th>';
  }).join('');
  document.getElementById('cl-head').innerHTML = headHtml;

  var pianoColor = {NONE:'#555',BASIC:'#4A90D9',PRO:'#F6AD55',VALUE:'#68D391'};
  var statoColor = {TESTER:'#F6AD55',ATTIVO:'#68D391',SOSPESO:'#FC8181',SCADUTO:'#9F7AEA'};
  var wosColor   = {NONE:'#444',ATTIVO:'#c9a84c',SOSPESO:'#FC8181'};

  function badge(val, colors){
    var c = colors[val]||'#888';
    return '<span style="background:'+c+'22;color:'+c+';border:1px solid '+c+'44;border-radius:4px;padding:.15rem .45rem;font-size:.75rem;font-weight:600">'+val+'</span>';
  }

  // Mappa: categoria → indice reale nella lista originale
  var _clMap = [];
  (_clienti.tester||[]).forEach(function(c,i){_clMap.push({cat:'tester',idx:i,c:c});});
  (_clienti.clienti||[]).forEach(function(c,i){_clMap.push({cat:'clienti',idx:i,c:c});});

  var PAESE_FLAG = {IT:'🇮🇹',ES:'🇪🇸',FR:'🇫🇷',DE:'🇩🇪',UK:'🇬🇧'};

  var rows = _clMap.map(function(entry,i){
    var c=entry.c, cat=entry.cat, idx=entry.idx;
    var bg = i%2===0 ? 'rgba(255,255,255,.02)' : 'transparent';
    var df = c.dati_fiscali || {};
    var paeseCell = df.paese ? (PAESE_FLAG[df.paese]||'') + ' ' + df.paese : '<span style="opacity:.3">—</span>';
    var cfOk = df.codice_fiscale ? '✓' : '';
    var anagBtn = '<button class="btn" style="padding:.2rem .55rem;font-size:.75rem;border-color:rgba(179,151,90,.4);color:#B3975A" '
      +'onclick="mostraModalAnagrafica(\''+cat+'\','+idx+')" title="Dati anagrafici e fiscali">📋'+cfOk+'</button>';
    var attivaBtn = (c.stato!=='ATTIVO')
      ? '<button class="btn btn-gr" style="padding:.2rem .6rem;font-size:.75rem" onclick="mostraModalAttiva(\''+cat+'\','+idx+',\''+c.nome+'\',\''+c.email+'\',\''+c.piano_azioni+'\',\''+c.piano_etf+'\',\''+c.piano_fondi+'\',\''+c.piano_ordini+'\',\''+(c.piano_wealthos||'NONE')+'\')">Attiva</button>'
      : '<span style="color:#68D391;font-size:.78rem">✓</span>';
    var fattBtn = (c.numero_fattura)
      ? '<a href="/api/fattura/'+c.numero_fattura+'" target="_blank" class="btn" style="padding:.2rem .5rem;font-size:.72rem;border-color:rgba(246,173,85,.35);color:#F6AD55;text-decoration:none" title="Scarica fattura '+c.numero_fattura+'">🧾</a>'
      : '';
    var eliminaBtn = '<button class="btn" style="padding:.2rem .5rem;font-size:.72rem;border-color:rgba(239,68,68,.35);color:#f87171" onclick="eliminaTester(\''+cat+'\','+idx+',\''+c.email+'\')" title="Elimina cliente">🗑</button>';
    var waOn = c.whatsapp_optin === true;
    var waBtn = '<button class="btn" style="padding:.2rem .5rem;font-size:.72rem;'
      +(waOn ? 'border-color:#25D36644;color:#25D366' : 'border-color:#55555566;color:#666')
      +'" onclick="toggleWhatsapp(\''+cat+'\','+idx+','+waOn+')" title="'+(waOn?'WhatsApp attivo — clicca per disattivare':'Attiva notifiche WhatsApp')+'">📱'+(waOn?'✓':'')+'</button>';
    var wosStatus = c.piano_wealthos || 'NONE';
    var wosBtn = (wosStatus === 'ATTIVO')
      ? '<a href="http://localhost:3099" target="_blank" class="btn" style="padding:.2rem .5rem;font-size:.72rem;border-color:#c9a84c55;color:#c9a84c;text-decoration:none" title="Apri WealthOS Admin">⚡</a>'
      : '<a href="http://localhost:3099" target="_blank" class="btn" style="padding:.2rem .5rem;font-size:.72rem;border-color:#55555566;color:#666;text-decoration:none" title="Attiva WealthOS">W</a>';
    return '<tr style="background:'+bg+'">'
      +'<td style="padding:.45rem .8rem;font-size:.84rem">'+(c.cognome?c.nome+' '+c.cognome:c.nome)+(c.codice_cliente?'<br><span style="font-size:.68rem;color:#F6AD55;opacity:.6;font-family:monospace">'+c.codice_cliente+'</span>':'')+'</td>'
      +'<td style="padding:.45rem .8rem;font-size:.82rem;opacity:.75">'+c.email+'</td>'
      +'<td style="padding:.45rem .8rem;font-size:.82rem">'+paeseCell+'</td>'
      +'<td style="padding:.45rem .8rem">'+badge(c.piano_azioni||'NONE',pianoColor)+'</td>'
      +'<td style="padding:.45rem .8rem">'+badge(c.piano_etf||'NONE',pianoColor)+'</td>'
      +'<td style="padding:.45rem .8rem">'+badge(c.piano_fondi||'NONE',pianoColor)+'</td>'
      +'<td style="padding:.45rem .8rem">'+badge(c.piano_ordini||'NONE',pianoColor)+'</td>'
      +'<td style="padding:.45rem .8rem">'+badge(wosStatus,wosColor)+' '+wosBtn+'</td>'
      +'<td style="padding:.45rem .8rem">'+badge(c.stato||'—',statoColor)+'</td>'
      +'<td style="padding:.45rem .8rem;font-size:.78rem;opacity:.6">'+c.data_registrazione+'</td>'
      +'<td style="padding:.45rem .8rem;display:flex;gap:.35rem">'+anagBtn+' '+attivaBtn+' '+fattBtn+' '+waBtn+' '+eliminaBtn+'</td>'
      +'</tr>';
  }).join('');
  document.getElementById('cl-body').innerHTML = rows || '<tr><td colspan="11" style="padding:2rem;text-align:center;opacity:.4">Nessun cliente</td></tr>';
}

// ─── MODALS CLIENTI ──────────────────────────────────────────
var _atCat='', _atIdx=0;

function chiudiModals(){
  document.getElementById('modal-aggiungi').style.display='none';
  document.getElementById('modal-attiva').style.display='none';
  document.getElementById('modal-anagrafica').style.display='none';
}

// ─── MODAL ANAGRAFICA / DATI FISCALI ─────────────────────────
var _anCat='', _anIdx=0;

var PAESE_CFG = {
  IT:{nome:'🇮🇹 Italia',      cf:'Codice Fiscale',   ph:'RSSMRA80A01H501U', piva:true},
  ES:{nome:'🇪🇸 Spagna',      cf:'DNI / NIE',        ph:'12345678A',        piva:false},
  FR:{nome:'🇫🇷 Francia',     cf:'Numéro Fiscal',    ph:'1234567890123',    piva:false},
  DE:{nome:'🇩🇪 Germania',    cf:'Steuer-ID',        ph:'12345678901',      piva:false},
  UK:{nome:'🇬🇧 Regno Unito', cf:'NI Number / UTR',  ph:'AB123456C',        piva:false},
};

function aggiornaPaeseForm(){
  var paese = document.getElementById('an-paese').value;
  var cfg = PAESE_CFG[paese] || {};
  var cfLbl = document.getElementById('an-cf-label');
  var cfInp = document.getElementById('an-cf');
  var pivaRow = document.getElementById('an-piva-row');
  if(cfg.cf){ cfLbl.textContent=cfg.cf; cfInp.placeholder=cfg.ph||''; }
  if(pivaRow) pivaRow.style.display = cfg.piva ? '' : 'none';
}

function eliminaTester(cat, idx, email){
  if(!confirm('Eliminare il tester ' + email + '?')) return;
  fetch('/api/clienti/elimina',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({cat:cat, idx:idx, email:email})
  }).then(function(r){return r.json();}).then(function(res){
    if(res.ok){ _clienti=null; loadClienti(); showMsg('cl-msg','🗑 Tester eliminato','ok'); }
    else showMsg('cl-msg','❌ '+res.msg,'err');
  });
}

function toggleWhatsapp(cat, idx, current){
  var label = current ? 'Disattivare le notifiche WhatsApp per questo cliente?' : 'Attivare le notifiche WhatsApp per questo cliente?\n(Il cliente deve aver dato consenso esplicito)';
  if(!confirm(label)) return;
  fetch('/api/clienti/whatsapp',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({cat:cat, idx:idx, optin:!current})
  }).then(function(r){return r.json();}).then(function(res){
    if(res.ok){ _clienti=null; loadClienti(); showMsg('cl-msg', current ? '📵 WhatsApp disattivato' : '📱 WhatsApp attivato','ok'); }
    else showMsg('cl-msg','❌ '+res.msg,'err');
  });
}

function mostraModalAnagrafica(cat, idx){
  _anCat=cat; _anIdx=idx;
  var entry = null;
  var lista = cat==='tester' ? (_clienti.tester||[]) : (_clienti.clienti||[]);
  entry = lista[idx];
  if(!entry) return;
  var df = entry.dati_fiscali || {};
  var set = function(id,val){ var el=document.getElementById(id); if(el) el.value=val||''; };
  set('an-nome',    entry.nome);
  set('an-cognome', entry.cognome || '');
  set('an-email',   entry.email);
  set('an-paese',   df.paese||'IT');
  set('an-nascita', df.data_nascita||'');
  set('an-indirizzo',df.indirizzo||'');
  set('an-cap',     df.cap||'');
  set('an-citta',   df.citta||'');
  set('an-cf',      df.codice_fiscale||'');
  set('an-tel',     df.telefono||'');
  set('an-piva',    df.p_iva||'');
  aggiornaPaeseForm();
  document.getElementById('modal-anagrafica').style.display='flex';
}

function salvaAnagrafica(){
  fetch('/api/clienti/anagrafica',{method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      categoria:      _anCat,
      index:          _anIdx,
      cognome:        document.getElementById('an-cognome').value.trim(),
      paese:          document.getElementById('an-paese').value,
      data_nascita:   document.getElementById('an-nascita').value.trim(),
      indirizzo:      document.getElementById('an-indirizzo').value.trim(),
      cap:            document.getElementById('an-cap').value.trim(),
      citta:          document.getElementById('an-citta').value.trim(),
      codice_fiscale: document.getElementById('an-cf').value.trim(),
      telefono:       document.getElementById('an-tel').value.trim(),
      p_iva:          document.getElementById('an-piva').value.trim(),
    })
  }).then(function(r){return r.json();}).then(function(res){
    chiudiModals();
    if(res.ok){ showMsg('cl-msg','✅ Dati fiscali salvati','ok'); _clienti=null; loadClienti(); }
    else showMsg('cl-msg','❌ '+res.msg,'err');
  });
}

function mostraModalAggiungi(){
  document.getElementById('modal-aggiungi').style.display='flex';
}

function confermaAggiungi(){
  var nome=document.getElementById('ag-nome').value.trim();
  var cognome=document.getElementById('ag-cognome').value.trim();
  var email=document.getElementById('ag-email').value.trim();
  if(!nome||!email){alert('Nome ed email obbligatori');return;}
  fetch('/api/clienti/aggiungi',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
      nome:nome, cognome:cognome, email:email,
      piano_azioni:document.getElementById('ag-azioni').value,
      piano_etf:document.getElementById('ag-etf').value,
      piano_fondi:document.getElementById('ag-fondi').value,
      piano_ordini:document.getElementById('ag-ordini').value,
      piano_wealthos:document.getElementById('ag-wealthos').value,
    })
  }).then(function(r){return r.json();}).then(function(res){
    if(res.ok){chiudiModals();_clienti=null;loadClienti();showMsg('cl-msg','✅ Cliente aggiunto','ok');}
    else showMsg('cl-msg','❌ '+res.msg,'err');
  });
}

function mostraModalAttiva(cat,idx,nome,email,pAz,pEtf,pFondi,pOrd,pWos){
  _atCat=cat; _atIdx=idx;
  document.getElementById('at-info').textContent=nome+' — '+email;
  var sel=function(id,val){
    var s=document.getElementById(id);
    for(var i=0;i<s.options.length;i++) s.options[i].selected=(s.options[i].value===val);
  };
  sel('at-azioni',pAz||'NONE');
  sel('at-etf',pEtf||'NONE');
  sel('at-fondi',pFondi||'NONE');
  sel('at-ordini',pOrd||'NONE');
  sel('at-wealthos',pWos||'NONE');
  document.getElementById('modal-attiva').style.display='flex';
}

function confermaAttiva(){
  fetch('/api/clienti/attiva',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
      categoria:_atCat, index:_atIdx,
      piano_azioni:document.getElementById('at-azioni').value,
      piano_etf:document.getElementById('at-etf').value,
      piano_fondi:document.getElementById('at-fondi').value,
      piano_ordini:document.getElementById('at-ordini').value,
      piano_wealthos:document.getElementById('at-wealthos').value,
    })
  }).then(function(r){return r.json();}).then(function(res){
    chiudiModals();
    if(res.ok){
      _clienti=null; loadClienti();
      if(res.email_inviata){
        showMsg('cl-msg','✅ Cliente attivato — credenziali inviate via email.','ok');
      } else {
        var pwd = res.password_temp;
        alert('🔑 PASSWORD TEMPORANEA:\n\n' + pwd + '\n\nAnnotala ora — non verrà mostrata di nuovo!\nURL cliente: __BASE_URL__/client-login');
        // Mostra anche il box persistente dopo il reload DOM
        setTimeout(function(){
          var box=document.getElementById('cl-pwd-box');
          if(box){
            document.getElementById('cl-pwd-val').textContent=pwd;
            box.style.display='block';
            box.scrollIntoView({behavior:'smooth',block:'center'});
          }
        }, 800);
        showMsg('cl-msg','⚠️ Email NON inviata — vedi il riquadro arancione con la password.','err');
      }
    } else showMsg('cl-msg','❌ '+res.msg,'err');
  });
}

// ─── IMPORT / EXPORT CSV CLIENTI ─────────────────────────────
function exportClienti(){
  window.location.href = '/api/clienti/export';
}

function importClienti(input){
  var file = input.files[0];
  if(!file) return;
  var reader = new FileReader();
  reader.onload = function(e){
    var csv = e.target.result;
    fetch('/api/clienti/import',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({csv_content: csv})
    }).then(function(r){return r.json();}).then(function(res){
      input.value = '';  // reset input file
      if(!res.ok){ showMsg('cl-msg','❌ '+res.msg,'err'); return; }
      var msg = '✅ Importati: '+res.aggiunti;
      if(res.duplicati) msg += ' · Duplicati saltati: '+res.duplicati;
      if(res.errori && res.errori.length) msg += ' · ⚠️ '+res.errori.length+' righe con errori';
      showMsg('cl-msg', msg, 'ok');
      if(res.aggiunti > 0){ _clienti=null; loadClienti(); }
      // Mostra eventuali errori di riga in console
      if(res.errori && res.errori.length) console.warn('[Import CSV]', res.errori);
    }).catch(function(e){ showMsg('cl-msg','❌ '+e.message,'err'); });
  };
  reader.readAsText(file, 'UTF-8');
}

// ═══════════════════════════════════════════════
// CRM & MARKETING — Sotto-tab
// ═══════════════════════════════════════════════
var _crmSubActive = 'clienti';

function loadFatture(){
  var tb=document.getElementById('fat-tbody');
  if(!tb) return;
  fetch('/api/fatture').then(function(r){return r.json();}).then(function(d){
    document.getElementById('fat-count').textContent=d.length+' fatture totali';
    if(!d.length){tb.innerHTML='<tr><td colspan="4" style="text-align:center;padding:2rem;opacity:.4">Nessuna fattura trovata</td></tr>';return;}
    tb.innerHTML=d.map(function(f){
      return '<tr>'+
        '<td><strong style="color:#F6AD55">'+f.numero+'</strong></td>'+
        '<td>'+f.data+'</td>'+
        '<td style="text-align:right;font-family:monospace">'+f.size_kb+' KB</td>'+
        '<td style="text-align:center"><a href="/api/fattura/'+f.numero+'" download style="background:#276749;color:#68D391;padding:.3rem .8rem;border-radius:5px;font-size:.78rem;font-weight:700;text-decoration:none">PDF</a></td>'+
      '</tr>';
    }).join('');
  }).catch(function(){tb.innerHTML='<tr><td colspan="4" style="color:#fc8181;text-align:center;padding:1rem">Errore</td></tr>';});
}

function creaFatturaManuale(){
  var nome=document.getElementById('fm-nome').value.trim();
  var email=document.getElementById('fm-email').value.trim();
  var desc=document.getElementById('fm-desc').value.trim();
  var imp=parseFloat(document.getElementById('fm-importo').value)||0;
  var msg=document.getElementById('fm-msg');
  if(!nome||!email||!desc||!imp){
    msg.style.display='block';msg.style.background='rgba(114,28,36,.4)';msg.style.color='#fc8181';
    msg.textContent='Compila i campi obbligatori: nome, email, descrizione, importo.';return;
  }
  var btn=document.querySelector('#modal-fat-manuale button:last-child');
  btn.disabled=true;btn.textContent='Generazione...';
  fetch('/api/fatture/manuale',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    nome:nome,email:email,descrizione:desc,importo:imp,
    data_fattura:document.getElementById('fm-data').value.trim(),
    periodo:document.getElementById('fm-periodo').value.trim(),
    piva:document.getElementById('fm-piva').value.trim(),
    paese:document.getElementById('fm-paese').value.trim(),
    indirizzo:document.getElementById('fm-indirizzo').value.trim(),
    invia_email:document.getElementById('fm-email-flag').checked
  })}).then(function(r){return r.json();}).then(function(res){
    btn.disabled=false;btn.textContent='Genera Fattura PDF';
    if(res.ok){
      msg.style.display='block';msg.style.background='rgba(39,103,73,.4)';msg.style.color='#68D391';
      msg.innerHTML='✅ Fattura <strong>'+res.numero+'</strong> generata'+(res.email_inviata?' — email inviata.':' — email NON inviata (SMTP non configurato).');
      loadFatture();
      setTimeout(function(){window.open('/api/fattura/'+res.numero,'_blank');},400);
    } else {
      msg.style.display='block';msg.style.background='rgba(114,28,36,.4)';msg.style.color='#fc8181';
      msg.textContent='Errore: '+(res.msg||'sconosciuto');
    }
  }).catch(function(e){
    btn.disabled=false;btn.textContent='Genera Fattura PDF';
    msg.style.display='block';msg.style.background='rgba(114,28,36,.4)';msg.style.color='#fc8181';
    msg.textContent='Errore di rete.';
  });
}

function resetContatoreFatture(){
  if(!confirm('⚠️ ATTENZIONE\n\nVerranno eliminati tutti i PDF nella cartella FATTURE/ e il contatore sarà azzerato.\n\nLa prossima fattura sarà FVC-'+new Date().getFullYear()+'-0001.\n\nConfermi?')) return;
  fetch('/api/fatture/reset-contatore',{method:'POST'}).then(function(r){return r.json();}).then(function(res){
    if(res.ok){alert('✅ '+res.msg);loadFatture();}
    else{alert('Errore: '+(res.msg||'sconosciuto'));}
  });
}

function switchCrmTab(el, tab) {
  document.querySelectorAll('.crm-subtab').forEach(function(t){t.classList.remove('active');});
  if(el) el.classList.add('active');
  document.querySelectorAll('.crm-sub').forEach(function(p){p.style.display='none';});
  var sub = document.getElementById('crm-' + tab);
  if(sub) sub.style.display = '';
  _crmSubActive = tab;
  if(tab === 'clienti' && !_clienti) loadClienti();
  if(tab === 'pipeline') loadPipelineData();
  if(tab === 'campagne') { renderCampagne(); loadCampagna(); }
  if(tab === 'social') renderSocial();
  if(tab === 'whatsapp') renderWhatsappSub();
  if(tab === 'prospect') loadProspect();
  if(tab === 'calendario') renderCalendario();
}

function renderPipeline() {
  loadPipelineData();
}

var _brevo_campagne = null;
var _brevo_liste = null;
var _brevo_template = null;
var _brevo_camp_names = {};

function _htmlAzioniLancio() {
  return '<div class="box" style="margin-bottom:1rem;border:1px solid rgba(246,173,85,.25)">'
    +'<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.8rem">'
    +'<div><div style="font-size:.9rem;font-weight:700;color:#F6AD55;margin-bottom:.25rem">⭐ Offerta Early Adopter</div>'
    +'<div style="font-size:.78rem;color:rgba(255,255,255,.5)">Invia email personalizzata ai Tester — 50% sconto per 3 mesi (scade 1° set 2026)</div></div>'
    +'<button id="btn-early-adopter" onclick="inviaEarlyAdopter()" style="background:#F6AD55;border:none;border-radius:6px;color:#0a0f1e;padding:.5rem 1.2rem;font-size:.85rem;font-weight:700;cursor:pointer;white-space:nowrap">📩 Invia a Tester ora</button>'
    +'</div></div>'
    +'<div class="box" style="margin-bottom:1rem;border:1px solid rgba(96,165,250,.25)">'
    +'<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.8rem">'
    +'<div><div style="font-size:.9rem;font-weight:700;color:#60a5fa;margin-bottom:.25rem">🚀 Lancio — Importa Prospect in Brevo</div>'
    +'<div style="font-size:.78rem;color:rgba(255,255,255,.5)">Crea lista Brevo e importa i 2.435 prospect — operazione sicura, aggiorna contatti esistenti</div></div>'
    +'<button id="btn-import-prospect" onclick="importaProspectBrevo()" style="background:#2C5282;border:none;border-radius:6px;color:#60a5fa;padding:.5rem 1.2rem;font-size:.85rem;font-weight:700;cursor:pointer;white-space:nowrap">⬆ Importa in Brevo</button>'
    +'</div></div>'
    +'<div class="box" style="margin-bottom:1rem;border:1px solid rgba(104,211,145,.25)">'
    +'<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.8rem">'
    +'<div><div style="font-size:.9rem;font-weight:700;color:#68D391;margin-bottom:.25rem">📧 Campagna Lancio — Email ai 2.435 Prospect</div>'
    +'<div style="font-size:.78rem;color:rgba(255,255,255,.5)">Crea la campagna Brevo con il template email di lancio — salvata come bozza, revisiona prima di inviare</div></div>'
    +'<button onclick="mostraLancioCampagna()" style="background:rgba(104,211,145,.15);border:1px solid rgba(104,211,145,.4);border-radius:6px;color:#68D391;padding:.5rem 1.2rem;font-size:.85rem;font-weight:700;cursor:pointer;white-space:nowrap">📧 Crea Campagna Lancio</button>'
    +'</div></div>';
}

function renderCampagne() {
  var el = document.getElementById('campagne-content');
  // I bottoni azione sono sempre visibili, indipendentemente da Brevo
  el.innerHTML = _htmlAzioniLancio()
    +'<div id="brevo-campagne-table"><div style="opacity:.5;padding:1.5rem;text-align:center">Caricamento campagne Brevo...</div></div>';
  fetch('/api/brevo/campagne').then(function(r){return r.json();}).then(function(d){
    var tbl = document.getElementById('brevo-campagne-table');
    if(!tbl) return;
    if(!d.ok){
      tbl.innerHTML = '<div class="box">'
        +'<h3 style="color:#F6AD55;margin-bottom:1rem">📧 Campagne Email — Brevo</h3>'
        +'<div style="background:rgba(252,129,129,.08);border:1px solid rgba(252,129,129,.3);border-radius:8px;padding:.8rem 1rem;margin-bottom:1rem;font-size:.85rem">'
        +'⚠️ ' + (d.msg || 'Brevo non configurato')
        +'</div>'
        +'<div style="opacity:.65;font-size:.85rem;line-height:2">'
        +'• Invio newsletter segmentate BASIC / PRO / VALUE<br>'
        +'• Avanzamento automatico dei prospect che aprono le email<br>'
        +'• Tracciamento aperture, click e conversioni'
        +'</div></div>'
        +'<div class="box"><h3 style="color:#68D391;margin-bottom:.8rem">✅ Email Report Automatiche — attive</h3>'
        +'<div style="font-size:.84rem;line-height:1.9;opacity:.75">'
        +'<strong>📈 Azioni:</strong> ogni notte alle 23:00 — lun/ven<br>'
        +'<strong>📦 ETF + Fondi:</strong> ogni notte alle 23:30 — lun / mer / ven<br>'
        +'<strong>Destinatari:</strong> automatici in base al piano abbonamento'
        +'</div></div>';
      return;
    }
    _brevo_campagne = d.campagne || [];
    tbl.innerHTML = '';
    renderCampagneTable(_brevo_campagne);
  }).catch(function(e){
    var tbl = document.getElementById('brevo-campagne-table');
    if(tbl) tbl.innerHTML = '<div class="box"><p style="color:#ef4444">Errore caricamento: '+e+'</p></div>';
  });
}

function inviaEarlyAdopter() {
  var btn = document.getElementById('btn-early-adopter');
  if(btn){ btn.disabled = true; btn.textContent = '⏳ Invio in corso...'; }
  fetch('/api/marketing/early-adopter', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'})
    .then(function(r){ return r.json(); })
    .then(function(d){
      if(btn){ btn.disabled = false; btn.textContent = '📩 Invia a Tester ora'; }
      if(d.ok){
        var righe = (d.dettaglio||[]).map(function(r){
          return '<li style="margin:.2rem 0;font-size:.82rem;color:'+(r.ok?'#68D391':'#ef4444')+'">'
            +(r.ok ? '✅' : '❌')+' '+r.email+(r.ok?' — '+r.piani+' piani':' — '+(r.msg||'errore'))+'</li>';
        }).join('');
        alert('✅ Inviate: '+d.inviati+' / '+d.totale+'\n\nDettaglio:\n'
          +(d.dettaglio||[]).map(function(r){ return (r.ok?'✅':'❌')+' '+r.email; }).join('\n'));
      } else {
        alert('❌ Errore: '+(d.msg||'sconosciuto'));
      }
    })
    .catch(function(e){
      if(btn){ btn.disabled = false; btn.textContent = '📩 Invia a Tester ora'; }
      alert('Errore di rete: '+e);
    });
}

var _campagna_data = null;

function loadCampagna() {
  var sel = document.getElementById('camp-mese-sel');
  var mese = sel ? sel.value : '2026-09';
  var tbody = document.getElementById('camp-tbody');
  var kpi   = document.getElementById('camp-kpi');
  if(tbody) tbody.innerHTML = '<tr><td colspan="7" style="padding:1.5rem;opacity:.4;text-align:center">Caricamento...</td></tr>';

  fetch('/api/campagna/calendario').then(function(r){return r.json();}).then(function(d){
    if(!d.ok){ if(tbody) tbody.innerHTML='<tr><td colspan="7" style="color:#ef4444;padding:1rem">'+d.error+'</td></tr>'; return; }
    _campagna_data = d.campagne || [];
    var camp = _campagna_data.find(function(c){return c.mese === mese;});
    if(!camp){ if(tbody) tbody.innerHTML='<tr><td colspan="7" style="opacity:.4;padding:1rem;text-align:center">Mese non trovato</td></tr>'; return; }

    // KPI
    if(kpi){
      var inviati   = camp.giorni.filter(function(g){return g.stato==='inviato';}).length;
      var oggi_g    = camp.giorni.filter(function(g){return g.stato==='oggi';}).length;
      var programmati = camp.giorni.filter(function(g){return g.stato==='programmato';}).length;
      var TEMA_LABELS = {'SALARY_TRAP':'SALARY TRAP','WEALTHOS_PROMO':'WEALTHOS','TREND_MOBILIARE':'TREND MOBILIARE'};
      kpi.innerHTML =
        '<div style="background:rgba(246,173,85,.08);border:1px solid rgba(246,173,85,.2);border-radius:8px;padding:.65rem 1rem">'
          +'<div style="font-size:.7rem;color:rgba(255,255,255,.4);text-transform:uppercase;letter-spacing:.05em">Tema</div>'
          +'<div style="font-size:.95rem;font-weight:700;color:#F6AD55;margin-top:.2rem">'+(TEMA_LABELS[camp.tema]||camp.tema)+'</div>'
          +'<div style="font-size:.72rem;color:rgba(255,255,255,.35);margin-top:.1rem">'+camp.lang_principale+'</div>'
        +'</div>'
        +'<div style="background:rgba(104,211,145,.07);border:1px solid rgba(104,211,145,.2);border-radius:8px;padding:.65rem 1rem">'
          +'<div style="font-size:.7rem;color:rgba(255,255,255,.4);text-transform:uppercase;letter-spacing:.05em">Inviati</div>'
          +'<div style="font-size:1.3rem;font-weight:700;color:#68D391;margin-top:.2rem">'+inviati+'</div>'
          +'<div style="font-size:.72rem;color:rgba(255,255,255,.35)">× 250 = '+(inviati*250).toLocaleString()+' email</div>'
        +'</div>'
        +'<div style="background:rgba(96,165,250,.07);border:1px solid rgba(96,165,250,.2);border-radius:8px;padding:.65rem 1rem">'
          +'<div style="font-size:.7rem;color:rgba(255,255,255,.4);text-transform:uppercase;letter-spacing:.05em">Programmati</div>'
          +'<div style="font-size:1.3rem;font-weight:700;color:#60a5fa;margin-top:.2rem">'+programmati+'</div>'
          +'<div style="font-size:.72rem;color:rgba(255,255,255,.35)">rimanenti del mese</div>'
        +'</div>'
        +'<div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:8px;padding:.65rem 1rem">'
          +'<div style="font-size:.7rem;color:rgba(255,255,255,.4);text-transform:uppercase;letter-spacing:.05em">Totale mese</div>'
          +'<div style="font-size:1.3rem;font-weight:700;color:#e0e0e0;margin-top:.2rem">'+camp.totale_email.toLocaleString()+'</div>'
          +'<div style="font-size:.72rem;color:rgba(255,255,255,.35)">'+camp.giorni.length+' gg × 250/gg</div>'
        +'</div>';
    }

    // Tabella giorni
    var STATO_COLOR = {inviato:'#68D391', oggi:'#F6AD55', programmato:'#60a5fa', scaduto:'rgba(255,255,255,.25)'};
    var STATO_ICON  = {inviato:'✅', oggi:'📅', programmato:'🕐', scaduto:'—'};
    var VARIANTE_LABEL = {PAIN_HOOK:'🎯 Pain Hook', SOLUTION:'💡 Soluzione', SOCIAL_PROOF:'📣 Prova Sociale', CTA:'🚀 CTA'};
    var html = '';
    camp.giorni.forEach(function(g){
      var col = STATO_COLOR[g.stato] || 'rgba(255,255,255,.4)';
      var icon = STATO_ICON[g.stato] || '—';
      var isOggi = g.stato === 'oggi';
      var rowBg  = isOggi ? 'background:rgba(246,173,85,.04);' : '';
      var canSend = (g.stato === 'programmato' || g.stato === 'oggi');
      var btnInvia = canSend
        ? '<button onclick="inviaCampagna(\''+mese+'\',\''+g.data+'\')" style="background:#276749;border:none;border-radius:5px;color:#68D391;padding:.2rem .55rem;font-size:.72rem;font-weight:600;cursor:pointer">▶ Invia</button>'
        : '<span style="opacity:.25;font-size:.72rem">—</span>';
      var statoExtra = '';
      if(g.stato === 'inviato' && g.n_inviati != null) {
        statoExtra = '<br><span style="font-size:.68rem;color:rgba(104,211,145,.6)">' + g.n_inviati + ' ok';
        if(g.n_errori) statoExtra += ' / <span style="color:#ef4444">' + g.n_errori + ' err</span>';
        statoExtra += '</span>';
      }
      html += '<tr style="border-bottom:1px solid rgba(255,255,255,.04);'+rowBg+'">';
      html += '<td style="padding:.38rem .7rem;font-family:monospace;font-size:.8rem;color:rgba(255,255,255,.7)">'+g.data+'</td>';
      html += '<td style="padding:.38rem .7rem;text-align:center;font-size:.8rem;opacity:.6">S'+g.settimana+'</td>';
      html += '<td style="padding:.38rem .7rem;font-size:.78rem;color:#e0e0e0">'+(VARIANTE_LABEL[g.variante]||g.variante)+'</td>';
      html += '<td style="padding:.38rem .7rem;font-size:.77rem;color:rgba(255,255,255,.65);max-width:280px">'+g.soggetto+'</td>';
      html += '<td style="padding:.38rem .7rem;text-align:center;font-size:.8rem;opacity:.6">250</td>';
      html += '<td style="padding:.38rem .7rem;text-align:center"><span style="color:'+col+';font-size:.75rem">'+icon+' '+g.stato+statoExtra+'</span></td>';
      html += '<td style="padding:.38rem .7rem;text-align:center">'+btnInvia+'</td>';
      html += '</tr>';
    });
    if(tbody) tbody.innerHTML = html;

  }).catch(function(e){
    if(tbody) tbody.innerHTML = '<tr><td colspan="7" style="color:#ef4444;padding:1rem">Errore: '+e.message+'</td></tr>';
  });
}

function inviaCampagna(mese, data_giorno) {
  if(!confirm('Inviare l\'email del ' + data_giorno + ' a 250 destinatari?')) return;
  fetch('/api/campagna/invia', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({mese: mese, data: data_giorno})
  }).then(function(r){return r.json();}).then(function(d){
    if(d.ok){
      showMsg('crm-msg', '✅ Email inviate: ' + data_giorno + ' — batch 250', 'ok');
      loadCampagna();
    } else {
      showMsg('crm-msg', '❌ ' + (d.msg || 'Errore invio'), 'err');
    }
  }).catch(function(e){
    showMsg('crm-msg', '❌ Errore di rete: ' + e.message, 'err');
  });
}

function forzaInvioOggi() {
  var oggi = new Date().toISOString().slice(0,10);
  if(!confirm('Avviare il batch automatico per OGGI (' + oggi + ')?\n\nIl sistema invierà fino a 250 email ai prospect non ancora contattati questo mese.\nL\'operazione viene eseguita in background — ricarica il calendario tra 2-3 minuti.')) return;
  fetch('/api/campagna/forza-invio-oggi', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'})
    .then(function(r){return r.json();}).then(function(d){
      if(d.ok){
        showMsg('crm-msg', '⚡ Batch avviato — ricarica tra 2-3 minuti per vedere i risultati', 'ok');
        setTimeout(loadCampagna, 3000);
      } else {
        showMsg('crm-msg', '❌ ' + (d.msg || 'Errore avvio batch'), 'err');
      }
    }).catch(function(e){
      showMsg('crm-msg', '❌ Errore di rete: ' + e.message, 'err');
    });
}

function importaProspectBrevo() {
  var btn = document.getElementById('btn-import-prospect');
  if(btn){ btn.disabled = true; btn.textContent = '⏳ Importazione in corso...'; }
  fetch('/api/brevo/import-prospect', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'})
    .then(function(r){ return r.json(); })
    .then(function(d){
      if(btn){ btn.disabled = false; btn.textContent = '⬆ Importa in Brevo'; }
      if(d.ok){
        alert('✅ Import avviato!\n\n'
          +'Prospect importati: ' + d.totale + '\n'
          +'Lista Brevo: "' + d.lista_nome + '" (ID ' + d.lista_id + ')\n'
          +'Process ID: ' + (d.process_id || '—') + '\n\n'
          +'Brevo elabora in background — controlla la lista su app.brevo.com tra qualche minuto.\n'
          +'Poi usa quella lista come destinatari nella tua campagna di lancio.');
      } else {
        alert('❌ Errore: ' + (d.msg || 'sconosciuto') + (d.detail ? '\n\n' + JSON.stringify(d.detail) : ''));
      }
    })
    .catch(function(e){
      if(btn){ btn.disabled = false; btn.textContent = '⬆ Importa in Brevo'; }
      alert('Errore di rete: ' + e);
    });
}

var _lancioHtmlCache = null;

function mostraLancioCampagna() {
  var old = document.getElementById('brevo-modal'); if(old) old.remove();
  var backdrop = document.createElement('div');
  backdrop.id = 'brevo-modal';
  backdrop.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:1rem';
  var card = document.createElement('div');
  card.style.cssText = 'background:#1e293b;border:1px solid rgba(255,255,255,.1);border-radius:12px;width:100%;max-width:520px;max-height:85vh;display:flex;flex-direction:column';
  card.innerHTML = '<div style="padding:1.5rem;text-align:center;opacity:.5;flex:1">Caricamento...</div>'
    +'<div style="padding:.75rem 1.5rem;border-top:1px solid rgba(255,255,255,.08)">'
    +'<button id="lancio-chiudi-tmp" style="width:100%;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:rgba(255,255,255,.6);padding:.6rem;font-size:.85rem;cursor:pointer">Chiudi</button></div>';
  backdrop.appendChild(card);
  document.body.appendChild(backdrop);
  document.getElementById('lancio-chiudi-tmp').addEventListener('click', brevoChiudiModal);

  var loadH = fetch('/api/brevo/html-lancio').then(function(r){return r.json();});
  var loadL = _brevo_liste ? Promise.resolve(_brevo_liste) :
    fetch('/api/brevo/liste').then(function(r){return r.json();}).then(function(d){ _brevo_liste = d.liste||[]; return _brevo_liste; });

  Promise.all([loadH, loadL]).then(function(res){
    _lancioHtmlCache = res[0].html || '';
    var liste = Array.isArray(res[1]) ? res[1] : [];
    var listeHtml = '';
    liste.forEach(function(l){
      var presel = (l.name||'').indexOf('Prospect Lancio') !== -1 ? ' checked' : '';
      listeHtml += '<label style="display:flex;align-items:center;gap:.4rem;font-size:.82rem;margin-bottom:.3rem;cursor:pointer">'
        +'<input type="checkbox" class="lancio-lista" value="'+l.id+'"'+presel+'> '
        +(l.name||'ID '+l.id)
        +' <span style="color:rgba(255,255,255,.3);font-size:.72rem">('+( l.uniqueSubscribers||l.totalSubscribers||0)+' contatti)</span></label>';
    });
    card.innerHTML = '<div style="padding:1.5rem;overflow-y:auto;flex:1 1 auto;min-height:0">'
      +'<h3 style="color:#68D391;margin-bottom:1.2rem;font-size:1rem">📧 Campagna Lancio Prospect</h3>'
      +'<div style="display:flex;flex-direction:column;gap:.75rem">'
      +'<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.25rem">Nome Campagna</label>'
      +'<input id="lancio-nome" value="Lancio Fuerte — 2.435 Prospect" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem .75rem;font-size:.85rem"></div>'
      +'<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.25rem">Oggetto email</label>'
      +'<input id="lancio-oggetto" value="Ogni notte 10.086 asset analizzati per te — prova 7 giorni gratis" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem .75rem;font-size:.85rem"></div>'
      +'<div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem"><div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.25rem">Email mittente <span style="color:#ef4444">★ verificata su Brevo</span></label>'
      +'<input id="lancio-sender-email" value="marketing@fuerteventurecapital.com" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem .75rem;font-size:.85rem"></div>'
      +'<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.25rem">Nome mittente</label>'
      +'<input id="lancio-sender-name" value="Fuerte Venture Capital" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem .75rem;font-size:.85rem"></div></div>'
      +'<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.4rem">Liste destinatari</label>'
      +(listeHtml || '<div style="opacity:.5;font-size:.8rem">Nessuna lista trovata su Brevo</div>')+'</div>'
      +'<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.25rem">Anteprima email</label>'
      +'<div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:6px;padding:.6rem 1rem;font-size:.8rem;color:rgba(255,255,255,.5)">'
      +'HTML pronto — '+(_lancioHtmlCache.length)+' caratteri. '
      +'<a href="#" id="lancio-anteprima-link" style="color:#F6AD55;text-decoration:none">Visualizza anteprima →</a>'
      +'</div></div>'
      +'<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.25rem">Data invio schedulato (opzionale)</label>'
      +'<input id="lancio-data" type="datetime-local" style="background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem .75rem;font-size:.85rem"></div>'
      +'<div style="background:rgba(246,173,85,.06);border:1px solid rgba(246,173,85,.2);border-radius:6px;padding:.7rem 1rem;font-size:.78rem;color:rgba(255,255,255,.5)">'
      +'⚠️ La campagna viene creata come <strong style="color:#F6AD55">bozza</strong> su Brevo. Rivedi su app.brevo.com prima di inviare.</div>'
      +'</div></div>'
      +'<div style="padding:.75rem 1.5rem;flex:0 0 auto;border-top:1px solid rgba(255,255,255,.08)">'
      +'<div id="lancio-error" style="display:none;color:#ef4444;font-size:.8rem;padding:.4rem .6rem;background:rgba(239,68,68,.08);border-radius:6px;margin-bottom:.5rem"></div>'
      +'<button id="lancio-crea-btn" style="width:100%;background:rgba(104,211,145,.15);border:1px solid rgba(104,211,145,.4);border-radius:8px;color:#68D391;padding:.7rem;font-size:.9rem;font-weight:700;cursor:pointer;margin-bottom:.5rem">📧 Crea Bozza Campagna</button>'
      +'<button id="lancio-chiudi-btn" style="width:100%;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:rgba(255,255,255,.6);padding:.6rem;font-size:.85rem;cursor:pointer">Chiudi</button>'
      +'</div>';
    document.getElementById('lancio-crea-btn').addEventListener('click', confermaLancioCampagna);
    document.getElementById('lancio-chiudi-btn').addEventListener('click', brevoChiudiModal);
    var ant = document.getElementById('lancio-anteprima-link');
    if(ant) ant.addEventListener('click', function(e){ e.preventDefault(); lancioMostraAnteprima(); });
  }).catch(function(e){
    card.innerHTML = '<div style="padding:1.5rem"><p style="color:#ef4444">Errore caricamento: '+e+'</p></div>'
      +'<div style="padding:.75rem 1.5rem;border-top:1px solid rgba(255,255,255,.08)">'
      +'<button id="lancio-chiudi-err" style="width:100%;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:rgba(255,255,255,.6);padding:.6rem;font-size:.85rem;cursor:pointer">Chiudi</button></div>';
    document.getElementById('lancio-chiudi-err').addEventListener('click', brevoChiudiModal);
  });
}

function lancioMostraAnteprima() {
  var w = window.open('','_blank','width=700,height=600');
  if(w && _lancioHtmlCache){ w.document.write(_lancioHtmlCache); w.document.close(); }
}

function confermaLancioCampagna() {
  var errEl = document.getElementById('lancio-error');
  function _err(msg){ if(errEl){ errEl.textContent=msg; errEl.style.display='block'; } }
  if(errEl) errEl.style.display='none';
  var nome = (document.getElementById('lancio-nome')||{value:''}).value.trim();
  var oggetto = (document.getElementById('lancio-oggetto')||{value:''}).value.trim();
  var data_inv = (document.getElementById('lancio-data')||{value:''}).value;
  var checkboxes = document.querySelectorAll('.lancio-lista:checked');
  var lista_ids = Array.from(checkboxes).map(function(cb){return parseInt(cb.value);});
  if(!nome){ _err('Inserisci il nome della campagna'); return; }
  if(!oggetto){ _err("Inserisci l'oggetto email"); return; }
  if(lista_ids.length === 0){ _err('Seleziona almeno una lista destinatari'); return; }
  if(!_lancioHtmlCache){ _err('HTML email non caricato — riapri il modal'); return; }
  var sender_email = (document.getElementById('lancio-sender-email')||{value:''}).value.trim();
  var sender_name  = (document.getElementById('lancio-sender-name')||{value:''}).value.trim();
  if(!sender_email){ _err('Inserisci la email mittente verificata su Brevo'); return; }
  var btn = document.getElementById('lancio-crea-btn');
  if(btn){ btn.disabled=true; btn.textContent='⏳ Creazione in corso...'; }
  var payload = {nome:nome, oggetto:oggetto, html_content:_lancioHtmlCache, lista_ids:lista_ids,
    sender_email:sender_email, sender_name:sender_name};
  if(data_inv) payload.data_invio_schedulato = new Date(data_inv).toISOString();
  fetch('/api/brevo/campagne',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
    .then(function(r){return r.json();}).then(function(d){
      if(btn){ btn.disabled=false; btn.textContent='📧 Crea Bozza Campagna'; }
      if(d.ok){
        brevoChiudiModal();
        _brevo_campagne = null;
        renderCampagne();
        alert('Bozza creata su Brevo (ID '+d.id+')!\n\nVai su app.brevo.com per revisionarla e inviarla.');
      } else {
        _err('Errore Brevo: '+(d.msg||'sconosciuto')+' '+(d.detail?JSON.stringify(d.detail):''));
      }
    }).catch(function(e){ if(btn){btn.disabled=false;btn.textContent='📧 Crea Bozza Campagna';} _err('Errore di rete: '+e); });
}

function renderCampagneTable(campagne, filtro) {
  filtro = filtro || 'tutti';
  var STATO_COLOR = {sent:'#68D391',draft:'#9ca3af',queued:'#60a5fa',suspended:'#F6AD55'};
  var lista = filtro === 'tutti' ? campagne : campagne.filter(function(c){return c.status===filtro;});
  var tbl = document.getElementById('brevo-campagne-table');
  var html = '<div class="box">'
    +'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;flex-wrap:wrap;gap:.5rem">'
    +'<h3 style="color:#F6AD55">📧 Campagne Email — Brevo ('+campagne.length+')</h3>'
    +'<div style="display:flex;gap:.5rem;align-items:center">'
    +'<select id="brevo-filtro-stato" onchange="renderCampagneTable(_brevo_campagne,this.value)" style="background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.35rem .6rem;font-size:.8rem">'
    +'<option value="tutti">Tutti</option>'
    +'<option value="sent">Inviate</option>'
    +'<option value="draft">Bozze</option>'
    +'<option value="queued">Schedulate</option>'
    +'<option value="suspended">Sospese</option>'
    +'</select>'
    +'<button onclick="renderCampagne()" style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.35rem .7rem;font-size:.8rem;cursor:pointer">↺ Aggiorna</button>'
    +'<button onclick="mostraNuovaCampagna()" style="background:#2C5282;border:none;border-radius:6px;color:#F6AD55;padding:.35rem .8rem;font-size:.8rem;font-weight:700;cursor:pointer">+ Nuova Campagna</button>'
    +'</div></div>';

  if(lista.length === 0){
    html += '<div style="opacity:.5;padding:1.5rem;text-align:center;font-size:.85rem">Nessuna campagna trovata</div></div>';
  } else {
    html += '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:.82rem">'
      +'<thead><tr style="border-bottom:1px solid rgba(255,255,255,.1);color:rgba(255,255,255,.4);font-size:.75rem;text-transform:uppercase;letter-spacing:.05em">'
      +'<th style="padding:.5rem .75rem;text-align:left">Nome Campagna</th>'
      +'<th style="padding:.5rem .75rem;text-align:left">Oggetto</th>'
      +'<th style="padding:.5rem .75rem;text-align:center">Stato</th>'
      +'<th style="padding:.5rem .75rem;text-align:center">Data</th>'
      +'<th style="padding:.5rem .75rem;text-align:right">Inviati</th>'
      +'<th style="padding:.5rem .75rem;text-align:right">Aperture</th>'
      +'<th style="padding:.5rem .75rem;text-align:right">Click</th>'
      +'<th style="padding:.5rem .75rem;text-align:center">Azioni</th>'
      +'</tr></thead><tbody>';
    _brevo_camp_names = {};
    lista.forEach(function(c){
      _brevo_camp_names[c.id] = c.name;
      var stats = (c.statistics && c.statistics.globalStats) || {};
      var sent = stats.sent || 0;
      var views = stats.uniqueViews || 0;
      var clicks = stats.uniqueClicks || 0;
      var aperturePct = sent > 0 ? (views/sent*100).toFixed(1)+'%' : '—';
      var clickPct = sent > 0 ? (clicks/sent*100).toFixed(1)+'%' : '—';
      var dataStr = '—';
      if(c.sentDate || c.scheduledAt){
        var dt = new Date(c.sentDate || c.scheduledAt);
        dataStr = dt.toLocaleDateString('it-IT',{day:'2-digit',month:'2-digit',year:'2-digit'});
      }
      var statoBadge = '<span style="background:'+(STATO_COLOR[c.status]||'#9ca3af')+'22;color:'+(STATO_COLOR[c.status]||'#9ca3af')+';border:1px solid '+(STATO_COLOR[c.status]||'#9ca3af')+'44;border-radius:12px;padding:.15rem .55rem;font-size:.72rem;font-weight:600">'+c.status+'</span>';
      html += '<tr style="border-bottom:1px solid rgba(255,255,255,.05)">'
        +'<td style="padding:.55rem .75rem;font-weight:600;color:#e0e0e0;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="'+c.name+'">'+c.name+'</td>'
        +'<td style="padding:.55rem .75rem;color:rgba(255,255,255,.55);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="'+(c.subject||'')+'">'+( c.subject||'—')+'</td>'
        +'<td style="padding:.55rem .75rem;text-align:center">'+statoBadge+'</td>'
        +'<td style="padding:.55rem .75rem;text-align:center;color:rgba(255,255,255,.45);font-size:.75rem">'+dataStr+'</td>'
        +'<td style="padding:.55rem .75rem;text-align:right;color:rgba(255,255,255,.6)">'+sent.toLocaleString()+'</td>'
        +'<td style="padding:.55rem .75rem;text-align:right;color:#60a5fa;font-weight:600">'+aperturePct+'</td>'
        +'<td style="padding:.55rem .75rem;text-align:right;color:#68D391;font-weight:600">'+clickPct+'</td>'
        +'<td style="padding:.55rem .75rem;text-align:center">'
        +'<div style="display:flex;gap:.3rem;justify-content:center;align-items:center">';
      if(c.status === 'draft'){
        html += '<button onclick="brevoInviaCampagna('+c.id+')" style="background:#2C5282;border:none;border-radius:5px;color:#F6AD55;padding:.2rem .5rem;font-size:.72rem;cursor:pointer">▶ Invia</button>';
      }
      if(c.status === 'sent'){
        html += '<button onclick="brevoAvanzaProspect('+c.id+',this)" style="background:#276749;border:none;border-radius:5px;color:#68D391;padding:.2rem .5rem;font-size:.72rem;cursor:pointer" title="Avanza prospect che hanno aperto">▲ LinkedIn</button>';
        html += '<button onclick="brevoNonAperti('+c.id+')" style="background:rgba(246,173,85,.15);border:1px solid rgba(246,173,85,.3);border-radius:5px;color:#F6AD55;padding:.2rem .5rem;font-size:.72rem;cursor:pointer" title="Chi non ha aperto">✉ Non aperti</button>';
      }
      html += '<button onclick="brevoRisultati('+c.id+')" style="background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:5px;color:rgba(255,255,255,.6);padding:.2rem .4rem;font-size:.72rem;cursor:pointer" title="Statistiche dettagliate">👁</button>';
      html += '</div></td></tr>';
    });
    html += '</tbody></table></div></div>';
  }
  html += '<div id="brevo-modal-container"></div>';
  if(tbl) { tbl.innerHTML = html; } else { document.getElementById('campagne-content').innerHTML = _htmlAzioniLancio() + html; }
  if(filtro !== 'tutti'){
    var sel = document.getElementById('brevo-filtro-stato');
    if(sel) sel.value = filtro;
  }
}

function brevoInviaCampagna(id) {
  var nome = _brevo_camp_names[id] || 'ID '+id;
  if(!confirm('Inviare ora la campagna "'+nome+'" a tutti i destinatari?')) return;
  fetch('/api/brevo/campagne/'+id+'/invia',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
    .then(function(r){return r.json();}).then(function(d){
      if(d.ok){ alert('✅ Campagna inviata con successo'); renderCampagne(); }
      else alert('❌ Errore: '+(d.msg||'sconosciuto'));
    });
}

function brevoRisultati(id) {
  var cont = document.getElementById('brevo-modal-container');
  if(!cont) return;
  cont.innerHTML = _brevoModalOverlay('<div style="opacity:.5;text-align:center;padding:2rem">Caricamento...</div>','brevoChiudiModal()');
  fetch('/api/brevo/campagne/'+id+'/risultati').then(function(r){return r.json();}).then(function(d){
    if(!d.ok){ cont.innerHTML = ''; alert('Errore: '+d.msg); return; }
    var html = '<h3 style="color:#F6AD55;margin-bottom:.3rem;font-size:1rem">'+d.nome+'</h3>'
      +'<p style="color:rgba(255,255,255,.4);font-size:.8rem;margin-bottom:1.2rem">'+d.oggetto+'</p>'
      +'<div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem;margin-bottom:1rem">'
      +_brevoKpi('Inviati',d.inviati,'#e0e0e0')
      +_brevoKpi('Consegnati',d.consegnati,'#e0e0e0')
      +_brevoKpi('Aperture uniche',d.tasso_apertura_pct+'%','#60a5fa')
      +_brevoKpi('Click unici',d.tasso_click_pct+'%','#68D391')
      +_brevoKpi('Rimbalzi',d.rimbalzi,'#F6AD55')
      +_brevoKpi('Disiscritti',d.disiscritti,'#ef4444')
      +'</div>';
    if(d.data_invio){
      html += '<p style="font-size:.75rem;color:rgba(255,255,255,.3);text-align:center">Inviata il '+new Date(d.data_invio).toLocaleString('it-IT')+'</p>';
    }
    cont.innerHTML = _brevoModalOverlay(html,'brevoChiudiModal()');
  });
}

function brevoAvanzaProspect(id, btn) {
  var nome = _brevo_camp_names[id] || 'ID '+id;
  if(!confirm('Avanzare a PROSPECT LINKEDIN i lead che hanno aperto "'+nome+'"?\n(Da Contattare → Contattato, Contattato → Interessato)')) return;
  btn.disabled = true; btn.textContent = '...';
  fetch('/api/brevo/campagne/'+id+'/avanza-prospect',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
    .then(function(r){return r.json();}).then(function(d){
      btn.disabled = false; btn.textContent = '▲ LinkedIn';
      if(!d.ok){ alert('Errore: '+(d.msg||'sconosciuto')); return; }
      var avanzati   = d.avanzati||[];
      var gia        = d.gia_avanzati||[];
      var non_trovati= d.non_trovati||[];
      // header + export LinkedIn Ads
      var html = '<h3 style="color:#F6AD55;margin-bottom:.3rem;font-size:1rem">Avanzamento Prospect LinkedIn</h3>'
        +'<p style="color:rgba(255,255,255,.4);font-size:.78rem;margin-bottom:1rem">'+nome+'</p>';
      // sezione avanzati
      html += '<div style="margin-bottom:1rem">'
        +'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.5rem">'
        +'<div style="display:flex;align-items:center;gap:.4rem">'
        +'<span style="width:8px;height:8px;border-radius:50%;background:#68D391;display:inline-block"></span>'
        +'<span style="font-size:.85rem;font-weight:600;color:#68D391">Avanzati a PROSPECT ('+avanzati.length+')</span>'
        +'</div>';
      if(avanzati.length > 0){
        html += '<button onclick="brevoEsportaLinkedIn()" style="display:flex;align-items:center;gap:.3rem;background:rgba(10,102,194,.15);border:1px solid rgba(10,102,194,.4);border-radius:5px;color:#60a5fa;padding:.2rem .55rem;font-size:.72rem;cursor:pointer" title="Esporta per LinkedIn Ads (Matched Audiences)">'
          +'<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zM9 17H6.5v-7H9v7zm-1.3-8a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm9.3 8h-2.5v-3.5c0-.8-.7-1.5-1.5-1.5s-1.5.7-1.5 1.5V17H9v-7h2.5v1a3 3 0 015.5 1.7V17z"/></svg>'
          +' LinkedIn Ads</button>';
      }
      html += '</div>';
      if(avanzati.length > 0){
        // salva per export
        html += '<script>window._liAds='+JSON.stringify(avanzati)+';<\/script>';
        html += '<div style="max-height:180px;overflow-y:auto;border:1px solid rgba(255,255,255,.08);border-radius:6px">';
        avanzati.forEach(function(a){
          var liBtn = a.linkedin_url
            ? '<a href="'+a.linkedin_url+'" target="_blank" style="color:#0A66C2;display:inline-flex;align-items:center;gap:2px;text-decoration:none;flex-shrink:0" title="Apri profilo LinkedIn"><svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zM9 17H6.5v-7H9v7zm-1.3-8a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm9.3 8h-2.5v-3.5c0-.8-.7-1.5-1.5-1.5s-1.5.7-1.5 1.5V17H9v-7h2.5v1a3 3 0 015.5 1.7V17z"/></svg></a>'
            : '<a href="https://www.linkedin.com/search/results/people/?keywords='+encodeURIComponent(a.nome)+'" target="_blank" style="color:rgba(255,255,255,.25);display:inline-flex;align-items:center;flex-shrink:0" title="Cerca su LinkedIn"><svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zM9 17H6.5v-7H9v7zm-1.3-8a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm9.3 8h-2.5v-3.5c0-.8-.7-1.5-1.5-1.5s-1.5.7-1.5 1.5V17H9v-7h2.5v1a3 3 0 015.5 1.7V17z"/></svg></a>';
          html += '<div style="display:flex;align-items:center;gap:.4rem;font-size:.79rem;padding:.3rem .5rem;border-bottom:1px solid rgba(255,255,255,.05)">'
            +'<span style="flex:1;min-width:0;color:#e0e0e0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+a.nome+'</span>'
            +'<span style="color:rgba(255,255,255,.4);font-size:.72rem;flex-shrink:0">'+a.email+'</span>'
            +'<span style="color:#F6AD55;font-size:.72rem;flex-shrink:0">'+a.da+' → '+a.a+'</span>'
            +liBtn+'</div>';
        });
        html += '</div>';
      } else { html += '<p style="font-size:.8rem;color:rgba(255,255,255,.35);padding:.25rem .5rem">Nessuno</p>'; }
      html += '</div>';
      // già avanzati
      if(gia.length > 0){
        html += '<div style="margin-bottom:1rem"><div style="display:flex;align-items:center;gap:.4rem;margin-bottom:.4rem">'
          +'<span style="width:8px;height:8px;border-radius:50%;background:#60a5fa;display:inline-block"></span>'
          +'<span style="font-size:.85rem;font-weight:600;color:#60a5fa">Già oltre LEAD ('+gia.length+')</span></div>';
        gia.forEach(function(a){
          html += '<div style="font-size:.78rem;color:rgba(255,255,255,.4);padding:.2rem .5rem">'+a.nome+' <span style="color:rgba(255,255,255,.25)">→ '+a.stato+'</span></div>';
        });
        html += '</div>';
      }
      // non trovati in CRM
      if(non_trovati.length > 0){
        html += '<div><div style="display:flex;align-items:center;gap:.4rem;margin-bottom:.4rem">'
          +'<span style="width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,.25);display:inline-block"></span>'
          +'<span style="font-size:.85rem;font-weight:600;color:rgba(255,255,255,.4)">Non presenti in CRM ('+non_trovati.length+')</span></div>';
        non_trovati.forEach(function(e){
          html += '<div style="font-size:.72rem;color:rgba(255,255,255,.3);padding:.15rem .5rem">'+e+'</div>';
        });
        html += '</div>';
      }
      _prospect = null;
      var cont = document.getElementById('brevo-modal-container');
      if(cont) cont.innerHTML = _brevoModalOverlay(html,'brevoChiudiModal()');
    }).catch(function(e){ btn.disabled=false; btn.textContent='▲ LinkedIn'; alert('Errore: '+e); });
}

function brevoEsportaLinkedIn() {
  var data = window._liAds || [];
  if(!data.length){ alert('Nessun dato da esportare'); return; }
  var bom = '﻿';
  var header = 'Email,Nome';
  var righe = data.map(function(c){ return c.email+',"'+c.nome.replace(/"/g,'""')+'"'; }).join('\n');
  var blob = new Blob([bom+header+'\n'+righe], {type:'text/csv;charset=utf-8'});
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url; a.download = 'prospect-linkedin-ads.csv';
  a.click(); URL.revokeObjectURL(url);
}

function brevoNonAperti(id) {
  var nome = _brevo_camp_names[id] || 'ID '+id;
  var cont = document.getElementById('brevo-modal-container');
  if(!cont) return;
  cont.innerHTML = _brevoModalOverlay('<div style="opacity:.5;text-align:center;padding:2rem">Analisi in corso... (può richiedere qualche secondo)</div>','brevoChiudiModal()');
  fetch('/api/brevo/campagne/'+id+'/non-aperti').then(function(r){return r.json();}).then(function(d){
    if(!d.ok){ cont.innerHTML=''; alert('Errore: '+d.msg); return; }
    var html = '<h3 style="color:#F6AD55;margin-bottom:.3rem;font-size:1rem">Non Aperti</h3>'
      +'<p style="color:rgba(255,255,255,.4);font-size:.78rem;margin-bottom:1rem">'+nome+'</p>'
      +'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:.5rem;margin-bottom:1rem">'
      +'<div style="background:rgba(0,0,0,.3);border-radius:8px;padding:.6rem;text-align:center"><div style="font-size:1.2rem;font-weight:700;color:#e0e0e0">'+d.totale+'</div><div style="font-size:.72rem;color:rgba(255,255,255,.4)">Verificati</div></div>'
      +'<div style="background:rgba(104,211,145,.08);border-radius:8px;padding:.6rem;text-align:center"><div style="font-size:1.2rem;font-weight:700;color:#68D391">'+d.aperti+'</div><div style="font-size:.72rem;color:rgba(255,255,255,.4)">Hanno aperto</div></div>'
      +'<div style="background:rgba(246,173,85,.08);border-radius:8px;padding:.6rem;text-align:center"><div style="font-size:1.2rem;font-weight:700;color:#F6AD55">'+d.non_aperti+'</div><div style="font-size:.72rem;color:rgba(255,255,255,.4)">Non aperti</div></div>'
      +'</div>';
    if(d.contatti && d.contatti.length > 0){
      html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.4rem">'
        +'<span style="font-size:.78rem;color:rgba(255,255,255,.4)">Lista non aperti</span>'
        +'<button onclick="brevoEsportaNonAperti('+id+')" style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);border-radius:5px;color:#e0e0e0;padding:.2rem .55rem;font-size:.72rem;cursor:pointer">⬇ CSV</button>'
        +'</div>'
        +'<div style="max-height:220px;overflow-y:auto;border:1px solid rgba(255,255,255,.08);border-radius:6px">'
        +'<table style="width:100%;border-collapse:collapse;font-size:.78rem">'
        +'<thead><tr style="background:rgba(0,0,0,.3);color:rgba(255,255,255,.35);font-size:.7rem">'
        +'<th style="padding:.3rem .5rem;text-align:left">Nome</th>'
        +'<th style="padding:.3rem .5rem;text-align:left">Email</th>'
        +'<th style="padding:.3rem .5rem;text-align:left">Piano</th>'
        +'</tr></thead><tbody>';
      d.contatti.forEach(function(c){
        html += '<tr style="border-bottom:1px solid rgba(255,255,255,.05)">'
          +'<td style="padding:.3rem .5rem;color:#e0e0e0">'+c.nome+'</td>'
          +'<td style="padding:.3rem .5rem;color:rgba(255,255,255,.5)">'+c.email+'</td>'
          +'<td style="padding:.3rem .5rem;color:#F6AD55">'+c.piano+'</td>'
          +'</tr>';
      });
      html += '</tbody></table></div>';
      window._brevoNonApertiData = d.contatti;
      window._brevoNonApertiNome = nome;
    }
    cont.innerHTML = _brevoModalOverlay(html,'brevoChiudiModal()');
  });
}

function brevoEsportaNonAperti(id) {
  var lista = window._brevoNonApertiData || [];
  var bom = '﻿';
  var header = 'Nome,Email,Piano,Stato';
  var righe = lista.map(function(c){ return '"'+c.nome+'",'+c.email+',"'+c.piano+'","'+c.stato+'"'; }).join('\n');
  var blob = new Blob([bom+header+'\n'+righe],{type:'text/csv;charset=utf-8'});
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a'); a.href=url; a.download='non-aperti-campagna-'+id+'.csv'; a.click(); URL.revokeObjectURL(url);
}

function _brevoKpi(label, value, color) {
  return '<div style="background:rgba(0,0,0,.3);border-radius:8px;padding:.75rem;text-align:center">'
    +'<div style="font-size:1.3rem;font-weight:700;color:'+color+'">'+value+'</div>'
    +'<div style="font-size:.72rem;color:rgba(255,255,255,.4);margin-top:.15rem">'+label+'</div>'
    +'</div>';
}

function _brevoModalOverlay(content, onclose, footer) {
  var ftHtml = (footer !== undefined) ? footer
    : '<button onclick="'+onclose+'" style="width:100%;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:rgba(255,255,255,.6);padding:.6rem;font-size:.85rem;cursor:pointer">Chiudi</button>';
  return '<div id="brevo-modal" style="position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:1rem">'
    +'<div style="background:#1e293b;border:1px solid rgba(255,255,255,.1);border-radius:12px;width:100%;max-width:520px;max-height:85vh;display:flex;flex-direction:column;position:relative">'
    +'<button onclick="'+onclose+'" style="position:absolute;top:.75rem;right:.75rem;background:none;border:none;color:rgba(255,255,255,.4);font-size:1.1rem;cursor:pointer;z-index:1">✕</button>'
    +'<div style="padding:1.5rem;overflow-y:auto;flex:1 1 auto;min-height:0">'
    +content
    +'</div>'
    +'<div style="padding:.75rem 1.5rem;flex:0 0 auto;border-top:1px solid rgba(255,255,255,.08)">'
    +ftHtml
    +'</div>'
    +'</div></div>';
}
function brevoChiudiModal() {
  var m = document.getElementById('brevo-modal'); if(m) m.remove();
  var cont = document.getElementById('brevo-modal-container'); if(cont) cont.innerHTML='';
}

// ─── Nuova Campagna ───────────────────────────────────────────────────────────
function mostraNuovaCampagna() {
  var cont = document.getElementById('brevo-modal-container');
  if(!cont) { cont = document.createElement('div'); cont.id='brevo-modal-container'; document.getElementById('campagne-content').appendChild(cont); }
  // Carica template e liste in parallelo
  var loadT = _brevo_template ? Promise.resolve(_brevo_template) :
    fetch('/api/brevo/template').then(function(r){return r.json();}).then(function(d){ _brevo_template = d.template||[]; return _brevo_template; });
  var loadL = _brevo_liste ? Promise.resolve(_brevo_liste) :
    fetch('/api/brevo/liste').then(function(r){return r.json();}).then(function(d){ _brevo_liste = d.liste||[]; return _brevo_liste; });
  cont.innerHTML = _brevoModalOverlay('<div style="opacity:.5;text-align:center;padding:2rem">Caricamento template e liste...</div>','brevoChiudiModal()');
  Promise.all([loadT, loadL]).then(function(results){
    var template = results[0];
    var liste = results[1];
    var html = '<h3 style="color:#F6AD55;margin-bottom:1.2rem;font-size:1rem">+ Nuova Campagna</h3>'
      +'<div style="display:flex;flex-direction:column;gap:.75rem">'
      +'<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.25rem">Nome Campagna</label>'
      +'<input id="nc-nome" placeholder="es. Newsletter Luglio 2026 — Azioni" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem .75rem;font-size:.85rem"></div>'
      +'<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.25rem">Oggetto email</label>'
      +'<input id="nc-oggetto" placeholder="es. 📈 Report Azioni — Luglio 2026" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem .75rem;font-size:.85rem"></div>'
      +'<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.25rem">Template</label>'
      +'<select id="nc-template" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem .75rem;font-size:.85rem">'
      +'<option value="">— scegli template —</option>';
    template.forEach(function(t){ html += '<option value="'+t.id+'">'+t.name+'</option>'; });
    html += '</select></div>';
    if(liste.length > 0){
      html += '<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.4rem">Liste destinatari</label>';
      liste.forEach(function(l){
        html += '<label style="display:flex;align-items:center;gap:.4rem;font-size:.82rem;margin-bottom:.25rem;cursor:pointer">'
          +'<input type="checkbox" class="nc-lista" value="'+l.id+'"> '+l.name
          +' <span style="color:rgba(255,255,255,.3);font-size:.72rem">('+( l.uniqueSubscribers||l.totalSubscribers||0)+' contatti)</span></label>';
      });
      html += '</div>';
    } else {
      html += '<div style="background:rgba(252,129,129,.08);border:1px solid rgba(252,129,129,.2);border-radius:6px;padding:.5rem .75rem;font-size:.78rem;color:rgba(255,255,255,.5)">Nessuna lista trovata su Brevo. Crea prima una lista sul pannello Brevo.</div>';
    }
    html += '<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.25rem">Data invio schedulato (opzionale)</label>'
      +'<input id="nc-data" type="datetime-local" style="background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem .75rem;font-size:.85rem"></div>'
      +'<button onclick="confermaNuovaCampagna()" style="width:100%;background:#2C5282;border:none;border-radius:8px;color:#F6AD55;padding:.7rem;font-size:.9rem;font-weight:700;cursor:pointer;margin-top:.25rem">Crea Campagna</button>'
      +'</div>';
    cont.innerHTML = _brevoModalOverlay(html,'brevoChiudiModal()');
  }).catch(function(e){
    cont.innerHTML = _brevoModalOverlay('<p style="color:#ef4444">Errore: '+e+'</p>','brevoChiudiModal()');
  });
}

function confermaNuovaCampagna() {
  var nome = (document.getElementById('nc-nome')||{value:''}).value.trim();
  var oggetto = (document.getElementById('nc-oggetto')||{value:''}).value.trim();
  var template_id = (document.getElementById('nc-template')||{value:''}).value;
  var data_inv = (document.getElementById('nc-data')||{value:''}).value;
  var checkboxes = document.querySelectorAll('.nc-lista:checked');
  var lista_ids = Array.from(checkboxes).map(function(cb){return parseInt(cb.value);});
  if(!nome){ alert('Inserisci il nome della campagna'); return; }
  if(!oggetto){ alert('Inserisci l\'oggetto dell\'email'); return; }
  if(!template_id){ alert('Seleziona un template'); return; }
  if(lista_ids.length === 0){ alert('Seleziona almeno una lista destinatari'); return; }
  var payload = {nome:nome, oggetto:oggetto, template_id:parseInt(template_id), lista_ids:lista_ids};
  if(data_inv) payload.data_invio_schedulato = new Date(data_inv).toISOString();
  fetch('/api/brevo/campagne',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
    .then(function(r){return r.json();}).then(function(d){
      if(d.ok){
        brevoChiudiModal();
        alert('✅ Campagna creata con successo (ID '+d.id+')');
        _brevo_campagne = null;
        renderCampagne();
      } else {
        alert('❌ Errore: '+(d.msg||'sconosciuto'));
      }
    }).catch(function(e){ alert('Errore: '+e); });
}

function renderSocial() {
  var el = document.getElementById('social-content');
  el.innerHTML = '<div style="opacity:.5;padding:1rem;text-align:center">Caricamento...</div>';
  // Carica platforms + drafts + calendario in parallelo
  Promise.all([
    fetch('/api/social/platforms').then(function(r){return r.json();}),
    fetch('/api/social/status').then(function(r){return r.json();}),
    fetch('/api/social/calendario').then(function(r){return r.json();})
  ]).then(function(results){
    var platforms = results[0];
    var statusData = results[1];
    var calData    = results[2];
    var drafts   = (statusData.drafts  || []);
    var calendar = (calData.calendario || []);
    var pending  = drafts.filter(function(d){return d.status==='pending';});
    var recent   = drafts.filter(function(d){return d.status!=='pending';}).slice(0,8);
    var html = '';

    // ── Stato piattaforme ──────────────────────────────────────
    html += '<div class="box" style="margin-bottom:1rem">';
    html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.9rem;flex-wrap:wrap;gap:.5rem">';
    html += '<h3 style="color:#F6AD55;margin:0">📱 Stato Piattaforme</h3>';
    html += '<div style="display:flex;gap:.5rem">';
    html += '<button onclick="renderSocial()" style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.3rem .65rem;font-size:.8rem;cursor:pointer">↺ Aggiorna</button>';
    html += '<button onclick="socialGeneraDraft()" style="background:#2C5282;border:none;border-radius:6px;color:#F6AD55;padding:.3rem .75rem;font-size:.8rem;font-weight:700;cursor:pointer" id="btn-genera-draft">▶ Genera Draft</button>';
    html += '<button onclick="socialApriPubblicaOra()" style="background:#276749;border:none;border-radius:6px;color:#68D391;padding:.3rem .75rem;font-size:.8rem;font-weight:700;cursor:pointer">🚀 Pubblica Ora</button>';
    html += '</div></div>';
    html += '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:.6rem">';
    // LinkedIn
    var li = (platforms.linkedin || {});
    var liCol = li.connesso ? '#68D391' : (li.configurato ? '#F6AD55' : '#FC8181');
    var liLabel = li.connesso ? '✅ Connesso' : (li.configurato ? '⚠️ Token scaduto' : '❌ Da configurare');
    html += '<div style="background:rgba(10,102,194,.12);border:1px solid rgba(10,102,194,.25);border-radius:8px;padding:.7rem 1rem">';
    html += '<div style="display:flex;align-items:center;gap:.4rem;margin-bottom:.3rem"><span style="color:#0A66C2;font-size:1rem">in</span><span style="font-weight:700;font-size:.85rem;color:#e0e0e0">LinkedIn</span></div>';
    html += '<div style="font-size:.78rem;color:'+liCol+'">'+liLabel+'</div>';
    if(!li.connesso && li.configurato){
      html += '<a href="/api/linkedin/connect" style="display:inline-block;margin-top:.5rem;background:#0A66C2;color:#fff;border-radius:5px;padding:.2rem .55rem;font-size:.72rem;text-decoration:none">Connetti</a>';
    } else if(!li.configurato){
      html += '<div style="font-size:.7rem;color:rgba(255,255,255,.3);margin-top:.3rem">config.json → social.linkedin</div>';
    }
    html += '</div>';
    // Facebook
    var fb = (platforms.facebook || {});
    var fbCol = fb.connesso ? '#68D391' : (fb.configurato ? '#F6AD55' : '#FC8181');
    var fbLabel = fb.connesso ? '✅ ' + (fb.page_name || 'Connesso') : (fb.configurato ? '⚠️ Token scaduto' : '❌ Da configurare');
    html += '<div style="background:rgba(66,103,178,.12);border:1px solid rgba(66,103,178,.25);border-radius:8px;padding:.7rem 1rem">';
    html += '<div style="display:flex;align-items:center;gap:.4rem;margin-bottom:.3rem"><span style="color:#4267B2;font-size:1rem">f</span><span style="font-weight:700;font-size:.85rem;color:#e0e0e0">Facebook</span></div>';
    html += '<div style="font-size:.78rem;color:'+fbCol+'">'+fbLabel+'</div>';
    if(!fb.connesso && fb.configurato){
      html += '<a href="/api/meta/connect" style="display:inline-block;margin-top:.5rem;background:#4267B2;color:#fff;border-radius:5px;padding:.2rem .55rem;font-size:.72rem;text-decoration:none">Connetti</a>';
    } else if(!fb.configurato){
      html += '<div style="font-size:.7rem;color:rgba(255,255,255,.3);margin-top:.3rem">config.json → social.meta</div>';
    }
    html += '</div>';
    // Instagram
    var ig = (platforms.instagram || {});
    var igCol = ig.connesso ? '#68D391' : '#FC8181';
    var igLabel = ig.connesso ? '✅ Connesso' : '❌ Richiede Meta connesso';
    html += '<div style="background:rgba(188,42,141,.1);border:1px solid rgba(188,42,141,.25);border-radius:8px;padding:.7rem 1rem">';
    html += '<div style="display:flex;align-items:center;gap:.4rem;margin-bottom:.3rem"><span style="font-size:.72rem;background:linear-gradient(135deg,#833ab4,#fd1d1d,#fcb045);color:#fff;border-radius:4px;padding:.1rem .3rem;font-weight:700">IG</span><span style="font-weight:700;font-size:.85rem;color:#e0e0e0">Instagram</span></div>';
    html += '<div style="font-size:.78rem;color:'+igCol+'">'+igLabel+'</div>';
    html += '<div style="font-size:.7rem;color:rgba(255,255,255,.3);margin-top:.3rem">Collegato a Meta/Facebook</div>';
    html += '</div>';
    // Brevo
    var br = (platforms.brevo || {});
    var brCol = br.configurato ? '#68D391' : '#FC8181';
    var brLabel = br.configurato ? '✅ Attivo — Lista ' + (br.list_ids||[]).join(',') : '❌ API key mancante';
    html += '<div style="background:rgba(44,130,201,.1);border:1px solid rgba(44,130,201,.25);border-radius:8px;padding:.7rem 1rem">';
    html += '<div style="display:flex;align-items:center;gap:.4rem;margin-bottom:.3rem"><span style="font-weight:700;font-size:.85rem;color:#e0e0e0">📧 Brevo</span></div>';
    html += '<div style="font-size:.78rem;color:'+brCol+'">'+brLabel+'</div>';
    html += '<div style="font-size:.7rem;color:rgba(255,255,255,.3);margin-top:.3rem">Email newsletter venerdì</div>';
    html += '</div>';
    // WhatsApp
    var wa = (platforms.whatsapp || {});
    var waCol = wa.configurato ? '#68D391' : '#FC8181';
    var waLabel = wa.configurato ? '✅ Token presente' : (wa.token_presente ? '⚠️ Phone ID mancante' : '❌ Token scaduto/mancante');
    html += '<div style="background:rgba(37,211,102,.1);border:1px solid rgba(37,211,102,.25);border-radius:8px;padding:.7rem 1rem">';
    html += '<div style="display:flex;align-items:center;gap:.4rem;margin-bottom:.3rem"><span style="font-weight:700;font-size:.85rem;color:#e0e0e0">💬 WhatsApp</span></div>';
    html += '<div style="font-size:.78rem;color:'+waCol+'">'+waLabel+'</div>';
    html += '<div style="font-size:.7rem;color:rgba(255,255,255,.3);margin-top:.3rem">Token 24h — aggiornare in Meta BM</div>';
    html += '</div>';
    html += '</div></div>';

    // ── Draft in attesa ────────────────────────────────────────
    if(pending.length > 0){
      html += '<div class="box"><h3 style="color:#F6AD55;margin-bottom:.9rem">⏳ Draft in attesa di approvazione ('+pending.length+')</h3>';
      pending.forEach(function(d){
        var preview = (d.text_it || d.text_es || '').slice(0,300);
        var chIcons = (d.channels||[]).map(function(ch){
          if(ch==='linkedin') return '<span style="color:#0A66C2;font-size:.75rem;font-weight:700">in</span>';
          if(ch==='facebook') return '<span style="color:#4267B2;font-size:.8rem;font-weight:700">f</span>';
          if(ch==='instagram') return '<span style="font-size:.65rem;background:linear-gradient(135deg,#833ab4,#fd1d1d,#fcb045);color:#fff;border-radius:3px;padding:.05rem .25rem;font-weight:700">IG</span>';
          return '<span style="opacity:.5;font-size:.75rem">'+ch+'</span>';
        }).join(' ');
        html += '<div style="background:rgba(0,0,0,.3);border-radius:8px;padding:1rem;margin-bottom:.8rem;border:1px solid rgba(246,173,85,.2)">';
        html += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem;flex-wrap:wrap;gap:.3rem">';
        html += '<span style="font-weight:700;color:#F6AD55;font-size:.88rem">'+d.theme+' · '+d.lang+' · '+d.date+'</span>';
        html += '<span style="display:flex;gap:.35rem;align-items:center">'+chIcons+'</span>';
        html += '</div>';
        html += '<div style="font-size:.82rem;opacity:.72;margin-bottom:.8rem;white-space:pre-wrap;line-height:1.5">'+preview+(preview.length===300?'…':'')+'</div>';
        if(d.image_url){
          html += '<div style="font-size:.75rem;color:rgba(255,255,255,.35);margin-bottom:.6rem">🖼 '+d.image_url+'</div>';
        }
        html += '<div style="display:flex;gap:.5rem;flex-wrap:wrap">';
        html += '<button onclick="socialApprova(\''+d.draft_id+'\')" style="background:#276749;border:none;border-radius:6px;color:#68D391;padding:.3rem .8rem;font-size:.78rem;font-weight:600;cursor:pointer">✅ Approva &amp; Pubblica</button>';
        html += '<button onclick="socialModificaDraft(\''+d.draft_id+'\',this)" style="background:rgba(246,173,85,.15);border:1px solid rgba(246,173,85,.3);border-radius:6px;color:#F6AD55;padding:.3rem .7rem;font-size:.78rem;cursor:pointer">✏ Modifica</button>';
        html += '<button onclick="socialRifiuta(\''+d.draft_id+'\')" style="background:rgba(252,129,129,.1);border:1px solid rgba(252,129,129,.3);border-radius:6px;color:#FC8181;padding:.3rem .7rem;font-size:.78rem;cursor:pointer">✕ Rifiuta</button>';
        html += '</div></div>';
      });
      html += '</div>';
    } else {
      html += '<div class="box" style="text-align:center;color:#68D391;padding:1.2rem;font-size:.88rem">✅ Nessun draft in attesa · Lo scheduler gira alle 08:00 lun/mer/ven</div>';
    }

    // ── Calendario prossimi post ───────────────────────────────
    if(calendar.length > 0){
      var today2 = new Date().toISOString().slice(0,10);
      var prossimi = calendar.filter(function(e){return e.date >= today2;}).slice(0,8);
      if(prossimi.length > 0){
        html += '<div class="box"><h3 style="color:#aaa;margin-bottom:.8rem;font-size:.88rem">📅 Prossimi Post Programmati</h3>';
        html += '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:.8rem">';
        html += '<thead><tr style="border-bottom:1px solid rgba(255,255,255,.08);color:rgba(255,255,255,.35);font-size:.72rem;text-transform:uppercase">';
        html += '<th style="padding:.35rem .6rem;text-align:left">Data</th>';
        html += '<th style="padding:.35rem .6rem;text-align:left">Tema</th>';
        html += '<th style="padding:.35rem .6rem;text-align:left">Lingua</th>';
        html += '<th style="padding:.35rem .6rem;text-align:left">Canali</th>';
        html += '<th style="padding:.35rem .6rem;text-align:center">Stato</th>';
        html += '</tr></thead><tbody>';
        var STATO_BADGE = {
          oggi:        '<span style="background:rgba(246,173,85,.2);color:#F6AD55;border-radius:10px;padding:.1rem .45rem;font-size:.7rem;font-weight:600">OGGI</span>',
          programmato: '<span style="background:rgba(96,165,250,.12);color:#60a5fa;border-radius:10px;padding:.1rem .45rem;font-size:.7rem">schedulato</span>',
          pending:     '<span style="background:rgba(246,173,85,.15);color:#F6AD55;border-radius:10px;padding:.1rem .45rem;font-size:.7rem">draft pronto</span>'
        };
        prossimi.forEach(function(e){
          var chStr = (e.channels||[]).join(', ');
          var badge = STATO_BADGE[e.stato] || '<span style="opacity:.4;font-size:.7rem">'+e.stato+'</span>';
          var rowStyle = e.stato==='oggi' ? 'background:rgba(246,173,85,.04);' : '';
          html += '<tr style="border-bottom:1px solid rgba(255,255,255,.04);'+rowStyle+'">';
          html += '<td style="padding:.4rem .6rem;color:rgba(255,255,255,.7)">'+e.date+'</td>';
          html += '<td style="padding:.4rem .6rem;font-weight:600;color:#e0e0e0">'+e.theme+'</td>';
          html += '<td style="padding:.4rem .6rem;color:rgba(255,255,255,.5)">'+e.lang+'</td>';
          html += '<td style="padding:.4rem .6rem;color:rgba(255,255,255,.45)">'+chStr+'</td>';
          html += '<td style="padding:.4rem .6rem;text-align:center">'+badge+'</td>';
          html += '</tr>';
        });
        html += '</tbody></table></div></div>';
      }
    }

    // ── Cronologia recente ─────────────────────────────────────
    if(recent.length > 0){
      html += '<div class="box"><h3 style="color:#aaa;margin-bottom:.7rem;font-size:.88rem">📋 Cronologia Recente</h3>';
      recent.forEach(function(d){
        var col    = d.status==='published' ? '#68D391' : '#FC8181';
        var icon   = d.status==='published' ? '✅' : '✕';
        var detail = '';
        if(d.publish_results){
          var r = d.publish_results;
          var parts = [];
          if(r.linkedin && r.linkedin.ok)  parts.push('LI ✓');
          if(r.facebook && r.facebook.ok)  parts.push('FB ✓');
          if(r.instagram && r.instagram.ok) parts.push('IG ✓');
          if(parts.length) detail = ' · '+parts.join(' ');
        }
        html += '<div style="display:flex;justify-content:space-between;align-items:center;padding:.4rem 0;border-bottom:1px solid rgba(255,255,255,.04);font-size:.81rem">';
        html += '<span style="opacity:.8">'+d.theme+' · '+d.lang+'</span>';
        html += '<span style="opacity:.5;font-size:.76rem">'+d.date+'</span>';
        html += '<span style="color:'+col+'">'+icon+' '+d.status+detail+'</span>';
        html += '</div>';
      });
      html += '</div>';
    }

    html += '<div id="social-modal-container"></div>';
    el.innerHTML = html;
  }).catch(function(e){
    el.innerHTML = '<div class="box" style="color:#FC8181">Errore caricamento: '+e.message+'</div>';
  });
}

function socialApprova(draftId) {
  fetch('/api/social/approve?draft_id='+draftId+'&action=approve')
    .then(function(r){return r.json();})
    .then(function(d){
      showMsg('crm-msg','✅ Draft approvato e inviato per la pubblicazione','ok');
      renderSocial();
    })
    .catch(function(e){ showMsg('crm-msg','❌ '+e.message,'err'); });
}

function socialRifiuta(draftId) {
  if(!confirm('Rifiutare questo draft?')) return;
  fetch('/api/social/approve?draft_id='+draftId+'&action=reject')
    .then(function(r){return r.json();})
    .then(function(){
      showMsg('crm-msg','🗑 Draft rifiutato','ok');
      renderSocial();
    })
    .catch(function(e){ showMsg('crm-msg','❌ '+e.message,'err'); });
}

function socialGeneraDraft() {
  var btn = document.getElementById('btn-genera-draft');
  if(btn){ btn.disabled=true; btn.textContent='⏳ Generazione...'; }
  fetch('/api/social/genera',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
    .then(function(r){return r.json();})
    .then(function(d){
      if(btn){ btn.disabled=false; btn.textContent='▶ Genera Draft'; }
      if(d.ok){
        showMsg('crm-msg','✅ Draft generato: '+d.draft_id,'ok');
        renderSocial();
      } else {
        showMsg('crm-msg','⚠️ '+(d.msg||'Impossibile generare draft'),'err');
      }
    })
    .catch(function(e){
      if(btn){ btn.disabled=false; btn.textContent='▶ Genera Draft'; }
      showMsg('crm-msg','❌ '+e.message,'err');
    });
}

function socialModificaDraft(draftId, triggerBtn) {
  var cont = document.getElementById('social-modal-container');
  if(!cont) return;
  // Carica il draft corrente
  fetch('/api/social/status').then(function(r){return r.json();}).then(function(d){
    var draft = (d.drafts||[]).find(function(x){return x.draft_id===draftId;});
    if(!draft){ alert('Draft non trovato'); return; }
    var mainLang = draft.lang || 'IT';
    var mainText = draft.text_main || (mainLang==='IT' ? draft.text_it : (mainLang==='ES' ? draft.text_es : ''));
    var isOther  = (mainLang !== 'IT' && mainLang !== 'ES');
    var html = '<h3 style="color:#F6AD55;margin-bottom:.3rem;font-size:1rem">✏ Modifica Draft</h3>'
      +'<p style="color:rgba(255,255,255,.4);font-size:.78rem;margin-bottom:1rem">'+draft.theme+' · '+draft.lang+' · '+draft.date+'</p>'
      +(isOther ? '<div style="margin-bottom:.8rem"><label style="font-size:.75rem;color:#F6AD55;display:block;margin-bottom:.25rem">Testo '+mainLang+' (principale — usato per post e mail)</label>'
        +'<textarea id="edit-text-main" style="width:100%;height:140px;background:rgba(0,0,0,.5);border:1px solid rgba(246,173,85,.3);border-radius:6px;color:#e0e0e0;padding:.5rem;font-size:.82rem;resize:vertical;line-height:1.5">'+mainText+'</textarea></div>' : '')
      +'<div style="margin-bottom:.8rem">'
      +'<label style="font-size:.75rem;color:rgba(255,255,255,.4);display:block;margin-bottom:.25rem">Testo IT</label>'
      +'<textarea id="edit-text-it" style="width:100%;height:'+(isOther?'70':'120')+'px;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem;font-size:.82rem;resize:vertical;line-height:1.5">'+((draft.text_it||''))+'</textarea>'
      +'</div>'
      +'<div style="margin-bottom:1rem">'
      +'<label style="font-size:.75rem;color:rgba(255,255,255,.4);display:block;margin-bottom:.25rem">Testo ES</label>'
      +'<textarea id="edit-text-es" style="width:100%;height:70px;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem;font-size:.82rem;resize:vertical;line-height:1.5">'+((draft.text_es||''))+'</textarea>'
      +'</div>'
      +'<div style="display:flex;gap:.5rem">'
      +'<button onclick="socialSalvaModifica(\''+draftId+'\')" style="flex:1;background:#2C5282;border:none;border-radius:7px;color:#F6AD55;padding:.6rem;font-size:.85rem;font-weight:600;cursor:pointer">💾 Salva</button>'
      +'<button onclick="socialChiudiModal()" style="background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:7px;color:rgba(255,255,255,.5);padding:.6rem .9rem;font-size:.85rem;cursor:pointer">Annulla</button>'
      +'</div>';
    cont.innerHTML = _socialModalOverlay(html,'socialChiudiModal()');
  });
}

function socialSalvaModifica(draftId) {
  var textIt   = (document.getElementById('edit-text-it')||{value:''}).value;
  var textEs   = (document.getElementById('edit-text-es')||{value:''}).value;
  var textMain = (document.getElementById('edit-text-main')||{value:''}).value;
  fetch('/api/social/draft/edit',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({draft_id:draftId,text_it:textIt,text_es:textEs,text_main:textMain||undefined})
  }).then(function(r){return r.json();}).then(function(d){
    if(d.ok){
      socialChiudiModal();
      showMsg('crm-msg','✅ Draft aggiornato','ok');
      renderSocial();
    } else {
      alert('Errore: '+(d.msg||'sconosciuto'));
    }
  });
}

function _socialModalOverlay(content, onclose) {
  return '<div id="social-modal" style="position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:1rem">'
    +'<div style="background:#1e293b;border:1px solid rgba(255,255,255,.1);border-radius:12px;padding:1.5rem;width:100%;max-width:540px;max-height:88vh;overflow-y:auto;position:relative">'
    +'<button onclick="'+onclose+'" style="position:absolute;top:.75rem;right:.75rem;background:none;border:none;color:rgba(255,255,255,.4);font-size:1.1rem;cursor:pointer">✕</button>'
    +content
    +'</div></div>';
}

function socialChiudiModal() {
  var m = document.getElementById('social-modal'); if(m) m.remove();
  var c = document.getElementById('social-modal-container'); if(c) c.innerHTML='';
}

function socialApriPubblicaOra() {
  var cont = document.getElementById('social-modal-container');
  if(!cont) return;
  var temi = ['SALARY_TRAP','TREND_MOBILIARE','VALUE_INTRO','5_FILTRI','EVFCF','PB_ROE','CASE_STUDY','ETF_SCREENING','FONDI_SCREENING','TEAM','LAUNCH','WEALTHOS_PROMO'];
  var lingue = ['IT','ES','EN','FR','DE'];
  var temiOpts = temi.map(function(t){return '<option value="'+t+'">'+t+'</option>';}).join('');
  var lingueOpts = lingue.map(function(l){return '<option value="'+l+'">'+l+'</option>';}).join('');
  var canali = ['linkedin','facebook','brevo'];
  var canaliChk = canali.map(function(ch){
    return '<label style="display:flex;align-items:center;gap:.4rem;font-size:.85rem;cursor:pointer">'
      +'<input type="checkbox" id="pub-ch-'+ch+'" checked style="accent-color:#F6AD55"> '+ch+'</label>';
  }).join('');
  var html = '<h3 style="color:#68D391;margin-bottom:.3rem;font-size:1rem">🚀 Pubblica Ora</h3>'
    +'<p style="color:rgba(255,255,255,.4);font-size:.78rem;margin-bottom:1rem">Genera e pubblica immediatamente un post sui canali selezionati.</p>'
    +'<div style="display:grid;grid-template-columns:1fr 1fr;gap:.8rem;margin-bottom:1rem">'
    +'<div><label style="font-size:.75rem;color:rgba(255,255,255,.4);display:block;margin-bottom:.3rem">Tema</label>'
    +'<select id="pub-tema" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.2);border-radius:6px;padding:.5rem;color:#e0e0e0;font-size:.88rem;outline:none">'+temiOpts+'</select></div>'
    +'<div><label style="font-size:.75rem;color:rgba(255,255,255,.4);display:block;margin-bottom:.3rem">Lingua</label>'
    +'<select id="pub-lang" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.2);border-radius:6px;padding:.5rem;color:#e0e0e0;font-size:.88rem;outline:none">'+lingueOpts+'</select></div>'
    +'</div>'
    +'<div style="margin-bottom:1rem"><label style="font-size:.75rem;color:rgba(255,255,255,.4);display:block;margin-bottom:.5rem">Canali</label>'
    +'<div style="display:flex;gap:1rem;flex-wrap:wrap">'+canaliChk+'</div></div>'
    +'<div style="display:flex;gap:.5rem">'
    +'<button id="btn-pub-ora" onclick="socialEseguiPubblicaOra()" style="flex:1;background:#276749;border:none;border-radius:7px;color:#68D391;padding:.7rem;font-size:.88rem;font-weight:700;cursor:pointer">🚀 Pubblica Subito</button>'
    +'<button onclick="socialChiudiModal()" style="background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:7px;color:rgba(255,255,255,.5);padding:.7rem .9rem;font-size:.88rem;cursor:pointer">Annulla</button>'
    +'</div><div id="pub-ora-msg" style="margin-top:.7rem;font-size:.82rem"></div>';
  cont.innerHTML = _socialModalOverlay(html,'socialChiudiModal()');
}

function socialEseguiPubblicaOra() {
  var tema = (document.getElementById('pub-tema')||{value:''}).value;
  var lang = (document.getElementById('pub-lang')||{value:'IT'}).value;
  var btn  = document.getElementById('btn-pub-ora');
  var msg  = document.getElementById('pub-ora-msg');
  if(!tema){ if(msg) msg.innerHTML='<span style="color:#FC8181">Seleziona un tema</span>'; return; }
  if(btn){ btn.disabled=true; btn.textContent='⏳ Generazione in corso...'; }
  if(msg) msg.innerHTML='<span style="color:rgba(255,255,255,.4)">Generazione testo e pubblicazione...</span>';
  fetch('/api/social/genera',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({theme:tema,lang:lang})
  }).then(function(r){return r.json();}).then(function(d){
    if(btn){ btn.disabled=false; btn.textContent='🚀 Pubblica Subito'; }
    if(d.ok){
      if(msg) msg.innerHTML='<span style="color:#68D391">✅ Pubblicato! Draft: '+d.draft_id+'</span>';
      setTimeout(function(){ socialChiudiModal(); renderSocial(); }, 1500);
    } else {
      if(msg) msg.innerHTML='<span style="color:#FC8181">❌ '+(d.msg||'Errore sconosciuto')+'</span>';
    }
  }).catch(function(e){
    if(btn){ btn.disabled=false; btn.textContent='🚀 Pubblica Subito'; }
    if(msg) msg.innerHTML='<span style="color:#FC8181">❌ '+e.message+'</span>';
  });
}

function renderWhatsappSub() {
  if(!_clienti) { loadClienti(); return; }
  var all = (_clienti.tester||[]).concat(_clienti.clienti||[]);
  var optIn = all.filter(function(c){ return c.whatsapp_optin === true; });
  var el = document.getElementById('whatsapp-content');

  var kpi = '<div class="kpi-row" style="margin-bottom:1.2rem">'
    +'<div class="kpi"><div class="kpi-label">📱 Opt-in WA</div><div class="kpi-val" style="color:#68D391">'+optIn.length+'</div></div>'
    +'<div class="kpi"><div class="kpi-label">👥 Tot. clienti</div><div class="kpi-val">'+all.length+'</div></div>'
    +'</div>';

  var statoBox = '<div class="box" style="margin-bottom:1rem">'
    +'<h3 style="color:#F6AD55;margin-bottom:.7rem">💬 Stato WhatsApp Business</h3>'
    +'<div style="background:rgba(252,129,129,.08);border:1px solid rgba(252,129,129,.3);border-radius:8px;padding:.8rem 1rem;font-size:.85rem;margin-bottom:.8rem">'
    +'⚠️ In attesa: Meta Business Manager verificato (CIF B23881691) + numero dedicato + template approvati'
    +'</div>'
    +'<div style="font-size:.83rem;line-height:1.9;opacity:.7">'
    +'⏳ Template <strong>screener_pronto</strong> (4 parametri) — da sottomettere a Meta<br>'
    +'⏳ Template <strong>brief_mattutino</strong> (3 parametri) — da sottomettere a Meta<br>'
    +'📄 Procedura: <code>01_DOCUMENTAZIONE_OPERATIVA/WhatsApp_Business_Setup_Procedura.md</code>'
    +'</div></div>';

  var optInTable = '';
  if(optIn.length > 0) {
    var rows = '';
    optIn.forEach(function(c){
      var nome = ((c.nome||'')+' '+(c.cognome||'')).trim()||'—';
      var piani = [c.piano_azioni,c.piano_etf,c.piano_fondi].filter(function(p){return p&&p!=='NONE';}).join(' / ')||'—';
      rows += '<tr><td>'+nome+'</td><td style="font-size:.8rem;opacity:.7">'+c.email+'</td><td style="font-size:.82rem">'+piani+'</td></tr>';
    });
    optInTable = '<div class="box"><h4 style="opacity:.7;font-size:.85rem;margin-bottom:.7rem">Clienti con consenso WhatsApp</h4>'
      +'<div class="tbl-wrap"><table><thead><tr><th>Nome</th><th>Email</th><th>Piani</th></tr></thead><tbody>'+rows+'</tbody></table></div></div>';
  } else {
    optInTable = '<div class="box" style="opacity:.5;font-size:.85rem">Nessun cliente ha ancora attivato le notifiche WhatsApp. Usa il bottone 📱 nella tab Clienti per ogni singolo cliente.</div>';
  }

  el.innerHTML = kpi + statoBox + optInTable;
}

// ─── PIPELINE ─────────────────────────────────────────────────
var _pipelineSearch = '';

function pipelineSearch(val){
  _pipelineSearch = val;
  renderPipelineKanban();
}

function loadPipelineData(){
  var tasks = 0;
  var done = function(){
    tasks--;
    if(tasks<=0) renderPipelineKanban();
  };
  if(!_clienti){
    tasks++;
    fetch('/api/clienti').then(function(r){return r.json();}).then(function(d){_clienti=d;done();}).catch(done);
  } else tasks = 0;
  if(!_prospect){
    tasks++;
    fetch('/api/prospect').then(function(r){return r.json();}).then(function(d){_prospect=d.items||[];done();}).catch(done);
  }
  if(tasks===0) renderPipelineKanban();
}

var PIPELINE_COLS = [
  {stato:'Da Contattare',    label:'Lead',             color:'#9ca3af', source:'prospect'},
  {stato:'Contattato',       label:'Contattato',       color:'#60a5fa', source:'prospect'},
  {stato:'Interessato',      label:'Interessato',      color:'#34d399', source:'prospect'},
  {stato:'Prospect LinkedIn',label:'Prospect LinkedIn',color:'#0A66C2', source:'prospect'},
  {stato:'TESTER',           label:'Tester',           color:'#F6AD55', source:'clienti'},
  {stato:'ATTIVO',           label:'Abbonato',         color:'#68D391', source:'clienti'},
];

var INTERESSE_COLOR = {Azioni:'#4A90D9',ETF:'#68D391',Fondi:'#F6AD55',Tutti:'#a78bfa',WealthOS:'#c9a84c'};

function renderPipelineKanban(){
  var board = document.getElementById('pipeline-board');
  var strip = document.getElementById('pipeline-strip');
  var statsLbl = document.getElementById('pipeline-stats-label');
  if(!board) return;

  var tester  = (_clienti ? (_clienti.tester||[]) : []);
  var attivi  = (_clienti ? (_clienti.clienti||[]).filter(function(c){return c.stato==='ATTIVO';}) : []);
  var prospect = _prospect || [];

  var q = _pipelineSearch.toLowerCase();

  function matchSearch(nome, cognome, email){
    if(!q) return true;
    return ((nome||'')+(cognome||'')).toLowerCase().indexOf(q)>=0 || (email||'').toLowerCase().indexOf(q)>=0;
  }

  var totalCount = prospect.filter(function(p){return p.stato!=='Non Interessato'&&p.stato!=='Promosso ✓';}).length + tester.length + attivi.length;
  if(statsLbl) statsLbl.textContent = totalCount + ' contatti attivi';

  var boardHtml = '';

  PIPELINE_COLS.forEach(function(col){
    var cards = [];

    if(col.source === 'prospect'){
      cards = prospect.filter(function(p){
        return p.stato === col.stato && matchSearch(p.nome, p.cognome, p.email);
      });
    } else if(col.stato === 'TESTER'){
      cards = tester.filter(function(c){
        return matchSearch(c.nome, c.cognome, c.email);
      });
    } else if(col.stato === 'ATTIVO'){
      cards = attivi.filter(function(c){
        return matchSearch(c.nome, c.cognome, c.email);
      });
    }

    boardHtml += '<div style="flex-shrink:0;width:220px;background:rgba(255,255,255,.03);border:1px solid '+col.color+'33;border-radius:10px;padding:.75rem">';
    var colHeaderExtra = '';
    if(col.stato === 'Prospect LinkedIn' && cards.length > 0){
      colHeaderExtra = '<button onclick="pipelineEsportaLinkedIn()" style="background:rgba(10,102,194,.15);border:1px solid rgba(10,102,194,.35);border-radius:5px;color:#0A66C2;padding:.1rem .4rem;font-size:.68rem;cursor:pointer" title="Esporta CSV per LinkedIn Ads">⬇ Ads</button>';
    }
    boardHtml += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.7rem">'
      +'<span style="font-weight:700;font-size:.83rem;color:'+col.color+'">'+col.label+'</span>'
      +'<div style="display:flex;align-items:center;gap:.35rem">'
      +colHeaderExtra
      +'<span style="background:'+col.color+'22;color:'+col.color+';border-radius:10px;padding:.1rem .55rem;font-size:.74rem;font-weight:700">'+cards.length+'</span>'
      +'</div>'
      +'</div>';

    if(cards.length === 0){
      boardHtml += '<div style="opacity:.25;font-size:.76rem;text-align:center;padding:1.5rem 0">—</div>';
    } else {
      cards.forEach(function(c){
        var nome = (c.nome||'') + (c.cognome?' '+c.cognome:'') || (c.ragione_sociale||'');
        var email = c.email || '';
        var interesse = c.interesse || (c.piano_azioni&&c.piano_azioni!=='NONE'?'Azioni':c.piano_etf&&c.piano_etf!=='NONE'?'ETF':c.piano_fondi&&c.piano_fondi!=='NONE'?'Fondi':'');
        var intColor = INTERESSE_COLOR[interesse] || '#888';
        var cardActions = '';
        if(col.source === 'prospect'){
          var nextStato = col.stato === 'Da Contattare' ? 'Contattato' : col.stato === 'Contattato' ? 'Interessato' : col.stato === 'Interessato' ? 'Prospect LinkedIn' : null;
          if(nextStato){
            cardActions += '<button onclick="pipelineAvanza('+c.id+',\''+nextStato+'\')" style="font-size:.68rem;background:'+col.color+'22;color:'+col.color+';border:1px solid '+col.color+'44;border-radius:4px;padding:.1rem .4rem;cursor:pointer;margin-right:.25rem" title="Avanza stato">▶</button>';
          }
          if(col.stato === 'Prospect LinkedIn'){
            var liUrl = c.linkedin_url || '';
            var liHref = liUrl ? liUrl : 'https://www.linkedin.com/search/results/people/?keywords='+encodeURIComponent((c.nome||'')+(c.cognome?' '+c.cognome:''));
            cardActions += '<a href="'+liHref+'" target="_blank" style="font-size:.68rem;background:rgba(10,102,194,.15);color:#0A66C2;border:1px solid rgba(10,102,194,.35);border-radius:4px;padding:.1rem .4rem;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;gap:2px" title="'+(liUrl?'Apri profilo LinkedIn':'Cerca su LinkedIn')+'"><svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zM9 17H6.5v-7H9v7zm-1.3-8a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm9.3 8h-2.5v-3.5c0-.8-.7-1.5-1.5-1.5s-1.5.7-1.5 1.5V17H9v-7h2.5v1a3 3 0 015.5 1.7V17z"/></svg> LinkedIn</a>';
          }
          cardActions += '<button onclick="promuoviProspect('+(_prospect?_prospect.indexOf(c):0)+')" style="font-size:.68rem;background:rgba(246,173,85,.15);color:#F6AD55;border:1px solid rgba(246,173,85,.3);border-radius:4px;padding:.1rem .4rem;cursor:pointer" title="Promuovi a Tester">▲</button>';
        }
        boardHtml += '<div style="background:rgba(0,0,0,.25);border-radius:7px;padding:.6rem .7rem;margin-bottom:.45rem;border:1px solid rgba(255,255,255,.06)">'
          +'<div style="font-weight:600;font-size:.81rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:.2rem">'+nome+'</div>'
          +'<div style="font-size:.72rem;opacity:.55;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:.35rem">'+email+'</div>'
          +(interesse?'<span style="font-size:.68rem;background:'+intColor+'22;color:'+intColor+';border-radius:4px;padding:.1rem .35rem">'+interesse+'</span>':'')
          +(cardActions?'<div style="margin-top:.4rem;display:flex;gap:.25rem">'+cardActions+'</div>':'')
          +'</div>';
      });
    }
    boardHtml += '</div>';
  });

  board.innerHTML = boardHtml;

  // Strip Non Interessato + Sospeso
  var nonInt = prospect.filter(function(p){return p.stato==='Non Interessato';});
  var sospesi = (_clienti ? ((_clienti.tester||[]).concat(_clienti.clienti||[])).filter(function(c){return c.stato==='SOSPESO';}) : []);
  var stripHtml = '';
  if(nonInt.length>0){
    stripHtml += '<div style="border:1px solid rgba(248,113,113,.25);border-radius:9px;padding:.6rem .9rem;background:rgba(248,113,113,.05);flex:1;min-width:200px">'
      +'<div style="font-size:.75rem;font-weight:700;color:#f87171;margin-bottom:.45rem">✕ Non Interessato ('+nonInt.length+')</div>'
      +'<div style="display:flex;flex-wrap:wrap;gap:.3rem">'
      + nonInt.map(function(p){return '<span style="font-size:.72rem;background:rgba(0,0,0,.2);border-radius:5px;padding:.15rem .45rem;opacity:.7">'+(p.nome||'')+(p.cognome?' '+p.cognome:'')+'</span>';}).join('')
      +'</div></div>';
  }
  if(sospesi.length>0){
    stripHtml += '<div style="border:1px solid rgba(156,163,175,.25);border-radius:9px;padding:.6rem .9rem;background:rgba(156,163,175,.05);flex:1;min-width:200px">'
      +'<div style="font-size:.75rem;font-weight:700;color:#9ca3af;margin-bottom:.45rem">⏸ Sospesi ('+sospesi.length+')</div>'
      +'<div style="display:flex;flex-wrap:wrap;gap:.3rem">'
      + sospesi.map(function(c){return '<span style="font-size:.72rem;background:rgba(0,0,0,.2);border-radius:5px;padding:.15rem .45rem;opacity:.7">'+(c.nome||'')+(c.cognome?' '+c.cognome:'')+'</span>';}).join('')
      +'</div></div>';
  }
  if(strip) strip.innerHTML = stripHtml;
}

function pipelineAvanza(id, nuovoStato){
  fetch('/api/prospect/update',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:id, stato:nuovoStato})
  }).then(function(r){return r.json();}).then(function(res){
    if(res.ok){
      var p = (_prospect||[]).find(function(x){return x.id===id;});
      if(p){ p.stato = nuovoStato; renderPipelineKanban(); }
    }
  });
}

function pipelineEsportaLinkedIn(){
  var data = (_prospect||[]).filter(function(p){return p.stato==='Prospect LinkedIn';});
  if(!data.length){ alert('Nessun Prospect LinkedIn da esportare'); return; }
  var bom = '﻿';
  var header = 'Email,Nome,LinkedIn';
  var righe = data.map(function(p){
    var nome = ((p.nome||'')+(p.cognome?' '+p.cognome:'')).trim();
    return p.email+',"'+nome.replace(/"/g,'""')+'",'+(p.linkedin_url||'');
  }).join('\n');
  var blob = new Blob([bom+header+'\n'+righe], {type:'text/csv;charset=utf-8'});
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a'); a.href=url; a.download='prospect-linkedin-ads.csv';
  a.click(); URL.revokeObjectURL(url);
}

function importApolloFile(input) {
  var file = input.files[0];
  if(!file) return;
  input.value = '';
  var reader = new FileReader();
  reader.onload = function(e) {
    var csv = e.target.result;
    fetch('/api/prospect/import-apollo', {
      method: 'POST',
      headers: {'Content-Type': 'text/plain; charset=utf-8'},
      body: csv
    }).then(function(r){return r.json();}).then(function(d){
      if(!d.ok){ alert('Errore import Apollo: '+(d.msg||'sconosciuto')); return; }
      alert('Apollo.io import completato!\nInseriti: '+d.inseriti+'\nDuplicati: '+d.duplicati+'\nCon LinkedIn: '+d.con_linkedin);
      _prospect = null;
      loadCrmData();
    }).catch(function(e){ alert('Errore: '+e); });
  };
  reader.readAsText(file, 'UTF-8');
}

function mostraNuovoLead(){
  document.getElementById('modal-nuovo-lead').style.display='flex';
  document.getElementById('nl-nome').value='';
  document.getElementById('nl-cognome').value='';
  document.getElementById('nl-email').value='';
  document.getElementById('nl-fonte').value='';
}

function confermaNuovoLead(){
  var nome=document.getElementById('nl-nome').value.trim();
  var email=document.getElementById('nl-email').value.trim();
  if(!nome||!email){alert('Nome ed email obbligatori');return;}
  fetch('/api/prospect/aggiungi',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
      nome:nome,
      cognome:document.getElementById('nl-cognome').value.trim(),
      email:email,
      fonte:document.getElementById('nl-fonte').value.trim()||'Manuale',
      interesse:document.getElementById('nl-interesse').value,
    })
  }).then(function(r){return r.json();}).then(function(res){
    document.getElementById('modal-nuovo-lead').style.display='none';
    if(res.ok){
      _prospect=null;
      loadPipelineData();
      showMsg('crm-msg','✅ Lead aggiunto','ok');
    } else showMsg('crm-msg','❌ '+res.msg,'err');
  });
}

// ═══════════════════════════════════════════════════════════════
// PROSPECT
// ═══════════════════════════════════════════════════════════════
var _prospect = null;
var _prospectFiltroStato = '';
var _prospectRicerca = '';
var _notaProspectIdx = -1;

var PROSPECT_STATI = [
  {value:'Da Contattare',    color:'#9ca3af'},
  {value:'Contattato',       color:'#60a5fa'},
  {value:'Interessato',      color:'#34d399'},
  {value:'Prospect LinkedIn',color:'#0A66C2'},
  {value:'Non Interessato',  color:'#f87171'},
  {value:'Promosso ✓', color:'#a78bfa'},
];

function loadProspect(){
  fetch('/api/prospect').then(function(r){
    if(!r.ok||r.redirected) throw new Error('Sessione scaduta');
    return r.json();
  }).then(function(d){
    _prospect = d.items || [];
    renderProspect();
  }).catch(function(e){ showMsg('crm-msg','❌ '+e.message,'err'); });
}

function setProspectFiltro(stato){
  _prospectFiltroStato = stato;
  renderProspect();
}

function prospectSearch(val){
  _prospectRicerca = val;
  renderProspect();
}

function renderProspect(){
  if(!_prospect) return;
  var list = _prospect.slice();
  if(_prospectFiltroStato) list = list.filter(function(p){ return p.stato === _prospectFiltroStato; });
  if(_prospectRicerca){
    var q = _prospectRicerca.toLowerCase();
    list = list.filter(function(p){
      return ((p.nome||'')+(p.cognome||'')).toLowerCase().indexOf(q)>=0
          || (p.email||'').toLowerCase().indexOf(q)>=0
          || (p.fonte||'').toLowerCase().indexOf(q)>=0;
    });
  }

  var totale = _prospect.length;
  var conteggi = {};
  _prospect.forEach(function(p){ conteggi[p.stato] = (conteggi[p.stato]||0)+1; });

  // Chips filtro
  var chipStyle = 'padding:.3rem .8rem;border-radius:14px;border:1px solid rgba(255,255,255,.15);background:transparent;color:rgba(255,255,255,.5);cursor:pointer;font-size:.78rem;font-weight:600;transition:all .15s';
  var chipsHtml = '<div style="display:flex;gap:.4rem;flex-wrap:wrap">';
  var allActive = !_prospectFiltroStato ? ';background:#2C5282;border-color:#2C5282;color:#F6AD55' : '';
  chipsHtml += '<button onclick="setProspectFiltro(\'\')" style="'+chipStyle+allActive+'">Tutti ('+totale+')</button>';
  PROSPECT_STATI.forEach(function(s){
    var cnt = conteggi[s.value] || 0;
    var active = (_prospectFiltroStato===s.value) ? ';background:'+s.color+'22;border-color:'+s.color+';color:'+s.color : '';
    chipsHtml += '<button onclick="setProspectFiltro(\''+s.value+'\')" style="'+chipStyle+active+'">'+s.value+' ('+cnt+')</button>';
  });
  chipsHtml += '</div>';

  // Righe tabella
  var rows = list.map(function(p){
    var idx = _prospect.indexOf(p);
    var bg = list.indexOf(p)%2===0?'rgba(255,255,255,.02)':'transparent';
    var sc = PROSPECT_STATI.find(function(s){return s.value===p.stato;})||{color:'#888'};
    var statoBadge = '<span style="background:'+sc.color+'22;color:'+sc.color+';border:1px solid '+sc.color+'44;border-radius:12px;padding:.12rem .5rem;font-size:.72rem;font-weight:600;white-space:nowrap">'+p.stato+'</span>';
    var statoSel = '<select onchange="aggiornaStatoProspect('+idx+',this.value)" style="background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.25rem .4rem;color:#e0e0e0;font-size:.74rem;outline:none">'
      + PROSPECT_STATI.map(function(s){ return '<option value="'+s.value+'"'+(p.stato===s.value?' selected':'')+'>'+s.value+'</option>'; }).join('')
      + '</select>';
    var notaBtn = p.note
      ? '<button class="btn" style="padding:.18rem .45rem;font-size:.71rem;border-color:rgba(246,173,85,.4);color:#F6AD55" onclick="mostraNotaProspect('+idx+')" title="'+p.note.replace(/"/g,'\'')+'">📝</button>'
      : '<button class="btn" style="padding:.18rem .45rem;font-size:.71rem;opacity:.4" onclick="mostraNotaProspect('+idx+')">nota</button>';
    var liBtn = p.linkedin_url
      ? '<a href="'+p.linkedin_url+'" target="_blank" class="btn" style="padding:.18rem .45rem;font-size:.71rem;border-color:rgba(10,102,194,.4);color:#4A90D9;text-decoration:none" title="LinkedIn">in</a>'
      : '';
    var promuoviBtn = (p.stato !== 'Promosso ✓')
      ? '<button class="btn btn-gr" style="padding:.18rem .55rem;font-size:.71rem" onclick="promuoviProspect('+idx+')" title="Promuovi a Tester">▲ Tester</button>'
      : '<span style="color:#a78bfa;font-size:.75rem;padding:.2rem .4rem">✓ Tester</span>';
    var delBtn = '<button class="btn" style="padding:.18rem .4rem;font-size:.71rem;border-color:rgba(239,68,68,.35);color:#f87171" onclick="eliminaProspect('+idx+',\''+p.email+'\')">🗑</button>';
    var ult = p.data_ultimo_contatto ? p.data_ultimo_contatto.slice(0,10) : '<span style="opacity:.3">—</span>';
    return '<tr style="background:'+bg+'">'
      +'<td style="padding:.4rem .8rem;font-size:.84rem;font-weight:500">'+((p.nome||'')+(p.cognome?' '+p.cognome:''))+'</td>'
      +'<td style="padding:.4rem .8rem;font-size:.79rem;opacity:.7">'+p.email+'</td>'
      +'<td style="padding:.4rem .8rem;font-size:.77rem;opacity:.6">'+(p.fonte||'—')+'</td>'
      +'<td style="padding:.4rem .8rem;font-size:.77rem">'+(p.interesse||'—')+'</td>'
      +'<td style="padding:.4rem .8rem">'+statoSel+'</td>'
      +'<td style="padding:.4rem .8rem;font-size:.75rem;opacity:.65">'+ult+'</td>'
      +'<td style="padding:.4rem .8rem"><div style="display:flex;gap:.25rem;align-items:center">'+notaBtn+liBtn+promuoviBtn+delBtn+'</div></td>'
      +'</tr>';
  }).join('') || '<tr><td colspan="7" style="padding:2rem;text-align:center;opacity:.4">Nessun prospect trovato. Importa un CSV per iniziare.</td></tr>';

  var chips = document.getElementById('prospect-chips');
  if(chips) chips.innerHTML = chipsHtml;
  var tbody = document.getElementById('prospect-tbody');
  if(tbody) tbody.innerHTML = rows;
  var cnt = document.getElementById('prospect-count');
  if(cnt) cnt.textContent = totale + ' prospect totali';
}

function aggiornaStatoProspect(idx, stato){
  var p = _prospect[idx]; if(!p) return;
  fetch('/api/prospect/update',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:p.id, stato:stato})
  }).then(function(r){return r.json();}).then(function(res){
    if(res.ok){ p.stato = stato; renderProspect(); }
    else showMsg('crm-msg','❌ '+res.msg,'err');
  });
}

function mostraNotaProspect(idx){
  _notaProspectIdx = idx;
  var p = _prospect[idx]; if(!p) return;
  var el = document.getElementById('modal-nota-prospect');
  document.getElementById('modal-nota-nome').textContent = (p.nome||'')+(p.cognome?' '+p.cognome:'')+' — '+p.email;
  document.getElementById('modal-nota-testo').value = p.note || '';
  document.getElementById('modal-nota-data').value = p.data_ultimo_contatto ? p.data_ultimo_contatto.slice(0,10) : '';
  el.style.display = 'flex';
}

function salvaNotaProspect(){
  var p = _prospect[_notaProspectIdx]; if(!p) return;
  var nota = document.getElementById('modal-nota-testo').value.trim();
  var data = document.getElementById('modal-nota-data').value || null;
  fetch('/api/prospect/update',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:p.id, note:nota, data_ultimo_contatto:data})
  }).then(function(r){return r.json();}).then(function(res){
    document.getElementById('modal-nota-prospect').style.display='none';
    if(res.ok){
      p.note = nota;
      p.data_ultimo_contatto = data;
      renderProspect();
      showMsg('crm-msg','✅ Nota salvata','ok');
    } else showMsg('crm-msg','❌ '+res.msg,'err');
  });
}

function promuoviProspect(idx){
  var p = _prospect[idx]; if(!p) return;
  if(!confirm('Promuovi '+p.nome+' '+p.cognome+' ('+p.email+') come Tester?')) return;
  fetch('/api/prospect/promuovi',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:p.id})
  }).then(function(r){return r.json();}).then(function(res){
    if(res.ok){
      p.stato = 'Promosso ✓';
      _clienti = null;
      renderProspect();
      showMsg('crm-msg','✅ Promosso a Tester. Vai nella tab Clienti per attivarlo.','ok');
    } else showMsg('crm-msg','❌ '+res.msg,'err');
  });
}

function eliminaProspect(idx, email){
  var p = _prospect[idx]; if(!p) return;
  if(!confirm('Eliminare prospect '+email+'?')) return;
  fetch('/api/prospect/elimina',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:p.id})
  }).then(function(r){return r.json();}).then(function(res){
    if(res.ok){ _prospect.splice(idx,1); renderProspect(); showMsg('crm-msg','🗑 Prospect eliminato','ok'); }
    else showMsg('crm-msg','❌ '+res.msg,'err');
  });
}

function importProspectCSV(input){
  var file = input.files[0]; if(!file) return;
  var reader = new FileReader();
  reader.onload = function(e){
    var csv = e.target.result;
    fetch('/api/prospect/import',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({csv_content:csv})
    }).then(function(r){return r.json();}).then(function(res){
      input.value = '';
      // Mostra risultato nel box giusto (pipeline o prospect)
      var boxId = document.getElementById('pipeline-import-result') ? 'pipeline-import-result' : 'prospect-import-result';
      var box = document.getElementById(boxId);
      if(res.ok){
        if(box){ box.style.display=''; box.innerHTML='✅ Import completato — Inseriti: <strong>'+res.inseriti+'</strong>'+(res.duplicati?' · Duplicati: <strong>'+res.duplicati+'</strong>':'')+(res.errori?' · Errori: <strong>'+res.errori+'</strong>':''); }
        _prospect = null;
        if(_crmSubActive==='pipeline') loadPipelineData();
        else loadProspect();
        showMsg('crm-msg','✅ Importati '+res.inseriti+' prospect','ok');
      } else {
        if(box){ box.style.display=''; box.style.borderColor='rgba(252,129,129,.3)'; box.innerHTML='❌ '+res.msg; }
        showMsg('crm-msg','❌ '+res.msg,'err');
      }
    }).catch(function(e){ showMsg('crm-msg','❌ '+e.message,'err'); });
  };
  reader.readAsText(file, 'UTF-8');
}

function exportProspect(){
  window.location.href = '/api/prospect/export';
}

// ═══════════════════════════════════════════════════════════════
// CALENDARIO EDITORIALE
// ═══════════════════════════════════════════════════════════════
var _calYear = new Date().getFullYear();
var _calMonth = new Date().getMonth(); // 0-based

function calNav(dir){
  _calMonth += dir;
  if(_calMonth < 0){ _calMonth = 11; _calYear--; }
  if(_calMonth > 11){ _calMonth = 0; _calYear++; }
  renderCalendario();
}

function renderCalendario(){
  var MESI = ['Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno',
              'Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre'];
  var GIORNI = ['Lun','Mar','Mer','Gio','Ven','Sab','Dom'];
  var lbl = document.getElementById('cal-month-label');
  if(lbl) lbl.textContent = MESI[_calMonth] + ' ' + _calYear;

  // Genera eventi fissi (schedule screener) per il mese corrente
  var eventi = {};
  var primoGiorno = new Date(_calYear, _calMonth, 1);
  var ultimoGiorno = new Date(_calYear, _calMonth+1, 0).getDate();

  for(var d=1; d<=ultimoGiorno; d++){
    var dt = new Date(_calYear, _calMonth, d);
    var wd = dt.getDay(); // 0=Dom, 1=Lun, ..., 6=Sab
    var key = d;
    eventi[key] = eventi[key] || [];
    // Lun-Ven: invio Azioni 23:00
    if(wd>=1 && wd<=5){
      eventi[key].push({tipo:'screener', label:'📈 Azioni 23:00', color:'#4A90D9'});
    }
    // Lun, Mer, Ven: invio ETF + Fondi 23:30
    if(wd===1||wd===3||wd===5){
      eventi[key].push({tipo:'screener', label:'📦 ETF+Fondi 23:30', color:'#68D391'});
    }
    // Lun, Mer, Ven: social post (se scheduler attivo)
    if(wd===1||wd===3||wd===5){
      eventi[key].push({tipo:'social', label:'📱 Social 08:00', color:'#F6AD55'});
    }
  }

  // Grid calendario
  var firstWeekday = (new Date(_calYear, _calMonth, 1).getDay() + 6) % 7; // 0=Lun
  var html = '<div class="box">';
  html += '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:2px;margin-bottom:.4rem">';
  GIORNI.forEach(function(g){
    html += '<div style="text-align:center;font-size:.72rem;font-weight:700;opacity:.45;padding:.3rem">'+g+'</div>';
  });
  html += '</div>';
  html += '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px">';

  // Celle vuote prima del 1
  for(var i=0; i<firstWeekday; i++){
    html += '<div style="min-height:80px"></div>';
  }

  var today = new Date();
  for(var d=1; d<=ultimoGiorno; d++){
    var isToday = (today.getDate()===d && today.getMonth()===_calMonth && today.getFullYear()===_calYear);
    var ev = eventi[d] || [];
    var border = isToday ? 'border:2px solid #F6AD55' : 'border:1px solid rgba(255,255,255,.07)';
    html += '<div style="min-height:80px;background:rgba(255,255,255,.03);border-radius:6px;padding:.4rem .35rem;'+border+'">'
      +'<div style="font-size:.78rem;font-weight:700;'+(isToday?'color:#F6AD55':'opacity:.5')+';margin-bottom:.3rem">'+d+'</div>';
    ev.forEach(function(e){
      html += '<div style="font-size:.66rem;background:'+e.color+'22;color:'+e.color+';border-radius:4px;padding:.15rem .3rem;margin-bottom:.2rem;line-height:1.3">'+e.label+'</div>';
    });
    html += '</div>';
  }

  html += '</div></div>';

  // Legenda
  html += '<div class="box" style="margin-top:1rem">'
    +'<h4 style="opacity:.55;font-size:.8rem;margin-bottom:.7rem">LEGENDA INVII AUTOMATICI</h4>'
    +'<div style="display:flex;flex-wrap:wrap;gap:1rem;font-size:.82rem">'
    +'<div><span style="color:#4A90D9">■</span> Azioni — Lun/Mar/Mer/Gio/Ven alle 23:00</div>'
    +'<div><span style="color:#68D391">■</span> ETF + Fondi — Lun/Mer/Ven alle 23:30</div>'
    +'<div><span style="color:#F6AD55">■</span> Social Post — Lun/Mer/Ven alle 08:00 (se scheduler attivo)</div>'
    +'</div></div>';

  var el = document.getElementById('calendario-content');
  if(el) el.innerHTML = html;
}

// ─── SCREENER PARAMS (parametri.json) ────────────────────────
var _scrParams = null;

function loadScreenerParams(){
  fetch('/api/params').then(function(r){
    if(!r.ok || r.redirected) throw new Error('Sessione scaduta — effettua il login');
    var ct = r.headers.get('content-type')||'';
    if(!ct.includes('json')) throw new Error('Sessione scaduta — effettua il login');
    return r.json();
  }).then(function(data){
    _scrParams = data;
    renderScreenerParams();
  }).catch(function(e){
    document.getElementById('scr-params-content').innerHTML =
      '<span style="color:#F6AD55">⚠️ '+e.message+'</span>';
  });
}

function renderScreenerParams(){
  if(!_scrParams){loadScreenerParams();return;}
  var sections = ['azioni','etf','fondi'];
  var inputStyle = 'width:100%;background:rgba(0,0,0,.3);border:1px solid rgba(255,255,255,.15);border-radius:6px;padding:.4rem .6rem;color:#e0e0e0;font-size:.9rem;margin-top:.3rem;outline:none';
  var html = '';
  sections.forEach(function(asset){
    var params = _scrParams[asset];
    if(!params) return;
    html += '<div style="margin-bottom:1.4rem">'
          + '<h4 style="margin:0 0 .6rem;opacity:.7">'+ICONS[asset]+' '+asset.toUpperCase()+'</h4>'
          + '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:.7rem">';
    Object.keys(params).forEach(function(key){
      var p = params[key];
      var label = SP_LABELS[key] || key;
      if(typeof p.value === 'boolean'){
        html += '<div style="background:rgba(255,255,255,.04);border-radius:8px;padding:.7rem .9rem;display:flex;align-items:center">'
              + '<label style="display:flex;align-items:center;gap:.6rem;cursor:pointer;width:100%">'
              + '<input type="checkbox" class="sp-inp" data-asset="'+asset+'" data-param="'+key+'"'+(p.value?' checked':'')
              + ' style="width:1.1rem;height:1.1rem;accent-color:#F6AD55;cursor:pointer">'
              + '<span style="font-size:.88rem">'+label+'</span></label></div>';
      } else {
        var step = SP_STEP[key] || 0.05;
        var rangeInfo = (p.min!==undefined) ? '<div style="font-size:.68rem;opacity:.38;margin-top:.2rem">min: '+p.min+' — max: '+p.max+'</div>' : '';
        html += '<div style="background:rgba(255,255,255,.04);border-radius:8px;padding:.7rem .9rem">'
              + '<div style="font-size:.82rem;opacity:.6;margin-bottom:.3rem">'+label+'</div>'
              + '<input type="number" class="sp-inp" data-asset="'+asset+'" data-param="'+key+'"'
              + ' min="'+(p.min!==undefined?p.min:'')+'" max="'+(p.max!==undefined?p.max:'')+'"'
              + ' step="'+step+'" value="'+p.value+'" style="'+inputStyle+'">'
              + rangeInfo+'</div>';
      }
    });
    html += '</div></div>';
  });
  var el = document.getElementById('scr-params-content');
  el.innerHTML = html;
  el.style.opacity = '1';
}

function saveScreenerParams(){
  if(!_scrParams)return;
  var data = JSON.parse(JSON.stringify(_scrParams));
  document.querySelectorAll('#scr-params-content .sp-inp').forEach(function(inp){
    var asset=inp.dataset.asset, key=inp.dataset.param;
    if(!data[asset]||!data[asset][key]) return;
    if(inp.type==='checkbox'){
      data[asset][key].value = inp.checked;
    } else {
      data[asset][key].value = parseFloat(inp.value);
    }
  });
  data.meta = {last_modified: new Date().toISOString(), modified_by:'admin', version:'1.0'};
  fetch('/api/params',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})
    .then(function(r){return r.json();}).then(function(res){
      if(res.ok){_scrParams=data; showMsg('sp-msg','✅ Parametri screener salvati','ok');}
      else showMsg('sp-msg','❌ '+res.msg,'err');
    }).catch(function(e){showMsg('sp-msg','❌ '+e.message,'err');});
}

// ═══════════════════════════════════════════════
// CLOCK
// ═══════════════════════════════════════════════
function tick(){
  var n=new Date();
  document.getElementById('clock').textContent=n.toLocaleString('it-IT',{weekday:'short',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'});
}
setInterval(tick,1000); tick();

// ═══════════════════════════════════════════════
// TABS
// ═══════════════════════════════════════════════
// ── EMAIL LOG ──────────────────────────────────────────────────────────────
var _elogData = {};
function loadEmailLog(){
  fetch('/api/email-log').then(function(r){return r.json();}).then(function(d){
    _elogData = d;
    var total = 0, ok = 0;
    Object.values(d).forEach(function(arr){ total+=arr.length; arr.forEach(function(e){ if(e.status==='OK')ok++; }); });
    var s = document.getElementById('elog-stats');
    if(s) s.innerHTML =
      '<div style="background:rgba(44,82,130,.2);border:1px solid #2C5282;border-radius:8px;padding:.6rem 1rem;font-size:.84rem">' +
        '<span style="color:#90cdf4">Destinatari:</span> <strong>' + Object.keys(d).length + '</strong>' +
      '</div>' +
      '<div style="background:rgba(104,211,145,.1);border:1px solid #276749;border-radius:8px;padding:.6rem 1rem;font-size:.84rem">' +
        '<span style="color:#68D391">Invii OK:</span> <strong>' + ok + ' / ' + total + '</strong>' +
      '</div>';
    elogRender();
  }).catch(function(){});
}
function elogRender(){
  var filterType   = (document.getElementById('elog-filter-type')   || {}).value || '';
  var filterStatus = (document.getElementById('elog-filter-status') || {}).value || '';
  var rows = '';
  var alt = false;
  Object.keys(_elogData).sort().forEach(function(email){
    var entries = _elogData[email];
    if(filterType)   entries = entries.filter(function(e){ return e.report_type===filterType; });
    if(filterStatus) entries = entries.filter(function(e){ return e.status.startsWith(filterStatus); });
    if(!entries.length) return;
    entries = entries.slice(-20).reverse();
    entries.forEach(function(e, i){
      var bg = alt ? 'rgba(255,255,255,.02)' : 'rgba(0,0,0,.1)';
      var sc = e.status==='OK'?'#68D391':'#FC8181';
      rows += '<tr style="background:' + bg + '">' +
        '<td style="padding:.4rem .7rem;font-size:.8rem;color:#90cdf4">' + (i===0?email:'') + '</td>' +
        '<td style="padding:.4rem .7rem;font-size:.8rem">' + (e.nome||'') + '</td>' +
        '<td style="padding:.4rem .7rem;font-size:.8rem;font-family:monospace">' + (e.report_type||'') + ' ' + (e.piano||'') + '</td>' +
        '<td style="padding:.4rem .7rem;font-size:.8rem;color:' + sc + ';font-weight:700">' + e.status + '</td>' +
        '<td style="padding:.4rem .7rem;font-size:.75rem;color:#64748b">' + (e.ts||'') + '</td>' +
        '</tr>';
      alt = !alt;
    });
  });
  var t = document.getElementById('elog-table');
  if(!t) return;
  t.innerHTML = rows ? '<table><thead><tr>' +
    '<th>Email</th><th>Nome</th><th>Report</th><th>Stato</th><th>Data/Ora</th>' +
    '</tr></thead><tbody>' + rows + '</tbody></table>' :
    '<p style="color:#64748b;font-size:.84rem">Nessun invio registrato con i filtri selezionati.</p>';
}

// ── TICKER FREQUENCY ───────────────────────────────────────────────────────
var _tfData = {};
function loadTickerFreq(){
  fetch('/api/ticker-frequency').then(function(r){return r.json();}).then(function(d){
    _tfData = d;
    tfRender();
  }).catch(function(){});
}
function tfRender(){
  var asset = (document.getElementById('tf-asset') || {}).value || 'AZIONI';
  var piano = (document.getElementById('tf-piano') || {}).value || 'BASIC';
  var minDays = parseInt((document.getElementById('tf-min') || {}).value || '1');
  var planData = ((_tfData[asset]||{})[piano])||{};
  var entries = Object.keys(planData).map(function(tk){
    return {ticker:tk, nome:planData[tk].nome||'', count:planData[tk].count||0, last:planData[tk].last_date||''};
  }).filter(function(e){ return e.count >= minDays; }).sort(function(a,b){ return b.count-a.count; });
  var rows = '';
  entries.forEach(function(e, i){
    var bg = i%2===0?'rgba(0,0,0,.1)':'rgba(255,255,255,.02)';
    var col = e.count>=5?'#68D391':(e.count>=3?'#F6AD55':'#94a3b8');
    var bar = Math.min(100, e.count*10);
    rows += '<tr style="background:' + bg + '">' +
      '<td style="padding:.45rem .8rem;font-size:.8rem;color:#64748b">' + (i+1) + '</td>' +
      '<td style="padding:.45rem .8rem;font-family:monospace;font-weight:700;font-size:.88rem;color:#90cdf4">' + e.ticker + '</td>' +
      '<td style="padding:.45rem .8rem;font-size:.8rem">' + (e.nome?e.nome.substring(0,35):'') + '</td>' +
      '<td style="padding:.45rem .8rem">' +
        '<div style="display:flex;align-items:center;gap:.5rem">' +
          '<div style="width:' + bar + 'px;height:8px;background:' + col + ';border-radius:4px;min-width:4px"></div>' +
          '<span style="color:' + col + ';font-weight:700;font-size:.85rem">' + e.count + 'gg</span>' +
        '</div>' +
      '</td>' +
      '<td style="padding:.45rem .8rem;font-size:.75rem;color:#64748b">' + (e.last?e.last.substring(0,4)+'/'+e.last.substring(4,6)+'/'+e.last.substring(6):'') + '</td>' +
      '</tr>';
  });
  var t = document.getElementById('tf-table');
  if(!t) return;
  t.innerHTML = rows ? '<table><thead><tr>' +
    '<th>#</th><th>Ticker</th><th>Nome</th><th>Stabilita (giorni)</th><th>Ultima Data</th>' +
    '</tr></thead><tbody>' + rows + '</tbody></table>' :
    '<p style="color:#64748b;font-size:.84rem">Nessun dato disponibile. Il file ticker_frequency.json verra generato dopo il prossimo run notturno.</p>';
}

// ═══════════════════════════════════════════════
// SOCIAL ENRICHMENT
// ═══════════════════════════════════════════════
var _seData = null;

function loadSocialEnrich(){
  document.getElementById('se-table').innerHTML = '<p style="color:#94a3b8;font-size:.84rem">Caricamento...</p>';
  fetch('/api/social-profiles').then(function(r){return r.json();}).then(function(d){
    _seData = d;
    seRender();
  }).catch(function(){ document.getElementById('se-table').innerHTML = '<p style="color:#FC8181">Errore caricamento.</p>'; });
}

function seRender(){
  if(!_seData) return;
  var prio   = (document.getElementById('se-filter-prio') || {}).value;
  var plat   = (document.getElementById('se-filter-platform') || {}).value;
  var search = ((document.getElementById('se-search') || {}).value || '').toLowerCase();

  var entries = Object.keys(_seData).map(function(email){
    var p = _seData[email];
    return {email:email, firstname:p.firstname||'', lastname:p.lastname||'',
            company:p.company||'', priority:p.priority!==undefined?p.priority:2,
            li:p.linkedin_url||'', li_c:p.linkedin_confidence||'',
            ig:p.instagram_url||'', ig_c:p.instagram_confidence||'',
            fb:p.facebook_url||'', fb_c:p.facebook_confidence||'',
            verified:p.manually_verified||false,
            enriched:p.enriched_at||''};
  });

  // Filtri
  if(prio !== '') entries = entries.filter(function(e){ return String(e.priority) === prio; });
  if(plat === 'li') entries = entries.filter(function(e){ return !!e.li; });
  else if(plat === 'ig') entries = entries.filter(function(e){ return !!e.ig; });
  else if(plat === 'fb') entries = entries.filter(function(e){ return !!e.fb; });
  else if(plat === 'none') entries = entries.filter(function(e){ return !e.li && !e.ig && !e.fb; });
  if(search) entries = entries.filter(function(e){
    return (e.firstname+' '+e.lastname+' '+e.email).toLowerCase().indexOf(search) >= 0;
  });

  // Sort: priority asc, then enriched desc
  entries.sort(function(a,b){
    if(a.priority !== b.priority) return a.priority - b.priority;
    return b.enriched.localeCompare(a.enriched);
  });

  // KPI
  var total    = Object.keys(_seData).length;
  var withLi   = Object.values(_seData).filter(function(p){ return p.linkedin_url; }).length;
  var withIg   = Object.values(_seData).filter(function(p){ return p.instagram_url; }).length;
  var withFb   = Object.values(_seData).filter(function(p){ return p.facebook_url; }).length;
  var verified = Object.values(_seData).filter(function(p){ return p.manually_verified; }).length;
  var kpis = [
    {label:'Arricchiti', val:total, color:'#90cdf4'},
    {label:'LinkedIn',   val:withLi + ' (' + (total?Math.round(withLi*100/total):0) + '%)', color:'#0a66c2'},
    {label:'Instagram',  val:withIg + ' (' + (total?Math.round(withIg*100/total):0) + '%)', color:'#e1306c'},
    {label:'Facebook',   val:withFb + ' (' + (total?Math.round(withFb*100/total):0) + '%)', color:'#1877f2'},
    {label:'Verificati', val:verified, color:'#68D391'},
  ];
  var kpiEl = document.getElementById('se-kpi');
  if(kpiEl) kpiEl.innerHTML = kpis.map(function(k){
    return '<div style="background:#1E293B;border:1px solid #2C5282;border-radius:8px;padding:.6rem 1rem;min-width:120px">' +
      '<div style="font-size:.75rem;color:#94a3b8">' + k.label + '</div>' +
      '<div style="font-size:1.2rem;font-weight:700;color:' + k.color + '">' + k.val + '</div></div>';
  }).join('');

  // Tabella
  var prioTag = ['<span style="color:#FC8181;font-weight:700">CLICKER</span>',
                 '<span style="color:#F6AD55;font-weight:700">READER</span>',
                 '<span style="color:#94a3b8">COLD</span>'];
  var confBadge = function(url, conf){
    if(!url) return '<span style="color:#374151">—</span>';
    var color = conf==='manual'?'#68D391':(conf==='high'?'#90cdf4':'#F6AD55');
    return '<a href="' + url + '" target="_blank" style="color:' + color + ';font-size:.78rem;text-decoration:none;word-break:break-all">' +
      url.replace(/https?:\/\/(www\.)?/,'').substring(0,35) + (url.length>45?'...':'') + '</a>';
  };
  var rows = '';
  entries.slice(0, 500).forEach(function(e, i){
    var bg = i%2===0?'rgba(0,0,0,.1)':'rgba(255,255,255,.02)';
    rows += '<tr style="background:' + bg + '">' +
      '<td style="padding:.45rem .7rem;font-size:.82rem">' + e.firstname + ' ' + e.lastname + '</td>' +
      '<td style="padding:.45rem .7rem;font-size:.75rem;color:#64748b">' + e.email + '</td>' +
      '<td style="padding:.45rem .7rem;font-size:.75rem;color:#94a3b8">' + (e.company||'—') + '</td>' +
      '<td style="padding:.45rem .7rem;font-size:.75rem">' + (prioTag[e.priority]||'—') + '</td>' +
      '<td style="padding:.45rem .7rem">' + confBadge(e.li, e.li_c) + '</td>' +
      '<td style="padding:.45rem .7rem">' + confBadge(e.ig, e.ig_c) + '</td>' +
      '<td style="padding:.45rem .7rem">' + confBadge(e.fb, e.fb_c) + '</td>' +
      '<td style="padding:.45rem .7rem;font-size:.72rem;color:#64748b">' + (e.enriched?e.enriched.substring(0,10):'—') + '</td>' +
      '<td style="padding:.45rem .7rem">' +
        '<button onclick="seOpenModal(\'' + e.email.replace(/'/g,"\\'") + '\')" ' +
        'style="background:#2C5282;color:#fff;border:none;padding:.25rem .6rem;border-radius:4px;cursor:pointer;font-size:.72rem">Edit</button>' +
      '</td>' +
      '</tr>';
  });

  var t = document.getElementById('se-table');
  if(!t) return;
  if(!entries.length){
    t.innerHTML = '<p style="color:#94a3b8;font-size:.84rem;padding:1rem">Nessun profilo trovato. Il job parte domenica alle 02:00 oppure avvia manualmente: <code>python social_enrichment.py --test 5</code></p>';
    return;
  }
  t.innerHTML = '<p style="font-size:.75rem;color:#64748b;margin-bottom:.4rem">Mostro ' +
    Math.min(500,entries.length) + ' / ' + entries.length + ' profili</p>' +
    '<table><thead><tr>' +
    '<th>Nome</th><th>Email</th><th>Azienda</th><th>Priorita</th>' +
    '<th>LinkedIn</th><th>Instagram</th><th>Facebook</th><th>Data</th><th></th>' +
    '</tr></thead><tbody>' + rows + '</tbody></table>';
}

function seOpenModal(email){
  var p = _seData[email] || {};
  document.getElementById('se-modal-email').value = email;
  document.getElementById('se-modal-li').value  = p.linkedin_url  || '';
  document.getElementById('se-modal-ig').value  = p.instagram_url || '';
  document.getElementById('se-modal-fb').value  = p.facebook_url  || '';
  document.getElementById('se-modal').style.display = 'flex';
}

function seSaveModal(){
  var email = document.getElementById('se-modal-email').value;
  var body  = {
    email:         email,
    linkedin_url:  document.getElementById('se-modal-li').value.trim(),
    instagram_url: document.getElementById('se-modal-ig').value.trim(),
    facebook_url:  document.getElementById('se-modal-fb').value.trim(),
  };
  fetch('/api/social-profiles/update', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)})
    .then(function(r){return r.json();})
    .then(function(d){
      if(d.ok){
        document.getElementById('se-modal').style.display = 'none';
        loadSocialEnrich();
      } else { alert('Errore: ' + (d.msg||'sconosciuto')); }
    }).catch(function(){ alert('Errore di rete'); });
}

function switchTab(el,id){
  document.querySelectorAll('.panel').forEach(function(p){p.classList.remove('active')});
  document.querySelectorAll('.tab').forEach(function(t){t.classList.remove('active')});
  document.getElementById(id).classList.add('active');
  el.classList.add('active');
  if(!_loaded[id]){
    _loaded[id]=true;
    if(id==='azioni'||id==='etf'||id==='fondi') loadTable(id);
    if(id==='servizi'||id==='parametri'){if(!_sv) loadServizi();}
    if(id==='parametri'){if(!_scrParams) loadScreenerParams(); if(!_scoring) loadScoring();}
    if(id==='crm'){if(!_clienti) loadClienti();}
    if(id==='database') loadDatabase();
    if(id==='kb') loadKbFiles();
    if(id==='settori') loadSettori(false);
    if(id==='emaillog') loadEmailLog();
    if(id==='tickerfreq') loadTickerFreq();
    if(id==='analytics') renderAnalytics();
    if(id==='fatture') loadFatture();
    if(id==='socialenrich') loadSocialEnrich();
  }
}

function renderAnalytics() {
  var el = document.getElementById('analytics-content');
  if(!el) return;
  el.innerHTML = '<div style="opacity:.5;padding:2rem;text-align:center">Caricamento...</div>';
  fetch('/api/analytics').then(function(r){return r.json();}).then(function(d){
    var fmt = function(n){ return Math.round(n).toLocaleString('it-IT'); };
    var eur = function(n){ return '€ ' + fmt(n); };
    var html = '<div class="kpi-row">'
      +'<div class="kpi"><div class="kpi-label">MRR</div><div class="kpi-val" style="color:#68D391">'+eur(d.mrr)+'</div><div class="kpi-sub">ricavi mensili ricorrenti</div></div>'
      +'<div class="kpi"><div class="kpi-label">ARR</div><div class="kpi-val" style="color:#68D391">'+eur(d.arr)+'</div><div class="kpi-sub">proiezione annuale</div></div>'
      +'<div class="kpi"><div class="kpi-label">ARPU</div><div class="kpi-val">'+eur(d.arpu)+'</div><div class="kpi-sub">ricavo medio/cliente/mese</div></div>'
      +'<div class="kpi"><div class="kpi-label">LTV</div><div class="kpi-val">'+eur(d.ltv)+'</div><div class="kpi-sub">'+(d.churn_rate===0?'stimato 24 mesi':'churn '+d.churn_rate+'%')+'</div></div>'
      +'</div>'
      +'<div class="kpi-row">'
      +'<div class="kpi"><div class="kpi-label">Clienti ATTIVI</div><div class="kpi-val" style="color:#68D391">'+d.n_attivi+'</div><div class="kpi-sub">abbonati paganti</div></div>'
      +'<div class="kpi"><div class="kpi-label">TESTER</div><div class="kpi-val" style="color:#F6AD55">'+d.n_tester+'</div><div class="kpi-sub">trial in corso</div></div>'
      +'<div class="kpi"><div class="kpi-label">Churn Rate</div><div class="kpi-val" style="color:'+(d.churn_rate===0?'#68D391':'#ef4444')+'">'+d.churn_rate+'%</div><div class="kpi-sub">'+(d.n_sospesi+d.n_scaduti)+' persi / '+(d.n_attivi+d.n_sospesi+d.n_scaduti)+' totali</div></div>'
      +'<div class="kpi"><div class="kpi-label">Ricavi Cumulativi</div><div class="kpi-val">'+eur(d.cumulative)+'</div><div class="kpi-sub">da inizio attività</div></div>'
      +'</div>';
    html += '<div class="box" style="margin-bottom:1rem">'
      +'<h3 style="color:#F6AD55;margin-bottom:1.2rem">Funnel Clienti</h3>'
      +'<div style="display:flex;flex-direction:column;gap:.6rem">';
    var steps = [
      {label:'Da Contattare', n:d.n_da_cont, color:'rgba(255,255,255,.2)'},
      {label:'Prospect LinkedIn', n:d.n_linkedin, color:'rgba(96,165,250,.6)'},
      {label:'TESTER (trial)', n:d.n_tester, color:'rgba(246,173,85,.6)'},
      {label:'ATTIVI (paganti)', n:d.n_attivi, color:'rgba(104,211,145,.8)'}
    ];
    var maxN = d.n_da_cont + d.n_linkedin || 1;
    steps.forEach(function(s){
      var pct = Math.max(4, Math.round(s.n / maxN * 100));
      html += '<div style="display:flex;align-items:center;gap:.75rem">'
        +'<div style="width:150px;font-size:.78rem;color:rgba(255,255,255,.6);text-align:right;flex-shrink:0">'+s.label+'</div>'
        +'<div style="flex:1;background:rgba(255,255,255,.05);border-radius:4px;height:26px">'
        +'<div style="width:'+pct+'%;background:'+s.color+';border-radius:4px;height:100%;display:flex;align-items:center;padding:0 .5rem;font-size:.78rem;font-weight:700">'+s.n.toLocaleString('it-IT')+'</div>'
        +'</div></div>';
    });
    html += '</div></div>';
    html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem">';
    html += '<div class="box"><h3 style="color:#F6AD55;margin-bottom:1rem">Dettaglio Abbonamenti</h3>';
    if(d.mrr_breakdown && d.mrr_breakdown.length > 0){
      html += '<table style="width:100%;border-collapse:collapse;font-size:.82rem">'
        +'<thead><tr style="border-bottom:1px solid rgba(255,255,255,.1);color:rgba(255,255,255,.4);font-size:.72rem;text-transform:uppercase">'
        +'<th style="text-align:left;padding:.4rem .5rem">Servizio</th><th style="text-align:left;padding:.4rem .5rem">Piano</th><th style="text-align:right;padding:.4rem .5rem">€/mese</th>'
        +'</tr></thead><tbody>';
      d.mrr_breakdown.forEach(function(r){
        html += '<tr style="border-bottom:1px solid rgba(255,255,255,.05)">'
          +'<td style="padding:.4rem .5rem;color:#e0e0e0">'+r.servizio+'</td>'
          +'<td style="padding:.4rem .5rem"><span style="background:rgba(246,173,85,.12);color:#F6AD55;border-radius:4px;padding:.1rem .4rem;font-size:.72rem">'+r.piano+'</span></td>'
          +'<td style="padding:.4rem .5rem;text-align:right;color:#68D391;font-weight:700">€ '+r.importo+'</td>'
          +'</tr>';
      });
      html += '<tr style="border-top:1px solid rgba(255,255,255,.15)">'
        +'<td colspan="2" style="padding:.5rem;font-weight:700;color:#F6AD55">TOTALE MRR</td>'
        +'<td style="padding:.5rem;text-align:right;font-weight:700;color:#68D391;font-size:1rem">'+eur(d.mrr)+'</td>'
        +'</tr></tbody></table>';
    } else {
      html += '<div style="opacity:.5;font-size:.85rem">Nessun abbonamento attivo — MRR € 0</div>';
    }
    html += '</div>';
    html += '<div class="box"><h3 style="color:#F6AD55;margin-bottom:.8rem">Scenari di Crescita</h3>'
      +'<div style="font-size:.74rem;color:rgba(255,255,255,.4);margin-bottom:.8rem">'+d.n_prospect.toLocaleString('it-IT')+' prospect × ARPU € '+Math.round(d.arpu||60)+'/mese</div>';
    d.scenari.forEach(function(s){
      var barW = Math.min(100, Math.round(s.conv / 5 * 100));
      html += '<div style="margin-bottom:.8rem">'
        +'<div style="display:flex;justify-content:space-between;margin-bottom:.2rem">'
        +'<span style="font-size:.8rem;color:'+s.color+'">'+s.label+' ('+s.conv+'%)</span>'
        +'<span style="font-size:.8rem;font-weight:700;color:'+s.color+'">'+eur(s.mrr)+'/mese</span>'
        +'</div>'
        +'<div style="background:rgba(255,255,255,.05);border-radius:4px;height:6px">'
        +'<div style="width:'+barW+'%;background:'+s.color+';border-radius:4px;height:100%"></div>'
        +'</div>'
        +'<div style="font-size:.7rem;color:rgba(255,255,255,.35);margin-top:.15rem">'+s.n+' abbonati · profitto netto ~'+eur(s.mrr-58)+'/mese</div>'
        +'</div>';
    });
    html += '<div style="border-top:1px solid rgba(255,255,255,.08);padding-top:.6rem;font-size:.74rem;color:rgba(255,255,255,.35)">Break-even: 1 abbonato (costi fissi ~€ 58/mese)</div>';
    html += '</div></div>';
    el.innerHTML = html;
  }).catch(function(e){
    el.innerHTML = '<div class="box"><p style="color:#ef4444">Errore analytics: '+e+'</p></div>';
  });
}

// ═══════════════════════════════════════════════
// SCORING WEIGHTS — Pesi Score Bontà
// ═══════════════════════════════════════════════
var _scoring  = null;
var _scDef    = null;   // defaults dal server
var _scAsset  = 'azioni';
var _scPlan   = 'BASIC';

var _scDirs = {
  'Dividend Yield': true, 'P/B': false, 'ROE': true, 'Var_1D_%': true,
  'EV/FCF': false, 'Net Debt/EBITDA': false,
  'Perf 3M %': true, 'Performance 1Y': true, 'TER': false, 'Sharpe Ratio': true
};
var _scLabels = {
  'Var_1D_%': 'Var 1D %', 'Performance 1Y': 'Perf 1Y %',
  'Perf 3M %': 'Perf 3M %', 'Sharpe Ratio': 'Sharpe', 'Net Debt/EBITDA': 'Net Debt/EBITDA'
};

function loadScoring(){
  fetch('/api/parametri/scoring').then(function(r){return r.json();}).then(function(d){
    _scoring = d.weights;
    _scDef   = d.defaults;
    renderScoringUI();
  }).catch(function(e){ document.getElementById('sc-metrics').textContent='Errore: '+e.message; });
}

function renderScoringUI(){
  if(!_scoring) return;
  var weights = ((_scoring[_scAsset]||{})[_scPlan]) || {};
  var html = '<table style="width:100%;border-collapse:collapse">';
  html += '<tr style="font-size:.72rem;opacity:.4;text-transform:uppercase">'
    + '<td style="padding:.2rem 0;width:160px">Metrica</td>'
    + '<td style="width:120px">Direzione</td>'
    + '<td style="width:80px;text-align:right">Peso %</td>'
    + '<td>Barra</td></tr>';
  Object.keys(weights).forEach(function(metric){
    var val = parseFloat(weights[metric]) || 0;
    var hib = _scDirs[metric];
    var dirLabel = hib ? '▲ alto' : '▼ basso';
    var dirColor = hib ? '#68D391' : '#F6AD55';
    var barColor = val > 0 ? dirColor : 'rgba(255,255,255,.08)';
    var metricId = 'sc_' + metric.replace(/[^a-zA-Z0-9]/g,'_');
    var label = _scLabels[metric] || metric;
    html += '<tr style="border-bottom:1px solid rgba(255,255,255,.05)">'
      + '<td style="padding:.45rem 0;font-size:.84rem">' + label + '</td>'
      + '<td style="font-size:.72rem;color:' + dirColor + '">' + dirLabel + ' = meglio</td>'
      + '<td style="text-align:right;padding-right:.6rem">'
      + '<input type="number" id="' + metricId + '" min="0" max="100" step="1" value="' + val + '" '
      + 'oninput="_scUpdate(\'' + metric + '\',this.value)" '
      + 'style="width:64px;text-align:right;background:#1a2e4a;border:1px solid rgba(255,255,255,.18);'
      + 'border-radius:4px;color:#e2e8f0;padding:.28rem .4rem;font-size:.88rem">'
      + '</td>'
      + '<td style="padding-left:.5rem">'
      + '<div style="position:relative;height:7px;background:rgba(255,255,255,.08);border-radius:4px;min-width:80px">'
      + '<div id="' + metricId + '_bar" style="position:absolute;left:0;top:0;height:100%;border-radius:4px;'
      + 'background:' + barColor + ';width:' + Math.min(val,100) + '%"></div>'
      + '</div></td></tr>';
  });
  html += '</table>';
  document.getElementById('sc-metrics').innerHTML = html;
  _scUpdateTotal();
}

function _scUpdate(metric, value){
  if(!_scoring[_scAsset]) _scoring[_scAsset] = {};
  if(!_scoring[_scAsset][_scPlan]) _scoring[_scAsset][_scPlan] = {};
  var v = parseFloat(value) || 0;
  _scoring[_scAsset][_scPlan][metric] = v;
  var hib = _scDirs[metric];
  var barColor = v > 0 ? (hib ? '#68D391' : '#F6AD55') : 'rgba(255,255,255,.08)';
  var barId = 'sc_' + metric.replace(/[^a-zA-Z0-9]/g,'_') + '_bar';
  var bar = document.getElementById(barId);
  if(bar){ bar.style.width = Math.min(v,100)+'%'; bar.style.background = barColor; }
  _scUpdateTotal();
}

function _scUpdateTotal(){
  var weights = ((_scoring[_scAsset]||{})[_scPlan]) || {};
  var total = Object.values(weights).reduce(function(a,b){ return a+(parseFloat(b)||0); }, 0);
  var ok = Math.abs(total-100) < 0.5;
  document.getElementById('sc-total').innerHTML =
    'Totale: <span style="color:'+(ok?'#68D391':'#FC8181')+';font-size:1rem">'+total.toFixed(0)+'%</span>'
    +(ok?' ✓':' &nbsp;← deve essere 100%');
}

function switchScAsset(btn, asset){
  document.querySelectorAll('.sc-asset-tab').forEach(function(b){b.classList.remove('active');});
  btn.classList.add('active');
  _scAsset = asset;
  renderScoringUI();
}

function switchScPlan(btn, plan){
  document.querySelectorAll('.sc-plan-tab').forEach(function(b){b.classList.remove('active');});
  btn.classList.add('active');
  _scPlan = plan;
  renderScoringUI();
}

function saveScoring(){
  var weights = ((_scoring[_scAsset]||{})[_scPlan]) || {};
  var total = Object.values(weights).reduce(function(a,b){ return a+(parseFloat(b)||0); }, 0);
  if(Math.abs(total-100) >= 1){
    showMsg('sc-msg','I pesi devono sommare a 100%',false); return;
  }
  fetch('/api/parametri/scoring',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({weights:_scoring})
  }).then(function(r){return r.json();}).then(function(d){
    showMsg('sc-msg', d.ok ? 'Pesi salvati ✓' : ('Errore: '+(d.msg||'')), d.ok);
  });
}

function resetScoringDefaults(){
  if(!_scDef) return;
  _scoring = JSON.parse(JSON.stringify(_scDef));
  renderScoringUI();
  showMsg('sc-msg','Default ripristinati (premi 💾 per salvare)',true);
}

// ═══════════════════════════════════════════════
// DATABASE — elenco completo ticker
// ═══════════════════════════════════════════════
var _dbData  = null;
var _dbCache = {};
var _dbAsset = 'azioni';   // asset corrente (senza prefisso 'db-')

// Colonne draggabili (esclusi # e Ticker che sono fissi)
var _dbColDefs = {
  azioni: ['Nome', 'Prezzo', 'Var %', 'Gruppo / Mercato'],
  etf:    ['Nome', 'Prezzo', 'Var %', 'Gruppo / Mercato'],
  fondi:  ['Nome', 'Prezzo', 'Var %', 'Famiglia / Gestore'],
};
var _dbCols = {};        // asset → ordine corrente colonne (array di stringhe)
var _dbSortState = {};   // asset → {col: null|idx, dir: -1|1}

function _dbGetCols(asset){
  if(!_dbCols[asset]){
    var def = (_dbColDefs[asset] || []).slice();
    try{
      var s = localStorage.getItem('dbcols_'+asset);
      if(s){
        var p = JSON.parse(s);
        if(p.length === def.length && p.every(function(c){ return def.indexOf(c) >= 0; })) def = p;
      }
    }catch(e){}
    _dbCols[asset] = def;
  }
  return _dbCols[asset];
}

function _fmtVar(v){
  if(v===null||v===undefined) return '<span style="opacity:.3">—</span>';
  var c = v>=0 ? '#68D391' : '#FC8181';
  var s = v>=0 ? '+' : '';
  return '<span style="color:'+c+';font-weight:600">'+s+v.toFixed(2)+'%</span>';
}

function _renderDbHead(asset){
  var thead = document.getElementById('db-head-'+asset);
  if(!thead) return;
  var cols = _dbGetCols(asset);
  if(!_dbSortState[asset]) _dbSortState[asset] = {col: null, dir: -1};
  var ss = _dbSortState[asset];
  var h = '<tr><th style="width:3rem;text-align:right;opacity:.4">#</th><th>Ticker</th>';
  cols.forEach(function(c, i){
    var st = '';
    if(c==='Prezzo') st=' style="width:6rem;text-align:right"';
    if(c==='Var %')  st=' style="width:5.5rem;text-align:right"';
    var cls = 'sortable';
    if(ss.col === i) cls += (ss.dir === -1 ? ' sorted-desc' : ' sorted-asc');
    h += '<th class="'+cls+'" draggable="true"'+st
      +' onclick="if(this._skipNextClick){this._skipNextClick=false;return;}_sortDbTable(\''+asset+'\','+i+')"'
      +' ondragstart="_dbColDragStart(\''+asset+'\','+i+',this)"'
      +' ondragend="_colDragEnd(this)"'
      +' ondragover="_colDragOver(event,this)"'
      +' ondragleave="_colDragLeave(this)"'
      +' ondrop="_dbColDrop(\''+asset+'\','+i+',event)"'
      +' title="Clicca per ordinare · Trascina per spostare la colonna">'+c+'</th>';
  });
  h += '</tr>';
  thead.innerHTML = h;
}

function loadDatabase(){
  fetch('/api/database').then(function(r){return r.json();}).then(function(d){
    _dbData  = d;
    _dbCache = d.cache || {};
    var tot = d.totali;
    var azioni_at = d.cache_azioni_at ? ' · dati '+d.cache_azioni_at.slice(0,10) : '';
    document.getElementById('db-totali').textContent =
      tot.azioni+' Azioni · '+tot.etf+' ETF · '+tot.fondi+' Fondi = '+(tot.azioni+tot.etf+tot.fondi)+' totali'+azioni_at;
    document.getElementById('dbtab-azioni').textContent = '📈 Azioni ('+tot.azioni+')';
    document.getElementById('dbtab-etf').textContent   = '📦 ETF ('+tot.etf+')';
    document.getElementById('dbtab-fondi').textContent = '🏦 Fondi ('+tot.fondi+')';
    renderDbBody('azioni', d.azioni);
    renderDbBody('etf',    d.etf);
    renderDbBody('fondi',  d.fondi);
    updateDbCount();
  }).catch(function(e){ document.getElementById('db-totali').textContent='Errore: '+e.message; });
}

// Restituisce true se il ticker è un ISIN puro (2 lettere + 10 alfanumerici)
// Gli ISIN non hanno una pagina Yahoo Finance e non sono fetchabili da yfinance
function _isIsin(ticker){
  return /^[A-Z]{2}[0-9A-Z]{10}$/.test(ticker);
}

function renderDbBody(asset, rows){
  _renderDbHead(asset);
  var tbody = document.getElementById('db-body-'+asset);
  var cache = _dbCache[asset] || {};
  var cols  = _dbGetCols(asset);
  var ss    = _dbSortState[asset] || {col: null, dir: -1};
  // Ordina se selezionata una colonna
  var sortedRows = rows.slice();
  if(ss.col !== null){
    var sortCol = cols[ss.col];
    sortedRows.sort(function(a, b){
      var ca = cache[a.ticker] || {};
      var cb = cache[b.ticker] || {};
      var va, vb;
      if(sortCol === 'Nome')       { va = ca.name || ''; vb = cb.name || ''; }
      else if(sortCol === 'Prezzo'){ va = ca.price;      vb = cb.price; }
      else if(sortCol === 'Var %') { va = ca.change_pct; vb = cb.change_pct; }
      else                         { va = a.gruppo;      vb = b.gruppo; }
      var aNull = (va === null || va === undefined || va === '');
      var bNull = (vb === null || vb === undefined || vb === '');
      if(aNull && bNull) return 0;
      if(aNull) return 1;
      if(bNull) return -1;
      if(typeof va === 'number' && typeof vb === 'number') return (va - vb) * ss.dir;
      return String(va).localeCompare(String(vb), 'it', {numeric: true}) * ss.dir;
    });
  }
  var html  = '';
  sortedRows.forEach(function(r, i){
    var isIsin = _isIsin(r.ticker);
    var tid = 'db-'+asset+'-'+r.ticker.replace(/\./g,'_');
    var cd  = cache[r.ticker] || {};
    // Costruisce mappa colonna → cella HTML
    var cells = {};
    if(isIsin){
      // ISIN puro: non fetchabile da yfinance, niente dati live
      cells['Nome']   = '<span style="font-size:.82rem;color:#718096;font-style:italic">ISIN — nessun ticker YF</span>';
      cells['Prezzo'] = '<span id="'+tid+'-price" style="font-size:.82rem;opacity:.3">—</span>';
      cells['Var %']  = '<span id="'+tid+'-var" style="opacity:.3">—</span>';
    } else {
      cells['Nome'] = cd.name
        ? '<span style="font-size:.82rem;color:#90cdf4">'+cd.name+'</span>'
        : '<span id="'+tid+'-nome" style="font-size:.82rem;color:#90cdf4">—</span>';
      cells['Prezzo'] = (cd.price !== null && cd.price !== undefined)
        ? '<span id="'+tid+'-price" style="font-size:.82rem;font-variant-numeric:tabular-nums">'+cd.price+(cd.currency?' '+cd.currency:'')+'</span>'
        : '<span id="'+tid+'-price" style="font-size:.82rem;opacity:.3">—</span>';
      cells['Var %'] = (cd.change_pct !== null && cd.change_pct !== undefined)
        ? '<span id="'+tid+'-var">'+_fmtVar(cd.change_pct)+'</span>'
        : '<span id="'+tid+'-var" style="opacity:.3">—</span>';
    }
    // Colonna gruppo (il nome varia tra azioni/etf e fondi)
    cols.forEach(function(c){
      if(!(c in cells)) cells[c] = '<span class="db-group">'+r.gruppo+'</span>';
    });
    if(isIsin){
      // Riga ISIN: non cliccabile per caricare dati, link JustETF
      var jtUrl = 'https://www.justetf.com/en/etf-profile.html?isin='+encodeURIComponent(r.ticker);
      html += '<tr data-ticker="'+r.ticker.toLowerCase()+'" data-gruppo="'+r.gruppo.toLowerCase()+'" style="opacity:.6" title="ISIN senza ticker Yahoo Finance — dati non disponibili">';
      html += '<td style="text-align:right;opacity:.35;font-size:.75rem;padding-right:.6rem">'+(i+1)+'</td>';
      html += '<td onclick="event.stopPropagation()" style="white-space:nowrap">'
            + '<a href="'+jtUrl+'" target="_blank" class="btn-yf" style="font-family:monospace;font-size:.82rem;background:#68D391;color:#1a202c" title="Apri su JustETF">'+r.ticker+'</a>'
            + ' <button onclick="event.stopPropagation();_removeTicker(\''+asset+'\',\''+r.ticker+'\')" '
            + 'style="background:rgba(239,68,68,.18);border:1px solid rgba(239,68,68,.35);color:#fca5a5;font-size:.75rem;cursor:pointer;border-radius:3px;padding:.05rem .3rem;line-height:1" '
            + 'title="Elimina ticker dalle liste">✕</button></td>';
    } else {
      // Riga normale: link Yahoo Finance, click per caricare dati
      var yf = 'https://finance.yahoo.com/quote/'+encodeURIComponent(r.ticker);
      html += '<tr data-ticker="'+r.ticker.toLowerCase()+'" data-gruppo="'+r.gruppo.toLowerCase()+'" style="cursor:pointer" onclick="_loadRowPrice(\''+asset+'\',\''+r.ticker+'\')" title="Clicca per caricare Nome/Prezzo/Var%">';
      html += '<td style="text-align:right;opacity:.35;font-size:.75rem;padding-right:.6rem">'+(i+1)+'</td>';
      html += '<td onclick="event.stopPropagation()" style="white-space:nowrap">'
            + '<a href="'+yf+'" target="_blank" class="btn-yf" style="font-family:monospace;font-size:.82rem" title="Apri su Yahoo Finance">'+r.ticker+'</a>'
            + ' <button onclick="event.stopPropagation();_removeTicker(\''+asset+'\',\''+r.ticker+'\')" '
            + 'style="background:rgba(239,68,68,.18);border:1px solid rgba(239,68,68,.35);color:#fca5a5;font-size:.75rem;cursor:pointer;border-radius:3px;padding:.05rem .3rem;line-height:1" '
            + 'title="Elimina ticker dalle liste">✕</button></td>';
    }
    cols.forEach(function(c){
      var st = (c==='Prezzo'||c==='Var %') ? ' style="text-align:right"' : '';
      html += '<td'+st+'>'+cells[c]+'</td>';
    });
    html += '</tr>';
  });
  tbody.innerHTML = html;
  _updateMissingCount();
}

// ─── Carica dati su clic riga ─────────────────────────────────
var _rowLoadingSet = new Set();

function _loadRowPrice(asset, ticker){
  var tid = 'db-'+asset+'-'+ticker.replace(/\./g,'_');
  var ne = document.getElementById(tid+'-nome');
  var pe = document.getElementById(tid+'-price');
  var ve = document.getElementById(tid+'-var');
  // già caricato o in corso
  if(!ne && !pe) return;
  if(_rowLoadingSet.has(ticker)) return;
  // dati già presenti (nome != '—')
  if(ne && ne.textContent && ne.textContent !== '—') return;
  _rowLoadingSet.add(ticker);
  // evidenzia riga in caricamento
  var tid = 'db-'+asset+'-'+ticker.replace(/\./g,'_');
  var row = ne ? ne.closest('tr') : null;
  if(row) row.style.background = 'rgba(99,179,237,.12)';
  if(ne) ne.innerHTML = '<span style="color:#90cdf4;opacity:.7;font-style:italic">caricamento…</span>';
  fetch('/api/database/lookup?t='+encodeURIComponent(ticker)).then(function(r){return r.json();}).then(function(data){
    var d = data[ticker.toUpperCase()] || {};
    if(ne) ne.textContent = d.name || '—';
    if(pe){
      if(d.price && d.price !== '—'){
        pe.textContent = d.price+(d.currency ? ' '+d.currency : '');
        pe.style.color = '#68D391';
        pe.style.opacity = '1';
      } else { pe.textContent = '—'; }
    }
    if(ve) ve.innerHTML = _fmtVar(d.change_pct !== undefined ? d.change_pct : null);
    if(!_dbCache[asset]) _dbCache[asset] = {};
    _dbCache[asset][ticker.toUpperCase()] = d;
    if(row){ row.style.background = 'rgba(72,187,120,.08)'; setTimeout(function(){ row.style.background=''; }, 1200); }
  }).catch(function(){
    if(ne) ne.textContent = '—';
    if(row) row.style.background = '';
  }).finally(function(){
    _rowLoadingSet.delete(ticker);
  });
}

// ─── Elimina ticker dal Database ──────────────────────────────
function _removeTicker(asset, ticker){
  if(!confirm('Eliminare ' + ticker + ' dalle liste permanentemente?')) return;
  fetch('/api/database/remove', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ticker: ticker})
  }).then(function(r){ return r.json(); }).then(function(d){
    if(d.ok){
      // Rimuovi la riga dalla tabella
      var tbody = document.getElementById('db-body-'+asset);
      if(tbody){
        var rows = tbody.querySelectorAll('tr');
        rows.forEach(function(row){
          if(row.dataset.ticker === ticker.toLowerCase()) row.remove();
        });
      }
      // Aggiorna contatore
      if(_dbData && _dbData[asset]){
        _dbData[asset] = _dbData[asset].filter(function(r){ return r.ticker !== ticker; });
        var tot = _dbData.totali;
        tot[asset] = (_dbData[asset]||[]).length;
        document.getElementById('db-totali').textContent =
          tot.azioni+' Azioni · '+tot.etf+' ETF · '+tot.fondi+' Fondi = '+(tot.azioni+tot.etf+tot.fondi)+' totali';
        document.getElementById('dbtab-azioni').textContent = '📈 Azioni ('+tot.azioni+')';
        document.getElementById('dbtab-etf').textContent   = '📦 ETF ('+tot.etf+')';
        document.getElementById('dbtab-fondi').textContent = '🏦 Fondi ('+tot.fondi+')';
      }
      filterDb();
    } else {
      alert('Errore: ' + d.msg);
    }
  }).catch(function(e){ alert('Errore di rete: '+e.message); });
}

// ─── Drag & drop colonne DATABASE ─────────────────────────────
var _dbDragIdx   = null;
var _dbDragAsset = null;

function _dbColDragStart(asset, idx, el){
  _dbDragIdx   = idx;
  _dbDragAsset = asset;
  el.style.opacity = '.45';
  el._skipNextClick = true;
}

function _dbColDrop(asset, targetIdx, event){
  event.preventDefault();
  document.querySelectorAll('#db-head-'+asset+' th').forEach(function(th){ th.classList.remove('col-drag-over'); });
  if(_dbDragAsset !== asset || _dbDragIdx === null || _dbDragIdx === targetIdx){ _dbDragIdx=null; return; }
  var cols  = _dbGetCols(asset);
  var moved = cols.splice(_dbDragIdx, 1)[0];
  cols.splice(targetIdx, 0, moved);
  _dbDragIdx = null;
  if(_dbData) renderDbBody(asset, _dbData[asset]);
  try{ localStorage.setItem('dbcols_'+asset, JSON.stringify(cols)); }catch(e){}
}

function _resetDbCols(asset){
  try{ localStorage.removeItem('dbcols_'+asset); }catch(e){}
  delete _dbCols[asset];
  if(_dbData) renderDbBody(asset, _dbData[asset]);
}

function _sortDbTable(asset, colIdx){
  if(!_dbSortState[asset]) _dbSortState[asset] = {col: null, dir: -1};
  var ss = _dbSortState[asset];
  if(ss.col === colIdx){
    ss.dir = -ss.dir;
  } else {
    ss.col = colIdx;
    ss.dir = -1;
  }
  if(_dbData) renderDbBody(asset, _dbData[asset]);
}

function switchDbTab(el, panelId){
  document.querySelectorAll('.db-tab').forEach(function(t){t.classList.remove('active');});
  document.querySelectorAll('.db-panel').forEach(function(p){p.classList.remove('active');});
  el.classList.add('active');
  document.getElementById(panelId).classList.add('active');
  _dbAsset = panelId.replace('db-','');
  document.getElementById('db-search').value = '';
  updateDbCount();
  filterDb();
  _updateMissingCount();
}

function filterDb(){
  var q = (document.getElementById('db-search').value||'').toLowerCase().trim();
  var tbody = document.getElementById('db-body-'+_dbAsset);
  if(!tbody) return;
  var rows = tbody.querySelectorAll('tr');
  var vis = 0;
  rows.forEach(function(row){
    var ok = !q || row.dataset.ticker.indexOf(q)>=0 || row.dataset.gruppo.indexOf(q)>=0;
    row.style.display = ok ? '' : 'none';
    if(ok) vis++;
  });
  var tot = rows.length;
  document.getElementById('db-count').textContent =
    q ? vis+' di '+tot+' risultati per "'+q+'"' : tot+' ticker';
  var btn = document.getElementById('db-load-btn');
  if(btn) btn.textContent = '📊 Carica dati ('+vis+' visibili)';
}

function updateDbCount(){
  if(!_dbData) return;
  var asset = _dbAsset || 'azioni';
  var rows  = document.getElementById('db-body-'+asset);
  var vis   = rows ? rows.querySelectorAll('tr:not([style*="display: none"])').length : 0;
  var len   = (_dbData[asset]||[]).length;
  document.getElementById('db-count').textContent = len+' ticker';
  var btn = document.getElementById('db-load-btn');
  if(btn) btn.textContent = '📊 Carica dati ('+len+' visibili)';
}

function loadDbPrices(){
  var asset = _dbAsset || 'azioni';
  var tbody = document.getElementById('db-body-'+asset);
  if(!tbody) return;
  var visibleRows = [];
  tbody.querySelectorAll('tr').forEach(function(row){
    if(row.style.display !== 'none' && row.dataset.ticker){
      visibleRows.push(row);
    }
  });
  // Escludi righe ISIN puro (nessun dato Yahoo Finance disponibile)
  visibleRows = visibleRows.filter(function(row){ return !_isIsin(row.dataset.ticker.toUpperCase()); });
  if(!visibleRows.length){ alert('Nessun ticker visibile'); return; }
  if(visibleRows.length > 30){ visibleRows = visibleRows.slice(0,30); }
  var visible = visibleRows.map(function(r){ return r.dataset.ticker.toUpperCase(); });
  // evidenzia righe in caricamento
  visibleRows.forEach(function(row){
    row.style.background = 'rgba(99,179,237,.12)';
    var tid = 'db-'+asset+'-'+row.dataset.ticker.replace(/\./g,'_');
    var ne = document.getElementById(tid+'-nome');
    if(ne) ne.innerHTML = '<span style="color:#90cdf4;opacity:.7;font-style:italic">caricamento…</span>';
  });
  var btn = document.getElementById('db-load-btn');
  if(btn){ btn.textContent = '⏳ Caricamento...'; btn.disabled = true; }
  fetch('/api/database/lookup?t='+encodeURIComponent(visible.join(','))).then(function(r){return r.json();}).then(function(data){
    visibleRows.forEach(function(row){
      var t   = row.dataset.ticker.toUpperCase();
      var d   = data[t] || {};
      var tid = 'db-'+asset+'-'+t.replace(/\./g,'_');
      var ne  = document.getElementById(tid+'-nome');
      var pe  = document.getElementById(tid+'-price');
      var ve  = document.getElementById(tid+'-var');
      if(ne) ne.textContent = d.name || '—';
      if(pe){
        if(d.price && d.price !== '—'){
          pe.textContent = d.price+(d.currency ? ' '+d.currency : '');
          pe.style.color = '#68D391';
          pe.style.opacity = '1';
        } else { pe.textContent = '—'; }
      }
      if(ve) ve.innerHTML = _fmtVar(d.change_pct !== undefined ? d.change_pct : null);
      row.style.background = 'rgba(72,187,120,.08)';
      setTimeout(function(){ row.style.background = ''; }, 1200);
    });
    if(btn){ btn.textContent = '✅ Dati caricati'; btn.disabled = false; }
  }).catch(function(e){
    visibleRows.forEach(function(row){ row.style.background = ''; });
    if(btn){ btn.textContent = '❌ Errore — riprova'; btn.disabled = false; }
    console.error(e);
  });
}

// ─── Conta e aggiorna badge dati mancanti ─────────────────────
function _updateMissingCount(){
  var asset = (_dbAsset || 'db-azioni').replace('db-','');
  var tbody = document.getElementById('db-body-'+asset);
  if(!tbody){ document.getElementById('db-missing-count').textContent = '0'; return; }
  var cache = _dbCache[asset] || {};
  var missing = 0;
  tbody.querySelectorAll('tr[data-ticker]').forEach(function(row){
    var t = row.dataset.ticker.toUpperCase();
    if(_isIsin(t)) return;
    var cd = cache[t];
    if(!cd || cd.price === null || cd.price === undefined) missing++;
  });
  document.getElementById('db-missing-count').textContent = missing;
}

// ─── Carica tutti i ticker con dati mancanti (batch 30) ────────
function loadMissingDbPrices(){
  var asset = (_dbAsset || 'db-azioni').replace('db-','');
  var tbody = document.getElementById('db-body-'+asset);
  if(!tbody) return;
  var cache = _dbCache[asset] || {};
  var toLoad = [];
  tbody.querySelectorAll('tr[data-ticker]').forEach(function(row){
    var t = row.dataset.ticker.toUpperCase();
    if(_isIsin(t)) return;
    var cd = cache[t];
    if(!cd || cd.price === null || cd.price === undefined) toLoad.push(t);
  });
  if(!toLoad.length){ alert('Nessun dato mancante nel tab corrente.'); return; }
  var btn = document.getElementById('db-missing-btn');
  btn.disabled = true;
  var total = toLoad.length;
  var done  = 0;
  var BATCH = 30;
  function _nextBatch(){
    if(!toLoad.length){
      btn.disabled = false;
      btn.innerHTML = '✅ Completato — <span id="db-missing-count">0</span>';
      _updateMissingCount();
      return;
    }
    var batch = toLoad.splice(0, BATCH);
    btn.innerHTML = '⏳ ' + done + '/' + total + ' — <span id="db-missing-count">...</span>';
    // evidenzia righe in caricamento
    batch.forEach(function(t){
      var tid = 'db-'+asset+'-'+t.replace(/\./g,'_');
      var ne = document.getElementById(tid+'-nome');
      if(ne) ne.innerHTML = '<span style="color:#90cdf4;opacity:.6;font-style:italic">…</span>';
    });
    fetch('/api/database/lookup?t='+encodeURIComponent(batch.join(','))).then(function(r){return r.json();}).then(function(data){
      if(!_dbCache[asset]) _dbCache[asset] = {};
      batch.forEach(function(t){
        var d   = data[t] || {};
        var tid = 'db-'+asset+'-'+t.replace(/\./g,'_');
        _dbCache[asset][t] = d;
        var ne = document.getElementById(tid+'-nome');
        var pe = document.getElementById(tid+'-price');
        var ve = document.getElementById(tid+'-var');
        if(ne) ne.textContent = d.name || '—';
        if(pe){
          pe.textContent = (d.price && d.price !== '—') ? d.price+(d.currency?' '+d.currency:'') : '—';
          if(d.price && d.price !== '—'){ pe.style.color='#68D391'; pe.style.opacity='1'; }
        }
        if(ve) ve.innerHTML = _fmtVar(d.change_pct !== undefined ? d.change_pct : null);
      });
      done += batch.length;
      _nextBatch();
    }).catch(function(){
      btn.disabled = false;
      btn.innerHTML = '❌ Errore — <span id="db-missing-count">'+toLoad.length+'</span>';
    });
  }
  _nextBatch();
}

// ─── Verifica ticker morti ────────────────────────────────────
function verifyDeadTickers(){
  var asset = (_dbAsset || 'db-azioni').replace('db-','');
  var tbody = document.getElementById('db-body-'+asset);
  if(!tbody){ alert('Carica prima il database.'); return; }
  var cache = _dbCache[asset] || {};

  // Raccoglie solo ticker senza prezzo (non ISIN)
  var toCheck = [];
  tbody.querySelectorAll('tr[data-ticker]').forEach(function(row){
    var t = row.dataset.ticker.toUpperCase();
    if(_isIsin(t)) return;
    var cd = cache[t];
    if(!cd || !cd.price || cd.price === '—') toCheck.push(t);
  });

  if(!toCheck.length){ alert('Nessun ticker vuoto nel tab corrente. Prima clicca "Aggiorna mancanti".'); return; }

  var btn = document.getElementById('db-dead-btn');
  btn.disabled = true;
  btn.textContent = '⏳ Verifica in corso ('+toCheck.length+' ticker)...';

  // Invia in un batch unico (max 100 lato server)
  fetch('/api/database/verify-dead', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({tickers: toCheck})
  }).then(function(r){ return r.json(); }).then(function(data){
    btn.disabled = false;
    btn.textContent = '☠️ Verifica ticker morti';
    _showDeadModal(asset, data.dead || [], data.uncertain || []);
  }).catch(function(e){
    btn.disabled = false;
    btn.textContent = '☠️ Verifica ticker morti';
    alert('Errore verifica: '+e);
  });
}

function _showDeadModal(asset, dead, uncertain){
  // Rimuovi modale precedente se esiste
  var old = document.getElementById('dead-modal');
  if(old) old.remove();

  var deadHtml = '';
  if(dead.length){
    deadHtml += '<div style="margin-bottom:.5rem;font-size:.82rem;color:#fca5a5;font-weight:600">☠️ Probabilmente morti ('+dead.length+') — nessuna risposta da Yahoo Finance</div>';
    deadHtml += '<div style="max-height:220px;overflow-y:auto;margin-bottom:1rem">';
    dead.forEach(function(t){
      deadHtml += '<label style="display:flex;align-items:center;gap:.5rem;padding:.25rem 0;cursor:pointer">'
        + '<input type="checkbox" class="dead-chk" value="'+t+'" checked style="accent-color:#FC8181">'
        + '<span style="font-family:monospace;font-size:.85rem;color:#fca5a5">'+t+'</span></label>';
    });
    deadHtml += '</div>';
  }

  var uncHtml = '';
  if(uncertain.length){
    uncHtml += '<div style="margin-bottom:.5rem;font-size:.82rem;color:#F6AD55;font-weight:600">⚠️ Incerti ('+uncertain.length+') — dati assenti ma ticker potrebbe esistere</div>';
    uncHtml += '<div style="max-height:140px;overflow-y:auto;margin-bottom:1rem">';
    uncertain.forEach(function(t){
      uncHtml += '<label style="display:flex;align-items:center;gap:.5rem;padding:.2rem 0;cursor:pointer">'
        + '<input type="checkbox" class="dead-chk" value="'+t+'" style="accent-color:#F6AD55">'
        + '<span style="font-family:monospace;font-size:.82rem;color:#aaa">'+t+'</span></label>';
    });
    uncHtml += '</div>';
  }

  if(!dead.length && !uncertain.length){
    alert('Nessun ticker morto trovato.'); return;
  }

  var modal = document.createElement('div');
  modal.id = 'dead-modal';
  modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:9000;display:flex;align-items:center;justify-content:center';
  modal.innerHTML = '<div style="background:#111827;border:1px solid rgba(239,68,68,.4);border-radius:14px;padding:1.8rem 2rem;width:100%;max-width:520px;max-height:85vh;overflow-y:auto">'
    + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.2rem">'
    + '<h3 style="color:#fca5a5;margin:0">☠️ Risultati verifica ticker</h3>'
    + '<button onclick="document.getElementById(\'dead-modal\').remove()" style="background:none;border:none;color:#666;font-size:1.3rem;cursor:pointer">✕</button></div>'
    + deadHtml + uncHtml
    + '<div style="display:flex;gap:.7rem;justify-content:flex-end;margin-top:.5rem">'
    + '<button onclick="document.getElementById(\'dead-modal\').remove()" style="padding:.5rem 1.2rem;background:transparent;border:1px solid rgba(255,255,255,.15);border-radius:7px;color:#aaa;cursor:pointer">Annulla</button>'
    + '<button onclick="_bulkRemoveDead(\''+asset+'\')" style="padding:.5rem 1.4rem;background:rgba(239,68,68,.25);border:1px solid rgba(239,68,68,.5);border-radius:7px;color:#fca5a5;font-weight:600;cursor:pointer">🗑️ Elimina selezionati</button>'
    + '</div></div>';
  document.body.appendChild(modal);
}

function _bulkRemoveDead(asset){
  var checked = Array.from(document.querySelectorAll('.dead-chk:checked')).map(function(c){ return c.value; });
  if(!checked.length){ alert('Nessun ticker selezionato.'); return; }
  if(!confirm('Eliminare '+checked.length+' ticker dalle liste? Operazione irreversibile.')) return;

  fetch('/api/database/remove-bulk', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({tickers: checked})
  }).then(function(r){ return r.json(); }).then(function(data){
    document.getElementById('dead-modal').remove();
    alert('✓ Eliminati '+data.removed+'/'+checked.length+' ticker. Ricarica il database per aggiornare la vista.');
    loadDatabase();
  }).catch(function(e){ alert('Errore eliminazione: '+e); });
}

// ═══════════════════════════════════════════════
// HOME — STATUS + KPI
// ═══════════════════════════════════════════════
function loadStatus(){
  fetch('/api/status').then(function(r){return r.json()}).then(function(d){
    var run=d._running||{};
    delete d._running;
    var html='';
    var pc={'BASIC':'#4A90D9','PRO':'#F6AD55','VALUE':'#68D391'};
    var assetOrder=['azioni','etf','fondi'];
    assetOrder.forEach(function(tipo){
      var info=d[tipo];
      var rs=run[tipo];
      var badge=rs?'<span class="rs rs-'+rs+'" style="font-size:.68rem">'+rs+'</span>':'';
      var pianiHtml='';
      if(info&&info.piani&&Object.keys(info.piani).length){
        ['BASIC','PRO','VALUE'].forEach(function(p){
          var pi=info.piani[p];
          if(pi){
            pianiHtml+='<span style="display:inline-flex;align-items:center;gap:.25rem;'
              +'background:'+pc[p]+'22;color:'+pc[p]+';border:1px solid '+pc[p]+'44;'
              +'border-radius:4px;padding:.1rem .45rem;font-size:.72rem;font-weight:700;margin-right:.3rem">'
              +p+' <span style="color:#ccc;font-weight:400">'+pi.count+'</span></span>';
          }
        });
      } else if(info&&info.count!==undefined){
        pianiHtml='<span style="color:#ccc;font-size:.85rem">'+info.count+' risultati</span>';
      }
      html+='<div class="kpi">'
           +'<div class="kpi-label">'+ICONS[tipo]+' '+tipo.toUpperCase()+' '+badge+'</div>'
           +'<div style="margin:.35rem 0 .2rem">'+( pianiHtml||'<span style="color:#555;font-size:.8rem">—</span>')+'</div>'
           +'<div class="kpi-sub">'+(info?info.time:'Nessun report')+'</div>'
           +'</div>';
      var btn=document.getElementById('run-'+tipo);
      if(btn){btn.disabled=rs==='running';if(rs!=='running')btn.textContent='▶ '+tipo.charAt(0).toUpperCase()+tipo.slice(1);}
    });
    // Revenue KPI
    var rev=0;
    if(_sv){
      ASSETS.forEach(function(a){TIERS.forEach(function(t){rev+=(_sv[a]&&_sv[a][t]?(_sv[a][t].prezzo||0):0);});});
    }
    html+='<div class="kpi"><div class="kpi-label">💰 Revenue Potenziale</div>'
         +'<div class="kpi-val" style="font-size:1.5rem">€'+rev+'</div>'
         +'<div class="kpi-sub">12 piani × 3 tier / mese</div></div>';
    document.getElementById('kpi-row').innerHTML=html;
  }).catch(function(){});
}

// ═══════════════════════════════════════════════
// RELOAD KB
// ═══════════════════════════════════════════════
function loadKBStatus(){
  fetch('/api/kb-status').then(function(r){return r.json();}).then(function(d){
    var el=document.getElementById('kb-status');
    if(el) el.innerHTML='<strong style="color:#68D391">✓ Attiva</strong>'
      +' &nbsp;·&nbsp; '+d.chars+' caratteri'
      +' &nbsp;·&nbsp; '+d.files+' file'
      +' &nbsp;·&nbsp; caricata alle '+d.loaded_at;
  }).catch(function(){});
}

function reloadKB(){
  var btn=document.getElementById('btn-reload-kb');
  var el=document.getElementById('kb-status');
  btn.disabled=true; btn.textContent='↺ Ricarico...';
  fetch('/api/reload-kb').then(function(r){return r.json();}).then(function(d){
    btn.disabled=false; btn.textContent='↺ Ricarica KB';
    if(d.ok){
      el.innerHTML='<strong style="color:#68D391">✓ Ricaricata</strong>'
        +' &nbsp;·&nbsp; '+d.chars+' caratteri'
        +' &nbsp;·&nbsp; '+d.files+' file'
        +' &nbsp;·&nbsp; aggiornata alle '+d.loaded_at;
    } else {
      el.innerHTML='<span style="color:#FC8181">Errore: '+d.error+'</span>';
    }
  }).catch(function(e){
    btn.disabled=false; btn.textContent='↺ Ricarica KB';
    if(el) el.innerHTML='<span style="color:#FC8181">Errore di rete</span>';
  });
}

// ═══════════════════════════════════════════════
// KB TAB
// ═══════════════════════════════════════════════
function loadKbFiles(){
  var grid = document.getElementById('kb-files-grid');
  var status = document.getElementById('kb-status-panel');
  fetch('/api/kb-files').then(function(r){return r.json();}).then(function(d){
    if(d.error){ grid.innerHTML='<div style="opacity:.5;grid-column:1/-1;text-align:center;padding:1.5rem">'+d.error+'</div>'; return; }
    var files = d.files || [];
    if(!files.length){ grid.innerHTML='<div style="opacity:.5;grid-column:1/-1;text-align:center;padding:1.5rem">Nessun file trovato</div>'; return; }
    var html='';
    files.forEach(function(f){
      var kb = f.name === 'kb_reports.md' ? '#E9D8FD' : '#C6F6D5';
      html += '<div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:8px;padding:.9rem 1rem">'
        +'<div style="font-weight:600;font-size:.9rem;margin-bottom:.3rem">'+f.name+'</div>'
        +'<div style="font-size:.78rem;opacity:.7">'+_fmtBytes(f.size)
        +' &nbsp;·&nbsp; <span title="'+f.modified+'">'+f.modified_rel+'</span></div>'
        +'</div>';
    });
    grid.innerHTML = html;
    if(status) status.innerHTML = '<strong style="color:#68D391">✓ '+files.length+' file</strong> &nbsp;·&nbsp; totale '+_fmtBytes(d.total_size);
  }).catch(function(){
    if(grid) grid.innerHTML='<div style="opacity:.5;grid-column:1/-1;text-align:center;padding:1.5rem">Errore caricamento file</div>';
  });
}

function _fmtBytes(b){
  if(b<1024) return b+' B';
  if(b<1048576) return (b/1024).toFixed(1)+' KB';
  return (b/1048576).toFixed(1)+' MB';
}

function reloadKB2(){
  var btn=document.getElementById('btn-reload-kb2');
  var status=document.getElementById('kb-status-panel');
  btn.disabled=true; btn.textContent='↺ Ricarico...';
  fetch('/api/reload-kb').then(function(r){return r.json();}).then(function(d){
    btn.disabled=false; btn.textContent='↺ Ricarica KB';
    if(d.ok){
      if(status) status.innerHTML='<strong style="color:#68D391">✓ Ricaricata</strong>'
        +' &nbsp;·&nbsp; '+d.chars+' caratteri &nbsp;·&nbsp; alle '+d.loaded_at;
      loadKbFiles();
    } else {
      if(status) status.innerHTML='<span style="color:#FC8181">Errore: '+d.error+'</span>';
    }
  }).catch(function(){
    btn.disabled=false; btn.textContent='↺ Ricarica KB';
    if(status) status.innerHTML='<span style="color:#FC8181">Errore di rete</span>';
  });
}

// ═══════════════════════════════════════════════
// ONBOARDING TAB
// ═══════════════════════════════════════════════
function switchObTab(el, panelId){
  document.querySelectorAll('#onboarding .db-tab').forEach(function(t){ t.classList.remove('active'); });
  document.querySelectorAll('#onboarding .db-panel').forEach(function(p){ p.style.display='none'; });
  el.classList.add('active');
  var panel = document.getElementById(panelId);
  if(panel) panel.style.display='block';
}

// ═══════════════════════════════════════════════
// MERCATI
// ═══════════════════════════════════════════════
function loadMercati(){
  fetch('/api/mercati').then(function(r){return r.json()}).then(function(d){
    var wrap=document.getElementById('mercati-wrap');
    if(!d.rows||!d.rows.length){
      wrap.innerHTML='<table><tbody><tr><td style="padding:1.5rem;opacity:.5;text-align:center">Nessun dato — esegui prima lo screener Azioni</td></tr></tbody></table>';
      return;
    }
    var cols=Object.keys(d.rows[0]);
    var head='<tr>'+cols.map(function(c){return '<th>'+c+'</th>'}).join('')+'</tr>';
    var totT=0,totS=0;
    var body=d.rows.map(function(row){
      totT+=parseInt(row['Ticker Totali'])||0;
      totS+=parseInt(row['Selezionate'])||0;
      return '<tr>'+cols.map(function(c){
        var v=row[c]!==null&&row[c]!==undefined?row[c]:'—';
        var st='';
        if(c==='Mercato') st=' style="font-weight:600;color:#F6AD55"';
        if(c==='Selezionate'&&v>0) st=' style="color:#22c55e;font-weight:700"';
        return '<td'+st+'>'+v+'</td>';
      }).join('')+'</tr>';
    }).join('');
    var foot='<tr style="border-top:2px solid rgba(246,173,85,.2);font-weight:700"><td style="color:#F6AD55">TOTALE</td><td>'+totT+'</td>'
             +cols.slice(2).map(function(c){return c==='Selezionate'?'<td style="color:#22c55e">'+totS+'</td>':'<td>—</td>';}).join('')+'</tr>';
    wrap.innerHTML='<table><thead>'+head+'</thead><tbody>'+body+foot+'</tbody></table>';
  }).catch(function(){});
}

// ═══════════════════════════════════════════════
// TABLE DATA — con sorting per colonna
// ═══════════════════════════════════════════════
function loadTable(tipo){
  var body=document.getElementById(tipo+'-body');
  var info=document.getElementById(tipo+'-info');
  body.innerHTML='<tr><td style="padding:2rem;opacity:.5;text-align:center">Caricamento...</td></tr>';
  fetch('/api/data/'+tipo).then(function(r){return r.json()}).then(function(d){
    var n=d.rows?d.rows.length:0;
    info.innerHTML='<div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap">'
      +'<span><strong>'+(d.file||'—')+'</strong> &nbsp;·&nbsp; '+(d.time||'—')+' &nbsp;·&nbsp; <strong style="color:#22c55e">'+n+'</strong> risultati</span>'
      +'<button onclick="_resetCols(\''+tipo+'\')" style="margin-left:auto;padding:.25rem .7rem;font-size:.75rem;background:transparent;border:1px solid rgba(255,255,255,.2);border-radius:5px;color:#aaa;cursor:pointer" title="Ripristina ordine colonne originale">↺ Reset colonne</button>'
      +'</div>';
    if(!n){body.innerHTML='<tr><td style="padding:2rem;opacity:.5;text-align:center">Nessun dato disponibile</td></tr>';return;}
    _tableData[tipo]=d.rows;
    var defaultCols=Object.keys(d.rows[0]);
    // Ripristina ordine salvato (se compatibile con i dati attuali)
    var savedCols=null;
    try{
      var raw=localStorage.getItem('cols_'+tipo);
      if(raw){
        var parsed=JSON.parse(raw);
        if(parsed.length===defaultCols.length&&parsed.every(function(c){return defaultCols.indexOf(c)>=0;}))
          savedCols=parsed;
      }
    }catch(e){}
    _tableCols[tipo]=savedCols||defaultCols;
    _sortState[tipo]={col:null,dir:-1};
    _renderTable(tipo);
  }).catch(function(e){body.innerHTML='<tr><td style="color:#ef4444">Errore: '+e.message+'</td></tr>';});
}

function _renderTable(tipo){
  var head=document.getElementById(tipo+'-head');
  var body=document.getElementById(tipo+'-body');
  var cols=_tableCols[tipo];
  var ss=_sortState[tipo];
  var rows=_tableData[tipo].slice();

  // Ordina se è selezionata una colonna
  if(ss.col!==null){
    var cName=cols[ss.col];
    rows.sort(function(a,b){
      var va=a[cName], vb=b[cName];
      var aNull=(va===null||va===undefined||va==='—'||va==='');
      var bNull=(vb===null||vb===undefined||vb==='—'||vb==='');
      if(aNull&&bNull) return 0;
      if(aNull) return 1;
      if(bNull) return -1;
      if(typeof va==='number'&&typeof vb==='number') return (va-vb)*ss.dir;
      return String(va).localeCompare(String(vb),'it',{numeric:true})*ss.dir;
    });
  }

  // Header con indicatori di sort + drag-and-drop per riordinare colonne
  head.innerHTML='<tr>'+cols.map(function(c,i){
    var cls='sortable';
    if(ss.col===i) cls+=(ss.dir===-1?' sorted-desc':' sorted-asc');
    return '<th class="'+cls+'" draggable="true"'
      +' onclick="if(this._skipNextClick){this._skipNextClick=false;return;}_sortTable(\''+tipo+'\','+i+')"'
      +' ondragstart="_colDragStart(\''+tipo+'\','+i+',this)"'
      +' ondragend="_colDragEnd(this)"'
      +' ondragover="_colDragOver(event,this)"'
      +' ondragleave="_colDragLeave(this)"'
      +' ondrop="_colDrop(\''+tipo+'\','+i+',event)"'
      +' title="Clicca per ordinare · Trascina per spostare la colonna">'+c+'</th>';
  }).join('')+'</tr>';

  // Righe
  body.innerHTML=rows.map(function(row){
    return '<tr>'+cols.map(function(c){
      var v=row[c];
      if(v===null||v===undefined) return '<td>—</td>';
      var cls='';
      if(c==='Ticker'){
        return '<td><a class="ticker" href="https://finance.yahoo.com/quote/'+encodeURIComponent(v)+'" target="_blank" rel="noopener" title="Apri su Yahoo Finance">'+v+'</a></td>';
      }
      if(typeof v==='number'&&v<0) cls=' class="neg"';
      if(typeof v==='number'&&!Number.isInteger(v)) v=v.toFixed(2);
      return '<td'+cls+'>'+v+'</td>';
    }).join('')+'</tr>';
  }).join('');
}

function _sortTable(tipo,colIdx){
  var ss=_sortState[tipo];
  if(ss.col===colIdx){
    ss.dir=-ss.dir;
  } else {
    ss.col=colIdx;
    ss.dir=-1;
  }
  _renderTable(tipo);
}

// ─── Drag & drop colonne ──────────────────────────────────────
var _dragColIdx  = null;
var _dragColTipo = null;

function _colDragStart(tipo, idx, el){
  _dragColIdx  = idx;
  _dragColTipo = tipo;
  el.style.opacity = '.45';
  // click-then-drag non trigga sort: stoppiamo click successivo
  el._skipNextClick = true;
}

function _colDragEnd(el){
  el.style.opacity = '';
  _dragColIdx  = null;
  _dragColTipo = null;
}

function _colDragOver(event, el){
  event.preventDefault();
  el.classList.add('col-drag-over');
}

function _colDragLeave(el){
  el.classList.remove('col-drag-over');
}

function _colDrop(tipo, targetIdx, event){
  event.preventDefault();
  // Rimuovi indicatore visivo su tutti gli header
  document.querySelectorAll('#'+tipo+'-head th').forEach(function(th){
    th.classList.remove('col-drag-over');
  });
  if(_dragColTipo !== tipo || _dragColIdx === null || _dragColIdx === targetIdx){
    _dragColIdx = null; return;
  }
  var cols  = _tableCols[tipo];
  var moved = cols.splice(_dragColIdx, 1)[0];
  cols.splice(targetIdx, 0, moved);
  // Aggiusta indice di sort dopo lo spostamento
  var ss = _sortState[tipo];
  if(ss.col !== null){
    if(ss.col === _dragColIdx){
      ss.col = targetIdx;
    } else if(_dragColIdx < targetIdx && ss.col > _dragColIdx && ss.col <= targetIdx){
      ss.col--;
    } else if(_dragColIdx > targetIdx && ss.col >= targetIdx && ss.col < _dragColIdx){
      ss.col++;
    }
  }
  _dragColIdx = null;
  _renderTable(tipo);
  // Persiste in localStorage
  try{ localStorage.setItem('cols_'+tipo, JSON.stringify(_tableCols[tipo])); }catch(e){}
}

function _resetCols(tipo){
  try{ localStorage.removeItem('cols_'+tipo); }catch(e){}
  if(!_tableData[tipo]||!_tableData[tipo].length) return;
  _tableCols[tipo] = Object.keys(_tableData[tipo][0]);
  _sortState[tipo] = {col:null, dir:-1};
  _renderTable(tipo);
}

// ═══════════════════════════════════════════════
// SERVIZI — LOAD & RENDER
// ═══════════════════════════════════════════════
function loadServizi(){
  fetch('/api/servizi').then(function(r){return r.json()}).then(function(d){
    _sv=d;
    renderServizi();
    renderParametri();
    loadStatus();
  }).catch(function(e){console.error('loadServizi:',e);});
}

function renderServizi(){
  if(!_sv) return;
  ASSETS.forEach(function(asset){
    TIERS.forEach(function(tier){
      var cfg=(_sv[asset]&&_sv[asset][tier])||{};
      var params=cfg.parametri||{};
      var el=document.getElementById('sv-'+asset+'-'+tier);
      if(!el) return;
      var pRows=Object.entries(params).map(function(kv){
        var k=kv[0],v=kv[1];
        return '<div class="param-row">'
          +'<span class="param-lbl">'+(PLABELS[k]||k)+'</span>'
          +'<input class="param-inp" type="number" step="'+(PSTEP[k]||0.1)+'"'
          +' data-asset="'+asset+'" data-tier="'+tier+'" data-param="'+k+'" value="'+v+'">'
          +'</div>';
      }).join('');
      var selOpts=['attivo','beta','inattivo'].map(function(s){
        return '<option value="'+s+'"'+(cfg.status===s?' selected':'')+'>'+{attivo:'✅ Attivo',beta:'🟡 Beta',inattivo:'⛔ Inattivo'}[s]+'</option>';
      }).join('');
      var caratteristiche=(cfg.caratteristiche||[]).join('\n');
      var target=cfg.target||'';
      el.innerHTML='<div class="sv-card t-'+tier+'">'
        +'<div class="price-row">'
          +'<span class="price-eur">€</span>'
          +'<input class="price-inp" type="number" min="0" step="1"'
          +' data-asset="'+asset+'" data-tier="'+tier+'" data-field="prezzo" value="'+(cfg.prezzo||0)+'">'
          +'<span class="price-mo">/mese</span>'
        +'</div>'
        +'<div class="status-row">'
          +'<span class="bdg bdg-'+tier+'">'+tier.toUpperCase()+'</span>'
          +'<select class="status-sel" data-asset="'+asset+'" data-tier="'+tier+'" data-field="status">'+selOpts+'</select>'
        +'</div>'
        +'<div class="param-rows">'+pRows+'</div>'
        +'<div class="sv-extra">'
          +'<label class="sv-lbl">Caratteristiche <small>(una per riga)</small></label>'
          +'<textarea class="sv-textarea" rows="5" data-asset="'+asset+'" data-tier="'+tier+'" data-field="caratteristiche"></textarea>'
          +'<label class="sv-lbl" style="margin-top:.5rem">Profilo target</label>'
          +'<textarea class="sv-textarea" style="min-height:12rem;height:12rem" data-asset="'+asset+'" data-tier="'+tier+'" data-field="target"></textarea>'
        +'</div>'
      +'</div>';
      // imposta .value dopo innerHTML per gestire correttamente newline e caratteri speciali
      el.querySelector('[data-field="caratteristiche"]').value = caratteristiche;
      el.querySelector('[data-field="target"]').value = target;
    });
  });
}

function saveServizi(){
  var data=JSON.parse(JSON.stringify(_sv));
  // prices & status
  document.querySelectorAll('[data-field="prezzo"]').forEach(function(inp){
    var a=inp.dataset.asset,t=inp.dataset.tier;
    if(data[a]&&data[a][t]) data[a][t].prezzo=parseFloat(inp.value)||0;
  });
  document.querySelectorAll('[data-field="status"]').forEach(function(sel){
    var a=sel.dataset.asset,t=sel.dataset.tier;
    if(data[a]&&data[a][t]) data[a][t].status=sel.value;
  });
  // parametri inside cards
  document.querySelectorAll('.sv-card .param-inp').forEach(function(inp){
    var a=inp.dataset.asset,t=inp.dataset.tier,p=inp.dataset.param;
    if(data[a]&&data[a][t]&&data[a][t].parametri) data[a][t].parametri[p]=parseFloat(inp.value);
  });
  // caratteristiche & target
  document.querySelectorAll('.sv-textarea[data-field="caratteristiche"]').forEach(function(ta){
    var a=ta.dataset.asset,t=ta.dataset.tier;
    if(data[a]&&data[a][t]) data[a][t].caratteristiche=ta.value.split('\n').map(function(s){return s.trim();}).filter(Boolean);
  });
  document.querySelectorAll('.sv-textarea[data-field="target"]').forEach(function(ta){
    var a=ta.dataset.asset,t=ta.dataset.tier;
    if(data[a]&&data[a][t]) data[a][t].target=ta.value.trim();
  });
  fetch('/api/servizi',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})
    .then(function(r){return r.json()}).then(function(res){
      if(res.ok){_sv=data; renderParametri(); showMsg('sv-msg','✅ Servizi salvati','ok');}
      else showMsg('sv-msg','❌ '+res.msg,'err');
      loadStatus();
    }).catch(function(e){showMsg('sv-msg','❌ '+e.message,'err');});
}

// ═══════════════════════════════════════════════
// PARAMETRI — RENDER COMPARISON TABLE
// ═══════════════════════════════════════════════
function renderParametri(){
  if(!_sv) return;
  var html='';
  ASSETS.forEach(function(asset){
    var allKeys=[];
    TIERS.forEach(function(tier){
      var params=(_sv[asset]&&_sv[asset][tier]&&_sv[asset][tier].parametri)||{};
      Object.keys(params).forEach(function(k){if(allKeys.indexOf(k)===-1) allKeys.push(k);});
    });
    html+='<div class="pm-section box">'
      +'<h3>'+ICONS[asset]+' '+asset.toUpperCase()+'</h3>'
      +'<div class="tbl-wrap"><table class="pm-table">'
      +'<thead><tr>'
        +'<th style="width:200px">Parametro</th>'
        +'<th class="th-basic">BASIC</th>'
        +'<th class="th-pro">PRO</th>'
        +'<th class="th-value">VALUE</th>'
      +'</tr></thead><tbody>';
    allKeys.forEach(function(key){
      html+='<tr><td>'+(PLABELS[key]||key)+'</td>';
      TIERS.forEach(function(tier){
        var val=(_sv[asset]&&_sv[asset][tier]&&_sv[asset][tier].parametri&&_sv[asset][tier].parametri[key]!==undefined)?_sv[asset][tier].parametri[key]:'';
        html+='<td class="tc"><input class="pm-inp '+tier+'" type="number" step="'+(PSTEP[key]||0.1)+'"'
             +' data-asset="'+asset+'" data-tier="'+tier+'" data-param="'+key+'" value="'+val+'"></td>';
      });
      html+='</tr>';
    });
    html+='</tbody></table></div></div>';
  });
  document.getElementById('pm-container').innerHTML=html;
}

function saveParametri(){
  if(!_sv) return;
  var data=JSON.parse(JSON.stringify(_sv));
  document.querySelectorAll('#pm-container .pm-inp').forEach(function(inp){
    var a=inp.dataset.asset,t=inp.dataset.tier,p=inp.dataset.param;
    if(data[a]&&data[a][t]&&data[a][t].parametri) data[a][t].parametri[p]=parseFloat(inp.value);
  });
  fetch('/api/servizi',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})
    .then(function(r){return r.json()}).then(function(res){
      if(res.ok){_sv=data; renderServizi(); showMsg('pm-msg','✅ Parametri salvati','ok');}
      else showMsg('pm-msg','❌ '+res.msg,'err');
    }).catch(function(e){showMsg('pm-msg','❌ '+e.message,'err');});
}

// ═══════════════════════════════════════════════
// SCREENER RUN + LOG
// ═══════════════════════════════════════════════
function runScreener(tipo){
  var btn=document.getElementById('run-'+tipo);
  if(btn) btn.disabled=true;
  document.getElementById('run-msg').textContent='';
  fetch('/api/run/'+tipo,{method:'POST'}).then(function(r){return r.json()}).then(function(d){
    if(d.ok){
      var logNome=tipo==='orchestrator'?'orchestrator':tipo;
      startLog(logNome);
      document.getElementById('run-msg').innerHTML='⏳ '+tipo.toUpperCase()+' avviato';
    } else {
      document.getElementById('run-msg').innerHTML='❌ '+d.msg;
      if(btn) btn.disabled=false;
    }
    setTimeout(loadStatus,2000);
  }).catch(function(e){document.getElementById('run-msg').innerHTML='❌ '+e.message;if(btn)btn.disabled=false;});
}

function startLog(nome){
  var box=document.getElementById('log-box');
  var term=document.getElementById('log-term');
  var badge=document.getElementById('log-badge');
  document.getElementById('log-title').textContent='📟 Log — '+nome.toUpperCase();
  box.style.display='block';
  term.textContent='In attesa output...';
  badge.className='rs rs-running'; badge.textContent='running';
  box.scrollIntoView({behavior:'smooth',block:'nearest'});
  if(_logInt) clearInterval(_logInt);
  _logInt=setInterval(function(){pollLog(nome);},2000);
}

function pollLog(nome){
  fetch('/api/log/'+nome).then(function(r){return r.json()}).then(function(d){
    var term=document.getElementById('log-term');
    var badge=document.getElementById('log-badge');
    if(d.log&&d.log.length){term.textContent=d.log.join('\n');term.scrollTop=term.scrollHeight;}
    badge.textContent=d.status; badge.className='rs rs-'+d.status;
    if(d.status!=='running'){
      clearInterval(_logInt); _logInt=null;
      document.getElementById('log-info').textContent='Completato: '+new Date().toLocaleTimeString('it-IT');
      loadStatus();
      ['azioni','etf','fondi','tutti','orchestrator'].forEach(function(k){
        var b=document.getElementById('run-'+k);
        if(b){b.disabled=false;b.textContent=k==='tutti'?'▶▶ Tutti':k==='orchestrator'?'🚀 Orchestrator + Email':'▶ '+k.charAt(0).toUpperCase()+k.slice(1);}
      });
    }
  }).catch(function(){});
}

// ═══════════════════════════════════════════════
// UTILS
// ═══════════════════════════════════════════════
function showMsg(id,text,type){
  var el=document.getElementById(id);
  if(!el) return;
  el.textContent=text;
  el.className='msg'+(type?' msg-'+type:'');
  setTimeout(function(){el.className='msg';el.textContent='';},4000);
}

function refreshAll(){
  loadStatus();
  loadMercati();
  if(_sv) loadServizi();
  var active=document.querySelector('.panel.active');
  if(active&&(active.id==='azioni'||active.id==='etf'||active.id==='fondi')) loadTable(active.id);
}

// ═══════════════════════════════════════════════
// SETTORI — Analisi Settoriale & Mercati
// ═══════════════════════════════════════════════
// ── Dati statici settori GICS ───────────────────────────────
var SETT_INFO = {
  'Technology': {
    desc: 'Software, hardware, semiconduttori, cloud e IT enterprise. Il settore più capitalizzato dell\'S&P 500 (~30% peso).',
    include: 'Apple (AAPL), Microsoft (MSFT), NVIDIA (NVDA), Broadcom (AVGO), Oracle (ORCL)',
    ciclo: 'Ciclico-growth. Beneficia da: tassi bassi, innovazione, spesa IT aziendale. Rischio: tassi alti, antitrust, valutazioni elevate.',
    etf_us: [['XLK','SPDR Technology (TER 0.10%)'],['VGT','Vanguard IT (TER 0.10%)'],['SOXX','iShares Semiconduttori (TER 0.35%)'],['QQQM','Invesco Nasdaq 100 (TER 0.15%)']],
    etf_eu: [['EXV3.DE','iShares STOXX EU Tech (TER 0.46%)'],['IUIT.L','iShares EU IT UCITS (TER 0.46%)'],['TECH.L','Global X Tech UCITS (TER 0.50%)']],
    fondi:  ['T. Rowe Price Science & Tech (PRSCX)','Fidelity Select Technology (FSPTX)'],
  },
  'Financial Services': {
    desc: 'Banche, assicurazioni, gestori patrimoniali, fintech, mercati dei capitali. Correlato al ciclo tassi.',
    include: 'JPMorgan (JPM), Visa (V), Mastercard (MA), Goldman Sachs (GS), Bank of America (BAC)',
    ciclo: 'Ciclico. Beneficia da: tassi alti (margine interesse), espansione economica. Rischio: recessione, credit crunch, regolamentazione.',
    etf_us: [['XLF','SPDR Financials (TER 0.10%)'],['VFH','Vanguard Financials (TER 0.10%)'],['KBE','SPDR S&P Bank ETF (TER 0.35%)']],
    etf_eu: [['EXH2.DE','iShares STOXX EU Banks (TER 0.46%)'],['EXH5.DE','iShares STOXX EU Insurance (TER 0.46%)']],
    fondi:  ['Fidelity Select Financial (FIDSX)','Davis Financial Fund (RPFGX)'],
  },
  'Health Care': {
    desc: 'Farmaceutiche, biotech, dispositivi medici, assicurazioni sanitarie. Settore difensivo con componente growth.',
    include: 'UnitedHealth (UNH), Eli Lilly (LLY), Johnson & Johnson (JNJ), AbbVie (ABBV), Merck (MRK)',
    ciclo: 'Difensivo-growth. Resiliente in recessione. Beneficia da: invecchiamento demografico, biotech. Rischio: riforme sanitarie, brevetti in scadenza.',
    etf_us: [['XLV','SPDR Health Care (TER 0.10%)'],['VHT','Vanguard Health Care (TER 0.10%)'],['IBB','iShares Biotech (TER 0.44%)'],['IHI','iShares Medical Devices (TER 0.40%)']],
    etf_eu: [['EXH3.DE','iShares STOXX EU Health Care (TER 0.46%)']],
    fondi:  ['Fidelity Select Medical (FSMEX)','T. Rowe Price Health Sciences (PRHSX)'],
  },
  'Industrials': {
    desc: 'Aerospazio, difesa, macchinari, trasporti, costruzioni, logistica. Barometro del ciclo economico.',
    include: 'GE (GE), Caterpillar (CAT), Honeywell (HON), RTX Corp (RTX), Union Pacific (UNP)',
    ciclo: 'Fortemente ciclico. Beneficia da: espansione economica, spesa infrastrutturale, difesa. Rischio: recessione, rallentamento manifatturiero.',
    etf_us: [['XLI','SPDR Industrials (TER 0.10%)'],['VIS','Vanguard Industrials (TER 0.10%)'],['ITA','iShares Aerospace & Defense (TER 0.40%)'],['PAVE','Global X Infrastructure (TER 0.47%)']],
    etf_eu: [['EXH4.DE','iShares STOXX EU Industrial G&S (TER 0.46%)']],
    fondi:  ['Fidelity Select Industrials (FCYIX)','T. Rowe Price Industrials (TRIIX)'],
  },
  'Consumer Discret.': {
    desc: 'Retail, auto, ristorazione, intrattenimento, beni di lusso. Dipende dal reddito disponibile dei consumatori.',
    include: 'Amazon (AMZN), Tesla (TSLA), Home Depot (HD), McDonald\'s (MCD), Nike (NKE)',
    ciclo: 'Ciclico. Beneficia da: crescita salariale, ottimismo consumi. Rischio: inflazione, recessione, tassi alti che comprimono spesa.',
    etf_us: [['XLY','SPDR Consumer Discret. (TER 0.10%)'],['VCR','Vanguard Consumer Discret. (TER 0.10%)'],['RTH','VanEck Retail ETF (TER 0.35%)']],
    etf_eu: [['EXH1.DE','iShares STOXX EU Auto & Parts (TER 0.46%)'],['EXV6.DE','iShares STOXX EU Travel & Leisure (TER 0.46%)']],
    fondi:  ['Fidelity Select Retailing (FSRPX)','Fidelity Select Consumer Discret. (FSCPX)'],
  },
  'Consumer Staples': {
    desc: 'Alimentari, bevande, prodotti per la casa, tabacco. Beni essenziali con domanda anelastica e alti dividendi.',
    include: 'Procter & Gamble (PG), Coca-Cola (KO), Walmart (WMT), Costco (COST), PepsiCo (PEP)',
    ciclo: 'Difensivo. Resiliente in recessione. Beneficia da: inflazione traslata sui prezzi, dividendi stabili. Sottoperforma nei boom ciclici.',
    etf_us: [['XLP','SPDR Consumer Staples (TER 0.10%)'],['VDC','Vanguard Consumer Staples (TER 0.10%)'],['KXI','iShares Global Consumer Staples (TER 0.42%)']],
    etf_eu: [['EXV8.DE','iShares STOXX EU Food & Beverage (TER 0.46%)']],
    fondi:  ['Fidelity Select Consumer Staples (FDFAX)','Vanguard Consumer Staples Fund (VCSAX)'],
  },
  'Energy': {
    desc: 'Petrolio, gas naturale, raffinerie, energie rinnovabili, servizi petroliferi. Correlato al prezzo delle commodity.',
    include: 'ExxonMobil (XOM), Chevron (CVX), ConocoPhillips (COP), EOG Resources (EOG), SLB (SLB)',
    ciclo: 'Ciclico commodity-driven. Beneficia da: prezzo petrolio alto, geopolitica, ripresa economia. Rischio: transizione energetica, oversupply, recessione.',
    etf_us: [['XLE','SPDR Energy (TER 0.10%)'],['VDE','Vanguard Energy (TER 0.10%)'],['XOP','SPDR Oil & Gas Exploration (TER 0.35%)'],['OIH','VanEck Oil Services (TER 0.35%)']],
    etf_eu: [['EXV1.DE','iShares STOXX EU Oil & Gas (TER 0.46%)']],
    fondi:  ['Fidelity Select Energy (FSENX)','Vanguard Energy Fund (VGELX)'],
  },
  'Utilities': {
    desc: 'Elettricità, gas, acqua, servizi ambientali. Monopoli regolamentati con cash flow stabili e alti dividendi.',
    include: 'NextEra Energy (NEE), Duke Energy (DUK), Southern Co (SO), Dominion (D), Exelon (EXC)',
    ciclo: 'Difensivo-bond proxy. Beneficia da: tassi bassi, AI (fabbisogno elettrico data center), rinnovabili. Rischio: tassi alti (concorrenza con bond).',
    etf_us: [['XLU','SPDR Utilities (TER 0.10%)'],['VPU','Vanguard Utilities (TER 0.10%)'],['FUTY','Fidelity MSCI Utilities (TER 0.08%)']],
    etf_eu: [['EXV7.DE','iShares STOXX EU Utilities (TER 0.46%)']],
    fondi:  ['Fidelity Select Utilities (FSUTX)','Vanguard Utilities Fund (VUIAX)'],
  },
  'Materials': {
    desc: 'Metalli, minerali, chimica industriale, carta, packaging, fertilizzanti. Legato al ciclo industriale.',
    include: 'Linde (LIN), Freeport-McMoRan (FCX), Air Products (APD), Sherwin-Williams (SHW), Nucor (NUE)',
    ciclo: 'Fortemente ciclico. Beneficia da: espansione industriale, inflazione commodity, dollaro debole. Rischio: recessione, dollaro forte, oversupply.',
    etf_us: [['XLB','SPDR Materials (TER 0.10%)'],['VAW','Vanguard Materials (TER 0.10%)'],['GDX','VanEck Gold Miners (TER 0.51%)'],['PICK','iShares Global Metals & Mining (TER 0.39%)']],
    etf_eu: [],
    fondi:  ['Fidelity Select Materials (FSDPX)','Vanguard Materials Fund (VMIAX)'],
  },
  'Real Estate': {
    desc: 'REIT (Real Estate Investment Trust): uffici, residenziale, data center, logistica, retail, healthcare. Alta cedola da dividendi.',
    include: 'Prologis (PLD), American Tower (AMT), Equinix (EQIX), Simon Property (SPG), Extra Space (EXR)',
    ciclo: 'Bond proxy. Beneficia da: tassi bassi, e-commerce, AI (data center REIT). Rischio: tassi alti (aumento costo debito), vacancy uffici post-Covid.',
    etf_us: [['XLRE','SPDR Real Estate (TER 0.10%)'],['VNQ','Vanguard Real Estate (TER 0.12%)'],['REET','iShares Global REIT (TER 0.14%)']],
    etf_eu: [],
    fondi:  ['Fidelity Real Estate (FRESX)','Vanguard Real Estate Fund (VGSIX)'],
  },
  'Comm. Services': {
    desc: 'Social media, streaming, telecom, media, videogiochi. Mix tra crescita (Meta, Alphabet) e valore difensivo (Verizon, AT&T).',
    include: 'Alphabet (GOOGL), Meta (META), Netflix (NFLX), Comcast (CMCSA), T-Mobile (TMUS)',
    ciclo: 'Misto growth/difensivo. Telecom difensivi; media/streaming ciclici. Beneficia da: pubblicità digitale, AI, streaming. Rischio: regolamentazione.',
    etf_us: [['XLC','SPDR Comm. Services (TER 0.10%)'],['VOX','Vanguard Comm. Services (TER 0.10%)'],['FCOM','Fidelity MSCI Comm. (TER 0.08%)']],
    etf_eu: [['EXH6.DE','iShares STOXX EU Media (TER 0.46%)']],
    fondi:  ['Fidelity Select Telecommunications (FSTCX)'],
  },
};
var EU_TO_US = {
  'Technology':'Technology','Banks':'Financial Services','Health Care':'Health Care',
  'Industrials':'Industrials','Auto & Parts':'Consumer Discret.','Food & Beverage':'Consumer Staples',
  'Oil & Gas':'Energy','Utilities':'Utilities','Insurance':'Financial Services',
  'Media':'Comm. Services','Travel & Leisure':'Consumer Discret.',
};

// ── Dati statici ETF per nazioni ─────────────────────────────
var NAZIONI_ETF = {
  'USA':       { desc:'Il mercato azionario più grande al mondo (~45% market cap globale). Altissima liquidità e trasparenza.', etf_us:[['SPY','SPDR S&P 500 (TER 0.09%)'],['SPLG','SPDR Portfolio S&P 500 (TER 0.02%)'],['VTI','Vanguard Total Market (TER 0.03%)']], etf_eu:[['CSPX.L','iShares S&P 500 UCITS (TER 0.07%)'],['VUAA.AS','Vanguard S&P 500 UCITS (TER 0.07%)']] },
  'USA Tech':  { desc:'Esposizione concentrata al Nasdaq 100 — le 100 maggiori aziende non-finanziarie quotate sul Nasdaq.', etf_us:[['QQQ','Invesco Nasdaq 100 (TER 0.20%)'],['QQQM','Invesco Nasdaq 100 Mini (TER 0.15%)']], etf_eu:[['EQQQ.L','Invesco EQQQ Nasdaq (TER 0.30%)'],['CNDX.AS','iShares Nasdaq 100 UCITS (TER 0.33%)']] },
  'Canada':    { desc:'TSX dominato da energia, materiali e banche. Fortemente correlato alle commodity. Valuta CAD.', etf_us:[['EWC','iShares MSCI Canada (TER 0.50%)']], etf_eu:[] },
  'Brasile':   { desc:'Mercato emergente con focus su commodity, energia e banche. Alta volatilità e rischio politico/cambio.', etf_us:[['EWZ','iShares MSCI Brazil (TER 0.59%)'],['FLBR','Franklin FTSE Brazil (TER 0.19%)']], etf_eu:[] },
  'Messico':   { desc:'Economia emergente in crescita. Beneficia dal nearshoring USA. IPC concentrato in poche grandi aziende.', etf_us:[['EWW','iShares MSCI Mexico (TER 0.50%)']], etf_eu:[] },
  'UK':        { desc:'FTSE 100 dominato da energia (BP, Shell), banche, farmaceutiche. Alta dividend yield. Valuta GBP.', etf_us:[['EWU','iShares MSCI UK (TER 0.50%)']], etf_eu:[['VUKE.L','Vanguard FTSE 100 (TER 0.09%)'],['ISF.L','iShares Core FTSE 100 (TER 0.07%)']] },
  'Germania':  { desc:'DAX 40: auto (BMW, Mercedes, VW), chimica (BASF), assicurazioni (Allianz). Barometro dell\'economia EU.', etf_us:[['EWG','iShares MSCI Germany (TER 0.50%)']], etf_eu:[['EXS1.DE','iShares Core DAX (TER 0.16%)'],['DBXD.DE','Xtrackers DAX (TER 0.09%)']] },
  'Francia':   { desc:'CAC 40: lusso (LVMH, L\'Oréal, Hermès), aerospazio (Airbus), energia (TotalEnergies). Forte export globale.', etf_us:[['EWQ','iShares MSCI France (TER 0.50%)']], etf_eu:[] },
  'Italia':    { desc:'FTSE MIB: banche (Intesa, Unicredit), energy (ENI, Enel), lusso (Moncler, Ferrari). Spread BTP driver chiave.', etf_us:[['EWI','iShares MSCI Italy (TER 0.50%)']], etf_eu:[] },
  'Spagna':    { desc:'IBEX 35: banche (Santander, BBVA), telecom (Telefónica), utility (Iberdrola). Forte esposizione Latam.', etf_us:[['EWP','iShares MSCI Spain (TER 0.50%)']], etf_eu:[] },
  'Svizzera':  { desc:'SMI: farmaceutiche (Novartis, Roche), beni di lusso (Richemont), alimentari (Nestlé). Mercato molto difensivo.', etf_us:[['EWL','iShares MSCI Switzerland (TER 0.50%)']], etf_eu:[] },
  'Olanda':    { desc:'AEX: semiconduttori (ASML ~25% peso), energia (Shell), finanza (ING). ASML è il principale driver.', etf_us:[['EWN','iShares MSCI Netherlands (TER 0.50%)']], etf_eu:[] },
  'Giappone':  { desc:'Nikkei 225: auto (Toyota, Honda), tech (Sony, SoftBank), industria. Yen debole = vantaggio esportatori.', etf_us:[['EWJ','iShares MSCI Japan (TER 0.50%)'],['DXJ','WisdomTree Japan Hedged (TER 0.48%)']], etf_eu:[['VJPN.AS','Vanguard Japan UCITS (TER 0.15%)'],['ISJP.L','iShares Core MSCI Japan (TER 0.15%)']] },
  'Hong Kong': { desc:'Hang Seng: fortemente esposto alla Cina. Tech (Tencent, Alibaba), banche, immobiliare. Rischio geopolitico.', etf_us:[['EWH','iShares MSCI Hong Kong (TER 0.50%)']], etf_eu:[] },
  'Cina':      { desc:'Shanghai Comp.: tech di Stato, banche, energia. Rischio regolamentazione, geopolitica, crisi immobiliare.', etf_us:[['FXI','iShares China Large-Cap (TER 0.74%)'],['MCHI','iShares MSCI China (TER 0.59%)'],['KWEB','KraneShares China Internet (TER 0.76%)']], etf_eu:[['CNYA.L','iShares MSCI China A UCITS (TER 0.40%)']] },
  'India':     { desc:'BSE Sensex: crescita demografica, IT (Infosys, TCS), consumer. Tra i mercati emergenti con crescita più rapida.', etf_us:[['INDA','iShares MSCI India (TER 0.65%)'],['INDY','iShares India 50 (TER 0.93%)']], etf_eu:[] },
  'Australia': { desc:'ASX 200: banche (CBA, ANZ, NAB), mining (BHP, Rio Tinto), REIT. Fortemente correlato alle commodity.', etf_us:[['EWA','iShares MSCI Australia (TER 0.50%)']], etf_eu:[] },
  'Corea Sud': { desc:'KOSPI: semiconduttori (Samsung, SK Hynix), auto (Hyundai, Kia), tech. Il ciclo dei chip è il driver principale.', etf_us:[['EWY','iShares MSCI South Korea (TER 0.50%)']], etf_eu:[] },
  'Singapore': { desc:'STI: hub finanziario Asia. Banche (DBS, OCBC, UOB), REIT, telecom. Stabile, rating AAA, bassa volatilità.', etf_us:[['EWS','iShares MSCI Singapore (TER 0.50%)']], etf_eu:[] },
  'Indonesia': { desc:'IDX Composite: finanza, commodity, consumer. Alta crescita demografica. Rischio cambio rupiah.', etf_us:[['EIDO','iShares MSCI Indonesia (TER 0.57%)']], etf_eu:[] },
  'Argentina': { desc:'Merval: altissima volatilità, iperinflazione, rischio cambio. Solo per investitori speculativi con orizzonte breve.', etf_us:[['ARGT','Global X MSCI Argentina (TER 0.59%)']], etf_eu:[] },
};

var _settoriData = null;

function loadSettori(force) {
  if (_settoriData && !force) return;
  _settoriData = null;
  var loading = document.getElementById('sett-loading');
  var gics    = document.getElementById('sett-gics');
  var naz     = document.getElementById('sett-nazioni');
  loading.style.display = 'block';
  gics.style.opacity = '0.3';
  naz.style.opacity  = '0.3';
  fetch('/api/settori').then(function(r){ return r.json(); }).then(function(d){
    _settoriData = d;
    loading.style.display = 'none';
    gics.style.opacity = '1';
    naz.style.opacity  = '1';
    if (d.ts) document.getElementById('sett-ts').textContent = 'Aggiornato: ' + d.ts;
    renderSettGics(d);
    renderSettNazioni(d);
  }).catch(function(e){
    loading.innerHTML = '<span style="color:#fca5a5">Errore: ' + e.message + '</span>';
    loading.style.display = 'block';
  });
}

function switchSettTab(el, id) {
  document.querySelectorAll('.sett-subtab').forEach(function(b){ b.classList.remove('active'); });
  document.querySelectorAll('.sett-subpanel').forEach(function(p){ p.style.display = 'none'; });
  el.classList.add('active');
  document.getElementById(id).style.display = 'block';
}

function _settBg(v) {
  if (v === null || v === undefined) return 'rgba(30,41,59,.8)';
  if (v >=  8) return 'rgba(20,83,45,.9)';
  if (v >=  4) return 'rgba(22,101,52,.85)';
  if (v >=  1) return 'rgba(21,128,61,.7)';
  if (v >=  0) return 'rgba(20,83,45,.5)';
  if (v >= -1) return 'rgba(127,29,29,.5)';
  if (v >= -4) return 'rgba(153,27,27,.75)';
  return 'rgba(127,29,29,.95)';
}

function _settPill(v, label) {
  if (v === null || v === undefined)
    return '<span class="sett-pill" style="background:rgba(100,116,139,.25);color:#64748b">' + label + ' —</span>';
  var pos = v >= 0;
  var col = pos ? '#86efac' : '#fca5a5';
  var bg  = pos ? 'rgba(34,197,94,.18)' : 'rgba(239,68,68,.18)';
  return '<span class="sett-pill" style="background:' + bg + ';color:' + col + '">' + label + ' ' + (pos?'+':'') + v.toFixed(2) + '%</span>';
}

function _settInterpreta(d) {
  var m = d.p1m, m3 = d.p3m, m1y = d.p1y, g = d.p1d;
  if (m === null || m === undefined) return {label:'Dati non disponibili', segnali:[], color:'#64748b'};
  var label, color;
  if      (m >= 8  && (m3||0) >= 15) { label='🚀 Forte momentum rialzista';   color='#86efac'; }
  else if (m >= 4  && (m3||0) >= 5)  { label='📈 Trend rialzista';             color='#6ee7b7'; }
  else if (m >= 1)                    { label='↗️ Lieve rialzo';                color='#a7f3d0'; }
  else if (m >= -1)                   { label='↔️ Laterale / neutro';           color='#fbd38d'; }
  else if (m >= -4)                   { label='↘️ Debolezza moderata';          color='#fca5a5'; }
  else if (m >= -8)                   { label='📉 Trend ribassista';            color='#f87171'; }
  else                                { label='🔻 Forte trend ribassista';      color='#ef4444'; }
  var segnali = [];
  if (g !== null && g < -1.5 && (m||0) > 2 && (m1y||0) > 5)
    segnali.push('📌 Pullback su trend rialzista — potenziale ingresso tattico');
  if ((m||0) > 0 && (m3||0) > 0 && (m1y||0) > 0)
    segnali.push('✅ Momentum positivo confermato su 1M + 3M + 1A');
  if ((m1y||0) > 20 && (m||0) < -5)
    segnali.push('⚠️ Correzione su trend annuale positivo — monitorare supporti');
  if ((m||0) < -5 && (m3||0) < -10 && (m1y||0) < -10)
    segnali.push('🚫 Evitare: trend negativo confermato su tutti i timeframe');
  if ((m||0) > 5 && (m3||0) > 10)
    segnali.push('🔥 Settore in forte momentum — considerare sovrappeso in portafoglio');
  if ((m||0) > 0 && (m3||0) < -5)
    segnali.push('⚡ Possibile rimbalzo tecnico da ipervenduto — verificare con volumi');
  return {label:label, segnali:segnali, color:color};
}

var _settPerf = {};   // ticker → {p1d,p1w,p1m,p3m,p1y}

function renderSettGics(d) {
  function makeGrid(items, cid, regione) {
    var html = '';
    items.forEach(function(s) {
      _settPerf[s.ticker] = {p1d:s.p1d, p1w:s.p1w, p1m:s.p1m, p3m:s.p3m, p1y:s.p1y};
      var bg  = _settBg(s.p1m);
      var nom = s.nome.replace(/\\/g,'\\\\').replace(/'/g,"\\'");
      var tk  = s.ticker.replace(/'/g,"\\'");
      html += '<div class="sett-card" style="background:' + bg + '" onclick="openSettModal(\'' +
              nom + '\',\'' + tk + '\',\'' + regione + '\')">' +
              '<div class="sett-card-emoji">' + s.emoji + '</div>' +
              '<div class="sett-card-nome">'  + s.nome   + '</div>' +
              '<div class="sett-card-ticker">' + s.ticker + '</div>' +
              '<div class="sett-card-prezzo">' + (s.prezzo !== null ? s.prezzo : '—') + '</div>' +
              '<div class="sett-perf-row">' +
                _settPill(s.p1d,'1G') + _settPill(s.p1w,'1S') +
                _settPill(s.p1m,'1M') + _settPill(s.p3m,'3M') + _settPill(s.p1y,'1A') +
              '</div></div>';
    });
    document.getElementById(cid).innerHTML = html || '<span style="opacity:.4">Nessun dato disponibile</span>';
  }
  makeGrid(d.settori_us, 'sett-us-grid', 'us');
  makeGrid(d.settori_eu, 'sett-eu-grid', 'eu');
}

function renderSettNazioni(d) {
  var regioni = {}, order = [];
  d.nazioni.forEach(function(n) {
    if (!regioni[n.regione]) { regioni[n.regione] = []; order.push(n.regione); }
    regioni[n.regione].push(n);
  });
  var html = '';
  order.forEach(function(reg) {
    html += '<div class="sett-section-title">' + reg + '</div>';
    html += '<div class="tbl-wrap" style="margin-bottom:1.4rem"><table style="width:100%;border-collapse:collapse">' +
            '<thead><tr style="font-size:.7rem;opacity:.5;text-align:right">' +
            '<th style="text-align:left;padding:.35rem .6rem">Paese</th>' +
            '<th style="text-align:left;padding:.35rem .6rem">Indice</th>' +
            '<th style="padding:.35rem .6rem">Prezzo</th>' +
            '<th style="padding:.35rem .6rem">1G</th><th style="padding:.35rem .6rem">1S</th>' +
            '<th style="padding:.35rem .6rem">1M</th><th style="padding:.35rem .6rem">3M</th>' +
            '<th style="padding:.35rem .6rem">1A</th>' +
            '<th style="padding:.35rem .6rem"></th><th style="padding:.35rem .6rem"></th>' +
            '</tr></thead><tbody>';
    regioni[reg].forEach(function(n) {
      function fmtTd(v) {
        if (v===null||v===undefined) return '<td style="text-align:right;padding:.3rem .5rem;opacity:.3">—</td>';
        var c = v>=0?'#86efac':'#fca5a5';
        return '<td style="text-align:right;padding:.3rem .5rem;color:'+c+';font-weight:600">'+(v>=0?'+':'')+v.toFixed(2)+'%</td>';
      }
      var sema = n.p1m===null ? '⚪' : (n.p1m>=2?'🟢':(n.p1m<=-2?'🔴':'🟡'));
      var nm   = n.nome.replace(/'/g,"\\'");
      html += '<tr style="border-bottom:1px solid rgba(255,255,255,.04);font-size:.8rem">' +
              '<td style="padding:.3rem .6rem">' + n.flag + ' <strong>' + n.nome + '</strong></td>' +
              '<td style="padding:.3rem .6rem;opacity:.55;font-size:.72rem">' + n.indice + '</td>' +
              '<td style="text-align:right;padding:.3rem .5rem;font-family:monospace">' + (n.prezzo!==null?n.prezzo:'—') + '</td>' +
              fmtTd(n.p1d)+fmtTd(n.p1w)+fmtTd(n.p1m)+fmtTd(n.p3m)+fmtTd(n.p1y)+
              '<td style="padding:.3rem .5rem;font-size:.9rem">' + sema + '</td>' +
              '<td style="padding:.3rem .5rem"><button onclick="openNazioneModal(\'' + nm + '\')" style="background:rgba(44,82,130,.4);border:none;color:#90cdf4;padding:.15rem .5rem;border-radius:4px;cursor:pointer;font-size:.68rem">ETF ▸</button></td>' +
              '</tr>';
    });
    html += '</tbody></table></div>';
  });
  document.getElementById('sett-naz-wrap').innerHTML = html;
}

function _etfTableHtml(lista, titolo) {
  if (!lista || lista.length === 0) return '';
  var rows = lista.map(function(e){
    return '<tr style="border-bottom:1px solid rgba(255,255,255,.05);font-size:.79rem">' +
           '<td style="padding:.28rem .5rem;font-family:monospace;font-weight:700;color:#fbd38d">' + e[0] + '</td>' +
           '<td style="padding:.28rem .5rem;opacity:.75">' + e[1] + '</td>' +
           '<td style="padding:.28rem .5rem">' +
           '<a href="https://finance.yahoo.com/quote/' + encodeURIComponent(e[0]) + '" target="_blank" style="color:#60a5fa;font-size:.7rem;text-decoration:none">YF ↗</a></td>' +
           '</tr>';
  }).join('');
  return '<div style="font-size:.72rem;font-weight:700;opacity:.55;margin:.7rem 0 .35rem">' + titolo + '</div>' +
         '<table style="width:100%;border-collapse:collapse"><tbody>' + rows + '</tbody></table>';
}

function openSettModal(settore, ticker, regione) {
  var modal = document.getElementById('sett-modal');
  var title = document.getElementById('sett-modal-title');
  var sub   = document.getElementById('sett-modal-sub');
  var info  = document.getElementById('sett-modal-info');
  var body  = document.getElementById('sett-modal-body');
  title.textContent = settore + '  ·  ' + ticker;
  sub.textContent   = (regione==='eu'?'Europa — iShares STOXX Europe 600 Sector ETF':'USA — SPDR Sector ETF');
  body.innerHTML    = '<div style="text-align:center;padding:2rem;opacity:.5">⏳ Caricamento titoli...</div>';
  modal.style.display = 'block';

  var key  = (regione === 'eu') ? (EU_TO_US[settore] || settore) : settore;
  var inf  = SETT_INFO[key] || {};
  var intp = _settInterpreta(_settPerf[ticker] || {});

  var etfHtml = regione === 'eu'
    ? _etfTableHtml(inf.etf_eu, '🇪🇺 ETF Europa (UCITS) consigliati') +
      _etfTableHtml(inf.etf_us, '🇺🇸 ETF USA equivalenti')
    : _etfTableHtml(inf.etf_us, '🇺🇸 ETF USA consigliati') +
      _etfTableHtml(inf.etf_eu, '🇪🇺 ETF Europa (UCITS) equivalenti');
  var fondiHtml = (inf.fondi && inf.fondi.length)
    ? '<div style="font-size:.72rem;font-weight:700;opacity:.55;margin:.7rem 0 .3rem">🏦 Fondi US</div>' +
      '<ul style="margin:0;padding-left:1.2rem;font-size:.78rem;opacity:.7">' +
      inf.fondi.map(function(f){ return '<li>' + f + '</li>'; }).join('') + '</ul>'
    : '';
  var segnaliHtml = intp.segnali.length
    ? '<ul style="margin:.4rem 0 0;padding-left:1.1rem;font-size:.78rem;opacity:.85">' +
      intp.segnali.map(function(s){ return '<li style="margin-bottom:.25rem">' + s + '</li>'; }).join('') + '</ul>'
    : '';

  info.innerHTML =
    '<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">' +
      '<div style="background:rgba(15,23,42,.7);border:1px solid rgba(44,82,130,.35);border-radius:8px;padding:1rem">' +
        '<div style="font-size:.72rem;font-weight:700;opacity:.5;margin-bottom:.4rem;text-transform:uppercase;letter-spacing:.05em">📋 Descrizione</div>' +
        '<div style="font-size:.8rem;opacity:.85;line-height:1.6;margin-bottom:.6rem">' + (inf.desc||'—') + '</div>' +
        '<div style="font-size:.72rem;opacity:.5;margin-bottom:.2rem"><strong>Principali titoli:</strong></div>' +
        '<div style="font-size:.75rem;opacity:.65;margin-bottom:.6rem">' + (inf.include||'—') + '</div>' +
        '<div style="font-size:.72rem;opacity:.5;margin-bottom:.2rem"><strong>Ciclicità:</strong></div>' +
        '<div style="font-size:.75rem;opacity:.65">' + (inf.ciclo||'—') + '</div>' +
      '</div>' +
      '<div>' +
        '<div style="background:rgba(15,23,42,.7);border:1px solid rgba(44,82,130,.35);border-radius:8px;padding:1rem;margin-bottom:.8rem">' +
          '<div style="font-size:.72rem;font-weight:700;opacity:.5;margin-bottom:.4rem;text-transform:uppercase;letter-spacing:.05em">📈 Situazione attuale</div>' +
          '<div style="font-size:.9rem;font-weight:700;color:' + intp.color + ';margin-bottom:.4rem">' + intp.label + '</div>' +
          segnaliHtml +
        '</div>' +
        '<div style="background:rgba(15,23,42,.7);border:1px solid rgba(44,82,130,.35);border-radius:8px;padding:1rem">' +
          '<div style="font-size:.72rem;font-weight:700;opacity:.5;margin-bottom:.4rem;text-transform:uppercase;letter-spacing:.05em">🛒 ETF &amp; Fondi consigliati</div>' +
          etfHtml + fondiHtml +
        '</div>' +
      '</div>' +
    '</div>' +
    '<div style="border-top:1px solid rgba(255,255,255,.08);margin-top:1.2rem;padding-top:1rem;font-size:.75rem;font-weight:600;opacity:.5">Titoli nel database screener</div>';

  fetch('/api/settori/titoli?s=' + encodeURIComponent(settore)).then(function(r){ return r.json(); }).then(function(d){
    if (!d.titoli || d.titoli.length === 0) {
      body.innerHTML = '<p style="opacity:.4;text-align:center;padding:1.5rem">Nessun titolo trovato — esegui lo screener azioni per popolare i dati.</p>';
      return;
    }
    sub.textContent = (regione==='eu'?'Europa — iShares STOXX Europe 600':'USA — SPDR') + ' · ' + d.tot + ' titoli nel database';
    var rows = d.titoli.map(function(t) {
      function fp(v) {
        if (v===null||v===undefined) return '<span style="opacity:.3">—</span>';
        var c = parseFloat(v)>=0?'#86efac':'#fca5a5';
        return '<span style="color:'+c+'">'+(parseFloat(v)>=0?'+':'')+parseFloat(v).toFixed(1)+'%</span>';
      }
      var sc    = t.score!==null ? parseFloat(t.score) : null;
      var scCol = sc===null?'#64748b':(sc>=70?'#86efac':(sc>=50?'#fbd38d':'#fca5a5'));
      var fsh   = t.foglio||'';
      var badge = (fsh.indexOf('Selezionat')>=0||fsh.indexOf('Top')>=0)
                  ? '<span style="font-size:.58rem;background:rgba(34,197,94,.2);color:#86efac;padding:.1rem .35rem;border-radius:3px;margin-left:.3rem">SEL</span>' : '';
      return '<tr style="border-bottom:1px solid rgba(255,255,255,.04);font-size:.79rem">' +
             '<td style="padding:.3rem .5rem;font-family:monospace;font-weight:700">' + t.ticker + badge + '</td>' +
             '<td style="padding:.3rem .5rem;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="'+t.nome+'">'+t.nome+'</td>' +
             '<td style="padding:.3rem .5rem;opacity:.5;font-size:.7rem">'+t.mercato+'</td>' +
             '<td style="padding:.3rem .5rem;text-align:right;font-weight:700;color:'+scCol+'">'+(sc!==null?sc.toFixed(1):'—')+'</td>' +
             '<td style="padding:.3rem .5rem;text-align:right">'+fp(t.p1d)+'</td>' +
             '<td style="padding:.3rem .5rem;text-align:right">'+fp(t.p1y)+'</td>' +
             '</tr>';
    }).join('');
    body.innerHTML = '<div class="tbl-wrap"><table style="width:100%;border-collapse:collapse">' +
      '<thead><tr style="font-size:.68rem;opacity:.45;text-align:right">' +
      '<th style="text-align:left;padding:.3rem .5rem">Ticker</th><th style="text-align:left;padding:.3rem .5rem">Nome</th>' +
      '<th style="text-align:left;padding:.3rem .5rem">Mercato</th><th style="padding:.3rem .5rem">Score</th>' +
      '<th style="padding:.3rem .5rem">1G%</th><th style="padding:.3rem .5rem">1A%</th>' +
      '</tr></thead><tbody>' + rows + '</tbody></table></div>';
  }).catch(function(e){
    body.innerHTML = '<span style="color:#fca5a5">Errore: ' + e.message + '</span>';
  });
}

function openNazioneModal(nome) {
  var modal = document.getElementById('sett-modal');
  var title = document.getElementById('sett-modal-title');
  var sub   = document.getElementById('sett-modal-sub');
  var info  = document.getElementById('sett-modal-info');
  var body  = document.getElementById('sett-modal-body');
  var n     = NAZIONI_ETF[nome] || {};
  title.textContent = nome + ' — Mercato & ETF';
  sub.textContent   = n.desc || '—';
  body.innerHTML    = '';
  var etfHtml = _etfTableHtml(n.etf_us, '🇺🇸 ETF USA per esposizione a ' + nome) +
                _etfTableHtml(n.etf_eu, '🇪🇺 ETF Europa (UCITS) equivalenti');
  info.innerHTML =
    '<div style="background:rgba(15,23,42,.7);border:1px solid rgba(44,82,130,.35);border-radius:8px;padding:1.1rem">' +
      (etfHtml || '<span style="opacity:.4">Nessun ETF mappato per questo mercato</span>') +
      '<div style="font-size:.7rem;opacity:.4;margin-top:.8rem">ℹ️ TER = Total Expense Ratio annuo · Clicca YF per dati live su Yahoo Finance</div>' +
    '</div>';
  modal.style.display = 'block';
}

// ═══════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════
loadStatus();
loadMercati();
loadServizi();
loadKBStatus();
setInterval(loadStatus,15000);
</script>
</body>
</html>"""
