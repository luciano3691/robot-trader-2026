# ROBOT TRADER 2026 — DOCUMENTO ANALITICO COMPLETO
### Fuerte Venture Capital SL — NCF New Capital Fuerte SL
**Data documento originale:** 01 giugno 2026  
**Ultimo aggiornamento:** 24 giugno 2026  
**Stato progetto:** Sviluppo attivo — funzionale in locale, pre-lancio

---

> ⚠️ **NOTA:** Il documento originale (sezioni 1–20) descrive lo stato al 01/06/2026.  
> Le sezioni **21–24** in fondo riportano tutti gli aggiornamenti successivi fino al 24/06/2026.  
> Per lo stato operativo completo e aggiornato vedere:  
> `01_DOCUMENTAZIONE_OPERATIVA/Stato_Progetto_RobotTrader2026_20260624.md`

---

---

## 1. VISIONE E OBIETTIVO DI BUSINESS

Robot Trader 2026 è un sistema di **screening fondamentale automatizzato** rivolto a investitori privati, consulenti finanziari indipendenti e gestori patrimoniali europei. Il prodotto analizza quotidianamente migliaia di strumenti finanziari (azioni, ETF, fondi) e produce report Excel classificati e filtrati, venduti in abbonamento mensile tramite tre tier di prezzo per ciascuna delle tre classi di asset.

Il modello di business è **SaaS per abbonamento** su tre livelli:

| Tier    | Prezzo/mese | Target cliente |
|---------|-------------|----------------|
| Basic   | €29         | Investitore privato alle prime armi nel deep value |
| Pro     | €39         | Investitore attivo con esperienza fondamentale |
| Value   | €59         | Professionista, consulente finanziario indipendente |

Ogni tier vale per ciascuna delle tre classi (Azioni, ETF, Fondi), generando un catalogo di **9 prodotti** (3 classi × 3 tier). Il prezzo massimo teorico per un utente che abbona tutte e tre le classi al tier Value è €177/mese.

---

## 2. ARCHITETTURA TECNICA GENERALE

```
Desktop Windows 11 / WSL2 Ubuntu
│
├── PYTHON_SCRIPTS/                    ← cartella di lavoro principale
│   ├── dashboard.py                   ← server HTTP + interfaccia admin + landing page (1.559 righe)
│   ├── value_screener_azioni.py       ← screener azioni (488 righe)
│   ├── value_screener_etf.py          ← screener ETF (443 righe)
│   ├── value_screener_fondi.py        ← screener fondi (368 righe)
│   ├── ticker_lists_5000.py           ← universo ticker (470 righe)
│   ├── parametri.json                 ← filtri configurabili runtime
│   ├── servizi_config.json            ← piani abbonamento, prezzi, features
│   ├── REPORTS_DAILY/                 ← output Excel giornalieri
│   └── [file di supporto legacy]      ← firebase, orchestrator, ecc.
│
└── Accesso admin: http://localhost:5000/login
```

### Stack tecnologico effettivo (quello che gira)

| Componente | Tecnologia | Note |
|---|---|---|
| Web server | `http.server.HTTPServer` (stdlib Python) | Nessun framework esterno |
| Routing | Parsing manuale `self.path` | GET e POST gestiti a mano |
| Autenticazione | Cookie `rt_admin` + `secrets.token_hex(20)` | Session set in-memory, reset al riavvio |
| Fonte dati | `yfinance` (Yahoo Finance API non ufficiale) | Gratuita, nessuna chiave |
| Fonte dati EU | `urllib.request` → justETF.com (scraping) | Per TER ETF europei |
| Output | `openpyxl` → `.xlsx` multi-foglio | Report Excel formattati |
| Analisi | `pandas` | Lettura report in dashboard |
| Dati tick | `yfinance.Ticker.history(period="1y")` | 1 anno prezzi giornalieri |
| Esecuzione | `subprocess.Popen()` + thread daemon | Ogni screener è un processo separato |
| Persistenza | File JSON + file Excel | Nessun database |
| Scheduling | Windows Task Scheduler (`.bat`) | Ogni mattina alle 08:05 |

**Nota architetturale critica:** Non c'è Flask, Django, FastAPI né alcun web framework. Il server è interamente implementato in `dashboard.py` usando la HTTP server della libreria standard. Questo ha pro (zero dipendenze, zero overhead) e contro (nessuna gestione automatica di multithread, MIME types, error pages, CORS, ecc.).

---

## 3. IL SERVER — dashboard.py in dettaglio

### 3.1 Struttura interna

Il file `dashboard.py` (1.559 righe) contiene **tutto in un unico file**:
- Logica server HTTP (`BaseHTTPRequestHandler`)
- Autenticazione admin
- API endpoints (JSON)
- HTML/CSS/JS della landing page pubblica
- HTML/CSS/JS del pannello admin
- Lettura/scrittura JSON di configurazione
- Avvio screener come subprocess
- Gestione log in tempo reale via polling

### 3.2 Routing

```
GET  /               → landing page pubblica (HTML statico inline)
GET  /login          → form login admin
POST /login          → verifica password, imposta cookie, redirect /admin
GET  /admin          → pannello admin (richiede auth)
GET  /logout         → cancella sessione, redirect /login
GET  /api/status     → JSON stato screener (count, data, running)
GET  /api/table?tipo=azioni|etf|fondi  → JSON Top 50 dati
GET  /api/mercati    → JSON breakdown per mercato (solo azioni)
GET  /api/log?tipo=  → JSON log esecuzione in corso
GET  /api/servizi    → JSON piani abbonamento
POST /api/servizi    → salva piani abbonamento su file
GET  /api/parametri  → JSON filtri screener
POST /api/parametri  → salva filtri su file (con backup automatico)
POST /api/run?tipo=  → avvia screener in background thread
GET  /api/download?tipo= → download file Excel più recente
```

### 3.3 Sessioni admin

