# Stato Progetto — Robot Trader 2026

**Fuerte Venture Capital SL** · CIF B23881691 · marketing@fuerteventurecapital.com  
**Ultimo aggiornamento:** 01/07/2026  
**Path progetto:** `C:\Users\lucia\Desktop\Robot Trader 2026\PYTHON_SCRIPTS\`

---

## Modifiche applicate — 01/07/2026

### Fix performance server — ThreadingMixIn

| File | Modifica |
|---|---|
| `dashboard.py` | Aggiunto `ThreadingMixIn` a HTTPServer — richieste gestite in parallelo |
| `dashboard.py` | Tempo risposta: da 58 secondi → 4 millisecondi |

**Causa:** HTTPServer stdlib Python è single-thread. Con ngrok che apre più connessioni parallele, le richieste si incodavano. Risolto con `ThreadedHTTPServer(ThreadingMixIn, HTTPServer)`.

---

### ngrok dedicato Robot Trader 2026

| Parametro | Valore |
|---|---|
| Account | `newcapitalfuerte@gmail.com` |
| Authtoken | `3FtqUuhLTKb99VuJRfNXIgsr72B_6EoBYhmSRKLM15qre3hHP` |
| Dominio statico | `plaza-gothic-barcode.ngrok-free.dev` |
| File config | `NGROK/ngrok_authtoken.txt` + `NGROK/ngrok_domain.txt` |
| `config.json base_url` | `https://plaza-gothic-barcode.ngrok-free.dev` |

**Avvio ngrok corretto (da WSL):**
```bash
cmd.exe /c start /min "" "C:\Users\lucia\Desktop\Robot Trader 2026\PYTHON_SCRIPTS\ngrok.exe" http --url=plaza-gothic-barcode.ngrok-free.dev http://localhost:5000
```
⚠️ NON usare `pkill` da WSL per fermare ngrok.exe — usare `taskkill.exe /IM ngrok.exe /F`

---

### PWA (Progressive Web App) — Installa su Android ✅ TESTATA

| File | Modifica |
|---|---|
| `dashboard.py` | Nuova route `GET /manifest.json` — manifest PWA con nome "Robot Trader 2026" |
| `dashboard.py` | Nuova route `GET /sw.js` — service worker minimale (network-first, richiesto da Chrome) |
| `dashboard.py` | Nuova route `GET /icons/icon-192.png` e `/icons/icon-512.png` — serve il logo PNG esistente |
| `dashboard.py` | Nuovo metodo `_raw(body, ctype)` nella classe handler — risposta HTTP binaria generica |
| `dashboard.py` | `_build_area_clienti()`: aggiunto `<link rel="manifest">` + meta PWA nel `<head>` |
| `dashboard.py` | `_build_area_clienti()`: banner installazione con pulsante "⬇ Installa" + dismiss |
| `dashboard.py` | `_build_area_clienti()`: JS registrazione SW + listener `beforeinstallprompt` + `appinstalled` |

**Flusso installazione su Android:**
1. Cliente apre `/area-clienti` in Chrome Android
2. Chrome riconosce la PWA (manifest + SW) e memorizza il prompt
3. Appare il banner dorato "Installa Robot Trader 2026 — Accedi ai tuoi report dalla schermata home"
4. Cliente tocca **⬇ Installa** → Chrome mostra dialogo nativo "Aggiungi alla schermata home"
5. App si avvia in modalità standalone (senza barra indirizzo, come app nativa)
6. L'icona dell'app usa il logo Fuerte esistente

**Comportamento banner:**
- Visibile solo se Chrome è pronto a installare (evento `beforeinstallprompt`)
- Dismissibile con ✕ → non riappare per tutta la sessione (sessionStorage)
- Si nasconde automaticamente dopo l'installazione (evento `appinstalled`)

**Requisito deployment:**
- Il sito **deve essere servito su HTTPS** per il prompt di installazione → già previsto con Cloudflare Tunnel

---

## Stato precedente (30/06/2026) — invariato

Vedere `Stato_Progetto_RobotTrader2026_20260630.md` per lo stato completo del sistema prima di questa sessione.

---

## Semaforo attuale

### ✅ FUNZIONANTE (aggiornato 01/07)
- **PWA Android**: manifest + SW + banner installazione
- **Order Builder — Picker titoli dal Report**: modal con lista titoli, selezione multipla, ricerca
- 4 screener operativi (Azioni, ETF, Fondi US, Fondi EU)
- Database Universo Ticker: 9.779 strumenti
- Scheduling 3 job automatici con log
- Email report con conteggi dinamici
- Dashboard admin + area clienti
- Sistema fatture PDF automatico
- Chatbot AI (KB 5 lingue)

### ⚠️ RICHIEDE RIAVVIO SERVER
- Riavviare `START_SISTEMA_PUBBLICO.bat` per attivare le modifiche

### 🔴 BLOCCA IL LANCIO PUBBLICO (e il prompt PWA su Android)
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
