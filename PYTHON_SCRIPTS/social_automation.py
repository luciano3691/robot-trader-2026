"""
Social Automation — Robot Trader 2026 / Fuerte Venture Capital
Orchestratore giornaliero: legge il calendario, genera il contenuto,
salva il draft e invia email di approvazione all'admin.

Esecuzione: chiamato da scheduler_daemon.py alle 08:00
Oppure manuale: python social_automation.py
"""
import json
import os
import sys
from datetime import datetime
from typing import Optional

try:
    from content_generator import generate_post as _generate_post
    _CONTENT_OK = True
except ImportError:
    _generate_post = None
    _CONTENT_OK = False

try:
    from social_publisher import BrevoService as _BrevoService, publish_to_all_channels as _publish_to_all_channels
    _PUBLISHER_OK = True
except ImportError:
    _BrevoService = None
    _publish_to_all_channels = None
    _PUBLISHER_OK = False

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
DRAFTS_DIR    = os.path.join(BASE_DIR, "SOCIAL_DRAFTS")
CALENDAR_FILE = os.path.join(BASE_DIR, "social_calendar.json")
PUBLISHED_LOG = os.path.join(BASE_DIR, "SOCIAL_DRAFTS", "published.json")
os.makedirs(DRAFTS_DIR, exist_ok=True)


# ── Calendario ────────────────────────────────────────────────────────────────

def _load_calendar() -> list[dict]:
    if not os.path.exists(CALENDAR_FILE):
        print("[SocialAuto] social_calendar.json non trovato")
        return []
    with open(CALENDAR_FILE, encoding='utf-8') as f:
        return json.load(f).get('calendar', [])


def get_today_entry(today: Optional[str] = None) -> Optional[dict]:
    """Ritorna l'entry del calendario per oggi (formato YYYY-MM-DD)."""
    today = today or datetime.now().strftime('%Y-%m-%d')
    for entry in _load_calendar():
        if entry.get('date') == today:
            return entry
    return None


def get_next_scheduled() -> Optional[dict]:
    """Ritorna la prossima entry futura nel calendario (utile per preview)."""
    today = datetime.now().strftime('%Y-%m-%d')
    future = [e for e in _load_calendar() if e.get('date', '') >= today]
    return future[0] if future else None


# ── Draft management ──────────────────────────────────────────────────────────

def _load_published() -> list[str]:
    if not os.path.exists(PUBLISHED_LOG):
        return []
    with open(PUBLISHED_LOG, encoding='utf-8') as f:
        return json.load(f)


def _mark_published(draft_id: str):
    published = _load_published()
    if draft_id not in published:
        published.append(draft_id)
    with open(PUBLISHED_LOG, 'w', encoding='utf-8') as f:
        json.dump(published, f, indent=2)


