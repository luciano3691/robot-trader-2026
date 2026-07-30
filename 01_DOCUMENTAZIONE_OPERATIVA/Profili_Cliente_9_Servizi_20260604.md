# Nove Profili Cliente — Robot Trader 2026

**Fuerte Venture Capital SL** · CIF B23881691 · marketing@fuerteventurecapital.com  
*Redatto il 04/06/2026 — basato su parametri `servizi_config.json` v2.1 e `config.json` scoring_weights*

---

## Logica di segmentazione

I 9 profili derivano dall'incrocio di **3 asset class** (Azioni, ETF, Fondi) × **3 piani** (BASIC / PRO / VALUE).  
Ogni piano è calibrato su un orizzonte temporale specifico:

| Piano | Orizzonte | Logica scoring dominante |
|---|---|---|
| BASIC | Breve (6–18 mesi) | Rendimento immediato, momentum, reddito da dividendi |
| PRO | Medio (2–7 anni) | Qualità fondamentale, Sharpe ratio, bilanciamento rischio/rendimento |
| VALUE | Lungo (10–30 anni) | Deep value, costi minimi, efficienza composta nel tempo |

---

## AZIONI

### Profilo 1 — AZIONI BASIC · *"L'Investitore in Dividendi"*

**Orizzonte:** 3–12 mesi | **Prezzo:** €29/mese

**Chi è**  
Investitore privato, 40–65 anni, che ha accumulato liquidità e vuole farla lavorare senza rischiare su titoli oscuri. Conosce nomi come Enel, LVMH, Apple, Nestlé — vuole stare su società solide e riconoscibili. Non legge i bilanci in profondità ma capisce cosa è un dividendo. Può essere un libero professionista, un piccolo imprenditore o un dipendente con risparmio da investire.

**Cosa cerca**  
Rendita immediata (dividendo) + qualche plusvalenza a breve. Non vuole aspettare 5 anni per vedere un risultato. Vuole aprire il report, trovare 20 nomi sicuri, scegliere i migliori 5 e acquistare.

**Come il sistema lo serve**
- Universe ristretto: solo blue chip (SP500, FTSE100, DAX, CAC, MIB, IBEX, SMI, AEX, Nikkei) — nessuna small cap sconosciuta
- Filtri larghi (EV/FCF ≤ 18x, P/B ≤ 3x) per non escludere grandi aziende mature con P/B alto ma bilancio sano
- Score dominato da **Dividend Yield (35%)** e **variazione giornaliera (25%)**: vince chi rende di più e si muove in senso positivo oggi
- Top 20 — lista corta, decisione rapida

**Segnale d'acquisto tipico**  
Società blue chip con rendimento dividendo >3%, in momentum positivo nella settimana corrente.

**Parametri tecnici**

| Filtro | Soglia |
|---|---|
| EV/FCF max | 18x |
| P/B max | 3x |
| ROE min | 0% |
| Net Debt/EBITDA max | 4x |

| Metrica scoring | Peso |
|---|---|
| Dividend Yield | 35% |
| Var_1D_% | 25% |
| ROE | 20% |
| P/B | 10% |
| EV/FCF | 10% |

---

### Profilo 2 — AZIONI PRO · *"L'Analista Fondamentale Globale"*

**Orizzonte:** 2–5 anni | **Prezzo:** €39/mese

**Chi è**  
Investitore attivo, 35–55 anni, con esperienza in analisi fondamentale. Ha studiato finanza o è autodidatta avanzato. Sa leggere un conto economico, capisce cosa significa EV/FCF e perché un ROE elevato con poco debito è un segnale forte. Investe anche all'estero — non si limita all'Italia o all'Europa. Gestisce un portafoglio personale di dimensioni significative (€50k–€500k).

**Cosa cerca**  
Società sottovalutate a livello globale che il mercato non ha ancora prezzato correttamente. Non gli interessa il dividendo ora — vuole comprare a sconto e aspettare che il prezzo converga al valore intrinseco in 2–5 anni.

**Come il sistema lo serve**
- Universe completo: 3.072 ticker globali (USA, Europa, Giappone, HK, Australia, Canada, India, Taiwan)
- Filtri moderati (EV/FCF ≤ 15x, P/B ≤ 2x, ROE ≥ 1%, ND/EBITDA ≤ 3x) — qualità certificata senza essere iper-selettivi
- Score dominato da **EV/FCF (35%)** e **ROE (25%)**: vince chi genera più cassa rispetto al valore d'impresa e lo reinveste bene
- Top 50 — lista ampia per analisi di secondo livello e costruzione di portafoglio diversificato

