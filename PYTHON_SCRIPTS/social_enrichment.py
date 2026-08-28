"""
social_enrichment.py — Arricchimento profili social dei prospect Brevo

Cerca su DuckDuckGo LinkedIn / Instagram / Facebook per ogni contatto.
Priorità: clicker → reader → cold (prospect senza engagement).
Rate:     6s tra ogni ricerca (10 req/min) — nessuna API key richiesta.
Output:   social_profiles.json (locale VPS) + write-back campo LINKEDIN su Brevo.

Usage:
    python social_enrichment.py              # tutti i contatti non arricchiti
    python social_enrichment.py --batch 300  # max 300 per run (job notturno)
    python social_enrichment.py --test 5     # solo 5 contatti, per test
"""

import os, sys, re, json, time, random, logging, argparse, urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

import requests

# ── Percorsi ──────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
PROFILES_FILE = os.path.join(BASE_DIR, 'social_profiles.json')
LOG_FILE      = os.path.join(BASE_DIR, 'social_enrichment.log')

# ── Config ────────────────────────────────────────────────────────────────
try:
    _cfg_path = os.path.join(BASE_DIR, 'config.json')
    with open(_cfg_path, encoding='utf-8') as _f:
        _cfg = json.load(_f)
    BREVO_KEY = _cfg.get('social', {}).get('brevo', {}).get('api_key', '') or os.getenv('BREVO_API_KEY', '')
except Exception:
    BREVO_KEY = os.getenv('BREVO_API_KEY', '')

BREVO_LIST_ID   = 3
RATE_DELAY_SEC  = 6.0       # 10 req/min
ENRICH_MAX_AGE  = 30        # ri-arricchisce dopo N giorni
DDG_URL         = 'https://html.duckduckgo.com/html/'

# Domini email personali → nessun segnale azienda
PERSONAL_DOMAINS = {
    'gmail.com','yahoo.com','yahoo.it','yahoo.es','yahoo.fr','yahoo.de',
    'hotmail.com','hotmail.it','outlook.com','live.com','msn.com',
    'libero.it','virgilio.it','alice.it','tiscali.it','tin.it',
    'icloud.com','me.com','mac.com','protonmail.com','pm.me',
    'gmx.com','gmx.de','gmx.net','web.de','t-online.de',
    'orange.fr','sfr.fr','laposte.net','free.fr','bbox.fr',
    'wanadoo.fr','aol.com','yandex.com','mail.com',
}

# User-Agent pool per variare le richieste
_UA_POOL = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
]

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-7s %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ]
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


def _brevo_fetch_all_contacts() -> list:
    """Scarica tutti i contatti della lista Brevo con paginazione."""
    contacts, offset = [], 0
    while True:
        url = f'https://api.brevo.com/v3/contacts?limit=500&offset={offset}&listIds={BREVO_LIST_ID}'
        try:
            r = requests.get(url, headers=_brevo_headers(), timeout=20)
            r.raise_for_status()
            batch = r.json().get('contacts', [])
        except Exception as e:
            log.error(f'Brevo fetch error offset={offset}: {e}')
            break
        if not batch:
            break
        contacts.extend(batch)
        log.info(f'  Brevo: scaricati {len(contacts)} contatti...')
        if len(batch) < 500:
            break
        offset += 500
        time.sleep(0.5)
    return contacts


def _brevo_update(email: str, attrs: dict):
    """Write-back attributi su Brevo (LINKEDIN, JOB_TITLE)."""
    url = f'https://api.brevo.com/v3/contacts/{urllib.parse.quote(email, safe="")}'
    try:
        r = requests.put(url, json={'attributes': attrs}, headers=_brevo_headers(), timeout=15)
        if r.status_code not in (200, 204):
            log.warning(f'Brevo update {email}: HTTP {r.status_code}')
    except Exception as e:
        log.warning(f'Brevo update {email}: {e}')


# ─────────────────────────────────────────────────────────────────────────
# DuckDuckGo scraping
# ─────────────────────────────────────────────────────────────────────────

