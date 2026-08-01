# Robot Trader 2026 — Piani e Servizi / Planes / Plans / Tarifs / Tarife

## DATI TECNICI (riferimento unico — tutte le lingue / reference data — all languages)

### Universo analizzato
| Asset | Screener live | Dettaglio |
|---|---|---|
| Azioni | {N_AZIONI} ticker | 23 mercati: USA, Europa (15 paesi), Giappone, Hong Kong, Australia, Canada, India, Taiwan |
| ETF | {N_ETF} ETF | Solo accumulazione fisica — Europa multi-exchange, dedup per ISIN |
| Fondi US | {N_FONDI_US} fondi | 45 famiglie americane (Vanguard, Fidelity, T.Rowe Price, PIMCO, DFA, Dodge & Cox, ecc.) |
| Fondi EU UCITS | {N_FONDI_EU} fondi | Fondi UCITS europei regolamentati con dati Yahoo Finance |
| **TOTALE screener** | **{N_TOTALE}** | Aggiornato ogni sera lun–ven con dati di mercato live |

### Prezzi — Panoramica / Precios / Pricing / Prix / Preise
| Piano / Plan | BASIC | PRO | VALUE |
|---|---|---|---|
| Azioni / Acciones / Stocks / Actions / Aktien | €29/mese | €39/mese | €59/mese |
| ETF | €29/mese | €39/mese | €59/mese |
| Fondi US / Fondos US / US Funds / Fonds US / US-Fonds | €29/mese | €39/mese | €59/mese |
| Fondi EU UCITS / Fondos EU / EU Funds / Fonds EU / EU-Fonds | €29/mese | €39/mese | €59/mese |
| Order Builder / Constructor de Órdenes | €19/mese | €29/mese | €49/mese |

I piani si possono combinare liberamente (es. Azioni PRO + ETF VALUE + Ordini BASIC).

---

### Logica di selezione — Azioni
I piani Azioni applicano filtri fondamentali rigorosi sulle seguenti metriche: **EV/FCF**, **P/B**, **ROE**, **Net Debt/EBITDA**, **Market Cap**. I piani BASIC, PRO e VALUE differiscono per selettività crescente dei filtri e per la composizione dello score percentile. Il piano VALUE è il più esigente — lista molto concentrata. Il piano BASIC ha i filtri più ampi — maggior numero di titoli selezionati.

Tutti i piani Azioni: solo titoli con Market Cap minima sufficiente a garantire liquidità.

---

### Logica di selezione — ETF
I piani ETF applicano filtri su: **TER**, **Sharpe Ratio**, **Volume** (liquidità), **Performance 1Y** e **Performance 3M**. I piani BASIC, PRO e VALUE differiscono per selettività dei filtri e peso nello score.

Tutti i piani ETF: solo ETF a **replica fisica** (no sintetici), solo ETF ad **accumulazione** (no distribuzione), almeno 3 anni di storia.

---

### Logica di selezione — Fondi US e Fondi EU UCITS
I piani Fondi applicano filtri su: **TER**, **Sharpe Ratio**, **Volume/AUM** (liquidità), **Performance 1Y** e **Performance 3M**. I Fondi EU usano l'AUM come proxy di liquidità invece del volume.

---

### Order Builder — Caratteristiche
| Piano | Prezzo | Caratteristiche |
|---|---|---|
| BASIC | €19/mese | Email bancaria professionale MiFID II · CSV generico (Fineco, Directa, Trade Republic, WeBank) · Prezzi live auto-fetch · Max 10 titoli per ordine |
| PRO | €29/mese | Tutto BASIC + CSV IBKR Basket Trader (import TWS in 3 click) · Titoli e ordini illimitati · Riferimento ordine tracciabile |
| VALUE | €49/mese | Tutto PRO + Integrazione IBKR API diretta (prossimamente) · Archivio ordini storico (prossimamente) · Supporto prioritario |

---

## [IT] Italiano — Descrizioni piani

### Piani Azioni
**Azioni BASIC €29/mese** — "L'Investitore in Dividendi"
Per chi vuole un portafoglio di Blue Chip con reddito da dividendi. Universo focalizzato sui principali indici mondiali (S&P500, FTSE100, DAX, CAC40, MIB, IBEX). Filtri permissivi, score dominato dal Dividend Yield. Output: Top 20 per Score.

**Azioni PRO €39/mese** — "L'Analista Fondamentale Globale"
Accesso all'universo completo di {N_AZIONI} ticker su 23 mercati. Filtri bilanciati, score ponderato su EV/FCF e ROE. Ideale per chi fa analisi fondamentale attiva. Output: Top 50 per Score.

