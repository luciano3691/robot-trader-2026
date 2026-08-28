"""
CampagnaAgent — Robot Trader 2026 / Fuerte Venture Capital
Agente intelligente per gestione campagna email + social.

4 strati Knowledge Base:
  1. strategic    — intenzione umana (solo lettura per agente)
  2. empirical    — dati appresi da Brevo (agente scrive ogni 08:45)
  3. market_ctx   — contesto mercato da Yahoo Finance (VIX proxy)
  4. content_evo  — loop Claude → A/B test → vincitori

Escalation a umano:
  - open_rate < soglia per N giorni → PAUSA + ALERT
  - unsub > soglia giornaliera → PAUSA IMMEDIATA
  - prospect clicca → notifica personale
  - fine mese → proposte per mese successivo (richiedono approvazione)
"""

import json
import os
import time
import requests
from datetime import datetime, timedelta, date
from typing import Optional

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
KB_FILE         = os.path.join(BASE_DIR, 'campagna_knowledge.json')
KPI_FILE        = os.path.join(BASE_DIR, 'campagna_kpi.json')
SUGGESTIONS_FILE= os.path.join(BASE_DIR, 'campagna_suggestions.json')

BREVO_API_URL   = 'https://api.brevo.com/v3'
ANTHROPIC_URL   = 'https://api.anthropic.com/v1/messages'
CLAUDE_MODEL    = 'claude-opus-4-7'

# ── Mapping paese → lingua ────────────────────────────────────────────────────
PAESE_LANG = {
    'IT': 'IT', 'ITA': 'IT', 'ITALIA': 'IT', 'ITALY': 'IT',
    'ES': 'ES', 'ESP': 'ES', 'SPAGNA': 'ES', 'SPAIN': 'ES',
    'MX': 'ES', 'MEX': 'ES', 'MESSICO': 'ES', 'MEXICO': 'ES',
    'AR': 'ES', 'ARG': 'ES', 'ARGENTINA': 'ES',
    'CO': 'ES', 'COLOMBIA': 'ES',
    'DE': 'DE', 'DEU': 'DE', 'GERMANIA': 'DE', 'GERMANY': 'DE',
    'AT': 'DE', 'AUT': 'DE', 'AUSTRIA': 'DE',
    'CH': 'DE', 'CHE': 'DE', 'SVIZZERA': 'DE',
    'FR': 'FR', 'FRA': 'FR', 'FRANCIA': 'FR', 'FRANCE': 'FR',
    'BE': 'FR', 'BEL': 'FR', 'BELGIO': 'FR',
    'GB': 'EN', 'GBR': 'EN', 'UK': 'EN',
    'US': 'EN', 'USA': 'EN',
    'AU': 'EN', 'AUS': 'EN',
    'NL': 'EN', 'PT': 'ES',
}


def _brevo_key() -> str:
    return os.getenv('BREVO_API_KEY', '')


def _anthropic_key() -> str:
    return os.getenv('ANTHROPIC_API_KEY', '')


# ── Knowledge Base I/O ────────────────────────────────────────────────────────

def _load_kb() -> dict:
    if os.path.exists(KB_FILE):
        with open(KB_FILE, encoding='utf-8') as f:
            return json.load(f)
    return _default_kb()


def _save_kb(kb: dict):
    tmp = KB_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(kb, f, indent=2, ensure_ascii=False)
    os.replace(tmp, KB_FILE)


def _default_kb() -> dict:
    return {
        'strategic': {
            'priorita_temi': ['SALARY_TRAP', 'WEALTHOS_PROMO', 'TREND_MOBILIARE'],
            'mercati_target': ['IT', 'ES', 'EN'],
            'obiettivi': 'Conversioni RT2026 + WealthOS awareness Q4 2026',
            'note': '',
            'soglie': {
                'open_rate_minimo': 0.15,
                'click_rate_minimo': 0.02,
                'unsub_allarme_giornaliero': 10,
                'giorni_consecutivi_sotto_soglia': 3
            }
        },
        'empirical': {
            'tema_stats': {},
            'subject_stats': {},
            'timing': {
                'monday': [], 'tuesday': [], 'wednesday': [], 'thursday': [],
                'friday': [], 'saturday': [], 'sunday': []
            },
            'segment_preferences': {
                'new':    'PAIN_HOOK',
                'opener': 'SOLUTION',
                'clicker':'CTA',
                'cold':   'SOCIAL_PROOF'
            },
            'giorni_consecutivi_sotto_soglia': 0,
            'campagna_in_pausa': False
        },
        'market_context': {
            'ultimo_aggiornamento': None,
            'trend': 'neutro',
            'vix_proxy': None,
            'tema_suggerito': None,
            'note': ''
        },
        'content_evolution': {
            'variants': {},
            'test_attivi': [],
            'test_conclusi': []
        },
        'insights': [],
        'alerts': [],
        'human_feedback': {}
    }


