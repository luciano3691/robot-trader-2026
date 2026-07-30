# -*- coding: utf-8 -*-
"""
WhatsApp Business Cloud API — Robot Trader 2026
Invia notifiche WhatsApp ai clienti opt-in tramite Meta Graph API.

Prerequisiti (una-tantum, admin):
  1. Meta Business Manager verificato  → business.facebook.com
  2. WhatsApp Business Account con numero dedicato
  3. Template messaggi approvati da Meta (vedi TEMPLATE_TESTO sotto)
  4. config.json → sezione "whatsapp" compilata con token + phone_number_id

Docs Meta: https://developers.facebook.com/docs/whatsapp/cloud-api

CLI test:
  python whatsapp_service.py                        # lista clienti opt-in
  python whatsapp_service.py test +39XXXXXXXXXX     # invia template di test
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional

try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
except ImportError:
    pass

try:
    import requests as _requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
CLIENTI_FILE = os.path.join(BASE_DIR, 'clienti.json')
CONFIG_FILE  = os.path.join(BASE_DIR, 'config.json')

logger = logging.getLogger('whatsapp')

# ── Template messaggi (da sottomettere a Meta per approvazione) ───────────────
#
# Template: screener_pronto
#   Parametri: {{1}}=nome, {{2}}=piani, {{3}}=data, {{4}}=link
#   Testo da usare in Meta Business Manager:
#   ---------------------------------------------------------------
#   Ciao {{1}}, i tuoi segnali Robot Trader ({{2}}) del {{3}} sono pronti.
#
#   Accedi alla tua area clienti:
#   {{4}}
#
#   Fuerte Venture Capital — Robot Trader 2026
#   Rispondi STOP per disattivare le notifiche.
#   ---------------------------------------------------------------
#
# Template: brief_mattutino
#   Parametri: {{1}}=nome, {{2}}=titolo brief, {{3}}=link
#   Testo:
#   ---------------------------------------------------------------
#   Buongiorno {{1}},
#
#   {{2}} è disponibile nella tua area clienti:
#   {{3}}
#
#   Fuerte Venture Capital — Robot Trader 2026
#   ---------------------------------------------------------------


# ── Config ────────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    try:
        with open(CONFIG_FILE, encoding='utf-8') as f:
            cfg = json.load(f).get('whatsapp', {})
    except Exception:
        cfg = {}
    # env vars sovrascrivono config.json
    if os.getenv('WHATSAPP_TOKEN'):
        cfg['token'] = os.getenv('WHATSAPP_TOKEN')
    if os.getenv('WHATSAPP_PHONE_NUMBER_ID'):
        cfg['phone_number_id'] = os.getenv('WHATSAPP_PHONE_NUMBER_ID')
    if os.getenv('WHATSAPP_WABA_ID'):
        cfg['waba_id'] = os.getenv('WHATSAPP_WABA_ID')
    return cfg


def _base_url() -> str:
    try:
        with open(CONFIG_FILE, encoding='utf-8') as f:
            return json.load(f).get('base_url', 'https://www.fuerteventurecapital.com')
    except Exception:
        return 'https://www.fuerteventurecapital.com'


_WA_API_VERSION = 'v20.0'   # aggiornare quando Meta depreca la versione corrente


def _api_url(cfg: dict) -> str:
    version  = cfg.get('api_version', _WA_API_VERSION)
    phone_id = cfg.get('phone_number_id', '')
    return f"https://graph.facebook.com/{version}/{phone_id}/messages"


def _headers(cfg: dict) -> dict:
    return {
        'Authorization': f"Bearer {cfg.get('token', '')}",
        'Content-Type': 'application/json',
    }


# ── Phone normalization ───────────────────────────────────────────────────────

def _normalize_phone(phone: str) -> Optional[str]:
    """
    Normalizza numero in formato internazionale senza simbolo +.
    Esempi:
      '3396543210'        → '393396543210'   (aggiunge prefisso Italia)
      '+39 339 654 3210'  → '393396543210'
      '0034 612 345 678'  → '34612345678'    (Spagna)
    """
    if not phone:
        return None
    cleaned = ''.join(c for c in phone if c.isdigit())
    if len(cleaned) < 8:
        return None
    if cleaned.startswith('39') and len(cleaned) >= 11:
        return cleaned
    if cleaned.startswith('3') and len(cleaned) == 10:
        return '39' + cleaned
    if len(cleaned) >= 10:
        return cleaned
    return None


# ── Core send ─────────────────────────────────────────────────────────────────

def send_template(phone: str, template_name: str, lang: str = 'it',
                  body_params: Optional[list] = None) -> bool:
    """
    Invia un template message pre-approvato da Meta.
    Ritorna True se la richiesta ha avuto successo (HTTP 200).
    """
    if not _REQUESTS_OK:
        logger.error("Libreria 'requests' non installata: pip install requests")
        return False

    cfg = _load_config()
    if not cfg.get('token') or not cfg.get('phone_number_id'):
        logger.warning("WhatsApp non configurato (token o phone_number_id mancanti in config.json)")
        return False

    to = _normalize_phone(phone)
    if not to:
        logger.warning(f"Numero non valido: {phone!r}")
        return False

    payload: dict = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": lang},
        }
    }

    if body_params:
        payload["template"]["components"] = [{
            "type": "body",
            "parameters": [{"type": "text", "text": str(p)} for p in body_params]
        }]

    try:
        resp = _requests.post(
            _api_url(cfg),
            headers=_headers(cfg),
            json=payload,
            timeout=15,
        )
        if resp.status_code == 200:
            logger.info(f"Template '{template_name}' inviato a +{to}")
            return True
        logger.error(f"Errore API WhatsApp {resp.status_code}: {resp.text[:400]}")
        return False
    except Exception as e:
        logger.error(f"Eccezione invio WhatsApp a +{to}: {e}")
        return False


def send_text(phone: str, message: str) -> bool:
    """
    Invia messaggio testo libero.
    ATTENZIONE: funziona solo dentro la finestra di 24h dall'ultimo contatto del cliente.
    Per notifiche proattive usare sempre send_template().
    """
    if not _REQUESTS_OK:
        logger.error("Libreria 'requests' non installata: pip install requests")
        return False

    cfg = _load_config()
    if not cfg.get('token') or not cfg.get('phone_number_id'):
        logger.warning("WhatsApp non configurato")
        return False

    to = _normalize_phone(phone)
    if not to:
        logger.warning(f"Numero non valido: {phone!r}")
        return False

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message, "preview_url": False}
    }

    try:
        resp = _requests.post(
            _api_url(cfg),
            headers=_headers(cfg),
            json=payload,
            timeout=15,
        )
        if resp.status_code == 200:
            logger.info(f"Testo inviato a +{to}")
            return True
        logger.error(f"Errore API WhatsApp {resp.status_code}: {resp.text[:400]}")
        return False
    except Exception as e:
        logger.error(f"Eccezione invio WhatsApp a +{to}: {e}")
        return False


# ── Client list ───────────────────────────────────────────────────────────────

def get_opted_in_clients() -> list:
    """Ritorna i clienti con whatsapp_optin=True e telefono valorizzato."""
    try:
        with open(CLIENTI_FILE, encoding='utf-8') as f:
            db = json.load(f)
    except Exception:
        return []

    result = []
    for cat in ('tester', 'clienti'):
        for c in db.get(cat, []):
            if not c.get('whatsapp_optin'):
                continue
            phone = c.get('telefono') or c.get('dati_fiscali', {}).get('telefono', '')
            if phone:
                result.append({**c, '_phone': phone})
    return result


# ── Notifiche ─────────────────────────────────────────────────────────────────

def notify_screener_ready(base_url: str = '') -> dict:
    """
    Notifica 'screener_pronto' a tutti i clienti opt-in.
    Chiamata automaticamente dallo scheduler dopo orchestrator.py (23:00).
    Ritorna {'sent': N, 'failed': N, 'skipped': N}.
    """
    cfg      = _load_config()
    template = cfg.get('templates', {}).get('screener_pronto', 'screener_pronto')
    url      = (base_url or _base_url()).rstrip('/') + '/area-clienti'
    data     = datetime.now().strftime('%d/%m/%Y')

    clients          = get_opted_in_clients()
    sent = failed = skipped = 0

    for c in clients:
        phone = c.get('_phone', '')
        nome  = c.get('nome', 'Cliente')
        piani = _piani_label(c)

        if not phone:
            skipped += 1
            continue

        ok = send_template(phone, template, body_params=[nome, piani, data, url])
        if ok:
            sent += 1
        else:
            failed += 1

    logger.info(f"notify_screener_ready: sent={sent} failed={failed} skipped={skipped}")
    return {'sent': sent, 'failed': failed, 'skipped': skipped}


def notify_morning_brief(titolo: str = '', base_url: str = '') -> dict:
    """
    Notifica 'brief_mattutino' ai clienti opt-in.
    Chiamata dallo scheduler dopo social_automation.py (08:00 lun/mer/ven).
    """
    cfg      = _load_config()
    template = cfg.get('templates', {}).get('brief_mattutino', 'brief_mattutino')
    url      = (base_url or _base_url()).rstrip('/') + '/area-clienti'
    data     = datetime.now().strftime('%d/%m/%Y')
    titolo   = titolo or f"Brief del {data}"

    clients          = get_opted_in_clients()
    sent = failed = skipped = 0

    for c in clients:
        phone = c.get('_phone', '')
        nome  = c.get('nome', 'Cliente')

        if not phone:
            skipped += 1
            continue

        ok = send_template(phone, template, body_params=[nome, titolo, url])
        if ok:
            sent += 1
        else:
            failed += 1

    logger.info(f"notify_morning_brief: sent={sent} failed={failed} skipped={skipped}")
    return {'sent': sent, 'failed': failed, 'skipped': skipped}


# ── Util ──────────────────────────────────────────────────────────────────────

def _piani_label(c: dict) -> str:
    parts = []
    for asset, label in [('azioni', 'Azioni'), ('etf', 'ETF'), ('fondi', 'Fondi')]:
        piano = c.get(f'piano_{asset}', 'NONE')
        if piano and piano != 'NONE':
            parts.append(f"{label} {piano}")
    return ', '.join(parts) if parts else 'Screener'


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    if len(sys.argv) >= 3 and sys.argv[1] == 'test':
        phone = sys.argv[2]
        # template opzionale: default hello_world (pre-approvato Meta sandbox)
        # per test completo: python whatsapp_service.py test +39XXX screener_pronto
        tmpl = sys.argv[3] if len(sys.argv) > 3 else 'hello_world'
        params = None
        if tmpl == 'screener_pronto':
            params = ['Test', 'Azioni PRO', datetime.now().strftime('%d/%m/%Y'),
                      _base_url() + '/area-clienti']
        elif tmpl == 'brief_mattutino':
            params = ['Test', f"Brief del {datetime.now().strftime('%d/%m/%Y')}",
                      _base_url() + '/area-clienti']
        print(f"\nTest invio template '{tmpl}' a {phone}...")
        ok = send_template(phone, tmpl, body_params=params)
        print("OK" if ok else "ERRORE — controlla log sopra")
    else:
        clients = get_opted_in_clients()
        print(f"\nClienti con WhatsApp opt-in: {len(clients)}")
        for c in clients:
            print(f"  - {c['nome']:<20} {c.get('_phone','?'):<15} {_piani_label(c)}")
        if not clients:
            print("  (nessuno — abilita opt-in dalla dashboard admin > tab Clienti)")
        print()
