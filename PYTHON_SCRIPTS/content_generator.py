"""
Content Generator — Robot Trader 2026 / Fuerte Venture Capital
Genera testo post social (IT + ES) via Claude API.
Fallback automatico ai template statici se API non disponibile.

Credenziali in config.json → social.anthropic.api_key
"""
import json
import os
import requests
from datetime import datetime
from typing import Optional

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL      = "claude-opus-4-7"


def _anthropic_key() -> str:
    with open(CONFIG_FILE, encoding='utf-8') as f:
        return json.load(f).get('social', {}).get('anthropic', {}).get('api_key', '')


# ── Template statici (fallback) ───────────────────────────────────────────────
# Fonte: 05_LINKEDIN_AUTOMATION/5C_LINKEDIN_POST_TEMPLATES.txt

TEMPLATES: dict[str, dict[str, str]] = {
    "VALUE_INTRO": {
        "IT": """Stai cercando azioni sottovalutate ma non sai da dove iniziare?

La risposta: 5 filtri quantitativi hard.

📊 EV/FCF · P/B · ROE · Net Debt/EBITDA · Score

Niente emozioni. Niente intuizioni. Solo numeri.

Qual è il tuo filtro preferito? 👇

#ValueInvesting #StockScreening #FinancialAnalysis""",
        "ES": """¿Buscas acciones infravaloradas pero no sabes por dónde empezar?

La respuesta: 5 filtros cuantitativos duros.

📊 EV/FCF · P/B · ROE · Deuda Neta/EBITDA · Score

Sin emociones. Sin intuiciones. Solo números.

¿Cuál es tu filtro favorito? 👇

#ValueInvesting #ScreeningDeAcciones #AnalisisFinanciero""",
    },
    "5_FILTRI": {
        "IT": """🔍 I 5 Filtri Che Usiamo Ogni Mattina

Ecco come troviamo opportunità undervalue in 3.000+ azioni globali:

1️⃣ EV/FCF ≤ 12 — Enterprise Value vs Free Cash Flow
2️⃣ P/B ≤ 1,2 — Prezzo vs Valore Contabile
3️⃣ ROE ≥ 0% — Return on Equity positivo
4️⃣ ND/EBITDA ≤ 2,5 — Debito contenuto
5️⃣ SCORE — Ranking composito

Risultato: le migliori opportunità selezionate ogni notte alle 23:00.

Quante ne avresti trovate senza questi filtri?

#DeepValue #StockScreening #InvestmentStrategy""",
        "ES": """🔍 Los 5 Filtros Que Usamos Cada Mañana

Así encontramos oportunidades infravaloradas en 3.000+ acciones globales:

1️⃣ EV/FCF ≤ 12 — Valor Empresarial vs Flujo de Caja Libre
2️⃣ P/B ≤ 1,2 — Precio vs Valor Contable
3️⃣ ROE ≥ 0% — Rentabilidad positiva
4️⃣ ND/EBITDA ≤ 2,5 — Deuda controlada
5️⃣ SCORE — Ranking compuesto

¿Cuántas hubieras encontrado sin estos filtros?

#ValueDeep #ScreeningAcciones #EstrategiaInversión""",
    },
    "EVFCF": {
        "IT": """💡 EV/FCF: Perché È Il Nostro Filtro Preferito

Enterprise Value ÷ Free Cash Flow.

Cosa ti dice? La velocità con cui l'azienda genera liquidità reale.

EV/FCF basso (≤ 12) = paghi poco per ogni euro di cassa generato.
EV/FCF alto (> 20) = stai pagando premium per aspettative future.

Noi filtriamo solo le aziende che generano cassa abbondante al prezzo giusto.

Perché ancora scegli titoli al feel? 😏

#InvestmentAnalysis #ValueMetrics #Screening""",
        "ES": """💡 EV/FCF: Por Qué Es Nuestro Filtro Favorito

Valor Empresarial ÷ Flujo de Caja Libre.

¿Qué te dice? La velocidad con que la empresa genera liquidez real.

EV/FCF bajo (≤ 12) = pagas poco por cada euro de caja generado.
EV/FCF alto (> 20) = pagas prima por expectativas futuras.

Solo filtramos empresas que generan caja abundante al precio correcto.

#AnalisisInversión #ValueMetrics #Screening""",
    },
    "PB_ROE": {
        "IT": """⚖️ P/B vs ROE: Quale Scegliere?

Non è P/B O ROE.
È P/B AND ROE.

P/B basso (≤ 1,2) = prezzo scontato rispetto al valore contabile
ROE positivo (≥ 0%) = l'azienda genera profitti dal capitale

Combinati insieme? Identificano aziende solide acquistate a sconto.

Robot Trader 2026 li usa entrambi — ogni notte — su 3.072 azioni globali.

#StockAnalysis #FinancialMetrics #ValueInvesting""",
        "ES": """⚖️ P/B vs ROE: ¿Cuál Elegir?

No es P/B O ROE.
Es P/B AND ROE.

P/B bajo (≤ 1,2) = precio descontado respecto al valor contable
ROE positivo (≥ 0%) = la empresa genera beneficios desde el capital

Combinados: identifican empresas sólidas compradas con descuento.

Robot Trader 2026 los usa ambos — cada noche — en 3.072 acciones globales.

#AnalisisAcciones #MetricasFinancieras #ValueInvesting""",
    },
    "CASE_STUDY": {
        "IT": """📈 Come Funziona il Nostro Screener — Esempio Reale

Ogni notte alle 23:00, Robot Trader analizza 3.072 azioni su 23 mercati globali.

Applica 5 filtri hard:
✅ EV/FCF ≤ 12
✅ P/B ≤ 1,2
✅ ROE ≥ 0%
✅ Net Debt/EBITDA ≤ 2,5
✅ Score composito

Output: Top 50 opportunità ranked per score — pronte alle 07:00.

Zero emozioni. Zero intuizioni. Solo dati.

#RobotTrader #ValueInvesting #ScreenerResults""",
        "ES": """📈 Cómo Funciona Nuestro Screener — Ejemplo Real

Cada noche a las 23:00, Robot Trader analiza 3.072 acciones en 23 mercados globales.

Aplica 5 filtros duros:
✅ EV/FCF ≤ 12
✅ P/B ≤ 1,2
✅ ROE ≥ 0%
✅ Deuda Neta/EBITDA ≤ 2,5
✅ Score compuesto

Output: Top 50 oportunidades rankeadas por score — listas a las 07:00.

Sin emociones. Sin intuiciones. Solo datos.

#RobotTrader #ValueInvesting #ResultadosScreener""",
    },
    "ETF_SCREENING": {
        "IT": """📊 Anche Gli ETF Hanno I Loro Filtri

Robot Trader 2026 non screena solo azioni.
Analizza 678 ETF globali con criteri precisi:

✅ TER ≤ 0,35% (costo annuo massimo per BASIC)
✅ Sharpe Ratio ≥ 0,8 (rendimento/rischio)
✅ Volume ≥ 500k (liquidità garantita)
✅ Solo replica fisica
✅ Solo accumulazione (no distribuzione)

Risultato: solo gli ETF che valgono davvero il tuo capitale.

#ETFScreening #PassiveInvesting #RobotTrader""",
        "ES": """📊 Los ETFs También Tienen Sus Filtros

Robot Trader 2026 no solo analiza acciones.
Analiza 678 ETFs globales con criterios precisos:

✅ TER ≤ 0,35% (coste anual máximo)
✅ Sharpe Ratio ≥ 0,8 (rentabilidad/riesgo)
✅ Volumen ≥ 500k (liquidez garantizada)
✅ Solo réplica física
✅ Solo acumulación

Resultado: solo los ETFs que realmente merecen tu capital.

#ScreeningETF #InversiónPasiva #RobotTrader""",
    },
    "TEAM": {
        "IT": """👥 Chi C'è Dietro Robot Trader 2026?

Fuerte Venture Capital SL — Spagna

3 decenni di esperienza in:
✅ Operations & Logistics (scaling internazionale)
✅ Venture Capital & Deal-Making
✅ Intelligenza Artificiale & Automazione
✅ Strategia Finanziaria

Ossessionati da:
📊 Dati puliti e verificabili
⚡ Automazione intelligente
🎯 Value investing puro — niente hype

Questo è Robot Trader 2026.

#FuerteVC #VentureCapital #QuantitativeInvesting""",
        "ES": """👥 ¿Quién Está Detrás de Robot Trader 2026?

Fuerte Venture Capital SL — España

3 décadas de experiencia en:
✅ Operations & Logistics (scaling internacional)
✅ Venture Capital & Deal-Making
✅ Inteligencia Artificial & Automatización
✅ Estrategia Financiera

Obsesionados por:
📊 Datos limpios y verificables
⚡ Automatización inteligente
🎯 Value investing puro — sin hype

Esto es Robot Trader 2026.

#FuerteVC #VentureCapital #InversiónCuantitativa""",
    },
    "LAUNCH": {
        "IT": """🚀 Robot Trader 2026 — Disponibile Adesso

Lo screener quantitativo che stavi aspettando.

Ogni notte: 3.072 azioni + 678 ETF + 1.087 fondi analizzati.
Ogni mattina: il tuo report Excel pronto da scaricare.

Piano BASIC → indici principali · Top 20
Piano PRO → universo completo · Top 50
Piano VALUE → filtri più ampi · turnaround inclusi

Primo passo: registrati su https://trader.fuerteventurecapital.com

#RobotTrader #ValueInvesting #Launching""",
        "ES": """🚀 Robot Trader 2026 — Disponible Ahora

El screener cuantitativo que estabas esperando.

Cada noche: 3.072 acciones + 678 ETFs + 1.087 fondos analizados.
Cada mañana: tu informe Excel listo para descargar.

Plan BASIC → índices principales · Top 20
Plan PRO → universo completo · Top 50
Plan VALUE → filtros más amplios · turnaround incluidos

Primer paso: regístrate en https://trader.fuerteventurecapital.com

#RobotTrader #ValueInvesting #Lanzamiento""",
    },
    "FONDI_SCREENING": {
        "IT": """🎯 1.087 Fondi — Screenati Ogni Notte

Robot Trader 2026 analizza anche i fondi comuni:

✅ TER ≤ 0,75% (piani BASIC)
✅ Sharpe Ratio ≥ 0,6
✅ Dimensione ≥ 200 milioni $
✅ Performance 1Y positiva

36 famiglie: Vanguard, Fidelity, T.Rowe Price, BlackRock, PIMCO e altri.

Il tuo piano include anche il modulo fondi?

#FundScreening #MutualFunds #RobotTrader""",
        "ES": """🎯 1.087 Fondos — Analizados Cada Noche

Robot Trader 2026 también analiza fondos de inversión:

✅ TER ≤ 0,75% (planes BASIC)
✅ Sharpe Ratio ≥ 0,6
✅ Tamaño ≥ 200 millones $
✅ Rendimiento 1Y positivo

36 familias: Vanguard, Fidelity, T.Rowe Price, BlackRock, PIMCO y otros.

¿Tu plan incluye también el módulo de fondos?

#ScreeningFondos #FondosInversión #RobotTrader""",
    },
    "SALARY_TRAP": {
        "IT": """💸 Il Tuo Stipendio Ti Tradisce Ogni Mese

Ogni mese il tuo stipendio arriva, e ogni mese il potere d'acquisto scende.

L'inflazione erode quello che non investi.
Il conto corrente non ti protegge.

La soluzione non è lavorare di più — è far lavorare i tuoi soldi con metodo.

Robot Trader 2026 analizza ogni notte 3.072 azioni su 23 mercati globali.
Risultato: le opportunità migrate a valore, pronte ogni mattina alle 07:00.

Smetti di lasciare i tuoi risparmi fermi.

Scopri come → https://trader.fuerteventurecapital.com

#InvestireConMetodo #ValueInvesting #FinanzaPersonale""",
        "ES": """💸 Tu Sueldo Te Traiciona Cada Mes

Cada mes llega tu sueldo, y cada mes baja tu poder adquisitivo.

La inflación erosiona lo que no inviertes.
La cuenta corriente no te protege.

La solución no es trabajar más — es hacer trabajar tu dinero con método.

Robot Trader 2026 analiza cada noche 3.072 acciones en 23 mercados globales.
Resultado: las mejores oportunidades de valor, listas cada mañana a las 07:00.

Deja de tener tus ahorros parados.

Descubre cómo → https://trader.fuerteventurecapital.com

#InvertirConMétodo #ValueInvesting #FinanzasPersonales""",
        "EN": """💸 Your Salary Is Betraying You Every Month

Every month your paycheck arrives, and every month your purchasing power drops.

Inflation erodes what you don't invest.
A savings account doesn't protect you.

The solution isn't working harder — it's making your money work with a system.

Robot Trader 2026 analyzes 3,072 stocks across 23 global markets every night.
Result: the best value opportunities, ready every morning at 07:00.

Stop leaving your savings idle.

Discover how → https://trader.fuerteventurecapital.com

#InvestWithMethod #ValueInvesting #PersonalFinance""",
        "FR": """💸 Votre Salaire Vous Trahit Chaque Mois

Chaque mois votre salaire arrive, et chaque mois votre pouvoir d'achat baisse.

L'inflation érode ce que vous n'investissez pas.
Un compte courant ne vous protège pas.

La solution n'est pas de travailler plus — c'est de faire travailler votre argent avec méthode.

Robot Trader 2026 analyse chaque nuit 3 072 actions sur 23 marchés mondiaux.
Résultat : les meilleures opportunités value, prêtes chaque matin à 07h00.

Arrêtez de laisser votre épargne dormir.

Découvrez comment → https://trader.fuerteventurecapital.com

#InvestirAvecMéthode #ValueInvesting #FinancesPersonnelles""",
        "DE": """💸 Ihr Gehalt Verrät Sie Jeden Monat

Jeden Monat kommt Ihr Gehalt, und jeden Monat sinkt Ihre Kaufkraft.

Inflation zehrt auf, was Sie nicht investieren.
Ein Girokonto schützt Sie nicht.

Die Lösung ist nicht mehr arbeiten — sondern Ihr Geld mit System arbeiten lassen.

Robot Trader 2026 analysiert jede Nacht 3.072 Aktien auf 23 globalen Märkten.
Ergebnis: die besten Value-Chancen, jeden Morgen um 07:00 Uhr bereit.

Hören Sie auf, Ihre Ersparnisse stilllegen zu lassen.

Mehr erfahren → https://trader.fuerteventurecapital.com

#InvestierenMitSystem #ValueInvesting #Persönlichefinanzen""",
    },
    "WEALTHOS_PROMO": {
        "IT": """🏛️ WealthOS — Il Tuo Patrimonio, Finalmente Sotto Controllo

Conti bancari sparsi. Investimenti su 3 piattaforme diverse. ETF, azioni, liquidità.

Sai esattamente quanto vali oggi?

WealthOS aggrega tutto in un unico cruscotto:
✅ Patrimonio netto in tempo reale
✅ Allocazione per asset class e valuta
✅ Performance storica e proiezioni
✅ Integrazione con Robot Trader 2026

Non è un conto bancario. Non è un robo-advisor.
È il tuo ufficio di analisi personale.

Scopri WealthOS → https://trader.fuerteventurecapital.com

#WealthOS #PatrimonioPersonale #FinanzaPrivata""",
        "ES": """🏛️ WealthOS — Tu Patrimonio, Por Fin Bajo Control

Cuentas bancarias dispersas. Inversiones en 3 plataformas diferentes. ETFs, acciones, liquidez.

¿Sabes exactamente cuánto vales hoy?

WealthOS lo agrega todo en un único panel:
✅ Patrimonio neto en tiempo real
✅ Asignación por clase de activo y divisa
✅ Rendimiento histórico y proyecciones
✅ Integración con Robot Trader 2026

No es una cuenta bancaria. No es un robo-advisor.
Es tu oficina de análisis personal.

Descubre WealthOS → https://trader.fuerteventurecapital.com

#WealthOS #PatrimonioPersonal #FinanzaPrivada""",
        "EN": """🏛️ WealthOS — Your Wealth, Finally Under Control

Bank accounts scattered. Investments on 3 different platforms. ETFs, stocks, cash.

Do you know exactly what you're worth today?

WealthOS aggregates everything into a single dashboard:
✅ Real-time net worth
✅ Asset class and currency allocation
✅ Historical performance and projections
✅ Integration with Robot Trader 2026

Not a bank account. Not a robo-advisor.
Your personal analysis office.

Discover WealthOS → https://trader.fuerteventurecapital.com

#WealthOS #PersonalWealth #PrivateFinance""",
    },
    "TREND_MOBILIARE": {
        "IT": """📊 Il Mercato Si Muove — Stai Guardando o Stai Agendo?

Ogni settimana i mercati offrono opportunità.
Ogni settimana la maggior parte degli investitori le lascia passare.

Non perché non esistano — ma perché non hanno un sistema per trovarle.

Robot Trader 2026 monitora ogni notte:
📈 3.072 azioni su 23 mercati globali
📦 678 ETF con Sharpe e performance 1Y
🏦 1.087 fondi comuni con criteri quantitativi

Il risultato? Una lista ordinata per score — ogni mattina alle 07:00.

Il mercato non aspetta. Tu hai un sistema?

#TrendDiMercato #ValueInvesting #QuantitativeFinance""",
        "ES": """📊 El Mercado Se Mueve — ¿Estás Mirando o Actuando?

Cada semana los mercados ofrecen oportunidades.
Cada semana la mayoría de los inversores las deja pasar.

No porque no existan — sino porque no tienen un sistema para encontrarlas.

Robot Trader 2026 monitoriza cada noche:
📈 3.072 acciones en 23 mercados globales
📦 678 ETFs con Sharpe y rendimiento 1Y
🏦 1.087 fondos de inversión con criterios cuantitativos

¿El resultado? Una lista ordenada por score — cada mañana a las 07:00.

El mercado no espera. ¿Tienes un sistema?

#TendenciaMercado #ValueInvesting #FinanzaCuantitativa""",
        "EN": """📊 Markets Are Moving — Are You Watching or Acting?

Every week markets offer opportunities.
Every week most investors let them pass.

Not because they don't exist — but because they have no system to find them.

Robot Trader 2026 monitors every night:
📈 3,072 stocks across 23 global markets
📦 678 ETFs with Sharpe ratio and 1Y performance
🏦 1,087 mutual funds with quantitative criteria

The result? A ranked list by score — every morning at 07:00.

Markets don't wait. Do you have a system?

#MarketTrends #ValueInvesting #QuantitativeFinance""",
    },
}

