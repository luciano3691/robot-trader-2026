# Glossario Finanziario / Glosario / Financial Glossary / Glossaire / Finanzielles Glossar
# Robot Trader 2026

---

## [IT] Italiano

### Metriche per le Azioni

**EV/FCF — Enterprise Value / Free Cash Flow**
Quante volte il mercato paga il cash generato dall'azienda. Più è basso, più il titolo è economico rispetto alla sua capacità di generare cassa. EV/FCF ≤ 12x (piano VALUE) indica un'azienda sottovalutata rispetto ai flussi reali. *Basso = meglio.*

**P/B — Price-to-Book**
Rapporto tra prezzo di mercato e valore contabile (patrimonio netto). P/B ≤ 1x significa comprare un'azienda sotto il suo valore di libro — approccio "deep value" classico. *Basso = meglio.*

**ROE — Return on Equity**
Redditività del patrimonio netto: quanto l'azienda guadagna per ogni euro di capitale proprio. ROE ≥ 2% (VALUE) filtra le aziende con una redditività minima sul capitale investito. *Alto = meglio.*

**Net Debt/EBITDA — Indebitamento netto su EBITDA**
Quanti anni di margine operativo lordo servirebbero per ripagare il debito netto. ≤ 2x (VALUE) seleziona aziende con bassa leva finanziaria. *Basso = meglio.*

**Dividend Yield — Rendimento da dividendo**
Dividendo annuale diviso per il prezzo dell'azione. Espressa in percentuale. Nel piano Azioni BASIC pesa il 35% dello score perché il profilo è orientato all'income. *Alto = meglio.*

**Market Cap — Capitalizzazione di mercato**
Valore totale di tutte le azioni in circolazione. Robot Trader filtra per Market Cap ≥ 100M USD per escludere micro-cap illiquide.

**Var 1D% — Variazione giornaliera**
Variazione percentuale del prezzo nell'ultima seduta di borsa. Nel piano BASIC pesa il 25% dello score come indicatore di momentum di breve.

---

### Metriche per ETF e Fondi

**TER — Total Expense Ratio (Costo totale annuo)**
Percentuale annua addebitata dall'ETF o fondo per coprire le spese di gestione. Cruciale su orizzonti lunghi: una differenza di 0,1% su 20 anni può valere migliaia di euro. *Basso = meglio.*

**Sharpe Ratio**
Rendimento in eccesso (rispetto al tasso privo di rischio) per unità di volatilità. Sharpe 1,0 = ogni punto % di rischio genera 1% di rendimento extra. *Alto = meglio.*

**Performance 1Y — Rendimento a 1 anno**
Variazione percentuale del prezzo (o NAV) nell'ultimo anno solare. Usata come filtro minimo e come componente dello score.

**Perf 3M% — Rendimento a 3 mesi**
Variazione dell'ultimo trimestre. Nel piano ETF BASIC pesa il 45% dello score (orientamento al momentum).

**AUM — Assets Under Management**
Patrimonio totale gestito dal fondo. Usato come filtro di liquidità per i Fondi EU UCITS: BASIC ≥ 50M€, PRO ≥ 10M€, VALUE ≥ 1M€.

**ETF ad Accumulazione (Accumulating / ACC)**
ETF che reinveste automaticamente i dividendi nel fondo. Fiscalmente efficiente per gli investitori europei. Robot Trader seleziona SOLO ETF ad accumulazione.

**ETF Fisico (Physical)**
ETF che detiene direttamente i titoli sottostanti (vs sintetico che usa swap). Minore rischio di controparte. Robot Trader seleziona SOLO ETF fisici.

**UCITS — Undertakings for Collective Investment in Transferable Securities**
Direttiva europea che regola i fondi di investimento vendibili in tutta l'UE. Garantisce standard minimi di diversificazione, liquidità e trasparenza.

---

### Score e Metodologia

