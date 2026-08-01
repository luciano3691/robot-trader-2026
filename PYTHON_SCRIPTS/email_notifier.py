# -*- coding: utf-8 -*-
"""
Robot Trader 2026 - Email Notifier V2
Invio per piano (BASIC/PRO/VALUE) con destinatari da clienti.json
"""

import os
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
except ImportError:
    pass

import base64
import io
import json
import openpyxl
import requests
from datetime import datetime

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(os.path.dirname(BASE_DIR), "REPORTS_DAILY")

ADMIN_EMAIL = "rioluc63@gmail.com"
ADMIN_NAME  = "Luciano"

def _count_fmt(n):
    return f"{n:,}".replace(',', '.')

def _get_azioni_count():
    try:
        import sys as _sys; _sys.path.insert(0, BASE_DIR)
        from ticker_lists_5000 import ALL_AZIONI
        return _count_fmt(len(ALL_AZIONI))
    except Exception:
        return "~2.625"

def _get_etf_count():
    try:
        import sys as _sys; _sys.path.insert(0, BASE_DIR)
        from ticker_lists_5000 import ALL_ETF
        etf_set = set(ALL_ETF)
        _cache = os.path.join(BASE_DIR, 'etf_universe_cache.json')
        if os.path.exists(_cache):
            with open(_cache, encoding='utf-8') as _f:
                for entry in json.load(_f).values():
                    tk = entry.get('preferred_ticker')
                    if tk and not entry.get('error'):
                        etf_set.add(tk)
        return _count_fmt(len(etf_set))
    except Exception:
        return "~4.800"

def _get_fondi_count():
    try:
        import sys as _sys; _sys.path.insert(0, BASE_DIR)
        from ticker_lists_5000 import ALL_FONDI
        fondi_set = set(ALL_FONDI)
        _cache = os.path.join(BASE_DIR, 'fondi_eu_universe_cache.json')
        if os.path.exists(_cache):
            with open(_cache, encoding='utf-8') as _f:
                for entry in json.load(_f).values():
                    tk = entry.get('yahoo_ticker')
                    if tk:
                        fondi_set.add(tk)
        return _count_fmt(len(fondi_set))
    except Exception:
        return "~1.400"

def _get_fondi_eu_count():
    try:
        _cache = os.path.join(BASE_DIR, 'fondi_eu_universe_cache.json')
        if os.path.exists(_cache):
            with open(_cache, encoding='utf-8') as _f:
                return _count_fmt(sum(1 for v in json.load(_f).values() if v.get('yahoo_ticker')))
        return "~493"
    except Exception:
        return "~493"

TICKER_COUNT = {
    "AZIONI":   _get_azioni_count(),
    "ETF":      _get_etf_count(),
    "FONDI":    _get_fondi_count(),
    "FONDI_EU": _get_fondi_eu_count(),
}


