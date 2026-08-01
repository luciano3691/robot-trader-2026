# Guida ai Broker — Come Scegliere e Come Usare l'Order Builder
# Broker Guide / Guía de Brókers / Guide des Courtiers / Broker-Leitfaden
# Robot Trader 2026 · Fuerte Venture Capital

---

## [IT] Italiano

### Quale broker scegliere

Robot Trader 2026 genera report con i migliori titoli selezionati dagli screener. Per acquistarli hai bisogno di un **broker** (banca/piattaforma di intermediazione). La scelta del broker dipende dal tuo profilo, dal piano Robot Trader che usi e da quanto investi.

---

### I Broker Principali — Confronto

| Broker | Paese | Commissioni azioni IT/EU | Azioni USA | ETF | IBKR CSV | Target |
|---|---|---|---|---|---|---|
| **Interactive Brokers (IBKR)** | USA/IE | ~€1.25 min/ordine | ~$0.005/azione | Sì, vasto | ✅ Nativo | PRO/VALUE |
| **Fineco Bank** | IT | €2.95 online, €19 telefono | $3.95 online | Sì | ✅ CSV generico | BASIC/PRO |
| **Trade Republic** | DE | €1 flat/ordine | €1 flat | Sì (ETF gratuiti) | ✅ CSV generico | BASIC |
| **Directa Plus** | IT | Da €3/ordine | Da €3.90 | Sì | ✅ CSV generico | BASIC/PRO |
| **XTB** | PL/EU | 0% fino €100k/mese | 0% fino €100k/mese | Sì | ✅ CSV generico | BASIC/PRO |
| **Scalable Capital** | DE | €0.99/ordine (Prime) | €0.99/ordine | Sì, 1.750+ gratis | ✅ CSV generico | BASIC/PRO |
| **DEGIRO** | NL | ~€2-4/ordine EU | ~$0.50 + €1 | Sì | ✅ CSV generico | BASIC |
| **WeBank (Banca Mediolanum)** | IT | Gratuito fino certi limiti | Sì | Sì (limitato) | ✅ CSV generico | BASIC |

---

### Interactive Brokers (IBKR) — Per il Piano Ordini PRO/VALUE

**Perché IBKR è il broker principale per Robot Trader PRO:**
- Il piano Ordini PRO genera un **CSV nativamente compatibile con TWS Basket Trader**
- Import in 3 click: File → Import Orders → Trasmetti
- Commissioni professionale (€1.25 min su EU, $0.005/azione su USA)
- Accesso a **tutti i 23 mercati** dell'universo Robot Trader
- Margine disponibile (non obbligatorio da usare)
- Report fiscale completo per la dichiarazione dei redditi

**Come aprire un conto IBKR:**
1. Vai su interactivebrokers.eu (sede europea — Irlanda)
2. Scegli "Individual Account"
3. Carica documento d'identità e prova di residenza
4. Tempo approvazione: 1–3 giorni lavorativi
5. Versamento minimo: nessuno (conto base gratuito)

**TWS Basket Trader — Come importare il CSV di Robot Trader:**
1. Scarica e installa **TWS** (Trader Workstation) da IBKR
2. In TWS: File → Import Orders → seleziona il CSV generato dall'Order Builder
3. Rivedi la lista degli ordini nell'anteprima
4. Clicca "Trasmetti tutti" — gli ordini vengono inviati al mercato in sequenza
5. Alternativa: **IBKR Mobile** → Portfolio → Import

---

### Fineco Bank — Il Broker Italiano di Riferimento

**Punti di forza:**
- Banco italiano regolamentato — ideale per chi vuole supporto in italiano
- Regime fiscale **amministrato**: Fineco calcola e versa automaticamente la tassa del 26% → nessuna dichiarazione fiscale aggiuntiva per le operazioni in guadagno
- Accesso a Borsa Italiana, Milano, ETF italiani e europei
- App mobile eccellente (voto 4.7/5 App Store)
- Conto corrente integrato con rendimento su liquidità

**Limitazioni:**
- Commissioni più alte rispetto a IBKR (€2.95 vs €1.25)
- Mercati asiatici (Giappone, Hong Kong, Australia) con commissioni più elevate
- CSV IBKR non compatibile — usare il CSV generico dell'Order Builder BASIC

**Come usare con Robot Trader:**
1. Dall'Order Builder, seleziona "CSV generico"
2. Apri Fineco → Trading → Portafoglio → Nuovo Ordine
3. Inserisci manualmente ticker, quantità e prezzo (o usa il CSV come riferimento)
4. Alternativa: ordini telefonici con il consulente Fineco (usare l'email MiFID II generata dall'Order Builder come guida)

---

### Trade Republic — Il Broker per Iniziare

