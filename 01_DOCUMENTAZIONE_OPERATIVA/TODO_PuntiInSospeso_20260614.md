# TODO — Punti in Sospeso
## Robot Trader 2026 / Fuerte Venture Capital SL

**Ultimo aggiornamento:** 14/06/2026  
**Stato sistema:** Pre-lancio — sviluppo funzionalità completato  
**URL target:** https://www.fuerteventurecapital.com

---

## BLOCCO 1 — CRITICO (blocca il lancio)

| # | Cosa fare | Dettaglio | Dove |
|---|---|---|---|
| 1 | **Cloudflare Tunnel** | Scaricare `cloudflared.exe` da GitHub → eseguire `1_SETUP_TUNNEL.bat` → UUID in `config.yml` → `2_CONFIGURA_DNS.bat` → aggiornare `config.json → base_url` | `CLOUDFLARE_TUNNEL\` |
| 2 | **Password admin** | Cambiare `ADMIN_PASSWORD = "123"` con password sicura | `dashboard.py` riga ~68 |

---

## BLOCCO 2 — SOCIAL AUTOMATION (codice pronto — solo credenziali)

| # | Cosa fare | Credenziale | Config |
|---|---|---|---|
| 3 | **Account Brevo** | `api_key`, `smtp_login`, `smtp_password`, `list_ids[]` | `config.json → social.brevo` |
| 4 | **LinkedIn Company Page FVC** + Developer App | `client_id`, `client_secret`, `org_id` | `config.json → social.linkedin` |
| 5 | **Facebook Page FVC** + **Instagram Business** + Meta App | `app_id`, `app_secret`, `page_id`, `ig_user_id` | `config.json → social.meta` |
| 6 | **Aggiornare `social.brevo.base_url`** | Da `http://localhost:5000` a `https://www.fuerteventurecapital.com` | Fare dopo Cloudflare attivo |
| 7 | **Reminder rinnovo token LinkedIn** | Il token OAuth scade ogni 60 giorni | Mettere evento ricorrente in calendario |

---

## BLOCCO 3 — WHATSAPP BUSINESS (codice pronto — attesa Meta)

| # | Cosa fare | Dettaglio |
|---|---|---|
| 8 | **Meta Business Manager** | Verifica azienda con CIF B23881691 su business.facebook.com |
| 9 | **Numero dedicato** | SIM business non già usata su WhatsApp personale |
| 10 | **Token permanente + phone_number_id** | Da Meta Developer App → inserire in `config.json → whatsapp` |
| 11 | **Template `screener_pronto`** | Sottomettere a Meta per approvazione (~24-48h) — testo in `WhatsApp_Business_Setup_Procedura.md` |
| 12 | **Template `brief_mattutino`** | Sottomettere a Meta per approvazione (~24-48h) |
| 13 | **Opt-in clienti** | Consenso GDPR esplicito → Dashboard admin → tab Clienti → bottone 📱 |

---

## COMPLETATI IN QUESTA SESSIONE (14/06/2026) ✅

| Cosa | Dettaglio |
|---|---|
| ✅ Scheduling separato AZIONI / ETF+FONDI | AZIONI 23:00 lun-ven / ETF+FONDI 23:30 lun-mer-ven |
| ✅ Universo ETF EU ACC | +60 ETF settoriali/tematici/factor → totale 1.198 |
| ✅ Deduplicazione ETF per ISIN | Preferisce ACC su DIST, poi max volume |
| ✅ Template email `{PIANO}` | In email_template.html e .txt |
| ✅ Cambio password volontario clienti | Link 🔑 in area riservata |
| ✅ Sessioni con timeout | Admin 8h fisso / Clienti 24h sliding |
| ✅ Fattura PDF — IBAN bonifico | ES83 2100 1513 7202 0070 3406 CaixaBank |
| ✅ Fattura PDF — P.IVA cliente | Mostrata se presente in dati_fiscali |
| ✅ Fattura PDF — pagina singola | Fix auto_page_break prima del footer |
| ✅ Cartella FATTURE radice progetto | Spostata da PYTHON_SCRIPTS/ a radice |
| ✅ Download fattura area clienti | GET /api/mia-fattura + link 🧾 in area riservata |
| ✅ WhatsApp Business documentato | Procedura completa in 01_DOCUMENTAZIONE_OPERATIVA/ |

---

## FUTURO (post-lancio)

| # | Cosa | Note |
|---|---|---|
| 14 | **Gestione rinnovi abbonamento** | Rinnovo, sospensione, downgrade non automatizzati |
| 15 | **IBKR API diretta** | Ordini diretti al broker — previsto piano VALUE "coming soon" |
| 16 | **Immagini DALL-E per Instagram** | Instagram richiede `image_url` — senza immagini IG non funziona |
| 17 | **Verifica CIF B23881691** | Controllare nel Registro Mercantil spagnolo |
| 18 | **Analytics social settimanali** | Metriche LinkedIn + Meta → report email admin ogni lunedì |

---

## Ordine operativo consigliato

```
OGGI (o domani)
  → [1] Cloudflare Tunnel (30 min)
  → [2] Password admin (5 min)

QUESTA SETTIMANA
  → [3] Account Brevo
  → [4] LinkedIn Developer App
  → [5] Meta App + Facebook/Instagram
  → [8-9] Meta Business Manager + WhatsApp number
  → [10-12] Token + submit template (attesa 24-48h)

DOPO IL LANCIO
  → [6-7] URL social e reminder token
  → [13] Opt-in WhatsApp dai clienti
  → [14-18] Roadmap evolutiva
```

---

*Fuerte Venture Capital SL · CIF B23881691 · marketing@fuerteventurecapital.com*  
*Documento aggiornato il 14/06/2026*
