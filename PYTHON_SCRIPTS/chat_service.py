# -*- coding: utf-8 -*-
"""
Chatbot AI — Robot Trader 2026
Usa Claude Haiku con prompt caching sulla Knowledge Base.
"""

import os
import json
import time
import uuid
import threading
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_DIR   = os.path.join(BASE_DIR, "KNOWLEDGE_BASE")

RATE_LIMIT  = 30   # messaggi max per IP per ora
MAX_HISTORY = 10   # messaggi conservati per sessione (5 turni)
MAX_MSG_LEN = 600  # caratteri max per messaggio utente

_lock = threading.Lock()

# ─── Conteggi universo ticker (dinamici, da file sorgente) ────────────────────

def _load_universe_counts() -> dict:
    """Legge i conteggi reali dall'universo ticker (stessa logica di email_notifier.py)."""
    c = {}
    try:
        import sys as _sys; _sys.path.insert(0, BASE_DIR)
        from ticker_lists_5000 import ALL_AZIONI, ALL_ETF, ALL_FONDI
        c['azioni'] = len(ALL_AZIONI)
        etf_set = set(ALL_ETF)
        _cache_etf = os.path.join(BASE_DIR, 'etf_universe_cache.json')
        if os.path.exists(_cache_etf):
            with open(_cache_etf, encoding='utf-8') as f:
                for entry in json.load(f).values():
                    tk = entry.get('preferred_ticker')
                    if tk and not entry.get('error'):
                        etf_set.add(tk)
        c['etf'] = len(etf_set)
        fondi_set = set(ALL_FONDI)
        _cache_eu = os.path.join(BASE_DIR, 'fondi_eu_universe_cache.json')
        if os.path.exists(_cache_eu):
            with open(_cache_eu, encoding='utf-8') as f:
                data_eu = json.load(f)
            for entry in data_eu.values():
                if entry.get('yahoo_ticker'):
                    fondi_set.add(entry['yahoo_ticker'])
            c['fondi_us']  = len(fondi_set)
            c['fondi_eu']  = sum(1 for v in data_eu.values() if v.get('yahoo_ticker'))
        else:
            c['fondi_us'] = len(fondi_set)
            c['fondi_eu'] = 0
    except Exception:
        c = {'azioni': 2625, 'etf': 1182, 'fondi_us': 886, 'fondi_eu': 493}
    c['totale'] = c['azioni'] + c['etf'] + c['fondi_us'] + c['fondi_eu']
    return c

def _fmt_n(n: int) -> str:
    return f"{n:,}".replace(',', '.')

def _apply_counts(text: str, c: dict) -> str:
    """Sostituisce i placeholder {N_AZIONI}, {N_ETF} ecc. con i valori reali."""
    return (text
            .replace('{N_AZIONI}',   _fmt_n(c['azioni']))
            .replace('{N_ETF}',      _fmt_n(c['etf']))
            .replace('{N_FONDI_US}', _fmt_n(c['fondi_us']))
            .replace('{N_FONDI_EU}', _fmt_n(c['fondi_eu']))
            .replace('{N_TOTALE}',   _fmt_n(c['totale'])))

UNIVERSE_COUNTS = _load_universe_counts()

# ─── Caricamento Knowledge Base ───────────────────────────────────────────────

def _load_kb() -> str:
    counts = _load_universe_counts()
    files = ["kb_azienda.md", "kb_prodotto.md", "kb_faq.md", "kb_glossario.md", "kb_profili.md",
             "kb_metriche.md", "kb_educazione_etf.md", "kb_mercati_globali.md",
             "kb_teoria_investimento.md"]
    parts = []
    for fname in files:
        path = os.path.join(KB_DIR, fname)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                parts.append(f.read())
    combined = "\n\n---\n\n".join(parts)
    return _apply_counts(combined, counts)

KB_CONTENT = _load_kb()
_kb_loaded_at = time.strftime("%H:%M:%S")

