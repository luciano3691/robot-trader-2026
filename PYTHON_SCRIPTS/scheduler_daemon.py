# -*- coding: utf-8 -*-
"""
SCHEDULER DAEMON - Robot Trader 2026
=====================================
Job schedulati (orario Canarie — Atlantic/Canary):
  21:00 lun-ven  -> FONDI_EU_FETCH + AZIONI + ETF+FONDI+EU (in sequenza)
  08:00 lun/mer/ven -> social_automation.py

AVVIO:
  python scheduler_daemon.py

STOP:
  CTRL+C
"""

import os
import socket
import sys
import logging
import subprocess
import time
import smtplib
from email.mime.text import MIMEText
import requests
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
except ImportError:
    pass

try:
    import whatsapp_service as _wa
    _WA_OK = True
except ImportError:
    _WA_OK = False

# Brevo IPv4 patch — Brevo blocca IPv6 non whitelistati
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_getaddrinfo(host, port, family=0, *a, **kw):
    if host and (host.endswith("brevo.com") or host.endswith("mailin.fr")):
        family = socket.AF_INET
    return _orig_getaddrinfo(host, port, family, *a, **kw)
socket.getaddrinfo = _ipv4_getaddrinfo

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON   = sys.executable

ORCHESTRATOR_PATH      = os.path.join(BASE_DIR, 'orchestrator.py')
SOCIAL_AUTOMATION_PATH = os.path.join(BASE_DIR, 'social_automation.py')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, 'scheduler_daemon.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger('scheduler')


def _notify_brevo(subject, html):
    api_key      = os.getenv('BREVO_API_KEY', '')
    sender_email = os.getenv('BREVO_SENDER_EMAIL', 'marketing@fuerteventurecapital.com')
    sender_name  = os.getenv('BREVO_SENDER_NAME',  'Fuerte Venture Capital SL')
    smtp_host    = os.getenv('BREVO_SMTP_HOST', 'smtp.gmail.com')
    smtp_port    = int(os.getenv('BREVO_SMTP_PORT', '587'))
    smtp_user    = os.getenv('BREVO_SMTP_LOGIN', '')
    smtp_pwd     = os.getenv('BREVO_SMTP_PASSWORD', '')

    if api_key:
        try:
            resp = requests.post(
                'https://api.brevo.com/v3/smtp/email',
                headers={'api-key': api_key, 'content-type': 'application/json'},
                json={
                    'sender': {'name': sender_name, 'email': sender_email},
                    'to':     [{'email': 'rioluc63@gmail.com', 'name': 'Luciano'}],
                    'subject': subject,
                    'htmlContent': html,
                },
                timeout=15,
            )
            resp.raise_for_status()
            logger.info('Email inviata OK via Brevo')
            return
        except Exception as e:
            logger.warning('Brevo fallito (%s) — fallback Gmail SMTP' % e)

    if smtp_user and smtp_pwd:
        try:
            msg = MIMEText(html, 'html', 'utf-8')
            msg['Subject'] = subject
            msg['From']    = smtp_user
            msg['To']      = 'rioluc63@gmail.com'
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as smtp:
                smtp.ehlo(); smtp.starttls(); smtp.login(smtp_user, smtp_pwd)
                smtp.sendmail(smtp_user, ['rioluc63@gmail.com'], msg.as_string())
            logger.info('Email inviata OK via SMTP')
        except Exception as e2:
            logger.warning('Email fallita anche via SMTP: %s' % e2)


