# Stato Progetto — Robot Trader 2026

**Fuerte Venture Capital SL** · CIF B23881691 · marketing@fuerteventurecapital.com  
**Ultimo aggiornamento:** 14/06/2026  
**Path progetto:** `C:\Users\lucia\Desktop\Robot Trader 2026\PYTHON_SCRIPTS\`

---

## Stack Tecnico

- **Server:** `http.server.HTTPServer` stdlib Python — ZERO framework web
- **Dati:** `yfinance` + scraping justETF per ETF EU
- **Output:** `openpyxl` → Excel multi-sheet, `pandas` per lettura dashboard
- **Auth admin:** cookie `rt_admin=secrets.token_hex(20)`, in-memory dict, timeout **8 ore fisso**
- **Auth cliente:** cookie `rt_client`, dict `CLIENT_SESSIONS`, **sliding 24 ore**
- **Email:** Gmail SMTP (smtplib stdlib) — `newcapitalfuerte@gmail.com` — credenziali in `config.json → email{}`
- **Scheduling:** `scheduler_daemon.py` — 3 job separati (AZIONI 23:00 / ETF+FONDI 23:30 / social 08:00)
- **Fatture:** FPDF, cartella `FATTURE/` alla radice del progetto, IBAN CaixaBank ES83 2100 1513 7202 0070 3406

---

## File Principali

| File | Funzione |
|---|---|
| `dashboard.py` | Server HTTP unico — admin console + landing page + area clienti + Order Builder |
| `order_builder.py` | Order Builder — email bancaria MiFID II, CSV IBKR/Generico, prezzi live |
| `value_screener_azioni.py` | Screener azioni: 3.072 ticker, 23 mercati, output 3 Excel (BASIC/PRO/VALUE) |
| `value_screener_etf.py` | Screener ETF: 1.198 ETF EU ACC, dedup ISIN (preferisce ACC), output 3 Excel |
| `value_screener_fondi.py` | Screener fondi: 781 fondi, output 3 Excel (BASIC/PRO/VALUE) |
| `screener_utils.py` | Score bontà percentile — `batch_percentile_score()` condiviso tra tutti gli screener |
| `orchestrator.py` | Lancia screener selezionati + email per piano. Args: `AZIONI` / `ETF FONDI` / nessuno=tutti |
| `scheduler_daemon.py` | APScheduler — 3 job: AZIONI 23:00 lun-ven / ETF+FONDI 23:30 lun/mer/ven / social 08:00 |
| `email_notifier.py` | `python email_notifier.py TIPO PIANO FILENAME` — invia solo agli iscritti del piano |
| `social_automation.py` | Orchestratore social — genera draft, email approvazione, pubblica |
| `content_generator.py` | Genera testo post via Claude API (fallback 9 template statici IT+ES) |
| `social_publisher.py` | Brevo SMTP + LinkedIn API + Meta Graph API |
| `ticker_lists_5000.py` | Universo ticker: ALL_AZIONI 3.072 / ALL_ETF 1.198 / ALL_FONDI 781 |
| `clienti.json` | Database clienti con piano_azioni/etf/fondi/ordini + dati fiscali + GDPR + numero_fattura |
| `servizi_config.json` | Prezzi e caratteristiche piani v2.1 — include sezione Ordini |
| `config.json` | Config globale: SMTP, social credentials, whatsapp, scoring_weights, fattura (IBAN), base_url |
| `fatture_counter.json` | `{"ultimo": 18}` — contatore progressivo numeri fattura |
| `whatsapp_service.py` | Notifiche WhatsApp via Meta Cloud API — send_template, notify_screener_ready, notify_morning_brief |
| `chat_service.py` | Chatbot AI — Claude Haiku 4.5 + KB 4 file, rate limit 30 msg/h per IP |

---

## Cartelle Dati (radice progetto — NON dentro PYTHON_SCRIPTS)

```
Robot Trader 2026/
  FATTURE/          → FVC-2026-0001...0018.pdf — generate automaticamente da dashboard.py
  REPORTS_DAILY/    → Azioni/ETF/FONDI_Screener_PIANO_YYYYMMDD_HHMMSS.xlsx
  LOGS/
  BACKUPS/
  PYTHON_SCRIPTS/   → solo codice + config + clienti.json