def _load_kpi() -> list:
    if os.path.exists(KPI_FILE):
        with open(KPI_FILE, encoding='utf-8') as f:
            return json.load(f)
    return []


def _save_kpi(data: list):
    tmp = KPI_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, KPI_FILE)


def _load_suggestions() -> list:
    if os.path.exists(SUGGESTIONS_FILE):
        with open(SUGGESTIONS_FILE, encoding='utf-8') as f:
            return json.load(f)
    return []


def _save_suggestions(data: list):
    tmp = SUGGESTIONS_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, SUGGESTIONS_FILE)


# ── Brevo API ─────────────────────────────────────────────────────────────────

def _brevo_get(path: str, params: dict = None) -> dict:
    headers = {'api-key': _brevo_key(), 'Accept': 'application/json'}
    r = requests.get(f'{BREVO_API_URL}{path}', headers=headers, params=params or {}, timeout=15)
    if r.status_code == 200:
        return r.json()
    return {}


def fetch_yesterday_stats() -> dict:
    """Statistiche aggregate Brevo per ieri."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    data = _brevo_get('/smtp/statistics/reports', {
        'startDate': yesterday,
        'endDate':   yesterday,
        'limit':     1
    })
    reports = data.get('reports', [])
    if not reports:
        return {'sent': 0, 'opened': 0, 'clicked': 0, 'unsubscribed': 0,
                'open_rate': 0.0, 'click_rate': 0.0}
    r = reports[0]
    sent      = r.get('requests', 0)
    opened    = r.get('uniqueOpens', 0)
    clicked   = r.get('uniqueClicks', 0)
    unsubbed  = r.get('unsubscriptions', 0)
    return {
        'sent':         sent,
        'opened':       opened,
        'clicked':      clicked,
        'unsubscribed': unsubbed,
        'open_rate':    round(opened / sent, 4) if sent > 0 else 0.0,
        'click_rate':   round(clicked / sent, 4) if sent > 0 else 0.0,
        'date':         yesterday
    }


def fetch_yesterday_events() -> dict:
    """Email che hanno aperto / cliccato ieri (Brevo events API)."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    openers   = set()
    clickers  = set()
    unsubs    = set()

    for event, target_set in [('opened', openers), ('clicks', clickers),
                               ('unsubscribed', unsubs)]:
        offset = 0
        while True:
            data = _brevo_get('/smtp/statistics/events', {
                'startDate': yesterday,
                'endDate':   yesterday,
                'event':     event,
                'limit':     100,
                'offset':    offset
            })
            events = data.get('events', [])
            for e in events:
                email = e.get('email', '').lower().strip()
                if email:
                    target_set.add(email)
            if len(events) < 100:
                break
            offset += 100

    return {
        'openers':  openers,
        'clickers': clickers,
        'unsubs':   unsubs
    }


# ── Market Context ─────────────────────────────────────────────────────────────

def update_market_context(kb: dict):
    """
    Usa S&P500 come proxy per sentiment di mercato.
    Yahoo Finance v8 — nessuna API key richiesta.
    """
    try:
        url = 'https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC'
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10,
                         params={'interval': '1d', 'range': '5d'})
        data = r.json()
        closes = data['chart']['result'][0]['indicators']['quote'][0]['close']
        closes = [c for c in closes if c is not None]
        if len(closes) >= 2:
            change_pct = (closes[-1] - closes[-2]) / closes[-2] * 100
            if change_pct < -1.5:
                trend = 'ribassista'
                tema_suggerito = 'SALARY_TRAP'  # paura funziona
            elif change_pct > 1.5:
                trend = 'rialzista'
                tema_suggerito = 'WEALTHOS_PROMO'  # chi guadagna vuole gestire
            else:
                trend = 'neutro'
                tema_suggerito = None

            kb['market_context'].update({
                'ultimo_aggiornamento': datetime.now().isoformat(),
                'trend':           trend,
                'change_pct_1d':   round(change_pct, 2),
                'sp500_last':      round(closes[-1], 2),
                'tema_suggerito':  tema_suggerito,
            })
    except Exception as e:
        print(f'[Agent] market_context errore: {e}')


