# Stato Progetto — Robot Trader 2026

**Fuerte Venture Capital SL** · CIF B23881691 · marketing@fuerteventurecapital.com  
**Ultimo aggiornamento:** 24/06/2026  
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
| `value_screener_azioni.py` | Screener azioni: 3.072 ticker, 23 mercati, output 3 Excel (BASIC/PRO/VALUE) |
| `value_screener_etf.py` | Screener ETF: 1.182 ETF EU ACC, dedup ISIN (preferisce ACC), output 3 Excel |
| `value_screener_fondi.py` | Screener fondi US: 911 fondi, 45 famiglie, output 3 Excel |
| `value_screener_fondi_eu.py` | Screener fondi UCITS EU: 472 fondi, legge cache, output 3 Excel |
| `fetch_fondi_eu_universe.py` | Scraper 2 fasi → `fondi_eu_universe_cache.json` |
| `screener_utils.py` | Score bontà percentile — `batch_percentile_score()` condiviso tra tutti gli screener |
| `ticker_lists_5000.py` | Universo ticker: ALL_AZIONI 3.072 / ALL_ETF 1.182 / ALL_FONDI 911 |
| `email_notifier.py` | `python email_notifier.py TIPO PIANO FILENAME` — invia solo agli iscritti del piano |
| `order_builder.py` | Order Builder — email bancaria MiFID II, CSV IBKR/Generico, prezzi live |
| `chat_service.py` | Chatbot AI — Claude Haiku 4.5 + KB 4 file, rate limit 30 msg/h per IP |
| `whatsapp_service.py` | Notifiche WhatsApp via Meta Cloud API |
| `social_automation.py` | Orchestratore social — Brevo/LinkedIn/Meta — lun/mer/ven |
| `clienti.json` | Database clienti: piano_azioni/etf/fondi, dati_fiscali, numero_fattura, gdpr |
| `config.json` | Config globale: SMTP, social, whatsapp, scoring_weights, fattura (IBAN), base_url |
| `fatture_counter.json` | `{"ultimo": 18}` — contatore progressivo numeri fattura |
| `fondi_eu_universe_cache.json` | Cache 536 voci fondi UCITS EU — 472 pronti per screener |

---

## Cartelle Dati (radice progetto — NON dentro PYTHON_SCRIPTS)

```
Robot Trader 2026/
  FATTURE/          → FVC-2026-0001...0018.pdf — generate automaticamente
  REPORTS_DAILY/    → Azioni/ETF/FONDI/FONDI_EU_Screener_PIANO_YYYYMMDD_HHMMSS.xlsx
  LOGS/
  BACKUPS/
  PYTHON_SCRIPTS/   → codice + config + clienti.json
```

---

## Universo Strumenti (aggiornato 20/06/2026)

| Asset | Count | Fonte dati | Note |
|---|---|---|---|
| ALL_AZIONI | **3.072** | yfinance | USA, EU15, Nordici, JP, HK, Australia, Canada, India, Taiwan — 23 mercati |
| ALL_ETF | **1.182** | yfinance + justETF | Europa ACC, dedup ISIN (preferisce ACC su DIST, poi max volume) |
| ALL_FONDI (US) | **911** | yfinance | 45 famiglie — +9 aggiunte 20/06: AB, PGIM, Morgan Stanley, State Street, William Blair, Causeway, Hotchkis, Alger, Transamerica |
| FONDI EU (UCITS) | **472** | yfinance + cache | 21 paesi EU — discovery 2 fasi completata 20/06 |
| **TOTALE** | **5.637** | | |

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
| PRO | Universo 3.072 | ≤15x | ≤2x | ≥1% | ≤3x | 50 |
| VALUE | Universo 3.072 | ≤12x | ≤1x | ≥2% | ≤2x | 50 |

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

## Struttura Excel Report (aggiornato 23/06/2026)

```
REPORTS_DAILY/
  Azioni_Screener_BASIC_YYYYMMDD_HHMMSS.xlsx
  Azioni_Screener_PRO_YYYYMMDD_HHMMSS.xlsx
  Azioni_Screener_VALUE_YYYYMMDD_HHMMSS.xlsx
  ETF_Screener_BASIC_YYYYMMDD_HHMMSS.xlsx   (x3)
  FONDI_Screener_BASIC_YYYYMMDD_HHMMSS.xlsx  (x3)
  FONDI_EU_Screener_BASIC_YYYYMMDD_HHMMSS.xlsx  (x3)
```

