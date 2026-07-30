# TODO — Punti in Sospeso
## Robot Trader 2026 / Fuerte Venture Capital SL

**Ultimo aggiornamento:** 04/06/2026  
**Stato sistema:** Sviluppo completato — pre-lancio  
**URL target:** https://www.fuerteventurecapital.com

---

## BLOCCO 1 — CRITICO (blocca il lancio)

> Questi 4 punti devono essere completati prima che il sistema vada online.

| # | Cosa fare | Dettaglio | Dove |
|---|---|---|---|
| 1 | **Cloudflare Tunnel** | Scaricare `cloudflared.exe` da GitHub, eseguire i 3 bat in sequenza, inserire UUID in `config.yml`, aggiornare `config.json → base_url` | `CLOUDFLARE_TUNNEL\` — procedura completa in `Stato_Progetto_RobotTrader2026_20260604.md` |
| 2 | **Password admin** | Cambiare `ADMIN_PASSWORD = "123"` con password sicura | `PYTHON_SCRIPTS\dashboard.py` riga 61 |
| 3 | **Stripe keys** | Inserire `STRIPE_SECRET_KEY` e `STRIPE_PUBLISHABLE_KEY` reali | `PYTHON_SCRIPTS\dashboard.py` riga ~3061 |
| 4 | **Email marketing@fuerteventurecapital.com** | Verificare che la casella sia attiva e riceva messaggi | Email provider (Cloudflare / Mailgun / altro) |

---

## BLOCCO 2 — SOCIAL AUTOMATION (codice pronto — solo credenziali)

> Il codice è scritto e funzionante. Serve solo compilare `config.json → social{}` quando gli account sono pronti.

| # | Cosa fare | Credenziale da inserire | Config |
|---|---|---|---|
| 5 | **Account Brevo** | `api_key`, `smtp_login`, `smtp_password`, `list_ids[]` | `config.json → social.brevo` |
| 6 | **LinkedIn Company Page FVC** + Developer App | `client_id`, `client_secret`, `org_id` | `config.json → social.linkedin` |
| 7 | **Facebook Page FVC** + **Instagram Business** + Meta App | `app_id`, `app_secret`, `page_id`, `ig_user_id` | `config.json → social.meta` |
| 8 | **Anthropic API key** | `api_key` (per generazione testi AI con Claude) | `config.json → social.anthropic.api_key` |
| 9 | **Aggiornare `social.brevo.base_url`** | Da `http://localhost:5000` a `https://www.fuerteventurecapital.com` | Fare dopo Cloudflare Tunnel attivo |
| 10 | **Reminder rinnovo token LinkedIn** | Il token OAuth scade ogni 60 giorni — mettere evento ricorrente in calendario | Calendario |

---

## BLOCCO 3 — WHATSAPP BUSINESS (codice pronto — attesa approvazione Meta)

> Il modulo `whatsapp_service.py` è completo. Servono le credenziali Meta e l'approvazione dei template (~24-48h).

| # | Cosa fare | Dettaglio |
|---|---|---|
| 11 | **Meta Business Manager — verifica azienda** | Accedere a business.facebook.com con CIF B23881691 |
| 12 | **WhatsApp Business Account** | Aggiungere numero di telefono dedicato (SIM business) |
| 13 | **Ottenere token permanente e phone_number_id** | Da Meta Developer App → prodotto WhatsApp → inserire in `config.json → whatsapp` |
| 14 | **Sottomettere template `screener_pronto`** | Testo pronto nel commento iniziale di `whatsapp_service.py` — 4 parametri |
| 15 | **Sottomettere template `brief_mattutino`** | Testo pronto nel commento iniziale di `whatsapp_service.py` — 3 parametri |
| 16 | **Raccogliere opt-in dai clienti** | Consenso WhatsApp esplicito (GDPR) → attivare da Dashboard admin → tab Clienti → bottone 📱 |

### Template da sottomettere a Meta

