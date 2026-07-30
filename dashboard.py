# -*- coding: utf-8 -*-
"""
ROBOT TRADER 2026 - DASHBOARD
Un file. Un comando. python dashboard.py → http://localhost:5000

Funzionalità:
  - Visualizza report (Top 50 per Azioni/ETF/Fondi)
  - Modifica parametri.json dalla UI
  - Lancia screener dalla UI (singoli o tutti)
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import sys
import glob
import subprocess
import threading
from datetime import datetime

try:
    import pandas as pd
except ImportError:
    print("ERRORE: pip install pandas openpyxl")
    exit(1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(BASE_DIR, "REPORTS_DAILY")
PARAMETRI_FILE = os.path.join(BASE_DIR, "parametri.json")

# --- Stato screener in esecuzione ---
running = {}  # {'azioni': {'pid': ..., 'start': ..., 'status': 'running'}}
run_lock = threading.Lock()


# ========== FUNZIONI DATI ==========

def get_latest_file(pattern):
    files = sorted(glob.glob(os.path.join(REPORTS_DIR, pattern)))
    return files[-1] if files else None

def get_status():
    data = {}
    for tipo, pat in [('azioni','Azioni_Screener_*.xlsx'),('etf','ETF_Screener_*.xlsx'),('fondi','FONDI_Screener_*.xlsx')]:
        f = get_latest_file(pat)
        if f:
            stat = os.stat(f)
            data[tipo] = {
                'file': os.path.basename(f),
                'size': f"{stat.st_size/1024:.0f} KB",
                'time': datetime.fromtimestamp(stat.st_mtime).strftime('%d/%m/%Y %H:%M'),
            }
            try:
                xls = pd.ExcelFile(f)
                for sn in xls.sheet_names:
                    if 'selezionat' in sn.lower() or 'top' in sn.lower():
                        df = pd.read_excel(f, sheet_name=sn)
                        data[tipo]['count'] = len(df)
                        break
            except:
                data[tipo]['count'] = '?'
        else:
            data[tipo] = None
    # Stato screener in esecuzione
    with run_lock:
        data['_running'] = {k: v['status'] for k, v in running.items()}
    return data

def get_table_data(tipo):
    patterns = {
        'azioni': ('Azioni_Screener_*.xlsx', 'Top 50 per Score'),
        'etf': ('ETF_Screener_*.xlsx', 'Top 50 per Score'),
        'fondi': ('FONDI_Screener_*.xlsx', 'Top 50 per Score'),
    }
    if tipo not in patterns:
        return {'error': 'tipo non valido'}
    pat, sheet = patterns[tipo]
    f = get_latest_file(pat)
    if not f:
        return {'rows': [], 'file': None, 'time': None}
    try:
        df = pd.read_excel(f, sheet_name=sheet)
        rows = df.head(50).to_dict(orient='records')
    except:
        # Fallback
        try:
            xls = pd.ExcelFile(f)
            rows = None
            for sn in xls.sheet_names:
                if 'selezionat' in sn.lower():
                    df = pd.read_excel(f, sheet_name=sn)
                    rows = df.head(50).to_dict(orient='records')
                    break
            if rows is None:
                return {'rows': [], 'file': os.path.basename(f), 'time': None}
        except:
            return {'rows': [], 'file': os.path.basename(f), 'time': None}
    # Pulisci NaN
    for r in rows:
        for k, v in r.items():
            if isinstance(v, float) and (v != v):
                r[k] = None
    ts = datetime.fromtimestamp(os.path.getmtime(f)).strftime('%d/%m/%Y %H:%M')
    return {'rows': rows, 'file': os.path.basename(f), 'time': ts}


# ========== PARAMETRI ==========

def read_params():
    try:
        with open(PARAMETRI_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def save_params(data):
    # Backup prima di scrivere
    if os.path.exists(PARAMETRI_FILE):
        bk = PARAMETRI_FILE.replace('.json', f'_bk_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        with open(PARAMETRI_FILE, 'r', encoding='utf-8') as f:
            with open(bk, 'w', encoding='utf-8') as fb:
                fb.write(f.read())
    with open(PARAMETRI_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return True


# ========== LANCIO SCREENER ==========

SCREENER_MAP = {
    'azioni': 'value_screener_azioni.py',
    'etf': 'value_screener_etf.py',
    'fondi': 'value_screener_fondi.py',
    'tutti': None,  # speciale
}

def run_screener(tipo):
    """Lancia screener in background thread"""
    with run_lock:
        if tipo in running and running[tipo]['status'] == 'running':
            return {'ok': False, 'msg': f'{tipo} già in esecuzione'}

    def _run():
        scripts = []
        if tipo == 'tutti':
            scripts = [('azioni','value_screener_azioni.py'), ('etf','value_screener_etf.py'), ('fondi','value_screener_fondi.py')]
        else:
            scripts = [(tipo, SCREENER_MAP[tipo])]

        for name, script in scripts:
            with run_lock:
                running[name] = {'status': 'running', 'start': datetime.now().strftime('%H:%M:%S')}
            try:
                script_path = os.path.join(BASE_DIR, script)
                result = subprocess.run(
                    [sys.executable, script_path],
                    cwd=BASE_DIR,
                    capture_output=True,
                    timeout=2400,
                    text=True
                )
                with run_lock:
                    running[name] = {
                        'status': 'completato' if result.returncode == 0 else 'errore',
                        'end': datetime.now().strftime('%H:%M:%S'),
                        'exit_code': result.returncode
                    }
            except subprocess.TimeoutExpired:
                with run_lock:
                    running[name] = {'status': 'timeout', 'end': datetime.now().strftime('%H:%M:%S')}
            except Exception as e:
                with run_lock:
                    running[name] = {'status': f'errore: {str(e)[:50]}', 'end': datetime.now().strftime('%H:%M:%S')}

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return {'ok': True, 'msg': f'{tipo} avviato'}


# ========== HTML ==========

HTML = r"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Robot Trader 2026</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f1923;color:#e0e0e0;min-height:100vh}
.topbar{background:rgba(0,0,0,0.5);border-bottom:1px solid rgba(255,149,0,0.3);padding:1rem 2rem;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100;backdrop-filter:blur(10px)}
.topbar h1{color:#FF9500;font-size:1.4rem;letter-spacing:1px}
.topbar .meta{font-size:0.85rem;opacity:0.7}
.container{max-width:1400px;margin:0 auto;padding:1.5rem}
.tabs{display:flex;gap:0;margin-bottom:1.5rem;background:rgba(0,0,0,0.3);border-radius:8px;overflow:hidden;border:1px solid rgba(255,149,0,0.15)}
.tab{flex:1;padding:0.9rem;text-align:center;cursor:pointer;font-weight:600;font-size:0.95rem;transition:all 0.2s;border-right:1px solid rgba(255,149,0,0.1)}
.tab:last-child{border-right:none}
.tab:hover{background:rgba(255,149,0,0.08)}
.tab.active{background:rgba(255,149,0,0.18);color:#FF9500}
.kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin-bottom:1.5rem}
.kpi{background:rgba(255,149,0,0.04);border:1px solid rgba(255,149,0,0.15);border-radius:8px;padding:1.2rem;text-align:center}
.kpi .label{font-size:0.8rem;opacity:0.6;margin-bottom:0.3rem}
.kpi .value{font-size:1.8rem;font-weight:700;color:#FF9500}
.kpi .sub{font-size:0.75rem;opacity:0.5;margin-top:0.3rem}
.panel{display:none}
.panel.active{display:block}
.tbl-wrap{overflow-x:auto;border:1px solid rgba(255,149,0,0.15);border-radius:8px;background:rgba(0,0,0,0.2)}
table{width:100%;border-collapse:collapse;font-size:0.85rem}
th{padding:0.8rem 0.6rem;text-align:left;color:#FF9500;font-weight:600;background:rgba(0,0,0,0.3);border-bottom:1px solid rgba(255,149,0,0.2);white-space:nowrap}
td{padding:0.6rem;border-bottom:1px solid rgba(255,255,255,0.04)}
tr:hover td{background:rgba(255,149,0,0.04)}
.ticker{color:#FF9500;font-weight:700;font-family:'SF Mono',monospace}
.num-neg{color:#ef4444}
.box{background:rgba(255,149,0,0.04);border:1px solid rgba(255,149,0,0.15);border-radius:8px;padding:1.2rem;margin-bottom:1rem}
.box strong{color:#FF9500}
.box h3{color:#FF9500;margin-bottom:0.8rem;font-size:1rem}
.footer{text-align:center;padding:2rem;opacity:0.4;font-size:0.8rem}
.btn{padding:0.5rem 1.2rem;border-radius:6px;cursor:pointer;font-weight:600;font-size:0.85rem;border:1px solid;transition:all 0.15s}
.btn-orange{background:rgba(255,149,0,0.15);border-color:#FF9500;color:#FF9500}
.btn-orange:hover{background:rgba(255,149,0,0.3)}
.btn-green{background:rgba(34,197,94,0.15);border-color:#22c55e;color:#22c55e}
.btn-green:hover{background:rgba(34,197,94,0.3)}
.btn-red{background:rgba(239,68,68,0.15);border-color:#ef4444;color:#ef4444}
.btn-red:hover{background:rgba(239,68,68,0.3)}
.btn:disabled{opacity:0.4;cursor:not-allowed}
.run-status{display:inline-block;padding:0.2rem 0.6rem;border-radius:4px;font-size:0.75rem;font-weight:600}
.run-running{background:rgba(255,149,0,0.2);color:#FF9500;animation:pulse 1.5s infinite}
.run-completato{background:rgba(34,197,94,0.2);color:#22c55e}
.run-errore,.run-timeout{background:rgba(239,68,68,0.2);color:#ef4444}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}
.param-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem}
.param-group{background:rgba(0,0,0,0.2);border:1px solid rgba(255,149,0,0.1);border-radius:8px;padding:1rem}
.param-group h4{color:#FF9500;margin-bottom:0.8rem;font-size:0.95rem}
.param-row{display:flex;justify-content:space-between;align-items:center;padding:0.4rem 0;border-bottom:1px solid rgba(255,255,255,0.04)}
.param-row:last-child{border-bottom:none}
.param-label{font-size:0.85rem;opacity:0.8}
.param-input{background:rgba(0,0,0,0.3);border:1px solid rgba(255,149,0,0.2);color:#e0e0e0;padding:0.4rem 0.6rem;border-radius:4px;width:100px;text-align:right;font-size:0.85rem}
.param-input:focus{outline:none;border-color:#FF9500}
.param-desc{font-size:0.7rem;opacity:0.5}
.msg{padding:0.6rem 1rem;border-radius:6px;margin-bottom:1rem;font-size:0.85rem;display:none}
.msg-ok{background:rgba(34,197,94,0.15);border:1px solid rgba(34,197,94,0.3);color:#22c55e;display:block}
.msg-err{background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.3);color:#ef4444;display:block}
@media(max-width:768px){.kpi-row{grid-template-columns:1fr 1fr}.topbar{padding:0.8rem 1rem}.container{padding:1rem}.param-grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="topbar">
  <h1>🤖 Robot Trader 2026</h1>
  <div style="display:flex;gap:1rem;align-items:center">
    <span class="meta" id="last-update">—</span>
    <button class="btn btn-orange" onclick="loadAll()">↻ Aggiorna</button>
  </div>
</div>

<div class="container">
  <div class="tabs">
    <div class="tab active" onclick="switchTab(this,'home')">📊 Home</div>
    <div class="tab" onclick="switchTab(this,'azioni')">📈 Azioni</div>
    <div class="tab" onclick="switchTab(this,'etf')">📦 ETF</div>
    <div class="tab" onclick="switchTab(this,'fondi')">🏦 Fondi</div>
    <div class="tab" onclick="switchTab(this,'parametri')">⚙️ Parametri</div>
  </div>

  <!-- HOME -->
  <div id="home" class="panel active">
    <div class="kpi-row" id="kpis"></div>
    <div class="box">
      <h3>🚀 Esecuzione Manuale</h3>
      <div style="display:flex;gap:0.8rem;flex-wrap:wrap;margin-top:0.5rem">
        <button class="btn btn-green" onclick="runScreener('azioni')" id="run-azioni">▶ Azioni</button>
        <button class="btn btn-green" onclick="runScreener('etf')" id="run-etf">▶ ETF</button>
        <button class="btn btn-green" onclick="runScreener('fondi')" id="run-fondi">▶ Fondi</button>
        <button class="btn btn-orange" onclick="runScreener('tutti')" id="run-tutti">▶▶ Tutti</button>
      </div>
      <div id="run-msg" style="margin-top:0.8rem;font-size:0.85rem"></div>
    </div>
    <div class="box">
      <strong>⏰ Scheduler:</strong> 08:05 CEST giornaliero via Task Scheduler<br>
      <strong>📧 Email:</strong> 5 destinatari
    </div>
  </div>

  <!-- AZIONI -->
  <div id="azioni" class="panel">
    <div class="box" id="azioni-info">Caricamento...</div>
    <div class="tbl-wrap"><table id="azioni-table"><tr><td style="text-align:center;padding:2rem;opacity:0.5">Clicca per caricare</td></tr></table></div>
  </div>

  <!-- ETF -->
  <div id="etf" class="panel">
    <div class="box" id="etf-info">Caricamento...</div>
    <div class="tbl-wrap"><table id="etf-table"><tr><td style="text-align:center;padding:2rem;opacity:0.5">Clicca per caricare</td></tr></table></div>
  </div>

  <!-- FONDI -->
  <div id="fondi" class="panel">
    <div class="box" id="fondi-info">Caricamento...</div>
    <div class="tbl-wrap"><table id="fondi-table"><tr><td style="text-align:center;padding:2rem;opacity:0.5">Clicca per caricare</td></tr></table></div>
  </div>

  <!-- PARAMETRI -->
  <div id="parametri" class="panel">
    <div id="params-msg" class="msg"></div>
    <div id="params-container">Caricamento parametri...</div>
    <div style="margin-top:1rem;display:flex;gap:0.8rem">
      <button class="btn btn-green" onclick="saveParams()">💾 Salva Parametri</button>
      <button class="btn btn-red" onclick="loadParams()">↺ Annulla Modifiche</button>
    </div>
  </div>

  <div class="footer">Robot Trader 2026 — Fuerte Venture Capital / NCF New Capital Fuerte SL</div>
</div>

<script>
let paramsData = null;

function switchTab(el, id) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  el.classList.add('active');
  if (['azioni','etf','fondi'].includes(id)) {
    const tbl = document.getElementById(id+'-table');
    if (!tbl.dataset.loaded) loadTable(id);
  }
  if (id === 'parametri' && !paramsData) loadParams();
}

// === STATUS + KPI ===
async function loadStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    const runState = d._running || {};
    delete d._running;
    let html = '';
    for (const [tipo, info] of Object.entries(d)) {
      const rs = runState[tipo];
      const badge = rs ? `<span class="run-status run-${rs}">${rs}</span>` : '';
      if (info) {
        html += `<div class="kpi">
          <div class="label">${tipo.toUpperCase()} ${badge}</div>
          <div class="value">${info.count ?? '—'}</div>
          <div class="sub">${info.size} · ${info.time}</div>
        </div>`;
      } else {
        html += `<div class="kpi"><div class="label">${tipo.toUpperCase()} ${badge}</div><div class="value">—</div><div class="sub">Nessun report</div></div>`;
      }
    }
    document.getElementById('kpis').innerHTML = html;
    document.getElementById('last-update').textContent = new Date().toLocaleTimeString('it-IT');
    // Aggiorna bottoni run
    for (const [k, v] of Object.entries(runState)) {
      const btn = document.getElementById('run-'+k);
      if (btn) {
        btn.disabled = (v === 'running');
        if (v === 'running') btn.textContent = '⏳ ' + k.charAt(0).toUpperCase() + k.slice(1) + '...';
        else btn.textContent = '▶ ' + k.charAt(0).toUpperCase() + k.slice(1);
      }
    }
  } catch(e) {}
}

// === TABELLE ===
async function loadTable(tipo) {
  const tbl = document.getElementById(tipo+'-table');
  const info = document.getElementById(tipo+'-info');
  try {
    const r = await fetch('/api/data/'+tipo);
    const d = await r.json();
    info.innerHTML = `<strong>📄 ${d.file || '—'}</strong> · ${d.time || '—'} · ${d.rows?.length || 0} righe`;
    if (!d.rows || d.rows.length === 0) { tbl.innerHTML = '<tr><td>Nessun dato</td></tr>'; return; }
    const cols = Object.keys(d.rows[0]);
    let h = '<tr>' + cols.map(c => '<th>'+c+'</th>').join('') + '</tr>';
    let b = d.rows.map(row => '<tr>' + cols.map(c => {
      let v = row[c];
      if (v === null || v === undefined) return '<td>—</td>';
      let cls = '';
      if (c === 'Ticker') cls = ' class="ticker"';
      else if (typeof v === 'number' && v < 0) cls = ' class="num-neg"';
      if (typeof v === 'number' && !Number.isInteger(v)) v = v.toFixed(2);
      return '<td'+cls+'>'+v+'</td>';
    }).join('') + '</tr>').join('');
    tbl.innerHTML = h + b;
    tbl.dataset.loaded = '1';
  } catch(e) {
    tbl.innerHTML = '<tr><td>Errore: '+e.message+'</td></tr>';
  }
}

// === PARAMETRI ===
const PARAM_LABELS = {
  'ev_fcf_max': 'EV/FCF max',
  'price_book_max': 'P/B max',
  'roe_min': 'ROE min',
  'net_debt_ebitda_max': 'Net Debt/EBITDA max',
  'ter_max': 'TER max (%)',
  'sharpe_min': 'Sharpe min',
  'volume_min': 'Volume min',
  'performance_1y_min': 'Performance 1Y min (%)'
};

const SECTION_NAMES = {
  'azioni': '📈 Azioni',
  'etf': '📦 ETF',
  'fondi': '🏦 Fondi'
};

async function loadParams() {
  try {
    const r = await fetch('/api/params');
    paramsData = await r.json();
    renderParams();
    showParamMsg('', '');
  } catch(e) {
    document.getElementById('params-container').innerHTML = 'Errore caricamento: ' + e.message;
  }
}

function renderParams() {
  let html = '<div class="param-grid">';
  for (const [section, params] of Object.entries(paramsData)) {
    if (typeof params !== 'object') continue;
    const title = SECTION_NAMES[section] || section;
    html += `<div class="param-group"><h4>${title}</h4>`;
    for (const [key, obj] of Object.entries(params)) {
      if (typeof obj !== 'object' || !('value' in obj)) continue;
      const label = PARAM_LABELS[key] || obj.description || key;
      const desc = obj.description || '';
      const val = obj.value;
      html += `<div class="param-row">
        <div><div class="param-label">${label}</div><div class="param-desc">${desc}</div></div>
        <input class="param-input" type="number" step="any"
          data-section="${section}" data-key="${key}" value="${val}">
      </div>`;
    }
    html += '</div>';
  }
  html += '</div>';
  document.getElementById('params-container').innerHTML = html;
}

async function saveParams() {
  // Leggi valori dagli input
  const inputs = document.querySelectorAll('.param-input');
  inputs.forEach(inp => {
    const s = inp.dataset.section;
    const k = inp.dataset.key;
    const v = parseFloat(inp.value);
    if (!isNaN(v) && paramsData[s] && paramsData[s][k]) {
      paramsData[s][k].value = v;
    }
  });
  try {
    const r = await fetch('/api/params', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(paramsData)
    });
    const d = await r.json();
    if (d.ok) showParamMsg('✅ Parametri salvati! (backup creato)', 'ok');
    else showParamMsg('❌ Errore: ' + d.msg, 'err');
  } catch(e) {
    showParamMsg('❌ ' + e.message, 'err');
  }
}

function showParamMsg(text, type) {
  const el = document.getElementById('params-msg');
  el.className = 'msg' + (type ? ' msg-'+type : '');
  el.textContent = text;
}

// === RUN SCREENER ===
async function runScreener(tipo) {
  const btn = document.getElementById('run-'+tipo);
  if (btn) btn.disabled = true;
  try {
    const r = await fetch('/api/run/'+tipo, {method:'POST'});
    const d = await r.json();
    document.getElementById('run-msg').innerHTML = d.ok
      ? `✅ ${tipo.toUpperCase()} avviato alle ${new Date().toLocaleTimeString('it-IT')}`
      : `❌ ${d.msg}`;
    setTimeout(loadStatus, 2000);
  } catch(e) {
    document.getElementById('run-msg').innerHTML = '❌ ' + e.message;
    if (btn) btn.disabled = false;
  }
}

function loadAll() {
  loadStatus();
  ['azioni','etf','fondi'].forEach(t => {
    const tbl = document.getElementById(t+'-table');
    if (tbl) tbl.dataset.loaded = '';
  });
  const active = document.querySelector('.panel.active');
  if (active && ['azioni','etf','fondi'].includes(active.id)) loadTable(active.id);
  if (active && active.id === 'parametri') loadParams();
}

loadStatus();
setInterval(loadStatus, 15000);
</script>
</body>
</html>"""