```

---

## Universo Ticker (aggiornato 14/06/2026)

| Asset | Count | Note |
|---|---|---|
| ALL_AZIONI | 3.072 | USA, EU15, Nordici, JP, HK, Australia, Canada, India, Taiwan |
| ALL_ETF | 1.198 | Europa ACC: universo base + ETF_EUROPE_ACC_CORE (~60 nuovi settoriali/tematici/factor) |
| ALL_FONDI | 781 | 36 famiglie US: Vanguard, Fidelity, T.Rowe, American, Schwab, PIMCO, DFA, Dodge&Cox + altre |

---

## Scheduling Separato (implementato 14/06/2026)

| Job | Orario | Giorni | Comando | Timeout |
|---|---|---|---|---|
| Screener AZIONI | 23:00 | lun-ven (5 gg) | `orchestrator.py AZIONI` | 1h |
| Screener ETF+FONDI | 23:30 | lun/mer/ven (3 gg) | `orchestrator.py ETF FONDI` | 90 min |
| Social automation | 08:00 | lun/mer/ven | `social_automation.py` | 5 min |

**Logica:** AZIONI giornaliere (alta volatilità), ETF+FONDI ogni 2 giorni (segnali stabili).  
**orchestrator.py** accetta argomenti CLI: `python orchestrator.py AZIONI` / `python orchestrator.py ETF FONDI` / nessun argomento = tutti e 3.

---

## Sistema 9-File — IMPLEMENTATO

### Output per screener run

```
REPORTS_DAILY/
  Azioni_Screener_BASIC_YYYYMMDD_HHMMSS.xlsx
  Azioni_Screener_PRO_YYYYMMDD_HHMMSS.xlsx
  Azioni_Screener_VALUE_YYYYMMDD_HHMMSS.xlsx
  ETF_Screener_BASIC_YYYYMMDD_HHMMSS.xlsx
  ETF_Screener_PRO_YYYYMMDD_HHMMSS.xlsx
  ETF_Screener_VALUE_YYYYMMDD_HHMMSS.xlsx
  FONDI_Screener_BASIC_YYYYMMDD_HHMMSS.xlsx
  FONDI_Screener_PRO_YYYYMMDD_HHMMSS.xlsx
  FONDI_Screener_VALUE_YYYYMMDD_HHMMSS.xlsx