**`screener_pronto`** — inviato ogni sera dopo lo screener (23:00):
```
Ciao {{1}}, i tuoi segnali Robot Trader ({{2}}) del {{3}} sono pronti.

Accedi alla tua area clienti:
{{4}}

Fuerte Venture Capital — Robot Trader 2026
Rispondi STOP per disattivare le notifiche.
```

**`brief_mattutino`** — inviato ogni lunedì/mercoledì/venerdì (08:00):
```
Buongiorno {{1}},

{{2}} è disponibile nella tua area clienti:
{{3}}

Fuerte Venture Capital — Robot Trader 2026
```

---

## BLOCCO 4 — QUALITÀ (non blocca il lancio)

> Da affrontare dopo il go-live, migliora la robustezza del prodotto.

| # | Cosa | Impatto |
|---|---|---|
| 17 | **Deduplicazione ETF per ISIN** | Stesso ETF su più exchange selezionato più volte nei risultati |
| 18 | **Reset password clienti self-service** | Attualmente solo l'admin può reimpostare la password |
| 19 | **Scadenza automatica sessioni admin** | Le sessioni non scadono — reset solo al riavvio del server |
| 20 | **Fattura PDF → integrazione Stripe** | La fattura viene generata ma non è collegata al pagamento Stripe |
| 21 | **Verifica CIF B23881691** | Controllare nel Registro Mercantil spagnolo che sia attivo e corretto |

---

## BLOCCO 5 — FUTURO (post-lancio)

> Roadmap evolutiva — da pianificare dopo aver acquisito i primi clienti paganti.

| # | Cosa | Note |
|---|---|---|
| 22 | **Scheduling separato Azioni vs ETF/Fondi** | Azioni ogni giorno (dati real-time), ETF/Fondi il giorno dopo (dati 24-48h) |
| 23 | **Console CRM B2B collegata** | Progetto separato "Line Express" — `brevo_service.py` riutilizzabile |
| 24 | **Gestione rinnovi abbonamento automatica** | Rinnovo, sospensione, downgrade non automatizzati |
| 25 | **IBKR API diretta** | Ordini diretti all'broker — previsto per piano VALUE ("coming soon") |
| 26 | **Immagini DALL-E 3 per Instagram** | Instagram richiede `image_url` — senza immagini la pubblicazione IG non funziona |
| 27 | **Analytics social settimanali** | Metriche LinkedIn + Meta → report email admin ogni lunedì |
| 28 | **Rinnovo automatico token LinkedIn** | Il token scade ogni 60 giorni — oggi è manuale |

---

## Riepilogo contatori

| Blocco | Punti | Stato |
|---|---|---|
| Critico (blocca lancio) | 4 | ❌ Da fare |
| Social Automation | 6 | ⏳ Attesa credenziali |
| WhatsApp Business | 6 | ⏳ Attesa Meta (~1-2 settimane) |
| Qualità | 5 | 🔜 Post-lancio |
| Futuro | 7 | 📅 Roadmap |
| **TOTALE** | **28** | |

---

## Ordine operativo consigliato

```
OGGI (o domani)
  → [1] Cloudflare Tunnel (30 min)
  → [2] Password admin (5 min)
  → [3] Stripe keys (10 min)
  → [4] Verifica email marketing@fuerteventurecapital.com

QUESTA SETTIMANA
  → [5] Account Brevo (30 min)
  → [6] LinkedIn Developer App (60 min)
  → [7] Meta App + Facebook/Instagram (60 min)
  → [8] Anthropic API key (5 min)
  → [11-12] Meta Business Manager + WhatsApp number (30 min)
  → [13-15] Token WhatsApp + submit template (30 min + attesa 24-48h)

DOPO IL LANCIO
  → [9-10] URL social e reminder token
  → [16] Opt-in WhatsApp dai clienti
  → [17-21] Miglioramenti qualità
  → [22-28] Roadmap evolutiva
```

---

*Fuerte Venture Capital SL · CIF B23881691 · marketing@fuerteventurecapital.com*  
*Documento generato il 04/06/2026*