# Tema → prompt Claude (per generazione AI)
CLAUDE_PROMPTS: dict[str, str] = {
    "VALUE_INTRO":      "value investing quantitativo — introduzione ai 5 filtri EV/FCF, P/B, ROE, ND/EBITDA, Score",
    "5_FILTRI":         "spiegazione dettagliata dei 5 filtri usati dallo screener Robot Trader 2026",
    "EVFCF":            "EV/FCF ratio — perché è il filtro più importante nel value investing",
    "PB_ROE":           "combinazione P/B e ROE — come identificare aziende solide a sconto",
    "CASE_STUDY":       "come funziona lo screener Robot Trader 2026 — esempio concreto con dati reali",
    "ETF_SCREENING":    "screening ETF — criteri TER, Sharpe, Volume, replica fisica, accumulazione",
    "TEAM":             "team Fuerte Venture Capital — esperienza e mission dietro Robot Trader 2026",
    "LAUNCH":           "lancio Robot Trader 2026 — piani BASIC/PRO/VALUE e come iniziare",
    "FONDI_SCREENING":  "screening fondi comuni — 1087 fondi, 36 famiglie, criteri filtro",
    "SALARY_TRAP":      "lo stipendio perde valore senza investimento — invito ad agire con Robot Trader 2026",
    "WEALTHOS_PROMO":   "WealthOS — patrimonio netto aggregato, dashboard personale, integrazione RT2026",
    "TREND_MOBILIARE":  "trend di mercato settimanale — il sistema RT2026 trova opportunità che altri perdono",
}

