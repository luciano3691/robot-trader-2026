# WhatsApp Business Cloud API — Procedura Setup
**Progetto:** Robot Trader 2026 — Fuerte Venture Capital SL  
**Stato:** DA FARE — codice pronto, mancano account e numero di telefono  
**Data documento:** 2026-06-14

---

## Prerequisiti da procurare (una-tantum)

| Cosa | Stato | Note |
|---|---|---|
| Meta Business Manager verificato | ⏳ DA FARE | Verifica CIF B23881691 |
| WhatsApp Business Account | ⏳ DA FARE | Dipende da Business Manager |
| Numero di telefono dedicato | ⏳ DA FARE | Non già usato su WhatsApp |
| Token permanente (System User) | ⏳ DA FARE | Dipende dai precedenti |
| Template `screener_pronto` approvato | ⏳ DA FARE | 24-48h dopo sottomissione |
| Template `brief_mattutino` approvato | ⏳ DA FARE | 24-48h dopo sottomissione |

---

## Test in Sandbox (fattibile SUBITO senza nulla di quanto sopra)

È possibile testare senza Business Manager verificato, senza numero dedicato e senza template approvati.

### Come attivare la Sandbox Meta

1. Vai su **developers.facebook.com** con il tuo account Facebook personale
2. **Le mie app → Crea app → Tipo: Business**
3. Nome: `Robot Trader 2026 TEST`
4. Dashboard app → **Aggiungi prodotto → WhatsApp → Configura**
5. Meta ti assegna un **numero di test gratuito** (es. +1 555 123 4567)
6. Vai su **WhatsApp → API Setup**:
   - Copia il **Temporary access token** (dura 24h, rinnovabile manualmente)
   - Copia il **Phone Number ID** del numero di test
7. Sezione **"To"** → aggiungi i tuoi numeri personali come destinatari di test (max 5)
   - Ogni numero deve scansionare un QR code per aderire alla sandbox

### Limiti sandbox
- Puoi inviare solo ai numeri aggiunti manualmente (non a tutti)
- Il token dura 24h (non il token permanente)
- I template non devono essere approvati — puoi usare `hello_world` (template di default Meta)
- Perfetto per testare il codice end-to-end

### Test dalla CLI (dopo aver riempito config.json con i dati sandbox)

```bash
cd "Robot Trader 2026/PYTHON_SCRIPTS"

# Verifica configurazione e clienti opt-in
python whatsapp_service.py

# Invia template di test al tuo numero personale
python whatsapp_service.py test +39XXXXXXXXXX
```

### config.json per sandbox test

```json
"whatsapp": {
  "token": "EAAxxxxxx....",
  "phone_number_id": "123456789012345",
  "waba_id": "",
  "api_version": "v19.0",
  "templates": {
    "screener_pronto": "hello_world",
    "brief_mattutino": "hello_world"
  }
}
```

> Nota: in sandbox usa `"hello_world"` come nome template (è il solo pre-approvato da Meta).  
> Quando vai in produzione sostituisci con `"screener_pronto"` e `"brief_mattutino"`.

---

## Procedura Completa (produzione)

### PASSO 1 — Verifica Business Manager

1. Vai su **business.facebook.com**
2. Crea o accedi al Business Manager di Fuerte Venture Capital
3. **Impostazioni Business → Centro sicurezza → Avvia la verifica**
4. Dati da inserire:
   - Nome azienda: `Fuerte Venture Capital SL`
   - CIF: `B23881691`
   - Indirizzo: `Calle Puipana 3, 35640 Villaverde, Las Palmas, España`
5. Documenti da allegare: Certificado Registro Mercantil o estratto CIF spagnolo
6. Attesa: **1-5 giorni lavorativi**

---

### PASSO 2 — Crea App Meta

1. **developers.facebook.com → Le mie app → Crea app**
2. Tipo: **Business**
3. Nome: `Robot Trader 2026`
4. Business Manager: seleziona Fuerte Venture Capital
5. Dashboard app → **Aggiungi prodotto → WhatsApp → Configura**

---

### PASSO 3 — Numero di telefono dedicato

Serve un numero **non già usato su WhatsApp** (personale o Business App).

**Opzioni:**
| Opzione | Costo | Pro | Contro |
|---|---|---|---|
| SIM italiana prepagata | ~€5 una tantum | Affidabile, SMS | Fisica da tenere attiva |
| Numero virtuale (Twilio, VoIP.ms) | ~€5/mese | Flessibile, online | Setup aggiuntivo |
| Numero fisso aziendale inutilizzato | €0 | Già disponibile | Serve ricezione SMS/chiamata |

