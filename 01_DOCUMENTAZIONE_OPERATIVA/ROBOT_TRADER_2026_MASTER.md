# Robot Trader 2026 — Documentazione Master

**Fuerte Venture Capital SL** · CIF B23881691  
**Email operativa:** newcapitalfuerte@gmail.com  
**Email clienti:** marketing@fuerteventurecapital.com  
**URL pubblico (target):** https://www.fuerteventurecapital.com  
**Path progetto:** `C:\Users\lucia\Desktop\Robot Trader 2026\`  
**Documento aggiornato:** 26/06/2026 — sostituisce tutti i precedenti file Stato_Progetto_*

---

## INDICE

1. [Stack Tecnico](#1-stack-tecnico)
2. [Struttura File](#2-struttura-file)
3. [Avvio Sistema](#3-avvio-sistema)
4. [Universo Strumenti](#4-universo-strumenti)
5. [Screener — Logica e Filtri](#5-screener--logica-e-filtri)
6. [Pesi Score per Piano](#6-pesi-score-per-piano)
7. [Report Excel — Struttura](#7-report-excel--struttura)
8. [Sistema Email](#8-sistema-email)
9. [CRM Clienti](#9-crm-clienti)
10. [Prezzi Servizi e Profili Cliente](#10-prezzi-servizi-e-profili-cliente)
11. [Sistema Fatture](#11-sistema-fatture)
12. [Scheduling e Orchestrator](#12-scheduling-e-orchestrator)
13. [Dashboard Admin](#13-dashboard-admin)
14. [Area Clienti](#14-area-clienti)
15. [Tab Database Universo Ticker](#15-tab-database-universo-ticker)
16. [Chatbot AI](#16-chatbot-ai)
17. [Social Automation](#17-social-automation)
18. [WhatsApp Business](#18-whatsapp-business)
19. [Order Builder](#19-order-builder)
20. [Sicurezza e Autenticazione](#20-sicurezza-e-autenticazione)
21. [Stato Attuale — Semaforo](#21-stato-attuale--semaforo)
22. [Note Tecniche Critiche](#22-note-tecniche-critiche)
23. [Comandi Operativi](#23-comandi-operativi)
24. [Storico Implementazioni](#24-storico-implementazioni)

---

## 1. Stack Tecnico

| Componente | Tecnologia |
|---|---|
| **Server web** | `http.server.HTTPServer` stdlib Python — ZERO framework |
| **Dati mercato** | `yfinance` (stock/ETF/fondi) + scraping JustETF (TER ETF EU) |
| **Output report** | `openpyxl` → Excel multi-sheet |
| **Auth admin** | Cookie `rt_admin=secrets.token_hex(20)`, in-memory dict, timeout **8h fisso** |
| **Auth cliente** | Cookie `rt_client`, dict `CLIENT_SESSIONS`, sliding **24h** |
| **Email** | `smtplib` stdlib → Gmail SMTP (`newcapitalfuerte@gmail.com`) |
| **Scheduling** | `APScheduler BackgroundScheduler` — 3 job separati |
| **Fatture** | `FPDF`, PDF A4, logo embedded base64 |
| **Chatbot** | Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) + prompt caching |
| **Tunnel pubblico** | `ngrok` statico (temporaneo) → target: Cloudflare Tunnel |
| **Sessioni** | In-memory — reset a ogni riavvio Python |

---

## 2. Struttura File

### PYTHON_SCRIPTS/ — File core

| File | Funzione |
|---|---|
| `dashboard.py` | **Unico server HTTP** — tutto in un file: admin console, landing page, area clienti, Order Builder, chatbot, CRM, database ticker, API REST |
| `orchestrator.py` | Lancia screener selezionati in sequenza + invia email per piano. Args: `AZIONI` / `ETF` / `FONDI` / `FONDI_EU` |
| `scheduler_daemon.py` | APScheduler: AZIONI 23:00 lun-ven / ETF+FONDI+EU 23:30 lun-mer-ven / social 08:00 lun-mer-ven |
| `robot_trader_scheduler.bat` | BAT per Windows Task Scheduler — redirect stdout+stderr → `logs\robot_trader_YYYYMMDD_HHMM.log` |

### PYTHON_SCRIPTS/ — Screener

| File | Asset | Ticker screener |
|---|---|---|
| `value_screener_azioni.py` | Azioni globali | 2.625 |
| `value_screener_etf.py` | ETF EU UCITS | ~4.245 (ALL_ETF ∪ JustETF cache) |
| `value_screener_fondi.py` | Fondi mutual US | 886 |
| `value_screener_fondi_eu.py` | Fondi UCITS EU | 493 (con yahoo_ticker) |

### PYTHON_SCRIPTS/ — Universo e cache

| File | Funzione |
|---|---|
| `ticker_lists_5000.py` | Tutte le liste ticker: `ALL_AZIONI` (2.625) / `ALL_ETF` (1.174) / `ALL_FONDI` (886) + ~100 subliste |
| `fetch_justetf_universe.py` | Scraper JustETF sitemap → `etf_universe_cache.json` (4.630 ISIN, 3.143 con ticker YF) |
| `fetch_fondi_eu_universe.py` | Scraper 2 fasi (ISIN seed + discovery 420 termini) → `fondi_eu_universe_cache.json` |
| `etf_universe_cache.json` | Cache JustETF: 4.630 ISIN, 3.143 `preferred_ticker` YF, 1.487 solo ISIN puri |
| `fondi_eu_universe_cache.json` | Cache fondi EU: 536 voci, 493 con `yahoo_ticker`, 43 ISIN puri senza ticker |

### PYTHON_SCRIPTS/ — Moduli di supporto

| File | Funzione |
|---|---|
| `screener_utils.py` | `batch_percentile_score()` — score 0–100 percentile condiviso tra tutti i screener |
| `email_notifier.py` | `python email_notifier.py TIPO PIANO FILENAME` — invia Excel a ATTIVI e TESTER con piano |
| `chat_service.py` | Chatbot AI — Claude Haiku + KB 4 file MD (5 lingue), rate limit 30 msg/h per IP |
| `order_builder.py` | Order Builder — email bancaria MiFID II, CSV IBKR/Generico, prezzi live |
| `whatsapp_service.py` | Meta Cloud API — `notify_screener_ready()`, `notify_morning_brief()` |
| `social_automation.py` | Orchestratore social — Brevo / LinkedIn / Meta — lun/mer/ven |
| `content_generator.py` | Genera testo post social via Claude API (fallback 9 template IT+ES) |
| `social_publisher.py` | Brevo SMTP + LinkedIn API + Meta Graph API |

### PYTHON_SCRIPTS/ — Dati e config

| File | Funzione |
|---|---|
| `clienti.json` | DB clienti: `{tester: [...], clienti: [...]}` — piano, dati_fiscali, numero_fattura, gdpr |
| `config.json` | Config globale: SMTP, social, WhatsApp, scoring_weights, IBAN fattura, base_url |
| `fatture_counter.json` | `{"ultimo": 18}` — contatore progressivo numeri fattura |
| `servizi_config.json` | Prezzi, filtri, profili cliente per 9 servizi (3 asset × 3 piani) |
| `parametri.json` | Soglie filtri screener modificabili dalla dashboard admin |

### Cartelle (radice progetto — NON dentro PYTHON_SCRIPTS)

```
Robot Trader 2026/
  FATTURE/                  → FVC-2026-0001...0018.pdf (generati automaticamente)
  REPORTS_DAILY/            → Azioni/ETF/FONDI/FONDI_EU_Screener_PIANO_YYYYMMDD_HHMMSS.xlsx
  LOGS/
  BACKUPS/
  PYTHON_SCRIPTS/
    logs/                   → robot_trader_YYYYMMDD_HHMM.log (schedulatore notturno)
  01_DOCUMENTAZIONE_OPERATIVA/
  KNOWLEDGE_BASE/           → kb_azienda.md / kb_prodotto.md / kb_faq.md / kb_glossario.md
  ASSETS/                   → logo.png, immagini