def _ddg_search(query: str) -> list[str]:
    """Restituisce lista di URL dai risultati DuckDuckGo (formato HTML)."""
    headers = {
        'User-Agent': random.choice(_UA_POOL),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    try:
        r = requests.post(
            DDG_URL,
            data={'q': query, 'kl': 'wt-wt', 'b': ''},
            headers=headers,
            timeout=15,
            allow_redirects=True,
        )
        # Estrai URLs dai redirect uddg= (URL reali codificati)
        encoded = re.findall(r'uddg=([^&"\']+)', r.text)
        urls = []
        for enc in encoded:
            try:
                urls.append(urllib.parse.unquote(enc))
            except Exception:
                pass
        return urls
    except Exception as e:
        log.warning(f'DDG error per "{query[:60]}": {e}')
        return []


def _extract_match(urls: list[str], pattern: str) -> tuple[str, str]:
    """Estrae il primo URL che matcha il pattern. Returns (url, confidence)."""
    rx = re.compile(pattern, re.IGNORECASE)
    for url in urls[:6]:
        if rx.search(url):
            return url.split('?')[0].rstrip('/'), 'high'
    return '', ''


# ─────────────────────────────────────────────────────────────────────────
# Priorità contatti
# ─────────────────────────────────────────────────────────────────────────

def _priority(contact: dict) -> int:
    """0=clicker, 1=reader, 2=cold."""
    a = contact.get('attributes', {})
    if a.get('CLICKERS', 0):
        return 0
    if a.get('READERS', 0):
        return 1
    return 2


def _company_from_email(email: str) -> str:
    """Estrae il nome dell'azienda dal dominio email (se non personale)."""
    try:
        domain = email.split('@')[1].lower()
        if domain in PERSONAL_DOMAINS:
            return ''
        # Prende il nome principale del dominio (senza TLD)
        parts = domain.split('.')
        return parts[-2] if len(parts) >= 2 else parts[0]
    except Exception:
        return ''


def _needs_enrichment(profile: dict) -> bool:
    """True se il profilo non è stato arricchito di recente."""
    enriched_at = profile.get('enriched_at', '')
    if not enriched_at:
        return True
    try:
        age = datetime.utcnow() - datetime.fromisoformat(enriched_at)
        return age.days >= ENRICH_MAX_AGE
    except Exception:
        return True


# ─────────────────────────────────────────────────────────────────────────
# Ricerca multi-platform
# ─────────────────────────────────────────────────────────────────────────

def _search_all(firstname: str, lastname: str, company: str) -> dict:
    """
    Cerca LinkedIn, Instagram, Facebook per un prospect.
    Piattaforme ordinate per rilevanza B2C: Instagram > Facebook > LinkedIn.
    """
    name_q   = f'"{firstname} {lastname}"'
    co_q     = f' "{company}"' if company else ''
    result   = {
        'linkedin_url': '', 'linkedin_confidence': '',
        'instagram_url': '', 'instagram_confidence': '',
        'facebook_url': '',  'facebook_confidence': '',
    }

    # ── Instagram (priorità B2C) ──────────────────────────────────────
    q_ig = f'{name_q} site:instagram.com'
    urls = _ddg_search(q_ig)
    ig_url, ig_conf = _extract_match(urls, r'instagram\.com/(?!p/|reel/|stories/|explore/)[^/?#]+')
    result['instagram_url']        = ig_url
    result['instagram_confidence'] = ig_conf
    log.debug(f'  IG: {ig_url or "—"}')
    time.sleep(RATE_DELAY_SEC + random.uniform(-1, 1))

    # ── Facebook ─────────────────────────────────────────────────────
    q_fb = f'{name_q}{co_q} site:facebook.com'
    urls = _ddg_search(q_fb)
    fb_url, fb_conf = _extract_match(
        urls, r'facebook\.com/(?!groups/|events/|pages/|photo|video|share|login|help)[^/?#]+'
    )
    result['facebook_url']        = fb_url
    result['facebook_confidence'] = fb_conf
    log.debug(f'  FB: {fb_url or "—"}')
    time.sleep(RATE_DELAY_SEC + random.uniform(-1, 1))

    # ── LinkedIn ─────────────────────────────────────────────────────
    q_li = f'{name_q}{co_q} site:linkedin.com/in'
    urls = _ddg_search(q_li)
    li_url, li_conf = _extract_match(urls, r'linkedin\.com/in/[^/?#]+')
    result['linkedin_url']        = li_url
    result['linkedin_confidence'] = li_conf
    log.debug(f'  LI: {li_url or "—"}')
    time.sleep(RATE_DELAY_SEC + random.uniform(-1, 1))

    return result


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────

def run_enrichment(batch_size: int = 0, test_mode: int = 0) -> dict:
    """
    Arricchisce i profili social dei prospect Brevo.

    Args:
        batch_size: max contatti da elaborare (0 = tutti)
        test_mode:  se > 0, elabora solo N contatti (per debug)

    Returns:
        Stats dict: {processed, found_li, found_ig, found_fb, skipped, errors}
    """
    profiles = _load_profiles()
    stats    = {'processed': 0, 'found_li': 0, 'found_ig': 0, 'found_fb': 0,
                'skipped': 0, 'errors': 0}

    log.info('=' * 60)
    log.info('SOCIAL ENRICHMENT — START %s' % datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'))
    log.info('=' * 60)

    # 1. Fetch contatti Brevo
    log.info('Fetching contatti Brevo lista %d...' % BREVO_LIST_ID)
    all_contacts = _brevo_fetch_all_contacts()
    log.info(f'Totale contatti: {len(all_contacts)}')

    # 2. Ordina per priorità: clicker → reader → cold
    all_contacts.sort(key=_priority)

    # 3. Filtra: solo quelli che hanno bisogno di arricchimento
    to_process = []
    for c in all_contacts:
        email = c.get('email', '')
        if not email:
            continue
        existing = profiles.get(email, {})
        if not _needs_enrichment(existing):
            stats['skipped'] += 1
            continue
        to_process.append(c)

    log.info(f'Da arricchire: {len(to_process)} | Già arricchiti: {stats["skipped"]}')

    # 4. Applica limite batch / test
    limit = test_mode if test_mode else (batch_size if batch_size else len(to_process))
    to_process = to_process[:limit]
    log.info(f'Elaboro {len(to_process)} contatti (limit={limit})')

    # 5. Ciclo principale
    for i, contact in enumerate(to_process):
        email     = contact.get('email', '')
        attrs     = contact.get('attributes', {})
        firstname = attrs.get('FIRSTNAME', '').strip()
        lastname  = attrs.get('LASTNAME', '').strip()
        priority  = _priority(contact)
        company   = _company_from_email(email)
        prio_tag  = ['CLICKER', 'READER', 'COLD'][priority]

        if not firstname or not lastname:
            log.info(f'[{i+1}/{len(to_process)}] SKIP {email} — nome mancante')
            stats['errors'] += 1
            continue

        log.info(
            f'[{i+1}/{len(to_process)}] {firstname} {lastname} <{email}> '
            f'[{prio_tag}] company={company or "personal"}'
        )

        try:
            found = _search_all(firstname, lastname, company)
        except Exception as e:
            log.error(f'  Errore ricerca: {e}')
            stats['errors'] += 1
            continue

        # Salva nel profilo locale
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

        # Stats
        if found['linkedin_url']:  stats['found_li'] += 1
        if found['instagram_url']: stats['found_ig'] += 1
        if found['facebook_url']:  stats['found_fb'] += 1
        stats['processed'] += 1

        # Write-back Brevo
        brevo_attrs = {}
        if found['linkedin_url']:
            brevo_attrs['LINKEDIN'] = found['linkedin_url']
        if brevo_attrs:
            _brevo_update(email, brevo_attrs)

        # Salva ogni 20 contatti (checkpoint)
        if (i + 1) % 20 == 0:
            _save_profiles(profiles)
            log.info(
                f'  Checkpoint — LI:{stats["found_li"]} IG:{stats["found_ig"]} '
                f'FB:{stats["found_fb"]} su {stats["processed"]} elaborati'
            )

    # Salva finale
    _save_profiles(profiles)

    log.info('=' * 60)
    log.info(
        f'FINE — processed:{stats["processed"]} | '
        f'LinkedIn:{stats["found_li"]} | Instagram:{stats["found_ig"]} | '
        f'Facebook:{stats["found_fb"]} | skip:{stats["skipped"]} | err:{stats["errors"]}'
    )
    log.info('=' * 60)
    return stats


# ─────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Social enrichment prospect Brevo')
    parser.add_argument('--batch', type=int, default=0,
                        help='Max contatti per run (0=tutti)')
    parser.add_argument('--test',  type=int, default=0,
                        help='Test mode: elabora solo N contatti')
    args = parser.parse_args()

    stats = run_enrichment(batch_size=args.batch, test_mode=args.test)
    print(json.dumps(stats, indent=2))