# ========== SERVER ==========

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self._html(HTML)
        elif self.path == '/api/status':
            self._json(get_status())
        elif self.path.startswith('/api/data/'):
            self._json(get_table_data(self.path.split('/')[-1]))
        elif self.path == '/api/params':
            self._json(read_params())
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/api/params':
            body = self._read_body()
            try:
                data = json.loads(body)
                save_params(data)
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
        elif self.path.startswith('/api/run/'):
            tipo = self.path.split('/')[-1]
            if tipo not in SCREENER_MAP:
                self._json({'ok': False, 'msg': f'tipo {tipo} non valido'})
            else:
                result = run_screener(tipo)
                self._json(result)
        else:
            self.send_error(404)

    def _html(self, content):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))

    def _json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, default=str).encode('utf-8'))

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(length).decode('utf-8')

    def log_message(self, format, *args):
        pass  # silenzio


if __name__ == '__main__':
    PORT = 5000
    print("=" * 60)
    print("ROBOT TRADER 2026 — DASHBOARD")
    print("=" * 60)
    print(f"\n  → http://localhost:{PORT}\n")
    print(f"  Reports: {REPORTS_DIR}")
    print(f"  Parametri: {PARAMETRI_FILE}")
    print(f"\n  Ctrl+C per chiudere")
    print("=" * 60)

    server = HTTPServer(('localhost', PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nChiuso.")
        server.server_close()
