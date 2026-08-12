# -*- coding: utf-8 -*-
"""
ORCHESTRATOR - ROBOT TRADER 2026
Esegue screener + invia email per piano (BASIC/PRO/VALUE)

Uso:
  python orchestrator.py                      # tutti gli screener
  python orchestrator.py AZIONI               # solo AZIONI
  python orchestrator.py ETF FONDI            # solo ETF e FONDI
  python orchestrator.py FONDI_EU_FETCH       # aggiorna universo fondi EU + email admin
"""
import subprocess
import sys
import os
import time
import threading
import json
import smtplib
import requests
from email.mime.text import MIMEText
from datetime import datetime

try:
    import whatsapp_service as _wa
    _WA_OK = True
except ImportError:
    _WA_OK = False

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr = sys.stdout

PYTHON_EXE  = sys.executable
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(os.path.dirname(BASE_DIR), "REPORTS_DAILY")
LOGS_DIR    = os.path.join(os.path.dirname(BASE_DIR), "LOGS")
os.makedirs(LOGS_DIR, exist_ok=True)

_log_path = os.path.join(LOGS_DIR, "orchestrator_%s.log" % datetime.now().strftime('%Y%m%d_%H%M%S'))
_log_file = open(_log_path, 'w', encoding='utf-8', buffering=1)

class _Tee:
    def __init__(self, *streams): self.streams = streams
    def write(self, data):
        for s in self.streams:
            s.write(data)
    def flush(self):
        for s in self.streams:
            s.flush()
    def reconfigure(self, **kw): pass

sys.stdout = _Tee(sys.__stdout__, _log_file)
sys.stderr = sys.stdout

PIANI = ["BASIC", "PRO", "VALUE"]

ALL_SCREENERS = [
    {"script": "fetch_fondi_eu_universe.py",  "type": "FONDI_EU_FETCH", "args": ["--update"], "admin_only": True},
    {"script": "value_screener_azioni.py",    "type": "AZIONI"},
    {"script": "value_screener_etf.py",       "type": "ETF"},
    {"script": "value_screener_fondi.py",     "type": "FONDI"},
    {"script": "value_screener_fondi_eu.py",  "type": "FONDI_EU"},
]

# Filtro opzionale da riga di comando: python orchestrator.py AZIONI  oppure  ETF FONDI
_tipi_richiesti = [t.upper() for t in sys.argv[1:]] if len(sys.argv) > 1 else []
screeners = [s for s in ALL_SCREENERS if not _tipi_richiesti or s['type'] in _tipi_richiesti]


TIMEOUT_SCREENER = 18000  # 5h max per screener (ETF: 3664 ticker ~2.5h)

# ---------------------------------------------------------------------------
# Email admin (per notifiche interne, es. FONDI_EU_FETCH)
# ---------------------------------------------------------------------------

def _load_smtp():
    cfg_path = os.path.join(BASE_DIR, 'config.json')
    try:
        with open(cfg_path, encoding='utf-8') as f:
            cfg = json.load(f).get('email', {})
    except Exception:
        cfg = {}
    host   = os.getenv('BREVO_SMTP_HOST', 'smtp-relay.brevo.com')
    login  = os.getenv('BREVO_SMTP_LOGIN', '') or cfg.get('smtp_login', '')
    pwd    = os.getenv('BREVO_SMTP_PASSWORD', '')
    sender = os.getenv('BREVO_SENDER_EMAIL', '') or cfg.get('sender', login)
    admin  = cfg.get('admin_email', 'rioluc63@gmail.com')
    return host, login, pwd, sender, admin

