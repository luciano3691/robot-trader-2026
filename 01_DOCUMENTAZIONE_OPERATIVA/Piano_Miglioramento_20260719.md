# Piano di Miglioramento — Robot Trader 2026
**Data:** 19 luglio 2026 | **Versione:** 1.4 — aggiornato sessione 9**

---

## PARTE 1 — ANALISI COSTI / RICAVI

### 1.1 Situazione attuale (luglio 2026)

| Voce | Dettaglio |
|---|---|
| Clienti ATTIVI paganti | **0** (1 ATTIVO = account proprietario) |
| TESTER | 6 (free) |
| Fatture emesse | 20 (quasi tutte test) |
| Prospect nel CRM | **2.435 contatti** |
| Ricavi mensili reali | **€ 0** |

### 1.2 Costi infrastruttura

**Oggi (pre-lancio):**

| Voce | Costo/mese |
|---|---|
| Anthropic Claude Haiku (chatbot testing) | €5–15 |
| Brevo email (piano free, 9.000 mail/mese) | €0 |
| ngrok dominio statico | €0 |
| Gmail SMTP | €0 |
| Hardware (PC Windows) | €0 (già ammortizzato) |
| **Totale** | **€5–15/mese** |

**Post-lancio (VPS Hetzner — già attivo):**

| Voce | Costo/mese |
|---|---|
| VPS Hetzner CPX22 (3 vCPU, 4 GB RAM, 80 GB NVMe) — già pagato | €8.49 |
| Anthropic API a regime (500 sessioni/mese) | €20–40 |
| Brevo Starter (20.000 email/mese) | €9 |
| Dominio + Cloudflare | €1 |
| **Totale** | **€38–58/mese** |

### 1.3 Listino prezzi attuale

| Piano | Azioni | ETF | Fondi | Ordini |
|---|---|---|---|---|
| BASIC | €29 | €29 | €29 | €19 |
| PRO | €39 | €39 | €39 | €29 |
| VALUE | €59 | €59 | €59 | €49 |

**ARPU stimato** (cliente tipo con 2 screener): **€60–80/mese**

### 1.4 Break-even e scenari di ricavo

Break-even con costi post-lancio (~€58/mese): **1 cliente pagante** (qualunque piano).

| Scenario | Conversione prospect | N. abbonati | MRR stimato | Profitto netto |
|---|---|---|---|---|
| Pessimistico | 0.3% | 7 | €420 | ~€362–382 |
| Base | 1% | 24 | **€1.440** | **~€1.382–1.402** |
| Ottimistico | 3% | 73 | €4.380 | ~€4.322–4.342 |
| Target 12 mesi | 5% | 122 | **€7.320** | **~€7.262** |

**Conclusione:** modello economico eccellente — costi fissi irrisori. Il problema non è il margine ma la **conversione** dei 2.435 prospect. Ogni singolo abbonato copre 1 mese di infrastruttura.

---

## PARTE 2 — QUALITY PLAN

### LIVELLO 0 — BLOCCA IL GO-LIVE

#### 0.1 Sicurezza credenziali ✅ COMPLETATO (sessione 6 — 19/07/2026)

| File | Stato |
|---|---|
| `.env` | **CREATO** — tutti i segreti qui |
| `config.json` | **PULITO** — tutti i campi sensibili → `""` |
| `dashboard.py` | Dotenv caricato all'avvio; `_brevo_api_key()` + `_load_anthropic_key()` leggono da env var |
| `whatsapp_service.py` | Dotenv + token/phone_id/waba_id da env var |
| `email_notifier.py` | Dotenv + Gmail password da env var |
| `social_publisher.py` | Dotenv + `_cfg()` inietta tutte le credenziali social da env var |

**Credenziali salvate nel `.env`:**
- Gmail SMTP ✅
- Brevo API key ✅
- Anthropic API key ✅
- WhatsApp token + phone_number_id + waba_id ✅
- LinkedIn client_id + client_secret + org_id ✅
- Meta app_id + app_secret + page_access_token ✅

#### 0.2 Password admin
Mantenuta semplice per accesso frequente (scelta consapevole del proprietario).

#### 0.3 Password clienti
Tutti con `FuerteRT#01`. Alla conversione in ATTIVO → `must_change_password: true`.

#### 0.4 Deployment stabile
VPS Hetzner CPX22 già attivo e pagato (€8.49/mese, fattura 05/2026). Credenziali SSH da recuperare via console Hetzner Cloud. Da fare nella prossima sessione dedicata.