**Score 0–100 (Percentile)**
Non un voto assoluto ma una classifica relativa. Se un titolo ha Score 80, supera l'80% degli altri strumenti del piano in quella specifica run. Si ricalcola ad ogni aggiornamento notturno.

**Pesi dello Score per piano:**
- Azioni BASIC: Dividend Yield 35%, Var 1D% 25%, ROE 20%, P/B 10%, EV/FCF 10%
- Azioni PRO: EV/FCF 35%, ROE 25%, P/B 20%, Debt/EBITDA 15%, Var 1D% 5%
- Azioni VALUE: EV/FCF 40%, ROE 25%, Debt/EBITDA 20%, P/B 15%
- ETF BASIC: Perf 3M% 45%, Perf 1Y 20%, TER 20%, Sharpe 15%
- ETF PRO: Sharpe 40%, Perf 1Y 30%, TER 20%, Perf 3M% 10%
- ETF VALUE: Sharpe 45%, Perf 1Y 25%, TER 25%, Perf 3M% 5%
- Fondi BASIC: Perf 3M% 30%, Perf 1Y 30%, TER 25%, Sharpe 15%
- Fondi PRO: Sharpe 40%, TER 30%, Perf 1Y 25%, Perf 3M% 5%
- Fondi VALUE: Sharpe 45%, TER 35%, Perf 1Y 15%, Perf 3M% 5%

---

### Concetti di Investimento

**Deep Value Investing**
Strategia basata sull'acquisto di aziende significativamente al di sotto del loro valore intrinseco (EV/FCF basso, P/B basso, bilancio solido). Orizzonte tipico 5–15 anni.

**Blue Chip**
Aziende di grande capitalizzazione, storia consolidata, bilanci solidi. Tipicamente presenti nei principali indici mondiali (S&P500, FTSE100, DAX, ecc.).

**MiFID II**
Direttiva europea (Markets in Financial Instruments Directive II). Stabilisce obblighi di trasparenza e protezione degli investitori. I report di Robot Trader sono informativi e non costituiscono consulenza ai sensi di MiFID II.

**IBKR / Interactive Brokers**
Broker americano tra i più usati da professionisti. Il piano Ordini PRO genera CSV compatibili con il TWS Basket Trader di IBKR.

**NAV — Net Asset Value (Valore Patrimoniale Netto)**
Valore per quota di un fondo comune. Calcolato giornalmente dividendo il patrimonio totale del fondo per il numero di quote in circolazione.

---

## [ES] Español

### Métricas para Acciones

**EV/FCF — Enterprise Value / Free Cash Flow**
Cuántas veces el mercado paga el efectivo generado por la empresa. Cuanto más bajo, más barata está la empresa respecto a su capacidad de generar caja. EV/FCF ≤ 12x (plan VALUE) indica empresa infravalorada. *Bajo = mejor.*

**P/B — Price-to-Book (Precio/Valor Contable)**
Ratio entre precio de mercado y valor contable (patrimonio neto). P/B ≤ 1x = comprar una empresa por debajo de su valor en libros. Enfoque "deep value" clásico. *Bajo = mejor.*

**ROE — Return on Equity (Rentabilidad sobre Fondos Propios)**
Rentabilidad del patrimonio neto: cuánto gana la empresa por cada euro de capital propio. ROE ≥ 2% (VALUE) selecciona empresas con rentabilidad mínima. *Alto = mejor.*

**Net Debt/EBITDA — Deuda Neta / EBITDA**
Cuántos años de beneficio operativo se necesitarían para pagar la deuda neta. ≤ 2x (VALUE) selecciona empresas con baja apalancamiento. *Bajo = mejor.*

**Dividend Yield — Rentabilidad por Dividendo**
Dividendo anual dividido por el precio de la acción (%). En el plan Acciones BASIC pondera un 35% del score. *Alto = mejor.*

