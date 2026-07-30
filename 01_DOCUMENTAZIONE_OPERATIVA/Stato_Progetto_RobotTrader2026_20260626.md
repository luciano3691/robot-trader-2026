# Stato Progetto — Robot Trader 2026

**Fuerte Venture Capital SL** · CIF B23881691 · marketing@fuerteventurecapital.com  
**Ultimo aggiornamento:** 26/06/2026  
**Path progetto:** `C:\Users\lucia\Desktop\Robot Trader 2026\PYTHON_SCRIPTS\`

---

## Stack Tecnico

- **Server:** `http.server.HTTPServer` stdlib Python — ZERO framework web
- **Dati:** `yfinance` + scraping justETF per ETF EU + Yahoo Finance Search API per Fondi EU
- **Output:** `openpyxl` → Excel multi-sheet, `pandas` per lettura dashboard
- **Auth admin:** cookie `rt_admin=secrets.token_hex(20)`, in-memory dict, timeout **8 ore fisso**
- **Auth cliente:** cookie `rt_client`, dict `CLIENT_SESSIONS`, **sliding 24 ore**
- **Email:** Gmail SMTP (smtplib stdlib) — `newcapitalfuerte@gmail.com` — credenziali in `config.json → email{}`
- **Scheduling:** `scheduler_daemon.py` — 3 job separati (AZIONI 23:00 / ETF+FONDI+EU 23:30 / social 08:00)
- **Fatture:** FPDF, cartella `FATTURE/` alla radice del progetto, IBAN CaixaBank ES83 2100 1513 7202 0070 3406
- **Chatbot:** Claude Haiku 4.5 + KB 4 file MD, prompt caching, rate limit 30 msg/h per IP

---

## File Principali (PYTHON_SCRIPTS/)

| File | Funzione |
|---|---|
| `dashboard.py` | Server HTTP unico — admin console + landing page + area clienti + Order Builder |
| `orchestrator.py` | Lancia screener selezionati + email per piano. Args: `AZIONI` / `ETF` / `FONDI` / `FONDI_EU` |
| `scheduler_daemon.py` | APScheduler — 3 job: AZIONI 23:00 lun-ven / ETF+FONDI+EU 23:30 lun/mer/ven / social 08:00 |
| `value_screener_azioni.py` | Screener azioni: 2.625 ticker, 23 mercati, output 3 Excel (BASIC/PRO/VALUE) |
| `value_screener_etf.py` | Screener ETF: universo espanso con JustETF cache (~4.245 ticker), output 3 Excel |
| `value_screener_fondi.py` | Screener fondi US: 886 fondi, 45+ famiglie, output 3 Excel |
| `value_screener_fondi_eu.py` | Screener fondi UCITS EU: 493 fondi, legge cache, output 3 Excel |
| `fetch_justetf_universe.py` | Scraper JustETF sitemap → `etf_universe_cache.json` (4630 ISIN, 3143 con ticker YF) |
| `fetch_fondi_eu_universe.py` | Scraper 2 fasi → `fondi_eu_universe_cache.json` (536 voci, 493 con ticker YF) |
| `screener_utils.py` | Score bontà percentile — `batch_percentile_score()` condiviso tra tutti gli screener |
| `ticker_lists_5000.py` | Universo ticker: ALL_AZIONI 2.625 / ALL_ETF 1.174 / ALL_FONDI 886 + tutte le subliste |
| `email_notifier.py` | `python email_notifier.py TIPO PIANO FILENAME` — invia a ATTIVI e TESTER con piano |
| `order_builder.py` | Order Builder — email bancaria MiFID II, CSV IBKR/Generico, prezzi live |
| `chat_service.py` | Chatbot AI — Claude Haiku 4.5 + KB 4 file, rate limit 30 msg/h per IP |
| `whatsapp_service.py` | Notifiche WhatsApp via Meta Cloud API |
| `social_automation.py` | Orchestratore social — Brevo/LinkedIn/Meta — lun/mer/ven |
| `clienti.json` | Database clienti: piano_azioni/etf/fondi, dati_fiscali, numero_fattura, gdpr |
| `config.json` | Config globale: SMTP, social, whatsapp, scoring_weights, fattura (IBAN), base_url |
| `fatture_counter.json` | `{"ultimo": 18}` — contatore progressivo numeri fattura |
| `etf_universe_cache.json` | Cache JustETF: 4630 ISIN, 3143 con preferred_ticker YF, 1487 solo ISIN puri |
| `fondi_eu_universe_cache.json` | Cache fondi UCITS EU: 536 voci, 493 con yahoo_ticker, 43 ISIN puri |
| `robot_trader_scheduler.bat` | BAT per Windows Task Scheduler — ora salva log in `logs/robot_trader_YYYYMMDD_HHMM.log` |

---

## Cartelle Dati (radice progetto — NON dentro PYTHON_SCRIPTS)

```
Robot Trader 2026/
  FATTURE/          → FVC-2026-0001...0018.pdf — generate automaticamente
  REPORTS_DAILY/    → Azioni/ETF/FONDI/FONDI_EU_Screener_PIANO_YYYYMMDD_HHMMSS.xlsx
  LOGS/
  BACKUPS/
  PYTHON_SCRIPTS/   → codice + config + clienti.json
                      logs/ → log schedulatore notturno
  01_DOCUMENTAZIONE_OPERATIVA/ → documentazione tecnica
