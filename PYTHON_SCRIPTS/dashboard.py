# -*- coding: utf-8 -*-
"""
ROBOT TRADER 2026 — DASHBOARD v2.0
python dashboard.py → http://localhost:8080

Tab: Home | Servizi | Parametri | Azioni | ETF | Fondi | Esecuzione
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import json, os, sys, glob, subprocess, threading, secrets, time, ssl
import smtplib, hashlib, html, string, csv, io, base64 as b64lib, tempfile
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders as email_encoders
from fpdf import FPDF

# Carica .env prima di qualsiasi os.getenv()
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
except ImportError:
    pass

try:
    import chat_service as _chat
    _CHAT_OK = True
except ImportError:
    _CHAT_OK = False

try:
    import pandas as pd
except ImportError:
    print("ERRORE: pip install pandas openpyxl")
    sys.exit(1)

try:
    # Carica config SMTP prima dell'import così order_builder la eredita
    _cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    try:
        with open(_cfg_path) as _f:
            _cfg_email = json.load(_f).get("email", {})
    except Exception:
        _cfg_email = {}
    if not os.getenv("BREVO_SMTP_LOGIN"):
        _v = _cfg_email.get("smtp_login","") or _cfg_email.get("sender","")
        if _v: os.environ["BREVO_SMTP_LOGIN"] = _v
    if not os.getenv("BREVO_SMTP_PASSWORD"):
        _v = _cfg_email.get("app_password","")
        if _v: os.environ["BREVO_SMTP_PASSWORD"] = _v
    if not os.getenv("BREVO_SMTP_HOST"):
        _v = _cfg_email.get("smtp_server","")
        if _v: os.environ["BREVO_SMTP_HOST"] = _v
    import order_builder as _ob
    _OB_OK = True
except ImportError:
    _OB_OK = False

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR   = os.path.join(os.path.dirname(BASE_DIR), "REPORTS_DAILY")

def _conta_ticker_universo():
    """Conta il totale ticker per ogni categoria screener dai file dati reali.
    Formula: ALL_AZIONI + (ALL_ETF + etf_universe_cache_ISINs - overlap) + (ALL_FONDI + fondi_eu_ISINs)
    """
    try:
        _sys_path_bak = sys.path[:]
        if BASE_DIR not in sys.path:
            sys.path.insert(0, BASE_DIR)
        from ticker_lists_5000 import ALL_AZIONI, ALL_ETF, ALL_FONDI
        sys.path[:] = _sys_path_bak
        n_azioni = len(ALL_AZIONI)
        # ETF: ticker da ticker_lists + ISINs da etf_universe_cache, deduplicati per preferred_ticker
        try:
            with open(os.path.join(BASE_DIR, 'etf_universe_cache.json'), encoding='utf-8') as _f:
                etf_cache = json.load(_f)
            eu_preferred = {v['preferred_ticker'] for v in etf_cache.values()
                            if not v.get('error') and v.get('preferred_ticker')}
            overlap = len(set(ALL_ETF) & eu_preferred)
            n_etf = len(ALL_ETF) + len(etf_cache) - overlap
        except Exception:
            n_etf = len(ALL_ETF)
        # Fondi: US (ALL_FONDI) + EU UCITS (fondi_eu_universe_cache ISINs)
        try:
            with open(os.path.join(BASE_DIR, 'fondi_eu_universe_cache.json'), encoding='utf-8') as _f:
                feu_cache = json.load(_f)
            n_fondi = len(ALL_FONDI) + len(feu_cache)
        except Exception:
            n_fondi = len(ALL_FONDI)
        return n_azioni, n_etf, n_fondi, n_azioni + n_etf + n_fondi
    except Exception:
        return 2621, 5730, 1735, 10086

_N_AZ, _N_ETF_TOT, _N_FD, _N_TOT = _conta_ticker_universo()

def _fmt_it(n):
    return f"{n:,}".replace(",", ".")

def _fmt_en(n):
    return f"{n:,}"
FATTURE_DIR   = os.path.join(os.path.dirname(BASE_DIR), "FATTURE")
REPORTS_PDF_DIR = os.path.join(os.path.dirname(BASE_DIR), "REPORTS_PDF")
os.makedirs(REPORTS_PDF_DIR, exist_ok=True)
FATTURE_COUNTER = os.path.join(BASE_DIR, "fatture_counter.json")
ORDINI_DIR    = os.path.join(BASE_DIR, "ORDINI")
PARAMETRI_FILE= os.path.join(BASE_DIR, "parametri.json")
SERVIZI_FILE  = os.path.join(BASE_DIR, "servizi_config.json")
CLIENTI_FILE  = os.path.join(BASE_DIR, "clienti.json")
BACKUPS_DIR   = os.path.join(BASE_DIR, "BACKUPS", "clienti")
SESSIONS_FILE  = os.path.join(BASE_DIR, "sessions.json")
RL_BLOCKS_FILE = os.path.join(BASE_DIR, ".rl_blocks.json")
PROSPECT_FILE  = os.path.join(BASE_DIR, "prospect.json")

running  = {}
run_lock = threading.Lock()
MAX_LOG  = 300

# ─── SESSIONI ADMIN ─────────────────────────────────────────
# Legge la password da variabile d'ambiente o da config.json → "admin_password".
# NON lasciare il default "changeme" in produzione.
def _load_admin_password():
    pw = os.getenv("ADMIN_PASSWORD", "")
    if pw:
        return pw
    try:
        with open(os.path.join(BASE_DIR, "config.json"), encoding="utf-8") as _f:
            return json.load(_f).get("admin_password", "")
    except Exception:
        return ""

ADMIN_PASSWORD = _load_admin_password()
if ADMIN_PASSWORD in ("123", "changeme", ""):
    print("⚠️  ATTENZIONE: password admin non sicura! Imposta ADMIN_PASSWORD in .env o config.json → admin_password", flush=True)

SESSIONS = {}              # token → login_time (float) — admin
CLIENT_SESSIONS = {}       # token → email  (clienti paganti)
CLIENT_SESSION_TIMES = {}  # token → last_access_time (float)
RESET_TOKENS = {}          # token → (email, expiry_timestamp)

# ─── RATE LIMITING LOGIN ──────────────────────────────────────
_LOGIN_ATTEMPTS  = {}   # ip → [timestamp, ...]
_LOGIN_BLOCKED   = {}   # ip → blocked_until (float)
_RL_WINDOW       = 15 * 60   # 15 minuti
_RL_MAX_ATTEMPTS = 5
_RL_BLOCK_TIME   = 30 * 60   # 30 minuti

def _rl_check(ip: str) -> bool:
    """Restituisce True se l'IP è bloccato."""
    now = time.time()
    if _LOGIN_BLOCKED.get(ip, 0) > now:
        return True
    cutoff = now - _RL_WINDOW
    attempts = [t for t in _LOGIN_ATTEMPTS.get(ip, []) if t > cutoff]
    _LOGIN_ATTEMPTS[ip] = attempts
    return False

def _rl_fail(ip: str):
    """Registra un tentativo fallito; blocca se si supera il limite."""
    now = time.time()
    cutoff = now - _RL_WINDOW
    attempts = [t for t in _LOGIN_ATTEMPTS.get(ip, []) if t > cutoff]
    attempts.append(now)
    _LOGIN_ATTEMPTS[ip] = attempts
    if len(attempts) >= _RL_MAX_ATTEMPTS:
        _LOGIN_BLOCKED[ip] = now + _RL_BLOCK_TIME
        _LOGIN_ATTEMPTS[ip] = []
        print(f"[SECURITY] IP {ip} bloccato per 30 minuti ({_RL_MAX_ATTEMPTS} tentativi falliti)", flush=True)
        _save_rl_blocks()

def _rl_ok(ip: str):
    """Azzera i tentativi dopo un login riuscito."""
    _LOGIN_ATTEMPTS.pop(ip, None)
    _LOGIN_BLOCKED.pop(ip, None)

def _save_rl_blocks():
    """Persiste blocchi IP attivi su file per sopravvivere al riavvio."""
    try:
        now = time.time()
        active = {ip: ts for ip, ts in _LOGIN_BLOCKED.items() if ts > now}
        tmp = RL_BLOCKS_FILE + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(active, f)
        os.replace(tmp, RL_BLOCKS_FILE)
        try: os.chmod(RL_BLOCKS_FILE, 0o600)
        except Exception: pass
    except Exception as e:
        print(f"[SECURITY] Errore salvataggio blocchi: {e}", flush=True)

def _load_rl_blocks():
    """Ripristina blocchi IP attivi all'avvio."""
    try:
        now = time.time()
        with open(RL_BLOCKS_FILE) as f:
            data = json.load(f)
        for ip, ts in data.items():
            if ts > now:
                _LOGIN_BLOCKED[ip] = ts
        if _LOGIN_BLOCKED:
            print(f"[SECURITY] Ripristinati {len(_LOGIN_BLOCKED)} blocchi IP", flush=True)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    except Exception as e:
        print(f"[SECURITY] Errore caricamento blocchi: {e}", flush=True)

# ─── VALIDAZIONE INPUT ────────────────────────────────────────
def _validate_str(s, max_len=200):
    """Tronca e stripa stringhe in ingresso — usa per tutti i campi utente."""
    if not isinstance(s, str):
        s = str(s) if s is not None else ''
    return s.strip()[:max_len]

ADMIN_SESSION_TIMEOUT  = 8  * 3600  # 8 ore — scade dal momento del login
CLIENT_SESSION_TIMEOUT = 24 * 3600  # 24 ore — finestra scorrevole sull'ultimo accesso
def _persist_sessions():
    """Salva sessioni attive su file (sopravvivono al riavvio)."""
    try:
        now = time.time()
        data = {
            'admin': {t: ts for t, ts in SESSIONS.items() if now - ts < ADMIN_SESSION_TIMEOUT},
            'client': {t: CLIENT_SESSIONS[t] for t in CLIENT_SESSIONS if now - CLIENT_SESSION_TIMES.get(t, 0) < CLIENT_SESSION_TIMEOUT},
            'client_times': {t: CLIENT_SESSION_TIMES[t] for t in CLIENT_SESSION_TIMES if now - CLIENT_SESSION_TIMES[t] < CLIENT_SESSION_TIMEOUT},
        }
        tmp = SESSIONS_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        os.replace(tmp, SESSIONS_FILE)
        try: os.chmod(SESSIONS_FILE, 0o600)
        except Exception: pass
    except Exception as e:
        print(f"[SESSIONS] Errore persist: {e}", flush=True)

def _load_sessions():
    """Ripristina sessioni valide all'avvio del server."""
    try:
        with open(SESSIONS_FILE, encoding='utf-8') as f:
            data = json.load(f)
        now = time.time()
        for t, ts in data.get('admin', {}).items():
            if now - ts < ADMIN_SESSION_TIMEOUT:
                SESSIONS[t] = ts
        for t, email in data.get('client', {}).items():
            ts = data.get('client_times', {}).get(t, 0)
            if now - ts < CLIENT_SESSION_TIMEOUT:
                CLIENT_SESSIONS[t] = email
                CLIENT_SESSION_TIMES[t] = ts
        n_admin = len(SESSIONS); n_cli = len(CLIENT_SESSIONS)
        if n_admin or n_cli:
            print(f"[SESSIONS] Ripristinate: {n_admin} admin, {n_cli} client", flush=True)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    except Exception as e:
        print(f"[SESSIONS] Errore caricamento: {e}", flush=True)

_load_sessions()
_load_rl_blocks()

def _scadenza_trial_check():
    """Imposta stato='SCADUTO' per i TESTER con trial_end nel passato."""
    try:
        from datetime import datetime as _dt
        now = _dt.now()
        db = read_clienti()
        changed = 0
        for lista in [db.get('tester', []), db.get('clienti', [])]:
            for c in lista:
                if c.get('stato') == 'TESTER' and c.get('trial_end'):
                    try:
                        end = _dt.strptime(c['trial_end'][:19], '%Y-%m-%dT%H:%M:%S')
                        if now > end:
                            c['stato'] = 'SCADUTO'
                            changed += 1
                            print(f"[TRIAL] Scaduto: {c.get('email','')} — trial terminato il {c['trial_end'][:10]}", flush=True)
                    except Exception:
                        pass
        if changed:
            save_clienti(db)
            print(f'[TRIAL] {changed} account(s) scaduti automaticamente', flush=True)
    except Exception as e:
        print(f'[TRIAL] Errore check scadenza: {e}', flush=True)

def _trial_check_loop():
    import time as _t
    _t.sleep(60)  # attende 1 minuto all'avvio per evitare race con read_clienti
    while True:
        _scadenza_trial_check()
        _t.sleep(86400)  # controlla ogni 24 ore

_t_trial = threading.Thread(target=_trial_check_loop, daemon=True, name='trial-check')
_t_trial.start()

# ─── LOCK SCRITTURA FILE CONDIVISI ──────────────────────────
_clienti_lock  = threading.Lock()
_fatture_lock  = threading.Lock()
_prospect_lock = threading.Lock()



from assets import FUERTE_LOGO_B64, PWA_ICON_192_B64, PWA_ICON_512_B64


# ─── BREVO SMTP (per invio credenziali B2C) ──────────────────
def _load_smtp_config():
    try:
        with open(os.path.join(BASE_DIR, "config.json")) as f:
            cfg = json.load(f).get("email", {})
    except Exception:
        cfg = {}
    host  = os.getenv("BREVO_SMTP_HOST")     or cfg.get("smtp_server",  "smtp.gmail.com")
    login = os.getenv("BREVO_SMTP_LOGIN")    or cfg.get("smtp_login",   "") or cfg.get("sender", "")
    pwd   = os.getenv("BREVO_SMTP_PASSWORD") or cfg.get("app_password", "")
    sender= os.getenv("BREVO_SENDER_EMAIL")  or cfg.get("sender",       "") or login
    name  = os.getenv("BREVO_SENDER_NAME",   "Fuerte Venture Capital")
    return host, login, pwd, sender, name

BREVO_SMTP_HOST, BREVO_SMTP_LOGIN, BREVO_SMTP_PASSWORD, BREVO_SENDER_EMAIL, BREVO_SENDER_NAME = _load_smtp_config()
BREVO_SMTP_PORT = 587
print(f"[SMTP] Host={BREVO_SMTP_HOST} Login={BREVO_SMTP_LOGIN} Pwd={'OK' if BREVO_SMTP_PASSWORD else 'VUOTA'}", flush=True)

# ─── BREVO REST API ───────────────────────────────────────────
def _brevo_api_key():
    v = os.getenv('BREVO_API_KEY', '')
    if v:
        return v
    try:
        with open(os.path.join(BASE_DIR, 'config.json'), encoding='utf-8') as f:
            return json.load(f).get('social', {}).get('brevo', {}).get('api_key', '')
    except Exception:
        return ''

def _brevo_call(path, method='GET', payload=None, timeout=20):
    import requests as _req
    key = _brevo_api_key()
    if not key:
        return None, 0
    url = 'https://api.brevo.com/v3' + path
    headers = {'api-key': key, 'Content-Type': 'application/json', 'Accept': 'application/json'}
    try:
        resp = _req.request(method, url, json=payload, headers=headers, timeout=timeout)
        try:
            return resp.json(), resp.status_code
        except Exception:
            return {}, resp.status_code
    except _req.exceptions.Timeout:
        return {'error': f'Brevo timeout dopo {timeout}s'}, -1
    except Exception as e:
        return {'error': str(e)}, -1

def _brevo_get_campaign_dates(campagna_id):
    """Returns (start_date, end_date) strings for campaignStats query."""
    from datetime import datetime, timedelta, date as _date
    data, status = _brevo_call(f'/emailCampaigns/{campagna_id}')
    if status != 200:
        today = _date.today().isoformat()
        return today, today
    sent = data.get('sentDate') or data.get('scheduledAt') or ''
    if sent:
        dt = datetime.fromisoformat(sent.replace('Z', '+00:00'))
        start = (dt - timedelta(days=1)).strftime('%Y-%m-%d')
        end = min((dt + timedelta(days=30)).strftime('%Y-%m-%d'), _date.today().isoformat())
    else:
        today = _date.today().isoformat()
        start = end = today
    return start, end

def _brevo_check_openers(campagna_id, emails):
    """Returns set of emails that opened the campaign. Synchronous, one call per email."""
    import urllib.request as _ur, urllib.error as _ue, urllib.parse as _up
    key = _brevo_api_key()
    if not key or not emails:
        return set()
    start, end = _brevo_get_campaign_dates(campagna_id)
    cid = str(campagna_id)
    openers = set()
    for email in emails:
        try:
            params = _up.urlencode({'startDate': start, 'endDate': end})
            url = f'https://api.brevo.com/v3/contacts/{_up.quote(email)}/campaignStats?{params}'
            req = _ur.Request(url)
            req.add_header('api-key', key)
            req.add_header('Accept', 'application/json')
            with _ur.urlopen(req, timeout=10, context=_SSL_CTX) as r:
                d = json.loads(r.read())
            if any(str(x.get('campaignId')) == cid for x in d.get('opened', [])):
                openers.add(email.lower())
        except Exception:
            pass
    return openers

# ─── BASE URL (un solo posto da cambiare al go-live) ─────────────────────────
def _load_base_url() -> str:
    """Legge BASE_URL da env var, poi da config.json, poi fallback localhost."""
    if os.getenv("BASE_URL"):
        return os.getenv("BASE_URL").rstrip("/")
    try:
        with open(os.path.join(BASE_DIR, "config.json")) as _f:
            _u = json.load(_f).get("base_url", "")
        if _u:
            return _u.rstrip("/")
    except Exception:
        pass
    return "http://localhost:8080"

BASE_URL            = _load_base_url()
CLIENT_LOGIN_URL    = os.getenv("CLIENT_LOGIN_URL", BASE_URL + "/area-clienti")
PWA_VERSION         = "2.0"
_SSL_CTX            = ssl.create_default_context()   # verifica certificati HTTPS
CORS_ORIGIN         = BASE_URL.rstrip('/')

def _load_anthropic_key() -> str:
    if os.getenv("ANTHROPIC_API_KEY"):
        return os.getenv("ANTHROPIC_API_KEY")
    try:
        with open(os.path.join(BASE_DIR, "config.json")) as _f:
            return json.load(_f).get("social", {}).get("anthropic", {}).get("api_key", "")
    except Exception:
        return ""

ANTHROPIC_API_KEY = _load_anthropic_key()
# ─────────────────────────────────────────────────────────────────────────────
# GO-LIVE CHECKLIST — un solo file da modificare: config.json
#   "base_url": "https://www.fuerteventurecapital.com"
# Oppure variabile d'ambiente: BASE_URL=https://www.fuerteventurecapital.com
# ─────────────────────────────────────────────────────────────────────────────

def _get_token(handler):
    for part in handler.headers.get('Cookie', '').split(';'):
        k, _, v = part.strip().partition('=')
        if k.strip() == 'rt_admin':
            raw = v.strip()
            return hashlib.sha256(raw.encode()).hexdigest() if raw else None
    return None

def _is_auth(handler):
    tok = _get_token(handler)
    if tok not in SESSIONS:
        return False
    if time.time() - SESSIONS[tok] > ADMIN_SESSION_TIMEOUT:
        SESSIONS.pop(tok, None)
        return False
    return True

def _redirect(handler, location):
    handler.send_response(302)
    handler.send_header('Location', location)
    handler.end_headers()

def _do_login(handler):
    token = secrets.token_hex(20)
    SESSIONS[hashlib.sha256(token.encode()).hexdigest()] = time.time()
    _persist_sessions()
    handler.send_response(302)
    handler.send_header('Location', '/admin')
    handler.send_header('Set-Cookie', f'rt_admin={token}; Path=/; HttpOnly; SameSite=Strict')
    handler.end_headers()

def _do_logout(handler):
    tok = _get_token(handler)
    if tok:
        SESSIONS.pop(tok, None)
    _persist_sessions()
    handler.send_response(302)
    handler.send_header('Location', '/login')
    handler.send_header('Set-Cookie', 'rt_admin=; Path=/; Max-Age=0')
    handler.end_headers()

# ─── CLIENT AUTH ─────────────────────────────────────────────
def _get_client_token(handler):
    for part in handler.headers.get('Cookie', '').split(';'):
        k, _, v = part.strip().partition('=')
        if k.strip() == 'rt_client':
            raw = v.strip()
            return hashlib.sha256(raw.encode()).hexdigest() if raw else None
    return None

def _is_client_auth(handler):
    tok = _get_client_token(handler)
    if tok not in CLIENT_SESSIONS:
        return False
    if time.time() - CLIENT_SESSION_TIMES.get(tok, 0) > CLIENT_SESSION_TIMEOUT:
        CLIENT_SESSIONS.pop(tok, None)
        CLIENT_SESSION_TIMES.pop(tok, None)
        return False
    CLIENT_SESSION_TIMES[tok] = time.time()  # finestra scorrevole
    return True

def _do_client_login(handler, email, must_change=False, next_url=''):
    token = secrets.token_hex(20)
    _tkey = hashlib.sha256(token.encode()).hexdigest()
    CLIENT_SESSIONS[_tkey] = email
    CLIENT_SESSION_TIMES[_tkey] = time.time()
    _persist_sessions()
    if must_change:
        dest = '/cambia-password'
    elif next_url and next_url.startswith('/') and not next_url.startswith('//'):
        dest = next_url
    else:
        dest = '/area-clienti'
    handler.send_response(302)
    handler.send_header('Location', dest)
    handler.send_header('Set-Cookie', f'rt_client={token}; Path=/; HttpOnly; SameSite=Strict')
    handler.end_headers()

def _do_client_logout(handler):
    tok = _get_client_token(handler)
    if tok:
        CLIENT_SESSIONS.pop(tok, None)
        CLIENT_SESSION_TIMES.pop(tok, None)
    _persist_sessions()
    handler.send_response(302)
    handler.send_header('Location', '/client-login')
    handler.send_header('Set-Cookie', 'rt_client=; Path=/; Max-Age=0')
    handler.end_headers()

# ─── PASSWORD + EMAIL CREDENZIALI B2C ────────────────────────
def _genera_password(n=10):
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(n))

def _hash_pwd(pwd):
    import bcrypt
    return bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()

def _verify_pwd(pwd, stored_hash):
    """Verifica password: supporta bcrypt (nuovo) e SHA256 legacy."""
    import bcrypt
    if stored_hash.startswith('$2b$') or stored_hash.startswith('$2a$'):
        try:
            return bcrypt.checkpw(pwd.encode(), stored_hash.encode())
        except Exception:
            return False
    return hashlib.sha256(pwd.encode()).hexdigest() == stored_hash

def _piani_label(c):
    parts = []
    for asset in ['azioni','etf','fondi','ordini']:
        piano = c.get(f'piano_{asset}','NONE')
        if piano and piano != 'NONE':
            parts.append(f"{asset.upper()} {piano}")
    return ', '.join(parts) if parts else 'Nessun piano attivo'

def _invia_email_credenziali(nome, email, piani_label, password_temp, pdf_bytes=None, numero_fattura=None):
    if not BREVO_SMTP_LOGIN or not BREVO_SMTP_PASSWORD:
        print(f"[EMAIL] BREVO_SMTP_LOGIN non configurato — email NON inviata a {email}", flush=True)
        return False
    logo_src   = f"data:image/png;base64,{FUERTE_LOGO_B64}"
    profilo_url = f"{BASE_URL}/profilo-investitore"
    corpo = f"""<!DOCTYPE html>
<html lang="it">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0a0f1e;font-family:Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0f1e;padding:32px 0">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0"
           style="background:#111827;border-radius:12px;overflow:hidden;border:1px solid rgba(246,173,85,.2)">
      <tr>
        <td style="background:#2C5282;padding:24px 40px;text-align:center">
          <img src="{logo_src}" alt="Fuerte Venture Capital" width="220"
               style="display:block;margin:0 auto;max-width:220px">
          <div style="font-size:12px;color:rgba(255,255,255,.6);margin-top:8px;letter-spacing:1px">Area Riservata Investitori</div>
        </td>
      </tr>
      <tr>
        <td style="padding:36px 40px">
          <p style="color:#e0e0e0;font-size:15px;margin:0 0 16px">Ciao <strong style="color:#F6AD55">{nome}</strong>,</p>
          <p style="color:#aaa;font-size:14px;line-height:1.7;margin:0 0 24px">
            Il tuo accesso all'Area Riservata di <strong>Fuerte Venture Capital</strong> è stato attivato.<br>
            Trovi qui sotto le credenziali per accedere ai report settimanali del tuo screener.
          </p>
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="background:#0a0f1e;border-radius:8px;border:1px solid rgba(255,255,255,.08);margin-bottom:28px">
            <tr>
              <td style="padding:14px 20px;border-bottom:1px solid rgba(255,255,255,.06)">
                <div style="font-size:11px;color:#888;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px">Piano attivo</div>
                <div style="font-size:14px;color:#F6AD55;font-weight:600">{piani_label}</div>
              </td>
            </tr>
            <tr>
              <td style="padding:14px 20px;border-bottom:1px solid rgba(255,255,255,.06)">
                <div style="font-size:11px;color:#888;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px">Email di accesso</div>
                <div style="font-size:14px;color:#e0e0e0">{email}</div>
              </td>
            </tr>
            <tr>
              <td style="padding:14px 20px">
                <div style="font-size:11px;color:#888;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px">Password temporanea</div>
                <div style="font-size:18px;font-weight:700;font-family:monospace;color:#68D391;letter-spacing:2px;background:rgba(104,211,145,.1);padding:8px 14px;border-radius:6px;display:inline-block">{password_temp}</div>
              </td>
            </tr>
          </table>
          <div style="text-align:center;margin-bottom:28px">
            <a href="{CLIENT_LOGIN_URL}"
               style="background:#F6AD55;color:#0a0f1e;padding:14px 40px;border-radius:8px;
                      text-decoration:none;font-weight:700;font-size:15px;display:inline-block">
              Accedi all'Area Riservata
            </a>
          </div>
          <div style="background:linear-gradient(135deg,#1a2744,#0d1b35);border:1px solid rgba(159,122,234,.35);border-radius:10px;padding:18px 22px;margin-bottom:24px">
            <div style="font-size:11px;color:#9F7AEA;font-weight:700;text-transform:uppercase;letter-spacing:.8px;margin-bottom:8px">🧠 Primo passo consigliato</div>
            <p style="margin:0 0 10px;font-size:13px;color:#c0cce0;line-height:1.65">
              Compila il tuo <strong style="color:#e0e0e0">Profilo Investitore MiFID II</strong> — 7 domande, meno di 3 minuti.<br>
              Scopri la tua allocazione ideale tra Liquidità, Obbligazioni, ETF, Azioni, Oro e Fondi.
            </p>
            <div style="text-align:center">
              <a href="{profilo_url}"
                 style="background:linear-gradient(135deg,#9F7AEA,#805AD5);color:#fff;
                        padding:11px 28px;border-radius:7px;text-decoration:none;
                        font-weight:700;font-size:13px;display:inline-block">
                Scopri il mio Profilo Investitore &rarr;
              </a>
            </div>
            <p style="margin:8px 0 0;font-size:10px;color:#445;text-align:center">A scopo informativo &middot; non costituisce consulenza finanziaria (MiFID II)</p>
          </div>
          <p style="font-size:12px;color:#666;border-top:1px solid rgba(255,255,255,.06);padding-top:16px;margin:0 0 20px">
            Conserva questa email. Se non riesci ad accedere scrivi a
            <a href="mailto:info@fuerteventurecapital.com" style="color:#F6AD55">info@fuerteventurecapital.com</a>
          </p>
          <div style="background:rgba(246,173,85,.04);border:1px solid rgba(246,173,85,.12);border-radius:8px;padding:14px 18px;font-size:11px;color:#666;line-height:1.7;margin-bottom:20px">
            <strong style="color:#8899aa;display:block;margin-bottom:6px;text-transform:uppercase;letter-spacing:.8px;font-size:10px">⚠ SaaS · Non Consulenza Finanziaria</strong>
            I report di Fuerte Screener sono generati automaticamente a scopo esclusivamente informativo e <strong style="color:#aaa">non costituiscono consulenza finanziaria</strong>, raccomandazione di investimento o sollecitazione all'acquisto/vendita di strumenti finanziari. Gli investimenti comportano rischi, inclusa la possibile perdita del capitale investito. Prima di qualsiasi decisione, consulta un consulente finanziario abilitato.
          </div>
          <div style="font-size:10px;color:#555;line-height:1.7">
            I tuoi dati personali sono trattati da <strong style="color:#667">Fuerte Venture Capital SL</strong> in qualità di Titolare del trattamento ai sensi del Regolamento UE 2016/679 (GDPR). Hai il diritto di accedere, rettificare o cancellare i tuoi dati scrivendo a <a href="mailto:info@fuerteventurecapital.com" style="color:#F6AD55;text-decoration:none">info@fuerteventurecapital.com</a>.
          </div>
        </td>
      </tr>
      <tr>
        <td style="background:#0F172A;padding:18px 24px;text-align:center;font-size:11px;color:#556;line-height:1.9">
          <strong style="color:#8899aa">Fuerte Venture Capital SL</strong> &middot; CIF B23881691<br>
          Calle Puipana 3, 35640 Villaverde, Las Palmas, España<br>
          <a href="mailto:info@fuerteventurecapital.com" style="color:#F6AD55;text-decoration:none">info@fuerteventurecapital.com</a>
          &nbsp;&middot;&nbsp;
          <a href="https://www.fuerteventurecapital.com" style="color:#F6AD55;text-decoration:none">fuerteventurecapital.com</a><br>
          <span style="font-size:10px;color:#445">© 2026 Fuerte Venture Capital SL. All rights reserved.</span>
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body></html>"""
    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = "Fuerte Venture Capital — Credenziali Area Riservata"
        msg["From"] = f"{BREVO_SENDER_NAME} <{BREVO_SENDER_EMAIL}>"
        msg["To"] = f"{nome} <{email}>"
        msg.attach(MIMEText(corpo, "html", "utf-8"))
        if pdf_bytes and numero_fattura:
            part = MIMEBase("application", "pdf")
            part.set_payload(pdf_bytes)
            email_encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="Fattura_{numero_fattura}.pdf"')
            msg.attach(part)
        with smtplib.SMTP(BREVO_SMTP_HOST, BREVO_SMTP_PORT, timeout=15) as srv:
            srv.ehlo(); srv.starttls()
            srv.login(BREVO_SMTP_LOGIN, BREVO_SMTP_PASSWORD)
            srv.sendmail(BREVO_SENDER_EMAIL, [email], msg.as_string())
        print(f"[EMAIL] Credenziali inviate a {email}", flush=True)
        return True
    except Exception as e:
        print(f"[EMAIL] Errore invio a {email}: {e}", flush=True)
        return False


def _invia_email_nuovo_piano(nome, email, asset_label, livello, pdf_bytes=None, numero_fattura=None):
    """Email di conferma attivazione/upgrade piano con fattura allegata."""
    if not BREVO_SMTP_LOGIN or not BREVO_SMTP_PASSWORD:
        print(f"[EMAIL] SMTP non configurato — email nuovo piano NON inviata a {email}", flush=True)
        return False
    logo_src = f"data:image/png;base64,{FUERTE_LOGO_B64}"
    asset_icons = {'azioni':'📈','etf':'📦','fondi':'🏦','ordini':'📋'}
    icon = asset_icons.get(asset_label.lower(), '📊')
    corpo = f"""<!DOCTYPE html>
<html lang="it">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0a0f1e;font-family:Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0f1e;padding:32px 0">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0"
           style="background:#111827;border-radius:12px;overflow:hidden;border:1px solid rgba(246,173,85,.2)">
      <tr>
        <td style="background:#2C5282;padding:24px 40px;text-align:center">
          <img src="{logo_src}" alt="Fuerte Venture Capital" width="220" style="display:block;margin:0 auto;max-width:220px">
          <div style="font-size:12px;color:rgba(255,255,255,.6);margin-top:8px;letter-spacing:1px">Conferma attivazione servizio</div>
        </td>
      </tr>
      <tr>
        <td style="padding:36px 40px">
          <p style="color:#e0e0e0;font-size:15px;margin:0 0 16px">Ciao <strong style="color:#F6AD55">{nome}</strong>,</p>
          <p style="color:#aaa;font-size:14px;line-height:1.7;margin:0 0 24px">
            Il tuo nuovo piano è stato attivato con successo. Trovi tutti i dettagli qui sotto
            e la fattura allegata a questa email.
          </p>
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="background:#0a0f1e;border-radius:8px;border:1px solid rgba(255,255,255,.08);margin-bottom:28px">
            <tr>
              <td style="padding:14px 20px;border-bottom:1px solid rgba(255,255,255,.06)">
                <div style="font-size:11px;color:#888;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px">Servizio attivato</div>
                <div style="font-size:16px;color:#F6AD55;font-weight:700">{icon} {asset_label}</div>
              </td>
            </tr>
            <tr>
              <td style="padding:14px 20px;border-bottom:1px solid rgba(255,255,255,.06)">
                <div style="font-size:11px;color:#888;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px">Livello piano</div>
                <div style="font-size:15px;color:#68D391;font-weight:700">{livello}</div>
              </td>
            </tr>
            <tr>
              <td style="padding:14px 20px">
                <div style="font-size:11px;color:#888;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px">Account</div>
                <div style="font-size:14px;color:#e0e0e0">{email}</div>
              </td>
            </tr>
          </table>
          <div style="text-align:center;margin-bottom:28px">
            <a href="{CLIENT_LOGIN_URL}"
               style="background:#F6AD55;color:#0a0f1e;padding:14px 40px;border-radius:8px;
                      text-decoration:none;font-weight:700;font-size:15px;display:inline-block">
              Vai all'Area Riservata
            </a>
          </div>
          <p style="font-size:12px;color:#666;border-top:1px solid rgba(255,255,255,.06);padding-top:16px;margin:0 0 20px">
            Per qualsiasi domanda scrivi a
            <a href="mailto:info@fuerteventurecapital.com" style="color:#F6AD55">info@fuerteventurecapital.com</a>
          </p>
          <div style="font-size:10px;color:#555;line-height:1.7">
            I tuoi dati personali sono trattati da <strong style="color:#667">Fuerte Venture Capital SL</strong>
            ai sensi del Reg. UE 2016/679 (GDPR).
            Diritto di accesso/cancellazione: <a href="mailto:info@fuerteventurecapital.com" style="color:#F6AD55;text-decoration:none">info@fuerteventurecapital.com</a>.
          </div>
        </td>
      </tr>
      <tr>
        <td style="background:#0F172A;padding:18px 24px;text-align:center;font-size:11px;color:#556;line-height:1.9">
          <strong style="color:#8899aa">Fuerte Venture Capital SL</strong> &middot; CIF B23881691<br>
          Calle Puipana 3, 35640 Villaverde, Las Palmas, España<br>
          <a href="mailto:info@fuerteventurecapital.com" style="color:#F6AD55;text-decoration:none">info@fuerteventurecapital.com</a>
          &nbsp;&middot;&nbsp;
          <a href="https://www.fuerteventurecapital.com" style="color:#F6AD55;text-decoration:none">fuerteventurecapital.com</a><br>
          <span style="font-size:10px;color:#445">© 2026 Fuerte Venture Capital SL. All rights reserved.</span>
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body></html>"""
    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = f"Fuerte Venture Capital — Nuovo piano attivato: {asset_label} {livello}"
        msg["From"]    = f"{BREVO_SENDER_NAME} <{BREVO_SENDER_EMAIL}>"
        msg["To"]      = f"{nome} <{email}>"
        msg.attach(MIMEText(corpo, "html", "utf-8"))
        if pdf_bytes and numero_fattura:
            part = MIMEBase("application", "pdf")
            part.set_payload(pdf_bytes)
            email_encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="Fattura_{numero_fattura}.pdf"')
            msg.attach(part)
        with smtplib.SMTP(BREVO_SMTP_HOST, BREVO_SMTP_PORT, timeout=15) as srv:
            srv.ehlo(); srv.starttls()
            srv.login(BREVO_SMTP_LOGIN, BREVO_SMTP_PASSWORD)
            srv.sendmail(BREVO_SENDER_EMAIL, [email], msg.as_string())
        print(f"[EMAIL] Nuovo piano {asset_label}/{livello} inviato a {email}", flush=True)
        return True
    except Exception as e:
        print(f"[EMAIL] Errore invio nuovo piano a {email}: {e}", flush=True)
        return False


def _invia_email_early_adopter(nome, email, piani_list):
    """Email offerta early adopter ai Tester via Brevo API (no SMTP)."""
    api_key = _brevo_api_key()
    if not api_key:
        print(f"[EMAIL] Brevo API key mancante — early adopter NON inviato a {email}", flush=True)
        return False
    piani_rows = ""
    totale_pieno = 0.0
    totale_scontato = 0.0
    for p in piani_list:
        pp = float(p['prezzo_pieno'])
        ps = round(pp * 0.5, 2)
        totale_pieno += pp
        totale_scontato += ps
        piani_rows += (
            f'<tr>'
            f'<td style="padding:10px 16px;border-bottom:1px solid rgba(255,255,255,.06);color:#e0e0e0;font-size:14px">{p["tipo"]}</td>'
            f'<td style="padding:10px 16px;border-bottom:1px solid rgba(255,255,255,.06);color:#68D391;font-size:14px;text-align:center">{p["livello"]}</td>'
            f'<td style="padding:10px 16px;border-bottom:1px solid rgba(255,255,255,.06);color:#888;font-size:14px;text-align:right;text-decoration:line-through">€{pp:.0f}/mese</td>'
            f'<td style="padding:10px 16px;border-bottom:1px solid rgba(255,255,255,.06);color:#F6AD55;font-size:14px;font-weight:700;text-align:right">€{ps:.2f}/mese</td>'
            f'</tr>'
        )
    corpo = f"""<!DOCTYPE html>
<html lang="it"><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0a0f1e;font-family:Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0f1e;padding:32px 0">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0"
       style="background:#111827;border-radius:12px;overflow:hidden;border:1px solid rgba(246,173,85,.2)">
  <tr>
    <td style="background:#2C5282;padding:24px 40px;text-align:center">
      <div style="font-size:22px;font-weight:700;color:#F6AD55;letter-spacing:2px">FUERTE VENTURE CAPITAL</div>
      <div style="font-size:12px;color:rgba(255,255,255,.6);margin-top:8px;letter-spacing:1px">OFFERTA RISERVATA EARLY ADOPTER</div>
    </td>
  </tr>
  <tr><td style="padding:36px 40px">
    <p style="color:#e0e0e0;font-size:15px;margin:0 0 16px">Ciao <strong style="color:#F6AD55">{nome}</strong>,</p>
    <p style="color:#aaa;font-size:14px;line-height:1.7;margin:0 0 24px">
      Sei stato tra i <strong style="color:#e0e0e0">primissimi</strong> a testare Robot Trader 2026.<br>
      Da questa settimana il servizio è ufficialmente <strong style="color:#68D391">live</strong>.
    </p>
    <div style="background:rgba(246,173,85,.08);border:1px solid rgba(246,173,85,.3);border-radius:8px;padding:16px 20px;margin-bottom:24px">
      <div style="font-size:13px;color:#F6AD55;font-weight:700;margin-bottom:6px">⭐ OFFERTA EARLY ADOPTER — scade il 1° settembre 2026</div>
      <div style="font-size:14px;color:#e0e0e0;line-height:1.7">
        <strong>Primi 3 mesi al 50%</strong> sui piani che stai già usando.<br>
        Poi il prezzo standard — nessun rincaro a sorpresa.
      </div>
    </div>
    <table width="100%" cellpadding="0" cellspacing="0"
           style="background:#0a0f1e;border-radius:8px;border:1px solid rgba(255,255,255,.08);margin-bottom:28px">
      <tr style="background:rgba(255,255,255,.04)">
        <th style="padding:10px 16px;text-align:left;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px">Screener</th>
        <th style="padding:10px 16px;text-align:center;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px">Piano</th>
        <th style="padding:10px 16px;text-align:right;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px">Prezzo pieno</th>
        <th style="padding:10px 16px;text-align:right;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px">Il tuo prezzo</th>
      </tr>
      {piani_rows}
      <tr style="background:rgba(246,173,85,.06)">
        <td colspan="2" style="padding:12px 16px;font-size:14px;color:#e0e0e0;font-weight:700">Totale mensile (× 3 mesi)</td>
        <td style="padding:12px 16px;text-align:right;color:#888;font-size:14px;text-decoration:line-through">€{totale_pieno:.0f}/mese</td>
        <td style="padding:12px 16px;text-align:right;color:#F6AD55;font-size:16px;font-weight:700">€{totale_scontato:.2f}/mese</td>
      </tr>
    </table>
    <div style="text-align:center;margin-bottom:28px">
      <a href="mailto:info@fuerteventurecapital.com?subject=Attivazione%20Early%20Adopter"
         style="background:#F6AD55;color:#0a0f1e;padding:14px 40px;border-radius:8px;font-weight:700;font-size:15px;text-decoration:none;display:inline-block">
        ✉️ Attiva l'offerta — rispondi a questa email
      </a>
    </div>
    <p style="color:#666;font-size:12px;text-align:center;margin:0">
      Nessuna carta di credito richiesta ora. Ti contatteremo entro 24 ore.
    </p>
  </td></tr>
  <tr>
    <td style="background:#0a0f1e;padding:20px 40px;text-align:center;border-top:1px solid rgba(255,255,255,.06)">
      <p style="color:#555;font-size:11px;margin:0">Fuerte Venture Capital SL — CIF B23881691<br>
      marketing@fuerteventurecapital.com · {BASE_URL}</p>
    </td>
  </tr>
</table>
</td></tr></table>
</body></html>"""
    try:
        import urllib.request as _ur
        payload = json.dumps({
            "sender":      {"name": BREVO_SENDER_NAME, "email": BREVO_SENDER_EMAIL},
            "to":          [{"email": email, "name": nome}],
            "replyTo":     {"email": "info@fuerteventurecapital.com"},
            "subject":     "Robot Trader 2026 è live — la tua offerta riservata",
            "htmlContent": corpo,
        }).encode("utf-8")
        req = _ur.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=payload,
            headers={"api-key": api_key, "Content-Type": "application/json", "Accept": "application/json"},
        )
        with _ur.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            status = resp.status
        if status in (200, 201):
            print(f"[EMAIL] Early adopter inviato a {email} (Brevo API {status})", flush=True)
            return True
        print(f"[EMAIL] Brevo API {status} per {email}", flush=True)
        return False
    except Exception as e:
        print(f"[EMAIL] Errore early adopter a {email}: {e}", flush=True)
        return False


def _send_early_adopter_blast():
    """Invia email early adopter a tutti i Tester (escluso account interno)."""
    PREZZI = {
        ('azioni','BASIC'):29,('azioni','PRO'):39,('azioni','VALUE'):59,
        ('etf','BASIC'):29,('etf','PRO'):39,('etf','VALUE'):59,
        ('fondi','BASIC'):29,('fondi','PRO'):39,('fondi','VALUE'):59,
        ('ordini','BASIC'):19,('ordini','PRO'):29,('ordini','VALUE'):49,
    }
    ASSET_LABEL = {'azioni':'📈 Azioni','etf':'📦 ETF','fondi':'🏦 Fondi','ordini':'📋 Ordini'}
    SKIP = {'marketing@fuerteventurecapital.com'}
    try:
        with open(CLIENTI_FILE, encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return {'ok': False, 'msg': str(e)}
    risultati = []
    for tester in data.get('tester', []):
        email = (tester.get('email') or '').strip()
        if not email or email in SKIP:
            continue
        nome = tester.get('nome', email.split('@')[0])
        piani_list = []
        for asset in ('azioni','etf','fondi','ordini'):
            livello = (tester.get(f'piano_{asset}') or 'NONE').upper()
            if livello != 'NONE':
                prezzo = PREZZI.get((asset, livello), 0)
                if prezzo:
                    piani_list.append({'tipo': ASSET_LABEL[asset], 'livello': livello, 'prezzo_pieno': prezzo})
        if not piani_list:
            risultati.append({'email': email, 'ok': False, 'msg': 'nessun piano'})
            continue
        ok = _invia_email_early_adopter(nome, email, piani_list)
        risultati.append({'email': email, 'nome': nome, 'ok': ok, 'piani': len(piani_list)})
    inviati = sum(1 for r in risultati if r.get('ok'))
    return {'ok': True, 'inviati': inviati, 'totale': len(risultati), 'dettaglio': risultati}


def _brevo_import_prospect():
    """Crea lista Brevo e importa i prospect (Da Contattare + Prospect LinkedIn) via API bulk."""
    import io as _io, csv as _csv
    from datetime import date as _date

    # 1. Carica prospect eleggibili
    items = read_prospect()
    eleggibili = [p for p in items if p.get('stato') in ('Da Contattare', 'Prospect LinkedIn') and p.get('email')]
    if not eleggibili:
        return {'ok': False, 'msg': 'Nessun prospect eleggibile (stato Da Contattare o Prospect LinkedIn con email)'}

    # 2. Crea lista Brevo (senza folderId — opzionale, causa 400 se cartella non esiste)
    nome_lista = f'Prospect Lancio {_date.today().strftime("%Y-%m-%d")}'
    lista_data, lista_status = _brevo_call('/contacts/lists', method='POST', payload={'name': nome_lista})
    if lista_status == 0:
        return {'ok': False, 'msg': 'Brevo API key non configurata'}
    if lista_status not in (200, 201):
        # potrebbe già esistere — cerca lista esistente con stesso nome
        liste_data, _ = _brevo_call('/contacts/lists?limit=50&sort=desc')
        lista_id = None
        for l in (liste_data.get('lists') or []):
            if l.get('name') == nome_lista:
                lista_id = l['id']
                break
        if not lista_id:
            return {'ok': False, 'msg': f'Errore creazione lista Brevo HTTP {lista_status}', 'detail': lista_data}
    else:
        lista_id = lista_data.get('id')

    # 3. Genera CSV — Brevo fileBody richiede punto e virgola come separatore
    buf = _io.StringIO()
    writer = _csv.writer(buf, delimiter=';', quoting=_csv.QUOTE_MINIMAL)
    writer.writerow(['EMAIL', 'FIRSTNAME', 'LASTNAME', 'SMS'])
    for p in eleggibili:
        email = (p.get('email') or '').strip()
        if not email or '@' not in email:
            continue
        writer.writerow([
            email,
            (p.get('nome') or '').strip(),
            (p.get('cognome') or '').strip(),
            (p.get('telefono') or '').strip(),
        ])
    csv_text = buf.getvalue()
    print(f'[BREVO] CSV prime 2 righe:\n{chr(10).join(csv_text.splitlines()[:2])}', flush=True)

    # 4. Import bulk — fileBody è testo CSV grezzo (non base64)
    payload = {
        'fileBody': csv_text,
        'listIds': [lista_id],
        'updateExistingContacts': True,
        'emptyContactsAttributes': False,
    }
    imp_data, imp_status = _brevo_call('/contacts/import', method='POST', payload=payload)
    print(f'[BREVO] Import response HTTP {imp_status}: {imp_data}', flush=True)
    if imp_status in (200, 201, 202):
        process_id = imp_data.get('processId') or imp_data.get('id')
        print(f'[BREVO] Import avviato: {len(eleggibili)} prospect → lista "{nome_lista}" (ID {lista_id}), processId={process_id}', flush=True)
        return {'ok': True, 'totale': len(eleggibili), 'lista_id': lista_id, 'lista_nome': nome_lista, 'process_id': process_id}
    return {'ok': False, 'msg': f'Brevo import HTTP {imp_status}', 'detail': imp_data}


def _html_email_lancio():
    """HTML email di lancio per i 2.435 prospect. Compatibile con client email (inline styles, table layout)."""
    BASE = os.getenv('BASE_URL', 'https://www.fuerteventurecapital.com')
    url_registrazione = f'{BASE}/register'
    return f"""<!DOCTYPE html>
<html lang="it">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:Arial,Helvetica,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:24px 0">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#0a0f1e;border-radius:12px;overflow:hidden">

  <!-- HEADER -->
  <tr><td style="background:#0a0f1e;padding:32px 40px 20px;text-align:center;border-bottom:1px solid rgba(246,173,85,.25)">
    <div style="font-size:11px;letter-spacing:3px;color:rgba(246,173,85,.6);text-transform:uppercase;margin-bottom:8px">Fuerte Venture Capital</div>
    <div style="font-size:26px;font-weight:900;color:#ffffff;letter-spacing:-1px">ROBOT TRADER <span style="color:#F6AD55">2026</span></div>
    <div style="font-size:12px;color:rgba(255,255,255,.4);margin-top:6px;letter-spacing:1px">SCREENER QUANTITATIVO</div>
  </td></tr>

  <!-- HERO -->
  <tr><td style="padding:36px 40px 28px;text-align:center">
    <div style="font-size:22px;font-weight:700;color:#ffffff;line-height:1.35;margin-bottom:14px">
      Il primo screener quantitativo<br>per il <span style="color:#F6AD55">deep value investing</span>
    </div>
    <div style="font-size:14px;color:rgba(255,255,255,.6);line-height:1.7">
      Ogni notte i nostri algoritmi analizzano <strong style="color:#F6AD55">10.086 asset globali</strong><br>
      e selezionano i titoli con i migliori fondamentali.<br>
      Il mattino dopo trovi il report direttamente nella tua inbox.
    </div>
  </td></tr>

  <!-- NUMERI -->
  <tr><td style="padding:0 40px 28px">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td width="33%" style="text-align:center;padding:16px 8px;background:rgba(246,173,85,.07);border-radius:8px;border:1px solid rgba(246,173,85,.2)">
          <div style="font-size:22px;font-weight:900;color:#F6AD55">2.621</div>
          <div style="font-size:11px;color:rgba(255,255,255,.5);margin-top:4px">📈 Azioni<br>17 mercati</div>
        </td>
        <td width="4%"></td>
        <td width="33%" style="text-align:center;padding:16px 8px;background:rgba(104,211,145,.07);border-radius:8px;border:1px solid rgba(104,211,145,.2)">
          <div style="font-size:22px;font-weight:900;color:#68D391">5.730</div>
          <div style="font-size:11px;color:rgba(255,255,255,.5);margin-top:4px">📦 ETF<br>US + EU</div>
        </td>
        <td width="4%"></td>
        <td width="33%" style="text-align:center;padding:16px 8px;background:rgba(96,165,250,.07);border-radius:8px;border:1px solid rgba(96,165,250,.2)">
          <div style="font-size:22px;font-weight:900;color:#60a5fa">1.735</div>
          <div style="font-size:11px;color:rgba(255,255,255,.5);margin-top:4px">🏦 Fondi<br>US + UCITS</div>
        </td>
      </tr>
    </table>
  </td></tr>

  <!-- COME FUNZIONA -->
  <tr><td style="padding:0 40px 28px">
    <div style="background:rgba(255,255,255,.04);border-radius:8px;padding:20px 24px;border-left:3px solid #F6AD55">
      <div style="font-size:13px;font-weight:700;color:#F6AD55;letter-spacing:1px;text-transform:uppercase;margin-bottom:12px">Come funziona</div>
      <div style="font-size:13px;color:rgba(255,255,255,.75);line-height:1.8">
        ✅ &nbsp;Ogni notte lo screener gira su 10.086 asset globali<br>
        ✅ &nbsp;Filtra per EV/FCF, P/B, ROE e Net Debt/EBITDA<br>
        ✅ &nbsp;Calcola un <strong style="color:#fff">score di qualità</strong> e genera il ranking<br>
        ✅ &nbsp;Il report ti arriva via email pronto per le decisioni di investimento
      </div>
    </div>
  </td></tr>

  <!-- PIANI -->
  <tr><td style="padding:0 40px 28px">
    <div style="font-size:13px;font-weight:700;color:rgba(255,255,255,.5);letter-spacing:1px;text-transform:uppercase;margin-bottom:14px;text-align:center">Scegli il piano</div>
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td style="padding:14px 10px;background:rgba(255,255,255,.04);border-radius:8px;text-align:center;border:1px solid rgba(255,255,255,.08)">
          <div style="font-size:11px;letter-spacing:2px;color:rgba(255,255,255,.4);text-transform:uppercase">Basic</div>
          <div style="font-size:24px;font-weight:900;color:#fff;margin:6px 0">€29<span style="font-size:12px;color:rgba(255,255,255,.4)">/mese</span></div>
          <div style="font-size:11px;color:rgba(255,255,255,.5)">Azioni · ETF · Fondi</div>
        </td>
        <td width="6%"></td>
        <td style="padding:14px 10px;background:rgba(246,173,85,.08);border-radius:8px;text-align:center;border:1px solid rgba(246,173,85,.3)">
          <div style="font-size:11px;letter-spacing:2px;color:#F6AD55;text-transform:uppercase">Pro</div>
          <div style="font-size:24px;font-weight:900;color:#F6AD55;margin:6px 0">€39<span style="font-size:12px;color:rgba(246,173,85,.6)">/mese</span></div>
          <div style="font-size:11px;color:rgba(255,255,255,.5)">Score + 17 mercati</div>
        </td>
        <td width="6%"></td>
        <td style="padding:14px 10px;background:rgba(255,255,255,.04);border-radius:8px;text-align:center;border:1px solid rgba(255,255,255,.08)">
          <div style="font-size:11px;letter-spacing:2px;color:rgba(255,255,255,.4);text-transform:uppercase">Value</div>
          <div style="font-size:24px;font-weight:900;color:#fff;margin:6px 0">€59<span style="font-size:12px;color:rgba(255,255,255,.4)">/mese</span></div>
          <div style="font-size:11px;color:rgba(255,255,255,.5)">Deep value completo</div>
        </td>
      </tr>
    </table>
  </td></tr>

  <!-- CTA -->
  <tr><td style="padding:0 40px 36px;text-align:center">
    <a href="{url_registrazione}" style="display:inline-block;background:#F6AD55;color:#0a0f1e;font-size:15px;font-weight:900;padding:16px 40px;border-radius:8px;text-decoration:none;letter-spacing:.5px">
      Inizia la prova gratuita di 7 giorni →
    </a>
    <div style="font-size:11px;color:rgba(255,255,255,.35);margin-top:12px">
      Nessuna carta di credito · Accesso immediato · Cancellazione in qualsiasi momento
    </div>
  </td></tr>

  <!-- FOOTER -->
  <tr><td style="padding:20px 40px;border-top:1px solid rgba(255,255,255,.08);text-align:center">
    <div style="font-size:11px;color:rgba(255,255,255,.3);line-height:1.8">
      <strong style="color:rgba(255,255,255,.5)">Fuerte Venture Capital SL</strong> — CIF B23881691<br>
      <a href="mailto:marketing@fuerteventurecapital.com" style="color:rgba(246,173,85,.5);text-decoration:none">marketing@fuerteventurecapital.com</a>
      &nbsp;·&nbsp;
      <a href="{BASE}" style="color:rgba(246,173,85,.5);text-decoration:none">fuerteventurecapital.com</a><br>
      <span style="margin-top:8px;display:block">
        Hai ricevuto questa email perché il tuo contatto è presente nel nostro database prospect.<br>
        <a href="{{{{ unsubscribe }}}}" style="color:rgba(255,255,255,.25);text-decoration:underline">Cancella iscrizione</a>
      </span>
    </div>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


# ─── FATTURE ────────────────────────────────────────────────────────────────

def _calc_analytics():
    from datetime import date as _date
    try:
        with open(CLIENTI_FILE, encoding='utf-8') as f:
            raw = json.load(f)
    except Exception:
        raw = {}
    clienti_list = raw.get('clienti', [])
    tester_list  = raw.get('tester',  [])
    try:
        with open(SERVIZI_FILE, encoding='utf-8') as f:
            sv = json.load(f)
    except Exception:
        sv = {}
    def _price(service, plan):
        if not plan or str(plan).upper() == 'NONE':
            return 0
        return sv.get(service, {}).get(str(plan).lower(), {}).get('prezzo', 0)
    PIANI = ['azioni', 'etf', 'fondi', 'ordini']
    attivi  = [c for c in clienti_list if c.get('stato') == 'ATTIVO']
    sospesi = [c for c in clienti_list if c.get('stato') == 'SOSPESO']
    scaduti = [c for c in clienti_list if c.get('stato') == 'SCADUTO']
    tester  = [c for c in tester_list  if c.get('stato') == 'TESTER']
    mrr = 0
    mrr_breakdown = []
    for c in attivi:
        for svc in PIANI:
            plan = c.get(f'piano_{svc}', 'NONE')
            price = _price(svc, plan)
            if price > 0:
                mrr += price
                mrr_breakdown.append({'cliente': c.get('email',''), 'servizio': svc.upper(), 'piano': str(plan).capitalize(), 'importo': price})
    n_attivi  = len(attivi)
    n_tester  = len(tester)
    n_sospesi = len(sospesi)
    n_scaduti = len(scaduti)
    arpu = mrr / n_attivi if n_attivi > 0 else 0
    arr  = mrr * 12
    total_ever = n_attivi + n_sospesi + n_scaduti
    churn_rate = round((n_sospesi + n_scaduti) / total_ever * 100, 1) if total_ever > 0 else 0
    monthly_churn = churn_rate / 100
    ltv = round(arpu / monthly_churn) if monthly_churn > 0 else (round(arpu * 24) if arpu > 0 else 0)
    cumulative = 0
    today = _date.today()
    for c in attivi:
        da = c.get('data_attivazione', '')
        c_mrr = sum(_price(svc, c.get(f'piano_{svc}', 'NONE')) for svc in PIANI)
        if da:
            try:
                d0 = _date.fromisoformat(da)
                months = max(1, round((today - d0).days / 30))
                cumulative += c_mrr * months
            except Exception:
                pass
    try:
        with open(PROSPECT_FILE, encoding='utf-8') as f:
            pr = json.load(f)
        n_da_cont  = sum(1 for p in pr if p.get('stato') == 'Da Contattare')
        n_linkedin = sum(1 for p in pr if p.get('stato') == 'Prospect LinkedIn')
        n_prospect = len(pr)
    except Exception:
        n_prospect, n_da_cont, n_linkedin = 2435, 2386, 49
    arpu_base = arpu if arpu > 0 else 60
    return {
        'mrr': mrr, 'arr': arr, 'arpu': round(arpu, 2), 'ltv': ltv,
        'churn_rate': churn_rate, 'cumulative': cumulative,
        'n_attivi': n_attivi, 'n_tester': n_tester,
        'n_sospesi': n_sospesi, 'n_scaduti': n_scaduti,
        'n_prospect': n_prospect, 'n_da_cont': n_da_cont, 'n_linkedin': n_linkedin,
        'mrr_breakdown': mrr_breakdown,
        'scenari': [
            {'label': 'Pessimistico', 'conv': 0.3, 'n': max(1, round(n_prospect * 0.003)), 'mrr': round(max(1, round(n_prospect * 0.003)) * arpu_base), 'color': '#ef4444'},
            {'label': 'Base',         'conv': 1.0, 'n': max(1, round(n_prospect * 0.01)),  'mrr': round(max(1, round(n_prospect * 0.01))  * arpu_base), 'color': '#60a5fa'},
            {'label': 'Ottimistico',  'conv': 3.0, 'n': max(1, round(n_prospect * 0.03)),  'mrr': round(max(1, round(n_prospect * 0.03))  * arpu_base), 'color': '#68D391'},
            {'label': 'Target 12m',   'conv': 5.0, 'n': max(1, round(n_prospect * 0.05)),  'mrr': round(max(1, round(n_prospect * 0.05))  * arpu_base), 'color': '#F6AD55'},
        ]
    }

def _prossimo_numero_fattura():
    os.makedirs(FATTURE_DIR, exist_ok=True)
    with _fatture_lock:
        try:
            with open(FATTURE_COUNTER, 'r') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {'ultimo': 0}
        data['ultimo'] += 1
        with open(FATTURE_COUNTER, 'w') as f:
            json.dump(data, f)
    return f"FVC-{datetime.now().year}-{data['ultimo']:04d}"


def _salva_fattura(pdf_bytes, numero):
    os.makedirs(FATTURE_DIR, exist_ok=True)
    path = os.path.join(FATTURE_DIR, f"{numero}.pdf")
    with open(path, 'wb') as f:
        f.write(pdf_bytes)
    return path


# ─── ORDINI ARCHIVIO ────────────────────────────────────────────────────────

def _email_to_folder(email: str) -> str:
    safe = email.lower().replace('@', '_at_').replace('.', '_').replace(' ', '_')
    return os.path.join(ORDINI_DIR, safe)

def _salva_ordine(email: str, ordine: dict) -> None:
    folder = _email_to_folder(email)
    os.makedirs(folder, exist_ok=True)
    rif   = ordine.get('riferimento', datetime.now().strftime('ORD-%Y%m%d-%H%M%S'))
    fname = os.path.join(folder, f'{rif}.json')
    with open(fname, 'w', encoding='utf-8') as f:
        json.dump(ordine, f, ensure_ascii=False, indent=2)

def _conti_path(email: str) -> str:
    return os.path.join(_email_to_folder(email), 'conti_bancari.json')

def _load_conti(email: str) -> list:
    path = _conti_path(email)
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def _save_conto(email: str, conto: str) -> None:
    conto = (conto or '').strip()
    if not conto:
        return
    folder = _email_to_folder(email)
    os.makedirs(folder, exist_ok=True)
    conti = _load_conti(email)
    if conto in conti:
        conti.remove(conto)
    conti.insert(0, conto)       # più recente in testa
    with open(_conti_path(email), 'w', encoding='utf-8') as f:
        json.dump(conti[:20], f, ensure_ascii=False)

def _delete_conto(email: str, conto: str) -> None:
    conti = [c for c in _load_conti(email) if c != conto]
    folder = _email_to_folder(email)
    os.makedirs(folder, exist_ok=True)
    with open(_conti_path(email), 'w', encoding='utf-8') as f:
        json.dump(conti, f, ensure_ascii=False)

# ─── Profili banca cliente (banca + iban + gestore + email) ──
def _profili_path(email: str) -> str:
    return os.path.join(_email_to_folder(email), 'profili_banca.json')

def _load_profili(email: str) -> list:
    path = _profili_path(email)
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def _save_profilo(email: str, profilo: dict) -> None:
    iban = (profilo.get('iban') or '').strip().upper().replace(' ', '')
    if not iban:
        return
    folder = _email_to_folder(email)
    os.makedirs(folder, exist_ok=True)
    profili = [p for p in _load_profili(email)
               if (p.get('iban') or '').strip().upper().replace(' ', '') != iban]
    profili.insert(0, profilo)
    with open(_profili_path(email), 'w', encoding='utf-8') as f:
        json.dump(profili[:20], f, ensure_ascii=False)

def _delete_profilo(email: str, iban: str) -> None:
    iban = iban.strip().upper().replace(' ', '')
    profili = [p for p in _load_profili(email)
               if (p.get('iban') or '').strip().upper().replace(' ', '') != iban]
    folder = _email_to_folder(email)
    os.makedirs(folder, exist_ok=True)
    with open(_profili_path(email), 'w', encoding='utf-8') as f:
        json.dump(profili, f, ensure_ascii=False)

def _leggi_ordini_cliente(email: str) -> list:
    folder = _email_to_folder(email)
    if not os.path.isdir(folder):
        return []
    ordini = []
    for fname in sorted(os.listdir(folder), reverse=True):
        if fname.endswith('.json'):
            try:
                with open(os.path.join(folder, fname), encoding='utf-8') as f:
                    ordini.append(json.load(f))
            except Exception:
                pass
    return ordini


def genera_fattura_pdf(cliente, numero_fattura):
    """Genera PDF fattura A4 brandizzata FVC per il cliente appena attivato."""
    sv       = read_servizi()
    nome     = f"{cliente.get('nome','')} {cliente.get('cognome','')}".strip() or cliente.get('email','')
    email_cl = cliente.get('email', '')
    df       = cliente.get('dati_fiscali', {})
    paese    = df.get('paese', '')
    cf       = df.get('codice_fiscale', '')
    piva     = df.get('p_iva', '')
    indirizzo = df.get('indirizzo', '')
    cap      = df.get('cap', '')
    citta    = df.get('citta', '')

    # Dati bancari da config
    try:
        with open(os.path.join(BASE_DIR, 'config.json'), encoding='utf-8') as _fc:
            _fcfg = json.load(_fc).get('fattura', {})
    except Exception:
        _fcfg = {}
    _iban  = _fcfg.get('iban', '')
    _bic   = _fcfg.get('bic', '')
    _banca = _fcfg.get('banca', '')

    righe, totale = [], 0.0
    for asset, label in [('azioni','Screener Azioni'), ('etf','Screener ETF'),
                         ('fondi','Screener Fondi'), ('fondi_eu','Screener Fondi EU UCITS')]:
        piano = cliente.get(f'piano_{asset}', 'NONE').lower()
        if piano and piano != 'none':
            prezzo = float(sv.get(asset, {}).get(piano, {}).get('prezzo', 0))
            if prezzo:
                righe.append({'desc': f'Fuerte Screener - {label}', 'piano': piano.upper(), 'prezzo': prezzo})
                totale += prezzo
    if not righe:
        return None

    data_fattura  = datetime.now().strftime('%d/%m/%Y')
    mese_fattura  = datetime.now().strftime('%B %Y').capitalize()

    BLU   = (44,  82,  130)
    WHITE = (255, 255, 255)
    DARK  = (20,  20,  40)
    GRAY  = (110, 110, 120)
    LGRAY = (243, 244, 248)

    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=22)
    pdf.set_margins(15, 15, 15)

    # Logo
    logo_path = None
    try:
        _b64 = FUERTE_LOGO_B64.strip()
        _b64 += '=' * (-len(_b64) % 4)
        logo_bytes = b64lib.b64decode(_b64)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            f.write(logo_bytes); logo_path = f.name
        pdf.image(logo_path, x=15, y=14, w=54)
    finally:
        if logo_path and os.path.exists(logo_path):
            os.unlink(logo_path)

    # Titolo FATTURA (dx)
    pdf.set_xy(115, 13)
    pdf.set_font('Helvetica', 'B', 28)
    pdf.set_text_color(*BLU)
    pdf.cell(80, 13, 'FATTURA', align='R')

    pdf.set_xy(115, 27)
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(*GRAY)
    pdf.cell(80, 5, f'N.  {numero_fattura}', align='R')
    pdf.set_xy(115, 33)
    pdf.cell(80, 5, f'Data:  {data_fattura}', align='R')

    # Linea blu separatrice
    pdf.set_draw_color(*BLU)
    pdf.set_line_width(0.5)
    pdf.line(15, 46, 195, 46)

    # Fornitore (sx)
    y0 = 50
    pdf.set_xy(15, y0)
    pdf.set_font('Helvetica', 'B', 7)
    pdf.set_text_color(*GRAY)
    pdf.cell(85, 5, 'FORNITORE')
    pdf.set_xy(15, y0+5)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(*DARK)
    pdf.cell(85, 5, 'Fuerte Venture Capital SL')
    for i, r in enumerate(['CIF B23881691', 'Calle Puipana 3, 35640 Villaverde', 'Las Palmas, España', 'info@fuerteventurecapital.com', 'www.fuerteventurecapital.com']):
        pdf.set_xy(15, y0+11+i*4.5)
        pdf.set_font('Helvetica', '', 8.5)
        pdf.set_text_color(*GRAY)
        pdf.cell(85, 4.5, r)

    # Cliente (dx)
    pdf.set_xy(110, y0)
    pdf.set_font('Helvetica', 'B', 7)
    pdf.set_text_color(*GRAY)
    pdf.cell(85, 5, 'INTESTATA A')
    pdf.set_xy(110, y0+5)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(*DARK)
    pdf.cell(85, 5, nome)
    cl_lines = [email_cl]
    if paese:     cl_lines.append(f'Paese: {paese}')
    if cf:        cl_lines.append(f'CF/ID Fiscale: {cf}')
    if piva:      cl_lines.append(f'P.IVA: {piva}')
    if indirizzo: cl_lines.append(indirizzo)
    if cap or citta: cl_lines.append(f'{cap} {citta}'.strip())
    for i, r in enumerate(cl_lines):
        pdf.set_xy(110, y0+11+i*4.5)
        pdf.set_font('Helvetica', '', 8.5)
        pdf.set_text_color(*GRAY)
        pdf.cell(85, 4.5, r)

    # Linea grigia
    y_sep = max(pdf.get_y() + 6, 98)
    pdf.set_draw_color(200, 205, 220)
    pdf.set_line_width(0.3)
    pdf.line(15, y_sep, 195, y_sep)

    # Header tabella
    yt = y_sep + 5
    pdf.set_fill_color(*BLU)
    pdf.set_text_color(*WHITE)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_xy(15, yt)
    pdf.cell(92, 7, '  DESCRIZIONE', fill=True)
    pdf.cell(35, 7, 'PERIODO', fill=True, align='C')
    pdf.cell(15, 7, 'Q.', fill=True, align='C')
    pdf.cell(33, 7, 'IMPORTO', fill=True, align='R')

    # Righe servizi
    yr = yt + 7
    for i, r in enumerate(righe):
        if i % 2 == 0:
            pdf.set_fill_color(*LGRAY)
            pdf.rect(15, yr, 175, 7, style='F')
        pdf.set_xy(15, yr)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(*DARK)
        pdf.cell(92, 7, f"  {r['desc']}  [Piano {r['piano']}]")
        pdf.cell(35, 7, mese_fattura, align='C')
        pdf.cell(15, 7, '1', align='C')
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(33, 7, f"EUR {r['prezzo']:.2f}", align='R')
        yr += 7

    # Separatore
    pdf.set_draw_color(180, 190, 215)
    pdf.set_line_width(0.3)
    pdf.line(15, yr+2, 195, yr+2)

    # Subtotale
    pdf.set_xy(127, yr+5)
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(*GRAY)
    pdf.cell(35, 5.5, 'Subtotale', align='R')
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(33, 5.5, f"EUR {totale:.2f}", align='R')

    pdf.set_xy(127, yr+11)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.cell(35, 5, 'IGIC/IVA (Canarias)', align='R')
    pdf.cell(33, 5, 'per legge vigente', align='R')

    # Box totale
    yt2 = yr + 18
    pdf.set_fill_color(*BLU)
    pdf.rect(127, yt2, 68, 10, style='F')
    pdf.set_xy(127, yt2+1)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(*WHITE)
    pdf.cell(35, 8, 'TOTALE', align='R')
    pdf.cell(33, 8, f"EUR {totale:.2f}", align='R')

    # Sezione bonifico bancario
    yb = yt2 + 14
    pdf.set_draw_color(180, 210, 180)
    pdf.set_line_width(0.25)
    pdf.rect(15, yb, 175, 26, style='D')
    pdf.set_fill_color(237, 247, 237)
    pdf.rect(15, yb, 175, 7, style='F')
    pdf.set_xy(17, yb + 1)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_text_color(34, 100, 34)
    pdf.cell(0, 5, 'MODALITA DI PAGAMENTO  -  Bonifico Bancario')
    _bon_rows = [
        ('Beneficiario', 'Fuerte Venture Capital SL'),
        ('Banca',        _banca or 'CaixaBank SA'),
        ('IBAN',         _iban  or 'DA CONFIGURARE IN config.json'),
        ('BIC/SWIFT',    _bic   or ''),
        ('Causale',      f'Abbonamento Fuerte Screener  |  Rif. {numero_fattura}'),
    ]
    yrow = yb + 8
    for label, val in _bon_rows:
        if not val:
            continue
        pdf.set_xy(17, yrow)
        pdf.set_font('Helvetica', 'B', 7.5)
        pdf.set_text_color(*GRAY)
        pdf.cell(32, 4.5, label + ':')
        pdf.set_font('Helvetica', '', 7.5)
        pdf.set_text_color(*DARK)
        pdf.cell(130, 4.5, val)
        yrow += 4.5

    # Note legali
    yn = yb + 30
    pdf.set_xy(15, yn)
    pdf.set_font('Helvetica', 'B', 7)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 5, 'NOTE LEGALI', new_x='LMARGIN', new_y='NEXT')
    pdf.set_x(15)
    pdf.set_font('Helvetica', '', 7.5)
    pdf.set_text_color(*GRAY)
    pdf.multi_cell(180, 4.2,
        'Fuerte Screener è un servizio SaaS di screening quantitativo automatico. '
        'I report sono esclusivamente informativi e non costituiscono consulenza finanziaria. '
        'Abbonamento mensile - rinnovo automatico salvo disdetta scritta a info@fuerteventurecapital.com. '
        'I dati personali del cliente sono trattati da Fuerte Venture Capital SL in qualità di '
        'Titolare ai sensi del Reg. UE 2016/679 (GDPR). Diritto di accesso/cancellazione: info@fuerteventurecapital.com.')

    # Footer — disabilito auto_page_break per evitare pagina extra
    pdf.set_auto_page_break(auto=False)
    pdf.set_y(-16)
    pdf.set_draw_color(*BLU)
    pdf.set_line_width(0.4)
    pdf.line(15, pdf.get_y()-2, 195, pdf.get_y()-2)
    pdf.set_font('Helvetica', '', 7)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 5,
        'Fuerte Venture Capital SL  ·  CIF B23881691  ·  Calle Puipana 3, 35640 Villaverde, Las Palmas, España'
        '  ·  info@fuerteventurecapital.com  ·  www.fuerteventurecapital.com',
        align='C')

    return bytes(pdf.output())


DEFAULT_SERVIZI = {
    "azioni": {
        "basic": {"prezzo":29,"status":"attivo","parametri":{"ev_fcf_max":12.0,"price_book_max":1.2,"roe_min":0.0,"net_debt_ebitda_max":2.5}},
        "pro":   {"prezzo":39,"status":"attivo","parametri":{"ev_fcf_max":12.0,"price_book_max":1.2,"roe_min":0.0,"net_debt_ebitda_max":2.5}},
        "value": {"prezzo":59,"status":"attivo","parametri":{"ev_fcf_max":12.0,"price_book_max":1.2,"roe_min":0.0,"net_debt_ebitda_max":2.5}},
    },
    "etf": {
        "basic": {"prezzo":29,"status":"attivo","parametri":{"ter_max":0.5,"sharpe_min":0.3,"volume_min":100000,"performance_1y_min":-0.2}},
        "pro":   {"prezzo":39,"status":"attivo","parametri":{"ter_max":0.5,"sharpe_min":0.4,"volume_min":100000,"performance_1y_min":-0.2}},
        "value": {"prezzo":59,"status":"attivo","parametri":{"ter_max":0.5,"sharpe_min":0.5,"volume_min":100000,"performance_1y_min":-0.2}},
    },
    "fondi": {
        "basic": {"prezzo":29,"status":"attivo","parametri":{"ter_max":1.0,"sharpe_min":0.1,"volume_min":50000,"performance_1y_min":-0.3}},
        "pro":   {"prezzo":39,"status":"attivo","parametri":{"ter_max":1.0,"sharpe_min":0.2,"volume_min":50000,"performance_1y_min":-0.3}},
        "value": {"prezzo":59,"status":"attivo","parametri":{"ter_max":1.0,"sharpe_min":0.3,"volume_min":50000,"performance_1y_min":-0.3}},
    },
}

# ─── SERVIZI I/O ────────────────────────────────────────────
def read_servizi():
    if not os.path.exists(SERVIZI_FILE):
        _write_servizi(DEFAULT_SERVIZI)
    try:
        with open(SERVIZI_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return DEFAULT_SERVIZI

def _write_servizi(data):
    with open(SERVIZI_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def save_servizi(data):
    data['_meta'] = {'last_modified': datetime.now().isoformat(), 'version': '2.0'}
    _write_servizi(data)

# ─── PARAMETRI I/O ──────────────────────────────────────────
def read_params():
    try:
        with open(PARAMETRI_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_params(data):
    if os.path.exists(PARAMETRI_FILE):
        bk = PARAMETRI_FILE.replace('.json', f'_bk_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        with open(PARAMETRI_FILE) as f, open(bk, 'w') as fb:
            fb.write(f.read())
    with open(PARAMETRI_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ─── SCORING WEIGHTS I/O ────────────────────────────────────
_SCORING_DEFAULTS = {
    'azioni': {
        'BASIC': {'Dividend Yield': 30, 'P/B': 20, 'ROE': 20, 'Var_1D_%': 15, 'EV/FCF': 15, 'Net Debt/EBITDA': 0},
        'PRO':   {'EV/FCF': 35, 'ROE': 25, 'P/B': 20, 'Net Debt/EBITDA': 20, 'Dividend Yield': 0, 'Var_1D_%': 5},
        'VALUE': {'EV/FCF': 40, 'ROE': 25, 'Net Debt/EBITDA': 20, 'P/B': 15, 'Dividend Yield': 0, 'Var_1D_%': 0},
    },
    'etf': {
        'BASIC': {'Perf 3M %': 35, 'Performance 1Y': 30, 'TER': 20, 'Sharpe Ratio': 15},
        'PRO':   {'Sharpe Ratio': 40, 'Performance 1Y': 30, 'TER': 20, 'Perf 3M %': 10},
        'VALUE': {'Sharpe Ratio': 45, 'Performance 1Y': 25, 'TER': 25, 'Perf 3M %': 5},
    },
    'fondi': {
        'BASIC': {'Perf 3M %': 30, 'Performance 1Y': 30, 'TER': 25, 'Sharpe Ratio': 15},
        'PRO':   {'Sharpe Ratio': 40, 'Performance 1Y': 25, 'TER': 30, 'Perf 3M %': 5},
        'VALUE': {'Sharpe Ratio': 45, 'TER': 35, 'Performance 1Y': 15, 'Perf 3M %': 5},
    },
}

def _load_scoring_weights():
    cfg_path = os.path.join(BASE_DIR, 'config.json')
    try:
        with open(cfg_path, encoding='utf-8') as f:
            cfg = json.load(f)
        w = cfg.get('scoring_weights')
        if w and isinstance(w, dict):
            return w
    except Exception:
        pass
    return {a: {p: dict(v) for p, v in plans.items()} for a, plans in _SCORING_DEFAULTS.items()}

def _save_scoring_weights(weights):
    cfg_path = os.path.join(BASE_DIR, 'config.json')
    try:
        with open(cfg_path, encoding='utf-8') as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    cfg['scoring_weights'] = weights
    with open(cfg_path, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def read_clienti():
    with _clienti_lock:
        try:
            with open(CLIENTI_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {'tester': [], 'clienti': []}

def read_prospect():
    with _prospect_lock:
        try:
            with open(PROSPECT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []

def save_prospect(data):
    with _prospect_lock:
        tmp = PROSPECT_FILE + '.tmp'
        try:
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, PROSPECT_FILE)
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

def _next_prospect_id(items):
    if not items:
        return 1
    return max(p.get('id', 0) for p in items) + 1

def _ruota_backup_clienti(max_keep=10):
    import shutil as _sh, glob as _gl
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    files = sorted(_gl.glob(os.path.join(BACKUPS_DIR, 'clienti_bk_*.json')))
    for old in files[:-max_keep]:
        try: os.remove(old)
        except Exception: pass

def save_clienti(data):
    with _clienti_lock:
        # Backup in BACKUPS/clienti/ con rotazione (mantieni ultimi 10)
        if os.path.exists(CLIENTI_FILE):
            os.makedirs(BACKUPS_DIR, exist_ok=True)
            bk = os.path.join(BACKUPS_DIR, f'clienti_bk_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
            try:
                import shutil
                shutil.copy2(CLIENTI_FILE, bk)
                _ruota_backup_clienti()
            except Exception:
                pass
        # Scrittura atomica: temp file → rename
        tmp_path = CLIENTI_FILE + '.tmp'
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, CLIENTI_FILE)
        except Exception:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

CSV_FIELDS = [
    'nome','cognome','email',
    'piano_azioni','piano_etf','piano_fondi','piano_ordini','piano_wealthos',
    'stato','data_registrazione','data_attivazione',
    # dati fiscali (flattenati)
    'paese','data_nascita','indirizzo','cap','citta',
    'codice_fiscale','telefono','p_iva',
]

FISCAL_FIELDS = ['paese','data_nascita','indirizzo','cap','citta','codice_fiscale','telefono','p_iva']
PAESI_VALIDI  = {'IT','ES','FR','DE','UK'}

def _flatten(c):
    """Restituisce il record cliente con dati_fiscali flattenati per il CSV."""
    row = {f: c.get(f, '') for f in CSV_FIELDS}
    df = c.get('dati_fiscali', {})
    for f in FISCAL_FIELDS:
        row[f] = df.get(f, '')
    return row

def clienti_to_csv():
    """Esporta tutti i clienti (tester + attivi) in CSV. Esclude password_hash."""
    db = read_clienti()
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=CSV_FIELDS, extrasaction='ignore', lineterminator='\n')
    w.writeheader()
    for cat in ['tester', 'clienti']:
        for c in db.get(cat, []):
            w.writerow(_flatten(c))
    return out.getvalue()

def csv_to_clienti(csv_content):
    """Importa clienti da stringa CSV. Ritorna {aggiunti, duplicati, errori}."""
    db = read_clienti()
    existing_emails = {c.get('email','').lower() for grp in db.values() for c in grp}
    aggiunti = 0; duplicati = 0; errori = []
    valori_piano = {'NONE','BASIC','PRO','VALUE'}
    valori_stato = {'TESTER','ATTIVO','SOSPESO','SCADUTO'}

    try:
        reader = csv.DictReader(io.StringIO(csv_content.strip()))
    except Exception as e:
        return {'aggiunti': 0, 'duplicati': 0, 'errori': [f'CSV non valido: {e}']}

    for i, row in enumerate(reader, start=2):
        nome  = (row.get('nome')  or '').strip()
        email = (row.get('email') or '').strip().lower()
        if not nome or not email:
            errori.append(f'Riga {i}: nome o email mancante — saltata'); continue
        if email in existing_emails:
            duplicati += 1; continue
        piano_az = (row.get('piano_azioni') or 'NONE').strip().upper()
        piano_et = (row.get('piano_etf')    or 'NONE').strip().upper()
        piano_fo = (row.get('piano_fondi')  or 'NONE').strip().upper()
        piano_or = (row.get('piano_ordini') or 'NONE').strip().upper()
        stato    = (row.get('stato')        or 'TESTER').strip().upper()
        if piano_az not in valori_piano: piano_az = 'NONE'
        if piano_et not in valori_piano: piano_et = 'NONE'
        if piano_fo not in valori_piano: piano_fo = 'NONE'
        if piano_or not in valori_piano: piano_or = 'NONE'
        if stato    not in valori_stato:  stato    = 'TESTER'
        paese = (row.get('paese') or '').strip().upper()
        dati_fiscali = {
            'paese':          paese if paese in PAESI_VALIDI else '',
            'data_nascita':   (row.get('data_nascita')   or '').strip(),
            'indirizzo':      (row.get('indirizzo')       or '').strip(),
            'cap':            (row.get('cap')             or '').strip(),
            'citta':          (row.get('citta')           or '').strip(),
            'codice_fiscale': (row.get('codice_fiscale')  or '').strip().upper(),
            'telefono':       (row.get('telefono')        or '').strip(),
            'p_iva':          (row.get('p_iva')           or '').strip(),
        }
        nuovo = {
            'nome':               nome,
            'cognome':            (row.get('cognome') or '').strip(),
            'email':              email,
            'piano_azioni': piano_az, 'piano_etf': piano_et,
            'piano_fondi':  piano_fo, 'piano_ordini': piano_or,
            'screener_attivi':    [],
            'data_registrazione': row.get('data_registrazione') or datetime.now().strftime('%Y-%m-%d'),
            'data_attivazione':   row.get('data_attivazione') or '',
            'stato':              stato,
            'dati_fiscali':       dati_fiscali,
        }
        dest = 'clienti' if stato == 'ATTIVO' else 'tester'
        db.setdefault(dest, []).append(nuovo)
        existing_emails.add(email); aggiunti += 1

    if aggiunti:
        save_clienti(db)
    return {'aggiunti': aggiunti, 'duplicati': duplicati, 'errori': errori}

# ─── REPORTS ────────────────────────────────────────────────
def _latest(patterns):
    files = []
    for p in patterns:
        files.extend(glob.glob(os.path.join(REPORTS_DIR, p)))
    return sorted(files, key=os.path.getmtime)[-1] if files else None

def _latest_plan(tipo, piano):
    """Trova il file più recente per tipo+piano specifico (es. Azioni_Screener_PRO_*.xlsx).
    Fallback sul file più recente di qualsiasi piano se quello specifico non esiste ancora.
    """
    piano = (piano or 'PRO').upper()
    prefixes = {
        'azioni': f'Azioni_Screener_{piano}_',
        'etf':    f'ETF_Screener_{piano}_',
        'fondi':  f'FONDI_Screener_{piano}_',
    }
    prefix = prefixes.get(tipo)
    if not prefix:
        return None
    files = glob.glob(os.path.join(REPORTS_DIR, f'{prefix}*.xlsx'))
    if files:
        return sorted(files, key=os.path.getmtime)[-1]
    # fallback: qualsiasi file di quel tipo (incluso formato vecchio)
    fallback = {
        'azioni': ['Azioni_Screener_*.xlsx', 'value_screener_azioni_*.xlsx'],
        'etf':    ['ETF_Screener_*.xlsx',    'value_screener_etf_*.xlsx'],
        'fondi':  ['FONDI_Screener_*.xlsx',  'value_screener_fondi_*.xlsx'],
    }
    return _latest(fallback.get(tipo, []))

def _latest_plan_pdf(tipo, piano):
    piano = (piano or "BASIC").upper()
    prefix_map = {
        "azioni": f"AZIONI_{piano}_Report_",
        "etf":    f"ETF_{piano}_Report_",
        "fondi":  f"FONDI_{piano}_Report_",
    }
    prefix = prefix_map.get(tipo)
    if not prefix:
        return None
    try:
        files = sorted([
            ff for ff in os.listdir(REPORTS_PDF_DIR)
            if ff.startswith(prefix) and ff.endswith(".pdf")
        ])
        return os.path.join(REPORTS_PDF_DIR, files[-1]) if files else None
    except Exception:
        return None


def _count_sheet(f):
    """Legge il conteggio righe dal foglio Selezionati o Top N di un Excel."""
    try:
        xls = pd.ExcelFile(f)
        for sn in xls.sheet_names:
            if 'selezionat' in sn.lower():
                return len(pd.read_excel(f, sheet_name=sn))
        for sn in xls.sheet_names:
            if 'top' in sn.lower():
                return len(pd.read_excel(f, sheet_name=sn))
    except Exception:
        pass
    return '?'

def get_status():
    result = {}
    _plan_prefix = {
        'azioni':   {'BASIC': 'Azioni_Screener_BASIC_',    'PRO': 'Azioni_Screener_PRO_',    'VALUE': 'Azioni_Screener_VALUE_'},
        'etf':      {'BASIC': 'ETF_Screener_BASIC_',       'PRO': 'ETF_Screener_PRO_',       'VALUE': 'ETF_Screener_VALUE_'},
        'fondi':    {'BASIC': 'FONDI_Screener_BASIC_',     'PRO': 'FONDI_Screener_PRO_',     'VALUE': 'FONDI_Screener_VALUE_'},
        'fondi_eu': {'BASIC': 'FONDI_EU_Screener_BASIC_',  'PRO': 'FONDI_EU_Screener_PRO_',  'VALUE': 'FONDI_EU_Screener_VALUE_'},
    }
    _legacy_pats = {
        'azioni':   ['Azioni_Screener_*.xlsx', 'value_screener_azioni_*.xlsx'],
        'etf':      ['ETF_Screener_*.xlsx',    'value_screener_etf_*.xlsx'],
        'fondi':    ['FONDI_Screener_*.xlsx',  'value_screener_fondi_*.xlsx'],
        'fondi_eu': ['FONDI_EU_Screener_*.xlsx'],
    }
    for tipo in ('azioni', 'etf', 'fondi', 'fondi_eu'):
        piani_info = {}
        latest_time = None
        latest_file = None
        for piano, prefix in _plan_prefix[tipo].items():
            files = glob.glob(os.path.join(REPORTS_DIR, f'{prefix}*.xlsx'))
            if not files:
                continue
            f = sorted(files, key=os.path.getmtime)[-1]
            st = os.stat(f)
            mtime = st.st_mtime
            if latest_time is None or mtime > latest_time:
                latest_time = mtime
                latest_file = f
            piani_info[piano] = {
                'count': _count_sheet(f),
                'size':  f"{st.st_size/1024:.0f} KB",
                'file':  os.path.basename(f),
            }
        if piani_info:
            result[tipo] = {
                'piani': piani_info,
                'time':  datetime.fromtimestamp(latest_time).strftime('%d/%m/%Y %H:%M'),
                'file':  os.path.basename(latest_file),
            }
        else:
            # Fallback: file vecchio formato (senza piano nel nome)
            f = _latest(_legacy_pats[tipo])
            if f:
                st = os.stat(f)
                result[tipo] = {
                    'piani': {},
                    'time':  datetime.fromtimestamp(st.st_mtime).strftime('%d/%m/%Y %H:%M'),
                    'file':  os.path.basename(f),
                    'count': _count_sheet(f),
                }
            else:
                result[tipo] = None
    with run_lock:
        result['_running'] = {k: v['status'] for k, v in running.items()}
    return result

def get_table_data(tipo):
    if tipo not in ('azioni', 'etf', 'fondi'):
        return {'error': 'tipo non valido'}
    # Admin vede sempre il file PRO (il più rappresentativo senza eccessi VALUE)
    f = _latest_plan(tipo, 'PRO')
    if not f:
        return {'rows': [], 'file': None, 'time': None}
    try:
        xls = pd.ExcelFile(f)
        df = None
        for sn in xls.sheet_names:
            if 'selezionat' in sn.lower():
                df = pd.read_excel(f, sheet_name=sn); break
        if df is None:
            for sn in xls.sheet_names:
                if 'top' in sn.lower():
                    df = pd.read_excel(f, sheet_name=sn); break
        if df is None:
            return {'rows': [], 'file': os.path.basename(f), 'time': None}
        rows = df.head(50).to_dict(orient='records')
        for r in rows:
            for k, v in r.items():
                if isinstance(v, float) and v != v:
                    r[k] = None
        return {
            'rows': rows,
            'file': os.path.basename(f),
            'time': datetime.fromtimestamp(os.path.getmtime(f)).strftime('%d/%m/%Y %H:%M')
        }
    except Exception:
        return {'rows': [], 'file': os.path.basename(f), 'time': None}

def get_mercati():
    f = _latest_plan('azioni', 'PRO')
    if not f:
        return {'rows': []}
    try:
        df = pd.read_excel(f, sheet_name='Dashboard', header=None)
        hrow = None
        for i, row in df.iterrows():
            if str(row.iloc[0]).strip() == 'Mercato':
                hrow = i; break
        if hrow is None:
            return {'rows': []}
        headers = [str(df.iloc[hrow, c]).strip() for c in range(df.shape[1]) if pd.notna(df.iloc[hrow, c])]
        rows = []
        for i in range(hrow+1, len(df)):
            v0 = df.iloc[i, 0]
            if pd.isna(v0) or str(v0).strip() == '':
                break
            row = {}
            for j, h in enumerate(headers):
                v = df.iloc[i, j]
                if pd.isna(v): v = None
                elif isinstance(v, float) and v == int(v): v = int(v)
                row[h] = v
            rows.append(row)
        return {'rows': rows}
    except Exception:
        return {'rows': []}

# ─── SCREENER ───────────────────────────────────────────────
# --- ANALISI SETTORIALI ---

SETTORI_US = [
    {'ticker': 'XLK',  'nome': 'Technology',          'emoji': '💻'},
    {'ticker': 'XLF',  'nome': 'Financial Services',  'emoji': '🏦'},
    {'ticker': 'XLV',  'nome': 'Health Care',         'emoji': '💊'},
    {'ticker': 'XLI',  'nome': 'Industrials',         'emoji': '🏭'},
    {'ticker': 'XLY',  'nome': 'Consumer Discret.',   'emoji': '🛍️'},
    {'ticker': 'XLP',  'nome': 'Consumer Staples',    'emoji': '🛒'},
    {'ticker': 'XLE',  'nome': 'Energy',              'emoji': '⚡'},
    {'ticker': 'XLU',  'nome': 'Utilities',           'emoji': '💡'},
    {'ticker': 'XLB',  'nome': 'Materials',           'emoji': '🔩'},
    {'ticker': 'XLRE', 'nome': 'Real Estate',         'emoji': '🏠'},
    {'ticker': 'XLC',  'nome': 'Comm. Services',      'emoji': '📡'},
]
SETTORI_EU = [
    {'ticker': 'EXV3.DE', 'nome': 'Technology',       'emoji': '💻'},
    {'ticker': 'EXH2.DE', 'nome': 'Banks',            'emoji': '🏦'},
    {'ticker': 'EXH3.DE', 'nome': 'Health Care',      'emoji': '💊'},
    {'ticker': 'EXH4.DE', 'nome': 'Industrials',      'emoji': '🏭'},
    {'ticker': 'EXH1.DE', 'nome': 'Auto & Parts',     'emoji': '🚗'},
    {'ticker': 'EXV8.DE', 'nome': 'Food & Beverage',  'emoji': '🛒'},
    {'ticker': 'EXV1.DE', 'nome': 'Oil & Gas',        'emoji': '⚡'},
    {'ticker': 'EXV7.DE', 'nome': 'Utilities',        'emoji': '💡'},
    {'ticker': 'EXH5.DE', 'nome': 'Insurance',        'emoji': '🛡️'},
    {'ticker': 'EXH6.DE', 'nome': 'Media',            'emoji': '📡'},
    {'ticker': 'EXV6.DE', 'nome': 'Travel & Leisure', 'emoji': '✈️'},
]
NAZIONI = [
    {'ticker': '^GSPC',      'nome': 'USA',          'flag': '🇺🇸', 'regione': 'Americas',      'indice': 'S&P 500'},
    {'ticker': '^NDX',       'nome': 'USA Tech',     'flag': '🇺🇸', 'regione': 'Americas',      'indice': 'Nasdaq 100'},
    {'ticker': '^GSPTSE',    'nome': 'Canada',       'flag': '🇨🇦', 'regione': 'Americas',      'indice': 'TSX Comp.'},
    {'ticker': '^BVSP',      'nome': 'Brasile',      'flag': '🇧🇷', 'regione': 'Americas',      'indice': 'Bovespa'},
    {'ticker': '^MXX',       'nome': 'Messico',      'flag': '🇲🇽', 'regione': 'Americas',      'indice': 'IPC'},
    {'ticker': '^FTSE',      'nome': 'UK',           'flag': '🇬🇧', 'regione': 'Europa',        'indice': 'FTSE 100'},
    {'ticker': '^DAX',       'nome': 'Germania',     'flag': '🇩🇪', 'regione': 'Europa',        'indice': 'DAX 40'},
    {'ticker': '^FCHI',      'nome': 'Francia',      'flag': '🇫🇷', 'regione': 'Europa',        'indice': 'CAC 40'},
    {'ticker': 'FTSEMIB.MI', 'nome': 'Italia',       'flag': '🇮🇹', 'regione': 'Europa',        'indice': 'FTSE MIB'},
    {'ticker': '^IBEX',      'nome': 'Spagna',       'flag': '🇪🇸', 'regione': 'Europa',        'indice': 'IBEX 35'},
    {'ticker': '^SSMI',      'nome': 'Svizzera',     'flag': '🇨🇭', 'regione': 'Europa',        'indice': 'SMI'},
    {'ticker': '^AEX',       'nome': 'Olanda',       'flag': '🇳🇱', 'regione': 'Europa',        'indice': 'AEX'},
    {'ticker': '^N225',      'nome': 'Giappone',     'flag': '🇯🇵', 'regione': 'Asia-Pacifico', 'indice': 'Nikkei 225'},
    {'ticker': '^HSI',       'nome': 'Hong Kong',    'flag': '🇭🇰', 'regione': 'Asia-Pacifico', 'indice': 'Hang Seng'},
    {'ticker': '000001.SS',  'nome': 'Cina',         'flag': '🇨🇳', 'regione': 'Asia-Pacifico', 'indice': 'Shanghai Comp.'},
    {'ticker': '^BSESN',     'nome': 'India',        'flag': '🇮🇳', 'regione': 'Asia-Pacifico', 'indice': 'BSE Sensex'},
    {'ticker': '^AXJO',      'nome': 'Australia',    'flag': '🇦🇺', 'regione': 'Asia-Pacifico', 'indice': 'ASX 200'},
    {'ticker': '^KS11',      'nome': 'Corea Sud',    'flag': '🇰🇷', 'regione': 'Asia-Pacifico', 'indice': 'KOSPI'},
    {'ticker': '^STI',       'nome': 'Singapore',    'flag': '🇸🇬', 'regione': 'Asia-Pacifico', 'indice': 'STI'},
    {'ticker': '^JKSE',      'nome': 'Indonesia',    'flag': '🇮🇩', 'regione': 'Emergenti',     'indice': 'IDX Composite'},
    {'ticker': '^MERV',      'nome': 'Argentina',    'flag': '🇦🇷', 'regione': 'Emergenti',     'indice': 'Merval'},
]

_settori_cache = {'data': None, 'ts': 0.0}
_SETTORI_TTL   = 900

# ETF principale per ogni settore US (per Idee di Investimento)
_SETTORE_ETF = {
    'Technology':         ('XLK',  'EXV3.DE'),
    'Financial Services': ('XLF',  'EXH2.DE'),
    'Health Care':        ('XLV',  'EXH3.DE'),
    'Industrials':        ('XLI',  'EXH4.DE'),
    'Consumer Discret.':  ('XLY',  'EXH1.DE'),
    'Consumer Staples':   ('XLP',  'EXV8.DE'),
    'Energy':             ('XLE',  'EXV1.DE'),
    'Utilities':          ('XLU',  'EXV7.DE'),
    'Materials':          ('XLB',  None),
    'Real Estate':        ('XLRE', None),
    'Comm. Services':     ('XLC',  'EXH6.DE'),
}
# ETF principale per ogni nazione
_NAZIONE_ETF = {
    'USA':       'SPY', 'USA Tech': 'QQQ',  'Canada':    'EWC',
    'Brasile':   'EWZ', 'Messico':  'EWW',  'UK':        'EWU',
    'Germania':  'EWG', 'Francia':  'EWQ',  'Italia':    'EWI',
    'Spagna':    'EWP', 'Svizzera': 'EWL',  'Olanda':    'EWN',
    'Giappone':  'EWJ', 'Hong Kong':'EWH',  'Cina':      'MCHI',
    'India':     'INDA','Australia': 'EWA', 'Corea Sud': 'EWY',
    'Singapore': 'EWS', 'Indonesia':'EIDO', 'Argentina': 'ARGT',
}
# EU→US name mapping per cercare ticker nel screener azioni
_EU_TO_US = {
    'Banks': 'Financial Services', 'Auto & Parts': 'Consumer Discret.',
    'Food & Beverage': 'Consumer Staples', 'Oil & Gas': 'Energy',
    'Insurance': 'Financial Services', 'Media': 'Comm. Services',
    'Travel & Leisure': 'Consumer Discret.',
}

_idee_cache = {'data': None, 'ts': 0.0}

def get_idee_data():
    """Restituisce settori e nazioni in momentum positivo con top ticker dallo screener."""
    global _idee_cache
    now = time.time()
    if _idee_cache['data'] and now - _idee_cache['ts'] < _SETTORI_TTL:
        return _idee_cache['data']

    sett_data = get_settori_data()
    if sett_data.get('error'):
        return {'error': sett_data['error'], 'settori': [], 'nazioni': []}

    # ── Leggi Excel screener una sola volta ──────────────────────
    titoli_per_settore = {}
    f = None
    for piano in ('VALUE', 'PRO', 'BASIC'):
        f = _latest_plan('azioni', piano)
        if f: break
    if f:
        try:
            xl = pd.ExcelFile(f)
            seen_global = {}
            for sheet in xl.sheet_names:
                try:
                    df = xl.parse(sheet)
                except Exception:
                    continue
                if 'Settore' not in df.columns or 'Ticker' not in df.columns:
                    continue
                for _, row in df.iterrows():
                    t  = str(row.get('Ticker', '')).strip()
                    s  = str(row.get('Settore', '')).strip()
                    if not t or not s:
                        continue
                    sc = row.get('Score')
                    try:
                        sc = float(sc) if sc is not None and not (isinstance(sc, float) and pd.isna(sc)) else None
                    except Exception:
                        sc = None
                    key = (s, t)
                    if key not in seen_global or (sc or 0) > (seen_global[key].get('score') or 0):
                        seen_global[key] = {
                            'ticker': t,
                            'nome':   str(row.get('Nome') or ''),
                            'score':  sc,
                        }
            for (s, t), v in seen_global.items():
                titoli_per_settore.setdefault(s, []).append(v)
            for s in titoli_per_settore:
                titoli_per_settore[s].sort(key=lambda x: x['score'] or -999, reverse=True)
        except Exception:
            pass

    # ── Settori positivi ─────────────────────────────────────────
    settori_out = []
    for s in sett_data.get('settori_us', []):
        p1m = s.get('p1m')
        if p1m is None or p1m <= 0:
            continue
        nome    = s['nome']
        us_etf, eu_etf = _SETTORE_ETF.get(nome, (None, None))
        top3    = titoli_per_settore.get(nome, [])[:3]
        settori_out.append({
            'nome':   nome,
            'emoji':  s.get('emoji', ''),
            'ticker': s.get('ticker', ''),
            'p1m':    p1m,
            'p1w':    s.get('p1w'),
            'p3m':    s.get('p3m'),
            'etf_us': us_etf,
            'etf_eu': eu_etf,
            'top':    top3,
        })
    settori_out.sort(key=lambda x: x['p1m'], reverse=True)

    # ── Settori EU positivi non già coperti dai US ────────────────
    nomi_us_positivi = {s['nome'] for s in settori_out}
    for s in sett_data.get('settori_eu', []):
        p1m = s.get('p1m')
        if p1m is None or p1m <= 0:
            continue
        nome_eu = s['nome']
        nome_us = _EU_TO_US.get(nome_eu, nome_eu)
        if nome_us in nomi_us_positivi:
            continue  # già mostrato come settore US
        _, eu_etf = _SETTORE_ETF.get(nome_us, (None, None))
        # cerca ETF EU diretto dal ticker del settore EU
        if not eu_etf:
            eu_etf = s.get('ticker')
        settori_out.append({
            'nome':   nome_eu,
            'emoji':  s.get('emoji', ''),
            'ticker': s.get('ticker', ''),
            'p1m':    p1m,
            'p1w':    s.get('p1w'),
            'p3m':    s.get('p3m'),
            'etf_us': None,
            'etf_eu': eu_etf,
            'top':    [],
            'regione': 'eu',
        })
    settori_out.sort(key=lambda x: x['p1m'], reverse=True)

    # ── Nazioni positive (semaforo 🟢: p1m >= 2) ─────────────────
    nazioni_out = []
    for n in sett_data.get('nazioni', []):
        p1m = n.get('p1m')
        if p1m is None or p1m < 2:
            continue
        nome = n['nome']
        nazioni_out.append({
            'nome':   nome,
            'flag':   n.get('flag', ''),
            'indice': n.get('indice', ''),
            'p1m':    p1m,
            'p1w':    n.get('p1w'),
            'etf':    _NAZIONE_ETF.get(nome),
        })
    nazioni_out.sort(key=lambda x: x['p1m'], reverse=True)

    data = {
        'settori': settori_out,
        'nazioni': nazioni_out,
        'ts': sett_data.get('ts', '—'),
    }
    _idee_cache = {'data': data, 'ts': now}
    return data

def _sett_perf(series, n):
    if series is None or len(series) < n + 1:
        return None
    try:
        v0 = float(series.iloc[-n - 1])
        v1 = float(series.iloc[-1])
        return round((v1 / v0 - 1) * 100, 2) if v0 != 0 else None
    except Exception:
        return None

def get_settori_data():
    import yfinance as yf
    global _settori_cache
    now = time.time()
    if _settori_cache['data'] and now - _settori_cache['ts'] < _SETTORI_TTL:
        return _settori_cache['data']
    all_defs = SETTORI_US + SETTORI_EU + NAZIONI
    tickers  = [d['ticker'] for d in all_defs]
    try:
        raw    = yf.download(tickers, period='1y', interval='1d',
                             auto_adjust=True, progress=False, threads=True)
        closes = raw['Close'] if isinstance(raw.columns, pd.MultiIndex) else raw
    except Exception as e:
        return {'error': str(e), 'settori_us': [], 'settori_eu': [], 'nazioni': [], 'ts': '—'}

    def _build(defn):
        out = []
        for d in defn:
            t = d['ticker']
            try:
                s = closes[t].dropna()
            except (KeyError, TypeError):
                s = None
            item = dict(d)
            if s is not None and len(s) > 0:
                item.update({
                    'prezzo': round(float(s.iloc[-1]), 2),
                    'p1d': _sett_perf(s, 1),
                    'p1w': _sett_perf(s, 5),
                    'p1m': _sett_perf(s, 21),
                    'p3m': _sett_perf(s, 63),
                    'p1y': _sett_perf(s, 252),
                    'ok':  True,
                })
            else:
                item.update({'prezzo': None, 'p1d': None, 'p1w': None,
                             'p1m': None, 'p3m': None, 'p1y': None, 'ok': False})
            out.append(item)
        return out

    data = {
        'settori_us': _build(SETTORI_US),
        'settori_eu': _build(SETTORI_EU),
        'nazioni':    _build(NAZIONI),
        'ts': datetime.now().strftime('%d/%m/%Y %H:%M'),
    }
    _settori_cache = {'data': data, 'ts': now}
    return data


def get_settori_titoli(settore):
    f = None
    for piano in ('VALUE', 'PRO', 'BASIC'):
        f = _latest_plan('azioni', piano)
        if f:
            break
    if not f:
        return {'titoli': [], 'settore': settore, 'tot': 0}
    try:
        xl = pd.ExcelFile(f)
    except Exception:
        return {'titoli': [], 'settore': settore, 'tot': 0}
    seen   = set()
    titoli = []
    for sheet in xl.sheet_names:
        try:
            df = xl.parse(sheet)
        except Exception:
            continue
        if 'Settore' not in df.columns or 'Ticker' not in df.columns:
            continue
        sub = df[df['Settore'].astype(str).str.strip() == settore]
        for _, row in sub.iterrows():
            t = str(row.get('Ticker', '')).strip()
            if not t or t in seen:
                continue
            seen.add(t)
            def _sv(col, _r=row):
                v = _r.get(col)
                try:
                    return None if (isinstance(v, float) and pd.isna(v)) else v
                except Exception:
                    return v
            p1y = _sv('Perf_1Y_%') if _sv('Perf_1Y_%') is not None else _sv('Perf 1Y %')
            p1d = _sv('Var_1D_%')  if _sv('Var_1D_%')  is not None else _sv('Var 1D %')
            titoli.append({
                'ticker':  t,
                'nome':    str(_sv('Nome') or ''),
                'mercato': str(_sv('Mercato') or ''),
                'score':   _sv('Score'),
                'p1y':     p1y,
                'p1d':     p1d,
                'pb':      _sv('P/B'),
                'roe':     _sv('ROE'),
                'foglio':  sheet,
            })
    titoli.sort(key=lambda x: float(x['score']) if x['score'] is not None else -999, reverse=True)
    return {'titoli': titoli, 'settore': settore, 'tot': len(titoli)}

SCREENER_MAP = {
    'azioni':           'value_screener_azioni.py',
    'etf':              'value_screener_etf.py',
    'fondi':            'value_screener_fondi.py',
    'fondi_eu':         'value_screener_fondi_eu.py',
    'fondi_eu_fetch':   'orchestrator.py',
    'tutti':            None,
    'orchestrator':     'orchestrator.py',
}
SCREENER_ARGS = {
    'fondi_eu_fetch': ['FONDI_EU_FETCH'],
}

def _log(name, line):
    with run_lock:
        if name in running:
            logs = running[name].setdefault('log', [])
            logs.append(line)
            if len(logs) > MAX_LOG:
                running[name]['log'] = logs[-MAX_LOG:]

def run_screener(tipo):
    with run_lock:
        if running.get(tipo, {}).get('status') == 'running':
            return {'ok': False, 'msg': f'{tipo} gia in esecuzione'}

    def _log_tutti(line):
        _log('tutti', line)

    def _run():
        if tipo == 'tutti':
            scripts = [('azioni','value_screener_azioni.py'),('etf','value_screener_etf.py'),('fondi','value_screener_fondi.py')]
            t0 = datetime.now()
            with run_lock:
                running['tutti'] = {
                    'status': 'running',
                    'start': t0.strftime('%H:%M:%S'),
                    'log': [f'[{t0.strftime("%H:%M:%S")}] AVVIO TUTTI GLI SCREENER...']
                }
        elif tipo == 'orchestrator':
            scripts = [('orchestrator','orchestrator.py')]
        else:
            scripts = [(tipo, SCREENER_MAP[tipo])]

        overall_ok = True
        for name, script in scripts:
            t0 = datetime.now()
            sep = f'{"─"*40}'
            if tipo == 'tutti':
                _log_tutti(sep)
                _log_tutti(f'[{t0.strftime("%H:%M:%S")}] ▶ {script.upper()}')
            with run_lock:
                running[name] = {
                    'status': 'running',
                    'start': t0.strftime('%H:%M:%S'),
                    'log': [f'[{t0.strftime("%H:%M:%S")}] AVVIO {script}...']
                }
            try:
                extra = SCREENER_ARGS.get(tipo, [])
                proc = subprocess.Popen(
                    [sys.executable, os.path.join(BASE_DIR, script)] + extra,
                    cwd=BASE_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding='utf-8', errors='replace', bufsize=1
                )
                for line in proc.stdout:
                    stripped = line.rstrip()
                    if stripped:
                        _log(name, stripped)
                        if tipo == 'tutti':
                            _log_tutti(stripped)
                proc.wait(timeout=2400)
                status = 'completato' if proc.returncode == 0 else 'errore'
                end_line = f'[{datetime.now().strftime("%H:%M:%S")}] {"✓ OK" if proc.returncode == 0 else "✗ ERRORE"} exit={proc.returncode}'
                _log(name, end_line)
                if tipo == 'tutti':
                    _log_tutti(end_line)
                if proc.returncode != 0:
                    overall_ok = False
            except subprocess.TimeoutExpired:
                proc.kill(); status = 'timeout'
                _log(name, 'TIMEOUT')
                if tipo == 'tutti': _log_tutti(f'TIMEOUT — {script}')
                overall_ok = False
            except Exception as e:
                status = 'errore'
                _log(name, f'ERRORE: {e}')
                if tipo == 'tutti': _log_tutti(f'ERRORE: {e}')
                overall_ok = False
            with run_lock:
                running[name]['status'] = status
                running[name]['end'] = datetime.now().strftime('%H:%M:%S')

        if tipo == 'tutti':
            final = 'completato' if overall_ok else 'errore'
            fin_line = f'[{datetime.now().strftime("%H:%M:%S")}] {"─"*40}'
            _log_tutti(fin_line)
            _log_tutti(f'[{datetime.now().strftime("%H:%M:%S")}] TUTTI {"COMPLETATI ✓" if overall_ok else "— ERRORI RILEVATI ✗"}')
            with run_lock:
                running['tutti']['status'] = final
                running['tutti']['end'] = datetime.now().strftime('%H:%M:%S')

    threading.Thread(target=_run, daemon=True).start()
    return {'ok': True, 'msg': f'{tipo} avviato'}



from html_admin import HTML



# ─── STRIPE — chiavi da .env + price_ids da config.json ─────
import os as _os_stripe
STRIPE_SECRET_KEY     = _os_stripe.getenv('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = _os_stripe.getenv('STRIPE_WEBHOOK_SECRET', '')

def _load_stripe_price_ids():
    try:
        with open(os.path.join(BASE_DIR, 'config.json'), encoding='utf-8') as _f:
            return json.load(_f).get('stripe', {}).get('price_ids', {})
    except Exception:
        return {}

STRIPE_PRICE_IDS = _load_stripe_price_ids()

# Prezzi mensili (€) per ogni asset × piano — fonte: read_servizi()
_PREZZI_MENSILI = {
    ('azioni','basic'):29, ('azioni','pro'):39, ('azioni','value'):59,
    ('etf','basic'):29,    ('etf','pro'):39,    ('etf','value'):59,
    ('fondi','basic'):29,  ('fondi','pro'):39,  ('fondi','value'):59,
}
_ASSET_LABEL_IT = {
    'azioni':'Screener Azioni', 'etf':'Screener ETF',
    'fondi':'Screener Fondi',   'fondi_eu':'Screener Fondi EU',
}

def create_checkout_session(asset, tier, email_prefill=''):
    if not STRIPE_SECRET_KEY:
        return {"error": "Stripe non ancora configurato"}
    try:
        import urllib.request, urllib.parse
        price_id = STRIPE_PRICE_IDS.get(f"{asset}_{tier}", "")
        if not price_id:
            return {"error": f"Price ID mancante per {asset} {tier} — configurare in config.json"}
        params = {
            "mode": "subscription",
            "line_items[0][price]": price_id,
            "line_items[0][quantity]": "1",
            "success_url": BASE_URL + "/landing?success=1&session_id={CHECKOUT_SESSION_ID}",
            "cancel_url":  BASE_URL + "/landing?cancel=1",
            "metadata[asset]": asset,
            "metadata[tier]":  tier,
            "locale": "it",
        }
        if email_prefill:
            params["customer_email"] = email_prefill
        payload = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(
            "https://api.stripe.com/v1/checkout/sessions",
            data=payload,
            headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}"}
        )
        with urllib.request.urlopen(req, context=_SSL_CTX) as resp:
            session = json.loads(resp.read())
            return {"url": session["url"]}
    except Exception as e:
        return {"error": str(e)}


# ─── STRIPE WEBHOOK — verifica firma + gestione eventi ──────
import hmac as _hmac, hashlib as _hashlib

def _verify_stripe_signature(body_bytes: bytes, sig_header: str, secret: str) -> bool:
    """Verifica firma HMAC-SHA256 del webhook Stripe."""
    try:
        parts = {}
        for kv in sig_header.split(','):
            if '=' in kv:
                k, v = kv.strip().split('=', 1)
                parts[k] = v
        ts = parts.get('t', '')
        v1 = parts.get('v1', '')
        signed = f"{ts}.{body_bytes.decode('utf-8')}"
        expected = _hmac.new(secret.encode(), signed.encode(), _hashlib.sha256).hexdigest()
        return _hmac.compare_digest(expected, v1)
    except Exception:
        return False


def _handle_stripe_webhook(body_bytes: bytes, sig_header: str) -> dict:
    """Processa evento Stripe: subscription + pagamento → crea client + fattura + email."""
    if not STRIPE_WEBHOOK_SECRET:
        return {'ok': False, 'msg': 'Webhook secret non configurato'}
    if not _verify_stripe_signature(body_bytes, sig_header, STRIPE_WEBHOOK_SECRET):
        return {'ok': False, 'msg': 'Firma webhook non valida'}

    event = json.loads(body_bytes)
    etype = event.get('type', '')
    obj   = event.get('data', {}).get('object', {})

    if etype == 'checkout.session.completed':
        _stripe_on_checkout_completed(obj)
    elif etype == 'customer.subscription.deleted':
        _stripe_on_subscription_deleted(obj)
    elif etype == 'invoice.payment_failed':
        _stripe_on_payment_failed(obj)

    return {'ok': True}


def _stripe_on_checkout_completed(session: dict):
    """Nuovo abbonamento pagato: crea cliente, genera fattura, invia credenziali."""
    details   = session.get('customer_details') or {}
    email     = details.get('email') or session.get('customer_email') or ''
    nome_full = details.get('name') or ''
    nome      = nome_full.split()[0] if nome_full else email.split('@')[0]
    cognome   = ' '.join(nome_full.split()[1:]) if len(nome_full.split()) > 1 else ''
    metadata  = session.get('metadata') or {}
    asset     = metadata.get('asset', '')
    tier      = metadata.get('tier', '')
    stripe_sub_id = session.get('subscription', '')
    stripe_cus_id = session.get('customer', '')

    if not email or not asset or not tier:
        return

    # Leggi clienti esistenti
    try:
        with open(CLIENTI_FILE, encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {'clienti': [], 'tester': []}

    # Cerca cliente esistente (per upgrade piano)
    clienti = data.get('clienti', [])
    cliente_esistente = next((c for c in clienti if c.get('email', '').lower() == email.lower()), None)

    import random, string as _string
    pw_temp = ''.join(random.choices(_string.ascii_letters + _string.digits, k=12))

    if cliente_esistente:
        # Aggiorna piano esistente
        piano_key = f'piano_{asset}'
        vecchio_piano = cliente_esistente.get(piano_key, 'NONE')
        cliente_esistente[piano_key] = tier.upper()
        if stripe_sub_id:
            cliente_esistente[f'stripe_sub_{asset}'] = stripe_sub_id
        if stripe_cus_id:
            cliente_esistente['stripe_customer_id'] = stripe_cus_id
        save_clienti(data)
        # Genera fattura per upgrade
        numero = _prossimo_numero_fattura()
        pdf_bytes = genera_fattura_pdf(cliente_esistente, numero)
        if pdf_bytes:
            _salva_fattura(pdf_bytes, numero)
        _invia_email_nuovo_piano(
            nome=cliente_esistente.get('nome', nome),
            email=email,
            asset_label=_ASSET_LABEL_IT.get(asset, asset),
            livello=tier.upper(),
            pdf_bytes=pdf_bytes,
            numero_fattura=numero,
        )
    else:
        # Nuovo cliente
        nuovo = {
            'nome': nome, 'cognome': cognome, 'email': email,
            'password': pw_temp,
            f'piano_{asset}': tier.upper(),
            'piano_etf': 'NONE', 'piano_fondi': 'NONE', 'piano_azioni': 'NONE',
            'piano_ordini': 'NONE',
            'stripe_customer_id': stripe_cus_id,
            f'stripe_sub_{asset}': stripe_sub_id,
            'dati_fiscali': {},
        }
        nuovo[f'piano_{asset}'] = tier.upper()
        clienti.append(nuovo)
        data['clienti'] = clienti
        save_clienti(data)
        # Genera fattura
        numero = _prossimo_numero_fattura()
        pdf_bytes = genera_fattura_pdf(nuovo, numero)
        if pdf_bytes:
            _salva_fattura(pdf_bytes, numero)
        # Email credenziali + fattura
        piani_label = f'{_ASSET_LABEL_IT.get(asset, asset)} {tier.upper()}'
        _invia_email_credenziali(
            nome=nome, email=email,
            piani_label=piani_label,
            password_temp=pw_temp,
            pdf_bytes=pdf_bytes,
            numero_fattura=numero,
        )


def _stripe_on_subscription_deleted(sub: dict):
    """Abbonamento cancellato: sospendi piano cliente."""
    meta      = sub.get('metadata') or {}
    asset     = meta.get('asset', '')
    cus_id    = sub.get('customer', '')
    sub_id    = sub.get('id', '')
    if not cus_id and not sub_id:
        return
    try:
        with open(CLIENTI_FILE, encoding='utf-8') as f:
            data = json.load(f)
        for c in data.get('clienti', []):
            if c.get('stripe_customer_id') == cus_id or c.get(f'stripe_sub_{asset}') == sub_id:
                if asset:
                    c[f'piano_{asset}'] = 'NONE'
                break
        save_clienti(data)
    except Exception:
        pass


def _stripe_on_payment_failed(inv: dict):
    """Pagamento fallito: log + notifica admin."""
    email = inv.get('customer_email', '')
    print(f'[STRIPE] Pagamento fallito per {email}', flush=True)


# ─── LOGIN PAGE ─────────────────────────────────────────────
LOGIN_HTML = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Admin Login — Robot Trader 2026</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0F172A;color:#e0e0e0;min-height:100vh;display:flex;align-items:center;justify-content:center}}
.card{{background:rgba(44,82,130,.1);border:1px solid rgba(44,82,130,.4);border-radius:16px;padding:2.5rem 2rem;width:100%;max-width:360px;text-align:center}}
.logo{{width:60px;height:60px;background:linear-gradient(135deg,#2C5282,#F6AD55);border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:1.8rem;margin:0 auto 1.2rem}}
.ttl{{color:#F6AD55;font-size:1.1rem;font-weight:700;margin-bottom:.3rem}}
.sub{{color:rgba(255,255,255,.4);font-size:.8rem;margin-bottom:1.8rem}}
input[type=password]{{width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(44,82,130,.5);border-radius:8px;padding:.75rem 1rem;color:#e0e0e0;font-size:1rem;margin-bottom:1rem;outline:none;transition:border-color .2s}}
input[type=password]:focus{{border-color:#F6AD55}}
.btn{{width:100%;background:#2C5282;color:#F6AD55;border:none;border-radius:8px;padding:.8rem;font-size:.95rem;font-weight:700;cursor:pointer;transition:background .2s;letter-spacing:.5px}}
.btn:hover{{background:#3a6bb5}}
.err{{color:#ef4444;font-size:.82rem;margin-bottom:.8rem}}
.back{{margin-top:1.2rem;font-size:.78rem}}
.back a{{color:rgba(246,173,85,.6);text-decoration:none}}
.back a:hover{{color:#F6AD55}}
</style>
</head>
<body>
<div class="card">
  <div class="logo">📊</div>
  <div class="ttl">ROBOT TRADER 2026</div>
  <div class="sub">Accesso Amministratore</div>
  {error}
  <form method="POST" action="/login">
    <div style="position:relative">
      <input type="password" name="pwd" id="adm-pwd" placeholder="Password" autofocus autocomplete="current-password" style="width:100%;padding-right:2.8rem">
      <span onclick="var i=document.getElementById('adm-pwd');i.type=i.type==='password'?'text':'password';this.textContent=i.type==='password'?'👁':'🙈'" style="position:absolute;right:.8rem;top:50%;transform:translateY(-50%);cursor:pointer;font-size:1.1rem;user-select:none">👁</span>
    </div>
    <button type="submit" class="btn">ENTRA</button>
  </form>
  <div class="back"><a href="/">← Robot Trader 2026</a></div>
</div>
</body>
</html>"""

# ─── LANDING PAGE ────────────────────────────────────────────
LANDING_HTML = r"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Robot Trader 2026 — Fuerte Venture Capital</title>
<link rel="icon" href="/icons/icon-192.png" type="image/png">
<link rel="apple-touch-icon" href="/icons/icon-192.png">
<style>
:root{--blu:#2C5282;--oro:#F6AD55;--oro2:#B3975A;--dark:#0F172A;--champ:#FDFAF5}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--dark);color:#e8e8e8;overflow-x:hidden}
/* NAV */
nav{position:fixed;top:0;left:0;right:0;z-index:200;padding:.8rem 2rem;display:flex;align-items:center;justify-content:space-between;background:#2C5282;border-bottom:2px solid var(--oro)}
.nav-brand{display:flex;align-items:center;gap:.6rem}
.nav-logo-img{height:34px;width:auto;border-radius:8px;display:block}
.nav-name{color:var(--oro);font-weight:800;font-size:.9rem;letter-spacing:.3px}
.nav-tagline{font-size:10px;color:rgba(255,255,255,.35);letter-spacing:.5px;line-height:1;margin-top:1px}
.lang-switcher{display:flex;gap:.3rem}
.lang-btn{background:transparent;border:1px solid rgba(246,173,85,.3);color:rgba(246,173,85,.6);padding:.25rem .6rem;border-radius:5px;cursor:pointer;font-size:.75rem;font-weight:700;transition:all .15s;letter-spacing:.5px}
.lang-btn:hover,.lang-btn.active{background:var(--oro);color:var(--dark);border-color:var(--oro)}
.btn-accedi{padding:.4rem 1.1rem;border:1.5px solid var(--oro);border-radius:6px;color:var(--oro);font-weight:700;font-size:.82rem;letter-spacing:.5px;text-decoration:none;transition:all .15s}
.btn-accedi:hover{background:var(--oro);color:var(--dark)}
/* HERO */
.hero{min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:7rem 2rem 4rem;background:radial-gradient(ellipse 80% 60% at 50% 0%,rgba(44,82,130,.25) 0%,transparent 70%)}
.live-badge{display:inline-flex;align-items:center;gap:.5rem;background:rgba(246,173,85,.08);border:1px solid rgba(246,173,85,.25);border-radius:20px;padding:.35rem 1rem;font-size:.74rem;font-weight:600;letter-spacing:.5px;color:var(--oro);margin-bottom:1.8rem}
.live-dot{width:7px;height:7px;background:var(--oro);border-radius:50%;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.hero-h1{font-size:6rem;font-weight:900;line-height:.93;letter-spacing:-3px;color:#fff;margin-bottom:1.6rem}
.hero-h1 span{color:var(--oro);font-size:1.2em}
.hero-sub{font-size:1.125rem;line-height:1.7;color:rgba(255,255,255,.58);max-width:560px;margin-bottom:2.4rem}
.btn-primary{display:inline-flex;align-items:center;gap:.5rem;background:var(--oro);color:var(--dark);font-weight:800;font-size:11px;padding:1rem 2.6rem;border-radius:8px;border:none;cursor:pointer;transition:all .15s;letter-spacing:.3px}
.btn-primary:hover{background:var(--oro2);transform:translateY(-1px)}
/* HOW IT WORKS */
.section{padding:5rem 2rem;max-width:1100px;margin:0 auto}
.section-title{font-size:2.5rem;font-weight:900;color:#fff;text-align:center;margin-bottom:.6rem;letter-spacing:-1px}
.section-title span{color:var(--oro)}
.section-sub{text-align:center;color:rgba(255,255,255,.48);font-size:1.1rem;margin-bottom:3rem}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1.5rem}
.step{background:rgba(44,82,130,.08);border:1px solid rgba(44,82,130,.35);border-radius:14px;padding:1.8rem;text-align:center;transition:border-color .2s}
.step:hover{border-color:var(--oro)}
.step-num{font-size:3.2rem;font-weight:900;color:rgba(246,173,85,.2);margin-bottom:.8rem;line-height:1}
.step h3{color:var(--oro);font-size:1.2rem;font-weight:800;margin-bottom:.6rem}
.step p{color:rgba(255,255,255,.5);font-size:1rem;line-height:1.65}
/* PLANS */
.plans-section{padding:5rem 2rem;background:rgba(44,82,130,.04);border-top:1px solid rgba(44,82,130,.2);border-bottom:1px solid rgba(44,82,130,.2)}
.plans-inner{max-width:1000px;margin:0 auto}
.asset-tabs{display:flex;gap:.5rem;justify-content:center;margin-bottom:2.5rem;flex-wrap:wrap}
.asset-tab{background:rgba(44,82,130,.1);border:1px solid rgba(44,82,130,.4);color:rgba(255,255,255,.55);padding:.5rem 1.5rem;border-radius:8px;cursor:pointer;font-weight:700;font-size:.88rem;transition:all .2s;letter-spacing:.3px}
.asset-tab:hover{border-color:var(--oro);color:var(--oro)}
.asset-tab.active{background:#2C5282;border-color:#2C5282;color:var(--oro)}
.plans-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1.5rem}
.plan-card{background:rgba(15,23,42,.8);border:1px solid rgba(44,82,130,.35);border-radius:14px;padding:2rem 1.5rem;text-align:center;position:relative;transition:all .2s}
.plan-card:hover{border-color:var(--oro);transform:translateY(-3px)}
.plan-card.featured{border:2px solid var(--oro);background:rgba(44,82,130,.15)}
.plan-badge{position:absolute;top:-12px;left:50%;transform:translateX(-50%);background:var(--oro);color:var(--dark);font-size:.68rem;font-weight:800;padding:.25rem .8rem;border-radius:20px;letter-spacing:.5px;white-space:nowrap}
.plan-tier{color:rgba(255,255,255,.7);font-size:.85rem;font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:1rem}
.plan-price{margin-bottom:1.5rem}
.price-num{font-size:3.8rem;font-weight:900;color:var(--oro);line-height:1}
.price-period{color:rgba(255,255,255,.4);font-size:.95rem;margin-left:.2rem}
.btn-buy{width:100%;background:#2C5282;color:var(--oro);border:1px solid rgba(246,173,85,.3);border-radius:8px;padding:.85rem;font-size:1rem;font-weight:700;cursor:pointer;transition:all .15s;letter-spacing:.3px}
.btn-buy:hover{background:#3a6bb5;border-color:var(--oro)}
.btn-buy.disabled{background:rgba(44,82,130,.15);color:rgba(255,255,255,.25);cursor:not-allowed;border-color:rgba(255,255,255,.08)}
.plan-features{list-style:none;margin:1.2rem 0 0;padding:0;text-align:left}
.plan-features li{padding:.38rem 0;font-size:.9rem;color:rgba(255,255,255,.78);border-bottom:1px solid rgba(255,255,255,.06);display:flex;align-items:flex-start;gap:.5rem}
.plan-features li:last-child{border-bottom:none}
.plan-features li::before{content:"✓";color:var(--oro);font-weight:800;flex-shrink:0}
.plan-target{margin-top:1rem;padding:.6rem .8rem;background:rgba(44,82,130,.18);border-left:3px solid var(--oro2);border-radius:0 6px 6px 0;font-size:.85rem;color:rgba(255,255,255,.58);text-align:left;line-height:1.45}
.plan-target::before{content:"👤 ";opacity:.7}
/* REGISTRAZIONE */
.reg-section{padding:5rem 2rem;background:radial-gradient(ellipse 80% 80% at 50% 50%,rgba(44,82,130,.18) 0%,transparent 70%)}
.reg-inner{max-width:560px;margin:0 auto;text-align:center}
.reg-inner h2{font-size:2.4rem;font-weight:900;color:#fff;margin-bottom:.6rem;letter-spacing:-1px}
.reg-inner h2 span{color:var(--oro)}
.reg-inner p{color:rgba(255,255,255,.48);margin-bottom:2.2rem;font-size:1.05rem}
.reg-form{background:rgba(15,23,42,.7);border:1px solid rgba(44,82,130,.4);border-radius:16px;padding:2rem;text-align:left}
.reg-row{display:grid;grid-template-columns:1fr 1fr;gap:.8rem;margin-bottom:.8rem}
.reg-field{display:flex;flex-direction:column;gap:.35rem;margin-bottom:.8rem}
.reg-field label{font-size:.78rem;color:rgba(255,255,255,.5);letter-spacing:.5px;text-transform:uppercase}
.reg-field input,.reg-field select{background:rgba(0,0,0,.35);border:1px solid rgba(44,82,130,.5);border-radius:8px;padding:.7rem .9rem;color:#e8e8e8;font-size:.95rem;outline:none;transition:border-color .2s;width:100%}
.reg-field input:focus,.reg-field select:focus{border-color:var(--oro)}
.reg-checks{display:flex;flex-direction:column;gap:.7rem;margin-bottom:1.2rem}
.reg-check{display:flex;align-items:flex-start;gap:.6rem;cursor:pointer;font-size:.95rem;color:rgba(255,255,255,.7)}
.reg-check input[type=checkbox]{width:1.1rem;height:1.1rem;accent-color:var(--oro);cursor:pointer;margin-top:.15rem;flex-shrink:0}
.reg-check-desc{display:block;font-size:.72rem;color:rgba(255,255,255,.4);font-weight:400;line-height:1.4;margin-top:.1rem}
.reg-submit{width:100%;background:var(--oro);color:var(--dark);border:none;border-radius:8px;padding:.9rem;font-size:1.05rem;font-weight:800;cursor:pointer;transition:all .15s;letter-spacing:.3px}
.reg-submit:hover{background:var(--oro2)}
.reg-disclaimer{background:rgba(44,82,130,.07);border:1px solid rgba(44,82,130,.25);border-radius:10px;padding:.9rem 1.1rem;font-size:.78rem;color:rgba(255,255,255,.4);line-height:1.6;margin-bottom:1rem}
.reg-disclaimer strong{color:rgba(246,173,85,.65);display:block;margin-bottom:.25rem;font-size:.77rem;letter-spacing:.3px;text-transform:uppercase}
.reg-gdpr{display:flex;align-items:flex-start;gap:.7rem;margin-bottom:1.2rem;cursor:pointer}
.reg-gdpr input[type=checkbox]{width:1rem;height:1rem;accent-color:var(--oro);cursor:pointer;flex-shrink:0;margin-top:.2rem}
.reg-gdpr span{font-size:.8rem;color:rgba(255,255,255,.45);line-height:1.55}
.reg-gdpr a{color:var(--oro);text-decoration:none}
.reg-gdpr a:hover{text-decoration:underline}
.reg-ok{display:none;text-align:center;padding:2.5rem 2rem;background:rgba(44,82,130,.12);border:1px solid rgba(104,211,145,.25);border-radius:14px}
.reg-err{color:#FC8181;font-size:.85rem;margin-top:.6rem;text-align:center;min-height:1.2rem}
.reg-section-label{font-size:.7rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--oro);opacity:.7;border-bottom:1px solid rgba(246,173,85,.15);padding-bottom:.4rem;margin:1.4rem 0 .9rem}
/* CTA FINALE */
.final-cta{padding:3rem 2rem;text-align:center}
.final-cta h2{font-size:2rem;font-weight:900;color:#fff;margin-bottom:.6rem;letter-spacing:-1px}
.final-cta p{color:rgba(255,255,255,.48);margin-bottom:1.5rem;font-size:1rem}
/* FOOTER */
footer{padding:2.5rem 2rem;background:#0a111e;border-top:1px solid rgba(44,82,130,.3);text-align:center}
.footer-brand{display:flex;align-items:center;justify-content:center;gap:.6rem;margin-bottom:1rem}
.footer-name{color:var(--oro);font-weight:700;font-size:.9rem}
footer p{color:rgba(255,255,255,.3);font-size:.78rem;line-height:1.8}
.admin-link{display:inline-block;margin-top:1.5rem;color:rgba(255,255,255,.45);font-size:.82rem;text-decoration:none;letter-spacing:1px;transition:all .2s;border:1px solid rgba(255,255,255,.15);padding:.3rem .8rem;border-radius:20px}
.admin-link:hover{color:var(--oro);border-color:var(--oro)}
/* RESPONSIVE */
@media(max-width:640px){
  nav{padding:.7rem 1rem}
  .nav-name{display:none}
  .hero-h1{font-size:3.75rem;letter-spacing:-1.5px}
  .lang-switcher{gap:.2rem}
}
</style>
</head>
<body>

<!-- NAV -->
<nav>
  <div class="nav-brand">
    <img class="nav-logo-img" src="data:image/png;base64,__LOGO_B64__" alt="Fuerte Venture Capital">
    <div>
      <span class="nav-name">ROBOT TRADER 2026</span>
      <div class="nav-tagline">Fuerte Venture Capital SL</div>
    </div>
  </div>
  <div class="lang-switcher">
    <button class="lang-btn active" id="btn-it" onclick="setLang('it')">IT</button>
    <button class="lang-btn" id="btn-en" onclick="setLang('en')">EN</button>
    <button class="lang-btn" id="btn-de" onclick="setLang('de')">DE</button>
    <button class="lang-btn" id="btn-fr" onclick="setLang('fr')">FR</button>
    <button class="lang-btn" id="btn-es" onclick="setLang('es')">ES</button>
  </div>
  <a href="/client-login" class="btn-accedi" data-t="accedi">ACCEDI</a>
</nav>

<!-- HERO -->
<section class="hero">
  <div class="live-badge"><span class="live-dot"></span><span data-t="live_badge">LIVE</span></div>
  <h1 class="hero-h1" id="hero-title">INFORMATI CON INTELLIGENZ<span>AI</span></h1>
  <p class="hero-sub" data-t="hero_sub"></p>
  <button class="btn-primary" onclick="scrollToPlans()" data-t="inizia_ora">INIZIA ORA →</button>
</section>

<!-- COME FUNZIONA -->
<div class="section">
  <h2 class="section-title" data-t="come_funziona">Come <span>Funziona</span></h2>
  <p class="section-sub" data-t="come_funziona_sub"></p>
  <div class="steps">
    <div class="step">
      <div class="step-num">01</div>
      <h3 data-t="step1_title"></h3>
      <p data-t="step1_desc"></p>
    </div>
    <div class="step">
      <div class="step-num">02</div>
      <h3 data-t="step2_title"></h3>
      <p data-t="step2_desc"></p>
    </div>
    <div class="step">
      <div class="step-num">03</div>
      <h3 data-t="step3_title"></h3>
      <p data-t="step3_desc"></p>
    </div>
  </div>
</div>

<!-- PIANI -->
<section id="piani" class="plans-section">
  <div class="plans-inner">
    <h2 class="section-title" data-t="scegli_piano">Scegli il <span>Tuo Piano</span></h2>
    <p class="section-sub" data-t="scegli_piano_sub"></p>
    <div class="asset-tabs">
      <button class="asset-tab active" id="tab-azioni" onclick="showAsset('azioni',this)" data-t="tab_azioni">Azioni</button>
      <button class="asset-tab" id="tab-etf" onclick="showAsset('etf',this)" data-t="tab_etf">ETF</button>
      <button class="asset-tab" id="tab-fondi" onclick="showAsset('fondi',this)" data-t="tab_fondi">Fondi</button>
      <button class="asset-tab" id="tab-ordini" onclick="showAsset('ordini',this)" data-t="tab_ordini" style="border-color:#68D39144;color:#68D391">Ordini</button>
    </div>
    <div class="plans-grid" id="plans-grid"></div>
  </div>
</section>

<!-- REGISTRAZIONE -->
<section id="registrazione" class="reg-section">
  <div class="reg-inner" style="text-align:center;max-width:560px;margin:0 auto">
    <h2 style="font-size:2rem;font-weight:900;color:#fff;margin-bottom:.8rem">Pronto a iniziare?</h2>
    <p style="color:rgba(255,255,255,.55);font-size:1rem;line-height:1.7;margin-bottom:2rem">
      Seleziona il piano nella sezione Prezzi e clicca <strong style="color:#F6AD55">Acquista</strong>.<br>
      Sarai reindirizzato a Stripe per il pagamento sicuro. Le credenziali arrivano via email in pochi minuti.
    </p>
    <button onclick="document.getElementById('piani').scrollIntoView({behavior:'smooth'})"
      style="background:#F6AD55;color:#0a0f1e;font-size:16px;font-weight:900;padding:18px 48px;border-radius:10px;border:none;cursor:pointer;letter-spacing:.5px;box-shadow:0 4px 24px rgba(246,173,85,.35)">
      SCEGLI IL TUO PIANO &uarr;
    </button>
    <div style="margin-top:1.6rem;color:rgba(255,255,255,.3);font-size:.78rem;display:flex;align-items:center;justify-content:center;gap:.5rem">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
      Pagamento sicuro con Stripe &middot; Nessun dato carta salvato sui nostri server
    </div>
  </div>
</section>

<!-- CTA FINALE -->
<section class="final-cta">
  <p data-t="footer_legal" style="color:rgba(255,255,255,.25);font-size:.8rem;max-width:600px;margin:0 auto"></p>
</section>

<!-- FOOTER -->
<footer>
  <div class="footer-brand">
    <img src="data:image/png;base64,__LOGO_B64__" alt="FVC" style="height:28px;width:auto;border-radius:7px;display:block">
    <span class="footer-name">ROBOT TRADER 2026</span>
  </div>
  <p>Fuerte Venture Capital SL &middot; CIF B23881691</p>
  <p>Calle Puipana 3, 35640 Villaverde, Las Palmas, España</p>
  <p><a href="mailto:info@fuerteventurecapital.com" style="color:#F6AD55;text-decoration:none">info@fuerteventurecapital.com</a> &middot; <a href="https://www.fuerteventurecapital.com" style="color:#F6AD55;text-decoration:none">www.fuerteventurecapital.com</a></p>
  <p style="margin-top:.5rem"><a href="https://www.linkedin.com/company/fuerte-venture-capital" style="color:#F6AD55;text-decoration:none">LinkedIn</a> &nbsp;&middot;&nbsp; <a href="https://www.facebook.com/profile.php?id=1092335337305997" style="color:#F6AD55;text-decoration:none">Facebook</a> &nbsp;&middot;&nbsp; <a href="https://www.instagram.com/fuerteventurecapital" style="color:#F6AD55;text-decoration:none">Instagram</a></p>
  <p data-t="footer_legal"></p>
  <p style="margin-top:.4rem;font-size:.72rem;opacity:.4">© 2026 FUERTE VENTURE CAPITAL SL. ALL RIGHTS RESERVED.</p>
  <a href="/login" class="admin-link">⚙ admin</a>
</footer>

<script>
var T = {
  it:{
    accedi:'ACCEDI',
    live_badge:'LIVE · Aggiornato ogni notte sui prezzi di chiusura',
    hero_title:'INFORMATI CON INTELLIGENZ<span>AI</span>',
    hero_sub:'Il primo screener quantitativo per il deep value investing. Ogni notte i migliori titoli selezionati su __NTOT_IT__ asset: __NAZ__ azioni in 17 mercati · __NETF__ ETF · __NFD__ fondi.',
    inizia_ora:'INIZIA ORA →',
    come_funziona:'Come <span>Funziona</span>',
    come_funziona_sub:'Tre passi per trasformare i dati in opportunità di investimento.',
    step1_title:'Scegli il Piano',
    step1_desc:'Seleziona tra Azioni, ETF o Fondi e il tier più adatto al tuo profilo di investimento.',
    step2_title:'Ricevi i Report',
    step2_desc:'Ogni notte alle 23:00 l\'algoritmo analizza i mercati globali sui prezzi di chiusura ufficiali. Al mattino il report è già pronto.',
    step3_title:'Investi Consapevolmente',
    step3_desc:'Dati quantitativi verificati ogni giorno per decisioni basate sulla realtà dei mercati.',
    scegli_piano:'Scegli il <span>Tuo Piano</span>',
    scegli_piano_sub:'Prezzi mensili. Disdici quando vuoi.',
    tab_azioni:'Azioni',
    tab_etf:'ETF',
    tab_fondi:'Fondi',
    tab_ordini:'Ordini',
    tier_basic:'Basic',
    tier_pro:'Pro',
    tier_value:'Value',
    mese:'/mese',
    acquista:'Acquista',
    most_popular:'PIÙ SCELTO',
    cta_title:'Pronto a Investire con Dati Reali?',
    cta_sub:'Unisciti agli investitori che usano Robot Trader 2026 ogni mattina.',
    footer_legal:'Tutti i diritti riservati. I report sono a scopo informativo e non costituiscono consulenza finanziaria.',
    reg_title:'Iscriviti al <span>Servizio</span>',reg_sub:'Compila il modulo per accedere al servizio di screening quantitativo. Riceverai le credenziali di accesso e la fattura via email in pochi minuti.',
    reg_nome:'Nome *',reg_cognome:'Cognome *',reg_email:'Email *',reg_paese:'Paese *',reg_interesse:'Mi interessa *',reg_note:'Note',
    reg_invia:'INVIA RICHIESTA →',reg_ok:'Registrazione completata! Controlla la tua email.',
    reg_disclaimer:'Fuerte Screener è un servizio SaaS di screening quantitativo automatico. I dati forniti sono esclusivamente a scopo informativo e non costituiscono consulenza finanziaria, raccomandazione di investimento o sollecitazione. Gli investimenti comportano rischi, inclusa la possibile perdita del capitale.',
    reg_gdpr_text:'Ho letto e accetto l\'<a href="/privacy" target="_blank">Informativa sulla Privacy</a> e acconsento al trattamento dei miei dati personali ai sensi del Reg. UE 2016/679 (GDPR). *',
    err_gdpr:'Devi accettare l\'informativa privacy per procedere.'
  },
  en:{
    accedi:'LOG IN',
    live_badge:'LIVE · Updated nightly on official closing prices',
    hero_title:'INFORMED BY INTELLIGENZ<span>AI</span>',
    hero_sub:'The first quantitative screener for deep value investing. Every night the best picks from __NTOT_EN__ assets: __NAZ__ stocks in 17 markets · __NETF__ ETFs · __NFD__ funds.',
    inizia_ora:'START NOW →',
    come_funziona:'How It <span>Works</span>',
    come_funziona_sub:'Three steps to turn data into investment opportunities.',
    step1_title:'Choose Your Plan',
    step1_desc:'Select from Stocks, ETFs or Funds and the tier that best suits your investment profile.',
    step2_title:'Receive Reports',
    step2_desc:'Every night at 23:00 the algorithm analyses global markets on official closing prices. The report is ready when you wake up.',
    step3_title:'Invest Wisely',
    step3_desc:'Quantitative data verified daily for decisions based on market reality.',
    scegli_piano:'Choose Your <span>Plan</span>',
    scegli_piano_sub:'Monthly pricing. Cancel anytime.',
    tab_azioni:'Stocks',
    tab_etf:'ETFs',
    tab_fondi:'Funds',
    tab_ordini:'Orders',
    tier_basic:'Basic',
    tier_pro:'Pro',
    tier_value:'Value',
    mese:'/month',
    acquista:'Buy Now',
    most_popular:'MOST POPULAR',
    cta_title:'Ready to Invest with Real Data?',
    cta_sub:'Join the investors using Robot Trader 2026 every morning.',
    footer_legal:'All rights reserved. Reports are for informational purposes and do not constitute financial advice.',
    reg_title:'Subscribe to the <span>Service</span>',reg_sub:'Fill in the form to access the quantitative screening service. You will receive your credentials and invoice by email in a few minutes.',
    reg_nome:'First Name *',reg_cognome:'Last Name *',reg_email:'Email *',reg_paese:'Country *',reg_interesse:'I am interested in *',reg_note:'Notes',
    reg_invia:'SEND REQUEST →',reg_ok:'Registration complete! Check your email.',
    reg_disclaimer:'Fuerte Screener is an automated quantitative screening SaaS. Data provided is for informational purposes only and does not constitute financial advice, investment recommendation or solicitation. Investments involve risks, including possible loss of capital.',
    reg_gdpr_text:'I have read and accept the <a href="/privacy" target="_blank">Privacy Policy</a> and consent to processing of my personal data under EU Reg. 2016/679 (GDPR). *',
    err_gdpr:'You must accept the privacy policy to proceed.'
  },
  de:{
    accedi:'ANMELDEN',
    live_badge:'LIVE · Nächtlich mit offiziellen Schlusskursen aktualisiert',
    hero_title:'INFORMIERT MIT INTELLIGENZ<span>AI</span>',
    hero_sub:'Der erste quantitative Screener für Deep Value Investing. Jeden Abend die besten Titel aus __NTOT_IT__ Assets: __NAZ__ Aktien in 17 Märkten · __NETF__ ETFs · __NFD__ Fonds.',
    inizia_ora:'JETZT STARTEN →',
    come_funziona:'So <span>Funktioniert Es</span>',
    come_funziona_sub:'Drei Schritte, um Daten in Investitionsmöglichkeiten zu verwandeln.',
    step1_title:'Plan Wählen',
    step1_desc:'Wählen Sie zwischen Aktien, ETFs oder Fonds und dem passenden Tier.',
    step2_title:'Berichte Empfangen',
    step2_desc:'Jeden Abend um 23:00 Uhr analysiert der Algorithmus die globalen Märkte anhand offizieller Schlusskurse. Am Morgen ist der Bericht fertig.',
    step3_title:'Bewusst Investieren',
    step3_desc:'Täglich verifizierte quantitative Daten für fundierte Anlageentscheidungen.',
    scegli_piano:'Ihren <span>Plan Wählen</span>',
    scegli_piano_sub:'Monatliche Preise. Jederzeit kündbar.',
    tab_azioni:'Aktien',
    tab_etf:'ETFs',
    tab_fondi:'Fonds',
    tab_ordini:'Aufträge',
    tier_basic:'Basic',
    tier_pro:'Pro',
    tier_value:'Value',
    mese:'/Monat',
    acquista:'Kaufen',
    most_popular:'BELIEBTESTE',
    cta_title:'Bereit, mit echten Daten zu investieren?',
    cta_sub:'Schließen Sie sich den Investoren an, die Robot Trader 2026 jeden Morgen nutzen.',
    footer_legal:'Alle Rechte vorbehalten. Berichte dienen nur zu Informationszwecken und stellen keine Finanzberatung dar.',
    reg_title:'Zum <span>Dienst</span> anmelden',reg_sub:'Füllen Sie das Formular aus, um auf den quantitativen Screening-Dienst zuzugreifen. Sie erhalten Ihre Zugangsdaten und Rechnung per E-Mail in wenigen Minuten.',
    reg_nome:'Vorname *',reg_cognome:'Nachname *',reg_email:'E-Mail *',reg_paese:'Land *',reg_interesse:'Ich interessiere mich für *',reg_note:'Anmerkungen',
    reg_invia:'ANFRAGE SENDEN →',reg_ok:'Registrierung abgeschlossen! Prüfen Sie Ihre E-Mail.',
    reg_disclaimer:'Fuerte Screener ist ein automatisierter SaaS-Screening-Dienst. Die bereitgestellten Daten dienen ausschließlich Informationszwecken und stellen keine Finanzberatung, Anlageempfehlung oder Aufforderung dar. Investitionen sind mit Risiken verbunden.',
    reg_gdpr_text:'Ich habe die <a href="/privacy" target="_blank">Datenschutzerklärung</a> gelesen und stimme der Verarbeitung meiner Daten gemäß EU-VO 2016/679 (DSGVO) zu. *',
    err_gdpr:'Bitte stimme der Datenschutzerklärung zu.'
  },
  fr:{
    accedi:'ACCÉDER',
    live_badge:'EN DIRECT · Mis à jour chaque nuit sur les cours de clôture officiels',
    hero_title:'INFORMÉ PAR INTELLIGENZ<span>AI</span>',
    hero_sub:'Le premier screener quantitatif pour le deep value investing. Chaque nuit les meilleurs titres parmi __NTOT_IT__ actifs: __NAZ__ actions · __NETF__ ETFs · __NFD__ fonds.',
    inizia_ora:'COMMENCER →',
    come_funziona:'Comment <span>Ça Marche</span>',
    come_funziona_sub:'Trois étapes pour transformer les données en opportunités d\'investissement.',
    step1_title:'Choisissez Votre Plan',
    step1_desc:'Sélectionnez parmi Actions, ETF ou Fonds et le niveau adapté à votre profil.',
    step2_title:'Recevez les Rapports',
    step2_desc:'Chaque nuit à 23h00 l\'algorithme analyse les marchés mondiaux sur les cours de clôture officiels. Le rapport est prêt dès le matin.',
    step3_title:'Investissez Intelligemment',
    step3_desc:'Données quantitatives vérifiées quotidiennement pour des décisions basées sur la réalité.',
    scegli_piano:'Choisissez <span>Votre Plan</span>',
    scegli_piano_sub:'Tarifs mensuels. Résiliable à tout moment.',
    tab_azioni:'Actions',
    tab_etf:'ETFs',
    tab_fondi:'Fonds',
    tab_ordini:'Ordres',
    tier_basic:'Basic',
    tier_pro:'Pro',
    tier_value:'Value',
    mese:'/mois',
    acquista:'Acheter',
    most_popular:'LE PLUS CHOISI',
    cta_title:'Prêt à investir avec des données réelles ?',
    cta_sub:'Rejoignez les investisseurs qui utilisent Robot Trader 2026 chaque matin.',
    footer_legal:'Tous droits réservés. Les rapports sont à titre informatif et ne constituent pas un conseil financier.',
    reg_title:'S\'inscrire au <span>Service</span>',reg_sub:'Remplissez le formulaire pour accéder au service de screening quantitatif. Vous recevrez vos identifiants et facture par email en quelques minutes.',
    reg_nome:'Prénom *',reg_cognome:'Nom *',reg_email:'Email *',reg_paese:'Pays *',reg_interesse:'Je suis intéressé par *',reg_note:'Notes',
    reg_invia:'ENVOYER LA DEMANDE →',reg_ok:'Inscription complète ! Vérifiez votre email.',
    reg_disclaimer:'Fuerte Screener est un SaaS de screening quantitatif automatisé. Les données fournies sont exclusivement à titre informatif et ne constituent pas un conseil financier, une recommandation d\'investissement ou une sollicitation. Les investissements comportent des risques.',
    reg_gdpr_text:'J\'ai lu et j\'accepte la <a href="/privacy" target="_blank">Politique de Confidentialité</a> et consens au traitement de mes données conformément au Règl. UE 2016/679 (RGPD). *',
    err_gdpr:'Vous devez accepter la politique de confidentialité pour continuer.'
  },
  es:{
    accedi:'ACCEDER',
    live_badge:'EN VIVO · Actualizado cada noche con precios de cierre oficiales',
    hero_title:'INFÓRMATE CON INTELLIGENZ<span>AI</span>',
    hero_sub:'El primer screener cuantitativo para deep value investing. Cada noche los mejores títulos de __NTOT_IT__ activos: __NAZ__ acciones en 17 mercados · __NETF__ ETFs · __NFD__ fondos.',
    inizia_ora:'COMENZAR →',
    come_funziona:'Cómo <span>Funciona</span>',
    come_funziona_sub:'Tres pasos para convertir datos en oportunidades de inversión.',
    step1_title:'Elige tu Plan',
    step1_desc:'Selecciona entre Acciones, ETFs o Fondos y el nivel más adecuado a tu perfil.',
    step2_title:'Recibe los Informes',
    step2_desc:'Cada noche a las 23:00 el algoritmo analiza los mercados globales sobre los precios de cierre oficiales. El informe está listo al despertar.',
    step3_title:'Invierte con Conciencia',
    step3_desc:'Datos cuantitativos verificados diariamente para decisiones basadas en la realidad del mercado.',
    scegli_piano:'Elige <span>tu Plan</span>',
    scegli_piano_sub:'Precios mensuales. Cancela cuando quieras.',
    tab_azioni:'Acciones',
    tab_etf:'ETFs',
    tab_fondi:'Fondos',
    tab_ordini:'Órdenes',
    tier_basic:'Basic',
    tier_pro:'Pro',
    tier_value:'Value',
    mese:'/mes',
    acquista:'Comprar',
    most_popular:'MÁS ELEGIDO',
    cta_title:'¿Listo para invertir con datos reales?',
    cta_sub:'Únete a los inversores que usan Robot Trader 2026 cada mañana.',
    footer_legal:'Todos los derechos reservados. Los informes son solo informativos y no constituyen asesoramiento financiero.',
    reg_title:'Suscríbete al <span>Servicio</span>',reg_sub:'Completa el formulario para acceder al servicio de screening cuantitativo. Recibirás tus credenciales y factura por email en pocos minutos.',
    reg_nome:'Nombre *',reg_cognome:'Apellido *',reg_email:'Email *',reg_paese:'País *',reg_interesse:'Me interesa *',reg_note:'Notas',
    reg_invia:'ENVIAR SOLICITUD →',reg_ok:'¡Registro completado! Revisa tu email.',
    reg_disclaimer:'Fuerte Screener es un SaaS de screening cuantitativo automatizado. Los datos proporcionados son exclusivamente informativos y no constituyen asesoramiento financiero, recomendación de inversión ni solicitud de compra. Las inversiones conllevan riesgos.',
    reg_gdpr_text:'He leído y acepto la <a href="/privacy" target="_blank">Política de Privacidad</a> y consiento el tratamiento de mis datos según el Regl. UE 2016/679 (RGPD). *',
    err_gdpr:'Debes aceptar la política de privacidad para continuar.'
  }
};

var lang='it', servizi=null, asset='azioni';

function setLang(l){
  lang=l;
  document.querySelectorAll('.lang-btn').forEach(function(b){b.classList.remove('active')});
  document.getElementById('btn-'+l).classList.add('active');
  // testi semplici
  document.querySelectorAll('[data-t]').forEach(function(el){
    var k=el.getAttribute('data-t');
    if(T[l][k]!==undefined && k!=='come_funziona' && k!=='scegli_piano' && k!=='hero_title' && k!=='reg_title' && k!=='reg_gdpr_text') el.textContent=T[l][k];
  });
  // testi con HTML (span colorato o link)
  document.getElementById('hero-title').innerHTML=T[l]['hero_title'];
  document.querySelector('[data-t="come_funziona"]').innerHTML=T[l]['come_funziona'];
  document.querySelector('[data-t="scegli_piano"]').innerHTML=T[l]['scegli_piano'];
  document.querySelector('[data-t="reg_title"]').innerHTML=T[l]['reg_title'];
  document.querySelector('[data-t="reg_gdpr_text"]').innerHTML=T[l]['reg_gdpr_text'];
  // rigenera piani con nuova lingua
  if(servizi) renderPlans();
}

function scrollToPlans(){
  document.getElementById('piani').scrollIntoView({behavior:'smooth'});
}

function showAsset(a,btn){
  asset=a;
  document.querySelectorAll('.asset-tab').forEach(function(t){t.classList.remove('active')});
  btn.classList.add('active');
  renderPlans();
}

function renderPlans(){
  if(!servizi) return;
  var t=T[lang], data=servizi[asset]||{}, tiers=['basic','pro','value'];
  document.getElementById('plans-grid').innerHTML=tiers.map(function(tier){
    var d=data[tier]||{}, price=d.prezzo||'—', active=d.status!=='disattivo', featured=tier==='pro';
    var features=(d.caratteristiche||[]).map(function(f){return '<li>'+f+'</li>';}).join('');
    var targetHtml=d.target?'<div class="plan-target">'+d.target+'</div>':'';
    return '<div class="plan-card'+(featured?' featured':'')+'">'+
      (featured?'<div class="plan-badge">'+t.most_popular+'</div>':'')+
      '<div class="plan-tier">'+t['tier_'+tier]+'</div>'+
      '<div class="plan-price"><span class="price-num">€'+price+'</span><span class="price-period">'+t.mese+'</span></div>'+
      '<button class="btn-buy'+(active?'':' disabled')+'" onclick="checkout(\''+asset+'\',\''+tier+'\')">'+
        (active?t.acquista:'—')+
      '</button>'+
      (features?'<ul class="plan-features">'+features+'</ul>':'')+
      targetHtml+
    '</div>';
  }).join('');
}

function checkout(a,tier){
  fetch('/api/checkout',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({asset:a,tier:tier})})
  .then(function(r){return r.json();}).then(function(d){
    if(d.url){ window.location.href=d.url; return; }
    // Stripe non configurato: scorri al form e preseleziona l'asset
    var cb = document.getElementById('reg-'+a);
    if(cb){ cb.checked=true; }
    document.getElementById('piani').scrollIntoView({behavior:'smooth'});
  });
}

function onCfPivaInput(){
  var cf   = document.getElementById('reg-cf').value.trim();
  var piva = document.getElementById('reg-piva').value.trim();
  var note = document.getElementById('reg-piva-note');
  if(cf && !piva)       { note.textContent = '(non necessaria con CF)'; note.style.color='rgba(104,211,145,.6)'; }
  else if(piva && !cf)  { note.textContent = '(P.IVA inserita)'; note.style.color='rgba(104,211,145,.6)'; }
  else                  { note.textContent = '(se azienda)'; note.style.color=''; }
}

function _validaCF(cf, paese){
  switch(paese){
    case 'IT':
      if(!/^[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]$/i.test(cf))
        return 'Codice Fiscale italiano non valido (es. RSSMRA80A01H501U)';
      break;
    case 'ES':
      if(!/^\d{8}[A-Z]$/i.test(cf) && !/^[XYZ]\d{7}[A-Z]$/i.test(cf))
        return 'DNI/NIE spagnolo non valido (es. 12345678A oppure X1234567A)';
      break;
    case 'FR':
      if(!/^\d{13}$/.test(cf.replace(/\s/g,'')))
        return 'Numéro fiscal français invalide (13 chiffres)';
      break;
    case 'DE':
      if(!/^\d{11}$/.test(cf.replace(/\s/g,'')))
        return 'Steuer-ID ungültig (11 Ziffern erforderlich)';
      break;
    case 'UK':
      if(!/^[A-Z]{2}\d{6}[A-D]$/i.test(cf.replace(/\s/g,'')) && !/^\d{10}$/.test(cf.replace(/\s/g,'')))
        return 'NI Number invalid (e.g. AB123456C) or UTR (10 digits)';
      break;
  }
  return null;
}

function inviaRegistrazione(){
  var nome      = document.getElementById('reg-nome').value.trim();
  var cognome   = document.getElementById('reg-cognome').value.trim();
  var email     = document.getElementById('reg-email').value.trim();
  var tel       = document.getElementById('reg-tel').value.trim();
  var paese     = document.getElementById('reg-paese').value;
  var cf        = document.getElementById('reg-cf').value.trim().toUpperCase();
  var indirizzo = document.getElementById('reg-indirizzo').value.trim();
  var cap       = document.getElementById('reg-cap').value.trim();
  var citta     = document.getElementById('reg-citta').value.trim();
  var nascita   = document.getElementById('reg-nascita').value.trim();
  var piva      = document.getElementById('reg-piva').value.trim();
  var azioni    = document.getElementById('reg-azioni').checked;
  var etf       = document.getElementById('reg-etf').checked;
  var fondi     = document.getElementById('reg-fondi').checked;
  var ordini    = document.getElementById('reg-ordini').checked;
  var note      = document.getElementById('reg-note').value.trim();
  var gdpr      = document.getElementById('reg-gdpr').checked;
  var errEl     = document.getElementById('reg-err');
  errEl.textContent = '';

  var T2 = {
    it:{err_nome:'Nome e cognome obbligatori.',err_email:'Email non valida.',err_tel:'Telefono obbligatorio.',err_paese:'Seleziona il tuo paese.',err_cf:'Inserisci il Codice Fiscale oppure la P.IVA.',err_indirizzo:'Indirizzo obbligatorio.',err_cap:'CAP obbligatorio.',err_citta:'Città obbligatoria.',err_interesse:'Seleziona almeno un servizio.',err_gdpr:'Devi accettare l\'informativa privacy per procedere.'},
    en:{err_nome:'First and last name required.',err_email:'Invalid email.',err_tel:'Phone number required.',err_paese:'Select your country.',err_cf:'Enter your Tax ID or VAT number.',err_indirizzo:'Address required.',err_cap:'Postcode required.',err_citta:'City required.',err_interesse:'Select at least one service.',err_gdpr:'You must accept the privacy policy to proceed.'},
    de:{err_nome:'Vor- und Nachname erforderlich.',err_email:'Ungültige E-Mail.',err_tel:'Telefonnummer erforderlich.',err_paese:'Land auswählen.',err_cf:'Steuer-ID oder USt-IdNr. erforderlich.',err_indirizzo:'Adresse erforderlich.',err_cap:'PLZ erforderlich.',err_citta:'Stadt erforderlich.',err_interesse:'Mindestens einen Dienst auswählen.',err_gdpr:'Bitte stimme der Datenschutzerklärung zu.'},
    fr:{err_nome:'Prénom et nom requis.',err_email:'Email invalide.',err_tel:'Téléphone obligatoire.',err_paese:'Sélectionner le pays.',err_cf:'Code fiscal ou numéro de TVA requis.',err_indirizzo:'Adresse requise.',err_cap:'Code postal requis.',err_citta:'Ville requise.',err_interesse:'Sélectionner au moins un service.',err_gdpr:'Vous devez accepter la politique de confidentialité.'},
    es:{err_nome:'Nombre y apellido obligatorios.',err_email:'Email inválido.',err_tel:'Teléfono obligatorio.',err_paese:'Selecciona el país.',err_cf:'Introduce el NIF/NIE o el CIF (empresa).',err_indirizzo:'Dirección obligatoria.',err_cap:'Código postal obligatorio.',err_citta:'Ciudad obligatoria.',err_interesse:'Selecciona al menos un servicio.',err_gdpr:'Debes aceptar la política de privacidad para continuar.'},
  };
  var e = T2[lang]||T2.it;

  if(!nome||!cognome)              { errEl.textContent=e.err_nome;      return; }
  if(!email||!email.includes('@')) { errEl.textContent=e.err_email;     return; }
  if(!tel)                         { errEl.textContent=e.err_tel;       return; }
  if(!paese)                       { errEl.textContent=e.err_paese;     return; }
  if(!cf&&!piva)                   { errEl.textContent=e.err_cf;        return; }
  if(cf){ var cfErr=_validaCF(cf,paese); if(cfErr){ errEl.textContent=cfErr; return; } }
  if(!indirizzo)                   { errEl.textContent=e.err_indirizzo; return; }
  if(!cap)                         { errEl.textContent=e.err_cap;       return; }
  if(!citta)                       { errEl.textContent=e.err_citta;     return; }
  if(!azioni&&!etf&&!fondi&&!ordini){ errEl.textContent=e.err_interesse; return; }
  if(!gdpr)                        { errEl.textContent=e.err_gdpr;      return; }

  fetch('/api/registrazione',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      nome:nome, cognome:cognome, email:email, paese:paese,
      telefono:tel, codice_fiscale:cf, indirizzo:indirizzo,
      cap:cap, citta:citta, data_nascita:nascita, p_iva:piva,
      piano_azioni:  azioni  ? 'BASIC' : 'NONE',
      piano_etf:     etf     ? 'BASIC' : 'NONE',
      piano_fondi:   fondi   ? 'BASIC' : 'NONE',
      piano_ordini:  ordini  ? 'BASIC' : 'NONE',
      note:note, gdpr_consent:true
    })
  }).then(function(r){return r.json();}).then(function(res){
    if(res.ok){
      window.location.href = '/grazie';
    } else {
      errEl.textContent = res.msg || 'Errore. Riprova.';
    }
  }).catch(function(){ errEl.textContent='Errore di rete. Riprova.'; });
}

// Init
fetch('/api/servizi').then(function(r){return r.json();}).then(function(sv){
  servizi=sv; renderPlans();
});
setLang('it');
</script>
</body>
</html>"""

# Sostituisce i placeholder con i valori reali calcolati dai file dati
LANDING_HTML = (
    LANDING_HTML
    .replace('__NTOT_IT__', _fmt_it(_N_TOT))
    .replace('__NTOT_EN__', _fmt_en(_N_TOT))
    .replace('__NAZ__',     _fmt_it(_N_AZ))
    .replace('__NETF__',    _fmt_it(_N_ETF_TOT))
    .replace('__NFD__',     _fmt_it(_N_FD))
)

# ─── CLIENT LOGIN PAGE ──────────────────────────────────────
CLIENT_LOGIN_HTML = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Area Riservata — Fuerte Venture Capital</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0f1e;font-family:'Segoe UI',Arial,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center}}
.card{{background:#111827;border:1px solid rgba(246,173,85,.2);border-radius:16px;padding:2.5rem 2rem;width:100%;max-width:400px}}
.logo{{text-align:center;margin-bottom:2rem}}
.logo img{{height:44px;width:auto;border-radius:9px;margin-bottom:.8rem}}
.logo h1{{font-size:20px;font-weight:700;color:#fff}}
label{{display:block;font-size:.82rem;color:#888;margin-bottom:.4rem;margin-top:1rem}}
input{{width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:8px;padding:.75rem 1rem;color:#e0e0e0;font-size:.95rem;outline:none;transition:border .2s}}
input:focus{{border-color:#F6AD55}}
.btn{{width:100%;background:#F6AD55;color:#0a0f1e;border:none;border-radius:8px;padding:.85rem;font-size:1rem;font-weight:700;cursor:pointer;margin-top:1.5rem;transition:opacity .2s}}
.btn:hover{{opacity:.85}}
.err{{color:#FC8181;font-size:.85rem;margin-top:.8rem;text-align:center}}
.footer{{text-align:center;margin-top:1.5rem;font-size:.75rem;color:#444}}
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    {logo}
    <h1>Area Riservata</h1>
  </div>
  {error}
  <form method="POST" action="/api/client-login">
    <input type="hidden" name="next" value="{next_url}">
    <label>Email</label>
    <input type="email" name="email" placeholder="la tua email" required autocomplete="email">
    <label>Password</label>
    <div style="position:relative">
      <input type="password" name="pwd" id="login-pwd" placeholder="password" required autocomplete="current-password" style="padding-right:2.8rem">
      <button type="button" onclick="var i=document.getElementById('login-pwd');i.type=i.type==='password'?'text':'password';this.textContent=i.type==='password'?'👁':'🙈'" style="position:absolute;right:.7rem;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;color:#666;font-size:1.1rem;padding:0;line-height:1" tabindex="-1">👁</button>
    </div>
    <button class="btn" type="submit">Accedi</button>
  </form>
  <div class="footer"><a href="/reset-password" style="color:#F6AD55;text-decoration:none">Password dimenticata?</a><br>
  <span style="font-size:.68rem;color:#333">Dati trattati ai sensi del Reg. UE 2016/679 (GDPR) da Fuerte Venture Capital SL · CIF B23881691</span></div>
</div>
</body></html>"""

FORGOT_PWD_HTML = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reset Password — Fuerte Venture Capital</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0f1e;font-family:'Segoe UI',Arial,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center}}
.card{{background:#111827;border:1px solid rgba(246,173,85,.2);border-radius:16px;padding:2.5rem 2rem;width:100%;max-width:400px}}
.logo{{text-align:center;margin-bottom:2rem}}
.logo img{{height:44px;width:auto;border-radius:9px;margin-bottom:.8rem}}
.logo h1{{font-size:20px;font-weight:700;color:#fff}}
p{{color:#aaa;font-size:.88rem;text-align:center;margin-bottom:1.2rem;line-height:1.6}}
label{{display:block;font-size:.82rem;color:#888;margin-bottom:.4rem;margin-top:1rem}}
input{{width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:8px;padding:.75rem 1rem;color:#e0e0e0;font-size:.95rem;outline:none;transition:border .2s}}
input:focus{{border-color:#F6AD55}}
.btn{{width:100%;background:#F6AD55;color:#0a0f1e;border:none;border-radius:8px;padding:.85rem;font-size:1rem;font-weight:700;cursor:pointer;margin-top:1.5rem;transition:opacity .2s}}
.btn:hover{{opacity:.85}}
.msg{{font-size:.85rem;margin-top:.8rem;text-align:center}}
.err{{color:#FC8181}}.ok{{color:#68D391}}
.back{{display:block;text-align:center;margin-top:1.2rem;font-size:.8rem;color:#666;text-decoration:none}}
.back:hover{{color:#F6AD55}}
</style>
</head>
<body>
<div class="card">
  <div class="logo">{logo}<h1>Reset Password</h1></div>
  <p>Inserisci la tua email. Riceverai un link per impostare una nuova password (valido 1 ora).</p>
  {msg}
  <form method="POST" action="/api/forgot-password">
    <label>Email</label>
    <input type="email" name="email" placeholder="la tua email" required autocomplete="email">
    <button class="btn" type="submit">Invia link di reset</button>
  </form>
  <a href="/client-login" class="back">← Torna al login</a>
</div>
</body></html>"""

RESET_PWD_HTML = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nuova Password — Fuerte Venture Capital</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0f1e;font-family:'Segoe UI',Arial,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center}}
.card{{background:#111827;border:1px solid rgba(246,173,85,.2);border-radius:16px;padding:2.5rem 2rem;width:100%;max-width:400px}}
.logo{{text-align:center;margin-bottom:2rem}}
.logo img{{height:44px;width:auto;border-radius:9px;margin-bottom:.8rem}}
.logo h1{{font-size:20px;font-weight:700;color:#fff}}
label{{display:block;font-size:.82rem;color:#888;margin-bottom:.4rem;margin-top:1rem}}
input{{width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:8px;padding:.75rem 1rem;color:#e0e0e0;font-size:.95rem;outline:none;transition:border .2s}}
input:focus{{border-color:#F6AD55}}
.btn{{width:100%;background:#F6AD55;color:#0a0f1e;border:none;border-radius:8px;padding:.85rem;font-size:1rem;font-weight:700;cursor:pointer;margin-top:1.5rem;transition:opacity .2s}}
.btn:hover{{opacity:.85}}
.err{{color:#FC8181;font-size:.85rem;margin-top:.8rem;text-align:center}}
.back{{display:block;text-align:center;margin-top:1.2rem;font-size:.8rem;color:#666;text-decoration:none}}
.back:hover{{color:#F6AD55}}
</style>
</head>
<body>
<div class="card">
  <div class="logo">{logo}<h1>Nuova Password</h1></div>
  {error}
  <form method="POST" action="/api/reset-password">
    <input type="hidden" name="token" value="{token}">
    <label>Nuova password</label>
    <div style="position:relative">
      <input type="password" name="pwd1" id="p1" placeholder="minimo 8 caratteri" required minlength="8" style="padding-right:2.8rem">
      <button type="button" onclick="var i=document.getElementById('p1');i.type=i.type==='password'?'text':'password'" style="position:absolute;right:.7rem;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;color:#666;font-size:1.1rem;padding:0" tabindex="-1">👁</button>
    </div>
    <label>Conferma password</label>
    <input type="password" name="pwd2" id="p2" placeholder="ripeti la password" required minlength="8">
    <button class="btn" type="submit" onclick="if(document.getElementById('p1').value!==document.getElementById('p2').value){{alert('Le password non coincidono');return false}}">Imposta password</button>
  </form>
  <a href="/client-login" class="back">← Torna al login</a>
</div>
</body></html>"""


def _build_ordine_bancario(nome: str, email: str, piano_ordini: str = 'BASIC', dati_fiscali: dict = None, prefill_rows: list = None, tipo: str = '') -> str:
    """Pagina Order Builder per il cliente autenticato."""
    import html as _html
    import json as _json
    nome_safe  = _html.escape(nome)
    email_safe = _html.escape(email)
    nome_js    = nome.replace('\\','\\\\').replace('"','\\"')
    email_js   = email.replace('\\','\\\\').replace('"','\\"')
    _piano_ord = (piano_ordini or 'BASIC').upper()
    anagrafica_js = _json.dumps(dati_fiscali or {}, ensure_ascii=False)
    prefill_js = _json.dumps(prefill_rows or [], ensure_ascii=False)
    _tipo_labels = {'azioni': 'Azioni', 'etf': 'ETF', 'fondi': 'Fondi'}
    _tipo_label  = _tipo_labels.get(tipo, '')
    _page_title  = f'Crea Ordine {_tipo_label}'.strip() if _tipo_label else 'Crea Ordine Bancario'
    _page_sub    = (f'I titoli del tuo report <strong>{_tipo_label}</strong> sono gi&agrave; precaricati &mdash; '
                    f'rimuovi quelli che non vuoi, imposta le quantit&agrave; e invia al gestore.'
                    if _tipo_label else
                    'Inserisci i titoli e le quantita &mdash; il sistema genera un\'email professionale pronta per il tuo gestore bancario.')

    page = '''<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__PAGE_TITLE__ — Fuerte Screener</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0f1e;color:#e2e8f0;font-family:Arial,sans-serif;min-height:100vh}
.hdr{background:linear-gradient(135deg,#1a365d,#2b6cb0);padding:14px 24px;display:flex;align-items:center;justify-content:space-between}
.hdr-logo{font-weight:700;font-size:15px;letter-spacing:1px;color:#fff}
.hdr-back{color:#90cdf4;text-decoration:none;font-size:13px}
.hdr-back:hover{color:#fff}
.wrap{max-width:980px;margin:0 auto;padding:28px 16px}
h1{font-size:22px;font-weight:700;margin-bottom:4px}
.sub{color:#718096;font-size:13px;margin-bottom:24px}
.card{background:#131929;border:1px solid #1e2a3a;border-radius:10px;padding:22px 24px;margin-bottom:18px}
.card-title{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:#90cdf4;
            margin-bottom:16px;border-bottom:1px solid #1e2a3a;padding-bottom:10px}
.form-row{display:flex;gap:12px;margin-bottom:12px;flex-wrap:wrap}
.fg{flex:1;min-width:160px}
.fg label{font-size:11px;color:#718096;text-transform:uppercase;letter-spacing:.5px;display:block;margin-bottom:5px}
.fg input,.fg textarea,.fg select{width:100%;background:#0a0f1e;border:1px solid #2d3748;border-radius:6px;
                        color:#e2e8f0;padding:8px 11px;font-size:13px}
.fg input:focus,.fg textarea:focus,.fg select:focus{outline:none;border-color:#2b6cb0}
.fg textarea{resize:vertical}
.fg select option{background:#1a2035}
.fg .hint{font-size:11px;color:#718096;margin-top:4px}
.risk-card .card-title{color:#f6ad55;border-color:#f6ad5533}
.tbl-wrap{overflow-x:auto}
table.ot{width:100%;border-collapse:collapse;font-size:13px}
table.ot th{padding:8px 9px;text-align:left;color:#718096;font-size:10px;
            text-transform:uppercase;letter-spacing:.5px;border-bottom:1px solid #1e2a3a;white-space:nowrap}
table.ot th.r{text-align:right}
table.ot td{padding:5px 5px;border-bottom:1px solid #0f1520;vertical-align:middle}
table.ot input{background:#0a0f1e;border:1px solid #2d3748;border-radius:4px;
               color:#e2e8f0;padding:6px 8px;font-size:13px;width:100%}
table.ot input.tk{font-family:monospace;font-weight:700;text-transform:uppercase;width:95px}
table.ot input:focus{outline:none;border-color:#2b6cb0}
table.ot input[readonly]{color:#90cdf4;border-color:#1e2a3a;cursor:default;background:#0a0f1e}
table.ot input.num{text-align:right;width:90px}
table.ot .cb-col{text-align:center;width:32px;padding:5px 2px}
table.ot .cb-col input[type=checkbox]{width:auto;height:15px;cursor:pointer;accent-color:#2b6cb0}
table.ot .w-name{min-width:130px}
table.ot .w-mkt{width:100px}
table.ot .w-curr{width:52px;text-align:center}
.btn-rm{background:none;border:1px solid #e53e3e44;color:#e53e3e;
        border-radius:4px;padding:4px 8px;cursor:pointer;font-size:12px}
.btn-rm:hover{background:#e53e3e22}
.btn-add{background:#1e2a3a;border:1px dashed #2b6cb066;color:#90cdf4;
         border-radius:6px;padding:9px;cursor:pointer;font-size:13px;
         margin-top:10px;width:100%}
.btn-add:hover{background:#2b6cb022;border-color:#2b6cb0}
.summary{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
.chip{background:#1a365d33;border:1px solid #2b6cb044;border-radius:6px;padding:8px 14px}
.chip .cl{font-size:10px;color:#718096;text-transform:uppercase;letter-spacing:.5px}
.chip .cv{font-weight:700;color:#f6ad55;font-family:monospace;font-size:15px;margin-top:2px}
.cb-row{margin-top:10px;font-size:13px;color:#a0aec0;cursor:pointer}
.cb-row input{margin-right:6px;cursor:pointer}
.status{padding:11px 14px;border-radius:6px;font-size:13px;margin-top:14px;display:none}
.ok{background:#276749;color:#9ae6b4}.err{background:#742a2a;color:#feb2b2}
.btns{display:flex;gap:12px;justify-content:flex-end;margin-top:22px;flex-wrap:wrap}
.btn-pre{background:#1e2a3a;border:1px solid #2b6cb0;color:#90cdf4;
         padding:11px 22px;border-radius:8px;cursor:pointer;font-size:14px;font-weight:600}
.btn-pre:hover{background:#2b6cb022}
.btn-snd{background:#2b6cb0;border:none;color:#fff;
         padding:11px 26px;border-radius:8px;cursor:pointer;font-size:14px;font-weight:700}
.btn-snd:hover{background:#3182ce}
.btn-snd:disabled{opacity:.5;cursor:default}
.btn-csv{background:#1a2e1a;border:1px solid #38a16966;color:#68d391;
         padding:10px 20px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600}
.btn-csv:hover{background:#38a16922;border-color:#68d391}
.pl-desc{font-size:11px;color:#718096;margin-top:12px;line-height:1.8}
.pl-desc code{color:#90cdf4;background:#0a0f1e;padding:1px 5px;
              border-radius:3px;font-size:11px;font-family:monospace}
.overlay{position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:1000;
         display:none;align-items:center;justify-content:center}
.overlay.show{display:flex}
.modal{background:#131929;border:1px solid #2b6cb0;border-radius:12px;
       width:90%;max-width:720px;max-height:90vh;overflow:auto;padding:26px}
.modal h3{font-size:16px;margin-bottom:14px;color:#90cdf4}
.mc{float:right;background:none;border:none;color:#718096;font-size:20px;cursor:pointer}
.pt{width:100%;border-collapse:collapse;font-size:13px;margin-top:10px}
.pt th{background:#1a365d;color:#90cdf4;padding:8px 12px;text-align:left;font-size:11px;text-transform:uppercase}
.pt td{padding:8px 12px;border-bottom:1px solid #1e2a3a}
.ptot{background:#f6ad5511;border:1px solid #f6ad5533;border-radius:6px;
      padding:12px 16px;text-align:right;font-size:16px;font-weight:700;
      color:#f6ad55;margin-top:8px;font-family:monospace}
.spin{display:inline-block;width:12px;height:12px;border:2px solid #90cdf4;
      border-top-color:transparent;border-radius:50%;animation:spin .7s linear infinite;margin-left:6px}
@keyframes spin{to{transform:rotate(360deg)}}
.sl-toggle{background:none;border:1px solid #e53e3e55;color:#e53e3e;border-radius:6px;
           padding:5px 14px;cursor:pointer;font-size:11px;font-weight:600}
.sl-toggle:hover{background:#e53e3e11}
table.sl-tbl{width:100%;border-collapse:collapse;font-size:13px;margin-top:10px}
table.sl-tbl th{padding:7px 10px;text-align:left;color:#718096;font-size:10px;
                text-transform:uppercase;letter-spacing:.5px;border-bottom:1px solid #f6ad5533}
table.sl-tbl td{padding:6px 5px;border-bottom:1px solid #0f1520;vertical-align:middle}
table.sl-tbl input.num{text-align:right;width:90px;background:#0a0f1e;border:1px solid #2d3748;
                       border-radius:4px;color:#e2e8f0;padding:6px 8px;font-size:13px}
table.sl-tbl input.num:focus{outline:none;border-color:#f6ad55}
</style>
</head>
<body>
<div class="hdr">
  <span class="hdr-logo">FUERTE SCREENER</span>
  <a href="/area-clienti" class="hdr-back">← Area Riservata</a>
</div>
<div class="wrap">
  <h1>__PAGE_TITLE__</h1>
  <p class="sub">__PAGE_SUB__</p>

  <div class="card">
    <div class="card-title">Titoli da Acquistare</div>
    <div id="prefill-info" style="display:none"></div>
    <div id="debug-msg" style="font-size:12px;color:#f6ad55;padding:6px 0 4px;font-family:monospace"></div>
    <div class="tbl-wrap">
      <table class="ot" id="tbl">
        <thead><tr>
          <th style="width:32px" title="Includi nel ordine">☑</th>
          <th style="width:100px">Ticker</th>
          <th class="w-name">Denominazione</th>
          <th class="w-mkt">Mercato</th>
          <th class="w-curr r">Val.</th>
          <th class="r" style="width:110px">Prezzo Rif.</th>
          <th class="r" style="width:90px">Quantita</th>
          <th class="r" style="width:105px">Importo</th>
          <th style="width:38px"></th>
        </tr></thead>
        <tbody id="rows"></tbody>
      </table>
    </div>
    <div style="display:flex;gap:8px;margin-top:10px">
      <button class="btn-add" onclick="pickerOpen()" style="flex:2">+ Aggiungi altro titolo dal Report</button>
      <button class="btn-add" onclick="addRow()" style="flex:1;color:#718096;font-size:12px">&#x270E; Inserisci manuale</button>
    </div>
    <div class="summary" id="summary"></div>
  </div>

  <div class="card">
    <div class="card-title">Parametri di Esecuzione</div>
    <div class="form-row">
      <div class="fg" style="max-width:160px">
        <label>Tipologia Strumento</label>
        <select id="tipo_strumento">
          <option value="AZIONE">Azione</option>
          <option value="ETF">ETF</option>
          <option value="FONDO">Fondo</option>
          <option value="OBBLIGAZIONE">Obbligazione</option>
        </select>
      </div>
      <div class="fg" style="max-width:220px">
        <label>Tipo di Ordine</label>
        <select id="tipo_ordine" onchange="toggleLimitPrice()">
          <option value="MKT">Al Meglio (Market)</option>
          <option value="LMT">Con Limite di Prezzo (Limit)</option>
        </select>
      </div>
      <div class="fg" id="fg_limit" style="display:none;max-width:140px">
        <label>Prezzo Limite</label>
        <input type="number" id="prezzo_limite" step="0.0001" min="0" placeholder="0.0000">
      </div>
      <div class="fg" style="max-width:200px">
        <label>Validità Ordine</label>
        <select id="validita" onchange="toggleValiditaDate()">
          <option value="DAY">Al Giorno</option>
          <option value="GTC">GTC (Good Till Cancelled)</option>
          <option value="DATE">Fino a Data</option>
        </select>
      </div>
      <div class="fg" id="fg_validita_date" style="display:none;max-width:160px">
        <label>Data Scadenza</label>
        <input type="date" id="validita_data">
      </div>
      <div class="fg" style="position:relative">
        <label>Conto di Appoggio <span style="opacity:.45;font-size:.78rem;font-weight:400">(opzionale · auto-memorizzato)</span></label>
        <div style="display:flex;gap:.35rem;align-items:stretch">
          <input type="text" id="conto" placeholder="es. 228245/02" autocomplete="off"
                 style="flex:1;padding-right:2.2rem"
                 oninput="contiFilter()" onfocus="contiShow()" onblur="setTimeout(contiHide,180)">
          <button type="button" onclick="contiToggle()" tabindex="-1"
                  style="padding:0 .65rem;background:#1a2e40;border:1px solid #2C5282;border-radius:6px;color:#90cdf4;cursor:pointer;font-size:.9rem;flex-shrink:0">▾</button>
        </div>
        <div id="conti-drop" style="display:none;position:absolute;left:0;right:0;top:calc(100% + 2px);
             background:#111827;border:1px solid #2C5282;border-radius:8px;z-index:200;
             box-shadow:0 8px 24px rgba(0,0,0,.6);overflow:hidden">
          <div id="conti-list-inner"></div>
          <div style="padding:.35rem .8rem;border-top:1px solid rgba(255,255,255,.05);font-size:.71rem;color:#4a5568">
            💡 Salvato automaticamente dopo ogni ordine
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="card risk-card" id="sl-card" style="display:none">
    <div class="card-title" style="display:flex;align-items:center;justify-content:space-between">
      <span>Stop Loss / Take Profit &mdash; Azioni selezionate</span>
      <button class="sl-toggle" id="sl-skip-btn" onclick="toggleSL()">&#x2715; Non inserire Stop Loss</button>
    </div>
    <div id="sl-body">
      <table class="sl-tbl">
        <thead><tr>
          <th style="width:95px">Ticker</th>
          <th>Denominazione</th>
          <th style="width:140px;text-align:right">Stop Loss %</th>
          <th style="width:140px;text-align:right">Take Profit %</th>
        </tr></thead>
        <tbody id="sl-rows"></tbody>
      </table>
      <p style="font-size:11px;color:#718096;margin-top:10px;line-height:1.6">
        I prezzi Stop Loss e Take Profit calcolati saranno indicati nell\'email al gestore.
        Le istruzioni di protezione devono essere impostate autonomamente sulla propria piattaforma bancaria.
      </p>
    </div>
    <div id="sl-skipped" style="display:none;font-size:13px;color:#718096;padding:4px 0">
      Stop Loss non inserito &mdash;
      <button style="background:none;border:none;color:#90cdf4;cursor:pointer;font-size:13px;text-decoration:underline"
              onclick="toggleSL()">Aggiungi</button>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Dati del Cliente Ordinante</div>
    <div class="form-row">
      <div class="fg" style="flex:3">
        <label>Indirizzo</label>
        <input type="text" id="ag_indirizzo" placeholder="Via Roma 1">
      </div>
      <div class="fg" style="max-width:100px">
        <label>CAP</label>
        <input type="text" id="ag_cap" placeholder="00100">
      </div>
      <div class="fg">
        <label>Città</label>
        <input type="text" id="ag_citta" placeholder="Roma">
      </div>
      <div class="fg" style="max-width:100px">
        <label>Paese</label>
        <input type="text" id="ag_paese" placeholder="IT">
      </div>
    </div>
    <div class="form-row">
      <div class="fg">
        <label>Codice Fiscale / NIE</label>
        <input type="text" id="ag_codice_fiscale" placeholder="RSSMRA80A01H501Z" style="text-transform:uppercase">
      </div>
      <div class="fg">
        <label>P.IVA <span style="font-weight:400;opacity:.55">(opzionale)</span></label>
        <input type="text" id="ag_p_iva" placeholder="">
      </div>
      <div class="fg">
        <label>Telefono</label>
        <input type="text" id="ag_telefono" placeholder="+39 333 1234567">
      </div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Destinatario &amp; Invio</div>
    <div class="form-row" style="margin-bottom:.75rem">
      <div class="fg" style="position:relative">
        <label>Profilo Banca Salvato <span style="opacity:.45;font-size:.78rem;font-weight:400">(pre-compila tutti i campi)</span></label>
        <div style="display:flex;gap:.35rem">
          <div style="flex:1;position:relative">
            <input type="text" id="profilo-inp" placeholder="Cerca banca salvata..." autocomplete="off"
                   style="width:100%" oninput="profiliFilter()" onfocus="profiliShow()" onblur="setTimeout(profiliHide,200)">
            <button type="button" onclick="profiliToggle()" tabindex="-1"
                    style="position:absolute;right:.45rem;top:50%;transform:translateY(-50%);
                           background:none;border:none;color:#90cdf4;cursor:pointer;font-size:.85rem">&#9660;</button>
          </div>
          <button type="button" onclick="profiliSalva()"
                  style="padding:0 .9rem;background:#1a2e40;border:1px solid #2C5282;
                         border-radius:6px;color:#90cdf4;cursor:pointer;font-size:.78rem;
                         white-space:nowrap;flex-shrink:0" title="Salva profilo banca corrente">&#x1F4BE; Salva</button>
        </div>
        <div id="profili-drop" style="display:none;position:absolute;left:0;right:0;top:calc(100% + 2px);
             background:#111827;border:1px solid #2C5282;border-radius:8px;z-index:200;
             box-shadow:0 8px 24px rgba(0,0,0,.6);overflow:hidden;max-height:220px;overflow-y:auto">
          <div id="profili-list"></div>
          <div style="padding:.3rem .8rem;border-top:1px solid rgba(255,255,255,.05);font-size:.7rem;color:#4a5568">
            &#x1F4BE; Salvato automaticamente dopo ogni ordine
          </div>
        </div>
        <div id="profili-msg" style="font-size:.75rem;margin-top:.25rem;min-height:.9rem"></div>
      </div>
    </div>
    <div class="form-row">
      <div class="fg" style="flex:2">
        <label>Nome Banca / Intermediario *</label>
        <input type="text" id="bank_nome" placeholder="es. Banca Sella, Fineco, Directa...">
      </div>
      <div class="fg" style="flex:2">
        <label>Nome Gestore *</label>
        <input type="text" id="nome_gestore" placeholder="es. Mario Rossi">
      </div>
    </div>
    <div class="form-row">
      <div class="fg" style="flex:3">
        <label>Email Gestore / Dealing Desk *</label>
        <input type="email" id="bank_email" placeholder="gestore@banca.it">
      </div>
      <div class="fg" style="flex:3">
        <label>IBAN Conto Cliente</label>
        <input type="text" id="bank_iban" placeholder="IT60 X054 2811 1010 0000 0123 456"
               style="font-family:monospace;text-transform:uppercase"
               oninput="this.value=this.value.toUpperCase()">
      </div>
    </div>
    <div class="form-row">
      <div class="fg">
        <label>Note aggiuntive (opzionale)</label>
        <textarea id="note" rows="2" placeholder="es. Ordine limite, orario preferito, istruzioni speciali..."></textarea>
      </div>
    </div>
    <div style="margin-top:10px;font-size:13px;color:#68d391">
      ✉ Una copia verrà inviata automaticamente a <strong>__EMAIL_SAFE__</strong>
    </div>
    <div class="status" id="status"></div>
  </div>

  <div class="card">
    <div class="card-title">Esporta per Piattaforma di Trading</div>
    <div style="display:flex;gap:12px;flex-wrap:wrap">
      __IBKR_BLOCK__
      <button class="btn-csv" onclick="downloadCsv(\'generico\')">
        &#x2B07; CSV Generico (.csv)
      </button>
    </div>
    <p class="pl-desc">
      __IBKR_DESC__
      <strong style="color:#e2e8f0">CSV Generico:</strong>
      riferimento per inserimento manuale su Fineco, Directa, Saxo, Trade Republic e qualsiasi altra piattaforma
    </p>
  </div>

  <div class="btns">
    <button class="btn-pre" onclick="showPreview()">Anteprima</button>
    <button class="btn-snd" id="btnSend" onclick="sendOrder()">Invia Email Bancaria</button>
  </div>
</div>

<div class="overlay" id="picker-overlay" onclick="if(event.target===this)pickerClose()">
  <div class="modal" onclick="event.stopPropagation()" style="max-width:700px">
    <button class="mc" onclick="pickerClose()">&#x2715;</button>
    <h3>Seleziona titoli dal tuo Report</h3>
    <input type="text" id="picker-search" placeholder="Cerca ticker o nome..."
           oninput="pickerFilter()"
           style="width:100%;background:#0a0f1e;border:1px solid #2d3748;border-radius:6px;
                  color:#e2e8f0;padding:8px 11px;font-size:13px;margin:10px 0">
    <div id="picker-list" style="max-height:360px;overflow-y:auto;border:1px solid #1e2a3a;border-radius:6px"></div>
    <div style="display:flex;gap:8px;margin-top:12px;justify-content:space-between;align-items:center">
      <div>
        <button onclick="pickerSelectAll(true)"
                style="background:none;border:1px solid #2d3748;color:#90cdf4;border-radius:6px;
                       padding:5px 10px;cursor:pointer;font-size:11px;margin-right:6px">Tutti</button>
        <button onclick="pickerSelectAll(false)"
                style="background:none;border:1px solid #2d3748;color:#718096;border-radius:6px;
                       padding:5px 10px;cursor:pointer;font-size:11px">Nessuno</button>
      </div>
      <button class="btn-snd" onclick="pickerAddSelected()" style="padding:9px 20px;font-size:13px">
        Aggiungi Selezionati &#x2192;
      </button>
    </div>
  </div>
</div>

<div class="overlay" id="overlay" onclick="closeModal(event)">
  <div class="modal" onclick="event.stopPropagation()">
    <button class="mc" onclick="closeModal()">&#x2715;</button>
    <h3>Anteprima Ordine</h3>
    <div id="previewContent"></div>
    <div style="text-align:right;margin-top:14px">
      <button class="btn-pre" onclick="closeModal()">Chiudi</button>
    </div>
  </div>
</div>

<script>
var rowId = 0;
var CLIENT_NOME       = "__NOME_JS__";
var CLIENT_EMAIL      = "__EMAIL_JS__";
var CLIENT_ANAGRAFICA = __ANAGRAFICA_JS__;
var PREFILL_DATA      = __PREFILL_ROWS_JS__;
var PAGE_TIPO         = "__TIPO_JS__";

function toggleLimitPrice(){
  var v=document.getElementById('tipo_ordine').value;
  document.getElementById('fg_limit').style.display=(v==='LMT'?'':'none');
}
function toggleValiditaDate(){
  var v=document.getElementById('validita').value;
  document.getElementById('fg_validita_date').style.display=(v==='DATE'?'':'none');
}
function getExecParams(){
  return {
    tipo_strumento: document.getElementById('tipo_strumento').value,
    tipo_ordine:    document.getElementById('tipo_ordine').value,
    prezzo_limite:  document.getElementById('prezzo_limite').value||'',
    validita:       document.getElementById('validita').value,
    validita_data:  document.getElementById('validita_data').value||'',
    conto:          document.getElementById('conto').value.trim(),
  };
}

function addRow() {
  var id = rowId++;
  var tr = document.createElement('tr');
  tr.id = 'row_' + id;
  tr.innerHTML =
    '<td class="cb-col"><input type="checkbox" id="cb_'+id+'" checked onchange="updateSummary()"></td>' +
    '<td><input class="tk" type="text" placeholder="AAPL"' +
    ' onblur="lookupPrice(this,' + id + ')" oninput="this.value=this.value.toUpperCase()"></td>' +
    '<td class="w-name"><input type="text" id="nm_' + id + '" placeholder="—" readonly></td>' +
    '<td class="w-mkt"><input type="text" id="mk_' + id + '" placeholder="—" readonly style="font-size:11px"></td>' +
    '<td class="w-curr"><input type="text" id="cu_' + id + '" placeholder="—" readonly style="text-align:center"></td>' +
    '<td><input class="num" type="number" id="pr_' + id + '" placeholder="0.0000"' +
    ' step="0.0001" min="0" onchange="onPriceChange(' + id + ')"></td>' +
    '<td><input class="num" type="number" id="qt_' + id + '" placeholder="0"' +
    ' step="1" min="0" oninput="calcFromQty(' + id + ')"></td>' +
    '<td><input class="num" type="number" id="am_' + id + '" placeholder="0.00"' +
    ' step="0.01" min="0" oninput="calcFromAmt(' + id + ')"></td>' +
    '<td><button class="btn-rm" onclick="removeRow(' + id + ')">&#x2715;</button></td>';
  document.getElementById('rows').appendChild(tr);
  tr.querySelector('.tk').focus();
}

function removeRow(id) {
  var el = document.getElementById('row_' + id);
  if (el) { el.remove(); updateSummary(); }
}

function gp(id){ var v=parseFloat(document.getElementById('pr_'+id).value); return isNaN(v)||v<=0?null:v; }
function gq(id){ var v=parseInt(document.getElementById('qt_'+id).value);   return isNaN(v)||v<0?null:v; }
function ga(id){ var v=parseFloat(document.getElementById('am_'+id).value); return isNaN(v)||v<0?null:v; }

function calcFromQty(id){ var p=gp(id),q=gq(id); if(p&&q!==null){ document.getElementById('am_'+id).value=(p*q).toFixed(2); } updateSummary(); }
function calcFromAmt(id){ var p=gp(id),a=ga(id); if(p&&a!==null){ document.getElementById('qt_'+id).value=Math.floor(a/p); } updateSummary(); }
function onPriceChange(id){ if(gq(id)!==null) calcFromQty(id); else calcFromAmt(id); }

function lookupPrice(input, id) {
  var ticker = input.value.trim().toUpperCase();
  if (!ticker) return;
  var spin = document.createElement('span'); spin.className='spin'; spin.id='sp_'+id;
  input.parentNode.appendChild(spin);
  fetch('/api/ordine/prezzi', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({tickers:[ticker]})
  }).then(function(r){return r.json();}).then(function(data){
    var d = data[ticker];
    if (d) {
      document.getElementById('nm_'+id).value = d.name     || ticker;
      document.getElementById('mk_'+id).value = d.exchange || '—';
      document.getElementById('cu_'+id).value = d.currency || '—';
      if (d.price) { document.getElementById('pr_'+id).value = d.price.toFixed(4); calcFromQty(id); }
    }
  }).catch(function(){}).finally(function(){
    var s=document.getElementById('sp_'+id); if(s) s.remove();
  });
}

function updateSummary() {
  var totals = {};
  document.querySelectorAll('#rows tr').forEach(function(tr){
    var id = tr.id.replace('row_','');
    var cu = (document.getElementById('cu_'+id)||{}).value||'';
    var am = ga(id);
    if (cu && am) totals[cu] = (totals[cu]||0) + am;
  });
  var div = document.getElementById('summary'); div.innerHTML='';
  Object.keys(totals).forEach(function(c){
    var chip=document.createElement('div'); chip.className='chip';
    chip.innerHTML='<div class="cl">'+c+'</div><div class="cv">'+c+' '+totals[c].toLocaleString('it-IT',{minimumFractionDigits:2,maximumFractionDigits:2})+'</div>';
    div.appendChild(chip);
  });
  var n = document.querySelectorAll('#rows tr').length;
  if (n>0){ var chip=document.createElement('div'); chip.className='chip';
    chip.innerHTML='<div class="cl">Posizioni</div><div class="cv">'+n+'</div>'; div.appendChild(chip); }
  rebuildSLTable();
}

// ─── Picker titoli dal report ─────────────────────────────────────────────────
var _pickerData = null;
var _pickerFiltered = [];

function _pickerPreload() {
  if (!PAGE_TIPO) return;
  fetch('/api/ordine/report-stocks?tipo=' + PAGE_TIPO)
    .then(function(r){ return r.json(); })
    .then(function(data){
      _pickerData = data;
      _pickerFiltered = data;
      var _dbgEl = document.getElementById('debug-msg');
      if (_dbgEl) _dbgEl.textContent = 'SERVER: ' + PREFILL_DATA.length + ' titoli | FETCH: ' + data.length + ' titoli';
      if (data.length > 0 && document.getElementById('rows').children.length === 0) {
        data.forEach(function(s) {
          addPrefillRow(s.ticker, s.nome||s.ticker, s.mercato||'', s.valuta||'', s.tipo||PAGE_TIPO, true);
        });
        loadBatchPrices();
      }
    })
    .catch(function(e){
      var _dbgEl = document.getElementById('debug-msg');
      if (_dbgEl) _dbgEl.textContent = 'ERRORE FETCH: ' + e;
    });
}

function pickerOpen() {
  document.getElementById('picker-overlay').classList.add('show');
  document.getElementById('picker-search').value = '';
  if (_pickerData === null) {
    _pickerLoad();
  } else {
    _pickerFiltered = _pickerData;
    pickerRender(_pickerFiltered);
  }
}

function pickerClose() {
  document.getElementById('picker-overlay').classList.remove('show');
}

function _pickerLoad() {
  var list = document.getElementById('picker-list');
  list.innerHTML = '<div style="color:#718096;font-size:13px;padding:16px;text-align:center">'
    + '<span class="spin"></span> Caricamento titoli...</div>';
  var tipo = PAGE_TIPO || 'azioni';
  fetch('/api/ordine/report-stocks?tipo=' + tipo)
    .then(function(r){ return r.json(); })
    .then(function(data){
      _pickerData = data;
      _pickerFiltered = data;
      pickerRender(data);
    })
    .catch(function(){
      list.innerHTML = '<div style="color:#e53e3e;font-size:13px;padding:16px">Errore caricamento. Usa "Manuale".</div>';
    });
}

function pickerRender(stocks) {
  var list = document.getElementById('picker-list');
  if (!stocks || stocks.length === 0) {
    list.innerHTML = '<div style="color:#718096;font-size:13px;padding:16px;text-align:center">'
      + 'Nessun titolo trovato nel report. Usa "Manuale".</div>';
    return;
  }
  list.innerHTML = stocks.map(function(s, i) {
    return '<label style="display:flex;align-items:center;gap:10px;padding:8px 10px;cursor:pointer;'
      + 'border-bottom:1px solid #0f1520;transition:background .1s" '
      + 'onmouseover="this.style.background=\\'#1a2035\\'" onmouseout="this.style.background=\\'\\'">'
      + '<input type="checkbox" class="picker-cb" data-idx="' + i + '" '
      + 'style="width:auto;height:15px;cursor:pointer;accent-color:#2b6cb0">'
      + '<span style="font-family:monospace;font-weight:700;color:#90cdf4;font-size:13px;min-width:85px">' + s.ticker + '</span>'
      + '<span style="flex:1;font-size:13px;color:#e2e8f0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + s.nome + '</span>'
      + '<span style="font-size:10px;color:#718096;min-width:55px;text-align:right">' + (s.mercato||'') + '</span>'
      + '</label>';
  }).join('');
}

function pickerFilter() {
  var q = (document.getElementById('picker-search').value || '').toLowerCase().trim();
  if (!_pickerData) return;
  _pickerFiltered = q
    ? _pickerData.filter(function(s){
        return s.ticker.toLowerCase().indexOf(q) >= 0 || (s.nome||'').toLowerCase().indexOf(q) >= 0;
      })
    : _pickerData;
  pickerRender(_pickerFiltered);
}

function pickerSelectAll(val) {
  document.querySelectorAll('.picker-cb').forEach(function(cb){ cb.checked = val; });
}

function pickerAddSelected() {
  var checked = document.querySelectorAll('.picker-cb:checked');
  if (!checked.length) { alert('Seleziona almeno un titolo'); return; }
  checked.forEach(function(cb) {
    var idx = parseInt(cb.getAttribute('data-idx'));
    var s = _pickerFiltered[idx];
    if (s) addPrefillRow(s.ticker, s.nome||s.ticker, s.mercato||'', s.valuta||'', s.tipo||PAGE_TIPO, true);
  });
  pickerClose();
  loadBatchPrices();
}
// ─────────────────────────────────────────────────────────────────────────────

function collectRows() {
  var rows=[]; var ok=true;
  document.querySelectorAll('#rows tr').forEach(function(tr){
    var id=tr.id.replace('row_','');
    var cb=document.getElementById('cb_'+id);
    if(cb && !cb.checked) return;
    var tk=(tr.querySelector('.tk')||{}).value||'';
    tk=tk.trim().toUpperCase(); if(!tk) return;
    var q=gq(id), p=gp(id), a=ga(id);
    if(!q||q<=0){ alert('Inserisci la quantita per '+tk); ok=false; return; }
    var badge=(tr.querySelector('.tipo-badge')||{});
    var tipo=badge.getAttribute?badge.getAttribute('data-tipo')||'':'';
    var sl_pct=0, tp_pct=0;
    if(tipo==='azioni' && _slVisible){
      sl_pct=parseFloat((document.getElementById('sl_pct_'+id)||{}).value)||0;
      tp_pct=parseFloat((document.getElementById('tp_pct_'+id)||{}).value)||0;
    }
    rows.push({
      ticker: tk,
      nome:     (document.getElementById('nm_'+id)||{}).value||tk,
      mercato:  (document.getElementById('mk_'+id)||{}).value||'—',
      valuta:   (document.getElementById('cu_'+id)||{}).value||'—',
      prezzo:   p||0, quantita: q, controvalore: a||(p?p*q:0),
      sl_pct: sl_pct, tp_pct: tp_pct
    });
  });
  return ok ? rows : null;
}

function fmtN(v,d){ return parseFloat(v).toLocaleString('it-IT',{minimumFractionDigits:d||2,maximumFractionDigits:d||2}); }

function showPreview() {
  var rows=collectRows(); if(!rows||rows.length===0){alert('Aggiungi almeno un titolo');return;}
  var totals={};
  var html='<table class="pt"><thead><tr><th>Ticker</th><th>Denominazione</th><th>Mercato</th>'
          +'<th style="text-align:right">Prezzo</th><th style="text-align:right">Qty</th>'
          +'<th style="text-align:right">Controvalore</th></tr></thead><tbody>';
  rows.forEach(function(r){
    totals[r.valuta]=(totals[r.valuta]||0)+r.controvalore;
    html+='<tr>'
      +'<td style="font-family:monospace;font-weight:700">'+r.ticker+'</td>'
      +'<td>'+r.nome+'</td>'
      +'<td style="font-size:11px;color:#718096">'+r.mercato+'</td>'
      +'<td style="text-align:right">'+r.valuta+' '+fmtN(r.prezzo,4)+'</td>'
      +'<td style="text-align:right;font-weight:700">'+r.quantita.toLocaleString()+'</td>'
      +'<td style="text-align:right;font-weight:700">'+r.valuta+' '+fmtN(r.controvalore)+'</td>'
      +'</tr>';
  });
  html+='</tbody></table>';
  html+='<div class="ptot">'+Object.entries(totals).map(function(e){return e[0]+' '+fmtN(e[1]);}).join(' &nbsp;|&nbsp; ')+'</div>';
  var _bNome=document.getElementById('bank_nome').value;
  var _bGestore=document.getElementById('nome_gestore').value;
  var _bEmail=document.getElementById('bank_email').value;
  var _bIban=document.getElementById('bank_iban').value;
  html+='<p style="font-size:11px;color:#718096;margin-top:8px">Destinatario: <strong>'+_bNome+'</strong>'
       +(_bGestore?' &mdash; '+_bGestore:'')
       +' &lt;'+_bEmail+'&gt;'
       +(_bIban?' &middot; IBAN: <code style="font-family:monospace">'+_bIban+'</code>':'')
       +'</p>';
  document.getElementById('previewContent').innerHTML=html;
  document.getElementById('overlay').classList.add('show');
}
function closeModal(e){ if(!e||e.target===document.getElementById('overlay')) document.getElementById('overlay').classList.remove('show'); }

function getAnagraficaFromForm(){
  return {
    indirizzo:      (document.getElementById('ag_indirizzo')||{value:''}).value.trim(),
    cap:            (document.getElementById('ag_cap')||{value:''}).value.trim(),
    citta:          (document.getElementById('ag_citta')||{value:''}).value.trim(),
    paese:          (document.getElementById('ag_paese')||{value:''}).value.trim(),
    codice_fiscale: (document.getElementById('ag_codice_fiscale')||{value:''}).value.trim(),
    p_iva:          (document.getElementById('ag_p_iva')||{value:''}).value.trim(),
    telefono:       (document.getElementById('ag_telefono')||{value:''}).value.trim(),
  };
}
function initAnagrafica(){
  var ag=CLIENT_ANAGRAFICA||{};
  ['indirizzo','cap','citta','paese','codice_fiscale','p_iva','telefono'].forEach(function(f){
    var el=document.getElementById('ag_'+f);
    if(el&&ag[f]) el.value=ag[f];
  });
}

function sendOrder() {
  var rows=collectRows(); if(!rows||rows.length===0){alert('Aggiungi almeno un titolo');return;}
  var bEmail=document.getElementById('bank_email').value.trim();
  var bNome =document.getElementById('bank_nome').value.trim();
  var bGestore=document.getElementById('nome_gestore').value.trim();
  if(!bEmail){alert("Inserisci l\'email del gestore bancario");return;}
  if(!bNome) {alert("Inserisci il nome della banca");return;}
  if(!bGestore){alert("Inserisci il nome del gestore");return;}
  var totals={};
  rows.forEach(function(r){totals[r.valuta]=(totals[r.valuta]||0)+r.controvalore;});
  var totEur=Object.values(totals).reduce(function(a,b){return a+b;},0);
  var payload={
    cliente_nome:CLIENT_NOME, cliente_email:CLIENT_EMAIL,
    bank_nome:bNome, nome_gestore:bGestore, bank_email:bEmail,
    bank_iban:document.getElementById('bank_iban').value.trim(),
    note:document.getElementById('note').value.trim(),
    cc_me:document.getElementById('cc_me').checked,
    righe:rows, totale_eur:totEur,
    exec_params: getExecParams(),
    anagrafica: getAnagraficaFromForm()
  };
  var btn=document.getElementById('btnSend');
  btn.textContent='Invio in corso...'; btn.disabled=true;
  fetch('/api/ordine/invia',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
  .then(function(r){return r.json();}).then(function(d){
    var bar=document.getElementById('status'); bar.style.display='block';
    if(d.ok){bar.className='status ok'; bar.textContent='Email inviata con successo a '+bEmail+' (Rif: '+d.riferimento+')';}
    else    {bar.className='status err'; bar.textContent='Errore: '+(d.msg||'invio fallito');}
  }).catch(function(e){
    var bar=document.getElementById('status'); bar.style.display='block';
    bar.className='status err'; bar.textContent='Errore di rete: '+e.message;
  }).finally(function(){btn.textContent='Invia Email Bancaria';btn.disabled=false;});
}

function downloadCsv(formato) {
  var rows = collectRows();
  if (!rows || rows.length === 0) { alert('Aggiungi almeno un titolo'); return; }
  var ts  = new Date().toISOString().replace(/[-:.TZ]/g,'').slice(0,14);
  var rif = 'FUERTE-' + ts;
  fetch('/api/ordine/csv', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({formato: formato, righe: rows,
                          cliente_nome: CLIENT_NOME, riferimento: rif,
                          exec_params: getExecParams()})
  }).then(function(r){ return r.text(); })
    .then(function(csvText){
      var blob = new Blob(['﻿' + csvText], {type: 'text/csv;charset=utf-8;'});
      var url  = URL.createObjectURL(blob);
      var a    = document.createElement('a');
      a.href   = url;
      a.download = (formato === 'ibkr' ? 'ordine_IBKR_' : 'ordine_Fuerte_') + ts + '.csv';
      document.body.appendChild(a);
      a.click();
      setTimeout(function(){ document.body.removeChild(a); URL.revokeObjectURL(url); }, 150);
    }).catch(function(e){ alert('Errore download: ' + e.message); });
}

var _slVisible = true;

function toggleSL() {
  _slVisible = !_slVisible;
  document.getElementById('sl-body').style.display    = _slVisible ? '' : 'none';
  document.getElementById('sl-skipped').style.display = _slVisible ? 'none' : '';
  document.getElementById('sl-skip-btn').style.display = _slVisible ? '' : 'none';
}

function rebuildSLTable() {
  var card  = document.getElementById('sl-card');
  var tbody = document.getElementById('sl-rows');
  if (!card || !tbody) return;
  var azioniRows = [];
  document.querySelectorAll('#rows tr').forEach(function(tr) {
    var id = tr.id.replace('row_','');
    var cb = document.getElementById('cb_'+id);
    if (cb && !cb.checked) return;
    var tk = (tr.querySelector('.tk')||{}).value||'';
    tk = tk.trim().toUpperCase(); if (!tk) return;
    var badge = tr.querySelector('.tipo-badge');
    if (!badge || badge.getAttribute('data-tipo') !== 'azioni') return;
    azioniRows.push({id: id, ticker: tk, nome: (document.getElementById('nm_'+id)||{}).value||tk});
  });
  if (azioniRows.length === 0) { card.style.display = 'none'; return; }
  card.style.display = '';
  // preserve existing SL/TP values before rebuild
  var saved = {};
  tbody.querySelectorAll('tr[data-row-id]').forEach(function(tr) {
    var rid = tr.getAttribute('data-row-id');
    var sl  = document.getElementById('sl_pct_'+rid);
    var tp  = document.getElementById('tp_pct_'+rid);
    saved[rid] = {sl: sl?sl.value:'', tp: tp?tp.value:''};
  });
  tbody.innerHTML = '';
  azioniRows.forEach(function(r) {
    var prev = saved[r.id]||{};
    var tr = document.createElement('tr');
    tr.setAttribute('data-row-id', r.id);
    tr.innerHTML =
      '<td style="font-family:monospace;font-weight:700;color:#90cdf4;font-size:13px">'+r.ticker+'</td>' +
      '<td style="font-size:12px;color:#a0aec0">'+r.nome+'</td>' +
      '<td style="text-align:right">' +
        '<input class="num" type="number" id="sl_pct_'+r.id+'" placeholder="es. 10"' +
        ' step="0.5" min="0" max="100" value="'+(prev.sl||'')+'">&nbsp;<span style="font-size:11px;color:#718096">%</span>' +
      '</td>' +
      '<td style="text-align:right">' +
        '<input class="num" type="number" id="tp_pct_'+r.id+'" placeholder="es. 20"' +
        ' step="0.5" min="0" value="'+(prev.tp||'')+'">&nbsp;<span style="font-size:11px;color:#718096">%</span>' +
      '</td>';
    tbody.appendChild(tr);
  });
}

function loadBatchPrices() {
  var ids = [], tickers = [];
  document.querySelectorAll('#rows tr').forEach(function(tr) {
    var id = tr.id.replace('row_', '');
    var pr = document.getElementById('pr_' + id);
    if (pr && !pr.value) {
      var tk = (tr.querySelector('.tk') || {}).value || '';
      tk = tk.trim().toUpperCase();
      if (tk) { ids.push(id); tickers.push(tk); }
    }
  });
  if (!tickers.length) { updateSummary(); return; }
  var dbg = document.getElementById('debug-msg');
  if (dbg) dbg.textContent = 'Caricamento prezzi per ' + tickers.length + ' titoli...';
  fetch('/api/ordine/prezzi', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({tickers: tickers})
  }).then(function(r) { return r.json(); }).then(function(data) {
    ids.forEach(function(id, i) {
      var tk = tickers[i];
      var d = data[tk];
      if (!d) return;
      var nmEl = document.getElementById('nm_' + id);
      var mkEl = document.getElementById('mk_' + id);
      var cuEl = document.getElementById('cu_' + id);
      var prEl = document.getElementById('pr_' + id);
      if (nmEl && !nmEl.value && d.name)     nmEl.value = d.name;
      if (mkEl && !mkEl.value && d.exchange) mkEl.value = d.exchange;
      if (cuEl && !cuEl.value && d.currency) cuEl.value = d.currency;
      if (prEl && d.price) { prEl.value = d.price.toFixed(4); calcFromQty(id); }
    });
    if (dbg) dbg.textContent = '';
    updateSummary();
  }).catch(function(e) {
    if (dbg) dbg.textContent = 'Errore prezzi: ' + e.message;
  });
}

function addPrefillRow(ticker, nome, mercato, valuta, tipo, skipLookup) {
  var id = rowId++;
  var tColors = {azioni:'#2b6cb0',etf:'#276749',fondi:'#b7791f'};
  var tLabels = {azioni:'AZIONI',etf:'ETF',fondi:'FONDI'};
  var tc = tColors[tipo]||'#2b6cb0';
  var tl = tLabels[tipo]||tipo.toUpperCase();
  var nomeSafe = (nome||'').replace(/"/g,"'");
  var tr = document.createElement('tr');
  tr.id = 'row_' + id;
  tr.innerHTML =
    '<td class="cb-col"><input type="checkbox" id="cb_'+id+'" checked onchange="updateSummary()"></td>' +
    '<td><input class="tk" type="text" value="'+ticker+'"' +
    ' onblur="lookupPrice(this,'+id+')" oninput="this.value=this.value.toUpperCase()">' +
    '<div style="margin-top:3px"><span class="tipo-badge" data-tipo="'+tipo+'" style="font-size:9px;font-weight:700;padding:1px 5px;border-radius:3px;' +
    'background:'+tc+'22;color:'+tc+';border:1px solid '+tc+'44">'+tl+'</span></div></td>' +
    '<td class="w-name"><input type="text" id="nm_'+id+'" value="'+nomeSafe+'" readonly></td>' +
    '<td class="w-mkt"><input type="text" id="mk_'+id+'" value="'+mercato+'" readonly style="font-size:11px"></td>' +
    '<td class="w-curr"><input type="text" id="cu_'+id+'" value="'+valuta+'" readonly style="text-align:center"></td>' +
    '<td><input class="num" type="number" id="pr_'+id+'" placeholder="0.0000"' +
    ' step="0.0001" min="0" onchange="onPriceChange('+id+')"></td>' +
    '<td><input class="num" type="number" id="qt_'+id+'" placeholder="0"' +
    ' step="1" min="0" oninput="calcFromQty('+id+')"></td>' +
    '<td><input class="num" type="number" id="am_'+id+'" placeholder="0.00"' +
    ' step="0.01" min="0" oninput="calcFromAmt('+id+')"></td>' +
    '<td><button class="btn-rm" onclick="removeRow('+id+')">&#x2715;</button></td>';
  document.getElementById('rows').appendChild(tr);
  if (!skipLookup) { lookupPrice(tr.querySelector('.tk'), id); }
}

function prefillRows() {
  if (PAGE_TIPO && PREFILL_DATA && PREFILL_DATA.length > 0) {
    PREFILL_DATA.forEach(function(s) {
      addPrefillRow(s.ticker, s.nome||s.ticker, s.mercato||'', s.valuta||'', s.tipo||PAGE_TIPO, true);
    });
    loadBatchPrices();
  } else if (PAGE_TIPO) {
    _pickerPreload();
  } else {
    addRow(); addRow(); addRow();
  }
}

prefillRows();
initAnagrafica();

// ─── Profili banca salvati ──────────────────────────────────
var _profiliSaved = [];

function profiliLoad(){
  fetch('/api/banche').then(function(r){return r.json();}).then(function(d){
    _profiliSaved = d.profili || [];
    profiliRender(_profiliSaved);
  }).catch(function(){});
}

function profiliRender(list){
  var el = document.getElementById('profili-list');
  if(!el) return;
  if(!list.length){
    el.innerHTML='<div style="padding:.55rem 1rem;color:#4a5568;font-size:.82rem">Nessun profilo salvato</div>';
    return;
  }
  el.innerHTML='';
  list.forEach(function(p){
    var row=document.createElement('div');
    row.style.cssText='display:flex;align-items:center;padding:.45rem .85rem;cursor:pointer;gap:.5rem;border-bottom:1px solid rgba(255,255,255,.04);transition:background .12s';
    row.addEventListener('mouseover',function(){this.style.background='#1a2e40';});
    row.addEventListener('mouseout',function(){this.style.background='';});
    row.addEventListener('mousedown',function(){profiliSelect(p);});
    var info=document.createElement('div');
    info.style.cssText='flex:1;min-width:0';
    info.innerHTML='<div style="font-size:.87rem;font-weight:600;color:#e2e8f0">'+(p.banca||'—')+'</div>'
      +'<div style="font-size:.75rem;color:#718096;font-family:monospace">'+(p.iban||'')+'</div>'
      +(p.nome_gestore?'<div style="font-size:.73rem;color:#4a5568">'+(p.nome_gestore)+'</div>':'');
    var del=document.createElement('span');
    del.title='Elimina';
    del.style.cssText='color:#e53e3e;font-size:.72rem;padding:.15rem .4rem;border-radius:3px;cursor:pointer;opacity:.65;flex-shrink:0';
    del.textContent='✕';
    del.addEventListener('mouseover',function(){this.style.opacity='1';});
    del.addEventListener('mouseout',function(){this.style.opacity='.65';});
    del.addEventListener('mousedown',function(e){e.stopPropagation();profiliDelete(p.iban);});
    row.appendChild(info);
    row.appendChild(del);
    el.appendChild(row);
  });
}

function profiliShow(){ var d=document.getElementById('profili-drop'); if(d) d.style.display='block'; }
function profiliHide(){ var d=document.getElementById('profili-drop'); if(d) d.style.display='none'; }
function profiliToggle(){ var d=document.getElementById('profili-drop'); if(d) d.style.display=(d.style.display==='none'?'block':'none'); }
function profiliFilter(){
  var q=(document.getElementById('profilo-inp').value||'').toLowerCase();
  var filtered=q?_profiliSaved.filter(function(p){
    return (p.banca||'').toLowerCase().indexOf(q)>=0
        || (p.nome_gestore||'').toLowerCase().indexOf(q)>=0
        || (p.iban||'').toLowerCase().indexOf(q)>=0;
  }):_profiliSaved;
  profiliRender(filtered);
  profiliShow();
}

function profiliSelect(p){
  var setBk=document.getElementById('bank_nome');
  var setGe=document.getElementById('nome_gestore');
  var setEm=document.getElementById('bank_email');
  var setIb=document.getElementById('bank_iban');
  if(setBk) setBk.value=p.banca||'';
  if(setGe) setGe.value=p.nome_gestore||'';
  if(setEm) setEm.value=p.email_gestore||'';
  if(setIb) setIb.value=p.iban||'';
  var inp=document.getElementById('profilo-inp');
  if(inp) inp.value=(p.banca||'')+(p.nome_gestore?' — '+p.nome_gestore:'');
  profiliHide();
}

function profiliDelete(iban){
  fetch('/api/banche/delete',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({iban:iban})}).then(function(r){return r.json();}).then(function(d){
    if(d.ok){
      _profiliSaved=_profiliSaved.filter(function(p){return p.iban!==iban;});
      profiliRender(_profiliSaved);
    }
  }).catch(function(){});
}

function profiliSalva(){
  var banca=(document.getElementById('bank_nome')||{}).value||'';
  var gestore=(document.getElementById('nome_gestore')||{}).value||'';
  var email=(document.getElementById('bank_email')||{}).value||'';
  var iban=(document.getElementById('bank_iban')||{}).value||'';
  var msg=document.getElementById('profili-msg');
  if(!iban){if(msg){msg.style.color='#FC8181';msg.textContent='Inserisci prima l\'IBAN nel form sottostante';}return;}
  fetch('/api/banche/save',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({banca:banca,iban:iban,nome_gestore:gestore,email_gestore:email})})
  .then(function(r){return r.json();}).then(function(d){
    if(d.ok){
      if(msg){msg.style.color='#68D391';msg.textContent='Profilo salvato!';setTimeout(function(){msg.textContent='';},2500);}
      profiliLoad();
    }else{if(msg){msg.style.color='#FC8181';msg.textContent=d.msg||'Errore';}}
  }).catch(function(){if(msg){msg.style.color='#FC8181';msg.textContent='Errore di rete';}});
}

profiliLoad();

// ─── Conti bancari salvati ─────────────────────────────────
var _contiSaved = [];

function contiLoad(){
  fetch('/api/ordine/conti').then(function(r){return r.json();}).then(function(d){
    _contiSaved = d.conti || [];
    contiRender(_contiSaved);
  }).catch(function(){});
}

function contiRender(list){
  var el = document.getElementById('conti-list-inner');
  if(!el) return;
  if(!list.length){
    el.innerHTML='<div style="padding:.55rem 1rem;color:#4a5568;font-size:.82rem">Nessun conto salvato</div>';
    return;
  }
  el.innerHTML='';
  list.forEach(function(c){
    var row=document.createElement('div');
    row.style.cssText='display:flex;align-items:center;padding:.42rem .85rem;cursor:pointer;gap:.5rem;border-bottom:1px solid rgba(255,255,255,.04);transition:background .12s';
    row.addEventListener('mouseover',function(){this.style.background='#1a2e40';});
    row.addEventListener('mouseout',function(){this.style.background='';});
    row.addEventListener('mousedown',function(){contiSelect(c);});
    var s1=document.createElement('span');
    s1.style.cssText='flex:1;font-size:.87rem;font-family:monospace;color:#e2e8f0';
    s1.textContent=c;
    var s2=document.createElement('span');
    s2.title='Elimina';
    s2.style.cssText='color:#e53e3e;font-size:.72rem;padding:.15rem .4rem;border-radius:3px;cursor:pointer;opacity:.65';
    s2.textContent='✕';
    s2.addEventListener('mouseover',function(){this.style.opacity='1';});
    s2.addEventListener('mouseout',function(){this.style.opacity='.65';});
    s2.addEventListener('mousedown',function(e){e.stopPropagation();contiDelete(c);});
    row.appendChild(s1);
    row.appendChild(s2);
    el.appendChild(row);
  });
}

function contiShow(){
  var d=document.getElementById('conti-drop'); if(d) d.style.display='block';
}
function contiHide(){
  var d=document.getElementById('conti-drop'); if(d) d.style.display='none';
}
function contiToggle(){
  var d=document.getElementById('conti-drop');
  if(d) d.style.display=(d.style.display==='none'?'block':'none');
}
function contiFilter(){
  var q=(document.getElementById('conto').value||'').toLowerCase().trim();
  var filtered=q?_contiSaved.filter(function(c){return c.toLowerCase().indexOf(q)>=0;}):_contiSaved;
  contiRender(filtered);
  contiShow();
}
function contiSelect(val){
  var inp=document.getElementById('conto'); if(inp) inp.value=val;
  contiHide();
}
function contiDelete(val){
  fetch('/api/ordine/conti/delete',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({conto:val})}).then(function(r){return r.json();}).then(function(d){
    if(d.ok){
      _contiSaved=_contiSaved.filter(function(c){return c!==val;});
      contiRender(_contiSaved);
    }
  }).catch(function(){});
}

contiLoad();
</script>
</body></html>'''

    _ibkr_block = (
        "<button class=\"btn-csv\" onclick=\"downloadCsv('ibkr')\">&#x2B07; IBKR &mdash; Basket Trader (.csv)</button>"
        if _piano_ord in ('PRO', 'VALUE') else
        "<span style=\"font-size:12px;color:#718096;padding:.5rem .8rem;background:rgba(255,255,255,.04);"
        "border-radius:6px;border:1px dashed rgba(255,255,255,.1)\">"
        "&#x1F512; IBKR Basket Trader &mdash; disponibile dal Piano Pro</span>"
    )
    _ibkr_desc = (
        "<strong style=\"color:#e2e8f0\">IBKR (Interactive Brokers):</strong>"
        " apri TWS &rarr; <code>File &rarr; Import Orders</code> &rarr; seleziona il file .csv"
        " &rarr; verifica le righe &rarr; <strong style=\"color:#68d391\">Trasmetti</strong><br>"
        if _piano_ord in ('PRO', 'VALUE') else ''
    )
    return (page
            .replace('__PAGE_TITLE__',      _page_title)
            .replace('__PAGE_SUB__',        _page_sub)
            .replace('__NOME_JS__',         nome_js)
            .replace('__EMAIL_JS__',        email_js)
            .replace('__EMAIL_SAFE__',      email_safe)
            .replace('__IBKR_BLOCK__',      _ibkr_block)
            .replace('__IBKR_DESC__',       _ibkr_desc)
            .replace('__ANAGRAFICA_JS__',   anagrafica_js)
            .replace('__PREFILL_ROWS_JS__', prefill_js)
            .replace('__TIPO_JS__',         tipo))


def _build_profilo_investitore(nome: str, email: str, cliente: dict = None) -> str:
    """Questionario MiFID II profilo investitore — area clienti."""
    import html as _html, json as _json
    profilo_js = _json.dumps((cliente or {}).get('profilo_investitore') or {}, ensure_ascii=False)
    nome_js    = nome.replace('\\','\\\\').replace('"','\\"')
    email_safe = _html.escape(email)

    page = '''<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Profilo Investitore — Fuerte Screener</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0a0f1e;color:#e0e0e0;font-family:'Segoe UI',Arial,sans-serif;min-height:100vh}
.hdr{background:linear-gradient(135deg,#1a365d,#2b6cb0);padding:14px 24px;display:flex;align-items:center;justify-content:space-between}
.hdr-back{color:#90cdf4;text-decoration:none;font-size:13px}
.main{max-width:640px;margin:2rem auto;padding:0 1.2rem 3rem}
.phase{display:none}.phase.active{display:block}
.progress-bar{background:rgba(255,255,255,.1);border-radius:99px;height:4px;margin-bottom:2rem}
.progress-fill{background:linear-gradient(90deg,#F6AD55,#ED8936);height:4px;border-radius:99px;transition:width .4s ease}
.card{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:14px;padding:1.8rem;margin-bottom:1rem}
.q-num{font-size:.75rem;color:#F6AD55;letter-spacing:1px;text-transform:uppercase;margin-bottom:.5rem}
.q-text{font-size:1.1rem;font-weight:600;line-height:1.5;margin-bottom:1.5rem}
.answers{display:flex;flex-direction:column;gap:.6rem}
.ans{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);border-radius:10px;
     padding:.85rem 1.1rem;cursor:pointer;transition:all .18s;font-size:.92rem;display:flex;align-items:center;gap:.8rem}
.ans:hover{background:rgba(246,173,85,.08);border-color:rgba(246,173,85,.4);color:#F6AD55}
.ans.selected{background:rgba(246,173,85,.12);border-color:#F6AD55;color:#F6AD55}
.ans-icon{width:28px;height:28px;border-radius:50%;background:rgba(255,255,255,.06);
          display:flex;align-items:center;justify-content:center;font-size:.75rem;
          color:#718096;flex-shrink:0;font-weight:700;min-width:28px}
.btn-next{background:linear-gradient(135deg,#F6AD55,#ED8936);color:#0a0f1e;border:none;
          border-radius:10px;padding:.85rem 2rem;font-size:.95rem;font-weight:700;
          cursor:pointer;width:100%;margin-top:1rem;display:none}
.btn-next.visible{display:block}
.profilo-badge{display:inline-flex;align-items:center;gap:.6rem;padding:.5rem 1.2rem;
               border-radius:99px;font-weight:700;font-size:1rem;margin-bottom:1.2rem}
.alloc-row{display:flex;align-items:center;gap:.8rem;margin-bottom:.55rem}
.alloc-bar-wrap{flex:1;background:rgba(255,255,255,.06);border-radius:99px;height:8px;overflow:hidden}
.alloc-bar{height:8px;border-radius:99px;transition:width .6s ease}
.alloc-pct{font-weight:700;font-size:.88rem;width:36px;text-align:right;flex-shrink:0}
.alloc-lbl{font-size:.85rem;width:105px;flex-shrink:0;color:#ccc}
.fuerte-box{background:rgba(246,173,85,.06);border:1px solid rgba(246,173,85,.2);border-radius:12px;padding:1.4rem;margin-top:1rem}
.btn-cta{display:inline-block;background:linear-gradient(135deg,#F6AD55,#ED8936);color:#0a0f1e;
         border:none;border-radius:10px;padding:.75rem 1.6rem;font-size:.9rem;font-weight:700;
         cursor:pointer;text-decoration:none;margin-top:.8rem;margin-right:.5rem}
.btn-redo{display:inline-block;background:transparent;color:#90cdf4;border:1px solid rgba(144,205,244,.3);
          border-radius:10px;padding:.75rem 1.4rem;font-size:.9rem;cursor:pointer;text-decoration:none;margin-top:.8rem}
</style>
</head>
<body>
<div class="hdr">
  <div style="display:flex;align-items:center;gap:1rem">
    <img src="data:image/png;base64,__FUERTE_LOGO__" alt="Fuerte" style="height:32px">
    <span style="font-size:.82rem;color:rgba(255,255,255,.5)">Profilo Investitore</span>
  </div>
  <a href="/area-clienti" class="hdr-back">&#8592; Area Riservata</a>
</div>
<div class="main">

<!-- FASE 0: INTRO -->
<div class="phase active" id="ph-intro">
  <div style="text-align:center;padding:2rem 0">
    <div style="font-size:3rem;margin-bottom:1rem">&#x1F9E0;</div>
    <h1 style="font-size:1.6rem;font-weight:700;margin-bottom:.8rem">Scopri il tuo Profilo Investitore</h1>
    <p style="color:#888;font-size:.95rem;line-height:1.7;margin-bottom:2rem;max-width:480px;margin-left:auto;margin-right:auto">
      7 domande &mdash; meno di 3 minuti.<br>
      Analizziamo obiettivi, tolleranza al rischio e orizzonte temporale
      per costruire il <strong style="color:#F6AD55">portafoglio su misura</strong> per te.
    </p>
    <div id="profilo-esistente" style="margin-bottom:1.2rem"></div>
    <button onclick="avviaQuiz()" style="background:linear-gradient(135deg,#F6AD55,#ED8936);color:#0a0f1e;
      border:none;border-radius:12px;padding:1rem 2.5rem;font-size:1rem;font-weight:700;cursor:pointer">
      Inizia il test &#8594;
    </button>
    <div style="margin-top:1.5rem;font-size:.75rem;color:#444">
      &#x26A0; A scopo informativo &mdash; non costituisce consulenza finanziaria (MiFID II)
    </div>
  </div>
</div>

<!-- FASE 1: QUIZ -->
<div class="phase" id="ph-quiz">
  <div class="progress-bar"><div class="progress-fill" id="progress-fill" style="width:0%"></div></div>
  <div id="quiz-container"></div>
  <button class="btn-next" id="btn-next" onclick="nextQuestion()">Continua &#8594;</button>
</div>

<!-- FASE 2: RISULTATI -->
<div class="phase" id="ph-results">
  <div id="results-container"></div>
</div>

</div>
<script>
var PROFILO_SALVATO = __PROFILO_JS__;
var PROFILI = {
  difensivo: {
    label:'Difensivo', emoji:'🛡️', color:'#4299E1',
    range:[7,11],
    desc:'La tua priorità è la <strong>protezione del capitale</strong>. Preferisci dormire tranquillo sapendo che il tuo patrimonio è al sicuro, anche se questo significa rendimenti più contenuti. Il portafoglio punta su strumenti a bassa volatilità — liquidità e obbligazioni governative di qualità — con una piccola componente diversificata.',
    desc2:'Le azioni sono presenti in quota minima: quando presenti, privilegia titoli ad alto dividendo e bassa volatilità.',
    alloc:{Liquidità:20,Obbligazioni:55,Oro:5,Fondi:10,ETF:5,Azioni:5},
    piano:'BASIC', piano_label:'Piano BASIC — Azioni dividendo, ETF a basso costo'
  },
  prudente: {
    label:'Prudente', emoji:'⚖️', color:'#48BB78',
    range:[12,16],
    desc:'Cerchi un equilibrio tra <strong>stabilità e rendimento</strong>. Accetti una modesta volatilità in cambio di risultati superiori al semplice deposito. Il portafoglio combina obbligazioni di qualità con una crescente esposizione a fondi ed ETF, costruendo rendimento costante nel medio termine.',
    desc2:'La componente azionaria è contenuta — ideale per titoli blue chip con buona visibilità di utili e dividendo sostenibile.',
    alloc:{Liquidità:10,Obbligazioni:45,Oro:5,Fondi:15,ETF:15,Azioni:10},
    piano:'BASIC', piano_label:'Piano BASIC — Azioni blue chip, ETF bilanciati'
  },
  bilanciato: {
    label:'Bilanciato', emoji:'📊', color:'#F6AD55',
    range:[17,20],
    desc:'Il tuo profilo è equilibrato: accetti <strong>volatilità moderata</strong> in cambio di rendimenti interessanti nel medio-lungo periodo. Il portafoglio combina strumenti difensivi con una significativa componente di crescita, bilanciando stabilità e opportunità senza eccessi.',
    desc2:'Azioni e ETF occupano metà del portafoglio — seleziona strumenti con buoni fondamentali e diversificazione geografica globale.',
    alloc:{Liquidità:5,Obbligazioni:30,Oro:5,Fondi:15,ETF:20,Azioni:25},
    piano:'PRO', piano_label:'Piano PRO — Analisi fondamentale globale, ETF diversificati'
  },
  dinamico: {
    label:'Dinamico', emoji:'🚀', color:'#ED8936',
    range:[21,24],
    desc:'La <strong>crescita del capitale</strong> è il tuo obiettivo principale. Sei disposto ad attraversare periodi di volatilità significativa con la consapevolezza che il lungo termine premia chi non si lascia spaventare dalle oscillazioni. Il portafoglio è orientato principalmente verso azioni ed ETF ad alto potenziale.',
    desc2:'La componente obbligazionaria funge da ammortizzatore — azioni ed ETF selezionati per qualità fondamentale e momentum di mercato.',
    alloc:{Liquidità:5,Obbligazioni:15,Oro:5,Fondi:10,ETF:25,Azioni:40},
    piano:'PRO', piano_label:'Piano PRO — Growth stocks, ETF settoriali e tematici'
  },
  aggressivo: {
    label:'Aggressivo', emoji:'⚡', color:'#FC8181',
    range:[25,28],
    desc:'Punti alla <strong>massima crescita del capitale</strong> nel lungo periodo. Hai piena consapevolezza dei rischi e la solidità emotiva per gestire drawdown anche importanti senza cedere alla paura. Il portafoglio è quasi interamente investito in azioni ed ETF ad alto potenziale di crescita.',
    desc2:"L'orizzonte temporale lungo è il tuo vantaggio competitivo — usa il value investing profondo per selezionare i migliori titoli globali con margine di sicurezza.",
    alloc:{Liquidità:0,Obbligazioni:5,Oro:5,Fondi:10,ETF:25,Azioni:55},
    piano:'VALUE', piano_label:'Piano VALUE — Deep value globale, ETF growth'
  }
};
var ALLOC_COLORS = {
  Liquidità:'#718096',Obbligazioni:'#4299E1',Oro:'#F6AD55',
  Fondi:'#68D391',ETF:'#9F7AEA',Azioni:'#FC8181'
};
var DOMANDE = [
  {testo:'Quanti anni hai?', risposte:[
    {t:'Più di 65 anni',p:1},{t:'Tra 50 e 65 anni',p:2},
    {t:'Tra 35 e 50 anni',p:3},{t:'Meno di 35 anni',p:4}]},
  {testo:'Per quanto tempo puoi tenere investito il tuo denaro senza toccarlo?', risposte:[
    {t:'Meno di 1 anno — ho bisogno di liquidità a breve',p:1},{t:'Da 1 a 3 anni',p:2},
    {t:'Da 3 a 10 anni',p:3},{t:'Più di 10 anni — orizzonte lungo',p:4}]},
  {testo:'Qual è il tuo obiettivo principale?', risposte:[
    {t:"Proteggere il capitale dall'inflazione",p:1},
    {t:'Generare un reddito regolare (cedole, dividendi)',p:2},
    {t:'Far crescere il capitale nel medio-lungo periodo',p:3},
    {t:'Massimizzare la crescita — accetto alta volatilità',p:4}]},
  {testo:'Se il tuo portafoglio perdesse il 20% del valore in pochi mesi, cosa faresti?', risposte:[
    {t:'Venderei tutto per evitare ulteriori perdite',p:1},
    {t:'Aspetterei preoccupato senza fare nulla',p:2},
    {t:'Manterrei la posizione con fiducia nel lungo termine',p:3},
    {t:"Comprerei di più — è un'opportunità",p:4}]},
  {testo:'Qual è la tua esperienza con gli investimenti finanziari?', risposte:[
    {t:'Nessuna — ho solo un conto corrente',p:1},
    {t:'Limitata — qualche fondo pensione o polizza',p:2},
    {t:'Media — investo regolarmente in azioni o ETF',p:3},
    {t:'Avanzata — gestisco un portafoglio diversificato',p:4}]},
  {testo:'Che quota del tuo patrimonio complessivo intendi investire?', risposte:[
    {t:'Meno del 10%',p:1},{t:'Tra il 10% e il 30%',p:2},
    {t:'Tra il 30% e il 50%',p:3},{t:'Più del 50%',p:4}]},
  {testo:'Hai bisogno di accedere ai tuoi risparmi investiti entro i prossimi 12 mesi?', risposte:[
    {t:'Sì, ho bisogno urgente di liquidità',p:1},{t:'Forse, non sono sicuro',p:2},
    {t:'Probabilmente no',p:3},{t:'No, sono finanziariamente sereno',p:4}]}
];

var currentQ=0, risposte=[], selectedP=-1;

function avviaQuiz(){showPhase('ph-quiz');renderQ(0);}
function showPhase(id){document.querySelectorAll('.phase').forEach(function(p){p.classList.remove('active');});document.getElementById(id).classList.add('active');}

function renderQ(idx){
  currentQ=idx; selectedP=-1;
  var d=DOMANDE[idx];
  document.getElementById('progress-fill').style.width=Math.round((idx/DOMANDE.length)*100)+'%';
  var letters=['A','B','C','D'];
  var html='<div class="card"><div class="q-num">Domanda '+(idx+1)+' di '+DOMANDE.length+'</div>'
    +'<div class="q-text">'+d.testo+'</div><div class="answers">';
  d.risposte.forEach(function(r,i){
    html+='<div class="ans" id="ans-'+i+'" onclick="selectAns('+i+','+r.p+')">'
      +'<div class="ans-icon">'+letters[i]+'</div><span>'+r.t+'</span></div>';
  });
  html+='</div></div>';
  document.getElementById('quiz-container').innerHTML=html;
  var btn=document.getElementById('btn-next');
  btn.classList.remove('visible');
  btn.textContent=(idx<DOMANDE.length-1)?'Continua →':'Vedi il mio profilo →';
}

function selectAns(idx,punti){
  document.querySelectorAll('.ans').forEach(function(el){el.classList.remove('selected');});
  document.getElementById('ans-'+idx).classList.add('selected');
  selectedP=punti;
  document.getElementById('btn-next').classList.add('visible');
}

function nextQuestion(){
  if(selectedP<0) return;
  risposte.push(selectedP);
  if(currentQ<DOMANDE.length-1){renderQ(currentQ+1);}
  else{document.getElementById('progress-fill').style.width='100%';calcolaRisultato();}
}

function calcolaRisultato(){
  var score=risposte.reduce(function(s,v){return s+v;},0);
  var tipo='bilanciato';
  Object.keys(PROFILI).forEach(function(k){var r=PROFILI[k].range;if(score>=r[0]&&score<=r[1])tipo=k;});
  mostraRisultato(tipo,score);
  fetch('/api/salva-profilo-investitore',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({tipo:tipo,label:PROFILI[tipo].label,score:score,allocazione:PROFILI[tipo].alloc})
  }).catch(function(){});
}

function buildDonut(alloc){
  var items=Object.keys(alloc).filter(function(k){return alloc[k]>0;}).map(function(k){return {label:k,value:alloc[k],color:ALLOC_COLORS[k]};});
  var total=items.reduce(function(s,d){return s+d.value;},0);
  var cx=120,cy=120,r=95,ir=55,start=-Math.PI/2,paths='',gap=0.02;
  items.forEach(function(d){
    var ang=(d.value/total)*2*Math.PI-gap;
    var end=start+ang;
    var x1=cx+r*Math.cos(start),y1=cy+r*Math.sin(start);
    var x2=cx+r*Math.cos(end),  y2=cy+r*Math.sin(end);
    var ix1=cx+ir*Math.cos(end),iy1=cy+ir*Math.sin(end);
    var ix2=cx+ir*Math.cos(start),iy2=cy+ir*Math.sin(start);
    var la=ang>Math.PI?1:0;
    paths+='<path d="M '+x1+' '+y1+' A '+r+' '+r+' 0 '+la+' 1 '+x2+' '+y2
          +' L '+ix1+' '+iy1+' A '+ir+' '+ir+' 0 '+la+' 0 '+ix2+' '+iy2+' Z"'
          +' fill="'+d.color+'" stroke="#0a0f1e" stroke-width="3"/>';
    start+=ang+gap;
  });
  return '<svg width="240" height="240" viewBox="0 0 240 240" style="display:block;margin:1rem auto">'+paths+'</svg>';
}

function mostraRisultato(tipo,score){
  var p=PROFILI[tipo];
  var html='<div style="text-align:center;padding:1.5rem 0 1rem">'
    +'<div style="font-size:2.8rem;margin-bottom:.6rem">'+p.emoji+'</div>'
    +'<div class="profilo-badge" style="background:'+p.color+'22;color:'+p.color+';border:1px solid '+p.color+'44;margin:0 auto">'
    +p.label.toUpperCase()+'</div>'
    +'<div style="font-size:.8rem;color:#555;margin-top:.4rem">Score: '+score+' / 28</div>'
    +'</div>';

  // Descrizione
  html+='<div class="card">'
    +'<h3 style="color:'+p.color+';margin-bottom:.8rem;font-size:.88rem;text-transform:uppercase;letter-spacing:.5px">Il tuo profilo</h3>'
    +'<p style="color:#ccc;font-size:.92rem;line-height:1.8;margin-bottom:.8rem">'+p.desc+'</p>'
    +'<p style="color:#aaa;font-size:.87rem;line-height:1.7">'+p.desc2+'</p>'
    +'</div>';

  // Grafico + legenda + barre
  html+='<div class="card">'
    +'<h3 style="color:#e0e0e0;margin-bottom:.8rem;font-size:.88rem;text-transform:uppercase;letter-spacing:.5px">Allocazione consigliata</h3>'
    +buildDonut(p.alloc)
    +'<div style="display:flex;flex-wrap:wrap;gap:.45rem .9rem;margin:1rem 0">';
  Object.keys(p.alloc).forEach(function(k){
    if(p.alloc[k]===0) return;
    html+='<div style="display:flex;align-items:center;gap:.35rem;font-size:.78rem">'
      +'<span style="width:9px;height:9px;border-radius:50%;background:'+ALLOC_COLORS[k]+';display:inline-block"></span>'
      +'<span style="color:#aaa">'+k+'</span>'
      +'<strong style="color:'+ALLOC_COLORS[k]+'">'+p.alloc[k]+'%</strong></div>';
  });
  html+='</div>';
  Object.keys(p.alloc).forEach(function(k){
    if(p.alloc[k]===0) return;
    html+='<div class="alloc-row">'
      +'<div class="alloc-lbl">'+k+'</div>'
      +'<div class="alloc-bar-wrap"><div class="alloc-bar" style="width:'+p.alloc[k]+'%;background:'+ALLOC_COLORS[k]+'"></div></div>'
      +'<div class="alloc-pct" style="color:'+ALLOC_COLORS[k]+'">'+p.alloc[k]+'%</div>'
      +'</div>';
  });
  html+='</div>';

  // CTA Fuerte
  html+='<div class="fuerte-box">'
    +'<div style="font-size:.78rem;color:#F6AD55;font-weight:700;text-transform:uppercase;letter-spacing:.8px;margin-bottom:.6rem">&#x1F4BC; Prodotti Fuerte Venture Capital consigliati</div>'
    +'<div style="font-size:.92rem;color:#e0e0e0;font-weight:600;margin-bottom:.4rem">'+p.piano_label+'</div>'
    +'<div style="font-size:.83rem;color:#888;line-height:1.6;margin-bottom:.3rem">Ricevi ogni settimana i migliori titoli selezionati dal nostro screener quantitativo, già filtrati per il tuo profilo di rischio.</div>'
    +'<a href="/area-clienti" class="btn-cta">Gestisci il mio piano</a>'
    +'<button onclick="rifaiTest()" class="btn-redo">&#x21BA; Rifai il test</button>'
    +'</div>'
    +'<div style="font-size:.69rem;color:#333;text-align:center;margin-top:1.2rem;line-height:1.6">'
    +'&#x26A0; Documento informativo — non costituisce consulenza finanziaria, raccomandazione di investimento o sollecitazione all&#39;acquisto ai sensi della Direttiva MiFID II (2014/65/UE). Prima di investire consulta un consulente finanziario abilitato.'
    +'</div>';

  showPhase('ph-results');
  document.getElementById('results-container').innerHTML=html;
}

function rifaiTest(){risposte=[];currentQ=0;selectedP=-1;showPhase('ph-quiz');renderQ(0);}

// Mostra profilo esistente nella intro
(function(){
  var el=document.getElementById('profilo-esistente');
  if(!el||!PROFILO_SALVATO||!PROFILO_SALVATO.tipo) return;
  var p=PROFILI[PROFILO_SALVATO.tipo]||{};
  el.innerHTML='<div style="background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);'
    +'border-radius:10px;padding:.75rem 1.2rem;font-size:.85rem;color:#aaa;display:inline-block">'
    +'Profilo attuale: <strong style="color:'+(p.color||\'#F6AD55\')+'">'+(p.emoji||'')+' '+(p.label||PROFILO_SALVATO.tipo)+'</strong>'
    +(PROFILO_SALVATO.data?' &middot; '+PROFILO_SALVATO.data:'')
    +'</div>';
})();
</script>
</body></html>'''

    return (page
            .replace('__FUERTE_LOGO__', FUERTE_LOGO_B64)
            .replace('__PROFILO_JS__',  profilo_js))


def _build_grazie_page() -> str:
    logo_tag = f'<img src="data:image/png;base64,{FUERTE_LOGO_B64}" alt="Fuerte Venture Capital" style="height:60px;width:auto;border-radius:12px;margin-bottom:1.5rem">'
    return f"""<!DOCTYPE html><html lang="it"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Registrazione completata — Robot Trader 2026</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{min-height:100vh;display:flex;align-items:center;justify-content:center;
       background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);font-family:'Segoe UI',sans-serif;color:#e2e8f0}}
  .card{{text-align:center;padding:3rem 2.5rem;background:rgba(255,255,255,.05);
         border:1px solid rgba(104,211,145,.2);border-radius:20px;max-width:480px;width:90%;
         box-shadow:0 20px 60px rgba(0,0,0,.4)}}
  .check{{font-size:3.5rem;margin-bottom:1rem}}
  h1{{font-size:1.6rem;font-weight:700;color:#68D391;margin-bottom:.8rem}}
  p{{color:#94a3b8;font-size:.95rem;line-height:1.6;margin-bottom:.5rem}}
  .email-highlight{{color:#F6AD55;font-weight:600}}
  .back{{display:inline-block;margin-top:2rem;padding:.7rem 1.8rem;
         background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;
         border-radius:8px;text-decoration:none;font-weight:600;font-size:.9rem;
         transition:opacity .2s}}
  .back:hover{{opacity:.85}}
  .footer-note{{margin-top:1.5rem;font-size:.78rem;color:#475569}}
</style>
</head><body>
<div class="card">
  {logo_tag}
  <div class="check">✅</div>
  <h1>Registrazione completata!</h1>
  <p>Grazie per esserti iscritto a <strong style="color:#F6AD55">Robot Trader 2026</strong>.</p>
  <p>Le tue <strong style="color:#e2e8f0">credenziali di accesso</strong> e la <strong style="color:#e2e8f0">fattura</strong> sono state inviate alla tua email.</p>
  <p style="margin-top:.8rem">Controlla la tua casella email, inclusa la cartella <strong>spam</strong>.</p>
  <a href="/" class="back">← Torna alla home</a>
  <div class="footer-note">Fuerte Venture Capital SL · CIF B23881691 · Calle Puipana 3, 35640 Villaverde, Las Palmas, España<br>
  <a href="mailto:info@fuerteventurecapital.com" style="color:#F6AD55;text-decoration:none">info@fuerteventurecapital.com</a> · <a href="https://www.fuerteventurecapital.com" style="color:#F6AD55;text-decoration:none">www.fuerteventurecapital.com</a><br>
  © 2026 Fuerte Venture Capital SL. All rights reserved.</div>
</div>
</body></html>"""


def _build_privacy_page() -> str:
    logo_tag = f'<img src="data:image/png;base64,{FUERTE_LOGO_B64}" alt="Fuerte Venture Capital" style="height:52px;width:auto;border-radius:10px;margin-bottom:1.2rem">'
    return f"""<!DOCTYPE html><html lang="it"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Informativa sulla Privacy — Robot Trader 2026</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{min-height:100vh;background:#0F172A;color:#e2e8f0;font-family:'Segoe UI',Arial,sans-serif;padding:2rem 1rem}}
  .container{{max-width:820px;margin:0 auto;background:#131929;border:1px solid rgba(99,179,237,.2);border-radius:16px;padding:2.5rem 3rem}}
  h1{{font-size:1.7rem;color:#F6AD55;margin-bottom:.4rem}}
  .sub{{color:#718096;font-size:.85rem;margin-bottom:2rem}}
  h2{{font-size:1.05rem;color:#63b3ed;margin:2rem 0 .6rem;border-bottom:1px solid rgba(99,179,237,.2);padding-bottom:.4rem}}
  p,li{{color:#a0aec0;font-size:.92rem;line-height:1.7;margin-bottom:.5rem}}
  ul{{padding-left:1.4rem;margin-bottom:.8rem}}
  .badge{{display:inline-block;background:rgba(246,173,85,.15);color:#F6AD55;border:1px solid rgba(246,173,85,.4);border-radius:6px;padding:.2rem .7rem;font-size:.78rem;font-weight:700;margin-left:.5rem}}
  a{{color:#63b3ed;text-decoration:none}}
  a:hover{{text-decoration:underline}}
  .footer{{margin-top:2.5rem;padding-top:1.2rem;border-top:1px solid rgba(255,255,255,.08);color:#4a5568;font-size:.8rem;text-align:center}}
  .back{{display:inline-block;margin-top:2rem;padding:.55rem 1.4rem;background:rgba(99,179,237,.15);color:#63b3ed;border:1px solid rgba(99,179,237,.3);border-radius:8px;font-size:.9rem;font-weight:600}}
</style>
</head><body>
<div class="container">
  <div style="text-align:center;margin-bottom:1rem">{logo_tag}</div>
  <h1>Informativa sulla Privacy <span class="badge">GDPR</span></h1>
  <p class="sub">Regolamento UE 2016/679 — Ultima revisione: 04 giugno 2026</p>

  <h2>1. Titolare del trattamento</h2>
  <p><strong>Fuerte Venture Capital SL</strong><br>
  CIF B23881691 · C/ Villaverde, Las Palmas de Gran Canaria, Isole Canarie, Spagna<br>
  Email: <a href="mailto:marketing@fuerteventurecapital.com">marketing@fuerteventurecapital.com</a></p>

  <h2>2. Dati raccolti</h2>
  <p>Raccogliamo esclusivamente i dati che l'utente fornisce volontariamente:</p>
  <ul>
    <li><strong>Nome e cognome</strong> — identificazione dell'utente</li>
    <li><strong>Indirizzo email</strong> — comunicazioni di servizio e invio report</li>
    <li><strong>Paese di residenza</strong> — adempimenti fiscali e normativi</li>
    <li><strong>Dati di pagamento</strong> — gestiti da Stripe Inc. (PCI-DSS compliant); non conserviamo dati di carta</li>
    <li><strong>Dati di navigazione</strong> — log tecnici anonimi per sicurezza e debug</li>
  </ul>

  <h2>3. Finalità e basi giuridiche</h2>
  <ul>
    <li><strong>Erogazione del servizio</strong> (art. 6.1.b GDPR) — accesso all'area riservata, invio report Excel, Order Builder</li>
    <li><strong>Adempimenti contrattuali e fiscali</strong> (art. 6.1.c GDPR) — fatturazione, IVA, normativa spagnola</li>
    <li><strong>Comunicazioni di marketing</strong> (art. 6.1.a GDPR) — solo previo consenso esplicito, revocabile in qualsiasi momento</li>
    <li><strong>Interesse legittimo</strong> (art. 6.1.f GDPR) — sicurezza del sistema, prevenzione frodi</li>
  </ul>

  <h2>4. Conservazione dei dati</h2>
  <p>I dati sono conservati per tutta la durata del rapporto contrattuale e per i successivi <strong>10 anni</strong> per obblighi fiscali (normativa spagnola e UE). I dati di marketing vengono eliminati entro 30 giorni dalla revoca del consenso.</p>

  <h2>5. Destinatari e trasferimenti</h2>
  <p>I dati non vengono venduti a terzi. Possono essere comunicati a:</p>
  <ul>
    <li><strong>Stripe Inc.</strong> (USA) — processore pagamenti, soggetto a Standard Contractual Clauses EU</li>
    <li><strong>Google LLC</strong> (USA) — SMTP per invio email, soggetto a SCC EU</li>
    <li><strong>Brevo SAS</strong> (Francia) — piattaforma email marketing, sede UE</li>
    <li>Autorità fiscali e giudiziarie spagnole ed europee, ove richiesto per legge</li>
  </ul>

  <h2>6. Diritti dell'interessato</h2>
  <p>Ai sensi degli artt. 15-22 GDPR, l'utente ha diritto di:</p>
  <ul>
    <li><strong>Accesso</strong> — ottenere copia dei propri dati trattati</li>
    <li><strong>Rettifica</strong> — correggere dati inesatti o incompleti</li>
    <li><strong>Cancellazione</strong> ("diritto all'oblio") — ottenere la rimozione dei dati</li>
    <li><strong>Limitazione</strong> — limitare il trattamento in determinati casi</li>
    <li><strong>Portabilità</strong> — ricevere i dati in formato strutturato (JSON/CSV)</li>
    <li><strong>Opposizione</strong> — opporsi al trattamento per marketing</li>
    <li><strong>Revoca del consenso</strong> — in qualsiasi momento, senza conseguenze per il servizio già erogato</li>
  </ul>
  <p>Per esercitare i propri diritti: <a href="mailto:marketing@fuerteventurecapital.com">marketing@fuerteventurecapital.com</a> — risposta entro <strong>30 giorni</strong>.</p>

  <h2>7. Reclami</h2>
  <p>In caso di violazione dei propri diritti, l'utente può proporre reclamo all'<strong>AEPD</strong> (Agencia Española de Protección de Datos): <a href="https://www.aepd.es" target="_blank">www.aepd.es</a>, o all'autorità di controllo del proprio paese di residenza.</p>

  <h2>8. Cookie</h2>
  <p>Il sito utilizza esclusivamente <strong>cookie tecnici di sessione</strong> (autenticazione). Non utilizziamo cookie di profilazione o di terze parti a fini pubblicitari. Non è richiesto il consenso ai cookie per l'utilizzo del servizio.</p>

  <h2>9. Sicurezza</h2>
  <p>I dati sono conservati su server con accesso ristretto, protetti da autenticazione. Le sessioni sono identificate da token crittografici generati con <code>secrets.token_hex()</code>. Le password sono trasmesse su connessioni cifrate (HTTPS in produzione).</p>

  <h2>10. Disclaimer — Servizio non consulenziale</h2>
  <p>Robot Trader 2026 è uno <strong>strumento di screening quantitativo</strong> a uso informativo. I report e i ranking prodotti <strong>non costituiscono consulenza finanziaria, raccomandazione di investimento o sollecitazione all'acquisto/vendita di strumenti finanziari</strong> ai sensi della Direttiva MiFID II (2014/65/UE). L'utente è l'unico responsabile delle proprie decisioni di investimento.</p>

  <a href="/" class="back">← Torna alla home</a>

  <div class="footer">
    Fuerte Venture Capital SL · CIF B23881691 · Las Palmas de Gran Canaria, Spagna<br>
    <a href="mailto:marketing@fuerteventurecapital.com">marketing@fuerteventurecapital.com</a>
  </div>
</div>
</body></html>"""


def _build_cambia_password_page(error='', voluntary=False):
    logo_src = f"data:image/png;base64,{FUERTE_LOGO_B64}"
    err_html = f'<p style="color:#FC8181;font-size:.85rem;text-align:center;margin-bottom:1rem">{html.escape(error)}</p>' if error else ''
    if voluntary:
        _title    = 'Modifica la tua password'
        _subtitle = 'Inserisci la password attuale e scegli la nuova password sicura.'
        _notice   = ''
        _old_field = '''<label>Password attuale</label>
    <div class="inp-wrap">
      <input type="password" name="old_pwd" id="op" placeholder="Password attuale" required autocomplete="current-password">
      <button type="button" class="eye-btn" onclick="togglePwd(\'op\',this)" tabindex="-1">&#x1F441;</button>
    </div>'''
        _hidden   = '<input type="hidden" name="voluntary" value="1">'
        _btn_text = 'SALVA NUOVA PASSWORD'
        _back     = '<a href="/area-clienti" style="display:block;text-align:center;margin-top:1rem;font-size:.82rem;color:#888;text-decoration:none">&#8592; Torna all\'Area Riservata</a>'
    else:
        _title    = 'Imposta la tua password'
        _subtitle = 'Stai accedendo per la prima volta.<br>Scegli una password personale sicura.'
        _notice   = '<div class="notice">&#9888; La password temporanea ricevuta via email deve essere sostituita ora.</div>'
        _old_field = ''
        _hidden   = ''
        _btn_text = 'SALVA E ACCEDI →'
        _back     = ''
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{'Modifica' if voluntary else 'Imposta'} password — Robot Trader 2026</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0f1e;font-family:'Segoe UI',Arial,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center}}
.card{{background:#111827;border:1px solid rgba(246,173,85,.3);border-radius:16px;padding:2.5rem 2rem;width:100%;max-width:420px}}
.logo{{text-align:center;margin-bottom:1.5rem}}
.logo img{{height:44px;width:auto;border-radius:9px}}
h1{{font-size:1.1rem;font-weight:700;color:#F6AD55;text-align:center;margin-bottom:.4rem}}
.sub{{text-align:center;color:#888;font-size:.85rem;margin-bottom:1rem;line-height:1.5}}
.notice{{background:rgba(246,173,85,.06);border:1px solid rgba(246,173,85,.2);border-radius:8px;padding:.8rem 1rem;font-size:.78rem;color:#F6AD55;text-align:center;margin-bottom:1.2rem}}
label{{display:block;font-size:.82rem;color:#888;margin-bottom:.4rem;margin-top:1rem}}
.inp-wrap{{position:relative}}
input{{width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:8px;padding:.75rem 2.8rem .75rem 1rem;color:#e0e0e0;font-size:.95rem;outline:none;transition:border .2s;box-sizing:border-box}}
input:focus{{border-color:#F6AD55}}
.eye-btn{{position:absolute;right:.7rem;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;color:#666;font-size:1.1rem;padding:0;line-height:1}}
.rules{{margin:.5rem 0 .4rem;font-size:.76rem;line-height:1.9}}
.strength-bar{{height:4px;border-radius:2px;background:#1a1a2e;margin-bottom:1rem;overflow:hidden}}
.strength-fill{{height:100%;width:0;transition:width .3s,background .3s}}
.btn{{width:100%;background:#F6AD55;color:#0a0f1e;border:none;border-radius:8px;padding:.85rem;font-size:1rem;font-weight:700;cursor:pointer;margin-top:1.5rem;transition:opacity .2s}}
.btn:hover{{opacity:.85}}
.err{{color:#FC8181;font-size:.85rem;margin-top:.8rem;text-align:center}}
</style>
</head>
<body>
<div class="card">
  <div class="logo"><img src="{logo_src}" alt="Fuerte Venture Capital"></div>
  <h1>{_title}</h1>
  <p class="sub">{_subtitle}</p>
  {_notice}
  {err_html}
  <form method="POST" action="/api/cambia-password" onsubmit="return checkPwdForm()">
    {_hidden}
    {_old_field}
    <label>Nuova password</label>
    <div class="inp-wrap">
      <input type="password" name="new_pwd" id="np" placeholder="Minimo 8 car. + maiusc. + num. + simbolo" required autocomplete="new-password" oninput="pwdCheck()">
      <button type="button" class="eye-btn" onclick="togglePwd('np',this)" tabindex="-1">👁</button>
    </div>
    <div class="rules" id="pwd-rules">
      <span id="r-len" style="color:#555">○ Almeno 8 caratteri</span><br>
      <span id="r-up"  style="color:#555">○ Una lettera maiuscola (A-Z)</span><br>
      <span id="r-lo"  style="color:#555">○ Una lettera minuscola (a-z)</span><br>
      <span id="r-num" style="color:#555">○ Un numero (0-9)</span><br>
      <span id="r-sym" style="color:#555">○ Un simbolo (@$!%*?&_#^)</span>
    </div>
    <div class="strength-bar"><div class="strength-fill" id="pwd-bar"></div></div>
    <label>Conferma password</label>
    <div class="inp-wrap">
      <input type="password" name="conf_pwd" id="cp" placeholder="Ripeti la password" required autocomplete="new-password">
      <button type="button" class="eye-btn" onclick="togglePwd('cp',this)" tabindex="-1">👁</button>
    </div>
    <button class="btn" type="submit">{_btn_text}</button>
  </form>
  {_back}
</div>
<script>
function togglePwd(id,btn){{
  var inp=document.getElementById(id);
  inp.type=inp.type==='password'?'text':'password';
  btn.textContent=inp.type==='password'?'👁':'🙈';
}}
function pwdCheck(){{
  var v=document.getElementById('np').value;
  var checks=[
    [/.{{8,}}/,      'r-len','Almeno 8 caratteri'],
    [/[A-Z]/,        'r-up', 'Una lettera maiuscola (A-Z)'],
    [/[a-z]/,        'r-lo', 'Una lettera minuscola (a-z)'],
    [/[0-9]/,        'r-num','Un numero (0-9)'],
    [/[@$!%*?&_#^]/, 'r-sym','Un simbolo (@$!%*?&_#^)'],
  ];
  var ok=0;
  checks.forEach(function(c){{
    var pass=c[0].test(v);
    var el=document.getElementById(c[1]);
    el.style.color=pass?'#68D391':'#555';
    el.textContent=(pass?'✓ ':'○ ')+c[2];
    if(pass) ok++;
  }});
  var colors=['#ef4444','#f97316','#eab308','#84cc16','#22c55e'];
  var bar=document.getElementById('pwd-bar');
  bar.style.width=(ok*20)+'%';
  bar.style.background=ok>0?colors[ok-1]:'transparent';
}}
function checkPwdForm(){{
  var v=document.getElementById('np').value;
  var c=document.getElementById('cp').value;
  if(!/.{{8,}}/.test(v)||!/[A-Z]/.test(v)||!/[a-z]/.test(v)||!/[0-9]/.test(v)||!/[@$!%*?&_#^]/.test(v)){{
    alert('La password non soddisfa tutti i requisiti di sicurezza.');
    return false;
  }}
  if(v!==c){{ alert('Le password non coincidono.'); return false; }}
  return true;
}}
</script>
</body></html>"""


# ── Pagina Idee di Investimento per subscriber ────────────────────
def _build_idee_clienti(nome):
    _logo = FUERTE_LOGO_B64
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Robot Trader 2026 — Idee di Investimento</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0f1e;font-family:'Segoe UI',Arial,sans-serif;min-height:100vh;color:#e0e0e0}}
.top{{background:linear-gradient(135deg,#1a2744,#0d1b35);padding:1.2rem 2rem;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid rgba(246,173,85,.2)}}
.main{{max-width:860px;margin:2rem auto;padding:0 1.2rem 3rem}}
.back{{background:transparent;border:1px solid rgba(255,255,255,.15);color:#aaa;padding:.4rem .9rem;border-radius:6px;font-size:.82rem;text-decoration:none}}
.back:hover{{border-color:#F6AD55;color:#F6AD55}}
.sec-title{{font-size:.75rem;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:#888;margin:2rem 0 .9rem}}
.card{{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);border-radius:12px;padding:1.1rem 1.3rem;margin-bottom:.75rem;display:flex;align-items:center;gap:1.2rem;flex-wrap:wrap}}
.card:hover{{border-color:rgba(246,173,85,.3)}}
.card-left{{min-width:130px}}
.card-emoji{{font-size:1.5rem;margin-bottom:.2rem}}
.card-nome{{font-size:.9rem;font-weight:700;color:#e0e0e0;line-height:1.2}}
.badge-p1m{{display:inline-block;font-size:.72rem;font-weight:700;padding:.18rem .55rem;border-radius:4px;margin-top:.35rem}}
.card-mid{{flex:1;min-width:180px}}
.card-label{{font-size:.68rem;font-weight:600;letter-spacing:.6px;text-transform:uppercase;color:#555;margin-bottom:.4rem}}
.ticker-pills{{display:flex;flex-wrap:wrap;gap:.35rem}}
.pill{{font-size:.75rem;font-weight:700;padding:.25rem .6rem;border-radius:5px;background:rgba(44,82,130,.35);color:#90cdf4;font-family:monospace}}
.pill-score{{font-size:.65rem;font-weight:600;color:#F6AD55;margin-left:.2rem}}
.no-ticker{{font-size:.78rem;color:#444;font-style:italic}}
.card-right{{display:flex;flex-direction:column;gap:.4rem;align-items:flex-end;min-width:90px}}
.etf-tag{{font-size:.72rem;font-weight:700;padding:.22rem .6rem;border-radius:4px;background:rgba(16,185,129,.15);color:#6ee7b7;font-family:monospace;white-space:nowrap;text-decoration:none}}
.etf-tag:hover{{background:rgba(16,185,129,.3)}}
.etf-label{{font-size:.62rem;color:#555;text-align:right;margin-top:-.15rem}}
.empty-msg{{text-align:center;padding:3rem;color:#444;font-size:.9rem}}
.how{{background:rgba(246,173,85,.04);border:1px solid rgba(246,173,85,.1);border-radius:10px;padding:1rem 1.3rem;font-size:.78rem;color:#666;line-height:1.75;margin-top:2rem}}
.how strong{{color:#aaa}}
</style>
</head>
<body>
<div class="top">
  <div style="display:flex;align-items:center;gap:1rem">
    <img src="data:image/png;base64,{_logo}" alt="Fuerte" style="height:36px;display:block">
    <div style="font-size:.85rem;color:rgba(255,255,255,.5)">Idee di Investimento</div>
  </div>
  <a href="/area-clienti" class="back">&#8592; Area Riservata</a>
</div>
<div class="main">
  <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.6rem;margin-bottom:.3rem">
    <div>
      <h2 style="color:#F6AD55;font-size:1.1rem;font-weight:700">&#x1F4A1; Idee di Investimento</h2>
      <div style="font-size:.78rem;color:#555;margin-top:.3rem">Settori e mercati con momentum positivo &mdash; i migliori titoli del tuo screener</div>
    </div>
    <button onclick="ricarica()" style="background:#2C5282;border:none;color:#F6AD55;padding:.35rem .85rem;border-radius:6px;cursor:pointer;font-size:.78rem;font-weight:600">&#x1F504; Aggiorna</button>
  </div>
  <div id="ts" style="font-size:.68rem;color:#3a3a3a;margin-bottom:.5rem">Caricamento...</div>
  <div id="content">
    <div style="text-align:center;padding:3rem;color:#444">&#9203; Caricamento dati mercato...</div>
  </div>
  <div class="how">
    <strong>Come usare queste idee</strong><br>
    I settori e i mercati mostrati hanno un <strong>trend mensile positivo</strong> confermato dai dati Yahoo Finance.
    I titoli in elenco sono quelli con il <strong>punteggio Score pi&ugrave; alto</strong> nel tuo screener per quel settore.
    Gli ETF sono lo strumento pi&ugrave; semplice per seguire il trend senza scegliere singoli titoli.<br>
    <span style="color:#666">&#x26A0;&#xFE0F; Non costituisce consulenza finanziaria &mdash; verifica sempre prima di investire.</span>
  </div>
</div>
<script>
function pct(v){{
  if(v===null||v===undefined)return'—';
  var s=(v>=0?'+':'')+v.toFixed(2)+'%';
  return'<span style="color:'+(v>=0?'#86efac':'#fca5a5')+'">'+s+'</span>';
}}
function badgeP1m(v){{
  if(v===null||v===undefined)return'';
  var bg=v>=5?'rgba(20,83,45,.9)':v>=2?'rgba(22,101,52,.75)':'rgba(21,128,61,.55)';
  return'<span class="badge-p1m" style="background:'+bg+';color:#86efac">+'+v.toFixed(2)+'% 1M</span>';
}}
function renderSettore(s){{
  var pills='';
  if(s.top&&s.top.length){{
    s.top.forEach(function(t){{
      var sc=t.score!==null?'<span class="pill-score">'+parseFloat(t.score).toFixed(0)+'</span>':'';
      pills+='<span class="pill">'+t.ticker+sc+'</span>';
    }});
  }}else{{
    pills='<span class="no-ticker">Esegui lo screener azioni per popolare</span>';
  }}
  var etfHtml='';
  var isEu=(s.regione==='eu');
  if(!isEu&&s.etf_us)etfHtml+='<a href="https://finance.yahoo.com/quote/'+encodeURIComponent(s.etf_us)+'" target="_blank" class="etf-tag">'+s.etf_us+'</a><div class="etf-label">ETF USA</div>';
  if(s.etf_eu)etfHtml+='<a href="https://finance.yahoo.com/quote/'+encodeURIComponent(s.etf_eu)+'" target="_blank" class="etf-tag" style="background:rgba(59,130,246,.15);color:#93c5fd">'+s.etf_eu+'</a><div class="etf-label">ETF Europa</div>';
  return'<div class="card">'+
    '<div class="card-left"><div class="card-emoji">'+s.emoji+'</div><div class="card-nome">'+s.nome+'</div>'+badgeP1m(s.p1m)+'</div>'+
    '<div class="card-mid"><div class="card-label">Top picks dallo screener</div><div class="ticker-pills">'+pills+'</div>'+
    '<div style="margin-top:.5rem;font-size:.7rem;color:#3a3a3a">1S: '+pct(s.p1w)+'&nbsp;&nbsp;3M: '+pct(s.p3m)+'</div></div>'+
    '<div class="card-right">'+etfHtml+'</div>'+
  '</div>';
}}
function renderNazione(n){{
  var etfHtml=n.etf?'<a href="https://finance.yahoo.com/quote/'+encodeURIComponent(n.etf)+'" target="_blank" class="etf-tag">'+n.etf+'</a><div class="etf-label">ETF principale</div>':'';
  return'<div class="card">'+
    '<div class="card-left"><div class="card-emoji" style="font-size:1.8rem">'+n.flag+'</div><div class="card-nome">'+n.nome+'</div>'+badgeP1m(n.p1m)+'</div>'+
    '<div class="card-mid"><div class="card-label">Indice di riferimento</div>'+
    '<div style="font-size:.85rem;color:#aaa;font-weight:600">'+n.indice+'</div>'+
    '<div style="margin-top:.5rem;font-size:.7rem;color:#3a3a3a">1S: '+pct(n.p1w)+'</div></div>'+
    '<div class="card-right">'+etfHtml+'</div>'+
  '</div>';
}}
function carica(){{
  fetch('/api/idee').then(function(r){{return r.json();}}).then(function(d){{
    if(d.error){{document.getElementById('content').innerHTML='<div class="empty-msg">&#x26A0;&#xFE0F; '+d.error+'</div>';return;}}
    document.getElementById('ts').textContent=d.ts?'Dati aggiornati: '+d.ts:'';
    var html='';
    if(d.settori&&d.settori.length){{
      html+='<div class="sec-title">&#x1F680; Settori in Momentum Positivo ('+d.settori.length+')</div>';
      d.settori.forEach(function(s){{html+=renderSettore(s);}});
    }}else{{
      html+='<div class="sec-title">Settori in Momentum Positivo</div><div class="empty-msg">Nessun settore in momentum positivo al momento</div>';
    }}
    if(d.nazioni&&d.nazioni.length){{
      html+='<div class="sec-title">&#x1F7E2; Mercati in Rialzo ('+d.nazioni.length+')</div>';
      d.nazioni.forEach(function(n){{html+=renderNazione(n);}});
    }}else{{
      html+='<div class="sec-title">Mercati in Rialzo</div><div class="empty-msg">Nessun mercato sopra +2% mensile al momento</div>';
    }}
    document.getElementById('content').innerHTML=html;
  }}).catch(function(e){{
    document.getElementById('content').innerHTML='<div class="empty-msg">Errore: '+e.message+'</div>';
  }});
}}
function ricarica(){{
  document.getElementById('content').innerHTML='<div style="text-align:center;padding:3rem;color:#444">&#9203; Caricamento...</div>';
  document.getElementById('ts').textContent='Caricamento...';
  fetch('/api/idee?force=1').then(function(r){{return r.json();}}).then(function(d){{
    document.getElementById('ts').textContent=d.ts?'Dati aggiornati: '+d.ts:'';
    var html='';
    if(d.settori&&d.settori.length){{
      html+='<div class="sec-title">&#x1F680; Settori in Momentum Positivo ('+d.settori.length+')</div>';
      d.settori.forEach(function(s){{html+=renderSettore(s);}});
    }}else{{
      html+='<div class="sec-title">Settori in Momentum Positivo</div><div class="empty-msg">Nessun settore in momentum positivo al momento</div>';
    }}
    if(d.nazioni&&d.nazioni.length){{
      html+='<div class="sec-title">&#x1F7E2; Mercati in Rialzo ('+d.nazioni.length+')</div>';
      d.nazioni.forEach(function(n){{html+=renderNazione(n);}});
    }}else{{
      html+='<div class="sec-title">Mercati in Rialzo</div><div class="empty-msg">Nessun mercato sopra +2% mensile al momento</div>';
    }}
    document.getElementById('content').innerHTML=html;
  }}).catch(function(e){{
    document.getElementById('content').innerHTML='<div class="empty-msg">Errore: '+e.message+'</div>';
  }});
}}
window.addEventListener('load', carica);
</script>
</body>
</html>"""


# ── Pagina Analisi Settoriale & Mercati per subscriber ────────────
def _build_settori_clienti(nome):
    _logo = FUERTE_LOGO_B64
    _js = r"""
var EU_TO_US = {
  'Technology':'Technology','Banks':'Financial Services','Health Care':'Health Care',
  'Industrials':'Industrials','Auto & Parts':'Consumer Discret.','Food & Beverage':'Consumer Staples',
  'Oil & Gas':'Energy','Utilities':'Utilities','Insurance':'Financial Services',
  'Media':'Comm. Services','Travel & Leisure':'Consumer Discret.',
};

var SETT_INFO = {
  'Technology': {
    desc: 'Software, hardware, semiconduttori, cloud e IT enterprise. Il settore più capitalizzato dell\'S&P 500 (~30% peso).',
    include: 'Apple (AAPL), Microsoft (MSFT), NVIDIA (NVDA), Broadcom (AVGO), Oracle (ORCL)',
    ciclo: 'Ciclico-growth. Beneficia da: tassi bassi, innovazione, spesa IT aziendale. Rischio: tassi alti, antitrust, valutazioni elevate.',
    etf_us: [['XLK','SPDR Technology (TER 0.10%)'],['VGT','Vanguard IT (TER 0.10%)'],['SOXX','iShares Semiconduttori (TER 0.35%)'],['QQQM','Invesco Nasdaq 100 (TER 0.15%)']],
    etf_eu: [['EXV3.DE','iShares STOXX EU Tech (TER 0.46%)'],['IUIT.L','iShares EU IT UCITS (TER 0.46%)'],['TECH.L','Global X Tech UCITS (TER 0.50%)']],
    fondi:  ['T. Rowe Price Science & Tech (PRSCX)','Fidelity Select Technology (FSPTX)'],
  },
  'Financial Services': {
    desc: 'Banche, assicurazioni, gestori patrimoniali, fintech, mercati dei capitali. Correlato al ciclo tassi.',
    include: 'JPMorgan (JPM), Visa (V), Mastercard (MA), Goldman Sachs (GS), Bank of America (BAC)',
    ciclo: 'Ciclico. Beneficia da: tassi alti (margine interesse), espansione economica. Rischio: recessione, credit crunch, regolamentazione.',
    etf_us: [['XLF','SPDR Financials (TER 0.10%)'],['VFH','Vanguard Financials (TER 0.10%)'],['KBE','SPDR S&P Bank ETF (TER 0.35%)']],
    etf_eu: [['EXH2.DE','iShares STOXX EU Banks (TER 0.46%)'],['EXH5.DE','iShares STOXX EU Insurance (TER 0.46%)']],
    fondi:  ['Fidelity Select Financial (FIDSX)','Davis Financial Fund (RPFGX)'],
  },
  'Health Care': {
    desc: 'Farmaceutiche, biotech, dispositivi medici, assicurazioni sanitarie. Settore difensivo con componente growth.',
    include: 'UnitedHealth (UNH), Eli Lilly (LLY), Johnson & Johnson (JNJ), AbbVie (ABBV), Merck (MRK)',
    ciclo: 'Difensivo-growth. Resiliente in recessione. Beneficia da: invecchiamento demografico, biotech. Rischio: riforme sanitarie, brevetti in scadenza.',
    etf_us: [['XLV','SPDR Health Care (TER 0.10%)'],['VHT','Vanguard Health Care (TER 0.10%)'],['IBB','iShares Biotech (TER 0.44%)'],['IHI','iShares Medical Devices (TER 0.40%)']],
    etf_eu: [['EXH3.DE','iShares STOXX EU Health Care (TER 0.46%)']],
    fondi:  ['Fidelity Select Medical (FSMEX)','T. Rowe Price Health Sciences (PRHSX)'],
  },
  'Industrials': {
    desc: 'Aerospazio, difesa, macchinari, trasporti, costruzioni, logistica. Barometro del ciclo economico.',
    include: 'GE (GE), Caterpillar (CAT), Honeywell (HON), RTX Corp (RTX), Union Pacific (UNP)',
    ciclo: 'Fortemente ciclico. Beneficia da: espansione economica, spesa infrastrutturale, difesa. Rischio: recessione, rallentamento manifatturiero.',
    etf_us: [['XLI','SPDR Industrials (TER 0.10%)'],['VIS','Vanguard Industrials (TER 0.10%)'],['ITA','iShares Aerospace & Defense (TER 0.40%)'],['PAVE','Global X Infrastructure (TER 0.47%)']],
    etf_eu: [['EXH4.DE','iShares STOXX EU Industrial G&S (TER 0.46%)']],
    fondi:  ['Fidelity Select Industrials (FCYIX)','T. Rowe Price Industrials (TRIIX)'],
  },
  'Consumer Discret.': {
    desc: 'Retail, auto, ristorazione, intrattenimento, beni di lusso. Dipende dal reddito disponibile dei consumatori.',
    include: 'Amazon (AMZN), Tesla (TSLA), Home Depot (HD), McDonald\'s (MCD), Nike (NKE)',
    ciclo: 'Ciclico. Beneficia da: crescita salariale, ottimismo consumi. Rischio: inflazione, recessione, tassi alti che comprimono spesa.',
    etf_us: [['XLY','SPDR Consumer Discret. (TER 0.10%)'],['VCR','Vanguard Consumer Discret. (TER 0.10%)'],['RTH','VanEck Retail ETF (TER 0.35%)']],
    etf_eu: [['EXH1.DE','iShares STOXX EU Auto & Parts (TER 0.46%)'],['EXV6.DE','iShares STOXX EU Travel & Leisure (TER 0.46%)']],
    fondi:  ['Fidelity Select Retailing (FSRPX)','Fidelity Select Consumer Discret. (FSCPX)'],
  },
  'Consumer Staples': {
    desc: 'Alimentari, bevande, prodotti per la casa, tabacco. Beni essenziali con domanda anelastica e alti dividendi.',
    include: 'Procter & Gamble (PG), Coca-Cola (KO), Walmart (WMT), Costco (COST), PepsiCo (PEP)',
    ciclo: 'Difensivo. Resiliente in recessione. Beneficia da: inflazione traslata sui prezzi, dividendi stabili. Sottoperforma nei boom ciclici.',
    etf_us: [['XLP','SPDR Consumer Staples (TER 0.10%)'],['VDC','Vanguard Consumer Staples (TER 0.10%)'],['KXI','iShares Global Consumer Staples (TER 0.42%)']],
    etf_eu: [['EXV8.DE','iShares STOXX EU Food & Beverage (TER 0.46%)']],
    fondi:  ['Fidelity Select Consumer Staples (FDFAX)','Vanguard Consumer Staples Fund (VCSAX)'],
  },
  'Energy': {
    desc: 'Petrolio, gas naturale, raffinerie, energie rinnovabili, servizi petroliferi. Correlato al prezzo delle commodity.',
    include: 'ExxonMobil (XOM), Chevron (CVX), ConocoPhillips (COP), EOG Resources (EOG), SLB (SLB)',
    ciclo: 'Ciclico commodity-driven. Beneficia da: prezzo petrolio alto, geopolitica, ripresa economia. Rischio: transizione energetica, oversupply, recessione.',
    etf_us: [['XLE','SPDR Energy (TER 0.10%)'],['VDE','Vanguard Energy (TER 0.10%)'],['XOP','SPDR Oil & Gas Exploration (TER 0.35%)'],['OIH','VanEck Oil Services (TER 0.35%)']],
    etf_eu: [['EXV1.DE','iShares STOXX EU Oil & Gas (TER 0.46%)']],
    fondi:  ['Fidelity Select Energy (FSENX)','Vanguard Energy Fund (VGELX)'],
  },
  'Utilities': {
    desc: 'Elettricità, gas, acqua, servizi ambientali. Monopoli regolamentati con cash flow stabili e alti dividendi.',
    include: 'NextEra Energy (NEE), Duke Energy (DUK), Southern Co (SO), Dominion (D), Exelon (EXC)',
    ciclo: 'Difensivo-bond proxy. Beneficia da: tassi bassi, AI (fabbisogno elettrico data center), rinnovabili. Rischio: tassi alti (concorrenza con bond).',
    etf_us: [['XLU','SPDR Utilities (TER 0.10%)'],['VPU','Vanguard Utilities (TER 0.10%)'],['FUTY','Fidelity MSCI Utilities (TER 0.08%)']],
    etf_eu: [['EXV7.DE','iShares STOXX EU Utilities (TER 0.46%)']],
    fondi:  ['Fidelity Select Utilities (FSUTX)','Vanguard Utilities Fund (VUIAX)'],
  },
  'Materials': {
    desc: 'Metalli, minerali, chimica industriale, carta, packaging, fertilizzanti. Legato al ciclo industriale.',
    include: 'Linde (LIN), Freeport-McMoRan (FCX), Air Products (APD), Sherwin-Williams (SHW), Nucor (NUE)',
    ciclo: 'Fortemente ciclico. Beneficia da: espansione industriale, inflazione commodity, dollaro debole. Rischio: recessione, dollaro forte, oversupply.',
    etf_us: [['XLB','SPDR Materials (TER 0.10%)'],['VAW','Vanguard Materials (TER 0.10%)'],['GDX','VanEck Gold Miners (TER 0.51%)'],['PICK','iShares Global Metals & Mining (TER 0.39%)']],
    etf_eu: [],
    fondi:  ['Fidelity Select Materials (FSDPX)','Vanguard Materials Fund (VMIAX)'],
  },
  'Real Estate': {
    desc: 'REIT (Real Estate Investment Trust): uffici, residenziale, data center, logistica, retail, healthcare. Alta cedola da dividendi.',
    include: 'Prologis (PLD), American Tower (AMT), Equinix (EQIX), Simon Property (SPG), Extra Space (EXR)',
    ciclo: 'Bond proxy. Beneficia da: tassi bassi, e-commerce, AI (data center REIT). Rischio: tassi alti (aumento costo debito), vacancy uffici post-Covid.',
    etf_us: [['XLRE','SPDR Real Estate (TER 0.10%)'],['VNQ','Vanguard Real Estate (TER 0.12%)'],['REET','iShares Global REIT (TER 0.14%)']],
    etf_eu: [],
    fondi:  ['Fidelity Real Estate (FRESX)','Vanguard Real Estate Fund (VGSIX)'],
  },
  'Comm. Services': {
    desc: 'Social media, streaming, telecom, media, videogiochi. Mix tra crescita (Meta, Alphabet) e valore difensivo (Verizon, AT&T).',
    include: 'Alphabet (GOOGL), Meta (META), Netflix (NFLX), Comcast (CMCSA), T-Mobile (TMUS)',
    ciclo: 'Misto growth/difensivo. Telecom difensivi; media/streaming ciclici. Beneficia da: pubblicità digitale, AI, streaming. Rischio: regolamentazione.',
    etf_us: [['XLC','SPDR Comm. Services (TER 0.10%)'],['VOX','Vanguard Comm. Services (TER 0.10%)'],['FCOM','Fidelity MSCI Comm. (TER 0.08%)']],
    etf_eu: [['EXH6.DE','iShares STOXX EU Media (TER 0.46%)']],
    fondi:  ['Fidelity Select Telecommunications (FSTCX)'],
  },
};

var NAZIONI_ETF = {
  'USA':       { desc:'Il mercato azionario più grande al mondo (~45% market cap globale). Altissima liquidità e trasparenza.', etf_us:[['SPY','SPDR S&P 500 (TER 0.09%)'],['SPLG','SPDR Portfolio S&P 500 (TER 0.02%)'],['VTI','Vanguard Total Market (TER 0.03%)']], etf_eu:[['CSPX.L','iShares S&P 500 UCITS (TER 0.07%)'],['VUAA.AS','Vanguard S&P 500 UCITS (TER 0.07%)']] },
  'USA Tech':  { desc:'Esposizione concentrata al Nasdaq 100 — le 100 maggiori aziende non-finanziarie quotate sul Nasdaq.', etf_us:[['QQQ','Invesco Nasdaq 100 (TER 0.20%)'],['QQQM','Invesco Nasdaq 100 Mini (TER 0.15%)']], etf_eu:[['EQQQ.L','Invesco EQQQ Nasdaq (TER 0.30%)'],['CNDX.AS','iShares Nasdaq 100 UCITS (TER 0.33%)']] },
  'Canada':    { desc:'TSX dominato da energia, materiali e banche. Fortemente correlato alle commodity. Valuta CAD.', etf_us:[['EWC','iShares MSCI Canada (TER 0.50%)']], etf_eu:[] },
  'Brasile':   { desc:'Mercato emergente con focus su commodity, energia e banche. Alta volatilità e rischio politico/cambio.', etf_us:[['EWZ','iShares MSCI Brazil (TER 0.59%)'],['FLBR','Franklin FTSE Brazil (TER 0.19%)']], etf_eu:[] },
  'Messico':   { desc:'Economia emergente in crescita. Beneficia dal nearshoring USA. IPC concentrato in poche grandi aziende.', etf_us:[['EWW','iShares MSCI Mexico (TER 0.50%)']], etf_eu:[] },
  'UK':        { desc:'FTSE 100 dominato da energia (BP, Shell), banche, farmaceutiche. Alta dividend yield. Valuta GBP.', etf_us:[['EWU','iShares MSCI UK (TER 0.50%)']], etf_eu:[['VUKE.L','Vanguard FTSE 100 (TER 0.09%)'],['ISF.L','iShares Core FTSE 100 (TER 0.07%)']] },
  'Germania':  { desc:'DAX 40: auto (BMW, Mercedes, VW), chimica (BASF), assicurazioni (Allianz). Barometro dell\'economia EU.', etf_us:[['EWG','iShares MSCI Germany (TER 0.50%)']], etf_eu:[['EXS1.DE','iShares Core DAX (TER 0.16%)'],['DBXD.DE','Xtrackers DAX (TER 0.09%)']] },
  'Francia':   { desc:'CAC 40: lusso (LVMH, L\'Oréal, Hermès), aerospazio (Airbus), energia (TotalEnergies). Forte export globale.', etf_us:[['EWQ','iShares MSCI France (TER 0.50%)']], etf_eu:[] },
  'Italia':    { desc:'FTSE MIB: banche (Intesa, Unicredit), energy (ENI, Enel), lusso (Moncler, Ferrari). Spread BTP driver chiave.', etf_us:[['EWI','iShares MSCI Italy (TER 0.50%)']], etf_eu:[] },
  'Spagna':    { desc:'IBEX 35: banche (Santander, BBVA), telecom (Telefónica), utility (Iberdrola). Forte esposizione Latam.', etf_us:[['EWP','iShares MSCI Spain (TER 0.50%)']], etf_eu:[] },
  'Svizzera':  { desc:'SMI: farmaceutiche (Novartis, Roche), beni di lusso (Richemont), alimentari (Nestlé). Mercato molto difensivo.', etf_us:[['EWL','iShares MSCI Switzerland (TER 0.50%)']], etf_eu:[] },
  'Olanda':    { desc:'AEX: semiconduttori (ASML ~25% peso), energia (Shell), finanza (ING). ASML è il principale driver.', etf_us:[['EWN','iShares MSCI Netherlands (TER 0.50%)']], etf_eu:[] },
  'Giappone':  { desc:'Nikkei 225: auto (Toyota, Honda), tech (Sony, SoftBank), industria. Yen debole = vantaggio esportatori.', etf_us:[['EWJ','iShares MSCI Japan (TER 0.50%)'],['DXJ','WisdomTree Japan Hedged (TER 0.48%)']], etf_eu:[['VJPN.AS','Vanguard Japan UCITS (TER 0.15%)'],['ISJP.L','iShares Core MSCI Japan (TER 0.15%)']] },
  'Hong Kong': { desc:'Hang Seng: fortemente esposto alla Cina. Tech (Tencent, Alibaba), banche, immobiliare. Rischio geopolitico.', etf_us:[['EWH','iShares MSCI Hong Kong (TER 0.50%)']], etf_eu:[] },
  'Cina':      { desc:'Shanghai Comp.: tech di Stato, banche, energia. Rischio regolamentazione, geopolitica, crisi immobiliare.', etf_us:[['FXI','iShares China Large-Cap (TER 0.74%)'],['MCHI','iShares MSCI China (TER 0.59%)'],['KWEB','KraneShares China Internet (TER 0.76%)']], etf_eu:[['CNYA.L','iShares MSCI China A UCITS (TER 0.40%)']] },
  'India':     { desc:'BSE Sensex: crescita demografica, IT (Infosys, TCS), consumer. Tra i mercati emergenti con crescita più rapida.', etf_us:[['INDA','iShares MSCI India (TER 0.65%)'],['INDY','iShares India 50 (TER 0.93%)']], etf_eu:[] },
  'Australia': { desc:'ASX 200: banche (CBA, ANZ, NAB), mining (BHP, Rio Tinto), REIT. Fortemente correlato alle commodity.', etf_us:[['EWA','iShares MSCI Australia (TER 0.50%)']], etf_eu:[] },
  'Corea Sud': { desc:'KOSPI: semiconduttori (Samsung, SK Hynix), auto (Hyundai, Kia), tech. Il ciclo dei chip è il driver principale.', etf_us:[['EWY','iShares MSCI South Korea (TER 0.50%)']], etf_eu:[] },
  'Singapore': { desc:'STI: hub finanziario Asia. Banche (DBS, OCBC, UOB), REIT, telecom. Stabile, rating AAA, bassa volatilità.', etf_us:[['EWS','iShares MSCI Singapore (TER 0.50%)']], etf_eu:[] },
  'Indonesia': { desc:'IDX Composite: finanza, commodity, consumer. Alta crescita demografica. Rischio cambio rupiah.', etf_us:[['EIDO','iShares MSCI Indonesia (TER 0.57%)']], etf_eu:[] },
  'Argentina': { desc:'Merval: altissima volatilità, iperinflazione, rischio cambio. Solo per investitori speculativi con orizzonte breve.', etf_us:[['ARGT','Global X MSCI Argentina (TER 0.59%)']], etf_eu:[] },
};

var _settoriData = null;
function loadSettori(force) {
  if (_settoriData && !force) return;
  _settoriData = null;
  var loading = document.getElementById('sett-loading');
  var gics    = document.getElementById('sett-gics');
  var naz     = document.getElementById('sett-nazioni');
  loading.style.display = 'block';
  gics.style.opacity = '0.3';
  naz.style.opacity  = '0.3';
  fetch('/api/settori').then(function(r){ return r.json(); }).then(function(d){
    _settoriData = d;
    loading.style.display = 'none';
    gics.style.opacity = '1';
    naz.style.opacity  = '1';
    if (d.ts) document.getElementById('sett-ts').textContent = 'Aggiornato: ' + d.ts;
    renderSettGics(d);
    renderSettNazioni(d);
  }).catch(function(e){
    loading.innerHTML = '<span style="color:#fca5a5">Errore: ' + e.message + '</span>';
    loading.style.display = 'block';
  });
}
function switchSettTab(el, id) {
  document.querySelectorAll('.sett-subtab').forEach(function(b){ b.classList.remove('active'); });
  document.querySelectorAll('.sett-subpanel').forEach(function(p){ p.style.display = 'none'; });
  el.classList.add('active');
  document.getElementById(id).style.display = 'block';
}
function _settBg(v) {
  if (v === null || v === undefined) return 'rgba(30,41,59,.8)';
  if (v >=  8) return 'rgba(20,83,45,.9)';
  if (v >=  4) return 'rgba(22,101,52,.85)';
  if (v >=  1) return 'rgba(21,128,61,.7)';
  if (v >=  0) return 'rgba(20,83,45,.5)';
  if (v >= -1) return 'rgba(127,29,29,.5)';
  if (v >= -4) return 'rgba(153,27,27,.75)';
  return 'rgba(127,29,29,.95)';
}
function _settPill(v, label) {
  if (v === null || v === undefined)
    return '<span class="sett-pill" style="background:rgba(100,116,139,.25);color:#64748b">' + label + ' —</span>';
  var pos = v >= 0;
  var col = pos ? '#86efac' : '#fca5a5';
  var bg  = pos ? 'rgba(34,197,94,.18)' : 'rgba(239,68,68,.18)';
  return '<span class="sett-pill" style="background:' + bg + ';color:' + col + '">' + label + ' ' + (pos?'+':'') + v.toFixed(2) + '%</span>';
}
function _settInterpreta(d) {
  var m = d.p1m, m3 = d.p3m, m1y = d.p1y, g = d.p1d;
  if (m === null || m === undefined) return {label:'Dati non disponibili', segnali:[], color:'#64748b'};
  var label, color;
  if      (m >= 8  && (m3||0) >= 15) { label='🚀 Forte momentum rialzista';   color='#86efac'; }
  else if (m >= 4  && (m3||0) >= 5)  { label='📈 Trend rialzista';             color='#6ee7b7'; }
  else if (m >= 1)                    { label='↗️ Lieve rialzo';                color='#a7f3d0'; }
  else if (m >= -1)                   { label='↔️ Laterale / neutro';           color='#fbd38d'; }
  else if (m >= -4)                   { label='↘️ Debolezza moderata';          color='#fca5a5'; }
  else if (m >= -8)                   { label='📉 Trend ribassista';            color='#f87171'; }
  else                                { label='🔻 Forte trend ribassista';      color='#ef4444'; }
  var segnali = [];
  if (g !== null && g < -1.5 && (m||0) > 2 && (m1y||0) > 5)
    segnali.push('📌 Pullback su trend rialzista — potenziale ingresso tattico');
  if ((m||0) > 0 && (m3||0) > 0 && (m1y||0) > 0)
    segnali.push('✅ Momentum positivo confermato su 1M + 3M + 1A');
  if ((m1y||0) > 20 && (m||0) < -5)
    segnali.push('⚠️ Correzione su trend annuale positivo — monitorare supporti');
  if ((m||0) < -5 && (m3||0) < -10 && (m1y||0) < -10)
    segnali.push('🚫 Evitare: trend negativo confermato su tutti i timeframe');
  if ((m||0) > 5 && (m3||0) > 10)
    segnali.push('🔥 Settore in forte momentum — considerare sovrappeso in portafoglio');
  if ((m||0) > 0 && (m3||0) < -5)
    segnali.push('⚡ Possibile rimbalzo tecnico da ipervenduto — verificare con volumi');
  return {label:label, segnali:segnali, color:color};
}
var _settPerf = {};
function renderSettGics(d) {
  function makeGrid(items, cid, regione) {
    var html = '';
    items.forEach(function(s) {
      _settPerf[s.ticker] = {p1d:s.p1d, p1w:s.p1w, p1m:s.p1m, p3m:s.p3m, p1y:s.p1y};
      var bg  = _settBg(s.p1m);
      var nom = s.nome.replace(/\\/g,'\\\\').replace(/'/g,"\\'");
      var tk  = s.ticker.replace(/'/g,"\\'");
      html += '<div class="sett-card" style="background:' + bg + '" onclick="openSettModal(\'' +
              nom + '\',\'' + tk + '\',\'' + regione + '\')">' +
              '<div class="sett-card-emoji">' + s.emoji + '</div>' +
              '<div class="sett-card-nome">'  + s.nome   + '</div>' +
              '<div class="sett-card-ticker">' + s.ticker + '</div>' +
              '<div class="sett-card-prezzo">' + (s.prezzo !== null ? s.prezzo : '—') + '</div>' +
              '<div class="sett-perf-row">' +
                _settPill(s.p1d,'1G') + _settPill(s.p1w,'1S') +
                _settPill(s.p1m,'1M') + _settPill(s.p3m,'3M') + _settPill(s.p1y,'1A') +
              '</div></div>';
    });
    document.getElementById(cid).innerHTML = html || '<span style="opacity:.4">Nessun dato disponibile</span>';
  }
  makeGrid(d.settori_us, 'sett-us-grid', 'us');
  makeGrid(d.settori_eu, 'sett-eu-grid', 'eu');
}
function renderSettNazioni(d) {
  var regioni = {}, order = [];
  d.nazioni.forEach(function(n) {
    if (!regioni[n.regione]) { regioni[n.regione] = []; order.push(n.regione); }
    regioni[n.regione].push(n);
  });
  var html = '';
  order.forEach(function(reg) {
    html += '<div class="sett-section-title">' + reg + '</div>';
    html += '<div class="tbl-wrap" style="margin-bottom:1.4rem"><table style="width:100%;border-collapse:collapse">' +
            '<thead><tr style="font-size:.7rem;opacity:.5;text-align:right">' +
            '<th style="text-align:left;padding:.35rem .6rem">Paese</th>' +
            '<th style="text-align:left;padding:.35rem .6rem">Indice</th>' +
            '<th style="padding:.35rem .6rem">Prezzo</th>' +
            '<th style="padding:.35rem .6rem">1G</th><th style="padding:.35rem .6rem">1S</th>' +
            '<th style="padding:.35rem .6rem">1M</th><th style="padding:.35rem .6rem">3M</th>' +
            '<th style="padding:.35rem .6rem">1A</th>' +
            '<th style="padding:.35rem .6rem"></th><th style="padding:.35rem .6rem"></th>' +
            '</tr></thead><tbody>';
    regioni[reg].forEach(function(n) {
      function fmtTd(v) {
        if (v===null||v===undefined) return '<td style="text-align:right;padding:.3rem .5rem;opacity:.3">—</td>';
        var c = v>=0?'#86efac':'#fca5a5';
        return '<td style="text-align:right;padding:.3rem .5rem;color:'+c+';font-weight:600">'+(v>=0?'+':'')+v.toFixed(2)+'%</td>';
      }
      var sema = n.p1m===null ? '⚪' : (n.p1m>=2?'🟢':(n.p1m<=-2?'🔴':'🟡'));
      var nm   = n.nome.replace(/'/g,"\\'");
      html += '<tr style="border-bottom:1px solid rgba(255,255,255,.04);font-size:.8rem">' +
              '<td style="padding:.3rem .6rem">' + n.flag + ' <strong>' + n.nome + '</strong></td>' +
              '<td style="padding:.3rem .6rem;opacity:.55;font-size:.72rem">' + n.indice + '</td>' +
              '<td style="text-align:right;padding:.3rem .5rem;font-family:monospace">' + (n.prezzo!==null?n.prezzo:'—') + '</td>' +
              fmtTd(n.p1d)+fmtTd(n.p1w)+fmtTd(n.p1m)+fmtTd(n.p3m)+fmtTd(n.p1y)+
              '<td style="padding:.3rem .5rem;font-size:.9rem">' + sema + '</td>' +
              '<td style="padding:.3rem .5rem"><button onclick="openNazioneModal(\'' + nm + '\')" style="background:rgba(44,82,130,.4);border:none;color:#90cdf4;padding:.15rem .5rem;border-radius:4px;cursor:pointer;font-size:.68rem">ETF ▸</button></td>' +
              '</tr>';
    });
    html += '</tbody></table></div>';
  });
  document.getElementById('sett-naz-wrap').innerHTML = html;
}
function _etfTableHtml(lista, titolo) {
  if (!lista || lista.length === 0) return '';
  var rows = lista.map(function(e){
    return '<tr style="border-bottom:1px solid rgba(255,255,255,.05);font-size:.79rem">' +
           '<td style="padding:.28rem .5rem;font-family:monospace;font-weight:700;color:#fbd38d">' + e[0] + '</td>' +
           '<td style="padding:.28rem .5rem;opacity:.75">' + e[1] + '</td>' +
           '<td style="padding:.28rem .5rem">' +
           '<a href="https://finance.yahoo.com/quote/' + encodeURIComponent(e[0]) + '" target="_blank" style="color:#60a5fa;font-size:.7rem;text-decoration:none">YF ↗</a></td>' +
           '</tr>';
  }).join('');
  return '<div style="font-size:.72rem;font-weight:700;opacity:.55;margin:.7rem 0 .35rem">' + titolo + '</div>' +
         '<table style="width:100%;border-collapse:collapse"><tbody>' + rows + '</tbody></table>';
}
function openSettModal(settore, ticker, regione) {
  var modal = document.getElementById('sett-modal');
  var title = document.getElementById('sett-modal-title');
  var sub   = document.getElementById('sett-modal-sub');
  var info  = document.getElementById('sett-modal-info');
  var body  = document.getElementById('sett-modal-body');
  title.textContent = settore + '  ·  ' + ticker;
  sub.textContent   = (regione==='eu'?'Europa — iShares STOXX Europe 600 Sector ETF':'USA — SPDR Sector ETF');
  body.innerHTML    = '<div style="text-align:center;padding:2rem;opacity:.5">⏳ Caricamento titoli...</div>';
  modal.style.display = 'block';
  var key  = (regione === 'eu') ? (EU_TO_US[settore] || settore) : settore;
  var inf  = SETT_INFO[key] || {};
  var intp = _settInterpreta(_settPerf[ticker] || {});
  var etfHtml = regione === 'eu'
    ? _etfTableHtml(inf.etf_eu, '🇪🇺 ETF Europa (UCITS) consigliati') +
      _etfTableHtml(inf.etf_us, '🇺🇸 ETF USA equivalenti')
    : _etfTableHtml(inf.etf_us, '🇺🇸 ETF USA consigliati') +
      _etfTableHtml(inf.etf_eu, '🇪🇺 ETF Europa (UCITS) equivalenti');
  var fondiHtml = (inf.fondi && inf.fondi.length)
    ? '<div style="font-size:.72rem;font-weight:700;opacity:.55;margin:.7rem 0 .3rem">🏦 Fondi US</div>' +
      '<ul style="margin:0;padding-left:1.2rem;font-size:.78rem;opacity:.7">' +
      inf.fondi.map(function(f){ return '<li>' + f + '</li>'; }).join('') + '</ul>'
    : '';
  var segnaliHtml = intp.segnali.length
    ? '<ul style="margin:.4rem 0 0;padding-left:1.1rem;font-size:.78rem;opacity:.85">' +
      intp.segnali.map(function(s){ return '<li style="margin-bottom:.25rem">' + s + '</li>'; }).join('') + '</ul>'
    : '';
  info.innerHTML =
    '<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">' +
      '<div style="background:rgba(15,23,42,.7);border:1px solid rgba(44,82,130,.35);border-radius:8px;padding:1rem">' +
        '<div style="font-size:.72rem;font-weight:700;opacity:.5;margin-bottom:.4rem;text-transform:uppercase;letter-spacing:.05em">📋 Descrizione</div>' +
        '<div style="font-size:.8rem;opacity:.85;line-height:1.6;margin-bottom:.6rem">' + (inf.desc||'—') + '</div>' +
        '<div style="font-size:.72rem;opacity:.5;margin-bottom:.2rem"><strong>Principali titoli:</strong></div>' +
        '<div style="font-size:.75rem;opacity:.65;margin-bottom:.6rem">' + (inf.include||'—') + '</div>' +
        '<div style="font-size:.72rem;opacity:.5;margin-bottom:.2rem"><strong>Ciclicità:</strong></div>' +
        '<div style="font-size:.75rem;opacity:.65">' + (inf.ciclo||'—') + '</div>' +
      '</div>' +
      '<div>' +
        '<div style="background:rgba(15,23,42,.7);border:1px solid rgba(44,82,130,.35);border-radius:8px;padding:1rem;margin-bottom:.8rem">' +
          '<div style="font-size:.72rem;font-weight:700;opacity:.5;margin-bottom:.4rem;text-transform:uppercase;letter-spacing:.05em">📈 Situazione attuale</div>' +
          '<div style="font-size:.9rem;font-weight:700;color:' + intp.color + ';margin-bottom:.4rem">' + intp.label + '</div>' +
          segnaliHtml +
        '</div>' +
        '<div style="background:rgba(15,23,42,.7);border:1px solid rgba(44,82,130,.35);border-radius:8px;padding:1rem">' +
          '<div style="font-size:.72rem;font-weight:700;opacity:.5;margin-bottom:.4rem;text-transform:uppercase;letter-spacing:.05em">🛒 ETF &amp; Fondi consigliati</div>' +
          etfHtml + fondiHtml +
        '</div>' +
      '</div>' +
    '</div>' +
    '<div style="border-top:1px solid rgba(255,255,255,.08);margin-top:1.2rem;padding-top:1rem;font-size:.75rem;font-weight:600;opacity:.5">Titoli nel database screener</div>';
  fetch('/api/settori/titoli?s=' + encodeURIComponent(settore)).then(function(r){ return r.json(); }).then(function(d){
    if (!d.titoli || d.titoli.length === 0) {
      body.innerHTML = '<p style="opacity:.4;text-align:center;padding:1.5rem">Nessun titolo trovato — esegui lo screener azioni per popolare i dati.</p>';
      return;
    }
    sub.textContent = (regione==='eu'?'Europa — iShares STOXX Europe 600':'USA — SPDR') + ' · ' + d.tot + ' titoli nel database';
    var rows = d.titoli.map(function(t) {
      function fp(v) {
        if (v===null||v===undefined) return '<span style="opacity:.3">—</span>';
        var c = parseFloat(v)>=0?'#86efac':'#fca5a5';
        return '<span style="color:'+c+'">'+(parseFloat(v)>=0?'+':'')+parseFloat(v).toFixed(1)+'%</span>';
      }
      var sc    = t.score!==null ? parseFloat(t.score) : null;
      var scCol = sc===null?'#64748b':(sc>=70?'#86efac':(sc>=50?'#fbd38d':'#fca5a5'));
      var fsh   = t.foglio||'';
      var badge = (fsh.indexOf('Selezionat')>=0||fsh.indexOf('Top')>=0)
                  ? '<span style="font-size:.58rem;background:rgba(34,197,94,.2);color:#86efac;padding:.1rem .35rem;border-radius:3px;margin-left:.3rem">SEL</span>' : '';
      return '<tr style="border-bottom:1px solid rgba(255,255,255,.04);font-size:.79rem">' +
             '<td style="padding:.3rem .5rem;font-family:monospace;font-weight:700">' + t.ticker + badge + '</td>' +
             '<td style="padding:.3rem .5rem;max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="'+t.nome+'">'+t.nome+'</td>' +
             '<td style="padding:.3rem .5rem;opacity:.5;font-size:.7rem">'+t.mercato+'</td>' +
             '<td style="padding:.3rem .5rem;text-align:right;font-weight:700;color:'+scCol+'">'+(sc!==null?sc.toFixed(1):'—')+'</td>' +
             '<td style="padding:.3rem .5rem;text-align:right">'+fp(t.p1d)+'</td>' +
             '<td style="padding:.3rem .5rem;text-align:right">'+fp(t.p1y)+'</td>' +
             '</tr>';
    }).join('');
    body.innerHTML = '<div class="tbl-wrap"><table style="width:100%;border-collapse:collapse">' +
      '<thead><tr style="font-size:.68rem;opacity:.45;text-align:right">' +
      '<th style="text-align:left;padding:.3rem .5rem">Ticker</th><th style="text-align:left;padding:.3rem .5rem">Nome</th>' +
      '<th style="text-align:left;padding:.3rem .5rem">Mercato</th><th style="padding:.3rem .5rem">Score</th>' +
      '<th style="padding:.3rem .5rem">1G%</th><th style="padding:.3rem .5rem">1A%</th>' +
      '</tr></thead><tbody>' + rows + '</tbody></table></div>';
  }).catch(function(e){
    body.innerHTML = '<span style="color:#fca5a5">Errore: ' + e.message + '</span>';
  });
}
function openNazioneModal(nome) {
  var modal = document.getElementById('sett-modal');
  var title = document.getElementById('sett-modal-title');
  var sub   = document.getElementById('sett-modal-sub');
  var info  = document.getElementById('sett-modal-info');
  var body  = document.getElementById('sett-modal-body');
  var n     = NAZIONI_ETF[nome] || {};
  title.textContent = nome + ' — Mercato & ETF';
  sub.textContent   = n.desc || '—';
  body.innerHTML    = '';
  var etfHtml = _etfTableHtml(n.etf_us, '🇺🇸 ETF USA per esposizione a ' + nome) +
                _etfTableHtml(n.etf_eu, '🇪🇺 ETF Europa (UCITS) equivalenti');
  info.innerHTML =
    '<div style="background:rgba(15,23,42,.7);border:1px solid rgba(44,82,130,.35);border-radius:8px;padding:1.1rem">' +
      (etfHtml || '<span style="opacity:.4">Nessun ETF mappato per questo mercato</span>') +
      '<div style="font-size:.7rem;opacity:.4;margin-top:.8rem">ℹ️ TER = Total Expense Ratio annuo · Clicca YF per dati live su Yahoo Finance</div>' +
    '</div>';
  modal.style.display = 'block';
}
"""
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Robot Trader 2026 — Analisi Settoriale &amp; Mercati</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0f1e;font-family:'Segoe UI',Arial,sans-serif;min-height:100vh;color:#e0e0e0}}
.top{{background:linear-gradient(135deg,#1a2744,#0d1b35);padding:1.2rem 2rem;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid rgba(246,173,85,.2)}}
.main{{max-width:1100px;margin:2rem auto;padding:0 1.2rem 3rem}}
.back{{background:transparent;border:1px solid rgba(255,255,255,.15);color:#aaa;padding:.4rem .9rem;border-radius:6px;font-size:.82rem;cursor:pointer;text-decoration:none}}
.back:hover{{border-color:#F6AD55;color:#F6AD55}}
.tbl-wrap{{overflow-x:auto;border:1px solid rgba(44,82,130,.4);border-radius:8px;background:rgba(0,0,0,.2)}}
.db-tabs{{display:flex;gap:.4rem;margin-bottom:1rem;flex-wrap:wrap}}
.db-tab{{padding:.45rem 1.1rem;border-radius:6px;border:1px solid rgba(44,82,130,.5);background:transparent;color:rgba(255,255,255,.5);cursor:pointer;font-size:.82rem;font-weight:600;transition:all .18s}}
.db-tab:hover{{border-color:#F6AD55;color:#F6AD55}}
.db-tab.active{{background:#2C5282;border-color:#2C5282;color:#F6AD55}}
.sett-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:.8rem;margin-bottom:1.6rem}}
.sett-card{{border-radius:10px;padding:.9rem 1rem;cursor:pointer;transition:transform .15s,box-shadow .15s;border:1px solid rgba(255,255,255,.1)}}
.sett-card:hover{{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.5)}}
.sett-card-emoji{{font-size:1.3rem;margin-bottom:.25rem}}
.sett-card-nome{{font-size:.78rem;font-weight:700;line-height:1.2;margin-bottom:.15rem}}
.sett-card-ticker{{font-size:.68rem;opacity:.45;margin-bottom:.5rem;font-family:monospace}}
.sett-card-prezzo{{font-size:.95rem;font-weight:700;margin-bottom:.5rem;font-family:monospace}}
.sett-perf-row{{display:flex;gap:.3rem;flex-wrap:wrap}}
.sett-pill{{font-size:.62rem;padding:.12rem .35rem;border-radius:3px;font-weight:700;white-space:nowrap}}
.sett-section-title{{font-size:.85rem;font-weight:600;opacity:.6;margin:.5rem 0 .8rem;letter-spacing:.04em}}
</style>
</head>
<body>
<div class="top">
  <div style="display:flex;align-items:center;gap:1rem">
    <img src="data:image/png;base64,{_logo}" alt="Fuerte" style="height:36px;display:block">
    <div style="font-size:.85rem;color:rgba(255,255,255,.5)">Analisi Settoriale &amp; Mercati</div>
  </div>
  <a href="/area-clienti" class="back">&#8592; Area Riservata</a>
</div>
<div class="main">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;flex-wrap:wrap;gap:.6rem">
    <h2 style="color:#F6AD55;font-size:1.1rem;font-weight:700">&#127757; Analisi Settoriale &amp; Mercati</h2>
    <div style="display:flex;align-items:center;gap:.8rem">
      <span id="sett-ts" style="font-size:.72rem;opacity:.45">&#8212;</span>
      <button onclick="loadSettori(true)" style="background:#2C5282;border:none;color:#F6AD55;padding:.3rem .8rem;border-radius:6px;cursor:pointer;font-size:.78rem;font-weight:600">&#x1F504; Aggiorna</button>
    </div>
  </div>
  <div style="margin-bottom:1.2rem">
    <button onclick="var g=document.getElementById('sett-guide');g.style.display=g.style.display==='none'?'block':'none'" style="background:rgba(44,82,130,.25);border:1px solid rgba(44,82,130,.5);color:#90cdf4;padding:.3rem .85rem;border-radius:6px;cursor:pointer;font-size:.76rem">&#128214; Come leggere questi dati &#9658;</button>
    <div id="sett-guide" style="display:none;background:rgba(15,23,42,.85);border:1px solid rgba(44,82,130,.35);border-radius:8px;padding:1.2rem 1.4rem;margin-top:.7rem;font-size:.78rem;line-height:1.75">
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1.2rem 2rem">
        <div><strong style="color:#F6AD55">&#128202; Periodi temporali</strong><br><span style="opacity:.75">
          <strong>1G</strong> &#8212; variazione giornaliera (alta volatilit&#224;, poco predittiva)<br>
          <strong>1S</strong> &#8212; trend settimanale &#8594; utile per timing ingresso/uscita<br>
          <strong>1M</strong> &#8212; momentum mensile &#8594; <em>il pi&#249; importante per decisioni tattiche</em><br>
          <strong>3M</strong> &#8212; tendenza trimestrale &#8594; conferma la direzione<br>
          <strong>1A</strong> &#8212; trend strutturale &#8594; forza secolare del settore/mercato
        </span></div>
        <div><strong style="color:#F6AD55">&#127912; Scala colori card settori</strong><br><span style="opacity:.75">
          <span style="color:#86efac">&#9632;</span> Verde scuro &#8594; +8%+ mensile (forte momentum)<br>
          <span style="color:#6ee7b7">&#9632;</span> Verde medio &#8594; tra +4% e +8% mensile<br>
          <span style="color:#a7f3d0">&#9632;</span> Verde chiaro &#8594; tra 0% e +4% mensile<br>
          <span style="color:#fca5a5">&#9632;</span> Rosso chiaro &#8594; tra 0% e -4% mensile<br>
          <span style="color:#f87171">&#9632;</span> Rosso scuro &#8594; oltre -4% mensile (trend negativo)
        </span></div>
        <div><strong style="color:#F6AD55">&#128680; Semaforo nazioni</strong><br><span style="opacity:.75">
          &#x1F7E2; &gt; +2% mensile &#8594; mercato in fase rialzista<br>
          &#x1F7E1; tra &#8722;2% e +2% &#8594; mercato laterale / neutro<br>
          &#x1F534; &lt; &#8722;2% mensile &#8594; mercato in fase ribassista<br><br>
          <em>Combina sempre 1M + 3M per evitare falsi segnali</em>
        </span></div>
        <div><strong style="color:#F6AD55">&#128204; Come usare i dati</strong><br><span style="opacity:.75">
          <strong>Sovrappeso:</strong> 1M, 3M e 1A tutti positivi &#8594; momentum confermato<br>
          <strong>Ingresso tattico:</strong> 1G negativo ma 1M e 1A positivi &#8594; pullback su trend<br>
          <strong>Attenzione:</strong> 1A positivo, 3M e 1M negativi &#8594; possibile inversione<br>
          <strong>Evitare:</strong> 1M, 3M e 1A tutti negativi &#8594; trend negativo confermato<br>
          Clicca una card &#8594; vedi descrizione settore + ETF/Fondi consigliati
        </span></div>
      </div>
    </div>
  </div>
  <div class="db-tabs" style="margin-bottom:1.4rem">
    <button class="db-tab sett-subtab active" onclick="switchSettTab(this,'sett-gics')">&#128202; Settori GICS</button>
    <button class="db-tab sett-subtab" onclick="switchSettTab(this,'sett-nazioni')">&#127760; Nazioni &amp; Mercati</button>
  </div>
  <div id="sett-loading" style="display:none;text-align:center;padding:3rem;opacity:.6">
    <div style="font-size:2rem;margin-bottom:.6rem">&#9203;</div>
    <div>Caricamento dati da Yahoo Finance...</div>
    <div style="font-size:.75rem;margin-top:.4rem;opacity:.7">Primo caricamento ~10 secondi</div>
  </div>
  <div id="sett-gics" class="sett-subpanel">
    <div class="sett-section-title">&#127482;&#127480; USA &#8212; SPDR Sector ETFs (11 settori GICS)</div>
    <div id="sett-us-grid" class="sett-grid"></div>
    <div class="sett-section-title">&#127466;&#127482; Europa &#8212; iShares STOXX Europe 600 Sector ETFs</div>
    <div id="sett-eu-grid" class="sett-grid"></div>
  </div>
  <div id="sett-nazioni" class="sett-subpanel" style="display:none">
    <div id="sett-naz-wrap"></div>
  </div>
</div>
<div id="sett-modal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.75);z-index:9000;overflow-y:auto">
  <div style="background:#1a1a2e;margin:3rem auto 2rem;max-width:920px;border-radius:12px;padding:1.8rem;position:relative;border:1px solid rgba(44,82,130,.5)">
    <button onclick="document.getElementById('sett-modal').style.display='none'" style="position:absolute;top:1rem;right:1rem;background:none;border:none;color:#aaa;font-size:1.5rem;cursor:pointer;line-height:1">&#x2715;</button>
    <h3 id="sett-modal-title" style="margin-bottom:.4rem;color:#F6AD55;font-size:1rem"></h3>
    <p id="sett-modal-sub" style="font-size:.75rem;opacity:.5;margin-bottom:1rem"></p>
    <div id="sett-modal-info" style="margin-bottom:1.2rem"></div>
    <div id="sett-modal-body"></div>
  </div>
</div>
<script>""" + _js + """
window.addEventListener('load', function(){ loadSettori(false); });
</script>
</body>
</html>"""


def _build_area_clienti(email):
    """Genera HTML area riservata per il cliente autenticato."""
    db = read_clienti()
    cliente = None
    for c in (db.get('tester', []) + db.get('clienti', [])):
        if c.get('email', '').lower() == email.lower():
            cliente = c; break
    if not cliente:
        return None

    nome = cliente.get('nome', email)
    piani = {
        'azioni': cliente.get('piano_azioni', 'NONE'),
        'etf':    cliente.get('piano_etf',    'NONE'),
        'fondi':  cliente.get('piano_fondi',  'NONE'),
    }
    piano_ordini = cliente.get('piano_ordini', 'NONE')
    piano_color = {'NONE':'#555','BASIC':'#4A90D9','PRO':'#F6AD55','VALUE':'#68D391'}

    # ── Badge trial ─────────────────────────────────────────────
    trial_badge = ''
    if cliente.get('stato') == 'TESTER' and cliente.get('trial_end'):
        try:
            _trial_end = datetime.strptime(cliente['trial_end'][:19], '%Y-%m-%dT%H:%M:%S')
            _giorni = (_trial_end - datetime.now()).days
            if _giorni > 1:
                trial_badge = (
                    f'<div style="background:rgba(246,173,85,.07);border:1px solid rgba(246,173,85,.25);'
                    f'border-radius:8px;padding:.6rem 1rem;font-size:.82rem;color:#F6AD55;margin-bottom:1rem">'
                    f'⏱ Periodo di prova: <strong>{_giorni} giorni rimanenti</strong>'
                    f' &nbsp;·&nbsp; <a href="mailto:info@fuerteventurecapital.com" style="color:#F6AD55">Attiva un piano</a></div>'
                )
            elif _giorni == 1:
                trial_badge = (
                    f'<div style="background:rgba(252,129,129,.07);border:1px solid rgba(252,129,129,.3);'
                    f'border-radius:8px;padding:.6rem 1rem;font-size:.82rem;color:#FC8181;margin-bottom:1rem">'
                    f'⚠ Periodo di prova: <strong>ultimo giorno!</strong>'
                    f' &nbsp;·&nbsp; <a href="mailto:info@fuerteventurecapital.com" style="color:#FC8181">Attiva ora</a></div>'
                )
            elif _giorni == 0:
                trial_badge = (
                    f'<div style="background:rgba(252,129,129,.07);border:1px solid rgba(252,129,129,.3);'
                    f'border-radius:8px;padding:.6rem 1rem;font-size:.82rem;color:#FC8181;margin-bottom:1rem">'
                    f'⚠ Periodo di prova: <strong>scade oggi!</strong>'
                    f' &nbsp;·&nbsp; <a href="mailto:info@fuerteventurecapital.com" style="color:#FC8181">Attiva ora</a></div>'
                )
        except Exception:
            pass

    def piano_badge(asset):
        p = piani[asset]
        c = piano_color.get(p, '#555')
        return (f'<span style="background:{c}22;color:{c};border:1px solid {c}44;'
                f'border-radius:6px;padding:.25rem .7rem;font-size:.82rem;font-weight:600">{p}</span>')

    def _upgrade_btn(asset, label, current):
        if current in ('VALUE', 'NONE'):
            return ''
        style = 'background:linear-gradient(135deg,#744210,#b7791f)'
        return (f'<button onclick="apriModalPiano(\'{asset}\',\'{label}\',\'{current}\')" '
                f'style="{style};color:#fff;border:none;border-radius:6px;'
                f'padding:.35rem .9rem;font-size:.8rem;font-weight:600;cursor:pointer;white-space:nowrap">'
                f'⬆ Upgrade</button>')

    def report_row(asset, label, icon):
        p = piani[asset]
        if p == 'NONE':
            return (f'<div style="background:rgba(255,255,255,.03);border-radius:10px;padding:1rem 1.2rem;'
                    f'display:flex;align-items:center;margin-bottom:.6rem">'
                    f'<span style="color:#444">{icon} {label} — nessun piano attivo</span></div>')
        f = _latest_plan(asset, p)
        fname = os.path.basename(f) if f else None
        if fname:
            _fpdf = _latest_plan_pdf(asset, p)
            if _fpdf:
                dl = (f'<a href="/api/report-pdf/{asset}" '
                      f'style="background:#F6AD55;color:#0a0f1e;padding:.4rem 1rem;border-radius:6px;'
                      f'font-weight:700;font-size:.82rem;text-decoration:none">⬇ Scarica PDF</a>')
            else:
                dl = (f'<a href="/api/report/{asset}" '
                      f'style="background:#F6AD55;color:#0a0f1e;padding:.4rem 1rem;border-radius:6px;'
                      f'font-weight:700;font-size:.82rem;text-decoration:none">⬇ Scarica</a>')
            info = f'<span style="font-size:.78rem;color:#888">{fname}</span>'
        else:
            dl = '<span style="color:#555;font-size:.82rem">Nessun report disponibile</span>'
            info = ''
        return (f'<div style="background:rgba(255,255,255,.03);border-radius:10px;padding:1rem 1.2rem;'
                f'display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem;margin-bottom:.6rem">'
                f'<div><div style="font-weight:600;margin-bottom:.3rem">{icon} {label} — {piano_badge(asset)}</div>{info}</div>'
                f'<div style="display:flex;gap:.5rem;align-items:center">{dl}{_upgrade_btn(asset, label, p)}</div></div>')

    rows = (report_row('azioni','Azioni','📈') +
            report_row('etf',   'ETF',  '📦') +
            report_row('fondi', 'Fondi','🏦'))

    _idee_card = (
        '<a href="/idee" style="display:block;text-decoration:none;'
        'background:linear-gradient(135deg,rgba(20,83,45,.3),rgba(15,23,42,.6));'
        'border:1px solid rgba(34,197,94,.25);border-radius:10px;padding:1rem 1.2rem;'
        'margin-bottom:.6rem;transition:border-color .2s" '
        'onmouseover="this.style.borderColor=\'#68D391\'" onmouseout="this.style.borderColor=\'rgba(34,197,94,.25)\'">'
        '<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem">'
        '<div>'
        '<div style="font-weight:700;font-size:.95rem;color:#68D391;margin-bottom:.3rem">&#x1F4A1; Idee di Investimento</div>'
        '<div style="font-size:.78rem;color:#888;line-height:1.5">'
        'Settori e mercati in momentum positivo questa settimana, con i migliori titoli del tuo screener per ognuno. '
        'Semplice e immediato: cosa guarda il mercato adesso.'
        '</div>'
        '</div>'
        '<span style="font-size:.82rem;color:#68D391;white-space:nowrap;font-weight:600">Apri &#8594;</span>'
        '</div>'
        '</a>'
    )

    _pi = cliente.get('profilo_investitore') if cliente else None
    _pi_label = _pi.get('label','') if _pi else ''
    _pi_data  = _pi.get('data','')  if _pi else ''
    _pi_color_map = {'Difensivo':'#4299E1','Prudente':'#48BB78','Bilanciato':'#F6AD55','Dinamico':'#ED8936','Aggressivo':'#FC8181'}
    _pi_color = _pi_color_map.get(_pi_label, '#F6AD55')
    _pi_sub   = (f'<span style="color:{_pi_color};font-weight:700">{_pi_label}</span>'
                 f'<span style="color:#555;font-size:.75rem"> &middot; {_pi_data}</span>') if _pi_label else \
                '<span style="color:#555;font-size:.82rem">Non ancora compilato — fai il test in 3 minuti</span>'
    _profilo_card = (
        '<a href="/profilo-investitore" style="display:block;text-decoration:none;'
        'background:linear-gradient(135deg,rgba(66,153,225,.12),rgba(15,23,42,.6));'
        'border:1px solid rgba(66,153,225,.3);border-radius:10px;padding:1rem 1.2rem;'
        'margin-bottom:.6rem;transition:border-color .2s" '
        'onmouseover="this.style.borderColor=\'#4299E1\'" onmouseout="this.style.borderColor=\'rgba(66,153,225,.3)\'">'
        '<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem">'
        '<div>'
        f'<div style="font-weight:700;font-size:.95rem;color:#90cdf4;margin-bottom:.3rem">&#x1F9E0; Profilo Investitore</div>'
        f'<div style="font-size:.82rem">{_pi_sub}</div>'
        '</div>'
        '<span style="font-size:.82rem;color:#90cdf4;white-space:nowrap;font-weight:600">Apri &#8594;</span>'
        '</div>'
        '</a>'
    )

    _settori_card = (
        '<a href="/settori" style="display:block;text-decoration:none;'
        'background:linear-gradient(135deg,rgba(44,82,130,.25),rgba(15,23,42,.6));'
        'border:1px solid rgba(44,82,130,.45);border-radius:10px;padding:1rem 1.2rem;'
        'margin-bottom:.6rem;transition:border-color .2s" '
        'onmouseover="this.style.borderColor=\'#F6AD55\'" onmouseout="this.style.borderColor=\'rgba(44,82,130,.45)\'">'
        '<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem">'
        '<div>'
        '<div style="font-weight:700;font-size:.95rem;color:#F6AD55;margin-bottom:.3rem">&#127757; Analisi Settoriale &amp; Mercati</div>'
        '<div style="font-size:.78rem;color:#888;line-height:1.5">'
        'Momentum in tempo reale per 11 settori GICS (USA &amp; Europa) e 21 mercati globali. '
        'Card colorate verde/rosso, semaforo nazioni, ETF consigliati per ogni settore e drill-down '
        'sui titoli presenti nel tuo screener.'
        '</div>'
        '</div>'
        '<span style="font-size:.82rem;color:#90cdf4;white-space:nowrap;font-weight:600">Apri &#8594;</span>'
        '</div>'
        '</a>'
    )

    if piano_ordini != 'NONE':
        _asset_info = [('azioni','📈','Azioni'), ('etf','📦','ETF'), ('fondi','🏦','Fondi')]
        _btns = ''.join(
            f'<a href="/ordine-bancario?tipo={_a}" '
            f'style="display:inline-flex;align-items:center;gap:.5rem;'
            f'background:linear-gradient(135deg,#1a365d,#2b6cb0);color:#fff;text-decoration:none;'
            f'padding:.6rem 1.2rem;border-radius:8px;font-weight:700;font-size:.85rem;'
            f'box-shadow:0 2px 8px rgba(43,108,176,.35);white-space:nowrap">'
            f'{_ico} Ordine {_lbl}</a>'
            for _a, _ico, _lbl in _asset_info if piani[_a] != 'NONE'
        )
        if _btns:
            _ordine_block = (
                f'<div style="background:rgba(255,255,255,.03);border-radius:10px;padding:1rem 1.2rem">'
                f'<div style="display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;margin-bottom:.5rem">'
                f'{_btns}'
                f'</div>'
                f'<div style="font-size:.78rem;color:#555">Seleziona il tipo di strumento per creare un ordine con i tuoi titoli già precaricati</div>'
                f'</div>'
            )
        else:
            _ordine_block = (
                f'<div style="background:rgba(255,255,255,.03);border-radius:10px;padding:1rem 1.2rem">'
                f'<span style="color:#718096;font-size:.87rem">📋 Order Builder attivo — '
                f'abbonati a uno screener per creare ordini</span></div>'
            )
    else:
        _ordine_block = (
            f'<div style="background:rgba(255,255,255,.03);border:1px dashed rgba(255,255,255,.1);'
            f'border-radius:10px;padding:1rem 1.2rem;display:flex;align-items:center">'
            f'<span style="color:#444;font-size:.87rem">&#x1F512; <strong style="color:#666">Order Builder</strong>'
            f' — nessun piano attivo</span></div>'
        )

    # ─── Storico ordini cliente ──────────────────────────────────
    if piano_ordini != 'NONE':
        ordini_list = _leggi_ordini_cliente(email)
        if ordini_list:
            ordini_cards = ''
            for _ord in ordini_list[:20]:
                if not isinstance(_ord, dict): continue
                _n   = len(_ord.get('righe', []))
                _tot = {}
                for _r in _ord.get('righe', []):
                    _v = _r.get('valuta', 'EUR') or 'EUR'
                    _tot[_v] = _tot.get(_v, 0) + float(_r.get('controvalore') or 0)
                _tot_str = ' / '.join(
                    f'{v} {t:,.0f}' for v, t in _tot.items()
                ) if _tot else '—'
                _stato  = _ord.get('stato', 'inviato')
                _s_col  = '#68D391' if _stato == 'inviato' else '#FC8181'
                _s_lbl  = '✓ Inviato' if _stato == 'inviato' else '⚠ Errore'
                _banca  = _ord.get('bank_nome') or _ord.get('bank_email', '—')
                ordini_cards += (
                    f'<div style="background:rgba(255,255,255,.03);border-radius:8px;'
                    f'padding:.75rem 1rem;margin-bottom:.45rem;border:1px solid rgba(255,255,255,.07)">'
                    f'<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.4rem">'
                    f'<div>'
                    f'<div style="font-family:monospace;font-size:.8rem;color:#90cdf4;font-weight:700">'
                    f'{_ord.get("riferimento","—")}</div>'
                    f'<div style="font-size:.76rem;color:#555;margin-top:.2rem">'
                    f'{_ord.get("data","—")} &middot; {_n} titol{"o" if _n==1 else "i"} &middot; {_banca}</div>'
                    f'</div>'
                    f'<div style="display:flex;align-items:center;gap:.8rem">'
                    f'<span style="font-size:.82rem;font-weight:700;color:#F6AD55;font-family:monospace">{_tot_str}</span>'
                    f'<span style="font-size:.76rem;color:{_s_col};font-weight:600">{_s_lbl}</span>'
                    f'</div></div></div>'
                )
            _ordini_storico = (
                f'<div style="margin-top:1.5rem">'
                f'<h3>📋 I miei Ordini</h3>'
                f'{ordini_cards}'
                f'</div>'
            )
        else:
            _ordini_storico = (
                f'<div style="margin-top:1.5rem">'
                f'<h3>📋 I miei Ordini</h3>'
                f'<div style="background:rgba(255,255,255,.03);border-radius:8px;padding:.75rem 1rem;'
                f'font-size:.85rem;color:#555">Nessun ordine ancora inviato.</div>'
                f'</div>'
            )
    else:
        _ordini_storico = ''

    # ─── Sezione unificata "Aggiungi Servizi" ────────────────────
    level_rank = {'NONE': 0, 'BASIC': 1, 'PRO': 2, 'VALUE': 3}
    none_screener = [(a, lbl, ico) for a, lbl, ico in [
        ('azioni', 'Azioni', '📈'), ('etf', 'ETF', '📦'), ('fondi', 'Fondi', '🏦')
    ] if piani[a] == 'NONE']
    ordini_none = piano_ordini == 'NONE'
    has_any_none = bool(none_screener) or ordini_none

    if has_any_none:
        modal_rows_html = ''
        for a, lbl, ico in none_screener:
            modal_rows_html += (
                f'<div style="display:flex;align-items:center;gap:.8rem;padding:.7rem 0;'
                f'border-bottom:1px solid rgba(255,255,255,.06)">'
                f'<input type="checkbox" id="chk-{a}" value="{a}" '
                f'style="width:16px;height:16px;accent-color:#F6AD55;cursor:pointer">'
                f'<label for="chk-{a}" style="flex:1;cursor:pointer;font-size:.9rem">{ico} {lbl}</label>'
                f'<select id="lv-{a}" style="background:#0a0f1e;border:1px solid rgba(255,255,255,.15);'
                f'border-radius:6px;padding:.35rem .6rem;color:#e0e0e0;font-size:.82rem">'
                f'<option value="BASIC">BASIC</option>'
                f'<option value="PRO">PRO</option>'
                f'<option value="VALUE">VALUE</option>'
                f'</select></div>'
            )
        if ordini_none:
            modal_rows_html += (
                f'<div style="display:flex;align-items:center;gap:.8rem;padding:.7rem 0">'
                f'<input type="checkbox" id="chk-ordini" value="ordini" '
                f'style="width:16px;height:16px;accent-color:#F6AD55;cursor:pointer">'
                f'<label for="chk-ordini" style="flex:1;cursor:pointer;font-size:.9rem">📋 Order Builder</label>'
                f'<span style="font-size:.78rem;color:#888;white-space:nowrap">Servizio aggiuntivo</span>'
                f'</div>'
            )
        none_assets_js = ','.join(f"'{a}'" for a, _, _ in none_screener)
        aggiungi_section = f"""
<div style="margin-top:.8rem">
  <button onclick="document.getElementById('modal-svc').style.display='flex'"
          style="background:linear-gradient(135deg,#1a365d,#2b6cb0);color:#fff;border:none;
                 border-radius:8px;padding:.65rem 1.4rem;font-size:.88rem;font-weight:700;cursor:pointer">
    ➕ Aggiungi Servizi
  </button>
</div>
<div id="modal-svc" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;
     background:rgba(0,0,0,.78);z-index:9999;align-items:center;justify-content:center">
  <div style="background:#111827;border:1px solid rgba(246,173,85,.35);border-radius:14px;
              padding:2rem;max-width:420px;width:90%;color:#e0e0e0">
    <h3 style="color:#F6AD55;margin-bottom:1rem;font-size:1rem">Aggiungi Servizi</h3>
    {modal_rows_html}
    <div style="display:flex;gap:.8rem;margin-top:1.2rem">
      <button onclick="confermaAggiuntaSvc()"
              style="flex:1;background:#F6AD55;color:#0a0f1e;border:none;border-radius:8px;
                     padding:.75rem;font-weight:700;cursor:pointer">Conferma</button>
      <button onclick="document.getElementById('modal-svc').style.display='none'"
              style="flex:1;background:transparent;color:#aaa;border:1px solid rgba(255,255,255,.15);
                     border-radius:8px;padding:.75rem;cursor:pointer">Annulla</button>
    </div>
    <div id="err-svc" style="color:#FC8181;font-size:.8rem;margin-top:.6rem;text-align:center"></div>
  </div>
</div>
<script>
function confermaAggiuntaSvc(){{
  document.getElementById('err-svc').textContent='';
  var toAdd=[];
  [{none_assets_js}].forEach(function(a){{
    var chk=document.getElementById('chk-'+a);
    var sel=document.getElementById('lv-'+a);
    if(chk&&chk.checked)toAdd.push({{asset:a,livello:sel?sel.value:'BASIC'}});
  }});
  var chkO=document.getElementById('chk-ordini');
  if(chkO&&chkO.checked)toAdd.push({{asset:'ordini',livello:'BASIC'}});
  if(!toAdd.length){{document.getElementById('err-svc').textContent='Seleziona almeno un servizio.';return;}}
  Promise.all(toAdd.map(function(item){{
    return fetch('/api/aggiungi-piano',{{method:'POST',headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify(item)}}).then(function(r){{return r.json();}});
  }})).then(function(rs){{
    var err=rs.find(function(r){{return !r.ok;}});
    if(err){{document.getElementById('err-svc').textContent=err.msg||'Errore.';}}
    else{{location.reload();}}
  }}).catch(function(){{document.getElementById('err-svc').textContent='Errore di rete.';}});
}}
</script>"""
    else:
        aggiungi_section = ''

    # ─── Sezione Banche Salvate ──────────────────────────────
    _banche_section = (
        '<div style="margin-top:1.5rem">'
        '<h3>&#x1F3E6; Banche Salvate</h3>'
        '<div id="banche-list" style="margin-bottom:.8rem"></div>'
        '<div style="background:rgba(255,255,255,.03);border-radius:10px;padding:1rem 1.2rem">'
        '<div style="font-size:.82rem;color:#F6AD55;font-weight:600;margin-bottom:.8rem">Aggiungi profilo banca</div>'
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:.6rem;margin-bottom:.6rem">'
        '<div><label style="font-size:.75rem;color:#888;display:block;margin-bottom:.25rem">Nome Banca / Intermediario</label>'
        '<input id="nb-banca" type="text" placeholder="es. Banca Sella, Fineco..." style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.5rem .7rem;color:#e0e0e0;font-size:.85rem"></div>'
        '<div><label style="font-size:.75rem;color:#888;display:block;margin-bottom:.25rem">IBAN Conto Cliente</label>'
        '<input id="nb-iban" type="text" placeholder="IT60 X054..." style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.5rem .7rem;color:#e0e0e0;font-size:.85rem;font-family:monospace;text-transform:uppercase" oninput="this.value=this.value.toUpperCase()"></div>'
        '<div><label style="font-size:.75rem;color:#888;display:block;margin-bottom:.25rem">Nome Gestore</label>'
        '<input id="nb-gestore" type="text" placeholder="es. Mario Rossi" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.5rem .7rem;color:#e0e0e0;font-size:.85rem"></div>'
        '<div><label style="font-size:.75rem;color:#888;display:block;margin-bottom:.25rem">Email Gestore</label>'
        '<input id="nb-email" type="email" placeholder="gestore@banca.it" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.5rem .7rem;color:#e0e0e0;font-size:.85rem"></div>'
        '</div>'
        '<div style="display:flex;align-items:center;gap:.6rem">'
        '<button onclick="bancaSalva()" style="background:#2C5282;color:#fff;border:none;border-radius:6px;padding:.5rem 1.2rem;font-size:.83rem;font-weight:600;cursor:pointer">Salva profilo</button>'
        '<span id="nb-msg" style="font-size:.78rem"></span>'
        '</div></div></div>'
        '<script>'
        'function bancaLoad(){'
        '  fetch("/api/banche").then(function(r){return r.json();}).then(function(d){'
        '    bancaRender(d.profili||[]);'
        '  }).catch(function(){});'
        '}'
        'function bancaRender(list){'
        '  var el=document.getElementById("banche-list");'
        '  if(!el)return;'
        '  if(!list.length){el.innerHTML=\'<div style="font-size:.82rem;color:#555;padding:.4rem 0">Nessun profilo salvato</div>\';return;}'
        '  el.innerHTML="";'
        '  list.forEach(function(c){'
        '    var row=document.createElement("div");'
        '    row.style.cssText="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);border-radius:8px;padding:.65rem 1rem;margin-bottom:.4rem;display:flex;align-items:center;gap:.8rem";\n'
        '    var sub=(c.nome_gestore?(c.nome_gestore+(c.email_gestore?" \xb7 "+c.email_gestore:"")):"");\n'
        '    row.innerHTML=\'<div style="flex:1"><div style="font-weight:600;font-size:.88rem;color:#90cdf4">\''
        '      +(c.banca||"—")+"</div>"'
        '      +\'<div style="font-size:.76rem;color:#888;font-family:monospace">\''
        '      +(c.iban||"—")+"</div>"'
        '      +(sub?\'<div style="font-size:.75rem;color:#666">\'+sub+"</div>":"")+'
        '      \'</div>\''
        '      +\'<span onclick="bancaDel(\\\'\'+c.iban+\'\\\')" style="color:#e53e3e;font-size:.8rem;cursor:pointer;padding:.2rem .5rem">&#x2715;</span>\';\n'
        '    el.appendChild(row);'
        '  });'
        '}'
        'function bancaSalva(){'
        '  var banca=document.getElementById("nb-banca").value.trim();'
        '  var iban=document.getElementById("nb-iban").value.trim();'
        '  var gestore=document.getElementById("nb-gestore").value.trim();'
        '  var email=document.getElementById("nb-email").value.trim();'
        '  var msg=document.getElementById("nb-msg");'
        '  if(!iban){msg.style.color="#FC8181";msg.textContent="IBAN obbligatorio";return;}'
        '  fetch("/api/banche/save",{method:"POST",headers:{"Content-Type":"application/json"},'
        '    body:JSON.stringify({banca:banca,iban:iban,nome_gestore:gestore,email_gestore:email})})'
        '  .then(function(r){return r.json();}).then(function(d){'
        '    if(d.ok){'
        '      msg.style.color="#68D391";msg.textContent="Salvato!";'
        '      document.getElementById("nb-banca").value="";'
        '      document.getElementById("nb-iban").value="";'
        '      document.getElementById("nb-gestore").value="";'
        '      document.getElementById("nb-email").value="";'
        '      setTimeout(function(){msg.textContent="";},2500);'
        '      bancaLoad();'
        '    }else{msg.style.color="#FC8181";msg.textContent=d.msg||"Errore";}'
        '  }).catch(function(){msg.style.color="#FC8181";msg.textContent="Errore di rete";});'
        '}'
        'function bancaDel(iban){'
        '  fetch("/api/banche/delete",{method:"POST",headers:{"Content-Type":"application/json"},'
        '    body:JSON.stringify({iban:iban})})'
        '  .then(function(r){return r.json();}).then(function(d){if(d.ok)bancaLoad();})'
        '  .catch(function(){});'
        '}'
        'bancaLoad();'
        '</script>'
    )

    _num_fatt = cliente.get('numero_fattura', '')
    _fattura_btn = (
        f'<a href="/api/mia-fattura" target="_blank"'
        f' style="font-size:.78rem;color:#68D391;text-decoration:none;'
        f'border:1px solid rgba(104,211,145,.25);border-radius:6px;padding:.3rem .75rem;'
        f'transition:color .2s"'
        f' onmouseover="this.style.color=\'#48BB78\'" onmouseout="this.style.color=\'#68D391\'">'
        f'&#x1F9FE; Scarica fattura {_num_fatt}</a>'
    ) if _num_fatt else ''

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Robot Trader 2026 — Area Riservata</title>
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#F6AD55">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Robot Trader">
<link rel="apple-touch-icon" href="/icons/icon-192.png">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0a0f1e;font-family:'Segoe UI',Arial,sans-serif;min-height:100vh;color:#e0e0e0}}
.top{{background:linear-gradient(135deg,#1a2744,#0d1b35);padding:1.2rem 2rem;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid rgba(246,173,85,.2)}}
.brand{{font-size:11px;letter-spacing:3px;color:#F6AD55;text-transform:uppercase}}
.main{{max-width:700px;margin:2.5rem auto;padding:0 1.2rem}}
h2{{font-size:1.3rem;margin-bottom:.4rem}}
.sub{{color:#888;font-size:.9rem;margin-bottom:2rem}}
h3{{font-size:1rem;color:#F6AD55;margin-bottom:1rem;letter-spacing:.5px;text-transform:uppercase}}
.logout{{background:transparent;border:1px solid rgba(255,255,255,.15);color:#aaa;padding:.4rem .9rem;border-radius:6px;font-size:.82rem;cursor:pointer;text-decoration:none}}
.logout:hover{{border-color:#FC8181;color:#FC8181}}
</style>
</head>
<body>
<div class="top">
  <div style="display:flex;align-items:center;gap:1rem">
    <img src="data:image/png;base64,{FUERTE_LOGO_B64}" alt="Fuerte" style="height:36px;display:block">
    <div style="font-size:.85rem;color:rgba(255,255,255,.5)">Area Riservata Investitori</div>
  </div>
  <a href="/api/client-logout" class="logout">Esci</a>
</div>
<div class="main">
  <div id="pwa-banner" style="display:none;background:linear-gradient(135deg,#1a2744,#0d1b35);border:1px solid rgba(246,173,85,.3);border-radius:10px;padding:.9rem 1.2rem;margin-bottom:1.2rem;align-items:center;justify-content:space-between;gap:.8rem;flex-wrap:wrap">
    <div style="display:flex;align-items:center;gap:.75rem">
      <img src="/icons/icon-192.png" style="width:38px;height:38px;border-radius:8px;object-fit:cover;flex-shrink:0">
      <div>
        <div style="font-weight:700;font-size:.9rem;color:#F6AD55">Installa Robot Trader 2026</div>
        <div style="font-size:.75rem;color:#888;margin-top:.1rem">Accedi ai tuoi report dalla schermata home</div>
      </div>
    </div>
    <div style="display:flex;gap:.5rem;flex-shrink:0;margin-left:auto">
      <button id="pwa-install-btn" style="background:#F6AD55;color:#0a0f1e;border:none;border-radius:7px;padding:.5rem 1rem;font-weight:700;font-size:.82rem;cursor:pointer">&#x2B07; Installa</button>
      <button id="pwa-dismiss-btn" style="background:transparent;color:#666;border:1px solid rgba(255,255,255,.1);border-radius:7px;padding:.5rem .7rem;font-size:.82rem;cursor:pointer">✕</button>
    </div>
  </div>
  <h2>Benvenuto, {nome}</h2>
  <div class="sub">I tuoi report sono aggiornati ogni lunedì mattina</div>
  {trial_badge}
  <h3>I tuoi screener</h3>
  {rows}
  <div style="margin-bottom:.6rem">{_profilo_card}{_idee_card}{_settori_card}</div>
  <div style="margin:1.2rem 0">
    {_ordine_block}
  </div>
  {_ordini_storico}
  {_banche_section}
  {aggiungi_section}
  <div style="display:flex;justify-content:flex-end;align-items:center;gap:.8rem;margin-top:1.2rem;margin-bottom:.5rem">
    {_fattura_btn}
    <a href="/cambia-password?v=1" style="font-size:.78rem;color:#888;text-decoration:none;border:1px solid rgba(255,255,255,.1);border-radius:6px;padding:.3rem .75rem;transition:color .2s" onmouseover="this.style.color='#F6AD55'" onmouseout="this.style.color='#888'">&#x1F511; Modifica password</a>
  </div>
  <div style="background:rgba(246,173,85,.04);border:1px solid rgba(246,173,85,.1);border-radius:10px;padding:1rem 1.2rem;font-size:.75rem;color:#666;line-height:1.7;margin-top:1.5rem;margin-bottom:1rem">
    <div style="font-size:.7rem;color:#888;text-transform:uppercase;letter-spacing:.8px;margin-bottom:.4rem;font-weight:600">⚠ SaaS · Non Consulenza Finanziaria</div>
    I report forniti da Fuerte Screener sono elaborati automaticamente a scopo esclusivamente informativo e <strong style="color:#aaa">non costituiscono consulenza finanziaria</strong>, raccomandazione di investimento o sollecitazione. Gli investimenti comportano rischi, inclusa la possibile perdita del capitale. Prima di qualsiasi decisione, consulta un consulente finanziario abilitato.
  </div>
  <div style="padding-top:1.2rem;border-top:1px solid rgba(255,255,255,.06);font-size:.72rem;color:#444;text-align:center;line-height:1.9">
    <strong style="color:#667">Fuerte Venture Capital SL</strong> &middot; CIF B23881691<br>
    Calle Puipana 3, 35640 Villaverde, Las Palmas, España<br>
    <a href="mailto:info@fuerteventurecapital.com" style="color:#F6AD55">info@fuerteventurecapital.com</a>
    &nbsp;&middot;&nbsp;
    <a href="https://www.fuerteventurecapital.com" style="color:#F6AD55">www.fuerteventurecapital.com</a><br>
    <span style="color:#3a3a3a;font-size:.68rem">I tuoi dati sono trattati ai sensi del Reg. UE 2016/679 (GDPR) &middot; Diritto di accesso/cancellazione: <a href="mailto:info@fuerteventurecapital.com" style="color:#555;text-decoration:none">info@fuerteventurecapital.com</a></span><br>
    <span style="color:#333;font-size:.65rem">© 2026 FUERTE VENTURE CAPITAL SL. ALL RIGHTS RESERVED.</span>
  </div>
</div>
<div id="modal-piano" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.75);z-index:9999;align-items:center;justify-content:center">
  <div style="background:#111827;border:1px solid rgba(246,173,85,.35);border-radius:14px;padding:2rem;max-width:380px;width:90%;color:#e0e0e0">
    <h3 id="modal-title" style="color:#F6AD55;margin-bottom:.6rem;font-size:1rem">Aggiungi Piano</h3>
    <p id="modal-asset-label" style="color:#aaa;font-size:.88rem;margin-bottom:.4rem"></p>
    <p id="modal-current-label" style="color:#666;font-size:.78rem;margin-bottom:1rem"></p>
    <label style="font-size:.82rem;color:#888;display:block;margin-bottom:.4rem">Seleziona livello</label>
    <select id="modal-livello" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.15);border-radius:8px;padding:.7rem;color:#e0e0e0;font-size:.95rem;margin-bottom:1.2rem"></select>
    <div style="display:flex;gap:.8rem">
      <button onclick="confermaAggiungiPiano()" style="flex:1;background:#F6AD55;color:#0a0f1e;border:none;border-radius:8px;padding:.75rem;font-weight:700;cursor:pointer">Conferma</button>
      <button onclick="document.getElementById('modal-piano').style.display='none'" style="flex:1;background:transparent;color:#aaa;border:1px solid rgba(255,255,255,.15);border-radius:8px;padding:.75rem;cursor:pointer">Annulla</button>
    </div>
    <div id="modal-err" style="color:#FC8181;font-size:.8rem;margin-top:.6rem;text-align:center"></div>
  </div>
</div>
<script>
var _mAsset='';
var _livelli=['BASIC','PRO','VALUE'];
var _livelloLabels={{'BASIC':'BASIC — Accesso base','PRO':'PRO — Analisi avanzate','VALUE':'VALUE — Suite completa'}};
function apriModalPiano(asset,label,current){{
  _mAsset=asset;
  var isAdd=(current==='NONE');
  document.getElementById('modal-title').textContent=isAdd?'Aggiungi Piano':'Upgrade Piano';
  document.getElementById('modal-asset-label').textContent='Servizio: '+label;
  document.getElementById('modal-current-label').textContent=isAdd?'':'Piano attuale: '+current;
  document.getElementById('modal-err').textContent='';
  var sel=document.getElementById('modal-livello');
  sel.innerHTML='';
  var startIdx=isAdd?0:_livelli.indexOf(current)+1;
  for(var i=startIdx;i<_livelli.length;i++){{
    var o=document.createElement('option');
    o.value=_livelli[i]; o.textContent=_livelloLabels[_livelli[i]];
    sel.appendChild(o);
  }}
  document.getElementById('modal-piano').style.display='flex';
}}
function confermaAggiungiPiano(){{
  var livello=document.getElementById('modal-livello').value;
  document.getElementById('modal-err').textContent='';
  fetch('/api/aggiungi-piano',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{asset:_mAsset,livello:livello}})}})
  .then(function(r){{return r.json();}}).then(function(res){{
    if(res.ok){{ location.reload(); }}
    else{{ document.getElementById('modal-err').textContent=res.msg||'Errore.'; }}
  }}).catch(function(){{ document.getElementById('modal-err').textContent='Errore di rete.'; }});
}}
</script>
<script>
if('serviceWorker' in navigator){{navigator.serviceWorker.register('/sw.js',{{scope:'/'}});}}
var _dp=null;
window.addEventListener('beforeinstallprompt',function(e){{
  e.preventDefault();_dp=e;
  if(!sessionStorage.getItem('pwa-off')){{document.getElementById('pwa-banner').style.display='flex';}}
}});
document.getElementById('pwa-install-btn').addEventListener('click',function(){{
  if(!_dp)return;
  _dp.prompt();
  _dp.userChoice.then(function(){{_dp=null;document.getElementById('pwa-banner').style.display='none';}});
}});
document.getElementById('pwa-dismiss-btn').addEventListener('click',function(){{
  sessionStorage.setItem('pwa-off','1');
  document.getElementById('pwa-banner').style.display='none';
}});
window.addEventListener('appinstalled',function(){{document.getElementById('pwa-banner').style.display='none';}});
</script>
</body></html>"""


# ─── PRICES CACHE — letto dal dashboard dopo le esecuzioni ──
def load_prices_cache() -> dict:
    """Legge prices_cache.json salvato dagli screener. Ritorna {azioni:{}, etf:{}, fondi:{}, *_at}"""
    cache_path = os.path.join(BASE_DIR, "prices_cache.json")
    if not os.path.exists(cache_path):
        return {}
    try:
        with open(cache_path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


# ─── DATABASE — elenco universo ticker ──────────────────────
def get_database_data() -> dict:
    from ticker_lists_5000 import (
        # azioni
        USA_SP500, USA_MIDCAP, USA_RUSSELL2000, USA_SMALLCAP_SP600,
        UK_FTSE100, UK_FTSE250,
        FRANCE_CAC40, GERMANY_DAX, ITALY_MIB, SPAIN_IBEX,
        SWISS_SMI, NETHERLANDS_AEX, SWEDEN_OMXS, NORWAY_OBX,
        DENMARK_OMXC, FINLAND_OMXH, BELGIUM_BEL20,
        JAPAN_NIKKEI, HK_HANGSENG,
        AUSTRALIA_ASX, CANADA_TSX, GERMANY_MDAX, FRANCE_MIDCAP,
        AUSTRIA_ATX, PORTUGAL_PSI, KOREA_KOSPI, BRAZIL_IBOVESPA,
        CANADA_TSX_EXT, AUSTRALIA_ASX_EXT, JAPAN_TOPIX_EXT,
        INDIA_NIFTY, TAIWAN_TWSE,
        # etf US
        ETF_US_BROAD, ETF_US_SECTOR, ETF_US_BONDS, ETF_US_INTL,
        ETF_US_FACTOR, ETF_US_REAL_COMM,
        ETF_US_THEMATIC, ETF_US_DIVIDEND, ETF_US_INCOME, ETF_US_ESG,
        ETF_US_BONDS_CORP, ETF_US_BONDS_HY, ETF_US_BONDS_GOVT,
        ETF_US_COUNTRY, ETF_US_MULTI_FACTOR, ETF_US_REAL_EXTRA,
        # etf Europa borsa
        ETF_EUROPE_L, ETF_EUROPE_DE, ETF_EUROPE_AS,
        ETF_EUROPE_PA, ETF_EUROPE_MI, ETF_EUROPE_SW,
        ETF_EUROPE_L_EXT, ETF_EUROPE_DE_EXT, ETF_EUROPE_AS_EXT,
        ETF_EUROPE_PA_EXT, ETF_EUROPE_MI_EXT,
        # etf Europa emittente
        ETF_EUROPE_INVESCO, ETF_EUROPE_VANECK, ETF_EUROPE_FIDELITY_UCITS,
        ETF_EUROPE_JPMORGAN, ETF_EUROPE_FRANKLIN, ETF_EUROPE_WISDOMTREE_EQ,
        ETF_EUROPE_AMUNDI_EXT, ETF_EUROPE_XTRACKERS_EXT,
        ETF_EUROPE_ISHARES_UCITS_EXT, ETF_EUROPE_GLOBALX_UCITS,
        ETF_EUROPE_SPDR_UCITS_EXT, ETF_EUROPE_ACC_CORE,
        # fondi US originali
        FONDI_VANGUARD, FONDI_FIDELITY, FONDI_TROWE, FONDI_AMERICAN,
        FONDI_SCHWAB, FONDI_PIMCO, FONDI_DODGECOX, FONDI_DFA,
        FONDI_BOUTIQUE, FONDI_FRANKLIN, FONDI_BLACKROCK_MF, FONDI_INVESCO_MF,
        FONDI_MFS, FONDI_PUTNAM, FONDI_COLUMBIA, FONDI_JPMORGAN_MF,
        FONDI_GOLDMAN_MF, FONDI_LORDABBETT, FONDI_NEUBERGER, FONDI_NUVEEN,
        FONDI_TIAA, FONDI_HARBOR, FONDI_EATON_VANCE, FONDI_HARTFORD,
        FONDI_JOHN_HANCOCK, FONDI_ARTISAN, FONDI_PARNASSUS, FONDI_WASATCH,
        FONDI_ROYCE, FONDI_THORNBURG, FONDI_FIRST_EAGLE, FONDI_MANNING,
        FONDI_ARIEL, FONDI_BROWN, FONDI_MERIDIAN, FONDI_BAIRD,
        # fondi US aggiuntivi
        FONDI_BARON, FONDI_MATTHEWS, FONDI_PRIMECAP, FONDI_WEITZ,
        FONDI_LOOMIS, FONDI_LOOMIS_EXT, FONDI_THIRD_AVENUE, FONDI_CHAMPLAIN,
        FONDI_AMERICAN_CENTURY, FONDI_JANUS, FONDI_CALAMOS, FONDI_PRINCIPAL,
        FONDI_COHEN_STEERS, FONDI_TCW, FONDI_LEGG_MASON, FONDI_NATIXIS,
        FONDI_VIRTUS, FONDI_GABELLI_EXT, FONDI_CALVERT, FONDI_HENNESSY,
        FONDI_AQR, FONDI_FIDELITY_SELECT, FONDI_TROWE_EXT, FONDI_FEDERATED,
        FONDI_COLUMBIA_EXT, FONDI_DELAWARE, FONDI_INVESCO_EXT, FONDI_WELLS_FARGO,
        FONDI_AMERICAN_BEACON, FONDI_VICTORY, FONDI_FRANKLIN_EXT,
        FONDI_VANGUARD_EXT, FONDI_SCHWAB_EXT, FONDI_NATIONWIDE, FONDI_SENTINEL,
        FONDI_MESIROW, FONDI_PERRITT,
        # fondi US espansione 2026-06-20
        FONDI_AB, FONDI_PGIM, FONDI_MORGAN_STANLEY, FONDI_STATE_STREET_MF,
        FONDI_WILLIAM_BLAIR, FONDI_CAUSEWAY, FONDI_HOTCHKIS, FONDI_ALGER,
        FONDI_TRANSAMERICA,
    )

    def _build(groups):
        seen, out = set(), []
        for label, lst in groups:
            for t in lst:
                if t not in seen:
                    seen.add(t)
                    out.append({"ticker": t, "gruppo": label})
        return out

    azioni = _build([
        ("S&P 500",              USA_SP500),
        ("Russell / MidCap",     USA_MIDCAP),
        ("Russell 2000",         USA_RUSSELL2000),
        ("S&P 600 SmallCap",     USA_SMALLCAP_SP600),
        ("FTSE 100",             UK_FTSE100),
        ("FTSE 250",             UK_FTSE250),
        ("CAC 40",               FRANCE_CAC40),
        ("DAX",                  GERMANY_DAX),
        ("FTSE MIB",             ITALY_MIB),
        ("IBEX 35",              SPAIN_IBEX),
        ("SMI",                  SWISS_SMI),
        ("AEX",                  NETHERLANDS_AEX),
        ("OMX Stockholm",        SWEDEN_OMXS),
        ("OBX Norway",           NORWAY_OBX),
        ("OMX Copenhagen",       DENMARK_OMXC),
        ("OMX Helsinki",         FINLAND_OMXH),
        ("BEL 20",               BELGIUM_BEL20),
        ("Nikkei 225",           JAPAN_NIKKEI),
        ("Hang Seng",            HK_HANGSENG),
        ("ASX 200",              AUSTRALIA_ASX),
        ("TSX 60",               CANADA_TSX),
        ("MDAX",                 GERMANY_MDAX),
        ("CAC Mid",              FRANCE_MIDCAP),
        ("ATX",                  AUSTRIA_ATX),
        ("PSI 20",               PORTUGAL_PSI),
        ("KOSPI",                KOREA_KOSPI),
        ("Ibovespa",             BRAZIL_IBOVESPA),
        ("TSX Extended",         CANADA_TSX_EXT),
        ("ASX Extended",         AUSTRALIA_ASX_EXT),
        ("TOPIX",                JAPAN_TOPIX_EXT),
        ("NIFTY 500",            INDIA_NIFTY),
        ("TWSE",                 TAIWAN_TWSE),
    ])

    etf = _build([
        # US core
        ("US Broad Market",          ETF_US_BROAD),
        ("US Settoriali",            ETF_US_SECTOR),
        ("US Obbligazionari",        ETF_US_BONDS),
        ("US Internazionali",        ETF_US_INTL),
        ("US Factor / Smart Beta",   ETF_US_FACTOR),
        ("US Real / Commodities",    ETF_US_REAL_COMM),
        # US extra
        ("US Tematici",              ETF_US_THEMATIC),
        ("US Dividendi",             ETF_US_DIVIDEND),
        ("US Income / CEF",          ETF_US_INCOME),
        ("US ESG",                   ETF_US_ESG),
        ("US Obblig. Corporate",     ETF_US_BONDS_CORP),
        ("US Obblig. High Yield",    ETF_US_BONDS_HY),
        ("US Obblig. Governativi",   ETF_US_BONDS_GOVT),
        ("US Country / Single",      ETF_US_COUNTRY),
        ("US Multi-Factor",          ETF_US_MULTI_FACTOR),
        ("US Real Estate Extra",     ETF_US_REAL_EXTRA),
        # Europa per borsa
        ("Europa .L (Londra)",       ETF_EUROPE_L),
        ("Europa .DE (Germania)",    ETF_EUROPE_DE),
        ("Europa .AS (Amsterdam)",   ETF_EUROPE_AS),
        ("Europa .PA (Parigi)",      ETF_EUROPE_PA),
        ("Europa .MI (Milano)",      ETF_EUROPE_MI),
        ("Europa .SW (Zurigo)",      ETF_EUROPE_SW),
        ("Europa .L Extra",          ETF_EUROPE_L_EXT),
        ("Europa .DE Extra",         ETF_EUROPE_DE_EXT),
        ("Europa .AS Extra",         ETF_EUROPE_AS_EXT),
        ("Europa .PA Extra",         ETF_EUROPE_PA_EXT),
        ("Europa .MI Extra",         ETF_EUROPE_MI_EXT),
        # Europa per emittente
        ("Europa Invesco UCITS",     ETF_EUROPE_INVESCO),
        ("Europa VanEck UCITS",      ETF_EUROPE_VANECK),
        ("Europa Fidelity UCITS",    ETF_EUROPE_FIDELITY_UCITS),
        ("Europa JPMorgan UCITS",    ETF_EUROPE_JPMORGAN),
        ("Europa Franklin UCITS",    ETF_EUROPE_FRANKLIN),
        ("Europa WisdomTree",        ETF_EUROPE_WISDOMTREE_EQ),
        ("Europa Amundi Extra",      ETF_EUROPE_AMUNDI_EXT),
        ("Europa Xtrackers Extra",   ETF_EUROPE_XTRACKERS_EXT),
        ("Europa iShares UCITS Ext", ETF_EUROPE_ISHARES_UCITS_EXT),
        ("Europa Global X UCITS",    ETF_EUROPE_GLOBALX_UCITS),
        ("Europa SPDR UCITS",        ETF_EUROPE_SPDR_UCITS_EXT),
        ("Europa ACC Core",          ETF_EUROPE_ACC_CORE),
    ])

    fondi = _build([
        # famiglie originali
        ("Vanguard",              FONDI_VANGUARD),
        ("Fidelity",              FONDI_FIDELITY),
        ("T.Rowe Price",          FONDI_TROWE),
        ("American Funds",        FONDI_AMERICAN),
        ("Schwab",                FONDI_SCHWAB),
        ("PIMCO",                 FONDI_PIMCO),
        ("Dodge & Cox",           FONDI_DODGECOX),
        ("DFA",                   FONDI_DFA),
        ("Multi-Famiglia",        FONDI_BOUTIQUE),
        ("Franklin Templeton",    FONDI_FRANKLIN),
        ("BlackRock MF",          FONDI_BLACKROCK_MF),
        ("Invesco MF",            FONDI_INVESCO_MF),
        ("MFS",                   FONDI_MFS),
        ("Putnam",                FONDI_PUTNAM),
        ("Columbia",              FONDI_COLUMBIA),
        ("JPMorgan MF",           FONDI_JPMORGAN_MF),
        ("Goldman Sachs MF",      FONDI_GOLDMAN_MF),
        ("Lord Abbett",           FONDI_LORDABBETT),
        ("Neuberger Berman",      FONDI_NEUBERGER),
        ("Nuveen",                FONDI_NUVEEN),
        ("TIAA-CREF",             FONDI_TIAA),
        ("Harbor",                FONDI_HARBOR),
        ("Eaton Vance/Calvert",   FONDI_EATON_VANCE),
        ("Hartford",              FONDI_HARTFORD),
        ("John Hancock",          FONDI_JOHN_HANCOCK),
        ("Artisan",               FONDI_ARTISAN),
        ("Parnassus",             FONDI_PARNASSUS),
        ("Wasatch",               FONDI_WASATCH),
        ("Royce",                 FONDI_ROYCE),
        ("Thornburg",             FONDI_THORNBURG),
        ("First Eagle",           FONDI_FIRST_EAGLE),
        ("Manning & Napier",      FONDI_MANNING),
        ("Ariel",                 FONDI_ARIEL),
        ("Brown Advisory",        FONDI_BROWN),
        ("Meridian",              FONDI_MERIDIAN),
        ("Baird",                 FONDI_BAIRD),
        # famiglie aggiuntive
        ("Baron",                 FONDI_BARON),
        ("Matthews",              FONDI_MATTHEWS),
        ("Primecap",              FONDI_PRIMECAP),
        ("Weitz",                 FONDI_WEITZ),
        ("Loomis Sayles",         FONDI_LOOMIS),
        ("Loomis Sayles",         FONDI_LOOMIS_EXT),
        ("Third Avenue",          FONDI_THIRD_AVENUE),
        ("Champlain",             FONDI_CHAMPLAIN),
        ("American Century",      FONDI_AMERICAN_CENTURY),
        ("Janus Henderson",       FONDI_JANUS),
        ("Calamos",               FONDI_CALAMOS),
        ("Principal",             FONDI_PRINCIPAL),
        ("Cohen & Steers",        FONDI_COHEN_STEERS),
        ("TCW",                   FONDI_TCW),
        ("Legg Mason",            FONDI_LEGG_MASON),
        ("Natixis",               FONDI_NATIXIS),
        ("Virtus",                FONDI_VIRTUS),
        ("Gabelli",               FONDI_GABELLI_EXT),
        ("Calvert",               FONDI_CALVERT),
        ("Hennessy",              FONDI_HENNESSY),
        ("AQR Capital",           FONDI_AQR),
        ("Fidelity Select",       FONDI_FIDELITY_SELECT),
        ("T.Rowe Price",          FONDI_TROWE_EXT),
        ("Federated Hermes",      FONDI_FEDERATED),
        ("Columbia",              FONDI_COLUMBIA_EXT),
        ("Delaware / Macquarie",  FONDI_DELAWARE),
        ("Invesco MF",            FONDI_INVESCO_EXT),
        ("Wells Fargo/Allspring", FONDI_WELLS_FARGO),
        ("American Beacon",       FONDI_AMERICAN_BEACON),
        ("Victory Capital",       FONDI_VICTORY),
        ("Franklin Templeton",    FONDI_FRANKLIN_EXT),
        ("Vanguard",              FONDI_VANGUARD_EXT),
        ("Schwab",                FONDI_SCHWAB_EXT),
        ("Nationwide",            FONDI_NATIONWIDE),
        ("Sentinel",              FONDI_SENTINEL),
        ("Mesirow",               FONDI_MESIROW),
        ("Perritt",               FONDI_PERRITT),
        # espansione 2026-06-20
        ("AB (AllianceBernstein)",FONDI_AB),
        ("PGIM",                  FONDI_PGIM),
        ("Morgan Stanley MF",     FONDI_MORGAN_STANLEY),
        ("State Street MF",       FONDI_STATE_STREET_MF),
        ("William Blair",         FONDI_WILLIAM_BLAIR),
        ("Causeway",              FONDI_CAUSEWAY),
        ("Hotchkis & Wiley",      FONDI_HOTCHKIS),
        ("Alger",                 FONDI_ALGER),
        ("Transamerica",          FONDI_TRANSAMERICA),
    ])

    # ── ETF UCITS da JustETF cache ────────────────────────────────────
    import os as _os, json as _json
    _justetf_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'etf_universe_cache.json')
    if _os.path.exists(_justetf_path):
        try:
            with open(_justetf_path, encoding='utf-8') as _jf:
                _ju = _json.load(_jf)
            _etf_seen = {row['ticker'] for row in etf}

            def _etf_issuer(_name):
                if not _name: return 'ETF UCITS Altro'
                _known = ['iShares','Amundi','Xtrackers','Vanguard','SPDR','WisdomTree',
                          'Invesco','Lyxor','Franklin','VanEck','Fidelity','HSBC','UBS',
                          'JPMorgan','BlackRock','BNP Paribas','DWS','Pictet','Ossiam',
                          'HANetf','First Trust','Global X','Flossbach','Deka',
                          'Dimensional','PIMCO','Nuveen','AXA','State Street']
                _nl = _name.lower()
                for _iss in _known:
                    if _iss.lower() in _nl:
                        return 'UCITS ' + _iss
                _w = _name.split()
                return 'UCITS ' + (_w[0] if _w else 'Altro')

            for _isin, _entry in _ju.items():
                if _entry.get('preferred_ticker'):
                    _tk = _entry['preferred_ticker']
                elif _entry.get('all_tickers'):
                    _tk = _entry['all_tickers'][0]
                else:
                    _tk = _isin  # ISIN puro, nessun ticker YF
                if _tk not in _etf_seen:
                    _etf_seen.add(_tk)
                    etf.append({'ticker': _tk, 'gruppo': _etf_issuer(_entry.get('name', ''))})
        except Exception:
            pass

    # ── Fondi EU da cache ─────────────────────────────────────────────
    _fondi_eu_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'fondi_eu_universe_cache.json')
    if _os.path.exists(_fondi_eu_path):
        try:
            with open(_fondi_eu_path, encoding='utf-8') as _ff:
                _feu = _json.load(_ff)
            _fondi_seen = {row['ticker'] for row in fondi}

            def _fondo_eu_gruppo(_ename):
                if not _ename: return 'Fondi EU'
                _mgrs = ['Carmignac','Pictet','Amundi','DWS','Allianz','Fidelity',
                         'BlackRock','Schroders','PIMCO','Robeco','Nordea','Comgest',
                         'Oddo','Natixis','AXA','BNP','Candriam','Flossbach',
                         'Franklin','GAM','Invesco','JPMorgan','MFS','Neuberger',
                         'Templeton','Union Investment','Xtrackers','Threadneedle',
                         'Aberdeen','M&G','Henderson','Baillie Gifford','Lazard']
                _nl = _ename.lower()
                for _m in _mgrs:
                    if _m.lower() in _nl:
                        return 'EU ' + _m
                return 'EU ' + (_ename.split()[0] if _ename else 'Altro')

            for _isin, _entry in _feu.items():
                if _entry.get('error'):
                    _tk = _isin  # ISIN puro, nessun ticker YF
                else:
                    _tk = _entry.get('yahoo_ticker', _isin)
                _ename = _entry.get('name', '')
                if _tk not in _fondi_seen:
                    _fondi_seen.add(_tk)
                    fondi.append({'ticker': _tk, 'gruppo': _fondo_eu_gruppo(_ename)})
        except Exception:
            pass

    return {
        "azioni": azioni,
        "etf":    etf,
        "fondi":  fondi,
        "totali": {"azioni": len(azioni), "etf": len(etf), "fondi": len(fondi)},
    }


# ─── DATABASE LOOKUP — nome + prezzo live ───────────────────
def get_database_lookup(tickers: list) -> dict:
    import yfinance as yf
    import math as _math
    from concurrent.futures import ThreadPoolExecutor, as_completed as _asc

    import re as _re
    _ISIN_RE = _re.compile(r'^[A-Z]{2}[0-9A-Z]{10}$')
    tickers = [t.strip().upper() for t in tickers if t.strip() and not _ISIN_RE.match(t.strip().upper())][:30]
    if not tickers:
        return {}

    def _safe(v, ndigits=2):
        """Converte float yfinance in numero pulito o None (mai NaN/Inf)."""
        if v is None:
            return None
        try:
            f = round(float(v), ndigits)
            return None if (_math.isnan(f) or _math.isinf(f)) else f
        except (TypeError, ValueError):
            return None

    def _fetch(t):
        try:
            obj    = yf.Ticker(t)
            fi     = obj.fast_info
            info   = obj.info
            name   = info.get('longName') or info.get('shortName') or '—'
            price  = getattr(fi, 'last_price', None) or info.get('currentPrice') or info.get('regularMarketPrice')
            curr   = getattr(fi, 'currency', None) or info.get('currency') or ''
            change_pct = None
            raw = info.get('regularMarketChangePercent')
            if raw is not None:
                change_pct = _safe(raw)
            if change_pct is None:
                prev_close = getattr(fi, 'previous_close', None)
                if price and prev_close:
                    change_pct = _safe((float(price) - float(prev_close)) / float(prev_close) * 100)
            price_clean = _safe(price)
            return t, {
                'name':       name,
                'price':      price_clean if price_clean is not None else '—',
                'currency':   curr,
                'change_pct': change_pct,
            }
        except Exception:
            return t, {'name': '—', 'price': '—', 'currency': '', 'change_pct': None}

    result = {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        fs = {ex.submit(_fetch, t): t for t in tickers}
        for f in _asc(fs, timeout=40):
            try:
                t, data = f.result()
                result[t] = data
            except Exception:
                pass
    return result


# ─── DATABASE VERIFY DEAD TICKERS ───────────────────────────
def verify_dead_tickers(tickers: list) -> dict:
    """Controlla se i ticker sono davvero morti su Yahoo Finance.
    Morto = info dict con <= 2 chiavi (yfinance restituisce quasi nulla).
    Incerto = info normale ma nessun prezzo (problema temporaneo YF).
    """
    import yfinance as yf
    import re as _re
    from concurrent.futures import ThreadPoolExecutor, as_completed as _asc

    _ISIN_RE = _re.compile(r'^[A-Z]{2}[0-9A-Z]{10}$')
    tickers = [t.strip().upper() for t in tickers
               if t.strip() and not _ISIN_RE.match(t.strip().upper())][:100]
    if not tickers:
        return {'dead': [], 'uncertain': []}

    def _check(t):
        try:
            info = yf.Ticker(t).info
            n_keys = len([k for k, v in info.items() if v is not None])
            if n_keys <= 3:
                return t, 'dead'
            has_name  = bool(info.get('longName') or info.get('shortName'))
            has_price = bool(info.get('regularMarketPrice') or info.get('currentPrice'))
            if not has_name and not has_price:
                return t, 'dead'
            return t, 'uncertain'
        except Exception:
            return t, 'uncertain'

    dead, uncertain = [], []
    with ThreadPoolExecutor(max_workers=8) as ex:
        fs = {ex.submit(_check, t): t for t in tickers}
        for f in _asc(fs, timeout=60):
            try:
                t, status = f.result()
                if status == 'dead':
                    dead.append(t)
                else:
                    uncertain.append(t)
            except Exception:
                pass
    return {'dead': sorted(dead), 'uncertain': sorted(uncertain)}


# ─── DATABASE REMOVE TICKER ─────────────────────────────────
def remove_ticker_from_lists(ticker: str) -> dict:
    import re, importlib
    ticker = ticker.strip().upper()
    if not ticker:
        return {"ok": False, "msg": "Ticker vuoto"}
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ticker_lists_5000.py')
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    if f"'{ticker}'" not in content:
        return {"ok": False, "msg": f"{ticker} non trovato nelle liste"}
    original = content
    removed = False
    for pat in [
        r",\s*'" + re.escape(ticker) + r"'",
        r"'" + re.escape(ticker) + r"'\s*,\s*",
        r"'" + re.escape(ticker) + r"'",
    ]:
        new_content, n = re.subn(pat, '', content)
        if n > 0:
            content = new_content
            removed = True
            break
    if not removed:
        return {"ok": False, "msg": f"{ticker} non rimovibile"}
    content = re.sub(r',\s*,', ',', content)
    content = re.sub(r',\s*\]', ']', content)
    content = re.sub(r'\[\s*,', '[', content)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    import ticker_lists_5000 as _tl
    importlib.reload(_tl)
    return {"ok": True, "msg": f"{ticker} rimosso"}


# ─── SOCIAL AUTOMATION HELPERS ──────────────────────────────
def _social_response_page(message: str, success: bool) -> str:
    color  = '#276749' if success else '#742a2a'
    icon   = '✅' if success else '❌'
    return f"""<!DOCTYPE html><html lang="it"><head><meta charset="UTF-8">
<title>Social Automation</title>
<style>
  body{{background:#0F172A;color:#e2e8f0;font-family:Arial,sans-serif;
       display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}
  .box{{background:{color};border-radius:14px;padding:2.5rem 3rem;max-width:520px;text-align:center}}
  h2{{margin:0 0 1rem;font-size:1.4rem}} p{{color:#e2e8f0;font-size:.95rem;line-height:1.6}}
  a{{display:inline-block;margin-top:1.5rem;padding:.7rem 2rem;background:#2C5282;
     color:#fff;border-radius:8px;text-decoration:none;font-weight:700;font-size:.9rem}}
</style></head><body>
<div class="box">
  <h2>{icon} Social Automation</h2>
  <p>{message}</p>
  <a href="/api/social/status">← Stato Draft</a>
  &nbsp;<a href="/">Home</a>
</div></body></html>"""


# ─── CHAT WIDGET ────────────────────────────────────────────
CHAT_WIDGET_HTML = """
<style>
#rt-chat-btn{position:fixed;bottom:24px;right:24px;width:56px;height:56px;border-radius:50%;background:#F6AD55;border:none;cursor:pointer;box-shadow:0 4px 16px rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;z-index:9999;transition:transform .2s}
#rt-chat-btn:hover{transform:scale(1.08)}
#rt-chat-btn svg{width:28px;height:28px;fill:#0a0f1e}
#rt-chat-box{position:fixed;bottom:92px;right:24px;width:340px;max-width:calc(100vw - 32px);background:#ffffff;border:1px solid #e0e0e0;border-radius:16px;box-shadow:0 8px 32px rgba(0,0,0,.18);display:none;flex-direction:column;z-index:9998;overflow:hidden}
#rt-chat-hdr{background:linear-gradient(135deg,#F6AD55,#e09030);padding:14px 16px;display:flex;align-items:center;gap:10px;border-bottom:1px solid #e8c070}
#rt-chat-hdr span{font-size:.75rem;color:#fff;font-weight:700;letter-spacing:.05em;text-shadow:0 1px 2px rgba(0,0,0,.2)}
#rt-chat-hdr small{color:rgba(255,255,255,.8);font-size:.7rem;margin-left:auto}
#rt-chat-msgs{height:300px;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;scroll-behavior:smooth;background:#f8f9fa}
.rt-msg{max-width:85%;padding:9px 13px;border-radius:12px;font-size:.82rem;line-height:1.45;word-break:break-word}
.rt-msg.user{background:#F6AD55;color:#1a1a1a;align-self:flex-end;border-bottom-right-radius:3px}
.rt-msg.bot{background:#ffffff;color:#1a1a1a;align-self:flex-start;border-bottom-left-radius:3px;border:1px solid #e0e0e0}
.rt-msg.bot.typing{color:#888;font-style:italic}
#rt-chat-form{display:flex;gap:8px;padding:12px;border-top:1px solid #e0e0e0;background:#ffffff}
#rt-chat-input{flex:1;background:#f8f9fa;border:1px solid #d0d0d0;border-radius:8px;padding:9px 12px;color:#1a1a1a;font-size:.82rem;outline:none;resize:none}
#rt-chat-input:focus{border-color:#F6AD55}
#rt-chat-send{background:#F6AD55;border:none;border-radius:8px;width:38px;height:38px;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0}
#rt-chat-send svg{width:16px;height:16px;fill:#1a1a1a}
</style>

<button id="rt-chat-btn" onclick="rtToggleChat()" title="VERA — Value & Research Assistant">
  <svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/></svg>
</button>

<div id="rt-chat-box">
  <div id="rt-chat-hdr">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="#fff"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/></svg>
    <span>VERA</span>
    <small>Value &amp; Research Assistant</small>
  </div>
  <div id="rt-chat-msgs">
    <div class="rt-msg bot">Ciao! Sono VERA, la tua Value &amp; Research Assistant di Fuerte Venture Capital. Come posso aiutarti? 👋</div>
  </div>
  <form id="rt-chat-form" onsubmit="rtSend(event)">
    <textarea id="rt-chat-input" rows="1" placeholder="Scrivi un messaggio..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();rtSend(event)}"></textarea>
    <button type="submit" id="rt-chat-send">
      <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
    </button>
  </form>
</div>

<script>
(function(){
  var _sid = sessionStorage.getItem('rt_chat_sid') || '';
  var _busy = false;

  window.rtToggleChat = function(){
    var box = document.getElementById('rt-chat-box');
    var open = box.style.display === 'flex';
    box.style.display = open ? 'none' : 'flex';
    if(!open){ document.getElementById('rt-chat-input').focus(); }
  };

  window.rtSend = function(e){
    if(e) e.preventDefault();
    if(_busy) return;
    var inp = document.getElementById('rt-chat-input');
    var msg = inp.value.trim();
    if(!msg) return;
    inp.value = '';
    inp.style.height = '';
    _appendMsg(msg, 'user');
    var typing = _appendMsg('...', 'bot typing');
    _busy = true;
    fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: msg, session_id: _sid})
    })
    .then(function(r){ return r.json(); })
    .then(function(res){
      typing.remove();
      if(res.ok){
        if(res.session_id) { _sid = res.session_id; sessionStorage.setItem('rt_chat_sid', _sid); }
        _appendMsg(res.reply, 'bot');
      } else {
        _appendMsg(res.error || 'Errore. Riprova.', 'bot');
      }
    })
    .catch(function(){
      typing.remove();
      _appendMsg('Errore di rete. Riprova.', 'bot');
    })
    .finally(function(){ _busy = false; });
  };

  function _appendMsg(text, cls){
    var msgs = document.getElementById('rt-chat-msgs');
    var d = document.createElement('div');
    d.className = 'rt-msg ' + cls;
    d.textContent = text;
    msgs.appendChild(d);
    msgs.scrollTop = msgs.scrollHeight;
    return d;
  }

  document.getElementById('rt-chat-input').addEventListener('input', function(){
    this.style.height = '';
    this.style.height = Math.min(this.scrollHeight, 90) + 'px';
  });
})();
</script>
"""

# ─── CHAT WIDGET ABBONATI ───────────────────────────────────
CHAT_ABB_WIDGET_HTML = """
<style>
#rt-abb-btn{position:fixed;bottom:24px;right:24px;width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,#2b6cb0,#1a4a8a);border:none;cursor:pointer;box-shadow:0 4px 16px rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;z-index:9999;transition:transform .2s}
#rt-abb-btn:hover{transform:scale(1.08)}
#rt-abb-btn svg{width:28px;height:28px;fill:#fff}
#rt-abb-box{position:fixed;bottom:92px;right:24px;width:360px;max-width:calc(100vw - 32px);background:#ffffff;border:1px solid #bee3f8;border-radius:16px;box-shadow:0 8px 32px rgba(0,0,0,.18);display:none;flex-direction:column;z-index:9998;overflow:hidden}
#rt-abb-hdr{background:linear-gradient(135deg,#2b6cb0,#1a4a8a);padding:14px 16px;display:flex;align-items:center;gap:10px;border-bottom:1px solid #2a5a9a}
#rt-abb-hdr span{font-size:.75rem;color:#fff;font-weight:700;letter-spacing:.05em}
#rt-abb-hdr small{color:rgba(255,255,255,.8);font-size:.7rem;margin-left:auto}
#rt-abb-msgs{height:320px;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:10px;scroll-behavior:smooth;background:#f0f7ff}
.rt-abb-msg{max-width:88%;padding:9px 13px;border-radius:12px;font-size:.82rem;line-height:1.45;word-break:break-word}
.rt-abb-msg.user{background:#2b6cb0;color:#fff;align-self:flex-end;border-bottom-right-radius:3px}
.rt-abb-msg.bot{background:#ffffff;color:#1a1a1a;align-self:flex-start;border-bottom-left-radius:3px;border:1px solid #bee3f8}
.rt-abb-msg.bot.typing{color:#888;font-style:italic}
#rt-abb-form{display:flex;gap:8px;padding:12px;border-top:1px solid #bee3f8;background:#ffffff}
#rt-abb-input{flex:1;background:#f0f7ff;border:1px solid #bee3f8;border-radius:8px;padding:9px 12px;color:#1a1a1a;font-size:.82rem;outline:none;resize:none}
#rt-abb-input:focus{border-color:#2b6cb0}
#rt-abb-send{background:linear-gradient(135deg,#2b6cb0,#1a4a8a);border:none;border-radius:8px;width:38px;height:38px;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0}
#rt-abb-send svg{width:16px;height:16px;fill:#fff}
</style>

<button id="rt-abb-btn" onclick="rtAbbToggle()" title="VERA — Report Abbonati">
  <svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14l4-4h12c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 9H7v-2h7v2zm3-4H7V6h10v2z"/></svg>
</button>

<div id="rt-abb-box">
  <div id="rt-abb-hdr">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="#fff"><path d="M19 3H5c-1.1 0-2 .9-2 2v14l4-4h12c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 9H7v-2h7v2zm3-4H7V6h10v2z"/></svg>
    <span>VERA</span>
    <small>Report Abbonati</small>
  </div>
  <div id="rt-abb-msgs">
    <div class="rt-abb-msg bot">Ciao! Sono VERA, la tua assistente personale. Puoi chiedermi informazioni sui tuoi report — ad esempio se un titolo è presente, il suo score, o perché è stato scartato. 📊</div>
  </div>
  <form id="rt-abb-form" onsubmit="rtAbbSend(event)">
    <textarea id="rt-abb-input" rows="1" placeholder="Es: LLY è nel report Azioni PRO?" onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();rtAbbSend(event)}"></textarea>
    <button type="submit" id="rt-abb-send">
      <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
    </button>
  </form>
</div>

<script>
(function(){
  var _sid = sessionStorage.getItem('rt_abb_sid') || '';
  var _busy = false;

  window.rtAbbToggle = function(){
    var box = document.getElementById('rt-abb-box');
    var open = box.style.display === 'flex';
    box.style.display = open ? 'none' : 'flex';
    if(!open){ document.getElementById('rt-abb-input').focus(); }
  };

  window.rtAbbSend = function(e){
    if(e) e.preventDefault();
    if(_busy) return;
    var inp = document.getElementById('rt-abb-input');
    var msg = inp.value.trim();
    if(!msg) return;
    inp.value = '';
    inp.style.height = '';
    _abbMsg(msg, 'user');
    var typing = _abbMsg('...', 'bot typing');
    _busy = true;
    fetch('/api/chat-abbonati', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: msg, session_id: _sid})
    })
    .then(function(r){ return r.json(); })
    .then(function(res){
      typing.remove();
      if(res.ok){
        if(res.session_id){ _sid = res.session_id; sessionStorage.setItem('rt_abb_sid', _sid); }
        _abbMsg(res.reply, 'bot');
      } else {
        _abbMsg(res.error || 'Errore. Riprova.', 'bot');
      }
    })
    .catch(function(){
      typing.remove();
      _abbMsg('Errore di rete. Riprova.', 'bot');
    })
    .finally(function(){ _busy = false; });
  };

  function _abbMsg(text, cls){
    var msgs = document.getElementById('rt-abb-msgs');
    var d = document.createElement('div');
    d.className = 'rt-abb-msg ' + cls;
    d.textContent = text;
    msgs.appendChild(d);
    msgs.scrollTop = msgs.scrollHeight;
    return d;
  }

  document.getElementById('rt-abb-input').addEventListener('input', function(){
    this.style.height = '';
    this.style.height = Math.min(this.scrollHeight, 90) + 'px';
  });
})();
</script>
"""

# ─── HTTP SERVER ────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        p = self.path.split('?')[0]
        # ── Rotte pubbliche (no auth) ──────────────────────────
        if p in ('/', '/index.html'):
            self._html(LANDING_HTML.replace('__LOGO_B64__', FUERTE_LOGO_B64).replace('</html>', CHAT_WIDGET_HTML + '</html>')); return  # root = pagina di vendita
        if p == '/api/servizi':
            self._json(read_servizi()); return
        if p in ('/login', '/login/'):
            self._html(LOGIN_HTML.format(error='')); return
        if p in ('/logout', '/logout/'):
            _do_logout(self); return
        if p in ('/grazie', '/grazie/'):
            self._html(_build_grazie_page()); return
        if p in ('/privacy', '/privacy/'):
            self._html(_build_privacy_page()); return
        if p == '/manifest.json':
            self._raw(json.dumps({
                "name": "Robot Trader 2026",
                "short_name": "Robot Trader",
                "description": "Screener quantitativo — Area Riservata Investitori",
                "start_url": "/area-clienti",
                "scope": "/",
                "display": "standalone",
                "background_color": "#0a0f1e",
                "theme_color": "#F6AD55",
                "lang": "it",
                "version": PWA_VERSION,
                "icons": [
                    {"src": f"/icons/icon-192.png?v={PWA_VERSION}", "sizes": "192x192", "type": "image/png"},
                    {"src": f"/icons/icon-512.png?v={PWA_VERSION}", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}
                ]
            }, ensure_ascii=False).encode(), 'application/manifest+json'); return
        if p == '/sw.js':
            _sw = (f"const CACHE='rt2026-v{PWA_VERSION}';"
                   "self.addEventListener('install',e=>self.skipWaiting());"
                   "self.addEventListener('activate',e=>e.waitUntil("
                   "caches.keys().then(ks=>Promise.all("
                   f"ks.filter(k=>k!=='rt2026-v{PWA_VERSION}').map(k=>caches.delete(k))"
                   ")).then(()=>clients.claim())));"
                   "self.addEventListener('fetch',e=>{"
                   "if(e.request.method!=='GET')return;"
                   "e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)));});")
            self._raw(_sw.encode(), 'application/javascript; charset=utf-8'); return
        if p.startswith('/icons/icon-192.png'):
            import base64 as _b64i
            self._raw(_b64i.b64decode(PWA_ICON_192_B64), 'image/png'); return
        if p.startswith('/icons/icon-512.png'):
            import base64 as _b64i
            self._raw(_b64i.b64decode(PWA_ICON_512_B64), 'image/png'); return
        # ── Rotte cliente ──────────────────────────────────────
        if p in ('/client-login', '/client-login/') or self.path.startswith('/client-login?'):
            import urllib.parse as _up_cl
            _qs_cl   = dict(_up_cl.parse_qsl(self.path.split('?')[1] if '?' in self.path else ''))
            _next_cl = _qs_cl.get('next', '')
            if _next_cl and not (_next_cl.startswith('/') and not _next_cl.startswith('//')):
                _next_cl = ''
            _login_logo = f'<img src="data:image/png;base64,{FUERTE_LOGO_B64}" alt="Fuerte Venture Capital">'
            self._html(CLIENT_LOGIN_HTML.format(logo=_login_logo, error='', next_url=_next_cl)); return
        if p in ('/reset-password', '/reset-password/'):
            import urllib.parse as _up
            _qs = dict(_up.parse_qsl(self.path.split('?')[1] if '?' in self.path else ''))
            _logo = f'<img src="data:image/png;base64,{FUERTE_LOGO_B64}" alt="Fuerte Venture Capital">'
            token = _qs.get('token', '')
            if token:
                if token in RESET_TOKENS and time.time() < RESET_TOKENS[token][1]:
                    self._html(RESET_PWD_HTML.format(logo=_logo, token=token, error='')); return
                else:
                    RESET_TOKENS.pop(token, None)
                    self._html(FORGOT_PWD_HTML.format(logo=_logo, msg='<p class="msg err">Link scaduto o non valido. Richiedine uno nuovo.</p>')); return
            self._html(FORGOT_PWD_HTML.format(logo=_logo, msg='')); return
        if p in ('/api/client-logout', '/client-logout'):
            _do_client_logout(self); return
        if p in ('/area-clienti', '/area-clienti/'):
            if not _is_client_auth(self):
                _redirect(self, '/client-login'); return
            email = CLIENT_SESSIONS.get(_get_client_token(self), '')
            html = _build_area_clienti(email)
            if html: self._html(html.replace('</body></html>', CHAT_ABB_WIDGET_HTML + '</body></html>'))
            else: _redirect(self, '/client-login')
            return
        if p in ('/settori', '/settori/'):
            if not _is_client_auth(self):
                _redirect(self, '/client-login?next=/settori'); return
            tok   = _get_client_token(self)
            email = CLIENT_SESSIONS.get(tok, '')
            db    = read_clienti()
            c     = next((x for grp in db.values() for x in grp
                          if x.get('email','').lower() == email.lower()), None)
            nome  = c.get('nome', email) if c else email
            self._html(_build_settori_clienti(nome)); return
        if p in ('/profilo-investitore', '/profilo-investitore/'):
            if not _is_client_auth(self):
                _redirect(self, '/client-login?next=/profilo-investitore'); return
            tok   = _get_client_token(self)
            email = CLIENT_SESSIONS.get(tok, '')
            db    = read_clienti()
            c     = next((x for grp in db.values() for x in grp
                          if x.get('email','').lower() == email.lower()), None)
            nome  = c.get('nome', email) if c else email
            self._html(_build_profilo_investitore(nome, email, c)); return
        if p in ('/idee', '/idee/'):
            if not _is_client_auth(self):
                _redirect(self, '/client-login?next=/idee'); return
            tok   = _get_client_token(self)
            email = CLIENT_SESSIONS.get(tok, '')
            db    = read_clienti()
            c     = next((x for grp in db.values() for x in grp
                          if x.get('email','').lower() == email.lower()), None)
            nome  = c.get('nome', email) if c else email
            self._html(_build_idee_clienti(nome)); return
        if p in ('/cambia-password', '/cambia-password/'):
            if not _is_client_auth(self):
                _redirect(self, '/client-login'); return
            import urllib.parse as _up
            _qs = dict(_up.parse_qsl(self.path.split('?')[1] if '?' in self.path else ''))
            self._html(_build_cambia_password_page(voluntary=_qs.get('v') == '1')); return
        if p == '/api/ordine/prefill':
            if not _is_client_auth(self):
                self._json([]); return
            tok   = _get_client_token(self)
            email = CLIENT_SESSIONS.get(tok, '')
            db    = read_clienti()
            c     = next((x for grp in db.values() for x in grp
                          if x.get('email','').lower() == email.lower()), None)
            if not c:
                self._json([]); return
            risultato = []
            for tipo in ('azioni', 'etf', 'fondi'):
                td = get_table_data(tipo)
                for row in td.get('rows', [])[:5]:
                    ticker = str(row.get('Ticker', '')).strip()
                    if not ticker or ticker.lower() == 'nan':
                        continue
                    nome    = str(row.get('Nome', '')).strip()
                    mercato = str(row.get('Mercato', '')).strip() if row.get('Mercato') else ''
                    valuta  = str(row.get('Valuta', '')).strip() if row.get('Valuta') else ''
                    risultato.append({'ticker': ticker, 'nome': nome,
                                      'mercato': mercato, 'valuta': valuta, 'tipo': tipo})
            self._json(risultato); return
        # ── Titoli da report per picker ordine ────────────────
        if p == '/api/ordine/report-stocks':
            if not _is_client_auth(self):
                self._json([]); return
            import urllib.parse as _up_rs
            _qs_rs   = dict(_up_rs.parse_qsl(self.path.split('?')[1] if '?' in self.path else ''))
            _tipo_rs = _qs_rs.get('tipo', '').lower()
            if _tipo_rs not in ('azioni', 'etf', 'fondi'):
                self._json([]); return
            _tok_rs  = _get_client_token(self)
            _em_rs   = CLIENT_SESSIONS.get(_tok_rs, '')
            _db_rs   = read_clienti()
            _c_rs    = next((x for grp in _db_rs.values() for x in grp
                             if x.get('email','').lower() == _em_rs.lower()), None)
            if not _c_rs:
                self._json([]); return
            _piano_rs = _c_rs.get(f'piano_{_tipo_rs}', 'NONE')
            if _piano_rs == 'NONE':
                self._json([]); return
            _fpath_rs = _latest_plan(_tipo_rs, _piano_rs)
            if not _fpath_rs:
                self._json([]); return
            _result_rs = []
            try:
                _xls_rs = pd.ExcelFile(_fpath_rs)
                _df_rs  = None
                for _sn_rs in _xls_rs.sheet_names:
                    if 'selezion' in _sn_rs.lower():
                        _df_rs = pd.read_excel(_fpath_rs, sheet_name=_sn_rs); break
                if _df_rs is None:
                    for _sn_rs in _xls_rs.sheet_names:
                        if 'top' in _sn_rs.lower():
                            _df_rs = pd.read_excel(_fpath_rs, sheet_name=_sn_rs); break
                if _df_rs is not None:
                    for _, _r_rs in _df_rs.iterrows():
                        _tk_rs = str(_r_rs.get('Ticker','') or '').strip()
                        if not _tk_rs or _tk_rs.lower() == 'nan' or ' ' in _tk_rs: continue
                        _nm_rs = str(_r_rs.get('Nome','') or '').strip()
                        _mk_rs = str(_r_rs.get('Mercato','') or _r_rs.get('Categoria','') or '').strip()
                        _vl_rs = str(_r_rs.get('Valuta','') or '').strip()
                        if _nm_rs.lower() == 'nan': _nm_rs = _tk_rs
                        if _mk_rs.lower() == 'nan': _mk_rs = ''
                        if _vl_rs.lower() == 'nan': _vl_rs = ''
                        _result_rs.append({'ticker': _tk_rs, 'nome': _nm_rs,
                                           'mercato': _mk_rs, 'valuta': _vl_rs, 'tipo': _tipo_rs})
            except Exception:
                pass
            self._json(_result_rs); return
        if p in ('/ordine-bancario', '/ordine-bancario/'):
            if not _is_client_auth(self):
                _redirect(self, '/client-login'); return
            import urllib.parse as _up
            _qs   = dict(_up.parse_qsl(self.path.split('?')[1] if '?' in self.path else ''))
            tipo  = _qs.get('tipo', '').lower()
            if tipo not in ('azioni', 'etf', 'fondi'):
                tipo = ''
            tok   = _get_client_token(self)
            email = CLIENT_SESSIONS.get(tok, '')
            db    = read_clienti()
            c     = next((x for grp in db.values() for x in grp
                          if x.get('email','').lower() == email.lower()), None)
            piano_ord = c.get('piano_ordini', 'NONE') if c else 'NONE'
            if piano_ord == 'NONE':
                self._html('''<!DOCTYPE html><html lang="it"><head><meta charset="UTF-8">
<title>Accesso non attivo</title>
<style>body{background:#0a0f1e;color:#e2e8f0;font-family:Arial,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
.box{background:#131929;border:1px solid rgba(246,173,85,.3);border-radius:14px;padding:2.5rem 3rem;max-width:480px;text-align:center}
h2{color:#F6AD55;margin-bottom:.8rem}p{color:#a0aec0;font-size:.95rem;line-height:1.6}
a{color:#63b3ed;text-decoration:none}.btn{display:inline-block;margin-top:1.5rem;padding:.7rem 2rem;background:linear-gradient(135deg,#2b6cb0,#1a365d);color:#fff;border-radius:8px;font-weight:700;font-size:.95rem}</style>
</head><body><div class="box">
<h2>Piano Ordini non attivo</h2>
<p>Il servizio <strong>Order Builder</strong> richiede un piano Ordini attivo.<br>
Contatta il supporto per attivare il tuo piano.</p>
<a href="/area-clienti" class="btn">← Torna all\'Area Clienti</a>
</div></body></html>'''); return
            nome = (c.get('nome','') + ' ' + c.get('cognome','')).strip() if c else email
            df   = c.get('dati_fiscali', {}) if c else {}
            prefill_rows = []
            if tipo and c:
                _pa = c.get(f'piano_{tipo}', 'NONE')
                if _pa not in ('NONE', '', None):
                    _fp = _latest_plan(tipo, _pa)
                    print(f'[ORDER] tipo={tipo} piano={_pa} file={_fp}', flush=True)
                    if _fp:
                        try:
                            _xls = pd.ExcelFile(_fp)
                            _df2 = None
                            for _sn in _xls.sheet_names:
                                if 'selezion' in _sn.lower():
                                    _df2 = pd.read_excel(_fp, sheet_name=_sn, dtype=str); break
                            if _df2 is None:
                                for _sn in _xls.sheet_names:
                                    if 'top' in _sn.lower():
                                        _df2 = pd.read_excel(_fp, sheet_name=_sn, dtype=str); break
                            if _df2 is not None:
                                print(f'[ORDER] foglio letto, righe={len(_df2)}', flush=True)
                                for _, _rr in _df2.iterrows():
                                    _tk = str(_rr.get('Ticker','') or '').strip()
                                    if not _tk or _tk.lower() == 'nan' or ' ' in _tk: continue
                                    _nm = str(_rr.get('Nome','') or _tk).strip()
                                    _mk = str(_rr.get('Mercato','') or '').strip()
                                    _vl = str(_rr.get('Valuta','') or '').strip()
                                    if _nm.lower() == 'nan': _nm = _tk
                                    if _mk.lower() == 'nan': _mk = ''
                                    if _vl.lower() == 'nan': _vl = ''
                                    prefill_rows.append({'ticker': _tk, 'nome': _nm, 'mercato': _mk, 'valuta': _vl, 'tipo': tipo})
                                prefill_rows = prefill_rows[:20]
                                print(f'[ORDER] ticker caricati={len(prefill_rows)}', flush=True)
                        except Exception as _ex:
                            print(f'[ORDER ERROR] {_ex}', flush=True)
            self._html(_build_ordine_bancario(nome, email, piano_ord, dati_fiscali=df, prefill_rows=prefill_rows, tipo=tipo)); return
        if p.startswith('/api/report/') and _is_client_auth(self):
            asset = p.split('/')[-1]
            email = CLIENT_SESSIONS.get(_get_client_token(self), '')
            db = read_clienti()
            c = next((x for grp in db.values() for x in grp if x.get('email','').lower()==email.lower()), None)
            piano = c.get(f'piano_{asset}', 'NONE') if c else 'NONE'
            if piano == 'NONE':
                self.send_error(403); return
            f = _latest_plan(asset, piano)
            if not f: self.send_error(404); return
            with open(f, 'rb') as fh: data = fh.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(f)}"')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if p.startswith('/api/report-pdf/') and _is_client_auth(self):
            _asset = p.split('/')[-1]
            _email = CLIENT_SESSIONS.get(_get_client_token(self), '')
            _db = read_clienti()
            _c = next((x for grp in _db.values() for x in grp if x.get('email','').lower()==_email.lower()), None)
            _piano = _c.get(f'piano_{_asset}', 'NONE') if _c else 'NONE'
            if _piano == 'NONE':
                self.send_error(403); return
            _fpdf = _latest_plan_pdf(_asset, _piano)
            if not _fpdf:
                self.send_error(404, 'PDF non disponibile'); return
            with open(_fpdf, 'rb') as _fh: _pdata = _fh.read()
            _fname_out = f'RT2026_{_asset.upper()}_{_piano}_{datetime.now().strftime("%Y%m%d")}.pdf'
            self.send_response(200)
            self.send_header('Content-Type', 'application/pdf')
            self.send_header('Content-Disposition', f'attachment; filename="{_fname_out}"')
            self.send_header('Content-Length', str(len(_pdata)))
            self.end_headers()
            self.wfile.write(_pdata)
            return
        # ── Scarica fattura (cliente autenticato) ────────────────
        if p == '/api/mia-fattura' and _is_client_auth(self):
            email = CLIENT_SESSIONS.get(_get_client_token(self), '')
            db = read_clienti()
            c = next((x for grp in db.values() for x in grp if x.get('email','').lower()==email.lower()), None)
            numero = c.get('numero_fattura', '') if c else ''
            if not numero:
                self.send_error(404, 'Nessuna fattura disponibile'); return
            path = os.path.join(FATTURE_DIR, f"{numero}.pdf")
            if not os.path.isfile(path):
                self.send_error(404, 'File fattura non trovato'); return
            with open(path, 'rb') as fh:
                data = fh.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/pdf')
            self.send_header('Content-Disposition', f'attachment; filename="{numero}.pdf"')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        # ── Route miste admin+client (settori / idee) ──────────
        if p == '/api/idee' and (_is_auth(self) or _is_client_auth(self)):
            if 'force=1' in self.path:
                _idee_cache['data'] = None
            self._json(get_idee_data()); return
        if p == '/api/settori' and (_is_auth(self) or _is_client_auth(self)):
            self._json(get_settori_data()); return
        if p == '/api/settori/titoli' and (_is_auth(self) or _is_client_auth(self)):
            qs_params = {}
            if '?' in self.path:
                for kv in self.path.split('?',1)[1].split('&'):
                    if '=' in kv:
                        k,v = kv.split('=',1)
                        qs_params[k] = v.replace('%20',' ').replace('+',' ')
            from urllib.parse import unquote_plus
            settore = unquote_plus(qs_params.get('s',''))
            self._json(get_settori_titoli(settore)); return
        # ── Endpoint interno WealthOS (solo localhost, no auth) ──
        if p == '/internal/next-invoice-number':
            if self.client_address[0] not in ('127.0.0.1', '::1') and not self.client_address[0].startswith('172.18.'):
                self.send_error(403); return
            self._json({'numero': _prossimo_numero_fattura()})
            return
        # ── File statici pubblici (no auth) ────────────────────
        if p.startswith('/static/'):
            _sfile = os.path.join(BASE_DIR, 'static', p[8:].lstrip('/'))
            if os.path.isfile(_sfile):
                import mimetypes as _mmt2
                _ct2, _ = _mmt2.guess_type(_sfile)
                with open(_sfile, 'rb') as _sf2:
                    _sd2 = _sf2.read()
                self.send_response(200)
                self.send_header('Content-Type', _ct2 or 'application/octet-stream')
                self.send_header('Content-Length', str(len(_sd2)))
                self.end_headers()
                self.wfile.write(_sd2)
            else:
                self.send_error(404)
            return
        # ── Rotte admin (richiede sessione) ────────────────────
        if not _is_auth(self):
            _redirect(self, '/login'); return
        if p in ('/admin', '/admin/'):
            self._html(HTML.replace('__BASE_URL__', BASE_URL).replace('__FUERTE_LOGO__', FUERTE_LOGO_B64))  # console admin
        elif p == '/api/status':
            self._json(get_status())
        elif p == '/api/kb-status' and _is_auth(self):
            if _CHAT_OK:
                self._json(_chat.get_kb_info())
            else:
                self._json({"error": "Chat non disponibile (pip install anthropic)"})
        elif p == '/api/prospect' and _is_auth(self):
            items = read_prospect()
            self._json({'items': items, 'total': len(items)})
        elif p == '/api/prospect/export' and _is_auth(self):
            import csv as _csv, io as _io
            items = read_prospect()
            out = _io.StringIO()
            fields = ['id','nome','cognome','email','telefono','linkedin_url','paese','fonte','interesse','stato','note','data_creazione','data_ultimo_contatto']
            w = _csv.DictWriter(out, fieldnames=fields, extrasaction='ignore')
            w.writeheader()
            for item in items:
                w.writerow(item)
            csv_bytes = out.getvalue().encode('utf-8-sig')
            self.send_response(200)
            self.send_header('Content-Type','text/csv; charset=utf-8')
            self.send_header('Content-Disposition','attachment; filename="prospect.csv"')
            self.send_header('Content-Length', str(len(csv_bytes)))
            self.end_headers()
            self.wfile.write(csv_bytes)
        elif p == '/api/kb-files' and _is_auth(self):
            import datetime as _dt
            kb_dir = os.path.join(os.path.dirname(__file__), 'KNOWLEDGE_BASE')
            try:
                now = time.time()
                files = []
                total = 0
                for fname in sorted(os.listdir(kb_dir)):
                    if not fname.endswith('.md'):
                        continue
                    fpath = os.path.join(kb_dir, fname)
                    st = os.stat(fpath)
                    size = st.st_size
                    total += size
                    mtime = st.st_mtime
                    diff = int(now - mtime)
                    if diff < 60:
                        rel = 'adesso'
                    elif diff < 3600:
                        rel = f"{diff//60} min fa"
                    elif diff < 86400:
                        rel = f"{diff//3600} ore fa"
                    else:
                        rel = f"{diff//86400} giorni fa"
                    modified = _dt.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
                    files.append({'name': fname, 'size': size, 'modified': modified, 'modified_rel': rel})
                self._json({'files': files, 'total_size': total})
            except Exception as e:
                self._json({'error': str(e), 'files': [], 'total_size': 0})
        elif p == '/api/reload-kb' and _is_auth(self):
            if not _CHAT_OK:
                self._json({"ok": False, "error": "Chat non disponibile"}); return
            try:
                _chat.reload_kb()
                self._json({"ok": True, **_chat.get_kb_info()})
            except Exception as e:
                self._json({"ok": False, "error": str(e)})
        elif p.startswith('/api/data/'):
            self._json(get_table_data(p.split('/')[-1]))
        elif p == '/api/mercati':
            self._json(get_mercati())
        elif p == '/api/params':
            self._json(read_params())
        elif p == '/api/clienti':
            self._json(read_clienti())
        elif p == '/api/clienti/export':
            csv_data = clienti_to_csv().encode('utf-8')
            fname = f"clienti_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
            self.send_response(200)
            self.send_header('Content-Type', 'text/csv; charset=utf-8')
            self.send_header('Content-Disposition', f'attachment; filename="{fname}"')
            self.send_header('Content-Length', str(len(csv_data)))
            self.end_headers()
            self.wfile.write(csv_data)
            return
        elif p == '/api/fatture' and _is_auth(self):
            fatture = []
            if os.path.isdir(FATTURE_DIR):
                for fname in sorted(os.listdir(FATTURE_DIR), reverse=True):
                    if fname.endswith('.pdf'):
                        numero = fname[:-4]
                        fpath = os.path.join(FATTURE_DIR, fname)
                        stat = os.stat(fpath)
                        import datetime as _dt
                        data_str = _dt.datetime.fromtimestamp(stat.st_mtime).strftime('%d/%m/%Y')
                        fatture.append({
                            'numero': numero,
                            'data': data_str,
                            'size_kb': round(stat.st_size / 1024, 1),
                        })
            self._json(fatture); return
        elif p.startswith('/api/fattura/') and _is_auth(self):
            numero = p.split('/')[-1]
            path = os.path.join(FATTURE_DIR, f"{numero}.pdf")
            if not os.path.isfile(path):
                self.send_error(404, 'Fattura non trovata'); return
            with open(path, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/pdf')
            self.send_header('Content-Disposition', f'attachment; filename="{numero}.pdf"')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        elif p == '/api/email-log' and _is_auth(self):
            import json as _ej
            _elog_path = os.path.join(BASE_DIR, 'email_log.json')
            if os.path.exists(_elog_path):
                with open(_elog_path, encoding='utf-8') as _ef:
                    self._json(_ej.load(_ef))
            else:
                self._json({})
            return
        elif p == '/api/ticker-frequency' and _is_auth(self):
            import json as _tfj
            _tf_path = os.path.join(BASE_DIR, 'ticker_frequency.json')
            if os.path.exists(_tf_path):
                with open(_tf_path, encoding='utf-8') as _tff:
                    self._json(_tfj.load(_tff))
            else:
                self._json({})
            return
        elif p == '/api/database' and _is_auth(self):
            try:
                data  = get_database_data()
                cache = load_prices_cache()
                data['cache']        = {'azioni': cache.get('azioni', {}),
                                        'etf':    cache.get('etf', {}),
                                        'fondi':  cache.get('fondi', {})}
                data['cache_azioni_at'] = cache.get('azioni_at')
                data['cache_etf_at']    = cache.get('etf_at')
                data['cache_fondi_at']  = cache.get('fondi_at')
                self._json(data)
            except Exception as e:
                self._json({'error': str(e)})
        elif p == '/api/database/lookup' and _is_auth(self):
            try:
                import urllib.parse as _up
                qs  = dict(_up.parse_qsl(self.path.split('?')[1] if '?' in self.path else ''))
                raw = qs.get('t', '')
                tickers = [t.strip().upper() for t in raw.split(',') if t.strip()]
                self._json(get_database_lookup(tickers))
            except Exception as e:
                self._json({'error': str(e)})
        elif p == '/api/parametri/scoring' and _is_auth(self):
            self._json({'ok': True, 'weights': _load_scoring_weights(),
                        'defaults': {a: {pl: dict(v) for pl, v in plans.items()}
                                     for a, plans in _SCORING_DEFAULTS.items()}})
        elif p.startswith('/api/log/'):
            nome = p.split('/')[-1]
            with run_lock:
                info = running.get(nome, {})
            self._json({'status': info.get('status','idle'), 'log': info.get('log',[])})
        # ── Social Automation ──────────────────────────────────
        elif p == '/api/social/approve' and _is_auth(self):
            import urllib.parse as _up
            qs       = dict(_up.parse_qsl(self.path.split('?')[1] if '?' in self.path else ''))
            draft_id = qs.get('draft_id', '')
            action   = qs.get('action', '')
            if not draft_id or action not in ('approve', 'reject', 'edit'):
                self._html(_social_response_page('Parametri mancanti', False)); return
            try:
                from social_automation import approve_and_publish, reject_draft
                if action == 'approve':
                    result = approve_and_publish(draft_id)
                    ok  = result.get('ok', False)
                    msg = result.get('summary', 'Pubblicazione completata')
                elif action == 'reject':
                    result = reject_draft(draft_id)
                    ok  = result.get('ok', False)
                    msg = f"Draft {draft_id} rifiutato"
                else:
                    ok  = True
                    msg = f"Apri il draft {draft_id} e modifica il testo, poi approva."
                self._html(_social_response_page(msg, ok))
            except Exception as e:
                self._html(_social_response_page(f'Errore: {e}', False))
        elif p == '/api/social/status' and _is_auth(self):
            try:
                from social_automation import list_all_drafts
                self._json({'ok': True, 'drafts': list_all_drafts(30)})
            except Exception as e:
                self._json({'ok': False, 'error': str(e)})
        elif p == '/api/social/platforms' and _is_auth(self):
            try:
                tokens_path = os.path.join(BASE_DIR, 'social_tokens.json')
                tokens = {}
                if os.path.exists(tokens_path):
                    with open(tokens_path, encoding='utf-8') as _f:
                        tokens = json.load(_f)
                li_token   = tokens.get('linkedin', {}).get('access_token', '')
                meta_token = tokens.get('meta', {}).get('page_token', '')
                meta_ig    = tokens.get('meta', {}).get('ig_user_id', '')
                # Leggi config per verificare se le credenziali OAuth sono configurate
                try:
                    with open(os.path.join(BASE_DIR, 'config.json'), encoding='utf-8') as _fc:
                        _cfg = json.load(_fc)
                except Exception:
                    _cfg = {}
                li_cfg   = _cfg.get('social', {}).get('linkedin', {})
                meta_cfg = _cfg.get('social', {}).get('meta', {})
                li_configurato   = bool(li_cfg.get('client_id')   or os.getenv('LINKEDIN_CLIENT_ID'))
                meta_configurato = bool(meta_cfg.get('app_id')    or os.getenv('META_APP_ID'))
                brevo_cfg  = _cfg.get('social', {}).get('brevo', {})
                brevo_key  = brevo_cfg.get('api_key', '') or _brevo_api_key()
                brevo_lists= brevo_cfg.get('list_ids', [])
                wa_token   = os.getenv('WHATSAPP_TOKEN', '')
                wa_phone   = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')
                self._json({
                    'ok': True,
                    'linkedin':  {'connesso': bool(li_token),  'configurato': li_configurato,  'member_id': tokens.get('linkedin',{}).get('member_id','')},
                    'facebook':  {'connesso': bool(meta_token), 'configurato': meta_configurato, 'page_name': tokens.get('meta',{}).get('page_name',''), 'page_id': tokens.get('meta',{}).get('page_id','')},
                    'instagram': {'connesso': bool(meta_token and meta_ig), 'ig_user_id': meta_ig},
                    'brevo':     {'configurato': bool(brevo_key), 'list_ids': brevo_lists},
                    'whatsapp':  {'configurato': bool(wa_token and wa_phone), 'token_presente': bool(wa_token)},
                })
            except Exception as e:
                self._json({'ok': False, 'error': str(e)})
        elif p == '/api/social/calendario' and _is_auth(self):
            try:
                cal_path = os.path.join(BASE_DIR, 'social_calendar.json')
                if not os.path.exists(cal_path):
                    self._json({'ok': True, 'calendario': []})
                    return
                with open(cal_path, encoding='utf-8') as _f:
                    cal = json.load(_f).get('calendar', [])
                today = datetime.now().strftime('%Y-%m-%d')
                # Aggiungi campo stato a ogni voce
                from social_automation import list_all_drafts
                drafts = list_all_drafts(50)
                published_dates = {d.get('date') for d in drafts if d.get('status') == 'published'}
                pending_dates   = {d.get('date') for d in drafts if d.get('status') == 'pending'}
                for entry in cal:
                    d = entry.get('date', '')
                    if d < today:
                        entry['stato'] = 'pubblicato' if d in published_dates else 'scaduto'
                    elif d == today:
                        entry['stato'] = 'oggi'
                    else:
                        entry['stato'] = 'pending' if d in pending_dates else 'programmato'
                self._json({'ok': True, 'calendario': cal})
            except Exception as e:
                self._json({'ok': False, 'error': str(e)})
        elif p == '/api/campagna/calendario' and _is_auth(self):
            try:
                cal_path = os.path.join(BASE_DIR, 'campagna_email_calendar.json')
                if not os.path.exists(cal_path):
                    self._json({'ok': False, 'error': 'campagna_email_calendar.json non trovato'}); return
                with open(cal_path, encoding='utf-8') as _f:
                    data = json.load(_f)
                today = datetime.now().strftime('%Y-%m-%d')
                for campagna in data.get('campagne', []):
                    for g in campagna.get('giorni', []):
                        if g.get('stato') == 'programmato' and g.get('data', '') < today:
                            g['stato'] = 'scaduto'
                        elif g.get('data', '') == today:
                            g['stato'] = 'oggi'
                self._json({'ok': True, 'campagne': data.get('campagne', [])})
            except Exception as e:
                self._json({'ok': False, 'error': str(e)})

        elif p == '/api/campagna/invia' and _is_auth(self):
            try:
                req = json.loads(self._body())
                mese  = req.get('mese', '')
                data_giorno = req.get('data', '')
                if not mese or not data_giorno:
                    self._json({'ok': False, 'msg': 'Parametri mancanti'}); return
                cal_path = os.path.join(BASE_DIR, 'campagna_email_calendar.json')
                with open(cal_path, encoding='utf-8') as _f:
                    cal_data = json.load(_f)
                giorno = None
                for camp in cal_data.get('campagne', []):
                    if camp['mese'] == mese:
                        for g in camp['giorni']:
                            if g['data'] == data_giorno:
                                giorno = g
                                break
                if not giorno:
                    self._json({'ok': False, 'msg': f'Giorno {data_giorno} non trovato in {mese}'}); return
                from social_publisher import BrevoService
                brevo = BrevoService()
                from content_generator import generate_post
                text = generate_post(giorno['tema'], giorno['lang'])
                from social_publisher import _build_email_html
                html_body = _build_email_html(text, None, giorno['lang'])
                result = brevo.send_newsletter_campaign(
                    subject=giorno['soggetto'],
                    html_content=html_body,
                )
                if result.get('ok'):
                    giorno['stato'] = 'inviato'
                    with open(cal_path, 'w', encoding='utf-8') as _f:
                        json.dump(cal_data, _f, indent=2, ensure_ascii=False)
                self._json(result)
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})

        elif p == '/api/linkedin/connect' and _is_auth(self):
            try:
                from social_publisher import LinkedInService
                li = LinkedInService()
                if not li.client_id:
                    self._html(_social_response_page('LinkedIn client_id non configurato in config.json', False)); return
                _redirect(self, li.get_auth_url())
            except Exception as e:
                self._html(_social_response_page(f'Errore: {e}', False))
        elif p == '/api/linkedin/callback':
            import urllib.parse as _up
            qs   = dict(_up.parse_qsl(self.path.split('?')[1] if '?' in self.path else ''))
            code = qs.get('code', '')
            if not code:
                self._html(_social_response_page('LinkedIn: codice OAuth mancante', False)); return
            try:
                from social_publisher import LinkedInService
                result = LinkedInService().exchange_code(code)
                ok  = result.get('ok', False)
                msg = 'LinkedIn collegato con successo! Token salvato.' if ok else f"Errore: {result.get('detail')}"
                self._html(_social_response_page(msg, ok))
            except Exception as e:
                self._html(_social_response_page(f'Errore OAuth LinkedIn: {e}', False))
        elif p == '/api/meta/connect' and _is_auth(self):
            try:
                from social_publisher import MetaService
                meta = MetaService()
                if not meta.app_id:
                    self._html(_social_response_page('Meta app_id non configurato in config.json', False)); return
                _redirect(self, meta.get_auth_url())
            except Exception as e:
                self._html(_social_response_page(f'Errore: {e}', False))
        elif p == '/api/meta/callback':
            import urllib.parse as _up
            qs   = dict(_up.parse_qsl(self.path.split('?')[1] if '?' in self.path else ''))
            code = qs.get('code', '')
            if not code:
                self._html(_social_response_page('Meta: codice OAuth mancante', False)); return
            try:
                from social_publisher import MetaService
                result = MetaService().exchange_code(code)
                ok  = result.get('ok', False)
                msg = (f"Meta collegato! page_id={result.get('page_id')} ig_user_id={result.get('ig_user_id')}"
                       if ok else f"Errore: {result.get('detail')}")
                self._html(_social_response_page(msg, ok))
            except Exception as e:
                self._html(_social_response_page(f'Errore OAuth Meta: {e}', False))
        # ── Brevo API ──────────────────────────────────────────
        elif p == '/api/brevo/campagne' and _is_auth(self):
            data, status = _brevo_call('/emailCampaigns?limit=50&sort=desc&statistics=globalStats')
            if status == 0:
                self._json({'ok': False, 'msg': 'Brevo API key non configurata. Inserisci api_key in config.json → social.brevo'})
            elif status == 200:
                self._json({'ok': True, 'campagne': data.get('campaigns', [])})
            else:
                self._json({'ok': False, 'msg': f'Brevo HTTP {status}', 'detail': data})
        elif p.startswith('/api/brevo/campagne/') and p.endswith('/risultati') and _is_auth(self):
            try:
                cid = p.split('/')[4]
                data, status = _brevo_call(f'/emailCampaigns/{cid}?statistics=globalStats')
                if status == 0:
                    self._json({'ok': False, 'msg': 'API key non configurata'})
                elif status == 200:
                    stats = data.get('statistics', {}).get('globalStats', {})
                    delivered = stats.get('delivered', 0) or 1
                    self._json({'ok': True, 'id': cid,
                        'nome': data.get('name'), 'oggetto': data.get('subject'),
                        'stato': data.get('status'), 'data_invio': data.get('sentDate'),
                        'inviati': stats.get('sent', 0), 'consegnati': stats.get('delivered', 0),
                        'aperture_uniche': stats.get('uniqueViews', 0),
                        'click_unici': stats.get('uniqueClicks', 0),
                        'disiscritti': stats.get('unsubscriptions', 0),
                        'rimbalzi': stats.get('hardBounces', 0) + stats.get('softBounces', 0),
                        'tasso_apertura_pct': round(stats.get('uniqueViews', 0) / delivered * 100, 1),
                        'tasso_click_pct': round(stats.get('uniqueClicks', 0) / delivered * 100, 1),
                    })
                else:
                    self._json({'ok': False, 'msg': f'Brevo HTTP {status}'})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
        elif p.startswith('/api/brevo/campagne/') and p.endswith('/non-aperti') and _is_auth(self):
            try:
                cid = int(p.split('/')[4])
                # Raccogli tutti i contatti (prospect + clienti)
                all_emails = {}
                for item in read_prospect():
                    e = (item.get('email') or '').strip().lower()
                    if e:
                        all_emails[e] = {
                            'nome': f"{item.get('nome','')} {item.get('cognome','')}".strip(),
                            'piano': item.get('interesse', ''),
                            'stato': item.get('stato', ''),
                        }
                cli = read_clienti()
                for c in cli.get('clienti', []) + cli.get('tester', []):
                    e = (c.get('email') or '').strip().lower()
                    if e:
                        all_emails[e] = {
                            'nome': f"{c.get('nome','')} {c.get('cognome','')}".strip(),
                            'piano': c.get('piano', ''),
                            'stato': c.get('stato', ''),
                        }
                openers = _brevo_check_openers(cid, list(all_emails.keys()))
                non_aperti = [
                    {'email': e, 'nome': v['nome'], 'piano': v['piano'], 'stato': v['stato']}
                    for e, v in all_emails.items()
                    if e not in openers
                ]
                self._json({'ok': True,
                    'totale': len(all_emails), 'aperti': len(openers),
                    'non_aperti': len(non_aperti), 'contatti': non_aperti})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
        elif p == '/api/analytics' and _is_auth(self):
            self._json(_calc_analytics())
        elif p == '/api/brevo/html-lancio' and _is_auth(self):
            self._json({'ok': True, 'html': _html_email_lancio()})
        elif p == '/api/brevo/liste' and _is_auth(self):
            data, status = _brevo_call('/contacts/lists?limit=50&sort=asc')
            if status == 0:
                self._json({'ok': False, 'msg': 'API key non configurata'})
            elif status == 200:
                self._json({'ok': True, 'liste': data.get('lists', [])})
            else:
                self._json({'ok': False, 'msg': f'Brevo HTTP {status}'})
        elif p == '/api/brevo/template' and _is_auth(self):
            data, status = _brevo_call('/smtp/templates?templateStatus=true&limit=50')
            if status == 0:
                self._json({'ok': False, 'msg': 'API key non configurata'})
            elif status == 200:
                self._json({'ok': True, 'template': data.get('templates', [])})
            else:
                self._json({'ok': False, 'msg': f'Brevo HTTP {status}'})
        else:
            self.send_error(404)

    def do_POST(self):
        p = self.path.split('?')[0]
        # ── Rimuovi ticker dal Database ────────────────────────
        if p == '/api/database/remove' and _is_auth(self):
            try:
                req    = json.loads(self._body())
                ticker = req.get('ticker', '').strip().upper()
                self._json(remove_ticker_from_lists(ticker))
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
            return
        if p == '/api/database/verify-dead' and _is_auth(self):
            try:
                req     = json.loads(self._body())
                tickers = req.get('tickers', [])
                self._json(verify_dead_tickers(tickers))
            except Exception as e:
                self._json({'dead': [], 'uncertain': [], 'error': str(e)})
            return
        if p == '/api/database/remove-bulk' and _is_auth(self):
            try:
                req     = json.loads(self._body())
                tickers = req.get('tickers', [])
                results = []
                for t in tickers:
                    r = remove_ticker_from_lists(t)
                    results.append({'ticker': t, 'ok': r.get('ok'), 'msg': r.get('msg','')})
                removed = sum(1 for r in results if r['ok'])
                self._json({'ok': True, 'removed': removed, 'details': results})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
            return
        # ── Chatbot AI (pubblico, rate-limited) ────────────────
        if p == '/api/chat':
            if not _CHAT_OK:
                self._json({'ok': False, 'error': 'Chatbot non disponibile.'}); return
            try:
                req     = json.loads(self._body())
                message = req.get('message', '').strip()
                sid     = req.get('session_id', '')
                ip      = self.client_address[0]
                result  = _chat.chat(message, sid, ip, ANTHROPIC_API_KEY)
                self._json(result)
            except Exception as e:
                self._json({'ok': False, 'error': 'Errore interno.', 'detail': str(e)})
            return
        # ── Chatbot abbonati (area clienti, report data) ───────
        if p == '/api/chat-abbonati':
            if not _is_client_auth(self):
                self._json({'ok': False, 'error': 'Accesso riservato agli abbonati.'}); return
            if not _CHAT_OK:
                self._json({'ok': False, 'error': 'Chatbot non disponibile.'}); return
            try:
                req     = json.loads(self._body())
                message = req.get('message', '').strip()
                sid     = req.get('session_id', '')
                ip      = self.client_address[0]
                tok     = _get_client_token(self)
                email   = CLIENT_SESSIONS.get(tok, '')
                db      = read_clienti()
                c       = next((x for grp in db.values() for x in grp
                                if x.get('email','').lower() == email.lower()), None)
                nome_cl = c.get('nome', '') if c else ''
                piani   = {
                    'azioni': (c or {}).get('piano_azioni', 'NONE'),
                    'etf':    (c or {}).get('piano_etf',    'NONE'),
                    'fondi':  (c or {}).get('piano_fondi',  'NONE'),
                } if c else {}
                result  = _chat.chat_abbonati(message, sid, ip, ANTHROPIC_API_KEY,
                                              client_nome=nome_cl, piani_attivi=piani)
                self._json(result)
            except Exception as e:
                self._json({'ok': False, 'error': 'Errore interno.', 'detail': str(e)})
            return
        # ── Reload KB interno (solo localhost, usato dall'orchestrator) ─
        if p == '/api/internal/reload-kb':
            if self.client_address[0] not in ('127.0.0.1', '::1', '::ffff:127.0.0.1'):
                self._json({'ok': False, 'error': 'Forbidden'}); return
            if not _CHAT_OK:
                self._json({'ok': False, 'error': 'Chat non disponibile'}); return
            try:
                _chat.reload_kb()
                self._json({'ok': True, **_chat.get_kb_info()})
            except Exception as e:
                self._json({'ok': False, 'error': str(e)})
            return
        # ── Social: genera draft manuale ──────────────────────
        if p == '/api/social/genera' and _is_auth(self):
            try:
                _raw = self._body()
                req = json.loads(_raw) if _raw else {}
                force_theme = req.get('theme')
                force_date  = req.get('date')
                force_lang  = req.get('lang')
                from social_automation import run as _sa_run
                result = _sa_run(force_theme=force_theme, force_date=force_date, force_lang=force_lang)
                if result:
                    self._json({'ok': True, 'draft_id': result.get('draft_id'), 'msg': 'Draft generato con successo'})
                else:
                    self._json({'ok': False, 'msg': 'Nessun contenuto generato. Verifica social_calendar.json e le credenziali AI.'})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
            return
        if p == '/api/social/draft/edit' and _is_auth(self):
            try:
                req      = json.loads(self._body())
                draft_id = req.get('draft_id', '')
                text_it  = req.get('text_it', '')
                text_es  = req.get('text_es', '')
                from social_automation import load_draft, save_draft
                draft = load_draft(draft_id)
                if not draft:
                    self._json({'ok': False, 'msg': 'Draft non trovato'}); return
                text_main = req.get('text_main', '')
                if text_it:   draft['text_it']   = text_it
                if text_es:   draft['text_es']   = text_es
                if text_main: draft['text_main'] = text_main
                draft['updated_at'] = datetime.now().isoformat()
                save_draft(draft)
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
            return
        # ── Login form ─────────────────────────────────────────
        if p == '/login':
            body = self._body()
            pwd = ''
            for part in body.split('&'):
                k, _, v = part.partition('=')
                if k == 'pwd':
                    import urllib.parse
                    pwd = urllib.parse.unquote_plus(v)
            _ip = self.client_address[0]
            if _rl_check(_ip):
                self._html(LOGIN_HTML.format(
                    error='<p class="err">Troppi tentativi. Riprova tra 30 minuti.</p>'
                )); return
            if pwd == ADMIN_PASSWORD:
                _rl_ok(_ip)
                _do_login(self)
            else:
                _rl_fail(_ip)
                self._html(LOGIN_HTML.format(
                    error='<p class="err">Password errata. Riprova.</p>'
                ))
            return
        # ── Registrazione pubblica (landing page) ─────────────
        if p == '/api/registrazione':
            try:
                req   = json.loads(self._body())
                nome  = req.get('nome','').strip()
                cogn  = req.get('cognome','').strip()
                email = req.get('email','').strip().lower()
                paese = req.get('paese','').strip().upper()
                tel   = req.get('telefono','').strip()
                cf    = req.get('codice_fiscale','').strip().upper()
                ind   = req.get('indirizzo','').strip()
                cap   = req.get('cap','').strip()
                cit   = req.get('citta','').strip()
                piva  = req.get('p_iva','').strip()
                if not nome or not email:
                    self._json({'ok': False, 'msg': 'Nome ed email obbligatori'}); return
                if '@' not in email:
                    self._json({'ok': False, 'msg': 'Email non valida'}); return
                if not tel or not (cf or piva) or not ind or not cap or not cit:
                    self._json({'ok': False, 'msg': 'Dati fiscali incompleti (CF o P.IVA obbligatorio)'}); return
                db = read_clienti()
                if any(c.get('email','').lower()==email
                       for grp in db.values() for c in grp):
                    self._json({'ok': False, 'msg': 'Email già registrata'}); return
                # Genera codice cliente progressivo
                total = sum(len(v) for v in db.values())
                codice_cliente = f"FVC-{datetime.now().strftime('%Y%m%d')}-{total+1:03d}"
                # Genera credenziali accesso
                from datetime import timedelta as _td
                pwd_temp   = _genera_password()
                now_dt     = datetime.now()
                now_str    = now_dt.strftime('%Y-%m-%d')
                pwd_expiry = (now_dt + _td(hours=48)).strftime('%Y-%m-%dT%H:%M:%S')
                nuovo = {
                    'nome':    nome, 'cognome': cogn, 'email': email,
                    'codice_cliente': codice_cliente,
                    'piano_azioni':    req.get('piano_azioni',   'NONE'),
                    'piano_etf':       req.get('piano_etf',      'NONE'),
                    'piano_fondi':     req.get('piano_fondi',    'NONE'),
                    'piano_ordini':    req.get('piano_ordini',   'NONE'),
                    'piano_wealthos':  req.get('piano_wealthos', 'NONE'),
                    'screener_attivi': [],
                    'data_registrazione': now_str,
                    'data_attivazione':   now_str,
                    'stato': 'ATTIVO',
                    'password_hash':        _hash_pwd(pwd_temp),
                    'must_change_password': True,
                    'password_expiry':      pwd_expiry,
                    'note': req.get('note',''),
                    'gdpr_consent': bool(req.get('gdpr_consent', False)),
                    'gdpr_consent_date': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                    'dati_fiscali': {
                        'paese':          paese,
                        'data_nascita':   req.get('data_nascita','').strip(),
                        'indirizzo':      ind,
                        'cap':            cap,
                        'citta':          cit,
                        'codice_fiscale': cf,
                        'telefono':       tel,
                        'p_iva':          piva,
                    },
                }
                db.setdefault('clienti', []).append(nuovo)
                save_clienti(db)
                _cf_mask = (cf[:4] + '***') if cf else '-'
                print(f"[REG] {codice_cliente} — {nome} {cogn} <{email}> — {paese} — CF:{_cf_mask}", flush=True)
                # Genera fattura PDF e invia email con credenziali
                num_fatt  = _prossimo_numero_fattura()
                pdf_bytes = genera_fattura_pdf(nuovo, num_fatt)
                if pdf_bytes:
                    _salva_fattura(pdf_bytes, num_fatt)
                    nuovo['numero_fattura'] = num_fatt
                    save_clienti(db)
                piani_lbl = _piani_label(nuovo)
                _invia_email_credenziali(
                    f"{nome} {cogn}".strip(), email, piani_lbl, pwd_temp,
                    pdf_bytes=pdf_bytes, numero_fattura=num_fatt
                )
                self._json({'ok': True, 'codice_cliente': codice_cliente})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
            return
        # ── Login cliente (pubblico) ───────────────────────────
        if p == '/api/client-login':
            body = self._body()
            fields = {}
            for part in body.split('&'):
                k, _, v = part.partition('=')
                import urllib.parse
                fields[k.strip()] = urllib.parse.unquote_plus(v)
            _ip = self.client_address[0]
            _login_logo = f'<img src="data:image/png;base64,{FUERTE_LOGO_B64}" alt="Fuerte Venture Capital">'
            if _rl_check(_ip):
                self._html(CLIENT_LOGIN_HTML.format(logo=_login_logo,
                    error='<p class="err">Troppi tentativi. Riprova tra 30 minuti.</p>',
                    next_url='')); return
            email_in   = _validate_str(fields.get('email', ''), 200).lower()
            pwd_in     = _validate_str(fields.get('pwd', ''), 200)
            _next_login = fields.get('next', '').strip()
            if _next_login and not (_next_login.startswith('/') and not _next_login.startswith('//')):
                _next_login = ''
            db = read_clienti()
            match = None
            for c in (db.get('tester', []) + db.get('clienti', [])):
                if c.get('email', '').lower() == email_in:
                    match = c; break
            if match and match.get('stato') in ('ATTIVO', 'TESTER') and _verify_pwd(pwd_in, match.get('password_hash', '')):
                _rl_ok(_ip)
                # Controlla scadenza trial (solo TESTER con trial_end impostato)
                if match.get('stato') == 'TESTER' and match.get('trial_end'):
                    try:
                        _tend = datetime.strptime(match['trial_end'][:19], '%Y-%m-%dT%H:%M:%S')
                        if datetime.now() > _tend:
                            self._html(CLIENT_LOGIN_HTML.format(logo=_login_logo,
                                error='<p class="err">⏱ Il tuo periodo di prova di 7 giorni è scaduto. '
                                      'Contatta <a href="mailto:info@fuerteventurecapital.com" style="color:#F6AD55">'
                                      'info@fuerteventurecapital.com</a> per attivare un piano.</p>',
                                next_url=_next_login))
                            return
                    except Exception:
                        pass
                # Controlla scadenza password temporanea
                expiry_str = match.get('password_expiry', '')
                if expiry_str:
                    try:
                        if datetime.now() > datetime.strptime(expiry_str, '%Y-%m-%dT%H:%M:%S'):
                            self._html(CLIENT_LOGIN_HTML.format(logo=_login_logo,
                                error='<p class="err">⏱ Password temporanea scaduta. Contatta <a href="mailto:info@fuerteventurecapital.com" style="color:#F6AD55">info@fuerteventurecapital.com</a> per ricevere nuove credenziali.</p>',
                                next_url=_next_login))
                            return
                    except Exception:
                        pass
                _do_client_login(self, email_in, must_change=bool(match.get('must_change_password')), next_url=_next_login)
            else:
                _rl_fail(_ip)
                self._html(CLIENT_LOGIN_HTML.format(logo=_login_logo, error='<p class="err">Email o password non corretti.</p>', next_url=_next_login))
            return
        # ── Forgot password ────────────────────────────────────
        if p == '/api/forgot-password':
            _logo = f'<img src="data:image/png;base64,{FUERTE_LOGO_B64}" alt="Fuerte Venture Capital">'
            _fp_ok = FORGOT_PWD_HTML.format(logo=_logo, msg='<p class="msg ok">Se l\'email è registrata riceverai il link entro pochi minuti.</p>')
            _ip_fp = self.client_address[0]
            if _rl_check(_ip_fp):
                self._html(_fp_ok); return  # stessa risposta per non rivelare il blocco
            _rl_fail(_ip_fp)
            import urllib.parse as _up
            body = self._body()
            fields = dict(_up.parse_qsl(body, keep_blank_values=True))
            email_in = fields.get('email', '').strip().lower()
            db = read_clienti()
            match = next((c for c in (db.get('tester', []) + db.get('clienti', []))
                          if c.get('email', '').lower() == email_in and c.get('stato') in ('ATTIVO', 'TESTER')), None)
            if match:
                token = secrets.token_urlsafe(32)
                RESET_TOKENS[token] = (email_in, time.time() + 3600)
                reset_url = f"{BASE_URL}/reset-password?token={token}"
                logo_src = f"data:image/png;base64,{FUERTE_LOGO_B64}"
                corpo = f"""<html><body style="background:#0a0f1e;font-family:Arial,sans-serif;padding:32px">
<div style="max-width:480px;margin:0 auto;background:#111827;border-radius:12px;padding:32px;border:1px solid rgba(246,173,85,.2)">
<img src="{logo_src}" alt="Fuerte Venture Capital" style="height:40px;display:block;margin:0 auto 20px">
<p style="color:#e0e0e0;font-size:15px">Hai richiesto il reset della password per la tua area riservata.</p>
<p style="margin:20px 0;text-align:center">
  <a href="{reset_url}" style="background:#F6AD55;color:#0a0f1e;padding:12px 28px;border-radius:8px;font-weight:700;text-decoration:none;font-size:15px">Imposta nuova password</a>
</p>
<p style="color:#666;font-size:12px">Il link è valido per 1 ora. Se non hai richiesto il reset, ignora questa email.</p>
</div></body></html>"""
                _fp_payload = {
                    "sender":      {"name": BREVO_SENDER_NAME, "email": BREVO_SENDER_EMAIL},
                    "to":          [{"email": email_in}],
                    "subject":     "Reset password — Fuerte Venture Capital",
                    "htmlContent": corpo,
                }
                _fp_data, _fp_status = _brevo_call('/smtp/email', method='POST', payload=_fp_payload)
                if _fp_status in (200, 201):
                    print(f"[RESET-PWD] Email inviata a {email_in} (Brevo {_fp_status})", flush=True)
                else:
                    print(f"[RESET-PWD] Brevo {_fp_status}: {_fp_data}", flush=True)
            self._html(_fp_ok); return
        # ── Reset password (da link email) ─────────────────────
        if p == '/api/reset-password':
            import urllib.parse as _up
            body = self._body()
            fields = dict(_up.parse_qsl(body, keep_blank_values=True))
            token  = fields.get('token', '').strip()
            pwd1   = fields.get('pwd1', '').strip()
            pwd2   = fields.get('pwd2', '').strip()
            _logo  = f'<img src="data:image/png;base64,{FUERTE_LOGO_B64}" alt="Fuerte Venture Capital">'
            def _reset_err(msg):
                self._html(RESET_PWD_HTML.format(logo=_logo, token=token, error=f'<p class="err">{msg}</p>'))
            if token not in RESET_TOKENS or time.time() >= RESET_TOKENS[token][1]:
                RESET_TOKENS.pop(token, None)
                _reset_err('Link scaduto. <a href="/reset-password" style="color:#F6AD55">Richiedine uno nuovo.</a>'); return
            if pwd1 != pwd2:
                _reset_err('Le password non coincidono.'); return
            if len(pwd1) < 8:
                _reset_err('La password deve essere di almeno 8 caratteri.'); return
            email_reset = RESET_TOKENS.pop(token)[0]
            db = read_clienti()
            updated = False
            for cat in ('tester', 'clienti'):
                for c in db.get(cat, []):
                    if c.get('email', '').lower() == email_reset:
                        c['password_hash'] = _hash_pwd(pwd1)
                        c['must_change_password'] = False
                        c.pop('password_expiry', None)
                        updated = True; break
                if updated: break
            if updated:
                save_clienti(db)
                print(f"[RESET-PWD] Password aggiornata per {email_reset}", flush=True)
                _login_logo = f'<img src="data:image/png;base64,{FUERTE_LOGO_B64}" alt="Fuerte Venture Capital">'
                self._html(CLIENT_LOGIN_HTML.format(logo=_login_logo,
                    error='<p style="color:#68D391;text-align:center;margin-top:.5rem">✓ Password aggiornata. Accedi ora.</p>',
                    next_url='')); return
            _reset_err('Errore interno. Contatta il supporto.'); return
        # ── Aggiungi piano da area clienti ────────────────────
        if p == '/api/aggiungi-piano':
            if not _is_client_auth(self):
                self._json({'ok': False, 'msg': 'Non autorizzato'}); return
            try:
                req = json.loads(self._body())
                asset   = req.get('asset', '').strip().lower()
                livello = req.get('livello', 'BASIC').strip().upper()
                if asset not in ('azioni','etf','fondi','ordini'):
                    self._json({'ok': False, 'msg': 'Servizio non valido'}); return
                if livello not in ('BASIC','PRO','VALUE'):
                    self._json({'ok': False, 'msg': 'Livello non valido'}); return
                email = CLIENT_SESSIONS.get(_get_client_token(self), '')
                db = read_clienti()
                found = None
                for grp in db.values():
                    for c in grp:
                        if c.get('email','').lower() == email.lower():
                            found = c; break
                    if found: break
                if not found:
                    self._json({'ok': False, 'msg': 'Cliente non trovato'}); return
                campo = f'piano_{asset}'
                found[campo] = livello
                save_clienti(db)
                print(f"[PIANO] {email}: {campo} → {livello}", flush=True)
                # Fattura + email conferma
                asset_labels = {'azioni':'Azioni','etf':'ETF','fondi':'Fondi','ordini':'Order Builder'}
                asset_label  = asset_labels.get(asset, asset.capitalize())
                try:
                    num_fatt  = _prossimo_numero_fattura()
                    pdf_bytes = genera_fattura_pdf(found, num_fatt)
                    if pdf_bytes:
                        _salva_fattura(pdf_bytes, num_fatt)
                        found['numero_fattura'] = num_fatt
                        save_clienti(db)
                    _invia_email_nuovo_piano(
                        found.get('nome', email), email,
                        asset_label, livello,
                        pdf_bytes=pdf_bytes, numero_fattura=num_fatt
                    )
                except Exception as ex:
                    print(f"[PIANO] Errore fattura/email: {ex}", flush=True)
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
            return
        # ── Cambio password (primo accesso obbligatorio o volontario) ─
        if p == '/api/cambia-password':
            if not _is_client_auth(self):
                self._json({'ok': False, 'msg': 'Non autorizzato'}); return
            try:
                import urllib.parse as _up
                fields = {}
                for part in self._body().split('&'):
                    k, _, v = part.partition('=')
                    fields[k.strip()] = _up.unquote_plus(v)
                voluntary = fields.get('voluntary', '') == '1'
                new_pwd   = fields.get('new_pwd', '').strip()
                conf_pwd  = fields.get('conf_pwd', '').strip()
                old_pwd   = fields.get('old_pwd', '').strip()
                import re as _re
                if len(new_pwd) < 8 or not _re.search(r'[A-Z]', new_pwd) or not _re.search(r'[a-z]', new_pwd) or not _re.search(r'[0-9]', new_pwd) or not _re.search(r'[@$!%*?&_#^]', new_pwd):
                    self._html(_build_cambia_password_page(error='La password deve avere almeno 8 caratteri, una maiuscola, una minuscola, un numero e un simbolo (@$!%*?&_#^).', voluntary=voluntary)); return
                if new_pwd != conf_pwd:
                    self._html(_build_cambia_password_page(error='Le password non coincidono.', voluntary=voluntary)); return
                email = CLIENT_SESSIONS.get(_get_client_token(self), '')
                db = read_clienti()
                for grp in db.values():
                    for c in grp:
                        if c.get('email','').lower() == email.lower():
                            if voluntary:
                                if not old_pwd or not _verify_pwd(old_pwd, c.get('password_hash', '')):
                                    self._html(_build_cambia_password_page(error='Password attuale non corretta.', voluntary=True)); return
                            c['password_hash']        = _hash_pwd(new_pwd)
                            c['must_change_password'] = False
                            c['password_expiry']      = ''
                            save_clienti(db)
                            print(f"[PWD] Password {'modificata' if voluntary else 'impostata'} per {email}", flush=True)
                            _redirect(self, '/area-clienti'); return
                self._json({'ok': False, 'msg': 'Cliente non trovato'})
            except Exception as e:
                self._html(_build_cambia_password_page(error=html.escape(str(e))))
            return
        # ── Checkout pubblico ──────────────────────────────────
        if p == '/api/checkout':
            try:
                req = json.loads(self._body())
                self._json(create_checkout_session(
                    req.get('asset',''), req.get('tier',''),
                    email_prefill=req.get('email',''),
                ))
            except Exception as e:
                self._json({'error': str(e)})
            return
        # ── Webhook Stripe ─────────────────────────────────────
        if p == '/webhooks/stripe':
            try:
                body_b = self.rfile.read(int(self.headers.get('Content-Length', 0)))
                sig    = self.headers.get('Stripe-Signature', '')
                result = _handle_stripe_webhook(body_b, sig)
                if result.get('ok'):
                    self._json({'ok': True})
                else:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                self._json({'ok': False, 'error': str(e)})
            return
        # ── Conti bancari cliente ──────────────────────────────
        if p in ('/api/ordine/conti', '/api/ordine/conti/delete'):
            if not _is_client_auth(self):
                self._json({'ok': False, 'msg': 'Non autorizzato'}); return
            tok_c   = _get_client_token(self)
            c_email = CLIENT_SESSIONS.get(tok_c, '')
            if p == '/api/ordine/conti':
                self._json({'ok': True, 'conti': _load_conti(c_email)}); return
            else:  # /api/ordine/conti/delete
                try:
                    req   = json.loads(self._body())
                    conto = req.get('conto', '').strip()
                    if conto and c_email:
                        _delete_conto(c_email, conto)
                    self._json({'ok': True})
                except Exception as e:
                    self._json({'ok': False, 'msg': str(e)})
                return
        # ── Profili banca cliente ─────────────────────────────
        if p == '/api/salva-profilo-investitore':
            if not _is_client_auth(self):
                self._json({'ok': False, 'msg': 'Non autorizzato'}); return
            try:
                tok_c   = _get_client_token(self)
                c_email = CLIENT_SESSIONS.get(tok_c, '')
                req     = json.loads(self._body())
                db      = read_clienti()
                c       = next((x for grp in db.values() for x in grp
                                if x.get('email','').lower() == c_email.lower()), None)
                if c:
                    from datetime import datetime as _dt
                    c['profilo_investitore'] = {
                        'tipo':       req.get('tipo', ''),
                        'label':      req.get('label', ''),
                        'score':      req.get('score', 0),
                        'allocazione': req.get('allocazione', {}),
                        'data':       _dt.now().strftime('%d/%m/%Y'),
                    }
                    save_clienti(db)
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
            return
        if p in ('/api/banche', '/api/banche/save', '/api/banche/delete'):
            if not _is_client_auth(self):
                self._json({'ok': False, 'msg': 'Non autorizzato'}); return
            tok_c   = _get_client_token(self)
            c_email = CLIENT_SESSIONS.get(tok_c, '')
            if p == '/api/banche':
                self._json({'ok': True, 'profili': _load_profili(c_email)}); return
            try:
                req = json.loads(self._body())
                if p == '/api/banche/save':
                    iban = req.get('iban', '').strip()
                    if not iban:
                        self._json({'ok': False, 'msg': 'IBAN obbligatorio'}); return
                    _save_profilo(c_email, {
                        'banca':         req.get('banca', '').strip(),
                        'iban':          iban.upper(),
                        'nome_gestore':  req.get('nome_gestore', '').strip(),
                        'email_gestore': req.get('email_gestore', '').strip(),
                    })
                else:  # /api/banche/delete
                    _delete_profilo(c_email, req.get('iban', ''))
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
            return
        # ── Rotte ordine cliente (richiede sessione cliente) ──
        if p in ('/api/ordine/prezzi', '/api/ordine/csv', '/api/ordine/invia'):
            if not _is_client_auth(self):
                self._json({'ok': False, 'msg': 'Non autorizzato'}); return
            if not _OB_OK:
                self._json({'ok': False, 'msg': 'order_builder non disponibile'}); return
            try:
                data = json.loads(self._body())
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)}); return
            if p == '/api/ordine/prezzi':
                try:
                    self._json(_ob.get_live_prices(data.get('tickers', [])))
                except Exception as e:
                    self._json({'ok': False, 'msg': str(e)})
            elif p == '/api/ordine/csv':
                try:
                    fmt = data.get('formato', 'generico')
                    righe = data.get('righe', [])
                    rif = data.get('riferimento', '')
                    ep = data.get('exec_params', {})
                    if fmt == 'ibkr':
                        csv_out = _ob.genera_csv_ibkr(righe, rif, ep)
                        filename = f'ordine_IBKR_{rif}.csv'
                    else:
                        csv_out = _ob.genera_csv_generico(righe, ep)
                        filename = f'ordine_Fuerte_{rif}.csv'
                    payload = csv_out.encode('utf-8-sig')
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/csv; charset=utf-8')
                    self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                    self.send_header('Content-Length', str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except Exception as e:
                    self._json({'ok': False, 'msg': str(e)})
            elif p == '/api/ordine/invia':
                try:
                    now = datetime.now()
                    rif = 'ORD-' + now.strftime('%Y%m%d-%H%M%S')
                    ordine = {
                        'cliente_nome':  data.get('cliente_nome', ''),
                        'cliente_email': data.get('cliente_email', ''),
                        'data':          now.strftime('%d/%m/%Y %H:%M'),
                        'timestamp':     now.isoformat(),
                        'riferimento':   rif,
                        'bank_nome':     data.get('bank_nome', ''),
                        'nome_gestore':  data.get('nome_gestore', ''),
                        'bank_email':    data.get('bank_email', ''),
                        'bank_iban':     data.get('bank_iban', ''),
                        'note':          data.get('note', ''),
                        'righe':         data.get('righe', []),
                        'totale_eur':    data.get('totale_eur', 0),
                        'exec_params':   data.get('exec_params', {}),
                        'anagrafica':    data.get('anagrafica', {}),
                    }
                    bank_email = data.get('bank_email', '')
                    cc_email   = data.get('cliente_email', '')  # sempre in copia al cliente
                    oggetto    = (f"Istruzioni Acquisto Titoli — {ordine['cliente_nome']} — "
                                  f"{now.strftime('%d/%m/%Y')} [{rif}]")
                    html_body  = _ob.genera_email_html(ordine)
                    tok_c = _get_client_token(self)
                    c_email = CLIENT_SESSIONS.get(tok_c, '')
                    try:
                        ok, msg = _ob.invia_email_ordine(bank_email, oggetto, html_body, cc_email)
                    except Exception as email_ex:
                        ok, msg = False, str(email_ex)
                    ordine['stato']     = 'inviato' if ok else 'errore'
                    ordine['stato_msg'] = msg
                    # Archivia ordine sempre, anche se invio fallisce
                    if c_email:
                        try:
                            _salva_ordine(c_email, ordine)
                        except Exception as ex:
                            print(f'[ORDINI] Errore salvataggio: {ex}', flush=True)
                        # Aggiorna dati_fiscali in clienti.json con i valori non vuoti del form
                        ag_form = data.get('anagrafica') or {}
                        if any(ag_form.values()):
                            try:
                                _db_cl = read_clienti()
                                _cl = next((x for grp in _db_cl.values() for x in grp
                                            if x.get('email','').lower() == c_email.lower()), None)
                                if _cl:
                                    _df = _cl.setdefault('dati_fiscali', {})
                                    for _k in ('indirizzo','cap','citta','paese','codice_fiscale','p_iva','telefono'):
                                        if ag_form.get(_k):
                                            _df[_k] = ag_form[_k]
                                    save_clienti(_db_cl)
                            except Exception as ex:
                                print(f'[ORDINI] Errore aggiornamento anagrafica: {ex}', flush=True)
                        conto_val = (data.get('exec_params', {}) or {}).get('conto', '')
                        if conto_val:
                            try:
                                _save_conto(c_email, conto_val)
                            except Exception:
                                pass
                        # Auto-salva profilo banca completo se IBAN e email gestore presenti
                        _bank_iban  = data.get('bank_iban', '').strip()
                        _bank_email = data.get('bank_email', '').strip()
                        if _bank_iban and _bank_email and c_email:
                            try:
                                _save_profilo(c_email, {
                                    'banca':         data.get('bank_nome', '').strip(),
                                    'iban':          _bank_iban.upper(),
                                    'nome_gestore':  data.get('nome_gestore', '').strip(),
                                    'email_gestore': _bank_email,
                                })
                            except Exception:
                                pass
                    self._json({'ok': ok, 'msg': msg, 'riferimento': rif})
                except Exception as e:
                    self._json({'ok': False, 'msg': str(e)})
            return
        # ── Rotte admin (richiede sessione) ────────────────────
        if not _is_auth(self):
            self._json({'ok': False, 'msg': 'Non autorizzato'}); return
        body = self._body()
        if p == '/api/params':
            try:
                save_params(json.loads(body))
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
        elif p == '/api/prospect/import' and _is_auth(self):
            try:
                req = json.loads(body)
                csv_text = req.get('csv_content', '')

                import csv as _csv, io as _io
                reader = _csv.DictReader(_io.StringIO(csv_text))
                items = read_prospect()
                email_set = {p.get('email','').lower() for p in items if p.get('email')}
                inseriti = 0; duplicati = 0; errori = 0

                # Mappa colonne flessibile (Apollo, LinkedIn, manuale)
                COL_MAP = {
                    'nome': ['nome','first name','firstname','name','first_name'],
                    'cognome': ['cognome','last name','lastname','surname','last_name'],
                    'email': ['email','email address','e-mail','mail'],
                    'telefono': ['telefono','phone','mobile','cellulare'],
                    'linkedin_url': ['linkedin url','linkedin_url','linkedin','profile url','profile_url'],
                    'fonte': ['fonte','source','lead source'],
                    'interesse': ['interesse','interest','piano','asset'],
                    'paese': ['paese','country','nation'],
                    'note': ['note','notes','comment','commento'],
                }

                def _get_col(row, candidates):
                    for c in candidates:
                        for k in row:
                            if k.strip().lower() == c.lower():
                                v = row[k]
                                return v.strip() if v else ''
                    return ''

                for row in reader:
                    try:
                        email = _get_col(row, COL_MAP['email']).lower()
                        if not email:
                            errori += 1; continue
                        if email in email_set:
                            duplicati += 1; continue
                        email_set.add(email)
                        nome = _get_col(row, COL_MAP['nome']) or email.split('@')[0]
                        item = {
                            'id': _next_prospect_id(items),
                            'nome': nome,
                            'cognome': _get_col(row, COL_MAP['cognome']),
                            'email': email,
                            'email_verificata': False,
                            'telefono': _get_col(row, COL_MAP['telefono']),
                            'linkedin_url': _get_col(row, COL_MAP['linkedin_url']),
                            'paese': _get_col(row, COL_MAP['paese']) or 'IT',
                            'fonte': _get_col(row, COL_MAP['fonte']) or 'CSV',
                            'interesse': _get_col(row, COL_MAP['interesse']) or 'Tutti',
                            'stato': 'Da Contattare',
                            'note': _get_col(row, COL_MAP['note']),
                            'data_creazione': datetime.now().strftime('%Y-%m-%d'),
                            'data_ultimo_contatto': None,
                            'promosso': False,
                        }
                        items.append(item)
                        inseriti += 1
                    except Exception:
                        errori += 1
                save_prospect(items)
                print(f'[PROSPECT IMPORT] inseriti={inseriti} duplicati={duplicati} errori={errori}', flush=True)
                self._json({'ok': True, 'inseriti': inseriti, 'duplicati': duplicati, 'errori': errori})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})

        elif p == '/api/prospect/update' and _is_auth(self):
            try:
                req = json.loads(body)
                pid = int(req.get('id', 0))
                items = read_prospect()
                found = None
                for item in items:
                    if item.get('id') == pid:
                        found = item; break
                if not found:
                    self._json({'ok': False, 'msg': 'Prospect non trovato'}); return
                if 'stato' in req: found['stato'] = req['stato']
                if 'note' in req: found['note'] = req['note']
                if 'data_ultimo_contatto' in req: found['data_ultimo_contatto'] = req['data_ultimo_contatto']
                save_prospect(items)
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})

        elif p == '/api/prospect/promuovi' and _is_auth(self):
            try:
                req = json.loads(body)
                pid = int(req.get('id', 0))
                items = read_prospect()
                found = None
                for item in items:
                    if item.get('id') == pid:
                        found = item; break
                if not found:
                    self._json({'ok': False, 'msg': 'Prospect non trovato'}); return
                # Aggiungi come tester in clienti.json
                db = read_clienti()
                email = found.get('email','').lower()
                tutti = (db.get('tester',[]) + db.get('clienti',[]))
                if any(c.get('email','').lower() == email for c in tutti):
                    self._json({'ok': False, 'msg': f'Email {email} già presente nei clienti'}); return
                from datetime import timedelta as _td_p
                _now_p = datetime.now()
                _pwd_p = _genera_password()
                nuovo = {
                    'nome': found.get('nome',''),
                    'cognome': found.get('cognome',''),
                    'email': email,
                    'piano_azioni': 'NONE',
                    'piano_etf': 'NONE',
                    'piano_fondi': 'NONE',
                    'piano_ordini': 'NONE',
                    'stato': 'TESTER',
                    'data_registrazione': _now_p.strftime('%Y-%m-%d'),
                    'trial_start': _now_p.strftime('%Y-%m-%dT%H:%M:%S'),
                    'trial_end':   (_now_p + _td_p(days=7)).strftime('%Y-%m-%dT%H:%M:%S'),
                    'fonte': 'prospect',
                    'password_hash':      _hash_pwd(_pwd_p),
                    'must_change_password': True,
                    'password_expiry':    (_now_p + _td_p(hours=48)).strftime('%Y-%m-%dT%H:%M:%S'),
                    'dati_fiscali': {'paese': found.get('paese','IT'), 'telefono': found.get('telefono','')},
                }
                db.setdefault('tester', []).append(nuovo)
                save_clienti(db)
                found['stato'] = 'Promosso ✓'
                found['promosso'] = True
                save_prospect(items)
                _nome_p = f"{nuovo['nome']} {nuovo['cognome']}".strip() or email
                _invia_email_credenziali(_nome_p, email, 'Trial 7 giorni — accesso completo', _pwd_p)
                print(f'[PROSPECT] {email} promosso a Tester', flush=True)
                self._json({'ok': True, 'email': email})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})

        elif p == '/api/prospect/import-apollo' and _is_auth(self):
            try:
                import csv as _csv, io as _io
                raw = self._body()
                reader = _csv.DictReader(_io.StringIO(raw))
                items = read_prospect()
                email_set = {(x.get('email') or '').strip().lower() for x in items}
                inseriti = duplicati = errori = 0
                con_linkedin = 0
                for row in reader:
                    email = (row.get('Email') or '').strip().lower()
                    if not email or '@' not in email:
                        errori += 1; continue
                    if email in email_set:
                        duplicati += 1; continue
                    email_set.add(email)
                    nome    = (row.get('First Name') or '').strip()
                    cognome = (row.get('Last Name') or '').strip()
                    company = (row.get('Company Name') or '').strip()
                    title   = (row.get('Title') or '').strip()
                    li_url  = (row.get('Person Linkedin Url') or '').strip()
                    tel     = (row.get('Mobile Phone') or row.get('Work Direct Phone') or '').strip()
                    city    = (row.get('City') or '').strip()
                    country = (row.get('Country') or '').strip()
                    if not nome and company:
                        nome = company; cognome = ''
                    note_parts = [x for x in [company, title, city, country] if x]
                    if li_url: con_linkedin += 1
                    items.append({
                        'id':                   _next_prospect_id(items),
                        'nome':                 nome,
                        'cognome':              cognome,
                        'email':                email,
                        'email_verificata':     True,
                        'telefono':             tel,
                        'linkedin_url':         li_url,
                        'paese':                country or 'IT',
                        'fonte':                'Apollo.io',
                        'interesse':            'BASIC',
                        'stato':                'Prospect LinkedIn',
                        'note':                 ' | '.join(note_parts),
                        'data_creazione':       datetime.now().strftime('%Y-%m-%d'),
                        'data_ultimo_contatto': None,
                        'promosso':             False,
                    })
                    inseriti += 1
                save_prospect(items)
                self._json({'ok': True, 'inseriti': inseriti, 'duplicati': duplicati, 'errori': errori, 'con_linkedin': con_linkedin})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
            return

        elif p == '/api/prospect/aggiungi' and _is_auth(self):
            try:
                req = json.loads(body)
                email = req.get('email','').strip().lower()
                if not email:
                    self._json({'ok': False, 'msg': 'Email obbligatoria'}); return
                items = read_prospect()
                if any(p.get('email','').lower() == email for p in items):
                    self._json({'ok': False, 'msg': f'Email {email} già presente'}); return
                item = {
                    'id': _next_prospect_id(items),
                    'nome': req.get('nome','').strip(),
                    'cognome': req.get('cognome','').strip(),
                    'email': email,
                    'email_verificata': False,
                    'telefono': req.get('telefono','').strip(),
                    'linkedin_url': req.get('linkedin_url','').strip(),
                    'paese': req.get('paese','IT'),
                    'fonte': req.get('fonte','Manuale'),
                    'interesse': req.get('interesse','Tutti'),
                    'stato': 'Da Contattare',
                    'note': '',
                    'data_creazione': datetime.now().strftime('%Y-%m-%d'),
                    'data_ultimo_contatto': None,
                    'promosso': False,
                }
                items.append(item)
                save_prospect(items)
                print(f'[PROSPECT] Nuovo lead: {email}', flush=True)
                self._json({'ok': True, 'id': item['id']})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})

        elif p == '/api/prospect/elimina' and _is_auth(self):
            try:
                req = json.loads(body)
                pid = int(req.get('id', 0))
                items = read_prospect()
                prima = len(items)
                items = [i for i in items if i.get('id') != pid]
                if len(items) == prima:
                    self._json({'ok': False, 'msg': 'Prospect non trovato'}); return
                save_prospect(items)
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})

        # ── Brevo API ──────────────────────────────────────────
        if p == '/api/brevo/campagne' and _is_auth(self):
            try:
                req = json.loads(body)
                sender_email = req.get('sender_email') or BREVO_SENDER_EMAIL or 'marketing@fuerteventurecapital.com'
                sender_name  = req.get('sender_name')  or BREVO_SENDER_NAME  or 'Fuerte Venture Capital SL'
                payload = {
                    'name': req.get('nome', ''),
                    'subject': req.get('oggetto', ''),
                    'sender': {'name': sender_name, 'email': sender_email},
                }
                if req.get('segment_ids'):
                    payload['recipients'] = {'segmentIds': req['segment_ids']}
                else:
                    ids = req.get('lista_ids') or []
                    payload['recipients'] = {'listIds': ids}
                if req.get('template_id'):
                    payload['templateId'] = int(req['template_id'])
                if req.get('html_content'):
                    payload['htmlContent'] = req['html_content']
                if req.get('data_invio_schedulato'):
                    payload['scheduledAt'] = req['data_invio_schedulato']
                data, status = _brevo_call('/emailCampaigns', method='POST', payload=payload)
                if status == 0:
                    self._json({'ok': False, 'msg': 'API key non configurata'})
                elif status in (200, 201):
                    self._json({'ok': True, 'id': data.get('id')})
                else:
                    self._json({'ok': False, 'msg': f'Brevo HTTP {status}', 'detail': data})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
            return
        if p.startswith('/api/brevo/campagne/') and p.endswith('/invia') and _is_auth(self):
            try:
                cid = p.split('/')[4]
                data, status = _brevo_call(f'/emailCampaigns/{cid}/sendNow', method='POST', payload={})
                if status == 0:
                    self._json({'ok': False, 'msg': 'API key non configurata'})
                elif status in (200, 201, 204):
                    self._json({'ok': True})
                else:
                    self._json({'ok': False, 'msg': f'Brevo HTTP {status}', 'detail': data})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
            return
        if p == '/api/marketing/early-adopter' and _is_auth(self):
            try:
                res = _send_early_adopter_blast()
                self._json(res)
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
            return

        if p == '/api/brevo/import-prospect' and _is_auth(self):
            try:
                res = _brevo_import_prospect()
                self._json(res)
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
            return

        if p.startswith('/api/brevo/campagne/') and p.endswith('/avanza-prospect') and _is_auth(self):
            try:
                cid = int(p.split('/')[4])
                items = read_prospect()
                # Prospect in stato Da Contattare o Contattato con email
                candidati = {
                    (item.get('email') or '').strip().lower(): item
                    for item in items
                    if item.get('email') and item.get('stato') in ('Da Contattare', 'Contattato', 'Interessato')
                }
                if not candidati:
                    self._json({'ok': True, 'avanzati': [], 'gia_avanzati': [], 'non_trovati': []})
                    return
                openers = _brevo_check_openers(cid, list(candidati.keys()))
                avanzati, gia_avanzati = [], []
                AVANZAMENTO = {'Da Contattare': 'Contattato', 'Contattato': 'Interessato', 'Interessato': 'Prospect LinkedIn'}
                for email in openers:
                    item = candidati.get(email)
                    if not item:
                        continue
                    old_stato = item.get('stato')
                    new_stato = AVANZAMENTO.get(old_stato)
                    if not new_stato:
                        gia_avanzati.append({'email': email, 'nome': f"{item.get('nome','')} {item.get('cognome','')}".strip(), 'stato': old_stato})
                        continue
                    item['stato'] = new_stato
                    item['data_ultimo_contatto'] = datetime.now().strftime('%Y-%m-%d')
                    avanzati.append({'email': email, 'nome': f"{item.get('nome','')} {item.get('cognome','')}".strip(), 'da': old_stato, 'a': new_stato, 'linkedin_url': item.get('linkedin_url','')})
                save_prospect(items)
                self._json({'ok': True, 'avanzati': avanzati, 'gia_avanzati': gia_avanzati, 'non_trovati': []})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
            return

        elif p == '/api/clienti':
            try:
                save_clienti(json.loads(body))
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
        elif p == '/api/clienti/anagrafica':
            try:
                req = json.loads(body)
                cat = req.get('categoria', 'tester')
                idx = int(req.get('index', 0))
                db  = read_clienti()
                lista = db.get(cat, [])
                if idx < 0 or idx >= len(lista):
                    self._json({'ok': False, 'msg': 'Cliente non trovato'}); return
                c = lista[idx]
                c['cognome'] = req.get('cognome', c.get('cognome', '')).strip()
                c['dati_fiscali'] = {
                    'paese':          req.get('paese', '').strip().upper(),
                    'data_nascita':   req.get('data_nascita', '').strip(),
                    'indirizzo':      req.get('indirizzo', '').strip(),
                    'cap':            req.get('cap', '').strip(),
                    'citta':          req.get('citta', '').strip(),
                    'codice_fiscale': req.get('codice_fiscale', '').strip().upper(),
                    'telefono':       req.get('telefono', '').strip(),
                    'p_iva':          req.get('p_iva', '').strip(),
                }
                save_clienti(db)
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
        elif p == '/api/clienti/whatsapp':
            try:
                req   = json.loads(body)
                cat   = req.get('cat', 'tester')
                idx   = int(req.get('idx', 0))
                optin = bool(req.get('optin', False))
                db    = read_clienti()
                lista = db.get(cat, [])
                if idx < 0 or idx >= len(lista):
                    self._json({'ok': False, 'msg': 'Cliente non trovato'}); return
                lista[idx]['whatsapp_optin'] = optin
                save_clienti(db)
                print(f"[WhatsApp] opt-in={optin} per {lista[idx].get('email','?')}", flush=True)
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
        elif p == '/api/clienti/import':
            try:
                req = json.loads(body)
                result = csv_to_clienti(req.get('csv_content', ''))
                self._json({'ok': True, **result})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
        elif p == '/api/clienti/elimina':
            try:
                req   = json.loads(body)
                email = req.get('email', '').lower()
                db    = read_clienti()
                trovato = False
                for grp in list(db.keys()):
                    prima = len(db[grp])
                    db[grp] = [c for c in db[grp] if c.get('email','').lower() != email]
                    if len(db[grp]) < prima:
                        trovato = True
                if not trovato:
                    self._json({'ok': False, 'msg': 'Cliente non trovato'}); return
                save_clienti(db)
                print(f"[ELIMINA] Cliente rimosso: {email}", flush=True)
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
        elif p == '/api/clienti/aggiungi':
            try:
                req   = json.loads(body)
                email = req.get('email', '').strip().lower()
                db    = read_clienti()
                if any(c.get('email','').lower()==email for grp in db.values() for c in grp):
                    self._json({'ok': False, 'msg': 'Email già presente'}); return
                from datetime import timedelta as _td_a
                _now_a = datetime.now()
                _pwd_a = _genera_password()
                nuovo = {
                    'nome':               req.get('nome', '').strip(),
                    'cognome':            req.get('cognome', '').strip(),
                    'email':              email,
                    'piano_azioni':       req.get('piano_azioni',   'NONE'),
                    'piano_etf':          req.get('piano_etf',      'NONE'),
                    'piano_fondi':        req.get('piano_fondi',    'NONE'),
                    'piano_ordini':       req.get('piano_ordini',   'NONE'),
                    'piano_wealthos':     req.get('piano_wealthos', 'NONE'),
                    'screener_attivi':    [],
                    'data_registrazione': _now_a.strftime('%Y-%m-%d'),
                    'data_attivazione':   '',
                    'stato':              'TESTER',
                    'trial_start':        _now_a.strftime('%Y-%m-%dT%H:%M:%S'),
                    'trial_end':          (_now_a + _td_a(days=7)).strftime('%Y-%m-%dT%H:%M:%S'),
                    'password_hash':      _hash_pwd(_pwd_a),
                    'must_change_password': True,
                    'password_expiry':    (_now_a + _td_a(hours=48)).strftime('%Y-%m-%dT%H:%M:%S'),
                    'dati_fiscali':       {'paese':'','data_nascita':'','indirizzo':'','cap':'','citta':'','codice_fiscale':'','telefono':'','p_iva':''},
                }
                db.setdefault('tester', []).append(nuovo)
                save_clienti(db)
                _nome_a = f"{nuovo['nome']} {nuovo['cognome']}".strip() or email
                _invia_email_credenziali(_nome_a, email, 'Trial 7 giorni — accesso completo', _pwd_a)
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
        elif p == '/api/clienti/attiva':
            try:
                req   = json.loads(body)
                cat   = req.get('categoria', 'tester')   # "tester" o "clienti"
                idx   = int(req.get('index', 0))
                db    = read_clienti()
                lista = db.get(cat, [])
                if idx < 0 or idx >= len(lista):
                    self._json({'ok': False, 'msg': 'Cliente non trovato'}); return
                c = lista[idx]
                # Aggiorna piani se forniti
                for asset in ['azioni','etf','fondi','ordini','wealthos']:
                    k = f'piano_{asset}'
                    if k in req: c[k] = req[k]
                # Genera credenziali
                from datetime import timedelta as _td
                pwd_temp = _genera_password()
                _now_act = datetime.now()
                c['password_hash']        = _hash_pwd(pwd_temp)
                c['must_change_password'] = True
                c['password_expiry']      = (_now_act + _td(hours=48)).strftime('%Y-%m-%dT%H:%M:%S')
                c['stato']                = 'ATTIVO'
                c['data_attivazione']     = _now_act.strftime('%Y-%m-%d')
                # Sposta da tester a clienti se necessario
                if cat == 'tester':
                    db['tester'].pop(idx)
                    db.setdefault('clienti', []).append(c)
                save_clienti(db)
                # Genera fattura PDF
                num_fatt = _prossimo_numero_fattura()
                pdf_bytes = genera_fattura_pdf(c, num_fatt)
                if pdf_bytes:
                    _salva_fattura(pdf_bytes, num_fatt)
                    c['numero_fattura'] = num_fatt
                    save_clienti(db)
                    print(f"[FATTURA] Generata {num_fatt} per {c.get('email','')}")
                # Invia email credenziali (con fattura allegata se disponibile)
                print(f"[ATTIVA] Invio email a {c.get('email','')} login={BREVO_SMTP_LOGIN}", flush=True)
                email_ok = _invia_email_credenziali(
                    c.get('nome', ''), c.get('email', ''),
                    _piani_label(c), pwd_temp,
                    pdf_bytes=pdf_bytes, numero_fattura=num_fatt
                )
                print(f"[ATTIVA] email_ok={email_ok}", flush=True)
                self._json({
                    'ok': True,
                    'email_inviata': email_ok,
                    'numero_fattura': num_fatt,
                    'password_temp': pwd_temp if not email_ok else '(inviata via email)',
                    'msg': 'Cliente attivato.' + ('' if email_ok else ' ⚠️ Email NON inviata — configura BREVO_SMTP_LOGIN.')
                })
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
        elif p == '/api/servizi':
            try:
                save_servizi(json.loads(body))
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
        elif p == '/api/parametri/scoring' and _is_auth(self):
            try:
                _save_scoring_weights(json.loads(body).get('weights', {}))
                self._json({'ok': True})
            except Exception as e:
                self._json({'ok': False, 'msg': str(e)})
        elif p.startswith('/api/run/'):
            tipo = p.split('/')[-1]
            if tipo not in SCREENER_MAP:
                self._json({'ok': False, 'msg': f'tipo non valido: {tipo}'})
            else:
                self._json(run_screener(tipo))
        else:
            self.send_error(404)

    def _raw(self, body: bytes, ctype: str):
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, content):
        body = content.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data):
        import math as _m
        def _san(o):
            if isinstance(o, float) and (_m.isnan(o) or _m.isinf(o)):
                return None
            if isinstance(o, dict):
                return {k: _san(v) for k, v in o.items()}
            if isinstance(o, list):
                return [_san(v) for v in o]
            return o
        body = json.dumps(_san(data), ensure_ascii=False, default=str).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', CORS_ORIGIN)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        return self.rfile.read(int(self.headers.get('Content-Length', 0))).decode('utf-8')

    def log_message(self, fmt, *args):
        if any(x in str(args) for x in ('404','500')):
            print(f'  [HTTP] {args}')


# ─── MAIN ───────────────────────────────────────────────────
if __name__ == '__main__':
    PORT = 8080

    # Verifica directory critiche all'avvio
    for _req_dir in [REPORTS_DIR, FATTURE_DIR, ORDINI_DIR]:
        os.makedirs(_req_dir, exist_ok=True)

    # Inizializza fatture_counter se non esiste
    if not os.path.exists(FATTURE_COUNTER):
        with open(FATTURE_COUNTER, 'w') as _fc:
            json.dump({'ultimo': 0}, _fc)

    # Cleanup sessioni chat ogni ora (thread daemon)
    if _CHAT_OK:
        import sched as _sched_mod
        def _chat_cleanup_loop():
            while True:
                time.sleep(3600)
                try:
                    _chat.cleanup_expired_sessions()
                except Exception:
                    pass
        _t = threading.Thread(target=_chat_cleanup_loop, daemon=True, name='chat-cleanup')
        _t.start()

    print('=' * 55)
    print('  ROBOT TRADER 2026 — DASHBOARD v2.0')
    print('=' * 55)
    print(f'\n  URL      : http://localhost:{PORT}')
    print(f'  Reports  : {REPORTS_DIR}')
    print(f'  Servizi  : {SERVIZI_FILE}')
    print(f'  Parametri: {PARAMETRI_FILE}')
    print(f'\n  Ctrl+C per chiudere')
    print('=' * 55)

    # Libera la porta se occupata da un processo precedente
    import subprocess as _sp, socket as _sock
    try:
        _ps_cmd = (
            f'$p = (Get-NetTCPConnection -LocalPort {PORT} -State Listen -ErrorAction SilentlyContinue).OwningProcess;'
            f'if ($p) {{ Stop-Process -Id $p -Force; Write-Output "killed:$p" }}'
        )
        _r = _sp.run(['powershell', '-NoProfile', '-Command', _ps_cmd],
                     capture_output=True, text=True)
        if 'killed:' in _r.stdout:
            print(f'  [AUTO] Processo sulla porta {PORT} terminato ({_r.stdout.strip()}).')
            time.sleep(2)
    except Exception:
        pass

    class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
        daemon_threads = True
        allow_reuse_address = True

    server = None
    for _attempt in range(4):
        try:
            server = ThreadedHTTPServer(('0.0.0.0', PORT), Handler)
            break
        except OSError:
            if _attempt < 3:
                print(f'  [WAIT] Porta {PORT} non ancora libera, attendo... ({_attempt+1}/3)')
                time.sleep(2)
            else:
                raise
    # Avvio automatico ngrok
    _ngrok_exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ngrok.exe')
    _domain_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'NGROK', 'ngrok_domain.txt')
    print(f'  [NGROK] ngrok.exe trovato: {os.path.exists(_ngrok_exe)}', flush=True)
    print(f'  [NGROK] domain file trovato: {os.path.exists(_domain_file)}', flush=True)
    if os.path.exists(_ngrok_exe) and os.path.exists(_domain_file):
        with open(_domain_file) as _df:
            _ngrok_domain = _df.read().strip()
        print(f'  [NGROK] Dominio: {_ngrok_domain}', flush=True)
        import re as _re
        if not _re.fullmatch(r'[a-zA-Z0-9._-]+', _ngrok_domain):
            print('  [NGROK] Dominio non valido — skip avvio per sicurezza.', flush=True)
        else:
            _sp.run(['taskkill', '/IM', 'ngrok.exe', '/F'], capture_output=True)
            # Apre ngrok in finestra visibile (shell=True richiesto da cmd start)
            _sp.Popen(
                f'start "ngrok" "{_ngrok_exe}" http --domain={_ngrok_domain} {PORT}',
                shell=True
            )
        print(f'  [NGROK] Tunnel avviato → https://{_ngrok_domain}', flush=True)
    else:
        print('  [NGROK] ngrok.exe o ngrok_domain.txt non trovati.', flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nChiuso.')
        server.server_close()