# ── Prospect Language ─────────────────────────────────────────────────────────

def lang_for_prospect(prospect: dict, default_lang: str) -> str:
    """Determina la lingua dall'attributo paese del prospect."""
    paese = (prospect.get('paese') or '').upper().strip()
    return PAESE_LANG.get(paese, default_lang)


# ── Empirical Updates ─────────────────────────────────────────────────────────

def update_empirical(kb: dict, stats: dict, tema: str, lang: str, subject: str):
    """Aggiorna statistiche empiriche nella KB con i risultati di ieri."""
    emp = kb['empirical']

    # tema_stats
    ts = emp.setdefault('tema_stats', {}).setdefault(tema, {}).setdefault(lang, {
        'open_rate_sum': 0.0, 'click_rate_sum': 0.0, 'giorni': 0, 'sent_totale': 0
    })
    if stats['sent'] > 0:
        ts['open_rate_sum']  += stats['open_rate']
        ts['click_rate_sum'] += stats['click_rate']
        ts['giorni']         += 1
        ts['sent_totale']    += stats['sent']
        ts['open_rate_avg']   = round(ts['open_rate_sum'] / ts['giorni'], 4)
        ts['click_rate_avg']  = round(ts['click_rate_sum'] / ts['giorni'], 4)

    # subject_stats
    ss = emp.setdefault('subject_stats', {}).setdefault(subject, {
        'sent': 0, 'opened': 0, 'clicked': 0
    })
    ss['sent']    += stats['sent']
    ss['opened']  += stats['opened']
    ss['clicked'] += stats['clicked']
    if ss['sent'] > 0:
        ss['open_rate']  = round(ss['opened'] / ss['sent'], 4)
        ss['click_rate'] = round(ss['clicked'] / ss['sent'], 4)

    # timing (giorno settimana)
    ieri = (date.today() - timedelta(days=1))
    giorno_nome = ieri.strftime('%A').lower()
    day_list = emp['timing'].setdefault(giorno_nome, [])
    if stats['sent'] > 0:
        day_list.append(stats['open_rate'])
        if len(day_list) > 30:
            day_list.pop(0)

    # soglia consecutiva
    soglia = kb['strategic']['soglie']['open_rate_minimo']
    if stats['sent'] > 0 and stats['open_rate'] < soglia:
        emp['giorni_consecutivi_sotto_soglia'] = emp.get('giorni_consecutivi_sotto_soglia', 0) + 1
    else:
        emp['giorni_consecutivi_sotto_soglia'] = 0


# ── Decisione Soggetto ────────────────────────────────────────────────────────

def decide_subject(kb: dict, giorno: dict) -> str:
    """
    Sceglie il soggetto per oggi.
    Se ci sono varianti A/B attive, ruota tra loro.
    Altrimenti usa il soggetto del calendario.
    """
    tema    = giorno.get('tema', '')
    default = giorno.get('soggetto', '')

    # Cerca varianti A/B attive per questo tema
    test_attivi = kb['content_evolution'].get('test_attivi', [])
    for test in test_attivi:
        if test.get('tema') == tema and test.get('stato') == 'in_corso':
            varianti = test.get('varianti', [])
            if varianti:
                # Sceglie la variante con meno invii (bilanciamento)
                variante = min(varianti, key=lambda v: v.get('invii', 0))
                variante['invii'] = variante.get('invii', 0) + 1
                return variante['soggetto']

    return default


# ── Escalation Checks ─────────────────────────────────────────────────────────