# ─── Reports KB (chatbot abbonati) ────────────────────────────────────────────

KB_REPORTS_FILE = os.path.join(KB_DIR, "kb_reports.md")

def _load_kb_reports() -> str:
    if os.path.exists(KB_REPORTS_FILE):
        with open(KB_REPORTS_FILE, encoding="utf-8") as f:
            return f.read()
    return ""

KB_REPORTS_CONTENT = _load_kb_reports()

_EXAMPLES = """
ESEMPI DI RISPOSTA IDEALE — seguire questo stile e tono in ogni lingua:

---
ESEMPIO 1 — Raccomandazione piano (IT)
Utente: "Sono un investitore privato alle prime armi, mi interessano le azioni con dividendi alti."
Assistente: "Per chi inizia con focus sui dividendi, il piano **Azioni BASIC** (€29/mese) è la scelta giusta. Analizza centinaia di Blue Chip dei principali indici mondiali (S&P500, DAX, FTSE100, ecc.) con filtri fondamentali accessibili su EV/FCF, P/B e ROE. Lo score privilegia il Dividend Yield e il momentum di breve termine. Se in futuro vuole espandere l'analisi a {N_AZIONI} ticker globali con filtri più selettivi, può passare ad Azioni PRO (€39/mese)."

---
ESEMPIO 2 — Domanda sui prezzi (ES)
Utente: "¿Cuánto cuestan los planes de ETF?"
Assistente: "Los planes ETF tienen tres niveles:\n- **ETF BASIC €29/mes** — Orientado al momentum a corto plazo. Ideal para horizontes de 6–18 meses.\n- **ETF PRO €39/mes** — Equilibrio entre Sharpe Ratio y Rendimiento anual. Gestión activa a medio plazo (3–7 años).\n- **ETF VALUE €59/mes** — Filtros muy exigentes en TER y Sharpe. Ideal para construir patrimonio a 10–30 años.\nTodos los planes analizan {N_ETF} ETFs europeos de acumulación física. ¿Tiene preferencia por algún horizonte temporal?"

---
ESEMPIO 3 — Spiegazione dello Score (EN)
Utente: "What does a score of 75 mean in the report?"
Assistente: "A score of 75 means that instrument outperforms **75% of all other instruments** selected in the same plan's current run. It's a relative percentile ranking — not an absolute quality grade. So score 75 is solid, but always compare instruments within the same plan and the same run date. The score recalculates every night (Mon–Fri) as market data changes."

---
ESEMPIO 4 — Domanda fuori tema / consiglio investimento (IT)
Utente: "Mi conviene comprare Tesla adesso?"
Assistente: "Non fornisco consigli di acquisto su singoli titoli — i nostri report sono strumenti informativi e non costituiscono consulenza finanziaria personalizzata (MiFID II). Per verificare se Tesla compare nei nostri screener Azioni PRO o VALUE, acceda all'area clienti su www.fuerteventurecapital.com o scriva a marketing@fuerteventurecapital.com."

---
ESEMPIO 5 — Obiezione prezzo (FR)
Utente: "C'est trop cher, 59€ par mois pour des données disponibles gratuitement en ligne."
Assistente: "La différence n'est pas dans les données brutes — c'est dans l'analyse : Robot Trader 2026 filtre chaque soir plus de **{N_TOTALE} instruments financiers** (actions, ETF, fonds US et EU) avec des filtres fondamentaux rigoureux et un score percentile, vous livrant directement les 20–50 meilleurs de votre plan. Pour commencer, le plan **BASIC à €29/mois** offre une excellente base. Vous pouvez évaluer la valeur du service et upgrader ensuite."

---
ESEMPIO 6 — Password dimenticata (DE)
Utente: "Ich habe mein Passwort vergessen."
Assistente: "Kein Problem! Schreiben Sie bitte eine E-Mail an **marketing@fuerteventurecapital.com** und geben Sie dabei Ihre Registrierungs-E-Mail-Adresse an. Unser Team setzt Ihr Passwort manuell innerhalb von 24 Wertstunden zurück."

---
ESEMPIO 7 — Confronto piani (IT)
Utente: "Qual è la differenza tra Azioni PRO e Azioni VALUE?"
Assistente: "Entrambi analizzano {N_AZIONI} ticker su 23 mercati globali, ma i filtri e l'orizzonte temporale differiscono:\n\n**Azioni PRO €39/mese** — Filtri fondamentali bilanciati su EV/FCF, P/B e ROE. Lo score privilegia la generazione di cassa e l'efficienza del capitale. Ideale per analisi fondamentale attiva, orizzonte 2–5 anni.\n\n**Azioni VALUE €59/mese** — Filtri fondamentali molto più rigidi — lista estremamente concentrata. Lo score è dominato dalle metriche di valore a lungo termine. Include fogli 'Scartati' e 'Non Validi' per analisi completa. Per deep value investor con orizzonte 5–15 anni.\n\nSe ha esperienza in analisi fondamentale e orizzonte lungo, VALUE è più completo. Se preferisce un approccio più flessibile, PRO è ottimale."

---
ESEMPIO 8 — Fondi EU (EN)
Utente: "What's the difference between US Funds and EU UCITS Funds plans?"
Assistente: "Both cover mutual funds but different universes:\n\n**US Funds** — {N_FONDI_US} funds from 45 American fund families (Vanguard, Fidelity, T.Rowe Price, PIMCO, DFA, etc.). Filters use Volume as liquidity proxy.\n\n**EU UCITS Funds** — {N_FONDI_EU} European UCITS-regulated funds. Filters use AUM (Assets Under Management) as the liquidity measure. UCITS regulation ensures EU-wide distribution standards.\n\nFor European investors, EU UCITS funds are generally easier to access through local banks and brokers. Both categories are available in BASIC/PRO/VALUE plans at €29/39/59 per month."
---
"""