```

---

## 3. Avvio Sistema

### Avvio completo (normale)

```bat
START_SISTEMA_PUBBLICO.bat
```

Avvia in sequenza: `ngrok` (tunnel pubblico) → `dashboard.py` (server HTTP porta 5000) → `scheduler_daemon.py` (job notturni).

### Avvio manuale componenti singoli

```bat
REM Solo dashboard (admin + area clienti)
cd "C:\Users\lucia\Desktop\ROBOT TRADER 2026\PYTHON_SCRIPTS"
python dashboard.py

REM Solo scheduler (job automatici)
python scheduler_daemon.py
```

### Riavvio dopo modifiche a dashboard.py

**Chiudere** la CMD con il server → riaprire con `START_SISTEMA_PUBBLICO.bat`.  
Logout/login dalla dashboard NON riavvia il server Python.

---

## 4. Universo Strumenti

### Conteggi screener (ticker con dati Yahoo Finance)

| Asset | Count | Mercati / Famiglie |
|---|---|---|
| **Azioni** | **2.625** | 23 mercati: USA (SP500/Russell/MidCap/SP600), UK, Francia, Germania, Italia, Spagna, Svizzera, Olanda, Svezia, Norvegia, Danimarca, Finlandia, Belgio, Giappone, Hong Kong, Australia, Canada, Corea, India, Taiwan, Brasile |
| **ETF** | **~4.245** | ALL_ETF (1.174, Europa) ∪ JustETF cache preferred_ticker (3.143, UCITS) — dedup |
| **Fondi US** | **886** | 45+ famiglie: Vanguard, Fidelity, T.Rowe Price, American Funds, Schwab, PIMCO, DFA, Dodge&Cox, BlackRock, Invesco, Franklin, MFS, JPMorgan, Goldman, Lord Abbett, Baron, AQR, Janus, Calamos, ecc. |
| **Fondi EU** | **493** | UCITS europei con ticker Yahoo Finance (cache `fondi_eu_universe_cache.json`) |

### Conteggi Database Universo Ticker (tab nella dashboard)

| Asset | Count Database | Di cui ISIN puri (no YF) | Fonte aggiuntiva |
|---|---|---|---|
| Azioni | **2.625** | 0 | — |
| ETF | **5.732** | 1.487 | JustETF cache completa |
| Fondi | **1.422** | 43 | Fondi EU cache completa |
| **TOTALE** | **9.779** | **1.530** | |

**Comportamento ISIN puri nel Database:**

| Tipo | Riconoscimento | Bottone | Dati live | Link aperto |
|---|---|---|---|---|
| Ticker normale | Tutto il resto | 🟠 Arancione | ✅ Click per caricare | Yahoo Finance |
| Ticker 0P (Morningstar) | Inizia con `0P` | 🟠 Arancione | ✅ Click per caricare | Yahoo Finance |
| **ISIN puro** | Regex `^[A-Z]{2}[0-9A-Z]{10}$` | 🟢 Verde | ❌ Non disponibile | **JustETF** |

### Costruzione universo ETF (value_screener_etf.py)

```
ETF_UNIVERSE = ALL_ETF (1.174, da ticker_lists_5000)
             ∪ etf_universe_cache.json preferred_ticker (3.143 UCITS con ticker YF)
             → dedup → ~4.245 ETF unici
```

I 1.487 ISIN senza `preferred_ticker` non entrano nello screener ma sono visibili nel Database.

### Costruzione universo Fondi EU (fetch_fondi_eu_universe.py)

```
FASE 1 — 71 ISIN seed → cerca ticker su Yahoo Finance per ISIN
         hit rate ~38% (ISINs LU/IE meno coperti) → ~27 trovati

FASE 2 — 420 termini di ricerca libera
         "Amundi SICAV", "Pictet Water", "europe equity UCITS", ...
         filtra: suffisso borsa EU (.F .PA .MI .L .AS .SW .ST ...)
         → ~466 fondi nuovi

