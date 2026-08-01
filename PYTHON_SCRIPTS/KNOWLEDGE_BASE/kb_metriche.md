# Metriche di Selezione — Robot Trader 2026
# Selection Metrics / Métricas de Selección / Métriques de Sélection / Auswahlkennzahlen

Spiega ogni indicatore usato nei filtri e nello score degli screener. Utile per rispondere a domande su "cosa significa EV/FCF?", "cos'è lo Sharpe ratio?", ecc.

---

## METRICHE AZIONI

### EV/FCF — Enterprise Value / Free Cash Flow
**Cosa misura:** quanti anni sarebbero necessari per recuperare l'intero valore dell'azienda (EV) attraverso il solo flusso di cassa libero (FCF).
- **EV** = Capitalizzazione di borsa + Debito Netto
- **FCF** = Utile Operativo − Investimenti − Variazione Capitale Circolante
- **EV/FCF basso** = azienda che genera molta cassa rispetto al suo prezzo → potenzialmente sottovalutata
- **EV/FCF alto** = il mercato paga molto rispetto alla cassa generata → titolo caro o in forte crescita attesa
- **Robot Trader lo usa come:** filtro primario e componente dello score per tutti i piani Azioni

### P/B — Price to Book Ratio (Prezzo / Valore Contabile)
**Cosa misura:** quanto il mercato paga rispetto al patrimonio netto contabile dell'azienda.
- Formula: Prezzo Azione / (Totale Attivo − Totale Passivo) per azione
- **P/B < 1** = il mercato prezza l'azienda meno del suo valore di bilancio → segnale di sottovalutazione
- **P/B > 3** = mercato paga un forte premium sulla crescita futura attesa
- **Robot Trader lo usa come:** filtro secondario e componente dello score per tutti i piani Azioni

### ROE — Return on Equity (Rendimento del Capitale Proprio)
**Cosa misura:** quanto rende il capitale investito dagli azionisti.
- Formula: Utile Netto / Patrimonio Netto × 100
- **ROE elevato** = management efficiente nel creare valore per gli azionisti
- **Attenzione:** un ROE molto alto può derivare da eccessivo indebitamento (leva finanziaria), non da efficienza operativa — verificare sempre insieme al Net Debt/EBITDA
- **Robot Trader lo usa come:** componente dello score per tutti i piani Azioni

### Net Debt / EBITDA (Leva Finanziaria)
**Cosa misura:** quanti anni di flusso di cassa operativo (EBITDA) sarebbero necessari per ripagare il debito netto.
- Formula: (Totale Debiti − Liquidità) / EBITDA
- Valore basso = azienda con indebitamento contenuto → solida e stabile
- Valore alto = azienda fortemente indebitata → maggiore rischio finanziario
- **Servizi finanziari (banche, assicurazioni):** esclusi dal filtro — il debito è il loro modello di business
- **Robot Trader lo usa come:** componente dello score nei piani Azioni VALUE e PRO

### Dividend Yield (Rendimento da Dividendo)
**Cosa misura:** quanto rende annualmente il dividendo rispetto al prezzo corrente dell'azione.
- Formula: Dividendo Annuo / Prezzo Azione × 100
- Rilevante soprattutto per il piano **Azioni BASIC** — orientato alla rendita immediata
- I piani PRO e VALUE non privilegiano il dividendo — il focus è sul valore intrinseco a lungo termine

### Var 1D% (Variazione Giornaliera)
**Cosa misura:** la variazione percentuale del prezzo dell'azione nella giornata corrente.
- Usato come segnale di momentum di breve termine
- Rilevante soprattutto per il piano **Azioni BASIC** — esclusiva degli investitori a breve termine

### Market Cap (Capitalizzazione di Mercato)
**Filtro di liquidità minima per tutti i piani Azioni**
- Elimina micro-cap e penny stock con liquidità insufficiente
- Non incluso nello score ma è un prerequisito per accedere all'universo analizzato

---

## METRICHE ETF

### TER — Total Expense Ratio (Costo Totale Annuo)
**Cosa misura:** la percentuale annua del patrimonio del fondo destinata a coprire i costi di gestione.
- Dedotto automaticamente dal NAV del fondo — non è una commissione esplicita
- **Include:** commissioni di gestione, banca depositaria, revisione, marketing
- **Non include:** costi di transazione, spread bid/ask, commissioni del broker
- **Confronto di mercato:** ETF passivi tipicamente 0.03%–0.50% / Fondi attivi 0.80%–2.50%
- **Robot Trader lo usa come:** filtro di costo e componente dello score per tutti i piani ETF e Fondi — più basso è meglio, specialmente su orizzonti lunghi

### Sharpe Ratio
**Cosa misura:** il rendimento extra ottenuto per ogni unità di rischio (volatilità) assunto.
- Formula: (Rendimento Portafoglio − Tasso Risk-Free) / Deviazione Standard
- **Negativo** = rendimento inferiore al tasso privo di rischio
- **< 1** = rendimento non adeguato al rischio assunto
- **1.0–1.99** = buono
- **≥ 2** = eccellente
- Ideato dal Premio Nobel William Sharpe (1966)
- **Robot Trader lo usa come:** componente dominante dello score per tutti i piani ETF e Fondi