_EXAMPLES_ABB = """
ESEMPI DI RISPOSTA — CHATBOT ABBONATI:

---
ESEMPIO 1 — Ticker nel report (IT)
Utente: "LLY è nel report Azioni PRO di oggi?"
Assistente: "Sì, **LLY (Eli Lilly)** è presente nell'ultimo report Azioni PRO con **Score 82** (supera l'82% dei titoli analizzati). Metriche chiave: EV/FCF 28.4x, P/B 44.2x, ROE 78.3%. — *Dato statistico, non consiglio di investimento.*"

---
ESEMPIO 2 — Ticker scartato (IT)
Utente: "Perché TSLA non è nel report Azioni VALUE?"
Assistente: "**TSLA (Tesla Inc)** risulta nei Scartati del piano Azioni VALUE. Motivo: EV/FCF troppo alto rispetto alla soglia richiesta dal piano. — *Questo è un dato di screening, non un giudizio sulla qualità dell'azienda.*"

---
ESEMPIO 3 — Statistiche generali (EN)
Utente: "How many stocks passed the PRO filter today?"
Assistente: "In the latest Azioni PRO run, **47 instruments** appear in the 'Selezionati' sheet out of {N_AZIONI} analyzed. Top scorer reached Score 97. For ETF PRO: 38 instruments selected. — *Statistical data only, not investment advice.*"

---
ESEMPIO 4 — Consiglio acquisto (IT)
Utente: "Mi conviene comprare LLY?"
Assistente: "Non posso darti consigli di acquisto (MiFID II). Posso dirti che **LLY ha Score 82** nell'ultimo report Azioni PRO, il che significa che supera l'82% dei titoli analizzati in quel piano. La decisione di investimento è esclusivamente tua."
---
"""