---

### LIVELLO 1 — PRIORITÀ ALTA (entro 2–4 settimane)

#### 1.1 Pulizia backup manuali ✅ COMPLETATO (sessione 7 — 19/07/2026)
51 file `clienti_bk_*.json` spostati in `BACKUPS/clienti/`. Rotazione automatica in `save_clienti()`: mantiene ultimi 10, cancella i più vecchi.

#### 1.2 Sessioni persistenti ✅ COMPLETATO (sessione 7 — 19/07/2026)
`_persist_sessions()` salva su `sessions.json` ad ogni login/logout. `_load_sessions()` ripristina le sessioni valide all'avvio. Sessioni admin: 8h — client: 24h (finestra scorrevole).

#### 1.3 requirements.txt — allineamento ✅ COMPLETATO (sessione 7 — 19/07/2026)
Riscritto con le dipendenze reali del codice (Flask/Firebase/gunicorn rimossi):
```
yfinance>=0.2.40  pandas>=2.0.0  openpyxl>=3.1.0  fpdf2>=2.7.0
apscheduler>=3.10.0  anthropic>=0.25.0  requests>=2.31.0
python-dotenv>=1.0.0  Pillow>=10.0.0
```

#### 1.4 servizi_config.json — sezione `fondi_eu` ✅ COMPLETATO (sessione 7 — 19/07/2026)
Aggiunta sezione `fondi_eu` con BASIC/PRO/VALUE (€29/€39/€59) — fondi UCITS domiciliati UE. Versione file: 2.2.

---

### LIVELLO 2 — QUALITÀ DEL CODICE (entro 1–2 mesi)

#### 2.1 Dividere `dashboard.py` (14.500+ righe → moduli)
Strategia: estrarre un modulo alla volta, testare, poi il prossimo.

#### 2.2 Logging strutturato
Sostituire `print()` sparsi con `logging` + `RotatingFileHandler`.

#### 2.3 Rate limiting su login ✅ COMPLETATO (sessione 7 — 19/07/2026)
`_rl_check / _rl_fail / _rl_ok` per IP. 5 tentativi in 15 min → blocco 30 min. Applicato a login admin e login clienti. Log `[SECURITY]` in console.

#### 2.4 Validazione input ✅ COMPLETATO (sessione 7 — 19/07/2026)
`_validate_str(s, max_len=200)` centralizzato. Applicato a email e password nel login clienti.

---

### LIVELLO 3 — ROADMAP PRODOTTO (2–6 mesi)

| Feature | Priorità | Impatto ricavi | Sforzo | Stato |
|---|---|---|---|---|
| **Stripe / pagamenti automatici** | Alta | ★★★★★ | Medio | ⏳ prossimo |
| Trial 7 giorni automatico | Alta | ★★★★ | Basso | ✅ COMPLETATO (sessione 8 — 19/07/2026) |
| Dashboard analytics admin (MRR, churn, LTV) | Media | ★★★ | Medio | ✅ COMPLETATO (sessione 9 — 19/07/2026) |
| FastAPI migration | Media | ★★ | Alto | — |
| SQLite per clienti/prospect | Media | ★★★ | Medio | — |
| Test automatici pytest (≥80% coverage) | Media | ★★ | Medio | — |
| Nuovi mercati screener (GCC, India extended) | Bassa | ★★★ | Basso | — |

#### Dashboard Analytics Admin — Dettaglio implementazione (sessione 9)

**Tab:** "📈 Analytics" — nuovo tab nel pannello admin, dopo "🏠 Home"

**Funzione Python:** `_calc_analytics()` — legge `clienti.json` + `servizi_config.json` + `prospect.json`

**Metriche calcolate:**
- **MRR:** somma prezzi piani ATTIVI (`piano_azioni/etf/fondi/ordini` × prezzo da `servizi_config.json`)
- **ARR:** MRR × 12
- **ARPU:** MRR / n_attivi
- **LTV:** ARPU / churn_rate (default 24 mesi se churn = 0)
- **Ricavi cumulativi:** somma (mesi_attivi × MRR_cliente) per ogni cliente ATTIVO
- **Churn:** (sospesi + scaduti) / totale_ever × 100

**Route:** `GET /api/analytics` → `_calc_analytics()`

**UI JavaScript `renderAnalytics()`:**
- 2 righe KPI: MRR / ARR / ARPU / LTV + Attivi / Tester / Churn / Cumulativi
- Funnel orizzontale: Da Contattare → LinkedIn → Tester → Attivi
- Griglia 2 colonne: tabella MRR breakdown per cliente + 4 scenari di crescita con progress bar