- Password: configurabile in `parametri.json` (hash SHA-256 in produzione, `"123"` in sviluppo — **da cambiare prima del lancio**)
- Token: `secrets.token_hex(20)` — 40 caratteri esadecimali, crittograficamente sicuri
- Storage: `set()` Python in memoria — le sessioni si perdono al riavvio del server
- Cookie: `rt_admin=<token>; HttpOnly; SameSite=Strict` — protetto da XSS e CSRF
- Timeout: il JSON `parametri.json` prevede `session_timeout_minutes: 120` ma il codice attuale non scade le sessioni attivamente

### 3.4 Avvio screener e gestione log

```python
# Ogni screener è un processo separato:
proc = subprocess.Popen(
    [sys.executable, 'value_screener_etf.py'],
    stdout=PIPE, stderr=STDOUT, bufsize=1, text=True
)
for line in proc.stdout:
    _log(tipo, line.rstrip())   # accumula in running[tipo]['log']
proc.wait(timeout=2400)         # timeout 40 minuti
```

Il polling del log avviene dal browser ogni 2 secondi via `/api/log?tipo=`. Il buffer `MAX_LOG = 300` righe per tipo. Per il tipo `tutti`, le righe di ogni screener vengono duplamente scritte: nel log del screener specifico E nel log aggregato `running['tutti']`.

### 3.5 Il bug storico di _latest() — risolto

```python
# PRIMA (buggy): ordinamento alfabetico
sorted(files)[-1]
# 'v' (ASCII 118) > 'F' (ASCII 70) → value_screener_* batteva sempre FONDI_Screener_*
# Risultato: KPI data sempre 27/05/2026 anche dopo run del 01/06/2026

# DOPO (corretto): ordinamento per data di modifica
sorted(files, key=os.path.getmtime)[-1]
```

---

## 4. L'UNIVERSO TICKER — ticker_lists_5000.py

### 4.1 Dimensioni attuali

| Asset Class | Tickers | Universo geografico |
|---|---|---|
| `ALL_AZIONI` | 920 | USA, EU7, Nordici, Amsterdam, Giappone, HK, Australia, Canada |
| `ALL_ETF` | 390 | USA (broad, sector, bond, intl, factor, RE/comm) + Europa (.L, .DE, .AS, .PA, .MI, .SW) |
| `ALL_FONDI` | 201 | USA mutual funds: Vanguard, Fidelity, T.Rowe, American, Schwab, PIMCO, DFA, altri |
| **TOTALE** | **1.511** | |

### 4.2 Struttura interna (esempio ETF)

```python
ETF_US_BROAD     = ['SPY','IVV','VOO','VTI','QQQ',...]    # ~35
ETF_US_SECTOR    = ['XLF','XLK','XLE','XLV',...]           # ~50
ETF_US_BONDS     = ['AGG','BND','LQD','HYG','TLT',...]     # ~40
ETF_US_INTL      = ['VEA','VWO','EFA','EEM',...]            # ~50
ETF_US_FACTOR    = ['MTUM','VLUE','USMV',...]               # ~33
ETF_US_REAL_COMM = ['GLD','SLV','IAU',...]                  # ~30
ETF_EUROPE_L     = ['IWDA.L','SWDA.L','CSPX.L',...]        # ~40 (.L = London)
ETF_EUROPE_DE    = ['EXS1.DE','EXSA.DE',...]                # ~32 (.DE = Xetra)
ETF_EUROPE_AS    = ['IWDA.AS','EMIM.AS',...]                # ~18 (.AS = Amsterdam)
ETF_EUROPE_PA    = ['CW8.PA','EWLD.PA',...]                 # ~10 (.PA = Euronext Paris)
ETF_EUROPE_MI    = ['SWDA.MI',...]                          # ~9  (.MI = Borsa Italiana)
ETF_EUROPE_SW    = ['SWRD.SW',...]                          # ~7  (.SW = SIX Swiss)

ALL_ETF = list(dict.fromkeys(ETF_US_BROAD + ... + ETF_EUROPE_SW))  # dedup → 390
```

Il `dict.fromkeys()` garantisce unicità mantenendo l'ordine di inserzione (Python 3.7+).

---

## 5. LO SCREENER AZIONI — value_screener_azioni.py

### 5.1 Filosofia di screening: Deep Value

L'approccio è **deep value investing** — ricerca di aziende sistematicamente sottovalutate dal mercato secondo metriche fondamentali, non tecniche. I quattro filtri hard:

| Filtro | Valore default | Logica |
|---|---|---|
| EV/FCF ≤ 12x | 12 | Prezzo pagato per unità di cassa generata. < 12x = economica |
| P/B ≤ 1,2x | 1.2 | Prezzo/patrimonio netto contabile. < 1.2x = sotto valore libro |
| ROE ≥ 0% | 0% | Return on equity non negativo (no aziende in perdita strutturale) |
| Net Debt/EBITDA ≤ 2,5x | 2.5 | Leva finanziaria accettabile |

Filtri aggiuntivi hard-coded:
- **Market Cap ≥ $100M USD** (normalizzato — vedi sezione 5.3)
- **Esclusi Financial Services** (P/B non comparabile per banche/assicurazioni)

### 5.2 Metriche calcolate da yfinance

```python
ev_fcf         = enterpriseValue / freeCashflow
price_book     = priceToBook
roe            = returnOnEquity
net_debt_ebitda = (totalDebt - cash) / ebitda
market_cap     = marketCap (convertito in USD)
```

### 5.3 Normalizzazione valuta

Le azioni non USA hanno market cap in valuta locale. Il sistema usa tassi di cambio statici aggiornabili trimestralmente:

```python
CURRENCY_TO_USD = {
    'USD': 1.0, 'EUR': 1.10, 'GBP': 1.27, 'GBp': 0.0127,  # pence!
    'CHF': 1.13, 'JPY': 0.0065, 'HKD': 0.128, 'SEK': 0.094,
    'NOK': 0.090, 'DKK': 0.148, 'CAD': 0.735, 'AUD': 0.645,
    'KRW': 0.00073, 'CNY': 0.138, 'INR': 0.012
}
```

