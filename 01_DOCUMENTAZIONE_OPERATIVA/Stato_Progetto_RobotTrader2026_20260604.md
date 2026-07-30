# Stato Progetto — Robot Trader 2026

**Fuerte Venture Capital SL** · CIF B23881691 · marketing@fuerteventurecapital.com  
**Ultimo aggiornamento:** 04/06/2026  
**Path progetto:** `C:\Users\lucia\Desktop\Robot Trader 2026\PYTHON_SCRIPTS\`

---

## Stack Tecnico

- **Server:** `http.server.HTTPServer` stdlib Python — ZERO framework web
- **Dati:** `yfinance` + scraping justETF per ETF EU
- **Output:** `openpyxl` → Excel multi-sheet, `pandas` per lettura dashboard
- **Auth admin:** cookie `rt_admin=secrets.token_hex(20)`, in-memory set, reset a ogni riavvio
- **Auth cliente:** cookie `rt_client`, dict `CLIENT_SESSIONS = {}`, stesso meccanismo
- **Email:** Gmail SMTP (smtplib stdlib) — credenziali in `config.json` → `email{}`
- **Scheduling:** `scheduler_daemon.py` — screener 23:00 lun-ven + social 08:00 lun/mer/ven

---

## File Principali

| File | Funzione |
|---|---|
| `dashboard.py` | Server HTTP unico — admin console + landing page + area clienti + Order Builder |
| `order_builder.py` | Order Builder — email bancaria MiFID II, CSV IBKR/Generico, prezzi live |
| `value_screener_azioni.py` | Screener azioni: 3072 ticker, 23 mercati, output 3 Excel (BASIC/PRO/VALUE) |
| `value_screener_etf.py` | Screener ETF: 678 ETF, output 3 Excel (BASIC/PRO/VALUE) |
| `value_screener_fondi.py` | Screener fondi: 1087 fondi, output 3 Excel (BASIC/PRO/VALUE) |
| `screener_utils.py` | Score bontà percentile — `batch_percentile_score()` condiviso tra tutti gli screener |
| `orchestrator.py` | Lancia i 3 screener in sequenza + invia email report |
| `scheduler_daemon.py` | APScheduler — screener 23:00 lun-ven + social automation 08:00 lun/mer/ven |
| `social_automation.py` | Orchestratore social — genera draft, email approvazione, pubblica |
| `content_generator.py` | Genera testo post via Claude API (fallback 9 template statici IT+ES) |
| `social_publisher.py` | Brevo SMTP + LinkedIn API + Meta Graph API |
| `ticker_lists_5000.py` | Universo ticker: ALL_AZIONI 3072, ALL_ETF 678, ALL_FONDI 1087 |
| `clienti.json` | Database clienti con piano_azioni/etf/fondi/ordini + dati fiscali + GDPR |
| `servizi_config.json` | Prezzi e caratteristiche piani v2.1 — include sezione Ordini |
| `config.json` | Config globale: SMTP, Stripe, social credentials, whatsapp credentials, scoring_weights, base_url |
| `whatsapp_service.py` | Notifiche WhatsApp via Meta Cloud API — send_template, notify_screener_ready, notify_morning_brief |

---

## Universo Ticker

| Asset | Count | Note |
|---|---|---|
| ALL_AZIONI | 3.072 | USA, EU15, Nordici, JP, HK, Australia, Canada, India, Taiwan |
| ALL_ETF | 678 | USA (394) + Europa multi-exchange (284) |
| ALL_FONDI | 1.087 | 36 famiglie US: Vanguard, Fidelity, T.Rowe, American, Schwab, PIMCO, DFA, Dodge&Cox + 28 altre |

---

## Sistema 9-File — IMPLEMENTATO

### Architettura 2-fase

**Phase 1:** unica passata yfinance su tutto l'universo → lista dati completa  
**Phase 2:** per ciascun piano (BASIC/PRO/VALUE) → applica filtri → scrive Excel separato

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

## Soglie Filtri per Piano

### AZIONI

| Piano | Universe | EV/FCF | P/B | ROE | ND/EBITDA | Top N |
|---|---|---|---|---|---|---|
| BASIC | Blue chip (~702: SP500+FTSE100+DAX+CAC+MIB+IBEX+SMI+AEX+Nikkei) | ≤18x | ≤3x | ≥0% | ≤4x | 20 |
| PRO | Universo completo 3072 | ≤15x | ≤2x | ≥1% | ≤3x | 50 |
| VALUE | Universo completo 3072 (17 mercati) | ≤12x | ≤1x | ≥2% | ≤2x | 50 |

### ETF (aggiornati 04/06/2026 — logica breve/medio/lungo)

| Piano | TER max | Sharpe min | Volume min | Perf 1Y min | Età min | Top N |
|---|---|---|---|---|---|---|
| BASIC | 0.50% (costo meno rilevante a breve) | 0.3 | 100k | +5% | 5 anni | 20 |
| PRO | 0.35% (equilibrio) | 0.4 | 100k | +7% | 3 anni | 50 |
| VALUE | 0.20% (ogni bp si capitalizza su 10+ anni) | 0.5 | 100k | +10% | 2 anni | 50 |

Tutti i piani ETF: `only_accumulating=True`, `only_physical=True`

### FONDI (aggiornati 04/06/2026 — logica breve/medio/lungo)

| Piano | TER max | Sharpe min | Volume min | Perf 1Y min | Top N |
|---|---|---|---|---|---|
| BASIC | 2.0% (accetta gestione attiva costosa) | 0.1 | 50k | +5% | 20 |
| PRO | 1.5% (equilibrio) | 0.2 | 50k | +7% | 50 |
| VALUE | 1.0% (efficienza costi sul lungo periodo) | 0.3 | 50k | +10% | 50 |

---

## Sistema Score Bontà — IMPLEMENTATO (04/06/2026)

**File:** `screener_utils.py` — funzione `batch_percentile_score(items, asset_type, plan_name)`

**Logica:** score percentile 0–100 calcolato in batch post-selezione. Per ogni metrica attiva: percentile rank tra tutti gli item del piano. Weighted average = Score finale.

**Direzioni fisse:** Dividend Yield / ROE / Var_1D_% / Perf 3M / Perf 1Y / Sharpe → alto=meglio. P/B / EV/FCF / Net Debt/EBITDA / TER → basso=meglio.

**Pesi modificabili** dalla dashboard (tab PARAMETRI → Sezione Score Bontà) o da `config.json → scoring_weights`.

### Pesi di default per orizzonte temporale

| Asset | Piano | Orizzonte | Score dominante |
|---|---|---|---|
| Azioni | BASIC | Breve (3–12 mesi) | Dividend Yield 35% + Var_1D_% 25% |
| Azioni | PRO | Medio (2–5 anni) | EV/FCF 35% + ROE 25% |
| Azioni | VALUE | Lungo (5–15 anni) | EV/FCF 40% + ROE 25% |
| ETF | BASIC | Breve (6–18 mesi) | Perf 3M 45% + Perf 1Y 20% |
| ETF | PRO | Medio (3–7 anni) | Sharpe 40% + Perf 1Y 30% |
| ETF | VALUE | Lungo (10–30 anni) | Sharpe 45% + TER 25% |
| Fondi | BASIC | Breve (6–24 mesi) | Perf 3M 30% + Perf 1Y 30% |
| Fondi | PRO | Medio (3–7 anni) | Sharpe 40% + TER 30% |
| Fondi | VALUE | Lungo (10–30 anni) | Sharpe 45% + TER 35% |

**Validazione matematica:** IUIT.L BASIC Score=95.7 verificato a mano.

---

## 9 Profili Cliente

Documento completo: `Profili_Cliente_9_Servizi_20260604.md` (stessa cartella)

| # | Servizio | Piano | Profilo | Orizzonte | Prezzo |
|---|---|---|---|---|---|
| 1 | Azioni | BASIC | L'Investitore in Dividendi | 3–12 mesi | €29 |
| 2 | Azioni | PRO | L'Analista Fondamentale Globale | 2–5 anni | €39 |
| 3 | Azioni | VALUE | Il Deep Value Investor Professionale | 5–15 anni | €59 |
| 4 | ETF | BASIC | Il Risparmiatore che Cavalca il Mercato | 6–18 mesi | €29 |
| 5 | ETF | PRO | Il Portfolio Manager Attivo | 3–7 anni | €39 |
| 6 | ETF | VALUE | Il Wealth Manager Istituzionale | 10–30 anni | €59 |
| 7 | Fondi | BASIC | Il Cliente della Banca | 6–24 mesi | €29 |
| 8 | Fondi | PRO | Il Consulente Finanziario Indipendente | 3–7 anni | €39 |
| 9 | Fondi | VALUE | Il Family Office o l'Istituzionale | 10–30 anni | €59 |

---

## WhatsApp Business — IMPLEMENTATO (04/06/2026 sera)

**Provider:** Meta WhatsApp Cloud API (ufficiale, numero tuo, €0 fino a 1.000 conversazioni/mese)  
**File:** `whatsapp_service.py`  
**Credenziali:** `config.json → whatsapp{}` (token, phone_number_id, waba_id, api_version, templates)

### Architettura

```
scheduler_daemon.py
  ├── 23:00 → orchestrator.py → [OK] → whatsapp_service.notify_screener_ready()
  └── 08:00 → social_automation.py → [OK] → whatsapp_service.notify_morning_brief()
