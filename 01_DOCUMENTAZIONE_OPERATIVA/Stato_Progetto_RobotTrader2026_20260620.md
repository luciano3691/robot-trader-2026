# Stato Progetto — Robot Trader 2026

**Fuerte Venture Capital SL** · CIF B23881691 · marketing@fuerteventurecapital.com  
**Ultimo aggiornamento:** 20/06/2026  
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
| `value_screener_fondi_eu.py` | **NUOVO** Screener fondi UCITS EU: 472 fondi, legge cache, output 3 Excel |
| `fetch_fondi_eu_universe.py` | **NUOVO** Scraper 2 fasi → `fondi_eu_universe_cache.json` |
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
| `fondi_eu_universe_cache.json` | **NUOVO** Cache 536 voci fondi UCITS EU — 472 pronti per screener |

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

## Come funziona il discovery Fondi EU UCITS

```
fetch_fondi_eu_universe.py — due fasi:

  FASE 1 — 71 ISIN seed
    → cerca ticker su Yahoo Finance per ISIN
    → ~38% hit rate (ISINs LU/IE meno coperti)
    → trovati: 27 fondi

  FASE 2 — 420 termini di ricerca libera
    → "Amundi SICAV", "Pictet Water", "europe equity UCITS", ...
    → filtra: tieni solo ticker con suffisso borsa EU (.F .PA .MI .L .AS ...)
    → trovati: 466 fondi nuovi unici

  TOTALE in cache: 536 voci — 472 pronte (con TER disponibile)
```

**Comandi:**
```bash
python fetch_fondi_eu_universe.py              # tutto (fase 1 + fase 2) ~2h
python fetch_fondi_eu_universe.py --discover   # solo fase 2
python fetch_fondi_eu_universe.py --stats      # statistiche cache
```

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

## Scheduling (aggiornato 20/06/2026)

| Job | Orario | Giorni | Argomenti | Timeout |
|---|---|---|---|---|
| Screener AZIONI | 23:00 | lun-ven (5 gg) | `AZIONI` | 1h |
| Screener ETF+FONDI+EU | 23:30 | lun/mer/ven (3 gg) | `ETF FONDI FONDI_EU` | **2h** |
| Social automation | 08:00 | lun/mer/ven | — | 5 min |

**Logica:** AZIONI giornaliere (alta volatilità). ETF+FONDI ogni 2 giorni (segnali stabili 24-48h).

---

## Output Report

```
REPORTS_DAILY/
  Azioni_Screener_BASIC_YYYYMMDD_HHMMSS.xlsx
  Azioni_Screener_PRO_YYYYMMDD_HHMMSS.xlsx
  Azioni_Screener_VALUE_YYYYMMDD_HHMMSS.xlsx
  ETF_Screener_BASIC_YYYYMMDD_HHMMSS.xlsx   (x3)
  FONDI_Screener_BASIC_YYYYMMDD_HHMMSS.xlsx  (x3)
  FONDI_EU_Screener_BASIC_YYYYMMDD_HHMMSS.xlsx  (x3)  ← NUOVO
```

**Struttura Excel per piano:**

| Piano | Fogli |
|---|---|
| BASIC | Dashboard + Top 20 per Score |
| PRO | Dashboard + Top 50 per Score + Selezionati |
| VALUE | Dashboard + Top 50 per Score + Selezionati + Scartati per motivo + Non Validi |

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
- Email report per piano con retry automatico
- Dashboard admin + area clienti
- Sistema fatture PDF automatico
- Chatbot AI con Knowledge Base
- Order Builder (CSV IBKR + email bancaria MiFID II)
- WhatsApp notifiche (codice pronto, credenziali mancanti)

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

---

*Fuerte Venture Capital SL · CIF B23881691 · Villaverde, Las Palmas de Gran Canaria, Spagna*  
*Documento aggiornato il 20/06/2026*