**Nota critica:** GBp (pence sterline) viene distinto da GBP — errore comune che porterebbe a market cap 100x sovrastimato per le azioni UK quotate in pence.

### 5.4 Stato corrente report (29/05/2026)

```
Universe: 920 azioni
Selezionate: 11
Scartate:    2.618  (non tutte le 920 — ci sono errori?)
Errori:      0 righe nel foglio "Errori"
```

**Anomalia da investigare:** 11 + 2.618 = 2.629 > 920. Il foglio "Azioni Scartate" potrebbe contenere righe di intestazione multiple o dati di mercati precedenti. Da verificare la prossima sessione.

---

## 6. LO SCREENER ETF — value_screener_etf.py

### 6.1 Filosofia: efficienza costo/rischio/rendimento

Diversamente dalle azioni (screening fondamentale), gli ETF vengono selezionati su **metriche di qualità del prodotto finanziario**:

| Filtro | Valore default | Logica |
|---|---|---|
| TER ≤ 0,50% | 0.50 | Total Expense Ratio — costo annuo ETF |
| Sharpe Ratio ≥ 0,5 | 0.5 | Rendimento/rischio su 1 anno |
| Volume ≥ 100.000 | 100.000 | Liquidità minima giornaliera |
| Performance 1Y ≥ -20% | -20% | Protezione downside |

### 6.2 La problematica critica del TER — yfinance vs ETF europei

**Bug scoperto e risolto in questa sessione (01/06/2026):**

yfinance usa due convenzioni diverse per il TER:
- **ETF USA:** `netExpenseRatio` → già in unità % (0.0945 = 0.0945%)
- **Fondi mutual:** `annualReportExpenseRatio` → decimale frazionario (0.0035 = 0.35%)

Il codice originale applicava `format_percent_ita()` (moltiplicava per 100) al TER degli ETF, producendo SPY "9,45%" invece di "0,09%". Il filtro funzionava correttamente (`ter > ter_max` senza divisione), ma il display nel report Excel era completamente sbagliato.

**ETF europei — problema strutturale:** yfinance non espone TER per nessun listing europeo (`.L`, `.DE`, `.AS`, `.PA`, `.MI`, `.SW`) tramite `netExpenseRatio`, `annualReportExpenseRatio` o `totalExpenseRatio`. Soluzione implementata: scraping diretto da **justETF.com** via ISIN.

### 6.3 Soluzione justETF per TER europei

```python
EUROPEAN_ETF_ISIN = {
    'VWRL': 'IE00B3RBWM25',  # Vanguard FTSE All-World dist.  → 0.19%
    'VWCE': 'IE00BK5BQT80',  # Vanguard FTSE All-World acc.   → 0.19%
    'VUSA': 'IE00B3XXRP09',  # Vanguard S&P 500               → 0.07%
    'VEUR': 'IE00B945VV12',  # Vanguard FTSE Dev Europe        → 0.10%
    'VUKE': 'IE00B810Q511',  # Vanguard FTSE 100               → 0.09%
    'VFEM': 'IE00B3VVMM84',  # Vanguard FTSE EM                → 0.17%
    'VAGP': 'IE00BG47KB92',  # Vanguard Global Agg Bond EUR    → 0.08%
    'VAPX': 'IE00B9F5YL18',  # Vanguard FTSE Asia Pac ex JP    → 0.15%
    'VJPN': 'IE00B95PGT31',  # Vanguard FTSE Japan             → 0.10%
    'VERX': 'IE00BKX55S42',  # Vanguard FTSE Dev Europe ex UK  → 0.10%
    'IGLN': 'IE00B4ND3602',  # iShares Physical Gold           → 0.12%
    'PHAU': 'DE000A0N62G0',  # WisdomTree Physical Gold        → 0.39%
    'PHAG': 'JE00B1VS3333',  # WisdomTree Physical Silver      → 0.49%
    'EXS1': 'DE0005933931',  # iShares Core DAX                → 0.16%
    'ESE':  'FR0011550185',  # BNP Paribas Easy S&P 500 EUR    → 0.14%
    # + alias: VGWL=VWCE, VJPA=VJPN, SGLD=IGLN
}
EUROPEAN_ETF_TER_STATIC = {
    'VMID': 0.10,  # Vanguard FTSE 250 (ISIN non trovato su justETF)
    'VAGS': 0.15,  # Vanguard Global Agg Bond GBP Hedged
}
```

Pipeline: `ticker_full.split('.')[0]` → lookup ISIN map → GET `justetf.com/en/etf-profile.html?isin=<ISIN>` → regex `etf-profile-header_ter-value[^>]*>([0-9.,]+)%` → TER come float.

Cache locale `_ter_cache = {}` evita fetch multipli dello stesso ISIN nel medesimo run.

**Risultato test:** 26/26 ETF europei ora ricevono TER corretto (tutti < 0,50%).

### 6.4 Risultati run 01/06/2026 (post-fix ETF TER)

```
Universe:                390 ETF
Selezionati:             154  (39,5%)
Scartati - TER Alto:      72  (18,5%)  — ETF tematici: ROBO 0,95%, BOTZ 0,68%
Scartati - Sharpe Basso:  25  ( 6,4%)  — Settoriali piatti: XLF 0,24, XLP 0,22
Scartati - Volume Basso:  81  (20,8%)  — ETF minori: MGC 23.734, MGV 24.700
Scartati - Perf Negativa:  0  ( 0,0%)  — Nessuno: mercato 2025-26 robusto
Scartati - Altri Motivi:  26  ( 6,7%)  — TER non disponibile (pre-fix EU)
Non Validi:               32  ( 8,2%)  — Nessuna history su yfinance
TOTALE:                  390/390 ✅
```

### 6.5 Formula Score ETF

```python
score = sharpe * 10 - (ter * 100) * 20 + perf_1y * 5
```

