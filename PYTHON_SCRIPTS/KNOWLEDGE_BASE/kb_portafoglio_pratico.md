# Costruire un Portafoglio con Robot Trader 2026 — Guida Pratica
# Building a Portfolio / Construir una Cartera / Construire un Portefeuille / Portfolioaufbau
# Robot Trader 2026 · Fuerte Venture Capital

---

## [IT] Italiano

### Dal Report all'Investimento: il Processo Completo

Robot Trader 2026 seleziona e ordina i migliori strumenti finanziari ogni sera. Ma come si usa concretamente il report per costruire un portafoglio? Questa guida risponde a questa domanda passo per passo.

---

### Step 1 — Definisci il tuo capitale e l'allocazione

Prima di aprire qualsiasi report, rispondi a queste 3 domande:

**Quanto investi?**
- Il capitale disponibile non deve includere la liquidità di emergenza (3–6 mesi di spese correnti)
- Non investire mai denaro che potresti aver bisogno nei prossimi 12 mesi

**Come distribuisci il capitale tra asset class?**
Usa il risultato del Profilo Investitore come punto di partenza. Esempio per un profilo **Bilanciato**:

| Asset class | Allocazione | Strumento Robot Trader |
|---|---|---|
| Azioni globali | 40% | Piano Azioni PRO o VALUE |
| ETF diversificati | 30% | Piano ETF PRO |
| Fondi | 15% | Piano Fondi US o EU |
| Liquidità/obbligazioni | 15% | Non coperto da Robot Trader |

**Quanto per posizione?**
- Regola pratica: **2–5% del capitale totale per singola posizione**
- Su €50.000: ogni posizione = €1.000–€2.500
- Su €100.000: ogni posizione = €2.000–€5.000
- Eccezione VALUE: portafogli più concentrati ammettono 5–8% per posizione (ma richiede alta conviction)

---

### Step 2 — Leggi il Report

Apri il file Excel scaricato dall'area clienti. La struttura è sempre uguale:

**Foglio "Dashboard":**
- Data e ora dell'elaborazione
- N° titoli analizzati, filtrati, selezionati
- Parametri attivi del piano

**Foglio "Top N per Score":**
- I migliori titoli ordinati per score decrescente (0–100)
- Colonne: Ticker, Nome, Exchange, Score, EV/FCF, P/B, ROE, Dividend Yield (Azioni) / TER, Sharpe, Perf1Y, Perf3M (ETF/Fondi)
- **Parti sempre da qui** — i titoli in cima hanno la combinazione migliore di tutte le metriche del piano

**Foglio "Selezionati":**
- Tutti i titoli che hanno superato i filtri (lista più lunga)
- Utile per trovare titoli che non sono nei top 20/50 ma hanno caratteristiche interessanti

**Foglio "Scartati" e "Non Validi" (solo piano VALUE):**
- Scartati: titoli esclusi per quale filtro specifico non hanno passato
- Non Validi: titoli con dati insufficienti su Yahoo Finance

---

### Step 3 — Seleziona le tue posizioni

**Quante posizioni aprire?**

| Capitale totale | N° posizioni consigliate | Posizione media |
|---|---|---|
| €5.000–€15.000 | 5–8 | €700–€2.500 |
| €15.000–€50.000 | 10–15 | €1.500–€3.500 |
| €50.000–€150.000 | 15–25 | €2.500–€7.000 |
| >€150.000 | 20–30 | €5.000–€10.000+ |

**Come scegliere dai Top 50:**
Non comprare meccanicamente i primi 50. Applica un secondo livello di selezione personale:

1. **Diversificazione geografica:** evita di avere tutti i titoli USA o tutti italiani. Guarda la colonna Exchange
2. **Diversificazione settoriale:** massimo 25–30% in un singolo settore GICS
3. **Dimensione aziendale:** mix di large cap (più stabili) e mid cap (più potenziale)
4. **Familiarità:** Buffett insegna — investi solo in business che capisci. Se non sai cosa fa l'azienda, approfondisci prima o salta

**Esempio pratico — Piano Azioni PRO, €50.000 totale:**
- Budget azioni: €30.000 (60% del totale)
- 15 posizioni da €2.000 ciascuna
- Prendi i Top 30 del report → escludi settori già in sovrappeso → seleziona i migliori 15 per diversificazione geografica e settoriale
- Usa l'Order Builder PRO per generare il CSV e importarlo su IBKR

---

### Step 4 — Esegui gli Ordini

**Con l'Order Builder:**
1. Accedi all'area clienti → Ordine Azioni
2. I titoli del report sono precaricati — rimuovi quelli che non vuoi
3. Inserisci l'importo totale (es. €30.000) → il sistema distribuisce automaticamente per posizione uguale
4. Oppure inserisci le quantità manualmente per posizioni diverse
5. Aggiorna i prezzi live
6. Genera CSV IBKR (PRO) o email bancaria (BASIC)