```

---

## Universo Strumenti (aggiornato 26/06/2026)

### Conteggi Screener (ticker con dati Yahoo Finance)

| Asset | Count | Fonte dati | Note |
|---|---|---|---|
| ALL_AZIONI | **2.625** | yfinance | 23 mercati — 452 ticker morti rimossi il 25/06 |
| ETF (screener) | **~4.245** | yfinance + justETF | ALL_ETF (1.174) ∪ JustETF preferred_ticker (3.143, dedup) |
| ALL_FONDI US | **886** | yfinance | 45+ famiglie — +9 aggiunte 20/06 |
| FONDI EU UCITS | **493** | yfinance + cache | Cache `fondi_eu_universe_cache.json` |
| **TOTALE screener** | **~4.248** | | Solo ticker fetchabili da yfinance |

### Conteggi Tab Database (tutto incluso)

| Asset | Count | Di cui ISIN puri | Note |
|---|---|---|---|
| Azioni | **2.625** | 0 | Solo ticker standard |
| ETF | **5.732** | 1.487 | ALL_ETF + JustETF cache completa |
| Fondi | **1.422** | 43 | ALL_FONDI US + cache EU completa |
| **TOTALE Database** | **9.779** | **1.530** | 1530 ISIN puri: link JustETF, no dati live |

**Comportamento ticker nel Database:**

| Tipo | Esempio | Bottone | Dati live | Link |
|---|---|---|---|---|
| Ticker normale | AAPL, VWCE.DE, VFIAX | 🟠 Arancione | ✅ Clicca per caricare | Yahoo Finance |
| Ticker 0P (Morningstar/Frankfurt) | 0P0000OMVZ.F | 🟠 Arancione | ✅ Clicca per caricare | Yahoo Finance |
| ISIN puro (no ticker YF) | CH0008899764 | 🟢 Verde | ❌ Non disponibile | JustETF |

---

## Screener Attivi (4 totali)

| Script | Asset | Metrica size | Filtri principali | Output |
|---|---|---|---|---|
| `value_screener_azioni.py` | Azioni | Volume | EV/FCF, P/B, ROE, ND/EBITDA | 3 Excel BASIC/PRO/VALUE |
| `value_screener_etf.py` | ETF EU | Volume | TER, Sharpe, perf 1Y, età | 3 Excel BASIC/PRO/VALUE |
| `value_screener_fondi.py` | Fondi US | Volume | TER, Sharpe, perf 1Y | 3 Excel BASIC/PRO/VALUE |
| `value_screener_fondi_eu.py` | Fondi EU | AUM | TER, Sharpe, AUM, perf 1Y | 3 Excel BASIC/PRO/VALUE |

### Soglie filtri per piano

**AZIONI**

| Piano | Universe | EV/FCF | P/B | ROE | ND/EBITDA | Top N |
|---|---|---|---|---|---|---|
| BASIC | Blue chip (~702) | ≤18x | ≤3x | ≥0% | ≤4x | 20 |
| PRO | Universo 2.625 | ≤15x | ≤2x | ≥1% | ≤3x | 50 |
| VALUE | Universo 2.625 | ≤12x | ≤1x | ≥2% | ≤2x | 50 |

**ETF**

| Piano | TER max | Sharpe min | Volume min | Perf 1Y min | Età min | Top N |
|---|---|---|---|---|---|---|
| BASIC | 0.50% | 0.3 | 100k | +5% | 5 anni | 20 |
| PRO | 0.35% | 0.4 | 100k | +7% | 3 anni | 50 |
| VALUE | 0.20% | 0.5 | 100k | +10% | 2 anni | 50 |

**FONDI US**

| Piano | TER max | Sharpe min | Volume min | Perf 1Y min | Top N |
|---|---|---|---|---|---|
| BASIC | 2.0% | 0.1 | 50k | +5% | 20 |
| PRO | 1.5% | 0.2 | 50k | +7% | 50 |
| VALUE | 1.0% | 0.3 | 50k | +10% | 50 |

**FONDI EU UCITS**

| Piano | TER max | AUM min | Sharpe min | Perf 1Y min | Top N |
|---|---|---|---|---|---|
| BASIC | 1.0% | 50M | 0.1 | +5% | 20 |
| PRO | 1.5% | 10M | 0.0 | 0% | 50 |
| VALUE | 2.0% | 1M | -0.5 | -10% | 50 |

---

## Struttura Excel Report

```
REPORTS_DAILY/
  Azioni_Screener_BASIC_YYYYMMDD_HHMMSS.xlsx
  Azioni_Screener_PRO_YYYYMMDD_HHMMSS.xlsx
  Azioni_Screener_VALUE_YYYYMMDD_HHMMSS.xlsx
  ETF_Screener_BASIC_YYYYMMDD_HHMMSS.xlsx   (x3)
  FONDI_Screener_BASIC_YYYYMMDD_HHMMSS.xlsx  (x3)
  FONDI_EU_Screener_BASIC_YYYYMMDD_HHMMSS.xlsx  (x3)
