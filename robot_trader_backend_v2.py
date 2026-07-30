# -*- coding: utf-8 -*-
"""
Robot Trader 2026 - Backend API v2
Con endpoint /api/signup (landing page + Stripe pagamenti)
"""

from flask import Flask, request, jsonify
import stripe
import os
from datetime import datetime
from database import db

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# Stripe API Key
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', 'sk_test_1234567890abcdef')

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

# ============= SIGNUP / ISCRIZIONI =============

@app.route('/api/signup', methods=['POST'])
def api_signup():
    """Endpoint per iscrizione da landing page"""
    try:
        data = request.json
        
        # Validazioni
        if not data.get('nome') or not data.get('email'):
            return jsonify({'error': 'Nome ed email richiesti'}), 400
        
        # 1. Crea cliente in database
        client_id = db.add_client(
            nome=data['nome'],
            email=data['email'],
            telefono=data.get('telefono'),
            azienda=data.get('azienda')
        )
        
        # 2. Crea iscrizione al servizio
        servizio_id = data.get('servizio', 1)
        db.add_subscription(client_id, servizio_id)
        
        # 3. Crea payment intent Stripe
        importo_centesimi = data.get('importo', 4900)
        
        payment_intent = stripe.PaymentIntent.create(
            amount=importo_centesimi,
            currency='eur',
            metadata={
                'client_id': client_id,
                'service_id': servizio_id,
                'email': data['email']
            }
        )
        
        # 4. Crea pagamento nel database (pendente)
        db.add_payment(
            client_id=client_id,
            importo=importo_centesimi / 100,
            stripe_payment_id=payment_intent.id
        )
        
        return jsonify({
            'client_id': client_id,
            'client_secret': payment_intent.client_secret,
            'payment_intent_id': payment_intent.id
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """Webhook Stripe per conferma pagamenti"""
    try:
        event = stripe.Event.construct_from(
            request.json, os.getenv('STRIPE_WEBHOOK_SECRET', 'whsec_test_1234567890')
        )
        
        if event['type'] == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            stripe_payment_id = payment_intent['id']
            
            # Conferma pagamento nel database
            db.confirm_payment(stripe_payment_id)
            
            return jsonify({'status': 'ok'})
        
        return jsonify({'status': 'ok'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= CLIENTS =============

@app.route('/api/clients', methods=['GET'])
def api_get_clients():
    """Leggi tutti i clienti"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM clients')
        clients = [dict(row) for row in cursor.fetchall()]
    return jsonify(clients)

@app.route('/api/clients/<int:client_id>', methods=['GET', 'PUT', 'DELETE'])
def api_client_detail(client_id):
    """CRUD singolo cliente"""
    if request.method == 'GET':
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM clients WHERE id = ?', (client_id,))
            client = dict(cursor.fetchone())
        return jsonify(client)
    
    elif request.method == 'PUT':
        data = request.json
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''UPDATE clients 
                SET nome=?, email=?, telefono=?, azienda=?, note=?
                WHERE id=?''',
                (data.get('nome'), data.get('email'), data.get('telefono'),
                 data.get('azienda'), data.get('note'), client_id))
        return jsonify({'status': 'ok'})
    
    elif request.method == 'DELETE':
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM clients WHERE id=?', (client_id,))
        return jsonify({'status': 'ok'})

# ============= SERVICES =============

@app.route('/api/services', methods=['GET'])
def api_get_services():
    """Leggi servizi"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM services')
        services = [dict(row) for row in cursor.fetchall()]
    return jsonify(services)

# ============= SUBSCRIPTIONS =============

@app.route('/api/clients/<int:client_id>/subscriptions', methods=['GET'])
def api_client_subscriptions(client_id):
    """Leggi servizi sottoscritti di un cliente"""
    servizi = db.get_subscriptions_by_client(client_id)
    return jsonify(servizi)

# ============= STATS =============

@app.route('/api/stats')
def api_stats():
    """Statistiche dashboard"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) as num FROM clients WHERE stato = "active"')
        num_clienti = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) as num FROM services')
        num_servizi = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(importo) as total FROM payments WHERE stato = "completed"')
        total_revenue = cursor.fetchone()[0] or 0
        
        mrr = total_revenue / 3  # Approssimativo
    
    return jsonify({
        'clienti_attivi': num_clienti,
        'servizi': num_servizi,
        'mrr': round(mrr, 2),
        'arr': round(mrr * 12, 2),
        'revenue_totale': round(total_revenue, 2)
    })

# ============= LOGS =============

@app.route('/api/email-logs')
def api_email_logs():
    """Leggi log invii email"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT * FROM email_logs ORDER BY data_invio DESC LIMIT 100''')
        logs = [dict(row) for row in cursor.fetchall()]
    return jsonify(logs)

@app.route('/api/execution-logs')
def api_execution_logs():
    """Leggi log esecuzioni screener"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT * FROM execution_logs ORDER BY data_esecuzione DESC LIMIT 100''')
        logs = [dict(row) for row in cursor.fetchall()]
    return jsonify(logs)

if __name__ == '__main__':
    print("\n" + "="*80)
    print("ROBOT TRADER 2026 - BACKEND API v2")
    print("="*80)
    print("\n✓ API disponibile su: http://localhost:5001")
    print("\nEndpoint:")
    print("  POST /api/signup                      - Iscrizione da landing page")
    print("  POST /api/webhook/stripe             - Webhook Stripe")
    print("  GET  /api/clients                    - Lista clienti")
    print("  GET  /api/clients/<id>               - Dettagli cliente")
    print("  PUT  /api/clients/<id>               - Modifica cliente")
    print("  DEL  /api/clients/<id>               - Elimina cliente")
    print("  GET  /api/services                   - Lista servizi")
    print("  GET  /api/clients/<id>/subscriptions - Servizi cliente")
    print("  GET  /api/stats                      - Statistiche")
    print("  GET  /api/email-logs                 - Log email")
    print("  GET  /api/execution-logs             - Log esecuzioni")
    print("\nPremere Ctrl+C per chiudere\n")
    print("="*80 + "\n")
    
    app.run(host='localhost', port=5001, debug=False)