**Azioni VALUE €59/mese** — "Il Deep Value Investor"
I filtri più rigidi su EV/FCF, P/B, ROE e Debt/EBITDA. Solo aziende sottovalutate con bilancio solido. Score dominato dall'efficienza finanziaria a lungo termine. Output: Top 50 + fogli Scartati e Non Validi. Orizzonte 5–15 anni.

### Piani ETF
**ETF BASIC €29/mese** — "Il Risparmiatore a Momentum"
ETF con buona performance recente e costi ragionevoli. Score orientato al rendimento di breve/medio termine. Ideale per orizzonte 6–18 mesi.

**ETF PRO €39/mese** — "Il Portfolio Manager Attivo"
Equilibrio tra Sharpe Ratio e Performance 1Y. Per chi gestisce attivamente un portafoglio ETF a medio termine (3–7 anni).

**ETF VALUE €59/mese** — "Il Wealth Manager a Lungo Termine"
Filtri molto esigenti su TER (basso) e Sharpe (alto). Il piano ottimale per chi costruisce patrimonio su 10–30 anni minimizzando i costi di gestione.

### Piani Fondi US
**Fondi BASIC €29/mese** — "Il Cliente della Banca Attivo"
{N_FONDI_US} fondi americani delle principali famiglie (Vanguard, Fidelity, ecc.). Orientato al rendimento recente.

**Fondi PRO €39/mese** — "Il Consulente Finanziario Indipendente"
Score dominato da Sharpe e TER. Ideale per selezione fondi in un portafoglio a medio-lungo termine.

**Fondi VALUE €59/mese** — "Il Family Office o l'Istituzionale"
Filtri molto rigidi su TER (basso) e Sharpe (alto). Massima efficienza e qualità rischio/rendimento. Orizzonte 10+ anni.

### Piani Fondi EU UCITS
**Fondi EU BASIC €29/mese** — "Il Miglior Fondo UCITS"
Selezione rigorosa sui fondi europei più efficienti e consolidati. I fondi europei UCITS più qualificati.

**Fondi EU PRO €39/mese** — "Accesso all'Universo UCITS Esteso"
Universo più ampio: fondi più piccoli o a gestione attiva con costi medi. Score bilanciato.

**Fondi EU VALUE €59/mese** — "L'Universo UCITS Completo"
Accesso all'intero universo di {N_FONDI_EU} fondi UCITS analizzati. Include fondi attivi di nicchia, gestori specializzati, fondi settoriali.

---

## [ES] Español — Descripción de planes

### Planes Acciones
**Acciones BASIC €29/mes** — "El Inversor en Dividendos"
Para quien busca Blue Chips con rentas por dividendo. Índices mundiales principales. El Score prioriza el Dividend Yield.

**Acciones PRO €39/mes** — "El Analista Fundamental Global"
Acceso al universo completo de {N_AZIONI} tickers en 23 mercados. Filtros equilibrados, Score ponderado en EV/FCF y ROE. Ideal para análisis fundamental activo. Top 50.

**Acciones VALUE €59/mes** — "El Deep Value Investor"
Los filtros más estrictos en EV/FCF, P/B, ROE y Debt/EBITDA. Solo empresas infravaloradas con balance sólido. Horizonte 5–15 años. Top 50 + hojas de Descartados y No Válidos.

### Planes ETF
**ETF BASIC €29/mes** — "El Ahorrador a Momentum"
ETFs con buen rendimiento reciente y costes razonables. Score orientado al rendimiento a corto plazo. Horizonte 6–18 meses.

**ETF PRO €39/mes** — "El Portfolio Manager Activo"
Equilibrio entre Sharpe Ratio y Rendimiento 1Y. Para gestión activa de cartera ETF a medio plazo (3–7 años).

**ETF VALUE €59/mes** — "El Wealth Manager a Largo Plazo"
Filtros muy exigentes en TER y Sharpe. Óptimo para construir patrimonio a 10–30 años minimizando costes.

### Planes Fondos US
**Fondos BASIC €29/mes** — Rendimiento reciente. {N_FONDI_US} fondos, 45 familias americanas.
**Fondos PRO €39/mes** — Score dominado por Sharpe y TER. Gestión a medio-largo plazo.
**Fondos VALUE €59/mes** — Filtros rigurosos en TER y Sharpe. Máxima eficiencia. Horizonte 10+ años.