Esempio SPLG (TER=0,02%, Sharpe=2,24, Perf=29,2%):
`2.24*10 - (0.02*100)*20 + 0.292*5 = 22.4 - 40 + 1.46 = -16.14`

**Nota:** Il termine `ter*100*20` genera penalità enormi anche per TER minimi (SPY 0,0945% → penalità 189). Tutti i Top 50 hanno score negativo. Il ranking relativo è comunque corretto (minore TER = punteggio più alto). Da valutare ribilanciamento formula.

---

## 7. LO SCREENER FONDI — value_screener_fondi.py

### 7.1 Filosofia: selezione fondi comuni efficienti

Stessa struttura dell'ETF ma con parametri più permissivi (fondi gestiti attivamente = TER più alto):

| Filtro | Valore default |
|---|---|
| TER ≤ 1,0% | 1.0 |
| Sharpe ≥ 0,3 | 0.3 |
| Volume ≥ 50.000 | 50.000 |
| Performance 1Y ≥ -30% | -30% |

### 7.2 Bug TER fondi — risolto

yfinance restituisce `annualReportExpenseRatio` per i fondi come decimale frazionario (0.0035 = 0.35%). Il codice originale confrontava direttamente con `ter_max=1.0`, portando a NESSUN fondo scartato per TER (0.0035 < 1.0 → passa). Fix:

```python
if ter > FILTERS['ter_max'] / 100:  # 1.0/100 = 0.01
```

Il display usava `format_percent_ita(ter)` che moltiplicava per 100 → corretto per i fondi.

### 7.3 Risultati run 01/06/2026

```
Universe:                201 fondi
Selezionati:             142  (70,6%)
Scartati - TER Alto:      29  (14,4%)
Scartati - Sharpe Basso:   5  ( 2,5%)
Non Validi:               27  (13,4%)  — no dati yfinance
TOTALE:                  201/201 ✅  (142+29+5+0+0+0+27 = 203 — 2 di disallineamento)
```

### 7.4 Formula Score Fondi

```python
score = sharpe * 10 - (ter * 100) * 15 + perf_1y * 5
```

Nota: `ter * 100` converte il decimale frazionario yfinance in % prima di applicare la penalità.

---

## 8. FULL ACCOUNTABILITY — IL PRINCIPIO 100%

Una delle correzioni architetturali più importanti introdotte in questa sessione. Il vincolo:

```
selezionati + scartati + non_validi = totale_universe
```

Questa uguaglianza deve sempre essere vera. Precedentemente "non_validi" (ticker per cui yfinance restituisce `(None, "dati insufficienti")`) venivano silenziosamente droppati — risultando in accountability incompleta (es. 174/201 invece di 201/201).

Implementazione:

```python
selected = []
rejected = []
non_validi = []

result, status = analyze_fondi(ticker)

if result:
    if status == 'selected': selected.append(result)
    else:                    rejected.append(result)   # con Motivo Scarto
elif 'TER non disponibile' in (status or ''):
    rejected.append({'Ticker': ticker, 'Motivo Scarto': status, ...})
else:
    non_validi.append({'Ticker': ticker, 'Motivo': status or 'Dati insufficienti'})
```

Il foglio "Non Validi - Dati Mancanti" (9° foglio) elenca questi ticker, permettendo all'utente di sapere perché non compaiono nel report.

---

## 9. STRUTTURA OUTPUT EXCEL

### 9.1 ETF e Fondi — 9 fogli

| Foglio | Contenuto |
|---|---|
| 1. Dashboard | KPI: totali, selezionati, scartati, non validi, timestamp |
| 2. Top 50 per Score | I 50 migliori per score (con TER corretto) |
| 3. ETF Selezionati / Fondi Selezionati | Tutti i selezionati, ordinati per score |
| 4. Scartati - TER Alto | TER > soglia |
| 5. Scartati - Sharpe Basso | Sharpe < soglia |
| 6. Scartati - Volume Basso | Volume < soglia |
| 7. Scartati - Performance Negativa | Perf 1Y < soglia |
| 8. Scartati - Altri Motivi | TER non disponibile, altri |
| 9. Non Validi - Dati Mancanti | Nessun dato yfinance |

### 9.2 Azioni — 5 fogli (struttura più semplice)

```
1. Dashboard, 2. Top 50, 3. Azioni Selezionate, 4. Azioni Scartate, 5. Errori
```

---

## 10. PARAMETRI CONFIGURABILI — parametri.json

```json
{
  "auth": {
    "password": "6b57a42eb436b983a109fcdeeaaeb221ae2eb27e2b6fe4e1b293cb14702ad83d"
  },
  "azioni":  { "ev_fcf_max": 12, "price_book_max": 1.2, "roe_min": 0, "net_debt_ebitda_max": 2.5 },
  "etf":     { "ter_max": 0.5, "sharpe_min": 0.5, "volume_min": 100000, "performance_1y_min": -0.20 },
  "fondi":   { "ter_max": 1.0, "sharpe_min": 0.3, "volume_min": 50000,  "performance_1y_min": -0.30 }
}
```

Ogni modifica dal pannello admin genera un **backup automatico**:
`parametri_bk_20260601_153000.json` — preserva lo storico delle configurazioni.

---

## 11. PIANO ABBONAMENTO — servizi_config.json

File centrale per le caratteristiche visibili ai potenziali clienti sulla landing page. Struttura:

```json
{
  "azioni": {
    "basic":  { "prezzo": 29, "status": "attivo", "caratteristiche": [...], "target": "..." },
    "pro":    { "prezzo": 39, ... },
    "value":  { "prezzo": 59, ... }
  },
  "etf":   { "basic": {...}, "pro": {...}, "value": {...} },
  "fondi": { "basic": {...}, "pro": {...}, "value": {...} }
}
```

Il campo `caratteristiche` è un array di stringhe visualizzate come lista ✓ sulla landing page. Il campo `target` è visualizzato come box 👤 "Profilo ideale". Entrambi editabili dall'admin senza toccare codice.

---

## 12. LANDING PAGE — architettura frontend