def save_draft(draft: dict) -> str:
    """Salva il draft JSON in SOCIAL_DRAFTS/. Ritorna il path del file."""
    path = os.path.join(DRAFTS_DIR, f"draft_{draft['draft_id']}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(draft, f, indent=2, ensure_ascii=False)
    return path


def load_draft(draft_id: str) -> Optional[dict]:
    path = os.path.join(DRAFTS_DIR, f"draft_{draft_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def update_draft_status(draft_id: str, status: str, publish_results: Optional[dict] = None):
    draft = load_draft(draft_id)
    if not draft:
        return
    draft['status']     = status
    draft['updated_at'] = datetime.now().isoformat()
    if publish_results:
        draft['publish_results'] = publish_results
    save_draft(draft)


def list_pending_drafts() -> list[dict]:
    """Ritorna tutti i draft con status='pending'."""
    pending = []
    for fname in sorted(os.listdir(DRAFTS_DIR)):
        if not fname.startswith('draft_') or not fname.endswith('.json'):
            continue
        path = os.path.join(DRAFTS_DIR, fname)
        try:
            with open(path, encoding='utf-8') as f:
                d = json.load(f)
            if d.get('status') == 'pending':
                pending.append(d)
        except Exception:
            continue
    return pending


def list_all_drafts(limit: int = 30) -> list[dict]:
    """Ritorna gli ultimi N draft (tutti gli stati)."""
    drafts = []
    for fname in sorted(os.listdir(DRAFTS_DIR), reverse=True):
        if not fname.startswith('draft_') or not fname.endswith('.json'):
            continue
        path = os.path.join(DRAFTS_DIR, fname)
        try:
            with open(path, encoding='utf-8') as f:
                drafts.append(json.load(f))
        except Exception:
            continue
        if len(drafts) >= limit:
            break
    return drafts


# ── Flusso principale ─────────────────────────────────────────────────────────

def run(force_theme: Optional[str] = None, force_date: Optional[str] = None):
    """
    Esegue il ciclo completo per oggi:
    1. Cerca entry nel calendario
    2. Genera testo (Claude API o template)
    3. Salva draft
    4. Invia email approvazione
    """
    generate_post = _generate_post
    BrevoService  = _BrevoService

    if not _CONTENT_OK or not _PUBLISHER_OK:
        print("[SocialAuto] Moduli content_generator / social_publisher non disponibili — skip")
        return None

    today     = force_date or datetime.now().strftime('%Y-%m-%d')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    print(f"\n{'='*55}")
    print(f"  SOCIAL AUTOMATION — {today}")
    print(f"{'='*55}\n")

    # 1. Trova entry calendario
    entry = get_today_entry(today)
    if not entry and not force_theme:
        print(f"[SocialAuto] Nessun post pianificato per {today} — skip")
        return None

    if force_theme:
        entry = entry or {
            "date":        today,
            "theme":       force_theme,
            "lang":        "IT",
            "channels":    ["linkedin", "facebook"],
            "article_url": None,
            "image_url":   None,
        }
        entry['theme'] = force_theme

    theme    = entry['theme']
    lang     = entry.get('lang', 'IT')
    channels = entry.get('channels', ['linkedin', 'facebook'])
    print(f"  Tema:    {theme}")
    print(f"  Lingua:  {lang}")
    print(f"  Canali:  {', '.join(channels)}\n")

    # 2. Genera testo
    # Genera sempre IT + ES (per avere entrambe le versioni nel draft)
    text_it = generate_post(theme, 'IT')
    text_es = generate_post(theme, 'ES')

    # 3. Crea draft
    draft = {
        "draft_id":    timestamp,
        "date":        today,
        "theme":       theme,
        "lang":        lang,
        "channels":    channels,
        "text_it":     text_it,
        "text_es":     text_es,
        "image_url":   entry.get('image_url'),
        "article_url": entry.get('article_url'),
        "status":      "pending",
        "created_at":  datetime.now().isoformat(),
    }
    draft_path = save_draft(draft)
    print(f"  Draft salvato: {draft_path}\n")
    print(f"  Testo (IT preview):\n  {text_it[:200]}...\n")

    # 4. Invia email approvazione
    brevo = BrevoService()
    if brevo.ready_smtp():
        ok = brevo.send_approval_email(draft)
        print(f"  Email approvazione: {'OK' if ok else 'FALLITA (configura Brevo SMTP)'}")
    else:
        print("  [ATTENZIONE] Brevo SMTP non configurato — draft salvato ma nessuna email inviata")
        print(f"  Approva manualmente: http://localhost:5000/api/social/approve?draft_id={timestamp}&action=approve")

    print(f"\n{'='*55}\n")
    return draft


def approve_and_publish(draft_id: str) -> dict:
    """
    Approva un draft e lo pubblica su tutti i canali configurati.
    Chiamato dal webhook /api/social/approve in dashboard.py.
    """
    publish_to_all_channels = _publish_to_all_channels

    if not _PUBLISHER_OK:
        return {"ok": False, "detail": "social_publisher non disponibile"}

    draft = load_draft(draft_id)
    if not draft:
        return {"ok": False, "detail": f"Draft {draft_id} non trovato"}
    if draft.get('status') == 'published':
        return {"ok": False, "detail": "Draft già pubblicato"}

    update_draft_status(draft_id, 'publishing')
    results = publish_to_all_channels(draft)
    update_draft_status(draft_id, 'published', results)
    _mark_published(draft_id)

    ok_count = sum(1 for v in results.values() if v.get('ok'))
    return {
        "ok":       ok_count > 0,
        "draft_id": draft_id,
        "results":  results,
        "summary":  f"{ok_count}/{len(results)} canali pubblicati con successo",
    }


def reject_draft(draft_id: str) -> dict:
    """Segna il draft come rifiutato."""
    draft = load_draft(draft_id)
    if not draft:
        return {"ok": False, "detail": f"Draft {draft_id} non trovato"}
    update_draft_status(draft_id, 'rejected')
    return {"ok": True, "draft_id": draft_id, "status": "rejected"}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Uso: python social_automation.py [--theme TEMA] [--date YYYY-MM-DD]
    import argparse
    parser = argparse.ArgumentParser(description="Social Automation Robot Trader 2026")
    parser.add_argument('--theme', help='Forza un tema specifico (es: VALUE_INTRO)')
    parser.add_argument('--date',  help='Data YYYY-MM-DD (default: oggi)')
    parser.add_argument('--list',  action='store_true', help='Mostra draft in attesa')
    args = parser.parse_args()

    if args.list:
        pending = list_pending_drafts()
        if not pending:
            print("Nessun draft in attesa di approvazione.")
        else:
            print(f"\n{len(pending)} draft in attesa:\n")
            for d in pending:
                print(f"  [{d['draft_id']}] {d['date']} · {d['theme']} · {d['lang']}")
                print(f"    Canali: {', '.join(d.get('channels', []))}")
                print(f"    Approva: http://localhost:5000/api/social/approve?draft_id={d['draft_id']}&action=approve\n")
    else:
        run(force_theme=args.theme, force_date=args.date)