**Segnale d'acquisto tipico**  
Azienda globale che genera FCF significativo, gestione efficiente del capitale, poca esposizione a debito ciclico.

**Parametri tecnici**

| Filtro | Soglia |
|---|---|
| EV/FCF max | 15x |
| P/B max | 2x |
| ROE min | 1% |
| Net Debt/EBITDA max | 3x |

| Metrica scoring | Peso |
|---|---|
| EV/FCF | 35% |
| ROE | 25% |
| P/B | 20% |
| Net Debt/EBITDA | 15% |
| Var_1D_% | 5% |

---

### Profilo 3 — AZIONI VALUE · *"Il Deep Value Investor Professionale"*

**Orizzonte:** 5–15 anni | **Prezzo:** €59/mese

**Chi è**  
Professionista finanziario (consulente indipendente, gestore patrimoniale, family office) o investitore istituzionale con approccio disciplinato stile Buffett/Munger. Può essere anche un investitore privato molto sofisticato che ha capito che il vero alpha si genera comprando aziende eccellenti a prezzi bassi e tenendole per decenni. Gestisce patrimoni rilevanti (>€1M) o portafogli di terzi.

**Cosa cerca**  
Solo le migliori aziende al mondo a sconto profondo: EV/FCF sotto 12x, P/B sotto 1x (paga meno del patrimonio netto), ROE stabile ≥ 2%, e bilancio pulito (ND/EBITDA ≤ 2x). Non transa sulla qualità. Preferisce poche posizioni di grande conviction piuttosto che molte posizioni mediocri.

**Come il sistema lo serve**
- Universe: 17 mercati globali inclusi Australia e Canada — massima latitudine geografica
- Filtri severi (EV/FCF ≤ 12x, P/B ≤ 1x, ROE ≥ 2%, ND/EBITDA ≤ 2x): passa solo il top assoluto di qualità
- Score dominato da **EV/FCF (40%)** + **ROE (25%)** + **Net Debt/EBITDA (20%)**: nessun peso su dividendo o variazione giornaliera — irrilevante sul lungo termine
- Report completo multi-sheet con tutti gli scartati e motivazioni — serve per due diligence interna

**Segnale d'acquisto tipico**  
Azienda con FCF yield >8% (EV/FCF < 12), capitalizzata sotto il book value, ROE stabile nel tempo, quasi zero debito.

**Parametri tecnici**

| Filtro | Soglia |
|---|---|
| EV/FCF max | 12x |
| P/B max | 1x |
| ROE min | 2% |
| Net Debt/EBITDA max | 2x |

| Metrica scoring | Peso |
|---|---|
| EV/FCF | 40% |
| ROE | 25% |
| Net Debt/EBITDA | 20% |
| P/B | 15% |

---

## ETF

### Profilo 4 — ETF BASIC · *"Il Risparmiatore che Vuole Cavalcare il Mercato"*

**Orizzonte:** 6–18 mesi | **Prezzo:** €29/mese

**Chi è**  
Risparmiatore, 25–45 anni, che ha scoperto gli ETF come strumento di investimento semplice e a basso costo. Ha un piano di accumulo mensile o una somma da investire e vuole sapere "quali settori stanno andando adesso." Non ha formazione finanziaria avanzata ma è tech-savvy. Segue i mercati sui social media e vuole stare sui trend del momento (IT, biotech, mercati emergenti in crescita).

**Cosa cerca**  
ETF che stanno performando bene nell'ultimo trimestre — vuole entrare su un trend già in atto e uscire quando si esaurisce. Non è un cassettista. Accetta ETF leggermente più costosi (fino a 0.50% TER) se stanno andando bene.

**Come il sistema lo serve**
- Filtro TER largo (≤ 0.50%): include ETF settoriali che costano un po' di più ma perforano di più
- Score dominato da **Perf 3M (45%)**: chi ha performato meglio negli ultimi tre mesi viene in cima
- Performance 1Y al 20%: conferma che non è un fuoco di paglia
- Filtro Perf 1Y ≥ +5%: esclude ETF in perdita strutturale
- Top 20 — focus su un numero piccolo di ETF ad alto segnale