**In Meta Developers → WhatsApp → Gestione numeri di telefono → Aggiungi numero:**
1. Inserisci il numero
2. Verifica con SMS o chiamata vocale
3. Annota il **Phone Number ID** che appare

---

### PASSO 4 — Token Permanente (System User)

> ⚠ Non usare il token temporaneo in produzione: scade ogni 24h.

1. **business.facebook.com → Impostazioni Business → Utenti → Utenti di sistema**
2. Crea: nome `robot-trader-api`, ruolo **ADMIN**
3. **Genera token** → seleziona l'app `Robot Trader 2026`
4. Permessi obbligatori:
   - `whatsapp_business_messaging`
   - `whatsapp_business_management`
5. Scadenza: **Mai**
6. Copia il token (mostrato **una sola volta** — salvalo subito)

Annota anche il **WABA ID** (WhatsApp Business Account ID), visibile in Gestione WhatsApp.

---

### PASSO 5 — Compila config.json

```json
"whatsapp": {
  "token": "EAAxxxxxxxxxxxxxx",
  "phone_number_id": "123456789012345",
  "waba_id": "987654321098765",
  "api_version": "v19.0",
  "templates": {
    "screener_pronto": "screener_pronto",
    "brief_mattutino": "brief_mattutino"
  }
}
```

File: `Robot Trader 2026/PYTHON_SCRIPTS/config.json`

---

### PASSO 6 — Crea i Template in Meta

**Meta Developers → WhatsApp → Gestione template messaggi → Crea template**

#### Template 1: `screener_pronto`

| Campo | Valore |
|---|---|
| Categoria | UTILITY |
| Nome | `screener_pronto` |
| Lingua | Italiano (it) |

Testo corpo (copia esatto):
```
Ciao {{1}}, i tuoi segnali Robot Trader ({{2}}) del {{3}} sono pronti.

Accedi alla tua area clienti:
{{4}}

Fuerte Venture Capital — Robot Trader 2026
Rispondi STOP per disattivare le notifiche.
```

Parametri: `{{1}}`=nome cliente, `{{2}}`=piani attivi, `{{3}}`=data, `{{4}}`=link area clienti

---

#### Template 2: `brief_mattutino`

| Campo | Valore |
|---|---|
| Categoria | UTILITY |
| Nome | `brief_mattutino` |
| Lingua | Italiano (it) |

Testo corpo:
```
Buongiorno {{1}},

{{2}} è disponibile nella tua area clienti:
{{3}}

Fuerte Venture Capital — Robot Trader 2026
```

Parametri: `{{1}}`=nome cliente, `{{2}}`=titolo brief, `{{3}}`=link area clienti

**Attesa approvazione: 24-48 ore** (UTILITY più veloce di MARKETING).

---

### PASSO 7 — Test finale in produzione

```bash
cd "Robot Trader 2026/PYTHON_SCRIPTS"
python whatsapp_service.py test +39XXXXXXXXXX
```

Risposta attesa: `✅ OK`

---

### PASSO 8 — Abilita opt-in clienti

1. Dashboard admin → tab **Clienti**
2. Bottone 📱 accanto a ogni cliente → attiva
3. In `clienti.json` appare `"whatsapp_optin": true`
4. Il numero di telefono deve essere compilato in `dati_fiscali.telefono`

---

## Problemi comuni

| Errore | Causa | Soluzione |
|---|---|---|
| `190` - Token expired | Token temporaneo scaduto | Usa System User token (Mai) |
| `132000` - Template not found | Nome template errato | Verifica nome in Gestione template |
| `131030` - Number not in allowlist | Sandbox: numero non aggiunto | Aggiungi numero in API Setup |
| Business Manager non verificato | Documenti in attesa | Aspetta 1-5 gg lavorativi |
| Numero già su WhatsApp personale | Conflitto account | Disassocia prima il numero |

---

## File di codice (già pronti — non modificare)

| File | Funzione |
|---|---|
| `PYTHON_SCRIPTS/whatsapp_service.py` | Modulo principale — send_template, notify_screener_ready, notify_morning_brief |
| `PYTHON_SCRIPTS/scheduler_daemon.py` | Chiama notify_screener_ready alle 23:00 dopo orchestrator |
| `PYTHON_SCRIPTS/config.json` | Credenziali — sezione `whatsapp` |
| `PYTHON_SCRIPTS/clienti.json` | Opt-in clienti — campo `whatsapp_optin` e `dati_fiscali.telefono` |
