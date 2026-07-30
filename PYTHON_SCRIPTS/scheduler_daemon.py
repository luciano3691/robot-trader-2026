# -*- coding: utf-8 -*-
"""
SCHEDULER DAEMON - Robot Trader 2026
=====================================
Job schedulati (orario Canarie — Atlantic/Canary):
  20:30 lun-ven       -> orchestrator.py FONDI_EU_FETCH    (aggiorna universo fondi EU + email admin)
  21:00 lun-ven       -> orchestrator.py AZIONI            (screener AZIONI + email clienti)
  21:45 lun-ven       -> orchestrator.py ETF FONDI FONDI_EU (screener ETF+FONDI+EU + email clienti)
  08:00 lun/mer/ven   -> social_automation.py              (post social + WhatsApp brief_mattutino)

Logica:
  - FONDI_EU_FETCH ogni giorno feriale (--update: solo errori/mancanti, ~40 min)
  - AZIONI ogni giorno feriale (alta volatilità, segnali cambiano ogni giorno)
  - ETF+FONDI+EU ogni giorno feriale (email clienti tutti i giorni)
  - Social lun/mer/ven (cadenza editoriale)

AVVIO:
  python scheduler_daemon.py

STOP:
  CTRL+C
"""

import os
import sys
import logging
import subprocess
import time
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

try:
    import whatsapp_service as _wa
    _WA_OK = True
except ImportError:
    _WA_OK = False

# ---------------------------------------------------------------------------
# PATH
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON   = sys.executable  # usa sempre il Python corrente

ORCHESTRATOR_PATH     = os.path.join(BASE_DIR, 'orchestrator.py')
SOCIAL_AUTOMATION_PATH = os.path.join(BASE_DIR, 'social_automation.py')

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, 'scheduler_daemon.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger('scheduler')

# ---------------------------------------------------------------------------
# Helper — esegue orchestrator con i tipi specificati
# ---------------------------------------------------------------------------

def _run_orchestrator(tipi, job_label, timeout_sec):
    """Esegue orchestrator.py con i tipi indicati e logga il risultato.
    tipi: lista di stringhe, es. ['AZIONI'] o ['ETF', 'FONDI']
    """
    logger.info("=" * 70)
    logger.info("JOB %s — INIZIO  %s" % (job_label, datetime.now().strftime('%d/%m/%Y %H:%M:%S')))
    logger.info("=" * 70)

    if not os.path.exists(ORCHESTRATOR_PATH):
        logger.error("ERRORE: orchestrator.py non trovato in %s" % BASE_DIR)
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
            logger.info("OUTPUT:\n%s" % result.stdout[-4000:])
        if result.stderr:
            logger.warning("STDERR:\n%s" % result.stderr[-2000:])
        if result.returncode == 0:
            logger.info("JOB %s — COMPLETATO CON SUCCESSO" % job_label)
            return True
        else:
            logger.error("JOB %s — ERRORE (returncode=%d)" % (job_label, result.returncode))
            return False
    except subprocess.TimeoutExpired:
        logger.error("JOB %s — TIMEOUT dopo %d sec" % (job_label, timeout_sec))
        return False
    except Exception as e:
        logger.error("JOB %s — ECCEZIONE: %s" % (job_label, e))
        return False
    finally:
        logger.info("=" * 70)


# ---------------------------------------------------------------------------
# JOB 0 — Aggiorna universo Fondi EU (22:30 lun-ven)
# ---------------------------------------------------------------------------

def run_fetch_fondi_eu():
    _run_orchestrator(['FONDI_EU_FETCH'], 'FONDI_EU_FETCH', timeout_sec=3600)  # max 1h


# ---------------------------------------------------------------------------
# JOB 1a — Screener AZIONI (23:00 lun-ven)
# ---------------------------------------------------------------------------

def run_screeners_azioni():
    ok = _run_orchestrator(['AZIONI'], 'AZIONI', timeout_sec=3600)  # max 1h
    if ok and _WA_OK:
        try:
            stats = _wa.notify_screener_ready()
            logger.info("WhatsApp screener_pronto: sent=%d failed=%d skipped=%d" % (
                stats['sent'], stats['failed'], stats['skipped']))
        except Exception as e_wa:
            logger.warning("WhatsApp notify_screener_ready fallito: %s" % e_wa)


# ---------------------------------------------------------------------------
# JOB 1b — Screener ETF + FONDI (23:30 lun-ven, ogni giorno)
# ---------------------------------------------------------------------------

def run_screeners_etf_fondi():
    _run_orchestrator(['ETF', 'FONDI', 'FONDI_EU'], 'ETF+FONDI+EU', timeout_sec=25200)  # max 7h

# ---------------------------------------------------------------------------
# JOB 2 — Social automation (08:00 lun/mer/ven)
# ---------------------------------------------------------------------------