**Segnale d'acquisto tipico**  
ETF Information Technology con Perf 3M >25%, ad accumulazione, fisico, età >5 anni.

**Parametri tecnici**

| Filtro | Soglia |
|---|---|
| TER max | 0.50% |
| Sharpe min | 0.3 |
| Volume min | 100.000 unità/gg |
| Performance 1Y min | +5% |
| Età ETF min | 5 anni |

| Metrica scoring | Peso |
|---|---|
| Perf 3M % | 45% |
| Performance 1Y | 20% |
| TER | 20% |
| Sharpe Ratio | 15% |

---

### Profilo 5 — ETF PRO · *"Il Portfolio Manager Attivo"*

**Orizzonte:** 3–7 anni | **Prezzo:** €39/mese

**Chi è**  
Investitore sofisticato o gestore che costruisce portafogli ETF diversificati per sé o per clienti. Conosce il Sharpe ratio e lo usa come bussola. Sa che un ETF con Perf 3M +30% ma Sharpe 0.3 è molto meno interessante di uno con Perf 1Y +20% e Sharpe 1.8. Seleziona 8–15 ETF per costruire un portafoglio bilanciato per classi di asset e geografia.

**Cosa cerca**  
ETF con il miglior rapporto rendimento/rischio nel medio periodo. Non insegue il momentum trimestrale — vuole ETF che si comportino bene in modo consistente. Attenzione ai costi (TER ≤ 0.35%) perché su 3-7 anni la differenza è significativa.

**Come il sistema lo serve**
- Filtri equilibrati: TER ≤ 0.35% (medio-basso), Sharpe ≥ 0.4, Perf 1Y ≥ +7%
- Score dominato da **Sharpe (40%)** + **Performance 1Y (30%)**: premia la consistenza risk-adjusted
- Perf 3M al 10%: dà un piccolo peso al momentum senza che domini
- ETF età ≥ 3 anni: track record minimo garantito
- Top 50 — lista ampia per analisi approfondita e costruzione portafoglio multi-asset

**Segnale d'acquisto tipico**  
ETF mercati emergenti con Sharpe >1.5, Perf 1Y >15%, TER <0.30%, accumulazione fisica.

**Parametri tecnici**

| Filtro | Soglia |
|---|---|
| TER max | 0.35% |
| Sharpe min | 0.4 |
| Volume min | 100.000 unità/gg |
| Performance 1Y min | +7% |
| Età ETF min | 3 anni |

| Metrica scoring | Peso |
|---|---|
| Sharpe Ratio | 40% |
| Performance 1Y | 30% |
| TER | 20% |
| Perf 3M % | 10% |

---

### Profilo 6 — ETF VALUE · *"Il Wealth Manager Istituzionale"*

**Orizzonte:** 10–30 anni | **Prezzo:** €59/mese

**Chi è**  
Wealth manager, gestore di fondi pensione, family office o istituzionale che gestisce patrimoni di lungo periodo. Pensa in decenni, non in trimestri. Sa perfettamente che 0.30% di TER annuo su €10M per 20 anni significa €600.000+ di costi aggiuntivi rispetto a 0.10% TER. Ogni basis point conta. Vuole solo ETF fisici ad accumulazione con track record solido, massima liquidità e costo minimo.

**Cosa cerca**  
I 5–10 ETF più efficienti del mercato per Sharpe ratio e costo. Non gli interessa il momentum di breve — sta costruendo allocazioni strategiche che dureranno anni. Accetta solo ETF con TER ≤ 0.20% e Sharpe ≥ 0.5.

**Come il sistema lo serve**
- Filtro TER durissimo (≤ 0.20%): seleziona solo i mega-ETF più efficienti del mercato
- Filtro Perf 1Y ≥ +10%: esclude tutto ciò che non ha track record di rendimento reale
- Score dominato da **Sharpe (45%)** + **TER (25%)** + **Perf 1Y (25%)**: tripletta perfetta per gestione patrimoniale di lungo termine
- Perf 3M al 5%: quasi irrilevante — l'orizzonte è strategico
- ETF età ≥ 2 anni: soglia minima, ma Perf 1Y ≥ +10% garantisce filtro de facto su maturità