```

### Template da approvare su Meta Business Manager

| Template | Trigger | Parametri |
|---|---|---|
| `screener_pronto` | Dopo screener 23:00 | {{1}}=nome, {{2}}=piani, {{3}}=data, {{4}}=link |
| `brief_mattutino` | Dopo social 08:00 | {{1}}=nome, {{2}}=titolo, {{3}}=link |

**Testo `screener_pronto`** (da sottomettere a Meta):
```
Ciao {{1}}, i tuoi segnali Robot Trader ({{2}}) del {{3}} sono pronti.

Accedi alla tua area clienti:
{{4}}

Fuerte Venture Capital — Robot Trader 2026
Rispondi STOP per disattivare le notifiche.
```

### Opt-in clienti

- Campo `whatsapp_optin` in `clienti.json` (default: assente/false)
- Dashboard admin → tab Clienti → bottone 📱 per ogni cliente (verde se attivo)
- Conferma richiesta prima di attivare (promemoria consenso GDPR)
- API: `POST /api/clienti/whatsapp` `{cat, idx, optin: bool}`

### Procedura go-live WhatsApp (5 passi — una sola volta)

**PASSO 1** — Meta Business Manager: crea/verifica azienda con CIF B23881691  
**PASSO 2** — WhatsApp Business Account: aggiungi numero dedicato  
**PASSO 3** — Meta Developer App → aggiungi prodotto "WhatsApp" → ottieni token permanente e phone_number_id  
**PASSO 4** — Sottoponi template `screener_pronto` e `brief_mattutino` per approvazione Meta (~24-48h)  
**PASSO 5** — Compila in `config.json`:
```json
"whatsapp": {
  "token": "EAAG...",
  "phone_number_id": "123456789",
  "waba_id": "987654321"
}
```

### Test
```bash
python whatsapp_service.py                        # lista clienti opt-in
python whatsapp_service.py test +39XXXXXXXXXX     # invia template di test
```

---

## Infrastruttura — Cloudflare Tunnel (scelta per il go-live)

**URL pubblico target:** `https://www.fuerteventurecapital.com`  
**Costo:** €0 — Cloudflare Tunnel gratuito  
**Siti che linkano:** `www.fuerteventurecapital.com` e `www.newcapitalfuerte.com`