SYSTEM_PROMPT = """Sei il content creator di Fuerte Venture Capital SL, una società di investimento spagnola.
Crei post LinkedIn/social per Robot Trader 2026, uno screener quantitativo di value investing.

TONO: Professionale, credibile, educativo. Mai hype. Mai promesse di rendimento.
FORMATO: Testo diretto, max 300 parole, 3-5 hashtag rilevanti, call-to-action semplice.
EMOJI: Massimo 2, solo se aggiungono valore.
IMPORTANTE: Rispondi SOLO con il testo del post, senza prefissi o spiegazioni."""


def generate_post(theme: str, lang: str = "IT") -> str:
    """
    Genera testo post per il tema e la lingua specificati.
    Prova prima Claude API, poi fallback al template statico.
    """
    lang = lang.upper()

    # Prova Claude API
    api_key = _anthropic_key()
    if api_key:
        try:
            text = _call_claude(theme, lang, api_key)
            if text:
                print(f"[ContentGen] Generato via Claude API — {theme} {lang}")
                return text
        except Exception as e:
            print(f"[ContentGen] Claude API errore: {e} — uso template statico")

    # Fallback template statico
    tpl = TEMPLATES.get(theme, {}).get(lang)
    if tpl:
        print(f"[ContentGen] Template statico — {theme} {lang}")
        return tpl

    # Ultimo fallback: primo template disponibile nella lingua
    tpl_any = TEMPLATES.get(theme, {})
    if tpl_any:
        first = next(iter(tpl_any.values()))
        print(f"[ContentGen] Template statico (lingua alternativa) — {theme}")
        return first

    return f"[Robot Trader 2026] Aggiornamento {theme} — {datetime.now().strftime('%d/%m/%Y')}"


