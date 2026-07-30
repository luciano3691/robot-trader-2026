# 🤖 TRADING ANALYZER
## Sistema di Analisi Tecnica con Alpha Vantage API

**Powered by Fuerte Venture Capital / NCF New Capital Fuerte SL**

---

## 📋 COSA FA QUESTO PROGRAMMA

Analizza azioni, ETF e altri strumenti finanziari usando indicatori tecnici professionali:
- **RSI** (Relative Strength Index) - identifica condizioni di ipervenduto/ipercomprato
- **MACD** (Moving Average Convergence Divergence) - momentum del prezzo
- **Bollinger Bands** - volatilità e range di prezzo

**Output:** File Excel professionale con:
- ✅ Segnali BUY/SELL/HOLD chiari
- ✅ Dashboard grafico
- ✅ Storico prezzi
- ✅ Tutti gli indicatori tecnici

---

## 🚀 INSTALLAZIONE (ISTRUZIONI PASSO PASSO)

### PASSO 1: Verifica se hai Python installato

**Su Windows:**
1. Premi il tasto Windows
2. Scrivi "cmd" e premi Invio
3. Nella finestra nera che si apre, scrivi:
   ```
   python --version
   ```
4. Se vedi qualcosa tipo "Python 3.10.X" o "Python 3.11.X" → **PERFETTO, vai al PASSO 2**
5. Se vedi "comando non riconosciuto" → **DEVI INSTALLARE PYTHON, leggi sotto**

**Su Mac:**
1. Apri "Terminale" (puoi trovarlo con Spotlight, premi Cmd+Spazio e scrivi "terminale")
2. Scrivi:
   ```
   python3 --version
   ```
3. Se vedi "Python 3.X.X" → **PERFETTO, vai al PASSO 2**
4. Altrimenti **DEVI INSTALLARE PYTHON, leggi sotto**

---

### 🔧 SE NON HAI PYTHON: COME INSTALLARLO

**Windows:**
1. Vai su: https://www.python.org/downloads/
2. Clicca sul bottone giallo "Download Python 3.12.X"
3. Apri il file scaricato
4. **IMPORTANTE:** Metti la spunta su "Add Python to PATH" (in basso)
5. Clicca "Install Now"
6. Aspetta che finisca
7. Riavvia il computer
8. Riprova PASSO 1