**Valori attuali (1 cliente ATTIVO — proprietario):**
- MRR: €77 (Azioni BASIC €29 + Fondi BASIC €29 + Ordini BASIC €19)
- ARR: €924 | ARPU: €77 | LTV: €1.848 | Churn: 0%

**Note tecniche sessione 9 — bug critici risolti:**

1. **Bug modal "Crea Bozza Campagna" non cliccabile** — root cause: `cont.innerHTML = ...` inserisce il modal dentro l'albero DOM del tab; conflitti con stacking context e `onclick` inline in innerHTML dinamico. Fix: `document.body.appendChild(backdrop)` + `addEventListener('click', ...)` invece di `onclick` inline.

2. **Bug do_POST double body read** — `body = self._body()` a riga ~14592 legge l'intero socket HTTP per tutte le route admin. La route `/api/brevo/campagne` usava `self._body()` una seconda volta → seconda lettura su socket vuoto → blocco indefinito. Fix: usare la variabile `body` (già letta), mai `self._body()` in route `if` indipendenti dopo riga 14592.

3. **Migrazione `_brevo_call` da urllib a requests** — `urllib` non applica timeout alla fase `r.read()`. Migrato a `requests` con `timeout=20` (connection + read). Ora tutti i timeout Brevo funzionano correttamente.

4. **Bozza campagna lancio creata su Brevo** — ID 1, 2.435 prospect (lista "Prospect Lancio 2026-07-19"). Mittente: `marketing@fuerteventurecapital.com` / `Fuerte Venture Capital SL`. Da inviare dopo go-live su fuerteventurecapital.com.

---