# Applica i conteggi reali ai placeholder degli esempi al momento del caricamento
_EXAMPLES     = _apply_counts(_EXAMPLES,     UNIVERSE_COUNTS)
_EXAMPLES_ABB = _apply_counts(_EXAMPLES_ABB, UNIVERSE_COUNTS)

SYSTEM_PROMPT_ABBONATI_BASE = """Sei l'assistente RISERVATO AGLI ABBONATI di Robot Trader 2026 (Fuerte Venture Capital SL).
Hai accesso ai dati degli ultimi report degli screener e puoi fornire informazioni statistiche su titoli specifici.

REGOLE:
1. Rispondi SEMPRE nella lingua dell'utente — IT, ES, EN, FR, DE e qualsiasi altra lingua.
2. Sii conciso (preferibilmente sotto 200 parole). Per dati numerici usa tabelle compatte.
3. Non fare MAI promesse di rendimento né garantire risultati — sei soggetto a normativa MiFID II.
4. Puoi fornire DATI dai report (score, metriche, presenza/assenza nei piani) ma NON dare mai consigli di acquisto/vendita.
5. Quando fornisci dati su un ticker, aggiungi SEMPRE: "*Dato statistico — non consiglio di investimento.*"
6. Se un ticker non è nei dati disponibili, dillo chiaramente e suggerisci di consultare il report completo.
7. Tono: professionale, preciso con i numeri. Usa **grassetto** per ticker e score.
8. Per domande sui piani, prezzi o accesso, rispondi normalmente usando la knowledge base.

"""

SYSTEM_PROMPT = """Sei l'assistente virtuale di Fuerte Venture Capital SL per il servizio Robot Trader 2026.
Il tuo compito è rispondere in modo chiaro, professionale e conciso alle domande degli utenti.

REGOLE:
1. Rispondi SEMPRE nella lingua dell'utente — rileva automaticamente: IT, ES, EN, FR, DE e qualsiasi altra lingua.
2. Sii conciso (preferibilmente sotto 150 parole), MA se la domanda richiede di elencare piani o prodotti, completa SEMPRE la risposta senza tagliarla.
3. Non fare MAI promesse di rendimento né garantire risultati — sei soggetto a normativa MiFID II.
4. Non inventare informazioni: usa SOLO ciò che trovi nella knowledge base qui sotto.
5. Per domande su singoli titoli ("conviene comprare X?") non fornire consigli — rimanda a marketing@fuerteventurecapital.com.
6. Se la domanda è fuori tema o non sai rispondere, indirizza sempre a marketing@fuerteventurecapital.com.
7. Tono: professionale, diretto, amichevole. Usa il **grassetto** per prezzi e nomi di piani.
8. Quando suggerisci un piano, basa il consiglio sul profilo dell'investitore (orizzonte temporale, asset class preferita, livello di esperienza).

""" + _EXAMPLES + """
KNOWLEDGE BASE:
""" + KB_CONTENT

# ─── Stato in memoria ─────────────────────────────────────────────────────────

CHAT_SESSIONS: dict = {}   # session_id -> [{"role": ..., "content": ...}]
CHAT_RATE:     dict = {}   # ip -> [timestamps]

SESSION_TTL = 24 * 3600    # sessioni scadono dopo 24h di inattività

# Sessioni separate per abbonati (area clienti)
CHAT_SESSIONS_ABB: dict = {}
CHAT_RATE_ABB:     dict = {}
_session_ts_abb:   dict = {}


def cleanup_expired_sessions():
    """Rimuove sessioni e rate-limit entries scaduti. Chiamare periodicamente."""
    now = time.time()
    with _lock:
        # Rimuovi sessioni vecchie: le sessioni sono liste; usiamo un dizionario
        # separato per i timestamp di creazione
        for sid in list(CHAT_SESSIONS.keys()):
            ts = _session_ts.get(sid, 0)
            if now - ts > SESSION_TTL:
                CHAT_SESSIONS.pop(sid, None)
                _session_ts.pop(sid, None)
        # Rimuovi entry rate-limit senza timestamp recenti
        for ip in list(CHAT_RATE.keys()):
            CHAT_RATE[ip] = [t for t in CHAT_RATE[ip] if now - t < 3600]
            if not CHAT_RATE[ip]:
                CHAT_RATE.pop(ip)