**Tipi di ordine:**
- **Market Order:** eseguito immediatamente al prezzo di mercato — vai preferire in apertura di borsa per liquidità massima
- **Limit Order:** eseguito solo se il prezzo tocca la soglia che imposti — più controllo ma rischio di non esecuzione
- **Robot Trader consiglia:** limit order vicino al prezzo di chiusura precedente (±0.5%) per titoli liquidi

---

### Step 5 — Monitora e Ribilancia

**Quando rientrare nel report?**
- Piano BASIC: ogni settimana (il report cambia ogni sera, ma non reagire ad ogni variazione)
- Piano PRO: ogni 2–4 settimane
- Piano VALUE: ogni 1–3 mesi (orizzonte lungo — non reagire al rumore di breve)

**Quando vendere una posizione?**
Non esiste una regola unica. Suggerimenti:

| Segnale | Azione |
|---|---|
| Il titolo esce dal Top 50 per 3 report consecutivi | Valuta uscita parziale o totale |
| Il titolo ha raggiunto il Take Profit impostato | Vendita parziale (50%) o totale |
| Il titolo ha toccato il Stop Loss impostato | Vendita totale — rispetta la regola |
| I fondamentali dell'azienda sono cambiati (nuovo CEO, scandali, perdite improvvise) | Rivaluta la tesi di investimento |
| Hai bisogno di liquidità | Vendi prima le posizioni in perdita (ottimizzazione fiscale) |

**Ribilanciamento periodico:**
- Ogni 3–6 mesi: verifica che l'allocazione per asset class e settore non si sia spostata troppo
- Se tech è salita dal 25% al 40% del portafoglio → considera riduzione parziale
- Reinvesti dividendi e cedole in nuovi titoli dal report aggiornato

---

### Strategie DCA (Piano di Accumulo del Capitale)

**Cos'è il DCA:** investire un importo fisso a cadenze regolari indipendentemente dal prezzo di mercato.

**Perché funziona:** compri più quote quando il prezzo è basso, meno quando è alto → prezzo medio di acquisto inferiore rispetto a chi investe tutto in una soluzione (lump sum) al momento sbagliato.

**Come implementare con Robot Trader:**
- Ogni mese (o trimestre): scarica il report aggiornato
- Investi €X fissi nel Top 5 o Top 10 per score di quel mese
- Usa l'Order Builder per generare l'ordine
- Evita di concentrare tutto in un singolo giorno → distribuisci su 2–3 giorni in settimane diverse

**DCA su ETF — l'abbinamento ideale:**
- ETF BASIC o PRO → seleziona i Top 3–5 ETF per score
- Investi mensilmente €X ripartiti equamente
- Non vendere in caso di correzione — il DCA funziona nel lungo termine solo se si mantiene la disciplina

---

### Errori Tipici da Evitare

| Errore | Conseguenza | Alternativa |
|---|---|---|
| Comprare solo i titoli "conosciuti" ignorando il report | Ignori le opportunità selezionate dall'algoritmo | Fidati del processo — guarda i fondamentali, non solo il nome |
| Cambiare portafoglio ogni settimana inseguendo ogni variazione | Trading eccessivo, commissioni elevate, decisioni emotive | Frequenza di revisione pre-stabilita |
| Concentrare tutto in 3–4 titoli | Rischio di concentrazione — un singolo crollo distrugge il portafoglio | Minimo 10–12 posizioni |
| Ignorare la diversificazione settoriale | Se tech crolla del 30%, il portafoglio crolla del 30% | Max 25% per settore |
| Non impostare stop loss | Perdite illimitate su singolo titolo | Stop loss al -15/20% su ogni posizione |
| Vendere in panico durante le correzioni | Si cristallizza la perdita e si manca la ripresa | Orizzonte temporale pre-definito, non cambiarlo sotto stress |

---

### Portfolio Model — Esempi Pratici

#### Portafoglio Principiante (€10.000)
- **Azioni BASIC** (Top 10): €6.000 → 6 posizioni da €1.000
- **ETF BASIC** (Top 5): €4.000 → 4 posizioni da €1.000
- Broker: Trade Republic o XTB (commissioni basse)
- Revisione: mensile
- Orizzonte: 2–3 anni

#### Portafoglio Intermedio (€50.000)
- **Azioni PRO** (Top 15): €25.000 → 15 posizioni da ~€1.667
- **ETF PRO** (Top 8): €15.000 → 8 posizioni da ~€1.875
- **Fondi EU PRO** (Top 5): €10.000 → 5 posizioni da €2.000
- Broker: IBKR per azioni, Fineco o IBKR per ETF
- Revisione: ogni 4 settimane
- Orizzonte: 3–7 anni