**Market Cap — Capitalización Bursátil**
Valor total de todas las acciones en circulación. Robot Trader filtra Market Cap ≥ 100M USD para excluir micro-caps ilíquidas.

---

### Métricas para ETF y Fondos

**TER — Total Expense Ratio (Comisión Total Anual)**
Porcentaje anual cobrado por el ETF o fondo por gastos de gestión. Crucial a largo plazo. *Bajo = mejor.*

**Sharpe Ratio**
Rendimiento en exceso por unidad de volatilidad. Sharpe 1,0 = por cada punto de riesgo, 1 punto de rentabilidad extra. *Alto = mejor.*

**AUM — Assets Under Management (Patrimonio bajo gestión)**
Activos totales gestionados por el fondo. Filtro de liquidez para Fondos EU UCITS.

**ETF de Acumulación (Accumulating / ACC)**
ETF que reinvierte automáticamente los dividendos. Fiscalmente eficiente para inversores europeos. Robot Trader selecciona SOLO ETF de acumulación.

**ETF Físico (Physical)**
ETF que posee directamente los activos subyacentes (vs sintético que usa swaps). Menor riesgo de contraparte. Robot Trader selecciona SOLO ETF físicos.

**UCITS — Organismos de Inversión Colectiva en Valores Mobiliarios**
Directiva europea que regula los fondos vendibles en toda la UE. Garantiza diversificación mínima, liquidez y transparencia.

---

### Conceptos de Inversión

**Deep Value Investing** — Estrategia basada en comprar empresas significativamente por debajo de su valor intrínseco. Horizonte típico 5–15 años.

**Blue Chip** — Empresas de gran capitalización, historia consolidada, balances sólidos. Típicamente en los principales índices mundiales.

**MiFID II** — Directiva europea sobre mercados de instrumentos financieros. Los informes de Robot Trader son informativos y NO constituyen asesoramiento financiero según MiFID II.

**NAV — Valor Liquidativo** — Valor por participación de un fondo común. Calculado diariamente.

**IBKR / Interactive Brokers** — Broker americano profesional. El plan Órdenes PRO genera CSV compatibles con IBKR TWS Basket Trader.

---

## [EN] English

### Stock Metrics

**EV/FCF — Enterprise Value / Free Cash Flow**
How many times the market pays for the company's generated cash. Lower = cheaper relative to real cash generation. EV/FCF ≤ 12x (VALUE plan) indicates undervaluation. *Lower = better.*

**P/B — Price-to-Book**
Market price vs. book value (net equity). P/B ≤ 1x = buying a company below its book value — classic "deep value" approach. *Lower = better.*

**ROE — Return on Equity**
How much profit the company earns per euro of equity capital. ROE ≥ 2% (VALUE) filters for companies with minimum return on invested capital. *Higher = better.*

**Net Debt/EBITDA**
How many years of operating profit would be needed to repay net debt. ≤ 2x (VALUE) selects low-leverage companies. *Lower = better.*

**Dividend Yield**
Annual dividend divided by share price (%). Dominates the Stocks BASIC score at 35% (income-oriented profile). *Higher = better.*

**Market Cap — Market Capitalization**
Total value of all outstanding shares. Robot Trader filters for Market Cap ≥ $100M USD to exclude illiquid micro-caps.

---

### ETF and Fund Metrics

**TER — Total Expense Ratio**
Annual percentage charged by the ETF or fund for management expenses. Critical over long horizons: a 0.1% difference over 20 years can mean thousands of euros. *Lower = better.*

**Sharpe Ratio**
Excess return (above risk-free rate) per unit of volatility. Sharpe 1.0 = every 1% of risk generates 1% of extra return. *Higher = better.*

**AUM — Assets Under Management**
Total assets managed by the fund. Used as a liquidity filter for EU UCITS Funds.

**Accumulating ETF (ACC)**
ETF that automatically reinvests dividends. Tax-efficient for European investors. Robot Trader selects ONLY accumulating ETFs.

