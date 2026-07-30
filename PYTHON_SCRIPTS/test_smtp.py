import smtplib, os, json
from email.mime.text import MIMEText

BASE = os.path.dirname(os.path.abspath(__file__))
try:
    with open(os.path.join(BASE, "config.json")) as f:
        cfg = json.load(f).get("email", {})
except Exception:
    cfg = {}

HOST  = os.getenv("BREVO_SMTP_HOST")     or cfg.get("smtp_server",  "smtp.gmail.com")
LOGIN = os.getenv("BREVO_SMTP_LOGIN")    or cfg.get("smtp_login",   "") or cfg.get("sender", "")
PWD   = os.getenv("BREVO_SMTP_PASSWORD") or cfg.get("app_password", "")
TO    = LOGIN

print(f"Host:   {HOST}")
print(f"Login:  {LOGIN}")
print(f"Pwd:    {'***' if PWD else '(VUOTA!)'}")
print(f"Dest:   {TO}")
print()

if not LOGIN or not PWD:
    print("❌ Credenziali mancanti in config.json e variabili d'ambiente.")
    exit(1)

msg = MIMEText("Test SMTP da Fuerte Screener. Se ricevi questa email tutto funziona.", "plain", "utf-8")
msg["Subject"] = "Test SMTP Fuerte Screener"
msg["From"]    = LOGIN
msg["To"]      = TO

try:
    print("Connessione SMTP...")
    with smtplib.SMTP(HOST, 587, timeout=15) as srv:
        srv.ehlo(); srv.starttls(); srv.ehlo()
        srv.login(LOGIN, PWD)
        srv.sendmail(LOGIN, [TO], msg.as_string())
    print(f"✅ Email inviata a {TO} — controlla la casella (incluso spam)")
except Exception as e:
    print(f"❌ Errore: {e}")