**Fogli in ogni Excel (tutti i piani):**

| # | Foglio | Contenuto |
|---|---|---|
| 0 | 📖 Legenda | Guida metriche e Score (solo AZIONI) |
| 1 | Dashboard | Filtri, statistiche, breakdown mercato, Top 5 |
| 2 | Top N per Score | Le migliori N azioni/ETF/fondi ordinate per Score |
| 3 | Selezionati | Tutti i selezionati — colonne fisse, ordinati per Score |
| 4+ | Scartati per motivo | Solo archivio interno — NON inviati ai clienti |
| — | Non Validi / Errori | Solo archivio interno — NON inviati ai clienti |

**Colonne fisse foglio Selezionati (aggiornato 23/06/2026):**

*AZIONI (30 colonne):*
`Ticker · Nome · Valuta · Settore · Industry · Mercato · Indice · Market Cap · P/B · ROE · EV/EBITDA · Free Cash Flow · Enterprise Value · Total Debt · Total Cash · EBITDA · Dividend Yield · Analyst Coverage · EV/FCF · Net Debt · Net Debt/EBITDA · Prezzo · Var_1D_% · Perf_1M_% · Perf_3M_% · Perf_6M_% · Perf_YTD_% · Perf_1Y_% · Data Dati · Score`

*ETF (20 colonne):*
`Ticker · ISIN · Nome · Categoria · Età (anni) · Tipo · Replica · Stelle MS · TER · Sharpe Ratio · Volume · Net Assets · Prezzo · Var_1D_% · Performance 1Y · Perf 3M % · Perf 6M % · Perf YTD % · Score · Data Dati`

*FONDI US (16 colonne):*
`Ticker · Nome · Categoria · TER · Sharpe Ratio · Volume · AUM · Prezzo · Var_1D_% · Performance 1Y · Perf 3M % · Perf 6M % · Perf YTD % · Stelle MS · Score · Data Dati`

**Metodo calcolo Score (0–100):**
Per ogni metrica, l'asset viene confrontato con tutti gli altri selezionati → percentile 0–100. I percentili vengono pesati e sommati. Pesi letti da `config.json → scoring_weights`. Funzione: `batch_percentile_score()` in `screener_utils.py`.

**Pesi Score per piano — AZIONI:**

| Metrica | BASIC | PRO | VALUE |
|---|---|---|---|
| Dividend Yield | 35% | 0% | 0% |
| Var_1D_% | 25% | 5% | 0% |
| ROE | 20% | 25% | 25% |
| EV/FCF | 10% | 35% | 40% |
| P/B | 10% | 20% | 15% |
| Net Debt/EBITDA | 0% | 15% | 20% |

**Pesi Score per piano — ETF:**

| Metrica | BASIC | PRO | VALUE |
|---|---|---|---|
| Perf 3M % | 45% | 10% | 5% |
| Sharpe Ratio | 15% | 40% | 45% |
| Performance 1Y | 20% | 30% | 25% |
| TER | 20% | 20% | 25% |

**Pesi Score per piano — FONDI US e FONDI EU** *(FONDI EU usa gli stessi pesi di FONDI US):*

| Metrica | BASIC | PRO | VALUE |
|---|---|---|---|
| Perf 3M % | 30% | 5% | 5% |
| Performance 1Y | 30% | 25% | 15% |
| TER | 25% | 30% | 35% |
| Sharpe Ratio | 15% | 40% | 45% |

**Formattazione numeri (tutti gli screener):**
- Market Cap / AUM / FCF / EV / Debt / Cash / EBITDA → leggibile (es. `78,8B`, `12,2M`)
- TER → percentuale 2 decimali (es. `0,35%`)
- ROE / Dividend Yield / Performance 1Y → percentuale 1 decimale (es. `25,0%`)
- Var_1D_% / Perf 3M-6M-YTD % → 2 decimali con virgola (es. `-17,97%`)
- P/B / EV/EBITDA / EV/FCF / ND/EBITDA / Sharpe → 2 decimali numerici
- Score → 1 decimale

**Email clienti — `_build_client_attachment()` in `email_notifier.py`:**
Il report viene generato al volo prima dell'invio: carica l'Excel da `REPORTS_DAILY/`, rimuove tutti i fogli scarto (`Esclusi*`, `Scartate*`, `Scartati*`, `Non Validi`, `Dati Mancanti*`, `Errori*`), invia solo i fogli utili al cliente.

