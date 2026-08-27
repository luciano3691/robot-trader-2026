# Stato Progetto Robot Trader 2026 — 27/08/2026 (Sessione 14)

## Attività sessione

### 1. VERA Chatbot — OTTIMIZZATA ✅

File: `chat_service.py` (VPS `/root/rt2026/` + locale `PYTHON_SCRIPTS/`)  
Commit: `a0f8f9e` — "VERA: risposte sintetiche + domanda finale garantita"

**Modifiche:**
- **SYSTEM_PROMPT:** identità VERA (Value & Research Assistant), max 80 parole, no headers/tabelle, template risposta obbligatorio (risposta → bullet opzionali → domanda finale)
- **max_tokens:** 800 → 280 (public chatbot)
- **`_EXAMPLES`:** riscritti con risposte 50-70 parole, tutti terminano con `?`
- **`_ensure_closing_question()`:** post-processor che aggiunge domanda finale se assente — rilevamento lingua (IT/ES/EN/FR/DE), appende "Hai altre domande?" o equivalente
- **Prima `return`** in `_call_claude()` ora chiama `_ensure_closing_question()` prima di restituire

**Risultato test:** risposte 44-130 parole, tutte terminano con `?` ✅

Backup: `.bak_20260827f` (ultima versione buona prima delle ottimizzazioni)

---

### 2. Fix Critico dashboard.py — SESSION_TIMEOUT ✅

**Problema:** `ADMIN_SESSION_TIMEOUT` e `CLIENT_SESSION_TIMEOUT` erano definiti alla riga 297, ma usati in `_persist_sessions()` (riga 220) e `_load_sessions()` (riga 243), entrambe chiamate PRIMA della definizione → NameError al riavvio del servizio.

**Fix:** Costanti spostate prima di `_persist_sessions()` (ora righe 213-214).  
Commit: `5abb582`

---

### 3. Stripe price_ids → LIVE ✅

**File:** `config.json`  
**Commit:** `5abb582`

I 9 price_ids in `config.json` erano ancora TEST (formato `price_1U7Vs8...`). Aggiornati ai price_ids LIVE (formato `price_1U7gi0...`):

| Piano | BASIC | PRO | VALUE |
|---|---|---|---|
| Azioni | price_1U7gi02QVjaGzlSwaG7PonKy | price_1U7gi02QVjaGzlSw7DuBInkc | price_1U7gi02QVjaGzlSwRn1frt90 |
| ETF | price_1U7gi02QVjaGzlSw17ITD28H | price_1U7gi02QVjaGzlSwS0EGPPhS | price_1U7gi02QVjaGzlSw9N1Pm1rt |
| Fondi | price_1U7gi02QVjaGzlSwAk13Z10D | price_1U7gi02QVjaGzlSwVzqmgea9 | price_1U7gi02QVjaGzlSwv8XkNggS |

---

### 4. Test Processo Completo — SUPERATO ✅

**Flusso testato end-to-end:**

1. **Email campagna settembre** → inviata a rioluc63@gmail.com via Brevo API  
   - Oggetto: "💸 Il Tuo Stipendio Ti Sta Tradendo · Robot Trader 2026 — Settembre"
   - Body: SALARY_TRAP (+2% stipendi vs +3.5% inflazione), statistiche, piani
   - Footer: logo FVC 72×72px circolare + dati societari MiFID

2. **VERA chatbot** → test interazione → risposte brevi + domanda finale ✅

3. **Acquisto simulato** → webhook Stripe `checkout.session.completed`  
   - **Fix HMAC:** il secret deve essere usato COMPLETO con prefisso `whsec_`  
     (il server usa `STRIPE_WEBHOOK_SECRET` as-is — NON strippare il prefisso)
   - Payload corretto: `metadata: {"asset": "azioni", "tier": "basic"}` (NON `asset_type`)
   - Risposta server: HTTP 200 `{"ok": true}`

4. **Cliente creato** in `clienti.json`:
   - nome: Luciano Manicardi
   - email: rioluc63@gmail.com
   - piano_azioni: BASIC
   - password temporanea generata automaticamente

5. **Fattura generata** → `/root/FATTURE/FVC-2026-0032.pdf` ✅

6. **Email credenziali** → `[EMAIL] Credenziali inviate a rioluc63@gmail.com` ✅  
   - Allegato: Fattura_FVC-2026-0032.pdf
   - Link: area riservata + profilo investitore MiFID II
   - **CONFERMATA RICEVUTA** dall'utente

Fatture counter attuale: `{"ultimo": 32}` (il test ha consumato il numero 32 — entry di test poi rimossa da clienti.json)

---

### 5. Social — Token Scaduti ⚠️ DA FARE

| Canale | Stato | Azione richiesta |
|---|---|---|
| **Meta (Facebook)** | ❌ Errore 190/492 — token scaduto | Rinnovare META_PAGE_ACCESS_TOKEN in Meta Business Manager (manuale ogni 60gg) |
| **LinkedIn** | ❌ `LINKEDIN_ACCESS_TOKEN` vuoto | OAuth completo con scope `w_organization_social` + version `202601` |
| Instagram | ⏳ Dipende da Meta | Dopo rinnovo token Meta |

---

## Git — stato finale sessione

```
commit 5abb582  fix: SESSION_TIMEOUT prima di _persist_sessions + Stripe price_ids LIVE
commit a0f8f9e  VERA: risposte sintetiche + domanda finale garantita
commit 20ec80f  Stripe LIVE + sync PDF locale + config WhatsApp corretti
```

Branch: `main` → pushato su GitHub ✅

---

## TODO Prioritari per lancio 1/9

| Priorità | Task | Stato |
|---|---|---|
| 🔴 1 | Rinnovo META_PAGE_ACCESS_TOKEN (Facebook) | ⚠️ Da fare — manuale in Meta Business Manager |
| 🔴 2 | LinkedIn OAuth (token + versione 202601) | ⚠️ Da fare — OAuth completo |
| 🟠 3 | WhatsApp SMS +34 680 67 87 34 — rate limit Meta | ⏳ Riprovare (rate limit scade 24-48h) |
| 🟠 4 | Test post social reale (3.1-3.6) | ⏳ Dopo rinnovo token |
| 🟡 5 | Estrarre html_client.py da dashboard.py | Futuro |