TOTALE cache: 536 voci (493 con yahoo_ticker, 43 con errore/nessun ticker)
```

**Aggiornamento universe:**
```bash
python fetch_fondi_eu_universe.py              # tutto ~2h
python fetch_fondi_eu_universe.py --discover   # solo fase 2
python fetch_fondi_eu_universe.py --stats      # statistiche cache
python fetch_justetf_universe.py               # ETF JustETF ~2h
python fetch_justetf_universe.py --update      # solo ISIN mancanti
```

---

## 5. Screener — Logica e Filtri

### Architettura comune (tutti e 4 i screener)

```
FASE 1 — Fetch dati (parallelo, ThreadPoolExecutor)
         → yfinance per ogni ticker → lista dati completa

FASE 2 — Per ogni piano (BASIC / PRO / VALUE):
         → applica filtri → calcola Score (batch_percentile_score)
         → ordina per Score → scrive Excel separato
```

### Filtri AZIONI (value_screener_azioni.py)

| Piano | Universe | EV/FCF max | P/B max | ROE min | ND/EBITDA max | Top N |
|---|---|---|---|---|---|---|
| BASIC | Blue chip ~702 (SP500+FTSE100+DAX+CAC+MIB+IBEX+SMI+AEX+Nikkei) | 18x | 3x | 0% | 4x | 20 |
| PRO | Universo completo 2.625 | 15x | 2x | 1% | 3x | 50 |
| VALUE | Universo completo 2.625 | 12x | 1x | 2% | 2x | 50 |

### Filtri ETF (value_screener_etf.py)

| Piano | TER max | Sharpe min | Volume min | Perf 1Y min | Età min | Top N |
|---|---|---|---|---|---|---|
| BASIC | 0.50% | 0.3 | 100k | +5% | 5 anni | 20 |
| PRO | 0.35% | 0.4 | 100k | +7% | 3 anni | 50 |
| VALUE | 0.20% | 0.5 | 100k | +10% | 2 anni | 50 |

**Note ETF:** TER da JustETF cache (più affidabile di yfinance per UCITS). Dedup ISIN: preferisce ACC su DIST, poi max volume. Performance 1Y: fraction yfinance (0.12) → ×100 nel foglio.

### Filtri FONDI US (value_screener_fondi.py)

| Piano | TER max | Sharpe min | Volume min | Perf 1Y min | Top N |
|---|---|---|---|---|---|
| BASIC | 2.0% | 0.1 | 50k | +5% | 20 |
| PRO | 1.5% | 0.2 | 50k | +7% | 50 |
| VALUE | 1.0% | 0.3 | 50k | +10% | 50 |

### Filtri FONDI EU UCITS (value_screener_fondi_eu.py)

| Piano | TER max | AUM min | Sharpe min | Perf 1Y min | Top N |
|---|---|---|---|---|---|
| BASIC | 1.0% | 50M€ | 0.1 | +5% | 20 |
| PRO | 1.5% | 10M€ | 0.0 | 0% | 50 |
| VALUE | 2.0% | 1M€ | -0.5 | -10% | 50 |

**Note Fondi EU:** TER e AUM dalla cache `fondi_eu_universe_cache.json` (più affidabili). AUM usato come proxy volume (fondi non hanno volume di borsa).

---

## 6. Pesi Score per Piano

Score calcolato da `batch_percentile_score()` in `screener_utils.py`: ogni metrica → percentile 0–100 rispetto agli altri selezionati → media pesata. Pesi in `config.json → scoring_weights`.

### AZIONI

| Metrica | BASIC | PRO | VALUE |
|---|---|---|---|
| Dividend Yield | **35%** | — | — |
| Var_1D_% | **25%** | 5% | — |
| ROE | 20% | 25% | 25% |
| EV/FCF | 10% | **35%** | **40%** |
| P/B | 10% | 20% | 15% |
| Net Debt/EBITDA | — | 15% | 20% |

*BASIC → rendimento immediato. PRO → qualità fondamentale. VALUE → deep value, costo debito.*

### ETF

| Metrica | BASIC | PRO | VALUE |
|---|---|---|---|
| Perf 3M % | **45%** | 10% | 5% |
| Performance 1Y | 20% | 30% | 25% |
| TER | 20% | 20% | **25%** |
| Sharpe Ratio | 15% | **40%** | **45%** |

*BASIC → momentum breve. PRO/VALUE → efficienza rischio/rendimento e costi.*

### FONDI US e FONDI EU *(pesi identici)*

| Metrica | BASIC | PRO | VALUE |
|---|---|---|---|
| Perf 3M % | **30%** | 5% | 5% |
| Performance 1Y | 30% | 25% | 15% |
| TER | 25% | 30% | **35%** |
| Sharpe Ratio | 15% | **40%** | **45%** |

---

## 7. Report Excel — Struttura

### Nomenclatura file

```
REPORTS_DAILY/
  Azioni_Screener_BASIC_20260626_230000.xlsx
  Azioni_Screener_PRO_20260626_230000.xlsx
  Azioni_Screener_VALUE_20260626_230000.xlsx
  ETF_Screener_BASIC_...xlsx            (×3)
  FONDI_Screener_BASIC_...xlsx          (×3)
  FONDI_EU_Screener_BASIC_...xlsx       (×3)