### Architettura a regime

```
PC Windows (sempre acceso)
  ├── dashboard.py         → localhost:5000
  ├── scheduler_daemon.py  → screener 23:00 lun-ven + social 08:00 lun/mer/ven
  └── cloudflared tunnel   → https://www.fuerteventurecapital.com
                                    ↑
              fuerteventurecapital.com  (link sezione Robot Trader)
              newcapitalfuerte.com      (link sezione Robot Trader)
```

### File pronti in `CLOUDFLARE_TUNNEL\`

| File | Funzione |
|---|---|
| `cloudflared.exe` | **DA SCARICARE** da github.com/cloudflare/cloudflared/releases |
| `config_template.yml` | Template — compilare con UUID tunnel |
| `1_SETUP_TUNNEL.bat` | Login Cloudflare + crea tunnel → UUID |
| `2_CONFIGURA_DNS.bat` | Aggiunge CNAME su Cloudflare DNS |
| `3_AVVIA_TUNNEL.bat` | Avvia tunnel manualmente |
| `INSTALLA_SERVIZIO_WINDOWS.bat` | Installa come servizio Windows (avvio automatico al boot) |

**Avvio completo:** `START_SISTEMA_PUBBLICO.bat` (root progetto)

### Procedura go-live (5 passi — una sola volta)

