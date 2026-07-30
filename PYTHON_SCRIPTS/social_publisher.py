"""
Social Publisher — Fuerte Venture Capital / Robot Trader 2026
Pubblica su LinkedIn (Company Page), Facebook Page e Instagram Business.
Invia campagne e email di approvazione via Brevo SMTP.

Credenziali in config.json → sezione "social".
Tutti i PLACEHOLDER sono marcati con # <<< da configurare.
"""
import json
import os
import smtplib
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
except ImportError:
    pass

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE  = os.path.join(BASE_DIR, "config.json")
TOKENS_FILE  = os.path.join(BASE_DIR, "social_tokens.json")
SOCIAL_LOGS  = os.path.join(BASE_DIR, "SOCIAL_LOGS")
os.makedirs(SOCIAL_LOGS, exist_ok=True)


def _cfg() -> dict:
    try:
        with open(CONFIG_FILE, encoding='utf-8') as f:
            cfg = json.load(f).get('social', {})
    except Exception:
        cfg = {}
    # Env vars sovrascrivono config.json per tutte le credenziali sensibili
    li = cfg.setdefault('linkedin', {})
    if os.getenv('LINKEDIN_CLIENT_ID'):     li['client_id']     = os.getenv('LINKEDIN_CLIENT_ID')
    if os.getenv('LINKEDIN_CLIENT_SECRET'): li['client_secret'] = os.getenv('LINKEDIN_CLIENT_SECRET')
    if os.getenv('LINKEDIN_ORG_ID'):        li['org_id']        = os.getenv('LINKEDIN_ORG_ID')
    if os.getenv('LINKEDIN_ACCESS_TOKEN'):  li['access_token']  = os.getenv('LINKEDIN_ACCESS_TOKEN')
    if os.getenv('BASE_URL'):               li['redirect_uri']  = os.getenv('BASE_URL').rstrip('/') + '/api/linkedin/callback'
    meta = cfg.setdefault('meta', {})
    if os.getenv('META_APP_ID'):            meta['app_id']      = os.getenv('META_APP_ID')
    if os.getenv('META_APP_SECRET'):        meta['app_secret']  = os.getenv('META_APP_SECRET')
    if os.getenv('META_PAGE_ID'):           meta['page_id']     = os.getenv('META_PAGE_ID')
    if os.getenv('META_IG_USER_ID'):        meta['ig_user_id']  = os.getenv('META_IG_USER_ID')
    return cfg

def _tokens() -> dict:
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {}

def _save_tokens(tokens: dict):
    with open(TOKENS_FILE, 'w', encoding='utf-8') as f:
        json.dump(tokens, f, indent=2, ensure_ascii=False)

def _log(msg: str):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_file = os.path.join(SOCIAL_LOGS, f"social_{datetime.now().strftime('%Y%m')}.log")
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"[Social] {msg}")


# ── BREVO ─────────────────────────────────────────────────────────────────────

