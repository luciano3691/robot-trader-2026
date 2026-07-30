# CONFIGURAZIONE N8N - ROBOT TRADER 2026
# Istruzioni passo-passo per collegare landing pages a backend Flask

## ARCHITETTURA COMPLETA
```
Landing Page (3 file HTML)
    ↓ POST JSON
N8N Webhook (già configurato)
    ↓ POST JSON
Backend Flask (localhost:5000)
    ↓ Salva in
clienti.json
    ↓ Letto da
Dashboard (localhost:5000/api/clienti)
```

## STEP 1 - VERIFICA WEBHOOK N8N ESISTENTE

Il tuo webhook N8N è già configurato:
```
https://lucianomanicardi.app.n8n.cloud/webhook/43f339e1-17d6-4bcb-a3f7-5165c32e9c2f
```

Riceve questo JSON dalle landing pages:
```json
{
  "nome": "Mario Rossi",
  "email": "mario@example.com",
  "piano": "BASIC",
  "screener": ["AZIONI"]
}
```

## STEP 2 - CONFIGURA N8N WORKFLOW

Vai su n8n.cloud e modifica il workflow:

### 2.1 Webhook Node (già esistente)
- URL: `/webhook/43f339e1-17d6-4bcb-a3f7-5165c32e9c2f`
- Method: POST
- Response Mode: immediato

### 2.2 Aggiungi HTTP Request Node
- Nome: "Invia a Backend Flask"
- Method: POST
- URL: `http://TUO_IP_PUBBLICO:5000/api/clienti/register`
  
  **IMPORTANTE:** Sostituisci TUO_IP_PUBBLICO con:
  - Se backend sul tuo PC: usa ngrok o indirizzo IP pubblico
  - Se backend su server: usa IP server

- Headers:
  ```
  Content-Type: application/json
  ```

- Body: 
  - Send Body: Yes
  - Body Content Type: JSON
  - Specify Body: Using JSON
  - JSON:
    ```json
    {
      "nome": "{{ $json.nome }}",
      "email": "{{ $json.email }}",
      "piano": "{{ $json.piano }}",
      "screener": "{{ $json.screener }}"
    }
    ```

### 2.3 Collega i nodi
```
Webhook → HTTP Request (Backend Flask)
```

### 2.4 Salva e Attiva Workflow

## STEP 3 - ESPOSIZIONE BACKEND (se su PC locale)

### Opzione A: NGROK (consigliata per test)
```powershell
# Installa ngrok: https://ngrok.com/download
ngrok http 5000
```

Ti darà un URL tipo: `https://abc123.ngrok.io`
Usa questo in N8N al posto di `http://TUO_IP_PUBBLICO:5000`

### Opzione B: Port Forwarding Router
- Apri porta 5000 sul router
- Usa IP pubblico: `http://TUO_IP_PUBBLICO:5000`

## STEP 4 - AVVIA BACKEND

```powershell
cd "C:\Users\lucia\Desktop\ROBOT TRADER 2026\PYTHON_SCRIPTS"
python clienti_backend.py
```

Dovresti vedere:
```
🚀 BACKEND CLIENTI - ROBOT TRADER 2026
📁 File clienti: C:\Users\lucia\...\clienti.json
🌐 Endpoints disponibili:
   GET  /api/clienti - Lista clienti
   POST /api/clienti/register - Registra nuovo cliente
⚠️  N8N deve fare POST a: http://localhost:5000/api/clienti/register
```

## STEP 5 - TEST COMPLETO

### Test 1: Backend Locale
```powershell
curl http://localhost:5000/health
# Risposta attesa: {"status":"ok","service":"Robot Trader 2026 - Clienti API"}
```

### Test 2: Registrazione Cliente
Apri una landing page (es. 3A_LANDING_PAGE_AZIONI_FINAL.html) e compila il form.

Se tutto funziona:
1. Landing page → mostra alert "✅ Registrazione completata!"
2. N8N → riceve webhook e invia a Flask
3. Flask → salva in clienti.json e stampa log
4. Dashboard → mostra nuovo cliente in tabella

### Test 3: Verifica Dashboard
```powershell
curl http://localhost:5000/api/clienti
```

Dovresti vedere:
```json
{
  "totale": 1,
  "clienti": [
    {
      "nome": "Mario Rossi",
      "email": "mario@example.com",
      "piano_azioni": "BASIC",
      "piano_etf": "NONE",
      "piano_fondi": "NONE",
      "screener_attivi": ["AZIONI"],
      "stato": "ATTIVO",
      "data_registrazione": "2026-05-15T19:00:00"
    }
  ],
  "tester": []
}
```

## TROUBLESHOOTING

### Errore: "Connection refused"
- Backend non in esecuzione → avvia `python clienti_backend.py`
- Porta sbagliata → verifica 5000
- Firewall → consenti porta 5000

### Errore: "CORS policy"
- Backend ha CORS abilitato
- Verifica che Flask stampi "CORS abilitato per tutte le origini"

### Landing page mostra "❌ Errore"
1. Apri Console browser (F12)
2. Controlla errori di rete
3. Verifica URL N8N webhook

### N8N non invia a Flask
1. Verifica URL in HTTP Request node
2. Testa manualmente:
   ```powershell
   curl -X POST http://localhost:5000/api/clienti/register \
     -H "Content-Type: application/json" \
     -d '{"nome":"Test","email":"test@test.com","piano":"BASIC","screener":["AZIONI"]}'
   ```

## FILE CORRELATI

- `clienti_backend.py` → Backend Flask
- `clienti.json` → Database clienti (auto-creato)
- `dashboard_FINALE_AGGIORNATA.html` → Dashboard (legge da backend)
- `3A_LANDING_PAGE_*.html` → Landing pages (inviano a N8N)

## NOTE IMPORTANTI

⚠️ Il backend deve essere SEMPRE in esecuzione quando:
- Landing pages sono attive
- Dashboard è aperta

⚠️ clienti.json è il database. Backup regolari raccomandati.

⚠️ Per produzione: considera database vero (MySQL/Postgres) invece di JSON
