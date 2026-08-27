# Robot Trader 2026 — Stato Progetto 01/08/2026
**Sessione 11 — Security Audit dashboard.py**

---

## COSA È STATO FATTO OGGI

### Audit e remediation completa di `dashboard.py`

Analisi sistematica di 16.085 righe di codice. Identificati e risolti **12 problemi** in 3 commit pushati su GitHub (`luciano3691/robot-trader-2026`).

---

## COMMIT 1 — `799c545` — CRITICAL FIXES

### Fix #1 — Password bcrypt (era SHA-256)
**Problema:** le password clienti erano hashate con SHA-256 — algoritmo veloce, attaccabile con GPU in pochi minuti.

**Soluzione implementata:**
- `_hash_pwd()` usa ora `bcrypt.hashpw()` con salt casuale
- `_verify_pwd()` supporta **entrambi** i formati: bcrypt (nuovo) e SHA-256 (legacy) — utenti esistenti continuano a funzionare senza re-set password
- Rilevamento automatico: `stored_hash.startswith('$2b')` → bcrypt, altrimenti SHA-256

### Fix #2 — XSS su messaggi di errore
**Problema:** errori di login/cambio password venivano inseriti direttamente nell'HTML senza escape.

**Soluzione:** `html.escape(error)` su tutti i messaggi di errore inseriti in template HTML.

### Fix #3 — Password admin di default rimossa
**Problema:** se `config.json` non conteneva `admin_password`, il codice usava una stringa di default hardcoded.

**Soluzione:** `return ""` — nessuna password default. Se non configurata, il login fallisce sempre.

### Fix #4 — sessions.json chmod 600
**Problema:** il file delle sessioni era scrivibile da altri utenti del sistema.

**Soluzione:** `os.chmod(SESSIONS_FILE, 0o600)` dopo ogni scrittura atomica.

---

## COMMIT 2 — `025616c` — HIGH FIXES

### Fix #5 — SSL verificato esplicitamente
**Soluzione:** `_SSL_CTX = ssl.create_default_context()` a livello modulo, passato a ogni `urlopen()` — tre punti nel codice.

### Fix #6 — CORS ristretto
**Problema:** `Access-Control-Allow-Origin: *` — qualunque sito poteva fare richieste cross-origin.

**Soluzione:** `CORS_ORIGIN = BASE_URL.rstrip('/')` — solo il dominio configurato è autorizzato.

### Fix #7 — Codice Fiscale mascherato nei log
**Problema:** il CF completo compariva nei log `[REG]` ad ogni registrazione.

**Soluzione:** `CF[:4] + '***'` nei log.

### Fix #8 — Ngrok command injection
**Problema:** il dominio ngrok letto dal file veniva inserito direttamente in un comando `shell=True`.

**Soluzione:** validazione regex `^[a-zA-Z0-9._-]+$` prima dell'esecuzione — se non valido, skip con warning.

---

## COMMIT 3 — `3df253a` — MEDIUM FIXES

### Fix #9 — Rate limit persistente
**Problema:** i blocchi IP per login falliti erano in-memory — sparivano a ogni riavvio del server.

**Soluzione:** `.rl_blocks.json` (chmod 600) — `_save_rl_blocks()` scritto a ogni nuovo blocco, `_load_rl_blocks()` caricato all'avvio.

### Fix #10 — Forgot-password throttle anti-enumeration
**Problema:** la route `/api/forgot-password` era priva di rate limiting.

**Soluzione:** controllo `_rl_check()` all'ingresso — se l'IP è bloccato, risponde con la **stessa pagina di successo** per non rivelare il blocco.

### Fix #11 — SHA256 come chiave sessione
**Problema:** `sessions.json` conteneva i token raw — un leak del file dava accesso diretto a tutte le sessioni.

**Soluzione:** `_get_token()` e `_get_client_token()` restituiscono `SHA256(raw_cookie)`. Il server non vede mai il token raw — solo il suo hash. Le sessioni esistenti vengono invalidate (ri-login una volta).

