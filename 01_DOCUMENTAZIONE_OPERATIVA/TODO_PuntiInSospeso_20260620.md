# TODO — Punti in Sospeso
## Robot Trader 2026 / Fuerte Venture Capital SL

**Ultimo aggiornamento:** 20/06/2026  
**Stato sistema:** Pre-lancio — 4 screener operativi, 5.637 strumenti  
**URL target:** https://www.fuerteventurecapital.com

---

## BLOCCO 1 — CRITICO (blocca il lancio pubblico)

| # | Cosa fare | Dettaglio | Dove |
|---|---|---|---|
| 1 | **Cloudflare Tunnel** | Scaricare `cloudflared.exe` da GitHub → eseguire `1_SETUP_TUNNEL.bat` → UUID in `config.yml` → `2_CONFIGURA_DNS.bat` → aggiornare `config.json → base_url` a `https://www.fuerteventurecapital.com` | `CLOUDFLARE_TUNNEL\` |
| 2 | **Password admin** | Cambiare `"123"` con password sicura | `config.json → admin_password` |

---

## BLOCCO 2 — SICUREZZA (azioni manuali — da fare prima possibile)

| # | Cosa fare | Motivo |
|---|---|---|
| 3 | **Ruotare API key Anthropic** | Era esposta in chiaro nei log debug (sessione 16/06) |
| 4 | **Rigenerare App Password Gmail** | Era in chiaro in `config.json` (sessione 16/06) — da `myaccount.google.com → Sicurezza → Password per le app` |

---

## BLOCCO 3 — SOCIAL AUTOMATION (codice pronto — solo credenziali)

| # | Cosa fare | Credenziale | Config |
|---|---|---|---|
| 5 | **Account Brevo** | `api_key`, `smtp_login`, `smtp_password`, `list_ids[]` | `config.json → social.brevo` |
| 6 | **LinkedIn Company Page FVC** + Developer App | `client_id`, `client_secret`, `org_id` | `config.json → social.linkedin` |
| 7 | **Facebook Page FVC** + **Instagram Business** + Meta App | `app_id`, `app_secret`, `page_id`, `ig_user_id` | `config.json → social.meta` |
| 8 | **Aggiornare `social.brevo.base_url`** | Da `http://localhost:5000` a `https://www.fuerteventurecapital.com` | Fare dopo Cloudflare attivo |
| 9 | **Reminder rinnovo token LinkedIn** | Il token OAuth scade ogni 60 giorni | Mettere evento ricorrente in calendario |

---

## BLOCCO 4 — WHATSAPP BUSINESS (codice pronto — attesa Meta)

| # | Cosa fare | Dettaglio |
|---|---|---|
| 10 | **Meta Business Manager** | Verifica azienda con CIF B23881691 su business.facebook.com |
| 11 | **Numero dedicato** | SIM business non già usata su WhatsApp personale |
| 12 | **Token permanente + phone_number_id** | Da Meta Developer App → inserire in `config.json → whatsapp` |
| 13 | **Template `screener_pronto`** | Sottomettere a Meta per approvazione (~24-48h) — testo in `WhatsApp_Business_Setup_Procedura.md` |
| 14 | **Template `brief_mattutino`** | Sottomettere a Meta per approvazione (~24-48h) |
| 15 | **Opt-in clienti** | Consenso GDPR esplicito → Dashboard admin → tab Clienti → bottone 📱 |

---

## FUTURO (post-lancio)

| # | Cosa | Note |
|---|---|---|
| 16 | **Gestione rinnovi abbonamento** | Rinnovo, sospensione, downgrade non automatizzati |
| 17 | **Stripe integrazione** | Chiavi vuote → bottoni acquisto non funzionano → Fattura PDF da collegare a Stripe |
| 18 | **Pagina /privacy** | Link GDPR punta a `/privacy` — pagina mancante |
| 19 | **IBKR API diretta** | Ordini diretti al broker — previsto piano VALUE "coming soon" |
| 20 | **Immagini DALL-E per Instagram** | Instagram richiede `image_url` — senza immagini IG non funziona |
| 21 | **Reset password clienti** | Non implementato — solo cambio volontario da area riservata |
| 22 | **Analytics social settimanali** | Metriche LinkedIn + Meta → report email admin ogni lunedì |
| 23 | **Espansione Fondi EU** | Attualmente 472 pronti — aggiungere termini in `fetch_fondi_eu_universe.py` per superare 700+ |