**PASSO 1** — Scarica `cloudflared-windows-amd64.exe`, rinominalo `cloudflared.exe`, mettilo in `CLOUDFLARE_TUNNEL\`

**PASSO 2** — Esegui `1_SETUP_TUNNEL.bat` → browser apre Cloudflare → seleziona `www.fuerteventurecapital.com` → annota UUID

**PASSO 3** — Apri `config_template.yml`, sostituisci `TUNNEL_UUID_QUI` (×2) con l'UUID, salva come:
```
C:\Users\lucia\.cloudflared\config.yml
```

**PASSO 4** — Esegui `2_CONFIGURA_DNS.bat` → aggiunge CNAME automaticamente

**PASSO 5** — Aggiorna `PYTHON_SCRIPTS\config.json`:
```json
"base_url": "https://www.fuerteventurecapital.com"
```
E nella sezione `social`:
```json
"brevo":    { "base_url": "https://www.fuerteventurecapital.com" },
"linkedin": { "redirect_uri": "https://www.fuerteventurecapital.com/api/linkedin/callback" },
"meta":     { "redirect_uri": "https://www.fuerteventurecapital.com/api/meta/callback" }
```

---

## ❌ Da fare prima del lancio

### Critico (blocca il lancio)

| # | Cosa | Dove |
|---|---|---|
| 1 | Eseguire procedura Cloudflare Tunnel (5 passi sopra) | `CLOUDFLARE_TUNNEL\` |
| 2 | Cambiare password admin "123" | `dashboard.py` riga 61: `ADMIN_PASSWORD = "123"` |
| 3 | Inserire chiavi Stripe | `dashboard.py` riga 3061: `STRIPE_SECRET_KEY = ""` |
| 4 | Verificare `marketing@fuerteventurecapital.com` attiva | Email provider |

### Social Automation (codice pronto — mancano le credenziali)

| # | Cosa | Config |
|---|---|---|
| 5 | Account Brevo | `config.json → social.brevo` (api_key, smtp_login, smtp_password, list_ids) |
| 6 | LinkedIn Company Page FVC + Developer App | `config.json → social.linkedin` (client_id, client_secret, org_id) |
| 7 | Facebook Page + Instagram Business + Meta App | `config.json → social.meta` (app_id, app_secret, page_id, ig_user_id) |
| 8 | Anthropic API key (per generazione testi AI) | `config.json → social.anthropic.api_key` |
| 9 | Aggiornare `social.brevo.base_url` al dominio pubblico | Dopo PASSO 5 Cloudflare |
| 10 | Reminder rinnovo token LinkedIn ogni 60 giorni | Calendario |

### WhatsApp Business (codice pronto — mancano credenziali Meta + approvazione template)

| # | Cosa | Dove |
|---|---|---|
| 11 | Meta Business Manager verificato (CIF B23881691) | business.facebook.com |
| 12 | WhatsApp Business Account + numero dedicato | Meta Business |
| 13 | Token permanente + phone_number_id | `config.json → whatsapp.token / phone_number_id` |
| 14 | Template `screener_pronto` approvato da Meta | Meta Business Manager → Template messaggi |
| 15 | Template `brief_mattutino` approvato da Meta | Meta Business Manager → Template messaggi |
| 16 | Raccogliere opt-in dai clienti (consenso GDPR esplicito) | Dashboard admin → tab Clienti → bottone 📱 |

### Qualità (non blocca il lancio)

| # | Cosa |
|---|---|
| 11 | Deduplicazione ETF per ISIN (stesso ETF su più exchange selezionato più volte) |
| 12 | Reset password per clienti (attualmente solo l'admin può reimpostare) |
| 13 | Sessioni admin non scadono automaticamente |
| 14 | Fattura PDF da collegare a Stripe quando attivo |
| 15 | Verificare CIF B23881691 nel Registro Mercantil spagnolo |

---

## Note Tecniche Critiche

**TER conventions yfinance:**
- ETF USA: `netExpenseRatio` → già in % (0.0945 = 0.0945%)
- Fondi: `annualReportExpenseRatio` → decimale (0.0035 = 0.35%) → filtro usa `ter > ter_max/100`
- ETF europei: nessun campo TER → fallback justETF scraping via ISIN map

**Performance 1Y:**
- ETF: fraction (0.12 = 12%) → moltiplicare ×100 nel foglio Top N
- Azioni/Fondi: già in % (12.34 = 12.34%)

**BASE_URL:** letto da `config.json → base_url` (o env var `BASE_URL`). Per go-live: aggiornare solo config.json.

**HTML dashboard:** raw string `r"""..."""` — le `{` e `}` in JS singole. Variabili Python via `.replace('__PLACEHOLDER__', valore)`.

**Sessioni:** in-memory → reset a ogni riavvio server → re-login necessario dopo restart.

---

## Chatbot AI con Knowledge Base — Sessione 06/06/2026

### Architettura

```
Browser (widget floating bottom-right)
    │  POST /api/chat
    ▼
