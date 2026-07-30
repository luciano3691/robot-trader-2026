# Stato Progetto — Robot Trader 2026 · Sessione 5

**Fuerte Venture Capital SL** · CIF B23881691 · marketing@fuerteventurecapital.com  
**Ultimo aggiornamento:** 17/07/2026 — Sessione 5  
**Path progetto:** `C:\Users\lucia\Desktop\Robot Trader 2026\PYTHON_SCRIPTS\`

---

## Modifiche applicate — 17/07/2026 Sessione 5

### Sezione Analisi Settoriale & Mercati — aperta ai subscriber ✅

Obiettivo: rendere la tab "🌍 Analisi Settoriale & Mercati" (finora solo admin) accessibile
agli abbonati, e inserire un link con spiegazione nell'email di notifica report.

---

### 1. Nuova pagina `/settori` per subscriber — `dashboard.py`

**Nuova funzione `_build_settori_clienti(nome)`** (inserita prima di `_build_area_clienti`):

- Pagina standalone con tema scuro identico all'area clienti
- Header: logo Fuerte + "← Area Riservata" (link a `/area-clienti`)
- Contenuto identico alla tab admin: 2 sub-tab (Settori GICS + Nazioni & Mercati)
- Guida lettura dati collassabile (stessa dell'admin)
- Modal drill-down titoli per settore
- JS completo inline: `SETT_INFO` (11 settori), `NAZIONI_ETF` (21 paesi), `EU_TO_US`,
  tutte le funzioni (`loadSettori`, `renderSettGics`, `renderSettNazioni`, `openSettModal`,
  `openNazioneModal`, `_settInterpreta`, `_settBg`, `_settPill`, `_etfTableHtml`)
- `loadSettori(false)` chiamato automaticamente al `window.load`

**Tecnica implementazione:** f-string Python per HTML/CSS (con `{{}}` per le graffe CSS),
raw string `r"""..."""` per il JS (evita conflitti con le graffe JS).

---

### 2. Route GET `/settori` — `dashboard.py`

Inserita subito dopo la route `/area-clienti` nel handler `do_GET`:

```python
if p in ('/settori', '/settori/'):
    if not _is_client_auth(self):
        _redirect(self, '/client-login'); return
    tok   = _get_client_token(self)
    email = CLIENT_SESSIONS.get(tok, '')
    ...
    self._html(_build_settori_clienti(nome)); return
```

- Protetta da `_is_client_auth` (redirect a `/client-login` se non loggato)
- Dopo login il subscriber torna automaticamente a `/settori`

---

### 3. API endpoints aperti ai subscriber — `dashboard.py`

Modificate 2 righe nel handler `do_GET`:

| Endpoint | Prima | Dopo |
|---|---|---|
| `/api/settori` | `_is_auth(self)` | `_is_auth(self) or _is_client_auth(self)` |
| `/api/settori/titoli` | `_is_auth(self)` | `_is_auth(self) or _is_client_auth(self)` |

---

### 4. Card "Analisi Settoriale & Mercati" in area clienti — `dashboard.py`

In `_build_area_clienti()`, aggiunta variabile `_settori_card`:

- Card cliccabile con link a `/settori`
- Sfondo sfumato blu scuro, bordo che diventa arancio al hover
- Testo: "Momentum in tempo reale per 11 settori GICS (USA & Europa) e 21 mercati globali..."
- Freccia "Apri →" in evidenza
- Posizione: subito sotto i 3 report row (Azioni/ETF/Fondi), sopra l'Order Builder

---

### 5. Email notifier — `email_notifier.py`

**`_load_email_config()`** ora legge anche `base_url` da `config.json`
(oltre a `email`). Restituisce tupla `(email_cfg, base_url)`.

**Nuove variabili modulo:**
```python
URL_SETTORI = BASE_URL.rstrip('/') + '/settori'
URL_AREA    = BASE_URL.rstrip('/') + '/area-clienti'
```

**`create_email_body()`** ora sostituisce 2 placeholder aggiuntivi:
- `{URL_SETTORI}` → link diretto alla pagina settori
- `{URL_AREA}` → link all'area clienti

---

### 6. Template email HTML — `email_template.html`

Aggiunto blocco CTA tra "Cosa contiene il report" e "Robot Trader 2026":

- Sfondo `linear-gradient(135deg, #1a2744, #0d1b35)`, bordo blu
- Titolo: "🌍 Analisi Settoriale & Mercati"
- Descrizione: "22 settori GICS (USA & Europa) e 21 mercati globali con dati di momentum..."
- Lista 5 punti: card colorate, semaforo nazioni, ETF consigliati, drill-down, segnali tattici
- Bottone arancio: "Apri Analisi Settoriale & Mercati →" → `{URL_SETTORI}`
- Link secondario: "Area Riservata" → `{URL_AREA}`

---

### 7. Template email TXT — `email_template.txt`

Aggiunta sezione equivalente in plain text con:

- Elenco puntato degli stessi 5 punti
- URL testuale `{URL_SETTORI}` e `{URL_AREA}`

---

## File modificati

| File | Tipo modifica |
|---|---|
| `dashboard.py` | Nuova funzione + route + API auth + card area clienti |
| `email_notifier.py` | Lettura base_url + 2 placeholder + 2 URL variabili |
| `email_template.html` | Blocco CTA con link e descrizione settori |
| `email_template.txt` | Sezione testo equivalente |

---

## Flusso utente post-modifica

```
Email con report allegato
  ↓
Bottone "Apri Analisi Settoriale & Mercati →"
  ↓
GET /settori  →  _is_client_auth?
  ├── SÌ → _build_settori_clienti(nome) → pagina completa
  └── NO → redirect /client-login → dopo login → /settori
```

---

## Stato TODO (invariato rispetto sessione precedente)

### Critico (blocca lancio)
1. **Cloudflare Tunnel** — scaricare cloudflared.exe, UUID in config.yml, aggiornare base_url
2. **Password admin** — cambiare `"123"` in `config.json → admin_password`
3. **servizi_config.json** — sezione `fondi_eu` con piani BASIC/PRO/VALUE

### Social Media
4. LinkedIn — `config.json → social.linkedin`
5. Meta (Facebook/Instagram) — `config.json → social.meta`
6. Calendario social — aggiornare date in `social_calendar.json`

### Sicurezza
7. Ruotare API key Anthropic
8. Rigenerare App Password Gmail
9. Impostare password admin forte