class BrevoService:
    BREVO_API = "https://api.brevo.com/v3"
    SMTP_HOST = "smtp-relay.brevo.com"
    SMTP_PORT = 587

    def __init__(self):
        cfg = _cfg().get('brevo', {})
        self.api_key       = cfg.get('api_key', '')         # <<< PLACEHOLDER: chiave API Brevo
        self.smtp_login    = cfg.get('smtp_login', '')      # <<< PLACEHOLDER: login SMTP Brevo
        self.smtp_password = cfg.get('smtp_password', '')   # <<< PLACEHOLDER: password SMTP Brevo
        self.sender_email  = cfg.get('sender_email', 'marketing@fuerteventurecapital.com')
        self.sender_name   = cfg.get('sender_name', 'Fuerte Venture Capital')
        self.list_ids      = cfg.get('list_ids', [])        # <<< PLACEHOLDER: [ID_LISTA_1, ID_LISTA_2]
        self.admin_email   = cfg.get('admin_email', 'rioluc63@gmail.com')
        self.base_url      = cfg.get('base_url', 'http://localhost:5000')

    def ready_smtp(self) -> bool:
        return bool(self.smtp_login and self.smtp_password)

    def ready_api(self) -> bool:
        return bool(self.api_key and self.list_ids)

    def send_approval_email(self, draft: dict) -> bool:
        """Email con anteprima post e link APPROVA/RIFIUTA all'admin."""
        draft_id      = draft['draft_id']
        text_preview  = draft.get('text_it', draft.get('text_es', ''))[:400]
        channels_str  = ', '.join(draft.get('channels', []))
        approve_url   = f"{self.base_url}/api/social/approve?draft_id={draft_id}&action=approve"
        reject_url    = f"{self.base_url}/api/social/approve?draft_id={draft_id}&action=reject"
        edit_url      = f"{self.base_url}/api/social/approve?draft_id={draft_id}&action=edit"

        html = f"""
<div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;
            background:#0F172A;border-radius:12px;overflow:hidden">
  <div style="background:#2C5282;padding:22px 30px">
    <h2 style="margin:0;color:#F6AD55;font-size:1.1rem;letter-spacing:.3px">
      Robot Trader 2026 — Post Social in attesa di approvazione
    </h2>
    <p style="margin:6px 0 0;color:#90cdf4;font-size:.85rem">
      {draft['date']} &nbsp;·&nbsp; Tema: <strong>{draft['theme']}</strong>
      &nbsp;·&nbsp; Canali: {channels_str}
    </p>
  </div>
  <div style="padding:28px 30px;background:#1e293b">
    <p style="margin-top:0;color:#94a3b8;font-size:.88rem">Testo generato (IT):</p>
    <div style="background:#0f172a;border-left:4px solid #F6AD55;padding:16px 20px;
                border-radius:6px;font-size:.95rem;line-height:1.7;
                color:#e2e8f0;white-space:pre-wrap">{text_preview}</div>

    <table style="width:100%;margin:28px 0;border-collapse:separate;border-spacing:12px">
      <tr>
        <td style="text-align:center">
          <a href="{approve_url}"
             style="display:block;background:#276749;color:#fff;padding:13px 0;
                    border-radius:8px;text-decoration:none;font-weight:700;font-size:.95rem">
            ✅ APPROVA — Pubblica ora
          </a>
        </td>
        <td style="text-align:center">
          <a href="{edit_url}"
             style="display:block;background:#744210;color:#fff;padding:13px 0;
                    border-radius:8px;text-decoration:none;font-weight:700;font-size:.95rem">
            ✏️ MODIFICA
          </a>
        </td>
        <td style="text-align:center">
          <a href="{reject_url}"
             style="display:block;background:#742a2a;color:#fff;padding:13px 0;
                    border-radius:8px;text-decoration:none;font-weight:700;font-size:.95rem">
            ❌ RIFIUTA
          </a>
        </td>
      </tr>
    </table>
    <p style="font-size:.78rem;color:#475569;text-align:center;margin-bottom:0">
      Link valido 24 ore &nbsp;·&nbsp; draft_id: {draft_id}
    </p>
  </div>
</div>"""
        ok = self._send_smtp(
            to_email=self.admin_email,
            to_nome='Admin FVC',
            oggetto=f"[FVC Social] Approva post · {draft['date']} · {draft['theme']}",
            corpo_html=html,
        )
        _log(f"Email approvazione {'OK' if ok else 'FALLITA'} → {self.admin_email} (draft {draft_id})")
        return ok

    def send_newsletter_campaign(self, subject: str, html_content: str,
                                  scheduled_at: Optional[str] = None) -> dict:
        """Crea e invia campagna Brevo alla lista abbonati Robot Trader."""
        if not self.ready_api():
            return {"ok": False, "detail": "Brevo API key o list_ids mancanti in config.json"}
        payload: dict = {
            "name":       f"RT_{datetime.now().strftime('%Y%m%d_%H%M')}",
            "subject":    subject,
            "sender":     {"name": self.sender_name, "email": self.sender_email},
            "recipients": {"listIds": self.list_ids},
            "htmlContent": html_content,
        }
        if scheduled_at:
            payload["scheduledAt"] = scheduled_at
        r = requests.post(f"{self.BREVO_API}/emailCampaigns",
                          json=payload, headers=self._api_headers(), timeout=20)
        if r.status_code not in (200, 201):
            _log(f"Brevo campagna FALLITA: {r.status_code} {r.text[:200]}")
            return {"ok": False, "status": r.status_code, "detail": r.text}
        campaign_id = r.json().get('id')
        if not scheduled_at:
            r2 = requests.post(f"{self.BREVO_API}/emailCampaigns/{campaign_id}/sendNow",
                               headers=self._api_headers(), timeout=20)
            ok = r2.status_code in (200, 201, 204)
            _log(f"Brevo campagna {campaign_id} inviata: {'OK' if ok else 'FALLITA'}")
            return {"ok": ok, "campaign_id": campaign_id}
        _log(f"Brevo campagna {campaign_id} schedulata per {scheduled_at}")
        return {"ok": True, "campaign_id": campaign_id, "scheduled_at": scheduled_at}

    def get_campaign_stats(self, campaign_id: int) -> dict:
        r = requests.get(f"{self.BREVO_API}/emailCampaigns/{campaign_id}",
                         params={"statistics": "globalStats"},
                         headers=self._api_headers(), timeout=15)
        if r.status_code != 200:
            return {"ok": False}
        data  = r.json()
        stats = data.get("statistics", {}).get("globalStats", {})
        delivered = stats.get("delivered", 1) or 1
        return {
            "ok":             True,
            "nome":           data.get("name"),
            "inviati":        stats.get("sent", 0),
            "consegnati":     stats.get("delivered", 0),
            "aperture":       stats.get("uniqueViews", 0),
            "click":          stats.get("uniqueClicks", 0),
            "tasso_apertura": round(stats.get("uniqueViews", 0) / delivered * 100, 1),
            "tasso_click":    round(stats.get("uniqueClicks", 0) / delivered * 100, 1),
        }

    def _api_headers(self) -> dict:
        return {"api-key": self.api_key, "Content-Type": "application/json"}

    def _send_smtp(self, to_email: str, to_nome: str, oggetto: str, corpo_html: str) -> bool:
        if not self.ready_smtp():
            print("[Brevo SMTP] Credenziali mancanti — configura social.brevo in config.json")
            return False
        msg = MIMEMultipart("alternative")
        msg["Subject"] = oggetto
        msg["From"]    = f"{self.sender_name} <{self.sender_email}>"
        msg["To"]      = f"{to_nome} <{to_email}>"
        msg.attach(MIMEText(corpo_html, "html", "utf-8"))
        try:
            with smtplib.SMTP(self.SMTP_HOST, self.SMTP_PORT, timeout=15) as s:
                s.ehlo()
                s.starttls()
                s.login(self.smtp_login, self.smtp_password)
                s.sendmail(self.sender_email, [to_email], msg.as_string())
            return True
        except Exception as e:
            print(f"[Brevo SMTP] Errore: {e}")
            return False