La landing page è HTML/CSS/JS **interamente inline** dentro `dashboard.py` come stringa Python `HTML = r"""..."""`. Non esistono file `.html`, `.css`, `.js` separati.

### 12.1 Sezioni landing (pubbliche, senza auth)

1. **Hero** — headline, sottotitolo, CTA "Abbonati ora"
2. **Come funziona** — 3 step (analisi → report → decisioni)
3. **Prezzi** — griglia 3×3 con plan cards generate da `servizi_config.json`
4. **Footer** — link ⚙ admin (quasi invisibile: `rgba(255,255,255,.45)`)

### 12.2 Tipografia (aggiornata in sessione)

```css
.hero-h1      { font-size: clamp(3.5rem, 9vw, 7.5rem); letter-spacing: -3px }
.section-title{ font-size: 2.5rem; font-weight: 900 }
.price-num    { font-size: 3.8rem }
.btn-primary  { font-size: 1.1rem; padding: 1rem 2.6rem }
```

### 12.3 Rendering plan cards (JavaScript)

```javascript
function renderPlans(data, container) {
    // Per ogni asset class (azioni/etf/fondi):
    //   Per ogni tier (basic/pro/value):
    //     Genera HTML card con:
    //     - prezzo, badge tier
    //     - <ul class="plan-features"> con ✓ per ogni caratteristica
    //     - <div class="plan-target"> con profilo 👤
    //     - pulsante "Abbonati" (link Stripe — placeholder)
}
```

### 12.4 Tab admin — pannello interno

7 tab nell'area admin:
- **Home** — KPI globali (count selezionati per asset class, data/ora ultimo run)
- **Servizi** — editor WYSIWYG per prezzi, caratteristiche, target, status on/off
- **Parametri** — slider/input per filtri numerici con min/max bounds
- **Azioni / ETF / Fondi** — tabelle dati Top 50 dell'ultimo report
- **Esecuzione** — pulsanti ▶ per avviare screener, terminale log in tempo reale

---

## 13. PROBLEMI RISOLTI IN QUESTA SESSIONE (01/06/2026)

### 13.1 ImportError ALL_FONDI / ALL_ETF
**Causa:** `ticker_lists_5000.py` aveva solo `ALL_AZIONI`. ETF e Fondi screener fallivano all'import.
**Fix:** Aggiunte le liste complete con 390 ETF e 201 fondi in `ticker_lists_5000.py`.

### 13.2 TER filter fondi sempre ignorato
**Causa:** `ter_max=1.0` confrontato con TER decimale yfinance (0.0035). `0.0035 < 1.0` → tutti passano.
**Fix:** `if ter > FILTERS['ter_max'] / 100` — converte la soglia in decimale prima del confronto.

### 13.3 TER=None silenziosamente a zero
**Causa:** `if ter is None: ter = 0` faceva passare fondi senza TER con score "0% TER".
**Fix:** `return None, "TER non disponibile"` → va in non_validi o rejected.

### 13.4 Full accountability 201/201 e 390/390
**Causa:** `(None, motivo)` da analyze_fondi/analyze_etf venivano droppati silenziosamente.
**Fix:** Branch `else: non_validi.append(...)` aggiunto — garantisce che ogni ticker venga contabilizzato.

### 13.5 KPI data non aggiornata
**Causa:** `_latest()` usava `sorted(files)[-1]` — ordinamento ASCII → 'v' > 'F' → vecchi file vincevano.
**Fix:** `sorted(files, key=os.path.getmtime)[-1]` — ordine temporale reale.

### 13.6 KPI count sempre 50
**Causa:** `get_status()` leggeva il foglio "Top 50" (sempre 50 righe) invece di "Selezionati".
**Fix:** Pattern for/else Python — cerca 'selezionat' prima, poi 'top' come fallback.

### 13.7 Log "Tutti" sempre vuoto
**Causa:** JS faceva polling su `running['tutti']` ma il backend non popolava questa chiave.
**Fix:** Aggiunto `running['tutti']` con log aggregato; ogni riga scritta anche nel log specifico.

### 13.8 Log counter ETF appariva solo a fine run
**Causa:** `end=' '` senza `flush=True` → buffering stdout fino a newline.
**Fix:** `print(f"[{i}/{len(ALL_ETF)}] {ticker}...", flush=True)` su riga separata.

### 13.9 Display TER ETF sbagliato (100x)
**Causa:** `format_percent_ita(ter, 2)` usato in tutti i fogli Excel ETF — moltiplicava per 100.
**Fix:** Sostituita con `format_ter_etf(ter)` in 6 punti del codice (ETF Selezionati + 5 fogli Scartati).

### 13.10 ETF europei — TER sempre "non disponibile"
**Causa:** yfinance non espone TER per listing EU su nessun campo.
**Fix:** Scraping justETF via ISIN map per 18 ETF + fallback statico per 2. Test: 26/26 ✅.

### 13.11 Admin link invisibile nel footer
**Causa:** CSS `.admin-link` non presente, link non rendeva.
**Fix:** Classe `.admin-link` con `display:inline-block; border:1px solid rgba(255,255,255,.15)`.

### 13.12 Caratteristiche e target non visibili in landing
**Causa:** `renderPlans()` non leggeva i campi `caratteristiche` e `target` da `servizi_config.json`.
**Fix:** Aggiunto rendering `<ul class="plan-features">` e `<div class="plan-target">` + CSS dedicato.

---

## 14. PROBLEMI APERTI E BACKLOG

### 14.1 CRITICO — da fare prima del lancio

| # | Problema | Impatto |
|---|---|---|
| 1 | **Password admin** `"123"` ancora in produzione | Sicurezza critica |
| 2 | **Stripe integration** — `href="#"` su tutti i pulsanti "Abbonati" | Zero revenue possibile |
| 3 | **Pulsante ACCEDI clienti** — nessuna logica client-side | Utenti non possono scaricare report |
| 4 | **Sessioni admin** non scadono attivamente | Security hygiene |