```

### Fogli per Excel

| # | Foglio | Contenuto | Inviato ai clienti? |
|---|---|---|---|
| 0 | 📖 Legenda | Guida metriche e Score (solo AZIONI) | ✅ |
| 1 | Dashboard | Filtri applicati, statistiche, breakdown mercato, Top 5 | ✅ |
| 2 | Top N per Score | Migliori N ordinati per Score decrescente | ✅ |
| 3 | Selezionati | Tutti i selezionati — colonne fisse ordinate per Score | ✅ |
| 4+ | Scartati per motivo | Archivio interno | ❌ Rimosso prima dell'invio |
| — | Non Validi / Errori | Archivio interno | ❌ Rimosso prima dell'invio |

La rimozione fogli scarto avviene in `_build_client_attachment()` in `email_notifier.py`: genera il file al volo prima dell'invio, NON modifica il file originale su disco.

### Colonne fisse foglio "Selezionati"

**AZIONI (30 colonne):**
`Ticker · Nome · Valuta · Settore · Industry · Mercato · Indice · Market Cap · P/B · ROE · EV/EBITDA · Free Cash Flow · Enterprise Value · Total Debt · Total Cash · EBITDA · Dividend Yield · Analyst Coverage · EV/FCF · Net Debt · Net Debt/EBITDA · Prezzo · Var_1D_% · Perf_1M_% · Perf_3M_% · Perf_6M_% · Perf_YTD_% · Perf_1Y_% · Data Dati · Score`

**ETF (20 colonne):**
`Ticker · ISIN · Nome · Categoria · Età (anni) · Tipo · Replica · Stelle MS · TER · Sharpe Ratio · Volume · Net Assets · Prezzo · Var_1D_% · Performance 1Y · Perf 3M % · Perf 6M % · Perf YTD % · Score · Data Dati`

**FONDI US (16 colonne):**
`Ticker · Nome · Categoria · TER · Sharpe Ratio · Volume · AUM · Prezzo · Var_1D_% · Performance 1Y · Perf 3M % · Perf 6M % · Perf YTD % · Stelle MS · Score · Data Dati`

### Formattazione numeri (tutti gli screener)

| Tipo valore | Formato output |
|---|---|
| Market Cap / AUM / FCF / EV / Debt / Cash / EBITDA | Leggibile: `78,8B` / `12,2M` / `450K` |
| TER | Percentuale 2 decimali: `0,35%` |
| ROE / Dividend Yield / Performance 1Y | Percentuale 1 decimale: `25,0%` |
| Var_1D_% / Perf 3M-6M-YTD % | 2 decimali con virgola: `-17,97%` |
| P/B / EV/EBITDA / EV/FCF / ND/EBITDA / Sharpe | Numerico 2 decimali |
| Score | 1 decimale |

---

## 8. Sistema Email

### Flusso invio

```
orchestrator.py
  ↓ (dopo ogni screener completato con exit_code=0)
  per ogni piano (BASIC / PRO / VALUE):
    → cerca file: REPORTS_DAILY/ dove nome.upper().startswith(TYPE+'_SCREENER_') and PIANO in nome.upper()
    → prende il più recente (sort reverse)
    → subprocess: python email_notifier.py TIPO PIANO FILENAME
      ↓
      → load_recipients_for_plan(tipo, piano)   ← legge clienti.json
      → _build_client_attachment(filepath)       ← rimuove fogli scarto
      → smtplib SMTP Gmail → invia a ogni destinatario
      → retry automatico 3 tentativi, 30s pausa se errore SMTP