# ─── Funzioni pubbliche ───────────────────────────────────────────────────────

def chat(message: str, session_id: str, ip: str, api_key: str) -> dict:
    if not api_key:
        return {"ok": False, "error": "Chatbot non disponibile (servizio non configurato)."}

    message = message.strip()[:MAX_MSG_LEN]
    if not message:
        return {"ok": False, "error": "Messaggio vuoto."}

    with _lock:
        if not _check_rate(ip):
            return {"ok": False, "error": "Troppi messaggi. Riprova tra qualche minuto."}
        session_id = _get_or_create_session(session_id)
        history = list(CHAT_SESSIONS[session_id])   # copia locale

    history.append({"role": "user", "content": message})
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]

    try:
        reply = _call_claude(history, api_key)
    except Exception as e:
        return {"ok": False, "error": "Errore temporaneo. Riprova.", "detail": str(e)}

    history.append({"role": "assistant", "content": reply})
    with _lock:
        CHAT_SESSIONS[session_id] = history

    return {"ok": True, "reply": reply, "session_id": session_id}


def chat_abbonati(message: str, session_id: str, ip: str, api_key: str,
                  client_nome: str = '', piani_attivi: dict = None) -> dict:
    """Chatbot per abbonati: accede ai dati dei report oltre alla KB standard."""
    if not api_key:
        return {"ok": False, "error": "Chatbot non disponibile (servizio non configurato)."}

    message = message.strip()[:MAX_MSG_LEN]
    if not message:
        return {"ok": False, "error": "Messaggio vuoto."}

    with _lock:
        if not _check_rate_abb(ip):
            return {"ok": False, "error": "Troppi messaggi. Riprova tra qualche minuto."}
        session_id = _get_or_create_session_abb(session_id)
        history = list(CHAT_SESSIONS_ABB[session_id])

    # Inject client context into first message of the session (keeps system prompt cacheable)
    if not history and (client_nome or piani_attivi):
        ctx = f"[Abbonato: {client_nome}"
        if piani_attivi:
            active = [f"{k.upper()} {v}" for k, v in piani_attivi.items()
                      if v and v not in ('NONE', 'none')]
            if active:
                ctx += f" | Piani attivi: {', '.join(active)}"
        ctx += f"]\n{message}"
        history.append({"role": "user", "content": ctx})
    else:
        history.append({"role": "user", "content": message})

    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]

    try:
        reply = _call_claude_abb(history, api_key)
    except Exception as e:
        return {"ok": False, "error": "Errore temporaneo. Riprova.", "detail": str(e)}

    history.append({"role": "assistant", "content": reply})
    with _lock:
        CHAT_SESSIONS_ABB[session_id] = history

    return {"ok": True, "reply": reply, "session_id": session_id}


def reload_kb():
    """Ricarica la knowledge base da disco (usa per aggiornamenti live)."""
    global KB_CONTENT, KB_REPORTS_CONTENT, SYSTEM_PROMPT, UNIVERSE_COUNTS, _kb_loaded_at
    UNIVERSE_COUNTS    = _load_universe_counts()
    KB_CONTENT         = _load_kb()          # _load_kb() chiama _load_universe_counts() internamente
    KB_REPORTS_CONTENT = _load_kb_reports()
    _kb_loaded_at      = time.strftime("%H:%M:%S")
    # Ricostruisce SYSTEM_PROMPT con esempi aggiornati e nuova KB
    fresh_examples = _apply_counts(_EXAMPLES, UNIVERSE_COUNTS)
    SYSTEM_PROMPT = SYSTEM_PROMPT.split("ESEMPI DI RISPOSTA", 1)[0] + fresh_examples + "\nKNOWLEDGE BASE:\n" + KB_CONTENT