### AUM — Assets Under Management (Patrimonio Gestito)
**Cosa misura:** il patrimonio totale investito in un ETF o fondo — indicatore di liquidità e stabilità.
- AUM basso (es. < 50M EUR) = rischio chiusura del fondo o scarsa liquidità
- AUM medio (es. ≥ 100M EUR) = soglia di stabilità accettabile
- AUM alto (es. ≥ 500M EUR) = fondo solido, spread stretto, alta liquidità
- Usato come **filtro di liquidità** (proxy per Volume nei fondi)
- **Robot Trader lo usa come:** prerequisito minimo di liquidità per accedere all'universo analizzato

### Performance 1Y (Rendimento a 1 Anno)
**Cosa misura:** la variazione percentuale del valore di un ETF/fondo nei 12 mesi precedenti.
- Formula: (Valore Finale − Valore Iniziale) / Valore Iniziale × 100
- Usato insieme allo Sharpe per distinguere rendimenti consistenti da rendimenti casuali
- **Robot Trader lo usa come:** componente dello score per tutti i piani ETF e Fondi, con peso crescente nei piani più orientati al rendimento recente

### Performance 3M (Rendimento Trimestrale)
**Cosa misura:** la variazione percentuale del valore nei 3 mesi precedenti — indicatore di momentum di breve termine.
- Peso maggiore nei piani **BASIC** (orientati al breve termine)
- Peso minore o assente nei piani **VALUE** — irrilevante per orizzonti decennali

### Volatilità
**Cosa misura:** l'ampiezza delle oscillazioni di prezzo di un asset.
- Calcolata come deviazione standard dei rendimenti giornalieri su un periodo
- Alta volatilità = maggiore rischio ma anche maggiore potenziale di rendimento
- Lo Sharpe Ratio "penalizza" automaticamente la volatilità eccessiva nel ranking
- **Robot Trader:** soglie di volatilità massima differenziate per ETF e Fondi

### Metodo di Replica ETF
| Tipo | Descrizione | Pro | Contro |
|---|---|---|---|
| **Fisica completa** | Acquista tutti i titoli dell'indice con le stesse ponderazioni | Massima trasparenza, zero rischio controparte | Costoso per indici con molti titoli |
| **Campionamento fisico** | Acquista solo un sottoinsieme rappresentativo | Efficiente per indici grandi | Leggero tracking error |
| **Sintetica (swap)** | Replica tramite contratti swap con una controparte bancaria | Replica precisa, costi bassi | Rischio controparte (mitigato da collaterale UCITS) |

**Robot Trader 2026 seleziona solo ETF a replica fisica** (nessun ETF sintetico nell'universo analizzato)

### Accumulazione vs Distribuzione
- **Accumulazione (ACC):** i dividendi vengono reinvestiti automaticamente → crescita del NAV tramite interesse composto → ottimale per chi costruisce patrimonio a lungo termine
- **Distribuzione (DIST):** i dividendi vengono pagati periodicamente all'investitore → genera reddito corrente ma riduce il valore del fondo
- **Robot Trader 2026 analizza solo ETF ad accumulazione** (ottimale per i piani VALUE e PRO, evita doppia tassazione in molti paesi europei)

---

## METRICHE FONDI

Le metriche per i fondi (TER, Sharpe, AUM, Performance 1Y/3M) hanno lo stesso significato delle metriche ETF.

### Differenze chiave Fondi vs ETF
| | ETF | Fondi (US e EU) |
|---|---|---|
| **Negoziazione** | In borsa in tempo reale (bid/ask) | NAV giornaliero (prezzo fisso al closing) |
| **Gestione** | Passiva (replica indice) | Attiva o semi-attiva |
| **TER tipico** | 0.03%–0.50% | 0.5%–2.5% |
| **Liquidità proxy** | Volume (unità/giorno) | AUM (patrimonio totale) |
| **Stelle Morningstar** | Presenti in report | Presenti in report |

### Stelle Morningstar
- Sistema di rating da ★ a ★★★★★ che misura la performance aggiustata per il rischio rispetto a fondi/ETF comparabili
- **★★★★★ (5 stelle)** = top 10% della categoria
- **★★★★ (4 stelle)** = top 22.5%
- **★★★ (3 stelle)** = 35% centrali
- Usato come informazione nel report, non come filtro diretto nello score di Robot Trader

---

## SCORE PERCENTILE — Come funziona il ranking

Il **Score** in ogni report Robot Trader 2026 è un **punteggio percentile da 0 a 100**:
- **Score 82** = questo strumento supera l'82% di tutti gli altri strumenti analizzati nello stesso piano e nella stessa elaborazione
- È un ranking **relativo** — non una valutazione assoluta della qualità
- Il punteggio cambia ogni sera con la nuova elaborazione (lunedì–venerdì)
- Non confrontare score di piani diversi (es. Score 70 Azioni BASIC ≠ Score 70 Azioni VALUE)
- Non confrontare score di date diverse

### Come è composto lo score

Ogni piano assegna **pesi diversi** alle metriche in base alla filosofia del piano:
- **Piani BASIC:** maggiore peso sulle metriche di rendimento recente e rendita immediata (Dividend Yield, Perf 3M, Var 1D%)
- **Piani PRO:** peso equilibrato tra qualità fondamentale e performance
- **Piani VALUE:** peso dominante sulle metriche di valore a lungo termine (EV/FCF, Sharpe, TER) — zero peso sulle metriche di breve termine

I pesi specifici sono parametri proprietari di Robot Trader 2026 e non vengono divulgati.