```

### Conteggi ticker nel testo email (dinamici, calcolati a runtime)

| Tipo screener | Valore {NUM_TICKER} | Come calcolato |
|---|---|---|
| AZIONI | **2.625** | `len(ALL_AZIONI)` da ticker_lists_5000 |
| ETF | **4.245** | `len(ALL_ETF ∪ JustETF_preferred_ticker)` dedup |
| FONDI | **1.379** | `len(ALL_FONDI ∪ fondi_eu_yahoo_ticker)` dedup |
| FONDI_EU | **493** | count `fondi_eu_universe_cache.json` con yahoo_ticker |

### Destinatari per piano (26/06/2026)

| Report | Piano | N. | Chi riceve |
|---|---|---|---|
| AZIONI | BASIC | 5 | Newfrontiers, Laura Manicardi, Luigi, Luciano (lineexpress), **Admin** |
| AZIONI | PRO | 3 | Fuerte Info (marketing@), Paolo Paterlini, **Admin** |
| AZIONI | VALUE | 2 | Davide Moretti, **Admin** |
| ETF | BASIC | 3 | Luigi, Davide, **Admin** |
| ETF | PRO | 3 | Fuerte Info, Paolo, **Admin** |
| FONDI | BASIC | 3 | Laura Manicardi, Luciano (lineexpress), **Admin** |
| FONDI | PRO | 2 | Fuerte Info, **Admin** |

**Regola inclusione:** `stato in ("ATTIVO", "TESTER") AND piano_{tipo} == piano`. L'admin (`rioluc63@gmail.com`) è sempre aggiunto incondizionatamente.

### Alert email automatiche (separato dall'invio report)

Ogni screener invia autonomamente un'email di **alert all'admin** se rileva troppi errori di rete (DNS `query2.finance.yahoo.com` irraggiungibile). Solo all'admin, non ai clienti.

---

## 9. CRM Clienti

### Struttura clienti.json

```json
{
  "tester": [
    {
      "email": "...",
      "nome": "...",
      "stato": "TESTER",          // TESTER | ATTIVO | SOSPESO
      "piano_azioni": "PRO",      // NONE | BASIC | PRO | VALUE
      "piano_etf": "BASIC",
      "piano_fondi": "NONE",
      "piano_ordini": "NONE",
      "data_registrazione": "2026-06-01",
      "dati_fiscali": {...},
      "numero_fattura": "FVC-2026-0001",
      "gdpr": true,
      "whatsapp_optin": false
    }
  ],
  "clienti": [...]
}
```

### Utenti presenti (26/06/2026)

| Nome | Email | Stato | Azioni | ETF | Fondi |
|---|---|---|---|---|---|
| Fuerte Info | marketing@fuerteventurecapital.com | TESTER | PRO | PRO | — |
| Newfrontiers | newfrontiers65@gmail.com | TESTER | BASIC | — | — |
| Laura Manicardi | laura.manicardi65@gmail.com | TESTER | BASIC | — | BASIC |
| Paolo Paterlini | paolo.paterlini@tin.it | TESTER | PRO | PRO | — |
| Luigi | ltepe69@gmail.com | TESTER | BASIC | BASIC | — |
| Davide | d.moretti71@gmail.com | TESTER | VALUE | BASIC | — |
| Luciano | luciano.manicardi@lineexpress.it | **ATTIVO** | BASIC | — | BASIC |
| **Admin** | rioluc63@gmail.com | — | **Tutto** | **Tutto** | **Tutto** |

### Dashboard admin CRM — tab disponibili

1. **👥 Clienti** — tabella con KPI (totale/tester/clienti/attivi), gestione piani, dati fiscali, attivazione
2. **📊 Pipeline** — prospect e conversioni
3. **📧 Campagne Email** — integrazione Brevo
4. **📱 Social Media** — post e statistiche
5. **💬 WhatsApp** — opt-in e notifiche

### Operazioni CRM disponibili

- Aggiunta / modifica / eliminazione tester
- Attivazione cliente (TESTER → ATTIVO): genera automaticamente fattura PDF
- Upgrade piano: genera automaticamente nuova fattura
- Import/export CSV
- Modifica dati fiscali (Ragione Sociale, P.IVA, indirizzo)
- Toggle WhatsApp opt-in
- Contatore "destinatari email" aggiornato dinamicamente dall'elenco

---

## 10. Prezzi Servizi e Profili Cliente

### Prezzi (tutti i piani)

| Piano | Azioni | ETF | Fondi |
|---|---|---|---|
| **BASIC** | €29/mese | €29/mese | €29/mese |
| **PRO** | €39/mese | €39/mese | €39/mese |
| **VALUE** | €59/mese | €59/mese | €59/mese |

### 9 Profili Cliente (da Profili_Cliente_9_Servizi_20260604.md)

| Piano | Asset | Profilo | Orizzonte | Logica scoring |
|---|---|---|---|---|
| BASIC | Azioni | *"L'Investitore in Dividendi"* | 3–12 mesi | Dividend Yield 35% + momentum |
| PRO | Azioni | *"L'Analista Fondamentale Globale"* | 2–5 anni | EV/FCF 35% + ROE 25% |
| VALUE | Azioni | *"Il Value Investor Paziente"* | 10–30 anni | EV/FCF 40% + ROE 25% + ND/EBITDA 20% |
| BASIC | ETF | *"Il Risparmiatore Dinamico"* | 6–18 mesi | Perf 3M 45% (momentum) |
| PRO | ETF | *"Il Costruttore di Portafoglio"* | 3–7 anni | Sharpe 40% + Perf1Y 30% |
| VALUE | ETF | *"Il Cassettista Efficiente"* | 10–30 anni | Sharpe 45% + TER 25% |
| BASIC | Fondi | *"Il Delegatore Attivo"* | 6–18 mesi | Perf 3M 30% + Perf1Y 30% |
| PRO | Fondi | *"Il Selezionatore di Gestori"* | 3–7 anni | Sharpe 40% + TER 30% |
| VALUE | Fondi | *"Il Paziente Compounder"* | 10–30 anni | Sharpe 45% + TER 35% |

---

## 11. Sistema Fatture

| Aspetto | Dettaglio |
|---|---|
| **Generazione** | Automatica su: registrazione cliente, upgrade piano, attivazione admin |
| **Formato** | FPDF, A4, logo embedded base64, una sola pagina |
| **Numerazione** | `FVC-2026-XXXX` — contatore in `fatture_counter.json` (`{"ultimo": 18}`) |
| **Cartella** | `Robot Trader 2026/FATTURE/FVC-2026-XXXX.pdf` |
| **IBAN** | ES83 2100 1513 7202 0070 3406 — CaixaBank SA — BIC CAIXESBBXXX |
| **Download admin** | GET `/api/fattura/{numero}` (richiede sessione admin) |
| **Download cliente** | GET `/api/mia-fattura` (richiede sessione cliente, link in area riservata) |
| **Screener inclusi** | AZIONI, ETF, FONDI, FONDI_EU — tutti generano fattura |

---

## 12. Scheduling e Orchestrator

### Job automatici (scheduler_daemon.py)

| Job | Orario | Giorni | Argomenti orchestrator | Timeout |
|---|---|---|---|---|
| Screener AZIONI | 23:00 | lun–ven (5 gg) | `AZIONI` | 1h |
| Screener ETF+FONDI+EU | 23:30 | lun / mer / ven (3 gg) | `ETF FONDI FONDI_EU` | 2h |
| Social automation | 08:00 | lun / mer / ven | — | 5 min |

**Logica:** AZIONI giornaliere (alta volatilità). ETF+Fondi ogni 2 giorni (segnali stabili 24–48h).

### Orchestrator — Flusso completo

```
python orchestrator.py [AZIONI] [ETF] [FONDI] [FONDI_EU]
  ↓
  Per ogni screener selezionato (in sequenza):
    → subprocess: python value_screener_*.py
    → output real-time in console + log
    → timeout 2h forzato
    ↓ (exit_code == 0)
    Per ogni piano (BASIC / PRO / VALUE):
      → cerca file più recente in REPORTS_DAILY/ con pattern type_SCREENER_piano_*.xlsx
      → subprocess: python email_notifier.py TIPO PIANO FILE
        → retry automatico 3 volte, 30s tra tentativi
  ↓
  Notifica WhatsApp (se whatsapp_service disponibile)
```

### Regola matching file (critica — bug fix 26/06/2026)

```python
# CORRETTO — usa _SCREENER_ per evitare ambiguità FONDI vs FONDI_EU
f.upper().startswith(screener['type'] + '_SCREENER_') and piano in f.upper()