```

**Fogli in ogni Excel:**

| # | Foglio | Contenuto | Inviato ai clienti? |
|---|---|---|---|
| 0 | 📖 Legenda | Guida metriche e Score (solo AZIONI) | ✅ Sì |
| 1 | Dashboard | Filtri, statistiche, breakdown mercato, Top 5 | ✅ Sì |
| 2 | Top N per Score | Migliori N ordinati per Score | ✅ Sì |
| 3 | Selezionati | Tutti i selezionati — colonne fisse | ✅ Sì |
| 4+ | Scartati per motivo | Archivio interno | ❌ Rimosso prima dell'invio |
| — | Non Validi / Errori | Archivio interno | ❌ Rimosso prima dell'invio |

**Colonne fisse foglio Selezionati:**

*AZIONI (30):* `Ticker · Nome · Valuta · Settore · Industry · Mercato · Indice · Market Cap · P/B · ROE · EV/EBITDA · FCF · EV · Total Debt · Total Cash · EBITDA · Div Yield · Analyst Coverage · EV/FCF · Net Debt · ND/EBITDA · Prezzo · Var_1D_% · Perf_1M_% · Perf_3M_% · Perf_6M_% · Perf_YTD_% · Perf_1Y_% · Data · Score`

*ETF (20):* `Ticker · ISIN · Nome · Categoria · Età · Tipo · Replica · Stelle MS · TER · Sharpe · Volume · Net Assets · Prezzo · Var_1D_% · Perf1Y · Perf3M · Perf6M · PerfYTD · Score · Data`

*FONDI US (16):* `Ticker · Nome · Categoria · TER · Sharpe · Volume · AUM · Prezzo · Var_1D_% · Perf1Y · Perf3M · Perf6M · PerfYTD · Stelle MS · Score · Data`

**Pesi Score per piano — AZIONI:**

| Metrica | BASIC | PRO | VALUE |
|---|---|---|---|
| Dividend Yield | 35% | — | — |
| Var_1D_% | 25% | 5% | — |
| ROE | 20% | 25% | 25% |
| EV/FCF | 10% | 35% | 40% |
| P/B | 10% | 20% | 15% |
| Net Debt/EBITDA | — | 15% | 20% |

**Pesi Score per piano — ETF:**

| Metrica | BASIC | PRO | VALUE |
|---|---|---|---|
| Perf 3M % | 45% | 10% | 5% |
| Sharpe Ratio | 15% | 40% | 45% |
| Performance 1Y | 20% | 30% | 25% |
| TER | 20% | 20% | 25% |

**Pesi Score per piano — FONDI US e FONDI EU** *(stessi pesi):*

| Metrica | BASIC | PRO | VALUE |
|---|---|---|---|
| Perf 3M % | 30% | 5% | 5% |
| Performance 1Y | 30% | 25% | 15% |
| TER | 25% | 30% | 35% |
| Sharpe Ratio | 15% | 40% | 45% |

---

## Scheduling

| Job | Orario | Giorni | Argomenti | Timeout |
|---|---|---|---|---|
| Screener AZIONI | 23:00 | lun-ven (5 gg) | `AZIONI` | 1h |
| Screener ETF+FONDI+EU | 23:30 | lun/mer/ven (3 gg) | `ETF FONDI FONDI_EU` | **2h** |
| Social automation | 08:00 | lun/mer/ven | — | 5 min |

**Avvio manuale singolo screener:**
```
cd "C:\Users\lucia\Desktop\ROBOT TRADER 2026\PYTHON_SCRIPTS"
python orchestrator.py AZIONI
python orchestrator.py ETF FONDI FONDI_EU
python orchestrator.py              ← tutti e 4
```

---

## Sistema Email (aggiornato 26/06/2026)

### Conteggi nel testo email (dinamici)

| Campo email | Valore calcolato |
|---|---|
| AZIONI: {NUM_TICKER} | 2.625 (da `len(ALL_AZIONI)`) |
| ETF: {NUM_TICKER} | 4.245 (ALL_ETF ∪ JustETF, dedup) |
| FONDI: {NUM_TICKER} | 1.379 (ALL_FONDI ∪ fondi_eu yahoo_ticker, dedup) |
| FONDI_EU: {NUM_TICKER} | 493 (fondi_eu_universe_cache.json) |

### Destinatari per piano (26/06/2026)

| Report | Piano | N. destinatari | Chi riceve |
|---|---|---|---|
| AZIONI | BASIC | 5 | Newfrontiers, Laura, Luigi, Luciano (lineexpress), Admin |
| AZIONI | PRO | 3 | Fuerte Info, Paolo, Admin |
| AZIONI | VALUE | 2 | Davide, Admin |
| ETF | BASIC | 3 | Luigi, Davide, Admin |
| ETF | PRO | 3 | Fuerte Info, Paolo, Admin |
| FONDI | BASIC | 3 | Laura, Luciano (lineexpress), Admin |
| FONDI | PRO | 2 | Fuerte Info, Admin |

> **Nota:** L'admin (`rioluc63@gmail.com`) riceve SEMPRE tutti i report, indipendentemente dal piano. I tester con `stato=TESTER` e piano assegnato ricevono esattamente come i clienti ATTIVI.

### Regola invio — `load_recipients_for_plan()` in `email_notifier.py`

```python
# Inclusi: ATTIVO e TESTER con piano assegnato ≠ NONE
# Esclusi: SOSPESO, o NONE per quel tipo di screener
if (utente.get(piano_key, "NONE").upper() == piano.upper()
        and utente.get("stato", "TESTER") in ("ATTIVO", "TESTER")):
    recipients[email] = nome
