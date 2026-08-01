# Guida alla Selezione degli ETF — Robot Trader 2026
# ETF Selection Guide / Guía de Selección de ETF / Guide de Sélection des ETF / ETF-Auswahlguide

---

## Cos'è un ETF

Un ETF (Exchange Traded Fund) è un fondo indicizzato che replica l'andamento di un indice già esistente (es. S&P 500, MSCI World) e viene negoziato in borsa come un'azione ordinaria. Combina la diversificazione di un fondo comune con la liquidità intraday di un'azione.

---

## Criteri di Selezione Oggettivi

### 1. TER — Total Expense Ratio (Costo Totale Annuo)

Il TER rappresenta i costi annuali addebitati automaticamente dal fornitore dell'ETF sul patrimonio del fondo. Include commissioni di gestione, custodia, licenza indice, marketing. **Non include** i costi di transazione dello spread bid/ask né le commissioni del broker.

- **ETF passivi tipici:** 0.03%–0.50%
- **Fondi attivi tipici:** 0.80%–2.50%
- **Soglie Robot Trader:** ≤ 0.20% (VALUE) · ≤ 0.35% (PRO) · ≤ 0.50% (BASIC)
- **Effetto tempo:** 0.20% di TER aggiuntivo su €100.000 per 20 anni = ~€9.000 di costi extra

### 2. Volume del Fondo / AUM

Il volume del fondo (patrimonio gestito) indica l'affermazione e la liquidità dell'ETF sul mercato.

| Soglia AUM | Valutazione |
|---|---|
| < 50M EUR | Rischio di chiusura, bassa liquidità |
| 50–100M EUR | Zona grigia — acceptable ma monitorare |
| ≥ 100M EUR | Stabile e affidabile |
| ≥ 500M EUR | Molto solido, spread stretto, alta liquidità |

Un AUM elevato garantisce più partecipanti che forniscono prezzi bid/ask → spread più stretto → costi di transazione inferiori.

**Soglie Robot Trader:** Volume ≥ 100.000 unità/giorno (proxy di liquidità)

### 3. Età del Fondo

- **≥ 5 anni** è la soglia consigliata: permette di verificare come l'ETF ha seguito l'indice nel tempo
- Un ETF più vecchio ha generalmente un AUM più elevato e una base dati storica comparabile
- Un ETF anziano con AUM basso è però segnale di poca domanda → rischio chiusura

### 4. Tracking Difference e Tracking Error

- **Tracking Difference:** quanto la performance dell'ETF si discosta dall'indice su un anno intero (include dividendi reinvestiti, costi, fiscalità)
- **Tracking Error:** deviazione standard delle differenze giornaliere tra ETF e indice — misura la costanza della replica
- Un TER basso non garantisce una tracking difference bassa: esistono ETF con TER 0.20% che replicano meglio di ETF con TER 0.10% grazie al prestito titoli

---

## Metodo di Replica

| Tipo | Descrizione | Vantaggi | Svantaggi |
|---|---|---|---|
| **Fisica completa** | Acquista tutti i titoli dell'indice con le stesse ponderazioni | Massima trasparenza, zero rischio controparte | Costoso per indici con molti titoli |
| **Campionamento fisico** | Acquista un sottoinsieme rappresentativo dell'indice | Efficiente per indici grandi (MSCI World ~1.400 titoli) | Leggero tracking error |
| **Sintetica (swap)** | Replica tramite contratti swap con una controparte bancaria | Replica precisa, accesso a mercati illiquidi, costi bassi | Rischio controparte (mitigato da collaterale UCITS) |

**Robot Trader 2026 seleziona esclusivamente ETF a replica fisica.** Gli ETF sintetici non entrano nell'universo analizzato.

---

## Accumulazione vs Distribuzione

| Tipo | Meccanismo | Adatto a |
|---|---|---|
| **ACC (Accumulazione)** | I dividendi vengono reinvestiti automaticamente nel fondo → crescita del NAV tramite interesse composto | Investitori che costruiscono patrimonio a lungo termine |
| **DIST (Distribuzione)** | I dividendi vengono pagati periodicamente all'investitore → reddito corrente, ma riduce il valore del fondo | Investitori che necessitano di reddito periodico |