**Physical ETF**
ETF that directly holds underlying assets (vs. synthetic which uses swaps). Lower counterparty risk. Robot Trader selects ONLY physical ETFs.

**UCITS — Undertakings for Collective Investment in Transferable Securities**
European directive regulating funds sellable across the EU. Ensures minimum diversification, liquidity, and transparency standards.

---

### Investment Concepts

**Deep Value Investing** — Strategy based on buying companies significantly below intrinsic value (low EV/FCF, low P/B, solid balance sheet). Typical horizon: 5–15 years.

**Blue Chip** — Large-cap companies with established track record and solid financials. Typically in major global indices (S&P500, FTSE100, DAX, etc.).

**MiFID II** — European directive on markets in financial instruments. Robot Trader reports are informational tools, NOT investment recommendations under MiFID II.

**NAV — Net Asset Value** — Per-share value of a mutual fund. Calculated daily by dividing total fund assets by shares outstanding.

**IBKR / Interactive Brokers** — Professional American broker. Orders PRO plan generates CSV compatible with IBKR TWS Basket Trader.

---

## [FR] Français

### Métriques pour les Actions

**EV/FCF — Enterprise Value / Free Cash Flow**
Combien de fois le marché paie les flux de trésorerie générés. Plus c'est bas, plus l'entreprise est bon marché par rapport à sa capacité à générer du cash. EV/FCF ≤ 12x (plan VALUE) = entreprise sous-évaluée. *Bas = mieux.*

**P/B — Price-to-Book (Cours/Valeur Comptable)**
Prix de marché vs. valeur comptable (capitaux propres). P/B ≤ 1x = acheter en dessous de la valeur comptable — approche "deep value" classique. *Bas = mieux.*

**ROE — Return on Equity (Rentabilité des Capitaux Propres)**
Combien l'entreprise gagne par euro de capital propre. ROE ≥ 2% (VALUE) filtre les entreprises avec une rentabilité minimum. *Haut = mieux.*

**Net Debt/EBITDA**
Combien d'années de résultat opérationnel seraient nécessaires pour rembourser la dette nette. ≤ 2x = faible endettement. *Bas = mieux.*

**Dividend Yield — Rendement du Dividende**
Dividende annuel / prix de l'action (%). Domine le score Actions BASIC à 35% (profil orienté revenus). *Haut = mieux.*

---

### Métriques pour ETF et Fonds

**TER — Total Expense Ratio (Frais totaux annuels)**
Pourcentage annuel facturé par l'ETF ou le fonds pour les frais de gestion. Crucial sur le long terme. *Bas = mieux.*

**Sharpe Ratio** — Rendement excédentaire par unité de volatilité. Sharpe 1,0 = pour chaque point de risque, 1 point de rendement supplémentaire. *Haut = mieux.*

**AUM — Actifs sous gestion** — Actifs totaux gérés par le fonds. Filtre de liquidité pour les Fonds EU UCITS.

**ETF Capitalisant (Accumulating / ACC)** — ETF qui réinvestit automatiquement les dividendes. Fiscalement efficace pour les investisseurs européens. Robot Trader sélectionne UNIQUEMENT des ETF capitalisants.

**ETF Physique** — ETF qui détient directement les actifs sous-jacents (vs. synthétique utilisant des swaps). Risque de contrepartie réduit.

**UCITS** — Directive européenne régissant les fonds vendables dans toute l'UE. Garantit diversification, liquidité et transparence minimales.

---

### Concepts d'Investissement

**Deep Value Investing** — Stratégie basée sur l'achat d'entreprises nettement en dessous de leur valeur intrinsèque. Horizon typique : 5–15 ans.

**Blue Chip** — Grandes entreprises, historique établi, bilans solides. Typiquement dans les grands indices mondiaux.