# SBAGLIATO (era prima del fix) — FONDI_ matchava anche FONDI_EU_
f.upper().startswith(screener['type'] + '_')
```

### Scheduled vs Manuale — Differenze

| Aspetto | Schedulato (BAT) | Manuale | Status |
|---|---|---|---|
| Python exe | Python314 hardcoded nel BAT | `python` in PATH | ⚠️ Verificare coincidano |
| Log | `logs/robot_trader_YYYYMMDD_HHMM.log` | Console PowerShell | Diverso per design |
| Screener | Tutti e 4 | Solo quelli specificati in args | Per design |
| File matching | `type_SCREENER_piano_*.xlsx` | Identico | ✅ Allineato |
| Conteggi email | Dinamici (runtime) | Identico | ✅ Allineato |
| Destinatari | ATTIVO + TESTER con piano | Identico | ✅ Allineato |

---

## 13. Dashboard Admin

**Accesso:** http://localhost:5000 → login con credenziali admin (`config.json → admin_password`)  
**Timeout sessione:** 8 ore fisso

### Tab disponibili

| Tab | Funzione |
|---|---|
| 🏠 Home | Stato sistema, KPI, last run screener, KB chatbot status, destinatari email |
| ⚙️ Servizi | 9 piani × configurazione filtri, profilo target (textarea), descrizione |
| 📊 Parametri | Soglie filtri screener modificabili live (aggiornano parametri.json) |
| 🗃️ Database | Universo 9.779 ticker — 3 subtab (Azioni/ETF/Fondi) con ricerca, dati live, ✕ rimozione |
| 🎯 CRM | 5 sub-tab: Clienti / Pipeline / Campagne Email / Social / WhatsApp |
| 📋 Ordini | Order Builder — gestione ordini clienti |
| 🔑 Sicurezza | Cambio password admin, gestione sessioni |

### Funzionalità tab Database

- **Ricerca:** filtra per ticker o gruppo
- **Carica dati (batch):** fetcha Nome/Prezzo/Var% per prime 30 righe visibili (salta ISIN)
- **Click per riga:** fetcha Nome/Prezzo/Var% di quel singolo ticker (highlight blu → verde)
- **Var% source:** `regularMarketChangePercent` (priorità) → fallback calcolo da `prev_close`
- **✕ Rimozione:** elimina ticker da `ticker_lists_5000.py` via regex, ricarica modulo a caldo
- **Link ticker:** YF normale → Yahoo Finance; ISIN puro → JustETF

---

## 14. Area Clienti

**Accesso:** http://localhost:5000/area-clienti → login con email + password

| Funzione | Dettaglio |
|---|---|
| **Dashboard** | Piano attivo, download report, accesso chatbot |
| **Report** | Download Excel filtrato (senza fogli scarto interni) |
| **Chatbot** | Claude Haiku — risponde in 5 lingue su prodotti, prezzi, FAQ |
| **Fattura** | Download PDF propria fattura (solo se `numero_fattura` nel profilo) |
| **Profilo** | Modifica dati, cambio password |
| **Timeout** | 24h sliding — rimane loggato se attivo |

---

## 15. Tab Database Universo Ticker

### Dati mostrati per riga

| Campo | Fonte | Note |
|---|---|---|
| Ticker | `ticker_lists_5000.py` + cache files | Simbolo o ISIN |
| Gruppo | Raggruppamento logico (indice/emittente/famiglia) | |
| Nome | yfinance `longName` o `shortName` | On-demand |
| Prezzo | yfinance `fast_info.last_price` o `info.regularMarketPrice` | On-demand |
| Var % | `info.regularMarketChangePercent` → fallback `(price-prev_close)/prev_close×100` | On-demand |
| Valuta | yfinance `fast_info.currency` | On-demand |

### Grouping ETF JustETF

Issuer estratto dal campo `name` nella cache: iShares, Amundi, Xtrackers, Vanguard, SPDR, WisdomTree, Invesco, Lyxor, Franklin, VanEck, Fidelity, HSBC, UBS, JPMorgan, BlackRock, DWS, Pictet, HANetf, ecc.  
Label: `"UCITS {Issuer}"` (es. "UCITS iShares", "UCITS Amundi")

### Grouping Fondi EU

Manager estratto dal campo `name`: Carmignac, Pictet, Amundi, DWS, Allianz, Fidelity, BlackRock, Schroders, PIMCO, Robeco, Nordea, Comgest, Oddo, Natixis, AXA, BNP, Candriam, Flossbach, GAM, M&G, Henderson, ecc.  
Label: `"EU {Manager}"` (es. "EU Carmignac", "EU Pictet")

---

## 16. Chatbot AI

### Architettura

```
POST /api/chat
  ↓
  Rate limit: 30 msg/h per IP
  ↓
  chat_service.chat(message, session_id, ip, api_key)
    → history sessione (max 10 msg, TTL 24h)
    → API Anthropic: model=claude-haiku-4-5-20251001, max_tokens=800
    → System prompt con prompt caching:
        8 regole comportamento
        8 esempi dialogo (IT/ES/EN/FR/DE)
        KB_CONTENT (4 file MD uniti, ~55.500 chars)
```

### Knowledge Base (KNOWLEDGE_BASE/)

| File | Contenuto |
|---|---|
| `kb_azienda.md` | Identità FVC, disclaimer, contatti — 5 lingue |
| `kb_prodotto.md` | Tutti i piani/filtri/prezzi/score — 5 lingue |
| `kb_faq.md` | FAQ accesso/report/pagamenti/orari — 5 lingue |
| `kb_glossario.md` | Termini finanziari + direzione metriche — 5 lingue |

### Parametri sessione

| Parametro | Valore |
|---|---|
| Rate limit | 30 msg/h per IP |
| Max history per sessione | 10 messaggi |
| Max lunghezza messaggio | 600 chars |
| TTL sessione | 24h |
| Max token risposta | 800 |

### Operazioni admin

- **Reload KB:** GET `/api/reload-kb` → ricarica i 4 file MD senza downtime
- **Status KB:** GET `/api/kb-status` → chars/file/orario ultimo caricamento
- **Box KB in dashboard home:** mostra stato in tempo reale, bottone ricarica

---

## 17. Social Automation

**Stato:** codice pronto — in attesa credenziali

### Scheduling

- Orario: **08:00** lun / mer / ven
- Trigger: `scheduler_daemon.py` → `social_automation.py`

### Flusso post social

```
social_automation.py
  ↓
  content_generator.py → Claude API (fallback 9 template statici IT+ES)
  ↓
  social_publisher.py:
    → Brevo SMTP (newsletter/email)
    → LinkedIn API (post profilo aziendale)
    → Meta Graph API (Facebook Page + Instagram)