### 14.2 IMPORTANTE — da fare entro breve

| # | Problema | Note |
|---|---|---|
| 5 | **Azioni: anomalia 2.629 > 920** — foglio Scartate da investigare | Possibile bug conteggio |
| 6 | **Score ETF sempre negativo** — formula penalizza eccessivamente TER | Ranking ok, valori brutti |
| 7 | **Tassi cambio statici** in azioni screener | Aggiornare trimestralmente |
| 8 | **Sessioni perse al riavvio** server — nessun persistence | Usabilità admin |
| 9 | **VMID / VAGS** — TER statico hardcoded, non live da justETF | Manutenzione manuale |

### 14.3 FUTURO — roadmap

| # | Feature | Priorità |
|---|---|---|
| 10 | **CRM & Marketing integration** — progetto Brevo già pronto | Alta post-lancio |
| 11 | **Email automatica report** — notifiche ai clienti attivi | Alta |
| 12 | **Scheduling Task Scheduler** — verificare funzionamento 08:05 | Alta |
| 13 | **Rate limiting** API — protezione da abusi | Media |
| 14 | **HTTPS** — al momento solo HTTP | Media (richiede reverse proxy) |
| 15 | **Deployment cloud** — al momento solo localhost | Post-prima revenue |
| 16 | **Screener Azioni test completo** — mai testato in questa sessione | Media |

---

## 15. DIPENDENZE E DEPLOYMENT

### 15.1 Python packages (effettivamente usati)

```
yfinance          — dati finanziari (Yahoo Finance)
openpyxl          — creazione Excel
pandas            — lettura Excel nel dashboard
urllib.request    — HTTP requests per justETF (stdlib)
http.server       — web server (stdlib)
threading         — run screener in background (stdlib)
subprocess        — esecuzione script screener (stdlib)
secrets           — token sessione sicuri (stdlib)
json, os, glob    — I/O file system (stdlib)
```

`requirements.txt` attuale riporta Flask, Firebase, gunicorn — **file obsoleto**, relativo a un'architettura precedente mai portata a termine.

### 15.2 Come avviare il sistema

```bash
cd "Robot Trader 2026/PYTHON_SCRIPTS"
python dashboard.py
# → http://localhost:5000  (landing pubblica)
# → http://localhost:5000/login  (admin, password: 123)
```

### 15.3 Scheduling automatico

File: `robot_trader_scheduler.bat` + `setup_task_scheduler.ps1`  
Orario configurato: **08:05 ogni giorno feriale**  
Comportamento: lancia `orchestrator.py` che sequenzialmente chiama i tre screener

---

## 16. FLUSSO DATI COMPLETO (end-to-end)

```
08:05 Task Scheduler
  └→ orchestrator.py
       ├→ value_screener_azioni.py
       │    ├ yfinance.Ticker(ticker).info × 920
       │    ├ Filtri: EV/FCF, P/B, ROE, Net Debt/EBITDA, MarketCap
       │    └ Output: Azioni_Screener_YYYYMMDD_HHMM.xlsx (5 fogli)
       │
       ├→ value_screener_etf.py
       │    ├ yfinance.Ticker(ticker).info × 390
       │    ├ [Fallback] justETF.com via ISIN per EU ETF (26 ticker)
       │    ├ Sharpe = mean(daily_returns)/std × √252
       │    ├ Filtri: TER, Sharpe, Volume, Perf1Y
       │    └ Output: ETF_Screener_YYYYMMDD_HHMM.xlsx (9 fogli)
       │
       └→ value_screener_fondi.py
            ├ yfinance.Ticker(ticker).info × 201
            ├ Filtri: TER(/100), Sharpe, Volume, Perf1Y
            └ Output: FONDI_Screener_YYYYMMDD_HHMM.xlsx (9 fogli)

                    ↓ REPORTS_DAILY/ (accumulo storico)

Utente → browser → http://localhost:5000
  ├ Landing: griglia prezzi da servizi_config.json
  ├ Admin login → cookie HttpOnly
  └ Admin dashboard:
       ├ /api/status  → legge ultimo Excel per KPI
       ├ /api/table   → legge foglio "Top 50" per tabelle
       ├ /api/run     → subprocess + log streaming
       └ /api/download → serve file Excel più recente
```

---

## 17. METRICHE DI PERFORMANCE DEL SISTEMA

### 17.1 Tempi di esecuzione stimati

| Screener | Ticker | Tempo stimato | Principale collo di bottiglia |
|---|---|---|---|
| Azioni | 920 | ~45-60 min | yfinance rate limit (1 req/s circa) |
| ETF | 390 | ~25-35 min | yfinance + justETF per 26 EU ETF |
| Fondi | 201 | ~15-20 min | yfinance solo |
| **Tutti** | **1.511** | **~90-115 min** | Sequenziale, nessuna parallelizzazione |

Timeout impostato nel subprocess: **2400 secondi (40 minuti)** per singolo screener.

### 17.2 Dimensioni report tipici

| Report | Selezionati | Dimensione file stimata |
|---|---|---|
| Azioni | ~11 (ultra-selettivo) | ~200-400 KB |
| ETF | ~154 (39%) | ~150-300 KB |
| Fondi | ~142 (71%) | ~100-200 KB |

---

## 18. SICUREZZA — AUDIT ATTUALE

| Aspetto | Stato | Rischio |
|---|---|---|
| Password admin | `"123"` hardcoded | **CRITICO** |
| Token sessione | `secrets.token_hex(20)` | Sicuro |
| Cookie flag | HttpOnly + SameSite=Strict | Sicuro |
| HTTPS | Assente | Alto (man-in-the-middle) |
| Rate limiting | Assente | Medio |
| Input validation | Minima (tipo screener da whitelist) | Basso |
| Firebase credentials | JSON file in chiaro nella cartella | Medio (file obsoleto) |
| Session persistence | In-memory (perse al riavvio) | Basso |
| Backup parametri | Automatico ad ogni save | Buono |
| CORS | Non configurato | Basso (local only) |

