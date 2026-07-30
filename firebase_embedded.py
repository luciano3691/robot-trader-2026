"""
Robot Trader 2026 — Firebase API (EMBEDDED CREDENTIALS)
=======================================================

NIENTE FILE BLOCCATI DA WINDOWS!
Credenziali direttamente nel .env come JSON string.

SETUP:
1. Scarica JSON da Firebase (robot-trader-2026-firebase-adminsdk-fbsvc-xxxxx.json)
2. Apri con Notepad
3. Copia TUTTO il contenuto JSON
4. Incolla nel .env come FIREBASE_CREDENTIALS_JSON="..."
5. python firebase_embedded.py
6. FUNZIONA!
"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, List
import tempfile

from flask import Flask, request, jsonify
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
from loguru import logger

# ============================================================================
# CONFIGURAZIONE
# ============================================================================

load_dotenv()

class Settings:
    """Configurazione centralizzata"""
    FIREBASE_CREDENTIALS_JSON = os.getenv("FIREBASE_CREDENTIALS_JSON")
    FLASK_ENV = os.getenv("FLASK_ENV", "production")
    FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    @staticmethod
    def validate():
        if not Settings.FIREBASE_CREDENTIALS_JSON:
            raise ValueError("FIREBASE_CREDENTIALS_JSON mancante nel .env!")

settings = Settings()

# ============================================================================
# LOGGING
# ============================================================================

def setup_logger(level: str = "INFO"):
    """Setup loguru"""
    logger.remove()
    logger.add(
        "logs/api_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
        level=level,
        rotation="1 day",
        retention="30 days"
    )
    logger.add(
        lambda msg: print(msg, end=""),
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level=level,
        colorize=True
    )
    return logger

logger = setup_logger(settings.LOG_LEVEL)

# ============================================================================
# FIREBASE INIT - EMBEDDED CREDENTIALS
# ============================================================================

def init_firebase():
    """Inizializza Firebase con credenziali embedded (NIENTE FILE!)"""
    try:
        settings.validate()
        
        # Parse JSON da env
        creds_dict = json.loads(settings.FIREBASE_CREDENTIALS_JSON)
        
        # Crea temp file in memoria per Firebase SDK
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(creds_dict, f)
            temp_path = f.name
        
        try:
            cred = credentials.Certificate(temp_path)
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            logger.info("✅ Firebase inizializzato (embedded credentials)")
            return db
        finally:
            # Pulisci temp file
            os.unlink(temp_path)
            
    except json.JSONDecodeError as e:
        logger.error(f"❌ FIREBASE_CREDENTIALS_JSON non è JSON valido: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Errore Firebase init: {e}")
        raise

db = init_firebase()

# ============================================================================
# FLASK APP
# ============================================================================

app = Flask(__name__)

# ============================================================================
# UTILITÀ
# ============================================================================

def validate_email(email: str) -> bool:
    """Validazione email"""
    return "@" in email and "." in email.split("@")[-1]

def validate_signup_data(data: Dict) -> tuple[bool, Optional[str]]:
    """Valida dati signup"""
    required = ["email", "nome", "piano", "screener"]
    
    for field in required:
        if field not in data:
            return False, f"Campo mancante: {field}"
    
    if not validate_email(data["email"]):
        return False, "Email non valida"
    
    valid_plans = ["BASIC", "PRO", "ENTERPRISE"]
    if data["piano"] not in valid_plans:
        return False, f"Piano non valido"
    
    if not isinstance(data["screener"], list) or len(data["screener"]) == 0:
        return False, "Screener deve essere una lista"
    
    return True, None

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.route("/health", methods=["GET"])
def health_check():
    """Health check"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "firebase": "connected"
    }), 200

@app.route("/api/signup", methods=["POST"])
def signup():
    """Registra cliente in Firestore"""
    try:
        data = request.get_json()
        logger.info(f"📥 Signup: {data.get('email')}")
        
        # Valida
        is_valid, error_msg = validate_signup_data(data)
        if not is_valid:
            logger.warning(f"⚠️ Validazione fallita: {error_msg}")
            return jsonify({"success": False, "error": error_msg}), 400
        
        # Prepara documento
        cliente_data = {
            "email": data["email"].lower().strip(),
            "nome": data["nome"].strip(),
            "piano": data["piano"],
            "screener": data["screener"],
            "data_registrazione": firestore.SERVER_TIMESTAMP,
            "status": "ATTIVO",
            "data_ultimo_screening": None,
            "ip_address": request.remote_addr,
            "user_agent": request.headers.get("User-Agent", "Unknown")
        }
        
        # Salva in Firestore
        doc_ref = db.collection("clienti").document(cliente_data["email"])
        doc_ref.set(cliente_data)
        logger.info(f"✅ Cliente salvato: {cliente_data['email']}")
        
        # Log email
        email_log = {
            "cliente_email": cliente_data["email"],
            "tipo_email": "BENVENUTO",
            "data_invio": firestore.SERVER_TIMESTAMP,
            "aperta": False,
            "data_apertura": None,
            "link_cliccato": False
        }
        db.collection("email_log").add(email_log)
        logger.info(f"📧 Email log creato")
        
        return jsonify({
            "success": True,
            "message": f"✅ Registrazione completata per {cliente_data['email']}",
            "cliente": {
                "email": cliente_data["email"],
                "nome": cliente_data["nome"],
                "piano": cliente_data["piano"],
                "screener": cliente_data["screener"]
            }
        }), 201
        
    except json.JSONDecodeError:
        logger.error("❌ JSON non valido")
        return jsonify({"success": False, "error": "JSON non valido"}), 400
    except Exception as e:
        logger.error(f"❌ Errore signup: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/clienti", methods=["GET"])
def get_clienti():
    """Leggi clienti da Firestore"""
    try:
        docs = db.collection("clienti").stream()
        clienti = []
        for doc in docs:
            data = doc.to_dict()
            clienti.append(data)
        
        logger.info(f"📊 Lettura {len(clienti)} clienti")
        return jsonify({
            "success": True,
            "count": len(clienti),
            "clienti": clienti
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Errore lettura: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Statistiche clienti"""
    try:
        docs = db.collection("clienti").stream()
        
        basic_count = 0
        pro_count = 0
        enterprise_count = 0
        
        for doc in docs:
            data = doc.to_dict()
            piano = data.get("piano")
            if piano == "BASIC":
                basic_count += 1
            elif piano == "PRO":
                pro_count += 1
            elif piano == "ENTERPRISE":
                enterprise_count += 1
        
        total = basic_count + pro_count + enterprise_count
        
        stats = {
            "total_clienti": total,
            "per_piano": {
                "BASIC": basic_count,
                "PRO": pro_count,
                "ENTERPRISE": enterprise_count
            }
        }
        
        logger.info(f"📊 Stats: {total} clienti")
        return jsonify({"success": True, "stats": stats}), 200
        
    except Exception as e:
        logger.error(f"❌ Errore stats: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    logger.info(f"🚀 Avvio API Robot Trader 2026 (Firebase Embedded)")
    logger.info(f"   Ambiente: {settings.FLASK_ENV}")
    logger.info(f"   Porta: {settings.FLASK_PORT}")
    logger.info("")
    logger.info("📡 Endpoint disponibili:")
    logger.info("   GET  /health")
    logger.info("   POST /api/signup")
    logger.info("   GET  /api/clienti")
    logger.info("   GET  /api/stats")
    logger.info("")
    
    app.run(
        host="0.0.0.0",
        port=settings.FLASK_PORT,
        debug=(settings.FLASK_ENV == "development")
    )