```

### Credenziali necessarie (da configurare in config.json)

```json
{
  "brevo": { "api_key": "" },
  "linkedin": { "client_id": "", "client_secret": "", "access_token": "" },
  "meta": { "page_id": "", "page_access_token": "", "instagram_account_id": "" }
}
```

**Meta token:** manuale ogni 60 giorni (OAuth bloccato dal router). Instagram: 3 opzioni collegamento + permesso `instagram_content_publish`.

---

## 18. WhatsApp Business

**Stato:** codice pronto — in attesa account Meta verificato

### Funzionalità previste

| Notifica | Trigger | Destinatari |
|---|---|---|
| Screener pronto | Fine run orchestrator | Clienti/tester con `whatsapp_optin=true` |
| Morning brief | 08:00 lun-ven | Stessi |

### Configurazione necessaria (config.json)

```json
{
  "whatsapp": {
    "phone_number_id": "",
    "access_token": "",
    "verify_token": ""
  }
}
```

Richiede: account Meta Business verificato + numero di telefono dedicato + template messaggio approvato da Meta.

---

## 19. Order Builder

**Accesso:** admin → tab Ordini; cliente → area riservata

### Funzionalità

| Funzione | Dettaglio |
|---|---|
| **Prezzi live** | Fetch yfinance per ticker selezionati |
| **Costruzione ordine** | Quantità, prezzo limite, tipo ordine |
| **Export CSV IBKR** | Formato compatibile Interactive Brokers |
| **Export CSV Generico** | Formato standard |
| **Email bancaria MiFID II** | Testo formale per invio ordine via email alla banca |

---

## 20. Sicurezza e Autenticazione

### Admin

| Aspetto | Dettaglio |
|---|---|
| **Cookie** | `rt_admin=secrets.token_hex(20)` |
| **Storage** | In-memory dict `SESSIONS` — reset a ogni riavvio |
| **Timeout** | 8 ore fisso (non sliding) |
| **Password** | In `config.json → admin_password` — ⚠️ CAMBIARE da "123" |
| **Lock** | `threading.Lock()` su lettura/scrittura clienti.json |

### Cliente

| Aspetto | Dettaglio |
|---|---|
| **Cookie** | `rt_client` |
| **Storage** | In-memory dict `CLIENT_SESSIONS` — reset a ogni riavvio |
| **Timeout** | 24h sliding (si rinnova ad ogni richiesta) |
| **Password** | Hash SHA-256 in clienti.json |
| **Primo accesso** | Flag `must_change_password` → redirect cambio password obbligatorio |

### Scrittura atomica (clienti.json)

```python
# Pattern sicuro — no corruzione file su crash
with tempfile.NamedTemporaryFile(...) as tmp:
    json.dump(data, tmp)
os.replace(tmp.name, CLIENTI_FILE)
```

### NaN safety (yfinance)

```python
# Doppio livello di protezione
# Livello 1: _safe() in get_database_lookup
def _safe(v):
    f = float(v); return None if math.isnan(f) or math.isinf(f) else round(f, 2)

# Livello 2: sanitizer ricorsivo in _json() handler
# Converte ricorsivamente NaN/Inf in None prima di json.dumps()
```

---

## 21. Stato Attuale — Semaforo

### ✅ Operativo e funzionante

- **4 screener** operativi (Azioni 2.625 / ETF ~4.245 / Fondi US 886 / Fondi EU 493)
- **Database Universo Ticker**: 9.779 strumenti con 3 subtab
- **ISIN detection**: bottone verde JustETF per 1.530 ISIN senza ticker YF
- **Scheduling**: 3 job automatici con log su file
- **Email report**: conteggi dinamici, destinatari ATTIVO+TESTER, retry SMTP automatico
- **Rimozione ticker** (✕) con aggiornamento ticker_lists_5000.py a caldo
- **Var%**: priorità `regularMarketChangePercent` — funziona anche per ETF EU
- **Fogli Selezionati**: colonne fisse, formattazione leggibile, ordinati per Score
- **Sistema fatture PDF**: automatico, include FONDI_EU
- **Dashboard admin**: tutte le funzionalità operative
- **Area clienti**: login, download report, chatbot
- **Chatbot AI**: Claude Haiku + KB 5 lingue, reload a caldo
- **Order Builder**: CSV IBKR + email bancaria MiFID II
- **WhatsApp**: codice pronto (credenziali mancanti)
- **Log schedulatore**: `PYTHON_SCRIPTS/logs/robot_trader_YYYYMMDD_HHMM.log`

### 🔴 Blocca il lancio pubblico

1. **Cloudflare Tunnel** — senza questo il sito non è raggiungibile da internet
   - Scaricare `cloudflared.exe`, configurare UUID in `config.yml`
   - Aggiornare `config.json → base_url` a `https://www.fuerteventurecapital.com`

2. **Password admin** — ancora `"123"` in `config.json → admin_password`
   - Cambiare con stringa forte prima del go-live

### 🟡 In attesa credenziali

3. **Social Automation** — Brevo `api_key`, LinkedIn `client_id/secret`, Meta `page_id`
4. **WhatsApp Business** — account Meta verificato + numero dedicato + template approvati

### 🔑 Sicurezza — Azioni pendenti (da 16/06/2026)

5. **Ruotare API key Anthropic** (era esposta in log debug di sessione)
6. **Rigenerare App Password Gmail** (era in chiaro in config.json)

### 🔵 Nota operativa Python path

Verificare che `python` in PowerShell coincida con `C:\Users\lucia\AppData\Local\Programs\Python\Python314\python.exe` (usato dal BAT schedulato). In caso contrario i pacchetti installati potrebbero essere diversi.

---

## 22. Note Tecniche Critiche