---

## ✅ COMPLETATI — 20/06/2026

| Cosa | Dettaglio |
|---|---|
| ✅ Domain rename completo | `fuertescreener.com` → `www.fuerteventurecapital.com` in tutti i file (.py/.html/.txt) |
| ✅ Email rename completo | `hello@/marketing@fuertescreener.com` → `marketing@fuerteventurecapital.com` |
| ✅ Fondi US espansi 781→911 | +130 ticker, +9 famiglie: AB, PGIM, Morgan Stanley, State Street, William Blair, Causeway, Hotchkis, Alger, Transamerica |
| ✅ Screener Fondi EU UCITS | `value_screener_fondi_eu.py` — 472 fondi pronti, 3 Excel per piano |
| ✅ Discovery Fondi EU | `fetch_fondi_eu_universe.py` — fase 1 ISIN + fase 2 420 termini Yahoo Finance |
| ✅ Cache Fondi EU | `fondi_eu_universe_cache.json` — 536 voci, 472 con TER, 385 con MS rating |
| ✅ Orchestrator 4° screener | `FONDI_EU` aggiunto ad `ALL_SCREENERS` |
| ✅ Scheduler timeout 2h | Job ETF+FONDI+EU con `timeout_sec=7200` |

## ✅ COMPLETATI — 17/06/2026

| Cosa | Dettaglio |
|---|---|
| ✅ Retry automatico SMTP | `send_plan_email()` — 3 tentativi, 30s pausa — fix errore DNS transitorio |

## ✅ COMPLETATI — 16/06/2026

| Cosa | Dettaglio |
|---|---|
| ✅ Threading lock | `_clienti_lock` + `_fatture_lock` — no race condition su file JSON |
| ✅ Scrittura atomica | `save_clienti()` temp file + `os.replace()` |
| ✅ Password admin da env/config | `os.getenv("ADMIN_PASSWORD")` o `config.json → admin_password` |
| ✅ Memory leak chatbot | `_session_ts` dict + `cleanup_expired_sessions()` |
| ✅ Timeout SMTP | `smtplib.SMTP(..., timeout=15)` |
| ✅ Scoring NaN fix | `import math` + filtro NaN in `batch_percentile_score` |
| ✅ Import circolare social | Guard `try/except` in `social_automation.py` |
| ✅ WhatsApp API version | `_WA_API_VERSION = 'v20.0'` costante |

## ✅ COMPLETATI — 14/06/2026

| Cosa | Dettaglio |
|---|---|
| ✅ Scheduling separato | AZIONI 23:00 lun-ven / ETF+FONDI 23:30 lun-mer-ven |
| ✅ Universo ETF EU ACC | +60 ETF settoriali/tematici/factor → totale 1.182 |
| ✅ Deduplicazione ETF per ISIN | Preferisce ACC su DIST, poi max volume |
| ✅ Sessioni con timeout | Admin 8h fisso / Clienti 24h sliding |
| ✅ Fattura PDF — IBAN bonifico | ES83 2100 1513 7202 0070 3406 CaixaBank |
| ✅ Fattura PDF — pagina singola | Fix auto_page_break prima del footer |
| ✅ Cartella FATTURE radice progetto | Spostata da PYTHON_SCRIPTS/ a radice |
| ✅ Download fattura area clienti | GET /api/mia-fattura + link 🧾 |
| ✅ WhatsApp Business documentato | Procedura completa in 01_DOCUMENTAZIONE_OPERATIVA/ |

---

## Ordine operativo consigliato

```
SUBITO (sicurezza):
  → [3] Ruota API key Anthropic
  → [4] Rigenera App Password Gmail

QUESTA SETTIMANA (lancio):
  → [1] Cloudflare Tunnel (30 min)
  → [2] Password admin (5 min)

DOPO CLOUDFLARE:
  → [5] Account Brevo
  → [6] LinkedIn Developer App
  → [7] Meta App + Facebook/Instagram
  → [10-11] Meta Business Manager + WhatsApp number
  → [12-14] Token + submit template (attesa 24-48h)

DOPO IL LANCIO:
  → [8-9] URL social e reminder token
  → [15] Opt-in WhatsApp dai clienti
  → [16-23] Roadmap evolutiva
```

---

*Fuerte Venture Capital SL · CIF B23881691 · marketing@fuerteventurecapital.com*  
*Documento aggiornato il 20/06/2026*