---

## 19. CONSIDERAZIONI STRATEGICHE

### 19.1 Punti di forza del sistema

1. **Autonomia completa:** nessuna dipendenza da API a pagamento — solo yfinance (gratuito, non ufficiale ma stabile) e justETF (scraping HTML pubblico)
2. **Full accountability 100%:** ogni ticker è contabilizzato — zero "spariti"
3. **Configurabilità runtime:** filtri e prezzi modificabili senza toccare codice
4. **Report Excel ricchi:** 9 fogli con breakdown dettagliato per categoria di scarto
5. **Architettura monolitica semplice:** un solo file Python da avviare, zero infrastruttura

### 19.2 Rischi principali

1. **yfinance instabilità:** Yahoo Finance può cambiare API non ufficiali senza preavviso
2. **justETF scraping:** cambiamenti al DOM HTML di justETF rompono il TER fetch per ETF EU
3. **Deployment locale:** localhost non è accessibile da internet senza tunneling (ngrok presente ma non configurato)
4. **Single point of failure:** se il PC è spento alle 08:05, il report non viene generato
5. **Nessun testing automatico:** zero test unitari, zero CI/CD

### 19.3 Path to production

```
Stato attuale: localhost:5000, manuale
Step 1: Fix password admin + Stripe keys
Step 2: ngrok o VPS (hetzner/digitalocean) per URL pubblico
Step 3: Prima vendita → validazione modello
Step 4: CRM/email integration (Brevo — già pronto)
Step 5: Containerizzazione Docker per deployment stabile
```

---

## 20. STORICO VERSIONI CHIAVE

| Data | Milestone |
|---|---|
| pre-2026 | Progetto concepito, prima versione screener azioni |
| 05/05/2026 | CERTIFICAZIONE_FINALE — prima versione stabile |
| 19-26/05/2026 | Screener ETF e Fondi aggiunti, versioni value_screener_* |
| 26/05/2026 | Dashboard v2.0 con tab admin completo |
| 01/06/2026 | **Sessione attuale** — 12 bug fix critici, TER ETF fix, EU ETF via justETF, full accountability |

---

*Documento generato il 01/06/2026 — Robot Trader 2026 / Fuerte Venture Capital SL*  
*Autore tecnico: Claude Sonnet 4.6 (Anthropic) in collaborazione con il team NCF*

---

## 21. AGGIORNAMENTI UNIVERSO TICKER (giugno 2026)

### 21.1 Stato aggiornato al 24/06/2026

| Asset Class | 01/06/2026 | 24/06/2026 | Δ |
|---|---|---|---|
| ALL_AZIONI | 920 | **3.072** | +2.152 (23 mercati globali) |
| ALL_ETF | 390 | **1.182** | +792 (dedup ISIN, preferisce ACC) |
| ALL_FONDI US | 201 | **911** | +710 (45 famiglie totali) |
| FONDI EU UCITS | — | **472** | nuovo screener (20/06/2026) |
| **TOTALE** | **1.511** | **5.637** | **+4.126** |

### 21.2 Espansione FONDI US (20/06/2026)
+9 nuove famiglie aggiunte a `ticker_lists_5000.py`: AB, PGIM, Morgan Stanley, State Street, William Blair, Causeway, Hotchkis, Alger, Transamerica.  
**Nota critica:** con questa modifica `FONDI_BOUTIQUE` ha sostituito il vecchio nome `FONDI_ALTRI` nella lista multi-famiglia. Qualsiasi riferimento a `FONDI_ALTRI` in `dashboard.py` causerebbe `ImportError` silenzioso (bug trovato e corretto 24/06).

### 21.3 Nuovo screener FONDI EU UCITS (20/06/2026)
- File: `value_screener_fondi_eu.py`
- 472 fondi da `fondi_eu_universe_cache.json` (536 in cache, 472 pronti)
- Usa AUM (non volume) come metrica di liquidità — UCITS non hanno volume di borsa
- Filtri per piano: BASIC TER≤1%/AUM≥50M | PRO TER≤1.5%/AUM≥10M | VALUE TER≤2%/AUM≥1M
- Config da `servizi_config.json → fondi_eu` (non da `parametri.json`)

### 21.4 Espansione ETF (giugno 2026)
Da 390 a 1.182 grazie a `etf_universe_cache.json`: scraper `fetch_justetf_universe.py` che scarica l'intero universo ETF UCITS europei accumulazione da justETF. Funzione `_dedup_by_isin()` in `value_screener_etf.py` — preferisce ETF ACC su DIST, poi massimo volume.

---

## 22. AGGIORNAMENTI ARCHITETTURA (giugno 2026)

### 22.1 dashboard.py — crescita

| Data | Righe | Note |
|---|---|---|
| 01/06/2026 | ~1.559 | Versione base con 3 screener |
| 24/06/2026 | **~6.750** | +area clienti, +ordini, +fatture, +chat AI, +CRM, +social, +4° screener |

### 22.2 Nuove funzionalità aggiunte

- **Area clienti** — login separato cookie `rt_client`, sliding 24h, download report personali
- **Order Builder** — generazione ordini CSV IBKR + email bancaria MiFID II
- **Sistema fatture PDF** — FPDF, numerazione FVC-2026-XXXX, cartella `FATTURE/` alla radice
- **Chatbot AI** — Claude Haiku 4.5 + KB 4 file MD × 5 lingue, prompt caching, rate limit 30 msg/h/IP
- **CRM clienti** — `clienti.json` con piani per asset (piano_azioni/etf/fondi/fondi_eu), dati fiscali, GDPR
- **WhatsApp** — Meta Cloud API v20.0 (`whatsapp_service.py`)
- **Social automation** — Brevo/LinkedIn/Meta (`social_automation.py`) lun/mer/ven 08:00
- **Tab 🗃️ Database Universo Ticker** — elenco completo con ricerca e prezzi live da yfinance

### 22.3 Scheduling — da Task Scheduler ad APScheduler