### Planes Fondos EU UCITS
**Fondos EU BASIC €29/mes** — Selección estricta. Los mejores fondos UCITS europeos.
**Fondos EU PRO €39/mes** — Universo más amplio, fondos activos con costes medios.
**Fondos EU VALUE €59/mes** — Acceso a los {N_FONDI_EU} fondos UCITS completos. Incluye fondos activos de nicho y gestores especializados.

---

## [EN] English — Plan descriptions

### Stock Plans
**Stocks BASIC €29/month** — "The Dividend Investor"
Focus on Blue Chip stocks with dividend income. Major global indices (S&P500, FTSE100, DAX, etc.). Score dominated by Dividend Yield. Top 20 output.

**Stocks PRO €39/month** — "The Global Fundamental Analyst"
Full universe: {N_AZIONI} tickers across 23 markets. Balanced filters, Score weighted on EV/FCF and ROE. For active fundamental analysis. Top 50 output.

**Stocks VALUE €59/month** — "The Deep Value Investor"
Strictest filters on EV/FCF, P/B, ROE and Debt/EBITDA. Only undervalued companies with solid balance sheets. 5–15 year horizon. Top 50 + Rejected and Invalid sheets.

### ETF Plans
**ETF BASIC €29/month** — Short/medium-term momentum ETFs. Score dominated by 3M performance. Horizon 6–18 months.
**ETF PRO €39/month** — Balance of Sharpe Ratio and 1Y performance. Active ETF portfolio management, 3–7 year horizon.
**ETF VALUE €59/month** — Very strict TER and Sharpe filters. Optimal for long-term wealth building (10–30 years).

### US Fund Plans
**US Funds BASIC €29/month** — Recent performance focus. {N_FONDI_US} funds from 45 American families.
**US Funds PRO €39/month** — Sharpe + TER dominated Score. Medium to long-term selection.
**US Funds VALUE €59/month** — Strict TER and Sharpe filters. Maximum efficiency. 10+ year horizon.

### EU UCITS Fund Plans
**EU Funds BASIC €29/month** — Strict selection. Best European UCITS funds.
**EU Funds PRO €29/month** — Broader universe with active funds.
**EU Funds VALUE €59/month** — Full access to all {N_FONDI_EU} UCITS funds. Includes niche active funds and specialized managers.

### Order Builder
**BASIC €19/month** — Professional MiFID II bank email + generic CSV (Fineco, Directa, Trade Republic, WeBank). Live prices auto-fetched. Up to 10 securities per order.
**PRO €29/month** — Everything in BASIC + IBKR TWS Basket Trader CSV (import in 3 clicks). Unlimited securities and orders.
**VALUE €49/month** — Everything in PRO + direct IBKR API integration (coming soon) + historical order archive + priority support.

---

## [FR] Français — Description des plans

### Plans Actions
**Actions BASIC €29/mois** — "L'Investisseur en Dividendes"
Blue Chips à hauts dividendes. Principaux indices mondiaux. Score dominé par le Dividend Yield. Top 20.

**Actions PRO €39/mois** — "L'Analyste Fondamental Mondial"
Univers complet : {N_AZIONI} tickers sur 23 marchés. Score pondéré EV/FCF et ROE. Analyse fondamentale active. Top 50.

**Actions VALUE €59/mois** — "Le Deep Value Investor"
Filtres les plus stricts sur EV/FCF, P/B, ROE et Debt/EBITDA. Sociétés sous-évaluées, bilan solide. Horizon 5–15 ans.

### Plans ETF
**ETF BASIC €29/mois** — Momentum court terme. Horizon 6–18 mois.
**ETF PRO €39/mois** — Équilibre Sharpe/Performance 1Y. Gestion active de portefeuille, 3–7 ans.
**ETF VALUE €59/mois** — Filtres très exigeants sur TER et Sharpe. Idéal pour construire un patrimoine sur 10–30 ans.

### Plans Fonds US
**Fonds US BASIC €29/mois** — Rendement récent. {N_FONDI_US} fonds, 45 familles américaines.
**Fonds US PRO €39/mois** — Score Sharpe + TER. Sélection moyen-long terme.
**Fonds US VALUE €59/mois** — Filtres rigoureux. Efficacité maximale. Horizon 10+ ans.

### Plans Fonds EU UCITS
**Fonds EU BASIC €29/mois** — Sélection stricte. Meilleurs fonds UCITS.
**Fonds EU PRO €29/mois** — Univers élargi, fonds actifs à coûts moyens.
**Fonds EU VALUE €59/mois** — Accès complet aux {N_FONDI_EU} fonds UCITS. Inclut fonds actifs de niche.