#### Trial 7 giorni — Dettaglio implementazione (sessione 8)
- `trial_start` + `trial_end` (ISO datetime, +7 giorni) aggiunti automaticamente alla creazione di ogni nuovo TESTER (2 percorsi: prospect→tester e form admin)
- Al login: TESTER con `trial_end` passato → messaggio "periodo di prova scaduto", nessun accesso
- Area cliente: badge arancio/rosso con giorni rimanenti (>1 / ultimo giorno / scade oggi)
- Thread daemon giornaliero `_scadenza_trial_check()` → imposta `stato='SCADUTO'` per i TESTER scaduti
- Nuovo stato `SCADUTO` (viola #9F7AEA) aggiunto in admin lista clienti
- I 6 TESTER esistenti non hanno `trial_end` → accesso invariato (backward compatible)

---

## PARTE 3 — HOMEPAGE & MARKETING

### Homepage — modifiche sessione 8

#### Tagline ✅ COMPLETATO
`INVESTI CON INTELLIGENZA` → `INFORMATI CON INTELLIGENZ<span>AI</span>`  
Aggiornato in 6 punti: HTML statico + traduzioni IT / EN / DE / FR / ES.

#### Ticker count dinamico ✅ COMPLETATO (sessione 8 — 19/07/2026)

**Problema:** homepage mostrava "3072 ticker in 17 mercati globali" (numero vecchio, hardcoded, non corrispondente alla realtà).

**Soluzione:** funzione `_conta_ticker_universo()` calcolata ad ogni avvio del server dai file dati reali.

**Formula:**

| Categoria | Fonte | Count |
|---|---|---|
| Azioni | `ALL_AZIONI` da ticker_lists_5000.py | **2.621** |
| ETF | `ALL_ETF` (1.172) + etf_universe_cache ISINs (4.630) − overlap preferred_ticker (72) | **5.730** |
| Fondi | `ALL_FONDI` (865) + fondi_eu_universe_cache ISINs (870) | **1.735** |
| **TOTALE** | | **10.086** |

**Hero sub in tutte le lingue:**  
`"10.086 asset: 2.621 azioni in 17 mercati · 5.730 ETF · 1.735 fondi"`

**Implementazione tecnica:**
- `_conta_ticker_universo()` → `(_N_AZ, _N_ETF_TOT, _N_FD, _N_TOT)` calcolati a startup
- Helper `_fmt_it(n)` → formato italiano (punto come separatore migliaia)
- Helper `_fmt_en(n)` → formato inglese (virgola)
- Placeholder `__NTOT_IT__`, `__NTOT_EN__`, `__NAZ__`, `__NETF__`, `__NFD__` in LANDING_HTML (raw string)
- Sostituzione immediata dopo definizione LANDING_HTML (non al serve — baked all'avvio)
- Fallback hardcoded `(2621, 5730, 1735, 10086)` se i file non sono leggibili

---

### Brevo — stato sessione 9

| Feature | Stato |
|---|---|
| Mittente verificato | `marketing@fuerteventurecapital.com` — **Verificato** |
| Dominio autenticato | `fuerteventurecapital.com` — **Autenticato** su Brevo |
| Lista prospect importata | "Prospect Lancio 2026-07-19" (ID 4) — **2.435 contatti** |
| Bozza campagna lancio | Brevo ID 1 — **Creata** — da inviare dopo go-live |
| `_brevo_call` | Migrato da `urllib` a `requests` — timeout reale 20s (connection + read) |
| Bug `self._body()` doppia lettura | **Fixato** — route `/api/brevo/campagne` POST usava `self._body()` dopo che era già stato letto a riga ~14592 |
| Modal campagna | `document.body.appendChild` + `addEventListener` — no più `onclick` inline in innerHTML |

**Mittente campagne:** `marketing@fuerteventurecapital.com` / `Fuerte Venture Capital SL` (in `.env`)

---

### Social Media — stato al 19/07/2026

| Piattaforma | Stato | Note |
|---|---|---|
| LinkedIn | ⏳ In attesa approvazione "Marketing Developer Platform" | Credenziali salvate in `.env`; Pagina aziendale creata (Org ID: 135937046) |
| Facebook/Instagram | ⏳ Parcheggiato | App ID + App Secret + Page Token salvati in `.env`; Page ID e IG User ID da recuperare |

### Social Calendar ✅ COMPLETATO (sessione 6)
Esteso da 24 a 49 post — copertura fino al 29 settembre 2026.

| Ciclo | Periodo | Lingua |
|---|---|---|
| ✅ Storico | 8 giu – 17 lug | IT + ES |
| ▶ In corso | 20 lug – 7 ago | IT |
| Prossimo | 10 ago – 28 ago | ES |
| Nuovo | 1 set – 19 set | EN (prima volta) |
| Nuovo | 22 set – 29 set | IT |

### Email Early Adopter ✅ COMPLETATO (sessione 7 — 19/07/2026)
- Funzione `_invia_email_early_adopter()` — HTML personalizzato con tabella piani + 50% sconto
- Route `POST /api/marketing/early-adopter`
- Bottone "📩 Invia a Tester ora" nel tab Email del CRM
- Account interno `marketing@fuerteventurecapital.com` escluso automaticamente
- **Invio effettuato: 5/5 Tester — 19/07/2026**
- Invio via **Brevo REST API** (non SMTP — più stabile, nessun limite Gmail)

### Funnel prospect

```
2.435 Da Contattare → 49 Prospect LinkedIn → 6 Tester (5 email early adopter inviati) → 0 Attivi paganti
```

**Prossimo passo critico:** email lancio ai 2.435 prospect via Brevo — aspettare pubblicazione sito su Register.it (entro 25/07).

---

## RIEPILOGO SESSIONI

| Sessione | Data | Azioni completate |
|---|---|---|
| **6** | 19/07/2026 | `.env` creato, segreti migrati, social_calendar esteso, email early adopter integrata, LinkedIn credenziali salvate, Meta credenziali parziali salvate |
| **7** | 19/07/2026 | Email early adopter inviata **5/5 Tester** via Brevo API; fix Gmail SMTP → switch a Brevo REST API; backup rotation; sessioni persistenti; requirements.txt; fondi_eu; rate limiting; validazione input |
| **8** | 19/07/2026 | Tagline INFORMATI CON INTELLIGENZAI (6 lingue); Trial 7gg automatico (trial_start/end, check login, badge, thread daemon, stato SCADUTO); ticker count dinamico 10.086 (formula reale da file dati) |
| **9** | 19/07/2026 | Fix modal Brevo (body.appendChild + addEventListener); bug do_POST double-body-read fixato; `_brevo_call` migrato a `requests`; bozza campagna lancio **Brevo ID 1** (2.435 prospect); tab **📈 Analytics** (MRR/ARR/ARPU/LTV/Churn/Funnel/Scenari); dominio Brevo autenticato; mittente marketing@ verificato |
| **10 — prossima** | — | Pubblicazione Register.it, email lancio 2.435 prospect, VPS Hetzner deploy |
| **11** | — | LinkedIn posting (dopo approvazione), Meta completare Page ID + IG User ID |
| **12** | — | Stripe pagamenti automatici |
