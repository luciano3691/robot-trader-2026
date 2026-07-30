# Stato Progetto — Robot Trader 2026

**Fuerte Venture Capital SL** · CIF B23881691 · marketing@fuerteventurecapital.com  
**Ultimo aggiornamento:** 04/07/2026  
**Path progetto:** `C:\Users\lucia\Desktop\Robot Trader 2026\PYTHON_SCRIPTS\`

---

## Modifiche applicate — 04/07/2026

### Order Builder — Dati fiscali cliente, banca, IBAN, nome gestore ✅ TESTATO

#### Problema risolto
Il form `/ordine-bancario` era incompleto: mancavano i dati fiscali del cliente (visibili), il nome del gestore bancario (persona fisica), e l'IBAN del conto cliente.

#### Modifiche `dashboard.py`

| Componente | Modifica |
|---|---|
| HTML form | Nuova card **"Dati del Cliente Ordinante"** prima della card "Destinatario & Invio" |
| Campi nuovi | `ag_indirizzo`, `ag_cap`, `ag_citta`, `ag_paese`, `ag_codice_fiscale`, `ag_p_iva`, `ag_telefono` |
| JS `initAnagrafica()` | Pre-compila i campi da `CLIENT_ANAGRAFICA` (profilo cliente) al caricamento pagina |
| JS `getAnagraficaFromForm()` | Raccoglie i dati fiscali dal form prima dell'invio |
| Card "Destinatario & Invio" | Aggiunto `nome_gestore` (obbligatorio) e `bank_iban` (IBAN conto cliente) |
| `sendOrder()` | Validation su `nome_gestore`; invia `nome_gestore`, `bank_iban`, `anagrafica` dal form |
| `showPreview()` | Anteprima mostra nome gestore e IBAN |
| Backend `/api/ordine/invia` | Salva `nome_gestore` e `bank_iban` nel JSON archivio ordine |
| Backend `/api/ordine/invia` | **Aggiorna `clienti.json`** con i dati fiscali non vuoti del form (merge selettivo) |

#### Modifiche `order_builder.py`

| Componente | Modifica |
|---|---|
| `genera_email_html()` | Sezione "1. Dati Identificativi" — aggiunta seconda riga con: Banca, Nome Gestore, IBAN Conto Cliente |
| `genera_email_html()` | Blocco "Dati Cliente Ordinante" — sempre visibile (rimossa condizione "solo se dati non vuoti") |
| Docstring | Aggiornata con i nuovi campi `nome_gestore`, `bank_nome`, `bank_iban`, `anagrafica` |

#### Comportamento salvataggio dati fiscali
Quando il cliente invia un ordine con campi anagrafica compilati:
- I dati vengono salvati nel JSON ordine (`ORDINI/<email>/ORD-xxx.json`) ✅
- I campi **non vuoti** aggiornano anche `clienti.json` → al prossimo ordine i campi sono pre-compilati ✅
- Merge selettivo: un campo vuoto nel form non sovrascrive il dato già esistente nel profilo ✅

---

### Test invio email ordine ✅ SUPERATO

**Test 1 — Invio base**
- To: `luciano.manicardi@lineexpress.it`
- Risultato: email ricevuta ✅

**Test 2 — Verifica CC al cliente**
- To: `luciano.manicardi@lineexpress.it` (banca)
- CC: `rioluc63@gmail.com` (cliente)
- Risultato: email ricevuta su **entrambe** le caselle ✅

**Stack SMTP verificato:**
- Host: `smtp.gmail.com:587` (STARTTLS)
- Login: `newcapitalfuerte@gmail.com`
- App Password: configurata in `config.json → email → app_password`
- Ereditata da `order_builder.py` tramite variabili d'ambiente impostate in `dashboard.py` (righe 40-48)

---

---

### Chatbot Abbonati — Assistente Report con dati screener ✅ IMPLEMENTATO

#### Funzionalità
Gli abbonati nell'area clienti hanno ora un chatbot dedicato (icona blu, in basso a destra) che:
- Risponde a domande su singoli ticker: "LLY è nel report PRO?" "Perché TSLA non è nel report VALUE?"
- Fornisce dati statistici (Score, presenza/assenza, motivo scarto) senza dare consigli di acquisto (MiFID II)
- Conosce i dati di TUTTI e 12 i piani (4 tipi × 3 livelli), indipendentemente dal piano del cliente
- Risponde in 5 lingue come il chatbot pubblico

#### Architettura

**`chat_service.py`** — nuove funzioni:
- `_load_kb_reports()` — carica `KNOWLEDGE_BASE/kb_reports.md` (aggiornata ogni notte dall'orchestrator)
- `KB_REPORTS_CONTENT` — global con il contenuto dei report correnti
- `SYSTEM_PROMPT_ABBONATI_BASE` — system prompt specifico per abbonati (con regole MiFID II adattate)
- `chat_abbonati(message, session_id, ip, api_key, client_nome, piani_attivi)` — funzione pubblica
- `_call_claude_abb()` — chiama Haiku con system prompt: KB generale + report data (cacheable con prompt caching)
- `_check_rate_abb()`, `_get_or_create_session_abb()` — rate limit e sessioni separate per abbonati
- `reload_kb()` aggiornato — ricarica anche `KB_REPORTS_CONTENT`

**`orchestrator.py`** — nuove funzioni:
- `genera_kb_reports()` — legge i report Excel più recenti da `REPORTS_DAILY/`, genera `KNOWLEDGE_BASE/kb_reports.md`
  - Selezionati (tutti i piani): colonne Ticker, Nome, Score
  - Scartati (solo piano VALUE): Ticker + Motivo Scarto
  - Chiamata HTTP a `localhost:8080/api/internal/reload-kb` per aggiornare KB live
- Viene chiamata automaticamente al termine di ogni run del orchestrator

**`dashboard.py`** — modifiche:
- `CHAT_ABB_WIDGET_HTML` — widget blu (distinguibile dal chatbot pubblico giallo)
- Area clienti ora inietta `CHAT_ABB_WIDGET_HTML` (non più quello pubblico giallo)
- Endpoint `POST /api/chat-abbonati` — richiede autenticazione client, recupera nome e piani dal profilo
- Endpoint `POST /api/internal/reload-kb` — solo localhost, usato dall'orchestrator per aggiornare KB live

#### KB Reports (`kb_reports.md`)
- **Dimensione:** ~534KB (~133K tokens)
- **Scartati VALUE:** 7.060 righe con Ticker + Motivo Scarto
- **Selezionati tutti i piani:** 2.138 righe
- **Prompt caching:** block "fixed system" = KB + report data (uguale per tutti i client → cache hit)
- **Contesto client:** iniettato nel primo messaggio della sessione (non nel system prompt → non rompe il cache)
- **Aggiornamento:** ogni notte dopo l'orchestrator, reload automatico senza riavvio server

#### File generato
`KNOWLEDGE_BASE/kb_reports.md` — creato manualmente il 04/07/2026 con i dati correnti

---

### KB Profili Investitore — `kb_profili.md` ✅ AGGIUNTO

**File:** `KNOWLEDGE_BASE/kb_profili.md` — 19.7KB, caricato nel chatbot pubblico e abbonati

**Contenuto:**
- Matrice di decisione rapida (Step 1: asset class, Step 2: orizzonte/esperienza, Step 3: segnali dialogo)
- 9 profili dettagliati: nome, chi è, cosa cerca, perché quel piano, segnali di riconoscimento, upgrade path
- Nota Fondi EU UCITS (stessi profili Fondi US, per investitori europei)
- 5 combinazioni di piani consigliate (principiante, attivo, professionale, con ordini, europeo)
- 6 obiezioni comuni con risposte pronte
- Tabelle riassuntive in IT/ES/EN/FR/DE

**Chat_service.py:** `_load_kb()` ora carica 5 file: kb_azienda + kb_prodotto + kb_faq + kb_glossario + **kb_profili**

---

### Unificazione Knowledge Base — 3 file .docx convertiti in .md ✅ COMPLETATO

**Cartella sorgente:** `01_DOCUMENTAZIONE_OPERATIVA/Knowledge Base/` (3 .docx + 4 Excel)
**Cartella KB chatbot:** `PYTHON_SCRIPTS/KNOWLEDGE_BASE/` — unica cartella letta dal chatbot

**File aggiunti alla KB:**

| File | Dimensione | Contenuto |
|---|---|---|
| `kb_metriche.md` | 9.6KB | Tutte le metriche screener con formule, soglie, pesi score per tutti i 9 piani |
| `kb_educazione_etf.md` | 7.2KB | Guida selezione ETF: TER, AUM, età, tracking difference, replica, ACC/DIST, UCITS, spread |
| `kb_mercati_globali.md` | 26KB | Mercati globali: struttura gerarchica, attori, indici, vincoli istituzionali, fondi sovrani, glossario |

**Chat_service.py aggiornato (sessione mattina):** `_load_kb()` ora carica **8 file**: kb_azienda + kb_prodotto + kb_faq + kb_glossario + kb_profili + **kb_metriche + kb_educazione_etf + kb_mercati_globali**

Gli Excel della cartella sorgente erano già i report VALUE del 04/07 — già inclusi in `kb_reports.md` tramite `genera_kb_reports()`.

---

### Rimozione parametri proprietari da tutta la comunicazione ✅ COMPLETATO

**Principio adottato:** i parametri numerici di screening (soglie EV/FCF, P/B, ROE, TER, Sharpe per piano; pesi % dello score) sono **segreti industriali** — cambiano nel tempo e non devono mai comparire in KB, email, report o risposte del chatbot. I nomi delle metriche (EV/FCF, ROE, ecc.) restano — sono conoscenza finanziaria pubblica.

**File riscritti:**

| File | Cosa è stato rimosso |
|---|---|
| `kb_metriche.md` | Tutte le soglie numeriche per piano (es. "VALUE: EV/FCF ≤ 12x"), tutti i pesi % dello score |
| `kb_profili.md` | Tutte le soglie numeriche nelle sezioni "Perché X è giusto per lui", tutti i pesi % score, conteggi titoli selezionati |
| `kb_prodotto.md` | Intera tabella filtri per piano (`BASIC 18x / PRO 15x / VALUE 12x...`), intera tabella pesi score (`BASIC: DY 35%...`) |
| `chat_service.py` | Esempio TSLA: rimossa soglia numerica ("EV/FCF ≤ 12x" → "EV/FCF troppo alto rispetto alla soglia") |

**Sostituzione score weights in KB:**
> *"I pesi specifici sono parametri proprietari di Robot Trader 2026 e non vengono divulgati."*

---

### Conteggi universo dinamici — sistema placeholder ✅ IMPLEMENTATO

**Problema:** i conteggi dell'universo ticker (`2.625 azioni`, `1.174 ETF`, ecc.) erano hardcoded in KB, email e chatbot — diventavano obsoleti a ogni aggiornamento.

**Soluzione implementata in `chat_service.py`:**

```python
# Nuove funzioni
_load_universe_counts() → dict   # legge ticker_lists_5000.py + etf_universe_cache.json + fondi_eu_universe_cache.json
_fmt_n(n)                         # formatta con punti: 2.625
_apply_counts(text, c)            # sostituisce {N_AZIONI}, {N_ETF}, {N_FONDI_US}, {N_FONDI_EU}, {N_TOTALE}