**Segnale d'acquisto tipico**  
MSCI World o All-World accumulation, TER 0.10–0.20%, Sharpe >1.8, AUM miliardario, track record >5 anni.

**Parametri tecnici**

| Filtro | Soglia |
|---|---|
| TER max | 0.20% |
| Sharpe min | 0.5 |
| Volume min | 100.000 unità/gg |
| Performance 1Y min | +10% |
| Età ETF min | 2 anni |

| Metrica scoring | Peso |
|---|---|
| Sharpe Ratio | 45% |
| Performance 1Y | 25% |
| TER | 25% |
| Perf 3M % | 5% |

---

## FONDI COMUNI

### Profilo 7 — FONDI BASIC · *"Il Cliente della Banca che Vuole Risultati Rapidi"*

**Orizzonte:** 6–24 mesi | **Prezzo:** €29/mese

**Chi è**  
Investitore retail, 45–70 anni, tipicamente cliente di una banca tradizionale o rete di consulenza (Mediolanum, Fineco, Azimut) abituato ai fondi comuni come strumento principale di investimento. Non ha un background tecnico — si fida del nome del gestore e guarda prima di tutto cosa ha fatto il fondo "nell'ultimo anno." Tollera costi più alti (TER fino al 2%) se il fondo performa.

**Cosa cerca**  
I fondi che stanno rendendo di più adesso — nell'ultimo trimestre e nell'ultimo anno. Vuole portare a casa risultati prima che il mercato cambi. Non si preoccupa troppo del costo di gestione se il rendimento compensa.

**Come il sistema lo serve**
- Filtro TER generoso (≤ 2.0%): include la maggioranza dei fondi attivi del mercato, anche i più costosi
- Score bilanciato tra **Perf 3M (30%)** e **Perf 1Y (30%)**: doppio segnale di performance recente
- Sharpe al 15%: presente ma non dominante — un po' di qualità del rischio c'è
- Filtro Perf 1Y ≥ +5%: esclude i fondi in perdita strutturale
- Top 20 — lista corta, adatta a chi non vuole fare analisi complessa

**Segnale d'acquisto tipico**  
Fondo azionario settoriale con Perf 3M >10% e Perf 1Y >20%, anche se TER è all'1.5%.

**Parametri tecnici**

| Filtro | Soglia |
|---|---|
| TER max | 2.0% |
| Sharpe min | 0.1 |
| Volume min | 50.000 unità |
| Performance 1Y min | +5% |

| Metrica scoring | Peso |
|---|---|
| Perf 3M % | 30% |
| Performance 1Y | 30% |
| TER | 25% |
| Sharpe Ratio | 15% |

---

### Profilo 8 — FONDI PRO · *"Il Consulente Finanziario Indipendente"*

**Orizzonte:** 3–7 anni | **Prezzo:** €39/mese

**Chi è**  
Consulente finanziario indipendente (CFI), private banker o advisor che seleziona fondi per i portafogli dei propri clienti. Sa spiegare il Sharpe ratio a un cliente, capisce la differenza tra un fondo con alfa reale e uno che performa solo perché il mercato sale. Deve giustificare le scelte e rispettare i mandati di investimento. Ha sotto gestione portafogli da €500k a €5M.

**Cosa cerca**  
Fondi con il miglior rapporto rischio/rendimento e costo contenuto (TER ≤ 1.5%). Non vuole fondi che hanno performato bene per caso — vuole gestori che dimostrano disciplina e consistenza nel tempo, misurata dal Sharpe. Il costo è importante perché riduce il rendimento netto al cliente.

**Come il sistema lo serve**
- Filtro TER equilibrato (≤ 1.5%): esclude i fondi più costosi, mantiene accesso a gestione attiva di qualità
- Score dominato da **Sharpe (40%)** + **TER (30%)**: efficienza risk-adjusted + controllo dei costi
- Performance 1Y al 25%: track record di medio periodo obbligatorio
- Filtro Perf 1Y ≥ +7%: soglia minima di rendimento reale
- Top 50 — lista ampia per due diligence del advisor

**Segnale d'acquisto tipico**  
Fondo multi-asset con Sharpe >0.8, TER <1.2%, Perf 1Y >10% consistente negli ultimi 3 anni.

**Parametri tecnici**