```

---

## Bug e Fix — 26/06/2026

| File | Bug | Fix |
|---|---|---|
| `dashboard.py` | Var% non si caricava per ETF EU (GOVS.L, ecc.): `prev_close=None` → `calc_chg=None` ma `raw_chg` disponibile | `regularMarketChangePercent` priorità su calcolo manuale da `prev_close` |
| `dashboard.py` | Database mostrava solo 1.178 ETF (mancava tutto JustETF universe) | `get_database_data()` carica `etf_universe_cache.json` post-build |
| `dashboard.py` | Database mostrava solo 886 fondi (mancavano i Fondi EU) | `get_database_data()` carica `fondi_eu_universe_cache.json` post-build |
| `dashboard.py` | ISIN puri (1.487 ETF + 43 fondi) linkavano a Yahoo Finance → pagina vuota | `_isIsin()` → bottone verde JustETF, no onclick, no fetch |
| `dashboard.py` | "5 destinatari" hardcoded nella home | `<span id="stat-dest">` aggiornato dinamicamente da `renderClienti()` |
| `email_notifier.py` | AZIONI hardcoded "3.072", FONDI "911", FONDI_EU "472" — numeri obsoleti | 4 funzioni `_get_*_count()` dinamiche, tutte calcolate a runtime |
| `email_notifier.py` | Tester (`stato=TESTER`) non ricevevano le email nonostante piano assegnato | Condizione `== "ATTIVO"` → `in ("ATTIVO", "TESTER")` |
| `orchestrator.py` | `startswith('FONDI_')` matchava `FONDI_EU_Screener_*.xlsx` → email con allegato sbagliato in run manuali parziali | Pattern cambiato a `startswith('FONDI_SCREENER_')` per tutti i tipi |
| `robot_trader_scheduler.bat` | Output schedulato notturno perduto (nessun log) | Redirect stdout+stderr → `logs\robot_trader_YYYYMMDD_HHMM.log` |

---

## Stato Attuale — Semaforo

### ✅ FUNZIONANTE

- 4 screener operativi (Azioni, ETF, Fondi US, Fondi EU)
- **Database Universo Ticker: 9.779 strumenti** (2.625 azioni + 5.732 ETF + 1.422 fondi)
- Identificazione automatica ISIN puri: link JustETF, no dati YF
- Scheduling 3 job automatici con log su file
- **Email report con conteggi dinamici aggiornati** — 4 funzioni runtime
- **Email a TESTER e ATTIVI** con piano assegnato
- Var% funzionante per tutti i ticker inclusi ETF EU (priorità `regularMarketChangePercent`)
- Rimozione manuale ticker (bottone ✕) con aggiornamento `ticker_lists_5000.py` a caldo
- Fogli Selezionati con colonne fisse, formattazione leggibile, ordinati per Score
- Dashboard admin + area clienti
- Sistema fatture PDF automatico
- Chatbot AI con Knowledge Base (5 lingue, reload a caldo)
- Order Builder (CSV IBKR + email bancaria MiFID II)
- WhatsApp notifiche (codice pronto, credenziali mancanti)
- Log schedulatore notturno in `PYTHON_SCRIPTS/logs/`

### 🔴 BLOCCA IL LANCIO PUBBLICO

1. **Cloudflare Tunnel** — senza questo il sito non è raggiungibile da fuori
   - Scaricare `cloudflared.exe`, eseguire bat, UUID in `config.yml`
   - Aggiornare `config.json → base_url` a `https://www.fuerteventurecapital.com`

