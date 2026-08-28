"""
social_enrichment.py — Arricchimento profili social dei prospect Brevo

Modalità operative (in ordine di preferenza):
  1. Brave Search API  (BRAVE_SEARCH_API_KEY in .env)  — 2000 query/mese GRATIS
     Registrazione: https://api.search.brave.com  (no carta di credito)
  2. URL Pattern       (fallback immediato, zero costo, zero API)
     Genera URL probabili da nome+cognome — confidenza "pattern"
     Luciano verifica manualmente dalla dashboard → 1 click

Setup Brave:
  1. Vai su https://api.search.brave.com → Sign Up → Free Plan
  2. Copia la chiave (BSA...)
  3. Aggiungi in /root/rt2026/.env:  BRAVE_SEARCH_API_KEY=BSA...
  4. Riavvia dashboard:  kill $(pgrep -f dashboard.py) && nohup python3 ...

Priorità prospect: clicker → reader → cold
Rate Brave:        10 req/min (6s tra ogni call)
Job scheduler:     domenica 02:00, batch 300/settimana

Usage:
    python social_enrichment.py              # tutti non arricchiti
    python social_enrichment.py --batch 300  # max 300 per run
    python social_enrichment.py --test 5     # solo 5 (per test)
    python social_enrichment.py --patterns   # solo pattern (no API)
"""

import os, sys, re, json, time, random, logging, argparse, urllib.parse, unicodedata
from datetime import datetime

import requests

# ── Percorsi ──────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
PROFILES_FILE = os.path.join(BASE_DIR, 'social_profiles.json')
LOG_FILE      = os.path.join(BASE_DIR, 'social_enrichment.log')

# ── Carica .env ───────────────────────────────────────────────────────────
_env_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(_env_path):
    with open(_env_path, encoding='utf-8') as _ef:
        for _line in _ef:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _, _v = _line.partition('=')
                os.environ.setdefault(_k.strip(), _v.strip())

# ── Config ────────────────────────────────────────────────────────────────
try:
    with open(os.path.join(BASE_DIR, 'config.json'), encoding='utf-8') as _f:
        _cfg = json.load(_f)
    BREVO_KEY = (_cfg.get('social', {}).get('brevo', {}).get('api_key', '')
                 or os.getenv('BREVO_API_KEY', ''))
except Exception:
    BREVO_KEY = os.getenv('BREVO_API_KEY', '')

BRAVE_KEY      = os.getenv('BRAVE_SEARCH_API_KEY', '')
BREVO_LIST_ID  = 3
RATE_DELAY_SEC = 6.0    # 10 req/min
ENRICH_MAX_AGE = 30     # ri-enrichisce dopo N giorni

PERSONAL_DOMAINS = {
    'gmail.com','yahoo.com','yahoo.it','yahoo.es','yahoo.fr','yahoo.de',
    'hotmail.com','hotmail.it','outlook.com','live.com','msn.com',
    'libero.it','virgilio.it','alice.it','tiscali.it','tin.it',
    'icloud.com','me.com','mac.com','protonmail.com','pm.me',
    'gmx.com','gmx.de','gmx.net','web.de','t-online.de',
    'orange.fr','sfr.fr','laposte.net','free.fr','bbox.fr',
    'wanadoo.fr','aol.com','yandex.com','mail.com',
}

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-7s %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger('enrichment')


# ─────────────────────────────────────────────────────────────────────────
# I/O
# ─────────────────────────────────────────────────────────────────────────