### Fix #12 — Session persist error logging
**Problema:** gli errori di scrittura sessioni erano inghiottiti silenziosamente (`except: pass`).

**Soluzione:** `print(f"[SESSIONS] Errore persist: {e}", flush=True)` per rendere il problema visibile.

---

## 3 ITEM RIMASTI (LOW PRIORITY — opzionali)

| # | Problema | Impatto | Note |
|---|---|---|---|
| 13 | URL fallback `http://localhost` nelle email se BASE_URL non in `.env` | Basso — solo se `.env` mancante | Rischio zero a produzione configurata |
| 14 | Validazione email minimale (`'@' not in email`) | Basso | Non blocca funzionalità |
| 15 | Placeholder Stripe `""` nel sorgente | Basso ora, medio quando verrà aggiunto | Ricordare di usare `.env` |

---

## STATO COMPLESSIVO SICUREZZA

| Livello | Problemi trovati | Risolti | Rimasti |
|---|---|---|---|
| CRITICAL | 4 | 4 ✅ | 0 |
| HIGH | 4 | 4 ✅ | 0 |
| MEDIUM | 4 | 4 ✅ | 0 |
| LOW | 3 | 0 | 3 (opzionali) |

**Giudizio:** il sistema può andare in produzione — tutti i problemi critici, alti e medi sono stati risolti.

---

## COSA MANCA PER IL GO-LIVE

### 🔴 BLOCCANTE

1. **Cloudflare Tunnel / VPS Hetzner** — il sito non è raggiungibile da internet
   - Credenziali SSH Hetzner da recuperare via console cloud
   - Installare `cloudflared` su VPS e configurare tunnel
   - Aggiornare `config.json → base_url` a `https://www.fuerteventurecapital.com`

2. **Email lancio 2.435 prospect** (Brevo bozza ID 1)
   - DA INVIARE solo dopo go-live sul dominio ufficiale

### 🟡 ALTA PRIORITÀ (post go-live)

3. **Stripe pagamenti automatici** — zero ricavi senza questo
4. **LinkedIn posting** — in attesa approvazione "Marketing Developer Platform"
5. **Meta completare** — recuperare Page ID + IG User ID

### 🟢 NICE TO HAVE

6. Items #13, #14, #15 sicurezza low-priority (vedi sopra)
7. Dashboard analytics (implementata in sessione 9, già pronta)
8. Trial 7 giorni automatico (implementato sessione 8, già pronto)

---

## RIEPILOGO SESSIONI

| Sessione | Data | Azioni |
|---|---|---|
| 1–5 | giu–lug 2026 | Screener, dashboard, area clienti, chatbot, social, WhatsApp, fatture |
| 6 | 19/07/2026 | `.env` creato, segreti migrati, social_calendar esteso, email early adopter, LinkedIn/Meta credenziali |
| 7 | 19/07/2026 | Email early adopter inviata 5/5 tester; sessioni persistenti; requirements.txt; rate limiting; validazione input |
| 8 | 19/07/2026 | Tagline INFORMATI CON INTELLIGENZAI; Trial 7gg; ticker count dinamico 10.086 |
| 9 | 19/07/2026 | Modal Brevo fix; bug do_POST; _brevo_call → requests; bozza campagna Brevo ID 1; tab Analytics |
| 10 | 29/07/2026 | Gmail SMTP fix orchestrator; logging su file; Task Scheduler Windows installato; START_SCHEDULER.bat |
| **11** | **01/08/2026** | **Security audit dashboard.py — 12 fix (bcrypt, XSS, CORS, SSL, SHA256 token, ngrok, rate limit persist)** |
| 12 | — | Go-live VPS Hetzner + email lancio prospect |
| 13 | — | Stripe pagamenti automatici |

---

*Fuerte Venture Capital SL · CIF B23881691*  
*Documento: 01/08/2026 — sessione 11*