#### Portafoglio Avanzato (€200.000)
- **Azioni VALUE** (Top 20, alta conviction): €100.000 → 20 posizioni da €5.000
- **ETF VALUE** (Top 8): €60.000 → 8 posizioni da €7.500
- **Fondi US PRO** (Top 6): €30.000 → 6 posizioni da €5.000
- **Liquidità**: €10.000 (riserva opportunità)
- Broker: IBKR (CSV nativo PRO/VALUE)
- Revisione: ogni 6–8 settimane
- Orizzonte: 5–15 anni

---

## [ES] Español — Construir una Cartera con Robot Trader 2026

### Del Informe a la Inversión: Proceso Resumido

**Reglas de oro:**
1. **Capital de emergencia primero** — nunca inviertas dinero que puedas necesitar en los próximos 12 meses
2. **2–5% por posición** — máximo 5% del capital total en un solo título
3. **Máximo 25% por sector GICS** — evita la concentración sectorial
4. **Frecuencia de revisión pre-definida** — BASIC mensual, PRO bimensual, VALUE trimestral
5. **Stop loss establecido antes de comprar** — define el punto de salida antes de entrar

### Asignación por Perfil Recomendado

| Perfil Inversor | Acciones | ETF | Fondos | Liquidez |
|---|---|---|---|---|
| Defensivo | 10% | 20% | 30% | 40% |
| Prudente | 20% | 30% | 25% | 25% |
| Equilibrado | 40% | 30% | 15% | 15% |
| Dinámico | 55% | 30% | 10% | 5% |
| Agresivo | 70% | 25% | 5% | 0% |

### DCA — Plan de Acumulación Mensual

El DCA (Dollar Cost Averaging) es especialmente adecuado para inversores con plan de ahorro mensual:
- Cada mes: descarga el informe actualizado
- Invierte €X fijos en el Top 5 ETF por score
- Si el mercado cae, compras más participaciones al mismo coste → precio medio más bajo
- Mantén la disciplina — el DCA solo funciona si no vendes durante las correcciones

---

## [EN] English — Portfolio Building with Robot Trader 2026

### Core Principles

**Position sizing:** 2–5% of total capital per position. This limits the maximum loss from any single stock failure to 2–5% of your portfolio (assuming a total write-off, which is rare for the quality screened by Robot Trader).

**Rebalancing cadence:**
- BASIC plans: monthly review
- PRO plans: every 2–4 weeks  
- VALUE plans: every 1–3 months (long-term — don't react to short-term noise)

**When to sell:**
- A position that falls out of the Top 50 for 3 consecutive reports → consider exit
- Stop loss triggered at your pre-defined threshold (suggested: -15 to -20% from purchase price)
- Fundamental change in the company (new CEO, major losses, regulatory action)
- Rebalancing: a sector that has grown to >30% of your portfolio → partial reduction

### Using Multiple Plans Together

Robot Trader's plans are designed to complement each other:
- **Stocks PRO + ETF PRO:** stocks provide individual company alpha potential; ETFs provide diversified beta exposure
- **Stocks VALUE + ETF VALUE:** both focused on long-term efficiency — stocks for individual deep value, ETFs for long-term low-cost accumulation
- **Any screener plan + Order Builder:** adds execution capability directly from the screener output

### The Reinvestment Rule

For long-term compounding, reinvest dividends and any realized gains:
- Dividends received → use in the next monthly DCA purchase
- Partial profits taken → reinvest in new positions from the updated report
- Tax efficiency: in accumulating ETFs, reinvestment is automatic and tax-deferred

---

## [FR] Français — Construction de Portefeuille

### Allocation par Profil Investisseur

| Profil | Actions | ETF | Fonds | Liquidités |
|---|---|---|---|---|
| Défensif | 10% | 20% | 30% | 40% |
| Prudent | 20% | 30% | 25% | 25% |
| Équilibré | 40% | 30% | 15% | 15% |
| Dynamique | 55% | 30% | 10% | 5% |
| Agressif | 70% | 25% | 5% | 0% |

**Règle des 2–5%:** ne jamais investir plus de 5% du capital total dans un seul titre. Sur €50.000 → maximum €2.500 par position.

**Rythme de révision:** BASIC mensuel · PRO toutes les 2–4 semaines · VALUE tous les 1–3 mois.

---

## [DE] Deutsch — Portfolioaufbau

### Positionsgrößen und Diversifikation

**Grundregel:** 2–5% des Gesamtkapitals pro Position. Auf €100.000 → €2.000–€5.000 pro Titel.

**Sektorenallokation:** maximal 25% in einem einzelnen GICS-Sektor. Bei 15 Positionen à 5% bedeutet 25% Sektordecision maximal 5 Positionen im gleichen Sektor.

**Überprüfungsrhythmus:** BASIC monatlich · PRO alle 2–4 Wochen · VALUE alle 1–3 Monate.

**DCA-Strategie:** Monatlich einen festen Betrag in die Top 5 ETFs nach Score investieren — unabhängig vom Marktpreis. Disziplin ist entscheidend: bei Korrekturen kauft man mehr Anteile zum gleichen Betrag.