**MiFID II** — Directive européenne sur les marchés d'instruments financiers. Les rapports Robot Trader sont des outils informatifs, PAS des recommandations d'investissement selon MiFID II.

**NAV — Valeur Liquidative** — Valeur par part d'un fonds commun. Calculée quotidiennement.

---

## [DE] Deutsch

### Aktien-Metriken

**EV/FCF — Enterprise Value / Free Cash Flow**
Wie oft der Markt den generierten Cashflow des Unternehmens bezahlt. Niedriger = günstiger im Verhältnis zur Cash-Generierung. EV/FCF ≤ 12x (VALUE) = unterbewertetes Unternehmen. *Niedriger = besser.*

**P/B — Kurs-Buchwert-Verhältnis**
Marktpreis vs. Buchwert (Eigenkapital). P/B ≤ 1x = Kauf unterhalb des Buchwertes — klassischer "Deep Value"-Ansatz. *Niedriger = besser.*

**ROE — Eigenkapitalrendite (Return on Equity)**
Wie viel Gewinn das Unternehmen pro Euro Eigenkapital erwirtschaftet. ROE ≥ 2% (VALUE) filtert Unternehmen mit Mindestrendite. *Höher = besser.*

**Net Debt/EBITDA — Nettoverschuldung / EBITDA**
Wie viele Jahre Betriebsergebnis nötig wären, um die Nettoschulden zu tilgen. ≤ 2x = geringe Verschuldung. *Niedriger = besser.*

**Dividend Yield — Dividendenrendite**
Jährliche Dividende / Aktienkurs (%). Dominiert den Aktien-BASIC-Score mit 35% (ertragsorientiertes Profil). *Höher = besser.*

---

### ETF- und Fonds-Metriken

**TER — Total Expense Ratio (Gesamtkostenquote)**
Jährlicher Prozentsatz, den der ETF oder Fonds für Verwaltungskosten berechnet. Entscheidend über lange Zeiträume. *Niedriger = besser.*

**Sharpe Ratio** — Überschussrendite (über risikofreiem Zinssatz) pro Volatilitätseinheit. Sharpe 1,0 = für jeden Risikopunkt 1 Punkt Mehrrendite. *Höher = besser.*

**AUM — Verwaltetes Vermögen** — Gesamtvermögen des Fonds. Liquiditätsfilter für EU-UCITS-Fonds.

**Thesaurierender ETF (Accumulating / ACC)** — ETF, der Dividenden automatisch reinvestiert. Steuerlich effizient für europäische Anleger. Robot Trader wählt AUSSCHLIESSLICH thesaurierende ETFs.

**Physischer ETF** — ETF, der die Basiswerte direkt hält (vs. synthetisch mit Swaps). Geringeres Gegenparteirisiko.

**UCITS — Europäische Investmentfonds-Richtlinie** — Regelt in der gesamten EU vertreibbare Fonds. Garantiert Mindeststandards für Diversifikation, Liquidität und Transparenz.

---

### Anlagekonzepte

**Deep Value Investing** — Strategie, die auf den Kauf von Unternehmen deutlich unter ihrem inneren Wert abzielt (niedriges EV/FCF, niedriges P/B, solide Bilanz). Typischer Zeithorizont: 5–15 Jahre.

**Blue Chip** — Großunternehmen mit etablierter Geschichte und soliden Finanzen. Typischerweise in den großen Weltindizes (S&P500, FTSE100, DAX usw.).

**MiFID II** — Europäische Richtlinie über Märkte für Finanzinstrumente. Robot Trader-Berichte sind Informationswerkzeuge, KEINE Anlageempfehlungen gemäß MiFID II.

**NAV — Nettoinventarwert** — Wert je Anteil eines Investmentfonds. Täglich berechnet.

**IBKR / Interactive Brokers** — Professioneller amerikanischer Broker. Der Orders-PRO-Plan generiert CSV-Dateien, die mit dem IBKR TWS Basket Trader kompatibel sind.