### Order Builder / Constructeur d'Ordres
**BASIC €19/mois** — Email bancaire professionnelle MiFID II + CSV générique. Prix live. Jusqu'à 10 titres.
**PRO €29/mois** — BASIC + CSV IBKR Basket Trader. Titres illimités.
**VALUE €49/mois** — PRO + API IBKR directe (bientôt) + historique d'ordres + support prioritaire.

---

## [DE] Deutsch — Planbeschreibungen

### Aktien-Pläne
**Aktien BASIC €29/Monat** — "Der Dividendeninvestor"
Blue Chips mit Dividendenertrag. Wichtigste Weltindizes. Score dominiert von Dividend Yield. Top 20.

**Aktien PRO €39/Monat** — "Der Globale Fundamentalanalyst"
Volles Universum: {N_AZIONI} Ticker auf 23 Märkten. Score gewichtet auf EV/FCF und ROE. Aktive Fundamentalanalyse. Top 50.

**Aktien VALUE €59/Monat** — "Der Deep Value Investor"
Strengste Filter auf EV/FCF, P/B, ROE und Debt/EBITDA. Nur unterbewertete Unternehmen. Zeithorizont 5–15 Jahre.

### ETF-Pläne
**ETF BASIC €29/Monat** — Kurzfristiger Momentum-Fokus. Zeithorizont 6–18 Monate.
**ETF PRO €39/Monat** — Balance Sharpe/Performance 1J. Aktives ETF-Portfolio-Management, 3–7 Jahre.
**ETF VALUE €59/Monat** — Sehr strenge TER- und Sharpe-Filter. Optimal für langfristigen Vermögensaufbau (10–30 Jahre).

### US-Fonds-Pläne
**US-Fonds BASIC €29/Monat** — Aktuelle Performance. {N_FONDI_US} Fonds, 45 amerikanische Familien.
**US-Fonds PRO €39/Monat** — Score Sharpe + TER. Mittel-/Langfristauswahl.
**US-Fonds VALUE €59/Monat** — Strenge Filter. Maximale Effizienz. Zeithorizont 10+ Jahre.

### EU-UCITS-Fonds-Pläne
**EU-Fonds BASIC €29/Monat** — Strikte Auswahl. Beste europäische UCITS-Fonds.
**EU-Fonds PRO €39/Monat** — Breiteres Universum mit aktiven Fonds.
**EU-Fonds VALUE €59/Monat** — Vollständiger Zugang zu allen {N_FONDI_EU} UCITS-Fonds. Inkl. Nischen-Aktivfonds.

### Order Builder / Orderersteller
**BASIC €19/Monat** — Professionelle MiFID-II-Bank-E-Mail + generische CSV. Live-Preise. Bis 10 Wertpapiere.
**PRO €29/Monat** — BASIC + IBKR TWS Basket Trader CSV. Unbegrenzte Wertpapiere.
**VALUE €49/Monat** — PRO + direkte IBKR-API (demnächst) + historisches Orderarchiv + Prioritätssupport.

---

## Sistema Score / Sistema de Puntuación / Scoring System / Système de Score / Score-System

**Score 0–100 (Percentile)**

IT: Non è un voto assoluto ma una classifica percentile. Score 80 = quel titolo supera l'80% degli altri strumenti selezionati in quella run del piano. Si ricalcola ad ogni aggiornamento.

ES: No es una calificación absoluta sino un ranking percentil. Score 80 = ese título supera al 80% de los demás instrumentos seleccionados en esa ejecución del plan.

EN: Not an absolute grade but a percentile ranking. Score 80 means that instrument outperforms 80% of all other selected instruments in that plan's run.

FR: Pas une note absolue mais un classement percentile. Score 80 = cet instrument surpasse 80% des autres instruments sélectionnés dans cette exécution du plan.

DE: Keine absolute Bewertung, sondern ein Perzentil-Ranking. Score 80 = dieses Instrument übertrifft 80% aller anderen ausgewählten Instrumente in diesem Plan-Durchlauf.

**Direzione metriche / Dirección / Direction:**
- Alto = meglio / mejor / better / mieux / besser: Dividend Yield, ROE, Var 1D%, Perf 3M%, Perf 1Y, Sharpe Ratio
- Basso = meglio / bajo mejor / lower = better / bas mieux / niedriger = besser: P/B, EV/FCF, Net Debt/EBITDA, TER