**Punti di forza:**
- Commissione flat €1 per ordine — ideale per importi piccoli (€500–€5.000 per operazione)
- App semplicissima — design pensato per chi inizia
- ETF gratuiti per piani di accumulo (PAC automatico incluso)
- Conto titoli disponibile per residenti italiani, spagnoli, francesi, tedeschi
- Interessi sulla liquidità non investita (tasso BCE – 0.5% circa)

**Limitazioni:**
- Solo azioni e ETF — no fondi comuni
- Mercati limitati: principalmente USA ed Europa
- Nessun accesso a mercati asiatici (Giappone, Australia, ecc.)
- No integrazione diretta con Order Builder (ordini da inserire manualmente dall'app)

**Adatto a:** piano Azioni BASIC e ETF BASIC — piccoli importi, mercati principali.

---

### XTB — Zero Commissioni fino a €100k/mese

**Punti di forza:**
- 0% commissioni su azioni e ETF fino a €100.000/mese di operatività
- Sopra €100k: 0.2% (minimo €10) — ancora competitivo
- Piattaforma xStation ben progettata con analisi tecnica integrata
- Accesso a oltre 3.000 azioni e 360 ETF
- Licenza CySEC e KNF — regolamentato in UE

**Limitazioni:**
- Offerta ETF meno ampia di IBKR
- Alcuni ETF justETF non disponibili su XTB
- Non tutti i 23 mercati Robot Trader sono accessibili

---

### DEGIRO — Per ETF a Basso Costo

**Punti di forza:**
- Commissioni basse su ETF europei (€2 fisso + €0.03% su molte borse EU)
- Ampio catalogo ETF UCITS
- Lista ETF gratuiti (free ETF list) — scambio gratuito una volta al mese per ETF selezionati

**Limitazioni:**
- Meno adatto per azioni singole (commissioni più frammentate)
- Non supporta il regime fiscale amministrato italiano — dichiarazione autonoma

---

### Come Scegliere il Broker in Base al Piano Robot Trader

| Piano Robot Trader | Broker consigliato | Motivo |
|---|---|---|
| Azioni BASIC | Trade Republic, XTB, Fineco | Commissioni basse, mercati principali |
| Azioni PRO | IBKR, Fineco | Accesso a 23 mercati, commissioni professionali |
| Azioni VALUE | IBKR | CSV Basket Trader, massima flessibilità mercati |
| ETF BASIC | Trade Republic, Scalable Capital, DEGIRO | ETF gratuiti o €1/ordine |
| ETF PRO | IBKR, Fineco | Ampio catalogo ETF UCITS |
| ETF VALUE | IBKR | TER minimo, ETF iShares/Vanguard su Xetra |
| Order Builder BASIC | Fineco, Trade Republic, Directa | CSV generico + email MiFID II |
| Order Builder PRO | IBKR (TWS) | Import CSV nativo Basket Trader |

---

### Cosa è il W-8BEN (per IBKR e azioni USA)

Se investi in azioni USA tramite IBKR o altri broker esteri, devi compilare il modulo **W-8BEN**:
- È un modulo USA che dichiara la tua residenza non-americana
- Riduce la ritenuta alla fonte sui dividendi USA dal 30% al 15% (per residenti italiani/spagnoli)
- Si compila una volta online su IBKR → Account Settings → Tax Forms
- Validità: 3 anni (poi da rinnovare)

**Se non compili il W-8BEN:** ritenuta dividendi USA al 30% invece del 15% → perdi il 15% di ogni dividendo da azioni USA.

---

## [ES] Español — Guía de Brókers para Inversores Españoles

### Brókers disponibles en España

| Bróker | Comisiones acciones ES/EU | Acciones USA | ETF | Target |
|---|---|---|---|---|
| **Interactive Brokers** | ~€1.25 mín/orden | ~$0.005/acción | Sí, amplio | PRO/VALUE |
| **Renta 4 Banco** | €3.95 online | $3.95 online | Sí | BASIC/PRO |
| **Self Bank (Singular Bank)** | €3.95 online | $3.95 online | Sí | BASIC |
| **XTB** | 0% hasta €100k/mes | 0% hasta €100k/mes | Sí | BASIC/PRO |
| **Trade Republic** | €1 fijo/orden | €1 fijo/orden | Sí (ETF gratis) | BASIC |
| **DEGIRO** | €2-4/orden EU | €0.50+€1 | Sí | BASIC |
| **Scalable Capital** | €0.99/orden (Prime) | €0.99/orden | Sí, 1.750+ gratis | BASIC/PRO |

**Nota fiscal España:** Renta 4 y Self Bank aplican retención automática del IRPF (régimen similar al administrado italiano) — el inversor no declara las operaciones individualmente. Con IBKR, XTB, DEGIRO → declaración autónoma en IRPF.

### Interactive Brokers en España

IBKR cuenta con licencia europea (IBKR Ireland Limited, regulado por Banco de España para clientes españoles). Ideal para:
- Plan Acciones PRO y VALUE — acceso a los 23 mercados
- Order Builder PRO — importación CSV TWS Basket Trader
- Inversores con cartera >€20.000

### Trade Republic en España

Trade Republic está disponible en España desde 2022. Cuentas en euros, comisión €1 por orden, interface en español. Ideal para:
- Plan Acciones BASIC y ETF BASIC con cantidades €500–€5.000 por operación
- Plan de ahorro mensual (PAC) automatizado en ETF

---

## [EN] English — Broker Guide

### Choosing a Broker Based on Your Robot Trader Plan

**Orders BASIC plan users:**
Any standard retail broker works: Trade Republic, XTB, Degiro, Scalable Capital. Use the "Generic CSV" from the Order Builder as a reference list. Import it into a spreadsheet to copy the tickers and quantities manually.

**Orders PRO plan users:**
Interactive Brokers (IBKR) is strongly recommended. The PRO plan generates a CSV natively compatible with IBKR TWS Basket Trader — import all positions in 3 clicks.

**Orders VALUE plan users:**
IBKR required for full functionality. Future releases will include direct IBKR API integration.

### IBKR TWS Basket Trader — Step by Step

1. Download and install **TWS** from interactivebrokers.eu
2. Log in to TWS
3. Menu: **File → Import Orders → CSV**
4. Select the CSV file downloaded from Robot Trader Order Builder (Orders PRO plan)
5. Preview the order list — verify tickers, quantities, order types
6. Click **"Transmit All"** to send orders to market
7. Monitor execution in the TWS Order Monitor

**Order types in the CSV:** by default, Robot Trader generates **Limit Orders** at the last market close price (with a configurable tolerance). You can change to Market Orders in TWS before transmitting.

### Key Considerations When Choosing a Broker

**Regulated and insured:** always use brokers regulated by EU authorities (BaFin, AMF, Consob, CNMV, CySEC). Your assets are protected up to €20.000 under EU investor compensation schemes (separate from bank deposits).

**Currency:** ensure your broker supports the currencies of the markets you invest in. IBKR holds multi-currency accounts — ideal for the 23-market universe of Robot Trader.

**Mobile vs Desktop:** for the Order Builder email (BASIC plan), you need to forward the generated email to your bank manager — this works from any device. For the CSV import (PRO plan), you need the desktop TWS application.

---

## [FR] Français / [DE] Deutsch — Note rapide

**FR:** En France, les courtiers disponibles incluent Fortuneo, Bourse Direct, Boursorama, Saxo Banque et Interactive Brokers (IE). Pour le plan Ordres PRO avec import CSV TWS, Interactive Brokers est recommandé. Les courtiers français appliquent automatiquement le PFU (30%) sur les transactions en gain.

**DE:** In Deutschland sind die wichtigsten Broker für Robot Trader Nutzer: Comdirect, DKB, ING (pour les Aktien BASIC / ETF BASIC), Scalable Capital (Prime) et Interactive Brokers. Für den Orders PRO Plan mit TWS CSV-Import ist IBKR erforderlich. Deutsche Broker behalten automatisch die Abgeltungsteuer (26.375%) ein.

---

## COME FUNZIONA L'ORDER BUILDER DI ROBOT TRADER

### Flusso completo passo per passo

**1. Accedi all'area clienti** → clicca la card "Ordine Azioni / ETF / Fondi"

**2. I titoli vengono precaricati automaticamente** dal tuo ultimo report. Vedi la lista con ticker, nome, prezzo precedente e quantità suggerita (calcolata dividendo l'importo per il prezzo).

**3. Personalizza l'ordine:**
- Rimuovi i titoli che non vuoi includere
- Modifica le quantità o inserisci un importo totale (il sistema calcola le quantità in automatico)
- Clicca "Aggiorna prezzi live" per avere i prezzi di mercato correnti
- Imposta Stop Loss e Take Profit (opzionale) per singolo titolo

**4. Compila i dati:**
- Nome, indirizzo, codice fiscale/NIE (salvati per i prossimi ordini)
- Nome della banca, nome del gestore, IBAN del conto

**5. Scegli il formato di output:**
- **"Invia Email Bancaria"** → email professionale MiFID II inviata al gestore + copia al tuo indirizzo
- **"Scarica CSV Generico"** → file importabile su qualsiasi broker (Fineco, Directa, Trade Republic, WeBank, ecc.)
- **"Scarica CSV IBKR"** (solo Piano PRO) → file compatibile con TWS Basket Trader

**6. Storico ordini:** i tuoi ultimi 20 ordini sono salvati nell'area clienti per riferimento.