def check_escalations(kb: dict, stats: dict) -> list:
    """Ritorna lista di alert/escalation da segnalare nella dashboard."""
    alerts = []
    soglie = kb['strategic']['soglie']

    # Open rate sotto soglia per N giorni
    n_sotto = kb['empirical'].get('giorni_consecutivi_sotto_soglia', 0)
    n_max   = soglie.get('giorni_consecutivi_sotto_soglia', 3)
    if n_sotto >= n_max and stats.get('sent', 0) > 0:
        alerts.append({
            'tipo':     'CRITICO',
            'codice':   'OPEN_RATE_BASSO',
            'msg':      f'Open rate sotto {soglie["open_rate_minimo"]*100:.0f}% per {n_sotto} giorni consecutivi',
            'azione':   'Considera pausa campagna o cambio tema/soggetto',
            'data':     datetime.now().isoformat(),
            'richiede_umano': True
        })

    # Unsub anomali
    if stats.get('unsubscribed', 0) >= soglie.get('unsub_allarme_giornaliero', 10):
        alerts.append({
            'tipo':     'CRITICO',
            'codice':   'UNSUB_ANOMALO',
            'msg':      f'{stats["unsubscribed"]} disiscrizioni in un giorno',
            'azione':   'PAUSA IMMEDIATA + verifica contenuto',
            'data':     datetime.now().isoformat(),
            'richiede_umano': True
        })

    return alerts


# ── Content Evolution — Genera Nuove Varianti ─────────────────────────────────