2. **Password admin** — ancora `"123"` in `config.json → admin_password`

### 🟡 IN ATTESA CREDENZIALI

3. **Social Automation** — Brevo api_key, LinkedIn client_id/secret, Meta page_id
4. **WhatsApp Business** — account Meta verificato + numero dedicato + template approvati

### 🔑 SICUREZZA — AZIONI PENDENTI (da 16/06)

5. Ruotare API key Anthropic (era esposta in log debug)
6. Rigenerare App Password Gmail (era in chiaro in config.json)
7. Impostare password admin forte

---

## Storico Implementazioni

| Data | Cosa |
|---|---|
| 01–02/06/2026 | Order Builder, fatturazione PDF, flusso B2C, landing 5 lingue, GDPR |
| 03/06/2026 | Performance uniformità, 9-file output, score percentile, FONDI 781 ticker |
| 04/06/2026 | Social automation, 9 profili cliente, Cloudflare Tunnel setup, WhatsApp |
| 06/06/2026 | Chatbot AI con Knowledge Base (Haiku + prompt caching) |
| 14/06/2026 | Scheduling separato AZIONI/ETF+FONDI, sessioni timeout, ETF ACC +universo, fattura IBAN |
| 16/06/2026 | 20 bug fix: threading lock, scrittura atomica, NaN scoring, memory leak chat, timeout SMTP |
| 17/06/2026 | Retry automatico SMTP (3 tentativi, 30s pausa) |
| 20/06/2026 | Domain rename; FONDI US 781→911 (+9 famiglie); screener FONDI EU UCITS 472 pronti |
| 22/06/2026 | Knowledge Base riscritta (5 lingue, universo 5.637); box KB in dashboard con reload a caldo |
| 23/06/2026 | Fogli Selezionati colonne fisse + formattazione + Score; Tab Servizi textarea profilo target |
| 24/06/2026 | Debug completo: 12 bug risolti (orchestrator file matching, NaN JSON, FONDI_ALTRI→BOUTIQUE, ecc.) |
| 25/06/2026 | Database: 452 ticker morti rimossi da ticker_lists_5000.py; bottone ✕ rimozione manuale ticker; click-per-riga con highlight; Var% fix (priorità regularMarketChangePercent) |
| 26/06/2026 | Database espanso a 9.779 (JustETF + Fondi EU); ISIN detection (link JustETF); email conteggi dinamici; tester inclusi; bug orchestrator FONDI/FONDI_EU; log schedulatore |