**Mac:**
1. Apri Terminale
2. Installa Homebrew (se non ce l'hai già), copia e incolla:
   ```
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
3. Poi installa Python:
   ```
   brew install python
   ```
4. Riprova PASSO 1

---

### PASSO 2: Scarica i file del programma

Hai ricevuto questi file:
- `trading_analyzer.py` (il programma principale)
- `requirements.txt` (lista librerie necessarie)
- `.env.example` (file configurazione)
- `README.md` (questo file)

**Crea una cartella sul tuo computer** (esempio: "TradingBot" sul Desktop) e **metti tutti i file lì dentro**.

---

### PASSO 3: Apri il terminale nella cartella

**Su Windows:**
1. Apri la cartella dove hai messo i file
2. Clicca sulla barra in alto (dove c'è il percorso, es: C:\Users\TuoNome\Desktop\TradingBot)
3. Scrivi "cmd" e premi Invio
4. Si aprirà il terminale già nella cartella giusta

**Su Mac:**
1. Apri Terminale
2. Scrivi "cd " (cd seguito da uno spazio)
3. Trascina la cartella con i file nella finestra del Terminale
4. Premi Invio

---

### PASSO 4: Installa le librerie necessarie

Nel terminale, copia e incolla questo comando e premi Invio:

**Windows:**
```
pip install -r requirements.txt
```

**Mac:**
```
pip3 install -r requirements.txt
```

**Aspetta che finisca** (potrebbero volerci 1-2 minuti). Vedrai scorrere del testo.

Quando finisce e torna il cursore lampeggiante, sei pronto! ✅

---

### PASSO 5: Ottieni la tua API Key Alpha Vantage (GRATIS)

1. Vai su: https://www.alphavantage.co/support/#api-key
2. Inserisci la tua email
3. Accetta i termini
4. Clicca "GET FREE API KEY"
5. Ti arriva un'email con la tua chiave (tipo: ABC123XYZ456)
6. **COPIA quella chiave** (la userai nel prossimo passo)

---

### PASSO 6: Configura la tua API Key

1. Nella cartella con i file, trova il file `.env.example`
2. **Rinominalo** in `.env` (togli ".example")
   - **Su Windows:** Tasto destro sul file → Rinomina → Cambia in ".env"
   - **Su Mac:** Tasto destro → Rinomina → Cambia in ".env"
3. Apri il file `.env` con un editor di testo (Notepad su Windows, TextEdit su Mac)
4. Trova la riga:
   ```
   ALPHA_VANTAGE_API_KEY=la_tua_chiave_qui
   ```
5. **Sostituisci** "la_tua_chiave_qui" con la vera chiave che hai copiato al PASSO 5
   
   Esempio:
   ```
   ALPHA_VANTAGE_API_KEY=ABC123XYZ456
   ```
6. Salva il file (Ctrl+S o Cmd+S)

---

## ▶️ COME USARE IL PROGRAMMA

### LANCIO NORMALE

Nel terminale (sempre nella cartella dei file), esegui:

**Windows:**
```
python trading_analyzer.py
```

**Mac:**
```
python3 trading_analyzer.py
```

Il programma partirà e vedrai:
```
🤖 TRADING ANALYZER - Alpha Vantage + Claude AI
   by Fuerte Venture Capital / NCF New Capital Fuerte SL
```

Scaricherà i dati, analizzerà i ticker e creerà i file Excel.

**ATTENZIONE:** Alpha Vantage ha un limite di 5 chiamate al minuto, quindi il programma fa pause automatiche di 12 secondi tra un ticker e l'altro.

---

## ⚙️ PERSONALIZZAZIONE

### Cambiare i ticker da analizzare

1. Apri `trading_analyzer.py` con un editor di testo
2. Trova la riga 357 circa:
   ```python
   tickers = ["AAPL", "MSFT", "GOOGL"]
   ```
3. Modifica questa lista a tuo piacimento, esempio:
   ```python
   tickers = ["AAPL", "TSLA", "NVDA", "SPY", "QQQ"]
   ```
4. Salva il file
5. Rilancia il programma

**NOTA:** Ogni ticker richiede 4 chiamate API (prezzo + RSI + MACD + Bollinger Bands), quindi 5 ticker = 20 chiamate = 4 minuti di attesa minima.

---

## 📊 RISULTATO

Per ogni ticker analizzato, il programma crea un file Excel nella stessa cartella:

**Nome file:** `trading_analysis_AAPL_20260420_143022.xlsx`

**Contiene 3 sheet:**
1. **📊 Dashboard** - Segnale principale (BUY/SELL/HOLD) + spiegazione
2. **📈 AAPL Prezzi** - Storico prezzi (open, high, low, close, volume)
3. **📊 AAPL Indicatori** - RSI, MACD, Bollinger Bands per ogni giorno

---

## 🎯 INTERPRETAZIONE SEGNALI

| Segnale | Significato | Azione suggerita |
|---------|-------------|------------------|
| 🟢 **BUY** | RSI oversold (<30) + momentum positivo | Considerare acquisto |
| 🟡 **BUY (moderato)** | RSI sotto 40 + momentum positivo | Possibile opportunità |
| ⚪ **HOLD** | Situazione neutrale | Mantenere posizione |
| 🟠 **SELL (moderato)** | RSI sopra 60 + momentum negativo | Possibile correzione |
| 🔴 **SELL** | RSI overbought (>70) + momentum negativo | Considerare vendita |

**DISCLAIMER:** Questi segnali sono puramente tecnici e non costituiscono consulenza finanziaria. Fai sempre le tue ricerche prima di investire.

---

## ❓ RISOLUZIONE PROBLEMI

### "comando non riconosciuto"
→ Python non installato o non nel PATH. Torna al PASSO 1.

### "API Key non trovata"
→ File `.env` non rinominato correttamente o chiave non inserita. Torna al PASSO 6.

### "Limite API raggiunto"
→ Hai fatto troppe chiamate in 1 minuto. Aspetta 60 secondi e riprova.

### "Ticker non valido: XXX"
→ Il simbolo ticker non esiste. Verifica su Yahoo Finance o Google Finance.

### "ModuleNotFoundError: No module named 'requests'"
→ Librerie non installate. Torna al PASSO 4.

---

## 📞 SUPPORTO

Per problemi o domande:
- **Email:** info@fuerteventurecapital.com
- **Website:** [Fuerte Venture Capital](https://fuerteventurecapital.com)

---

## 📜 LICENZA

© 2026 Fuerte Venture Capital / NCF New Capital Fuerte SL
Tutti i diritti riservati.

Questo software è fornito "così com'è", senza garanzie di alcun tipo.
L'utente è responsabile dell'uso del software e delle decisioni di investimento.

---

**Buon Trading! 📈**