| Filtro | Soglia |
|---|---|
| TER max | 1.5% |
| Sharpe min | 0.2 |
| Volume min | 50.000 unità |
| Performance 1Y min | +7% |

| Metrica scoring | Peso |
|---|---|
| Sharpe Ratio | 40% |
| TER | 30% |
| Performance 1Y | 25% |
| Perf 3M % | 5% |

---

### Profilo 9 — FONDI VALUE · *"Il Family Office o l'Istituzionale"*

**Orizzonte:** 10–30 anni | **Prezzo:** €59/mese

**Chi è**  
Family office, fondazione, fondo pensione o gestore patrimoniale istituzionale che usa fondi comuni per accedere a classi di asset specifiche o gestori con alfa comprovato. Gestisce patrimoni da €5M in su. Sa che su 20 anni, 0.50% di TER in più su €10M di AUM vale oltre €1M di costi aggiuntivi. Vuole solo i fondi più efficienti del mercato con track record solido di performance e disciplina di rischio.

**Cosa cerca**  
I fondi con il massimo Sharpe ratio e il TER più basso possibile tra quelli ammissibili (≤ 1.0%). Perf 1Y ≥ +10% come soglia minima per confermare che il gestore produce valore reale. Non si preoccupa di cosa è successo nell'ultimo trimestre — guarda la qualità del processo di investimento nel lungo periodo.

**Come il sistema lo serve**
- Filtro TER severo (≤ 1.0%): solo i fondi con struttura di costi sostenibile per patrimoni di lungo termine
- Filtro Perf 1Y ≥ +10%: solo gestori con track record di rendimento reale provato
- Score dominato da **Sharpe (45%)** + **TER (35%)**: TER ha il secondo peso più alto di tutto il sistema — perché su 10-30 anni il costo è il fattore di rischio più certo e controllabile
- Perf 3M al 5%: praticamente irrilevante — decisioni strategiche, non tattiche
- Top 50 con report completo multi-sheet per audit interno e reporting ai beneficiari

**Segnale d'acquisto tipico**  
Fondo obbligazionario o bilanciato istituzionale con Sharpe >1.0, TER <0.80%, Perf 1Y >12%, AUM >€1B, gestore con track record >7 anni.

**Parametri tecnici**

| Filtro | Soglia |
|---|---|
| TER max | 1.0% |
| Sharpe min | 0.3 |
| Volume min | 50.000 unità |
| Performance 1Y min | +10% |

| Metrica scoring | Peso |
|---|---|
| Sharpe Ratio | 45% |
| TER | 35% |
| Performance 1Y | 15% |
| Perf 3M % | 5% |

---

## Matrice di sintesi

| # | Servizio | Piano | Profilo | Orizzonte | Prezzo | Score dominante |
|---|---|---|---|---|---|---|
| 1 | Azioni | BASIC | L'Investitore in Dividendi | 3–12 mesi | €29 | Dividend Yield 35% + Momentum 25% |
| 2 | Azioni | PRO | L'Analista Fondamentale Globale | 2–5 anni | €39 | EV/FCF 35% + ROE 25% |
| 3 | Azioni | VALUE | Il Deep Value Investor Professionale | 5–15 anni | €59 | EV/FCF 40% + ROE 25% |
| 4 | ETF | BASIC | Il Risparmiatore che Cavalca il Mercato | 6–18 mesi | €29 | Perf 3M 45% |
| 5 | ETF | PRO | Il Portfolio Manager Attivo | 3–7 anni | €39 | Sharpe 40% + Perf 1Y 30% |
| 6 | ETF | VALUE | Il Wealth Manager Istituzionale | 10–30 anni | €59 | Sharpe 45% + TER 25% |
| 7 | Fondi | BASIC | Il Cliente della Banca | 6–24 mesi | €29 | Perf 3M 30% + Perf 1Y 30% |
| 8 | Fondi | PRO | Il Consulente Finanziario Indipendente | 3–7 anni | €39 | Sharpe 40% + TER 30% |
| 9 | Fondi | VALUE | Il Family Office o l'Istituzionale | 10–30 anni | €59 | Sharpe 45% + TER 35% |

---

*Fuerte Venture Capital SL · CIF B23881691 · Villaverde, Las Palmas, Canary Islands, Spain*  
*Documento interno — versione 1.0 del 04/06/2026*