def generate_new_variants(kb: dict, tema: str, lang: str):
    """
    Se abbiamo abbastanza dati (sample > 200), chiede a Claude
    di generare 3 nuovi soggetti basati sui vincitori storici.
    Inserisce un A/B test nella KB.
    """
    api_key = _anthropic_key()
    if not api_key:
        return

    # Raccoglie top 3 e bottom 3 soggetti con sample > 50
    ss = kb['empirical'].get('subject_stats', {})
    candidati = [(s, d) for s, d in ss.items() if d.get('sent', 0) > 50]
    if len(candidati) < 3:
        return  # non abbastanza dati

    top3    = sorted(candidati, key=lambda x: x[1].get('open_rate', 0), reverse=True)[:3]
    bottom3 = sorted(candidati, key=lambda x: x[1].get('open_rate', 0))[:3]

    vincitori  = '\n'.join(f'- "{s}" (open rate {d["open_rate"]*100:.1f}%)' for s, d in top3)
    perdenti   = '\n'.join(f'- "{s}" (open rate {d["open_rate"]*100:.1f}%)' for s, d in bottom3)
    lingua_map = {'IT': 'italiano', 'ES': 'spagnolo', 'EN': 'inglese',
                  'FR': 'francese', 'DE': 'tedesco'}
    lingua     = lingua_map.get(lang.upper(), 'italiano')

    prompt = (
        f"Sei il copywriter di Fuerte Venture Capital SL.\n"
        f"Stiamo inviando email di campagna sul tema: {tema}\n"
        f"Lingua: {lingua}\n\n"
        f"SOGGETTI CHE HANNO FUNZIONATO MEGLIO:\n{vincitori}\n\n"
        f"SOGGETTI CHE HANNO FUNZIONATO MENO:\n{perdenti}\n\n"
        f"Genera ESATTAMENTE 3 nuovi soggetti email (max 60 caratteri ciascuno) "
        f"ispirati ai vincitori. Solo i 3 soggetti, uno per riga, senza numerazione."
    )

    try:
        r = requests.post(
            ANTHROPIC_URL,
            headers={
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json'
            },
            json={
                'model': CLAUDE_MODEL,
                'max_tokens': 200,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=30
        )
        r.raise_for_status()
        testo = r.json()['content'][0]['text'].strip()
        nuovi = [s.strip() for s in testo.split('\n') if s.strip()][:3]

        if len(nuovi) >= 2:
            test = {
                'id':       f'test_{tema}_{lang}_{date.today().isoformat()}',
                'tema':     tema,
                'lang':     lang,
                'stato':    'in_corso',
                'avviato':  date.today().isoformat(),
                'varianti': [
                    {'soggetto': s, 'invii': 0, 'aperture': 0} for s in nuovi
                ] + [
                    {'soggetto': top3[0][0], 'invii': 0, 'aperture': 0, 'controllo': True}
                ]
            }
            kb['content_evolution']['test_attivi'].append(test)
            kb['insights'].append({
                'data':    date.today().isoformat(),
                'tipo':    'content_evolution',
                'msg':     f'Generati {len(nuovi)} nuovi soggetti per {tema} {lang} via Claude',
                'dettaglio': nuovi
            })
            print(f'[Agent] A/B test avviato per {tema} {lang}: {nuovi}')
    except Exception as e:
        print(f'[Agent] Errore generazione varianti: {e}')


# ── A/B Test Evaluation ────────────────────────────────────────────────────────

def evaluate_ab_tests(kb: dict, openers: set, clickers: set):
    """
    Aggiorna i contatori degli A/B test attivi.
    Se un test ha sample sufficiente (>= 30 invii per variante), dichiara vincitore.
    """
    test_attivi   = kb['content_evolution'].get('test_attivi', [])
    test_conclusi = kb['content_evolution'].get('test_conclusi', [])
    ancora_attivi = []

    for test in test_attivi:
        # Controlla se il test ha abbastanza dati
        min_invii = min(v.get('invii', 0) for v in test['varianti'])
        if min_invii >= 30:
            # Dichiara vincitore
            vincitore = max(
                test['varianti'],
                key=lambda v: v['aperture'] / max(v['invii'], 1)
            )
            test['stato']    = 'concluso'
            test['concluso'] = date.today().isoformat()
            test['vincitore']= vincitore['soggetto']

            # Aggiorna subject_stats con il vincitore come standard
            ss = kb['empirical'].setdefault('subject_stats', {})
            if vincitore['soggetto'] not in ss:
                ss[vincitore['soggetto']] = {'sent': 0, 'opened': 0, 'clicked': 0}

            kb['insights'].append({
                'data':  date.today().isoformat(),
                'tipo':  'ab_test_concluso',
                'msg':   f'Vincitore A/B test {test["tema"]} {test["lang"]}: "{vincitore["soggetto"]}"',
                'open_rate': round(vincitore['aperture'] / max(vincitore['invii'], 1), 4)
            })

            # Aggiunge suggestion per Luciano
            sug = _load_suggestions()
            sug.append({
                'id':       f'sug_{test["id"]}',
                'tipo':     'ab_test_vincitore',
                'data':     date.today().isoformat(),
                'stato':    'in_attesa',
                'msg':      f'A/B test completato: il soggetto "{vincitore["soggetto"]}" '
                            f'vince per {test["tema"]} {test["lang"]}. '
                            f'Vuoi adottarlo come standard?',
                'dati':     test
            })
            _save_suggestions(sug)

            test_conclusi.append(test)
            print(f'[Agent] A/B test concluso: {test["id"]} — vincitore: {vincitore["soggetto"]}')
        else:
            ancora_attivi.append(test)

    kb['content_evolution']['test_attivi']   = ancora_attivi
    kb['content_evolution']['test_conclusi'] = test_conclusi


# ── Prospect State Update ─────────────────────────────────────────────────────

def update_prospect_states(openers: set, clickers: set, unsubs: set):
    """
    Aggiorna stato prospect nel DB in base alle azioni Brevo.
    Clicker → Da Contattare + suggestion per Luciano.
    Unsub → no_email flag.
    """
    if not (openers or clickers or unsubs):
        return

    try:
        import sqlite3
        db_path = os.path.join(BASE_DIR, 'rt2026.db')
        if not os.path.exists(db_path):
            return

        con = sqlite3.connect(db_path)
        cur = con.cursor()

        # Opener → Prospect Attivo (se era Prospect)
        for email in openers - clickers:
            cur.execute(
                "UPDATE prospect SET stato='Prospect Attivo' "
                "WHERE LOWER(email)=? AND stato='Prospect'",
                (email.lower(),)
            )

        # Clicker → Da Contattare + suggestion
        da_contattare = []
        for email in clickers:
            cur.execute(
                "UPDATE prospect SET stato='Da Contattare' "
                "WHERE LOWER(email)=? AND stato NOT IN ('Cliente','Da Contattare')",
                (email.lower(),)
            )
            if cur.rowcount > 0:
                cur.execute("SELECT nome, cognome FROM prospect WHERE LOWER(email)=?",
                            (email.lower(),))
                row = cur.fetchone()
                nome = f"{row[0]} {row[1]}".strip() if row else email
                da_contattare.append({'email': email, 'nome': nome})

        # Unsub → no_email
        for email in unsubs:
            cur.execute(
                "UPDATE prospect SET no_email=1, stato='Inattivo' WHERE LOWER(email)=?",
                (email.lower(),)
            )

        con.commit()
        con.close()

        # Suggestions per clicker
        if da_contattare:
            sug = _load_suggestions()
            sug.append({
                'id':    f'clicker_{date.today().isoformat()}',
                'tipo':  'prospect_clicker',
                'data':  date.today().isoformat(),
                'stato': 'in_attesa',
                'msg':   f'{len(da_contattare)} prospect hanno cliccato oggi — contatto personale consigliato',
                'prospect': da_contattare
            })
            _save_suggestions(sug)
            print(f'[Agent] {len(da_contattare)} clicker → Da Contattare: {[p["email"] for p in da_contattare]}')

    except Exception as e:
        print(f'[Agent] update_prospect_states errore: {e}')


# ── KPI Log ───────────────────────────────────────────────────────────────────

def log_kpi(stats: dict, tema: str, lang: str, subject: str,
            decision_reasoning: str, alerts: list):
    """Aggiunge entry giornaliera al log KPI."""
    kpi = _load_kpi()
    kpi.append({
        'data':       date.today().isoformat(),
        'tema':       tema,
        'lang':       lang,
        'soggetto':   subject,
        'stats':      stats,
        'reasoning':  decision_reasoning,
        'alerts':     alerts,
        'timestamp':  datetime.now().isoformat()
    })
    # Mantieni max 365 giorni
    if len(kpi) > 365:
        kpi = kpi[-365:]
    _save_kpi(kpi)


# ── Weekly Report ─────────────────────────────────────────────────────────────

def generate_weekly_report(kb: dict) -> dict:
    """Genera report settimanale e proposte per la settimana successiva."""
    kpi = _load_kpi()
    ultima_settimana = [
        k for k in kpi
        if (date.today() - date.fromisoformat(k['data'])).days <= 7
    ]

    if not ultima_settimana:
        return {}

    sent_tot    = sum(k['stats']['sent'] for k in ultima_settimana)
    opened_tot  = sum(k['stats']['opened'] for k in ultima_settimana)
    clicked_tot = sum(k['stats']['clicked'] for k in ultima_settimana)
    unsub_tot   = sum(k['stats']['unsubscribed'] for k in ultima_settimana)

    report = {
        'periodo':     f'{ultima_settimana[0]["data"]} → {ultima_settimana[-1]["data"]}',
        'giorni':      len(ultima_settimana),
        'sent':        sent_tot,
        'opened':      opened_tot,
        'clicked':     clicked_tot,
        'unsubscribed':unsub_tot,
        'open_rate':   round(opened_tot / sent_tot, 4) if sent_tot > 0 else 0,
        'click_rate':  round(clicked_tot / sent_tot, 4) if sent_tot > 0 else 0,
        'generato':    datetime.now().isoformat()
    }

    # Proposta se performance bassa
    soglia = kb['strategic']['soglie']['open_rate_minimo']
    if report['open_rate'] < soglia:
        sug = _load_suggestions()
        sug.append({
            'id':    f'weekly_{date.today().isoformat()}',
            'tipo':  'report_settimanale',
            'data':  date.today().isoformat(),
            'stato': 'in_attesa',
            'msg':   f'Open rate settimana: {report["open_rate"]*100:.1f}% — sotto soglia {soglia*100:.0f}%. '
                     f'Considerare: cambio tema, nuovo soggetto, pausa temporanea.',
            'report': report
        })
        _save_suggestions(sug)

    return report


# ── Punto di entrata principale ───────────────────────────────────────────────

def run_morning_analysis(giorno: dict) -> dict:
    """
    Eseguito alle 08:45 — analisi completa prima dell'invio.
    Ritorna: {subject, reasoning, alerts, lang_map_fn, segment_map}
    """
    print('[Agent] === ANALISI MATTUTINA ===', flush=True)
    kb = _load_kb()

    # 1. Stats ieri
    stats = fetch_yesterday_stats()
    print(f'[Agent] Ieri: sent={stats["sent"]} open={stats["open_rate"]*100:.1f}% '
          f'click={stats["click_rate"]*100:.1f}% unsub={stats["unsubscribed"]}', flush=True)

    # 2. Events ieri (chi ha aperto/cliccato)
    events = {}
    if stats['sent'] > 0:
        try:
            events = fetch_yesterday_events()
            print(f'[Agent] Events: opener={len(events["openers"])} '
                  f'clicker={len(events["clickers"])} unsub={len(events["unsubs"])}', flush=True)
        except Exception as e:
            print(f'[Agent] fetch_yesterday_events errore: {e}', flush=True)
            events = {'openers': set(), 'clickers': set(), 'unsubs': set()}

    # 3. Aggiorna stati prospect
    if events:
        update_prospect_states(
            events.get('openers', set()),
            events.get('clickers', set()),
            events.get('unsubs', set())
        )

    # 4. Aggiorna KB empirical
    tema    = giorno.get('tema', '')
    lang    = giorno.get('lang', 'IT')
    subject = giorno.get('soggetto', '')
    if stats['sent'] > 0:
        update_empirical(kb, stats, tema, lang, subject)

    # 5. Contesto mercato
    update_market_context(kb)
    market = kb['market_context']
    if market.get('tema_suggerito') and market['tema_suggerito'] != tema:
        print(f'[Agent] Mercato {market["trend"]} → suggerisce {market["tema_suggerito"]} '
              f'(calendario: {tema})', flush=True)

    # 6. A/B test evaluation
    if events:
        evaluate_ab_tests(kb, events.get('openers', set()), events.get('clickers', set()))

    # 7. Genera nuove varianti se abbastanza dati
    tema_stats = kb['empirical'].get('tema_stats', {}).get(tema, {}).get(lang, {})
    if tema_stats.get('sent_totale', 0) >= 200:
        test_attivi = kb['content_evolution'].get('test_attivi', [])
        test_su_tema = [t for t in test_attivi if t['tema'] == tema and t['lang'] == lang]
        if not test_su_tema:
            generate_new_variants(kb, tema, lang)

    # 8. Sceglie soggetto
    soggetto_oggi = decide_subject(kb, giorno)
    reasoning_parts = [f'Soggetto: "{soggetto_oggi}"']
    if soggetto_oggi != subject:
        reasoning_parts.append('(da A/B test attivo)')
    if market.get('trend') != 'neutro':
        reasoning_parts.append(f'Mercato: {market.get("trend")} S&P500 {market.get("change_pct_1d", 0):+.1f}%')
    if stats['sent'] > 0:
        reasoning_parts.append(f'Open rate ieri: {stats["open_rate"]*100:.1f}%')
    reasoning = ' | '.join(reasoning_parts)

    # 9. Escalation checks
    alerts = check_escalations(kb, stats)
    for a in alerts:
        kb['alerts'].append(a)
        print(f'[Agent] ALERT {a["tipo"]}: {a["msg"]}', flush=True)

    # 10. Report settimanale (ogni lunedì)
    if date.today().weekday() == 0:
        generate_weekly_report(kb)

    # 11. Salva KB aggiornata
    _save_kb(kb)

    print(f'[Agent] Decisione: {reasoning}', flush=True)
    print('[Agent] === ANALISI COMPLETATA ===', flush=True)

    return {
        'subject':   soggetto_oggi,
        'reasoning': reasoning,
        'alerts':    alerts,
        'stats_ieri': stats,
        'market':    market,
        'in_pausa':  kb['empirical'].get('campagna_in_pausa', False)
    }


def get_dashboard_data() -> dict:
    """Dati completi per la dashboard admin."""
    kb  = _load_kb()
    kpi = _load_kpi()
    sug = _load_suggestions()

    # Trend 7 giorni
    ultimi7 = kpi[-7:] if len(kpi) >= 7 else kpi

    # Alert attivi non risolti
    alert_attivi = [a for a in kb.get('alerts', []) if not a.get('risolto')]

    return {
        'kb_strategic':     kb.get('strategic', {}),
        'kb_empirical':     kb.get('empirical', {}),
        'market_context':   kb.get('market_context', {}),
        'content_evolution':kb.get('content_evolution', {}),
        'insights':         kb.get('insights', [])[-10:],
        'kpi_ultimi7':      ultimi7,
        'kpi_totale':       len(kpi),
        'suggestions':      [s for s in sug if s.get('stato') == 'in_attesa'],
        'alerts_attivi':    alert_attivi,
        'ultimo_kpi':       kpi[-1] if kpi else None
    }