dashboard.py  →  chat_service.py  →  Claude API (Haiku)
                      │                    ↑
                      └── KNOWLEDGE_BASE/  (caricata a startup, cachata)
                              kb_prodotto.md   ← piani, prezzi, filtri, 9 profili
                              kb_faq.md        ← domande frequenti operative
                              kb_azienda.md    ← info Fuerte VC, contatti, disclaimer
                              kb_glossario.md  ← EV/FCF, Sharpe, TER, P/B, ROE…
```

### Scelte tecniche

| Decisione | Scelta | Motivo |
|---|---|---|
| Modello | `claude-haiku-4-5` | Risposta rapida (<1s), costo minimo |
| KB retrieval | Context injection | KB ≤15k token — nessuna dipendenza esterna, no vector DB |
| Ottimizzazione costo | Prompt caching Anthropic | KB cachata → −90% costo token input |
| Sessione | `CHAT_SESSIONS = {}` in memoria | Stesso pattern già usato per admin/clienti |
| Rate limiting | 30 msg/ora per IP | Protezione endpoint pubblico |
| Widget | Float bottom-right | Non invasivo, su landing + area clienti |
| Lingue | IT + ES (priorità) | Mercato target Fuerte VC |

### Nuovi file

| File | Funzione |
|---|---|
| `chat_service.py` | Logica conversazione, Claude API con prompt caching, cronologia, rate limit |
| `KNOWLEDGE_BASE/kb_prodotto.md` | Piani BASIC/PRO/VALUE, prezzi, filtri screener, 9 profili cliente |
| `KNOWLEDGE_BASE/kb_faq.md` | Domande frequenti: accesso report, Order Builder, pagamenti, privacy |
| `KNOWLEDGE_BASE/kb_azienda.md` | Chi è Fuerte VC, CIF B23881691, marketing@fuerteventurecapital.com, disclaimer MiFID |
| `KNOWLEDGE_BASE/kb_glossario.md` | Termini finanziari: EV/FCF, P/B, ROE, ND/EBITDA, TER, Sharpe, Percentile Score |

### Modifiche a `dashboard.py`

- Nuovo endpoint `POST /api/chat` — pubblico, protetto da rate limiting per IP
- Widget HTML/CSS/JS iniettato in `LANDING_HTML` e `AREA_CLIENTI_HTML`
- Caricamento KB a startup (`_load_knowledge_base()`)

### Endpoint

```
POST /api/chat
Body: { "message": "...", "session_id": "uuid", "lang": "it" }
Response: { "reply": "...", "session_id": "..." }
```

### Costo stimato (con prompt caching)

| Scenario | Costo per messaggio |
|---|---|
| Cache miss (1° messaggio sessione) | ~€0.0015 |
| Cache hit (messaggi successivi) | ~€0.00015 |
| 1.000 conversazioni/mese × 5 msg | ~€1–2/mese |

### Configurazione richiesta

```json
// config.json → social.anthropic.api_key  (già presente, da compilare)
"anthropic": { "api_key": "sk-ant-..." }
```

---

## Storico implementazioni

| Data | Cosa |
|---|---|
| 01–02/06/2026 | Order Builder, fatturazione PDF, flusso B2C, landing 5 lingue, GDPR |
| 03/06/2026 (mattina) | Performance uniformità, colonne Excel ottimizzate, FONDI 1087 ticker |
| 03/06/2026 (sera) | Sistema 9-file, architettura 2-fase, dashboard plan-aware |
| 04/06/2026 (mattina) | Social automation (Brevo+LinkedIn+Meta+Claude API), config.json social |
| 04/06/2026 (pomeriggio) | Score bontà percentile, taratura parametri breve/medio/lungo, 9 profili cliente |
| 04/06/2026 (sera) | Fix scheduler, cartelle ORDINI/SOCIAL_DRAFTS, pagina /privacy GDPR, BASE_URL centralizzato, Cloudflare Tunnel, WhatsApp Business Cloud API |
| 06/06/2026 | Chatbot AI con Knowledge Base (context injection + prompt caching, claude-haiku-4-5) |

---

*Fuerte Venture Capital SL · CIF B23881691 · Villaverde, Las Palmas de Gran Canaria, Spagna*  
*Documento aggiornato il 06/06/2026 — da aggiornare ad ogni sessione di sviluppo*
