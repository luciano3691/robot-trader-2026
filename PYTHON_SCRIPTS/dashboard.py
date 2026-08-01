# -*- coding: utf-8 -*-
"""
ROBOT TRADER 2026 — DASHBOARD v2.0
python dashboard.py → http://localhost:8080

Tab: Home | Servizi | Parametri | Azioni | ETF | Fondi | Esecuzione
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import json, os, sys, glob, subprocess, threading, secrets, time
import smtplib, hashlib, string, csv, io, base64 as b64lib, tempfile
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
FATTURE_COUNTER = os.path.join(BASE_DIR, "fatture_counter.json")
ORDINI_DIR    = os.path.join(BASE_DIR, "ORDINI")
PARAMETRI_FILE= os.path.join(BASE_DIR, "parametri.json")
SERVIZI_FILE  = os.path.join(BASE_DIR, "servizi_config.json")
CLIENTI_FILE  = os.path.join(BASE_DIR, "clienti.json")
BACKUPS_DIR   = os.path.join(BASE_DIR, "BACKUPS", "clienti")
SESSIONS_FILE = os.path.join(BASE_DIR, "sessions.json")
PROSPECT_FILE = os.path.join(BASE_DIR, "prospect.json")

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
            return json.load(_f).get("admin_password", "changeme")
    except Exception:
        return "changeme"

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

def _rl_ok(ip: str):
    """Azzera i tentativi dopo un login riuscito."""
    _LOGIN_ATTEMPTS.pop(ip, None)
    _LOGIN_BLOCKED.pop(ip, None)

# ─── VALIDAZIONE INPUT ────────────────────────────────────────
def _validate_str(s, max_len=200):
    """Tronca e stripa stringhe in ingresso — usa per tutti i campi utente."""
    if not isinstance(s, str):
        s = str(s) if s is not None else ''
    return s.strip()[:max_len]

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
    except Exception:
        pass

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

ADMIN_SESSION_TIMEOUT  = 8  * 3600  # 8 ore — scade dal momento del login
CLIENT_SESSION_TIMEOUT = 24 * 3600  # 24 ore — finestra scorrevole sull'ultimo accesso

# ─── LOGO FUERTE (base64 PNG, embedding diretto nelle email/HTML) ─
FUERTE_LOGO_B64 = (
    "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"
    "TkSuQmCC"
)

PWA_ICON_192_B64 = (
    "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"
    "gmv02of5AAAAAElFTkSuQmCC"
)
PWA_ICON_512_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAgAAAAIACAIAAAB7GkOtAAABCGlDQ1BJQ0MgUHJvZmlsZQAAeJxj"
    "YGA8wQAELAYMDLl5JUVB7k4KEZFRCuwPGBiBEAwSk4sLGHADoKpv1yBqL+viUYcLcKakFicD6Q9A"
    "rFIEtBxopAiQLZIOYWuA2EkQtg2IXV5SUAJkB4DYRSFBzkB2CpCtkY7ETkJiJxcUgdT3ANk2uTml"
    "yQh3M/Ck5oUGA2kOIJZhKGYIYnBncAL5H6IkfxEDg8VXBgbmCQixpJkMDNtbGRgkbiHEVBYwMPC3"
    "MDBsO48QQ4RJQWJRIliIBYiZ0tIYGD4tZ2DgjWRgEL7AwMAVDQsIHG5TALvNnSEfCNMZchhSgSKe"
    "DHkMyQx6QJYRgwGDIYMZAKbWPz9HbOBQAAD0+0lEQVR42uz9abAt2XUeBn5rrb0zz3DHN1XVK1Sh"
    "MBADwQEjKQ4ARUqiQhQhEGxKFEWakjWE5Xa3Qu5oR/ePdrsd7pbabbXd0VZbcsvhCKkp2bLCUtuS"
    "qMGkRBIkSACkCTQJEDNqHl4Nb7rv3nMy91qrf+zMc/Lc6d376lW9i1f7i4vErfPOPSdz5871rXnR"
    "Yx/58ygoKCgoeOOByxIUFBQUFAIoKCgoKCgEUFBQUFBQCKCgoKCgoBBAQUFBQUEhgIKCgoKCQgAF"
    "BQUFBYUACgoKCgoKARQUFBQUFAIoKCgoKCgEUFBQUFBQCKCgoKCgoBBAQUFBQUEhgIKCgoKCQgAF"
    "BQUFBYUACgoKCgoKARQUFBQUFAIoKCgoKCgEUFBQUFBQCKCgoKCgoBBAQUFBQUEhgIKCgoKCQgAF"
    "BQUFBYUACgoKCgoBFBQUFBQUAigoKCgoKARQUFBQUFAIoKCgoKCgEEBBQUFBQSGAgoKCgoJCAAUF"
    "BQUFhQAKCgoKCgoBFBQUFBQUAigoKCgoKARQUFBQUFAIoKCgoKCgEEBBQUFBQSGAgoKCgoJCAAUF"
    "BQUFhQAKCgoKCgoBFBQUFBQUAigoKCgoKARQUFBQUFAIoKCgoKCgEEBBQUFBQSGAgoKCgoKzSwAG"
    "2GneT16O5ViO5XhvjofACU5ZmGVpZmRGdjYJQLbe/P4zJf2dzGHuBCImIiIARGSA9z+U3+hOcHYC"
    "wI5yLMdyLMfX+Qiy/D8HnIxA5EIgYjMyY5iAyN2NnIXE4WeKAOixj/z5M6b+KzMzRFVhBoCZiciJ"
    "Vs0WIy/+q4KCgnsJ77RRAkBQdiaL7KbUJFIjdiZ3FUe0GDm0lpzO0PmHs+aQUgURgyBEBu6kv7t5"
    "Zk7PPMEA3EFuZQ8WFBTcMwbI3qBMAMj+HrhRIAERhc5p4Q7A7MyJq3DmTogZZg4QUQiBiMzMzETI"
    "AAYZGWfdPzuHACeQl2M5lmM5vq7HhR8FIJARnBwCBztcieDuWZ8lJmrdYGct6nrmCEBELKk7iMnd"
    "1AxwJiI3JiOAfbj0zARzYocB5ViO5ViOr9sR5DlnxQC4M4wAgpIDMHd3MJwJxOQM8rMWATiDBABz"
    "6mO/ZuZuUShGTqnJ3raF7g8AzjkMTF1wuBzLsRzL8XU6wgFKTjA4AEYih5CTgwRM7C7qcDfPVsKZ"
    "k/9njwBUVUQAMrNAxEFg2uztaDsjJMBBxnm1u2AKZydcMUjLsRzL8fU9Wg5DOgSAkpLDnOCsaKUa"
    "U7XFHMzc3a3XWgsB3AZE5A4zCyJCvjvbuXntxXbvJiExFGTkyK4gAGLHZOQWFBQUvJYOCzIHG8Qp"
    "ZwGBXAA0ppPNC5OtSqr1XqyBiPSMGQFnjgBI2OBmLsIOVVXy1O7d/OQnfuH81kSQYIlI3N1JAIif"
    "tnSsoKCg4C4lAREM7IgAQAqATJz48aef+t4P/4G3bj9EBHUyuMKF2b0QwMlX1sFkhERIF8+tnd8I"
    "ARVciShXivVGVSGAgoKCewX2gQxiwICr1+p6FANTcs9C3ymnsp8tN9CZIwADCDBygS8q7BgqSAGB"
    "0AKGnFsFKVuvoKDgnoorBZg8CgE5SAlhcBBjJFV1V2diJgL52QsDn10LwAiyKLYmc23dApHBGpDA"
    "DAQQe+lnV1BQcC9AILgDCuKuRJUM7oBoO9fUuBoYzExCUHNXgM9UB7YzRwAMI4ghp3guDSbmwMxw"
    "BQeAQQwSgHNEvqCgoOB1hyB3eXMB9f4LIoITOTOHEEyCEbsbXJErV8+WvD2T2j878YJlneGczMwA"
    "ytmfmUXZ0Un/0pWwHMuxHO9FN1DJvmjvfu/k1qKYyY3MDOYAmM+cvD17WUB+MEpCRuSdt8dAAhJ3"
    "zlEX6a0EQjmWYzmW4+t3BJBd0EZZm2Z0vYrZDKYwc8+tjMWJiIm0xABua5I4ODdZ7YV+1/7BCAIG"
    "Ad1xcSusbMZyLMdyfN2PjEH+T9ekMjeJyBYAkbMLE0AOTqpEsRDAsXDOHEq9NcWe3UApUE75Z3eA"
    "hjlAJQ5cUFBwLzwWB6RPHhbAEAYSOcjIHTAHMVdnrQ7g7IrORWiXAHajrvP2YokXnaELCgoK7iUH"
    "0EpBUue06MwCcoZxZyKcuXyVojsXFBQUvEFRCKCgoKCgEEBBQUFBQSGAgoKCgoJCAAUFBQUFhQAK"
    "CgoKCgoBFBQUFBQUAigoKCgoKARQUFBQUFAIoKCgoKCgEEBBQUFBQSGAgoKCgoJCAAUFBQUFhQAK"
    "CgoKCgoBFBQUFBQUAigoKCgoKARQUFBQUFAIoKCgoKCgEEBBQUFBQSGAgoKCgoJCAAUFBQUFhQAK"
    "CgoKCu5zAvAew1fu+fnkX8xs34nte+XOLvC0f56/9IQfkt9/wpXcd3X3duUBDJf39TyZxYodtTh3"
    "d5XyPVLVM/5I3vP9cFce5PsY4T64BiI6m+czPLHFTmLmE26+Qz/nzs5n35kc/4H73m9m+145avHz"
    "7/mxOeFl3n2NZvC9i/M5Zg2P/9c7+97jV/jOvmvfXTjmjtxzoXn8uQ0X/LZb8V6d/9kULIUAbnPD"
    "Fr+fnTtHRFkg7jul/KKZhRCOFxP7dJDTXtriz4fS8BiklLI4yxLttoJm3+ff88VfaOKLM78t270W"
    "e/Kuy+ghwRy8xjOrjS1M4Xz++x6EM8thB7W3+5UMvukJ4AzemH0y8dAzzI/ubdXkg+L1Va7PbT/n"
    "KEI61frfw5tyWstjyIiv5rSzhn4M175GZPBN8XhmNeggXZ1Bwfpa37tCAK+r8L2HWv9R1skJTeCh"
    "lncXl+W2ezqf0qneP7zqfNrMfK/Wf9+S3tbDc7fO8+RC+Y6dTgtT8uCmOoMP4EEOOHghZ5m37mOt"
    "/35zAR21ye6tynPUOZzwJA8KlDsTHEd58I/66qM0tZMIUCISkbOw/ieX73frPIkok98wEAJgsSCv"
    "nnJOdR/PjkV+6L5dbO8ze/4LNej+poH7xAWU0yEWT8g9DEKmlBZelEO3zkJHPl5tXLgUFurSnV3R"
    "4q/2LdHxQd1T6fLurqo5bHBQSz0LdoCqHhTEr7VnZuH1vitfZGYHN8DZ9H8OZfpw/+wLjeQsphjj"
    "mTr/vJPfIAGA+8QF1DTp1u5sb95k70XeZIsMOSfQqpLhh91NOkQRYcBOSUe+vbFprlU8XO+bzdvd"
    "fKoEIoL1CaO0/0w68UFwJyGMqjidjKrqTu5XSrY3a2az+bxtASZyJ8D88CtlWpxDHeN4PBqNKuEj"
    "H4BkuntrtrM7d3cicTJX67WnhcCywb3gfEecjBz978vjq5fC5srM4ypOp9N8I5gZDhy4CAeeu/Iy"
    "fOmy26f93V7eDc+ciUELjq+qqqqq8XgEBjmIkMXIQpgc5HM6Abs0re7tzXfnM1M/gxp0VgIMTkRR"
    "wriuxqMQAhPJUIw2rd7c3dvbnZ0xddIvbG/F0NltJ98GhQDuGdq2JY5/9a/99a8/8azEymHkLRFB"
    "yYmN8oNvANgZgJE5GQ48g+T7n0e2/FifggMI6Uf+yA//9E9+TFWZnDiYGTG7g+Duvjtr/8O/+p88"
    "99INc1Jr61h5ciN0p+ScpQC7gcyJzIVZdm/ceO+3v+s/+j/+b+bzeV3XQ63kUMVwn4xj4V/+xG/8"
    "9b/xX507/4A5EEg99QTAA5I0ACBJKQURMh9F/jf/9J/6yIc/2KS2CgIARiBywB3E5nBi+Vt/++9+"
    "6tOfY6lbNQ4sbCklorikte7D2QFy6oWmE8wJ5LZKADy8Neyn42BnB1mazb77Q+//3/7l/6Up3Eyk"
    "+zRzDFfra48/9V//nf/uc5//4tra2iJvnUiOUcT7Y3eSmVYcEOY2JSYPIZglVR2PxxsbG+fPX2w1"
    "CbG7b22d29raqoQvPXBhY226vbX5pocenEwZnmkXDMtLZqosYpblvuWzMoM5JMp/+3f/yS/84r+q"
    "6mmj9to/Yaf7CgEpHOxmFkAf+yM//FN/4qOWZsxZMwsAHJ4c//5/+B9feeUmnYbz2QGy5V+sPLNZ"
    "Ycp72IYb4nhX50LEm5np/Cd/4qN//OMfnTepqgIda2b57Ti7EMDrgRjjlZdv/P9+50uf/MxvJ2Mn"
    "I2oERM4ONmInA4y8IwDl/QTQ7yfeZwewdxKvf+BXjlmL3vc6o33LWx+78tK1C+sTCMjUhWipVNIL"
    "L770a7/x6d/90pOQvL0seMyc5AQ4kzPBGAaYwlMSZramdbXrN2eTmmezWVVVp7JJG/XHn3j6Vz7x"
    "61KtN64sAkqdI8i5l2WWnx93coCdtZlfOr/xfd/3Pd/13e9n8pSSiFDe8L6UDW3y3/n8F//ZP/tF"
    "pcqZwE6kAMgDwHAGGWCAOfHKA9m9flDE8IAGMBC4JzqqJzdla5n5xRdvbExGdRUW6v9i2bLG38zb"
    "f/GLv/TZ3/niZDLJavuJCIAsX0V3Rf39NTMiJyK3pKoiHGM1n7UGDyzz+Zw5iIhru729/cCl8w9c"
    "OP+Wx970lrc++t7v+PbvfO+3XdjezKzKxMycqT2lFELnkWAGAbfm/ju/+3v//Bd+2SHq9Nq7Ok9H"
    "AAwkMyV313PTtbc/9tj16zenY2G2xcIS6MaNG7/1uS987ne/JEKn/HxbUd1W5Xv/tB5lza88v0Q+"
    "fMUM0Nn3f9/v22uUzFIyQpelfVs1qxDAvUQyTabOVNejEJioIfMs8zUTABk5xBYWwAldQFk5zkRw"
    "IgHEaK68+OKzzz5r2xuT6Wg6WY8hK+xImkIIo9GoqkZ1XcfRmIlUW7FwFAE4k3tFRLs3bt66devJ"
    "J5+cjmRzc3NjY2PhOb0tE5jbIqm/Ho9GQYjZqHW1QwmASIiZnee7DODGjRvPP/98ELuwtVnXdeiK"
    "A7IABYEkUFVVMcZRPeUYWm3cW2Y+igAG62wDJjhcp/Ml3ZyUAIjdNXmaa7KXXnqpmYzW1yaTyaiu"
    "6+FqucMdqr6xsTGdTkejkar20RE52rWyQgArumcXdjJ3B3VOMFWdTqfuHkVGo5FIBNDszQA8+dTT"
    "jz/++K/++ictNQ89cOl7vvf3/diP/bE//MM/tFEHMzCDiLMe6q5EpKmRUAGoaxqPx6PRyKjiIK52"
    "Shl9yjRZOo0F7AgUjMwYTTPL++eZZ56bjGV7e3s6mQRyJ2KRGCMzSwzjujrl+eAYAti/nZa6yuEE"
    "QCTuuiQAk+eee+7ZZ5+d1NXa2tqojrjfcT8QQFVVo9GoqioQqxuZkrlQOHr324n8+2QOdsBo6JQ4"
    "7kiOtk3PPvtsu3P94Tc9NBmvORxOzCDuzieEwMxZvzg+CGwOwLIrOZm+8MILk5pDCJPJZB8BHBOn"
    "yn5pEeneQ6SqznYUb6iZqwYKVVUR4aWXXnrmmWc2N8ZrozrGeFB6qMPcs8aqbevkXTRYT6xUZpI4"
    "ylTH4lxPdhdSYmKC3Ly18/iTT2yvTx++/OB0Ot63RMzIPgD00ciBxD8mSfE226ZzIoFZugLAQJy7"
    "UwhRIHamEAKciSRWcTyZmtkrN/b+h3/yLz7zP//OP/r//uOf/PiPffRH/8A8QQJyyKdttaqChODu"
    "aqRZ0yVy99Qay10InNwtOEFVFc4xiER3v37zxtPPPbu1VldVtb6+SSwEgGDuenQV5DGf76seQtCh"
    "xuJym9nSSlvZJw4nYsDRP91GRsDOzs5TTz21Phk//PDD49F21v3vV/Uf90caaEpJVc3M2ZjAzCTk"
    "uv9JNcpenYMehlXlbqk13AmuX7/+0ksvjchUL+VzI8S8z1W9bdssa9ydmZj5KHkiVYRq22rTNLO2"
    "2dvbu3LlysZ6feHChRzfPmFygrk58axpkmnHK2YS2A+4j7NuJSIpJTMTJjO9evXqlStXCNvt+XOr"
    "NVP9eVIXMTMzliAhOKWkysTwQz2kttTRfKjH8RG63mldgrWmxh2zWfPKy9cCbDbbSNrESvYJC6K+"
    "dgHuOVbElO++H+3cJR9qnTxglN4pRDB3S0ZEBDEFkzCxujVN4+4KZ3g1mri7mjl4vLbdNM2Tz7z0"
    "wpV//aXf+/Ir16/95E/8L7KzI1Af/nUjEJEQYHA1c4aE4Jb8tfVDn072hRBTO0tuBLj7zZu3rly5"
    "grS+ubm5ubk3qsYiQrLMjr2Dk1/4edj5CCfV7a2Wg89ODgns7e299NJLtrlx8eLFo8r4CwGcJQzy"
    "GlmEyM3cVSNHAgHUPejD3yBdvGplo+R7LE7LZ98J5CQ4vKXXIecCpNSm1Lp7Sk1KaTyuF38tQp3l"
    "K0IhuqW2bWuusmIO6oUSiEBt2y4s5RijiOzNZ+trVW7VcGhZ2VEWgAEhhOyoaUzNDOqSHTJ5idD/"
    "CsoZk+xMcBERkcwZy75jq+k0BjRNY2ZxFDkG9TRIhyfKq764ETAQDRaYBvJlaKQj3wUHCC6nkVaq"
    "rsmFBEDTNIpDMmg7/xXB4MOHP2ewAMemyXbb5hCxqG65EsLdVXOcnNGHFnJyoRECkRN29+YhBCJq"
    "2+Tgqp4SVwT78tef+Kv/t/80KX7sYz86HUcJHELotRNiyglFpHB3MtOwsp4nemBeW3+smxkIIIlV"
    "ICJq2xZAttFFBNxpIXeaZT8I0eSUP2enfRYtLZIOBMfVuwyfIIeDsLe317Ztl8tklu9RcQGdbSOA"
    "Kbm1mhjCDCYQczLLap3B4MYAG+DIeUHDR2Gfl3OfYCek0/hArYqxM89TMrM+M7CXEapN0zRNEzky"
    "UfacGJmxZX8Tec5Z6qq3zLrPAZBSOqoU6PaRALO2bZumceEQAkkn0MnR6+k5NGJEwszaaEotO2V7"
    "ZbW6reOoRRZRdmq5e9u2yVoSizFqa3CQYxADwIEsGgCHO38Wb6bTOrgpZjtGODaaVFVVk2q1lBE8"
    "CAP4sGZ7Uf2wqOo6es8d4nR2dzgrdcERZP9CEEtqahSECE4wt6Zp69FYVVlCZDGz2bwxsyqG0XTj"
    "pas3/69/7T+bzWYf/7GPbkyrzemo9y6Zg7PlFkJos3/SThekpdNmNvvpLIAYmEXMaT6fC7Mm12TM"
    "YXc2b9s2SkUEIqaecu3UeUzp4Bk62X45P3AqHm1kDLM8Ce7k6q7unll82Fa29AI6o1DTTNRVVYGC"
    "kfVaZqd79qooctBnqALRPndGp3L2PsEuLc8pCym6/ZGIUkpZ5RERZna4G3VGvIOZq6oKIbi7uRGR"
    "c7ZLBjZKZ6ksM8qzETDUVY83RA4Kq4UfM0vqZcAT1F9/ZwFYLwRjjFXFuaJiX43rPpWzc2uYcQxR"
    "oqFNKTHFoQWQ4w8OAVm2wLL2BmcsvbTSG2FGC/+u00lWvn/gSSSkZr7grRgjh/5hpt6F0H9j1voH"
    "un9+1I9VS7NYoRUbdLmwBlPNH6hwMst6O0sAkVrr5iHGiiiHi/sIJCRwTlJwBA719Ru3/l9/429e"
    "vHD+h3/ow7u7sypSCELEBJAjsxoEzMFdT5Upe3oxdrq/yOqzxECmwiG7elS1rmsnJPUopG5GMIKZ"
    "yWl7T7nsj+GRU7eRjX1hR3YWp4HpyKc17+Xl7wSKMWZ7d9jc6T7GN31wQ1iyHr3QlI/q4t2nlCjY"
    "wa6ewL60J517TzQb2EDu2XzvXz/JsZcpy96HIOalzwF9w/qVji60dG4OtZUcgMpva5om08bBSsvb"
    "Rqho4C3LSu7+Tg+Dc8jvyeIsu5sWot/MQMRM++ykxZ8MMinpKG++KcDBwEmdJTrdtqXl6dY/pTQe"
    "jVLTuiV2pJTMEsvgShde/p69hkuaF/wYWjU4SQBLMnfKlXrLTyByIld4a5p3pxODRM1aTfkdSRti"
    "N0/MgCtMGY6cOekuIgYCh1eu7fzc3/17X/7q1+ZN0/n9zAC0rWWX4ILF86YlkvwLwO7EHNwpJXMn"
    "kUgk7nRshuuRtmPeMIuESNyu8RHl/InV7ZEtzpz0ycS3NVyox6Hrb07JnEgWP3kPGJY/i8f5qN3i"
    "RsPf3SmvmIjk681khrNXbVcsgFfBeCIL9ZCZU2rcuyTr3p+Y0/p6Q96H9au3OQJdMxzzlEWJmhLk"
    "jpMInF5dSPp1hN1OW+oKZ4IsqLtzBJMtOKn3+5svHXQA+ITr74Bpa8QszswhsmBZbn1XlB4iSmbk"
    "ntPz3RKIRMiSqhsAEq65k5WazAEncngIwV2zzdq2rYggOy7IuiJEMgI3KVufltr0pa989Zd/6ROb"
    "0/Gli9siEqsqC9+2bc1MwJZ0mEY/bF+TuWRh8N2xCKuqSnvg6C7lC9E/rup5avOdVWvznV324aCT"
    "GhZHnbBwVDOAhaM5zBOcJVDOthsWEloX8+cTPr9wclCMMTsz3fMtu/MuLIUAzhZytly2nQWUUjID"
    "kdexSin50o62ZVIKE6yrAzjJ0cA5wTibkPkJpN5vfkIZ5LTSpuHV53icMQbhtk0CYmL3xERM3sUi"
    "gD5mCvS1wfCQOeAk6w+YCAkpCcMTzFVbdxqad6/W4hSBag4faGpzibEpcZegSG6qqas1YSIJlbur"
    "GmAppaqqQKKqB+sh+lqSwBxgKiN74cUXf/3Tn/quD71vY326se6W3MnrikIIAiIREMycBjWp1ItO"
    "cxMRJsqepux0d/PT+oCa+Z6IMPkgvq2a0lG9lVJqUmo5hhA5gIndYW07P7o+63QBieTuxFWM5tq2"
    "bQjRnVKutT5iv53oyXXPdX0DuwrD4FCJAXyTKPh+G3nn7mROIlHYLGlqOadpZ1sPCu9SUwiS68lo"
    "ED07/giyZj5fuFAWnnVV47BaB4vcnea1LeX3M3mDIktVVaZtSsnVwdll251s6JsDONy6dI6Trj/B"
    "GElT6zpPqQEshHDaZPPbxJxSo6pELoGTtgEC17adL1TF3s3COcDTzBqWSETC0g5bhA5JnqzjAQcz"
    "NymJWxUjc3jqmWcff/Kp7c2Nuo6bm5ssQkBq2pQSByEhIQZblwnj7GTs7GSWkLRhCAmExMlgUGuP"
    "EtxH3i/mENidVFvVfJokknttHVaIR8FdQeyq5kSOyBJCyCxPvlT++cSqzTJdh4xJUtK5KjMAExG3"
    "bHwawUAM2LCtix+xT/o2ENb1iaEc2qKmaYho0XBl4Qc77boVArg3Cv7CvOS+3VmX7dj/63g02pvv"
    "WtIg5KqR4GnGzGnW9PuMvAt0ivOibrh3Thx7JOhoVGXrO9sBbWpjiIteNAc1mjeaCy4rv6bt7s7N"
    "URXcNDVtLt9dKlldmIEsm/AnXv9cS+06j8xC3sz24E6eved8ZPHH6VxALmznzm2/9bFHhbiOAlNz"
    "HVW1aquqYHH3+ay5fvPGjZ3dq1evz+Ztcq+iVEHMkqqLyNAHsuysQZ3HKqchxbq6eu3a733pS4+8"
    "6aHtrY2NjS0imIEcozqCeHc2C6HKIm9BAPk4ivU8qeTiBjV1FQhYTqsTuGtSzYFTAuVeTsQuOcrq"
    "+48MjDhQkKZRdzdLGXeowRyc7qDzSmQ2m0klMN27dcvavv9uH+BdJYDD90muAsuB/6Xh5M36dDyc"
    "tHzWJgwWAjhcqeQT7+umaciZCVC7cH77e777Q9PxiAnMkJx7Q12GsmUljvgUXhjyUSUxxmxIhsj9"
    "BjpDy+X0WqWC+wlSRgKLpgaGjbXJ933vdz/0wEV4gilR1zaJKMt9AOzugxyhE56DAcama5Px5sZa"
    "drvfPSPAhKHJLm5vffeHPnhuayMGYtC4ju18lrcNM5OEtm1v7c13Z/Onnn7my199/Mtf/vKtmzfH"
    "44n7wsAZ1rKiF9yAexSKEjTNiGh3d+/pp59Natdv7Gxtzje2IuUwwGxurHU9giUAjsQAyBbHpt3V"
    "lCgESp1WSzE6mCCncSpaXddNO3NPcHhf3q3N4e212WHWgsnd2tQEiTmQW1fVoX6Z05IBTLc3ph/5"
    "/t83Ho9FKKUUgsSutD4dogs6HXWxB0P97k7wrY1RTn8YOn9KDOD+cRAZOAoDNtvd9TR557e8Y3tr"
    "vRIOQswIvKj+c+fsez7FvTcCiOu6yt0aRCRIjgdCztIWstcs/csPkM3KU4e8DpSaxsje8uZH3v62"
    "x4RMyINkB4IQdblQTgxzIT+5K8tACcTM5OqmVZDAEpiZwhFXfDo5RNmfPdvRdm9cycZ0vLE2qmM1"
    "mY7ZLXuh3UjVc0cEB33w/R/4+jce/8Qnfu0Tv/rJ1CSWEEJM3kUMlglgXUchqGm2HVVViOapfeXa"
    "1b29vd3d3XnbEKFtEKLESuatMQyDpKyhRAshhCBZTDNTLmja2dsLQqe6+Sklbdq6rquqapoGQFVV"
    "K4WBq4hBzGzuGilORhNitO3cj2gMckwTi8PH0rkGat73be/Y3t52z/nfEkRSarosZz9pjOHQKt/8"
    "1I/H40W3lXwv7lf/D96AWUBE1LZNCFzXFcjMW23mk3Mb25sbIhRk2SF20bIfKx1D7VDpRl17SCix"
    "CF04t5kbTLoZ9YmaPmQKt9fjYk8fBqBeLnZZswTylcdoUaPLd0QPbashhgDevXXDLLk2o0m9ubE2"
    "rmOuce16sfUWAJOffK2c2CWomZtlUj+3tb2xtXWcSD+lNRRCiLEWEXetAi5dPHd+a3s6GWV5goHt"
    "kqzV5PPWHnv08sb62jPPPPPVrz3RpDSKtTYtSxcy7sLFffpKCLkGNXEQZhGr5/P2xo2d85tbs929"
    "3Z35ZK3+yT/+8Q984APXd3a/8Y1vXLv2Cg5Lfc75vovc3Kqq9vb2nnnuxd/87d89lcrUts3m5ua7"
    "3/XON7/5EVgysxhjSukopdjVwG5gFrD6he218aRO6oex7in2Zt9kyckNqdm9cW1ra+PcxYvELgRm"
    "dughLV78OAIw6MJZtHD/QpiZL1y4MB6PFzUi97E8vB8IIBeV7PNsWNc6qktPzDX0RjBPHINa454g"
    "MEvTtXr73MZDD1zc2thkkLtzEHfy7ILookYLKd/nbARqNeUsN6bAkK6ylDxGGdVxPKpCCLya7WHL"
    "tu/J+8Xv0l0GatGQZ159q6+DIo5PJEyXmZ3kfcuI3AeUli069djvIh+Ed7OgYwJxm1qJDPhoXG2s"
    "T9/8yEMb07WupsHZ3XNUzt35VGKCoOpdbZGriNR1PRqNQhW7p9iXNcx+0pVYIZhkMGd1MrPRqJ5M"
    "qwcfOD8Z1yFUcLY8EMYdZK7J3efzuUj84R/68AvPX/mP/sp/Mpqsa9bXKS2Mxu6edKelBHOYmQeO"
    "TatqNNtLe3t7mpoAJ/P3fds73vX2tz713AuPPHjuxRdfSClpavfN5hxOjCAWd2cOv/obn/lt8qav"
    "L+l7UvFxIz8lpJQefuj8u9/+6CgCQIyRWPqN6otnMCcY5Ww6BguRajJL43E9nk5iNbEco4WZw5k4"
    "J9GiOtLhs9rrkBYFd0zrW5sXL164fPnyeFS5pX0uPt9/W23Y7N27xuCunmAkIm3bjutJSilHpmPM"
    "26bmrvctnfCxKgTwTWICcJfzSUTMiDFMx/WFc+e3tjaE2Y1I2J1A4u5GBiDHzgYEYE4gYSJSdzIi"
    "EnJyN1VlgQiJ9On/1iUYLJqRdSLo6BaYQwF61zN5jmeUIRv5EU5bG+x+PuUjkVJS9ch9VyaR9fXp"
    "xtr6xQsXInfqv3Ule+zuR53toY+lE0IIuTlgTlvMpHL7yt5T6MSUg0O5zqAOUlehrmsJFawrNQfB"
    "oYTgbmtrY0DmDd75rndMJpPklOZtiNGhXeLK6jmk1OQGUNkLZOYEgXDX8dATPMBDEN+cji9dPDep"
    "OKXklnDYGNvuPzkAUND57a2TRWoOUb0rsc3pZLpWTyebHMSNKLdch+X2Ko6QHxaGsYWc0aueRpPx"
    "2sbWeDwOMfZ9QfiYm3hbL5+DqqqarG9sb21tb28Hpqad5VZ/i52z2Jv9OJADBCDIUYQYY2oUACmc"
    "xF1JOHfBGs5kLfMA7hf57wzPR/ekrrkZAsUY69ysKqsH3k3wU/iAAJY+lVYTB2Jicet8FyA3oZGs"
    "qh59NwpHAYDpdNrM9pjNFEwUiMfVOIRQ17UQIzfN7voN3UkPlvl8zkFyGt+wbLVXcv3Vqm7mjFw2"
    "auRdJbawDGrXsishu7MYjr3ZvBqP16brm5ubV2/sQW3Ql+KgY4T7ZGbN7vuqDj0ftAtnOjOvr69f"
    "Fk7nz5mZW9q3UCtD6kmIqDW/9DtfvOPrjjFubm4+8OD5c9uXJAY4H0MApCLkTuRkJByq0dp4LcbY"
    "FVgOBq+f9jT6imKp605DZxFOIWbzZNCoww+qJoOCCfXExK0rkVSVuDsv5q3S7VWNQgDftP4iszzh"
    "liHMgYiEQwx1JyCWRTV9y5puy/LKXiJEzq5q4y75LZd8dp6SvgjA8QZoJ3Kq5W9me6bKnlS7Onsz"
    "IxI4OzF1DqaFO+/Uq1fV9eJG53zcbHbcrTgedUFpy05215ydYhBZyIph22wQj8axdUzWptdv7jTq"
    "o/F0Npt1E+EOPpBSuUEtMQmL51kXmcK6hmf91OvRKEq1BU3unhPbh2p75oyuK5FBRFrztbW1O7OZ"
    "8+fUdb21tXXx4sVQRYIcSgDuHhhITK4k4mQGd5JKIhFyaQfhNkMsjjmXrJinVgGEWOdeqNWoXjI7"
    "HRJe6Fu8Lv+TKRgwqieAgZgJlpSZwbTa9rykgd5fYA55FqJ742qqnpKp9uPkh4bmkS3hu2cs5eRF"
    "FsBywwgwL5oJe5+ZUaT+PpdCneO91jUqaNREIljAB1Lj6U4Mp9xmZtgjKdf03xXvmTAxESM3oFmS"
    "/TDg3usBDrCBZnMLNX/+C1++eWunHq+3bctBHLb8ExpcM4uqAkwEMxXGdDxiLLtCYak+oxJAwkGe"
    "XDTC6/a8gRkM3BkLLtry5E7mMcZYVZ2B7ABMeseLAQ4XOAnDA3JSNfpcpb7X3tC5dNqTEQ4cKgO1"
    "TXJiYsntUYW7Shxfmt6Dp36VEgxIamAKRElNQEGIWfq5oW8gpe0N6ALqEiTIiSBExBI5RJA45YqC"
    "xYhytlV5REPnOAl3j5M5YNaSg4VXdYfDtJE3NoTZzNr5DLnfejWKoZJ65H17UADq+2XjKQgeK2Pf"
    "h3bAXbFg3Iex1q4TmbNQLhm3riiqayjl5ERVTU8/f/Pnfu7v1fU4xHpv3tR1bZYWAdRe50BuUugG"
    "CZGQ0qxZm1Ybm+uAhcAi5NwtDeUG9nSwy8ghTPDqOfuACkQn+bNjzmzRe/V0q0/YmzfJqB5PpZ5w"
    "iJDue/QQZ1q3uPumuOV/FeHWoQBxyLRBhKQWwhurNvMNRwBqbX44OYjEwBKMWB0IFThYv0X2bUxd"
    "VBev7jAH1EjIhSNguSV8X2pYnD+HWmBslkKohOMrV689f+XlpklqfOHChdxHwd3VQZR7u+FU+bIM"
    "S838TY88vDEdqXoQyp6QlFKQfi7Nq3YhmlmuUjYQKDpFQ+hmu/WMnztJJcAdO7v+N/7L//cXvvgl"
    "J1HV3HB4lbOWm2oRxTU1wC+c23rggfNEkEpiJfuYbJgjcDD8m8MAy2SEO3R50aDX6Z2sXj7HLqzD"
    "K9L41B/oHKrR8y9cqauRQ+bzdmtry11jjJ4Uy5yqlRqLA7uInSAiZqnrYtvMGfS2tzwaJc8nsNt1"
    "qC0E8M17wTGCzBWt6s7e7MWXX2HmVtPurNncXM8CqEuMY+m7VBo5gNxtPG8yNjiRu1oUunB+66FL"
    "F4OwmfZmQZH+h6NNSZhjXd+6ef2XfuWTn/70b2rbZN80c25l7OZERIuI4imkFVw8/dt/8S987Ec/"
    "OplUqp7TsQDgqCHFp2nH5LnVDDNxII4ulXFwCk7QrA04iCCAAkmhik/82qd+7u/+t//qV35N3ThU"
    "wjJvUwjBl0nrts9EIjWYuqYY+Pz5cxcvnCP2WImEwEEAttx2lI90kB3fs/MOCGART76tWOyqRPz2"
    "5e93JmSvXrvxT//FL6SmHY/HUaiqqqaZicgwwycv7AGOteF/taq5tK0K3M5mj1x+6N/9y3/pe3/f"
    "B7iPFexbutIM7j6BeTcrLIQwS+0//B//cRVERKpu8N6+lm3dAFJeWpOdJqJwZoalnRvX/51/6y/8"
    "pf/1XyQFkZihH//Suzu9hIKXTyIJu2PetqEavXj1OlTdEnCl04m7GuCDpvyJPBWEVLM9/sQTr1y/"
    "1uikklBVVQzsfki9l91BJ6Bs5THPkn7lG082qX356rWnnnkhTzshIpagqq+89PKXv/zl3/v8F556"
    "5ulnnnt+b67zpnUSBtQt99TkvmLAHdntoG5wuKYQgrUzIV+bVO98x1vrEKog09F4PB4zBXdnloO+"
    "mEMlVBf8WLjrD7iGbivX8tedui3+IOSaG3ENnoXl2Z78A7tSgCCq9sxzVzpO6odjH3MSRgC8S2Km"
    "ZdKtM3d9IQmeZlevXX/+pZdfePGVUSWbG2u3SR0uBPDNCyJiIribQ9uU53TTSsv4g7XydjCpLLf0"
    "Yngzu/XCi68898KL6+N6bToOgYr6f/z6g8AeENidScQ9AgjdOLDFGD+jQTTm0COYFr8bnBwMZbt1"
    "7dr1Jx5/8sLF85fOn6uq6u6ef1VVe6pPPfvsK6+8YtqyI0RWVYnRumm4gPl8Pm/2ZinZaDpRcyfh"
    "IEM9oEvRESYis2RmeTAVYAx3VyI9t33+bW99jMk31iaj0SiP3iwKBIHdiViz9GKQU3c8sE+GNpbR"
    "vlxb73yM1ooTX3np5aeffe7i9npdhdFotKiVK2mg9xWSqrNL17pXYOruuQZ8IIB6O4DsMGWRnSDO"
    "AJgcTXNj59bTzz5/bnNCdGFtOmUO/VjBEv89RJXLfmFCnu+9SJ2koe3VZ9Eee8wB0T4s6nAHqlC9"
    "dPWVJ556EuSba9PpdNoTxd05/9m8JZKkfv3mrqWGmUXYzBrdAUC58gxMRFJNRiNu29b7wZMOKJQ8"
    "d2aLKSVLSkQGY+YYAxE1s5aQ4Gl7a/oDH/7eaV3XUcbj8fr6el2PwTJMZvQ3Xp5xV79NizaLxDkz"
    "1+ywfbJ4nLucK6e8x3K0KXeTbiREA7/w/JWnnnkm0oMb69PRaDQsQi4EcB+pEMwOHfSBynNr+73i"
    "AwIgAmSRnbd0FjvD4RCHkbGBrl2/+fTTT6f51qSuJuNxcfmcnAlsmTqZ13yhsrH3HfIX7ovbHZ2c"
    "zdHM097efDZvVF2thclxHR9OWQmcUyEJUFXmfngB67geO1mnV1ouYSYDcahypbhTt+2YOIem0U+g"
    "hIEIqpqadjyq2tneqOIPfuD9b374MruNqsmlCxfXp2sxxoXLZzGZ+Y2nZSycUV3av/rg9QO7IneW"
    "5W5/5Ec4D4xEUoOTmwcCEe3s7Mx2d2ez2WI+3UL6l4Ew95MNSY5uuG6nNHSQ3ruz0iHMM0l0XkwD"
    "uHPt98nmMUbTdm/nVtoY5WbuA68l9j2ub3hY9n07UZc9z55FMNHQ87YYWI9TjbAi0HB+fZdss2KK"
    "WT96/k4vIH+mO4DQT8gikaRui7lmTgzpe9e4E5ulvDOIiJD/yIJIIEmeFhtThJpmru3eh77n+977"
    "He+JwtPJ6OLF8+vr6+PxVCj4oJcRyO7CuLhvPvFPi6fJV8dhHvp+WZaHEXVPNgnIiUWEic0Ac3Zo"
    "at11mO+0L6WqEMA3/+5xqBqYCKDVOI/qIDttmDTWlbAYuhfVc5ofORmcFLC2ne/Nbs6byXy+d0jn"
    "2+IL2qf497Nwh0/vIDOym9nknduNHXxUJCB7frtuS95lHBKJmeWW7n0K0MHU8Dt9YELo6kg6xnKw"
    "EQtUu17WgECAPJIyEbOT9SdGzAyDm8UQAOQu9hLF3VObAB9X/K3f+f4PfvC903G1Pq42N9be9PDD"
    "k/G4qioist64zCKQyN9oASeHonPjrMSBhpm1wx2yuOmE1G+C5GBCF5MRESQQjDODDxqpolQC338g"
    "EvQlutZlOB8/M2RhUA6jxOSet4UKkzAF4TqGIKvjX3pnEBEVCsBCb7VhS4N8M1hIBkqeLSVbN7b7"
    "qFCwO4E4F2CB+9furMr0ZEaGAS7Ey+RI5NQvtl63dzgzBw5MIamC0DUN7JiAsvEZiBVdN6G9vT2D"
    "bm2vf+h93/b93/NBMq2rsDYdP3L54e2NzfMXLhCHLq0l0477G9SkNAdsYFt3luJw3sZyh3Rj4Ay0"
    "bNgOMJxVjYjMvWJWcwAS6KhGiYUA7icCIOtFQz/ENXSmPQ17/Q9adXYZKdSPKe9HyrmSuaqqm5oZ"
    "PJn2bLF/x/TKyMC26EXbqgtzMR6W++6hzr6MQh9p9B+mCx7Yzkb74tv7PeA8bPE7mKXJRite2KFL"
    "5bTrT9w3WVwuuDmQNf3OPvCecb1X7I895pl+DgeByLOn3pncaNDGernSuFMrILfCFxZ3N1PiwESt"
    "JoXmLB0igRrMFa27k4CYHQ53KIiJQc5MqiTEpm5J5xZIH3nk4Q991/u+9V1vq4QnVb21sfbmNz38"
    "wOUHxuMxPGekLE+b3E47K+0+eX6Fc+7FwKJ0LJR9587c9sXuUeTOL93L+d8609CSknSFDk7i1kVl"
    "FjUKC1OgEMB9oT0QkjYhRlUnR4x1SgnIs+WC55l8MADqeWpo3/1/0U/FltnN5rTgDKmq3UZZamDZ"
    "RsjBNEjVNgOZk2dh58QEJ6e0f4w1ZY8wWaJcxal9PwPr5CZuJ34Zq+XK5krkxKoG5uDee94Xn9Mn"
    "SKgjhJDaPWETJrMEJnMHRZDkS0L/l3Z6KUoc8hDgEKRtUwjBQGZGgJGROzy76Hrf6yHt3Y9UzglK"
    "DnJfTHHKLZsCiy8n2Sx7Q97Bk00ckipHA+Xe95qHpKdEzCHXCVchmLZIbQwhD8YFWCBEA8HkHoV3"
    "927GgLe+5bG3Pvam97zn3etr0ypIHeTc9rmHLz946dKF9Y2tyWiaF51oGb6g+z0fdNGBeWjJuTso"
    "tm07qqJ50jaFkPNo0Wszy7bltHAzkrnzykNBgLtqG4S6kSEk5sE4ZmNukSSSfy8WwH10wTECcFem"
    "oNpqaoNUdaxUNfd+JiInk+yqcJU+9rvYWV1MICUJHoiMiZkJEqSyLBWp7yS6v0MviN1hfeM5Nrgs"
    "NuvQ+AAcMWv/C5+4EeyoDhN+pC/YunH1ZJ4Gp8RHUQiB4ZSHJnRxWiKjYXbsotzzTjCfz4U4hJCa"
    "OeBtMwexiKi2udtll85Jxu7o23GfGAprAGOGakqpgbAcOwn91O0oiUIIqklVQ2AiTclAMoohqbo7"
    "1Jq0V4UYqqpt5+BAPfn0zYoNYIl8/uL5j3z4uy9e2LywtXn+3CYjTcfjuh5vb29fvvzg+fPnp9Nx"
    "Xdd0cJqoYyUt7Y1lwTszZvNdYRMibZuss+eRwE6cjQDA2AEyGxZ/DW0mU2Inl5TMvHVorswYks19"
    "HwB4IxJA7kHGRDFwSondUrsDD8sgEnVaLrm7qXfdSxT7lAhL1njjKbV7zWxP2zn3avww/wer4YCu"
    "tKT39vj+enXb73l05IHpw5YsnZWw7DjmXTLrEc4fd4hQjlt2M+/daOlzX/1Shufek06wzl9/F5+B"
    "OlZExNB2vnfh/Ja7p9SAiTkuv8iyhLPsOj/5hzMkgqMEV2OiSkLkRcrm3VGZ3ayqKkvO5LmgkGAx"
    "SNIWTjEEiVVq21aTWTeJ5cBHMMje9KY3fee3f+sjly89fPmBkUgMGFUiIpcfemhra+vcua3pdBoC"
    "L+yYlVtAb5Andb+64657u7ceuHSxnYNJI0vTzDtDgcJCxJMDkBUCOGDyMUeCWZvMnKqwvhYJc9d5"
    "rs5+4zTyeuMNhbfcwkFdW1i7vbXRpoa9T9+khatdutGsAkB66b/cQJGjeYIzeZiMgpsG7kYn4mgv"
    "/dKS3e+636+SuyuR5Hwkos5mYOyfpLH8KDrS9e+e2+xkY8BARMsuNPtDCzkhJ6ymP9/F50FV4Sqk"
    "k/HoI9//vQ9cvOB9b/0+et7ZRzlu7ssZUrc/kps18wsXz4co7AagTXOmKndfOP6mnMaI2XNLa+Ox"
    "piZpwwZtlZxDCKatppTnSQHg1eyUIZ577rmnn3nywQvnvue7P/TB933n5Ycvr08n57e3tjbX67qu"
    "6xhCELn9st+vuQWH9oogx+UHLvzwH/r9lYhbEwPnGcVt24IkV2iin9xHfUTNeRnPWxgB7i4EzaV8"
    "ABFdfuiBupKFuVVaQdy/NABy96Tt+tr0uz70neO6YgIzhu3dnQXdrJJl8HAlAGvurgyD6eUHL66N"
    "IjmsH3JyUJGhPgxZx8rdmWiR0e2H9T7OZkRWMPM5LMWxA+a5tqhr8+KHuzW6AC53sSx3NzcnZqI8"
    "FXNfSHlRrZCro1k4i867mFEjgbQ1MyWkSxfPvfXNl4k8O4XA1OVW2iJKn7tEn5QAAKtDrdpWVTUe"
    "jWII3QfkmbWr3UDvLIdehFLjlx944APvf29gu3Ht+pUXX3j+hSs3b95qU+IQSCQldSDHbA4R2QQA"
    "t/Z2J+P6mWef/wf//T96/PGv/8mf/BN/+A/9wbVRDEx1tRD9Bnf3RMwrgzrfePk/WS9xqLezRy8/"
    "uD6dMHRURyGPMc6aRMKDjAbql3lRyc+LKPGSAAJpm0QkMJpmxqAAzbPg982ALHUA9w8WzdoIPh3H"
    "d7/zHRcvbI8qZlCUxaTs7AaXbig8OZz2yQsRITgRaTNn8vF4PB5VVVUd00ZKgChhfX091wosparz"
    "wDnQK+ZE7opc806k6iklIlrWzg6qQOm40TWgPCiRjxvEOrROuknu7jGG3LuY756emVRZWFy0mcM0"
    "MK1NRue2N3PxffaZ9OPgKY9FOUlfoMWxbZSIxqPR+fPba2uTqqqIuv6id2n/WJvmk3H9LW97y/mt"
    "jToIyK7d2Pn0b/7WZz/3uy+8/Mposh4Ct8ncKakG4cM6WnOM9d6sCSJ1VX3i1379ueee29jY+Mj3"
    "f9+4jsJwh7sxA0RuVmoIu61rLsSjIOMY1qcb57bXmRFEHCAJK49Sl7CLVRt3UO1PRkRt2woxkbOA"
    "IdPpdGNzM5dcFBfQ/QnpRveRA03TgDSwjUf1Axcu1lXIZT7ezYph29cFiAbVSmaSFXtzd40hbG+d"
    "39o8xxQOrTXNuYh1XW9vb3d7WfNwyqNTjwcDQ1JKbaPezRxRWk6sPGL2aV/1DkCBm7d2vXf6U6aW"
    "Q1xGbAT27g3kXlVVVYUB5djdEKCQLBTJhXwyiue21t786OX19fWcQ0lEbjkJV5xAbicU/V1pWD8F"
    "PoRQhcjdvGa6a6PZzGOMRBSY6iDra6OtjfXLDz7wnd/+nn/xi7/0T/7Zv3zm2SvVZDIaTVLu8HbU"
    "gxeCuxJ50zTb5y5944ln/sp//NfW1tY+8O3v2dqYCC8TEPmIaTZvkMKSfdp3ztqppLpw7sKjj1we"
    "j+soIjE2Ter7/HSbv+PdlXTnpRGf88TcPTCpKrFba7Guq1Fd91NFB+Z7yQK6P9R/AsCqiZArADyw"
    "1HV1/vz2mx5+YDQajeoagBsRiYMdOpB6NjQCulwxtZAz0YiqOAohHLVXcp5OXdfr6+uLiO5q5HZ/"
    "EBhkTmTZYWWq6u4Ez2UBgCso4NBuMN2mt76SALPZrIslcGdNHzxPG4QB3OGuIYTee253RfoD4Bjc"
    "TdXyOeSZt+vTyaUL55mZwESkXd72nbTkNSzbewjfviv9aXNpzCwwq7ZqaW06fujihQsXz41Go1lr"
    "P/Mn/3gI4W//3N/fmc2ZQ9NYXdem7aGf07ZtHkqkRPOURuPpV7729f/LX/mrf+X/9B+8421vvnBh"
    "i0jMnBludnTS5xurFMDdAQ4hjMfT9fX1ra1zG9MJyDiEPrWCF7o/r1gAeULAwD4QdndLGkJIqYkx"
    "atuSCPVugPve+fOGtACcHSASJtZ2TiQGZ+bpdLq2trZ9bjNKAJgg3aRyLBpI2VIor+jpAoA6UZX7"
    "g2Kfp6WPoyIpxuPwwAMPzHf3ti6s39xrxqNJ2+Wv5ewFXnzjMl3IXSS2jT7z3POPvulBkMzn88k6"
    "iFlTI6EC4L2LP9cnDDiHQXjx5Z1vPP5EqOpGU4jVINy68ngsdzzD3DWlcT0aVRXIY4whhJVcVXcQ"
    "7NTlSGwKqaJ7yxzcyN1DCNVozMwcQv40OTCV4RQWHnViOse9NSUJC+fAXejJISLNfLcKgUF1lPWN"
    "6QOXzo3H46TUGv3sz/z04088/Y9//l9abSGwakswg8O71NrMtO7OHBzaJM3Tdp0hcfS7X/jyf/5f"
    "/I3/w//+35MY1ybjuuJjDa/7Wfov1JRFT2YiAlHOhM4pm1VVURAJ8YBLlOGHrI+smMkASCQAiFwB"
    "kNw5fHUssA9qSu5LvBGLCb1Pu7eB40SWIBYJIUhgDixHI0glLMIi0ncB5ttuazzyyMMi0jTNaDS6"
    "devWCRxWULcbt3affuZZDtVs1kjVmagSAlzbtmXmtm2JKKV5Z+GmBJbZfNYqXnjhxS988csiUtej"
    "+byljioOOI46AcqmWoVARA6bTCa5qpZxiCF8WuUoGxlto5rcSYzgLCCZzWbaV2j1dW68GB5y6mNv"
    "n3VLBKS2vYuCqZ+QDhGOwqNYjWJYm4zPbU3f/MjDP/mTf/yd73j7bO8WPM+6OWT0VadjrrSeFeJA"
    "HD7567/xt//Oz730ytXd2bxNpqr0Rp8BsM8IUAekEhJu0twsIVfXLXu+DffDwAtEB/b68AFY/Vd3"
    "79o0iYjIMa68QgDfdNL/8HUgEoLkXH1Qn2hPy16h3Q+WP31iKPthY4QP+Q4GEd78pkcmk0mOPh2Y"
    "1krwXE4waDVDIhybefv4N56+du1Gm2zepKSu6nnYU4wCWD4Ss5kBzBIBrkcjFvx3/+AfPvHEU3U1"
    "Tq2JxIHubwd7n+ROxe7KjrW1tc3NzUVSxAFxz3eQjyIS3B1MzOzExBJiLaECSc7k6/L50Bf8kzns"
    "5EfvvUDWeeAZRiHUh5HdHXkR4ZoLeXPbSHZmsAgLCBhV+AM/9OGP/tE/MhlFt1aE9tUWdfJo8bNc"
    "SWYOELm2s/fz//IXfv1Tn7l24+at2Tw3F7mPBdBpFQgnNNqAjQKcDOwgc9e+m8jiSczLuzwOd8ih"
    "R/S2YzY4QujqutENKy0EcD8ZmMuL398MZziQ0A9fsf01Adnd4g67XfdiBi5evPi2t7+FiJqmOWZe"
    "VRbNqgoijgEsTz/3/Gd+87cbw2yu5sQiRJL1FACmmm1V5pC94G1CAn7j05//+//gv1cDhZDMc8+7"
    "fa0T84JwDnqoZv20qqoHH3wwxpgtABF59c5QdvRjytnBbmhb3WvahUR0cG7a4g7t6qrzryc8ulom"
    "RuRv6e7O3ROgQ+dAFhZmlsv88qqOIj72sR999zvfMd+7RdhfRueDPlQHVRPiMF3bvPLi1X/4j/7H"
    "bzzx1M2dW8ngYC5GQI+qis7WaEqmJOKUW65mYtb8022GnMsMNXjeG9Y9pnro0aAGHfaf6Lq33td4"
    "g20sMsIitXwh/jqB3j2Ttyt9ogM/+Y9o0feHjvT/ALh06dJ3fNu3p7ZxV9WW3HL5GDnxaneaEIJn"
    "a1TdSW7u3PrlX/uNz33+izuzpjHszpMDOQZgZllIz2ZNLi9WgAKeeu7aX/t//OevXL1RjaZJKcaY"
    "1JdXehhU2xjF3dfX1x9++OG2nYcQJpPJMfHtU0HbhmGu5mYxxiAVgSXWJNFBBnjut0mLbF051Q+Y"
    "QZwVwr49PxnI99dK36Et0HmlF/3CnLuaavdOTjve8643//iPfXR7faLtPM+4X+kl6+C+wqErdzJy"
    "I3dyp1bdJfzmZz/3qc/85tXrN3d3Z21q3UsiaIdZ2+RFy135OIRsMg7scnFIZ7r3/3nUz3Dn5P9c"
    "BB4WNODu8/m8EMB9xAJunB+/vi0xdw267vAx60tOjkuVsT6be2tr/Ja3vGVnZ2cQWbKDAc8cxmTm"
    "3OucOEisn33uhb/z//m5T/z6p3d2m7oOCqi6IRcKaJO0Ho2cMGtgwO999Zn/+3/6n/3qr/16rMfI"
    "3Sudcu5zjPVRtz6G4O7zvdnG5trFixeZua7rrs8lM44OHpzQiB+NKiGGmXaZQHmMYvADk+B90QzU"
    "+cTHjtPNus9rW82dMI63tE7jg+6QTRYwGQFE2RRLyTLR/NjHPvqhD35gtnvrkPkQAwVz/+o4GUiq"
    "at6mf/Wvf+nJJ5/euXWrmaeFnVdg5hKqyXg9VKMs91U9qWlX5t6xvoLd2UDaWbY4/McHP33NfA78"
    "Ljw/RDRMDL3P8MZrBdH5BDvxn3cHeV8AlUUOmbuD+jYsfpjEo+EvRp3GeRit+oqgYca73vWuBx98"
    "cNamUMUcxULv9kaXV2OUZQpXnpxIiDjEOrl+8avf+Jt/679+4smn/thHf+Rb3/G26ThSLhuTEEEK"
    "JMWtefM//IN/+jf+y7/1tW88XlcTdZgZU1DLpfA6OM+cMb3SCqJtk4hcvnx5Op2Ox/VkMqmq6m4l"
    "QmibTNsqcAhV0zTz+VzVb+3uTaZrnueoOJjg7uzGEMNpMncIEjFrNEaZtxYDSxRVEC2zs/a79HEn"
    "BDD4z1y557nJYF7TZLj8wNbHPvojv/3Zz92YmZN1ERRfJh/4oBurD/1LxElVKHz+i7/3qc98+vKD"
    "FzYm0/FodMTJv+EUuPFoffdWs7vbNHPdvTUfjSaBgjtSC/Tlv7RQHaizKQ+JdR12+w3uluo65khY"
    "zoFumibnQxcCONOaweAes4MW6Yk8qA1ZaWrv+zYEDT01Tn3b49v6PfrS/OOHPhJz22qIYobv+I5v"
    "+8B7v/Nff+JXWabI+aNkvfTvlNgQ6735LIaolkKoNKmqicRpjI8/8cx/8Tf/q3/1r37pBz78/e/5"
    "1ndeOLcVQufCeuXajWeee/7XPvmpT/7Gp2fzNoZRMoSqahtNpFVVzWaz8Xg8n+2KyLBCtVs9srZt"
    "hXTz/Pajjz4amERkNBrl2oWlZn7YmrCbEfdNk2hYkjOEiJi2Mda3dq5/9nOff/LJJ9fWp+vr61VV"
    "ZS+TmXHXFlSzCX+KTQAYpbZt1ybjvb29D77/vT/+Yz9WBageZa3wytzwlUkHR7qAsjRfNI5fUEJK"
    "TQiV9cNJ/ugf+cP/9J/981/4xGewUmDhi6m2vTcJ5DSMDRCxqupcP/2Z3/rg+983rkdVFdankwNK"
    "Bb8ODDDovJ9bnPOKHnSyKop92QJ3HpBxvnrtxid+7dOfjr91fntrVFdVVdUhmpl3zdWX57wQ8YcQ"
    "AOXO796nji6O6tb8xI9/7AMfeB+xZCv8Plb/7wcCWI4N7Iw6ceTZSTZw8S/6KttgqHQ/l5wO84n5"
    "Ph3/pJ60vhRlcHaEnNUTo5iDGQ8+sP6DP/h9n/z1X2FLiuiEGMTN3BMRaUoipG2KEuAqQu5K0nGW"
    "OsUwSdr83hcf//wXvh4Cr0+m48kITqp6a7a3s7Njhno8imGicCJJ6iRMQEopBtZmHpgIrilVVZVS"
    "UveqqlpNZBbFPM0fuPimx978JhHK0p+ZY5clvVLc0FsT0ssCBhheLXpmD2/RQoMOsZ63KtX0tz//"
    "JVdVbXM09W54Kc0IUK2iNLOdn/mpn/qRH/lRbRGYOadxDfRtA5wkx7+7JhzOtykYJiMHmdFynpwT"
    "JM+ADCGoKotkitxen/65f/PP/MZv/c713Ya5VtXAsevdmifE9Ikr/eTjvDPJHDHW85l+4Ytf+/Rn"
    "PvvIww/v7c1HsYpVAJbFfe0dunGpK4lYXuyRZdKEHKDKXfkG+vWydZUNtz0fYyr78sHyHOPpjO/D"
    "+4y4g9AN7yPkeawksZo16ROf/IyZwWxhPffPMp9GbHAeJUrki9/hqZL0yFve+p7vfJ9pCoS6YmQn"
    "XvYHHO7+LQRwz936yN3yu86atrqtaDEAa1HN6ytyf7G5X7NoihF1FkB+Vn7wBz7y9/+bv/fFr3xj"
    "snkpKbVpnn1NIXBdx67q1+FkWTnJTRocUAMTJI45qBncdaf1Wzd221aZQSRcjaPEEPJoKl0ZnD2Q"
    "yK5ajUaWkgFVVfWyDG7NeBTf+53fUQWpo2xtbmxMJ1WMt7t4P0Kxs+Gj4n0CEhETU+DgwcXvZsdp"
    "g5ongRPRvGmffeb5ccUba2sb69NlTwVaTodaaLV9I6Y71U37el0CzNTcYwgffP97f+AHPvyPf/5/"
    "apvZeDxVVTOEEJqmCXExoXB/7AeglKyKo51be5/+zd/60PvetzmdjKsYZQyh7KIEXq/0FDJeDVDx"
    "/pt7yHTK/b0N/S71sHOO1Qh9siZOaKMf69BbmfyOZO3O9Zs7Tz/7fCXYXJsGmTA5lTTQM3wBeXLI"
    "IufXAWNfplrTIhf4EAlltvwn8+Hb6O63WolRFkW473732z7+8Y9XVbh165bBWWJOh0/mTVLLOUHU"
    "pyfBGP2FsBubQl2cAlEkI0tIHJkiUSCuGIKE1GiTrM3xiY4gO7ZjJwYHJ563ShLMaTZvmQIzW0qP"
    "Pvrot7ztrXWUyWSyvb09nU6X6aor2esrrpc+CDf46UmXupGW3SUQ+/LusLOABcR+V35EYpCKmWNd"
    "7ezufO3xrz37wnO3dm+apUHwY7+MO+nPEWqfrbZxXWSgntta+9M/+zMPXDofBKbzwCKMnGKbN2+X"
    "C9SNme4ShKRrAEhm/ru/84VPfeY3X756fW/WtKq5o4ibwb03Xk4t9E5/va+p/LFTnA+ZeTJPDs2b"
    "59X8LLbi8JUQwssvv/z4449fuXJlNptlVewIpfN+6Mp6XzAbLYK6Q9FjBzNznDpdxHo79AQRhbtr"
    "qXQSPTL+xE/8+A98+CPEbpZyWYC7V3F0aPvlRcISsat7cmtVU87rCcIhSBWR55JTJj04U4iHxz5z"
    "cmRKKXc+Ue3a/qRmdunShQ+8771V4FEVt7c2tzfWqxhD4NvLlMwEK7/YarotACwKypbpNGZZoXv1"
    "MPeUkrsnVQDz+fyll166efNmk+bmyd0Xcm3Z9fpVNYfgfbtoMXiAmVNKavjuD7z3D/7gh9laa1tY"
    "yllYxzyAXQM45qZpxuPxXtP+6id//fEnntrZ3W2a1Laa40k9qb8eHeGW9OaMV9cTaumcd341Rvew"
    "uPou7p9sEOzs7Fy9enV3d3ffjLBiAZxhCvA+DHBwzxGc7Cgnz4HXl7Qx1JrvynPUti0zVDvd7bFH"
    "H/zzf+7PPvbII20zc0t1FVpNTsg1sb6MT6LXE428a1QnEkVizp40g6q3bec3yhXLALuTG1GXZG6L"
    "kK+DjTipOzjEWg0SKERO7Xw0qj/0wQ98y9veDNj6xtrFc+c31terqupNetv3MNtBPfqgpbXvr1xz"
    "3Wa3yOS5hQaR342f3KQh5K6iqtq2rVlSVbN08NzY99/02/54ty243zncRZIH0ZGcRCgigTCp8G/8"
    "1E8++vCD7K1bK+R5FN0gN5FXNEqyzFXqcJIQq6989eu/8enfeumVG3uzpmlSH7B0oIuW31Hg7MQ/"
    "WVI75edhpQRyEfAfnP8henGXDtAtufWBWaM7OZ99d/zgKyf/yRtvsfeYwczknlJKKWmyxVhguBcC"
    "OMM4rmsY7xP3ebytr840tyUN8KFi6265gAC4pWwHkOMHf+D3/eyf+qkHzp/buXmV4TGwarui/g/a"
    "xXSuWHf2XEfLZJ6t2EAhEAcKAsqvQwG1rgKWlrNfvFfoulY8nuuu7Ob1a4z0wQ+879u+9d1BeH1t"
    "em5zY3NjbTSq6ir2fufjJAqOMqqW41j54H5bmDt2l7Doem2drpybO6oT7nIHZSestlDN2fo0GKbG"
    "BAa+8z3v+okf/7il1lNrZoOcwsMXJB9Ho9G8Teo0b+3XPvWpJ558enevaZPB+onM7q91EHIhphed"
    "llcUplN992L20aptcVozYP/tXrUjXz2Qu5EQAej8P7nI80ge/ebGfZAFxEaUbftFJubCyOfVpoA2"
    "YAXr+neydbkrPOQMcr8bz9b+bGNNTYwVAFMHEIX+7J/56Rs3r/3d/+bvv/jSK3E0yl1rzDwLMh48"
    "bLawn93cOrnJRLkB/rBWiIDIOfGFUmoG04zZCHB2AoubuXojBGvS+qT+tne/67s/8N7N9XEkv3T+"
    "3KWLFzc3N6sQATiUjtAVOtcUrSxjH4QfhFX98JhnJ+/Mme9CnjWBzWEGIjGb5xZGueErFqvZ39ll"
    "XuvS2CI/liS6RMjD38LMIZnm5oAdB6mzCME//rGP/vzP//Pf+9LXHXPp+x0ts6P8gHODBMQOJSau"
    "+BtPPPPJT//mI488HKsHJ2kUA4gZmnD6NTPKNke2mf34qyYc7fI5dkDZsL7hBHnUp1BDc3r2wUq6"
    "Vz+0zt2ZjEB9lyf0/bju21ag94EFwANTlIFl4BS+yEnvVC2jfYIeB3QSvrMWxCdE2zQSQm7bI0Ii"
    "pK1Oa/p3/sKf/ek/8ePnNsc632ubGVyJnGEHrjFr806uQh4YgSHksGSpIdfAiEL5RXJ1bZtmttDa"
    "Frp/Doy7u5AKAdrA2/e8862//yPfs7U+YrOLFy5cOH/+4sXzG2tTEbmtMWRgOHchTBxwFKwaAYuK"
    "395dw7nX0F3TaIgJLMTM4k65AXVv6u0fgmN06n52XY65708TyHPnmVlNByEBImBcyWOPPvLxj38s"
    "1zqISBq8x/aNGu2th729vRjrEMdOvNe2n/r0bz7+zDM3dnb3Zk1Sx2C87T00uP2kT+hrcyID3DVn"
    "cp496R4O6dV40OgtBHDP3T95GhxJmyxIxdR182BnXvhPBk+YLNqL92MCK6nc+j4Q7q55iwuccVeH"
    "8cU+l0YklylYFQXaXjo/+bM/+1N/4c/8zIMXt+a3rsMTkzODvHPqO2VVP4CJAkFgZPnH2Z09/2Jk"
    "yVNrrZHlrlgsULccUTDi3h/i0ETaVMKe5qNA3/dd7/9DP/Thhy5t1uLntjcfvHTx4YceXJtMiYgF"
    "OHYmhnXKrzAHZp4nXWmVuqTh7i70gxM4t75Z/Kx22bvjH7h7EHb3PDaZiEKI7gTn7qyc96mNqi4S"
    "s/VPJG2rzOGozzdPRFBr82TpHPVdTIEnkOw3ZQyACP/oj/7od33Xd+3t7eX23d3jJ2BZ6rP5tJnZ"
    "zKqqSmatKkiqevylr37tNz716WvXb97am+VT9b4T7VHCMTs0Fo3/qKMWzle3CBcdu/hIqSHO46s1"
    "pbSIch8i049tits1Qu2tjaoK82bGDFO4E3Po24EwkXSemMN+7tZuWfT3XXkFYpYWLaBFxJLex9L/"
    "PokBzOdzIqnrOqWkKYUQ2Lux5jCHKdzcnczJ1F3JIYQQgoDMLHfSZxCR4PUe/2Z1Le1s/tCl83/6"
    "p3/qL/+v/u3v/uD72NrZ3g6sYdLQebDNLZmZqiZTzU0os+u8e7Aov5Jdll27egAkWeUkck+tp5bd"
    "KvYqEjztXHtle33yB3/wB37oI9+3Oa29nV26sHX5wQcuXLiwvr5e17VE7rvc0TEbKPdOsaREFGOM"
    "QrDkrl2pFBQ58OvmXf2UvkZHmJumtpnBEjHIoeqWVNBLDefFrEAAkQW5TbfDXV2NGVWIREeeZyAO"
    "ksdHO0zzjmqPnTegpiHgLW956A/8wR8cj+qUmiDUEXxqoSnPpM0hTXeF5RVbQVL95Cd/40tf/crO"
    "zs7Nnd3ZrDm+UeWik2VmJjN0c+rbZJZy2+x81eQ4+nq9CuyucI0xxhgBqLW3aU10mBlNBNUcIiaD"
    "7d66NZ2OoRYiAzlO3+YzkXzir+U+yffaLLnayiueyKHtvJ3Psv8wr96BbrL3T1nAN30MgIAoDFPT"
    "1uEUK4KptrIs+1yM2TIAlhK5krI1jWkbhFmW80OWPstcHnh6MqDbsOwB3cEtsCn80sXzH/tjf/TR"
    "xx77Jz//L/7lL/7SSy+9ogYOdayrGCjHooSjqjpi9rzmlme5k48wkzDMLU8EdnPLUV4DZgBiEGZu"
    "23nTNkK+tbH+7ve951vf9S2PXH5gbVxXAee3Nh966KGLDz60tbU1XRsfUfzCB6+XHW5KrnB1dWOG"
    "27DVBC8jz6cY734HRwAxsGvLINUuxWhhc2D1DudiUiYwuVsKQlhwrHmU6pDPJ7iqtnO15K7ZB8PM"
    "Obx/jKeCAAF+7I999BO/8ms//y//pzl7FUdwJSImNjNXAxEjMefYsi0KW3NeTT2uv/rlL33yk598"
    "+2OPbKxN1ex4r0d2SS0umBkGuHuMgcAwcjKYApp7oQnLoespwuSamrm1raXGklYhhjsQGw5Vk8AM"
    "C+AoIuRwJe/Si4jcTT138XMVDq/dPjl4NDgxMShWIXc/zF2A+rrFMhP4rMaATY1hbqnZ2x1NNwL7"
    "XrtHBE/m/ZDFvkmIA6hiJDCZms7JTeAMh2k/VuL1XpA0n4e6ZuKUbH0y/q4PvHdra+s7vuM7fvuz"
    "n/u93/vSl7/69b29W7kZpyOpOijn5BCD8kzhXDakqliUR3I3bJ6IOM8pANysnSeCPXTx3KNvuvwt"
    "b3/bWx65fP7cpqc2Br548fwjlx/a3t7e3N4ej8dd4086POC2zxompEjGZOzaamvOzOxtu2gxp8tb"
    "AF/GYV+TI5hNldg0zTS1sCREpi3n8t9cSMuAI5fctrM9a2YtU1VFYjZTYohwSrODn0/wGNCakhsD"
    "gVhTkxO3jlwesyjBgSbhoQfWPvbHfuS3P/tbV6/fhM4YHrhi8uSa285kQ826KANb7reR04LYzPWT"
    "v/orH3zvt188f24ymaj6wtI7NCQ97GkMIClSM2tnO8kFIBFmlpAr0NxV20OvN2mqJ1UUioEDU+5h"
    "Hj2cLnRCgKOq2F3VlRhV4L1bu7DWWyKYSGAiJTNVJxWCaXpN98m+o7s5yKE3d26085kQYhTybnR2"
    "bre+L93g/nAEfdNbAFEwqvnbvvVbdnd3m9b35rOmreo6urXITZ+yktoVCUMV5GCGprUL21uEpMsM"
    "cRvkNji9Jil2+55XC6NxFokiNJ2MqmTf8tY3P3Dx/Dve/pYnnnjqS1/56je+/vgTTz350ksv7e3N"
    "k0GtVRcfyJdFYzJ3N1UAhM5RK07whlxjjOfPbz/80OVLD1y8dOH8hXNbF85tqyV229jauHTx/IUL"
    "F86d21pfX6/rcTdneLkCh8cACMZgMN7yyMPf+o6377UtScieC1WVvqvdoNUoD8wgfi2OTrnLtNZV"
    "BdOL5zcttUTIlbfuRtS/n8CMjbXpe979dmGbz9u2nbetAsYcgDwR+pBvcXfd2rh4fpvhcBXi0DWb"
    "3p/U0w0dYqi2xJ3W/Ad//0c+/ak/9Eu/8suj0ahpGjXP7uY8JZiRe5plvsyJVbm1YdLU1vFcauZP"
    "Pv6N57/lrWtrE448HtXHuIAW8eScMiqCRx990wff9527e7O9vXlKDcDuagazFGN96PU2TZpO6rqu"
    "U2ocKpyL3YZz6vkkXhFNkAgCArPDU2q+9V3vHNUT8zSb7aZk1BU45wBMdxdeo31yxJ0lkNZycWNj"
    "I5cTLsY4H5D+xQI4MxaAm25OR3/x3/pzP/uz+sxzV77xjW/c3LnWtnsMBZDjp13WPxmAIKOUjBmW"
    "GnI7d357XMVYSX6Kc/d2otct8avrOttF6Nwl0Np4xAymhy+d33rbWx55+eWrV6/fvHnz5pUrV557"
    "4cr1G7dme83e3t5sNtvd3d3d3Z3P52bWD7MJdd01cI4x1qM4HY8euHTxwoVz0+l0MqrGdVWPqjpE"
    "wNamW1tbG5ubm/m4trZWVdWphiJkz8af+zM//Sf++MdffPmVL33lay+8+FJKiRmuCV25g3X5Kj6o"
    "scjdme720chCFZumEYa1aVRXdQymraquFIS7Zw/vhYvb/8G//7979tnnn3v2haefefL6tZsSCM5t"
    "mjOFQ74FUDiZx4AL57ZDCCFyLvoNR7RLUtMs4plYFQ9eXPv3/t2/9Cd/4uOPP/nEtWvXbuzsAGAO"
    "yG3gLGXiNCzyprIrxgKc2NhtPKnn8/nNmzfruo4xVnKk5E0p5aJB9Pr8hz7wwb/+/3zXiy+++PRT"
    "z7740gt7u/OkTb46Nzr0eqWq03y2sTGajEYMYmYWrEr/EynCeRRpSk0IAqLtza2/8n/+j16+euPx"
    "r3/lpZefv/rKdbWWICAjiHkyfQ33Sf6W/LtDh6+7prX1aQ57EB+bX7RS4FYI4F7FANgAf+ubL7cJ"
    "VRTYfN5szptdQkIunvJFtZcBbM4AixDBiVzb+ebGpK44xGwP5/7z5NTlN9OrDvjcJkNNJI+vCn15"
    "+2hU1VWYVLHZmG6tr22vT6/v3Grbdv72N+/s7OzNZvP5vGkaVVXVlNLCTZlHrDBzDtYxcwiBnEaj"
    "URRx98A8Gld1HUMIGxsb0+l0e3t7Y2OjrutQxRBCP6KqT8/v1PX9bdIGBdIG4IEL29tbG0Jo57ML"
    "5zZ25zNPSZgBY8dClBi95hYAYIk6h1UgJkclYWtrYzyuu0zTrv0LzJSASR1GF7cn42o8inXtOzu7"
    "+XNU2yMsAICCiDSzPYaOx3WelBCOjgHkpCAmd/cgpAmXzm2No0zH4eWXX75284a758R8M8A0CqM3"
    "RYcEQKrmaTodz2a7BGvTXALxsSMBhlM888Y4d2793Ln16SQK+3hMu7szdxWJIqTqh1yvE3HVtm2g"
    "ZjwK0+m0DhGaJ/HSHTwGIUSQuqsmfeCBtfX1tUqazc34ytZ6Sk1ec3da2AGv3T5ZfNe++5vDgZO6"
    "2tjYyIPwTDVnVdyX1cD3QTdQVk0iNtvbW5/WD1++pO1s3tzqsmAGlbROBkBdRKK7W9uMxtVsNju3"
    "tbm2PgkhZI+H956PnK/2WhO8ObgfV+Lw3A2fmcfjOgjFGLc21/dmza1bt3Z3d5t21jTNbNZp/dbP"
    "1cpPeOaDrPTlLMAQKuEIQCiMxtVkVFdVNZ7UOcknxjierMUYwV3yohkOKpR823xzdmaMR+GBi+c2"
    "Nqfz+ZyZKdtSy5ED3FWTvsYtxgyQGLRN7i5EzHx++9xoNIoxui/deiLigLmZWWCsTao3XX6waZoc"
    "98tvPlTpS44q1to2QWhzc319bdIHmY8O87RtiDU5uRqBRqNgOrp08Xxdhe1zmwDcKLkJhJndEoY9"
    "c3rGJXJyqLVV9RCLrE8ndV2b2VFVSovzzx2qczcnd6ilOsqFcxuTUWj7/iFHxnic1XNJoVWRtrc2"
    "RtMJHZsVdnsScGIKVZR5C2Ffn0703NZ0XC+87a9PxHVfgGTgqvKqquoqrK+vxxhFBET38eCdb3YC"
    "yIlu0Z2yljceV5oaM1tkWu/fg7QYatEpziEEZoxHE+8S1eXuyv3jPyrQ8m0EWhTEunusRrGCmdV1"
    "vTYd58d1NptlWd+2bUop2wHu3rbtYkx5jgrknpQ5gCwSqypUVZXlvohUVbUYbDKQ9b3dc5uH8EAu"
    "EPn29vba2lqTuub+fI9sY1/OrXEGiXSJsBxk3/0gQIjdU5Rw4dz5zfWN20jDToZ1PZ+ZEUKIMUqI"
    "GPTzObhKIQ/gJFDuBQofTepN2lxbW8u3L582d7LcDltkW1xU1woqRnIIMx0r4NCngfYvwkHT8aQK"
    "sW1bMzuBzGYAwtmg5Bgjh2q4hoPuKcfu/H7Z+tIwqgJcaGtzfX1tlA3ZM5Jsk1c431zLyUGHXh8V"
    "AjgLQQDreueKyGjEVRXcR8c/w8NulPkP+1FN9yDf65jvW4jyLM1z1/61tbWD7VDQ9y1ZXNTiD9Gn"
    "hOfylkUjmruV37ZofhljDCGMfHS2PIT9Uhz5AIQQQqiq6tihNIdf9XCRT0iW1NchTqfTBWGf8EKG"
    "Ja+LyP9pF2SxDeq6Hu75oz5qeHr5S19ddgQvqAjuRJhOx2b1cDcu9vBZ2Dn3UDIUAjiFKXeSR/2Y"
    "x3jfR52p6+qem9XrOlj+vnhlcVG0WtS27znnuzTj4qyt3j7ZsViT409vESx9fe7s4h7t+9LXTfAt"
    "Spfv7Q5faA/79upZIIA3CO4fAjiorZxcq6LDCoDPAvPvk+mHCtxTrcDiAw8lgFd5sYtvP+rz7zmP"
    "3pYwTn6NJ/yrQ3fRUXrlcS03Bjryq5yBdfA0jvnM7Jm5W5biUetwljwKdjY1wkIAuLtP8vH3+J7v"
    "y9Up4XTC077tChyUIHdR2zoLD8xpz+G1fv9Ri3zazzloAt7ZyZx8L91dS/FU63APNxLfv9Mf72cC"
    "OCivbyvB96UBHKpH31uJdowKf+iFHHoJ98SOuYea3VF+5OPiuoeZWUcOAjw9YRzvhlr47oYe59t+"
    "713n7Lt1vXe2Dvu+/Z7vn0IA39yOoJO7II7Zi2dK+t/2rI4SEMeYOK/dBd5zH+5Bn/KprKLj1+0k"
    "sdOTy75DQzW3dd3cFVfMHQSBXyMOOK1d8vqoksUF9E1PBq+bhX6v9uId09VR2uhdcXHcw9U7yqQ7"
    "OREebzMd9MidxMY6qNLmyqyTf8hdXNJT+bhPq4ic1jQ8azk2xQJ4I3LAGRFed3AVd/ds7/jTzvii"
    "HWMOvnrd84TvPz6t63VbwFevxd/dEyjZPvcWXJagoKCgoBBAQUFBQUEhgIKCgoKCQgAFBQUFBYUA"
    "CgoKCgoKARQUFBQUFAIoKCgoKCgEUFBQUFBQCKCgoKCgoBBAQUFBQUEhgIKCgoKCQgAFBQUFBYUA"
    "CgoKCgoKARQUFBQUFAIoKCgoKCgEUFBQUFBQCKCgoKCgoBBAQUFBQUEhgIKCgoKCQgAFBQUFBYUA"
    "CgoKCgoKARQUFBQUvGEJwPqfgrNzRwAAXpaioKAQwB3A2R0AkqkDDmvSHDB3hWP500t/Lxxwz+/Y"
    "fj7ufsws/2vTqueb6grXsmIFBa8dwjf7BRBB1UXE4QaSEB0gkoN6pR/yW8HrfLe65ad9N8KZGfMm"
    "VVWIUQhQVREyVRYpy1ZQUCyAIyFC7iCQu5sDYMsyhpaX6WDkHy9hj3uv/2NxO7ofAKiqoIpZmxxg"
    "ZgBF+hcUFAK4PVJSBZiYiQ2YJ/OhfgkYWMEGHrBCwT2wALLHxwHP96L/aRMMIEEVgwFtMjPAyt0q"
    "KHgNEe6Hi3DEKI0iCBxIihhZfUXvtN7zYAAVqXLvDADr9Q7ypfZhAAe0ChEQoAlVFALMrDB2QUEh"
    "gCNhhqT+6d/8rXnbjCZrKdmsmVfVSGhp3Dh11oCRMQwAOZzK8fU/di44dgDGi4gwwZ0AcBCYW9sw"
    "qat+z/d8FxePXUFBIYCjXApEePwbT/2pn/k3Xrl2ox5P2qTVaLK7OwsDAjCCU6dpZq8XO4zK8fU+"
    "AgAZYOLINJzpGYApIGxtquoghFs719/00OVf+eVffOiBc8UEKCgoBHCEBQBM1taT8WR90xBiYBeZ"
    "bo6hNiQAdCEBLrVv9/yOESxn7xIW9wUASRW1aVVTHYSEm+QSq7JeBQWFAI5Dk0yqqpkrS6XEIEmG"
    "ECilBJiIENjcAXZ3LiGAewcHSMTMjAwAzJkZYHVjCk1jEmoQt25KIdSTtqRsFRQUAjhepjgxwObu"
    "FMzJIQ5PCpAAlC0BdziRELtpDjqW4+t/dECTQ5gdudqry98FG8iJzdnhxuoWlBhOBpRU0IKCQgDH"
    "c4AYnJzUmYnAZGYShAzuTgR3BogZJankHoIANyJmMgKciQAYSJiTuS8Td7tYcVcSXFBQUAjgSLEy"
    "cOoQEZHA1QFPOm9mmhpmJiJTBkBcZMq9pOp8j0wVgIiYgohiPZIYVdEJferYoqCgoBDAbWQKwYSc"
    "YXAQg8jdUQVum0bbvaaZC4iI3FmdQOJUPMv3CtaVgpkTUQsAiLGGRUbMTK4ATBkGWLlRBQWFAG4v"
    "VtwVcGIXIrjBlITqijfXzlVByB3OIlEdBrKSCHQPCcCVCMIMQFVBrOq7s6ZNrcEDC8EYpm4MGxaL"
    "FRQUFALYDwYIRg7q8srNzLRtd+fNww9d+sB7v+1tb3sLg1Q1SuXuhtJg8p5abMTqFFnc3d2T4/Fv"
    "PPFbv/3Z5154ASwhVkJgwN3Ijb20bi0oKARwArFirgJksaKpUW0vXjj3kQ9/7+//yIdHsWqbhiWa"
    "JSZ/A3aEHni9jLyrhHbyrteOS0elbsDp6nsHRNz9OTB8fQlydjAFaVvNYRvhMG+bf/1Lv/rEE088"
    "8dRTIQSvAjkITNmRR4UACgoKARxrAbAFdQGTE9yViFXdDJPJ2pvedPlb3vKQONwB7hIS3zhYyGFd"
    "BGB7m8nBClOoghiBgNAvzqlSO3Vph6309vHBRy2/d8AZWbQ78OUvXxpPRmaWzNWNmVtldyYJRfwX"
    "FBQCuL2Mc0g3/YWM++ohNbOUM0tA6JJL3ni5JQZfdlTL0h9uBBYygwkABAGk79OW2yXxQrG/zZG5"
    "b+oA9J0ewLkDay/9E4MpWwn9G2XRpM8Umrr+QDn7E1wC9QUFhQBend/DXVUtk0PXDcLfcBTgDOq0"
    "9U7+GsMZDuJQZXmLXpnvmjOfVPhSpo1F621KYAUYpASSZZsHB9RhRNjXjcMcqqpaAjMFBffGg3Kf"
    "ej+IzMzMumKiN3oDCAMSI3VEsDKYhYAEsiEz0gmPPvgDztIfveOeAabuR3IRmGMlAONw61EexYKC"
    "YgHcTQJAHxNeaP30xqwuchCBh2753oOjgMKBBIIEZgghUP8ntz1i2WbVAPfOyUMAM7jzCzlATMR5"
    "ILM7AZ7vDiF/ykopX0FBQSGAu8wEb3jYinq/5EQGLPuAFOxwOaWPzAZjXvooC/PCsvTBkco9Kigo"
    "BPD6E8AbvPsDwcHYVwDhgEMAoeDEBuOOD+BAXrPbHgFI39PfQI6AQcLPioOIkCswmIaRAS/dfgoK"
    "CgG8Bm4Pd3cnIiK8oQlgoOn3wr1PzuwSp0DMeYDacIrySY60/BIeppDS0EIgACsNmIb6fu+jKygo"
    "KARwVwmAmQGYeWkslu+1wQBjWMcByuBlDo8T1FT4VGvFWGZYERxMIJi7EwTqCAaCGYi6MoBh3gGB"
    "eHXkYyZs7+9guWcFBa8pSrb1G8kMADtYu7ow7hrt5wRQAwBiGr7/JMduBzkY1BcEKJHBASYQw71X"
    "+UPZbwUFxQIoeN1gQ6bPxVkOJkAd4hC0CAQLYGTjAE5Lvf52R6c82TFnAuUGEQZqYABi7/zJOUO5"
    "w4+UcG9BQSGAgtfNwrN9dgBl8UxMdAv+IkhBIwCEOeAgAbgT6rc/2gFDw4A5eITmPMJGTjDt/tGB"
    "4o0rKCgEUPC6ckBfCccAkAAVJFjC7PHdF/91xA1OI2Yk2RFhMiY7qaPG2RRKRKxOuQMHU0u+Z1sb"
    "29+P9bcBnJs+mIsU/09BQSGAgtcVKzn4Q9GuSDdm1z9veF7aETMb30KAtji5lu7kDoCMlMRBRMa0"
    "R76nD62N38FrD4MqAjvM/RQdJgoKCgoBFNwNdFmwBhiBHQwEuMAYiIRZlN0IZlDrtxgeYoSf2AIg"
    "qDOAiNxwNUEcLIrG1YAIj6CIrhVEcf8UFBQCuLvqLR2u8i4k1Ko35I1qAbitZu2EPvczBWqYGgAC"
    "JWJoc4rPdhbE/Bs8gQ1wscSWKPcFgnhuCkTH3bKCgoJCAHdT6B2cSfIGLQjr+mWHPhpsBhYycAJZ"
    "BAvcfUYkTAFm6JJDTwQBAHN3cG4MBEACXFQJCkr5XYo8qrOI/oKCs4X7RCemUjN0unttIICsz8yx"
    "vkvo6feD97lAZFnZh+WJAjac51W6fRYUFAIoKCgoKCgEUFBQUFBQCKCgoKCgoBBAQUFBQUEhgIKC"
    "goKCQgAFBQUFBYUACgoKCgoKARQUFBQUFAIoKCgoKCgEUFBQUFBQCKCgoKCgoBBAQUFBQUEhgIKC"
    "goKCQgAFBQUFhQAKCgoKCgoBFBQUFBQUAigoKCgoKARQUFBQUFAIoKCgoKCgEEBBQUFBQSGAgoKC"
    "goJCAAUFBQUFhQAKCgoKCgoBFBQUFBQUAigoKCgoKARQUFBQUFAIoKCgoKCgEEBBQUFBQSGAgoKC"
    "goLXBqEsQcFZhgEM0P7XluqLr7wRBHh3NAL7yiuHHDO6z9//38ef16oW5Yu/ymdi/efxvs/zwZ/T"
    "QAnLr9P+6zr0dGz/J+d3kx3Q6oav7DtnO8Hx4LKsfkV/1YuLokN0SjtC0TQHL8+fbFUrXV4jTn5b"
    "VhYZtPIbfHDytLogg0u8c52YljfOjBJgq7cR7Kv/XQigoOC2T7IBkp9VZwAg7Z9p9u4hM8Dy49eL"
    "LjPYYSKNV18xBTMgC8nrS7nmNJQ7dkCo9aLFeVUEWy/K1cAKABzzvxBA3QkTFIBAeskAgwHWix+2"
    "gfQ8IJPUYI5IYMlf3QnQFgAQ8wcuzrMXTEYDmuqv6Pgj4LzKRdZdaH7duwXQfsGlY1YefIsd5mww"
    "wPIdoW7NDaSDt7UG9v5+ZWrkTBj7hCgdlOO8+EpainZTtAYAdX+e3U10kAEO7deT72CXUr8aYDOo"
    "y9x4DjJ2skw57meQAQoBFJx18EL6d7KH0AtrApjyP/Oq3msArH8xS5D+yANpxFkMHfvYr4p+517i"
    "0Ipco/0yaEAlvXRwgMC8esLO/TWt6Om8KjhpRQ0nHsrTzpZhDD5wYRosVGyiVb0efIJjFq+8JLul"
    "RO6/moamjB3Q9/kozd3B3QnR4uoYTt2fEzOwIASC8cJcoCPNwcFL/eL1hp6D9504wHADQBR4yeh8"
    "G5tx33FIAr7/7MjYhRfqAhULoKDglGZ1NuR58YBBw/AhJkBWpKHx0NL3gSQiWyr4AAChTn+k/CAs"
    "lDgCKC3e1xPNQrDyQMXOAnmo7XKvgTIAyeyy0IMJRBAEkK1cFEEITvlbunfLQQW8+z1QvzROZoB0"
    "bBKXy3CIrs+ZOE4u3BwGqJEyxf6TeFX1tsUtELCDCWlhjfWXxvvFngPgjsfJDCZ5VfPFZlOJI5GF"
    "oWur/xAfrHZPPDx09XD3rwoAFEGdpQjE7E7kbk14sbwEBnO3pACd7JgtlbyVnHt+6r6/htfwCA9O"
    "CTAnd0KxAAoK7ogH/IAmmV3SNDQOsq+gM8WH/pyBjraiospC9C8e3k6uDSU8H5Mu4R0PLaWh9/xg"
    "tFCR+/8j7Het0D65lk8iAQ6X1YsdCHRauH0MYO0iJftd8927aaAo+2lc6WCDOswO+vGpl7CLU3cQ"
    "DS/wwC8LLqKl+yi/w7sFZBy0F3xoe+X3rfjKuhs91L47kvYB+y3srT4wQL0LCqsRITrVvkxAykvM"
    "A2uDweSBreoDWHzAhVgIoKDgZND9Jv5Q3XZe+E984KLxsHySefF+7V/UpVi3gdbPA6EGoYGav9/h"
    "4L0COziT/l99oYYyVs+hDy1030ngrMM6LxzSNAx60+DcYJ7lzEB3XhgcQ1ojDMWZAQZK4LCQpOT7"
    "+ejII+UDOxSwbCcNYvKrS0y2FNOdv2j4viGtGij4ihdOAZaV754DBowXJlf/YXsMBYQQgLjPpBv8"
    "Z/8nlEBKMHhYtfBaiMEjepvIO+3BTrQyK9/Xrb8M/oFNekp3IwPc/fT8Ugig4A2OhV/cVz2+ffRx"
    "NWVl+OTnd/TP86oKZgtfdued5wUxrEQsyRcK/gGddJkAY7QQBN27tXOdL4KWlABkqTfkik6e0jKF"
    "aRicGIQlzGHW/QIi7qUwU6/brji+/QDzkN1ZzreAHdb7zobSf5CJRIMIylDI9jdmGUHo9W/r/1x6"
    "O6O7tFVjiAaW38BCWs19Osqp4gtTQLsVsGFoOgHwnFBAvFg7ObVlGgDyLEhpkdzFywWgBCjIVi6g"
    "EEBBwUmkf36mhJODbUXYZYlJBIf35vzQv0FwJBuERAkEZBGcHFCwZG86DbN3uBf4nbOCVuQ+HxQy"
    "1vn6hw79Obr8IoGFjhKOeNwInT9DqNfcFzRmgyVA6L3exos4rS8dL4w0ND4WAlz7dCki48Mzmo69"
    "A97xjYHZl3zpBIM7DGBBp/WTD4V9MriDrLvqfO/YBgTQ3Q9aVeI7Yyii16lz3lReDEFNB1dwkQh0"
    "wMHlnU1nBGLpM47IFOwwWsRaFrH5U4lEXxKVr9qrBCUoU6ukoOSU2ezM1V0VAig4u+hDuIsgZveI"
    "SufEYVlEV7OuN5T+tMhnJO5yhRaJQ2ywzp/cyw7tHT59SqjD7TCLfeDuGPh2VxIBO7kjjhCWsmKR"
    "3pPQK+9yqAK73x/Nvdzv3k1InUNj+eHJ4JlJiBIw/Nd9jiw7TY5LJlAe+nP6QEu2liIGWbZL9ZkW"
    "dg7v82vJ4AsEnVbOwrrf19ZbOb64efsEtHV2Vf9FixXzFd8U52j2agJOTjBVRuozjI2I70RAr9QZ"
    "LPiVepeXWZb+ZxWFAArOLrw3pJM5MTHmcCOMoBJyzgYSSHOO39xMuApZdOc0+5z/7twJJjcog0BI"
    "bEliltkJjkSjhdeGAIHCc5bOQuoqqAUZunyYfbntZMaSpZoqGIbQInD2LhgUYqAACBJhDyDWyFz3"
    "gqwFABIFOzmBQNy2iAzO1QRCDAVSd1moumsRgAykDRQAQRwq3lJ2ejhAIn18lJb5nXaKQjDnTDgG"
    "AuVEnwTMclIREBzOSAC70tJ8gnk+B4hnE8BaUGc7ELm4gXIuvgEgid7zfY4IM1TgUAOIKJtHBHBn"
    "OfAiotAalLqXcvQ9OpBNiwCQQYidON//LqlVmUJ21BjlNB4PA+o6uYai8AQERkz71ATngxEkRkkD"
    "LSg4FQeYERGzMHZhz0NvgWt4gEaQg3ZBgNaIW8LThCQAERZuB8reFzbQNbTXkQxVBGZEDSwgGSCo"
    "twICEM0QGIId6DX4HtzgEZ1i2IDmoCzGkfPHgUDEwgZncJ31b9gcTStxfUSXNTMQ5yR0FyTCLvRp"
    "cGIaIwG+8NDUkC3GVMEKYSBEuMMIQiCfg66S3wAU5vDQKcQ0Aa+BRhVEO+py0B72riIooPAcM+5L"
    "qdxBdJqC2grziNEmU2WIbGA47Br0ZVRzUgWNyBnmoBA8QjbBG/l6FJ4z9zmHWMINtNcBR2oRGJZX"
    "MqBh1JvAlBAG9REJUGAPzUsIBk9g7lx0sYIBSTv1m5Qpr25iYngARaAGKiDCa9gIJEYGFmGYOYOI"
    "wQ6hBLwAv9lFuKmCOip03Lk4ZnOF+PAqgJYQNwkXCKydysC95hJWUlSdcPZMgUIABWdZ/DMRw8Fm"
    "Or8yu/pJ3/vaGhuSGY1bN4pGsmb8iEzeGrbfBUSDYiWFM6dbXsP8C/NXvuB7NyLPwTPiVuHm09l8"
    "Y7Lx7rj+7SE8EFjgLfa+Pnv5fxZ9WuimITjYEIUcPgMZcUVunAnAayNWVgdlXbCSCNBcPUzfTOPv"
    "qKZvRgxOFVADTmmO61/efeWXRvKyUzA4cTIWs5HypTj99mrznYE31Ygk2wGAgqhFemH35U+m+ZOV"
    "zQVJDETkrokvVRsftupRXtsMYCSFtJg/1z73OdLnmXZc1CkXA0O6cLif3COhtmH01ur8u2XtIcI6"
    "e4TPcP0rdvPzJi+o7YhEdsAdPjbepvHbeeP9qM8buE8ZciIFrmPns7svf158R2wmlNwdXLc64XDZ"
    "xo9g691SXVr6vjyBdjF/cvbip6K+ZJhTgJPBFa2zM4GJIkHcHZTdLK4AIYIq4U2ptjA+j+ohyJvB"
    "60YxRwI4GLxbEPiV9uonmxtfmVhDALgCkdq8C/2vHgl88HXF1MJlqx/DOuLoYp/0K24Mr+BiELj0"
    "1QlWCsEKCu4gFAAAQkmbF5vrX615J1irNFaHcqO85nxt5+Ub07Q2Pf9Y6JXOPrGTQArawe7XZ9c+"
    "580rrd0k2mP2ZGrhwtwefeGlVG9U5y6E9e1LkDns5dn1L4t9OeCGE0DBvG7JGC3B4EwwcWVnQ+2g"
    "xA4yhlAykChJq3Hn5rUZZO1S2Lj4ENUVgAACJcxeTje+pPK8ZpdGSMkxT5JwiXZn4dat7Yvvlfq8"
    "QwEBmFjhCWmn2flqe+v3YHsVJfcsI5u5P/Lc1e2wLg8+OpU4gjvc0L5y8+oXa3+S+RpYnRUwdpgx"
    "d0lRh3g5uizFVbR+Yc/3Zjuz6lLaPPe2WiKwh9nT1178bIzPE90wCgBc4Zg2fuEWbsr58+sPboxH"
    "MYvJPrt1D/Pndq/9bsS1CjsJLRlIxnNdn/vzN/xF2q0vPrS+Xo3hgBu8gbSwG83OV9v5NwhzZjcy"
    "hrGbOzMiiMmDuecUVQg53IzNY4NxCBt13PDwMG9+ABtvjfUWIXZhGHK0DSSA5mn38dnVzwafi6tx"
    "cCaoEivAlB1WvUPMnQ66yBps7PiVHbsetqsLD47Hkynlu7YI3jh73o2ZJosFUFBwcuSsbAKIGKPp"
    "ZHLOb47ZblBl0eeRqfG9xpL681dfml1PD75l7XI1rvsoAHX+e3fovN15mvTFMe9Woc2OFyNvGFfn"
    "+uWnn12/8Gg8NxtzCjLHyD00wS1QIkQHKQgQhhLc3cRN0MBZnAAhdpAJlBhIt0SqINOXr998+uUX"
    "Hwxp/cI6UBmQoIESpIncxspDA8++KtK6alq+cr35zCs7zyqFCw9/gBATFAhCubzLRlXi2e6EmsAG"
    "d7CL6dybx5/+WpyfGz34yGY9kkoIQJ1cdjjsBtoBd+lM5Aga4H2u0WEMcMhraPf2Xv76M7N12YoX"
    "LldSE/Yw2ePqZhX3AhuZm5KLGtOtvfTsyy/E9rn63LeMR3FZA5UpICJQM5EmUgOdgRgQkvmseenF"
    "l+bN7KG49pbp1oiZQAYWuABUo61CIifA3FjhoYpwhc3VidyDOBEBZgQiArNT47anfn2+R40+S7du"
    "yq0ro0vvDZMH1SkljyGCI8whVYDVQWt2pNZhLSxEAqWFiHfXLghPckiMxGe+d/XqK/C9S5P1R6aT"
    "9Uyl1DGADdvzETS3AjpTMeFCAAVn2wnUOUIgqMP4IslGM39mjJkqSQyBGxcLfFWQrr/8XLOzO6kn"
    "xF0CCSFHABrMr873rjBuBE5gQ3IQMwd49fzze6/c2Nh4aK1e26SQc8YVqgwLMKM5UZufaXhygClQ"
    "V/CqWacTciMytUAwnzOTBE6k127tbTVuKn2mYwtqgdTabJRuGVgQ4ebWkHvgvSQ25/jylS+N1h5c"
    "23qYEBVKgLhDAJ2TzsVbwOEtiA1IKc1mu+3sVuttHwMwcAqhIewQds3y2YIdcM09GrImerI+Ny1T"
    "urlzPTaJpW5BlbXgeR1b8pkgwYXBLmwBNrOd3Vuj8a3cL87z93RNkALUTHPtVerqnI2Z60psb/f6"
    "jOamTNLHkD2nYgVHSz4HEVSJJDCsnTs7QYgckvX0nOWfo/hODmYWYhdi1ZS+uPPy7GYbtx8ZVaNz"
    "CF1SU648M0uEHMhNFFjMHAYHuzoTu+XcICemLNdXj0w2HZE2O3s7N9pGs22VgyxGjZE6dXFncrAP"
    "u4YUAigoOIn7xwGCmgoLJg+PJ2+y9hlwAyIlEw7R1fn6uWl948qtG1eub689iBrkIElwA1rQDHsv"
    "q9+IsbGUWNmU2QMk7u3xtVeqaf3YhXOPxjDpu4iGymN0JiKhBjlD3xjO7tJybeQBLbsBYs7J2cGB"
    "GaQsCRIaby0gRSRybwxRuJoTZqCEirkW49S1ITKmRjBTNBhXuh3syu7Vl5/9RhWn1fS85ZR/Aswl"
    "d5uxACTAIAE+sqYW4oqoMgqAOGAtdM46j2JCcJeu2VzugcGHNNc+BuxcaRilUNm66HoUgo7QJGpT"
    "IIUZkoKZyGBOwkQEZ6ZlTq5ZDsRHcECoXWamkYMC0CSQAGVXIkxE1voYQFBXkQni2NwbTxW5UWIR"
    "MIEJHMyCKbMLIERKnohakMIbQF2VJBJxJU0VX5rP6LmXNvdk++HHJsxTc1BOQUKlIINCFaqIThyI"
    "xN3dfFGy5yAQmZn33dwWR0NwhSXlEIRGfXPRFkSgFjwHzZ0mOZOq6wZ6xhigEMAZUHJxuv6Dd9Cp"
    "sO/kbn3haJc07csmlGexXUmuPCKCQ4EIuUijR/XW5xu7ygGuc/GI1Ji1G2OvZGf3+jPubyWPff1t"
    "7pB8o51dSfMbozrr7MJBzGPyeG037OyNzj/y2MULD1ch5oz0rkNknibQuW4VTm6cfP3abCNRDNgg"
    "JFhtFJTNwGQEV/GGWrnR4ma7ZaiblGIdEHLyu8GTWZu9BOrJvQlWg2tUNdyD6wh7F8bXr1z9wq2N"
    "rWqyQURABTCM3cHWGSjqrUDIQSpkHJy7vskEcAAmrW02vCs6cgQiAcBuwRPQGObwvqVzV8NsRlGx"
    "qah6l0X2GrH6VuNbYCGtdGY0EYjAI4OZY+fiIMCSeuOa87XYjcgBIh82IzW45Y7MWpEQkZkRu5vA"
    "g4Bd0TYQcRZijma77OYwZiAQJQepGZir2Txcv1XfvCVtksh1XcUoGiod17O6vhl4jzTXBsIxT3pj"
    "Ml7znRevvvj17QsPr21MkyN2ubEqhsAVSKEAU0opEqlLm6aNVo0Gc3FXkDHnIrLB8AYy83rWjPYa"
    "yHjEIvn2UHfh5mRL6sXZLAQuBHAGpL+dMjfbTjfOIyMRFsZybidsIDOCE8Olq4Yn4zOWpkAEV6sE"
    "QIBfDFvvbG58Ks2e5tSOYo3klEKcVPNZW8mVveZrL+++9fzksdypzIMQFM0LPH9hRFa5kEckoOIW"
    "PMPk+Ru6h/HWpcuj0agK6ApXoRS8hVUipuAYvTVD5bLx9afxxecCjy8T5iISZDy3ZFBnB9iUI0dV"
    "Vbh6NZk+tLY+aUUjhDwSjUB7RiAjBjMqCKt4sjYKMwQJFW4SffnC+OaVp8b1ZHty7uHWUuQxOJCF"
    "zhog41qStcFRuQtGKQX2QARYggj8Am+87+rN83t7L7sntZYdUSzY7nQ0nwoL9shz4auBHT5rdPTS"
    "7MJOuyYBZg0LVDVyVF175ebkFo02SFgULLAZKCSq2WPgFtHgc7hHFjEmJTMn4oXWwV3yZANHJHYk"
    "YXYDKUUiM1cwSzCdV2iExyJkDiJjNjS7QTyYa3LJzi1jJKlw8cXr67/9lVsb5x5hHkU4QQPNH7i0"
    "9/ADT6/xPJrlIQgGBlXuXsnOtavf2H3lXRtrl5lZHcIgNP9/9v60SY7syBIFz1G918zX2LElkAsz"
    "k0vt1SVP+j2ZkZmR92X+8nyZryMzIv26q/tVsYpVySzmvgAIxOrh7mb3qs6Ha+buEUCSCTariEya"
    "MsUJBMLdbXHX5ajqOdEFKcANlebcUAC0Kc8um/t//y+LRh6xmpFGycytQFi0FtwNuaBPqRWPe4fT"
    "A4mOgvOIZrhTHEKr6FKIMowA3zhBgCEAvAF57r/b452WKgC47pAcdxOB/H14EP8DY0A3aajGoNVJ"
    "PX980/xG/AKphUciorU62Hy+/ubmy6vF8/nhOzV7jjg0WH3drr5WrGkOFyjNU0J9uRo9u8zT/Yez"
    "+WFd17IFaHPyVMbOM4WuRpDaZl2kkMI79x/9r9Np7chENELEnBAJORGsAIQAN1OJJ/ceIJShQYHr"
    "TktWSqlhAgmazJmb6AlE8OvpqLpuvjn79l90NKsmDx1C0U5rShJoua/bxGFm4JaFjoioHsZ5Ov2m"
    "/ezz6+WqqapaHblZVOJP7oUP3qkVy165qhDiS8bol/96c7EehYrmEIEZA5hyYgULdYh1x58jgAgY"
    "rVBe06VM/O9Cdnd8XCHDcdAhMDCJhX5PDQZxgsiC9jaHdQKzeC8u03FKC4DGZYX9MH147yd/t3/0"
    "aCy1WPbmhvlX6/xiFGJUR2rhTqGKppwmVVwvri7Oz/fvLevpnGWFEEnsFnNRqc0osbFJg+lo/6/2"
    "H7wfAnJeRhbwrHKKFxMXtxiEEkbzw+l0TMAtQ9S8tQ5ro5SZUZiTAx30YC95t13gpWOy/AM+bnjH"
    "pCMquyumYW/21SncZ3SoORSAjHT+rp/9CrZwX9EDVDw3WvnezL68eHF1fm4PrFuiRQKWWH2V26e1"
    "NvBCjalmBo7OzydXV3j84ZODw72q3omYZujHIkmaJ8ApsJRzZj2aPnn3w8dv3XNkhZJOh5m5E67U"
    "YICrNzmZ63Q8djfy1kUXeqnGPLsiIGguvBVqIN2obKfhm4vzf3wxevjgvQekwRvxBGRjcrEeztdM"
    "SbIObKDZCYMoaqhM5u88eBJYP1qtVkINrJDWxGK//gL+XyktXHs2/NpdPR+kZr+uPnjw6GE9mQaN"
    "OVFczZC0jePpg0ePVBVOOFG8H5MgvyQPADATich8BVVb+bxlY5EBi8bbFG+3OOx2hWty9/q0FZsl"
    "1zk04/29k0cnbz35SR0qzRQPfqXLy3+25dOUb4I6EGiJQqQsGF8v0816nTzV3feudIPdaCQI0ikw"
    "R3DGlBtlPDne/+CnH87m82ytugNpk18ZKB5IT+0NFVmquq63YkD8wWitDwHgTeoDfC+Vvtd53HDz"
    "7kL83H0v0O21ORD/YyGgrh1Q5hQ9YvS2VI9t9VV34UQ8OaypwmIUsLh82qyX4zDvBm9w2ayfKq9U"
    "EqyFKIzUKqXR0xeVhPtHx29Np1MAZiYd15ySVGpR8iJMCLgRaTrSg+rmYHxa1VuZJzjEvCMqoMAE"
    "Oq5jnVCVE3AYXfqN4jJZ6DCnCUWQ1XMrJUOGUevc3sxiyP704vyfR2dHh0ePuy1emtONoIciFWA0"
    "CFzMYAXQgUNZs9L7j2cnDz9wIifQQ4yC9Vl7/V/a5/9D3HZEDgivDBV0un/05Od/9r/sH98ThpxU"
    "LFDMdJkla5xkJ6CleeqeUbYfXAA6zdiNkYrL7TbzHRmELkg4yTIL1IlWWh8edDcfYl9blI6M0XSk"
    "SIm2iDIahZtxvdICZJlx1IyWsrpB9hRKCeiCpg0cr1ZiPs4UaCknTdnxfDjNy86FdxlYRKr88nA6"
    "Opo+P6i/QtgP2+i1obsL8AhUWlVg5YjmDodI6fNyCACDvRYC9O9VX+z4/tClMLydst09mDewJjBD"
    "6A4tR8S3qtmHq5tfulzAne6i2toqkkfz0efnLxYXL+ajiagDq7w8bdfPK95QkufMQMsExzfr0dPT"
    "ML334f7B/bqOJeUv056dvIAI3AEnBW7mScXu7eeZ/1u1+H81n0U3C0JmEyeCwhoQKXnWvXr+AfZ/"
    "GsIT97GRVuaIdrPaTlMqwBTu4lJYR90cKgFGudgb6/X6n86fyrz+30MVfUNP6sKyYSRdm1Gc3suN"
    "9XUSQaUQwliV+UODqiZtN/l1D30YraP2FIbJSEcVQImF0FiUU0X2bgq++7jqhh9o46u3q0+Ex836"
    "a5/cCFzEuyvghNMUdNrG9Us3Na87H1tuvP82gKSUV1ehDXvUcf5SfQZOwRbLT9PpP6zOf1NJqqoA"
    "S0gZUnkrUu+dnmXjDFq3MEcWFiBUjJYJuZWA5cDF4Rh6T6fhv+Zn/4ZONUgBOL1cLrjQY2v36pP/"
    "jeMn0MgdnbA3b+F3CABvPBL02x6//2++9HgbddwVsLXbxfubWAQYYHB3A9ERZ0oFP6j2P1ifHeZ8"
    "rt4QLTQwN+rXx9Ojr1+cXV18dXx8XNcRWKXFM6QrYYtsBQFzkWzT52eyTNPH997ePzwKIXQev/TO"
    "SXEh6ebaEdIbLSuwP/OZn+rqfHVpJF2YU4qmUZnTkiorRysnl9c3emV796ZhOhK4bXmqCd/IFfiG"
    "gZiqDrgHUfGctYKvF6qYR55d2otvH9x/eOKSnBAPcJBESbrF6Sa7RMOU7f3tps+RPVU0qBtTfxXu"
    "XmqtghEu7jCD9tOnhYjZNUA6GS+HGQkpVKletq0TYLaLe/htRTWXVyUZ1qf/8B0+Z5aAURCqLlaV"
    "bTwTeM1QT6r4qFqs2rD65fWnn2WrxNeSn0nzLPhF9BbWFCDGPEh9fL4YffHsJo8ejSfzqqq4o2fj"
    "hG9KYJOO/5Xrac1QqfKT5vxjmEcJyNHgWcxpLuYOseomv322PtG96uDeoxjqnhPUhwAw2OuAP9//"
    "136PzxU3o5/Ypv8b5QrHrdr8jYwBQnXs0P37GOOH9eTtdPVceQ42ZiIi9GYs60l1vbj8zbp5t57u"
    "ARft4qnkpFR4hgisEU4vVtOnz2V6cP/o/r3JdNq9CXsUg3R3c+u0TtzgmaLwFCmRS1omqTGQ2eDK"
    "2psUakfAhLKEf3369Pwbvd/ef+u9kzrW8nKR597NY9FBhehyZW2u9+ZTpBfIDSWT13N1I9Zn/7KO"
    "Z0HWmQh5DLaQFZFcojHRPQDqTu+T5zLlZUYV6WgMSkjIuW3kjlokWID9tknSttm37NYGwKECkbBV"
    "cnEHslnqwC6EXq3FOo5l8VyCUu9k2cP3xj6vd+3glNs1qBS6Tt/RdSgHt1NMpIvzUKX9kc9rbfMX"
    "6SpL2Txo87iOqB1ta3ktIeaAZYrNev7rr/ymmZ48enx0dH+sY0I20jRGwa5gJoHATM9IImJ5GWgx"
    "BrjDS1DxLMk1u9G4DH740af/Ojraj5O9g/16J8T9YHoAMnjgP37uz50/3Pnvtzzle/1XNA7TS7Hm"
    "dvvX3+TLQ4ICg2c3A9EmAJM4fS/j0DWCHXxPgulmVl+2qy9X6yv4Gu1zWz0TazqWRq1hOSNe3kye"
    "X4XZ0cn+4TxEMTMzu+2fHRlda9DzprTPtqY18CZqBps2LY0tAlwdnqxdJWsg3rbti/Prm0USjgQd"
    "lLQj1yUoFY26o3XknP3sOj27jJfrKSSm1Q0qDbQ6Xx/Va81fnp/+ErL0vhqBU3xzE41kafe77+TW"
    "EmDqBhaGUwCQIOFWHbljMcYY60rHgCbrVN1L4pBSYs/SDAWimCduxdekR6IKXGMuyYoeSq/lsiul"
    "WZB9MQUKxM/u53j50F7hncL0ECDSOfE8+ulUzufhdIIX06pFusJqAafIXvKDpR0t+da/Pa0+/hb1"
    "3qMHj97Z3zsSsAspPYO/3VJ8k2wsQg6AmJkqoWbtNZDBbJLKTBqYBY2jOT19fnZ21jTN5nv0A2oA"
    "DBXAG5Dh+rbVWch6y+PtFmjnpn/LLsnmWbtPhzuZ4G5GUbUdlQ12OVc3o3xLjvBNSlB6la4MOmIE"
    "ESoAkQcftk9/OfZn1l4wVHBBi6D5aNY8/eqL8/On90/mWH7jq68VDUTgITet1vVqpV+dMuvxycOT"
    "8TwSTrmtBGJWtv0RgqcWAFSRMwjVCM8gsxGMXo1SzvDIEHJehjqmnCSMhON0I9KOtS1rWAS3yjNO"
    "oDALWOtsEdQh61x/8hWq6f50fhnqkTeZiESMqRnrt5lcLi5rcaABgUxKgGcwiyDnzA3JM3fnAChC"
    "OAQB7uAWhQeKNhc20F/b5ikqa50IlcC9F+N0C6HfJe4YblpR7TQJEl0hQTIM5gJm5FW+mWC6A/dk"
    "hUPc3TUwt6YUSvSUGCsigqE/BXaURHe7U9JFUFesBKy9NhPmVYwgBbQWMHen0n3UNvOl7X+7GH92"
    "Kp8/jzp6+MGHf/34yXujMJEygbWtMdjHHi9S0iqztE4SJ2YMscrWwFrWEQjmklkqqAyYM1EDKSml"
    "27X6AAEN9n2tFS7g655wCkC3RvmKWo23Z0bvZMr9s249nQZEcKQ68rt9BNnBo/FDyFoM7LR8FQo5"
    "qWc/WZ19PA6VU81cGOGseDWJvLn4dn19UN18XvPCbVmmPyFss67z6OkZxvuPp/P9cR1esTPXpare"
    "rQRTQYOImy+WuloeJKmaDEQ1zTlnxUgyBK0uuUotw+jyeuScOWv33Wu7IwPs4mWAB+7MGZJQt7yf"
    "9O0lrqNd1ZpgjuTQPK9urtt1dFcAbPrxTYgXwSl4GbrcOE++VNhxUy7kXjxzCwEV5y7eK8j7rbSj"
    "+zj5TmJBdVFkwhRU0swdhNDpWTRqHAFISKE0pDvYR2hwd6XTHAJCiZhN4CJSudMN36XK5VuIJpjp"
    "janGSRiJtTfaXgKGiswOCUS8uc6fP3vx6fn4dH0wv/fnb7//N+88eW++v6faNV3MNjLAUsaWupVm"
    "GHIbZJTy3ovr1hAyXCWV2GMImQGA0mFZLK98nlI1UlVVADmbBuHrSS4MAeBP2i5x8z+w/hL0Hpm0"
    "bpLD/fbH/6WB6+9TC9gsy9u6/zMgs2ep9Z39fHpZDyh8AG9yp6TTfTSgm2WSg8nhTy/P/ovxCjCz"
    "LKgA1Lo+mKSnl98szia2+qLWa2ANFq6EKvn49EovV/r4yaPj43tV+M7Pfz8FBADI7s7U4umZ/vNv"
    "9nJ8lJipZiGlZJojTGsJbinb2mW0tkkcH0itWvW3T2xHLZfWq8eXW2lgxjjrca7ebquUbpoqvyBv"
    "4GsQqohNE3PVqdtIhleliBAXp2TSBBlwlmWEzf3vmDIBB9bA0qSxrTp8QeEzy4R7YdRBBte9398M"
    "5HBXcBFaeZnzKXzPhdRBPUgizBpFOxYEKY0ZmBuICK/oQjcWNlMnGMwAaPZIUYMYod0UTeYrl1Ro"
    "0LWFwxeL2YunNhv50WR0EG6EDWxpoLgiYDJp9/f41mhyHN/df+evH737lyONUeNGDVOkV+jc9Jm7"
    "s0uAk5MX5+Gf/82u2/0cZhB3mrsb4ZAySSomYm5WXVm9J1JWPTRIqZmcQwUw2Pey5fUX/7989c+k"
    "q5ZWJ9yziMDzHWx053v72/1/x0br7ks7jCf/t4O9J/ARGOXu9MddYrA3cFNx51Bth4klEBNMH+n4"
    "UVqeq15JxxnkynZvnE6vvl1fsvZTiasy4eGes4/XcvT50yZO7u0dnBzOj/iKbLO0K8vwkVlZ6nGH"
    "Bmv1aik3fLJ38r8c7dWI7swAAmoa1QgzFXNaZqgms72jvexZqXfbLJ136IZhxElXRzSZI94fH8yW"
    "eb1a/nKiDYLCVynlKgRJhU+G5IavWACFF50ubvJ5dspkgjvSwr9/k0pQBmTLy0udGQ3aAUOlbQuE"
    "kGrN2V2M6tCSWJfgzQxPyqJsTHeHJyK4O6Rqk1eMoEpRF/htMLqbrVqxpy/40Werk+OD/CDGiY8D"
    "BDcSFJasWVTV6NGD2Z6NVqGujuOscgCWWpHqTmuN5SvW1R0Owq1h1GT1TRrF2S9OHnzIUeWAo0XR"
    "J3YRqBjUhG6s7Oj+vclkssmrduighwAw2O+wNNGblmckggTzVNIc0jcdpU0YEO/oer4bBer8/gaL"
    "NAZLF2De/cR7VwRsvL+86fvA3YFrrw8eiqS7yGx68NOL6y+nvFYxuGcYLI90Pauec73UeI2cEeg5"
    "gwYZny3m354vDx88Ojw+qUKN7jrIK+OouUEKmRqhIw2jTD149OC9v/iLh4+PSSQ3cQQJdKPDLUXR"
    "5MndGWp4VFW8FFML3lJmbMQDJNAIo1NNDkb7H7iltn2+TJfjKsCzp1zFuvCMmY8ERrmBA5gU2Snc"
    "zRHusIFs8oa6lA6A3T6qbiPMGRxadN5hfR2xrRYLGBQgE2BsoIiDGTA6CYvSTEfVtS2kvaHXSN6R"
    "QEgCb9C8AFYs0sIlpgZzM3OsW0QGSqRuPoq+Q6Z/KzxLdEupyRXj8fzwb+I0rvER0ye1fiOyAlbI"
    "Ge6RqH3Vrpvrb0eBsnf4IcIkNR4iQZglERSdnAzC6WCftgcyIMTRfHz//Z+889O/jdNpk8tmWTny"
    "TnJITATJbKUhsKp+oA5oCAB/ZFxbtFVtFKRmpoZlGp1222uUEWwBoLRXM39aDyLJ9ifBVy4ZaAv4"
    "C5fCrNB5vY3o+ZuM+3eP3aH2KFY51Qp772j1APlbIJsky05YLc3x9CzIVaUJG1CEBMM3z6TF/b3D"
    "h8fHx+7UV3z+e6cjhAdQzemgGrPRIebr8chmVUDHxwCF9dlfAKgeCx6wXa2g3fXF7NBnZAF39101"
    "ycH44ENb/ebm+bMqP9eQQgZygmRQ3YOjZy3yQFO6qIuUGVBYkcHZOO0+gSiT9aHskUnn/f32B6xc"
    "4SJjC+uLI7dyzTdjAhFhT+Mstx409z0D0lxktTcbXy++tfYbeA0to7cNuMDqS19+CVy6ZzeqxzKi"
    "RubVqmmbEHSkGgFkN/72/NkQUNVxf7L36N67f/f4/oFen6yeM6Wr0F6TJkHg7nlZUfbi1fLqoxcp"
    "TuqjMBlLLCwcmbJtfmzXDso+WgjJsGpX2VQ0VbXUQWNARABAbFQdC2KqwBiQ7Nuq5QeU/g8B4I9v"
    "OXt2A0XNWstKkG7ZtVO6kB3YoPOGnaDH7ceiIH7nJ+7uRX+j0+KgY0vW2FUV5S3ou6ueb1gMMHjY"
    "RLuOwK7UBPFkuv+2nf4jbGURBkaLgmY+WXXDkZwgOcTh61WDp2ehnr5zcPRgPp10Tu67v60iYg53"
    "Wi7gA4L6lOuRnzNHICprQME1mXqEqmK3O9bCrCOzfhnIdpcyjugBWQOpZmDjSOZgfTI6/ItmeWbL"
    "G8VaSLMWmiEJ2YgAREBK7q8uIUMdZQ+A3EDb/eT+TjDoqF79Vs1XiIuL+JrtkDNso0jfWHIHqaj3"
    "6nqeFw4BLDu6RQGVZj5b7enz3P4zlsD0CDRwCXvaXv9zu/40hmshsyk4hrfA0iVfL5bm++PpTKvY"
    "ZyduyJ2Q2B0w3RVLuIzc4iqlHBHmJ1r/Vd2e58vP2nwqdNGC33l0Vazvja6/vvj1V//26OEHRzqO"
    "LVyRuw/TTg3kW3TRzRtRH49QS1v5jULVAUt9tPNCyddXTjUgUmg+DaSLiP0ASuohALwh0EYRsgtK"
    "KZ1aF1H3Ls/rxOS2ebqh/4e7j33vt3xNCbh1vMNdPls+5wYCKaegm+S0uAwKu5nUNxQBuh0TWIjP"
    "fI+zJ/nFjBbF6R0kbRVbinhLhpHlDNHk9fVaVk09Oniwv3cvxFgYxnYnoLgT/8wMaih0bwqoVVH2"
    "x1nsm2r9T362ByNZwwy+crqrQ4K3Ag2G1mRezX7G6rifZP0uXLsM0pBl8tQdKsAoTD+c7J+n9bea"
    "ksS2SPs6e8ftobBMoixP9e9Bl22Gujvd5Ds3+lZPxTdZcMfz1l8C3+wus7xWFiK7CBSchfqo8RGw"
    "gq0IQNQ9k2kyWt8LZ+31f7vh6cQeg0ir83Xz9Obio4k9V23JIGZQIAdHSJhcLUeZe6N6XIVypGoA"
    "oIJQWIYgueOBKt+C8djXdPdAychr5yQex+O/aBf/A3YKuVTJNGhQZMnNdVXHsfD6/NP1+fvT8dih"
    "LLlS4TX1viENuLPfKbG90WoxsZH/Jl8yLMaWXDrojEALmokZAFbrJozmb+vkPcoUXY2aOtpBiBNG"
    "EbSA0XUQhR/sFYkmAZjnnGMIZgmWlQ6THc+Xf1uGTOlAos3Uimew6HHDnYBASmlvIuKOoBWQQDNm"
    "0LyMMbjJm+j5yxevRYerFOpgdYjlsRCoH2L69urqbJISsc7SuqjaFBnEAnYj9WjlmuPxZ7+xnML9"
    "g/tHew86rIwGhxcNcLLXyyk+TZ2AZadr9GQLAR+fTBO+9av/9+IqCCx4Vk8GMUpSOll5SLkxbdby"
    "9qpeze793Wy2RxHrv2m04ssKzbFazvTshTvTgzCSdFSU+6P9v17fnF5d5Vq/hl8KspgLRm6FHRXI"
    "GcxZMjUZc79FQnPron6/AQxL0ATkDMvIGU5EihMt6CqC1inSunkhCPeWVDi7F6BRpYU5zWHMkfN3"
    "dPS4WTUVAc1YtxBjpWJXBzDDmV19vFxEZ3DCrZ3Y1UQTzWBrcUFaI8yYR5eL/U++Gh08/svZ/p7q"
    "2lAniAOCIvwbW2aRpIk0RaxSap3rpkpgUwWG7FJgq9Gj8f7fXj09G8sNsWKKlAA4K7R2djAfr7/+"
    "dPHVP9ezkzg/Lgy5Xb2MqCbO5Hkt9chyS3fYYn9ss3Ht/vfts/+RSwduh46ohEkj4NIm9au/zNP/"
    "Z33wZ/VYzFvVpP2QqSMUIhF1IygugybwYHdbghtkgC7imw0dvAI6AF4XtRfveB83zuA2yGOgW9HT"
    "9h9AN9ixxaMdAMaIx3H8TrP8KuVvQy3qOZvDAtzgBk8OGkfni8nZdZ7PTu7fvx+qTa/UQCHpt5cv"
    "SLZNS82CAsUlAdxXETkyG4u4ehYsAVOvAVFhzrkyVkiQnBI//+pf89f1X/zVX+7vHxDqMOYM8yAR"
    "Em3VSgxSBzgNmZLdsxdKOAhzRLhfH/75qnmxSpejuFCKugHw1GYzRRQyCFtr4bkwfVsCy4JtR7Cz"
    "y99QginrEBUCk2yt53VQgrWqltkVkQCHpwxkhtFmisi2uwyV6gHqt2X8s9ymlL8KvEFci5RiqRVZ"
    "qF872mzIDKSKqRBIa7Mk4wiGdg2RyfVq9puvJIcHk71H8/ksBjpMIW13lxUaRATZOt2C3DpaZyFU"
    "NW1N3FmSeRvx4Gfx+jeLq0/nNVXpqWVQEadl5Iv92fT65pPl4uez2aGzFBnlVC3nrIFGWm5zzkoh"
    "UuUL45VAiiqnsfufuBhNbPMoo6r+8pl99tH+ww/33/3J4xAFoFkGxCm2y2ThhbRpEIQZbLDvHb/6"
    "T2kX/EgIom36mhnAhPOf6PVvVjefz7gkNJjBW/TohksrCBdn8ep89Oid+ycPjrUqBJMdjGv9XqhK"
    "4eeBQyTUyoYAvc05i4NSIkqZRMrSEWwUWnmhJ2XuCggXZLk6vcrjq7xu3E0Z4QGMSkkpwxrRWHLE"
    "lFujG0Ypr91zoSQ1uIQK+++Nl98sLr5p8wrm9KVgRYfKCBJgObdr1agSVGMBxXrdcQeM7NcNOrI4"
    "oak1LayFmsIQABFkpKZxS5s1Q4aqA626Kywq0uvgCnAADdX9/8flWheLxYyrSrKnG6SKCBArE1pK"
    "Ksr0fKQDo1lapyYvPIxW1eymHX91Nv/oFHv3Hj94eLy/v1+OkkAnbtys0CxpDnN4hieIxxjMvEas"
    "fSSmESJqXpy5HI8PPkzrf3VmoHFfEhEZGkJCU8+vnr34zfL5R9i/Px0fZgjAAPrIcw0NEa4ZrQZK"
    "7vgqBLj9SAFYyK77R0CgetMsvz798uCdhQSSChMhxbXkc9aToaLoM9PfqBgwBIDBfgjmu3B23xjv"
    "Wt4jVG+F+sly9auGrWYRaOFwhlQIMdOXTXV+PqYc7R89Gs8mzm6oEXdb3mVPVJJpQG2elHQ0cOt6"
    "zuw2iJxuKKLkKC1Z716wtBZDlBppHWFBFFY0CAUwWDanh4oUd3PzTGEcSzWhhkAxA6SQ9yiwV+19"
    "0KanN2eLug6Cc1iDnN1K1SKMlTlSZtu2uDX1k7d9k22bSICgMgILb2WGRUCBEWUkQvc2pcZ8q2eS"
    "Oz5UwKHOhA1R2wzj9zF/0ebzKwsj/6bWKpjAUmuZCocrzI1lrcIhdpO0mrdSt5wu7f7HX8snn8Oq"
    "J4/f/eDBgwdVXRdYTMsgGw3RO8YL1mWTw3zt2VLLzE4AIVubczKNAqHsYe/9+uanN5dXNV7UVQVH"
    "07SgKrPL5Ww2fnb1RXN5Oq/3VUKGATml1LSJou7R0FBcvIKHne53/yjdIsStR+piLR5mGe7MKRlV"
    "2LXgRDaDGy5etFcp/lvh3CEADDbYSx4Zt1gNCljTpFUdKg0CrxAeSf2+V4+X5oEpqIoHNyODqKwM"
    "56v62xcy23/n+NFjrdQ0l1nZIq1eqCm5oWu2AEySzZA9KIOOwJA8KUPOLgxGOA0sCrGE1VmQRTxD"
    "jAoFyk7TjeULTyaIXb+BTcOVjauEmo42Zaq6TN321s3EvMqZARUKCSYCUWH6cGp/vbq5vlj/w0Tr"
    "kYxE0ZYmo3iqRq6jGGv2PSD3ItmCrpDodlwVZUeC4SbrWGpRkrTcuikw8WqOGLQq00hZXLvKQXti"
    "ZwOBIG7IhuCEsp6c/E3L+uKb/av2H4/Gl3tVZroOsgQbsLAJBTKAAVChUPeQ64uL6vPno3/73DF6"
    "+OHP//btd97fn+91sLxoIWUGEqRFbpZJmOJYQ6y4tmDu1XjmaYYQQiWqTsmOnBECZggPw/Sn66tv"
    "DKmus7VJx7nNSQPpzd44nS0uLr7+5EDvxb3DEA0pSQriEwUkBjenuFsNfl+vmL1mdQzdc1YUJ539"
    "os1GTQg0ON9YcqAhAAz2g4gBu0wYEKAKETBnATqmOnsfNz97/iKjXdMhrp6L9Hi8ae30an6+nH74"
    "ztvzgxMo+3FHsv/8uwMsA7IRsq+Tt1cXvlrUljyIZa+BpBrNAKeJZxpo6iYmhtppWdcARikW8aoV"
    "6rWM66oqbHJFHRaodPxoufjg+fOmUJCSJKfNenx6MVadiYiIeO4IQ8koPMDsw+nR6sU3N8+vv7Bm"
    "rSA0ZKL15rqNVwtM9gM0gBAim79Ci1EKBBRCPOboZ2dXcnNxA1pwJUIyWeTq8oajDBeodAPy3UZu"
    "v+hbqFEVngtFEch6Njv6uUMun+Gb84+fN+dBMJ3OKQ2VolBEmroFy7Jcp/Ov88V1eHETz5bjev74"
    "vZ/97bvv//zo4DCEgE6krAtdIICIeFLNPly8wNnpNRStmKhakvV69PwiNFqDkT3ZhQEie3Lw83hz"
    "fnUqpxdP02I5mYyymHkTyXWSxdIvF6cPjtZxD4Aj1Dr7Sb6+/ubsfN2qu8eojur7T0Jn1A0m35zH"
    "1qKTGvqjYemsJcDfcMb1IQAM9gbbdnhRur8yF/2+spLTookQSsTkyXj2v744O/zk6y8tleEQwFuI"
    "rk1u2tHJ4/eOH78Tx+M+iFhAAJJTDMg0gRBCTDF6Kx7459/y+elkvQDJ5K3TQqjM3ZGNlqUbvqSL"
    "Ixgty0qpE5taMscq6ehMD44nxzIeo+O1kYBDmf4lbyaX6eEXX35GOlKKsfJUNagn82MyExBBYgOI"
    "Izhqyv3Rwd9Wi3h69a/Pnn6VVuYyZtDMZuWAHmoc5+SFSU26/QJ4D930S78CiRw9ltn//ez04eff"
    "fJaaJiIoxWlrVqPZcTU+oEpGDi7wIo8uCYC4FmFjKxRuWbFqkAELI5y89d58Pv/647dffPV121wv"
    "n1+YtE6DFlRMc9LchpyqxTIZYj07fPD4/sO337v3+MloNIqh1xojOxVrinkQ1Ajvxen/dfni3m+e"
    "fbVu0DK7MCKAo5WN68mRyywniQFFjkZYQd4eH+j55eE3Z/+2uFzW49FVWmVb16TlkONBPapOr5d1"
    "m0Llghn2/mZ1Pvvy2WdnZ2cp56qOTVoav6+nFpeAep1H0/kDjVWTV5WISgUXMNM3mxWlnspvWgNg"
    "CACD/eCqgU2qKNlz6CRqQU4nh399kh/q3uV61dIYRB3ZMhAmLlHreHzvXqw7gjPtxAsdkqWbg5cO"
    "0JeDehbe/vBwvHfWrCRWIxPLng1M2YMScBND1wakQ4zZpWFCtAkTQtW2Yk092js4mUzHIJI7yIQg"
    "4WR8PD9qT+LBlYql5TKGQCM1ynx8cHQvtynWIYCNtUFCJ1ZVHR08+k8W35ocnLupeZXcoA0DheHw"
    "8Ghv72DbLkFmD1NvKTydkIh4OD6Z7tsJDv5MwJDVUiLNouRqHGez+Wzec5BQugk1MUA7BjctXD7Q"
    "ELubkcylnr373i/eObp/dnV+cXWzWDU3N+uLVVpkb11IjNTqaOOT2bwej6fz6fH9g2pSS6yqArZ4"
    "BnTDUsKe2ZQ6D/sfHuaTx34hYdIKU249tTFGBg1VvHfyoNJKOqY9L5PB9d4H9985YfWzZtW2KR2P"
    "SHpl8ISGNpvuj+ppNQ4Ja0et43fm9w8fhnfmbzWWaSx67+l7fhzVEBI11DaeHdw7jiEoHMg5pzJf"
    "V1rnVugyNnDQm7RrOQSAwd5gc9lSFW2np7vvUGB0tIYy9i7Q6eHDn8yxNslwFRc6gOBOI0RT4cMg"
    "RMrH3qXTpNoiQSWyVFrt7R9N94/ehke4ZElOyxS6BOuUxLu6xFkm500aNdEUu2EZbdbBDTaCAq1s"
    "yS1VqtHDdz64Zw6YOrTXIs/SOhjYiT7WEgou3o2NV9ODx+8dPTYj4AHoEAZ1EpGUHRK1rX4vZReA"
    "Ami5ro7eeesAjwQIuVYjmDMtFzagTXx1dM2Ezl2tQYB1N82SlBqVJmhBcUSMsPfW/b1HD9MCOaeG"
    "160tsq8zM31ExMA6iFaRsRJVBQKs3+7ecmZ0U0vecVEYQjW7f//D43cyJBMZECRKJrKC4lWJwVpW"
    "aUBRTUC1f/RkfkSYoc2SCYRUi6Pz7F7BsgqAAK9G+ydPDvYMBtCc8jraqHSRTBBtLByvXeTQIjLq"
    "fe0H7YUa3rhNmyEADPaGm+xs4cgd6QIiOlL5YnXYBwtLZdwwXvQZVyFEKvCRvJJsePuqCNCiA15i"
    "S8yFfo49kQ7vsLwRrAs7Z9dckLpCskLB1HtR6WTbi9gWUQg1u1l7lY3n7X7fgFx+3yBQAmrFPbFI"
    "LsbtgDm+B+enixNCyTCWWRRloZMQqBUmZMjOxtOuWl1PIcfd8Rgha9+sFJemygTBQyUHhknuUulQ"
    "+EQVheDEulmp3P8j79CWFpodMUDKLVDBVkmZm7HWjVZBdwdguedALWCSgwotm/awPqT5prstXetf"
    "KqIFoP0A1iu4tl75uLn5nciSbD+xr6AZ6cXghgAw2GDf2/u/FAzuxoAAmMFECjXbKxYtHamogHQq"
    "h7tKKbKzMIWi9tSRdW6Ch90KFwICLHsGuiNgm0CHEtYNEdKCSgBaB4AoQOhfp39/KyQfviWW2fC1"
    "lrDXFnoQheVuNbyQ/JR8PXYvxZcJh2R7grciW7cqUPbppDSsiyMo5P7F4e70Lbt82Ou7N6TLpkPv"
    "fDvpR2cox6OoikIDNuvE3TWMXcQKVhbxvBM72lzwTeSWfve7XFPzXhdCoOyFcV467a3WPEDvws/u"
    "mh+cyCjSLuhX7+LdkbPv81iqCBQFzCJ7sGGFjhuyRe8IXRR843YthwAw2A/BCiGlbV3kBkntdWyy"
    "Fbe4+e51LsHQJbxByjKU3/IWBfXQl8KM7WRx2vGP3mlFWL8rtXEbRanG4XHzs37vtKee3wA1G6C5"
    "iA0DUo6tKDl3ro29yxDdDRudG+uS7tfKKelQlgjXrR1jQ67Xeajb17xzab0P7d4rdWO05Xp5WawD"
    "4IZGoO5CbknN4bCOSGdL6VpKAO8UyrZi9eWo+uXlsGWEpbPrFRQhhL706aSQtY8xux6WWx4tbnWZ"
    "d1ux/jJJE793BUBzGDrqOtmeLOEQ6/ma+g+V9+83LIINNtjrmd3NZ/uVJ9nuBDeEwMe7kxcwgeTi"
    "Mgi5+3R2vrVzCQ4Q2vs62XKkSknud8t638myt7JZJZffqC5sc3Zo55o6hUT4LnqTu2pgy9pWkJiC"
    "khceylDoHuAlid7qv9wV9PS7p+k73r+7kBKA21Kg5d0Fu+4ScCL1S2Sb2qntEvmdO6Jbf0puuDbL"
    "udDhFITNwXgXP7pmvmBH67Tz6btcpH2g7hQjeRufsg4T6lspW5XT3UshydFl/UACIAgFGCQMiDCW"
    "Hkh39N/7sW9YbANAWWRw7rz7XXb3oQIYbLDfIwDcRoS4k8F5hxgEvDxo1/2GvPSzkr7ZFlm6/Wbb"
    "P+7uIXekAD2I/Cq0ynGbrHXXYfndANb7sE1qahu3flccy2+Lg8q2a/o6hdRddKwjtu/WVuX27/BV"
    "QByKsPDmH3oeJQGMcIPTnV5ICR1uoG6cJbZTn3SnUnaKKnR3ii/pVJN3pG+2vnX3CHfv8u1LbehV"
    "gFEqidtyzQW5ev3PZYYI9I7SfHlN3x0npfVdh2EMdLDBvrffF4CbhJF9nrXZD+CGHDuikxnpZy62"
    "LiDccf29I9hEFSutwPJCGRui6BSY0SmJy663JcIt9+K9suAtCKUlUNB/Ky6g0Pwx9GwAolt9m9zh"
    "2z2KbNwoHwTpqCu3/V4ncg/j9OCC8bcOmXSt8g6R6kAt70ZrAEnwovDFzRWzTh9G5FZEK85+CYgh"
    "yiZmFMcN4QaY2kBh3RzkxlsH7Pje3oF751FpHZParejan92tmqbUIvrKE3fZDOEg9/erLNhpD26B"
    "sS9TuuY8+xtadnp/16NoV/+E/vbB0RpgkjvBZ6LwlIP5pbA2BIDBBnu93NVuf4M245i7zrN/Al+d"
    "/PagsrwCXOK2hOiRJOvRcsGuQuItKOlOHbADRjsIKNteiFH9tkzLBgbZ/qgn5bftkYh2J945QYOV"
    "1rQCQBk3lzL1v20I+/bUfadB6p1n37Y1enGsVNYaiLyZAb3bNu+g+U484nbVY7eu9E6m20tU3C0+"
    "tufboTclMmphgPMttmSGW02Y3Y2QQoEhvEW34B0oI7zddCWS3CqnOlBu0x5QvGYT2Hfue79/0V/q"
    "vl2zmQclXl3HDAFgsMG+2+RlmOXuL2x9WT966C9povOu/yFEi6ctY4M9G1zxquz1EW+9soetYxYA"
    "qfga7775gV0VYV0vuuOuZue+tzq7YesgdmNYwQq8Gynawc2FKEJU8K6hDfSkpI5YIOwuOsDKkWy8"
    "FaXLl73nUt0Ep2p7ZaQ7UKpvKgZ/GbYqRVifd+8CKZtL6OFu9O5Bui14UqAn2fji0MNJJdBudids"
    "t4LpX9DuuC/v2E9futEWyrtkdIsgBgFE9ZYqsv12oOx3JiYlhnVzWmqAFAI4CFyCWymnfFOtDQFg"
    "sMFePwD8zh++RB73EgrCHZV0ufub1s3cdHN7G+bRO4wUG8dqGwdtENl1iHf1luWOCvudCuaWHEE/"
    "Vrk5ka7HCdkcdYdi9+mm9AD35ixeXT5tex53+sZlNP4W4v/qF+HtcVi/E1+5UW/eCRjbd+kbxLZp"
    "j3fTp7tDOeiyeYHcmr7F7XvRxxgSvqsdDQCJENmd+NoifuV11HHrfX//Ba1btaPdree2VVtXAnAI"
    "AIMN9u8ZKjZIsb0qlUvoM1HtYIctiESWbaC4/ZJ2kza5z7LLtEift6LTE9/MB3X58gb77v20d7Lj"
    "aQtO+MZr5N4PFgCEW9n3u7FMuDvi0p3sFk/vwAU6oN1pdexJhcc/AolYa3cugbc8uOxgXP1YC7r1"
    "WOvCjAFWeK+9pNLcHZANtyoGbjvc3HGzPWbWbxh0EFzA7vDWFmHb6c/3uvT+ygpj+5dXDdo7wCA7"
    "7o6vhK3+52LBD9GGADDYj8t8M8BuvRQW7wLIsN111ruOw/ESfGQlSc/csLmb3t2xgtwZQGJRetz5"
    "hR782HU0fZZcRpJgRfD9O/zQrTrBX5mNlplRdmm4ZCA5wk73tS2Nyc3Mz26wk03bY8eJ35E49/76"
    "YqshLa84Em4W6EoltatTv3vNve9gv+qsNrCYy879Et8tOe70gXafzdutIH8lxmM7sfxPzoYAMNiP"
    "zzbzGLTtdn75P2Gflm59ymaivMuhd7JsAbjexZ/9DqIAECa39ptKSlsEeAtuQyJIBxNlIHXCA46e"
    "eUF6gUrk3vvbq09KBGWr9lUwC9suABA9qf2mtSn9GcbOjRJA2uzWoqjXdr8tILZrdzBB7noc/eqv"
    "3goAfeGBjStOBveuU71VJFV8V9yVnZHcO5veCWhBgONbl6O7BLdm8IFNP7mb8/Lu9lUbPR/eqhVs"
    "Z9Xg+zFqDAFgsMF+CJVAB1z4q2LDroPxPovkxvtz898G+id29sBk6y+sf67sQAqlVVvgpgCodtu8"
    "GzTYXyJp2NksexUYscH3+33oshUlt7ue3BLR3AJ2dmH9sJtZ99trglsrrtuCKXdPb7vFNu9pzcrE"
    "J3eLh92DLetRu7wOm9kYuT00tele2EtnbeX4u5ZvEeh1cDvLmzql3RJNb+0qdyyc5Tndure/jBTd"
    "mWEdKoDBBvtBG/Hd/eGSffd+x+VWbdCz2XTbBrpNn9n/Mh2RViQLt3DMLnTgfcHBVLJ+3TAu+AYL"
    "id4Tq3WDLp33sS77LmPvu0Q3RFmY6tGSXVlBsU2CjcAy/rRdRuu4faR3ee59a7R7cS0EQdj4bCB3"
    "Cskdu0V5f9286Z05yA05BDfkPEW6uRsT2oYoL7fACvPQBr9hP/HjEEK74Ej04U0c1XaasxBw0IDs"
    "O6ObL0FH1lMuVB0YtFsl0Mpe8abe2swV6Z/Y12UIAIP9yBL/V2fQRAbWwBpo+nkQ2WlLhj5JDUDd"
    "w/HAxh33kBGLv97w+/D2BrFnsCm8QNolwtrt93oNmxY+uk340B3EibcwjRbMd7eat1w3eQPsEKLQ"
    "Hh4pP487RYOgV8/pC4LyUmtw2e8uVXAtIvKK4Ih5KwTZnaXiBlj33ESxYCl9SCsXtmdpQ5E+L85d"
    "gV59uVPIaoEIHtiGHnWnhOEtqodrIBGFhK68fgClJywSgeXvcNo7scm1a4o4tnM/qa+famDsLz33"
    "T6oSGALAYD8q75+RSwPU3JQBLsgl+U3gEnKG1VM0p8g3mxUwZ2TcR7WPcADM4Uf0sW1cNxqgFYCo"
    "OkqDu6CSocwU+Qo4RbqCrcr2F9yRHVWF5gbch/8EUucED2KwokJTxsXRsfxnUjwtGW7QngMLoN3h"
    "nZFuTykV8cYIAmhAgU+gFUCgBufwSZnJyWhZNnsJmHhpc4jBv0V+AV/DHDJGzghEAmTGcKzYMwRH"
    "W9iYK7RIX0AWyA3cESpYgHu3n+stdA01OJCLYoxCBE7kqiyoQTJyQgCsAcaoAjHPpULZ8bhdE8Ya"
    "8Br5G3AJjx0rajcIpPCIsAc98i11XVka4+2KRLu6BNdYPu/OOiWodz0YG6O6JwgJcRf+GiCgwQb7"
    "QSNAbKwZSa0EUgPPkBZY4PJLW329Xn2V2+f0K7Mb5AS6U4hadCRhT6rDOH4go/cxfiw8hkvuO7QO"
    "344z0jrXI5tWcXErN+3p37c3nwVPuW2o4u5BollKuYnxgVY3evxnGsdtBzfBNvhRQTawSZlvlmf/"
    "mm5+E/xK3GhuCAZQxN1VY2HZMUsM2QnHiFJJDFLtxcnbqN+ingATMe0G7c3hZJkOzefr8182178O"
    "+QqeFZWZi+ZkMVdP4vz9MPt5iIdFVn4EgV2svv0l289hC0POlGwSXRRBXDKy6drVggd3h4tTWlI8"
    "xBTF3JldchC0lszMR29hJjr9Saznm4w7Izs8IMIa8ApXv754/l9FLvuBWuvY9BAa1uP5B3H21zJ+"
    "lNF42ayVntKo6z9L16ThTTr718WLj6p8HZgab6kmtBZVlnvV3k/D/GcMxzA4TFXsTy8GDAFgsB9Z"
    "ESAqNSAwgSfINdpP8OIf0uqT1fLLvD6LTCpCc8KF0S26uzMl+prS1gdh8q6OfhHn/xvkoda1MyQX"
    "AKEjCxKg02XJHaiSCYO1yE8Xl/8lXf9qqprXK42VmbVkmzMV7fJBk1fV6ubgvb8zHXe9iltyKpvR"
    "IwXWafnZ4vLvR3wRvBVzonKnK3J2iSNLSZjh2aXk2CEjJzasZvXNO1L/rJ7+DSZ/LjZzL/iWgRmk"
    "QKFrX33WXPx3x3lgY64AzFPKk2t8fXN6Nj8ZnTyYhVghZ3CNfIHrX7eLf1JeU5tMkOotwACLQDbN"
    "gJkFd4e2mZYVZiGkERwm2ZnW7mbIiM3yxfNvoHvNo8c/n0zn/aB/MjgRYWvIt+nsv+H6/6C8AKRI"
    "FtBFDIbYYry8eZGfj+6/eySTCILI8NwDfu1m7ggAfC3pU6z/Pq1OKU1GQoC4Zcxv7NHz0/PqACcP"
    "/zLWkxIk9S5wOASAwQb7YQUAh1LoQL6BXmD5b823/5/FxT+O4/PKLmMEJRawBXRoRA4g4W2FlL1Z"
    "r0/b9vT68rRepGr65/Xhh4zz0G/520ZiF8mAMjpJaEn/sfiMzRcj+WasNeoEKoJlszpCVZdJrq8+"
    "fn5pmD2YPvhg01/eAhelo5CLplmuNJlej+SshiMbUIGE2nq9rnXW5lUMCXSY9kJXucEqNS+a9qLl"
    "+c3lcv9YZPxXDDW8LEJsVLjWFa6X+XQcLypNnkgSxChwcX359dcfLZqf7B/9IoTYzVpKrnUd5DrI"
    "BWRN8aqqiBamYB3hpg1J2ggwyDqzTQJKqFDBEdmYGEkiQEYX6/Nvv/qYF9PDo7fm8/lWv6ULfi3W"
    "XzbXH03kWeR5p89OES/CPVWsJt9chadn/6j1w3vvfQhVR9oQcvvuwrYDTKJXES8in8eYKrSZRvfk"
    "jcn83776NS6O9vbfn4ymfZfi5ebREAAGG+wHg/9Avdew1ee4+dX11//f5vp/7E+usD5XIXyMXOZZ"
    "DLJGXgBAVvgEDEpOFIal+Bc3i/U6fetcjQ7+nGG/0Mz5Zru1R607NiEHcLk8/7jym0qI1sCA3EKh"
    "kkF4agOW0/H16elX56df7D14lx1pvOzw2mcHIQFm0CCIgaLZYYRFMAAOXwvdzCghM8FNXGgGBEAr"
    "VBUk01b52eL6/3ze5vEc85O/gtaAOLTopkOhROVeQVA2hQvXXBipV8vrtl437v3GrisoXiZGKRnM"
    "7k1qA1xh8AaEI3kZE3IiUylGo2UUbXRpYQkU85bu8PVqeaNhqaUxg+xlD5pETpAlrj7x9G2UNTzJ"
    "hkPbAVMwBb+ZV9enfHr6/FcHD+/FyYG7UDYjudLfINk0hcQ8WDf/JJ6K0HJwX90soY2XpTlr/+QG"
    "gIYAMNiPz4SF7+sc9tXi9L8vb/5lFi+VNxCDK4wwhUaECSQnW5OuDiTpHRFE0ojXJs1ilc6ejfd8"
    "ND3+C0iVbcMjvBlvNwLIpdv69Xr52YRLRdm9JXKGsjDne6KGPB4vq3hxef7VenFVz6ZbV+WAWCFX"
    "kKJtk9yy09yzwdiBOG4mQJyu877qCGyTraJQPdHWzBkeIaLMY10inr5Y/PP14lDj8eT+u4BY0SEu"
    "mTZDkNhVTFAgAsytJBNTSpCEBqyhdJImrYMQR6WqQvOcVPsWBo2kIZuZlCssAhUnQQUDgghjyg5S"
    "EWIYm4NOd3fLFLh7p+vuGbZcXX+mcgmkThcT/WhvWVNeLudjO9i7fHrz6+vrnx9PDsmw2cCwbuVt"
    "l4hfhYEk3OHuJAkRtRbCClq3RZteApCz313wHgLAYIP9kDoAMEBuwGft2S+Xi4/H9XrE0FznqprD"
    "HFCLMWG8zvV6FdbJRX0cm0m4DrqWlkgZ4mRTh5yri/PFvz79tr4vR9PDd0UbdupTod+Esk6oUpa+"
    "+CfqF0gNoAg1RLxqoG45KoOE4BTK9Xgcr65Pz55//WD6XqfC2I3Vh8xOhxLiMCHVhULp6g6KAylM"
    "Wsy+fT4G76nUlLaKi3F1NYlnUZbSEtnhWWIeV3mcwsWzz775+qO3p4dxflAOVylAQJKEkFwCmQSB"
    "ghBzDlnZ0nJMWdfOMcsClZBBKTHlFgiuatZmy+oZIMREHW4igixABSXE3emubp4YoUUpLLoTMs8Y"
    "ExEqFIFTII4IGDTb5ber9vlIb5AdPgIk0zITCAU1EzaS3E7Gp36Tzs4+PTz5qVLdCm5mGy1PIPX0"
    "omhJBdXEoKYitJSZGbJqRpUQeoH5kLwRyjAG+qfiK7jzp9skLuXH/Ybna77sncVIDn75P/S+JmCB"
    "my9uzj/S/CLqMtu6qkZwBSRLtcb8/Gb+9Vk+u/Bl4yHI8cHowdHocLSc8krFCkl0Wq+me3qzvHl6"
    "9kkYfTPZf1sCHfnWJq0AXn6yXJz9psalpxsHqALzhpFAKNECMM8iN4ezg7Ori8XZl3zyxCXurgR3"
    "+7fW0ec7t2u+7q0DzmjmVzf45cfLJqe6mozGsQp2cpQfHy4P67IjnCEO97y8mo+Ov7HLp9/8Zu/+"
    "B0fzfSsUQGXUXlQYRMSpdDU4vIW4qpo3TlNVwLM7GMBRqw8bu1hcnZlZCjHnVFlTyXoU0rheh7rB"
    "ZuPAHS45cZniejFrk7Z0FwqDmXly1JPrZZxMFC7d6H9pZCOBF8ubz5EvBQkeQTGRLOqMgJkYIcKA"
    "3I7CxTj6+YsvF9fn0/GxFjfmcovmtNDKuRLBlBoAahBxa82Y4Wbm7hSBdF3kINVL31bD3QlRGQLA"
    "Dxgj3kidGkxv6Thb/3Xr2Fxzt5n5GjGgMGf5liWm33bZAMd3mHIH+wPfYIMCbFfPPgrNc/EV0wKa"
    "Ey1oaFZgmD87H//jbybfnNdH994a7U3n8/kqLZ5eXwGn4/pfFV8DDsRRdbxayDhwVuvzs6fV/rMH"
    "D44N9MKb7B1JjRKUJc6/1MX1SNagQWnNEnG6zmqNH8SItPQRszXRw8hXR/Xi4uyT6/Ofz0/2zGyT"
    "9+uGC4ICsYxEc5JJzenIjcImqK5tlMPR4Vv/+e0nH4SqatKFrD5y+2/WfkNbAmsPIKmp1raqsi1v"
    "XizasznWAaGnOzBI9rymgtlEo+VMcfcGeV25sNFglSNIJ+NyNHnwv58u3/qXj//p/Pwcoc45Ryba"
    "2UH1/O/+4mhkn9dhiZy66iib6vzb5/IP/xZRPzEzEYFLtlZVG6tTOLq/f5zMAMnZRaEGyhr45Ob6"
    "Hw4khzULvX6raWlAGwVhFB0Ctwy2E+FhHH9+dXF18WI2ngE1eto/BZzWK9AEesUkgGVvSEmpVRGK"
    "q7dC9IuBoAC+oVO1nW+0lQ3m3e9tR/vhrxL+HALADyLztzvE8be5VPg/xw64GzDkZfrGLeXtltVk"
    "sD+cZaQrts+CvwhYqcNczMVbU51frw8+/cLObg6P3vqz93/6i6Ojo+l0GsWb5dn6xd9fLq8mUUmu"
    "ky4uw8UNrm+as+U5Zmfze5cndgCS7Hn4O/KAVdArW34i+aJbMYVCmFE/O2e7aqcnGitJvgaNbuqr"
    "SXVxsfh2cXk6PnxSmB8cmYUv8/anUZ1CGMTpVRXROlLOrVP2xvtvP3znL+ezeZPaaI/09DydPVeS"
    "lSZkT7nykbWsYoA3q3btyLRAhp68yHv9GNClJ6tPdBOImtLDRm3ZUeXwaHRUPfjgwcGqDaFKloM6"
    "0zdz+czip8RTs4US8BYeDMgt103Mo/dOHv/n2WReaSCZ3ESQ4dnj4eHhdDJ3d9FN7/UGNx9He+rN"
    "NYtslgQRLK/Wp89XD+8/mMTG80LEgaw5Tyur5Obq4sv79x8K676E31TtPTuGg4DRBEZXOuGkb77p"
    "ZTtu5+uJHVa4nulo58YI7tDw/cC/v396AWCX4WuH1URZlknKQqMACNLJwDrs+7t+9dva0HcpU+xP"
    "k3X2Pyq6G9Bi/cLap8HOVQwIkoMbyGw+e/7i8OnzZu/+g5//9Z89fPST2XTmyArn3nS9p1fP9JOv"
    "P3767bOrRUrtJOfoTtbz/fogBHF3lVgIxoquoxKCa+DjxfK/RzmDmru4q4kmzL99Gtq0fny8iiFl"
    "awUEVZjq0aXchMuzb+YnvxjvTUvQEhi7vFW7KFJ2oFzElE5rDKBoDFqpRqL0NjGKETyAYJGWo5Cj"
    "qBskVPCqafIqLxdLX9+saFFyAMuC8Gt+Y8ig4d69e3uzA7ioxjanoM50HH1y8fkXLPTSpJuTDCFk"
    "E4NPp9Of/OQnjx68FSWSbK0VgYu2WWOMo45+1AC4NMB1c/rJKF0irxG0yJqFdrK6iN98k472Hmj9"
    "nLaAGAgzH9dhUl1dnv56+eQXsZp3LEPUjS6xA0ALts6GZW8ZQRw0qEfNZRs7isUdfck7jgKk3Gav"
    "2/06px+BC/1TCwC2w+94tzIgbUuAgq0Y0+uVFy8Lh/J2z2E7rIY/ta2Tf//o7shrrC89XSnW8AAI"
    "sioJ9dTw2+cZ1cN3P/zFW28/qePYAQVzbkW1Hj/IJ3/TntfX+uVS83zv4Wx8MJ1Op9Px9GBvb3+/"
    "sJtthcPLWCUzrj/y9osgCWCCuAT3atnEF9fT0fgoVy9aXoFCEOaUVOvlfDp6ev750fWL6d50B15w"
    "p1nXFxbp0UKxaE5aKpWp203AZfRnNZ+Sc6SMm4/z6lkVXFVzbi3nGEL2jKDL7MsEY+0Wf2+ug5yz"
    "qBMcjcclOw4IpKHeA+YFSRcRz0aq5xYaHWZZSdbVeDKZd77GK4g7ELszdssuIu5ryg3ab9qrr8b5"
    "msxQhXt2adt6ca1rn7fyINl5FOunfUTR7I+uLk4/Ozv7ejJ7GALvTPGzkCYxgd59l8uqGm9ReTg3"
    "hf/3bfH1/f+NroMMAeAHZztydLZbFhRyqyILuKtB8Tow9OZTeEuKbxdbtP7KDwHgDx7gW6SlOoSh"
    "9E9hjkBPjQsv1uvRwf7x/QdBqyhaXEGQUPjLqtHR2+//+cHJu80qzcYns9HBuB5p0Nsakplkp47l"
    "AcFunn0efCmIMBpbl5g8vFi0izze33usk/Fy9SKqwRu4U1ri5mC2//Xzr68uvtg/uafVCBAib4iM"
    "CpTUc3YKKOJErJGXYFOFxcne8/3qX8K6hRM3L/LVJ958Mg6GJGaibN3XTSbG1U1Si4fV+LA1juLv"
    "qUcrIp0kpbubAeIEnRDAzd1zzoya20ZDRLZSNIgISTPLKakqQHeHmYtukJbCBE0YcOlXn+r6VGQJ"
    "dXib6SZ6vRg9vWzD7EOZPcjyUURbjojUlJb746tpxNnzz08e/CLE2CdgTiO5Yeo2uolTfLNTAKO5"
    "JBPP0iZdJ4Gj5fYek71j7On5cEsl4lYFEIcK4Afp/jeaEdxF7LkTA4rc3et+Z3bBn1ep0/lW4E56"
    "BHawP1wAkNa8AQBKdlMaPAFqlrxCSx/P5+PJPErVUTqbQ6QQTKpM92b1bGaeKV4FCbdLt03qV2ZX"
    "DFihOWuvvp7GNTIyHCQl5nb04jInGU2PntTTvZvVU5gBySyJQKwZV2kyulxcfHpz85N59VBAd/Zc"
    "QNITOJvRu0yzvJ053OZjvHsvherL9bOnzepiHFprTqPeQM3bIIGImg1aH71YhGdnDp2P6r1Q3Ju5"
    "vP6UIzdVMFlWrrhpXuUsIp5KbCDcqQpSKCEESRu4vMwfleu8E4bY46V+2lx8FgrrJ2E5W1Do5HQZ"
    "XyzjyaN3J0f3sd5rFowEy9pYXo+ri4OJfrn46vLi6WT8iBI2Sf22qber97L9MrsVMTKaEQYzODuq"
    "agCBvcKzwQTmG60Ivmmi7kMAeF3PfwvYSVYIe1EIZrtPiFMMliECKO11vjGSN8N7ryCmF6D7TtyV"
    "MRrsDxUAkFpvMsUpma2oMScgStDs5pWHcQyxDhKRgAzEnQVQFwcDa6jswHS9vglaouDoCgLaAC/w"
    "7FeKC9pCGDKyqrcW1+3k/ArVeH54+KiaPmivnuXlZR2WlBUsB9Ztuz7eX39z9dHi8s9m84dlCGib"
    "P3gNh3gyJJOWcHcKBUxIqmIn45XwGVsf2xKWUecur40ZQndkztbNvU8/48317N6Tt/dGs6pTnHlt"
    "ujPLLoHFwQvkFu8mAFKopLqVyVGBmdGSp5xzQYfct59y955Mw2CWpYPsW1x8nq8/r2mgIicXcdEb"
    "128WcTU6Hh8+mR+f4PLBaj0TWwVkcUSa2OU8VmHx/PzFJ8fH9zVW0rvostJXcP+yxmw0pYEGmrgV"
    "fiF6EAuAEEpwIxexEbCUrVjAbQGZXo35x4CE/MkWAYVG1nepyf0Vl8Zf8xE7ulECu40fim1cys7c"
    "wmB/ONPskp0Gd5qLgw7PJJs2QyqJlVl/PxRwuPQj6bRAcpcVBoWbH22HJTkgJV2ENpDn6fLXI83e"
    "pjIgpMbc6Ho1W6/nk3pvPjtCfX9UPXCrSKUWDtHK2tXedJmaz5eLb61dw+G5WwAQL1MoLsgFxHDJ"
    "zgykLlHxVnHt6VvkpwjXsCtwDUuWHaHKXi/Wk8y3vnw++c0XrEZPnrzz0+l07EgQIOjrphyiZfCx"
    "a4kW923lWLvOKkTEDQyhbDAUKwUDVajhNhzaZVsi/T41F1h8zvYUAjCaiYYRfbRc6vlCR9NHe/OT"
    "anIs+kD1fraqyM6IOvKyDsuJnq+vP0+pSbYD65eU3xVQIGC7uZ2ATDc66FSjmiqgUAUVopDyHAXU"
    "Qd+M7G2YlDZf5+i91uYQAH5AGLHt+NxOk0M6eeqSQYIGNQYvIV42//I7HwGoIxg0Qw20TDd1qEN8"
    "I/unr+oKDPaHqmjHo+pQRAG4M6fChq9wiWHUJg1xzkBHQjAQWdECDdqMBXAFX8DXQvPUJQTZW6B1"
    "pCa3ighEsGisr3H1m/bmC6Q2hCksMFfM0zHvf/slVtfTJyfv7o+nCLXO56pqKYOEObJWwoDzw9n6"
    "6vmnl2dP0fEXg1sdSnvpg+tg+SSlrGsLK8Q1wtqZAEeMCCP4xHmyaB7+6tPq//yYNvrw/ts/O3n4"
    "oJ4KQlqhaWC/7wdOhNvxx25ThoS72Y5aJQBxRy7e326n/+WHJfHpQghayALNV+n6s7EugTYnk3qe"
    "l4o8WVzY4gaz6eG92T7aEPZ/busTYuJmEC+Y2DjiZG95c/brF8+/Ll6aGykbBzzAqzK0BTrYAhme"
    "BFnMIyVk0exqCAY1L19VdTBv9ZX773bqkgH3oi5jEEPwH/4X5k/PeOv0tZR4co60AiOsRQGOGUoy"
    "0Qu6/u5HAHAFifIZRQsGNILqgD6VHcVYKXqqLkMf+A9prvCRyISmLq4SxVGEXVxB+KiqPbc5eYJF"
    "OBRtFldXUNHi5ktcv0BdY3LIcACvSFaUBiRGY53AhehZJ/0aiy+iLJgyqF4wbkNu1g6ZTeP+9CJW"
    "p5CMuqkrsnVkMzORTIr6cm8yu3jxtF0+R3oLUemFErOrHq30n7Z7rdKmRJJhsvZKqolZzk2ro0l2"
    "yYmp1fVaT6/45fP8zXnW8VsPH//Zex/+2cHRocAIGoK/Um3+NS7v//xntdNyl0LswzVwgeWXll6A"
    "S1ABhyWhw1prL6dVfbJ/fTR9Dolor+ezUbrZ2Z1xgacRz6chXp9/ffLgFxC4ONmD/YVDtDvs5Axk"
    "AsVAgzjECfcNDUAAEjYFz61lnrQjFu0A/cciH/OnFQB6teuu9cTuE2nAGZa/bC8/jmJgC2m7meLc"
    "jwC4gPa9HtlCFTlDFUL30brdH538OeQxMZcia1HqAEch4Rr89h+yorUInRDqSUJVd9miJQBu7XSc"
    "vbmiQVAVODwoHAwIQIuLX988/++mi2oyrSaPwAPM3kG8X+EIYYokZUCfCsEazfPm8svgN84EEXoC"
    "HLZmaO49nExtsb/3f6Trj3FOpvOmeRbRCAvusYYRrrMR1c6vTj++d/J+iPuOBLghKgVeO2IRPnSP"
    "DpCqITirm7z/q89iwokgJss5IGf3VtJa1mtdteL1ZHzv4K13f/rkrQ/eun8/BIWRiEVXl3/ENZSS"
    "OnMz+GrAGnixXHxq6arSDEmCBG8YoLo6mvtPI/b3/tFunsuiQfstlt8olpuICInwXMvVwXj6zelv"
    "mpu/Hu3vZyNUvdveLY04Y1/6O4SU7CFrbCAukpX94heBuMPMATO4Fy7UsKWC7Ysf9rvHwybwDxP1"
    "8rIyWNgXF8uzf3rx9X+ZaCtsnI17DgxoXV6HJdZpGa0EpmQuZKhbnyU8fGs8x/wIGG9SC+vE8Ib0"
    "/9+hvKsmEqa2ruD0AqvT6KKeDkbL6/W3aJcbJUIFsq0pQHOK9cfS/gvThSU5P51Uowfjiyc++kAO"
    "/w66h9xj1miJ83b55Wr9bMobskgBG6x1a+JI791rW9woPjr/NjtGk8iAZRD06uvJ3KPEnJvD6fr0"
    "7NeLxd/tj/dFkeEdlxThnca6FE7mtsmqdTK/vOEvf9PmMJpNj2I1atGIyEjH1Xgymo3m9Wzv+GTv"
    "+PDk3r3JZKJO5Ny9b4boH2XswHZle7kZ1qQDKzSftzefBSyBBLOuAyNEWh3NR/NDb/JnqxefReTK"
    "l2QiYF4qJSkNiZrNwaj96uLL89N/29v/K7Jy2HZyqQOGcj8AKurREUE1ZpfWdZU5pzshnqEBgDkN"
    "JVoD1iPEfVVg+BFlbX9yAcD7IpSbbXEniPEYY12OdR2YzRsBhAlqfM3NSTogYmyzA5JXJmtfoZYO"
    "kWQQwrqtxVJaDpNAf0Dvb9AMkTA5atYT96VjDSHc4BzR7s8W+eKLfP019u9DtbDQB2mBC9x8lJb/"
    "EuVbDQS8qnKbm6urZ4vLp34Tp8dxMn4YYwUCuAS+Sje/hpyZ38RQbq4DoFYOqK/MmgAVZOiyEhXJ"
    "7s7scEeAqMKFaX28tz69+vr0+afjw8dV3OTFCUyZECgsUio6q1iXHLquR+P9g/mDv337yfuTyczM"
    "6BYpVTWK9ShWE62mGoMqBDCCwfvXNaH8cYYOOsldI73nuis9sBUuP5X22yAtQDNICEiA082FqH3l"
    "7Y1kVnHUiyhnkta1o13c4Wkc1nvx/PzpPz948l41vldwWJSgh0Q2ZewHDHAFanhlOQtayLXKeShy"
    "86ihoSyTE+vyTQYqos4p9iOmhU7PulUe7zGFIQD8UD2G98imtczLIDl4cmSKICcQ8PXrhXsXGAVW"
    "JiMUEalBahFk+7EsIBRxZ65gsD9Mhcepzt7j1ZcJXwizgwSRLIT23rhZrc+w+hdbRJkdIFSAIV/h"
    "5tPVi/+WV1+OZQmM0bYyVskWVK/Ozr788l9Ontx/78PDIBXdYCu0X6blFyorswwJaHOHBag6Kdkr"
    "bwJU65DSSkwEZUyeUDU3EUXrirYOl3tTPz399OSdv65G+9pNBTiQjSYoSvGlbMhmBrOc2qDj/YOH"
    "j5785GDvSIt3zWZmrk7p95IypMM+Oi4TFZRpqP/Q5J+vysFgpMMNaZUuv6zsopJylCqI3X5MEFhC"
    "Xo/UwQisQS8yxSSzKAB6ds90KNYHs/VX159dXLw4Gt9jNmiZ4Uw7cxakU1zgCGhqXB/Pcxp/K80v"
    "sZzDBHkMBkgEGugabM0kYxLjIwkn8PE2mpV6gskdHKggfmgIgdxNTLr9DicpDG7mUtpIjkDPrzGp"
    "Iy50uDlDSdec5TtN7cr5be8oAQrYMAb6By3vQotQ4QTTv5Tqq9w+gzhdFIQJ0qoK1w+mq9b/+3Lx"
    "dOJHrEdY3mD9vL35LC+/Ul1Tx/CxMeZ2lTlZ+ezFi/jiOebHYuoZbSiyjedf++oUNEp0VxZEz5mh"
    "KbtqUChzgqUgscylsys7PSUXkeAM0iZ/MZ3Gp6eXZ2cvxpNZjHX/6UwubUlNnGX8lCIijHEtmlyS"
    "RWeAWdNSIykaxJkcDUDx2JFVEAnJCrWmB6SMKH+sL56Zl71Kd++GnRYXaXE68jWQgUAJrak41eGe"
    "ATpMVCEZOadQiwLrFYM6xOCBRnGYKvLeaPns5uL56dfTow/HInAHU9mhcwTrpIeFGZC1WDOP63eP"
    "udSP9PrpapnZZG0r5GgGCY6qSYIb0yz3prM/n8x/jvg2wiE6ftROewD8wZfvf8IVwC6ZnwvcBUqa"
    "0Up72DyJB5Lfv29GAEHRtOVTbu4iFNmIiW8WCrHTBxvsDwk2G+AYsXrE+CS3HytX5o0iIQLrJeiz"
    "UF+nz9bnX68vqqghpDV9QV+MtFGKJ+TcSgyG2sPhi2fjb56KxuOjg0eTeqJFf1xu1jdfMl+SbQyB"
    "yUHCxVgvfW/VBGVQ0PKa4iRTzoagkibVMkorIkHFPVEMXNUynYbL5dnnePDYBFuiBMDL4lLZo+0A"
    "jejuIRRlLgKQGLFd8BLABAATPCA7xBXMcLcMBqj2KYgVpLtbyipkmXAvsAq75ZjbghlC7mwvdgqZ"
    "9tId2Ob86mXmwQDCpdCO9i6zRfssLb5Auoas4QZVKHJm9kmy8arJVDTrluJqYi65ililGvs1W5eF"
    "c1UIHyAONhWvp1W8vPg2rReYzrDhdiwToR677rokwCEZuTkYx7FYbp7BlhWENoYFUJAbrFYSJKNe"
    "2fXlMp698IePj3U0Q111dU23Ec0hAPxQvb/fwQ08KJltLZLgAitArQMQfx03bd3MPyEKeDaYg9ZJ"
    "fnfi1WXLRAY66D80+tOPVbGO937Wfv10ee2j8Aw4R16hLjO9PkaqKRBP3rpkwoJTHciJDg0JEoPu"
    "X6z3vvwqLJYH7z/+2eHBfYESa+AaN182y88DL0cS2DraFlFb1as8+4d/C+cX01oPUpsR3JmMOTvM"
    "5WDe/OSRPjpYT2yJdgUCwQNzxNX9+vz5839aXf18fm8Cc4gBwaCNN3U0tqQIvAVgilYtga0hCXKR"
    "lfdu4IWQLSJBIBT9MiiEsitrQjAZk9MYvVkvqxg9rymJRAKSaybNs1B3Lq3lrnfVr5OZAMiWXFwo"
    "aK0cSbYkVXBkdaO1YAYIE0LcCbpQkM6hX7bnfy+8AjMC3BpqWq/rGN/51a+Xz86r1keINIikCqCj"
    "iQq19btP8PbDT6uwQhuzCcQdS6jt1dMXp5+vz78dTSaFyyFAytqXysTgjnWoiLZQa5Dmla+AcnUI"
    "GjSBGZYBl5ymVYS1T19cPr/+RiaLR+9UINyMFDjdG8oPfoz7T1QP4HbOImD3aS6ZUb81KICJ/0/5"
    "ozLJtyv81BUcGOY//51urwMCjjF+e3L0ny5bv1m7VIjxEu018gpSKV1aN7RBzdQFpEfPhYyHBqzS"
    "aJ3vffQpvz6b7R//4t7b786OxqoGrMALu/iNt2cqa2bAIkIFKMLs+Xn89nyW5f3Z/k9GYYTIjLUw"
    "k966VPo0y6/X7VcjZGGmREutKyaVWDqX868uz76anzyGG9wBEwkaAgBkwolKYJYhGXR3KYg43KG3"
    "09CXFYeEu4CnGehwITU7RVTEQDBIBEVEg8QgKpSyoLzTuOrGKLffGwGgIRi0dYt0qJaLmM0tSxEd"
    "g7iXPMcBMiEHCEKLs4+Rvg66NnehuDDnHOL4phl/e26X63t7J+/V86kjwMd0CNf0VWWNjJ6v2i8l"
    "p8iRSDQ0Ehg8T2IzkcX1809n9x+o7nmh1bMVPbl3Uz5OZuYgsXzLxfsNTgJM3VxGKIvYyXKb3HLO"
    "66bNhtYQg2VPgRX8x5D+Y2gCD/YjswwzaEAt+gCHI1n5xbP1KumIaTLyiCRtixbkWGWqpDeXjAJU"
    "QAttPU4azpbtvX/+ePybr0Y6fv+tn//d0TtHGLUJKWCF/M368tNaUhUDUlmxiq3Fdbt/ep4y9t/+"
    "yV/8+c/+rp4euDC169guYxBoIL7CYpQul7Z6IdHdxDGyBK1iPVpIPD07/fTkwS/q2RhlPSmbZ8LE"
    "QDqYkMGglboGePA8kaKGbq+dhLrAoltluahXWM5OcyNySkjuaSl5JRpggBBbVivZLkiV2UhBArIZ"
    "aK5QT3BkqZJXyaNJcFWH5CJD4AWRKRxMNzdnnwFLITw7oEQwg+r+5TUvr/yt93/xwV/859nJfoLC"
    "xgBCaG19NfVWml+ly099tRLW8Gw5iWUoKk3zen3+4pPjxQejeiw9uqUhO4x08TJE6lZSsO32f5ft"
    "AWgdKhrA1okwcqlb+traJGtj45CdrnL8EUC4QwAY7EdoCQgOkf3pvb+4yavrc10spfHFNLSRjQgC"
    "yEZyzlrft9ayAyFAdbHWz0/x1bP01VmMs/fe/fA/vfX++6N5zCVvBe3s7HqxmsQ9yYEYmVClThgt"
    "7eBmtZTqaO/wwezoKFZVC4y8DnmvEAhBDfb2zdmn6/bZPFiyMbVOtspJTeN4Pn2+XF5ent+bjEGF"
    "jJ3zbCcpKEIQQZuXThGMG993CzmbJYP574NAGME9w0nrFd0Q1N0orXMOPZLglEhzUMHt3haxs0bM"
    "vuXgVeae+0FVVSBT29AITnM+NHiCNm3bwBQSun6BKehofH19s2prn2UE40wsmoTWPKWTs8so1b3R"
    "7P7e8aPRdJR2+Fp0PFIYlotm8e6yWXiQINmwFGFOa8jeeDp/+uLm4sVZPb03qkbwgDxe+37bImgV"
    "dCaF8Q8hFxSY5luHLkZpJQOiJplQqZMdmswRqp7Cq+ND/dFU8EMAGOxHZQoATnatfNbHx2/9Z4bj"
    "F6dvf3n6ha+f701sf2TqiyhNPamvVpJNsttqgbOFPr/Qs+vxIs327j9+/N5Pn7z31t5hCAiKIA74"
    "LMu9PP7JxbK6PnsqrNzLOMvk7KY+v6knew8PDo9iJRnZIWUAFVYkCSMmH9azm7OFXL44u2msqqe5"
    "TcbWJd3kycXCTq9vDpMFrcC5jN9ZygfnZ1+sVw4R0ZSRAusXN9OWhwwzaA15TTKy0hSQCaonSZ+f"
    "XnydUuOuAAJy8upiPb1cy8wnjYeaoevxuvRFQJY+vMIAifBDrd+7urm5vHiOlC3lSgUybmx8vSbq"
    "EVQEURHgMDOoAUZ4k1iN3ru+zi9W1+7eZodoJpbN+KtnYTR7e+/o7aqeFYVtRZloSgYIao6fxPl/"
    "uryKl9enbbOE5zq6tTeGyVLCsg3fni2OHkVUAdzD9Bd+na4WX63WF/CGJIwiamUAu/P+7gRAp0Mt"
    "WQ4e3R0iy1SfXQbzKWVkEAOFtwj1OASAwQZ7Q4xAgJoZhQBSshBE49HRg8lo+uT56JPTb3/z7PrZ"
    "t2fPU7OkeQgppalDDWnV+NVNnfxg7/CDB/ffvv/k4fHDk8m03lBKogXCWKdvyWz57Qs+PXWnu3tO"
    "RtTLdmwyPzp+e2/viJ2qlxHRHAxIkhWi1fHo8G/yi/TVNx9dLBYSAo0Uy1w1iCvY/urGRLO5aj3a"
    "f3t5cXb6jZ2eXYMqmtt2rSKNTzE60tEo07Obvs4yeVl6EdTYe1uvbq5fxBfnZzkJIOqpdVlz5tUk"
    "Tg8tBifg1nWVfUN64B1sIgLUkJP9wz+/vrZnX3+0XiyDaErJISZxmSfT/T3ViEKe6lARh1nR84qH"
    "0/1fnD7Nnzz93MlmnUQhUdtUXefJvYNHRyePqAC8dPWFIESca0ct07D/C57nZ88+evHiac45CAOr"
    "7MiSW5W8aJbrZjqK9IDRuzbKl7l6fvF1s7p2d7qwEIBBAHNuVQCN5pJhHqWCefbUWmwxH80Oqzje"
    "9j4KFyrtR7DHPwSAwX5c5tjsuyqzJ6eq6mg6PxlNZ/cevnNxeXp9db6+WS6Xy/UqQTSnBK736vrx"
    "7GQ2O5lMH9Sj6WQ6jaMSVFwcyEVYRmT0aP5gduP3q5Mr81YECnWXqHtENd8/no1mMCNMAUrKISRY"
    "xqpFGmGm8yfHb085+/OT5iojKxiUyZoESfXe0fFDj57FHYHhcO/hX93H/cl1NkqsYJbULaPK9fH+"
    "8b3RtAZ8s9n+vbAfWEJWIFSHswd/dk8eju81bgEQFc9uHsdr1+NHb9d1aJFUXGEbDjh2vCmblxPI"
    "ftz7s3sP9yk/SY2rKkUyMkkTqWfHJyf3RhI26y6ECEKGaHXM6Wzv4d7be39pQs9G8SDZGeDz6d79"
    "2d5cAMKI3kWbUEDxFlpVJweP/7atH+zdLAyB9MDknlsnwrSe3JvtzagZiPAHs/v7D+TR+OgspYak"
    "MniZYYU4DXTA+oU1o2c6AsfIBjbOSJ2NpkeT2X6l1S7oL9twMASAwQZ7M6wIfLkls6yFod4MIiJR"
    "NGqox/N7rXlq0TZI2c0TacIssKghxrqOoy6r9sIF1u9uiMBgiLE+uf/osK60yWvQogTPpAUAIXRA"
    "ccd8jKItYAQVmiHmIc7vPT64Z2VcEhTQPLl4Eho8IABIaIkYxg/eeu8hpUoZTV5XQQJhrmuKE0Qj"
    "cL4OV1WxBq6YhMnkwZMn96GiMWfQzAkGWWUXpcO940HmVg3xDpMEi2pSnB6+Oz18t4sw7Ny8Wc6e"
    "Qgid7FqR50wZQQ1OjFTHx28f7sONFqjmreWVhCgYta1X1YZmrQh2dccQyCYnY6wmJw+eHJ4QZEye"
    "mJsYQvKcgcgxYKltQozZgtTzo0fz/fttUakUMGcnt/N93rU6SkwjTMVpySUYRHLrEKF2mzzl97oJ"
    "oB3tsSEADDbYHz37hwsSjOIqBjRggGx2lyASAIgiqoxGG5GnbrGncze+XXdip1pbmB4UFHGIIUQF"
    "MNJ603nYxIxeXggFQFeIQDJqgykgNMZOVTFoKMORigoAkVAoAgGhosx3llalotYoAFyEGLHwq8nr"
    "EkkJoGBA3U32SCivr1r0GuHAqFNKLrTmROHv3BJBh+3k9FYYYOf690GDoqHsuhd5nbL9q5GAFGLq"
    "WJD9jtZHSZVR8cKhKrpJSZDKhd8EI3WMtSxXWxBlGTFikCAEIkPc6DuFCg7VXAb9ZbNiB1e59Znp"
    "RRgMoEOKqpqErvmsNXeyCxPs1EM//D7wEAAG+7HFAOuUvrap+xbFdgOdoEB6jsqy+bHzOxuqr83G"
    "bO8/yTsZ8HajsM8F+5iyYQsoOi5SayE5KySA/tJBA1roPwtUIjvysyyZ6RZtYKG66ejHX6tHIlo8"
    "18ZPbxWPbfML3c/6rcVXg0llT4BbcAk7zQHbxUl4RygbW/n17tQ2WIptwZX+NXyz4+y7cb4ElaJw"
    "bOi1G2/dGg9d8EbGLYJ/296d29FxoxS3kYEnNnchATv35I743xAABhvsTTB2qXHs/e9GxwNAAlt0"
    "w+1QDx2sUf4JvVztVghug4HoNopsfDCtFxzfyHxmJQHJXVXQsz91/iJscIYeV7rjVHu/jB1KBRYa"
    "I9uurm9+YRPbXisG+A6Q0b9+93ffeuxbUkW8Fah2z6L8YXcYXvsEvKTwBggCZRvMfBPMturc1p9L"
    "B8vscKWEknf3byc77DtW/qrcqT42B8zN5JJ1sp+9Csid0+mRpnLYBpTd/QAgF7UoGtzgnRTMj0wW"
    "fggAg/24vH/naHaco93mfcJtf2HFWdhW7Jt3ygkh5LZzKXkldslyNiqEGy/WlSAb9yS2s4W+m+ru"
    "JJav9ubGl30Od5PZ16+SsHtNNtuwvKVtzZd+37dzkwD6hnDpDMhmTYzovLztPKFnYbTfxqfvuzn2"
    "RtW9XNhNH1m2F3P3Wu4eZzmPbQHDW5HS+2Uu7mh5E4Cw+zQUyovuvXVTHjhvFXw/ijgwBIDBfnQA"
    "EG57/FsKoLKt+G99/8Ot3Lpodm4VPLcZqwsMlmGCktluvJBsvFznlbfZbELPolP8ieMO0NTXHkjd"
    "c3wThwoV6G742ZxQuwu0fO8gWULdLsWJb5Qat6AQy+sTCC8FJ9nEjF7gSDbnW5RTCj7UB4Zd5MU6"
    "tKyvjW6xcnG3UtkERemDQS/GyQxYR9G425reIlq22ZHTOwTA6Intusb0LTIuIhTSFu4+pztU6YPl"
    "S/F7CACDDfYGVQF3Etj+J14AEL460fZX7PWH3TqgPMuAvAGknXBQjFvep53EuHtyGWEpHpY7jqP4"
    "0GT9d1BRhNJtQx59e+GIvhtdtqn0a00B9eyYHWwFueXLbjUnvHv9cPtybbyh7f6Edw63Q9GpfaSx"
    "W06+uwvOrXfevhx3vP8rCiPrwy0FO/oam6S+Q9PKXbA7Zc9OWDUA/vIWhaGQ6uVXFyhi/TXs2jBD"
    "ABhssDfI+/OWp+u9m2DTuNvFYbhR5bQdJLr3SR1wD0cCW2OX7Sp6dcfcNSRV+nGdTmc0cQNWFN+O"
    "uAtxlH8tvl5gdjeX5E4M6wsRDwWhkR6vsM24y2tcINlNXQU7r79NdTcuXIEsMG4z37CFzrahtOvH"
    "3opu5VQtoAfZFTtcpBAHMhOAgFCismxP3jZlytbD8lZAkp0btnP+uYfklGWKpwvHGdxtHqQ+qGf0"
    "+jMv5fWpSxj6Eq3nxN7kEvBt3TYEgMEGe1NAIOszdbxM/bqb6e3+pr+UDt9GeMWQHZm70yZ+Jzfc"
    "LTkct4bodxrI22cJ+6O9LVF0i2GYt6EG3sKD9PchI+s9tbzq9W/HigK0/84r2YeBXnry9sW4m0Hf"
    "/vvLlZttexI7hdf2TP3WcZfC6qVOiOzAR3nbCPBXlkRy668siJP3eJLd6bRzZ1pggIAGG+xNqwHk"
    "Fa7sFd/XW3M4vJsj38ajO2xHb/140/G848ABQUceUcBr2Y6avPIYZPetdxES7h7Sdiho66C/43x/"
    "V5F091jkVv2004N9RXnB28OjePn0ha+6rDv9g+5vugGv+Opodwd64u3jl7uP8h21oH7HMeiry6P+"
    "WfKKH2I3A+DQAxhssDfV5A/0O/ht33b5Xr/M1ziG1zok/Lv0Ifm7zvq7Tonf5Uxf55J+75N6VZtf"
    "vvNIvu/rb3KF79R6//e67G/w92SwwQYbbLA/0URpsMEGG2ywIQAMNthggw02BIDBBhtssMGGADDY"
    "YIMNNtgQAAYbbLDBBhsCwGCDDTbYYEMAGGywwQYbbAgAgw022GCDDQFgsMEGG2ywIQAMNthggw02"
    "BIDBBhtssMGGADDYYIMNNtgQAP6gdktXGjsCoTQKIHZLuPU1X5udhOtGkcS+gwv4pWfK3T/cuU2v"
    "Lz9E3z0HcYh3alZ2+zrI7/1JMEGmGG33Xa3wqe/IdexQ2tvwrRtssDfE/mTpoG0r9dApV9MQHCHD"
    "FOmWR/v+npdwMLPIa2cUzahXamnsimu7iN8WIPGNFpJ0wlV3j0R2/frOTzaSJoTfcrUGeEfSmwPa"
    "XZE+cXGwhD3x17qIkijOHDrN7EKCb86iyNrFFS0KGkxD0TnYYEMA+KNaESPt1KDu+mLvfmayKyj4"
    "OkkroeKgG+Bwyq6j/35VSeeu+aof7+gu3a4PrH/EbVn03Uy9ExGXO+JKcDpIZBrdXtNBGzuNQhfv"
    "9FRBA9xILcJM/NMuNwcbbAgAb47lzvV1cnKyGwaYiCxIAoP7Tur8WqgLgyc4izMNbsEMO2q0vBsw"
    "TJDBkrAb0SvYud124wW08VcfD8tb3A42dMLEuxKHMC0qsi6gwHXn7ieA6i1o8Pj9PbU4xFPRStwi"
    "X4Q6tBwqCxJG/26FjcEGG2wIAP/xtoO59+gHC2LvgLNXNbLXUN0u3ta20tuEsGht+21/7l1h4YCx"
    "NCCghPM79Ea/+xh2dGzvlhOdhrj3RcBuMt6hTKVu0B4Hs++QTv2tRUCpplxgAjHsCuruVAD+O85j"
    "sMEGGwLAv7vX3+Akwk1i7goTuoiLQGAVHJ0+HJN97yJAIEAESj5eig0FAly/Q5qORslUIdzdIdYV"
    "CdbLZ2+f5SXN9js/6QJYhoCd5y2i5k46pcPiXSDeHVJpSlP6VyiRgPBQokmBdb7PYx9LHFC49LFL"
    "/Labd5pDZYgAgw02BIA/rnELp8hOqutdsr8d3nlFu/V7JMOQgntI95KZMDPQCkrjr9Djlt6XSxd1"
    "4Ds/76uQLdC/c1S+U09gt0VcWgUG39XbJpCtFCVdZWNWDowlPmmXyHd10Pd6FAco8NBdRgJ8RcAc"
    "4P/BBhsCwJvg/V811UMDG5e1yTpLo1IcqBac5DUGY2imyZhExN0BmNeZCZKB1GM+UlAmEoCIQw1K"
    "uINaYKhbMM4OeiJ3f85d73pnshM0IZC7UCLoBoG68AJkSHImpxH9yW7j3/e1TEBcu1rKIAlMTvMd"
    "rIlMt6PXYIMNNgSAP24c8J2/0iBugImxWwsoYEsH53ep++9+NNAMCQwOFxcj4F5qC8ftRL70hLvZ"
    "TBAGL9kz+wWFfq7GUbD1Wwe/8f5uO+++RfxLG9m3EHxflWxWAZjB3EP/3lUhNHG7PVn0nY9GA+Fw"
    "g4FGbyFudBMzSdrHEnqZDR0CwGCDDQHgj2cFIbfiHwkQ/RSQQKRxV1Qh0JMBVAkpJeFtz/vbH+GE"
    "ilWeEUIgRCyoVH27FVvvX/q9gNOgnpE10HMLZgAUgRn6PnQ/W/lqMKubZ0I/w2/9b4q7ZSCX+U83"
    "gFQKIfAWTJDUtuuMJkgEe9xnZ4Ptdz6KW4YJ6ViJw7UlzT2RTstdL8Qd6tkakeD+HS3uwQYbbAgA"
    "/wFmt0EUQx8DjEQUy7ZOlrJSPMAznOycr+N7PSYLonB6y2zZzKG+2Qb2TezpYajkBrfSSAWNpLuj"
    "4EfFe/bBq4zXyE5KbwCQMwRuRoW7lO0DR+9oDUzlbYVl+rPrfwMO0VE1DmGE1jw37iSU2r8bv9ej"
    "gnAABA0sISvAg4bSyiZsO1BLyoAFDTbYEADeiFjQ7wGUlFbHjCMxWIY7KLAQnRB/PfaClCERAN2U"
    "Va2VS4SEnSJkSzShEJEARqERcKlAp5W13FIobPu60g3b7+wAb3sABggpcJAZJQC4C0JrqYODvI9+"
    "BkBgCeuc2zpbLC/FEEh6akv0cMf3ejQt7+U0cyHpDvPKsmgXwwTbRsrAAzHYYEMA+OOZ3Mr+wS63"
    "NqRsyY1llFNhBmtLmu38vpg4Ye7OlJAdJLSCI+eMlFC/8kiIbGbmyO5wZBHQ3N3J3eVeAGYEymLX"
    "NoLd2f418U33Irt7tiwl9mSD3V7GCmO0M+PJKi3JrIEOtZwC+TpuWlg+QmWM1QGhGcyPk1dqDpYw"
    "RUIdMDcdOgGDDTYEgD+KceMqKf3QZ8/bphVEDaQoA2BrmEG500b9Xm/AoE6x5CSFaJIlEehtr+c9"
    "6QQRQjAlQIrDMkXxin1hoOfZ2d2n0t0WtG26vOXZpEMg2RSooGGLvguABJPVus7ybovKmZ0Z1Iwc"
    "+VprYKQHhQLI9LLX7Mgt9iSegCO4YtvKwAD+DDbYEAD+qOabOLBxpQrWsHrt85xrsSaIZWsAixJy"
    "eg2H6ISrZLi4iDOllGxq1Rw+AcYZYcsy1KM3N83Y0mHx/p5btc5Pu3H3ZW+VLBtatzvO2NiVIOU1"
    "LC9tD9Z74U2oEDM4WY8O3xuNBXINaQFHiHBHTh2xxPeZeipLZCytB8AqkPD2ABX0PjjuPmBGiBOi"
    "HFCgwQYbAsAfFwMqU4kwQA0BhGK/4QNMfioBObcupcNqLsGzf382UCeM5u4iCpo06zpMW7mf06Fi"
    "L3erwugnbQRe5+p9y7UIwWSpRaD7TsjZfeuXWxG+2eYFHSQLflSe4+7uk3r2DlCBdMIMlEwkA9aQ"
    "iFlVvQdfQw3mQA0C4bXGdHZ5rwM8wg2+hgCcJtTaRQty2AAebLAhALwxSBAAsS358ah68BdHRw8Q"
    "qw2k0ju4+PpvkDovby2kho0g9xwit2CQMn1fzd/7vyBdIWyWsPylpd9ds9/6r9tCodjMFZiDs5RJ"
    "BcUddCCDCu1oKmCwMqlTba/N96sAnMjI7GoB6RvULWAZmspsKvvWgzmGQDDYYEMA+GPCP7335zYf"
    "L075HuLBd5QMr2ubSXwDBBKASBQQv1876A5jBBwjHO02e/+AAQAs3EQhqPZrZwRitXkJFr6jl6g6"
    "+b0eCSi0x6b6k6KCKkBd3mHz0gMf6GCDDQHgjUGCdpNRAab/QYVH96cN19t/0C3gbvjpo9HOkfzP"
    "vKzgpVMbnP1gg/0w/OBggw022GBDABhssMEGG2wIAIMNNthggw0BYLDBBhtssCEADDbYYIMNNgSA"
    "wQYbbLDBhgAw2GCDDTbYEAAGG2ywwQYbAsBggw022GBDABhssMEGG2wIAIMNNthggw0BYLDBBhts"
    "sCEADDbYYIMNNgSA3882Ar/9Gbn04lq3WTgHe7M+cgLA2D+UO8iNyMyQoAw22BAAvsuKSNaOVBZ7"
    "gmKRABf3XkTXBy3CNyRSe5FEdkdKMAdVbomgAYAZ3YrC2nDFBhvs381+PHoAd7L7nLO7O+CbANAp"
    "1/pw1/9o98g79+4AVUKAGdzdkCkOgC5F0L4rBnyo2QYbbAgAv72CeYVmr6lSA0MUDSX9N3dQhEMA"
    "+ONGaQfg7NThxR3uWUDZUWuDuTgH/Gewwf5DHOiP6kSK1q6Zp5xT267b3IIGARUDDPRmhAGWWsDc"
    "ckruTnF3hzncYRQXOsSFxiEIDDbYEAC+24ogOeROHSAiqlQlS15JOMyHAPDHt7zp2ZCMVahCDBSY"
    "3+4ECLy/d4MNNti/j/3gewDfhRK3bQvROBqLBAfcLNGFogOw8MfO/rsb5+4UISBMyZx3uziD9x9s"
    "sCEA/G4zdrAPdvD9WFUqwSFl/EdEBFIyz8Gv/FFLTgEK0tNNZlFCNZpwx8pdHcq1wQYbAsDvVxcI"
    "yIur608/+eJXv/4kmoqIKd39/9/e3azIlWVXHF9rnxuRmUqBG3dDg3G/gsEDTzzw1E9qMPgpjAee"
    "NBh6aFxuf2HwqKrbakkRcc9eHtzIVJbUlSpDtSKk+v8QhySVA+mGtNf5vmYN+LIBEEnbmq/W7nj5"
    "r//+n9/89pVqkYc8oqgckwEAAfDRUh9Jbad7HRmKktzf3789nn77m1d//w//+G//8tXd7q67p+xl"
    "qFc+9QsGsyPbnVXSst+9PR7/9df/+erNm/3tnbyb6SGN0lRSUbmlwXMDCIDfp+16b/bArs64vVm+"
    "/vp/f/nLf/pVqaa7s8qxiiWAiw4ASsN299q91rCr3hyPr353WHY3UtmW08pUWkkmjwwgAP4f7GF5"
    "jP3bN2+++fqbPh5GV9UyXVMxc0AXDYC0bQ8nmdGMvb+9u7l9Mcau5aSV3laIxTowQAB8ZFJhO1n0"
    "YPta8ul0amu/v81SoxdrTFcTABcPgChJSTWUzO4uL9tn1znfEbGV/RLbQAEC4KMZ8MFNMlLVbrlx"
    "DUnZea2Ou0as4iTwRQPANbo7PaW22o5qdLylwjaCe5zN++CTBUAAPC0okv3hMmHPeUp6+mBl0dKu"
    "2FNJZPX5yknaT9yqFblkpzOVtstpRZayLefE280Q3k4F838UIACej4Ht10OHMVHGUlFKZa0jsnNM"
    "R7FsRY5oL9Aqvao9SsNye6qTsuvhpxLF2y2gofgDBMCzppTMaFW/dc5/ndjzeFBFXpXZPZXSMoat"
    "ZlrhkqzRs7POMUqSuuUatax93vJfUZxSHJlj2wAB8IxIa5+s1+7XfaqqmnNWjVHWPBeUbVVAp5NU"
    "Rfm/tG3CLv1uNaZ1LNWcc7fbdfdxPWb24fiGCSCAAHg2AKJf/OnP/+5v/2a/30uac44xRu3WdX1y"
    "1R2F5OpTYYzD4WB7v99vSXA6nX76kzueDEAAfHfhsOacf/Hnf/Y4ILB0WrVb+HA/J7M1PojpdQ1X"
    "NwF/OJ9717hL2o8xpO5ZkaUh7RcNnb+m/SzaxW2plDnX7dNUz5uFgwAAI4Bneo7rcSyLVUuppKTX"
    "ddbYuVTS9lqpb7f9Hd+nvWhrrX0q136UMndlJT1PY+z4XwoQAN/xF1iW0+m02+16nbV4WGO308MZ"
    "osf3AT+0/cF3aK+lXWpsSzindV2WxfYYXAQHEADPT2PZWxKkW1Iya4zvmDswu8uvVCI5c26HuCXN"
    "0zoG7+8B/pDF8wsoHGNZ5rpqe8FU1XP3B1D9r9aW4rtdz7z7x8kSAMAI4NnCMSSNZf/4jadfP+jH"
    "AcC7SQdcZ5dk+OFzLHYAAQTADzLQefJuKcoKAHwht4F+3wzAZzjA4xEABMAPh9fMfnajNwAEwA/W"
    "SSQDqP4A9OO8MIGyAgBfQgA8253/Pfs+qf5f+PgOAH1hAMAXPgIo+o8AwAgAAEAAAAAIAAAAAQAA"
    "IAAAgAAAABAAAAACAABAAAAACAAAAAEAACAAAAAEAACAAAAAEADfXz9c4Oyc22+/8z1SW7G2q54J"
    "MABXwedfWw3rrXxV3Kp+V74IgGflSXV/kgoVuVtSq1drptdc4eME8OPS334pYUtTOsnd3aNrya47"
    "Ldu+wu5qXecTfZoHbUVqLfaQSrYc29tPkgEArq2ctjsV27bl0dt3Mq/tT3x1bwRrtzyyDaVynu5p"
    "WzUiW0O2VHk3qgKASxb9x26oVVJHmq5s/dfqmVZF6pYq19Xt/jzm0CPlW+lZ2xMP/X8A19BzPVeq"
    "x4paU95WA/wwn53rK1jX907glCVHlkqqaL63IJDIa3nJw4pxxGAAwKfmJ93oem9M0K6UO2nblsrn"
    "n7muPvfVBUBtj3Wb7knb7agib7uC3k37r9LCHiAAl+76t7XkXSSUpKFyKnFFTlQaGZLi6xoEXF0A"
    "OLY8ErcqPSqdWBmuZUsGrdKWqNn2WbEZFMCFqn/OOz7Ppb/Ondexq6olTjSkxEtGJ119VRmwXOFD"
    "raifnAOQpLiWXUulIcfnsRfVH8BlJyzm45LkVou8zVFUVVUq1irPkpNtifi6XF0AxDmcTvv93lGf"
    "2rshL6+P85+/+o8XN3Wzq9Ls7iRVZZfSxVIwgIuMANztntsW/ywVSaOlr/7919OdmtOH9jrnvN+/"
    "PB3X9xY0CYAPnqg7i2LNzFRN27vbF3/007/8q79elrnYytwW0+2RzIrkVoqWlpb2U7dbyZLaVSnn"
    "oY+/ePWubu5aQ5VRPpxWezAC+Ej1b7cXT3U7KdnW/u7lH//Jz37+C2cmU4k1bCdupes8HSSFlpaW"
    "9pO1jkaXHs6rbnv8R291bN2/vP/mVWksy97xHF6WGp31qk6vXuEIQFXuTitVNTNs39z/pOeaxFvf"
    "/xwAakvbPiEA+MQrAHF60fl6su5URR1Za+vtqzdzf/dyTZ9ySs9luVnX6euaAbrCbaBRknQcjVq6"
    "091elqk6X7a0LaSkSmVPZV3COQAAn34FoKZP83x9WSyXNCR5jsVrr6rD4fD29raHXOth7Xi5rlmg"
    "K1uVTjlV0xWVRm27aDtZz6eA7eHazl7PqRmOAgO4XATEkRLPuOM8zkYcDoeKTqfT/YvbrPP09pDu"
    "m2V3bbMV1zUCqHMGSNtJik5FLTuxFEs5Ztv6k5ZaXqKa7AQFcCluPxwFqAynFN3UrV3u3Zi745u8"
    "uLvf9/3r372tF2YN4PkMKHVXlaTuljSWSmJ3uuPzrdC1TQiVEveV7awC8OOQkobOJai03f1pa0g6"
    "HVcPrYfj7f6+ut68Prx8+fJ1v2IE8OyYSu3S3K73GdsoqyVFVo3HNy1Iimr7HXMnNICLJIAk2Tnf"
    "XxM9HvSNl7HtU4m1pn3n1/2KqyC+xzP1xwYJAHBVMxfvylfeD4hzTctV/7kBAD/S4AIAEAAAAAIA"
    "AEAAAAAIAAAAAQAAIAAAAAQAAIAAAAAQAAAAAgAAQAAAAAgAAAABAAAgAAAABAAAgAAAABAAAAAC"
    "AABAAAAACAAAAAEAACAAAIAAAAAQAAAAAgAAQAAAAAgAAAABAAAgAAAABAAAgAAAABAAAAACAABA"
    "AAAACAAAAAEAACAAAAAEAACAAAAAEAAAAAIAAEAAAAAIAAAAAQAAeOL/AFiYaAS/OS0JAAAAAElF"
    "TkSuQmCC"
)

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
            with _ur.urlopen(req, timeout=10) as r:
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
            return v.strip()
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
    SESSIONS[token] = time.time()
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
            return v.strip()
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
    CLIENT_SESSIONS[token] = email
    CLIENT_SESSION_TIMES[token] = time.time()
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
    return hashlib.sha256(pwd.encode()).hexdigest()

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
    logo_src = f"data:image/png;base64,{FUERTE_LOGO_B64}"
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
          <strong style="color:#8899aa">Fuerte Venture Capital SL</strong> &middot; NIF: B23881691<br>
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
          <strong style="color:#8899aa">Fuerte Venture Capital SL</strong> &middot; NIF: B23881691<br>
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
      <a href="mailto:newcapitalfuerte@gmail.com?subject=Attivazione%20Early%20Adopter"
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
            "replyTo":     {"email": "newcapitalfuerte@gmail.com"},
            "subject":     "Robot Trader 2026 è live — la tua offerta riservata",
            "htmlContent": corpo,
        }).encode("utf-8")
        req = _ur.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=payload,
            headers={"api-key": api_key, "Content-Type": "application/json", "Accept": "application/json"},
        )
        with _ur.urlopen(req, timeout=15) as resp:
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
    for i, r in enumerate(['NIF: B23881691', 'Calle Puipana 3, 35640 Villaverde', 'Las Palmas, España', 'info@fuerteventurecapital.com', 'www.fuerteventurecapital.com']):
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
        'Fuerte Venture Capital SL  ·  NIF: B23881691  ·  Calle Puipana 3, 35640 Villaverde, Las Palmas, España'
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
    'piano_azioni','piano_etf','piano_fondi','piano_ordini',
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


# ─── HTML ───────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Robot Trader 2026</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0F172A;color:#e0e0e0;min-height:100vh}

/* TOPBAR */
.topbar{background:#2C5282;border-bottom:3px solid #F6AD55;padding:.9rem 2rem;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100;backdrop-filter:blur(10px)}
.brand{display:flex;align-items:center;gap:.75rem}
.brand-logo{width:36px;height:36px;background:linear-gradient(135deg,#2C5282,#F6AD55);border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:1.2rem;flex-shrink:0}
.brand-title{color:#F6AD55;font-size:1.15rem;font-weight:700;letter-spacing:.3px}
.brand-sub{font-size:.72rem;opacity:.45;margin-top:.1rem}
.topbar-right{display:flex;align-items:center;gap:1rem}
.clock{font-size:.8rem;opacity:.55;font-variant-numeric:tabular-nums}

/* CONTAINER */
.wrap{max-width:1440px;margin:0 auto;padding:1.5rem}

/* TABS */
.tabs{display:flex;flex-wrap:wrap;background:#0F172A;border-radius:8px;overflow:hidden;border:1px solid #2C5282;margin-bottom:1.5rem}
.tab{flex:1 1 auto;min-width:7rem;padding:.7rem .5rem;text-align:center;cursor:pointer;font-weight:600;font-size:.78rem;transition:all .2s;border-right:1px solid rgba(44,82,130,.4);border-bottom:1px solid rgba(44,82,130,.2);color:rgba(255,255,255,.5);white-space:nowrap}
.tab:last-child{border-right:none}
.tab:hover{background:rgba(44,82,130,.4);color:#F6AD55}
.tab.active{background:#2C5282;color:#F6AD55}

/* PANELS */
.panel{display:none}.panel.active{display:block}

/* SECTION HEADER */
.sec-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:1.2rem;flex-wrap:wrap;gap:.6rem}
.sec-head h2{font-size:1.05rem;color:#F6AD55;font-weight:700}

/* KPI */
.kpi-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:1rem;margin-bottom:1.5rem}
.kpi{background:rgba(44,82,130,.08);border:1px solid rgba(44,82,130,.35);border-radius:10px;padding:1.2rem;text-align:center}
.kpi-label{font-size:.72rem;opacity:.5;text-transform:uppercase;letter-spacing:.5px;margin-bottom:.4rem}
.kpi-val{font-size:2rem;font-weight:700;color:#F6AD55;line-height:1}
.kpi-sub{font-size:.7rem;opacity:.4;margin-top:.35rem}

/* BOXES */
.box{background:rgba(44,82,130,.08);border:1px solid rgba(44,82,130,.35);border-radius:10px;padding:1.2rem;margin-bottom:1rem}
.box h3{color:#F6AD55;margin-bottom:.8rem;font-size:.95rem;font-weight:700}

/* TABLES */
.tbl-wrap{overflow-x:auto;border:1px solid rgba(44,82,130,.4);border-radius:8px;background:rgba(0,0,0,.2)}
table{width:100%;border-collapse:collapse;font-size:.83rem}
th{padding:.7rem .6rem;text-align:left;color:#F6AD55;font-weight:600;background:#2C5282;border-bottom:2px solid #F6AD55;white-space:nowrap}
th.sortable{cursor:pointer;user-select:none;transition:background .15s}
th.sortable:hover{background:#3a6899}
th.sorted-asc::after{content:' ▲';font-size:.7rem;color:#68D391}
th.sorted-desc::after{content:' ▼';font-size:.7rem;color:#FC8181}
th.sortable[draggable]{cursor:grab}
th.col-drag-over{border-left:3px solid #F6AD55!important;background:#2C5282}
td{padding:.52rem .6rem;border-bottom:1px solid rgba(255,255,255,.04)}
tr:hover td{background:rgba(246,173,85,.03)}
.ticker{color:#F6AD55;font-weight:700;font-family:'SF Mono',Consolas,monospace;text-decoration:none}
a.ticker:hover{text-decoration:underline;color:#ffc97a}
.neg{color:#ef4444}

/* BUTTONS */
.btn{padding:.45rem 1rem;border-radius:6px;cursor:pointer;font-weight:600;font-size:.82rem;border:1px solid;transition:all .15s}
.btn-or{background:rgba(246,173,85,.12);border-color:rgba(246,173,85,.45);color:#F6AD55}
.btn-or:hover{background:rgba(246,173,85,.25)}
.btn-gr{background:rgba(34,197,94,.12);border-color:rgba(34,197,94,.45);color:#22c55e}
.btn-gr:hover{background:rgba(34,197,94,.25)}
.btn-re{background:rgba(239,68,68,.12);border-color:rgba(239,68,68,.45);color:#ef4444}
.btn-re:hover{background:rgba(239,68,68,.25)}
.btn:disabled{opacity:.4;cursor:not-allowed}

/* BADGES */
.bdg{display:inline-block;padding:.15rem .5rem;border-radius:4px;font-size:.7rem;font-weight:700;letter-spacing:.5px}
.bdg-basic{background:rgba(156,163,175,.12);color:#9ca3af;border:1px solid rgba(156,163,175,.25)}
.bdg-pro{background:rgba(245,158,11,.12);color:#f59e0b;border:1px solid rgba(245,158,11,.25)}
.bdg-value{background:rgba(99,102,241,.12);color:#818cf8;border:1px solid rgba(99,102,241,.25)}

/* RUN STATUS */
.rs{display:inline-block;padding:.18rem .55rem;border-radius:4px;font-size:.7rem;font-weight:600}
.rs-running{background:rgba(246,173,85,.2);color:#F6AD55;animation:pulse 1.5s infinite}
.rs-completato{background:rgba(34,197,94,.2);color:#22c55e}
.rs-errore,.rs-timeout{background:rgba(239,68,68,.2);color:#ef4444}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}
@keyframes pwdPulse{0%,100%{box-shadow:0 0 0 0 rgba(246,173,85,.4)}50%{box-shadow:0 0 0 12px rgba(246,173,85,0)}}

/* MSG */
.msg{padding:.5rem .9rem;border-radius:6px;font-size:.82rem;display:none}
.msg-ok{background:rgba(34,197,94,.12);border:1px solid rgba(34,197,94,.3);color:#22c55e;display:block}
.msg-err{background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.3);color:#ef4444;display:block}

/* ═══════════════════════════════════════
   SERVIZI GRID
═══════════════════════════════════════ */
.sv-matrix{display:grid;grid-template-columns:100px 1fr 1fr 1fr;gap:.8rem;align-items:start}
.sv-tier-head{text-align:center;padding:.65rem;border-radius:8px;font-weight:700;font-size:.88rem;letter-spacing:.8px}
.sv-tier-head.basic{background:rgba(156,163,175,.1);color:#9ca3af;border:1px solid rgba(156,163,175,.2)}
.sv-tier-head.pro{background:rgba(245,158,11,.1);color:#f59e0b;border:1px solid rgba(245,158,11,.2)}
.sv-tier-head.value{background:rgba(99,102,241,.1);color:#818cf8;border:1px solid rgba(99,102,241,.2)}
.sv-asset-lbl{display:flex;align-items:center;justify-content:flex-end;padding-right:.5rem;font-weight:700;font-size:.84rem;color:#F6AD55;min-height:auto}
.sv-extra{margin-top:.8rem;border-top:1px solid rgba(255,255,255,.06);padding-top:.7rem}
.sv-lbl{display:block;font-size:.7rem;color:rgba(255,255,255,.4);text-transform:uppercase;letter-spacing:.5px;margin-bottom:.3rem}
.sv-textarea{width:100%;background:rgba(0,0,0,.3);border:1px solid rgba(255,255,255,.1);border-radius:6px;color:rgba(255,255,255,.85);font-size:.75rem;padding:.45rem .55rem;resize:vertical;font-family:inherit;line-height:1.5;box-sizing:border-box}
.sv-input{width:100%;background:rgba(0,0,0,.3);border:1px solid rgba(255,255,255,.1);border-radius:6px;color:rgba(255,255,255,.85);font-size:.75rem;padding:.38rem .55rem;box-sizing:border-box}
.sv-textarea:focus,.sv-input:focus{outline:none;border-color:rgba(246,173,85,.45)}
.sv-card{background:rgba(0,0,0,.25);border:1px solid rgba(255,255,255,.07);border-radius:10px;padding:1rem;transition:border-color .2s}
.sv-card:hover{border-color:rgba(246,173,85,.2)}
.sv-card.t-basic{border-top:3px solid #9ca3af}
.sv-card.t-pro{border-top:3px solid #f59e0b}
.sv-card.t-value{border-top:3px solid #818cf8}
.price-row{display:flex;align-items:center;gap:.3rem;margin-bottom:.75rem}
.price-eur{font-size:.9rem;opacity:.55}
.price-inp{background:rgba(0,0,0,.35);border:1px solid rgba(246,173,85,.25);color:#F6AD55;font-size:1.5rem;font-weight:700;width:72px;padding:.2rem .3rem;border-radius:5px;text-align:center}
.price-inp:focus{outline:none;border-color:#F6AD55}
.price-mo{font-size:.73rem;opacity:.45}
.status-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:.75rem}
.status-sel{background:rgba(0,0,0,.3);border:1px solid rgba(255,255,255,.1);color:#e0e0e0;padding:.22rem .5rem;border-radius:4px;font-size:.73rem;cursor:pointer}
.param-rows{border-top:1px solid rgba(255,255,255,.06);padding-top:.6rem}
.param-row{display:flex;justify-content:space-between;align-items:center;padding:.28rem 0;border-bottom:1px solid rgba(255,255,255,.04);font-size:.76rem}
.param-row:last-child{border-bottom:none}
.param-lbl{opacity:.6}
.param-inp{background:rgba(0,0,0,.3);border:1px solid rgba(255,255,255,.1);color:#e0e0e0;width:72px;padding:.22rem .4rem;border-radius:4px;text-align:right;font-size:.76rem}
.param-inp:focus{outline:none;border-color:#F6AD55}

/* ═══════════════════════════════════════
   PARAMETRI COMPARISON TABLE
═══════════════════════════════════════ */
.pm-section{margin-bottom:1.2rem}
.pm-section h3{color:#F6AD55;margin-bottom:.7rem;font-size:.97rem;font-weight:700}
.pm-table{width:100%;border-collapse:collapse}
.pm-table th{padding:.65rem 1rem;font-weight:700;font-size:.82rem}
.pm-table th:first-child{text-align:left;color:rgba(255,255,255,.5);font-weight:500}
.pm-table th.th-basic{text-align:center;color:#9ca3af;background:rgba(156,163,175,.07)}
.pm-table th.th-pro{text-align:center;color:#f59e0b;background:rgba(245,158,11,.07)}
.pm-table th.th-value{text-align:center;color:#818cf8;background:rgba(99,102,241,.07)}
.pm-table td{padding:.48rem 1rem;border-bottom:1px solid rgba(255,255,255,.05);font-size:.83rem}
.pm-table td:first-child{opacity:.75}
.pm-table td.tc{text-align:center}
.pm-table tr:hover td{background:rgba(246,173,85,.03)}
.pm-inp{background:rgba(0,0,0,.3);border:1px solid rgba(255,255,255,.1);color:#e0e0e0;width:95px;padding:.3rem .5rem;border-radius:4px;text-align:center;font-size:.83rem}
.pm-inp:focus{outline:none}
.pm-inp.basic:focus{border-color:#9ca3af}
.pm-inp.pro:focus{border-color:#f59e0b}
.pm-inp.value:focus{border-color:#818cf8}

/* LOG */
.log-term{background:#07120a;border:1px solid rgba(34,197,94,.18);border-radius:6px;padding:.8rem;font-family:'SF Mono',Consolas,monospace;font-size:.75rem;color:#88d4a0;height:290px;overflow-y:auto;line-height:1.55;white-space:pre-wrap;word-break:break-all}

.footer{text-align:center;padding:2rem;opacity:.3;font-size:.76rem}

@media(max-width:960px){.sv-matrix{grid-template-columns:70px 1fr 1fr 1fr}}
@media(max-width:700px){.sv-matrix{grid-template-columns:1fr};.sv-asset-lbl{min-height:auto;justify-content:flex-start;padding:.5rem 0};.tabs{flex-wrap:wrap};.tab{width:33.33%}}

/* ── SCREENER TABLES (azioni/etf/fondi) — colonne multiple, scroll orizzontale ── */
#azioni table,#etf table,#fondi table{width:auto;min-width:100%}
#azioni td,#etf td,#fondi td{white-space:nowrap;min-width:60px}
#azioni td:nth-child(2),#etf td:nth-child(2),#fondi td:nth-child(2){min-width:140px;max-width:220px;overflow:hidden;text-overflow:ellipsis}

/* ── DATABASE ── */
.db-tabs{display:flex;gap:.4rem;margin-bottom:1rem;flex-wrap:wrap}
.db-tab{padding:.45rem 1.1rem;border-radius:6px;border:1px solid rgba(44,82,130,.5);background:transparent;color:rgba(255,255,255,.5);cursor:pointer;font-size:.82rem;font-weight:600;transition:all .18s}
.db-tab:hover{border-color:#F6AD55;color:#F6AD55}
.db-tab.active{background:#2C5282;border-color:#2C5282;color:#F6AD55}
.sc-asset-tab,.sc-plan-tab{padding:.35rem .9rem;border-radius:6px;border:1px solid rgba(44,82,130,.5);background:transparent;color:rgba(255,255,255,.5);cursor:pointer;font-size:.8rem;font-weight:600;transition:all .18s}
.sc-asset-tab:hover,.sc-plan-tab:hover{border-color:#F6AD55;color:#F6AD55}
.sc-asset-tab.active{background:#2C5282;border-color:#2C5282;color:#F6AD55}
.sc-plan-tab.active{background:#276749;border-color:#276749;color:#68D391}
.db-panel{display:none}.db-panel.active{display:block}
.db-search{width:100%;box-sizing:border-box;padding:.55rem .9rem;background:rgba(0,0,0,.3);border:1px solid rgba(44,82,130,.5);border-radius:6px;color:#e2e8f0;font-size:.88rem;margin-bottom:.6rem;outline:none}
.db-search:focus{border-color:#F6AD55}
.db-count{font-size:.78rem;color:#64748b;margin-bottom:.8rem}
.db-group{display:inline-block;padding:.15rem .55rem;background:rgba(44,82,130,.25);border-radius:4px;font-size:.75rem;color:#90cdf4}
.btn-yf{display:inline-block;padding:.25rem .65rem;background:#F6AD55;color:#1a202c;border-radius:5px;text-decoration:none;font-weight:700;font-size:.8rem;transition:opacity .15s}
.btn-yf:hover{opacity:.8}
.db-ticker{font-family:'SF Mono',Consolas,monospace;font-size:.83rem;font-weight:600;color:#e2e8f0}
/* SETTORI */
.sett-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:.8rem;margin-bottom:1.6rem}
.sett-card{border-radius:10px;padding:.9rem 1rem;cursor:pointer;transition:transform .15s,box-shadow .15s;border:1px solid rgba(255,255,255,.1)}
.sett-card:hover{transform:translateY(-3px);box-shadow:0 8px 24px rgba(0,0,0,.5)}
.sett-card-emoji{font-size:1.3rem;margin-bottom:.25rem}
.sett-card-nome{font-size:.78rem;font-weight:700;line-height:1.2;margin-bottom:.15rem}
.sett-card-ticker{font-size:.68rem;opacity:.45;margin-bottom:.5rem;font-family:monospace}
.sett-card-prezzo{font-size:.95rem;font-weight:700;margin-bottom:.5rem;font-family:monospace}
.sett-perf-row{display:flex;gap:.3rem;flex-wrap:wrap}
.sett-pill{font-size:.62rem;padding:.12rem .35rem;border-radius:3px;font-weight:700;white-space:nowrap}
.sett-section-title{font-size:.85rem;font-weight:600;opacity:.6;margin:.5rem 0 .8rem;letter-spacing:.04em}
</style>
</head>
<body>

<!-- TOPBAR -->
<div class="topbar">
  <div class="brand">
    <div class="brand-logo">🤖</div>
    <div>
      <div class="brand-title">Robot Trader 2026</div>
      <div class="brand-sub">Fuerte Venture Capital SL</div>
    </div>
  </div>
  <div class="topbar-right">
    <span class="clock" id="clock"></span>
    <button class="btn btn-or" onclick="refreshAll()">↻ Aggiorna</button>
    <a href="/logout" class="btn btn-re" style="text-decoration:none;padding:.4rem .8rem;font-size:.78rem">⏻ Esci</a>
  </div>
</div>

<div class="wrap">
  <!-- TABS -->
  <div class="tabs">
    <div class="tab active" onclick="switchTab(this,'home')">📊 Home</div>
    <div class="tab" onclick="switchTab(this,'analytics')">📈 Analytics</div>
    <div class="tab" onclick="switchTab(this,'servizi')">💼 Servizi</div>
    <div class="tab" onclick="switchTab(this,'parametri')">⚙️ Parametri</div>
    <div class="tab" onclick="switchTab(this,'azioni')">📈 Azioni</div>
    <div class="tab" onclick="switchTab(this,'etf')">📦 ETF</div>
    <div class="tab" onclick="switchTab(this,'fondi')">🏦 Fondi</div>
    <div class="tab" onclick="switchTab(this,'settori')">🌍 Settori</div>
    <div class="tab" onclick="switchTab(this,'crm')">🎯 CRM & Marketing</div>
    <div class="tab" onclick="switchTab(this,'esecuzione')">🚀 Esecuzione</div>
    <div class="tab" onclick="switchTab(this,'database')">🗃️ Database</div>
    <div class="tab" onclick="switchTab(this,'kb')">📚 KB</div>
    <div class="tab" onclick="switchTab(this,'onboarding')">📋 Onboarding</div>
  </div>

  <!-- ══════════ HOME ══════════ -->
  <div id="home" class="panel active">
    <div class="kpi-row" id="kpi-row">
      <div class="kpi"><div class="kpi-label">📈 Azioni</div><div class="kpi-val">—</div><div class="kpi-sub">Caricamento...</div></div>
      <div class="kpi"><div class="kpi-label">📦 ETF</div><div class="kpi-val">—</div><div class="kpi-sub">Caricamento...</div></div>
      <div class="kpi"><div class="kpi-label">🏦 Fondi</div><div class="kpi-val">—</div><div class="kpi-sub">Caricamento...</div></div>
      <div class="kpi"><div class="kpi-label">💰 Revenue Potenziale</div><div class="kpi-val">—</div><div class="kpi-sub">9 servizi / mese</div></div>
    </div>
    <div class="box">
      <h3>🌍 Mercati Analizzati</h3>
      <div id="mercati-wrap" class="tbl-wrap"><table><tbody><tr><td style="padding:1.5rem;opacity:.5;text-align:center">Caricamento...</td></tr></tbody></table></div>
    </div>
    <div class="box" style="font-size:.85rem;line-height:1.7">
      <strong>⏰ Scheduler:</strong> 23:00 — Lun/Ven — Windows Task Scheduler &nbsp;|&nbsp;
      <strong>📧 Email:</strong> <span id="stat-dest">—</span>
    </div>
    <div class="box" style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:1rem">
      <div>
        <div style="font-weight:700;margin-bottom:.25rem">🤖 Assistente AI — Knowledge Base</div>
        <div style="font-size:.82rem;color:#aaa" id="kb-status">Caricamento...</div>
      </div>
      <button class="btn btn-gr" onclick="reloadKB()" id="btn-reload-kb">↺ Ricarica KB</button>
    </div>
  </div>

  <!-- ══════════ ANALYTICS ══════════ -->
  <div id="analytics" class="panel">
    <div class="sec-head">
      <h2 style="color:#F6AD55">📈 Business Analytics</h2>
      <button class="btn" onclick="renderAnalytics()" style="font-size:.78rem">↺ Aggiorna</button>
    </div>
    <div id="analytics-content">
      <div style="opacity:.5;padding:2rem;text-align:center">Caricamento...</div>
    </div>
  </div>

  <!-- ══════════ SERVIZI ══════════ -->
  <div id="servizi" class="panel">
    <div class="sec-head">
      <h2>💼 Catalogo Servizi</h2>
      <div style="display:flex;gap:.6rem;align-items:center">
        <span id="sv-msg" class="msg"></span>
        <button class="btn btn-gr" onclick="saveServizi()">💾 Salva Servizi</button>
      </div>
    </div>
    <div class="sv-matrix">
      <div></div>
      <div class="sv-tier-head basic">BASIC</div>
      <div class="sv-tier-head pro">PRO</div>
      <div class="sv-tier-head value">VALUE</div>

      <div class="sv-asset-lbl">📈 AZIONI</div>
      <div id="sv-azioni-basic"></div>
      <div id="sv-azioni-pro"></div>
      <div id="sv-azioni-value"></div>

      <div class="sv-asset-lbl">📦 ETF</div>
      <div id="sv-etf-basic"></div>
      <div id="sv-etf-pro"></div>
      <div id="sv-etf-value"></div>

      <div class="sv-asset-lbl">🏦 FONDI</div>
      <div id="sv-fondi-basic"></div>
      <div id="sv-fondi-pro"></div>
      <div id="sv-fondi-value"></div>
    </div>
  </div>

  <!-- ══════════ PARAMETRI ══════════ -->
  <div id="parametri" class="panel">

    <!-- ── SEZIONE 1: Parametri Screener (parametri.json) ── -->
    <div class="box" style="margin-bottom:1.2rem">
      <div class="sec-head" style="margin-bottom:.8rem">
        <h2>🎛️ Parametri Screener (Globali)</h2>
        <div style="display:flex;gap:.6rem;align-items:center;flex-wrap:wrap">
          <span id="sp-msg" class="msg"></span>
          <button class="btn btn-re" onclick="loadScreenerParams()">↺ Ricarica</button>
          <button class="btn btn-gr" onclick="saveScreenerParams()">💾 Salva Parametri</button>
        </div>
      </div>
      <div id="scr-params-content" style="opacity:.5;font-size:.85rem">Caricamento...</div>
    </div>

    <!-- ── SEZIONE 2: Parametri Tier Servizi (servizi_config.json) ── -->
    <div class="box">
      <div class="sec-head" style="margin-bottom:.8rem">
        <h2>⚙️ Parametri per Tier (Servizi)</h2>
        <div style="display:flex;gap:.6rem;align-items:center;flex-wrap:wrap">
          <span id="pm-msg" class="msg"></span>
          <button class="btn btn-re" onclick="loadServizi()">↺ Annulla</button>
          <button class="btn btn-gr" onclick="saveParametri()">💾 Salva Tier</button>
        </div>
      </div>
      <div id="pm-container"></div>
    </div>

    <!-- ── SEZIONE 3: Pesi Score Bontà ── -->
    <div class="box" style="margin-top:1.2rem">
      <div class="sec-head" style="margin-bottom:.8rem">
        <h2>🎯 Pesi Score Bontà</h2>
        <div style="display:flex;gap:.6rem;align-items:center;flex-wrap:wrap">
          <span id="sc-msg" class="msg"></span>
          <button class="btn btn-re" onclick="resetScoringDefaults()">↺ Reset Default</button>
          <button class="btn btn-gr" onclick="saveScoring()">💾 Salva Pesi</button>
        </div>
      </div>
      <p style="font-size:.8rem;opacity:.55;margin-bottom:1rem">
        Score 0–100: percentile della metrica tra tutti i titoli selezionati per quel piano. Alto = migliore della lista. VALUE usa i pesi PRO.
      </p>
      <!-- Asset tabs -->
      <div style="display:flex;gap:.4rem;margin-bottom:.6rem">
        <button class="sc-asset-tab active" onclick="switchScAsset(this,'azioni')">📈 Azioni</button>
        <button class="sc-asset-tab" onclick="switchScAsset(this,'etf')">📦 ETF</button>
        <button class="sc-asset-tab" onclick="switchScAsset(this,'fondi')">🏦 Fondi</button>
      </div>
      <!-- Plan tabs -->
      <div style="display:flex;gap:.4rem;margin-bottom:1rem">
        <button class="sc-plan-tab active" onclick="switchScPlan(this,'BASIC')">BASIC</button>
        <button class="sc-plan-tab" onclick="switchScPlan(this,'PRO')">PRO</button>
        <button class="sc-plan-tab" onclick="switchScPlan(this,'VALUE')">VALUE</button>
      </div>
      <!-- Weight rows rendered by JS -->
      <div id="sc-metrics"></div>
      <div id="sc-total" style="margin-top:.8rem;font-size:.85rem;font-weight:600;min-height:1.2rem"></div>
    </div>
  </div>

  <!-- ══════════ AZIONI ══════════ -->
  <div id="azioni" class="panel">
    <div class="box" id="azioni-info" style="font-size:.85rem">—</div>
    <div class="tbl-wrap"><table><thead id="azioni-head"></thead><tbody id="azioni-body"><tr><td style="padding:2rem;opacity:.5;text-align:center">Clicca la tab per caricare</td></tr></tbody></table></div>
  </div>

  <!-- ══════════ ETF ══════════ -->
  <div id="etf" class="panel">
    <div class="box" id="etf-info" style="font-size:.85rem">—</div>
    <div class="tbl-wrap"><table><thead id="etf-head"></thead><tbody id="etf-body"><tr><td style="padding:2rem;opacity:.5;text-align:center">Clicca la tab per caricare</td></tr></tbody></table></div>
  </div>

  <!-- ══════════ FONDI ══════════ -->
  <div id="fondi" class="panel">
    <div class="box" id="fondi-info" style="font-size:.85rem">—</div>
    <div class="tbl-wrap"><table><thead id="fondi-head"></thead><tbody id="fondi-body"><tr><td style="padding:2rem;opacity:.5;text-align:center">Clicca la tab per caricare</td></tr></tbody></table></div>
  </div>

  <!-- ══════════ SETTORI ══════════ -->
  <div id="settori" class="panel">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;flex-wrap:wrap;gap:.6rem">
      <h2 style="color:#F6AD55;font-size:1.1rem;font-weight:700">🌍 Analisi Settoriale &amp; Mercati</h2>
      <div style="display:flex;align-items:center;gap:.8rem">
        <span id="sett-ts" style="font-size:.72rem;opacity:.45">—</span>
        <button onclick="loadSettori(true)" style="background:#2C5282;border:none;color:#F6AD55;padding:.3rem .8rem;border-radius:6px;cursor:pointer;font-size:.78rem;font-weight:600">🔄 Aggiorna</button>
      </div>
    </div>
    <!-- Guida lettura dati -->
    <div style="margin-bottom:1.2rem">
      <button onclick="var g=document.getElementById('sett-guide');g.style.display=g.style.display==='none'?'block':'none'" style="background:rgba(44,82,130,.25);border:1px solid rgba(44,82,130,.5);color:#90cdf4;padding:.3rem .85rem;border-radius:6px;cursor:pointer;font-size:.76rem">📖 Come leggere questi dati ▸</button>
      <div id="sett-guide" style="display:none;background:rgba(15,23,42,.85);border:1px solid rgba(44,82,130,.35);border-radius:8px;padding:1.2rem 1.4rem;margin-top:.7rem;font-size:.78rem;line-height:1.75">
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1.2rem 2rem">
          <div><strong style="color:#F6AD55">📊 Periodi temporali</strong><br><span style="opacity:.75">
            <strong>1G</strong> — variazione giornaliera (alta volatilità, poco predittiva)<br>
            <strong>1S</strong> — trend settimanale → utile per timing ingresso/uscita<br>
            <strong>1M</strong> — momentum mensile → <em>il più importante per decisioni tattiche</em><br>
            <strong>3M</strong> — tendenza trimestrale → conferma la direzione<br>
            <strong>1A</strong> — trend strutturale → forza secolare del settore/mercato
          </span></div>
          <div><strong style="color:#F6AD55">🎨 Scala colori card settori</strong><br><span style="opacity:.75">
            <span style="color:#86efac">■</span> Verde scuro → +8%+ mensile (forte momentum)<br>
            <span style="color:#6ee7b7">■</span> Verde medio → tra +4% e +8% mensile<br>
            <span style="color:#a7f3d0">■</span> Verde chiaro → tra 0% e +4% mensile<br>
            <span style="color:#fca5a5">■</span> Rosso chiaro → tra 0% e -4% mensile<br>
            <span style="color:#f87171">■</span> Rosso scuro → oltre -4% mensile (trend negativo)
          </span></div>
          <div><strong style="color:#F6AD55">🚦 Semaforo nazioni</strong><br><span style="opacity:.75">
            🟢 &gt; +2% mensile → mercato in fase rialzista<br>
            🟡 tra −2% e +2% → mercato laterale / neutro<br>
            🔴 &lt; −2% mensile → mercato in fase ribassista<br><br>
            <em>Combina sempre 1M + 3M per evitare falsi segnali</em>
          </span></div>
          <div><strong style="color:#F6AD55">📌 Come usare i dati</strong><br><span style="opacity:.75">
            <strong>Sovrappeso:</strong> 1M, 3M e 1A tutti positivi → momentum confermato<br>
            <strong>Ingresso tattico:</strong> 1G negativo ma 1M e 1A positivi → pullback su trend<br>
            <strong>Attenzione:</strong> 1A positivo, 3M e 1M negativi → possibile inversione<br>
            <strong>Evitare:</strong> 1M, 3M e 1A tutti negativi → trend negativo confermato<br>
            Clicca una card → vedi descrizione settore + ETF/Fondi consigliati
          </span></div>
        </div>
      </div>
    </div>
    <div class="db-tabs" style="margin-bottom:1.4rem">
      <button class="db-tab sett-subtab active" onclick="switchSettTab(this,'sett-gics')">📊 Settori GICS</button>
      <button class="db-tab sett-subtab" onclick="switchSettTab(this,'sett-nazioni')">🌐 Nazioni &amp; Mercati</button>
    </div>
    <div id="sett-loading" style="display:none;text-align:center;padding:3rem;opacity:.6">
      <div style="font-size:2rem;margin-bottom:.6rem">⏳</div>
      <div>Caricamento dati da Yahoo Finance...</div>
      <div style="font-size:.75rem;margin-top:.4rem;opacity:.7">Primo caricamento ~10 secondi</div>
    </div>
    <div id="sett-gics" class="sett-subpanel">
      <div class="sett-section-title">🇺🇸 USA — SPDR Sector ETFs (11 settori GICS)</div>
      <div id="sett-us-grid" class="sett-grid"></div>
      <div class="sett-section-title">🇪🇺 Europa — iShares STOXX Europe 600 Sector ETFs</div>
      <div id="sett-eu-grid" class="sett-grid"></div>
    </div>
    <div id="sett-nazioni" class="sett-subpanel" style="display:none">
      <div id="sett-naz-wrap"></div>
    </div>
  </div>

  <!-- Modal drill-down titoli nel settore -->
  <div id="sett-modal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.75);z-index:9000;overflow-y:auto">
    <div style="background:#1a1a2e;margin:3rem auto 2rem;max-width:920px;border-radius:12px;padding:1.8rem;position:relative;border:1px solid rgba(44,82,130,.5)">
      <button onclick="document.getElementById('sett-modal').style.display='none'" style="position:absolute;top:1rem;right:1rem;background:none;border:none;color:#aaa;font-size:1.5rem;cursor:pointer;line-height:1">✕</button>
      <h3 id="sett-modal-title" style="margin-bottom:.4rem;color:#F6AD55;font-size:1rem"></h3>
      <p id="sett-modal-sub" style="font-size:.75rem;opacity:.5;margin-bottom:1rem"></p>
      <div id="sett-modal-info" style="margin-bottom:1.2rem"></div>
      <div id="sett-modal-body"></div>
    </div>
  </div>

  <!-- ══════════ CRM & MARKETING ══════════ -->
  <div id="crm" class="panel">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;flex-wrap:wrap;gap:.6rem">
      <h2 style="color:#F6AD55;font-size:1.1rem;font-weight:700">🎯 CRM &amp; Marketing</h2>
      <span id="crm-msg" class="msg"></span>
    </div>

    <!-- Sotto-tab CRM -->
    <div class="db-tabs" style="margin-bottom:1.4rem">
      <button class="db-tab crm-subtab active" onclick="switchCrmTab(this,'clienti')">👥 Clienti</button>
      <button class="db-tab crm-subtab" onclick="switchCrmTab(this,'pipeline')">📊 Pipeline</button>
      <button class="db-tab crm-subtab" onclick="switchCrmTab(this,'campagne')">📧 Campagne Email</button>
      <button class="db-tab crm-subtab" onclick="switchCrmTab(this,'social')">📱 Social Media</button>
      <button class="db-tab crm-subtab" onclick="switchCrmTab(this,'prospect')">🎯 Prospect</button>
      <button class="db-tab crm-subtab" onclick="switchCrmTab(this,'calendario')">📅 Calendario</button>
      <button class="db-tab crm-subtab" onclick="switchCrmTab(this,'whatsapp')">💬 WhatsApp</button>
    </div>

    <!-- ─── Clienti ─── -->
    <div id="crm-clienti" class="crm-sub">
      <div class="sec-head">
        <h2>👥 Gestione Clienti</h2>
        <div style="display:flex;gap:.6rem;align-items:center;flex-wrap:wrap">
          <span id="cl-msg" class="msg"></span>
          <button class="btn btn-re" onclick="loadClienti()">↺ Ricarica</button>
          <button class="btn btn-gr" onclick="mostraModalAggiungi()">+ Aggiungi</button>
          <button class="btn" onclick="exportClienti()" style="border-color:rgba(246,173,85,.4);color:#F6AD55">⬇ Esporta CSV</button>
          <label class="btn" style="border-color:rgba(74,144,217,.4);color:#4A90D9;cursor:pointer;margin:0">
            ⬆ Importa CSV
            <input type="file" id="cl-import-file" accept=".csv" onchange="importClienti(this)" style="display:none">
          </label>
        </div>
      </div>
      <div id="cl-stats" style="display:flex;gap:.8rem;flex-wrap:wrap;margin-bottom:1rem"></div>
      <div id="cl-pwd-box" style="display:none;background:rgba(246,173,85,.08);border:2px solid #F6AD55;border-radius:10px;padding:1.2rem 1.4rem;margin-bottom:1rem;animation:pwdPulse 1s ease 2">
        <div style="font-size:.9rem;color:#F6AD55;font-weight:700;margin-bottom:.6rem">🔑 PASSWORD TEMPORANEA — Annotala ora, non verrà mostrata di nuovo!</div>
        <div style="display:flex;align-items:center;gap:.8rem;flex-wrap:wrap">
          <code id="cl-pwd-val" style="font-size:1.3rem;font-family:monospace;color:#fff;background:rgba(0,0,0,.4);padding:.4rem 1rem;border-radius:6px;letter-spacing:2px"></code>
          <button onclick="navigator.clipboard.writeText(document.getElementById('cl-pwd-val').textContent);this.textContent='Copiato ✓'" style="background:#68D391;color:#0a0f1e;border:none;border-radius:6px;padding:.4rem .9rem;font-weight:700;font-size:.82rem;cursor:pointer">Copia</button>
          <button onclick="document.getElementById('cl-pwd-box').style.display='none'" style="background:transparent;border:1px solid rgba(255,255,255,.15);color:#aaa;border-radius:6px;padding:.4rem .7rem;font-size:.78rem;cursor:pointer">✕ Chiudi</button>
        </div>
        <div style="font-size:.75rem;color:#888;margin-top:.5rem">URL accesso: <a href="__BASE_URL__/client-login" target="_blank" style="color:#68D391">__BASE_URL__/client-login</a></div>
      </div>
      <div class="tbl-wrap"><table>
        <thead><tr id="cl-head"></tr></thead>
        <tbody id="cl-body"><tr><td style="padding:2rem;opacity:.5;text-align:center">Caricamento...</td></tr></tbody>
      </table></div>
    </div>

    <!-- ─── Pipeline ─── -->
    <div id="crm-pipeline" class="crm-sub" style="display:none">
      <!-- Header Pipeline -->
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.6rem;margin-bottom:1.2rem">
        <div>
          <h3 style="margin:0;color:#F6AD55;font-size:1rem">📊 Pipeline Commerciale</h3>
          <span id="pipeline-stats-label" style="font-size:.76rem;opacity:.5">—</span>
        </div>
        <div style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap">
          <input id="pipeline-search" type="text" placeholder="Cerca nome, email…"
            oninput="pipelineSearch(this.value)"
            style="background:rgba(0,0,0,.3);border:1px solid rgba(255,255,255,.15);border-radius:7px;padding:.4rem .75rem;color:#e0e0e0;font-size:.82rem;outline:none;width:200px">
          <button class="btn btn-gr" onclick="mostraNuovoLead()">+ Nuovo Lead</button>
          <input type="file" id="apollo-file-input" accept=".csv" style="display:none" onchange="importApolloFile(this)">
          <button onclick="document.getElementById('apollo-file-input').click()" style="background:rgba(10,102,194,.15);border:1px solid rgba(10,102,194,.35);border-radius:6px;color:#60a5fa;padding:.3rem .75rem;font-size:.8rem;cursor:pointer;display:inline-flex;align-items:center;gap:.35rem"><svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zM9 17H6.5v-7H9v7zm-1.3-8a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm9.3 8h-2.5v-3.5c0-.8-.7-1.5-1.5-1.5s-1.5.7-1.5 1.5V17H9v-7h2.5v1a3 3 0 015.5 1.7V17z"/></svg> Import Apollo.io</button>
          <button class="btn btn-re" onclick="loadPipelineData()">↺</button>
          <button class="btn" onclick="exportProspect()" style="border-color:rgba(246,173,85,.4);color:#F6AD55">⬇ Esporta</button>
          <label class="btn" style="border-color:rgba(74,144,217,.4);color:#4A90D9;cursor:pointer;margin:0">
            ⬆ Importa CSV
            <input type="file" id="pipeline-import-file" accept=".csv" onchange="importProspectCSV(this)" style="display:none">
          </label>
        </div>
      </div>
      <div id="pipeline-import-result" style="display:none;background:rgba(104,211,145,.08);border:1px solid rgba(104,211,145,.3);border-radius:8px;padding:.7rem 1rem;margin-bottom:.8rem;font-size:.84rem"></div>
      <!-- Board kanban -->
      <div id="pipeline-board" style="display:flex;gap:.7rem;overflow-x:auto;padding-bottom:.8rem;min-height:400px">
        <div style="opacity:.5;padding:2rem;text-align:center;width:100%">Caricamento...</div>
      </div>
      <!-- Strip Non Interessato + Sospeso -->
      <div id="pipeline-strip" style="margin-top:1rem;display:flex;gap:.8rem;flex-wrap:wrap"></div>
      <!-- Modal Nuovo Lead -->
      <div id="modal-nuovo-lead" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1010;align-items:center;justify-content:center">
        <div style="background:#1a1f2e;border:1px solid rgba(104,211,145,.3);border-radius:14px;padding:2rem;width:100%;max-width:420px;margin:1rem">
          <h3 style="margin-bottom:1.2rem;color:#68D391">+ Nuovo Lead</h3>
          <div style="display:grid;gap:.7rem">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:.6rem">
              <div>
                <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Nome *</div>
                <input id="nl-nome" placeholder="Mario" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.5rem .75rem;color:#e0e0e0;font-size:.88rem;outline:none;box-sizing:border-box">
              </div>
              <div>
                <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Cognome</div>
                <input id="nl-cognome" placeholder="Rossi" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.5rem .75rem;color:#e0e0e0;font-size:.88rem;outline:none;box-sizing:border-box">
              </div>
            </div>
            <div>
              <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Email *</div>
              <input id="nl-email" type="email" placeholder="mario@email.com" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.5rem .75rem;color:#e0e0e0;font-size:.88rem;outline:none;box-sizing:border-box">
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:.6rem">
              <div>
                <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Fonte</div>
                <input id="nl-fonte" placeholder="LinkedIn, Web…" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.5rem .75rem;color:#e0e0e0;font-size:.88rem;outline:none;box-sizing:border-box">
              </div>
              <div>
                <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Interesse</div>
                <select id="nl-interesse" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.15);border-radius:7px;padding:.5rem .75rem;color:#e0e0e0;font-size:.88rem;outline:none">
                  <option>Tutti</option><option>Azioni</option><option>ETF</option><option>Fondi</option>
                </select>
              </div>
            </div>
          </div>
          <div style="display:flex;gap:.7rem;justify-content:flex-end;margin-top:1.2rem">
            <button class="btn" onclick="document.getElementById('modal-nuovo-lead').style.display='none'" style="background:rgba(255,255,255,.07)">Annulla</button>
            <button class="btn btn-gr" onclick="confermaNuovoLead()">Crea Lead</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ─── Campagne Email ─── -->
    <div id="crm-campagne" class="crm-sub" style="display:none">
      <div id="campagne-content">
        <div style="opacity:.5;padding:1.5rem;text-align:center">Caricamento...</div>
      </div>
    </div>

    <!-- ─── Social Media ─── -->
    <div id="crm-social" class="crm-sub" style="display:none">
      <div id="social-content">
        <div style="opacity:.5;padding:1.5rem;text-align:center">Caricamento draft social...</div>
      </div>
    </div>

    <!-- ─── Prospect ─── -->
    <div id="crm-prospect" class="crm-sub" style="display:none">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.6rem;margin-bottom:1rem">
        <div>
          <h3 style="margin:0;color:#F6AD55;font-size:1rem">🎯 Prospect</h3>
          <span id="prospect-count" style="font-size:.78rem;opacity:.5">—</span>
        </div>
        <div style="display:flex;gap:.5rem;align-items:center;flex-wrap:wrap">
          <input id="prospect-search" type="text" placeholder="Cerca nome, email, fonte…"
            oninput="prospectSearch(this.value)"
            style="background:rgba(0,0,0,.3);border:1px solid rgba(255,255,255,.15);border-radius:7px;padding:.4rem .75rem;color:#e0e0e0;font-size:.82rem;outline:none;width:220px">
          <button class="btn btn-re" onclick="loadProspect()">↺ Ricarica</button>
          <button class="btn" onclick="exportProspect()" style="border-color:rgba(246,173,85,.4);color:#F6AD55">⬇ Esporta CSV</button>
        </div>
      </div>
      <div id="prospect-chips" style="margin-bottom:.8rem"></div>
      <div id="prospect-import-result" style="display:none;background:rgba(104,211,145,.08);border:1px solid rgba(104,211,145,.3);border-radius:8px;padding:.7rem 1rem;margin-bottom:.8rem;font-size:.84rem"></div>
      <div class="tbl-wrap"><table>
        <thead><tr style="background:#2C5282">
          <th style="padding:.5rem .8rem;text-align:left;font-size:.8rem">Nome</th>
          <th style="padding:.5rem .8rem;text-align:left;font-size:.8rem">Email</th>
          <th style="padding:.5rem .8rem;text-align:left;font-size:.8rem">Fonte</th>
          <th style="padding:.5rem .8rem;text-align:left;font-size:.8rem">Interesse</th>
          <th style="padding:.5rem .8rem;text-align:left;font-size:.8rem">Stato</th>
          <th style="padding:.5rem .8rem;text-align:left;font-size:.8rem">Ult. Contatto</th>
          <th style="padding:.5rem .8rem;text-align:left;font-size:.8rem">Azioni</th>
        </tr></thead>
        <tbody id="prospect-tbody"><tr><td colspan="7" style="padding:2rem;opacity:.4;text-align:center">Caricamento...</td></tr></tbody>
      </table></div>
    </div>

    <!-- Modal nota prospect -->
    <div id="modal-nota-prospect" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1010;align-items:center;justify-content:center">
      <div style="background:#1a1f2e;border:1px solid rgba(246,173,85,.3);border-radius:14px;padding:2rem;width:100%;max-width:460px;margin:1rem">
        <h3 style="margin-bottom:.3rem;color:#F6AD55">📝 Note Prospect</h3>
        <div id="modal-nota-nome" style="font-size:.82rem;color:#aaa;margin-bottom:1rem"></div>
        <textarea id="modal-nota-testo" rows="4" placeholder="Note sul contatto…"
          style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:8px;padding:.6rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none;resize:vertical;box-sizing:border-box"></textarea>
        <div style="margin-top:.7rem">
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Data ultimo contatto</div>
          <input id="modal-nota-data" type="date" style="background:rgba(0,0,0,.3);border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.4rem .7rem;color:#e0e0e0;font-size:.88rem;outline:none">
        </div>
        <div style="display:flex;gap:.7rem;justify-content:flex-end;margin-top:1.2rem">
          <button class="btn" onclick="document.getElementById('modal-nota-prospect').style.display='none'" style="background:rgba(255,255,255,.07)">Annulla</button>
          <button class="btn btn-gr" onclick="salvaNotaProspect()">Salva</button>
        </div>
      </div>
    </div>

    <!-- ─── Calendario ─── -->
    <div id="crm-calendario" class="crm-sub" style="display:none">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.6rem;margin-bottom:1.2rem">
        <h3 style="margin:0;color:#F6AD55;font-size:1rem">📅 Calendario Editoriale</h3>
        <div style="display:flex;gap:.5rem">
          <button id="cal-prev" class="btn" onclick="calNav(-1)">‹ Prec</button>
          <span id="cal-month-label" style="padding:.4rem 1rem;font-size:.9rem;font-weight:600;color:#F6AD55"></span>
          <button id="cal-next" class="btn" onclick="calNav(1)">Succ ›</button>
        </div>
      </div>
      <div id="calendario-content"></div>
    </div>

    <!-- ─── WhatsApp ─── -->
    <div id="crm-whatsapp" class="crm-sub" style="display:none">
      <div id="whatsapp-content">
        <div style="opacity:.5;padding:1.5rem;text-align:center">Caricamento...</div>
      </div>
    </div>
  </div>

  <!-- Modal Aggiungi Cliente -->
  <div id="modal-aggiungi" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1000;align-items:center;justify-content:center">
    <div style="background:#1a1f2e;border:1px solid rgba(246,173,85,.3);border-radius:14px;padding:2rem;width:100%;max-width:440px;margin:1rem">
      <h3 style="margin-bottom:1.2rem;color:#F6AD55">+ Nuovo Cliente</h3>
      <div style="display:grid;gap:.8rem">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:.7rem">
          <div>
            <div style="font-size:.8rem;color:#888;margin-bottom:.3rem">Nome</div>
            <input id="ag-nome" placeholder="Mario" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:8px;padding:.6rem .9rem;color:#e0e0e0;font-size:.9rem;outline:none">
          </div>
          <div>
            <div style="font-size:.8rem;color:#888;margin-bottom:.3rem">Cognome</div>
            <input id="ag-cognome" placeholder="Rossi" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:8px;padding:.6rem .9rem;color:#e0e0e0;font-size:.9rem;outline:none">
          </div>
        </div>
        <div>
          <div style="font-size:.8rem;color:#888;margin-bottom:.3rem">Email</div>
          <input id="ag-email" type="email" placeholder="mario@email.com" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:8px;padding:.6rem .9rem;color:#e0e0e0;font-size:.9rem;outline:none">
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:.6rem">
          <div>
            <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Piano Azioni</div>
            <select id="ag-azioni" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.5rem;color:#e0e0e0;font-size:.85rem;outline:none">
              <option>NONE</option><option>BASIC</option><option>PRO</option><option>VALUE</option>
            </select>
          </div>
          <div>
            <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Piano ETF</div>
            <select id="ag-etf" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.5rem;color:#e0e0e0;font-size:.85rem;outline:none">
              <option>NONE</option><option>BASIC</option><option>PRO</option><option>VALUE</option>
            </select>
          </div>
          <div>
            <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Piano Fondi</div>
            <select id="ag-fondi" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.5rem;color:#e0e0e0;font-size:.85rem;outline:none">
              <option>NONE</option><option>BASIC</option><option>PRO</option><option>VALUE</option>
            </select>
          </div>
          <div>
            <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Piano Ordini</div>
            <select id="ag-ordini" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.5rem;color:#e0e0e0;font-size:.85rem;outline:none">
              <option>NONE</option><option>BASIC</option><option>PRO</option><option>VALUE</option>
            </select>
          </div>
        </div>
      </div>
      <div style="display:flex;gap:.7rem;margin-top:1.4rem;justify-content:flex-end">
        <button class="btn" onclick="chiudiModals()" style="background:rgba(255,255,255,.07)">Annulla</button>
        <button class="btn btn-gr" onclick="confermaAggiungi()">Salva</button>
      </div>
    </div>
  </div>

  <!-- Modal Attiva Cliente -->
  <div id="modal-attiva" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1000;align-items:center;justify-content:center">
    <div style="background:#1a1f2e;border:1px solid rgba(104,211,145,.3);border-radius:14px;padding:2rem;width:100%;max-width:460px;margin:1rem">
      <h3 style="margin-bottom:.4rem;color:#68D391">✅ Attiva Cliente</h3>
      <div id="at-info" style="font-size:.85rem;color:#aaa;margin-bottom:1.2rem"></div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:.6rem;margin-bottom:1rem">
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Piano Azioni</div>
          <select id="at-azioni" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.5rem;color:#e0e0e0;font-size:.85rem;outline:none">
            <option>NONE</option><option>BASIC</option><option>PRO</option><option>VALUE</option>
          </select>
        </div>
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Piano ETF</div>
          <select id="at-etf" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.5rem;color:#e0e0e0;font-size:.85rem;outline:none">
            <option>NONE</option><option>BASIC</option><option>PRO</option><option>VALUE</option>
          </select>
        </div>
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Piano Fondi</div>
          <select id="at-fondi" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.5rem;color:#e0e0e0;font-size:.85rem;outline:none">
            <option>NONE</option><option>BASIC</option><option>PRO</option><option>VALUE</option>
          </select>
        </div>
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Piano Ordini</div>
          <select id="at-ordini" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.5rem;color:#e0e0e0;font-size:.85rem;outline:none">
            <option>NONE</option><option>BASIC</option><option>PRO</option><option>VALUE</option>
          </select>
        </div>
      </div>
      <div style="font-size:.8rem;color:#888;background:rgba(104,211,145,.05);border-radius:8px;padding:.7rem .9rem;margin-bottom:1rem">
        Verrà generata una password temporanea e inviata via email (se Brevo è configurato).
      </div>
      <div style="display:flex;gap:.7rem;justify-content:flex-end">
        <button class="btn" onclick="chiudiModals()" style="background:rgba(255,255,255,.07)">Annulla</button>
        <button class="btn btn-gr" onclick="confermaAttiva()">Attiva e Invia Credenziali</button>
      </div>
    </div>
  </div>

  <!-- Modal Anagrafica / Dati Fiscali -->
  <div id="modal-anagrafica" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:1000;align-items:center;justify-content:center;overflow-y:auto;padding:1rem">
    <div style="background:#1a1f2e;border:1px solid rgba(179,151,90,.35);border-radius:14px;padding:2rem;width:100%;max-width:560px;margin:auto">
      <h3 style="margin-bottom:.3rem;color:#B3975A">📋 Anagrafica &amp; Dati Fiscali</h3>
      <div style="font-size:.8rem;color:#666;margin-bottom:1.2rem">I dati fiscali sono necessari per la fatturazione.</div>

      <!-- Dati personali -->
      <div style="font-size:.75rem;color:#B3975A;letter-spacing:1px;text-transform:uppercase;margin-bottom:.7rem">Dati Personali</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:.7rem;margin-bottom:.9rem">
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Nome</div>
          <input id="an-nome" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.55rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none">
        </div>
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Cognome</div>
          <input id="an-cognome" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.55rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none">
        </div>
      </div>
      <div style="margin-bottom:.9rem">
        <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Email</div>
        <input id="an-email" readonly style="width:100%;background:rgba(0,0,0,.2);border:1px solid rgba(255,255,255,.07);border-radius:7px;padding:.55rem .8rem;color:#666;font-size:.88rem;outline:none">
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:.7rem;margin-bottom:1.1rem">
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Paese</div>
          <select id="an-paese" onchange="aggiornaPaeseForm()" style="width:100%;background:#0a0f1e;border:1px solid rgba(255,255,255,.15);border-radius:7px;padding:.55rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none">
            <option value="">— seleziona —</option>
            <option value="IT">🇮🇹 Italia</option>
            <option value="ES">🇪🇸 Spagna</option>
            <option value="FR">🇫🇷 Francia</option>
            <option value="DE">🇩🇪 Germania</option>
            <option value="UK">🇬🇧 Regno Unito</option>
          </select>
        </div>
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Data di nascita</div>
          <input id="an-nascita" type="date" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.55rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none">
        </div>
      </div>

      <!-- Indirizzo -->
      <div style="font-size:.75rem;color:#B3975A;letter-spacing:1px;text-transform:uppercase;margin-bottom:.7rem">Indirizzo</div>
      <div style="margin-bottom:.7rem">
        <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Indirizzo</div>
        <input id="an-indirizzo" placeholder="Via/Calle/Rue..." style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.55rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none">
      </div>
      <div style="display:grid;grid-template-columns:120px 1fr;gap:.7rem;margin-bottom:1.1rem">
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">CAP / Postcode</div>
          <input id="an-cap" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.55rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none">
        </div>
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Città / City</div>
          <input id="an-citta" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.55rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none">
        </div>
      </div>

      <!-- Dati fiscali -->
      <div style="font-size:.75rem;color:#B3975A;letter-spacing:1px;text-transform:uppercase;margin-bottom:.7rem">Dati Fiscali</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:.7rem;margin-bottom:.7rem">
        <div>
          <div id="an-cf-label" style="font-size:.78rem;color:#888;margin-bottom:.3rem">Codice Fiscale / Tax ID</div>
          <input id="an-cf" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.55rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none;font-family:monospace;letter-spacing:1px">
        </div>
        <div>
          <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Telefono</div>
          <input id="an-tel" placeholder="+39 333 1234567" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.55rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none">
        </div>
      </div>
      <div id="an-piva-row" style="margin-bottom:1.1rem">
        <div style="font-size:.78rem;color:#888;margin-bottom:.3rem">Partita IVA <span style="opacity:.5">(opzionale — solo per professionisti)</span></div>
        <input id="an-piva" placeholder="IT12345678901" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.12);border-radius:7px;padding:.55rem .8rem;color:#e0e0e0;font-size:.88rem;outline:none;font-family:monospace">
      </div>

      <div style="display:flex;gap:.7rem;justify-content:flex-end">
        <button class="btn" onclick="chiudiModals()" style="background:rgba(255,255,255,.07)">Annulla</button>
        <button class="btn" onclick="salvaAnagrafica()" style="background:#B3975A;color:#0a0f1e;border-color:#B3975A;font-weight:700">Salva Dati Fiscali</button>
      </div>
    </div>
  </div>

  <!-- ══════════ ESECUZIONE ══════════ -->
  <div id="esecuzione" class="panel">
    <div class="box">
      <h3>🚀 Esecuzione Manuale</h3>
      <div style="display:flex;gap:.7rem;flex-wrap:wrap;margin-top:.6rem">
        <button class="btn btn-gr"  id="run-azioni"         onclick="runScreener('azioni')">▶ Azioni</button>
        <button class="btn btn-gr"  id="run-etf"            onclick="runScreener('etf')">▶ ETF</button>
        <button class="btn btn-gr"  id="run-fondi"          onclick="runScreener('fondi')">▶ Fondi</button>
        <button class="btn btn-gr"  id="run-fondi_eu"       onclick="runScreener('fondi_eu')">▶ Fondi EU</button>
        <button class="btn btn-or"  id="run-tutti"          onclick="runScreener('tutti')">▶▶ Tutti</button>
        <button class="btn btn-or"  id="run-orchestrator"   onclick="runScreener('orchestrator')" style="background:rgba(246,173,85,.2)">🚀 Orchestrator + Email</button>
        <button class="btn"         id="run-fondi_eu_fetch" onclick="runScreener('fondi_eu_fetch')" style="background:rgba(99,179,237,.15);border-color:#4a7fb5;color:#90cdf4">🔄 Aggiorna Universo Fondi EU</button>
      </div>
      <div id="run-msg" style="margin-top:.7rem;font-size:.84rem"></div>
    </div>

    <div id="log-box" class="box" style="display:none">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.6rem">
        <h3 id="log-title">📟 Log</h3>
        <div style="display:flex;gap:.5rem;align-items:center">
          <span id="log-badge" class="rs rs-running">running</span>
          <button class="btn" style="padding:.2rem .6rem;font-size:.72rem;border-color:rgba(255,255,255,.12);color:rgba(255,255,255,.4)" onclick="document.getElementById('log-box').style.display='none'">✕</button>
        </div>
      </div>
      <div id="log-term" class="log-term">In attesa output...</div>
      <div id="log-info" style="margin-top:.4rem;font-size:.7rem;opacity:.4">Aggiornamento ogni 2s...</div>
    </div>

    <div class="box" style="font-size:.84rem;line-height:1.7">
      <strong>⏰ Scheduler automatico (lun-ven):</strong><br>
      <span style="opacity:.55">22:30 Aggiorna Universo Fondi EU &nbsp;·&nbsp; 23:00 AZIONI &nbsp;·&nbsp; 23:30 ETF+FONDI+FONDI_EU</span>
    </div>
  </div>

  <!-- ══════════ DATABASE ══════════ -->
  <div id="database" class="panel">
    <div class="box">
      <div class="sec-head" style="margin-bottom:1rem">
        <h2>🗃️ Database Universo Ticker</h2>
        <span id="db-totali" style="font-size:.82rem;color:#90cdf4;opacity:.7">Caricamento...</span>
      </div>
      <div class="db-tabs">
        <button class="db-tab active" id="dbtab-azioni" onclick="switchDbTab(this,'db-azioni')">📈 Azioni</button>
        <button class="db-tab" id="dbtab-etf"    onclick="switchDbTab(this,'db-etf')">📦 ETF</button>
        <button class="db-tab" id="dbtab-fondi"  onclick="switchDbTab(this,'db-fondi')">🏦 Fondi</button>
      </div>
      <input type="text" class="db-search" id="db-search" placeholder="🔍 Cerca ticker o gruppo mercato..." oninput="filterDb()">
      <div style="display:flex;align-items:center;gap:1rem;margin-top:.5rem;flex-wrap:wrap">
        <div class="db-count" id="db-count">—</div>
        <button id="db-load-btn" class="btn btn-or" onclick="loadDbPrices()" style="padding:.35rem 1rem;font-size:.8rem;border-radius:6px;opacity:.85">📊 Carica dati (0 visibili)</button>
        <button id="db-missing-btn" class="btn" onclick="loadMissingDbPrices()" style="padding:.35rem 1rem;font-size:.8rem;border-radius:6px;background:#2C5282;border:1px solid #4a7fb5;color:#90cdf4">🔄 Aggiorna mancanti (<span id="db-missing-count">0</span>)</button>
        <button id="db-dead-btn" class="btn" onclick="verifyDeadTickers()" style="padding:.35rem 1rem;font-size:.8rem;border-radius:6px;background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.4);color:#fca5a5">☠️ Verifica ticker morti</button>
        <button onclick="_resetDbCols(_dbAsset.replace('db-',''))" style="padding:.25rem .7rem;font-size:.75rem;background:transparent;border:1px solid rgba(255,255,255,.2);border-radius:5px;color:#aaa;cursor:pointer" title="Ripristina ordine colonne originale">↺ Reset colonne</button>
      </div>
    </div>

    <div id="db-azioni" class="db-panel active">
      <div class="tbl-wrap">
        <table>
          <thead id="db-head-azioni"></thead>
          <tbody id="db-body-azioni"><tr><td colspan="6" style="padding:2rem;text-align:center;opacity:.4">Clicca la tab per caricare</td></tr></tbody>
        </table>
      </div>
    </div>

    <div id="db-etf" class="db-panel">
      <div class="tbl-wrap">
        <table>
          <thead id="db-head-etf"></thead>
          <tbody id="db-body-etf"></tbody>
        </table>
      </div>
    </div>

    <div id="db-fondi" class="db-panel">
      <div class="tbl-wrap">
        <table>
          <thead id="db-head-fondi"></thead>
          <tbody id="db-body-fondi"></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- ══════════ KB ══════════ -->
  <div id="kb" class="panel">
    <div class="box">
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem;margin-bottom:1rem">
        <h3 style="margin:0">📚 Knowledge Base — File Caricati</h3>
        <div style="display:flex;align-items:center;gap:.8rem;flex-wrap:wrap">
          <span id="kb-status-panel" style="font-size:.82rem;opacity:.7">Caricamento...</span>
          <button class="btn btn-re" id="btn-reload-kb2" onclick="reloadKB2()">↺ Ricarica KB</button>
        </div>
      </div>
      <div id="kb-files-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:.8rem">
        <div style="opacity:.5;grid-column:1/-1;text-align:center;padding:1.5rem">Caricamento file...</div>
      </div>
    </div>
  </div>

  <!-- ══════════ ONBOARDING ══════════ -->
  <div id="onboarding" class="panel">
    <div class="db-tabs" style="margin-bottom:1rem">
      <div class="db-tab active" onclick="switchObTab(this,'ob-interno')">🏢 Onboarding Interno</div>
      <div class="db-tab" onclick="switchObTab(this,'ob-cliente')">👤 Onboarding Cliente</div>
    </div>

    <!-- ONBOARDING INTERNO -->
    <div id="ob-interno" class="db-panel" style="display:block">
      <div class="box">
        <h3>🏢 Onboarding Interno — Guida Operativa Fuerte Venture Capital</h3>
        <p style="opacity:.7;margin-bottom:1.5rem">Guida per il team interno: come usare la dashboard, gestire i clienti, interpretare i report e le procedure operative quotidiane.</p>

        <h4 style="color:var(--accent);margin-top:1.5rem">1. Accesso alla Dashboard Admin</h4>
        <ul>
          <li>URL: <code>/admin</code> — accessibile solo con password admin</li>
          <li>La dashboard è divisa in tab: Home, Servizi, Parametri, Azioni, ETF, Fondi, CRM, Esecuzione, Database, KB, Onboarding</li>
          <li>Il sistema si riavvia tramite <strong>START_SISTEMA_PUBBLICO.bat</strong> su Windows — da usare dopo ogni modifica ai file Python</li>
        </ul>

        <h4 style="color:var(--accent);margin-top:1.5rem">2. Architettura del Sistema</h4>
        <ul>
          <li><strong>Screener Azioni:</strong> universe da <code>ticker_lists_5000.py</code> — aggiornato manualmente</li>
          <li><strong>Screener ETF:</strong> universe da JustETF via scraping — cache in <code>etf_universe_cache.json</code></li>
          <li><strong>Screener Fondi EU:</strong> universe da JustETF — cache in <code>fondi_eu_universe_cache.json</code></li>
          <li><strong>Screener Fondi US:</strong> universe da <code>ticker_lists_5000.py</code></li>
          <li><strong>Dati di mercato:</strong> Yahoo Finance (yfinance) — chiamate in batch durante l'elaborazione</li>
          <li><strong>Email:</strong> Brevo SMTP — configurato in <code>email_notifier.py</code></li>
          <li><strong>Chatbot:</strong> Anthropic Claude API — configurato in <code>chat_service.py</code></li>
        </ul>

        <h4 style="color:var(--accent);margin-top:1.5rem">3. Elaborazione Giornaliera (Lunedì–Venerdì)</h4>
        <ul>
          <li>L'orchestratore lancia gli screener in sequenza: Azioni → ETF → Fondi US → Fondi EU</li>
          <li>Al termine, <code>email_notifier.py</code> invia i report ai clienti attivi per i rispettivi piani</li>
          <li>I report vengono salvati nella cartella <code>REPORTS/</code></li>
          <li>Lo schedulatore è visibile nel tab <strong>Esecuzione</strong> della dashboard</li>
          <li>Orario di invio email: configurabile nel tab <strong>Parametri</strong></li>
        </ul>

        <h4 style="color:var(--accent);margin-top:1.5rem">4. Gestione Clienti (Tab CRM)</h4>
        <ul>
          <li>Aggiungere cliente: bottone "Nuovo Cliente" nel tab Servizi o CRM</li>
          <li>Attivare abbonamento: impostare <em>piano</em> e <em>stato = Attivo</em></li>
          <li>I clienti con stato <strong>Non Attivo</strong> non ricevono report né email di elaborazione</li>
          <li>Ogni cliente ha: email, piano (BASIC/PRO/VALUE), asset (AZIONI/ETF/FONDI), stato, note</li>
          <li>Export clienti: bottone "Esporta CSV" nel tab CRM</li>
        </ul>

        <h4 style="color:var(--accent);margin-top:1.5rem">5. Knowledge Base e Chatbot</h4>
        <ul>
          <li>I file KB si trovano in <code>KNOWLEDGE_BASE/</code> — tutti in formato .md</li>
          <li>Modificare un file KB NON richiede riavvio: usare il bottone <strong>↺ Ricarica KB</strong> nel tab KB</li>
          <li>Il chatbot usa Claude (Anthropic) — la chiave API è in <code>.env</code> o nei parametri</li>
          <li>Le conteggi dell'universo (N. azioni, ETF, fondi) si aggiornano automaticamente al ricaricamento KB</li>
          <li><strong>IMPORTANTE:</strong> non inserire mai soglie di filtro o pesi dello score nei file KB — sono parametri proprietari</li>
        </ul>

        <h4 style="color:var(--accent);margin-top:1.5rem">6. Parametri di Configurazione</h4>
        <ul>
          <li>Tab <strong>Parametri</strong>: orari scheduler, soglie screener, configurazione email</li>
          <li>I parametri vengono salvati in <code>params.json</code></li>
          <li>Modifiche ai parametri di screening hanno effetto dalla prossima elaborazione</li>
        </ul>

        <h4 style="color:var(--accent);margin-top:1.5rem">7. Procedure di Emergenza</h4>
        <ul>
          <li><strong>Sistema down:</strong> verificare che Docker/ngrok siano attivi; riavviare con START_SISTEMA_PUBBLICO.bat</li>
          <li><strong>Email non inviate:</strong> verificare log in tab Esecuzione; controllare credenziali Brevo in params</li>
          <li><strong>Screener bloccato:</strong> controllare connessione internet e limiti API Yahoo Finance</li>
          <li><strong>Chatbot non risponde:</strong> verificare chiave API Anthropic e saldo account</li>
          <li><strong>Cache ETF/Fondi obsoleta:</strong> eseguire manualmente il refresh dal tab ETF o Fondi</li>
        </ul>
      </div>
    </div>

    <!-- ONBOARDING CLIENTE -->
    <div id="ob-cliente" class="db-panel">
      <div class="box">
        <h3>👤 Onboarding Cliente — Flusso di Benvenuto</h3>
        <p style="opacity:.7;margin-bottom:1.5rem">Procedura di attivazione per nuovi abbonati: dalla registrazione alla prima ricezione del report.</p>

        <h4 style="color:var(--accent);margin-top:1.5rem">Fase 1 — Registrazione</h4>
        <ol>
          <li>Il cliente si registra tramite il form sul sito <strong>fuerteventurecapital.com</strong></li>
          <li>Inserisce: nome, email, piano desiderato (BASIC / PRO / VALUE), asset (Azioni / ETF / Fondi)</li>
          <li>Sceglie la lingua del report: IT / ES / EN / FR / DE</li>
          <li>Completa il pagamento (abbonamento mensile o annuale)</li>
        </ol>

        <h4 style="color:var(--accent);margin-top:1.5rem">Fase 2 — Attivazione (lato admin)</h4>
        <ol>
          <li>Ricevuta la conferma di pagamento, aprire il tab <strong>CRM</strong> nella dashboard</li>
          <li>Aggiungere il cliente con i dati forniti, stato = <strong>Attivo</strong></li>
          <li>Il cliente inizierà a ricevere i report dalla prossima elaborazione (lun–ven)</li>
        </ol>

        <h4 style="color:var(--accent);margin-top:1.5rem">Fase 3 — Email di Benvenuto</h4>
        <p>Inviare manualmente (o tramite automazione Brevo) una email di benvenuto che include:</p>
        <ul>
          <li>Conferma del piano attivato e dell'asset scelto</li>
          <li>Spiegazione di cosa riceverà: report giornalieri lun–ven con i top titoli selezionati</li>
          <li>Come leggere il report: descrizione delle colonne (Score, EV/FCF, Sharpe, ecc.)</li>
          <li>Link al chatbot di supporto sul sito</li>
          <li>Contatto email per assistenza: supporto@fuerteventurecapital.com</li>
        </ul>

        <h4 style="color:var(--accent);margin-top:1.5rem">Fase 4 — Come Leggere il Report</h4>
        <p style="margin-bottom:.8rem">Il report è un file <strong>Excel multi-foglio</strong> ricevuto via email. Ogni piano include: <em>Top Selezionati</em> (foglio principale), <em>Azioni/ETF/Fondi Selezionati</em> (dati completi) e <em>Scartati per motivo</em> (solo VALUE). Le colonne variano per asset class — vedi sotto.</p>

        <!-- Colonne comuni a tutti i report -->
        <h5 style="color:#90CDF4;margin:1rem 0 .4rem">🔑 Colonne comuni a tutti i report</h5>
        <div class="tbl-wrap">
          <table>
            <thead><tr><th>Colonna</th><th>Cosa indica</th><th>Come leggerla</th></tr></thead>
            <tbody>
              <tr>
                <td><strong>Score</strong></td>
                <td>Punteggio percentile 0–100 calcolato da Robot Trader ogni sera</td>
                <td><strong>Score 85</strong> = questo strumento supera l'85% di tutti quelli analizzati nella stessa elaborazione. È un ranking <em>relativo</em>: cambia ogni giorno con il mercato. Non confrontare score di giorni diversi.</td>
              </tr>
              <tr>
                <td><strong>Ticker</strong></td>
                <td>Codice identificativo dello strumento sulla borsa di quotazione</td>
                <td>Usare questo codice per cercare lo strumento sul proprio broker (es. <em>AAPL</em> = Apple su NASDAQ, <em>VWCE.DE</em> = Vanguard FTSE All-World su Xetra)</td>
              </tr>
              <tr>
                <td><strong>Nome</strong></td>
                <td>Ragione sociale dell'azienda o nome ufficiale dell'ETF/Fondo</td>
                <td>Nome completo — utile per ricerche su Google Finance, Yahoo Finance o JustETF</td>
              </tr>
              <tr>
                <td><strong>Mercato / Indice</strong></td>
                <td>Borsa di quotazione e indice di appartenenza</td>
                <td>Indica il paese e il segmento di mercato (es. NYSE, Xetra, Borsa Italiana)</td>
              </tr>
              <tr>
                <td><strong>Prezzo</strong></td>
                <td>Prezzo di chiusura nella valuta locale dello strumento</td>
                <td>Prezzo al momento dell'elaborazione notturna — può variare all'apertura del giorno dopo</td>
              </tr>
              <tr>
                <td><strong>Data Dati</strong></td>
                <td>Data dell'ultima rilevazione dei dati</td>
                <td>Conferma che i dati sono aggiornati — utile per verificare in caso di festività o dati mancanti</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Report AZIONI -->
        <h5 style="color:#90CDF4;margin:1.2rem 0 .4rem">📈 Colonne Report AZIONI (PRO / VALUE)</h5>
        <div class="tbl-wrap">
          <table>
            <thead><tr><th>Colonna</th><th>Formula / Definizione</th><th>Interpretazione pratica</th></tr></thead>
            <tbody>
              <tr>
                <td><strong>EV/FCF</strong></td>
                <td>Enterprise Value ÷ Free Cash Flow.<br><small>EV = Market Cap + Debito Netto<br>FCF = Utile Op. − Investimenti</small></td>
                <td>Quanti anni ci vorrebbero per ripagare l'intera azienda con la sola cassa generata. <strong>Più basso = più conveniente.</strong> Un'azienda che genera molta cassa rispetto al suo prezzo è potenzialmente sottovalutata.</td>
              </tr>
              <tr>
                <td><strong>P/B</strong></td>
                <td>Prezzo Azione ÷ Valore Contabile per Azione</td>
                <td>Quanto paga il mercato rispetto al patrimonio netto reale. <strong>P/B &lt; 1</strong> = l'azienda quota sotto il suo valore contabile (possibile occasione). <strong>P/B &gt; 3</strong> = il mercato sconta forte crescita futura.</td>
              </tr>
              <tr>
                <td><strong>ROE</strong></td>
                <td>Utile Netto ÷ Patrimonio Netto × 100</td>
                <td>Quanto rende il capitale degli azionisti. <strong>ROE elevato</strong> = management efficiente. Attenzione: un ROE molto alto può derivare da eccessivo indebitamento — verificare sempre insieme al Net Debt/EBITDA.</td>
              </tr>
              <tr>
                <td><strong>Net Debt/EBITDA</strong></td>
                <td>(Totale Debiti − Liquidità) ÷ EBITDA</td>
                <td>Quanti anni di utile operativo servono per ripagare il debito. <strong>Valore basso</strong> = azienda solida e poco indebitata. <strong>Valore alto</strong> = rischio finanziario elevato. Non applicato a banche e assicurazioni.</td>
              </tr>
              <tr>
                <td><strong>Dividend Yield</strong></td>
                <td>Dividendo Annuo ÷ Prezzo × 100</td>
                <td>Rendimento annuo da dividendo rispetto al prezzo corrente. Colonna più rilevante per il piano <strong>BASIC</strong> — chi cerca reddito passivo immediato guarda questo valore per primo.</td>
              </tr>
              <tr>
                <td><strong>Var 1D %</strong></td>
                <td>Variazione % del prezzo nella seduta corrente</td>
                <td>Segnale di momentum di breve termine. Rilevante soprattutto per il piano <strong>BASIC</strong>. Un titolo che sale il giorno del report potrebbe confermare l'interesse del mercato.</td>
              </tr>
              <tr>
                <td><strong>Perf 1M / 3M / 6M / 1Y %</strong></td>
                <td>Variazione % del prezzo nei periodi indicati</td>
                <td>Storico di performance su più orizzonti. Utile per capire se il titolo è in trend positivo o ha già corso molto. Nel piano <strong>VALUE</strong> queste colonne sono informative — non guidano la selezione.</td>
              </tr>
              <tr>
                <td><strong>Market Cap</strong></td>
                <td>Capitalizzazione totale (Prezzo × Numero Azioni)</td>
                <td>Dimensione dell'azienda. Filtro di liquidità minima — garantisce che il titolo sia negoziabile senza problemi. Blue Chip = grandi cap, Mid Cap = capitalizzazioni medie.</td>
              </tr>
              <tr>
                <td><strong>Settore / Industry</strong></td>
                <td>Classificazione settoriale GICS</td>
                <td>Utile per valutare la concentrazione settoriale del proprio portafoglio. Se si acquistano 5 titoli tutti nello stesso settore, il portafoglio non è diversificato.</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Report ETF -->
        <h5 style="color:#90CDF4;margin:1.2rem 0 .4rem">📦 Colonne Report ETF</h5>
        <div class="tbl-wrap">
          <table>
            <thead><tr><th>Colonna</th><th>Formula / Definizione</th><th>Interpretazione pratica</th></tr></thead>
            <tbody>
              <tr>
                <td><strong>ISIN</strong></td>
                <td>International Securities Identification Number — codice universale a 12 caratteri</td>
                <td>Codice univoco dell'ETF indipendente dalla borsa di quotazione. Usare l'ISIN per cercare l'ETF su JustETF o sul proprio broker europeo senza ambiguità.</td>
              </tr>
              <tr>
                <td><strong>TER</strong></td>
                <td>Total Expense Ratio — costo di gestione annuo in %</td>
                <td>Costo dedotto automaticamente ogni anno dal patrimonio del fondo. <strong>Più basso è meglio</strong>, soprattutto su orizzonti lunghi. ETF passivi tipici: 0.03%–0.50%. Su €100.000 e 20 anni, uno 0.20% in più di TER costa oltre €5.000 in rendimento perso.</td>
              </tr>
              <tr>
                <td><strong>Sharpe Ratio</strong></td>
                <td>(Rendimento − Tasso Risk-Free) ÷ Deviazione Standard</td>
                <td>Rendimento ottenuto per ogni unità di rischio assunto. <strong>Negativo</strong> = rendimento inferiore al risk-free. <strong>&lt; 1</strong> = rendimento non adeguato al rischio. <strong>1–2</strong> = buono. <strong>≥ 2</strong> = eccellente. È la metrica principale di selezione nei piani PRO e VALUE.</td>
              </tr>
              <tr>
                <td><strong>Performance 1Y</strong></td>
                <td>Variazione % del NAV negli ultimi 12 mesi</td>
                <td>Rendimento annuo dell'ETF. Da leggere sempre insieme allo Sharpe: un rendimento alto con Sharpe basso significa che è stato ottenuto con molta volatilità (rischio elevato).</td>
              </tr>
              <tr>
                <td><strong>Perf 3M %</strong></td>
                <td>Variazione % negli ultimi 3 mesi</td>
                <td>Momentum di breve termine. Peso dominante nel piano <strong>BASIC</strong>. Nei piani VALUE il dato trimestrale è quasi irrilevante — un ETF value si valuta su decenni.</td>
              </tr>
              <tr>
                <td><strong>Net Assets (AUM)</strong></td>
                <td>Patrimonio totale gestito dall'ETF</td>
                <td>Indicatore di liquidità e stabilità. ETF con AUM basso rischiano la chiusura o spread bid/ask molto ampi. Robot Trader applica una soglia minima di AUM come prerequisito di accesso all'universo analizzato.</td>
              </tr>
              <tr>
                <td><strong>Replica</strong></td>
                <td>Metodo di replica dell'indice: Fisica completa / Campionamento / Sintetica</td>
                <td>Robot Trader seleziona <strong>solo ETF a replica fisica</strong>. Nessun ETF sintetico (swap) nell'universo analizzato — zero rischio controparte.</td>
              </tr>
              <tr>
                <td><strong>Tipo (ACC)</strong></td>
                <td>Accumulazione vs Distribuzione</td>
                <td>Robot Trader analizza <strong>solo ETF ad accumulazione</strong>: i dividendi vengono reinvestiti automaticamente nel fondo, ottimizzando l'interesse composto ed evitando la doppia tassazione europea.</td>
              </tr>
              <tr>
                <td><strong>Stelle MS</strong></td>
                <td>Rating Morningstar ★ a ★★★★★</td>
                <td>Valutazione Morningstar della performance aggiustata per il rischio rispetto ai fondi comparabili. <strong>5 stelle</strong> = top 10% della categoria. Informativo — non usato come filtro diretto nello score.</td>
              </tr>
              <tr>
                <td><strong>Età (anni)</strong></td>
                <td>Anni di vita dell'ETF dalla data di lancio</td>
                <td>ETF molto giovani (&lt; 3 anni) hanno storico di dati limitato — lo Sharpe su breve storia può essere poco affidabile. I piani PRO e VALUE preferiscono ETF con track record più lungo.</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Report FONDI -->
        <h5 style="color:#90CDF4;margin:1.2rem 0 .4rem">🏦 Colonne Report FONDI (US &amp; EU UCITS)</h5>
        <div class="tbl-wrap">
          <table>
            <thead><tr><th>Colonna</th><th>Formula / Definizione</th><th>Interpretazione pratica</th></tr></thead>
            <tbody>
              <tr>
                <td><strong>TER</strong></td>
                <td>Total Expense Ratio annuo</td>
                <td>Nei fondi a gestione attiva il TER è tipicamente 0.5%–2.5%, più alto rispetto agli ETF. Un TER alto è accettabile solo se il fondo genera alfa reale — cioè rendimento superiore all'indice di riferimento al netto dei costi.</td>
              </tr>
              <tr>
                <td><strong>Sharpe Ratio</strong></td>
                <td>(Rendimento − Tasso Risk-Free) ÷ Deviazione Standard</td>
                <td>Stessa logica degli ETF. Nei fondi è la metrica più importante per distinguere gestori che generano rendimento con disciplina da quelli che semplicemente cavalcano il mercato.</td>
              </tr>
              <tr>
                <td><strong>AUM</strong></td>
                <td>Assets Under Management — patrimonio totale del fondo</td>
                <td>Nei fondi l'AUM sostituisce il Volume come proxy di liquidità. Un fondo con AUM elevato ha più stabilità e rischio di chiusura vicino a zero.</td>
              </tr>
              <tr>
                <td><strong>Performance 1Y</strong></td>
                <td>Variazione % del NAV negli ultimi 12 mesi</td>
                <td>Rendimento annuo del fondo. Da confrontare sempre con il benchmark di riferimento: se il fondo rende il 10% ma il suo indice ha fatto il 15%, il gestore ha <em>distrutto</em> valore nonostante l'apparente buon rendimento.</td>
              </tr>
              <tr>
                <td><strong>Perf 3M %</strong></td>
                <td>Variazione % del NAV negli ultimi 3 mesi</td>
                <td>Momentum recente. Peso alto nel piano <strong>BASIC</strong> per chi cerca rendimento immediato. Nei piani VALUE il trimestrale è rumore — un gestore quality si valuta su cicli completi di mercato (5–10 anni).</td>
              </tr>
              <tr>
                <td><strong>Stelle MS</strong></td>
                <td>Rating Morningstar ★ a ★★★★★</td>
                <td><strong>5 stelle</strong> = top 10% della categoria per performance aggiustata per il rischio. <strong>4 stelle</strong> = top 22.5%. Informativo nel report — il sistema Robot Trader usa il proprio score basato su metriche quantitative.</td>
              </tr>
              <tr>
                <td><strong>Categoria</strong></td>
                <td>Classificazione Morningstar del fondo per stile e asset class</td>
                <td>Utile per capire in quale segmento opera il fondo (es. Large Cap Growth USA, Obbligazionario EUR, Bilanciato). Fondamentale per non duplicare l'esposizione nel portafoglio.</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Fogli Excel e struttura multi-sheet -->
        <h5 style="color:#90CDF4;margin:1.2rem 0 .4rem">📋 Struttura Excel multi-foglio</h5>
        <div class="tbl-wrap">
          <table>
            <thead><tr><th>Foglio</th><th>Contenuto</th><th>Disponibile in</th></tr></thead>
            <tbody>
              <tr><td><strong>Top Selezionati</strong></td><td>I migliori strumenti selezionati, ordinati per Score decrescente. Vista compatta con le colonne più utili.</td><td>Tutti i piani</td></tr>
              <tr><td><strong>Selezionati (completo)</strong></td><td>Tutti gli strumenti che hanno superato i filtri, con tutte le colonne disponibili. Vista analitica completa.</td><td>Tutti i piani</td></tr>
              <tr><td><strong>Scartati per motivo</strong></td><td>Strumenti esclusi, raggruppati per il criterio che non hanno superato (es. EV/FCF, P/B, Sharpe). Utile per capire perché un titolo specifico non è in lista.</td><td>Solo piani PRO e VALUE</td></tr>
              <tr><td><strong>Non Validi</strong></td><td>Strumenti con dati mancanti o insufficienti al momento dell'elaborazione.</td><td>Solo piani VALUE</td></tr>
            </tbody>
          </table>
        </div>
        <p style="font-size:.82rem;opacity:.7;margin-top:.6rem">💡 <strong>Consiglio:</strong> iniziare sempre dal foglio <em>Top Selezionati</em> per una panoramica rapida. Aprire <em>Selezionati (completo)</em> per approfondire un titolo specifico. Usare <em>Scartati</em> per capire perché un proprio titolo di interesse non è in lista.</p>

        <h4 style="color:var(--accent);margin-top:1.5rem">Fase 5 — Supporto e Chatbot</h4>
        <ul>
          <li>Il chatbot Robot Trader è disponibile sul sito 24/7 per rispondere a domande sui mercati, le metriche e il funzionamento del servizio</li>
          <li>Per domande sull'abbonamento o problemi tecnici: email diretta al team</li>
          <li>I report vengono inviati ogni giorno lavorativo — se manca un report, verificare la cartella spam</li>
        </ul>

        <h4 style="color:var(--accent);margin-top:1.5rem">Fase 6 — Profilazione Consigliata</h4>
        <p style="margin-bottom:.5rem">Suggerire al cliente di rispondere al questionario sul profilo investitore. La raccomandazione segue 3 step: <strong>1)</strong> asset class preferita → <strong>2)</strong> orizzonte temporale + esperienza → <strong>3)</strong> segnali chiave nel dialogo.</p>

        <h5 style="color:#90CDF4;margin:1.2rem 0 .4rem">📈 AZIONI</h5>
        <div class="tbl-wrap">
          <table>
            <thead><tr><th>Piano</th><th>Profilo</th><th>Orizzonte</th><th>Chi è</th><th>Segnali tipici</th></tr></thead>
            <tbody>
              <tr>
                <td><strong>BASIC €29</strong></td>
                <td>L'Investitore in Dividendi</td>
                <td>3–12 mesi</td>
                <td>Privato 40–65aa, libero professionista o dipendente con risparmio. Conosce i titoli noti (Enel, Apple, LVMH). Non legge bilanci in profondità.</td>
                <td><em>"voglio dividendi", "cedola", "rendita passiva", "titoli sicuri", "non sono esperto"</em></td>
              </tr>
              <tr>
                <td><strong>PRO €39</strong></td>
                <td>L'Analista Fondamentale Globale</td>
                <td>2–5 anni</td>
                <td>Investitore attivo 35–55aa, sa leggere un conto economico, conosce EV/FCF e ROE. Portafoglio personale €50k–€500k, investe sui mercati esteri.</td>
                <td><em>"analisi fondamentale", "EV/FCF", "sottovalutato", "valore intrinseco", "investo all'estero", "portafoglio €100k"</em></td>
              </tr>
              <tr>
                <td><strong>VALUE €59</strong></td>
                <td>Il Deep Value Investor</td>
                <td>5–15 anni</td>
                <td>Consulente indipendente, gestore patrimoniale, family office. Approccio stile Buffett/Munger. Gestisce patrimoni >€1M o portafogli di terzi. Cerca conviction su poche posizioni.</td>
                <td><em>"Buffett", "Munger", "deep value", "conviction", "patrimonio >€1M", "gestisco portafogli", "family office"</em></td>
              </tr>
            </tbody>
          </table>
        </div>

        <h5 style="color:#90CDF4;margin:1.2rem 0 .4rem">📦 ETF</h5>
        <div class="tbl-wrap">
          <table>
            <thead><tr><th>Piano</th><th>Profilo</th><th>Orizzonte</th><th>Chi è</th><th>Segnali tipici</th></tr></thead>
            <tbody>
              <tr>
                <td><strong>BASIC €29</strong></td>
                <td>Il Risparmiatore sul Trend</td>
                <td>6–18 mesi</td>
                <td>25–45aa, tech-savvy, PAC mensile o somma da investire. Non ha formazione avanzata. Vuole entrare su ETF che stanno già performando bene nel trimestre.</td>
                <td><em>"ETF", "PAC", "accumulo mensile", "quale settore sta andando bene", "momentum", "trend"</em></td>
              </tr>
              <tr>
                <td><strong>PRO €39</strong></td>
                <td>Il Portfolio Manager Attivo</td>
                <td>3–7 anni</td>
                <td>Investitore sofisticato che costruisce portafogli ETF diversificati (8–15 ETF). Conosce lo Sharpe ratio, attento ai costi su medio periodo.</td>
                <td><em>"Sharpe ratio", "portafoglio bilanciato", "8-15 ETF", "risk-adjusted", "costruisco portafoglio per cliente"</em></td>
              </tr>
              <tr>
                <td><strong>VALUE €59</strong></td>
                <td>Il Wealth Manager Istituzionale</td>
                <td>10–30 anni</td>
                <td>Wealth manager, fondo pensione, family office. Sa che frazioni di TER su grandi patrimoni si traducono in €100k+ di costi aggiuntivi in 20 anni. Ogni basis point conta.</td>
                <td><em>"wealth manager", "fondo pensione", "TER minimo", "basis point", "10-20-30 anni", "patrimonio istituzionale"</em></td>
              </tr>
            </tbody>
          </table>
        </div>

        <h5 style="color:#90CDF4;margin:1.2rem 0 .4rem">🏦 FONDI US &amp; FONDI EU UCITS</h5>
        <div class="tbl-wrap">
          <table>
            <thead><tr><th>Piano</th><th>Profilo</th><th>Orizzonte</th><th>Chi è</th><th>Segnali tipici</th></tr></thead>
            <tbody>
              <tr>
                <td><strong>BASIC €29</strong></td>
                <td>Il Cliente della Banca</td>
                <td>6–24 mesi</td>
                <td>Retail 45–70aa, cliente di banca tradizionale (Mediolanum, Fineco, Azimut). Nessun background tecnico, si fida del nome del gestore, guarda la performance recente.</td>
                <td><em>"fondo comune", "Mediolanum", "Fineco", "cosa rende di più adesso", "il mio consulente in banca"</em></td>
              </tr>
              <tr>
                <td><strong>PRO €39</strong></td>
                <td>Il Consulente Finanziario Indipendente</td>
                <td>3–7 anni</td>
                <td>CFI, private banker o advisor che seleziona fondi per portafogli clienti €500k–€5M. Capisce alfa reale vs. beta di mercato. Vuole gestori disciplinati e consistenti.</td>
                <td><em>"CFI", "private banker", "gestisco portafogli clienti", "alfa", "seleziono fondi", "advisor"</em></td>
              </tr>
              <tr>
                <td><strong>VALUE €59</strong></td>
                <td>Il Family Office / Istituzionale</td>
                <td>10–30 anni</td>
                <td>Family office, fondazione, fondo pensione. Patrimoni >€5M. Massimo Sharpe + TER minimo assoluto. Non guarda il trimestre — guarda la qualità del processo nel lungo periodo.</td>
                <td><em>"family office", "fondazione", "fondo pensione", "gestisco >€5M", "TER minimo", "20 anni di orizzonte"</em></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p style="margin-top:.8rem;font-size:.82rem;opacity:.7">💡 <strong>Fondi EU UCITS</strong> vs Fondi US: stessa struttura di profili, ma per investitori europei che preferiscono strumenti regolamentati UE (UCITS/KIID), acquistabili dalla propria banca italiana, spagnola o francese senza problemi fiscali o di distribuzione.</p>

        <h5 style="color:#90CDF4;margin:1.2rem 0 .4rem">🧭 Guida rapida di orientamento</h5>
        <div class="tbl-wrap">
          <table>
            <thead><tr><th>Orizzonte</th><th>Esperienza</th><th>Piano consigliato</th></tr></thead>
            <tbody>
              <tr><td>&lt; 1 anno</td><td>qualsiasi</td><td>BASIC (qualsiasi asset)</td></tr>
              <tr><td>1–3 anni</td><td>bassa / media</td><td>BASIC</td></tr>
              <tr><td>2–5 anni</td><td>media / alta</td><td>PRO</td></tr>
              <tr><td>5–15 anni</td><td>alta / professionale</td><td>VALUE</td></tr>
              <tr><td>&gt; 10 anni</td><td>istituzionale / family office</td><td>VALUE</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

  <div class="footer">Robot Trader 2026 — Fuerte Venture Capital SL</div>
</div>

<script>
// ═══════════════════════════════════════════════
// GLOBALS
// ═══════════════════════════════════════════════
var _sv = null;
var _tableData  = {};   // {tipo: rows[]}
var _tableCols  = {};   // {tipo: cols[]}
var _sortState  = {};   // {tipo: {col: null, dir: -1}}
var _logInt = null;
var _loaded = {};

var ASSETS = ['azioni','etf','fondi','ordini'];
var TIERS  = ['basic','pro','value'];
var ICONS  = {azioni:'📈',etf:'📦',fondi:'🏦'};

var PLABELS = {
  ev_fcf_max:'EV/FCF max', price_book_max:'P/B max',
  roe_min:'ROE min', net_debt_ebitda_max:'ND/EBITDA max',
  ter_max:'TER max (%)', sharpe_min:'Sharpe min',
  volume_min:'Volume/AUM min', performance_1y_min:'Perf 1Y min (%)'
};
var PSTEP = {
  ev_fcf_max:0.5, price_book_max:0.05, roe_min:0.01, net_debt_ebitda_max:0.1,
  ter_max:0.05, sharpe_min:0.05, volume_min:10000, performance_1y_min:0.01
};

// Etichette parametri screener globali (parametri.json)
var SP_LABELS = {
  ev_fcf_max:'EV/FCF max', price_book_max:'P/B max',
  roe_min:'ROE min (%)', net_debt_ebitda_max:'Net Debt/EBITDA max',
  ter_max:'TER max (%)', sharpe_min:'Sharpe min',
  volume_min:'Volume min', performance_1y_min:'Perf 1Y min',
  min_age_years:'Età minima ETF (anni)',
  only_accumulating:'Solo accumulazione (ACC)',
  only_physical:'Solo replica fisica'
};
var SP_STEP = {
  ev_fcf_max:0.5, price_book_max:0.05, roe_min:0.01, net_debt_ebitda_max:0.1,
  ter_max:0.05, sharpe_min:0.05, volume_min:10000, performance_1y_min:0.01,
  min_age_years:1
};

// ─── CLIENTI ─────────────────────────────────────────────────
var _clienti = null;

function loadClienti(){
  fetch('/api/clienti').then(function(r){
    if(!r.ok||r.redirected) throw new Error('Sessione scaduta');
    return r.json();
  }).then(function(data){
    _clienti = data;
    renderClienti();
  }).catch(function(e){showMsg('cl-msg','❌ '+e.message,'err');});
}

function renderClienti(){
  if(!_clienti) return;
  var all = (_clienti.tester||[]).concat(_clienti.clienti||[]);
  var nTester  = (_clienti.tester||[]).length;
  var nClienti = (_clienti.clienti||[]).length;
  var nAttivi  = all.filter(function(c){return c.stato==='ATTIVO';}).length;

  // Stats KPI
  var statsHtml = [
    ['👥 Totale', all.length, '#4A90D9'],
    ['🧪 Tester',  nTester,   '#F6AD55'],
    ['💳 Clienti', nClienti,  '#68D391'],
    ['✅ Attivi',  nAttivi,   '#48BB78'],
  ].map(function(s){
    return '<div style="background:rgba(255,255,255,.05);border-radius:10px;padding:.7rem 1.2rem;min-width:110px;text-align:center">'
         + '<div style="font-size:.75rem;opacity:.55;margin-bottom:.2rem">'+s[0]+'</div>'
         + '<div style="font-size:1.6rem;font-weight:700;color:'+s[2]+'">'+s[1]+'</div></div>';
  }).join('');
  document.getElementById('cl-stats').innerHTML = statsHtml;

  // Aggiorna contatore destinatari email nella home
  var nDest = all.filter(function(c){
    return c.stato !== 'SOSPESO' && (
      (c.piano_azioni && c.piano_azioni !== 'NONE') ||
      (c.piano_etf    && c.piano_etf    !== 'NONE') ||
      (c.piano_fondi  && c.piano_fondi  !== 'NONE')
    );
  }).length + 1; // +1 admin (rioluc63)
  var _sd = document.getElementById('stat-dest');
  if(_sd) _sd.textContent = nDest + ' destinatari';

  // Tabella
  var headers = ['Nome','Email','Paese','Azioni','ETF','Fondi','Ordini','Stato','Registrato','Operazioni'];
  var headHtml = headers.map(function(h){
    return '<th style="background:#2C5282;color:#fff;padding:.5rem .8rem;text-align:left;font-size:.82rem">'+h+'</th>';
  }).join('');
  document.getElementById('cl-head').innerHTML = headHtml;

  var pianoColor = {NONE:'#555',BASIC:'#4A90D9',PRO:'#F6AD55',VALUE:'#68D391'};
  var statoColor = {TESTER:'#F6AD55',ATTIVO:'#68D391',SOSPESO:'#FC8181',SCADUTO:'#9F7AEA'};

  function badge(val, colors){
    var c = colors[val]||'#888';
    return '<span style="background:'+c+'22;color:'+c+';border:1px solid '+c+'44;border-radius:4px;padding:.15rem .45rem;font-size:.75rem;font-weight:600">'+val+'</span>';
  }

  // Mappa: categoria → indice reale nella lista originale
  var _clMap = [];
  (_clienti.tester||[]).forEach(function(c,i){_clMap.push({cat:'tester',idx:i,c:c});});
  (_clienti.clienti||[]).forEach(function(c,i){_clMap.push({cat:'clienti',idx:i,c:c});});

  var PAESE_FLAG = {IT:'🇮🇹',ES:'🇪🇸',FR:'🇫🇷',DE:'🇩🇪',UK:'🇬🇧'};

  var rows = _clMap.map(function(entry,i){
    var c=entry.c, cat=entry.cat, idx=entry.idx;
    var bg = i%2===0 ? 'rgba(255,255,255,.02)' : 'transparent';
    var df = c.dati_fiscali || {};
    var paeseCell = df.paese ? (PAESE_FLAG[df.paese]||'') + ' ' + df.paese : '<span style="opacity:.3">—</span>';
    var cfOk = df.codice_fiscale ? '✓' : '';
    var anagBtn = '<button class="btn" style="padding:.2rem .55rem;font-size:.75rem;border-color:rgba(179,151,90,.4);color:#B3975A" '
      +'onclick="mostraModalAnagrafica(\''+cat+'\','+idx+')" title="Dati anagrafici e fiscali">📋'+cfOk+'</button>';
    var attivaBtn = (c.stato!=='ATTIVO')
      ? '<button class="btn btn-gr" style="padding:.2rem .6rem;font-size:.75rem" onclick="mostraModalAttiva(\''+cat+'\','+idx+',\''+c.nome+'\',\''+c.email+'\',\''+c.piano_azioni+'\',\''+c.piano_etf+'\',\''+c.piano_fondi+'\',\''+c.piano_ordini+'\')">Attiva</button>'
      : '<span style="color:#68D391;font-size:.78rem">✓</span>';
    var fattBtn = (c.numero_fattura)
      ? '<a href="/api/fattura/'+c.numero_fattura+'" target="_blank" class="btn" style="padding:.2rem .5rem;font-size:.72rem;border-color:rgba(246,173,85,.35);color:#F6AD55;text-decoration:none" title="Scarica fattura '+c.numero_fattura+'">🧾</a>'
      : '';
    var eliminaBtn = '<button class="btn" style="padding:.2rem .5rem;font-size:.72rem;border-color:rgba(239,68,68,.35);color:#f87171" onclick="eliminaTester(\''+cat+'\','+idx+',\''+c.email+'\')" title="Elimina cliente">🗑</button>';
    var waOn = c.whatsapp_optin === true;
    var waBtn = '<button class="btn" style="padding:.2rem .5rem;font-size:.72rem;'
      +(waOn ? 'border-color:#25D36644;color:#25D366' : 'border-color:#55555566;color:#666')
      +'" onclick="toggleWhatsapp(\''+cat+'\','+idx+','+waOn+')" title="'+(waOn?'WhatsApp attivo — clicca per disattivare':'Attiva notifiche WhatsApp')+'">📱'+(waOn?'✓':'')+'</button>';
    return '<tr style="background:'+bg+'">'
      +'<td style="padding:.45rem .8rem;font-size:.84rem">'+(c.cognome?c.nome+' '+c.cognome:c.nome)+(c.codice_cliente?'<br><span style="font-size:.68rem;color:#F6AD55;opacity:.6;font-family:monospace">'+c.codice_cliente+'</span>':'')+'</td>'
      +'<td style="padding:.45rem .8rem;font-size:.82rem;opacity:.75">'+c.email+'</td>'
      +'<td style="padding:.45rem .8rem;font-size:.82rem">'+paeseCell+'</td>'
      +'<td style="padding:.45rem .8rem">'+badge(c.piano_azioni||'NONE',pianoColor)+'</td>'
      +'<td style="padding:.45rem .8rem">'+badge(c.piano_etf||'NONE',pianoColor)+'</td>'
      +'<td style="padding:.45rem .8rem">'+badge(c.piano_fondi||'NONE',pianoColor)+'</td>'
      +'<td style="padding:.45rem .8rem">'+badge(c.piano_ordini||'NONE',pianoColor)+'</td>'
      +'<td style="padding:.45rem .8rem">'+badge(c.stato||'—',statoColor)+'</td>'
      +'<td style="padding:.45rem .8rem;font-size:.78rem;opacity:.6">'+c.data_registrazione+'</td>'
      +'<td style="padding:.45rem .8rem;display:flex;gap:.35rem">'+anagBtn+' '+attivaBtn+' '+fattBtn+' '+waBtn+' '+eliminaBtn+'</td>'
      +'</tr>';
  }).join('');
  document.getElementById('cl-body').innerHTML = rows || '<tr><td colspan="10" style="padding:2rem;text-align:center;opacity:.4">Nessun cliente</td></tr>';
}

// ─── MODALS CLIENTI ──────────────────────────────────────────
var _atCat='', _atIdx=0;

function chiudiModals(){
  document.getElementById('modal-aggiungi').style.display='none';
  document.getElementById('modal-attiva').style.display='none';
  document.getElementById('modal-anagrafica').style.display='none';
}

// ─── MODAL ANAGRAFICA / DATI FISCALI ─────────────────────────
var _anCat='', _anIdx=0;

var PAESE_CFG = {
  IT:{nome:'🇮🇹 Italia',      cf:'Codice Fiscale',   ph:'RSSMRA80A01H501U', piva:true},
  ES:{nome:'🇪🇸 Spagna',      cf:'DNI / NIE',        ph:'12345678A',        piva:false},
  FR:{nome:'🇫🇷 Francia',     cf:'Numéro Fiscal',    ph:'1234567890123',    piva:false},
  DE:{nome:'🇩🇪 Germania',    cf:'Steuer-ID',        ph:'12345678901',      piva:false},
  UK:{nome:'🇬🇧 Regno Unito', cf:'NI Number / UTR',  ph:'AB123456C',        piva:false},
};

function aggiornaPaeseForm(){
  var paese = document.getElementById('an-paese').value;
  var cfg = PAESE_CFG[paese] || {};
  var cfLbl = document.getElementById('an-cf-label');
  var cfInp = document.getElementById('an-cf');
  var pivaRow = document.getElementById('an-piva-row');
  if(cfg.cf){ cfLbl.textContent=cfg.cf; cfInp.placeholder=cfg.ph||''; }
  if(pivaRow) pivaRow.style.display = cfg.piva ? '' : 'none';
}

function eliminaTester(cat, idx, email){
  if(!confirm('Eliminare il tester ' + email + '?')) return;
  fetch('/api/clienti/elimina',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({cat:cat, idx:idx, email:email})
  }).then(function(r){return r.json();}).then(function(res){
    if(res.ok){ _clienti=null; loadClienti(); showMsg('cl-msg','🗑 Tester eliminato','ok'); }
    else showMsg('cl-msg','❌ '+res.msg,'err');
  });
}

function toggleWhatsapp(cat, idx, current){
  var label = current ? 'Disattivare le notifiche WhatsApp per questo cliente?' : 'Attivare le notifiche WhatsApp per questo cliente?\n(Il cliente deve aver dato consenso esplicito)';
  if(!confirm(label)) return;
  fetch('/api/clienti/whatsapp',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({cat:cat, idx:idx, optin:!current})
  }).then(function(r){return r.json();}).then(function(res){
    if(res.ok){ _clienti=null; loadClienti(); showMsg('cl-msg', current ? '📵 WhatsApp disattivato' : '📱 WhatsApp attivato','ok'); }
    else showMsg('cl-msg','❌ '+res.msg,'err');
  });
}

function mostraModalAnagrafica(cat, idx){
  _anCat=cat; _anIdx=idx;
  var entry = null;
  var lista = cat==='tester' ? (_clienti.tester||[]) : (_clienti.clienti||[]);
  entry = lista[idx];
  if(!entry) return;
  var df = entry.dati_fiscali || {};
  var set = function(id,val){ var el=document.getElementById(id); if(el) el.value=val||''; };
  set('an-nome',    entry.nome);
  set('an-cognome', entry.cognome || '');
  set('an-email',   entry.email);
  set('an-paese',   df.paese||'IT');
  set('an-nascita', df.data_nascita||'');
  set('an-indirizzo',df.indirizzo||'');
  set('an-cap',     df.cap||'');
  set('an-citta',   df.citta||'');
  set('an-cf',      df.codice_fiscale||'');
  set('an-tel',     df.telefono||'');
  set('an-piva',    df.p_iva||'');
  aggiornaPaeseForm();
  document.getElementById('modal-anagrafica').style.display='flex';
}

function salvaAnagrafica(){
  fetch('/api/clienti/anagrafica',{method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({
      categoria:      _anCat,
      index:          _anIdx,
      cognome:        document.getElementById('an-cognome').value.trim(),
      paese:          document.getElementById('an-paese').value,
      data_nascita:   document.getElementById('an-nascita').value.trim(),
      indirizzo:      document.getElementById('an-indirizzo').value.trim(),
      cap:            document.getElementById('an-cap').value.trim(),
      citta:          document.getElementById('an-citta').value.trim(),
      codice_fiscale: document.getElementById('an-cf').value.trim(),
      telefono:       document.getElementById('an-tel').value.trim(),
      p_iva:          document.getElementById('an-piva').value.trim(),
    })
  }).then(function(r){return r.json();}).then(function(res){
    chiudiModals();
    if(res.ok){ showMsg('cl-msg','✅ Dati fiscali salvati','ok'); _clienti=null; loadClienti(); }
    else showMsg('cl-msg','❌ '+res.msg,'err');
  });
}

function mostraModalAggiungi(){
  document.getElementById('modal-aggiungi').style.display='flex';
}

function confermaAggiungi(){
  var nome=document.getElementById('ag-nome').value.trim();
  var cognome=document.getElementById('ag-cognome').value.trim();
  var email=document.getElementById('ag-email').value.trim();
  if(!nome||!email){alert('Nome ed email obbligatori');return;}
  fetch('/api/clienti/aggiungi',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
      nome:nome, cognome:cognome, email:email,
      piano_azioni:document.getElementById('ag-azioni').value,
      piano_etf:document.getElementById('ag-etf').value,
      piano_fondi:document.getElementById('ag-fondi').value,
      piano_ordini:document.getElementById('ag-ordini').value,
    })
  }).then(function(r){return r.json();}).then(function(res){
    if(res.ok){chiudiModals();_clienti=null;loadClienti();showMsg('cl-msg','✅ Cliente aggiunto','ok');}
    else showMsg('cl-msg','❌ '+res.msg,'err');
  });
}

function mostraModalAttiva(cat,idx,nome,email,pAz,pEtf,pFondi,pOrd){
  _atCat=cat; _atIdx=idx;
  document.getElementById('at-info').textContent=nome+' — '+email;
  var sel=function(id,val){
    var s=document.getElementById(id);
    for(var i=0;i<s.options.length;i++) s.options[i].selected=(s.options[i].value===val);
  };
  sel('at-azioni',pAz||'NONE');
  sel('at-etf',pEtf||'NONE');
  sel('at-fondi',pFondi||'NONE');
  sel('at-ordini',pOrd||'NONE');
  document.getElementById('modal-attiva').style.display='flex';
}

function confermaAttiva(){
  fetch('/api/clienti/attiva',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
      categoria:_atCat, index:_atIdx,
      piano_azioni:document.getElementById('at-azioni').value,
      piano_etf:document.getElementById('at-etf').value,
      piano_fondi:document.getElementById('at-fondi').value,
      piano_ordini:document.getElementById('at-ordini').value,
    })
  }).then(function(r){return r.json();}).then(function(res){
    chiudiModals();
    if(res.ok){
      _clienti=null; loadClienti();
      if(res.email_inviata){
        showMsg('cl-msg','✅ Cliente attivato — credenziali inviate via email.','ok');
      } else {
        var pwd = res.password_temp;
        alert('🔑 PASSWORD TEMPORANEA:\n\n' + pwd + '\n\nAnnotala ora — non verrà mostrata di nuovo!\nURL cliente: __BASE_URL__/client-login');
        // Mostra anche il box persistente dopo il reload DOM
        setTimeout(function(){
          var box=document.getElementById('cl-pwd-box');
          if(box){
            document.getElementById('cl-pwd-val').textContent=pwd;
            box.style.display='block';
            box.scrollIntoView({behavior:'smooth',block:'center'});
          }
        }, 800);
        showMsg('cl-msg','⚠️ Email NON inviata — vedi il riquadro arancione con la password.','err');
      }
    } else showMsg('cl-msg','❌ '+res.msg,'err');
  });
}

// ─── IMPORT / EXPORT CSV CLIENTI ─────────────────────────────
function exportClienti(){
  window.location.href = '/api/clienti/export';
}

function importClienti(input){
  var file = input.files[0];
  if(!file) return;
  var reader = new FileReader();
  reader.onload = function(e){
    var csv = e.target.result;
    fetch('/api/clienti/import',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({csv_content: csv})
    }).then(function(r){return r.json();}).then(function(res){
      input.value = '';  // reset input file
      if(!res.ok){ showMsg('cl-msg','❌ '+res.msg,'err'); return; }
      var msg = '✅ Importati: '+res.aggiunti;
      if(res.duplicati) msg += ' · Duplicati saltati: '+res.duplicati;
      if(res.errori && res.errori.length) msg += ' · ⚠️ '+res.errori.length+' righe con errori';
      showMsg('cl-msg', msg, 'ok');
      if(res.aggiunti > 0){ _clienti=null; loadClienti(); }
      // Mostra eventuali errori di riga in console
      if(res.errori && res.errori.length) console.warn('[Import CSV]', res.errori);
    }).catch(function(e){ showMsg('cl-msg','❌ '+e.message,'err'); });
  };
  reader.readAsText(file, 'UTF-8');
}

// ═══════════════════════════════════════════════
// CRM & MARKETING — Sotto-tab
// ═══════════════════════════════════════════════
var _crmSubActive = 'clienti';

function switchCrmTab(el, tab) {
  document.querySelectorAll('.crm-subtab').forEach(function(t){t.classList.remove('active');});
  if(el) el.classList.add('active');
  document.querySelectorAll('.crm-sub').forEach(function(p){p.style.display='none';});
  var sub = document.getElementById('crm-' + tab);
  if(sub) sub.style.display = '';
  _crmSubActive = tab;
  if(tab === 'clienti' && !_clienti) loadClienti();
  if(tab === 'pipeline') loadPipelineData();
  if(tab === 'campagne') renderCampagne();
  if(tab === 'social') renderSocial();
  if(tab === 'whatsapp') renderWhatsappSub();
  if(tab === 'prospect') loadProspect();
  if(tab === 'calendario') renderCalendario();
}

function renderPipeline() {
  loadPipelineData();
}

var _brevo_campagne = null;
var _brevo_liste = null;
var _brevo_template = null;
var _brevo_camp_names = {};

function _htmlAzioniLancio() {
  return '<div class="box" style="margin-bottom:1rem;border:1px solid rgba(246,173,85,.25)">'
    +'<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.8rem">'
    +'<div><div style="font-size:.9rem;font-weight:700;color:#F6AD55;margin-bottom:.25rem">⭐ Offerta Early Adopter</div>'
    +'<div style="font-size:.78rem;color:rgba(255,255,255,.5)">Invia email personalizzata ai Tester — 50% sconto per 3 mesi (scade 1° set 2026)</div></div>'
    +'<button id="btn-early-adopter" onclick="inviaEarlyAdopter()" style="background:#F6AD55;border:none;border-radius:6px;color:#0a0f1e;padding:.5rem 1.2rem;font-size:.85rem;font-weight:700;cursor:pointer;white-space:nowrap">📩 Invia a Tester ora</button>'
    +'</div></div>'
    +'<div class="box" style="margin-bottom:1rem;border:1px solid rgba(96,165,250,.25)">'
    +'<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.8rem">'
    +'<div><div style="font-size:.9rem;font-weight:700;color:#60a5fa;margin-bottom:.25rem">🚀 Lancio — Importa Prospect in Brevo</div>'
    +'<div style="font-size:.78rem;color:rgba(255,255,255,.5)">Crea lista Brevo e importa i 2.435 prospect — operazione sicura, aggiorna contatti esistenti</div></div>'
    +'<button id="btn-import-prospect" onclick="importaProspectBrevo()" style="background:#2C5282;border:none;border-radius:6px;color:#60a5fa;padding:.5rem 1.2rem;font-size:.85rem;font-weight:700;cursor:pointer;white-space:nowrap">⬆ Importa in Brevo</button>'
    +'</div></div>'
    +'<div class="box" style="margin-bottom:1rem;border:1px solid rgba(104,211,145,.25)">'
    +'<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.8rem">'
    +'<div><div style="font-size:.9rem;font-weight:700;color:#68D391;margin-bottom:.25rem">📧 Campagna Lancio — Email ai 2.435 Prospect</div>'
    +'<div style="font-size:.78rem;color:rgba(255,255,255,.5)">Crea la campagna Brevo con il template email di lancio — salvata come bozza, revisiona prima di inviare</div></div>'
    +'<button onclick="mostraLancioCampagna()" style="background:rgba(104,211,145,.15);border:1px solid rgba(104,211,145,.4);border-radius:6px;color:#68D391;padding:.5rem 1.2rem;font-size:.85rem;font-weight:700;cursor:pointer;white-space:nowrap">📧 Crea Campagna Lancio</button>'
    +'</div></div>';
}

function renderCampagne() {
  var el = document.getElementById('campagne-content');
  // I bottoni azione sono sempre visibili, indipendentemente da Brevo
  el.innerHTML = _htmlAzioniLancio()
    +'<div id="brevo-campagne-table"><div style="opacity:.5;padding:1.5rem;text-align:center">Caricamento campagne Brevo...</div></div>';
  fetch('/api/brevo/campagne').then(function(r){return r.json();}).then(function(d){
    var tbl = document.getElementById('brevo-campagne-table');
    if(!tbl) return;
    if(!d.ok){
      tbl.innerHTML = '<div class="box">'
        +'<h3 style="color:#F6AD55;margin-bottom:1rem">📧 Campagne Email — Brevo</h3>'
        +'<div style="background:rgba(252,129,129,.08);border:1px solid rgba(252,129,129,.3);border-radius:8px;padding:.8rem 1rem;margin-bottom:1rem;font-size:.85rem">'
        +'⚠️ ' + (d.msg || 'Brevo non configurato')
        +'</div>'
        +'<div style="opacity:.65;font-size:.85rem;line-height:2">'
        +'• Invio newsletter segmentate BASIC / PRO / VALUE<br>'
        +'• Avanzamento automatico dei prospect che aprono le email<br>'
        +'• Tracciamento aperture, click e conversioni'
        +'</div></div>'
        +'<div class="box"><h3 style="color:#68D391;margin-bottom:.8rem">✅ Email Report Automatiche — attive</h3>'
        +'<div style="font-size:.84rem;line-height:1.9;opacity:.75">'
        +'<strong>📈 Azioni:</strong> ogni notte alle 23:00 — lun/ven<br>'
        +'<strong>📦 ETF + Fondi:</strong> ogni notte alle 23:30 — lun / mer / ven<br>'
        +'<strong>Destinatari:</strong> automatici in base al piano abbonamento'
        +'</div></div>';
      return;
    }
    _brevo_campagne = d.campagne || [];
    tbl.innerHTML = '';
    renderCampagneTable(_brevo_campagne);
  }).catch(function(e){
    var tbl = document.getElementById('brevo-campagne-table');
    if(tbl) tbl.innerHTML = '<div class="box"><p style="color:#ef4444">Errore caricamento: '+e+'</p></div>';
  });
}

function inviaEarlyAdopter() {
  var btn = document.getElementById('btn-early-adopter');
  if(btn){ btn.disabled = true; btn.textContent = '⏳ Invio in corso...'; }
  fetch('/api/marketing/early-adopter', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'})
    .then(function(r){ return r.json(); })
    .then(function(d){
      if(btn){ btn.disabled = false; btn.textContent = '📩 Invia a Tester ora'; }
      if(d.ok){
        var righe = (d.dettaglio||[]).map(function(r){
          return '<li style="margin:.2rem 0;font-size:.82rem;color:'+(r.ok?'#68D391':'#ef4444')+'">'
            +(r.ok ? '✅' : '❌')+' '+r.email+(r.ok?' — '+r.piani+' piani':' — '+(r.msg||'errore'))+'</li>';
        }).join('');
        alert('✅ Inviate: '+d.inviati+' / '+d.totale+'\n\nDettaglio:\n'
          +(d.dettaglio||[]).map(function(r){ return (r.ok?'✅':'❌')+' '+r.email; }).join('\n'));
      } else {
        alert('❌ Errore: '+(d.msg||'sconosciuto'));
      }
    })
    .catch(function(e){
      if(btn){ btn.disabled = false; btn.textContent = '📩 Invia a Tester ora'; }
      alert('Errore di rete: '+e);
    });
}

function importaProspectBrevo() {
  var btn = document.getElementById('btn-import-prospect');
  if(btn){ btn.disabled = true; btn.textContent = '⏳ Importazione in corso...'; }
  fetch('/api/brevo/import-prospect', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'})
    .then(function(r){ return r.json(); })
    .then(function(d){
      if(btn){ btn.disabled = false; btn.textContent = '⬆ Importa in Brevo'; }
      if(d.ok){
        alert('✅ Import avviato!\n\n'
          +'Prospect importati: ' + d.totale + '\n'
          +'Lista Brevo: "' + d.lista_nome + '" (ID ' + d.lista_id + ')\n'
          +'Process ID: ' + (d.process_id || '—') + '\n\n'
          +'Brevo elabora in background — controlla la lista su app.brevo.com tra qualche minuto.\n'
          +'Poi usa quella lista come destinatari nella tua campagna di lancio.');
      } else {
        alert('❌ Errore: ' + (d.msg || 'sconosciuto') + (d.detail ? '\n\n' + JSON.stringify(d.detail) : ''));
      }
    })
    .catch(function(e){
      if(btn){ btn.disabled = false; btn.textContent = '⬆ Importa in Brevo'; }
      alert('Errore di rete: ' + e);
    });
}

var _lancioHtmlCache = null;

function mostraLancioCampagna() {
  var old = document.getElementById('brevo-modal'); if(old) old.remove();
  var backdrop = document.createElement('div');
  backdrop.id = 'brevo-modal';
  backdrop.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:1rem';
  var card = document.createElement('div');
  card.style.cssText = 'background:#1e293b;border:1px solid rgba(255,255,255,.1);border-radius:12px;width:100%;max-width:520px;max-height:85vh;display:flex;flex-direction:column';
  card.innerHTML = '<div style="padding:1.5rem;text-align:center;opacity:.5;flex:1">Caricamento...</div>'
    +'<div style="padding:.75rem 1.5rem;border-top:1px solid rgba(255,255,255,.08)">'
    +'<button id="lancio-chiudi-tmp" style="width:100%;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:rgba(255,255,255,.6);padding:.6rem;font-size:.85rem;cursor:pointer">Chiudi</button></div>';
  backdrop.appendChild(card);
  document.body.appendChild(backdrop);
  document.getElementById('lancio-chiudi-tmp').addEventListener('click', brevoChiudiModal);

  var loadH = fetch('/api/brevo/html-lancio').then(function(r){return r.json();});
  var loadL = _brevo_liste ? Promise.resolve(_brevo_liste) :
    fetch('/api/brevo/liste').then(function(r){return r.json();}).then(function(d){ _brevo_liste = d.liste||[]; return _brevo_liste; });

  Promise.all([loadH, loadL]).then(function(res){
    _lancioHtmlCache = res[0].html || '';
    var liste = Array.isArray(res[1]) ? res[1] : [];
    var listeHtml = '';
    liste.forEach(function(l){
      var presel = (l.name||'').indexOf('Prospect Lancio') !== -1 ? ' checked' : '';
      listeHtml += '<label style="display:flex;align-items:center;gap:.4rem;font-size:.82rem;margin-bottom:.3rem;cursor:pointer">'
        +'<input type="checkbox" class="lancio-lista" value="'+l.id+'"'+presel+'> '
        +(l.name||'ID '+l.id)
        +' <span style="color:rgba(255,255,255,.3);font-size:.72rem">('+( l.uniqueSubscribers||l.totalSubscribers||0)+' contatti)</span></label>';
    });
    card.innerHTML = '<div style="padding:1.5rem;overflow-y:auto;flex:1 1 auto;min-height:0">'
      +'<h3 style="color:#68D391;margin-bottom:1.2rem;font-size:1rem">📧 Campagna Lancio Prospect</h3>'
      +'<div style="display:flex;flex-direction:column;gap:.75rem">'
      +'<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.25rem">Nome Campagna</label>'
      +'<input id="lancio-nome" value="Lancio Fuerte — 2.435 Prospect" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem .75rem;font-size:.85rem"></div>'
      +'<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.25rem">Oggetto email</label>'
      +'<input id="lancio-oggetto" value="Ogni notte 10.086 asset analizzati per te — prova 7 giorni gratis" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem .75rem;font-size:.85rem"></div>'
      +'<div style="display:grid;grid-template-columns:1fr 1fr;gap:.5rem"><div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.25rem">Email mittente <span style="color:#ef4444">★ verificata su Brevo</span></label>'
      +'<input id="lancio-sender-email" value="marketing@fuerteventurecapital.com" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem .75rem;font-size:.85rem"></div>'
      +'<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.25rem">Nome mittente</label>'
      +'<input id="lancio-sender-name" value="Fuerte Venture Capital" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem .75rem;font-size:.85rem"></div></div>'
      +'<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.4rem">Liste destinatari</label>'
      +(listeHtml || '<div style="opacity:.5;font-size:.8rem">Nessuna lista trovata su Brevo</div>')+'</div>'
      +'<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.25rem">Anteprima email</label>'
      +'<div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:6px;padding:.6rem 1rem;font-size:.8rem;color:rgba(255,255,255,.5)">'
      +'HTML pronto — '+(_lancioHtmlCache.length)+' caratteri. '
      +'<a href="#" id="lancio-anteprima-link" style="color:#F6AD55;text-decoration:none">Visualizza anteprima →</a>'
      +'</div></div>'
      +'<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.25rem">Data invio schedulato (opzionale)</label>'
      +'<input id="lancio-data" type="datetime-local" style="background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem .75rem;font-size:.85rem"></div>'
      +'<div style="background:rgba(246,173,85,.06);border:1px solid rgba(246,173,85,.2);border-radius:6px;padding:.7rem 1rem;font-size:.78rem;color:rgba(255,255,255,.5)">'
      +'⚠️ La campagna viene creata come <strong style="color:#F6AD55">bozza</strong> su Brevo. Rivedi su app.brevo.com prima di inviare.</div>'
      +'</div></div>'
      +'<div style="padding:.75rem 1.5rem;flex:0 0 auto;border-top:1px solid rgba(255,255,255,.08)">'
      +'<div id="lancio-error" style="display:none;color:#ef4444;font-size:.8rem;padding:.4rem .6rem;background:rgba(239,68,68,.08);border-radius:6px;margin-bottom:.5rem"></div>'
      +'<button id="lancio-crea-btn" style="width:100%;background:rgba(104,211,145,.15);border:1px solid rgba(104,211,145,.4);border-radius:8px;color:#68D391;padding:.7rem;font-size:.9rem;font-weight:700;cursor:pointer;margin-bottom:.5rem">📧 Crea Bozza Campagna</button>'
      +'<button id="lancio-chiudi-btn" style="width:100%;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:rgba(255,255,255,.6);padding:.6rem;font-size:.85rem;cursor:pointer">Chiudi</button>'
      +'</div>';
    document.getElementById('lancio-crea-btn').addEventListener('click', confermaLancioCampagna);
    document.getElementById('lancio-chiudi-btn').addEventListener('click', brevoChiudiModal);
    var ant = document.getElementById('lancio-anteprima-link');
    if(ant) ant.addEventListener('click', function(e){ e.preventDefault(); lancioMostraAnteprima(); });
  }).catch(function(e){
    card.innerHTML = '<div style="padding:1.5rem"><p style="color:#ef4444">Errore caricamento: '+e+'</p></div>'
      +'<div style="padding:.75rem 1.5rem;border-top:1px solid rgba(255,255,255,.08)">'
      +'<button id="lancio-chiudi-err" style="width:100%;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:rgba(255,255,255,.6);padding:.6rem;font-size:.85rem;cursor:pointer">Chiudi</button></div>';
    document.getElementById('lancio-chiudi-err').addEventListener('click', brevoChiudiModal);
  });
}

function lancioMostraAnteprima() {
  var w = window.open('','_blank','width=700,height=600');
  if(w && _lancioHtmlCache){ w.document.write(_lancioHtmlCache); w.document.close(); }
}

function confermaLancioCampagna() {
  var errEl = document.getElementById('lancio-error');
  function _err(msg){ if(errEl){ errEl.textContent=msg; errEl.style.display='block'; } }
  if(errEl) errEl.style.display='none';
  var nome = (document.getElementById('lancio-nome')||{value:''}).value.trim();
  var oggetto = (document.getElementById('lancio-oggetto')||{value:''}).value.trim();
  var data_inv = (document.getElementById('lancio-data')||{value:''}).value;
  var checkboxes = document.querySelectorAll('.lancio-lista:checked');
  var lista_ids = Array.from(checkboxes).map(function(cb){return parseInt(cb.value);});
  if(!nome){ _err('Inserisci il nome della campagna'); return; }
  if(!oggetto){ _err("Inserisci l'oggetto email"); return; }
  if(lista_ids.length === 0){ _err('Seleziona almeno una lista destinatari'); return; }
  if(!_lancioHtmlCache){ _err('HTML email non caricato — riapri il modal'); return; }
  var sender_email = (document.getElementById('lancio-sender-email')||{value:''}).value.trim();
  var sender_name  = (document.getElementById('lancio-sender-name')||{value:''}).value.trim();
  if(!sender_email){ _err('Inserisci la email mittente verificata su Brevo'); return; }
  var btn = document.getElementById('lancio-crea-btn');
  if(btn){ btn.disabled=true; btn.textContent='⏳ Creazione in corso...'; }
  var payload = {nome:nome, oggetto:oggetto, html_content:_lancioHtmlCache, lista_ids:lista_ids,
    sender_email:sender_email, sender_name:sender_name};
  if(data_inv) payload.data_invio_schedulato = new Date(data_inv).toISOString();
  fetch('/api/brevo/campagne',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
    .then(function(r){return r.json();}).then(function(d){
      if(btn){ btn.disabled=false; btn.textContent='📧 Crea Bozza Campagna'; }
      if(d.ok){
        brevoChiudiModal();
        _brevo_campagne = null;
        renderCampagne();
        alert('Bozza creata su Brevo (ID '+d.id+')!\n\nVai su app.brevo.com per revisionarla e inviarla.');
      } else {
        _err('Errore Brevo: '+(d.msg||'sconosciuto')+' '+(d.detail?JSON.stringify(d.detail):''));
      }
    }).catch(function(e){ if(btn){btn.disabled=false;btn.textContent='📧 Crea Bozza Campagna';} _err('Errore di rete: '+e); });
}

function renderCampagneTable(campagne, filtro) {
  filtro = filtro || 'tutti';
  var STATO_COLOR = {sent:'#68D391',draft:'#9ca3af',queued:'#60a5fa',suspended:'#F6AD55'};
  var lista = filtro === 'tutti' ? campagne : campagne.filter(function(c){return c.status===filtro;});
  var tbl = document.getElementById('brevo-campagne-table');
  var html = '<div class="box">'
    +'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;flex-wrap:wrap;gap:.5rem">'
    +'<h3 style="color:#F6AD55">📧 Campagne Email — Brevo ('+campagne.length+')</h3>'
    +'<div style="display:flex;gap:.5rem;align-items:center">'
    +'<select id="brevo-filtro-stato" onchange="renderCampagneTable(_brevo_campagne,this.value)" style="background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.35rem .6rem;font-size:.8rem">'
    +'<option value="tutti">Tutti</option>'
    +'<option value="sent">Inviate</option>'
    +'<option value="draft">Bozze</option>'
    +'<option value="queued">Schedulate</option>'
    +'<option value="suspended">Sospese</option>'
    +'</select>'
    +'<button onclick="renderCampagne()" style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.35rem .7rem;font-size:.8rem;cursor:pointer">↺ Aggiorna</button>'
    +'<button onclick="mostraNuovaCampagna()" style="background:#2C5282;border:none;border-radius:6px;color:#F6AD55;padding:.35rem .8rem;font-size:.8rem;font-weight:700;cursor:pointer">+ Nuova Campagna</button>'
    +'</div></div>';

  if(lista.length === 0){
    html += '<div style="opacity:.5;padding:1.5rem;text-align:center;font-size:.85rem">Nessuna campagna trovata</div></div>';
  } else {
    html += '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:.82rem">'
      +'<thead><tr style="border-bottom:1px solid rgba(255,255,255,.1);color:rgba(255,255,255,.4);font-size:.75rem;text-transform:uppercase;letter-spacing:.05em">'
      +'<th style="padding:.5rem .75rem;text-align:left">Nome Campagna</th>'
      +'<th style="padding:.5rem .75rem;text-align:left">Oggetto</th>'
      +'<th style="padding:.5rem .75rem;text-align:center">Stato</th>'
      +'<th style="padding:.5rem .75rem;text-align:center">Data</th>'
      +'<th style="padding:.5rem .75rem;text-align:right">Inviati</th>'
      +'<th style="padding:.5rem .75rem;text-align:right">Aperture</th>'
      +'<th style="padding:.5rem .75rem;text-align:right">Click</th>'
      +'<th style="padding:.5rem .75rem;text-align:center">Azioni</th>'
      +'</tr></thead><tbody>';
    _brevo_camp_names = {};
    lista.forEach(function(c){
      _brevo_camp_names[c.id] = c.name;
      var stats = (c.statistics && c.statistics.globalStats) || {};
      var sent = stats.sent || 0;
      var views = stats.uniqueViews || 0;
      var clicks = stats.uniqueClicks || 0;
      var aperturePct = sent > 0 ? (views/sent*100).toFixed(1)+'%' : '—';
      var clickPct = sent > 0 ? (clicks/sent*100).toFixed(1)+'%' : '—';
      var dataStr = '—';
      if(c.sentDate || c.scheduledAt){
        var dt = new Date(c.sentDate || c.scheduledAt);
        dataStr = dt.toLocaleDateString('it-IT',{day:'2-digit',month:'2-digit',year:'2-digit'});
      }
      var statoBadge = '<span style="background:'+(STATO_COLOR[c.status]||'#9ca3af')+'22;color:'+(STATO_COLOR[c.status]||'#9ca3af')+';border:1px solid '+(STATO_COLOR[c.status]||'#9ca3af')+'44;border-radius:12px;padding:.15rem .55rem;font-size:.72rem;font-weight:600">'+c.status+'</span>';
      html += '<tr style="border-bottom:1px solid rgba(255,255,255,.05)">'
        +'<td style="padding:.55rem .75rem;font-weight:600;color:#e0e0e0;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="'+c.name+'">'+c.name+'</td>'
        +'<td style="padding:.55rem .75rem;color:rgba(255,255,255,.55);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="'+(c.subject||'')+'">'+( c.subject||'—')+'</td>'
        +'<td style="padding:.55rem .75rem;text-align:center">'+statoBadge+'</td>'
        +'<td style="padding:.55rem .75rem;text-align:center;color:rgba(255,255,255,.45);font-size:.75rem">'+dataStr+'</td>'
        +'<td style="padding:.55rem .75rem;text-align:right;color:rgba(255,255,255,.6)">'+sent.toLocaleString()+'</td>'
        +'<td style="padding:.55rem .75rem;text-align:right;color:#60a5fa;font-weight:600">'+aperturePct+'</td>'
        +'<td style="padding:.55rem .75rem;text-align:right;color:#68D391;font-weight:600">'+clickPct+'</td>'
        +'<td style="padding:.55rem .75rem;text-align:center">'
        +'<div style="display:flex;gap:.3rem;justify-content:center;align-items:center">';
      if(c.status === 'draft'){
        html += '<button onclick="brevoInviaCampagna('+c.id+')" style="background:#2C5282;border:none;border-radius:5px;color:#F6AD55;padding:.2rem .5rem;font-size:.72rem;cursor:pointer">▶ Invia</button>';
      }
      if(c.status === 'sent'){
        html += '<button onclick="brevoAvanzaProspect('+c.id+',this)" style="background:#276749;border:none;border-radius:5px;color:#68D391;padding:.2rem .5rem;font-size:.72rem;cursor:pointer" title="Avanza prospect che hanno aperto">▲ LinkedIn</button>';
        html += '<button onclick="brevoNonAperti('+c.id+')" style="background:rgba(246,173,85,.15);border:1px solid rgba(246,173,85,.3);border-radius:5px;color:#F6AD55;padding:.2rem .5rem;font-size:.72rem;cursor:pointer" title="Chi non ha aperto">✉ Non aperti</button>';
      }
      html += '<button onclick="brevoRisultati('+c.id+')" style="background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:5px;color:rgba(255,255,255,.6);padding:.2rem .4rem;font-size:.72rem;cursor:pointer" title="Statistiche dettagliate">👁</button>';
      html += '</div></td></tr>';
    });
    html += '</tbody></table></div></div>';
  }
  html += '<div id="brevo-modal-container"></div>';
  if(tbl) { tbl.innerHTML = html; } else { document.getElementById('campagne-content').innerHTML = _htmlAzioniLancio() + html; }
  if(filtro !== 'tutti'){
    var sel = document.getElementById('brevo-filtro-stato');
    if(sel) sel.value = filtro;
  }
}

function brevoInviaCampagna(id) {
  var nome = _brevo_camp_names[id] || 'ID '+id;
  if(!confirm('Inviare ora la campagna "'+nome+'" a tutti i destinatari?')) return;
  fetch('/api/brevo/campagne/'+id+'/invia',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
    .then(function(r){return r.json();}).then(function(d){
      if(d.ok){ alert('✅ Campagna inviata con successo'); renderCampagne(); }
      else alert('❌ Errore: '+(d.msg||'sconosciuto'));
    });
}

function brevoRisultati(id) {
  var cont = document.getElementById('brevo-modal-container');
  if(!cont) return;
  cont.innerHTML = _brevoModalOverlay('<div style="opacity:.5;text-align:center;padding:2rem">Caricamento...</div>','brevoChiudiModal()');
  fetch('/api/brevo/campagne/'+id+'/risultati').then(function(r){return r.json();}).then(function(d){
    if(!d.ok){ cont.innerHTML = ''; alert('Errore: '+d.msg); return; }
    var html = '<h3 style="color:#F6AD55;margin-bottom:.3rem;font-size:1rem">'+d.nome+'</h3>'
      +'<p style="color:rgba(255,255,255,.4);font-size:.8rem;margin-bottom:1.2rem">'+d.oggetto+'</p>'
      +'<div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem;margin-bottom:1rem">'
      +_brevoKpi('Inviati',d.inviati,'#e0e0e0')
      +_brevoKpi('Consegnati',d.consegnati,'#e0e0e0')
      +_brevoKpi('Aperture uniche',d.tasso_apertura_pct+'%','#60a5fa')
      +_brevoKpi('Click unici',d.tasso_click_pct+'%','#68D391')
      +_brevoKpi('Rimbalzi',d.rimbalzi,'#F6AD55')
      +_brevoKpi('Disiscritti',d.disiscritti,'#ef4444')
      +'</div>';
    if(d.data_invio){
      html += '<p style="font-size:.75rem;color:rgba(255,255,255,.3);text-align:center">Inviata il '+new Date(d.data_invio).toLocaleString('it-IT')+'</p>';
    }
    cont.innerHTML = _brevoModalOverlay(html,'brevoChiudiModal()');
  });
}

function brevoAvanzaProspect(id, btn) {
  var nome = _brevo_camp_names[id] || 'ID '+id;
  if(!confirm('Avanzare a PROSPECT LINKEDIN i lead che hanno aperto "'+nome+'"?\n(Da Contattare → Contattato, Contattato → Interessato)')) return;
  btn.disabled = true; btn.textContent = '...';
  fetch('/api/brevo/campagne/'+id+'/avanza-prospect',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
    .then(function(r){return r.json();}).then(function(d){
      btn.disabled = false; btn.textContent = '▲ LinkedIn';
      if(!d.ok){ alert('Errore: '+(d.msg||'sconosciuto')); return; }
      var avanzati   = d.avanzati||[];
      var gia        = d.gia_avanzati||[];
      var non_trovati= d.non_trovati||[];
      // header + export LinkedIn Ads
      var html = '<h3 style="color:#F6AD55;margin-bottom:.3rem;font-size:1rem">Avanzamento Prospect LinkedIn</h3>'
        +'<p style="color:rgba(255,255,255,.4);font-size:.78rem;margin-bottom:1rem">'+nome+'</p>';
      // sezione avanzati
      html += '<div style="margin-bottom:1rem">'
        +'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.5rem">'
        +'<div style="display:flex;align-items:center;gap:.4rem">'
        +'<span style="width:8px;height:8px;border-radius:50%;background:#68D391;display:inline-block"></span>'
        +'<span style="font-size:.85rem;font-weight:600;color:#68D391">Avanzati a PROSPECT ('+avanzati.length+')</span>'
        +'</div>';
      if(avanzati.length > 0){
        html += '<button onclick="brevoEsportaLinkedIn()" style="display:flex;align-items:center;gap:.3rem;background:rgba(10,102,194,.15);border:1px solid rgba(10,102,194,.4);border-radius:5px;color:#60a5fa;padding:.2rem .55rem;font-size:.72rem;cursor:pointer" title="Esporta per LinkedIn Ads (Matched Audiences)">'
          +'<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zM9 17H6.5v-7H9v7zm-1.3-8a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm9.3 8h-2.5v-3.5c0-.8-.7-1.5-1.5-1.5s-1.5.7-1.5 1.5V17H9v-7h2.5v1a3 3 0 015.5 1.7V17z"/></svg>'
          +' LinkedIn Ads</button>';
      }
      html += '</div>';
      if(avanzati.length > 0){
        // salva per export
        html += '<script>window._liAds='+JSON.stringify(avanzati)+';<\/script>';
        html += '<div style="max-height:180px;overflow-y:auto;border:1px solid rgba(255,255,255,.08);border-radius:6px">';
        avanzati.forEach(function(a){
          var liBtn = a.linkedin_url
            ? '<a href="'+a.linkedin_url+'" target="_blank" style="color:#0A66C2;display:inline-flex;align-items:center;gap:2px;text-decoration:none;flex-shrink:0" title="Apri profilo LinkedIn"><svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zM9 17H6.5v-7H9v7zm-1.3-8a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm9.3 8h-2.5v-3.5c0-.8-.7-1.5-1.5-1.5s-1.5.7-1.5 1.5V17H9v-7h2.5v1a3 3 0 015.5 1.7V17z"/></svg></a>'
            : '<a href="https://www.linkedin.com/search/results/people/?keywords='+encodeURIComponent(a.nome)+'" target="_blank" style="color:rgba(255,255,255,.25);display:inline-flex;align-items:center;flex-shrink:0" title="Cerca su LinkedIn"><svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zM9 17H6.5v-7H9v7zm-1.3-8a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm9.3 8h-2.5v-3.5c0-.8-.7-1.5-1.5-1.5s-1.5.7-1.5 1.5V17H9v-7h2.5v1a3 3 0 015.5 1.7V17z"/></svg></a>';
          html += '<div style="display:flex;align-items:center;gap:.4rem;font-size:.79rem;padding:.3rem .5rem;border-bottom:1px solid rgba(255,255,255,.05)">'
            +'<span style="flex:1;min-width:0;color:#e0e0e0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+a.nome+'</span>'
            +'<span style="color:rgba(255,255,255,.4);font-size:.72rem;flex-shrink:0">'+a.email+'</span>'
            +'<span style="color:#F6AD55;font-size:.72rem;flex-shrink:0">'+a.da+' → '+a.a+'</span>'
            +liBtn+'</div>';
        });
        html += '</div>';
      } else { html += '<p style="font-size:.8rem;color:rgba(255,255,255,.35);padding:.25rem .5rem">Nessuno</p>'; }
      html += '</div>';
      // già avanzati
      if(gia.length > 0){
        html += '<div style="margin-bottom:1rem"><div style="display:flex;align-items:center;gap:.4rem;margin-bottom:.4rem">'
          +'<span style="width:8px;height:8px;border-radius:50%;background:#60a5fa;display:inline-block"></span>'
          +'<span style="font-size:.85rem;font-weight:600;color:#60a5fa">Già oltre LEAD ('+gia.length+')</span></div>';
        gia.forEach(function(a){
          html += '<div style="font-size:.78rem;color:rgba(255,255,255,.4);padding:.2rem .5rem">'+a.nome+' <span style="color:rgba(255,255,255,.25)">→ '+a.stato+'</span></div>';
        });
        html += '</div>';
      }
      // non trovati in CRM
      if(non_trovati.length > 0){
        html += '<div><div style="display:flex;align-items:center;gap:.4rem;margin-bottom:.4rem">'
          +'<span style="width:8px;height:8px;border-radius:50%;background:rgba(255,255,255,.25);display:inline-block"></span>'
          +'<span style="font-size:.85rem;font-weight:600;color:rgba(255,255,255,.4)">Non presenti in CRM ('+non_trovati.length+')</span></div>';
        non_trovati.forEach(function(e){
          html += '<div style="font-size:.72rem;color:rgba(255,255,255,.3);padding:.15rem .5rem">'+e+'</div>';
        });
        html += '</div>';
      }
      _prospect = null;
      var cont = document.getElementById('brevo-modal-container');
      if(cont) cont.innerHTML = _brevoModalOverlay(html,'brevoChiudiModal()');
    }).catch(function(e){ btn.disabled=false; btn.textContent='▲ LinkedIn'; alert('Errore: '+e); });
}

function brevoEsportaLinkedIn() {
  var data = window._liAds || [];
  if(!data.length){ alert('Nessun dato da esportare'); return; }
  var bom = '﻿';
  var header = 'Email,Nome';
  var righe = data.map(function(c){ return c.email+',"'+c.nome.replace(/"/g,'""')+'"'; }).join('\n');
  var blob = new Blob([bom+header+'\n'+righe], {type:'text/csv;charset=utf-8'});
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url; a.download = 'prospect-linkedin-ads.csv';
  a.click(); URL.revokeObjectURL(url);
}

function brevoNonAperti(id) {
  var nome = _brevo_camp_names[id] || 'ID '+id;
  var cont = document.getElementById('brevo-modal-container');
  if(!cont) return;
  cont.innerHTML = _brevoModalOverlay('<div style="opacity:.5;text-align:center;padding:2rem">Analisi in corso... (può richiedere qualche secondo)</div>','brevoChiudiModal()');
  fetch('/api/brevo/campagne/'+id+'/non-aperti').then(function(r){return r.json();}).then(function(d){
    if(!d.ok){ cont.innerHTML=''; alert('Errore: '+d.msg); return; }
    var html = '<h3 style="color:#F6AD55;margin-bottom:.3rem;font-size:1rem">Non Aperti</h3>'
      +'<p style="color:rgba(255,255,255,.4);font-size:.78rem;margin-bottom:1rem">'+nome+'</p>'
      +'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:.5rem;margin-bottom:1rem">'
      +'<div style="background:rgba(0,0,0,.3);border-radius:8px;padding:.6rem;text-align:center"><div style="font-size:1.2rem;font-weight:700;color:#e0e0e0">'+d.totale+'</div><div style="font-size:.72rem;color:rgba(255,255,255,.4)">Verificati</div></div>'
      +'<div style="background:rgba(104,211,145,.08);border-radius:8px;padding:.6rem;text-align:center"><div style="font-size:1.2rem;font-weight:700;color:#68D391">'+d.aperti+'</div><div style="font-size:.72rem;color:rgba(255,255,255,.4)">Hanno aperto</div></div>'
      +'<div style="background:rgba(246,173,85,.08);border-radius:8px;padding:.6rem;text-align:center"><div style="font-size:1.2rem;font-weight:700;color:#F6AD55">'+d.non_aperti+'</div><div style="font-size:.72rem;color:rgba(255,255,255,.4)">Non aperti</div></div>'
      +'</div>';
    if(d.contatti && d.contatti.length > 0){
      html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.4rem">'
        +'<span style="font-size:.78rem;color:rgba(255,255,255,.4)">Lista non aperti</span>'
        +'<button onclick="brevoEsportaNonAperti('+id+')" style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);border-radius:5px;color:#e0e0e0;padding:.2rem .55rem;font-size:.72rem;cursor:pointer">⬇ CSV</button>'
        +'</div>'
        +'<div style="max-height:220px;overflow-y:auto;border:1px solid rgba(255,255,255,.08);border-radius:6px">'
        +'<table style="width:100%;border-collapse:collapse;font-size:.78rem">'
        +'<thead><tr style="background:rgba(0,0,0,.3);color:rgba(255,255,255,.35);font-size:.7rem">'
        +'<th style="padding:.3rem .5rem;text-align:left">Nome</th>'
        +'<th style="padding:.3rem .5rem;text-align:left">Email</th>'
        +'<th style="padding:.3rem .5rem;text-align:left">Piano</th>'
        +'</tr></thead><tbody>';
      d.contatti.forEach(function(c){
        html += '<tr style="border-bottom:1px solid rgba(255,255,255,.05)">'
          +'<td style="padding:.3rem .5rem;color:#e0e0e0">'+c.nome+'</td>'
          +'<td style="padding:.3rem .5rem;color:rgba(255,255,255,.5)">'+c.email+'</td>'
          +'<td style="padding:.3rem .5rem;color:#F6AD55">'+c.piano+'</td>'
          +'</tr>';
      });
      html += '</tbody></table></div>';
      window._brevoNonApertiData = d.contatti;
      window._brevoNonApertiNome = nome;
    }
    cont.innerHTML = _brevoModalOverlay(html,'brevoChiudiModal()');
  });
}

function brevoEsportaNonAperti(id) {
  var lista = window._brevoNonApertiData || [];
  var bom = '﻿';
  var header = 'Nome,Email,Piano,Stato';
  var righe = lista.map(function(c){ return '"'+c.nome+'",'+c.email+',"'+c.piano+'","'+c.stato+'"'; }).join('\n');
  var blob = new Blob([bom+header+'\n'+righe],{type:'text/csv;charset=utf-8'});
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a'); a.href=url; a.download='non-aperti-campagna-'+id+'.csv'; a.click(); URL.revokeObjectURL(url);
}

function _brevoKpi(label, value, color) {
  return '<div style="background:rgba(0,0,0,.3);border-radius:8px;padding:.75rem;text-align:center">'
    +'<div style="font-size:1.3rem;font-weight:700;color:'+color+'">'+value+'</div>'
    +'<div style="font-size:.72rem;color:rgba(255,255,255,.4);margin-top:.15rem">'+label+'</div>'
    +'</div>';
}

function _brevoModalOverlay(content, onclose, footer) {
  var ftHtml = (footer !== undefined) ? footer
    : '<button onclick="'+onclose+'" style="width:100%;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:8px;color:rgba(255,255,255,.6);padding:.6rem;font-size:.85rem;cursor:pointer">Chiudi</button>';
  return '<div id="brevo-modal" style="position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:1rem">'
    +'<div style="background:#1e293b;border:1px solid rgba(255,255,255,.1);border-radius:12px;width:100%;max-width:520px;max-height:85vh;display:flex;flex-direction:column;position:relative">'
    +'<button onclick="'+onclose+'" style="position:absolute;top:.75rem;right:.75rem;background:none;border:none;color:rgba(255,255,255,.4);font-size:1.1rem;cursor:pointer;z-index:1">✕</button>'
    +'<div style="padding:1.5rem;overflow-y:auto;flex:1 1 auto;min-height:0">'
    +content
    +'</div>'
    +'<div style="padding:.75rem 1.5rem;flex:0 0 auto;border-top:1px solid rgba(255,255,255,.08)">'
    +ftHtml
    +'</div>'
    +'</div></div>';
}
function brevoChiudiModal() {
  var m = document.getElementById('brevo-modal'); if(m) m.remove();
  var cont = document.getElementById('brevo-modal-container'); if(cont) cont.innerHTML='';
}

// ─── Nuova Campagna ───────────────────────────────────────────────────────────
function mostraNuovaCampagna() {
  var cont = document.getElementById('brevo-modal-container');
  if(!cont) { cont = document.createElement('div'); cont.id='brevo-modal-container'; document.getElementById('campagne-content').appendChild(cont); }
  // Carica template e liste in parallelo
  var loadT = _brevo_template ? Promise.resolve(_brevo_template) :
    fetch('/api/brevo/template').then(function(r){return r.json();}).then(function(d){ _brevo_template = d.template||[]; return _brevo_template; });
  var loadL = _brevo_liste ? Promise.resolve(_brevo_liste) :
    fetch('/api/brevo/liste').then(function(r){return r.json();}).then(function(d){ _brevo_liste = d.liste||[]; return _brevo_liste; });
  cont.innerHTML = _brevoModalOverlay('<div style="opacity:.5;text-align:center;padding:2rem">Caricamento template e liste...</div>','brevoChiudiModal()');
  Promise.all([loadT, loadL]).then(function(results){
    var template = results[0];
    var liste = results[1];
    var html = '<h3 style="color:#F6AD55;margin-bottom:1.2rem;font-size:1rem">+ Nuova Campagna</h3>'
      +'<div style="display:flex;flex-direction:column;gap:.75rem">'
      +'<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.25rem">Nome Campagna</label>'
      +'<input id="nc-nome" placeholder="es. Newsletter Luglio 2026 — Azioni" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem .75rem;font-size:.85rem"></div>'
      +'<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.25rem">Oggetto email</label>'
      +'<input id="nc-oggetto" placeholder="es. 📈 Report Azioni — Luglio 2026" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem .75rem;font-size:.85rem"></div>'
      +'<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.25rem">Template</label>'
      +'<select id="nc-template" style="width:100%;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem .75rem;font-size:.85rem">'
      +'<option value="">— scegli template —</option>';
    template.forEach(function(t){ html += '<option value="'+t.id+'">'+t.name+'</option>'; });
    html += '</select></div>';
    if(liste.length > 0){
      html += '<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.4rem">Liste destinatari</label>';
      liste.forEach(function(l){
        html += '<label style="display:flex;align-items:center;gap:.4rem;font-size:.82rem;margin-bottom:.25rem;cursor:pointer">'
          +'<input type="checkbox" class="nc-lista" value="'+l.id+'"> '+l.name
          +' <span style="color:rgba(255,255,255,.3);font-size:.72rem">('+( l.uniqueSubscribers||l.totalSubscribers||0)+' contatti)</span></label>';
      });
      html += '</div>';
    } else {
      html += '<div style="background:rgba(252,129,129,.08);border:1px solid rgba(252,129,129,.2);border-radius:6px;padding:.5rem .75rem;font-size:.78rem;color:rgba(255,255,255,.5)">Nessuna lista trovata su Brevo. Crea prima una lista sul pannello Brevo.</div>';
    }
    html += '<div><label style="font-size:.78rem;color:rgba(255,255,255,.5);display:block;margin-bottom:.25rem">Data invio schedulato (opzionale)</label>'
      +'<input id="nc-data" type="datetime-local" style="background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem .75rem;font-size:.85rem"></div>'
      +'<button onclick="confermaNuovaCampagna()" style="width:100%;background:#2C5282;border:none;border-radius:8px;color:#F6AD55;padding:.7rem;font-size:.9rem;font-weight:700;cursor:pointer;margin-top:.25rem">Crea Campagna</button>'
      +'</div>';
    cont.innerHTML = _brevoModalOverlay(html,'brevoChiudiModal()');
  }).catch(function(e){
    cont.innerHTML = _brevoModalOverlay('<p style="color:#ef4444">Errore: '+e+'</p>','brevoChiudiModal()');
  });
}

function confermaNuovaCampagna() {
  var nome = (document.getElementById('nc-nome')||{value:''}).value.trim();
  var oggetto = (document.getElementById('nc-oggetto')||{value:''}).value.trim();
  var template_id = (document.getElementById('nc-template')||{value:''}).value;
  var data_inv = (document.getElementById('nc-data')||{value:''}).value;
  var checkboxes = document.querySelectorAll('.nc-lista:checked');
  var lista_ids = Array.from(checkboxes).map(function(cb){return parseInt(cb.value);});
  if(!nome){ alert('Inserisci il nome della campagna'); return; }
  if(!oggetto){ alert('Inserisci l\'oggetto dell\'email'); return; }
  if(!template_id){ alert('Seleziona un template'); return; }
  if(lista_ids.length === 0){ alert('Seleziona almeno una lista destinatari'); return; }
  var payload = {nome:nome, oggetto:oggetto, template_id:parseInt(template_id), lista_ids:lista_ids};
  if(data_inv) payload.data_invio_schedulato = new Date(data_inv).toISOString();
  fetch('/api/brevo/campagne',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
    .then(function(r){return r.json();}).then(function(d){
      if(d.ok){
        brevoChiudiModal();
        alert('✅ Campagna creata con successo (ID '+d.id+')');
        _brevo_campagne = null;
        renderCampagne();
      } else {
        alert('❌ Errore: '+(d.msg||'sconosciuto'));
      }
    }).catch(function(e){ alert('Errore: '+e); });
}

function renderSocial() {
  var el = document.getElementById('social-content');
  el.innerHTML = '<div style="opacity:.5;padding:1rem;text-align:center">Caricamento...</div>';
  // Carica platforms + drafts + calendario in parallelo
  Promise.all([
    fetch('/api/social/platforms').then(function(r){return r.json();}),
    fetch('/api/social/status').then(function(r){return r.json();}),
    fetch('/api/social/calendario').then(function(r){return r.json();})
  ]).then(function(results){
    var platforms = results[0];
    var statusData = results[1];
    var calData    = results[2];
    var drafts   = (statusData.drafts  || []);
    var calendar = (calData.calendario || []);
    var pending  = drafts.filter(function(d){return d.status==='pending';});
    var recent   = drafts.filter(function(d){return d.status!=='pending';}).slice(0,8);
    var html = '';

    // ── Stato piattaforme ──────────────────────────────────────
    html += '<div class="box" style="margin-bottom:1rem">';
    html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.9rem;flex-wrap:wrap;gap:.5rem">';
    html += '<h3 style="color:#F6AD55;margin:0">📱 Stato Piattaforme</h3>';
    html += '<div style="display:flex;gap:.5rem">';
    html += '<button onclick="renderSocial()" style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.3rem .65rem;font-size:.8rem;cursor:pointer">↺ Aggiorna</button>';
    html += '<button onclick="socialGeneraDraft()" style="background:#2C5282;border:none;border-radius:6px;color:#F6AD55;padding:.3rem .75rem;font-size:.8rem;font-weight:700;cursor:pointer" id="btn-genera-draft">▶ Genera Draft</button>';
    html += '</div></div>';
    html += '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:.6rem">';
    // LinkedIn
    var li = (platforms.linkedin || {});
    var liCol = li.connesso ? '#68D391' : (li.configurato ? '#F6AD55' : '#FC8181');
    var liLabel = li.connesso ? '✅ Connesso' : (li.configurato ? '⚠️ Token scaduto' : '❌ Da configurare');
    html += '<div style="background:rgba(10,102,194,.12);border:1px solid rgba(10,102,194,.25);border-radius:8px;padding:.7rem 1rem">';
    html += '<div style="display:flex;align-items:center;gap:.4rem;margin-bottom:.3rem"><span style="color:#0A66C2;font-size:1rem">in</span><span style="font-weight:700;font-size:.85rem;color:#e0e0e0">LinkedIn</span></div>';
    html += '<div style="font-size:.78rem;color:'+liCol+'">'+liLabel+'</div>';
    if(!li.connesso && li.configurato){
      html += '<a href="/api/linkedin/connect" style="display:inline-block;margin-top:.5rem;background:#0A66C2;color:#fff;border-radius:5px;padding:.2rem .55rem;font-size:.72rem;text-decoration:none">Connetti</a>';
    } else if(!li.configurato){
      html += '<div style="font-size:.7rem;color:rgba(255,255,255,.3);margin-top:.3rem">config.json → social.linkedin</div>';
    }
    html += '</div>';
    // Facebook
    var fb = (platforms.facebook || {});
    var fbCol = fb.connesso ? '#68D391' : (fb.configurato ? '#F6AD55' : '#FC8181');
    var fbLabel = fb.connesso ? '✅ ' + (fb.page_name || 'Connesso') : (fb.configurato ? '⚠️ Token scaduto' : '❌ Da configurare');
    html += '<div style="background:rgba(66,103,178,.12);border:1px solid rgba(66,103,178,.25);border-radius:8px;padding:.7rem 1rem">';
    html += '<div style="display:flex;align-items:center;gap:.4rem;margin-bottom:.3rem"><span style="color:#4267B2;font-size:1rem">f</span><span style="font-weight:700;font-size:.85rem;color:#e0e0e0">Facebook</span></div>';
    html += '<div style="font-size:.78rem;color:'+fbCol+'">'+fbLabel+'</div>';
    if(!fb.connesso && fb.configurato){
      html += '<a href="/api/meta/connect" style="display:inline-block;margin-top:.5rem;background:#4267B2;color:#fff;border-radius:5px;padding:.2rem .55rem;font-size:.72rem;text-decoration:none">Connetti</a>';
    } else if(!fb.configurato){
      html += '<div style="font-size:.7rem;color:rgba(255,255,255,.3);margin-top:.3rem">config.json → social.meta</div>';
    }
    html += '</div>';
    // Instagram
    var ig = (platforms.instagram || {});
    var igCol = ig.connesso ? '#68D391' : '#FC8181';
    var igLabel = ig.connesso ? '✅ Connesso' : '❌ Richiede Meta connesso';
    html += '<div style="background:rgba(188,42,141,.1);border:1px solid rgba(188,42,141,.25);border-radius:8px;padding:.7rem 1rem">';
    html += '<div style="display:flex;align-items:center;gap:.4rem;margin-bottom:.3rem"><span style="font-size:.72rem;background:linear-gradient(135deg,#833ab4,#fd1d1d,#fcb045);color:#fff;border-radius:4px;padding:.1rem .3rem;font-weight:700">IG</span><span style="font-weight:700;font-size:.85rem;color:#e0e0e0">Instagram</span></div>';
    html += '<div style="font-size:.78rem;color:'+igCol+'">'+igLabel+'</div>';
    html += '<div style="font-size:.7rem;color:rgba(255,255,255,.3);margin-top:.3rem">Collegato a Meta/Facebook</div>';
    html += '</div>';
    html += '</div></div>';

    // ── Draft in attesa ────────────────────────────────────────
    if(pending.length > 0){
      html += '<div class="box"><h3 style="color:#F6AD55;margin-bottom:.9rem">⏳ Draft in attesa di approvazione ('+pending.length+')</h3>';
      pending.forEach(function(d){
        var preview = (d.text_it || d.text_es || '').slice(0,300);
        var chIcons = (d.channels||[]).map(function(ch){
          if(ch==='linkedin') return '<span style="color:#0A66C2;font-size:.75rem;font-weight:700">in</span>';
          if(ch==='facebook') return '<span style="color:#4267B2;font-size:.8rem;font-weight:700">f</span>';
          if(ch==='instagram') return '<span style="font-size:.65rem;background:linear-gradient(135deg,#833ab4,#fd1d1d,#fcb045);color:#fff;border-radius:3px;padding:.05rem .25rem;font-weight:700">IG</span>';
          return '<span style="opacity:.5;font-size:.75rem">'+ch+'</span>';
        }).join(' ');
        html += '<div style="background:rgba(0,0,0,.3);border-radius:8px;padding:1rem;margin-bottom:.8rem;border:1px solid rgba(246,173,85,.2)">';
        html += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem;flex-wrap:wrap;gap:.3rem">';
        html += '<span style="font-weight:700;color:#F6AD55;font-size:.88rem">'+d.theme+' · '+d.lang+' · '+d.date+'</span>';
        html += '<span style="display:flex;gap:.35rem;align-items:center">'+chIcons+'</span>';
        html += '</div>';
        html += '<div style="font-size:.82rem;opacity:.72;margin-bottom:.8rem;white-space:pre-wrap;line-height:1.5">'+preview+(preview.length===300?'…':'')+'</div>';
        if(d.image_url){
          html += '<div style="font-size:.75rem;color:rgba(255,255,255,.35);margin-bottom:.6rem">🖼 '+d.image_url+'</div>';
        }
        html += '<div style="display:flex;gap:.5rem;flex-wrap:wrap">';
        html += '<button onclick="socialApprova(\''+d.draft_id+'\')" style="background:#276749;border:none;border-radius:6px;color:#68D391;padding:.3rem .8rem;font-size:.78rem;font-weight:600;cursor:pointer">✅ Approva &amp; Pubblica</button>';
        html += '<button onclick="socialModificaDraft(\''+d.draft_id+'\',this)" style="background:rgba(246,173,85,.15);border:1px solid rgba(246,173,85,.3);border-radius:6px;color:#F6AD55;padding:.3rem .7rem;font-size:.78rem;cursor:pointer">✏ Modifica</button>';
        html += '<button onclick="socialRifiuta(\''+d.draft_id+'\')" style="background:rgba(252,129,129,.1);border:1px solid rgba(252,129,129,.3);border-radius:6px;color:#FC8181;padding:.3rem .7rem;font-size:.78rem;cursor:pointer">✕ Rifiuta</button>';
        html += '</div></div>';
      });
      html += '</div>';
    } else {
      html += '<div class="box" style="text-align:center;color:#68D391;padding:1.2rem;font-size:.88rem">✅ Nessun draft in attesa · Lo scheduler gira alle 08:00 lun/mer/ven</div>';
    }

    // ── Calendario prossimi post ───────────────────────────────
    if(calendar.length > 0){
      var today2 = new Date().toISOString().slice(0,10);
      var prossimi = calendar.filter(function(e){return e.date >= today2;}).slice(0,8);
      if(prossimi.length > 0){
        html += '<div class="box"><h3 style="color:#aaa;margin-bottom:.8rem;font-size:.88rem">📅 Prossimi Post Programmati</h3>';
        html += '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse;font-size:.8rem">';
        html += '<thead><tr style="border-bottom:1px solid rgba(255,255,255,.08);color:rgba(255,255,255,.35);font-size:.72rem;text-transform:uppercase">';
        html += '<th style="padding:.35rem .6rem;text-align:left">Data</th>';
        html += '<th style="padding:.35rem .6rem;text-align:left">Tema</th>';
        html += '<th style="padding:.35rem .6rem;text-align:left">Lingua</th>';
        html += '<th style="padding:.35rem .6rem;text-align:left">Canali</th>';
        html += '<th style="padding:.35rem .6rem;text-align:center">Stato</th>';
        html += '</tr></thead><tbody>';
        var STATO_BADGE = {
          oggi:        '<span style="background:rgba(246,173,85,.2);color:#F6AD55;border-radius:10px;padding:.1rem .45rem;font-size:.7rem;font-weight:600">OGGI</span>',
          programmato: '<span style="background:rgba(96,165,250,.12);color:#60a5fa;border-radius:10px;padding:.1rem .45rem;font-size:.7rem">schedulato</span>',
          pending:     '<span style="background:rgba(246,173,85,.15);color:#F6AD55;border-radius:10px;padding:.1rem .45rem;font-size:.7rem">draft pronto</span>'
        };
        prossimi.forEach(function(e){
          var chStr = (e.channels||[]).join(', ');
          var badge = STATO_BADGE[e.stato] || '<span style="opacity:.4;font-size:.7rem">'+e.stato+'</span>';
          var rowStyle = e.stato==='oggi' ? 'background:rgba(246,173,85,.04);' : '';
          html += '<tr style="border-bottom:1px solid rgba(255,255,255,.04);'+rowStyle+'">';
          html += '<td style="padding:.4rem .6rem;color:rgba(255,255,255,.7)">'+e.date+'</td>';
          html += '<td style="padding:.4rem .6rem;font-weight:600;color:#e0e0e0">'+e.theme+'</td>';
          html += '<td style="padding:.4rem .6rem;color:rgba(255,255,255,.5)">'+e.lang+'</td>';
          html += '<td style="padding:.4rem .6rem;color:rgba(255,255,255,.45)">'+chStr+'</td>';
          html += '<td style="padding:.4rem .6rem;text-align:center">'+badge+'</td>';
          html += '</tr>';
        });
        html += '</tbody></table></div></div>';
      }
    }

    // ── Cronologia recente ─────────────────────────────────────
    if(recent.length > 0){
      html += '<div class="box"><h3 style="color:#aaa;margin-bottom:.7rem;font-size:.88rem">📋 Cronologia Recente</h3>';
      recent.forEach(function(d){
        var col    = d.status==='published' ? '#68D391' : '#FC8181';
        var icon   = d.status==='published' ? '✅' : '✕';
        var detail = '';
        if(d.publish_results){
          var r = d.publish_results;
          var parts = [];
          if(r.linkedin && r.linkedin.ok)  parts.push('LI ✓');
          if(r.facebook && r.facebook.ok)  parts.push('FB ✓');
          if(r.instagram && r.instagram.ok) parts.push('IG ✓');
          if(parts.length) detail = ' · '+parts.join(' ');
        }
        html += '<div style="display:flex;justify-content:space-between;align-items:center;padding:.4rem 0;border-bottom:1px solid rgba(255,255,255,.04);font-size:.81rem">';
        html += '<span style="opacity:.8">'+d.theme+' · '+d.lang+'</span>';
        html += '<span style="opacity:.5;font-size:.76rem">'+d.date+'</span>';
        html += '<span style="color:'+col+'">'+icon+' '+d.status+detail+'</span>';
        html += '</div>';
      });
      html += '</div>';
    }

    html += '<div id="social-modal-container"></div>';
    el.innerHTML = html;
  }).catch(function(e){
    el.innerHTML = '<div class="box" style="color:#FC8181">Errore caricamento: '+e.message+'</div>';
  });
}

function socialApprova(draftId) {
  fetch('/api/social/approve?draft_id='+draftId+'&action=approve')
    .then(function(r){return r.json();})
    .then(function(d){
      showMsg('crm-msg','✅ Draft approvato e inviato per la pubblicazione','ok');
      renderSocial();
    })
    .catch(function(e){ showMsg('crm-msg','❌ '+e.message,'err'); });
}

function socialRifiuta(draftId) {
  if(!confirm('Rifiutare questo draft?')) return;
  fetch('/api/social/approve?draft_id='+draftId+'&action=reject')
    .then(function(r){return r.json();})
    .then(function(){
      showMsg('crm-msg','🗑 Draft rifiutato','ok');
      renderSocial();
    })
    .catch(function(e){ showMsg('crm-msg','❌ '+e.message,'err'); });
}

function socialGeneraDraft() {
  var btn = document.getElementById('btn-genera-draft');
  if(btn){ btn.disabled=true; btn.textContent='⏳ Generazione...'; }
  fetch('/api/social/genera',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
    .then(function(r){return r.json();})
    .then(function(d){
      if(btn){ btn.disabled=false; btn.textContent='▶ Genera Draft'; }
      if(d.ok){
        showMsg('crm-msg','✅ Draft generato: '+d.draft_id,'ok');
        renderSocial();
      } else {
        showMsg('crm-msg','⚠️ '+(d.msg||'Impossibile generare draft'),'err');
      }
    })
    .catch(function(e){
      if(btn){ btn.disabled=false; btn.textContent='▶ Genera Draft'; }
      showMsg('crm-msg','❌ '+e.message,'err');
    });
}

function socialModificaDraft(draftId, triggerBtn) {
  var cont = document.getElementById('social-modal-container');
  if(!cont) return;
  // Carica il draft corrente
  fetch('/api/social/status').then(function(r){return r.json();}).then(function(d){
    var draft = (d.drafts||[]).find(function(x){return x.draft_id===draftId;});
    if(!draft){ alert('Draft non trovato'); return; }
    var html = '<h3 style="color:#F6AD55;margin-bottom:.3rem;font-size:1rem">✏ Modifica Draft</h3>'
      +'<p style="color:rgba(255,255,255,.4);font-size:.78rem;margin-bottom:1rem">'+draft.theme+' · '+draft.lang+' · '+draft.date+'</p>'
      +'<div style="margin-bottom:.8rem">'
      +'<label style="font-size:.75rem;color:rgba(255,255,255,.4);display:block;margin-bottom:.25rem">Testo IT</label>'
      +'<textarea id="edit-text-it" style="width:100%;height:120px;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem;font-size:.82rem;resize:vertical;line-height:1.5">'+((draft.text_it||''))+'</textarea>'
      +'</div>'
      +'<div style="margin-bottom:1rem">'
      +'<label style="font-size:.75rem;color:rgba(255,255,255,.4);display:block;margin-bottom:.25rem">Testo ES</label>'
      +'<textarea id="edit-text-es" style="width:100%;height:80px;background:rgba(0,0,0,.4);border:1px solid rgba(255,255,255,.15);border-radius:6px;color:#e0e0e0;padding:.5rem;font-size:.82rem;resize:vertical;line-height:1.5">'+((draft.text_es||''))+'</textarea>'
      +'</div>'
      +'<div style="display:flex;gap:.5rem">'
      +'<button onclick="socialSalvaModifica(\''+draftId+'\')" style="flex:1;background:#2C5282;border:none;border-radius:7px;color:#F6AD55;padding:.6rem;font-size:.85rem;font-weight:600;cursor:pointer">💾 Salva</button>'
      +'<button onclick="socialChiudiModal()" style="background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);border-radius:7px;color:rgba(255,255,255,.5);padding:.6rem .9rem;font-size:.85rem;cursor:pointer">Annulla</button>'
      +'</div>';
    cont.innerHTML = _socialModalOverlay(html,'socialChiudiModal()');
  });
}

function socialSalvaModifica(draftId) {
  var textIt = (document.getElementById('edit-text-it')||{value:''}).value;
  var textEs = (document.getElementById('edit-text-es')||{value:''}).value;
  fetch('/api/social/draft/edit',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({draft_id:draftId,text_it:textIt,text_es:textEs})
  }).then(function(r){return r.json();}).then(function(d){
    if(d.ok){
      socialChiudiModal();
      showMsg('crm-msg','✅ Draft aggiornato','ok');
      renderSocial();
    } else {
      alert('Errore: '+(d.msg||'sconosciuto'));
    }
  });
}

function _socialModalOverlay(content, onclose) {
  return '<div id="social-modal" style="position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:center;justify-content:center;padding:1rem">'
    +'<div style="background:#1e293b;border:1px solid rgba(255,255,255,.1);border-radius:12px;padding:1.5rem;width:100%;max-width:540px;max-height:88vh;overflow-y:auto;position:relative">'
    +'<button onclick="'+onclose+'" style="position:absolute;top:.75rem;right:.75rem;background:none;border:none;color:rgba(255,255,255,.4);font-size:1.1rem;cursor:pointer">✕</button>'
    +content
    +'</div></div>';
}

function socialChiudiModal() {
  var m = document.getElementById('social-modal'); if(m) m.remove();
  var c = document.getElementById('social-modal-container'); if(c) c.innerHTML='';
}

function renderWhatsappSub() {
  if(!_clienti) { loadClienti(); return; }
  var all = (_clienti.tester||[]).concat(_clienti.clienti||[]);
  var optIn = all.filter(function(c){ return c.whatsapp_optin === true; });
  var el = document.getElementById('whatsapp-content');

  var kpi = '<div class="kpi-row" style="margin-bottom:1.2rem">'
    +'<div class="kpi"><div class="kpi-label">📱 Opt-in WA</div><div class="kpi-val" style="color:#68D391">'+optIn.length+'</div></div>'
    +'<div class="kpi"><div class="kpi-label">👥 Tot. clienti</div><div class="kpi-val">'+all.length+'</div></div>'
    +'</div>';

  var statoBox = '<div class="box" style="margin-bottom:1rem">'
    +'<h3 style="color:#F6AD55;margin-bottom:.7rem">💬 Stato WhatsApp Business</h3>'
    +'<div style="background:rgba(252,129,129,.08);border:1px solid rgba(252,129,129,.3);border-radius:8px;padding:.8rem 1rem;font-size:.85rem;margin-bottom:.8rem">'
    +'⚠️ In attesa: Meta Business Manager verificato (CIF B23881691) + numero dedicato + template approvati'
    +'</div>'
    +'<div style="font-size:.83rem;line-height:1.9;opacity:.7">'
    +'⏳ Template <strong>screener_pronto</strong> (4 parametri) — da sottomettere a Meta<br>'
    +'⏳ Template <strong>brief_mattutino</strong> (3 parametri) — da sottomettere a Meta<br>'
    +'📄 Procedura: <code>01_DOCUMENTAZIONE_OPERATIVA/WhatsApp_Business_Setup_Procedura.md</code>'
    +'</div></div>';

  var optInTable = '';
  if(optIn.length > 0) {
    var rows = '';
    optIn.forEach(function(c){
      var nome = ((c.nome||'')+' '+(c.cognome||'')).trim()||'—';
      var piani = [c.piano_azioni,c.piano_etf,c.piano_fondi].filter(function(p){return p&&p!=='NONE';}).join(' / ')||'—';
      rows += '<tr><td>'+nome+'</td><td style="font-size:.8rem;opacity:.7">'+c.email+'</td><td style="font-size:.82rem">'+piani+'</td></tr>';
    });
    optInTable = '<div class="box"><h4 style="opacity:.7;font-size:.85rem;margin-bottom:.7rem">Clienti con consenso WhatsApp</h4>'
      +'<div class="tbl-wrap"><table><thead><tr><th>Nome</th><th>Email</th><th>Piani</th></tr></thead><tbody>'+rows+'</tbody></table></div></div>';
  } else {
    optInTable = '<div class="box" style="opacity:.5;font-size:.85rem">Nessun cliente ha ancora attivato le notifiche WhatsApp. Usa il bottone 📱 nella tab Clienti per ogni singolo cliente.</div>';
  }

  el.innerHTML = kpi + statoBox + optInTable;
}

// ─── PIPELINE ─────────────────────────────────────────────────
var _pipelineSearch = '';

function pipelineSearch(val){
  _pipelineSearch = val;
  renderPipelineKanban();
}

function loadPipelineData(){
  var tasks = 0;
  var done = function(){
    tasks--;
    if(tasks<=0) renderPipelineKanban();
  };
  if(!_clienti){
    tasks++;
    fetch('/api/clienti').then(function(r){return r.json();}).then(function(d){_clienti=d;done();}).catch(done);
  } else tasks = 0;
  if(!_prospect){
    tasks++;
    fetch('/api/prospect').then(function(r){return r.json();}).then(function(d){_prospect=d.items||[];done();}).catch(done);
  }
  if(tasks===0) renderPipelineKanban();
}

var PIPELINE_COLS = [
  {stato:'Da Contattare',    label:'Lead',             color:'#9ca3af', source:'prospect'},
  {stato:'Contattato',       label:'Contattato',       color:'#60a5fa', source:'prospect'},
  {stato:'Interessato',      label:'Interessato',      color:'#34d399', source:'prospect'},
  {stato:'Prospect LinkedIn',label:'Prospect LinkedIn',color:'#0A66C2', source:'prospect'},
  {stato:'TESTER',           label:'Tester',           color:'#F6AD55', source:'clienti'},
  {stato:'ATTIVO',           label:'Abbonato',         color:'#68D391', source:'clienti'},
];

var INTERESSE_COLOR = {Azioni:'#4A90D9',ETF:'#68D391',Fondi:'#F6AD55',Tutti:'#a78bfa'};

function renderPipelineKanban(){
  var board = document.getElementById('pipeline-board');
  var strip = document.getElementById('pipeline-strip');
  var statsLbl = document.getElementById('pipeline-stats-label');
  if(!board) return;

  var tester  = (_clienti ? (_clienti.tester||[]) : []);
  var attivi  = (_clienti ? (_clienti.clienti||[]).filter(function(c){return c.stato==='ATTIVO';}) : []);
  var prospect = _prospect || [];

  var q = _pipelineSearch.toLowerCase();

  function matchSearch(nome, cognome, email){
    if(!q) return true;
    return ((nome||'')+(cognome||'')).toLowerCase().indexOf(q)>=0 || (email||'').toLowerCase().indexOf(q)>=0;
  }

  var totalCount = prospect.filter(function(p){return p.stato!=='Non Interessato'&&p.stato!=='Promosso ✓';}).length + tester.length + attivi.length;
  if(statsLbl) statsLbl.textContent = totalCount + ' contatti attivi';

  var boardHtml = '';

  PIPELINE_COLS.forEach(function(col){
    var cards = [];

    if(col.source === 'prospect'){
      cards = prospect.filter(function(p){
        return p.stato === col.stato && matchSearch(p.nome, p.cognome, p.email);
      });
    } else if(col.stato === 'TESTER'){
      cards = tester.filter(function(c){
        return matchSearch(c.nome, c.cognome, c.email);
      });
    } else if(col.stato === 'ATTIVO'){
      cards = attivi.filter(function(c){
        return matchSearch(c.nome, c.cognome, c.email);
      });
    }

    boardHtml += '<div style="flex-shrink:0;width:220px;background:rgba(255,255,255,.03);border:1px solid '+col.color+'33;border-radius:10px;padding:.75rem">';
    var colHeaderExtra = '';
    if(col.stato === 'Prospect LinkedIn' && cards.length > 0){
      colHeaderExtra = '<button onclick="pipelineEsportaLinkedIn()" style="background:rgba(10,102,194,.15);border:1px solid rgba(10,102,194,.35);border-radius:5px;color:#0A66C2;padding:.1rem .4rem;font-size:.68rem;cursor:pointer" title="Esporta CSV per LinkedIn Ads">⬇ Ads</button>';
    }
    boardHtml += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.7rem">'
      +'<span style="font-weight:700;font-size:.83rem;color:'+col.color+'">'+col.label+'</span>'
      +'<div style="display:flex;align-items:center;gap:.35rem">'
      +colHeaderExtra
      +'<span style="background:'+col.color+'22;color:'+col.color+';border-radius:10px;padding:.1rem .55rem;font-size:.74rem;font-weight:700">'+cards.length+'</span>'
      +'</div>'
      +'</div>';

    if(cards.length === 0){
      boardHtml += '<div style="opacity:.25;font-size:.76rem;text-align:center;padding:1.5rem 0">—</div>';
    } else {
      cards.forEach(function(c){
        var nome = (c.nome||'') + (c.cognome?' '+c.cognome:'') || (c.ragione_sociale||'');
        var email = c.email || '';
        var interesse = c.interesse || (c.piano_azioni&&c.piano_azioni!=='NONE'?'Azioni':c.piano_etf&&c.piano_etf!=='NONE'?'ETF':c.piano_fondi&&c.piano_fondi!=='NONE'?'Fondi':'');
        var intColor = INTERESSE_COLOR[interesse] || '#888';
        var cardActions = '';
        if(col.source === 'prospect'){
          var nextStato = col.stato === 'Da Contattare' ? 'Contattato' : col.stato === 'Contattato' ? 'Interessato' : col.stato === 'Interessato' ? 'Prospect LinkedIn' : null;
          if(nextStato){
            cardActions += '<button onclick="pipelineAvanza('+c.id+',\''+nextStato+'\')" style="font-size:.68rem;background:'+col.color+'22;color:'+col.color+';border:1px solid '+col.color+'44;border-radius:4px;padding:.1rem .4rem;cursor:pointer;margin-right:.25rem" title="Avanza stato">▶</button>';
          }
          if(col.stato === 'Prospect LinkedIn'){
            var liUrl = c.linkedin_url || '';
            var liHref = liUrl ? liUrl : 'https://www.linkedin.com/search/results/people/?keywords='+encodeURIComponent((c.nome||'')+(c.cognome?' '+c.cognome:''));
            cardActions += '<a href="'+liHref+'" target="_blank" style="font-size:.68rem;background:rgba(10,102,194,.15);color:#0A66C2;border:1px solid rgba(10,102,194,.35);border-radius:4px;padding:.1rem .4rem;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;gap:2px" title="'+(liUrl?'Apri profilo LinkedIn':'Cerca su LinkedIn')+'"><svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zM9 17H6.5v-7H9v7zm-1.3-8a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm9.3 8h-2.5v-3.5c0-.8-.7-1.5-1.5-1.5s-1.5.7-1.5 1.5V17H9v-7h2.5v1a3 3 0 015.5 1.7V17z"/></svg> LinkedIn</a>';
          }
          cardActions += '<button onclick="promuoviProspect('+(_prospect?_prospect.indexOf(c):0)+')" style="font-size:.68rem;background:rgba(246,173,85,.15);color:#F6AD55;border:1px solid rgba(246,173,85,.3);border-radius:4px;padding:.1rem .4rem;cursor:pointer" title="Promuovi a Tester">▲</button>';
        }
        boardHtml += '<div style="background:rgba(0,0,0,.25);border-radius:7px;padding:.6rem .7rem;margin-bottom:.45rem;border:1px solid rgba(255,255,255,.06)">'
          +'<div style="font-weight:600;font-size:.81rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:.2rem">'+nome+'</div>'
          +'<div style="font-size:.72rem;opacity:.55;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:.35rem">'+email+'</div>'
          +(interesse?'<span style="font-size:.68rem;background:'+intColor+'22;color:'+intColor+';border-radius:4px;padding:.1rem .35rem">'+interesse+'</span>':'')
          +(cardActions?'<div style="margin-top:.4rem;display:flex;gap:.25rem">'+cardActions+'</div>':'')
          +'</div>';
      });
    }
    boardHtml += '</div>';
  });

  board.innerHTML = boardHtml;

  // Strip Non Interessato + Sospeso
  var nonInt = prospect.filter(function(p){return p.stato==='Non Interessato';});
  var sospesi = (_clienti ? ((_clienti.tester||[]).concat(_clienti.clienti||[])).filter(function(c){return c.stato==='SOSPESO';}) : []);
  var stripHtml = '';
  if(nonInt.length>0){
    stripHtml += '<div style="border:1px solid rgba(248,113,113,.25);border-radius:9px;padding:.6rem .9rem;background:rgba(248,113,113,.05);flex:1;min-width:200px">'
      +'<div style="font-size:.75rem;font-weight:700;color:#f87171;margin-bottom:.45rem">✕ Non Interessato ('+nonInt.length+')</div>'
      +'<div style="display:flex;flex-wrap:wrap;gap:.3rem">'
      + nonInt.map(function(p){return '<span style="font-size:.72rem;background:rgba(0,0,0,.2);border-radius:5px;padding:.15rem .45rem;opacity:.7">'+(p.nome||'')+(p.cognome?' '+p.cognome:'')+'</span>';}).join('')
      +'</div></div>';
  }
  if(sospesi.length>0){
    stripHtml += '<div style="border:1px solid rgba(156,163,175,.25);border-radius:9px;padding:.6rem .9rem;background:rgba(156,163,175,.05);flex:1;min-width:200px">'
      +'<div style="font-size:.75rem;font-weight:700;color:#9ca3af;margin-bottom:.45rem">⏸ Sospesi ('+sospesi.length+')</div>'
      +'<div style="display:flex;flex-wrap:wrap;gap:.3rem">'
      + sospesi.map(function(c){return '<span style="font-size:.72rem;background:rgba(0,0,0,.2);border-radius:5px;padding:.15rem .45rem;opacity:.7">'+(c.nome||'')+(c.cognome?' '+c.cognome:'')+'</span>';}).join('')
      +'</div></div>';
  }
  if(strip) strip.innerHTML = stripHtml;
}

function pipelineAvanza(id, nuovoStato){
  fetch('/api/prospect/update',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:id, stato:nuovoStato})
  }).then(function(r){return r.json();}).then(function(res){
    if(res.ok){
      var p = (_prospect||[]).find(function(x){return x.id===id;});
      if(p){ p.stato = nuovoStato; renderPipelineKanban(); }
    }
  });
}

function pipelineEsportaLinkedIn(){
  var data = (_prospect||[]).filter(function(p){return p.stato==='Prospect LinkedIn';});
  if(!data.length){ alert('Nessun Prospect LinkedIn da esportare'); return; }
  var bom = '﻿';
  var header = 'Email,Nome,LinkedIn';
  var righe = data.map(function(p){
    var nome = ((p.nome||'')+(p.cognome?' '+p.cognome:'')).trim();
    return p.email+',"'+nome.replace(/"/g,'""')+'",'+(p.linkedin_url||'');
  }).join('\n');
  var blob = new Blob([bom+header+'\n'+righe], {type:'text/csv;charset=utf-8'});
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a'); a.href=url; a.download='prospect-linkedin-ads.csv';
  a.click(); URL.revokeObjectURL(url);
}

function importApolloFile(input) {
  var file = input.files[0];
  if(!file) return;
  input.value = '';
  var reader = new FileReader();
  reader.onload = function(e) {
    var csv = e.target.result;
    fetch('/api/prospect/import-apollo', {
      method: 'POST',
      headers: {'Content-Type': 'text/plain; charset=utf-8'},
      body: csv
    }).then(function(r){return r.json();}).then(function(d){
      if(!d.ok){ alert('Errore import Apollo: '+(d.msg||'sconosciuto')); return; }
      alert('Apollo.io import completato!\nInseriti: '+d.inseriti+'\nDuplicati: '+d.duplicati+'\nCon LinkedIn: '+d.con_linkedin);
      _prospect = null;
      loadCrmData();
    }).catch(function(e){ alert('Errore: '+e); });
  };
  reader.readAsText(file, 'UTF-8');
}

function mostraNuovoLead(){
  document.getElementById('modal-nuovo-lead').style.display='flex';
  document.getElementById('nl-nome').value='';
  document.getElementById('nl-cognome').value='';
  document.getElementById('nl-email').value='';
  document.getElementById('nl-fonte').value='';
}

function confermaNuovoLead(){
  var nome=document.getElementById('nl-nome').value.trim();
  var email=document.getElementById('nl-email').value.trim();
  if(!nome||!email){alert('Nome ed email obbligatori');return;}
  fetch('/api/prospect/aggiungi',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
      nome:nome,
      cognome:document.getElementById('nl-cognome').value.trim(),
      email:email,
      fonte:document.getElementById('nl-fonte').value.trim()||'Manuale',
      interesse:document.getElementById('nl-interesse').value,
    })
  }).then(function(r){return r.json();}).then(function(res){
    document.getElementById('modal-nuovo-lead').style.display='none';
    if(res.ok){
      _prospect=null;
      loadPipelineData();
      showMsg('crm-msg','✅ Lead aggiunto','ok');
    } else showMsg('crm-msg','❌ '+res.msg,'err');
  });
}

// ═══════════════════════════════════════════════════════════════
// PROSPECT
// ═══════════════════════════════════════════════════════════════
var _prospect = null;
var _prospectFiltroStato = '';
var _prospectRicerca = '';
var _notaProspectIdx = -1;

var PROSPECT_STATI = [
  {value:'Da Contattare',    color:'#9ca3af'},
  {value:'Contattato',       color:'#60a5fa'},
  {value:'Interessato',      color:'#34d399'},
  {value:'Prospect LinkedIn',color:'#0A66C2'},
  {value:'Non Interessato',  color:'#f87171'},
  {value:'Promosso ✓', color:'#a78bfa'},
];

function loadProspect(){
  fetch('/api/prospect').then(function(r){
    if(!r.ok||r.redirected) throw new Error('Sessione scaduta');
    return r.json();
  }).then(function(d){
    _prospect = d.items || [];
    renderProspect();
  }).catch(function(e){ showMsg('crm-msg','❌ '+e.message,'err'); });
}

function setProspectFiltro(stato){
  _prospectFiltroStato = stato;
  renderProspect();
}

function prospectSearch(val){
  _prospectRicerca = val;
  renderProspect();
}

function renderProspect(){
  if(!_prospect) return;
  var list = _prospect.slice();
  if(_prospectFiltroStato) list = list.filter(function(p){ return p.stato === _prospectFiltroStato; });
  if(_prospectRicerca){
    var q = _prospectRicerca.toLowerCase();
    list = list.filter(function(p){
      return ((p.nome||'')+(p.cognome||'')).toLowerCase().indexOf(q)>=0
          || (p.email||'').toLowerCase().indexOf(q)>=0
          || (p.fonte||'').toLowerCase().indexOf(q)>=0;
    });
  }

  var totale = _prospect.length;
  var conteggi = {};
  _prospect.forEach(function(p){ conteggi[p.stato] = (conteggi[p.stato]||0)+1; });

  // Chips filtro
  var chipStyle = 'padding:.3rem .8rem;border-radius:14px;border:1px solid rgba(255,255,255,.15);background:transparent;color:rgba(255,255,255,.5);cursor:pointer;font-size:.78rem;font-weight:600;transition:all .15s';
  var chipsHtml = '<div style="display:flex;gap:.4rem;flex-wrap:wrap">';
  var allActive = !_prospectFiltroStato ? ';background:#2C5282;border-color:#2C5282;color:#F6AD55' : '';
  chipsHtml += '<button onclick="setProspectFiltro(\'\')" style="'+chipStyle+allActive+'">Tutti ('+totale+')</button>';
  PROSPECT_STATI.forEach(function(s){
    var cnt = conteggi[s.value] || 0;
    var active = (_prospectFiltroStato===s.value) ? ';background:'+s.color+'22;border-color:'+s.color+';color:'+s.color : '';
    chipsHtml += '<button onclick="setProspectFiltro(\''+s.value+'\')" style="'+chipStyle+active+'">'+s.value+' ('+cnt+')</button>';
  });
  chipsHtml += '</div>';

  // Righe tabella
  var rows = list.map(function(p){
    var idx = _prospect.indexOf(p);
    var bg = list.indexOf(p)%2===0?'rgba(255,255,255,.02)':'transparent';
    var sc = PROSPECT_STATI.find(function(s){return s.value===p.stato;})||{color:'#888'};
    var statoBadge = '<span style="background:'+sc.color+'22;color:'+sc.color+';border:1px solid '+sc.color+'44;border-radius:12px;padding:.12rem .5rem;font-size:.72rem;font-weight:600;white-space:nowrap">'+p.stato+'</span>';
    var statoSel = '<select onchange="aggiornaStatoProspect('+idx+',this.value)" style="background:#0a0f1e;border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:.25rem .4rem;color:#e0e0e0;font-size:.74rem;outline:none">'
      + PROSPECT_STATI.map(function(s){ return '<option value="'+s.value+'"'+(p.stato===s.value?' selected':'')+'>'+s.value+'</option>'; }).join('')
      + '</select>';
    var notaBtn = p.note
      ? '<button class="btn" style="padding:.18rem .45rem;font-size:.71rem;border-color:rgba(246,173,85,.4);color:#F6AD55" onclick="mostraNotaProspect('+idx+')" title="'+p.note.replace(/"/g,'\'')+'">📝</button>'
      : '<button class="btn" style="padding:.18rem .45rem;font-size:.71rem;opacity:.4" onclick="mostraNotaProspect('+idx+')">nota</button>';
    var liBtn = p.linkedin_url
      ? '<a href="'+p.linkedin_url+'" target="_blank" class="btn" style="padding:.18rem .45rem;font-size:.71rem;border-color:rgba(10,102,194,.4);color:#4A90D9;text-decoration:none" title="LinkedIn">in</a>'
      : '';
    var promuoviBtn = (p.stato !== 'Promosso ✓')
      ? '<button class="btn btn-gr" style="padding:.18rem .55rem;font-size:.71rem" onclick="promuoviProspect('+idx+')" title="Promuovi a Tester">▲ Tester</button>'
      : '<span style="color:#a78bfa;font-size:.75rem;padding:.2rem .4rem">✓ Tester</span>';
    var delBtn = '<button class="btn" style="padding:.18rem .4rem;font-size:.71rem;border-color:rgba(239,68,68,.35);color:#f87171" onclick="eliminaProspect('+idx+',\''+p.email+'\')">🗑</button>';
    var ult = p.data_ultimo_contatto ? p.data_ultimo_contatto.slice(0,10) : '<span style="opacity:.3">—</span>';
    return '<tr style="background:'+bg+'">'
      +'<td style="padding:.4rem .8rem;font-size:.84rem;font-weight:500">'+((p.nome||'')+(p.cognome?' '+p.cognome:''))+'</td>'
      +'<td style="padding:.4rem .8rem;font-size:.79rem;opacity:.7">'+p.email+'</td>'
      +'<td style="padding:.4rem .8rem;font-size:.77rem;opacity:.6">'+(p.fonte||'—')+'</td>'
      +'<td style="padding:.4rem .8rem;font-size:.77rem">'+(p.interesse||'—')+'</td>'
      +'<td style="padding:.4rem .8rem">'+statoSel+'</td>'
      +'<td style="padding:.4rem .8rem;font-size:.75rem;opacity:.65">'+ult+'</td>'
      +'<td style="padding:.4rem .8rem"><div style="display:flex;gap:.25rem;align-items:center">'+notaBtn+liBtn+promuoviBtn+delBtn+'</div></td>'
      +'</tr>';
  }).join('') || '<tr><td colspan="7" style="padding:2rem;text-align:center;opacity:.4">Nessun prospect trovato. Importa un CSV per iniziare.</td></tr>';

  var chips = document.getElementById('prospect-chips');
  if(chips) chips.innerHTML = chipsHtml;
  var tbody = document.getElementById('prospect-tbody');
  if(tbody) tbody.innerHTML = rows;
  var cnt = document.getElementById('prospect-count');
  if(cnt) cnt.textContent = totale + ' prospect totali';
}

function aggiornaStatoProspect(idx, stato){
  var p = _prospect[idx]; if(!p) return;
  fetch('/api/prospect/update',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:p.id, stato:stato})
  }).then(function(r){return r.json();}).then(function(res){
    if(res.ok){ p.stato = stato; renderProspect(); }
    else showMsg('crm-msg','❌ '+res.msg,'err');
  });
}

function mostraNotaProspect(idx){
  _notaProspectIdx = idx;
  var p = _prospect[idx]; if(!p) return;
  var el = document.getElementById('modal-nota-prospect');
  document.getElementById('modal-nota-nome').textContent = (p.nome||'')+(p.cognome?' '+p.cognome:'')+' — '+p.email;
  document.getElementById('modal-nota-testo').value = p.note || '';
  document.getElementById('modal-nota-data').value = p.data_ultimo_contatto ? p.data_ultimo_contatto.slice(0,10) : '';
  el.style.display = 'flex';
}

function salvaNotaProspect(){
  var p = _prospect[_notaProspectIdx]; if(!p) return;
  var nota = document.getElementById('modal-nota-testo').value.trim();
  var data = document.getElementById('modal-nota-data').value || null;
  fetch('/api/prospect/update',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:p.id, note:nota, data_ultimo_contatto:data})
  }).then(function(r){return r.json();}).then(function(res){
    document.getElementById('modal-nota-prospect').style.display='none';
    if(res.ok){
      p.note = nota;
      p.data_ultimo_contatto = data;
      renderProspect();
      showMsg('crm-msg','✅ Nota salvata','ok');
    } else showMsg('crm-msg','❌ '+res.msg,'err');
  });
}

function promuoviProspect(idx){
  var p = _prospect[idx]; if(!p) return;
  if(!confirm('Promuovi '+p.nome+' '+p.cognome+' ('+p.email+') come Tester?')) return;
  fetch('/api/prospect/promuovi',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:p.id})
  }).then(function(r){return r.json();}).then(function(res){
    if(res.ok){
      p.stato = 'Promosso ✓';
      _clienti = null;
      renderProspect();
      showMsg('crm-msg','✅ Promosso a Tester. Vai nella tab Clienti per attivarlo.','ok');
    } else showMsg('crm-msg','❌ '+res.msg,'err');
  });
}

function eliminaProspect(idx, email){
  var p = _prospect[idx]; if(!p) return;
  if(!confirm('Eliminare prospect '+email+'?')) return;
  fetch('/api/prospect/elimina',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:p.id})
  }).then(function(r){return r.json();}).then(function(res){
    if(res.ok){ _prospect.splice(idx,1); renderProspect(); showMsg('crm-msg','🗑 Prospect eliminato','ok'); }
    else showMsg('crm-msg','❌ '+res.msg,'err');
  });
}

function importProspectCSV(input){
  var file = input.files[0]; if(!file) return;
  var reader = new FileReader();
  reader.onload = function(e){
    var csv = e.target.result;
    fetch('/api/prospect/import',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({csv_content:csv})
    }).then(function(r){return r.json();}).then(function(res){
      input.value = '';
      // Mostra risultato nel box giusto (pipeline o prospect)
      var boxId = document.getElementById('pipeline-import-result') ? 'pipeline-import-result' : 'prospect-import-result';
      var box = document.getElementById(boxId);
      if(res.ok){
        if(box){ box.style.display=''; box.innerHTML='✅ Import completato — Inseriti: <strong>'+res.inseriti+'</strong>'+(res.duplicati?' · Duplicati: <strong>'+res.duplicati+'</strong>':'')+(res.errori?' · Errori: <strong>'+res.errori+'</strong>':''); }
        _prospect = null;
        if(_crmSubActive==='pipeline') loadPipelineData();
        else loadProspect();
        showMsg('crm-msg','✅ Importati '+res.inseriti+' prospect','ok');
      } else {
        if(box){ box.style.display=''; box.style.borderColor='rgba(252,129,129,.3)'; box.innerHTML='❌ '+res.msg; }
        showMsg('crm-msg','❌ '+res.msg,'err');
      }
    }).catch(function(e){ showMsg('crm-msg','❌ '+e.message,'err'); });
  };
  reader.readAsText(file, 'UTF-8');
}

function exportProspect(){
  window.location.href = '/api/prospect/export';
}

// ═══════════════════════════════════════════════════════════════
// CALENDARIO EDITORIALE
// ═══════════════════════════════════════════════════════════════
var _calYear = new Date().getFullYear();
var _calMonth = new Date().getMonth(); // 0-based

function calNav(dir){
  _calMonth += dir;
  if(_calMonth < 0){ _calMonth = 11; _calYear--; }
  if(_calMonth > 11){ _calMonth = 0; _calYear++; }
  renderCalendario();
}

function renderCalendario(){
  var MESI = ['Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno',
              'Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre'];
  var GIORNI = ['Lun','Mar','Mer','Gio','Ven','Sab','Dom'];
  var lbl = document.getElementById('cal-month-label');
  if(lbl) lbl.textContent = MESI[_calMonth] + ' ' + _calYear;

  // Genera eventi fissi (schedule screener) per il mese corrente
  var eventi = {};
  var primoGiorno = new Date(_calYear, _calMonth, 1);
  var ultimoGiorno = new Date(_calYear, _calMonth+1, 0).getDate();

  for(var d=1; d<=ultimoGiorno; d++){
    var dt = new Date(_calYear, _calMonth, d);
    var wd = dt.getDay(); // 0=Dom, 1=Lun, ..., 6=Sab
    var key = d;
    eventi[key] = eventi[key] || [];
    // Lun-Ven: invio Azioni 23:00
    if(wd>=1 && wd<=5){
      eventi[key].push({tipo:'screener', label:'📈 Azioni 23:00', color:'#4A90D9'});
    }
    // Lun, Mer, Ven: invio ETF + Fondi 23:30
    if(wd===1||wd===3||wd===5){
      eventi[key].push({tipo:'screener', label:'📦 ETF+Fondi 23:30', color:'#68D391'});
    }
    // Lun, Mer, Ven: social post (se scheduler attivo)
    if(wd===1||wd===3||wd===5){
      eventi[key].push({tipo:'social', label:'📱 Social 08:00', color:'#F6AD55'});
    }
  }

  // Grid calendario
  var firstWeekday = (new Date(_calYear, _calMonth, 1).getDay() + 6) % 7; // 0=Lun
  var html = '<div class="box">';
  html += '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:2px;margin-bottom:.4rem">';
  GIORNI.forEach(function(g){
    html += '<div style="text-align:center;font-size:.72rem;font-weight:700;opacity:.45;padding:.3rem">'+g+'</div>';
  });
  html += '</div>';
  html += '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px">';

  // Celle vuote prima del 1
  for(var i=0; i<firstWeekday; i++){
    html += '<div style="min-height:80px"></div>';
  }

  var today = new Date();
  for(var d=1; d<=ultimoGiorno; d++){
    var isToday = (today.getDate()===d && today.getMonth()===_calMonth && today.getFullYear()===_calYear);
    var ev = eventi[d] || [];
    var border = isToday ? 'border:2px solid #F6AD55' : 'border:1px solid rgba(255,255,255,.07)';
    html += '<div style="min-height:80px;background:rgba(255,255,255,.03);border-radius:6px;padding:.4rem .35rem;'+border+'">'
      +'<div style="font-size:.78rem;font-weight:700;'+(isToday?'color:#F6AD55':'opacity:.5')+';margin-bottom:.3rem">'+d+'</div>';
    ev.forEach(function(e){
      html += '<div style="font-size:.66rem;background:'+e.color+'22;color:'+e.color+';border-radius:4px;padding:.15rem .3rem;margin-bottom:.2rem;line-height:1.3">'+e.label+'</div>';
    });
    html += '</div>';
  }

  html += '</div></div>';

  // Legenda
  html += '<div class="box" style="margin-top:1rem">'
    +'<h4 style="opacity:.55;font-size:.8rem;margin-bottom:.7rem">LEGENDA INVII AUTOMATICI</h4>'
    +'<div style="display:flex;flex-wrap:wrap;gap:1rem;font-size:.82rem">'
    +'<div><span style="color:#4A90D9">■</span> Azioni — Lun/Mar/Mer/Gio/Ven alle 23:00</div>'
    +'<div><span style="color:#68D391">■</span> ETF + Fondi — Lun/Mer/Ven alle 23:30</div>'
    +'<div><span style="color:#F6AD55">■</span> Social Post — Lun/Mer/Ven alle 08:00 (se scheduler attivo)</div>'
    +'</div></div>';

  var el = document.getElementById('calendario-content');
  if(el) el.innerHTML = html;
}

// ─── SCREENER PARAMS (parametri.json) ────────────────────────
var _scrParams = null;

function loadScreenerParams(){
  fetch('/api/params').then(function(r){
    if(!r.ok || r.redirected) throw new Error('Sessione scaduta — effettua il login');
    var ct = r.headers.get('content-type')||'';
    if(!ct.includes('json')) throw new Error('Sessione scaduta — effettua il login');
    return r.json();
  }).then(function(data){
    _scrParams = data;
    renderScreenerParams();
  }).catch(function(e){
    document.getElementById('scr-params-content').innerHTML =
      '<span style="color:#F6AD55">⚠️ '+e.message+'</span>';
  });
}

function renderScreenerParams(){
  if(!_scrParams){loadScreenerParams();return;}
  var sections = ['azioni','etf','fondi'];
  var inputStyle = 'width:100%;background:rgba(0,0,0,.3);border:1px solid rgba(255,255,255,.15);border-radius:6px;padding:.4rem .6rem;color:#e0e0e0;font-size:.9rem;margin-top:.3rem;outline:none';
  var html = '';
  sections.forEach(function(asset){
    var params = _scrParams[asset];
    if(!params) return;
    html += '<div style="margin-bottom:1.4rem">'
          + '<h4 style="margin:0 0 .6rem;opacity:.7">'+ICONS[asset]+' '+asset.toUpperCase()+'</h4>'
          + '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:.7rem">';
    Object.keys(params).forEach(function(key){
      var p = params[key];
      var label = SP_LABELS[key] || key;
      if(typeof p.value === 'boolean'){
        html += '<div style="background:rgba(255,255,255,.04);border-radius:8px;padding:.7rem .9rem;display:flex;align-items:center">'
              + '<label style="display:flex;align-items:center;gap:.6rem;cursor:pointer;width:100%">'
              + '<input type="checkbox" class="sp-inp" data-asset="'+asset+'" data-param="'+key+'"'+(p.value?' checked':'')
              + ' style="width:1.1rem;height:1.1rem;accent-color:#F6AD55;cursor:pointer">'
              + '<span style="font-size:.88rem">'+label+'</span></label></div>';
      } else {
        var step = SP_STEP[key] || 0.05;
        var rangeInfo = (p.min!==undefined) ? '<div style="font-size:.68rem;opacity:.38;margin-top:.2rem">min: '+p.min+' — max: '+p.max+'</div>' : '';
        html += '<div style="background:rgba(255,255,255,.04);border-radius:8px;padding:.7rem .9rem">'
              + '<div style="font-size:.82rem;opacity:.6;margin-bottom:.3rem">'+label+'</div>'
              + '<input type="number" class="sp-inp" data-asset="'+asset+'" data-param="'+key+'"'
              + ' min="'+(p.min!==undefined?p.min:'')+'" max="'+(p.max!==undefined?p.max:'')+'"'
              + ' step="'+step+'" value="'+p.value+'" style="'+inputStyle+'">'
              + rangeInfo+'</div>';
      }
    });
    html += '</div></div>';
  });
  var el = document.getElementById('scr-params-content');
  el.innerHTML = html;
  el.style.opacity = '1';
}

function saveScreenerParams(){
  if(!_scrParams)return;
  var data = JSON.parse(JSON.stringify(_scrParams));
  document.querySelectorAll('#scr-params-content .sp-inp').forEach(function(inp){
    var asset=inp.dataset.asset, key=inp.dataset.param;
    if(!data[asset]||!data[asset][key]) return;
    if(inp.type==='checkbox'){
      data[asset][key].value = inp.checked;
    } else {
      data[asset][key].value = parseFloat(inp.value);
    }
  });
  data.meta = {last_modified: new Date().toISOString(), modified_by:'admin', version:'1.0'};
  fetch('/api/params',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})
    .then(function(r){return r.json();}).then(function(res){
      if(res.ok){_scrParams=data; showMsg('sp-msg','✅ Parametri screener salvati','ok');}
      else showMsg('sp-msg','❌ '+res.msg,'err');
    }).catch(function(e){showMsg('sp-msg','❌ '+e.message,'err');});
}

// ═══════════════════════════════════════════════
// CLOCK
// ═══════════════════════════════════════════════
function tick(){
  var n=new Date();
  document.getElementById('clock').textContent=n.toLocaleString('it-IT',{weekday:'short',day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'});
}
setInterval(tick,1000); tick();

// ═══════════════════════════════════════════════
// TABS
// ═══════════════════════════════════════════════
function switchTab(el,id){
  document.querySelectorAll('.panel').forEach(function(p){p.classList.remove('active')});
  document.querySelectorAll('.tab').forEach(function(t){t.classList.remove('active')});
  document.getElementById(id).classList.add('active');
  el.classList.add('active');
  if(!_loaded[id]){
    _loaded[id]=true;
    if(id==='azioni'||id==='etf'||id==='fondi') loadTable(id);
    if(id==='servizi'||id==='parametri'){if(!_sv) loadServizi();}
    if(id==='parametri'){if(!_scrParams) loadScreenerParams(); if(!_scoring) loadScoring();}
    if(id==='crm'){if(!_clienti) loadClienti();}
    if(id==='database') loadDatabase();
    if(id==='kb') loadKbFiles();
    if(id==='settori') loadSettori(false);
    if(id==='analytics') renderAnalytics();
  }
}

function renderAnalytics() {
  var el = document.getElementById('analytics-content');
  if(!el) return;
  el.innerHTML = '<div style="opacity:.5;padding:2rem;text-align:center">Caricamento...</div>';
  fetch('/api/analytics').then(function(r){return r.json();}).then(function(d){
    var fmt = function(n){ return Math.round(n).toLocaleString('it-IT'); };
    var eur = function(n){ return '€ ' + fmt(n); };
    var html = '<div class="kpi-row">'
      +'<div class="kpi"><div class="kpi-label">MRR</div><div class="kpi-val" style="color:#68D391">'+eur(d.mrr)+'</div><div class="kpi-sub">ricavi mensili ricorrenti</div></div>'
      +'<div class="kpi"><div class="kpi-label">ARR</div><div class="kpi-val" style="color:#68D391">'+eur(d.arr)+'</div><div class="kpi-sub">proiezione annuale</div></div>'
      +'<div class="kpi"><div class="kpi-label">ARPU</div><div class="kpi-val">'+eur(d.arpu)+'</div><div class="kpi-sub">ricavo medio/cliente/mese</div></div>'
      +'<div class="kpi"><div class="kpi-label">LTV</div><div class="kpi-val">'+eur(d.ltv)+'</div><div class="kpi-sub">'+(d.churn_rate===0?'stimato 24 mesi':'churn '+d.churn_rate+'%')+'</div></div>'
      +'</div>'
      +'<div class="kpi-row">'
      +'<div class="kpi"><div class="kpi-label">Clienti ATTIVI</div><div class="kpi-val" style="color:#68D391">'+d.n_attivi+'</div><div class="kpi-sub">abbonati paganti</div></div>'
      +'<div class="kpi"><div class="kpi-label">TESTER</div><div class="kpi-val" style="color:#F6AD55">'+d.n_tester+'</div><div class="kpi-sub">trial in corso</div></div>'
      +'<div class="kpi"><div class="kpi-label">Churn Rate</div><div class="kpi-val" style="color:'+(d.churn_rate===0?'#68D391':'#ef4444')+'">'+d.churn_rate+'%</div><div class="kpi-sub">'+(d.n_sospesi+d.n_scaduti)+' persi / '+(d.n_attivi+d.n_sospesi+d.n_scaduti)+' totali</div></div>'
      +'<div class="kpi"><div class="kpi-label">Ricavi Cumulativi</div><div class="kpi-val">'+eur(d.cumulative)+'</div><div class="kpi-sub">da inizio attività</div></div>'
      +'</div>';
    html += '<div class="box" style="margin-bottom:1rem">'
      +'<h3 style="color:#F6AD55;margin-bottom:1.2rem">Funnel Clienti</h3>'
      +'<div style="display:flex;flex-direction:column;gap:.6rem">';
    var steps = [
      {label:'Da Contattare', n:d.n_da_cont, color:'rgba(255,255,255,.2)'},
      {label:'Prospect LinkedIn', n:d.n_linkedin, color:'rgba(96,165,250,.6)'},
      {label:'TESTER (trial)', n:d.n_tester, color:'rgba(246,173,85,.6)'},
      {label:'ATTIVI (paganti)', n:d.n_attivi, color:'rgba(104,211,145,.8)'}
    ];
    var maxN = d.n_da_cont + d.n_linkedin || 1;
    steps.forEach(function(s){
      var pct = Math.max(4, Math.round(s.n / maxN * 100));
      html += '<div style="display:flex;align-items:center;gap:.75rem">'
        +'<div style="width:150px;font-size:.78rem;color:rgba(255,255,255,.6);text-align:right;flex-shrink:0">'+s.label+'</div>'
        +'<div style="flex:1;background:rgba(255,255,255,.05);border-radius:4px;height:26px">'
        +'<div style="width:'+pct+'%;background:'+s.color+';border-radius:4px;height:100%;display:flex;align-items:center;padding:0 .5rem;font-size:.78rem;font-weight:700">'+s.n.toLocaleString('it-IT')+'</div>'
        +'</div></div>';
    });
    html += '</div></div>';
    html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem">';
    html += '<div class="box"><h3 style="color:#F6AD55;margin-bottom:1rem">Dettaglio Abbonamenti</h3>';
    if(d.mrr_breakdown && d.mrr_breakdown.length > 0){
      html += '<table style="width:100%;border-collapse:collapse;font-size:.82rem">'
        +'<thead><tr style="border-bottom:1px solid rgba(255,255,255,.1);color:rgba(255,255,255,.4);font-size:.72rem;text-transform:uppercase">'
        +'<th style="text-align:left;padding:.4rem .5rem">Servizio</th><th style="text-align:left;padding:.4rem .5rem">Piano</th><th style="text-align:right;padding:.4rem .5rem">€/mese</th>'
        +'</tr></thead><tbody>';
      d.mrr_breakdown.forEach(function(r){
        html += '<tr style="border-bottom:1px solid rgba(255,255,255,.05)">'
          +'<td style="padding:.4rem .5rem;color:#e0e0e0">'+r.servizio+'</td>'
          +'<td style="padding:.4rem .5rem"><span style="background:rgba(246,173,85,.12);color:#F6AD55;border-radius:4px;padding:.1rem .4rem;font-size:.72rem">'+r.piano+'</span></td>'
          +'<td style="padding:.4rem .5rem;text-align:right;color:#68D391;font-weight:700">€ '+r.importo+'</td>'
          +'</tr>';
      });
      html += '<tr style="border-top:1px solid rgba(255,255,255,.15)">'
        +'<td colspan="2" style="padding:.5rem;font-weight:700;color:#F6AD55">TOTALE MRR</td>'
        +'<td style="padding:.5rem;text-align:right;font-weight:700;color:#68D391;font-size:1rem">'+eur(d.mrr)+'</td>'
        +'</tr></tbody></table>';
    } else {
      html += '<div style="opacity:.5;font-size:.85rem">Nessun abbonamento attivo — MRR € 0</div>';
    }
    html += '</div>';
    html += '<div class="box"><h3 style="color:#F6AD55;margin-bottom:.8rem">Scenari di Crescita</h3>'
      +'<div style="font-size:.74rem;color:rgba(255,255,255,.4);margin-bottom:.8rem">'+d.n_prospect.toLocaleString('it-IT')+' prospect × ARPU € '+Math.round(d.arpu||60)+'/mese</div>';
    d.scenari.forEach(function(s){
      var barW = Math.min(100, Math.round(s.conv / 5 * 100));
      html += '<div style="margin-bottom:.8rem">'
        +'<div style="display:flex;justify-content:space-between;margin-bottom:.2rem">'
        +'<span style="font-size:.8rem;color:'+s.color+'">'+s.label+' ('+s.conv+'%)</span>'
        +'<span style="font-size:.8rem;font-weight:700;color:'+s.color+'">'+eur(s.mrr)+'/mese</span>'
        +'</div>'
        +'<div style="background:rgba(255,255,255,.05);border-radius:4px;height:6px">'
        +'<div style="width:'+barW+'%;background:'+s.color+';border-radius:4px;height:100%"></div>'
        +'</div>'
        +'<div style="font-size:.7rem;color:rgba(255,255,255,.35);margin-top:.15rem">'+s.n+' abbonati · profitto netto ~'+eur(s.mrr-58)+'/mese</div>'
        +'</div>';
    });
    html += '<div style="border-top:1px solid rgba(255,255,255,.08);padding-top:.6rem;font-size:.74rem;color:rgba(255,255,255,.35)">Break-even: 1 abbonato (costi fissi ~€ 58/mese)</div>';
    html += '</div></div>';
    el.innerHTML = html;
  }).catch(function(e){
    el.innerHTML = '<div class="box"><p style="color:#ef4444">Errore analytics: '+e+'</p></div>';
  });
}

// ═══════════════════════════════════════════════
// SCORING WEIGHTS — Pesi Score Bontà
// ═══════════════════════════════════════════════
var _scoring  = null;
var _scDef    = null;   // defaults dal server
var _scAsset  = 'azioni';
var _scPlan   = 'BASIC';

var _scDirs = {
  'Dividend Yield': true, 'P/B': false, 'ROE': true, 'Var_1D_%': true,
  'EV/FCF': false, 'Net Debt/EBITDA': false,
  'Perf 3M %': true, 'Performance 1Y': true, 'TER': false, 'Sharpe Ratio': true
};
var _scLabels = {
  'Var_1D_%': 'Var 1D %', 'Performance 1Y': 'Perf 1Y %',
  'Perf 3M %': 'Perf 3M %', 'Sharpe Ratio': 'Sharpe', 'Net Debt/EBITDA': 'Net Debt/EBITDA'
};

function loadScoring(){
  fetch('/api/parametri/scoring').then(function(r){return r.json();}).then(function(d){
    _scoring = d.weights;
    _scDef   = d.defaults;
    renderScoringUI();
  }).catch(function(e){ document.getElementById('sc-metrics').textContent='Errore: '+e.message; });
}

function renderScoringUI(){
  if(!_scoring) return;
  var weights = ((_scoring[_scAsset]||{})[_scPlan]) || {};
  var html = '<table style="width:100%;border-collapse:collapse">';
  html += '<tr style="font-size:.72rem;opacity:.4;text-transform:uppercase">'
    + '<td style="padding:.2rem 0;width:160px">Metrica</td>'
    + '<td style="width:120px">Direzione</td>'
    + '<td style="width:80px;text-align:right">Peso %</td>'
    + '<td>Barra</td></tr>';
  Object.keys(weights).forEach(function(metric){
    var val = parseFloat(weights[metric]) || 0;
    var hib = _scDirs[metric];
    var dirLabel = hib ? '▲ alto' : '▼ basso';
    var dirColor = hib ? '#68D391' : '#F6AD55';
    var barColor = val > 0 ? dirColor : 'rgba(255,255,255,.08)';
    var metricId = 'sc_' + metric.replace(/[^a-zA-Z0-9]/g,'_');
    var label = _scLabels[metric] || metric;
    html += '<tr style="border-bottom:1px solid rgba(255,255,255,.05)">'
      + '<td style="padding:.45rem 0;font-size:.84rem">' + label + '</td>'
      + '<td style="font-size:.72rem;color:' + dirColor + '">' + dirLabel + ' = meglio</td>'
      + '<td style="text-align:right;padding-right:.6rem">'
      + '<input type="number" id="' + metricId + '" min="0" max="100" step="1" value="' + val + '" '
      + 'oninput="_scUpdate(\'' + metric + '\',this.value)" '
      + 'style="width:64px;text-align:right;background:#1a2e4a;border:1px solid rgba(255,255,255,.18);'
      + 'border-radius:4px;color:#e2e8f0;padding:.28rem .4rem;font-size:.88rem">'
      + '</td>'
      + '<td style="padding-left:.5rem">'
      + '<div style="position:relative;height:7px;background:rgba(255,255,255,.08);border-radius:4px;min-width:80px">'
      + '<div id="' + metricId + '_bar" style="position:absolute;left:0;top:0;height:100%;border-radius:4px;'
      + 'background:' + barColor + ';width:' + Math.min(val,100) + '%"></div>'
      + '</div></td></tr>';
  });
  html += '</table>';
  document.getElementById('sc-metrics').innerHTML = html;
  _scUpdateTotal();
}

function _scUpdate(metric, value){
  if(!_scoring[_scAsset]) _scoring[_scAsset] = {};
  if(!_scoring[_scAsset][_scPlan]) _scoring[_scAsset][_scPlan] = {};
  var v = parseFloat(value) || 0;
  _scoring[_scAsset][_scPlan][metric] = v;
  var hib = _scDirs[metric];
  var barColor = v > 0 ? (hib ? '#68D391' : '#F6AD55') : 'rgba(255,255,255,.08)';
  var barId = 'sc_' + metric.replace(/[^a-zA-Z0-9]/g,'_') + '_bar';
  var bar = document.getElementById(barId);
  if(bar){ bar.style.width = Math.min(v,100)+'%'; bar.style.background = barColor; }
  _scUpdateTotal();
}

function _scUpdateTotal(){
  var weights = ((_scoring[_scAsset]||{})[_scPlan]) || {};
  var total = Object.values(weights).reduce(function(a,b){ return a+(parseFloat(b)||0); }, 0);
  var ok = Math.abs(total-100) < 0.5;
  document.getElementById('sc-total').innerHTML =
    'Totale: <span style="color:'+(ok?'#68D391':'#FC8181')+';font-size:1rem">'+total.toFixed(0)+'%</span>'
    +(ok?' ✓':' &nbsp;← deve essere 100%');
}

function switchScAsset(btn, asset){
  document.querySelectorAll('.sc-asset-tab').forEach(function(b){b.classList.remove('active');});
  btn.classList.add('active');
  _scAsset = asset;
  renderScoringUI();
}

function switchScPlan(btn, plan){
  document.querySelectorAll('.sc-plan-tab').forEach(function(b){b.classList.remove('active');});
  btn.classList.add('active');
  _scPlan = plan;
  renderScoringUI();
}

function saveScoring(){
  var weights = ((_scoring[_scAsset]||{})[_scPlan]) || {};
  var total = Object.values(weights).reduce(function(a,b){ return a+(parseFloat(b)||0); }, 0);
  if(Math.abs(total-100) >= 1){
    showMsg('sc-msg','I pesi devono sommare a 100%',false); return;
  }
  fetch('/api/parametri/scoring',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({weights:_scoring})
  }).then(function(r){return r.json();}).then(function(d){
    showMsg('sc-msg', d.ok ? 'Pesi salvati ✓' : ('Errore: '+(d.msg||'')), d.ok);
  });
}

function resetScoringDefaults(){
  if(!_scDef) return;
  _scoring = JSON.parse(JSON.stringify(_scDef));
  renderScoringUI();
  showMsg('sc-msg','Default ripristinati (premi 💾 per salvare)',true);
}

// ═══════════════════════════════════════════════
// DATABASE — elenco completo ticker
// ═══════════════════════════════════════════════
var _dbData  = null;
var _dbCache = {};
var _dbAsset = 'azioni';   // asset corrente (senza prefisso 'db-')

// Colonne draggabili (esclusi # e Ticker che sono fissi)
var _dbColDefs = {
  azioni: ['Nome', 'Prezzo', 'Var %', 'Gruppo / Mercato'],
  etf:    ['Nome', 'Prezzo', 'Var %', 'Gruppo / Mercato'],
  fondi:  ['Nome', 'Prezzo', 'Var %', 'Famiglia / Gestore'],
};
var _dbCols = {};        // asset → ordine corrente colonne (array di stringhe)
var _dbSortState = {};   // asset → {col: null|idx, dir: -1|1}

function _dbGetCols(asset){
  if(!_dbCols[asset]){
    var def = (_dbColDefs[asset] || []).slice();
    try{
      var s = localStorage.getItem('dbcols_'+asset);
      if(s){
        var p = JSON.parse(s);
        if(p.length === def.length && p.every(function(c){ return def.indexOf(c) >= 0; })) def = p;
      }
    }catch(e){}
    _dbCols[asset] = def;
  }
  return _dbCols[asset];
}

function _fmtVar(v){
  if(v===null||v===undefined) return '<span style="opacity:.3">—</span>';
  var c = v>=0 ? '#68D391' : '#FC8181';
  var s = v>=0 ? '+' : '';
  return '<span style="color:'+c+';font-weight:600">'+s+v.toFixed(2)+'%</span>';
}

function _renderDbHead(asset){
  var thead = document.getElementById('db-head-'+asset);
  if(!thead) return;
  var cols = _dbGetCols(asset);
  if(!_dbSortState[asset]) _dbSortState[asset] = {col: null, dir: -1};
  var ss = _dbSortState[asset];
  var h = '<tr><th style="width:3rem;text-align:right;opacity:.4">#</th><th>Ticker</th>';
  cols.forEach(function(c, i){
    var st = '';
    if(c==='Prezzo') st=' style="width:6rem;text-align:right"';
    if(c==='Var %')  st=' style="width:5.5rem;text-align:right"';
    var cls = 'sortable';
    if(ss.col === i) cls += (ss.dir === -1 ? ' sorted-desc' : ' sorted-asc');
    h += '<th class="'+cls+'" draggable="true"'+st
      +' onclick="if(this._skipNextClick){this._skipNextClick=false;return;}_sortDbTable(\''+asset+'\','+i+')"'
      +' ondragstart="_dbColDragStart(\''+asset+'\','+i+',this)"'
      +' ondragend="_colDragEnd(this)"'
      +' ondragover="_colDragOver(event,this)"'
      +' ondragleave="_colDragLeave(this)"'
      +' ondrop="_dbColDrop(\''+asset+'\','+i+',event)"'
      +' title="Clicca per ordinare · Trascina per spostare la colonna">'+c+'</th>';
  });
  h += '</tr>';
  thead.innerHTML = h;
}

function loadDatabase(){
  fetch('/api/database').then(function(r){return r.json();}).then(function(d){
    _dbData  = d;
    _dbCache = d.cache || {};
    var tot = d.totali;
    var azioni_at = d.cache_azioni_at ? ' · dati '+d.cache_azioni_at.slice(0,10) : '';
    document.getElementById('db-totali').textContent =
      tot.azioni+' Azioni · '+tot.etf+' ETF · '+tot.fondi+' Fondi = '+(tot.azioni+tot.etf+tot.fondi)+' totali'+azioni_at;
    document.getElementById('dbtab-azioni').textContent = '📈 Azioni ('+tot.azioni+')';
    document.getElementById('dbtab-etf').textContent   = '📦 ETF ('+tot.etf+')';
    document.getElementById('dbtab-fondi').textContent = '🏦 Fondi ('+tot.fondi+')';
    renderDbBody('azioni', d.azioni);
    renderDbBody('etf',    d.etf);
    renderDbBody('fondi',  d.fondi);
    updateDbCount();
  }).catch(function(e){ document.getElementById('db-totali').textContent='Errore: '+e.message; });
}

// Restituisce true se il ticker è un ISIN puro (2 lettere + 10 alfanumerici)
// Gli ISIN non hanno una pagina Yahoo Finance e non sono fetchabili da yfinance
function _isIsin(ticker){
  return /^[A-Z]{2}[0-9A-Z]{10}$/.test(ticker);
}

function renderDbBody(asset, rows){
  _renderDbHead(asset);
  var tbody = document.getElementById('db-body-'+asset);
  var cache = _dbCache[asset] || {};
  var cols  = _dbGetCols(asset);
  var ss    = _dbSortState[asset] || {col: null, dir: -1};
  // Ordina se selezionata una colonna
  var sortedRows = rows.slice();
  if(ss.col !== null){
    var sortCol = cols[ss.col];
    sortedRows.sort(function(a, b){
      var ca = cache[a.ticker] || {};
      var cb = cache[b.ticker] || {};
      var va, vb;
      if(sortCol === 'Nome')       { va = ca.name || ''; vb = cb.name || ''; }
      else if(sortCol === 'Prezzo'){ va = ca.price;      vb = cb.price; }
      else if(sortCol === 'Var %') { va = ca.change_pct; vb = cb.change_pct; }
      else                         { va = a.gruppo;      vb = b.gruppo; }
      var aNull = (va === null || va === undefined || va === '');
      var bNull = (vb === null || vb === undefined || vb === '');
      if(aNull && bNull) return 0;
      if(aNull) return 1;
      if(bNull) return -1;
      if(typeof va === 'number' && typeof vb === 'number') return (va - vb) * ss.dir;
      return String(va).localeCompare(String(vb), 'it', {numeric: true}) * ss.dir;
    });
  }
  var html  = '';
  sortedRows.forEach(function(r, i){
    var isIsin = _isIsin(r.ticker);
    var tid = 'db-'+asset+'-'+r.ticker.replace(/\./g,'_');
    var cd  = cache[r.ticker] || {};
    // Costruisce mappa colonna → cella HTML
    var cells = {};
    if(isIsin){
      // ISIN puro: non fetchabile da yfinance, niente dati live
      cells['Nome']   = '<span style="font-size:.82rem;color:#718096;font-style:italic">ISIN — nessun ticker YF</span>';
      cells['Prezzo'] = '<span id="'+tid+'-price" style="font-size:.82rem;opacity:.3">—</span>';
      cells['Var %']  = '<span id="'+tid+'-var" style="opacity:.3">—</span>';
    } else {
      cells['Nome'] = cd.name
        ? '<span style="font-size:.82rem;color:#90cdf4">'+cd.name+'</span>'
        : '<span id="'+tid+'-nome" style="font-size:.82rem;color:#90cdf4">—</span>';
      cells['Prezzo'] = (cd.price !== null && cd.price !== undefined)
        ? '<span id="'+tid+'-price" style="font-size:.82rem;font-variant-numeric:tabular-nums">'+cd.price+(cd.currency?' '+cd.currency:'')+'</span>'
        : '<span id="'+tid+'-price" style="font-size:.82rem;opacity:.3">—</span>';
      cells['Var %'] = (cd.change_pct !== null && cd.change_pct !== undefined)
        ? '<span id="'+tid+'-var">'+_fmtVar(cd.change_pct)+'</span>'
        : '<span id="'+tid+'-var" style="opacity:.3">—</span>';
    }
    // Colonna gruppo (il nome varia tra azioni/etf e fondi)
    cols.forEach(function(c){
      if(!(c in cells)) cells[c] = '<span class="db-group">'+r.gruppo+'</span>';
    });
    if(isIsin){
      // Riga ISIN: non cliccabile per caricare dati, link JustETF
      var jtUrl = 'https://www.justetf.com/en/etf-profile.html?isin='+encodeURIComponent(r.ticker);
      html += '<tr data-ticker="'+r.ticker.toLowerCase()+'" data-gruppo="'+r.gruppo.toLowerCase()+'" style="opacity:.6" title="ISIN senza ticker Yahoo Finance — dati non disponibili">';
      html += '<td style="text-align:right;opacity:.35;font-size:.75rem;padding-right:.6rem">'+(i+1)+'</td>';
      html += '<td onclick="event.stopPropagation()" style="white-space:nowrap">'
            + '<a href="'+jtUrl+'" target="_blank" class="btn-yf" style="font-family:monospace;font-size:.82rem;background:#68D391;color:#1a202c" title="Apri su JustETF">'+r.ticker+'</a>'
            + ' <button onclick="event.stopPropagation();_removeTicker(\''+asset+'\',\''+r.ticker+'\')" '
            + 'style="background:rgba(239,68,68,.18);border:1px solid rgba(239,68,68,.35);color:#fca5a5;font-size:.75rem;cursor:pointer;border-radius:3px;padding:.05rem .3rem;line-height:1" '
            + 'title="Elimina ticker dalle liste">✕</button></td>';
    } else {
      // Riga normale: link Yahoo Finance, click per caricare dati
      var yf = 'https://finance.yahoo.com/quote/'+encodeURIComponent(r.ticker);
      html += '<tr data-ticker="'+r.ticker.toLowerCase()+'" data-gruppo="'+r.gruppo.toLowerCase()+'" style="cursor:pointer" onclick="_loadRowPrice(\''+asset+'\',\''+r.ticker+'\')" title="Clicca per caricare Nome/Prezzo/Var%">';
      html += '<td style="text-align:right;opacity:.35;font-size:.75rem;padding-right:.6rem">'+(i+1)+'</td>';
      html += '<td onclick="event.stopPropagation()" style="white-space:nowrap">'
            + '<a href="'+yf+'" target="_blank" class="btn-yf" style="font-family:monospace;font-size:.82rem" title="Apri su Yahoo Finance">'+r.ticker+'</a>'
            + ' <button onclick="event.stopPropagation();_removeTicker(\''+asset+'\',\''+r.ticker+'\')" '
            + 'style="background:rgba(239,68,68,.18);border:1px solid rgba(239,68,68,.35);color:#fca5a5;font-size:.75rem;cursor:pointer;border-radius:3px;padding:.05rem .3rem;line-height:1" '
            + 'title="Elimina ticker dalle liste">✕</button></td>';
    }
    cols.forEach(function(c){
      var st = (c==='Prezzo'||c==='Var %') ? ' style="text-align:right"' : '';
      html += '<td'+st+'>'+cells[c]+'</td>';
    });
    html += '</tr>';
  });
  tbody.innerHTML = html;
  _updateMissingCount();
}

// ─── Carica dati su clic riga ─────────────────────────────────
var _rowLoadingSet = new Set();

function _loadRowPrice(asset, ticker){
  var tid = 'db-'+asset+'-'+ticker.replace(/\./g,'_');
  var ne = document.getElementById(tid+'-nome');
  var pe = document.getElementById(tid+'-price');
  var ve = document.getElementById(tid+'-var');
  // già caricato o in corso
  if(!ne && !pe) return;
  if(_rowLoadingSet.has(ticker)) return;
  // dati già presenti (nome != '—')
  if(ne && ne.textContent && ne.textContent !== '—') return;
  _rowLoadingSet.add(ticker);
  // evidenzia riga in caricamento
  var tid = 'db-'+asset+'-'+ticker.replace(/\./g,'_');
  var row = ne ? ne.closest('tr') : null;
  if(row) row.style.background = 'rgba(99,179,237,.12)';
  if(ne) ne.innerHTML = '<span style="color:#90cdf4;opacity:.7;font-style:italic">caricamento…</span>';
  fetch('/api/database/lookup?t='+encodeURIComponent(ticker)).then(function(r){return r.json();}).then(function(data){
    var d = data[ticker.toUpperCase()] || {};
    if(ne) ne.textContent = d.name || '—';
    if(pe){
      if(d.price && d.price !== '—'){
        pe.textContent = d.price+(d.currency ? ' '+d.currency : '');
        pe.style.color = '#68D391';
        pe.style.opacity = '1';
      } else { pe.textContent = '—'; }
    }
    if(ve) ve.innerHTML = _fmtVar(d.change_pct !== undefined ? d.change_pct : null);
    if(!_dbCache[asset]) _dbCache[asset] = {};
    _dbCache[asset][ticker.toUpperCase()] = d;
    if(row){ row.style.background = 'rgba(72,187,120,.08)'; setTimeout(function(){ row.style.background=''; }, 1200); }
  }).catch(function(){
    if(ne) ne.textContent = '—';
    if(row) row.style.background = '';
  }).finally(function(){
    _rowLoadingSet.delete(ticker);
  });
}

// ─── Elimina ticker dal Database ──────────────────────────────
function _removeTicker(asset, ticker){
  if(!confirm('Eliminare ' + ticker + ' dalle liste permanentemente?')) return;
  fetch('/api/database/remove', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ticker: ticker})
  }).then(function(r){ return r.json(); }).then(function(d){
    if(d.ok){
      // Rimuovi la riga dalla tabella
      var tbody = document.getElementById('db-body-'+asset);
      if(tbody){
        var rows = tbody.querySelectorAll('tr');
        rows.forEach(function(row){
          if(row.dataset.ticker === ticker.toLowerCase()) row.remove();
        });
      }
      // Aggiorna contatore
      if(_dbData && _dbData[asset]){
        _dbData[asset] = _dbData[asset].filter(function(r){ return r.ticker !== ticker; });
        var tot = _dbData.totali;
        tot[asset] = (_dbData[asset]||[]).length;
        document.getElementById('db-totali').textContent =
          tot.azioni+' Azioni · '+tot.etf+' ETF · '+tot.fondi+' Fondi = '+(tot.azioni+tot.etf+tot.fondi)+' totali';
        document.getElementById('dbtab-azioni').textContent = '📈 Azioni ('+tot.azioni+')';
        document.getElementById('dbtab-etf').textContent   = '📦 ETF ('+tot.etf+')';
        document.getElementById('dbtab-fondi').textContent = '🏦 Fondi ('+tot.fondi+')';
      }
      filterDb();
    } else {
      alert('Errore: ' + d.msg);
    }
  }).catch(function(e){ alert('Errore di rete: '+e.message); });
}

// ─── Drag & drop colonne DATABASE ─────────────────────────────
var _dbDragIdx   = null;
var _dbDragAsset = null;

function _dbColDragStart(asset, idx, el){
  _dbDragIdx   = idx;
  _dbDragAsset = asset;
  el.style.opacity = '.45';
  el._skipNextClick = true;
}

function _dbColDrop(asset, targetIdx, event){
  event.preventDefault();
  document.querySelectorAll('#db-head-'+asset+' th').forEach(function(th){ th.classList.remove('col-drag-over'); });
  if(_dbDragAsset !== asset || _dbDragIdx === null || _dbDragIdx === targetIdx){ _dbDragIdx=null; return; }
  var cols  = _dbGetCols(asset);
  var moved = cols.splice(_dbDragIdx, 1)[0];
  cols.splice(targetIdx, 0, moved);
  _dbDragIdx = null;
  if(_dbData) renderDbBody(asset, _dbData[asset]);
  try{ localStorage.setItem('dbcols_'+asset, JSON.stringify(cols)); }catch(e){}
}

function _resetDbCols(asset){
  try{ localStorage.removeItem('dbcols_'+asset); }catch(e){}
  delete _dbCols[asset];
  if(_dbData) renderDbBody(asset, _dbData[asset]);
}

function _sortDbTable(asset, colIdx){
  if(!_dbSortState[asset]) _dbSortState[asset] = {col: null, dir: -1};
  var ss = _dbSortState[asset];
  if(ss.col === colIdx){
    ss.dir = -ss.dir;
  } else {
    ss.col = colIdx;
    ss.dir = -1;
  }
  if(_dbData) renderDbBody(asset, _dbData[asset]);
}

function switchDbTab(el, panelId){
  document.querySelectorAll('.db-tab').forEach(function(t){t.classList.remove('active');});
  document.querySelectorAll('.db-panel').forEach(function(p){p.classList.remove('active');});
  el.classList.add('active');
  document.getElementById(panelId).classList.add('active');
  _dbAsset = panelId.replace('db-','');
  document.getElementById('db-search').value = '';
  updateDbCount();
  filterDb();
  _updateMissingCount();
}

function filterDb(){
  var q = (document.getElementById('db-search').value||'').toLowerCase().trim();
  var tbody = document.getElementById('db-body-'+_dbAsset);
  if(!tbody) return;
  var rows = tbody.querySelectorAll('tr');
  var vis = 0;
  rows.forEach(function(row){
    var ok = !q || row.dataset.ticker.indexOf(q)>=0 || row.dataset.gruppo.indexOf(q)>=0;
    row.style.display = ok ? '' : 'none';
    if(ok) vis++;
  });
  var tot = rows.length;
  document.getElementById('db-count').textContent =
    q ? vis+' di '+tot+' risultati per "'+q+'"' : tot+' ticker';
  var btn = document.getElementById('db-load-btn');
  if(btn) btn.textContent = '📊 Carica dati ('+vis+' visibili)';
}

function updateDbCount(){
  if(!_dbData) return;
  var asset = _dbAsset || 'azioni';
  var rows  = document.getElementById('db-body-'+asset);
  var vis   = rows ? rows.querySelectorAll('tr:not([style*="display: none"])').length : 0;
  var len   = (_dbData[asset]||[]).length;
  document.getElementById('db-count').textContent = len+' ticker';
  var btn = document.getElementById('db-load-btn');
  if(btn) btn.textContent = '📊 Carica dati ('+len+' visibili)';
}

function loadDbPrices(){
  var asset = _dbAsset || 'azioni';
  var tbody = document.getElementById('db-body-'+asset);
  if(!tbody) return;
  var visibleRows = [];
  tbody.querySelectorAll('tr').forEach(function(row){
    if(row.style.display !== 'none' && row.dataset.ticker){
      visibleRows.push(row);
    }
  });
  // Escludi righe ISIN puro (nessun dato Yahoo Finance disponibile)
  visibleRows = visibleRows.filter(function(row){ return !_isIsin(row.dataset.ticker.toUpperCase()); });
  if(!visibleRows.length){ alert('Nessun ticker visibile'); return; }
  if(visibleRows.length > 30){ visibleRows = visibleRows.slice(0,30); }
  var visible = visibleRows.map(function(r){ return r.dataset.ticker.toUpperCase(); });
  // evidenzia righe in caricamento
  visibleRows.forEach(function(row){
    row.style.background = 'rgba(99,179,237,.12)';
    var tid = 'db-'+asset+'-'+row.dataset.ticker.replace(/\./g,'_');
    var ne = document.getElementById(tid+'-nome');
    if(ne) ne.innerHTML = '<span style="color:#90cdf4;opacity:.7;font-style:italic">caricamento…</span>';
  });
  var btn = document.getElementById('db-load-btn');
  if(btn){ btn.textContent = '⏳ Caricamento...'; btn.disabled = true; }
  fetch('/api/database/lookup?t='+encodeURIComponent(visible.join(','))).then(function(r){return r.json();}).then(function(data){
    visibleRows.forEach(function(row){
      var t   = row.dataset.ticker.toUpperCase();
      var d   = data[t] || {};
      var tid = 'db-'+asset+'-'+t.replace(/\./g,'_');
      var ne  = document.getElementById(tid+'-nome');
      var pe  = document.getElementById(tid+'-price');
      var ve  = document.getElementById(tid+'-var');
      if(ne) ne.textContent = d.name || '—';
      if(pe){
        if(d.price && d.price !== '—'){
          pe.textContent = d.price+(d.currency ? ' '+d.currency : '');
          pe.style.color = '#68D391';
          pe.style.opacity = '1';
        } else { pe.textContent = '—'; }
      }
      if(ve) ve.innerHTML = _fmtVar(d.change_pct !== undefined ? d.change_pct : null);
      row.style.background = 'rgba(72,187,120,.08)';
      setTimeout(function(){ row.style.background = ''; }, 1200);
    });
    if(btn){ btn.textContent = '✅ Dati caricati'; btn.disabled = false; }
  }).catch(function(e){
    visibleRows.forEach(function(row){ row.style.background = ''; });
    if(btn){ btn.textContent = '❌ Errore — riprova'; btn.disabled = false; }
    console.error(e);
  });
}

// ─── Conta e aggiorna badge dati mancanti ─────────────────────
function _updateMissingCount(){
  var asset = (_dbAsset || 'db-azioni').replace('db-','');
  var tbody = document.getElementById('db-body-'+asset);
  if(!tbody){ document.getElementById('db-missing-count').textContent = '0'; return; }
  var cache = _dbCache[asset] || {};
  var missing = 0;
  tbody.querySelectorAll('tr[data-ticker]').forEach(function(row){
    var t = row.dataset.ticker.toUpperCase();
    if(_isIsin(t)) return;
    var cd = cache[t];
    if(!cd || cd.price === null || cd.price === undefined) missing++;
  });
  document.getElementById('db-missing-count').textContent = missing;
}

// ─── Carica tutti i ticker con dati mancanti (batch 30) ────────
function loadMissingDbPrices(){
  var asset = (_dbAsset || 'db-azioni').replace('db-','');
  var tbody = document.getElementById('db-body-'+asset);
  if(!tbody) return;
  var cache = _dbCache[asset] || {};
  var toLoad = [];
  tbody.querySelectorAll('tr[data-ticker]').forEach(function(row){
    var t = row.dataset.ticker.toUpperCase();
    if(_isIsin(t)) return;
    var cd = cache[t];
    if(!cd || cd.price === null || cd.price === undefined) toLoad.push(t);
  });
  if(!toLoad.length){ alert('Nessun dato mancante nel tab corrente.'); return; }
  var btn = document.getElementById('db-missing-btn');
  btn.disabled = true;
  var total = toLoad.length;
  var done  = 0;
  var BATCH = 30;
  function _nextBatch(){
    if(!toLoad.length){
      btn.disabled = false;
      btn.innerHTML = '✅ Completato — <span id="db-missing-count">0</span>';
      _updateMissingCount();
      return;
    }
    var batch = toLoad.splice(0, BATCH);
    btn.innerHTML = '⏳ ' + done + '/' + total + ' — <span id="db-missing-count">...</span>';
    // evidenzia righe in caricamento
    batch.forEach(function(t){
      var tid = 'db-'+asset+'-'+t.replace(/\./g,'_');
      var ne = document.getElementById(tid+'-nome');
      if(ne) ne.innerHTML = '<span style="color:#90cdf4;opacity:.6;font-style:italic">…</span>';
    });
    fetch('/api/database/lookup?t='+encodeURIComponent(batch.join(','))).then(function(r){return r.json();}).then(function(data){
      if(!_dbCache[asset]) _dbCache[asset] = {};
      batch.forEach(function(t){
        var d   = data[t] || {};
        var tid = 'db-'+asset+'-'+t.replace(/\./g,'_');
        _dbCache[asset][t] = d;
        var ne = document.getElementById(tid+'-nome');
        var pe = document.getElementById(tid+'-price');
        var ve = document.getElementById(tid+'-var');
        if(ne) ne.textContent = d.name || '—';
        if(pe){
          pe.textContent = (d.price && d.price !== '—') ? d.price+(d.currency?' '+d.currency:'') : '—';
          if(d.price && d.price !== '—'){ pe.style.color='#68D391'; pe.style.opacity='1'; }
        }
        if(ve) ve.innerHTML = _fmtVar(d.change_pct !== undefined ? d.change_pct : null);
      });
      done += batch.length;
      _nextBatch();
    }).catch(function(){
      btn.disabled = false;
      btn.innerHTML = '❌ Errore — <span id="db-missing-count">'+toLoad.length+'</span>';
    });
  }
  _nextBatch();
}

// ─── Verifica ticker morti ────────────────────────────────────
function verifyDeadTickers(){
  var asset = (_dbAsset || 'db-azioni').replace('db-','');
  var tbody = document.getElementById('db-body-'+asset);
  if(!tbody){ alert('Carica prima il database.'); return; }
  var cache = _dbCache[asset] || {};

  // Raccoglie solo ticker senza prezzo (non ISIN)
  var toCheck = [];
  tbody.querySelectorAll('tr[data-ticker]').forEach(function(row){
    var t = row.dataset.ticker.toUpperCase();
    if(_isIsin(t)) return;
    var cd = cache[t];
    if(!cd || !cd.price || cd.price === '—') toCheck.push(t);
  });

  if(!toCheck.length){ alert('Nessun ticker vuoto nel tab corrente. Prima clicca "Aggiorna mancanti".'); return; }

  var btn = document.getElementById('db-dead-btn');
  btn.disabled = true;
  btn.textContent = '⏳ Verifica in corso ('+toCheck.length+' ticker)...';

  // Invia in un batch unico (max 100 lato server)
  fetch('/api/database/verify-dead', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({tickers: toCheck})
  }).then(function(r){ return r.json(); }).then(function(data){
    btn.disabled = false;
    btn.textContent = '☠️ Verifica ticker morti';
    _showDeadModal(asset, data.dead || [], data.uncertain || []);
  }).catch(function(e){
    btn.disabled = false;
    btn.textContent = '☠️ Verifica ticker morti';
    alert('Errore verifica: '+e);
  });
}

function _showDeadModal(asset, dead, uncertain){
  // Rimuovi modale precedente se esiste
  var old = document.getElementById('dead-modal');
  if(old) old.remove();

  var deadHtml = '';
  if(dead.length){
    deadHtml += '<div style="margin-bottom:.5rem;font-size:.82rem;color:#fca5a5;font-weight:600">☠️ Probabilmente morti ('+dead.length+') — nessuna risposta da Yahoo Finance</div>';
    deadHtml += '<div style="max-height:220px;overflow-y:auto;margin-bottom:1rem">';
    dead.forEach(function(t){
      deadHtml += '<label style="display:flex;align-items:center;gap:.5rem;padding:.25rem 0;cursor:pointer">'
        + '<input type="checkbox" class="dead-chk" value="'+t+'" checked style="accent-color:#FC8181">'
        + '<span style="font-family:monospace;font-size:.85rem;color:#fca5a5">'+t+'</span></label>';
    });
    deadHtml += '</div>';
  }

  var uncHtml = '';
  if(uncertain.length){
    uncHtml += '<div style="margin-bottom:.5rem;font-size:.82rem;color:#F6AD55;font-weight:600">⚠️ Incerti ('+uncertain.length+') — dati assenti ma ticker potrebbe esistere</div>';
    uncHtml += '<div style="max-height:140px;overflow-y:auto;margin-bottom:1rem">';
    uncertain.forEach(function(t){
      uncHtml += '<label style="display:flex;align-items:center;gap:.5rem;padding:.2rem 0;cursor:pointer">'
        + '<input type="checkbox" class="dead-chk" value="'+t+'" style="accent-color:#F6AD55">'
        + '<span style="font-family:monospace;font-size:.82rem;color:#aaa">'+t+'</span></label>';
    });
    uncHtml += '</div>';
  }

  if(!dead.length && !uncertain.length){
    alert('Nessun ticker morto trovato.'); return;
  }

  var modal = document.createElement('div');
  modal.id = 'dead-modal';
  modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:9000;display:flex;align-items:center;justify-content:center';
  modal.innerHTML = '<div style="background:#111827;border:1px solid rgba(239,68,68,.4);border-radius:14px;padding:1.8rem 2rem;width:100%;max-width:520px;max-height:85vh;overflow-y:auto">'
    + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.2rem">'
    + '<h3 style="color:#fca5a5;margin:0">☠️ Risultati verifica ticker</h3>'
    + '<button onclick="document.getElementById(\'dead-modal\').remove()" style="background:none;border:none;color:#666;font-size:1.3rem;cursor:pointer">✕</button></div>'
    + deadHtml + uncHtml
    + '<div style="display:flex;gap:.7rem;justify-content:flex-end;margin-top:.5rem">'
    + '<button onclick="document.getElementById(\'dead-modal\').remove()" style="padding:.5rem 1.2rem;background:transparent;border:1px solid rgba(255,255,255,.15);border-radius:7px;color:#aaa;cursor:pointer">Annulla</button>'
    + '<button onclick="_bulkRemoveDead(\''+asset+'\')" style="padding:.5rem 1.4rem;background:rgba(239,68,68,.25);border:1px solid rgba(239,68,68,.5);border-radius:7px;color:#fca5a5;font-weight:600;cursor:pointer">🗑️ Elimina selezionati</button>'
    + '</div></div>';
  document.body.appendChild(modal);
}

function _bulkRemoveDead(asset){
  var checked = Array.from(document.querySelectorAll('.dead-chk:checked')).map(function(c){ return c.value; });
  if(!checked.length){ alert('Nessun ticker selezionato.'); return; }
  if(!confirm('Eliminare '+checked.length+' ticker dalle liste? Operazione irreversibile.')) return;

  fetch('/api/database/remove-bulk', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({tickers: checked})
  }).then(function(r){ return r.json(); }).then(function(data){
    document.getElementById('dead-modal').remove();
    alert('✓ Eliminati '+data.removed+'/'+checked.length+' ticker. Ricarica il database per aggiornare la vista.');
    loadDatabase();
  }).catch(function(e){ alert('Errore eliminazione: '+e); });
}

// ═══════════════════════════════════════════════
// HOME — STATUS + KPI
// ═══════════════════════════════════════════════
function loadStatus(){
  fetch('/api/status').then(function(r){return r.json()}).then(function(d){
    var run=d._running||{};
    delete d._running;
    var html='';
    var pc={'BASIC':'#4A90D9','PRO':'#F6AD55','VALUE':'#68D391'};
    var assetOrder=['azioni','etf','fondi'];
    assetOrder.forEach(function(tipo){
      var info=d[tipo];
      var rs=run[tipo];
      var badge=rs?'<span class="rs rs-'+rs+'" style="font-size:.68rem">'+rs+'</span>':'';
      var pianiHtml='';
      if(info&&info.piani&&Object.keys(info.piani).length){
        ['BASIC','PRO','VALUE'].forEach(function(p){
          var pi=info.piani[p];
          if(pi){
            pianiHtml+='<span style="display:inline-flex;align-items:center;gap:.25rem;'
              +'background:'+pc[p]+'22;color:'+pc[p]+';border:1px solid '+pc[p]+'44;'
              +'border-radius:4px;padding:.1rem .45rem;font-size:.72rem;font-weight:700;margin-right:.3rem">'
              +p+' <span style="color:#ccc;font-weight:400">'+pi.count+'</span></span>';
          }
        });
      } else if(info&&info.count!==undefined){
        pianiHtml='<span style="color:#ccc;font-size:.85rem">'+info.count+' risultati</span>';
      }
      html+='<div class="kpi">'
           +'<div class="kpi-label">'+ICONS[tipo]+' '+tipo.toUpperCase()+' '+badge+'</div>'
           +'<div style="margin:.35rem 0 .2rem">'+( pianiHtml||'<span style="color:#555;font-size:.8rem">—</span>')+'</div>'
           +'<div class="kpi-sub">'+(info?info.time:'Nessun report')+'</div>'
           +'</div>';
      var btn=document.getElementById('run-'+tipo);
      if(btn){btn.disabled=rs==='running';if(rs!=='running')btn.textContent='▶ '+tipo.charAt(0).toUpperCase()+tipo.slice(1);}
    });
    // Revenue KPI
    var rev=0;
    if(_sv){
      ASSETS.forEach(function(a){TIERS.forEach(function(t){rev+=(_sv[a]&&_sv[a][t]?(_sv[a][t].prezzo||0):0);});});
    }
    html+='<div class="kpi"><div class="kpi-label">💰 Revenue Potenziale</div>'
         +'<div class="kpi-val" style="font-size:1.5rem">€'+rev+'</div>'
         +'<div class="kpi-sub">12 piani × 3 tier / mese</div></div>';
    document.getElementById('kpi-row').innerHTML=html;
  }).catch(function(){});
}

// ═══════════════════════════════════════════════
// RELOAD KB
// ═══════════════════════════════════════════════
function loadKBStatus(){
  fetch('/api/kb-status').then(function(r){return r.json();}).then(function(d){
    var el=document.getElementById('kb-status');
    if(el) el.innerHTML='<strong style="color:#68D391">✓ Attiva</strong>'
      +' &nbsp;·&nbsp; '+d.chars+' caratteri'
      +' &nbsp;·&nbsp; '+d.files+' file'
      +' &nbsp;·&nbsp; caricata alle '+d.loaded_at;
  }).catch(function(){});
}

function reloadKB(){
  var btn=document.getElementById('btn-reload-kb');
  var el=document.getElementById('kb-status');
  btn.disabled=true; btn.textContent='↺ Ricarico...';
  fetch('/api/reload-kb').then(function(r){return r.json();}).then(function(d){
    btn.disabled=false; btn.textContent='↺ Ricarica KB';
    if(d.ok){
      el.innerHTML='<strong style="color:#68D391">✓ Ricaricata</strong>'
        +' &nbsp;·&nbsp; '+d.chars+' caratteri'
        +' &nbsp;·&nbsp; '+d.files+' file'
        +' &nbsp;·&nbsp; aggiornata alle '+d.loaded_at;
    } else {
      el.innerHTML='<span style="color:#FC8181">Errore: '+d.error+'</span>';
    }
  }).catch(function(e){
    btn.disabled=false; btn.textContent='↺ Ricarica KB';
    if(el) el.innerHTML='<span style="color:#FC8181">Errore di rete</span>';
  });
}

// ═══════════════════════════════════════════════
// KB TAB
// ═══════════════════════════════════════════════
function loadKbFiles(){
  var grid = document.getElementById('kb-files-grid');
  var status = document.getElementById('kb-status-panel');
  fetch('/api/kb-files').then(function(r){return r.json();}).then(function(d){
    if(d.error){ grid.innerHTML='<div style="opacity:.5;grid-column:1/-1;text-align:center;padding:1.5rem">'+d.error+'</div>'; return; }
    var files = d.files || [];
    if(!files.length){ grid.innerHTML='<div style="opacity:.5;grid-column:1/-1;text-align:center;padding:1.5rem">Nessun file trovato</div>'; return; }
    var html='';
    files.forEach(function(f){
      var kb = f.name === 'kb_reports.md' ? '#E9D8FD' : '#C6F6D5';
      html += '<div style="background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:8px;padding:.9rem 1rem">'
        +'<div style="font-weight:600;font-size:.9rem;margin-bottom:.3rem">'+f.name+'</div>'
        +'<div style="font-size:.78rem;opacity:.7">'+_fmtBytes(f.size)
        +' &nbsp;·&nbsp; <span title="'+f.modified+'">'+f.modified_rel+'</span></div>'
        +'</div>';
    });
    grid.innerHTML = html;
    if(status) status.innerHTML = '<strong style="color:#68D391">✓ '+files.length+' file</strong> &nbsp;·&nbsp; totale '+_fmtBytes(d.total_size);
  }).catch(function(){
    if(grid) grid.innerHTML='<div style="opacity:.5;grid-column:1/-1;text-align:center;padding:1.5rem">Errore caricamento file</div>';
  });
}

function _fmtBytes(b){
  if(b<1024) return b+' B';
  if(b<1048576) return (b/1024).toFixed(1)+' KB';
  return (b/1048576).toFixed(1)+' MB';
}

function reloadKB2(){
  var btn=document.getElementById('btn-reload-kb2');
  var status=document.getElementById('kb-status-panel');
  btn.disabled=true; btn.textContent='↺ Ricarico...';
  fetch('/api/reload-kb').then(function(r){return r.json();}).then(function(d){
    btn.disabled=false; btn.textContent='↺ Ricarica KB';
    if(d.ok){
      if(status) status.innerHTML='<strong style="color:#68D391">✓ Ricaricata</strong>'
        +' &nbsp;·&nbsp; '+d.chars+' caratteri &nbsp;·&nbsp; alle '+d.loaded_at;
      loadKbFiles();
    } else {
      if(status) status.innerHTML='<span style="color:#FC8181">Errore: '+d.error+'</span>';
    }
  }).catch(function(){
    btn.disabled=false; btn.textContent='↺ Ricarica KB';
    if(status) status.innerHTML='<span style="color:#FC8181">Errore di rete</span>';
  });
}

// ═══════════════════════════════════════════════
// ONBOARDING TAB
// ═══════════════════════════════════════════════
function switchObTab(el, panelId){
  document.querySelectorAll('#onboarding .db-tab').forEach(function(t){ t.classList.remove('active'); });
  document.querySelectorAll('#onboarding .db-panel').forEach(function(p){ p.style.display='none'; });
  el.classList.add('active');
  var panel = document.getElementById(panelId);
  if(panel) panel.style.display='block';
}

// ═══════════════════════════════════════════════
// MERCATI
// ═══════════════════════════════════════════════
function loadMercati(){
  fetch('/api/mercati').then(function(r){return r.json()}).then(function(d){
    var wrap=document.getElementById('mercati-wrap');
    if(!d.rows||!d.rows.length){
      wrap.innerHTML='<table><tbody><tr><td style="padding:1.5rem;opacity:.5;text-align:center">Nessun dato — esegui prima lo screener Azioni</td></tr></tbody></table>';
      return;
    }
    var cols=Object.keys(d.rows[0]);
    var head='<tr>'+cols.map(function(c){return '<th>'+c+'</th>'}).join('')+'</tr>';
    var totT=0,totS=0;
    var body=d.rows.map(function(row){
      totT+=parseInt(row['Ticker Totali'])||0;
      totS+=parseInt(row['Selezionate'])||0;
      return '<tr>'+cols.map(function(c){
        var v=row[c]!==null&&row[c]!==undefined?row[c]:'—';
        var st='';
        if(c==='Mercato') st=' style="font-weight:600;color:#F6AD55"';
        if(c==='Selezionate'&&v>0) st=' style="color:#22c55e;font-weight:700"';
        return '<td'+st+'>'+v+'</td>';
      }).join('')+'</tr>';
    }).join('');
    var foot='<tr style="border-top:2px solid rgba(246,173,85,.2);font-weight:700"><td style="color:#F6AD55">TOTALE</td><td>'+totT+'</td>'
             +cols.slice(2).map(function(c){return c==='Selezionate'?'<td style="color:#22c55e">'+totS+'</td>':'<td>—</td>';}).join('')+'</tr>';
    wrap.innerHTML='<table><thead>'+head+'</thead><tbody>'+body+foot+'</tbody></table>';
  }).catch(function(){});
}

// ═══════════════════════════════════════════════
// TABLE DATA — con sorting per colonna
// ═══════════════════════════════════════════════
function loadTable(tipo){
  var body=document.getElementById(tipo+'-body');
  var info=document.getElementById(tipo+'-info');
  body.innerHTML='<tr><td style="padding:2rem;opacity:.5;text-align:center">Caricamento...</td></tr>';
  fetch('/api/data/'+tipo).then(function(r){return r.json()}).then(function(d){
    var n=d.rows?d.rows.length:0;
    info.innerHTML='<div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap">'
      +'<span><strong>'+(d.file||'—')+'</strong> &nbsp;·&nbsp; '+(d.time||'—')+' &nbsp;·&nbsp; <strong style="color:#22c55e">'+n+'</strong> risultati</span>'
      +'<button onclick="_resetCols(\''+tipo+'\')" style="margin-left:auto;padding:.25rem .7rem;font-size:.75rem;background:transparent;border:1px solid rgba(255,255,255,.2);border-radius:5px;color:#aaa;cursor:pointer" title="Ripristina ordine colonne originale">↺ Reset colonne</button>'
      +'</div>';
    if(!n){body.innerHTML='<tr><td style="padding:2rem;opacity:.5;text-align:center">Nessun dato disponibile</td></tr>';return;}
    _tableData[tipo]=d.rows;
    var defaultCols=Object.keys(d.rows[0]);
    // Ripristina ordine salvato (se compatibile con i dati attuali)
    var savedCols=null;
    try{
      var raw=localStorage.getItem('cols_'+tipo);
      if(raw){
        var parsed=JSON.parse(raw);
        if(parsed.length===defaultCols.length&&parsed.every(function(c){return defaultCols.indexOf(c)>=0;}))
          savedCols=parsed;
      }
    }catch(e){}
    _tableCols[tipo]=savedCols||defaultCols;
    _sortState[tipo]={col:null,dir:-1};
    _renderTable(tipo);
  }).catch(function(e){body.innerHTML='<tr><td style="color:#ef4444">Errore: '+e.message+'</td></tr>';});
}

function _renderTable(tipo){
  var head=document.getElementById(tipo+'-head');
  var body=document.getElementById(tipo+'-body');
  var cols=_tableCols[tipo];
  var ss=_sortState[tipo];
  var rows=_tableData[tipo].slice();

  // Ordina se è selezionata una colonna
  if(ss.col!==null){
    var cName=cols[ss.col];
    rows.sort(function(a,b){
      var va=a[cName], vb=b[cName];
      var aNull=(va===null||va===undefined||va==='—'||va==='');
      var bNull=(vb===null||vb===undefined||vb==='—'||vb==='');
      if(aNull&&bNull) return 0;
      if(aNull) return 1;
      if(bNull) return -1;
      if(typeof va==='number'&&typeof vb==='number') return (va-vb)*ss.dir;
      return String(va).localeCompare(String(vb),'it',{numeric:true})*ss.dir;
    });
  }

  // Header con indicatori di sort + drag-and-drop per riordinare colonne
  head.innerHTML='<tr>'+cols.map(function(c,i){
    var cls='sortable';
    if(ss.col===i) cls+=(ss.dir===-1?' sorted-desc':' sorted-asc');
    return '<th class="'+cls+'" draggable="true"'
      +' onclick="if(this._skipNextClick){this._skipNextClick=false;return;}_sortTable(\''+tipo+'\','+i+')"'
      +' ondragstart="_colDragStart(\''+tipo+'\','+i+',this)"'
      +' ondragend="_colDragEnd(this)"'
      +' ondragover="_colDragOver(event,this)"'
      +' ondragleave="_colDragLeave(this)"'
      +' ondrop="_colDrop(\''+tipo+'\','+i+',event)"'
      +' title="Clicca per ordinare · Trascina per spostare la colonna">'+c+'</th>';
  }).join('')+'</tr>';

  // Righe
  body.innerHTML=rows.map(function(row){
    return '<tr>'+cols.map(function(c){
      var v=row[c];
      if(v===null||v===undefined) return '<td>—</td>';
      var cls='';
      if(c==='Ticker'){
        return '<td><a class="ticker" href="https://finance.yahoo.com/quote/'+encodeURIComponent(v)+'" target="_blank" rel="noopener" title="Apri su Yahoo Finance">'+v+'</a></td>';
      }
      if(typeof v==='number'&&v<0) cls=' class="neg"';
      if(typeof v==='number'&&!Number.isInteger(v)) v=v.toFixed(2);
      return '<td'+cls+'>'+v+'</td>';
    }).join('')+'</tr>';
  }).join('');
}

function _sortTable(tipo,colIdx){
  var ss=_sortState[tipo];
  if(ss.col===colIdx){
    ss.dir=-ss.dir;
  } else {
    ss.col=colIdx;
    ss.dir=-1;
  }
  _renderTable(tipo);
}

// ─── Drag & drop colonne ──────────────────────────────────────
var _dragColIdx  = null;
var _dragColTipo = null;

function _colDragStart(tipo, idx, el){
  _dragColIdx  = idx;
  _dragColTipo = tipo;
  el.style.opacity = '.45';
  // click-then-drag non trigga sort: stoppiamo click successivo
  el._skipNextClick = true;
}

function _colDragEnd(el){
  el.style.opacity = '';
  _dragColIdx  = null;
  _dragColTipo = null;
}

function _colDragOver(event, el){
  event.preventDefault();
  el.classList.add('col-drag-over');
}

function _colDragLeave(el){
  el.classList.remove('col-drag-over');
}

function _colDrop(tipo, targetIdx, event){
  event.preventDefault();
  // Rimuovi indicatore visivo su tutti gli header
  document.querySelectorAll('#'+tipo+'-head th').forEach(function(th){
    th.classList.remove('col-drag-over');
  });
  if(_dragColTipo !== tipo || _dragColIdx === null || _dragColIdx === targetIdx){
    _dragColIdx = null; return;
  }
  var cols  = _tableCols[tipo];
  var moved = cols.splice(_dragColIdx, 1)[0];
  cols.splice(targetIdx, 0, moved);
  // Aggiusta indice di sort dopo lo spostamento
  var ss = _sortState[tipo];
  if(ss.col !== null){
    if(ss.col === _dragColIdx){
      ss.col = targetIdx;
    } else if(_dragColIdx < targetIdx && ss.col > _dragColIdx && ss.col <= targetIdx){
      ss.col--;
    } else if(_dragColIdx > targetIdx && ss.col >= targetIdx && ss.col < _dragColIdx){
      ss.col++;
    }
  }
  _dragColIdx = null;
  _renderTable(tipo);
  // Persiste in localStorage
  try{ localStorage.setItem('cols_'+tipo, JSON.stringify(_tableCols[tipo])); }catch(e){}
}

function _resetCols(tipo){
  try{ localStorage.removeItem('cols_'+tipo); }catch(e){}
  if(!_tableData[tipo]||!_tableData[tipo].length) return;
  _tableCols[tipo] = Object.keys(_tableData[tipo][0]);
  _sortState[tipo] = {col:null, dir:-1};
  _renderTable(tipo);
}

// ═══════════════════════════════════════════════
// SERVIZI — LOAD & RENDER
// ═══════════════════════════════════════════════
function loadServizi(){
  fetch('/api/servizi').then(function(r){return r.json()}).then(function(d){
    _sv=d;
    renderServizi();
    renderParametri();
    loadStatus();
  }).catch(function(e){console.error('loadServizi:',e);});
}

function renderServizi(){
  if(!_sv) return;
  ASSETS.forEach(function(asset){
    TIERS.forEach(function(tier){
      var cfg=(_sv[asset]&&_sv[asset][tier])||{};
      var params=cfg.parametri||{};
      var el=document.getElementById('sv-'+asset+'-'+tier);
      if(!el) return;
      var pRows=Object.entries(params).map(function(kv){
        var k=kv[0],v=kv[1];
        return '<div class="param-row">'
          +'<span class="param-lbl">'+(PLABELS[k]||k)+'</span>'
          +'<input class="param-inp" type="number" step="'+(PSTEP[k]||0.1)+'"'
          +' data-asset="'+asset+'" data-tier="'+tier+'" data-param="'+k+'" value="'+v+'">'
          +'</div>';
      }).join('');
      var selOpts=['attivo','beta','inattivo'].map(function(s){
        return '<option value="'+s+'"'+(cfg.status===s?' selected':'')+'>'+{attivo:'✅ Attivo',beta:'🟡 Beta',inattivo:'⛔ Inattivo'}[s]+'</option>';
      }).join('');
      var caratteristiche=(cfg.caratteristiche||[]).join('\n');
      var target=cfg.target||'';
      el.innerHTML='<div class="sv-card t-'+tier+'">'
        +'<div class="price-row">'
          +'<span class="price-eur">€</span>'
          +'<input class="price-inp" type="number" min="0" step="1"'
          +' data-asset="'+asset+'" data-tier="'+tier+'" data-field="prezzo" value="'+(cfg.prezzo||0)+'">'
          +'<span class="price-mo">/mese</span>'
        +'</div>'
        +'<div class="status-row">'
          +'<span class="bdg bdg-'+tier+'">'+tier.toUpperCase()+'</span>'
          +'<select class="status-sel" data-asset="'+asset+'" data-tier="'+tier+'" data-field="status">'+selOpts+'</select>'
        +'</div>'
        +'<div class="param-rows">'+pRows+'</div>'
        +'<div class="sv-extra">'
          +'<label class="sv-lbl">Caratteristiche <small>(una per riga)</small></label>'
          +'<textarea class="sv-textarea" rows="5" data-asset="'+asset+'" data-tier="'+tier+'" data-field="caratteristiche"></textarea>'
          +'<label class="sv-lbl" style="margin-top:.5rem">Profilo target</label>'
          +'<textarea class="sv-textarea" style="min-height:12rem;height:12rem" data-asset="'+asset+'" data-tier="'+tier+'" data-field="target"></textarea>'
        +'</div>'
      +'</div>';
      // imposta .value dopo innerHTML per gestire correttamente newline e caratteri speciali
      el.querySelector('[data-field="caratteristiche"]').value = caratteristiche;
      el.querySelector('[data-field="target"]').value = target;
    });
  });
}

function saveServizi(){
  var data=JSON.parse(JSON.stringify(_sv));
  // prices & status
  document.querySelectorAll('[data-field="prezzo"]').forEach(function(inp){
    var a=inp.dataset.asset,t=inp.dataset.tier;
    if(data[a]&&data[a][t]) data[a][t].prezzo=parseFloat(inp.value)||0;
  });
  document.querySelectorAll('[data-field="status"]').forEach(function(sel){
    var a=sel.dataset.asset,t=sel.dataset.tier;
    if(data[a]&&data[a][t]) data[a][t].status=sel.value;
  });
  // parametri inside cards
  document.querySelectorAll('.sv-card .param-inp').forEach(function(inp){
    var a=inp.dataset.asset,t=inp.dataset.tier,p=inp.dataset.param;
    if(data[a]&&data[a][t]&&data[a][t].parametri) data[a][t].parametri[p]=parseFloat(inp.value);
  });
  // caratteristiche & target
  document.querySelectorAll('.sv-textarea[data-field="caratteristiche"]').forEach(function(ta){
    var a=ta.dataset.asset,t=ta.dataset.tier;
    if(data[a]&&data[a][t]) data[a][t].caratteristiche=ta.value.split('\n').map(function(s){return s.trim();}).filter(Boolean);
  });
  document.querySelectorAll('.sv-textarea[data-field="target"]').forEach(function(ta){
    var a=ta.dataset.asset,t=ta.dataset.tier;
    if(data[a]&&data[a][t]) data[a][t].target=ta.value.trim();
  });
  fetch('/api/servizi',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})
    .then(function(r){return r.json()}).then(function(res){
      if(res.ok){_sv=data; renderParametri(); showMsg('sv-msg','✅ Servizi salvati','ok');}
      else showMsg('sv-msg','❌ '+res.msg,'err');
      loadStatus();
    }).catch(function(e){showMsg('sv-msg','❌ '+e.message,'err');});
}

// ═══════════════════════════════════════════════
// PARAMETRI — RENDER COMPARISON TABLE
// ═══════════════════════════════════════════════
function renderParametri(){
  if(!_sv) return;
  var html='';
  ASSETS.forEach(function(asset){
    var allKeys=[];
    TIERS.forEach(function(tier){
      var params=(_sv[asset]&&_sv[asset][tier]&&_sv[asset][tier].parametri)||{};
      Object.keys(params).forEach(function(k){if(allKeys.indexOf(k)===-1) allKeys.push(k);});
    });
    html+='<div class="pm-section box">'
      +'<h3>'+ICONS[asset]+' '+asset.toUpperCase()+'</h3>'
      +'<div class="tbl-wrap"><table class="pm-table">'
      +'<thead><tr>'
        +'<th style="width:200px">Parametro</th>'
        +'<th class="th-basic">BASIC</th>'
        +'<th class="th-pro">PRO</th>'
        +'<th class="th-value">VALUE</th>'
      +'</tr></thead><tbody>';
    allKeys.forEach(function(key){
      html+='<tr><td>'+(PLABELS[key]||key)+'</td>';
      TIERS.forEach(function(tier){
        var val=(_sv[asset]&&_sv[asset][tier]&&_sv[asset][tier].parametri&&_sv[asset][tier].parametri[key]!==undefined)?_sv[asset][tier].parametri[key]:'';
        html+='<td class="tc"><input class="pm-inp '+tier+'" type="number" step="'+(PSTEP[key]||0.1)+'"'
             +' data-asset="'+asset+'" data-tier="'+tier+'" data-param="'+key+'" value="'+val+'"></td>';
      });
      html+='</tr>';
    });
    html+='</tbody></table></div></div>';
  });
  document.getElementById('pm-container').innerHTML=html;
}

function saveParametri(){
  if(!_sv) return;
  var data=JSON.parse(JSON.stringify(_sv));
  document.querySelectorAll('#pm-container .pm-inp').forEach(function(inp){
    var a=inp.dataset.asset,t=inp.dataset.tier,p=inp.dataset.param;
    if(data[a]&&data[a][t]&&data[a][t].parametri) data[a][t].parametri[p]=parseFloat(inp.value);
  });
  fetch('/api/servizi',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})
    .then(function(r){return r.json()}).then(function(res){
      if(res.ok){_sv=data; renderServizi(); showMsg('pm-msg','✅ Parametri salvati','ok');}
      else showMsg('pm-msg','❌ '+res.msg,'err');
    }).catch(function(e){showMsg('pm-msg','❌ '+e.message,'err');});
}

// ═══════════════════════════════════════════════
// SCREENER RUN + LOG
// ═══════════════════════════════════════════════
function runScreener(tipo){
  var btn=document.getElementById('run-'+tipo);
  if(btn) btn.disabled=true;
  document.getElementById('run-msg').textContent='';
  fetch('/api/run/'+tipo,{method:'POST'}).then(function(r){return r.json()}).then(function(d){
    if(d.ok){
      var logNome=tipo==='orchestrator'?'orchestrator':tipo;
      startLog(logNome);
      document.getElementById('run-msg').innerHTML='⏳ '+tipo.toUpperCase()+' avviato';
    } else {
      document.getElementById('run-msg').innerHTML='❌ '+d.msg;
      if(btn) btn.disabled=false;
    }
    setTimeout(loadStatus,2000);
  }).catch(function(e){document.getElementById('run-msg').innerHTML='❌ '+e.message;if(btn)btn.disabled=false;});
}

function startLog(nome){
  var box=document.getElementById('log-box');
  var term=document.getElementById('log-term');
  var badge=document.getElementById('log-badge');
  document.getElementById('log-title').textContent='📟 Log — '+nome.toUpperCase();
  box.style.display='block';
  term.textContent='In attesa output...';
  badge.className='rs rs-running'; badge.textContent='running';
  box.scrollIntoView({behavior:'smooth',block:'nearest'});
  if(_logInt) clearInterval(_logInt);
  _logInt=setInterval(function(){pollLog(nome);},2000);
}

function pollLog(nome){
  fetch('/api/log/'+nome).then(function(r){return r.json()}).then(function(d){
    var term=document.getElementById('log-term');
    var badge=document.getElementById('log-badge');
    if(d.log&&d.log.length){term.textContent=d.log.join('\n');term.scrollTop=term.scrollHeight;}
    badge.textContent=d.status; badge.className='rs rs-'+d.status;
    if(d.status!=='running'){
      clearInterval(_logInt); _logInt=null;
      document.getElementById('log-info').textContent='Completato: '+new Date().toLocaleTimeString('it-IT');
      loadStatus();
      ['azioni','etf','fondi','tutti','orchestrator'].forEach(function(k){
        var b=document.getElementById('run-'+k);
        if(b){b.disabled=false;b.textContent=k==='tutti'?'▶▶ Tutti':k==='orchestrator'?'🚀 Orchestrator + Email':'▶ '+k.charAt(0).toUpperCase()+k.slice(1);}
      });
    }
  }).catch(function(){});
}

// ═══════════════════════════════════════════════
// UTILS
// ═══════════════════════════════════════════════
function showMsg(id,text,type){
  var el=document.getElementById(id);
  if(!el) return;
  el.textContent=text;
  el.className='msg'+(type?' msg-'+type:'');
  setTimeout(function(){el.className='msg';el.textContent='';},4000);
}

function refreshAll(){
  loadStatus();
  loadMercati();
  if(_sv) loadServizi();
  var active=document.querySelector('.panel.active');
  if(active&&(active.id==='azioni'||active.id==='etf'||active.id==='fondi')) loadTable(active.id);
}

// ═══════════════════════════════════════════════
// SETTORI — Analisi Settoriale & Mercati
// ═══════════════════════════════════════════════
// ── Dati statici settori GICS ───────────────────────────────
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
var EU_TO_US = {
  'Technology':'Technology','Banks':'Financial Services','Health Care':'Health Care',
  'Industrials':'Industrials','Auto & Parts':'Consumer Discret.','Food & Beverage':'Consumer Staples',
  'Oil & Gas':'Energy','Utilities':'Utilities','Insurance':'Financial Services',
  'Media':'Comm. Services','Travel & Leisure':'Consumer Discret.',
};

// ── Dati statici ETF per nazioni ─────────────────────────────
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

var _settPerf = {};   // ticker → {p1d,p1w,p1m,p3m,p1y}

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

// ═══════════════════════════════════════════════
// INIT
// ═══════════════════════════════════════════════
loadStatus();
loadMercati();
loadServizi();
loadKBStatus();
setInterval(loadStatus,15000);
</script>
</body>
</html>"""


# ─── STRIPE CHECKOUT (placeholder — inserire chiavi Stripe) ──
STRIPE_SECRET_KEY = ""   # sk_live_... oppure sk_test_...
STRIPE_PRICE_IDS  = {    # price_... da Stripe Dashboard
    "azioni_basic":"", "azioni_pro":"", "azioni_value":"",
    "etf_basic":"",    "etf_pro":"",    "etf_value":"",
    "fondi_basic":"",  "fondi_pro":"",  "fondi_value":"",
}

def create_checkout_session(asset, tier):
    if not STRIPE_SECRET_KEY:
        return {"error": "Stripe non ancora configurato. Inserire STRIPE_SECRET_KEY in dashboard.py"}
    try:
        import urllib.request, urllib.parse
        price_id = STRIPE_PRICE_IDS.get(f"{asset}_{tier}", "")
        if not price_id:
            return {"error": f"Price ID mancante per {asset} {tier}"}
        payload = urllib.parse.urlencode({
            "mode": "subscription",
            "line_items[0][price]": price_id,
            "line_items[0][quantity]": "1",
            "success_url": BASE_URL + "/landing?success=1",
            "cancel_url":  BASE_URL + "/landing?cancel=1",
        }).encode()
        req = urllib.request.Request(
            "https://api.stripe.com/v1/checkout/sessions",
            data=payload,
            headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}"}
        )
        with urllib.request.urlopen(req) as resp:
            session = json.loads(resp.read())
            return {"url": session["url"]}
    except Exception as e:
        return {"error": str(e)}


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
    <input type="password" name="pwd" placeholder="Password" autofocus autocomplete="current-password">
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
  <div class="reg-inner">
    <h2 data-t="reg_title">Iscriviti al <span>Servizio</span></h2>
    <p data-t="reg_sub">Compila il modulo per accedere al servizio di screening quantitativo. Riceverai le credenziali di accesso e la fattura via email in pochi minuti.</p>
    <div class="reg-form" id="reg-form-box">

      <div class="reg-section-label">Dati Personali</div>
      <div class="reg-row">
        <div class="reg-field">
          <label data-t="reg_nome">Nome *</label>
          <input id="reg-nome" type="text" placeholder="Mario">
        </div>
        <div class="reg-field">
          <label data-t="reg_cognome">Cognome *</label>
          <input id="reg-cognome" type="text" placeholder="Rossi">
        </div>
      </div>
      <div class="reg-field">
        <label data-t="reg_email">Email *</label>
        <input id="reg-email" type="email" placeholder="mario.rossi@email.com">
      </div>
      <div class="reg-row">
        <div class="reg-field">
          <label data-t="reg_tel">Telefono *</label>
          <input id="reg-tel" type="tel" placeholder="+39 333 1234567">
        </div>
        <div class="reg-field">
          <label data-t="reg_paese">Paese *</label>
          <select id="reg-paese">
            <option value="">— seleziona —</option>
            <option value="IT">🇮🇹 Italia</option>
            <option value="ES">🇪🇸 Spagna</option>
            <option value="FR">🇫🇷 Francia</option>
            <option value="DE">🇩🇪 Germania</option>
            <option value="UK">🇬🇧 Regno Unito</option>
          </select>
        </div>
      </div>

      <div class="reg-section-label">Dati Fiscali</div>
      <div class="reg-row">
        <div class="reg-field">
          <label data-t="reg_cf">Codice Fiscale / NIE / Tax ID *</label>
          <input id="reg-cf" type="text" placeholder="RSSMRA80A01H501U" style="font-family:monospace;letter-spacing:1px;text-transform:uppercase" oninput="onCfPivaInput()">
        </div>
        <div class="reg-field">
          <label data-t="reg_piva" id="reg-piva-label">P.IVA <span style="opacity:.5;font-size:.75rem" id="reg-piva-note">(se azienda)</span></label>
          <input id="reg-piva" type="text" placeholder="IT12345678901" style="font-family:monospace" oninput="onCfPivaInput()">
        </div>
      </div>
      <div style="font-size:.72rem;color:rgba(246,173,85,.6);margin:-.4rem 0 .9rem;letter-spacing:.2px" data-t="reg_cf_hint">Inserisci il Codice Fiscale (persona fisica) <em>oppure</em> la P.IVA (azienda/professionista). Almeno uno dei due è obbligatorio.</div>
      <div class="reg-field">
        <label data-t="reg_indirizzo">Indirizzo *</label>
        <input id="reg-indirizzo" type="text" placeholder="Via Roma 1">
      </div>
      <div style="display:grid;grid-template-columns:110px 1fr;gap:.8rem;margin-bottom:.8rem">
        <div class="reg-field" style="margin-bottom:0">
          <label data-t="reg_cap">CAP *</label>
          <input id="reg-cap" type="text" placeholder="00100">
        </div>
        <div class="reg-field" style="margin-bottom:0">
          <label data-t="reg_citta">Città *</label>
          <input id="reg-citta" type="text" placeholder="Roma">
        </div>
      </div>
      <div class="reg-field">
        <label data-t="reg_nascita">Data di nascita <span style="opacity:.5;font-size:.75rem">(opzionale)</span></label>
        <input id="reg-nascita" type="date">
      </div>

      <div class="reg-section-label">Servizi di Interesse</div>
      <div class="reg-field">
        <label data-t="reg_interesse">Seleziona i servizi *</label>
        <div class="reg-checks">
          <label class="reg-check"><input type="checkbox" id="reg-azioni"  value="azioni">  📈 <strong>Azioni</strong> <span class="reg-check-desc">Screener quantitativo su oltre 3.000 titoli azionari globali</span></label>
          <label class="reg-check"><input type="checkbox" id="reg-etf"    value="etf">    📦 <strong>ETF</strong> <span class="reg-check-desc">Selezione automatica su oltre 670 ETF europei armonizzati</span></label>
          <label class="reg-check"><input type="checkbox" id="reg-fondi"  value="fondi">  🏦 <strong>Fondi</strong> <span class="reg-check-desc">Analisi quantitativa su fondi comuni e SICAV</span></label>
          <label class="reg-check"><input type="checkbox" id="reg-ordini" value="ordini"> 📋 <strong>Order Builder</strong> <span class="reg-check-desc">Genera istruzioni di acquisto pronte per il tuo intermediario bancario o broker</span></label>
        </div>
      </div>
      <div class="reg-field">
        <label data-t="reg_note">Note <span style="opacity:.5;font-size:.75rem">(opzionale)</span></label>
        <input id="reg-note" type="text" placeholder="Domande o informazioni aggiuntive...">
      </div>

      <div class="reg-disclaimer">
        <strong>Servizio Informativo SaaS · Non Consulenza Finanziaria</strong>
        <span data-t="reg_disclaimer">Con questa iscrizione accedi a un servizio di screening quantitativo automatico a carattere esclusivamente informativo. I dati e i report forniti non costituiscono consulenza finanziaria, raccomandazione di investimento o sollecitazione all'acquisto. Gli investimenti comportano rischi, inclusa la possibile perdita del capitale. Fuerte Venture Capital SL non svolge attività di gestione patrimoniale né di intermediazione finanziaria.</span>
      </div>
      <label class="reg-gdpr">
        <input type="checkbox" id="reg-gdpr">
        <span data-t="reg_gdpr_text">Ho letto e accetto l'<a href="/privacy" target="_blank">Informativa sulla Privacy</a> e acconsento al trattamento dei miei dati personali ai sensi del Reg. UE 2016/679 (GDPR). *</span>
      </label>
      <button class="reg-submit" onclick="inviaRegistrazione()" data-t="reg_invia">INVIA RICHIESTA →</button>
      <div class="reg-err" id="reg-err"></div>
    </div>
    <div class="reg-ok" id="reg-ok">
      <img src="data:image/png;base64,__LOGO_B64__" alt="Fuerte Venture Capital" style="height:52px;width:auto;border-radius:10px;margin-bottom:1.2rem">
      <div style="font-size:2rem;margin-bottom:.6rem">✅</div>
      <div data-t="reg_ok" style="font-size:1.05rem;font-weight:700;color:#68D391;margin-bottom:.5rem">Registrazione completata! Controlla la tua email.</div>
      <div style="font-size:.8rem;color:#888;margin-top:.6rem">Fuerte Venture Capital SL &middot; <a href="mailto:info@fuerteventurecapital.com" style="color:#F6AD55;text-decoration:none">info@fuerteventurecapital.com</a></div>
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
  <p>Fuerte Venture Capital SL &middot; NIF: B23881691</p>
  <p>Calle Puipana 3, 35640 Villaverde, Las Palmas, España</p>
  <p><a href="mailto:info@fuerteventurecapital.com" style="color:#F6AD55;text-decoration:none">info@fuerteventurecapital.com</a> &middot; <a href="https://www.fuerteventurecapital.com" style="color:#F6AD55;text-decoration:none">www.fuerteventurecapital.com</a></p>
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
  document.getElementById('registrazione').scrollIntoView({behavior:'smooth'});
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
    document.getElementById('registrazione').scrollIntoView({behavior:'smooth'});
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
  <span style="font-size:.68rem;color:#333">Dati trattati ai sensi del Reg. UE 2016/679 (GDPR) da Fuerte Venture Capital SL · NIF: B23881691</span></div>
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
  <div class="footer-note">Fuerte Venture Capital SL · NIF: B23881691 · Calle Puipana 3, 35640 Villaverde, Las Palmas, España<br>
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
    err_html = f'<p style="color:#FC8181;font-size:.85rem;text-align:center;margin-bottom:1rem">{error}</p>' if error else ''
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
    <strong style="color:#667">Fuerte Venture Capital SL</strong> &middot; NIF: B23881691<br>
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

<button id="rt-chat-btn" onclick="rtToggleChat()" title="Assistente Robot Trader">
  <svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/></svg>
</button>

<div id="rt-chat-box">
  <div id="rt-chat-hdr">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="#fff"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/></svg>
    <span>Assistente Robot Trader</span>
    <small>Fuerte VC</small>
  </div>
  <div id="rt-chat-msgs">
    <div class="rt-msg bot">Ciao! Sono l'assistente di Robot Trader 2026. Come posso aiutarti? 👋</div>
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

<button id="rt-abb-btn" onclick="rtAbbToggle()" title="Assistente Report — Solo Abbonati">
  <svg viewBox="0 0 24 24"><path d="M19 3H5c-1.1 0-2 .9-2 2v14l4-4h12c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 9H7v-2h7v2zm3-4H7V6h10v2z"/></svg>
</button>

<div id="rt-abb-box">
  <div id="rt-abb-hdr">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="#fff"><path d="M19 3H5c-1.1 0-2 .9-2 2v14l4-4h12c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-5 9H7v-2h7v2zm3-4H7V6h10v2z"/></svg>
    <span>Assistente Report</span>
    <small>Solo Abbonati</small>
  </div>
  <div id="rt-abb-msgs">
    <div class="rt-abb-msg bot">Ciao! Sono il tuo assistente personale. Puoi chiedermi informazioni sui report — ad esempio se un titolo è presente, il suo score, o perché è stato scartato. 📊</div>
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
        # ── Rotte admin (richiede sessione) ────────────────────
        if not _is_auth(self):
            _redirect(self, '/login'); return
        if p in ('/admin', '/admin/'):
            self._html(HTML.replace('__BASE_URL__', BASE_URL))  # console admin
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
        elif p == '/api/idee' and (_is_auth(self) or _is_client_auth(self)):
            if 'force=1' in self.path:
                _idee_cache['data'] = None
            self._json(get_idee_data())
        elif p == '/api/settori' and (_is_auth(self) or _is_client_auth(self)):
            self._json(get_settori_data())
        elif p == '/api/settori/titoli' and (_is_auth(self) or _is_client_auth(self)):
            qs_params = {}
            if '?' in self.path:
                for kv in self.path.split('?',1)[1].split('&'):
                    if '=' in kv:
                        k,v = kv.split('=',1)
                        qs_params[k] = v.replace('%20',' ').replace('+',' ')
            from urllib.parse import unquote_plus
            settore = unquote_plus(qs_params.get('s',''))
            self._json(get_settori_titoli(settore))
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
                self._json({
                    'ok': True,
                    'linkedin':  {'connesso': bool(li_token),  'configurato': li_configurato,  'member_id': tokens.get('linkedin',{}).get('member_id','')},
                    'facebook':  {'connesso': bool(meta_token), 'configurato': meta_configurato, 'page_name': tokens.get('meta',{}).get('page_name',''), 'page_id': tokens.get('meta',{}).get('page_id','')},
                    'instagram': {'connesso': bool(meta_token and meta_ig), 'ig_user_id': meta_ig},
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
                from social_automation import run as _sa_run
                result = _sa_run(force_theme=force_theme, force_date=force_date)
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
                if text_it: draft['text_it'] = text_it
                if text_es: draft['text_es'] = text_es
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
                    'piano_azioni':  req.get('piano_azioni', 'NONE'),
                    'piano_etf':     req.get('piano_etf',    'NONE'),
                    'piano_fondi':   req.get('piano_fondi',  'NONE'),
                    'piano_ordini':  req.get('piano_ordini', 'NONE'),
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
                print(f"[REG] {codice_cliente} — {nome} {cogn} <{email}> — {paese} — CF:{cf}", flush=True)
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
            if match and match.get('stato') in ('ATTIVO', 'TESTER') and match.get('password_hash') == _hash_pwd(pwd_in):
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
            import urllib.parse as _up
            body = self._body()
            fields = dict(_up.parse_qsl(body, keep_blank_values=True))
            email_in = fields.get('email', '').strip().lower()
            _logo = f'<img src="data:image/png;base64,{FUERTE_LOGO_B64}" alt="Fuerte Venture Capital">'
            db = read_clienti()
            match = next((c for c in (db.get('tester', []) + db.get('clienti', []))
                          if c.get('email', '').lower() == email_in and c.get('stato') == 'ATTIVO'), None)
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
                try:
                    msg = MIMEText(corpo, 'html', 'utf-8')
                    msg['Subject'] = 'Reset password — Fuerte Venture Capital'
                    msg['From']    = f'{BREVO_SENDER_NAME} <{BREVO_SENDER_EMAIL}>'
                    msg['To']      = email_in
                    with smtplib.SMTP(BREVO_SMTP_HOST, BREVO_SMTP_PORT) as srv:
                        srv.starttls(); srv.login(BREVO_SMTP_LOGIN, BREVO_SMTP_PASSWORD)
                        srv.sendmail(BREVO_SENDER_EMAIL, [email_in], msg.as_string())
                    print(f"[RESET-PWD] Email inviata a {email_in}", flush=True)
                except Exception as e:
                    print(f"[RESET-PWD] Errore SMTP: {e}", flush=True)
            self._html(FORGOT_PWD_HTML.format(logo=_logo,
                msg='<p class="msg ok">Se l\'email è registrata riceverai il link entro pochi minuti.</p>')); return
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
                                if not old_pwd or _hash_pwd(old_pwd) != c.get('password_hash', ''):
                                    self._html(_build_cambia_password_page(error='Password attuale non corretta.', voluntary=True)); return
                            c['password_hash']        = _hash_pwd(new_pwd)
                            c['must_change_password'] = False
                            c['password_expiry']      = ''
                            save_clienti(db)
                            print(f"[PWD] Password {'modificata' if voluntary else 'impostata'} per {email}", flush=True)
                            _redirect(self, '/area-clienti'); return
                self._json({'ok': False, 'msg': 'Cliente non trovato'})
            except Exception as e:
                self._html(_build_cambia_password_page(error=str(e)))
            return
        # ── Checkout pubblico ──────────────────────────────────
        if p == '/api/checkout':
            try:
                req = json.loads(self._body())
                self._json(create_checkout_session(req.get('asset',''), req.get('tier','')))
            except Exception as e:
                self._json({'error': str(e)})
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
                    'dati_fiscali': {'paese': found.get('paese','IT'), 'telefono': found.get('telefono','')},
                }
                db.setdefault('tester', []).append(nuovo)
                save_clienti(db)
                found['stato'] = 'Promosso ✓'
                found['promosso'] = True
                save_prospect(items)
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
                nuovo = {
                    'nome':               req.get('nome', '').strip(),
                    'cognome':            req.get('cognome', '').strip(),
                    'email':              email,
                    'piano_azioni':       req.get('piano_azioni',  'NONE'),
                    'piano_etf':          req.get('piano_etf',     'NONE'),
                    'piano_fondi':        req.get('piano_fondi',   'NONE'),
                    'piano_ordini':       req.get('piano_ordini',  'NONE'),
                    'screener_attivi':    [],
                    'data_registrazione': _now_a.strftime('%Y-%m-%d'),
                    'data_attivazione':   '',
                    'stato':              'TESTER',
                    'trial_start':        _now_a.strftime('%Y-%m-%dT%H:%M:%S'),
                    'trial_end':          (_now_a + _td_a(days=7)).strftime('%Y-%m-%dT%H:%M:%S'),
                    'dati_fiscali':       {'paese':'','data_nascita':'','indirizzo':'','cap':'','citta':'','codice_fiscale':'','telefono':'','p_iva':''},
                }
                db.setdefault('tester', []).append(nuovo)
                save_clienti(db)
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
                for asset in ['azioni','etf','fondi','ordini']:
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
        self.send_header('Access-Control-Allow-Origin', '*')
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
        _sp.run(['taskkill', '/IM', 'ngrok.exe', '/F'], capture_output=True)
        # Apre ngrok in finestra visibile
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
