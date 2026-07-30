#!/usr/bin/env python3
# signup_handler.py
# Riceve i dati dal form e li aggiunge automaticamente al DATABASE_RECIPIENTS.json

import json
import os
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

DATABASE_FILE = 'DATABASE_RECIPIENTS.json'

def load_database():
    """Carica il database dei destinatari"""
    try:
        with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: {DATABASE_FILE} not found!")
        return None

def save_database(db):
    """Salva il database"""
    db['metadata']['last_updated'] = datetime.now().isoformat()
    with open(DATABASE_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

@app.route('/api/signup', methods=['POST'])
def signup():
    """
    Endpoint per registrare un nuovo beta user.
    
    Request body:
    {
        "first_name": "John",
        "email": "john@example.com",
        "product": "AZIONI",
        "timestamp": "2026-04-30T09:15:00"
    }
    """
    
    try:
        data = request.json
        
        # Validazione
        if not data.get('email'):
            return jsonify({'success': False, 'message': 'Email is required'}), 400
        
        if not data.get('product') or data['product'] not in ['AZIONI', 'FONDI', 'ETF']:
            return jsonify({'success': False, 'message': 'Product is required'}), 400
        
        # Carica database
        db = load_database()
        if not db:
            return jsonify({'success': False, 'message': 'Database not found'}), 500
        
        # Controlla se email esiste già
        existing_emails = [r['email'] for r in db['customer_recipients']]
        if data['email'] in existing_emails:
            return jsonify({'success': False, 'message': 'Email already registered'}), 409
        
        # Crea nuovo beta user
        new_id = f"cust_{len(db['customer_recipients']) + 1:03d}"
        
        new_customer = {
            'id': new_id,
            'customer_id': f"USER_{data['email']}",
            'customer_name': data.get('first_name', 'Beta User'),
            'plan': 'BETA',
            'email': data['email'],
            'status': 'active',
            'report_format': 'excel',
            'frequency': 'daily',
            'markets': [data['product']],
            'timezone': 'UTC+2',
            'created_date': datetime.now().strftime('%Y-%m-%d'),
            'notes': f'Beta signup - {data["product"]} product'
        }
        
        # Aggiungi al database
        db['customer_recipients'].append(new_customer)
        db['metadata']['total_customer_recipients'] = len(db['customer_recipients'])
        
        # Salva
        save_database(db)
        
        print(f"[SIGNUP] New user: {data['email']} ({data['product']})")
        
        return jsonify({
            'success': True,
            'message': 'Successfully registered for beta!',
            'customer_id': new_id,
            'email': data['email'],
            'first_report': '08:05 tomorrow (UTC+2)'
        }), 201
    
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/signup/list', methods=['GET'])
def list_signups():
    """
    Endpoint per vedere tutti i beta signups.
    
    Usage: curl http://localhost:5000/api/signup/list
    """
    try:
        db = load_database()
        if not db:
            return jsonify({'error': 'Database not found'}), 500
        
        signups = db['customer_recipients']
        
        return jsonify({
            'total': len(signups),
            'signups': signups
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    print("=" * 60)
    print("ROBOT TRADER — BETA SIGNUP HANDLER")
    print("=" * 60)
    print("\nServer running on: http://localhost:5000")
    print("API Endpoints:")
    print("  POST /api/signup — Register new beta user")
    print("  GET /api/signup/list — List all signups")
    print("  GET /health — Health check")
    print("\nDatabase: DATABASE_RECIPIENTS.json")
    print("=" * 60)
    print("\nNote: For production, use Gunicorn or similar.\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
