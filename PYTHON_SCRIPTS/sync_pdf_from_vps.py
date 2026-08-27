# -*- coding: utf-8 -*-
"""
RT2026 — Sync PDF dal VPS in locale
Scarica da /root/REPORTS_PDF/ solo i file non ancora presenti in locale.
Eseguito ogni mattina dal Windows Task Scheduler.
"""

import os
import sys
import paramiko
from datetime import datetime

VPS_HOST = '178.104.93.65'
VPS_USER = 'root'
VPS_PASS = 'tbLVCktVKCp3'

REMOTE_DIR = '/root/REPORTS_PDF'
LOCAL_DIR  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'REPORTS_PDF')

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sync_pdf.log')


def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def sync():
    os.makedirs(LOCAL_DIR, exist_ok=True)
    log(f'Sync PDF VPS → {LOCAL_DIR}')

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASS, timeout=30)
        sftp = ssh.open_sftp()
    except Exception as e:
        log(f'ERRORE connessione VPS: {e}')
        sys.exit(1)

    try:
        remote_files = sftp.listdir(REMOTE_DIR)
    except Exception as e:
        log(f'ERRORE lettura REPORTS_PDF: {e}')
        sftp.close(); ssh.close()
        sys.exit(1)

    scaricati = 0
    for fname in sorted(remote_files):
        if not fname.endswith('.pdf'):
            continue
        local_path = os.path.join(LOCAL_DIR, fname)
        if os.path.exists(local_path):
            continue
        try:
            sftp.get(f'{REMOTE_DIR}/{fname}', local_path)
            size = os.path.getsize(local_path)
            log(f'  Scaricato: {fname} ({size // 1024} KB)')
            scaricati += 1
        except Exception as e:
            log(f'  ERRORE {fname}: {e}')

    sftp.close()
    ssh.close()

    if scaricati == 0:
        log('Nessun file nuovo.')
    else:
        log(f'Sync completato: {scaricati} PDF scaricati.')


if __name__ == '__main__':
    sync()