def get_kb_info() -> dict:
    """Ritorna info sulla KB caricata (per la dashboard admin)."""
    files = [f for f in ["kb_azienda.md", "kb_prodotto.md", "kb_faq.md", "kb_glossario.md", "kb_profili.md"]
             if os.path.exists(os.path.join(KB_DIR, f))]
    has_reports = bool(KB_REPORTS_CONTENT)
    return {
        "chars":       len(KB_CONTENT),
        "chars_total": len(KB_CONTENT) + len(KB_REPORTS_CONTENT),
        "files":       len(files) + (1 if has_reports else 0),
        "has_reports": has_reports,
        "loaded_at":   _kb_loaded_at,
    }


# ─── Helpers interni ──────────────────────────────────────────────────────────

def _check_rate(ip: str) -> bool:
    now = time.time()
    ts  = [t for t in CHAT_RATE.get(ip, []) if now - t < 3600]
    if len(ts) >= RATE_LIMIT:
        return False
    ts.append(now)
    CHAT_RATE[ip] = ts
    return True


_session_ts: dict = {}     # session_id -> timestamp ultima attività


def _get_or_create_session(session_id: str) -> str:
    now = time.time()
    if session_id and session_id in CHAT_SESSIONS:
        _session_ts[session_id] = now
        return session_id
    new_id = str(uuid.uuid4())
    CHAT_SESSIONS[new_id] = []
    _session_ts[new_id] = now
    return new_id


def _check_rate_abb(ip: str) -> bool:
    now = time.time()
    ts  = [t for t in CHAT_RATE_ABB.get(ip, []) if now - t < 3600]
    if len(ts) >= RATE_LIMIT:
        return False
    ts.append(now)
    CHAT_RATE_ABB[ip] = ts
    return True


def _get_or_create_session_abb(session_id: str) -> str:
    now = time.time()
    if session_id and session_id in CHAT_SESSIONS_ABB:
        _session_ts_abb[session_id] = now
        return session_id
    new_id = str(uuid.uuid4())
    CHAT_SESSIONS_ABB[new_id] = []
    _session_ts_abb[new_id] = now
    return new_id


def _call_claude(history: list, api_key: str) -> str:
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 800,
        "system": [
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": history,
    }
    data = json.dumps(payload).encode("utf-8")
    req  = Request(
        "https://api.anthropic.com/v1/messages",
        data=data,
        headers={
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta":    "prompt-caching-2024-07-31",
            "content-type":      "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body[:200]}")
    except URLError as e:
        raise RuntimeError(f"Network error: {e.reason}")

    return result["content"][0]["text"].strip()


def _call_claude_abb(history: list, api_key: str) -> str:
    """Chiama Claude per il chatbot abbonati — sistema prompt con KB + report data."""
    fixed_system = (
        SYSTEM_PROMPT_ABBONATI_BASE +
        _EXAMPLES_ABB +
        "\n\nKNOWLEDGE BASE GENERALE:\n" + KB_CONTENT +
        "\n\n---\n\nREPORT DATA (ultima elaborazione):\n" +
        (KB_REPORTS_CONTENT if KB_REPORTS_CONTENT else
         "*Report non ancora disponibili. Verranno caricati dopo la prima elaborazione notturna.*")
    )
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1000,
        "system": [
            {
                "type": "text",
                "text": fixed_system,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": history,
    }
    data = json.dumps(payload).encode("utf-8")
    req  = Request(
        "https://api.anthropic.com/v1/messages",
        data=data,
        headers={
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta":    "prompt-caching-2024-07-31",
            "content-type":      "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body[:200]}")
    except URLError as e:
        raise RuntimeError(f"Network error: {e.reason}")

    return result["content"][0]["text"].strip()