```

### Struttura Excel per piano

| Piano | Fogli |
|---|---|
| BASIC | Dashboard + Top 20 per Score |
| PRO | Dashboard + Top 50 per Score + Selezionati |
| VALUE | Dashboard + Top 50 per Score + Selezionati + Scartati per motivo + Non Validi |

---

## Sistema Fatture (implementato/aggiornato 14/06/2026)

- **Generazione automatica:** su registrazione nuovo cliente, upgrade piano, attivazione admin
- **PDF:** FPDF, A4, logo embedded base64, una sola pagina
- **Sezione bonifico:** Beneficiario / Banca / IBAN / BIC / Causale con numero fattura
- **IBAN:** ES83 2100 1513 7202 0070 3406 — CaixaBank SA — BIC CAIXESBBXXX
- **Cartella:** `Robot Trader 2026/FATTURE/FVC-2026-XXXX.pdf`
- **Numerazione:** contatore in `fatture_counter.json`, attuale = 18
- **Download admin:** GET `/api/fattura/{numero}` (richiede sessione admin)
- **Download cliente:** GET `/api/mia-fattura` (richiede sessione cliente — link 🧾 in area riservata)
- **Allegato email:** PDF allegato automaticamente alle email di attivazione e upgrade piano

---

## Soglie Filtri per Piano

### AZIONI

| Piano | Universe | EV/FCF | P/B | ROE | ND/EBITDA | Top N |
|---|---|---|---|---|---|---|
| BASIC | Blue chip (~702) | ≤18x | ≤3x | ≥0% | ≤4x | 20 |
| PRO | Universo completo 3.072 | ≤15x | ≤2x | ≥1% | ≤3x | 50 |
| VALUE | Universo completo 3.072 | ≤12x | ≤1x | ≥2% | ≤2x | 50 |

### ETF

| Piano | TER max | Sharpe min | Volume min | Perf 1Y min | Età min | Top N |
|---|---|---|---|---|---|---|
| BASIC | 0.50% | 0.3 | 100k | +5% | 5 anni | 20 |
| PRO | 0.35% | 0.4 | 100k | +7% | 3 anni | 50 |
| VALUE | 0.20% | 0.5 | 100k | +10% | 2 anni | 50 |

Tutti i piani ETF: `only_accumulating=True`, `only_physical=True`, dedup per ISIN (preferisce ACC).

### FONDI

| Piano | TER max | Sharpe min | Volume min | Perf 1Y min | Top N |
|---|---|---|---|---|---|
| BASIC | 2.0% | 0.1 | 50k | +5% | 20 |
| PRO | 1.5% | 0.2 | 50k | +7% | 50 |
| VALUE | 1.0% | 0.3 | 50k | +10% | 50 |

---

## 9 Profili Cliente

| # | Servizio | Piano | Prezzo |
|---|---|---|---|
| 1 | Azioni | BASIC | €29 |
| 2 | Azioni | PRO | €39 |
| 3 | Azioni | VALUE | €59 |
| 4 | ETF | BASIC | €29 |
| 5 | ETF | PRO | €39 |
| 6 | ETF | VALUE | €59 |
| 7 | Fondi | BASIC | €29 |
| 8 | Fondi | PRO | €39 |
| 9 | Fondi | VALUE | €59 |

---

## Chatbot AI con Knowledge Base

- **Modello:** `claude-haiku-4-5` — risposta rapida, costo minimo
- **KB:** 4 file MD in `KNOWLEDGE_BASE/` — kb_prodotto, kb_faq, kb_azienda, kb_glossario
- **Retrieval:** context injection (KB ≤15k token)
- **Caching:** prompt caching Anthropic → -90% costo input
- **Rate limit:** 30 msg/ora per IP
- **Endpoint:** `POST /api/chat` — pubblico
- **Costo stimato:** €1-2/mese per 1.000 conversazioni da 5 msg

---

## WhatsApp Business

- **File:** `whatsapp_service.py` — completo
- **Credenziali:** `config.json → whatsapp{}` — da compilare
- **Template:** `screener_pronto` (4 param) e `brief_mattutino` (3 param) — da approvare Meta
- **Stato:** IN ATTESA — mancano account Meta verificato + numero dedicato
- **Procedura:** `01_DOCUMENTAZIONE_OPERATIVA/WhatsApp_Business_Setup_Procedura.md`

---

## Infrastruttura — Cloudflare Tunnel

- **URL target:** `https://www.fuerteventurecapital.com`
- **Costo:** €0 — gratuito
- **File pronti:** `CLOUDFLARE_TUNNEL\` — bat scripts pronti, manca solo `cloudflared.exe` da scaricare
- **Stato:** DA FARE — procedura in 5 passi nel documento precedente

---

## Storico Implementazioni

| Data | Cosa |
|---|---|
| 01–02/06/2026 | Order Builder, fatturazione PDF base, flusso B2C, landing 5 lingue, GDPR |
| 03/06/2026 | Performance uniformità, 9-file, architettura 2-fase, dashboard plan-aware, FONDI 781 ticker |
| 04/06/2026 | Social automation, score bontà percentile, 9 profili cliente, Cloudflare Tunnel, WhatsApp |
| 06/06/2026 | Chatbot AI con Knowledge Base (Haiku + prompt caching) |
| 14/06/2026 | Scheduling separato AZIONI/ETF+FONDI, sessioni con timeout, cambio password volontario, ETF ACC +60 universo, dedup ISIN preferisce ACC, fattura IBAN+bonifico+P.IVA cliente, cartella FATTURE radice, download fattura area clienti |

---

## Note Tecniche Critiche

- **TER ETF EU:** nessun campo yfinance → justETF scraping via ISIN map
- **Performance 1Y ETF:** fraction (0.12=12%) → ×100 nel foglio output
- **Sessioni:** in-memory → reset a ogni riavvio server → re-login necessario
- **Admin password:** `"123"` — CAMBIARE PRIMA DEL GO-LIVE (`dashboard.py` riga ~68)
- **BASE_URL:** `config.json → base_url` — aggiornare a `https://www.fuerteventurecapital.com` al lancio
- **Dedup ETF ISIN:** `_dedup_by_isin()` in `value_screener_etf.py` — prima pool ACC, poi max volume
- **Email notifier:** `python email_notifier.py TIPO PIANO FILENAME` — cerca `piano_{tipo} == piano` in clienti.json

---

*Fuerte Venture Capital SL · CIF B23881691 · Villaverde, Las Palmas de Gran Canaria, Spagna*  
*Documento aggiornato il 14/06/2026*
