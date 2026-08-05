# Stato Progetto Robot Trader 2026 — 05/08/2026 (Sessione 12)

## Attività sessione

### 1. Refactoring dashboard.py — COMPLETATO ✅
Dashboard.py ridotto da **16.158 a 8.763 righe** estraendo due blocchi statici in moduli separati:

| File | Righe | Contenuto |
|---|---|---|
| `assets.py` | 2.471 | `FUERTE_LOGO_B64` — logo PNG embedded in base64 |
| `html_admin.py` | 4.926 | Costante `HTML` — intera dashboard admin (CSS+JS+HTML) |
| `dashboard.py` | 8.763 | Server HTTP, routing, logica business |

**Backup:** `dashboard.py.bak_refactor` disponibile in PYTHON_SCRIPTS.

Prossimo step refactoring (da fare in sessione futura):
- Estrarre `html_client.py` (~2.900 righe: _build_area_clienti, _build_idee_clienti, _build_settori_clienti, _build_ordine_bancario, _build_profilo_investitore)
- Estrarre `html_public.py` (~900 righe: landing, login pages)
- Estrarre `data_layer.py` (~500 righe: I/O clienti, prospect, parametri)
- Estrarre `email_fatture.py` (~700 righe: Brevo + email credenziali + fatture PDF)

### 2. Meta Facebook/Instagram — PARZIALE ⚠️
- **META_PAGE_ID** trovato e configurato: `61591196613530`
- **META_APP_ID**: `841836765343945` (già in .env)
- **redirect_uri** aggiornato a: `https://plaza-gothic-barcode.ngrok-free.dev/api/meta/callback`
- **TOKEN** attuale ha solo permessi WhatsApp — manca token con `pages_manage_posts` + `instagram_basic` + `instagram_content_publish`
- **META_IG_USER_ID**: ancora da recuperare (dipende dal token Facebook valido)

**Per completare:** generare nuovo token da developers.facebook.com/tools/explorer con i permessi sopra, incollarlo nel dashboard → CRM → Social Media → Connetti.

### 3. Scheduler — VERIFICATO ✅
- Scheduler attivo e funzionante
- Orari configurati (timezone Atlantic/Canary):
  - 20:30 lun-ven: FONDI_EU_FETCH
  - 21:00 lun-ven: AZIONI + email clienti
  - 21:45 lun-ven: ETF + FONDI + FONDI_EU + email clienti
  - 08:00 lun/mer/ven: Social automation
- Fix pending: `UnicodeEncodeError` emoji in `social_automation.py` riga 210 (cp1252 Windows)

## Stato CRM
- **Clienti:** 6 Tester + 1 Attivo (Luciano Manicardi)
- **Prospect:** 2.435 (2.386 "Da Contattare", 49 "Prospect LinkedIn")
- **Email lancio Brevo:** Bozza ID 1 pronta — DA INVIARE dopo go-live

## TODO prioritari
1. Token Meta Facebook/Instagram (permessi completi)
2. Fix UnicodeEncodeError social_automation.py
3. Go-live VPS Hetzner + Cloudflare
4. Email lancio 2.435 prospect