---

## Scheduling (aggiornato 20/06/2026)

| Job | Orario | Giorni | Argomenti | Timeout |
|---|---|---|---|---|
| Screener AZIONI | 23:00 | lun-ven (5 gg) | `AZIONI` | 1h |
| Screener ETF+FONDI+EU | 23:30 | lun/mer/ven (3 gg) | `ETF FONDI FONDI_EU` | **2h** |
| Social automation | 08:00 | lun/mer/ven | — | 5 min |

**Logica:** AZIONI giornaliere (alta volatilità). ETF+FONDI ogni 2 giorni (segnali stabili 24-48h).

---

## Sistema Fatture

- **Generazione automatica:** su registrazione, upgrade piano, attivazione admin
- **PDF:** FPDF, A4, logo embedded base64, una sola pagina
- **IBAN:** ES83 2100 1513 7202 0070 3406 — CaixaBank SA — BIC CAIXESBBXXX
- **Cartella:** `Robot Trader 2026/FATTURE/FVC-2026-XXXX.pdf`
- **Numerazione:** contatore in `fatture_counter.json`, attuale = 18
- **Download admin:** GET `/api/fattura/{numero}`
- **Download cliente:** GET `/api/mia-fattura` (link in area riservata)

---

## Prezzi Servizi

| Piano | Azioni | ETF | Fondi |
|---|---|---|---|
| BASIC | €29/mese | €29/mese | €29/mese |
| PRO | €39/mese | €39/mese | €39/mese |
| VALUE | €59/mese | €59/mese | €59/mese |

---

## Stato Attuale — Semaforo

### ✅ FUNZIONANTE

- 4 screener operativi (Azioni, ETF, Fondi US, Fondi EU)
- Universo 5.637 strumenti
- Scheduling 3 job automatici
- Email report per piano con retry automatico (solo clienti ATTIVI)
- Fogli Selezionati con colonne fisse, formattazione leggibile, ordinati per Score
- Email clienti: senza fogli scarto (generazione al volo in `_build_client_attachment`)
- Tab Servizi: campo "Profilo target" multiriga con profili investitore completi per tutti e 9 i servizi
- Dashboard admin + area clienti
- Sistema fatture PDF automatico (include FONDI_EU)
- Chatbot AI con Knowledge Base (5 lingue, reload a caldo)
- Order Builder (CSV IBKR + email bancaria MiFID II)
- WhatsApp notifiche (codice pronto, credenziali mancanti)
- **Tab 🗃️ Database Universo Ticker** — operativa (3 tab: Azioni / ETF / Fondi)
- **FONDI_EU visibile** in get_status() dashboard admin e genera_fattura_pdf()

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

---

## Bug risolti — 24/06/2026 (debug completo + tab Database)

| File | Bug | Fix |
|---|---|---|
| `orchestrator.py` | `"FONDI" in "FONDI_EU_..."` → email con allegato sbagliato | `startswith(type + '_')` |
| `orchestrator.py` | log retry mostrava `max_retry-1` invece di `max_retry` | corretto |
| `email_notifier.py` | FONDI count 781→911, FONDI_EU assente da TICKER_COUNT | aggiornati conteggi |
| `email_notifier.py` | email inviate anche a clienti SOSPESO | filtro `stato == "ATTIVO"` |
| `dashboard.py` | `_chat.get_kb_info()` senza guard `_CHAT_OK` → NameError se anthropic non installato | guard aggiunto |
| `dashboard.py` | `genera_fattura_pdf()` non includeva FONDI_EU → nessuna fattura per abbonati FONDI EU | aggiunto al loop |
| `dashboard.py` | `get_status()` cieco a FONDI_EU in dashboard admin | aggiunto a `_plan_prefix`, `_legacy_pats`, loop |
| `dashboard.py` | `get_database_data()` importava `FONDI_ALTRI` (non esiste in `ticker_lists_5000.py`, si chiama `FONDI_BOUTIQUE`) → tab Database completamente vuota | rinominato import e `_build()` call |
| `dashboard.py` | yfinance restituisce `float('nan')` → `_json` produceva JSON non valido (`NaN`) | `_safe()` in `get_database_lookup` + sanitizer ricorsivo in `_json` |
| `value_screener_etf.py` | `load_filters()` usava `.get('key',{}).get('value',X)` → ignorava valori plain number da parametri.json | helper `_get_param` |
| `value_screener_fondi.py` | stesso bug ETF in `load_filters()` | helper `_get_param` |
| `chat_service.py` | `reload_kb()` usava `split("KNOWLEDGE BASE:")` senza maxsplit → comportamento imprevedibile se KB contiene la stringa | `split(..., 1)` |