UNIVERSE_COUNTS = _load_universe_counts()   # caricato a import time
```

**Placeholder nei file KB e negli esempi chatbot:**
- `{N_AZIONI}` — ticker azioni (da `ALL_AZIONI`)
- `{N_ETF}` — ETF (da `ALL_ETF` + `etf_universe_cache.json`)
- `{N_FONDI_US}` — fondi US (da `ALL_FONDI` + fondi eu yahoo_ticker)
- `{N_FONDI_EU}` — fondi EU UCITS (da `fondi_eu_universe_cache.json`)
- `{N_TOTALE}` — somma di tutti

**`_load_kb()` aggiornato:** chiama `_load_universe_counts()` e applica `_apply_counts()` a tutto il testo KB prima di restituirlo.

**`reload_kb()` aggiornato:** aggiorna `UNIVERSE_COUNTS`, ricarica KB con conteggi freschi, ricostruisce `SYSTEM_PROMPT` con esempi aggiornati.

**File KB aggiornati:** `kb_profili.md` e `kb_prodotto.md` — tutti i conteggi hardcoded sostituiti con placeholder.

---

### KB Teoria dell'Investimento — `kb_teoria_investimento.md` ✅ AGGIUNTO

**File:** `KNOWLEDGE_BASE/kb_teoria_investimento.md` — 19.8KB

**Contenuto:**
- 7 pilastri fondamentali dell'investimento (Value Investing, Diversificazione, Orizzonte Temporale, Costi, Rischio, Psicologia, Analisi Fondamentale) con formule, esempi pratici e collegamento al sistema Robot Trader
- 6 libri consigliati (Graham, Malkiel, Greenblatt, Burrough, Lynch, Fisher) con capitoli chiave e tempo di lettura
- Canali YouTube (IT e EN) e siti web gratuiti per formazione autonoma
- Tabella degli errori comuni dell'investitore con contromisura
- Framework decisionale a 5 domande per valutare qualsiasi investimento
- Glossario 30+ termini

**Chat_service.py:** `_load_kb()` ora carica **9 file** (aggiunto `kb_teoria_investimento`)

---

### Tab KB e Onboarding — Dashboard Admin ✅ IMPLEMENTATO

**Due nuovi tab aggiunti alla barra di navigazione admin** (`dashboard.py`):

#### Tab 📚 KB
- Griglia card con tutti i file `.md` presenti in `KNOWLEDGE_BASE/`
- Per ogni file: nome, dimensione, data/ora ultima modifica ("N ore fa")
- Bottone **↺ Ricarica KB** — chiama `/api/reload-kb`, aggiorna la griglia dopo il ricaricamento
- Caricamento lazy: i file vengono letti al primo click sulla tab

**Endpoint backend aggiunto:**
```
GET /api/kb-files   (autenticato)
→ { files: [{name, size, modified, modified_rel}], total_size }
```

**Funzioni JS aggiunte:**
- `loadKbFiles()` — carica e renderizza la griglia file
- `reloadKB2()` — versione del bottone ricarica per il tab KB
- `_fmtBytes(n)` — formattazione dimensione file (B / KB / MB)

#### Tab 📋 Onboarding (2 sub-tab)

**Sub-tab 🏢 Onboarding Interno:**
Guida operativa per il team Fuerte VC con 7 sezioni:
1. Accesso alla dashboard admin
2. Architettura del sistema (screener, dati, email, chatbot)
3. Elaborazione giornaliera (orari, sequenza, log)
4. Gestione clienti (CRM, attivazione, export)
5. Knowledge Base e chatbot (reload, segreti industriali)
6. Parametri di configurazione
7. Procedure di emergenza (sistema down, email non inviate, screener bloccato, chatbot, cache ETF)

**Sub-tab 👤 Onboarding Cliente:**
Flusso di benvenuto per nuovi abbonati con 6 fasi:
- **Fase 1 — Registrazione** (form, lingua, pagamento)
- **Fase 2 — Attivazione** (lato admin, CRM, stato Attivo)
- **Fase 3 — Email di benvenuto** (contenuto consigliato)
- **Fase 4 — Come Leggere il Report** *(espansa — vedi sotto)*
- **Fase 5 — Supporto e Chatbot**
- **Fase 6 — Profilazione Consigliata** *(espansa — vedi sotto)*

---

### Fase 4 — Come Leggere il Report: versione ampliata ✅

La sezione ora include 5 blocchi dettagliati basati sulle colonne reali degli Excel generati dagli screener:

| Blocco | Contenuto |
|---|---|
| 🔑 Colonne comuni | Score (con spiegazione percentile), Ticker, Nome, Mercato/Indice, Prezzo, Data Dati |
| 📈 Report Azioni | 9 colonne: EV/FCF (formula + interpretazione soglie), P/B (P/B<1 e P/B>3), ROE (avvertenza debito), Net Debt/EBITDA, Dividend Yield, Var 1D%, Perf multi-periodo, Market Cap, Settore |
| 📦 Report ETF | 10 colonne: ISIN, TER (esempio €100k × 20 anni), Sharpe (scala completa), Performance 1Y + 3M, AUM, Replica fisica (perché no sintetici), ACC (perché no distribuzione), Stelle MS, Età ETF |
| 🏦 Report Fondi | 7 colonne: TER (confronto attivo vs ETF), Sharpe (alfa reale vs beta), AUM, Performance 1Y (confronto benchmark), Perf 3M, Stelle MS, Categoria |
| 📋 Struttura multi-foglio | Tabella con 4 fogli Excel: Top Selezionati / Selezionati completo / Scartati per motivo / Non Validi — con disponibilità per piano |

Fonte colonne: `_SEL_COLS` in `value_screener_azioni.py`, `_ETF_SEL_COLS` in `value_screener_etf.py`, `_FONDI_SEL_COLS` in `value_screener_fondi.py`.

---

### Fase 6 — Profilazione Consigliata: versione ampliata ✅

La sezione ora include 3 tabelle (Azioni / ETF / Fondi) con colonne: Piano / Profilo / Orizzonte / Chi è / Segnali tipici — basate su `kb_profili.md`. Aggiunta anche:
- Nota Fondi EU UCITS (quando consigliare EU vs US)
- Tabella guida rapida orizzonte + esperienza → piano consigliato

---

## Stato precedente (01/07/2026) — invariato

Vedere `Stato_Progetto_RobotTrader2026_20260701.md` per lo stato completo del sistema prima di questa sessione.

---

## Semaforo attuale

### ✅ FUNZIONANTE (aggiornato 04/07 — sessione pomeriggio)
- **Order Builder completo**: dati fiscali cliente, banca, IBAN, nome gestore, CC automatica al cliente
- **Email ordine bancario**: To gestore + CC cliente — SMTP Gmail testato e verificato
- **Salvataggio anagrafica**: aggiornamento automatico `clienti.json` dopo invio ordine
- PWA Android: manifest + SW + banner installazione
- Order Builder — Picker titoli dal Report
- 4 screener operativi (Azioni, ETF, Fondi US, Fondi EU)
- Database Universo Ticker: 9.779 strumenti
- Scheduling 3 job automatici con log
- Email report con conteggi dinamici
- Dashboard admin + area clienti
- Sistema fatture PDF automatico
- **Chatbot AI pubblico (KB 9 file, 5 lingue)** — kb_azienda + kb_prodotto + kb_faq + kb_glossario + kb_profili + kb_metriche + kb_educazione_etf + kb_mercati_globali + kb_teoria_investimento
- **Chatbot Abbonati** (area clienti, dati screener, blu)
- **Conteggi universo dinamici**: `{N_AZIONI}`, `{N_ETF}`, `{N_FONDI_US}`, `{N_FONDI_EU}`, `{N_TOTALE}` — aggiornati ad ogni `reload_kb()`
- **Segreti industriali protetti**: nessun parametro numerico di screening o peso score in KB, email o chatbot
- **Tab KB in dashboard admin**: file browser KNOWLEDGE_BASE con reload live
- **Tab Onboarding in dashboard admin**: Interno (guida staff 7 sezioni) + Cliente (flusso benvenuto 6 fasi, Fase 4 e Fase 6 ampliate)

### 🔴 BLOCCA IL LANCIO PUBBLICO
1. **Cloudflare Tunnel** — `cloudflared.exe` non configurato (HTTPS obbligatorio per PWA)
2. **Password admin** — ancora `"123"` in `config.json → admin_password`

### 🟡 IN ATTESA CREDENZIALI
3. Social Automation — Brevo api_key, LinkedIn client_id/secret, Meta page_id
4. WhatsApp Business — account Meta + numero + template approvati

### 🔑 SICUREZZA PENDENTE
5. Ruotare API key Anthropic
6. Rigenerare App Password Gmail
7. Impostare password admin forte

---

*Fuerte Venture Capital SL · CIF B23881691 · Villaverde, Las Palmas de Gran Canaria, Spagna*
