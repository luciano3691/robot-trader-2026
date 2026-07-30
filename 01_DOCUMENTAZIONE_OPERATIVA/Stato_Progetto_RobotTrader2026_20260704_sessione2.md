# Stato Progetto — Robot Trader 2026 · Sessione 2

**Fuerte Venture Capital SL** · CIF B23881691 · marketing@fuerteventurecapital.com  
**Ultimo aggiornamento:** 04/07/2026 — Sessione 2 (pomeriggio/sera)  
**Path progetto:** `C:\Users\lucia\Desktop\Robot Trader 2026\PYTHON_SCRIPTS\`

---

## Modifiche applicate — 04/07/2026 Sessione 2

### 1. Brevo API — Configurazione completa ✅

**config.json → social.brevo** ora popolato:

| Campo | Valore |
|---|---|
| `api_key` | `xkeysib-d5459e...` |
| `smtp_login` | `info@fuerteventurecapital.com` |
| `smtp_password` | `xsmtpsib-d5459e...` |
| `sender_email` | `marketing@fuerteventurecapital.com` |
| `sender_name` | `Fuerte Venture Capital` |
| `list_ids` | `[3]` |
| `admin_email` | `rioluc63@gmail.com` |

**Connessione verificata:** `GET /api/brevo/campagne` → OK, 0 campagne (account nuovo).

---

### 2. Import Lead — 2.386 contatti da 4 file CSV ✅

| File | Inseriti | Duplicati | Stato assegnato |
|---|---|---|---|
| Import CSV.csv | 507 | 0 | Da Contattare |
| Import CSV 1.csv | 310 | 49 | Da Contattare |
| Import CSV 2.csv | 9 | 123 | Da Contattare |
| Import CSV 3.csv | 1.560 | 302 | Da Contattare |
| **TOTALE** | **2.386** | **474** | |

**Formato CSV 1/2:** separatore `;`, campi RAGIONE_SOCIALE/NOME/COGNOME/EMAIL/TELEFONO/LOCALITA — contatti B2B trasporto/logistica  
**Formato CSV 3:** separatore `,`, campi First Name/Last Name/Email/Phone/Tags — CRM GoHighLevel/GHL, tag tipo `italy lead`, `comprador`, `costa ancor`

**Tag GHL** salvati nel campo `note` di ogni prospect.

**Brevo lista creata:** "Robot Trader 2026 - Lead" → **ID = 3** — tutti i 2.386 contatti caricati.

---

### 3. Import Apollo.io — 49 contatti con LinkedIn URL ✅

Importati 3 file da `Downloads/apollo-contacts-export*.csv`:

| File | Inseriti | Duplicati | LinkedIn URL |
|---|---|---|---|
| apollo-contacts-export.csv | 24 | 0 | 24/24 |
| apollo-contacts-export (1).csv | 15 | 5 | 15/15 |
| apollo-contacts-export (2).csv | 10 | 5 | 10/10 |
| **TOTALE** | **49** | **10** | **49/49** ✅ |

**Stato assegnato:** `Prospect LinkedIn` (non Da Contattare — entrano direttamente nella colonna LinkedIn)  
**Fonte:** `Apollo.io`  
**Campi mappati:**
- `First Name` / `Last Name` → nome/cognome
- `Email` → email
- `Person Linkedin Url` → **linkedin_url** (popolato al 100%)
- `Company Name` + `Title` + `City` + `Country` → note
- `Mobile Phone` / `Work Direct Phone` → telefono

**Totale prospect.json dopo tutto l'import:** **2.435 contatti**

---

### 4. Nuovo stato pipeline: Prospect LinkedIn ✅

**Funnel completo aggiornato:**
```
Da Contattare → Contattato → Interessato → Prospect LinkedIn → Tester → Abbonato
      ↑                                           ↑
  (email Brevo)                           (Import Apollo.io)
```

**Modifiche dashboard.py:**

| Sezione | Modifica |
|---|---|
| `PIPELINE_COLS` | Aggiunta colonna `Prospect LinkedIn` (colore `#0A66C2`) tra Interessato e Tester |
| `PROSPECT_STATI` | Aggiunto `Prospect LinkedIn` nel dropdown scheda prospect |
| `cardActions` | Catena avanzamento: `Interessato → Prospect LinkedIn` tramite ▶ |
| Card Prospect LinkedIn | Tasto **LinkedIn** su ogni card — apre profilo diretto se `linkedin_url` esiste, altrimenti ricerca per nome |
| Header colonna | Tasto **⬇ Ads** (appare se ci sono card) → export CSV Email+Nome+LinkedIn per LinkedIn Matched Audiences |
| `pipelineEsportaLinkedIn()` | Nuova funzione JS — export CSV BOM UTF-8 della colonna Prospect LinkedIn |
| Backend `AVANZAMENTO` | `'Interessato': 'Prospect LinkedIn'` aggiunto al map |
| Backend candidati | Filter include `'Interessato'` per avanzamento automatico da Brevo |

---