def _load_profiles() -> dict:
    try:
        with open(PROFILES_FILE, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_profiles(profiles: dict):
    tmp = PROFILES_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(profiles, f, indent=2, ensure_ascii=False)
    os.replace(tmp, PROFILES_FILE)


# ─────────────────────────────────────────────────────────────────────────
# Brevo API
# ─────────────────────────────────────────────────────────────────────────

def _brevo_headers() -> dict:
    return {'api-key': BREVO_KEY, 'accept': 'application/json', 'content-type': 'application/json'}


def _brevo_fetch_all() -> list:
    contacts, offset = [], 0
    while True:
        url = (f'https://api.brevo.com/v3/contacts'
               f'?limit=500&offset={offset}&listIds={BREVO_LIST_ID}')
        try:
            r = requests.get(url, headers=_brevo_headers(), timeout=20)
            r.raise_for_status()
            batch = r.json().get('contacts', [])
        except Exception as e:
            log.error(f'Brevo fetch offset={offset}: {e}')
            break
        if not batch:
            break
        contacts.extend(batch)
        log.info(f'  Brevo: {len(contacts)} contatti...')
        if len(batch) < 500:
            break
        offset += 500
        time.sleep(0.5)
    return contacts


def _brevo_update(email: str, attrs: dict):
    url = f'https://api.brevo.com/v3/contacts/{urllib.parse.quote(email, safe="")}'
    try:
        r = requests.put(url, json={'attributes': attrs},
                         headers=_brevo_headers(), timeout=15)
        if r.status_code not in (200, 204):
            log.warning(f'Brevo update {email}: HTTP {r.status_code}')
    except Exception as e:
        log.warning(f'Brevo update {email}: {e}')


# ─────────────────────────────────────────────────────────────────────────
# Brave Search API  (primario — gratis 2000/mese)
# ─────────────────────────────────────────────────────────────────────────

def _brave_search(query: str) -> list[str]:
    """Restituisce lista di URL dal Brave Search API. Vuota se no API key."""
    if not BRAVE_KEY:
        return []
    try:
        r = requests.get(
            'https://api.search.brave.com/res/v1/web/search',
            params={'q': query, 'count': 5, 'safesearch': 'off'},
            headers={
                'Accept': 'application/json',
                'Accept-Encoding': 'gzip',
                'X-Subscription-Token': BRAVE_KEY,
            },
            timeout=15,
        )
        if r.status_code == 429:
            log.warning('Brave API rate limit — attendo 60s')
            time.sleep(60)
            return []
        r.raise_for_status()
        data = r.json()
        return [res['url'] for res in data.get('web', {}).get('results', [])]
    except Exception as e:
        log.warning(f'Brave search error "{query[:50]}": {e}')
        return []


def _extract_match(urls: list[str], pattern: str) -> tuple[str, str]:
    rx = re.compile(pattern, re.IGNORECASE)
    for url in urls[:5]:
        if rx.search(url):
            return url.split('?')[0].rstrip('/'), 'high'
    return '', ''


# ─────────────────────────────────────────────────────────────────────────
# URL Pattern (fallback — zero costo, zero API, immediato)
# ─────────────────────────────────────────────────────────────────────────

def _normalize(s: str) -> str:
    """Mario Rossi → mario-rossi (rimuove accenti e caratteri speciali)."""
    s = unicodedata.normalize('NFD', s.lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^a-z0-9]', '-', s)
    s = re.sub(r'-+', '-', s).strip('-')
    return s


def _url_patterns(firstname: str, lastname: str) -> dict:
    """
    Genera URL probabili da nome+cognome.
    Confidenza 'pattern' = non verificato, ma cliccabile dalla dashboard.
    """
    fn = _normalize(firstname)
    ln = _normalize(lastname)
    fn_raw = firstname.lower().replace(' ', '')
    ln_raw = lastname.lower().replace(' ', '')

    return {
        'linkedin_url': f'https://www.linkedin.com/in/{fn}-{ln}',
        'linkedin_confidence': 'pattern',
        'instagram_url': f'https://www.instagram.com/{fn_raw}{ln_raw}',
        'instagram_confidence': 'pattern',
        'facebook_url': f'https://www.facebook.com/{fn_raw}.{ln_raw}',
        'facebook_confidence': 'pattern',
    }


# ─────────────────────────────────────────────────────────────────────────
# Priorità contatti
# ─────────────────────────────────────────────────────────────────────────

def _priority(contact: dict) -> int:
    a = contact.get('attributes', {})
    if a.get('CLICKERS', 0): return 0
    if a.get('READERS',  0): return 1
    return 2


def _company_from_email(email: str) -> str:
    try:
        domain = email.split('@')[1].lower()
        if domain in PERSONAL_DOMAINS:
            return ''
        parts = domain.split('.')
        return parts[-2] if len(parts) >= 2 else parts[0]
    except Exception:
        return ''


def _needs_enrichment(profile: dict) -> bool:
    enriched_at = profile.get('enriched_at', '')
    if not enriched_at:
        return True
    try:
        age = (datetime.utcnow() - datetime.fromisoformat(enriched_at)).days
        return age >= ENRICH_MAX_AGE
    except Exception:
        return True


# ─────────────────────────────────────────────────────────────────────────
# Ricerca multi-platform
# ─────────────────────────────────────────────────────────────────────────

def _search_all(firstname: str, lastname: str, company: str) -> dict:
    """
    Cerca con Brave Search API (se disponibile).
    Priorità B2C: Instagram > Facebook > LinkedIn.
    """
    name_q = f'"{firstname} {lastname}"'
    co_q   = f' "{company}"' if company else ''

    result = {
        'linkedin_url': '', 'linkedin_confidence': '',
        'instagram_url': '', 'instagram_confidence': '',
        'facebook_url': '', 'facebook_confidence': '',
    }

    # ── Instagram (priorità B2C) ──
    urls = _brave_search(f'{name_q} site:instagram.com')
    ig_url, ig_c = _extract_match(
        urls, r'instagram\.com/(?!p/|reel/|stories/|explore/|tv/)[^/?#]+'
    )
    result['instagram_url'], result['instagram_confidence'] = ig_url, ig_c
    if BRAVE_KEY:
        time.sleep(RATE_DELAY_SEC + random.uniform(-1, 1))

    # ── Facebook ──
    urls = _brave_search(f'{name_q}{co_q} site:facebook.com')
    fb_url, fb_c = _extract_match(
        urls, r'facebook\.com/(?!groups/|events/|pages/|photo|video|share|login|help)[^/?#]+'
    )
    result['facebook_url'], result['facebook_confidence'] = fb_url, fb_c
    if BRAVE_KEY:
        time.sleep(RATE_DELAY_SEC + random.uniform(-1, 1))

    # ── LinkedIn ──
    urls = _brave_search(f'{name_q}{co_q} site:linkedin.com/in')
    li_url, li_c = _extract_match(urls, r'linkedin\.com/in/[^/?#]+')
    result['linkedin_url'], result['linkedin_confidence'] = li_url, li_c
    if BRAVE_KEY:
        time.sleep(RATE_DELAY_SEC + random.uniform(-1, 1))

    return result


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────

def run_enrichment(batch_size: int = 0, test_mode: int = 0,
                   patterns_only: bool = False) -> dict:
    """
    Arricchisce i profili social dei prospect Brevo.

    Args:
        batch_size:    max contatti da elaborare (0 = tutti)
        test_mode:     se > 0, elabora solo N contatti
        patterns_only: usa solo pattern URL (ignora Brave API)
    """
    profiles = _load_profiles()
    stats    = {'processed': 0, 'found_li': 0, 'found_ig': 0, 'found_fb': 0,
                'skipped': 0, 'errors': 0, 'mode': ''}

    use_brave = bool(BRAVE_KEY) and not patterns_only
    stats['mode'] = 'brave' if use_brave else 'pattern'

    log.info('=' * 60)
    log.info('SOCIAL ENRICHMENT — START %s' % datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'))
    log.info(f'Modalita: {"Brave Search API" if use_brave else "URL Pattern (fallback)"}')
    if not use_brave:
        log.info('  → Per abilitare Brave: aggiungi BRAVE_SEARCH_API_KEY in .env')
        log.info('  → Registrazione gratuita: https://api.search.brave.com')
    log.info('=' * 60)

    log.info('Fetching contatti Brevo...')
    all_contacts = _brevo_fetch_all()
    log.info(f'Totale: {len(all_contacts)}')

    all_contacts.sort(key=_priority)

    to_process = []
    for c in all_contacts:
        email = c.get('email', '')
        if not email:
            continue
        existing = profiles.get(email, {})
        # In modalità pattern: salta se già ha URL verificati o pattern recenti
        if not _needs_enrichment(existing):
            stats['skipped'] += 1
            continue
        # In modalità Brave: salta se già arricchito con Brave (confidence high/manual)
        if use_brave and existing.get('linkedin_confidence') in ('high', 'manual'):
            stats['skipped'] += 1
            continue
        to_process.append(c)

    log.info(f'Da arricchire: {len(to_process)} | Saltati: {stats["skipped"]}')

    limit = test_mode if test_mode else (batch_size if batch_size else len(to_process))
    to_process = to_process[:limit]
    log.info(f'Elaboro {len(to_process)} contatti')

    for i, contact in enumerate(to_process):
        email     = contact.get('email', '')
        attrs     = contact.get('attributes', {})
        firstname = attrs.get('FIRSTNAME', '').strip()
        lastname  = attrs.get('LASTNAME',  '').strip()
        priority  = _priority(contact)
        company   = _company_from_email(email)
        prio_tag  = ['CLICKER', 'READER', 'COLD'][priority]

        if not firstname or not lastname:
            stats['errors'] += 1
            continue

        log.info(
            f'[{i+1}/{len(to_process)}] {firstname} {lastname} <{email}> '
            f'[{prio_tag}] company={company or "personal"}'
        )

        try:
            if use_brave:
                found = _search_all(firstname, lastname, company)
            else:
                found = _url_patterns(firstname, lastname)
        except Exception as e:
            log.error(f'  Errore: {e}')
            stats['errors'] += 1
            continue

        profiles[email] = {
            'firstname':            firstname,
            'lastname':             lastname,
            'company':              company,
            'priority':             priority,
            'linkedin_url':         found['linkedin_url'],
            'linkedin_confidence':  found['linkedin_confidence'],
            'instagram_url':        found['instagram_url'],
            'instagram_confidence': found['instagram_confidence'],
            'facebook_url':         found['facebook_url'],
            'facebook_confidence':  found['facebook_confidence'],
            'enriched_at':          datetime.utcnow().isoformat(),
            'manually_verified':    False,
        }

        if found['linkedin_url']:  stats['found_li'] += 1
        if found['instagram_url']: stats['found_ig'] += 1
        if found['facebook_url']:  stats['found_fb'] += 1
        stats['processed'] += 1

        # Write-back LinkedIn su Brevo (solo se trovato con ricerca reale)
        if found['linkedin_url'] and found.get('linkedin_confidence') in ('high', 'manual'):
            _brevo_update(email, {'LINKEDIN': found['linkedin_url']})

        if (i + 1) % 20 == 0:
            _save_profiles(profiles)
            log.info(f'  [checkpoint] LI:{stats["found_li"]} IG:{stats["found_ig"]} FB:{stats["found_fb"]}')

    _save_profiles(profiles)

    log.info('=' * 60)
    log.info(
        f'FINE [{stats["mode"]}] processed:{stats["processed"]} | '
        f'LI:{stats["found_li"]} IG:{stats["found_ig"]} FB:{stats["found_fb"]} | '
        f'skip:{stats["skipped"]} err:{stats["errors"]}'
    )
    log.info('=' * 60)
    return stats


# ─────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Social enrichment prospect Brevo')
    parser.add_argument('--batch',    type=int, default=0, help='Max contatti per run')
    parser.add_argument('--test',     type=int, default=0, help='Test mode: N contatti')
    parser.add_argument('--patterns', action='store_true',  help='Solo pattern URL (no Brave API)')
    args = parser.parse_args()

    stats = run_enrichment(
        batch_size=args.batch,
        test_mode=args.test,
        patterns_only=args.patterns,
    )
    print(json.dumps(stats, indent=2))