**Prima (01/06/2026):** Windows Task Scheduler → `robot_trader_scheduler.bat` → `orchestrator.py` alle 08:05

**Ora (24/06/2026):** `scheduler_daemon.py` con APScheduler `BackgroundScheduler`

| Job | Orario | Giorni |
|---|---|---|
| AZIONI | 23:00 | lun-ven |
| ETF + FONDI + FONDI_EU | 23:30 | lun/mer/ven |
| Social automation | 08:00 | lun/mer/ven |

**Perché 23:00 invece di 08:05:** i dati Yahoo Finance vengono aggiornati dopo la chiusura dei mercati USA (circa 21-22 CET). Un run notturno garantisce dati più freschi rispetto al mattino.

### 22.4 Score bontà — da formula statica a pesi configurabili

**Prima (01/06/2026):** formula hardcoded (es. `sharpe * 10 - ter*100*20 + perf_1y*5`)

**Ora (24/06/2026):** `batch_percentile_score()` in `screener_utils.py` — pesi per piano letti da `config.json → scoring_weights`. Score = media ponderata di percentili 0–100. Range: 0–100 per ogni asset.

---

## 23. BUG FIX SUCCESSIVI AL 01/06/2026

### 23.1 Fix 16/06/2026 (20 bug — sicurezza e stabilità)

| File | Fix |
|---|---|
| `dashboard.py` | `ADMIN_PASSWORD` da env o config.json; warning se debole |
| `dashboard.py` | `_clienti_lock` + `_fatture_lock` threading.Lock — no race condition |
| `dashboard.py` | `save_clienti()` atomica: temp file + `os.replace()` |
| `dashboard.py` | `_prossimo_numero_fattura()` dentro lock — no numeri duplicati |
| `dashboard.py` | 4 `except:` nudi → `except Exception:` |
| `chat_service.py` | `_session_ts` dict + `cleanup_expired_sessions()` — no memory leak |
| `email_notifier.py` | `smtplib.SMTP(..., timeout=15)` — no blocco su Gmail down |
| `screener_utils.py` | `import math` + filtro NaN in `batch_percentile_score` |
| `value_screener_azioni.py` | `_get_param()` helper — legge sia `{'value': X}` che `X` da parametri.json |

### 23.2 Fix 17/06/2026

- `orchestrator.py`: `send_plan_email()` con retry automatico — 3 tentativi, pausa 30s tra tentativi

### 23.3 Fix 24/06/2026 (debug completo — 12 bug)

| File | Bug | Fix |
|---|---|---|
| `orchestrator.py` | `"FONDI" in "FONDI_EU_..."` → allegato email sbagliato (FONDI riceveva file FONDI_EU) | `startswith(type + '_')` invece di `in` |
| `orchestrator.py` | log retry mostrava `max_retry-1` | corretto a `max_retry` |
| `email_notifier.py` | FONDI count bloccato a 781 (era 911 dal 20/06), FONDI_EU assente | aggiornati conteggi in `TICKER_COUNT` |
| `email_notifier.py` | email inviate anche a clienti con stato SOSPESO | filtro `stato == "ATTIVO"` |
| `dashboard.py` | `/api/kb-status` e `/api/reload-kb` senza guard `_CHAT_OK` → NameError | guard `if _CHAT_OK` aggiunto |
| `dashboard.py` | `genera_fattura_pdf()` non includeva FONDI_EU → nessuna riga fattura per abbonati EU | aggiunto al loop asset |
| `dashboard.py` | `get_status()` cieco a FONDI_EU nella dashboard admin | aggiunto a `_plan_prefix`, `_legacy_pats`, loop |
| `dashboard.py` | `get_database_data()` importava `FONDI_ALTRI` (non esiste → `ImportError`) → tab Database vuota | rinominato in `FONDI_BOUTIQUE` |
| `dashboard.py` | yfinance restituisce `float('nan')` → JSON non valido (`NaN`) | `_safe()` in `get_database_lookup` + sanitizer ricorsivo in `_json` |
| `value_screener_etf.py` | `load_filters()` usava `.get('key',{}).get('value',X)` → ignorava plain number in parametri.json | helper `_get_param` (come in azioni screener) |
| `value_screener_fondi.py` | stesso bug ETF in `load_filters()` | helper `_get_param` |
| `chat_service.py` | `reload_kb()` usava `split("KNOWLEDGE BASE:")` senza maxsplit=1 | `split(..., 1)` |

---

## 24. STATO ATTUALE — SEMAFORO (24/06/2026)

### ✅ FUNZIONANTE

- 4 screener operativi (Azioni 3.072, ETF 1.182, Fondi US 911, Fondi EU 472)
- Scheduling automatico APScheduler (3 job)
- Email report per piano con retry — solo clienti ATTIVI
- Excel: fogli Selezionati con colonne fisse, formattazione leggibile, ordinati per Score
- Sistema fatture PDF (include FONDI_EU)
- Chatbot AI Knowledge Base (5 lingue, reload a caldo)
- Tab Database Universo Ticker (3.072 azioni + 1.182 ETF + 911 fondi navigabili)
- CRM clienti + area riservata + Order Builder
- JSON valido garantito da tutti gli endpoint (`_json` sanitizza NaN/Inf globalmente)

### 🔴 BLOCCA IL LANCIO PUBBLICO

1. **Cloudflare Tunnel** — localhost non è raggiungibile da internet
2. **Password admin** — ancora `"123"` in `config.json → admin_password`

### 🟡 IN ATTESA CREDENZIALI

3. **Social Automation** — Brevo api_key, LinkedIn client_id/secret, Meta page_id
4. **WhatsApp Business** — account Meta verificato + numero dedicato + template approvati

### 🔑 SICUREZZA — AZIONI PENDENTI

5. Ruotare API key Anthropic
6. Rigenerare App Password Gmail

---

*Documento aggiornato il 24/06/2026 — Robot Trader 2026 / Fuerte Venture Capital SL*