def run_social():
    logger.info("=" * 70)
    logger.info("JOB SOCIAL — INIZIO  %s" % datetime.now().strftime('%d/%m/%Y %H:%M:%S'))
    logger.info("=" * 70)

    if not os.path.exists(SOCIAL_AUTOMATION_PATH):
        logger.warning("social_automation.py non trovato — job saltato")
        return

    try:
        result = subprocess.run(
            [PYTHON, SOCIAL_AUTOMATION_PATH],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=300,  # 5 minuti
        )
        if result.stdout:
            logger.info("OUTPUT:\n%s" % result.stdout)
        if result.stderr:
            logger.warning("STDERR:\n%s" % result.stderr)
        if result.returncode == 0:
            logger.info("JOB SOCIAL — COMPLETATO CON SUCCESSO")
            if _WA_OK:
                try:
                    stats = _wa.notify_morning_brief()
                    logger.info("WhatsApp brief_mattutino: sent=%d failed=%d skipped=%d" % (
                        stats['sent'], stats['failed'], stats['skipped']))
                except Exception as e_wa:
                    logger.warning("WhatsApp notify_morning_brief fallito: %s" % e_wa)
        else:
            logger.error("JOB SOCIAL — ERRORE (returncode=%d)" % result.returncode)
    except subprocess.TimeoutExpired:
        logger.error("JOB SOCIAL — TIMEOUT dopo 5 minuti")
    except Exception as e:
        logger.error("JOB SOCIAL — ECCEZIONE: %s" % e)

    logger.info("=" * 70)

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    logger.info("")
    logger.info("=" * 70)
    logger.info("ROBOT TRADER 2026 — SCHEDULER DAEMON")
    logger.info("Start: %s" % datetime.now().strftime('%d/%m/%Y %H:%M:%S'))
    logger.info("Base dir: %s" % BASE_DIR)
    logger.info("Python: %s" % PYTHON)
    logger.info("=" * 70)

    # Verifica file critici
    for path, label in [(ORCHESTRATOR_PATH, 'orchestrator.py'), (SOCIAL_AUTOMATION_PATH, 'social_automation.py')]:
        if os.path.exists(path):
            logger.info("  OK   %s" % label)
        else:
            logger.warning("  WARN %s non trovato" % label)

    logger.info("")
    logger.info("Job schedulati:")
    logger.info("  [0] Fetch Fondi EU     -> 22:30 lun-ven       (orchestrator.py FONDI_EU_FETCH)")
    logger.info("  [1] Screener AZIONI    -> 23:00 lun-ven       (orchestrator.py AZIONI)")
    logger.info("  [2] Screener ETF+FONDI+EU -> 23:30 lun-ven   (orchestrator.py ETF FONDI FONDI_EU)")
    logger.info("  [3] Social             -> 08:00 lun/mer/ven   (social_automation.py)")
    logger.info("")

    scheduler = BackgroundScheduler(timezone='Atlantic/Canary')

    # Job 0: aggiorna universo fondi EU — ogni giorno feriale alle 20:30 Canarie
    scheduler.add_job(
        func=run_fetch_fondi_eu,
        trigger=CronTrigger(day_of_week='mon-fri', hour=20, minute=30, timezone='Atlantic/Canary'),
        id='fetch_fondi_eu',
        name='Fetch Fondi EU Universe',
        misfire_grace_time=300,
        coalesce=True,
    )

    # Job 1a: screener AZIONI — ogni giorno feriale alle 21:00 Canarie
    scheduler.add_job(
        func=run_screeners_azioni,
        trigger=CronTrigger(day_of_week='mon-fri', hour=21, minute=0, timezone='Atlantic/Canary'),
        id='screener_azioni',
        name='Screener AZIONI',
        misfire_grace_time=300,
        coalesce=True,
    )

    # Job 1b: screener ETF+FONDI+EU — ogni giorno feriale alle 21:45 Canarie
    scheduler.add_job(
        func=run_screeners_etf_fondi,
        trigger=CronTrigger(day_of_week='mon-fri', hour=21, minute=45, timezone='Atlantic/Canary'),
        id='screener_etf_fondi',
        name='Screener ETF+FONDI+EU',
        misfire_grace_time=300,
        coalesce=True,
    )

    # Job 2: social — lun/mer/ven alle 08:00
    scheduler.add_job(
        func=run_social,
        trigger=CronTrigger(day_of_week='mon,wed,fri', hour=8, minute=0, timezone='Atlantic/Canary'),
        id='social_automation',
        name='Social Automation',
        misfire_grace_time=1800,
        coalesce=True,
    )

    scheduler.start()
    logger.info("Scheduler avviato. Premi CTRL+C per fermare.")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("")
        logger.info("SCHEDULER FERMATO (CTRL+C)")
        scheduler.shutdown()
        sys.exit(0)
    except Exception as e:
        logger.error("ERRORE CRITICO: %s" % e)
        scheduler.shutdown()
        sys.exit(1)