---

## Note Tecniche Critiche

- **TER ETF EU:** nessun campo yfinance → justETF scraping via ISIN map
- **TER Fondi EU:** dalla `fondi_eu_universe_cache.json` — più affidabile di yfinance per UCITS
- **AUM Fondi EU:** proxy per volume (fondi non hanno volume di borsa)
- **Var% priority:** `regularMarketChangePercent` → se None, fallback a `(price-prev_close)/prev_close*100`
- **ISIN puri:** rilevati da `_isIsin()` JS e backend regex `^[A-Z]{2}[0-9A-Z]{10}$` — no fetch yfinance
- **Cache Fondi EU:** keyed per ISIN (fase 1) o ticker (fase 2 — senza ISIN disponibile)
- **Performance 1Y ETF:** fraction (0.12=12%) → ×100 nel foglio output
- **Sessioni:** in-memory → reset a ogni riavvio server → re-login necessario
- **BASE_URL:** `config.json → base_url` — aggiornare a `https://www.fuerteventurecapital.com` al lancio
- **Dedup ETF ISIN:** `_dedup_by_isin()` in `value_screener_etf.py` — preferisce ACC, poi max volume
- **FONDI_BOUTIQUE:** lista multi-famiglia — NON chiamarla `FONDI_ALTRI` (causa ImportError silenzioso)
- **NaN da yfinance:** bloccato in `_safe()` + sanitizer ricorsivo in `_json` handler
- **File matching orchestrator:** sempre `type+'_SCREENER_'` — NON `type+'_'` (ambiguo FONDI/FONDI_EU)
- **Log schedulato:** `PYTHON_SCRIPTS/logs/robot_trader_YYYYMMDD_HHMM.log`
- **Python path schedulato:** `C:\Users\lucia\AppData\Local\Programs\Python\Python314\python.exe` — verificare che corrisponda al `python` in PATH usato manualmente

---

## Differenze Scheduled vs Manuale — Verifica 26/06/2026

| Aspetto | Schedulato (BAT) | Manuale | Allineati? |
|---|---|---|---|
| Screener eseguiti | Tutti e 4 | Solo quelli specificati in args | Per design |
| File Excel generati | `type_SCREENER_piano_...xlsx` | Identico | ✅ |
| File ricercato per email | `startswith(type+'_SCREENER_')` | Identico | ✅ (fix 26/06) |
| TICKER_COUNT nelle email | Dinamico (calcolato a runtime) | Identico | ✅ (fix 26/06) |
| Destinatari email | ATTIVO + TESTER con piano | Identico | ✅ (fix 26/06) |
| Log output | `logs/robot_trader_*.log` | Console PowerShell | Diverso (per design) |
| Python exe | Python314 (hardcoded nel BAT) | `python` in PATH | ⚠️ Verificare coincidano |

---

*Fuerte Venture Capital SL · CIF B23881691 · Villaverde, Las Palmas de Gran Canaria, Spagna*  
**Nota operativa:** modifiche a `dashboard.py` richiedono riavvio del processo Python (chiudere CMD "Robot Trader - Dashboard" e riaprire via `START_SISTEMA_PUBBLICO.bat`). Logout/login dalla dashboard non è sufficiente.

*Documento aggiornato il 26/06/2026*
