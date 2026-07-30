# Stato Progetto — Robot Trader 2026

**Fuerte Venture Capital SL** · CIF B23881691 · marketing@fuerteventurecapital.com  
**Ultimo aggiornamento:** 30/06/2026 (sera)  
**Path progetto:** `C:\Users\lucia\Desktop\Robot Trader 2026\PYTHON_SCRIPTS\`

---

## Modifiche applicate — 30/06/2026 (sessione sera)

### Order Builder — Auto-popolamento tabella all'apertura (fix)

| File | Modifica |
|---|---|
| `dashboard.py` | `_pickerPreload()`: i ticker del report ora vengono aggiunti AUTOMATICAMENTE alla tabella all'apertura della pagina |
| `dashboard.py` | Rimosso banner "N titoli disponibili — clicca per selezionarli" (non più necessario) |
| `dashboard.py` | Bottoni rinominati: "+ Aggiungi altro titolo dal Report" / "Inserisci manuale" |

**Flusso corretto dopo fix:**
1. Cliente apre `/ordine-bancario?tipo=azioni`
2. I ticker del suo report appaiono AUTOMATICAMENTE nella tabella (con prezzi live)
3. Elimina quelli che non vuole (tasto ✕)
4. Imposta le quantità
5. Invia email bancaria o scarica CSV

---

## Modifiche applicate — 30/06/2026 (sessione pomeriggio)

### Order Builder — Picker titoli dal Report

| File | Modifica |
|---|---|
| `dashboard.py` | Bottone "+ Aggiungi Titolo dal Report" apre modal picker |
| `dashboard.py` | Nuovo endpoint `GET /api/ordine/report-stocks?tipo=azioni` — legge foglio "Azioni Selezionate" dall'ultimo Excel del cliente |
| `dashboard.py` | Modal picker con lista titoli, caselle selezione, ricerca, "Tutti/Nessuno" |
| `dashboard.py` | Banner informativo: "N titoli disponibili dal tuo report" caricato a pagina pronta |
| `dashboard.py` | Bottone secondario "✎ Manuale" per inserire ticker non presenti nel report |
| `dashboard.py` | Rimosso codice prefill server-side e debug file — sostituito con caricamento on-demand lato client |

**Flusso cliente:**
1. Il cliente riceve il report Excel via email
2. Va su `/ordine-bancario?tipo=azioni` (dal link in Area Riservata)
3. Vede il banner blu "N titoli disponibili dal tuo report"
4. Clicca "+ Aggiungi Titolo dal Report"
5. Si apre il modal con la lista completa dei titoli del suo screener
6. Seleziona quelli che vuole acquistare (con checkbox, ricerca per ticker/nome)
7. Clicca "Aggiungi Selezionati" → i titoli entrano nella tabella ordine
8. Imposta quantità → prezzi live da Yahoo Finance
9. Invia email bancaria o scarica CSV

**Logica lettura foglio:**
- Prima cerca foglio con "selezion" nel nome → "Azioni Selezionate" (tutti i selezionati, no sub-header)
- Fallback: foglio con "top" nel nome → "Top 20 per Score"
- Righe con spazi nel ticker (es. "Codice borsa") escluse automaticamente

**Endpoint:**
- `GET /api/ordine/report-stocks?tipo=azioni|etf|fondi` — richiede auth cliente, ritorna `[{ticker, nome, mercato, valuta, tipo}]`

---

## Modifiche applicate — 30/06/2026 (sessione mattina)

### Order Builder — Upload Report Excel (rimosso, sostituito dal Picker)

La feature "upload Excel" era pianificata ma non implementata. Sostituita dal Picker on-demand.

---

## Stato precedente (26/06/2026) — invariato

Vedere `Stato_Progetto_RobotTrader2026_20260626.md` per lo stato completo del sistema prima di questa sessione.

---

## Semaforo attuale

### ✅ FUNZIONANTE (aggiornato 30/06)
- **Order Builder — Picker titoli dal Report**: modal con lista titoli, selezione multipla, ricerca
- Bottone "✎ Manuale" per ticker liberi
- 4 screener operativi (Azioni, ETF, Fondi US, Fondi EU)
- Database Universo Ticker: 9.779 strumenti
- Scheduling 3 job automatici con log
- Email report con conteggi dinamici
- Dashboard admin + area clienti
- Sistema fatture PDF automatico
- Chatbot AI (KB 5 lingue)

### ⚠️ RICHIEDE RIAVVIO SERVER
- Riavviare `START_SISTEMA_PUBBLICO.bat` per attivare le modifiche di oggi

### 🔴 BLOCCA IL LANCIO PUBBLICO
1. **Cloudflare Tunnel** — `cloudflared.exe` non configurato
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