def send_admin_email(subject, body_text):
    admin = _load_smtp()[4]
    # Tentativo 1: Brevo REST API
    api_key     = os.getenv('BREVO_API_KEY', '')
    sender_email = os.getenv('BREVO_SENDER_EMAIL', 'marketing@fuerteventurecapital.com')
    sender_name  = os.getenv('BREVO_SENDER_NAME',  'Fuerte Venture Capital SL')
    if api_key:
        try:
            resp = requests.post(
                'https://api.brevo.com/v3/smtp/email',
                headers={'api-key': api_key, 'content-type': 'application/json'},
                json={
                    'sender':      {'name': sender_name, 'email': sender_email},
                    'to':          [{'email': admin, 'name': 'Admin'}],
                    'subject':     subject,
                    'textContent': body_text,
                },
                timeout=15,
            )
            resp.raise_for_status()
            print(f"  [ADMIN EMAIL] Inviata a {admin} via Brevo (HTTP {resp.status_code})", flush=True)
            return
        except Exception as e:
            print(f"  [ADMIN EMAIL] Brevo fallito ({e}) — fallback SMTP", flush=True)
    # Tentativo 2: SMTP fallback
    host, login, pwd, sender, _ = _load_smtp()
    if not login or not pwd:
        print(f"  [ADMIN EMAIL] SMTP non configurato — email non inviata", flush=True)
        return
    try:
        msg = MIMEText(body_text, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From']    = sender
        msg['To']      = admin
        with smtplib.SMTP(host, 587) as srv:
            srv.starttls()
            srv.login(login, pwd)
            srv.sendmail(sender, [admin], msg.as_string())
        print(f"  [ADMIN EMAIL] Inviata a {admin} via SMTP", flush=True)
    except Exception as e:
        print(f"  [ADMIN EMAIL] Errore SMTP: {e}", flush=True)

# ---------------------------------------------------------------------------

def run_live(script_name, extra_args=None):
    """Esegue script con output real-time e timeout automatico (2h)"""
    script_path = os.path.join(BASE_DIR, script_name)
    cmd = [PYTHON_EXE, script_path] + (extra_args or [])
    proc = subprocess.Popen(
        cmd,
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
        bufsize=1
    )

    def _reader():
        for line in proc.stdout:
            print(line, end='', flush=True)

    t = threading.Thread(target=_reader, daemon=True)
    t.start()

    try:
        proc.wait(timeout=TIMEOUT_SCREENER)
    except subprocess.TimeoutExpired:
        print(f"\n⚠️  TIMEOUT {TIMEOUT_SCREENER//60} min — terminazione forzata {script_name}", flush=True)
        proc.kill()
        proc.wait()
        return -1

    t.join(timeout=5)
    return proc.returncode


TIMEOUT_EMAIL = 120  # 2 minuti max per invio email

def send_plan_email(report_type, piano, filename, max_retry=3, retry_wait=30):
    """Chiama email_notifier per un singolo piano, con retry automatico su errore SMTP"""
    for attempt in range(1, max_retry + 1):
        proc = subprocess.Popen(
            [PYTHON_EXE, os.path.join(BASE_DIR, "email_notifier.py"),
             report_type, piano, filename],
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace', bufsize=1
        )

        def _reader():
            for line in proc.stdout:
                print(line, end='', flush=True)

        t = threading.Thread(target=_reader, daemon=True)
        t.start()
        try:
            proc.wait(timeout=TIMEOUT_EMAIL)
        except subprocess.TimeoutExpired:
            print(f"  ⚠️  TIMEOUT email {report_type} {piano} — terminazione forzata", flush=True)
            proc.kill()
            proc.wait()
            return -1
        t.join(timeout=5)

        if proc.returncode == 0:
            return 0
        if attempt < max_retry:
            print(f"  [retry {attempt}/{max_retry}] Riprovo tra {retry_wait}s...")
            sys.stdout.flush()
            time.sleep(retry_wait)
    return proc.returncode


print("=" * 70)
print("ORCHESTRATOR - ROBOT TRADER 2026")
print(f"Avvio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Python: {PYTHON_EXE}")
tipi_label = ', '.join(s['type'] for s in screeners)
print(f"Screener: {tipi_label}  ({len(screeners)}/{len(ALL_SCREENERS)})")
print("=" * 70)

for i, screener in enumerate(screeners, 1):
    print(f"\n[{i}/{len(screeners)}] Eseguendo {screener['script']}...")
    print("-" * 70)
    sys.stdout.flush()

    exit_code = run_live(screener['script'], extra_args=screener.get('args'))

    if exit_code == 0:
        print(f"OK {screener['script']} completato")

        if screener.get('admin_only'):
            # Notifica admin con stats (nessun Excel da inviare ai clienti)
            ts = datetime.now().strftime('%d/%m/%Y %H:%M')
            send_admin_email(
                f"[Robot Trader] {screener['type']} completato — {ts}",
                f"Job {screener['type']} completato con successo alle {ts}.\n"
                f"Script: {screener['script']} {' '.join(screener.get('args', []))}\n"
                f"Controlla la cache aggiornata dalla dashboard (tab Database > Fondi)."
            )
        elif os.path.exists(REPORTS_DIR):
            # Invia email per ogni piano separatamente
            for piano in PIANI:
                files = sorted(
                    [f for f in os.listdir(REPORTS_DIR)
                     if f.upper().startswith(screener['type'] + '_SCREENER_') and piano in f.upper()],
                    reverse=True
                )
                if files:
                    latest_file = files[0]
                    print(f"Invio email {screener['type']} {piano}: {latest_file}")
                    sys.stdout.flush()
                    rc = send_plan_email(screener['type'], piano, latest_file)
                    if rc != 0:
                        print(f"ERRORE invio email {screener['type']} {piano} (exit {rc})")
                else:
                    print(f"ATTENZIONE: nessun file {screener['type']} {piano} in REPORTS_DAILY")
    else:
        print(f"ERRORE durante {screener['script']} (exit {exit_code})")

    sys.stdout.flush()

print("\n" + "=" * 70)
print("ORCHESTRATOR COMPLETATO")
print(f"Fine: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# ── Genera KB report per chatbot abbonati ────────────────────────────────────
def _read_excel_sheet(fpath, sheet_name):
    """Legge un foglio Excel rilevando automaticamente se la riga 0 è un titolo."""
    import pandas as pd
    df = pd.read_excel(fpath, sheet_name=sheet_name, header=0)
    if df.empty:
        return df
    first_col = str(df.columns[0]).lower()
    if not any(first_col.startswith(k) for k in ('ticker', 'isin', 'nome')):
        # Riga 0 è un titolo — rileggi con header=1
        df = pd.read_excel(fpath, sheet_name=sheet_name, header=1)
    return df


def _df_to_md_table(df):
    """Genera tabella markdown da DataFrame (senza dipendenza da tabulate)."""
    import pandas as pd
    if df.empty:
        return "*Nessun dato*"
    cols = list(df.columns)
    sep  = "| " + " | ".join("---" for _ in cols) + " |"
    hdr  = "| " + " | ".join(str(c) for c in cols) + " |"
    rows = []
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            try:
                if pd.isna(v):
                    cells.append("—"); continue
            except (TypeError, ValueError):
                pass
            cells.append(f"{v:.2f}" if isinstance(v, float) else str(v).strip())
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join([hdr, sep] + rows)


def genera_kb_reports():
    """Legge i report Excel più recenti e genera KNOWLEDGE_BASE/kb_reports.md."""
    try:
        import pandas as pd
        import openpyxl  # solo per leggere i nomi dei fogli
    except ImportError as e:
        print(f"  [KB] dipendenza mancante ({e}) — kb_reports.md non generata", flush=True)
        return

    KB_DIR   = os.path.join(BASE_DIR, "KNOWLEDGE_BASE")
    KB_PATH  = os.path.join(KB_DIR, "kb_reports.md")
    now_str  = datetime.now().strftime('%Y-%m-%d %H:%M')

    lines = [
        "# Report Data — Robot Trader 2026",
        f"**Ultima elaborazione:** {now_str}",
        "",
        "Dati degli ultimi screener. Selezionati: tutti i piani. Scartati: solo piano VALUE.",
        "",
    ]

    # Colonne selezionati: solo Ticker/ISIN, Nome, Score (KB compatta)
    screener_configs = [
        {
            "type":          "AZIONI",
            "file_prefix":   "AZIONI_SCREENER_",
            "selected_name": "Azioni Selezionate",
            "scartati_pfx":  "Scartate",
            "excluded_name": "Esclusi - Settore",
            "cols_sel":      ["Ticker", "Nome", "Score"],
        },
        {
            "type":          "ETF",
            "file_prefix":   "ETF_SCREENER_",
            "selected_name": "ETF Selezionati",
            "scartati_pfx":  "Scartati",
            "excluded_name": None,
            "cols_sel":      ["Ticker", "ISIN", "Nome", "Score"],
        },
        {
            "type":          "FONDI",
            "file_prefix":   "FONDI_SCREENER_",
            "selected_name": "Fondi Selezionati",
            "scartati_pfx":  "Scartati",
            "excluded_name": None,
            "cols_sel":      ["Ticker", "Nome", "Score"],
        },
        {
            "type":          "FONDI_EU",
            "file_prefix":   "FONDI_EU_SCREENER_",
            "selected_name": "Fondi Selezionati",
            "scartati_pfx":  "Scartati",
            "excluded_name": None,
            "cols_sel":      ["ISIN", "Ticker", "Nome", "Score"],
        },
    ]

    for sc in screener_configs:
        for piano in ["BASIC", "PRO", "VALUE"]:
            files = sorted(
                [f for f in os.listdir(REPORTS_DIR)
                 if f.upper().startswith(sc["file_prefix"]) and piano in f.upper()],
                reverse=True
            )
            section = f"## {sc['type']} {piano}"
            if not files:
                lines += [section, "*Nessun report disponibile.*", ""]
                continue

            fpath = os.path.join(REPORTS_DIR, files[0])
            try:
                wb          = openpyxl.load_workbook(fpath, read_only=True)
                sheet_names = wb.sheetnames
                wb.close()
            except Exception as e:
                lines += [section, f"*Errore apertura file: {e}*", ""]
                continue

            # ─── SELEZIONATI ─────────────────────────────────────────────────
            if sc["selected_name"] in sheet_names:
                try:
                    df    = _read_excel_sheet(fpath, sc["selected_name"])
                    cols  = [c for c in sc["cols_sel"] if c in df.columns]
                    df    = df[cols].dropna(how='all')
                    n_sel = len(df)
                    lines.append(f"{section} — Selezionati ({n_sel})")
                    lines.append(f"File: `{files[0]}`")
                    lines.append("")
                    lines.append(_df_to_md_table(df))
                    lines.append("")
                except Exception as e:
                    lines += [section, f"*Errore lettura selezionati: {e}*", ""]
            else:
                lines += [section, "*Foglio selezionati non trovato.*", ""]

            # ─── SCARTATI ────────────────────────────────────────────────────
            sc_sheets = [sn for sn in sheet_names if sc["scartati_pfx"] in sn]
            if sc["excluded_name"] and sc["excluded_name"] in sheet_names:
                sc_sheets = [sc["excluded_name"]] + sc_sheets

            if piano == "VALUE" and sc_sheets:
                rows_out = []
                for sn in sc_sheets:
                    try:
                        df_sc = _read_excel_sheet(fpath, sn)
                        if df_sc.empty:
                            continue
                        t_col = next((c for c in df_sc.columns
                                      if str(c).lower() in ('ticker', 'isin')), None)
                        m_col = "Motivo Scarto" if "Motivo Scarto" in df_sc.columns else None
                        if not t_col:
                            continue
                        sheet_reason = sn.replace(sc["scartati_pfx"] + " - ", "").split("(")[0].strip()
                        for _, row in df_sc.iterrows():
                            t = str(row.get(t_col, '')).strip()
                            m = str(row.get(m_col, '')).strip() if m_col else sheet_reason
                            if t and t.lower() != 'nan':
                                rows_out.append(f"| {t} | {m} |")
                    except Exception:
                        continue

                if rows_out:
                    lines.append(f"### Scartati VALUE — {sc['type']} ({len(rows_out)} totali)")
                    lines.append("| Ticker | Motivo |")
                    lines.append("| --- | --- |")
                    lines.extend(rows_out)
                    lines.append("")
            elif sc_sheets:
                # BASIC/PRO: mostra solo i nomi dei fogli con i conteggi
                sc_summary = ", ".join(sn for sn in sc_sheets)
                lines.append(f"*Scartati {piano}: {sc_summary} (dettaglio solo per VALUE)*")
                lines.append("")

            lines.append("---")
            lines.append("")

    content = "\n".join(lines)
    os.makedirs(KB_DIR, exist_ok=True)
    with open(KB_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [KB] kb_reports.md generata: {len(content):,} caratteri → {KB_PATH}", flush=True)

    # Notifica dashboard per ricaricare la KB
    try:
        from urllib.request import urlopen, Request as _Req
        req = _Req(
            "http://localhost:8080/api/internal/reload-kb",
            data=b'{}',
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urlopen(req, timeout=5) as resp:
            print(f"  [KB] Dashboard reload KB: HTTP {resp.status}", flush=True)
    except Exception as e:
        print(f"  [KB] Dashboard reload KB: {e} (non critico)", flush=True)


if os.path.exists(REPORTS_DIR):
    genera_kb_reports()

# ── WhatsApp: notifica a tutti i clienti/tester con opt-in ──────────────────
if _WA_OK:
    print("\nInvio notifiche WhatsApp...")
    try:
        stats = _wa.notify_screener_ready()
        print(f"WhatsApp: inviati={stats['sent']} falliti={stats['failed']} saltati={stats['skipped']}")
    except Exception as e:
        print(f"WhatsApp: errore ({e})")
else:
    print("\nWhatsApp: modulo non disponibile (pip install requests)")