### 5. Tasto "Import Apollo.io" nel dashboard ✅

**Posizione:** CRM → Pipeline → toolbar accanto a "+ Nuovo Lead"

**Funzionamento:**
1. Click → file picker (filtra `.csv`)
2. Seleziona export Apollo.io
3. Carica via `POST /api/prospect/import-apollo`
4. Alert con conteggi: inseriti / duplicati / con LinkedIn
5. Pipeline si aggiorna automaticamente

**Backend route:** `POST /api/prospect/import-apollo`
- Legge CSV Apollo.io (Content-Type: text/plain)
- Deduplication per email
- Imposta sempre `stato = 'Prospect LinkedIn'`, `fonte = 'Apollo.io'`
- Popola `linkedin_url` da campo `Person Linkedin Url`

---

### 6. Sezione Social Media live ✅

Implementata nella sessione precedente, verificata in questa sessione.

**Endpoint attivi:**
| Route | Descrizione |
|---|---|
| `GET /api/social/platforms` | Stato connessione LinkedIn / Facebook / Instagram |
| `GET /api/social/calendario` | 24 voci da `social_calendar.json` con campo `stato` calcolato |
| `GET /api/social/status` | Draft in attesa da `SOCIAL_DRAFTS/` |
| `POST /api/social/genera` | Avvia `social_automation.run()` |
| `POST /api/social/draft/edit` | Modifica testo draft |

**Bug risolto:** `self._body()` chiamato due volte in `POST /api/social/genera` → la seconda lettura dal socket bloccava indefinitamente. Fix: `_raw = self._body()` come variabile locale, poi usata una sola volta.

---

### 7. Sezione Campagne Brevo — funzionalità complete ✅

**Endpoint attivi:**
| Route | Descrizione |
|---|---|
| `GET /api/brevo/campagne` | Lista campagne da Brevo API v3 |
| `GET /api/brevo/campagne/{id}/risultati` | KPI dettagliati campagna |
| `GET /api/brevo/campagne/{id}/non-aperti` | Confronto openers vs CRM |
| `GET /api/brevo/liste` | Liste Brevo |
| `GET /api/brevo/template` | Template email |
| `POST /api/brevo/campagne` | Crea nuova campagna |
| `POST /api/brevo/campagne/{id}/invia` | Invia campagna |
| `POST /api/brevo/campagne/{id}/avanza-prospect` | Avanza stato prospect che hanno aperto |

**Bottone "▲ LinkedIn"** (ex "▲ Prospect"):
- Controlla openers via Brevo API
- Avanza: Da Contattare→Contattato, Contattato→Interessato, Interessato→Prospect LinkedIn
- Modal "Avanzamento Prospect LinkedIn" con:
  - Lista avanzati con icona LinkedIn per ogni contatto
  - Tasto **LinkedIn Ads** → export CSV per LinkedIn Matched Audiences
  - Sezione "Già oltre LEAD"
  - Sezione "Non presenti in CRM"

---

## Stato database prospect — 04/07/2026

| Stato | Contatti | Fonte principale |
|---|---|---|
| Da Contattare | 2.386 | CSV import (4 file) |
| Prospect LinkedIn | 49 | Apollo.io (3 file) |
| **TOTALE** | **2.435** | |

**Brevo lista "Robot Trader 2026 - Lead" (ID 3):** 2.435 contatti

---

## TODO aggiornato — 04/07/2026

### Critico (blocca lancio)
1. **Cloudflare Tunnel** — scaricare cloudflared.exe, UUID in config.yml, aggiornare base_url
2. **Password admin** — cambiare `"123"` in `config.json → admin_password`
3. **servizi_config.json** — aggiungere sezione `fondi_eu` con piani BASIC/PRO/VALUE

### Social Media (da configurare)
4. **LinkedIn** — `config.json → social.linkedin.client_id/client_secret/org_id`
5. **Meta (Facebook/Instagram)** — `config.json → social.meta.app_id/app_secret/page_id/ig_user_id`
6. **Calendario social** — aggiornare date in `social_calendar.json` (tutte scadute, da luglio 2026)

### Sicurezza
7. Ruotare API key Anthropic
8. Rigenerare App Password Gmail
9. Password admin forte

### Apollo.io — prossimi import
- Scaricare nuovi export da Apollo.io → tasto "Import Apollo.io" nel dashboard
- Obiettivo: popolare `linkedin_url` anche per i 2.386 lead da Brevo

---

## Credenziali configurate (config.json)

| Servizio | Stato |
|---|---|
| Gmail SMTP | ✅ configurato |
| Brevo API | ✅ configurato (04/07/2026) |
| Brevo SMTP | ✅ configurato (04/07/2026) |
| WhatsApp Meta | ✅ token presente |
| Anthropic API | ✅ key presente |
| LinkedIn OAuth | ❌ da configurare |
| Meta OAuth | ❌ da configurare |
| ngrok | ✅ dominio statico attivo |
| Cloudflare Tunnel | ❌ da configurare |