def _run_orchestrator(tipi, job_label, timeout_sec):
    logger.info('=' * 70)
    logger.info('JOB %s — INIZIO  %s' % (job_label, datetime.now().strftime('%d/%m/%Y %H:%M:%S')))
    logger.info('=' * 70)
    if not os.path.exists(ORCHESTRATOR_PATH):
        logger.error('orchestrator.py non trovato')
        return False
    try:
        result = subprocess.run(
            [PYTHON, ORCHESTRATOR_PATH] + tipi,
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout_sec,
        )
        if result.stdout:
            logger.info('OUTPUT:\n%s' % result.stdout[-4000:])
        if result.stderr:
            logger.warning('STDERR:\n%s' % result.stderr[-2000:])
        ok = result.returncode == 0
        logger.info('JOB %s — %s' % (job_label, 'COMPLETATO' if ok else 'ERRORE (rc=%d)' % result.returncode))
        return ok
    except subprocess.TimeoutExpired:
        logger.error('JOB %s — TIMEOUT dopo %d sec' % (job_label, timeout_sec))
        return False
    except Exception as e:
        logger.error('JOB %s — ECCEZIONE: %s' % (job_label, e))
        return False
    finally:
        logger.info('=' * 70)


def _watchdog_check():
    """Controlla alle 07:30 (mar-sab) che i report della notte precedente siano stati generati.
    Se mancano, invia email di allarme a rioluc63@gmail.com."""
    import glob as _glob
    from datetime import timedelta
    now  = datetime.now()
    # I report devono essere stati scritti dopo le 20:00 di ieri
    cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=4)  # 20:00 ieri
    reports_dir = os.path.join(os.path.dirname(BASE_DIR), 'REPORTS_DAILY')
    if not os.path.isdir(reports_dir):
        logger.warning('[WATCHDOG] REPORTS_DAILY non trovata')
        return
    recent = [f for f in _glob.glob(os.path.join(reports_dir, '*.xlsx'))
              if os.path.getmtime(f) >= cutoff.timestamp()]
    types_found = set()
    for f in recent:
        bn = os.path.basename(f).upper()
        for t in ('AZIONI', 'ETF', 'FONDI_EU', 'FONDI'):
            if bn.startswith(t + '_SCREENER_'):
                types_found.add(t)
    expected = {'AZIONI', 'ETF', 'FONDI', 'FONDI_EU'}
    missing  = expected - types_found
    logger.info('[WATCHDOG] Report trovati: %s' % (types_found or 'NESSUNO'))
    if missing:
        msg = ('Screener notturno INCOMPLETO.\n'
               'Report trovati: %s\n'
               'Mancanti: %s\n\n'
               'Controllare /root/rt2026/scheduler_daemon.log e il servizio rt2026-scheduler.service.\n'
               'Per rilanciare manualmente: python /root/rt2026/orchestrator.py'
               % (', '.join(types_found) or 'NESSUNO', ', '.join(missing)))
        _notify_brevo(
            subject='[RT2026] ⚠️ WATCHDOG: report mancanti — %s' % now.strftime('%d/%m/%Y'),
            html='<pre style="font-family:monospace;">%s</pre>' % msg,
        )
        logger.warning('[WATCHDOG] ALLARME: %s' % msg)
    else:
        logger.info('[WATCHDOG] ✅ Tutti i report presenti (%d file)' % len(recent))
        if _WA_OK:
            try:
                stats = _wa.notify_screener_ready()
                logger.info('[WATCHDOG] WhatsApp notify_screener_ready: sent=%d failed=%d skipped=%d' % (
                    stats['sent'], stats['failed'], stats['skipped']))
            except Exception as e_wa:
                logger.warning('[WATCHDOG] WhatsApp fallito: %s' % e_wa)


def run_screeners():
    """Lancio unico alle 21:00 lun-ven: FONDI_EU_FETCH → AZIONI → ETF+FONDI+EU in sequenza."""
    ts = datetime.now().strftime('%d/%m/%Y %H:%M')
    _notify_brevo(
        subject='[RT2026] ▶ Screener AVVIATO — %s' % ts,
        html='<p>Screener RT2026 avviato alle <b>%s</b>.</p><p>Sequenza: Fondi EU → Azioni → ETF+Fondi. Riceverai mail quando i report sono pronti.</p>' % ts,
    )

    _run_orchestrator(['FONDI_EU_FETCH'], 'FONDI_EU_FETCH', timeout_sec=3600)
    ok_azioni = _run_orchestrator(['AZIONI'], 'AZIONI', timeout_sec=7200)
    logger.info('Pausa 5 min tra AZIONI e ETF — reset rate limit Yahoo Finance...')
    time.sleep(300)
    _run_orchestrator(['ETF', 'FONDI', 'FONDI_EU'], 'ETF+FONDI+EU', timeout_sec=25200)