# ── LINKEDIN ──────────────────────────────────────────────────────────────────

class LinkedInService:
    AUTH_URL  = "https://www.linkedin.com/oauth/v2/authorization"
    TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
    API_BASE  = "https://api.linkedin.com"
    SCOPES    = "w_organization_social r_organization_social"

    def __init__(self):
        cfg = _cfg().get('linkedin', {})
        self.client_id     = cfg.get('client_id', '')     # <<< PLACEHOLDER: LinkedIn App Client ID
        self.client_secret = cfg.get('client_secret', '') # <<< PLACEHOLDER: LinkedIn App Client Secret
        self.redirect_uri  = cfg.get('redirect_uri',
                                     'http://localhost:5000/api/linkedin/callback')
        self.org_id        = cfg.get('org_id', '')        # <<< PLACEHOLDER: ID numerico Company Page

    def ready(self) -> bool:
        return bool(self.client_id and self.client_secret
                    and self.org_id and self._get_token())

    def get_auth_url(self, state: str = "fuerte-li") -> str:
        return (
            f"{self.AUTH_URL}?response_type=code"
            f"&client_id={self.client_id}"
            f"&redirect_uri={self.redirect_uri}"
            f"&state={state}"
            f"&scope={self.SCOPES.replace(' ', '%20')}"
        )

    def exchange_code(self, code: str) -> dict:
        """Scambia il codice OAuth con access token e lo salva in social_tokens.json."""
        r = requests.post(self.TOKEN_URL, data={
            "grant_type":    "authorization_code",
            "code":          code,
            "redirect_uri":  self.redirect_uri,
            "client_id":     self.client_id,
            "client_secret": self.client_secret,
        }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=20)
        if r.status_code != 200:
            return {"ok": False, "status": r.status_code, "detail": r.text}
        data = r.json()
        tokens = _tokens()
        tokens['linkedin'] = {
            "access_token": data.get("access_token"),
            "expires_in":   data.get("expires_in", 5184000),
            "saved_at":     datetime.now().isoformat(),
        }
        _save_tokens(tokens)
        _log(f"LinkedIn token salvato (scade in {data.get('expires_in', '?')}s)")
        return {"ok": True}

    def publish_post(self, text: str, url: Optional[str] = None,
                     url_title: Optional[str] = None,
                     url_desc: Optional[str] = None) -> dict:
        """Pubblica sulla Company Page di Fuerte Venture Capital."""
        if not self.ready():
            _log("LinkedIn: non configurato (token o org_id mancante)")
            return {"ok": False, "detail": "LinkedIn non configurato"}
        org_urn = f"urn:li:organization:{self.org_id}"
        body: dict = {
            "author":      org_urn,
            "commentary":  text,
            "visibility":  "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities":   [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState":           "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        if url:
            body["content"] = {
                "article": {
                    "source":      url,
                    "title":       url_title or "Robot Trader 2026",
                    "description": url_desc or "",
                }
            }
        r = requests.post(f"{self.API_BASE}/rest/posts",
                          json=body, headers=self._headers(), timeout=30)
        if r.status_code in (200, 201):
            post_id = r.headers.get("x-restli-id", "")
            _log(f"LinkedIn post pubblicato: {post_id}")
            return {"ok": True, "post_id": post_id}
        _log(f"LinkedIn post FALLITO: {r.status_code} {r.text[:300]}")
        return {"ok": False, "status": r.status_code, "detail": r.text}

    def _get_token(self) -> Optional[str]:
        return _tokens().get('linkedin', {}).get('access_token', '') or None

    def _headers(self) -> dict:
        return {
            "Authorization":              f"Bearer {self._get_token()}",
            "Content-Type":               "application/json",
            "X-Restli-Protocol-Version":  "2.0.0",
            "LinkedIn-Version":           "202401",
        }


# ── META (Facebook + Instagram) ───────────────────────────────────────────────

class MetaService:
    GRAPH    = "https://graph.facebook.com/v19.0"
    AUTH_URL = "https://www.facebook.com/v19.0/dialog/oauth"
    SCOPES   = (
        "pages_show_list,pages_manage_posts,"
        "pages_read_engagement,instagram_basic,instagram_content_publish"
    )

    def __init__(self):
        cfg = _cfg().get('meta', {})
        self.app_id       = cfg.get('app_id', '')         # <<< PLACEHOLDER: Meta App ID
        self.app_secret   = cfg.get('app_secret', '')     # <<< PLACEHOLDER: Meta App Secret
        self.redirect_uri = cfg.get('redirect_uri',
                                    'http://localhost:5000/api/meta/callback')
        self.page_id      = cfg.get('page_id', '')        # <<< PLACEHOLDER: ID Pagina Facebook FVC
        self.ig_user_id   = cfg.get('ig_user_id', '')     # <<< PLACEHOLDER: ID Account Instagram Business

    def ready_facebook(self) -> bool:
        return bool(self.app_id and self.page_id and self._get_page_token())

    def ready_instagram(self) -> bool:
        t = _tokens().get('meta', {})
        ig_id = self.ig_user_id or t.get('ig_user_id', '')
        return bool(self.ready_facebook() and ig_id)

    def get_auth_url(self, state: str = "fuerte-meta") -> str:
        return (
            f"{self.AUTH_URL}?client_id={self.app_id}"
            f"&redirect_uri={self.redirect_uri}"
            f"&scope={self.SCOPES}&state={state}&response_type=code"
        )

    def exchange_code(self, code: str) -> dict:
        """OAuth: short → long-lived token (60 giorni) → page token permanente."""
        # 1. Short-lived user token
        r = requests.get(f"{self.GRAPH}/oauth/access_token", params={
            "client_id": self.app_id, "client_secret": self.app_secret,
            "redirect_uri": self.redirect_uri, "code": code,
        }, timeout=20)
        if r.status_code != 200:
            return {"ok": False, "step": "short_token", "detail": r.text}
        short_token = r.json().get("access_token")

        # 2. Long-lived user token (60 giorni)
        r2 = requests.get(f"{self.GRAPH}/oauth/access_token", params={
            "grant_type": "fb_exchange_token", "client_id": self.app_id,
            "client_secret": self.app_secret, "fb_exchange_token": short_token,
        }, timeout=20)
        if r2.status_code != 200:
            return {"ok": False, "step": "long_token", "detail": r2.text}
        long_token = r2.json().get("access_token")

        # 3. Page token (non scade se la pagina è collegata correttamente)
        r3 = requests.get(f"{self.GRAPH}/me/accounts", params={
            "access_token": long_token,
            "fields": "id,name,access_token,instagram_business_account",
        }, timeout=20)
        if r3.status_code != 200:
            return {"ok": False, "step": "page_token", "detail": r3.text}

        pages     = r3.json().get("data", [])
        page_tok  = None
        ig_id     = None
        found_pid = self.page_id

        for page in pages:
            if not self.page_id or str(page.get("id")) == str(self.page_id):
                page_tok  = page.get("access_token")
                ig_data   = page.get("instagram_business_account", {})
                ig_id     = ig_data.get("id")
                found_pid = page.get("id")
                break

        tokens = _tokens()
        tokens['meta'] = {
            "user_token": long_token,
            "page_token": page_tok or "",
            "page_id":    found_pid,
            "ig_user_id": ig_id or self.ig_user_id,
            "saved_at":   datetime.now().isoformat(),
        }
        _save_tokens(tokens)
        _log(f"Meta tokens salvati — page_id={found_pid} ig_user_id={ig_id}")
        return {"ok": True, "page_id": found_pid, "ig_user_id": ig_id, "pages_found": len(pages)}

    def publish_facebook(self, text: str, url: Optional[str] = None,
                         image_url: Optional[str] = None) -> dict:
        """Post testo (+ link o immagine opzionale) sulla Pagina Facebook FVC."""
        if not self.ready_facebook():
            _log("Facebook: non configurato (token o page_id mancante)")
            return {"ok": False, "detail": "Facebook non configurato"}
        pt  = self._get_page_token()
        pid = self._get_page_id()
        if image_url:
            payload = {"caption": text, "url": image_url, "access_token": pt}
            r = requests.post(f"{self.GRAPH}/{pid}/photos", data=payload, timeout=30)
        else:
            payload = {"message": text, "access_token": pt}
            if url:
                payload["link"] = url
            r = requests.post(f"{self.GRAPH}/{pid}/feed", data=payload, timeout=30)
        if r.status_code == 200:
            post_id = r.json().get("id")
            _log(f"Facebook post pubblicato: {post_id}")
            return {"ok": True, "post_id": post_id}
        _log(f"Facebook post FALLITO: {r.status_code} {r.text[:300]}")
        return {"ok": False, "status": r.status_code, "detail": r.text}

    def publish_instagram(self, text: str, image_url: str) -> dict:
        """
        Post su Instagram Business. image_url deve essere pubblico (accessibile da internet).
        Step 1: crea container media. Step 2: pubblica il container.
        """
        t     = _tokens().get('meta', {})
        pt    = self._get_page_token()
        ig_id = self.ig_user_id or t.get('ig_user_id', '')
        if not pt or not ig_id:
            _log("Instagram: non configurato (token o ig_user_id mancante)")
            return {"ok": False, "detail": "Instagram non configurato"}

        # Step 1
        r1 = requests.post(f"{self.GRAPH}/{ig_id}/media", data={
            "image_url": image_url, "caption": text, "access_token": pt,
        }, timeout=30)
        if r1.status_code != 200:
            _log(f"Instagram container FALLITO: {r1.status_code} {r1.text[:200]}")
            return {"ok": False, "step": "container", "detail": r1.text}
        container_id = r1.json().get("id")

        # Step 2
        r2 = requests.post(f"{self.GRAPH}/{ig_id}/media_publish", data={
            "creation_id": container_id, "access_token": pt,
        }, timeout=30)
        if r2.status_code == 200:
            post_id = r2.json().get("id")
            _log(f"Instagram post pubblicato: {post_id}")
            return {"ok": True, "post_id": post_id}
        _log(f"Instagram publish FALLITO: {r2.status_code} {r2.text[:200]}")
        return {"ok": False, "step": "publish", "detail": r2.text}

    def _get_page_token(self) -> Optional[str]:
        return _tokens().get('meta', {}).get('page_token', '') or None

    def _get_page_id(self) -> str:
        return self.page_id or _tokens().get('meta', {}).get('page_id', '')


# ── Helper pubblico: pubblica su tutti i canali configurati ───────────────────

def publish_to_all_channels(draft: dict) -> dict:
    """
    Pubblica un draft approvato su tutti i canali attivi.
    Ritorna dict con risultato per canale.
    """
    results  = {}
    channels = draft.get('channels', ['linkedin', 'facebook', 'instagram'])
    text_it  = draft.get('text_it', '')
    text_es  = draft.get('text_es', '')
    image_url = draft.get('image_url')
    article_url = draft.get('article_url')

    # Brevo newsletter (testo IT come corpo email)
    if 'brevo' in channels:
        brevo = BrevoService()
        html_body = f"""
<div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:32px 24px">
  <h2 style="color:#2C5282">Fuerte Venture Capital — Aggiornamento</h2>
  <div style="white-space:pre-wrap;line-height:1.7;color:#2d3748">{text_it}</div>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:28px 0">
  <p style="font-size:.8rem;color:#a0aec0">
    Robot Trader 2026 · <a href="https://www.fuerteventurecapital.com">www.fuerteventurecapital.com</a>
  </p>
</div>"""
        results['brevo'] = brevo.send_newsletter_campaign(
            subject=f"[Robot Trader] {draft['theme']} — {draft['date']}",
            html_content=html_body,
        )

    # LinkedIn (Company Page — testo IT)
    if 'linkedin' in channels:
        li = LinkedInService()
        results['linkedin'] = li.publish_post(
            text=text_it,
            url=article_url,
        )

    # Facebook (testo IT)
    if 'facebook' in channels:
        meta = MetaService()
        results['facebook'] = meta.publish_facebook(
            text=text_it,
            url=article_url,
            image_url=image_url,
        )

    # Instagram (testo IT — richiede image_url pubblico)
    if 'instagram' in channels:
        meta = MetaService()
        if image_url:
            results['instagram'] = meta.publish_instagram(text=text_it, image_url=image_url)
        else:
            results['instagram'] = {"ok": False, "detail": "Instagram richiede image_url — skippato"}
            _log("Instagram: skippato (nessuna image_url nel draft)")

    ok_count = sum(1 for v in results.values() if v.get('ok'))
    _log(f"Pubblicazione draft {draft['draft_id']}: {ok_count}/{len(results)} canali OK")
    return results