def _call_claude(theme: str, lang: str, api_key: str) -> Optional[str]:
    """Chiama Claude API via HTTP per generare il post."""
    tema_desc   = CLAUDE_PROMPTS.get(theme, theme)
    lingua_desc = "italiano" if lang == "IT" else ("spagnolo" if lang == "ES" else "inglese")
    user_prompt = (
        f"Crea un post LinkedIn in {lingua_desc} su questo tema:\n\n"
        f"TEMA: {tema_desc}\n\n"
        f"PRODOTTO: Robot Trader 2026 — screener value investing automatico\n"
        f"AUDIENCE: Investitori retail, imprenditori, professionisti finanziari\n"
        f"CTA: Invita a scoprire https://trader.fuerteventurecapital.com o a commentare\n\n"
        f"Scrivi SOLO il testo del post, pronto per la pubblicazione."
    )
    headers = {
        "x-api-key":         api_key,
        "anthropic-version": "2023-06-01",
        "content-type":      "application/json",
    }
    payload = {
        "model":      CLAUDE_MODEL,
        "max_tokens": 600,
        "system":     SYSTEM_PROMPT,
        "messages":   [{"role": "user", "content": user_prompt}],
    }
    r = requests.post(ANTHROPIC_API_URL, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data["content"][0]["text"].strip()


def get_available_themes() -> list[str]:
    return list(TEMPLATES.keys())