**Nota — FONDI_ALTRI vs FONDI_BOUTIQUE:** in `ticker_lists_5000.py` la lista multi-famiglia si chiama `FONDI_BOUTIQUE` (rinominata il 20/06 con l'aggiornamento del dominio). `dashboard.py` la importava ancora come `FONDI_ALTRI` causando un `ImportError` silenzioso che rendeva la tab Database completamente vuota.

---

## Storico Implementazioni

| Data | Cosa |
|---|---|
| 01–02/06/2026 | Order Builder, fatturazione PDF, flusso B2C, landing 5 lingue, GDPR |
| 03/06/2026 | Performance uniformità, 9-file output, score percentile, FONDI 781 ticker |
| 04/06/2026 | Social automation, 9 profili cliente, Cloudflare Tunnel setup, WhatsApp |
| 06/06/2026 | Chatbot AI con Knowledge Base (Haiku + prompt caching) |
| 14/06/2026 | Scheduling separato AZIONI/ETF+FONDI, sessioni timeout, ETF ACC +universo, fattura IBAN, cartella FATTURE radice |
| 16/06/2026 | 20 bug fix: threading lock, scrittura atomica, NaN scoring, memory leak chat, timeout SMTP |
| 17/06/2026 | Retry automatico SMTP (3 tentativi, 30s pausa) |
| 20/06/2026 | Domain rename fuertescreener.com→fuerteventurecapital.com; FONDI US 781→911 (+9 famiglie); nuovo screener FONDI EU UCITS 472 pronti; orchestrator+scheduler aggiornati |
| 22/06/2026 | Knowledge Base riscritta (5 lingue, universo 5.637); box KB in dashboard admin con reload a caldo |
| 23/06/2026 | Fogli Selezionati con colonne fisse + formattazione leggibile + ordinati per Score (AZIONI 30 col, ETF 20 col, FONDI US 16 col); Tab Servizi → textarea profilo target; `servizi_config.json` aggiornato con 9 profili investitore |
| 24/06/2026 | Debug completo: 12 bug risolti (orchestrator file matching, NaN JSON, FONDI_ALTRI→BOUTIQUE, FONDI_EU visibilità admin, _get_param ETF/Fondi, chat split, filtro ATTIVO su email) |

---

## Note Tecniche Critiche

- **TER ETF EU:** nessun campo yfinance → justETF scraping via ISIN map
- **TER Fondi EU:** dalla `fondi_eu_universe_cache.json` — più affidabile di yfinance per UCITS
- **AUM Fondi EU:** usato come proxy volume (fondi non hanno volume di borsa)
- **Cache Fondi EU:** keyed per ISIN (fase 1) o ticker (fase 2 — senza ISIN disponibile)
- **Performance 1Y ETF:** fraction (0.12=12%) → ×100 nel foglio output
- **Sessioni:** in-memory → reset a ogni riavvio server → re-login necessario
- **BASE_URL:** `config.json → base_url` — aggiornare a `https://www.fuerteventurecapital.com` al lancio
- **Dedup ETF ISIN:** `_dedup_by_isin()` in `value_screener_etf.py` — preferisce ACC, poi max volume
- **Email template {PIANO}:** presente in `email_template.html` e `.txt`
- **_write_azioni_plan_excel:** funzione unica chiamata per BASIC, PRO e VALUE — modifiche si applicano ai 3 piani
- **NaN da yfinance:** bloccato a due livelli — `_safe()` in `get_database_lookup` (alla fonte) + sanitizer ricorsivo in `_json` (difesa globale per tutti gli endpoint)
- **FONDI_BOUTIQUE:** lista multi-famiglia in `ticker_lists_5000.py` — NON chiamarla `FONDI_ALTRI` (nome precedente, causa ImportError)

---

*Fuerte Venture Capital SL · CIF B23881691 · Villaverde, Las Palmas de Gran Canaria, Spagna*  
**Nota operativa:** modifiche a `dashboard.py` richiedono riavvio del processo Python (chiudere CMD "Robot Trader - Dashboard" e riaprire via `START_SISTEMA_PUBBLICO.bat`). Logout/login dalla dashboard non è sufficiente.

*Documento aggiornato il 24/06/2026*