**Robot Trader 2026 analizza solo ETF ad accumulazione.** Motivi:
- Ottimale per i piani VALUE e PRO (orizzonte multi-decennale)
- Evita doppia tassazione sui dividendi distribuiti in molti paesi europei
- Massimizza l'effetto interesse composto

---

## UCITS — Standard Europeo di Protezione

**UCITS** = Undertakings for Collective Investments in Transferable Securities (in italiano: OICVM — Organismi di Investimento Collettivo in Valori Mobiliari).

Le direttive UCITS garantiscono:
- Max 10% del patrimonio in un singolo emittente
- Separazione del patrimonio del fondo da quello del gestore
- Verifica della conformità prima della quotazione in borsa
- Protezione degli investitori retail europei

**Come riconoscerli:** gli ETF UCITS hanno il suffisso "UCITS" nel nome e un ISIN che inizia con "IE" (Irlanda) o "LU" (Lussemburgo) — le due sedi fiscali preferite per i fondi europei. ETF con ISIN che inizia con "US" o "CA" non sono UCITS e non sono normalmente negoziabili da broker europei.

**Principali fornitori ETF in Europa:** iShares (BlackRock), Amundi, Xtrackers (DWS), Vanguard, UBS, Invesco.

---

## Criteri Soggettivi di Selezione

### Strategia di Investimento e Diversificazione

La scelta dell'indice sottostante determina l'esposizione geografica, settoriale e tematica:
- **Indici globali** (MSCI World, FTSE All-World): massima diversificazione, minor rischio paese/settore
- **Indici regionali** (S&P 500, EuroStoxx 600, MSCI Emerging Markets): concentrazione su un'area geografica
- **Indici settoriali** (Healthcare, Technology, Financials): elevato rischio di cluster — se il settore soffre, tutti gli ETF settoriali soffrono insieme

**Rischio di cluster:** più ETF concentrati sullo stesso tema, settore o regione aumentano il rischio totale invece di ridurlo. Un portafoglio ben diversificato deve coprire settori e geografie diverse.

---

## Processo di Selezione in 3 Passi

**Step 1 — Strategia personale:**
Qual è la tolleranza al rischio? Orizzonte temporale? Obiettivo (accumulo, reddito, copertura inflazione)? Quale esposizione geografica/settoriale si vuole?

**Step 2 — Selezione dell'indice:**
Quale indice rappresenta la strategia? Gli indici globali e ampiamente diversificati sono preferibili perché distribuiscono il rischio su centinaia o migliaia di titoli.

**Step 3 — Selezione dell'ETF:**
Tra tutti gli ETF che replicano l'indice scelto, confrontare: TER, AUM, età, metodo di replica, tracking difference, tipo di reddito (ACC/DIST).

---

## Domicilio del Fondo

La sede legale dell'ETF influisce sulla fiscalità e sulla distribuzione:
- **Irlanda (IE):** vantaggi fiscali sui dividendi USA (doppia convenzione USA-Irlanda) → molti ETF iShares e Vanguard
- **Lussemburgo (LU):** sede di molti ETF Amundi e DWS — ottimizzazione fiscale europea
- **Francia/Germania:** fondi di grandi case nazionali
- ETF non europei (ISIN US, CA) non sono normalmente accessibili ai clienti retail europei per ragioni regolamentari (MiFID II, PRIIPs)

---

## Spread Bid/Ask — Il Costo Nascosto

Lo **spread** è la differenza tra il prezzo di acquisto (ask) e il prezzo di vendita (bid). È il costo implicito di ogni transazione:
- **Spread stretto** = ETF liquido, basso costo di transazione
- **Spread largo** = ETF illiquido, alto costo di transazione anche con TER basso
- Lo spread è correlato all'AUM: maggiore è il patrimonio, più sono i partecipanti che fanno prezzi → spread più stretto

Il TER è il costo annuale ricorrente; lo spread è il costo di ingresso/uscita: entrambi vanno considerati insieme.