def run_social():
    logger.info('=' * 70)
    logger.info('JOB SOCIAL — INIZIO  %s' % datetime.now().strftime('%d/%m/%Y %H:%M:%S'))
    logger.info('=' * 70)
    if not os.path.exists(SOCIAL_AUTOMATION_PATH):
        logger.warning('social_automation.py non trovato — job saltato')
        return
    try:
        result = subprocess.run(
            [PYTHON, SOCIAL_AUTOMATION_PATH],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=300,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
        )
        if result.stdout:
            logger.info('OUTPUT:\n%s' % result.stdout)
        if result.stderr:
            logger.warning('STDERR:\n%s' % result.stderr)
        ok = result.returncode == 0
        logger.info('JOB SOCIAL — %s' % ('COMPLETATO' if ok else 'ERRORE'))
        if ok and _WA_OK:
            try:
                stats = _wa.notify_morning_brief()
                logger.info('WhatsApp brief_mattutino: sent=%d failed=%d skipped=%d' % (
                    stats['sent'], stats['failed'], stats['skipped']))
            except Exception as e_wa:
                logger.warning('WhatsApp notify_morning_brief fallito: %s' % e_wa)
    except subprocess.TimeoutExpired:
        logger.error('JOB SOCIAL — TIMEOUT dopo 5 minuti')
    except Exception as e:
        logger.error('JOB SOCIAL — ECCEZIONE: %s' % e)
    logger.info('=' * 70)


if __name__ == '__main__':
    logger.info('=' * 70)
    logger.info('ROBOT TRADER 2026 — SCHEDULER DAEMON')
    logger.info('Start: %s' % datetime.now().strftime('%d/%m/%Y %H:%M:%S'))
    logger.info('=' * 70)
    logger.info('Job schedulati:')
    logger.info('  [1] Screener completo  -> 21:00 lun-ven  (Fondi EU + Azioni + ETF+Fondi)')
    logger.info('  [2] Social             -> 08:00 lun/mer/ven')
    logger.info('  [3] Watchdog + WhatsApp -> 07:00 mar-sab')
    logger.info('')

    scheduler = BackgroundScheduler(timezone='Atlantic/Canary')

    scheduler.add_job(
        func=run_screeners,
        trigger=CronTrigger(day_of_week='mon-fri', hour=21, minute=0, timezone='Atlantic/Canary'),
        id='screeners',
        name='Screener completo 21:00',
        misfire_grace_time=300,
        coalesce=True,
    )

    scheduler.add_job(
        func=run_social,
        trigger=CronTrigger(day_of_week='mon,wed,fri', hour=8, minute=0, timezone='Atlantic/Canary'),
        id='social_automation',
        name='Social Automation',
        misfire_grace_time=1800,
        coalesce=True,
    )

    scheduler.add_job(
        func=_watchdog_check,
        trigger=CronTrigger(day_of_week='tue,wed,thu,fri,sat', hour=7, minute=0, timezone='Atlantic/Canary'),
        id='watchdog',
        name='Watchdog + WhatsApp 07:00',
        misfire_grace_time=1800,
        coalesce=True,
    )

    scheduler.start()
    logger.info('Scheduler avviato. In attesa dei job...')

    _notify_brevo(
        subject='[RT2026] Scheduler AVVIATO — %s' % datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
        html='<p>Scheduler RT2026 avviato. Job attivi: Screener 21:00 lun-ven, Social 08:00 lun/mer/ven.</p>',
    )

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info('SCHEDULER FERMATO (CTRL+C)')
        scheduler.shutdown()
        sys.exit(0)
    except Exception as e:
        logger.error('ERRORE CRITICO: %s' % e)
        scheduler.shutdown()
        sys.exit(1)