- **Sessioni in-memory**: reset a ogni riavvio → ri-login necessario per admin e clienti
- **Modifica dashboard.py**: richiede riavvio processo Python completo (non basta logout/login)
- **`FONDI_BOUTIQUE`** = lista multi-famiglia in ticker_lists_5000.py — MAI chiamarla `FONDI_ALTRI` (nome precedente causa ImportError silenzioso che svuota il Database)
- **TER ETF EU**: nessun campo yfinance → proviene da `etf_universe_cache.json` (JustETF scraping)
- **TER Fondi EU**: dalla `fondi_eu_universe_cache.json` — più affidabile di yfinance per UCITS
- **Performance 1Y ETF**: yfinance restituisce fraction (0.12 = 12%) → ×100 nel foglio output
- **File matching orchestrator**: SEMPRE usare `type+'_SCREENER_'` — MAI `type+'_'` (FONDI_ ambiguo con FONDI_EU_)
- **Var%**: `regularMarketChangePercent` ha priorità — `prev_close` spesso None per ETF EU e fondi
- **ISIN puri**: 1.530 nel Database — rilevati con regex `^[A-Z]{2}[0-9A-Z]{10}$` sia in JS che Python backend — non mandati al lookup yfinance
- **NaN da yfinance**: bloccato in `_safe()` (get_database_lookup) + sanitizer ricorsivo in `_json` (tutti gli endpoint)
- **Dedup ETF ISIN**: `_dedup_by_isin()` in value_screener_etf.py — preferisce ACC su DIST, poi max volume
- **BASE_URL**: aggiornare `config.json → base_url` a `https://www.fuerteventurecapital.com` prima del go-live
- **ticker_lists_5000.py reload**: dopo rimozione ticker via ✕, il modulo viene ricaricato a caldo con `importlib.reload()` senza riavvio server

---

## 23. Comandi Operativi

### Avvio / Riavvio

```bat
REM Avvio completo (normale)
START_SISTEMA_PUBBLICO.bat

REM Solo dashboard
cd "C:\Users\lucia\Desktop\ROBOT TRADER 2026\PYTHON_SCRIPTS"
python dashboard.py

REM Solo scheduler
python scheduler_daemon.py
```

### Screener manuali

```bat
cd "C:\Users\lucia\Desktop\ROBOT TRADER 2026\PYTHON_SCRIPTS"
python orchestrator.py                   ← tutti e 4
python orchestrator.py AZIONI            ← solo azioni
python orchestrator.py ETF FONDI FONDI_EU← ETF + Fondi
```

### Aggiornamento universo

```bat
REM Aggiorna ETF JustETF (~2h)
python fetch_justetf_universe.py --update

REM Aggiorna Fondi EU (~2h)
python fetch_fondi_eu_universe.py --discover

REM Statistiche cache
python fetch_justetf_universe.py --stats
python fetch_fondi_eu_universe.py --stats
```

### Invio email manuale (singolo)

```bat
python email_notifier.py AZIONI BASIC Azioni_Screener_BASIC_20260626_230000.xlsx
python email_notifier.py ETF PRO ETF_Screener_PRO_20260626_233000.xlsx
```

### Verifica log schedulatore

```
PYTHON_SCRIPTS\logs\robot_trader_20260626_2300.log
```

---

## 24. Storico Implementazioni

| Data | Cosa |
|---|---|
| 01–02/06/2026 | Order Builder, fatturazione PDF, flusso B2C completo, landing page 5 lingue, GDPR |
| 03/06/2026 | Performance uniformità tra screener, 9-file output (3 piani × 3 screener), score percentile, FONDI 781 ticker |
| 04/06/2026 | Social automation (Brevo/LinkedIn/Meta), 9 profili cliente, Cloudflare Tunnel setup, WhatsApp codice base |
| 06/06/2026 | Chatbot AI: Claude Haiku + Knowledge Base 4 file 5 lingue, prompt caching |
| 14/06/2026 | Scheduling separato AZIONI/ETF+FONDI, timeout sessioni, ETF ACC universe espanso, fattura con IBAN CaixaBank, cartella FATTURE spostata a radice |
| 16/06/2026 | 20 bug fix: threading lock, scrittura atomica, NaN scoring, memory leak chat sessions, timeout SMTP, guard import |
| 17/06/2026 | Retry automatico SMTP in orchestrator (3 tentativi, 30s pausa) |
| 20/06/2026 | Domain rename fuertescreener.com → fuerteventurecapital.com; FONDI US 781→911 (+9 famiglie: AB, PGIM, Morgan Stanley, State Street, William Blair, Causeway, Hotchkis, Alger, Transamerica); nuovo screener FONDI EU UCITS con 472 fondi pronti |
| 22/06/2026 | Knowledge Base riscritta (5 lingue, universo 5.637); box KB in dashboard admin con reload a caldo |
| 23/06/2026 | Fogli Selezionati con colonne fisse + formattazione leggibile + ordinati per Score (AZIONI 30 col, ETF 20 col, FONDI US 16 col); Tab Servizi → textarea profilo target; servizi_config.json aggiornato con 9 profili investitore |
| 24/06/2026 | Debug completo: 12 bug risolti — orchestrator file matching, NaN in JSON, FONDI_ALTRI→BOUTIQUE, FONDI_EU in get_status() e fatture, _get_param ETF/Fondi, chat split maxsplit, filtro SOSPESO email |
| 25/06/2026 | 452 ticker morti rimossi da ticker_lists_5000.py; bottone ✕ rimozione manuale ticker + remove_ticker_from_lists(); click-per-riga con highlight visivo; Var% fix (priorità regularMarketChangePercent) |
| 26/06/2026 | Database espanso a 9.779 ticker (JustETF 4.630 ISIN + Fondi EU 536); ISIN detection (regex JS+Python, bottone verde JustETF, no fetch YF); conteggi email dinamici runtime; tester inclusi nelle email; bug fix orchestrator FONDI/FONDI_EU (pattern _SCREENER_); log schedulatore notturno |

---

*Fuerte Venture Capital SL · CIF B23881691 · Villaverde, Las Palmas de Gran Canaria, Spagna*  
*Documento master — aggiornato il 26/06/2026 — sostituisce tutti i precedenti file Stato_Progetto_RobotTrader2026_\*.md*