def _load_email_config():
    try:
        with open(os.path.join(BASE_DIR, "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("email", {}), cfg.get("base_url", "https://www.fuerteventurecapital.com")
    except Exception as e:
        print(f"Errore lettura config.json: {e}")
        return {}, "https://www.fuerteventurecapital.com"


_email_cfg, BASE_URL = _load_email_config()
BREVO_API_KEY      = os.getenv("BREVO_API_KEY", "")
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "") or _email_cfg.get("sender", "marketing@fuerteventurecapital.com")
BREVO_SENDER_NAME  = os.getenv("BREVO_SENDER_NAME", "Fuerte Venture Capital SL")
URL_SETTORI   = BASE_URL.rstrip('/') + '/settori'
URL_AREA      = BASE_URL.rstrip('/') + '/area-clienti'
URL_PROFILO   = BASE_URL.rstrip('/') + '/profilo-investitore'


def load_recipients_for_plan(report_type, piano):
    """
    Legge clienti.json e restituisce {email: nome} per utenti
    il cui piano_{tipo.lower()} corrisponde al piano richiesto.
    L'admin riceve sempre tutto indipendentemente dal piano.
    """
    recipients = {}
    piano_key  = f"piano_{report_type.lower()}"

    try:
        with open(os.path.join(BASE_DIR, "clienti.json"), encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Errore lettura clienti.json: {e}")
        return {ADMIN_EMAIL: ADMIN_NAME}

    for section in ("tester", "clienti"):
        for utente in data.get(section, []):
            email = utente.get("email", "")
            nome  = utente.get("nome", email.split("@")[0])
            if (utente.get(piano_key, "NONE").upper() == piano.upper()
                    and utente.get("stato", "TESTER") in ("ATTIVO", "TESTER")):
                recipients[email] = nome

    recipients[ADMIN_EMAIL] = ADMIN_NAME
    return recipients


def load_template(template_name):
    """Carica template email da file"""
    template_path = os.path.join(BASE_DIR, template_name)
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    print(f"Template {template_name} non trovato, uso versione base")
    return None


def create_email_body(template, report_type, piano, recipient_name, report_date, num_ticker):
    """Sostituisce placeholder nel template"""
    if not template:
        return (
            f"Ciao {recipient_name},\n\n"
            f"Come abbonato al servizio {report_type} {piano} "
            f"ti inviamo il report aggiornato al {report_date}.\n\n"
            f"Il sistema ha analizzato {num_ticker} strumenti.\n\n"
            f"Trova il report in allegato.\n\n"
            f"---\nFuerte Venture Capital\nmarketing@fuerteventurecapital.com\n"
        )

    return (template
            .replace("{TIPO}",        report_type)
            .replace("{PIANO}",       piano)
            .replace("{NOME}",        recipient_name)
            .replace("{DATA}",        report_date)
            .replace("{NUM_TICKER}",  num_ticker)
            .replace("{URL_SETTORI}", URL_SETTORI)
            .replace("{URL_AREA}",    URL_AREA)
            .replace("{URL_PROFILO}", URL_PROFILO))


def _build_client_attachment(filepath):
    """Carica il file Excel, rimuove i fogli di scarto, restituisce bytes."""
    _SCARTO = ('Esclusi', 'Scartate', 'Scartati', 'Dati Mancanti', 'Non Validi', 'Errori')
    wb = openpyxl.load_workbook(filepath)
    for name in wb.sheetnames[:]:
        if any(name.startswith(p) for p in _SCARTO):
            del wb[name]
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def send_email(report_type, piano, report_file):
    """Invia email con report allegato ai destinatari del piano specificato"""

    if not os.path.exists(report_file):
        print(f"File non trovato: {report_file}")
        return False

    recipients = load_recipients_for_plan(report_type, piano)
    if not recipients:
        print(f"Nessun destinatario per {report_type} {piano}")
        return True

    html_template = load_template("email_template.html")
    text_template = load_template("email_template.txt")

    report_date     = datetime.now().strftime("%d/%m/%Y")
    num_ticker      = TICKER_COUNT.get(report_type, "N/A")
    attachment_name = os.path.basename(report_file)
    subject         = f"Robot Trader 2026 - Report {report_type} {piano} del {report_date}"

    attachment_b64 = base64.b64encode(_build_client_attachment(report_file)).decode('ascii')

    print(f"\nInvio email {report_type} {piano} a {len(recipients)} destinatari...")
    print(f"  Sender: {BREVO_SENDER_EMAIL}  API key: ...{BREVO_API_KEY[-8:]}")

    ok = 0
    for recipient_email, recipient_name in recipients.items():
        try:
            text_body = create_email_body(
                text_template, report_type, piano,
                recipient_name, report_date, num_ticker)
            payload = {
                "sender":      {"name": BREVO_SENDER_NAME, "email": BREVO_SENDER_EMAIL},
                "to":          [{"email": recipient_email, "name": recipient_name}],
                "subject":     subject,
                "textContent": text_body,
                "attachment":  [{"name": attachment_name, "content": attachment_b64}],
            }
            if html_template:
                payload["htmlContent"] = create_email_body(
                    html_template, report_type, piano,
                    recipient_name, report_date, num_ticker)

            resp = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": BREVO_API_KEY, "content-type": "application/json"},
                json=payload,
                timeout=30,
            )
            if resp.status_code in (200, 201):
                print(f"  OK {recipient_name} ({recipient_email})")
                ok += 1
            else:
                print(f"  ERRORE {recipient_email}: HTTP {resp.status_code} — {resp.text[:300]}")

        except Exception as e:
            print(f"  ERRORE {recipient_email}: {e}")

    print(f"Email {report_type} {piano}: {ok}/{len(recipients)} inviate")
    return ok > 0


def main():
    if len(sys.argv) < 4:
        print("Uso: python email_notifier.py [TIPO] [PIANO] [FILENAME]")
        print("Esempio: python email_notifier.py AZIONI BASIC AZIONI_Screener_BASIC_20260613_230000.xlsx")
        sys.exit(1)

    report_type = sys.argv[1].upper()
    piano       = sys.argv[2].upper()
    filename    = sys.argv[3]
    report_file = os.path.join(REPORTS_DIR, filename)

    print("=" * 70)
    print(f"EMAIL NOTIFIER V2 - Robot Trader 2026")
    print(f"Report: {report_type}  Piano: {piano}")
    print(f"File: {filename}")
    print("=" * 70)

    success = send_email(report_type, piano, report_file)

    if success:
        print("\nNotifiche completate")
    else:
        print("\nErrore durante l'invio")
        sys.exit(1)


if __name__ == "__main__":
    main()
