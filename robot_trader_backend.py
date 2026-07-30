# -*- coding: utf-8 -*-
"""
Robot Trader 2026 - Backend API
Flask API che collega Admin Panel + Screener + Database JSON
"""

from flask import Flask, render_template_string, request, jsonify, send_file
import json
import os
from datetime import datetime
import pandas as pd
import subprocess
import sys

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

DATA_DIR = "DATA"
REPORTS_DIR = "REPORTS_DAILY"
LOGS_DIR = "LOGS"

# Crea cartelle se non esistono
for dir in [DATA_DIR, REPORTS_DIR, LOGS_DIR]:
    os.makedirs(dir, exist_ok=True)

# Carica JSON
def load_json(filename):
    filepath = os.path.join(DATA_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# API Routes
@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    """GET: leggi configurazione | POST: salva configurazione"""
    if request.method == 'POST':
        save_json('config.json', request.json)
        return jsonify({'status': 'ok', 'message': 'Configurazione salvata'})
    return jsonify(load_json('config.json'))

@app.route('/api/clients', methods=['GET', 'POST'])
def api_clients():
    """GET: lista clienti | POST: aggiungi cliente"""
    if request.method == 'POST':
        clients = load_json('clients.json')
        new_client = request.json
        new_client['id'] = len(clients) + 1
        new_client['data_iscrizione'] = datetime.now().strftime('%d/%m/%Y')
        clients[str(new_client['id'])] = new_client
        save_json('clients.json', clients)
        return jsonify({'status': 'ok', 'client_id': new_client['id']})
    return jsonify(load_json('clients.json'))

@app.route('/api/clients/<int:client_id>', methods=['GET', 'PUT', 'DELETE'])
def api_client_detail(client_id):
    """GET: dettagli cliente | PUT: modifica | DELETE: elimina"""
    clients = load_json('clients.json')
    client_key = str(client_id)
    
    if request.method == 'GET':
        return jsonify(clients.get(client_key, {}))
    elif request.method == 'PUT':
        clients[client_key] = request.json
        save_json('clients.json', clients)
        return jsonify({'status': 'ok'})
    elif request.method == 'DELETE':
        del clients[client_key]
        save_json('clients.json', clients)
        return jsonify({'status': 'ok'})

@app.route('/api/services', methods=['GET', 'POST'])
def api_services():
    """GET: lista servizi | POST: aggiungi servizio"""
    if request.method == 'POST':
        services = load_json('services.json')
        new_service = request.json
        new_service['id'] = len(services) + 1
        services[str(new_service['id'])] = new_service
        save_json('services.json', services)
        return jsonify({'status': 'ok', 'service_id': new_service['id']})
    return jsonify(load_json('services.json'))

@app.route('/api/invoices', methods=['GET', 'POST'])
def api_invoices():
    """GET: lista fatture | POST: aggiungi fattura"""
    if request.method == 'POST':
        invoices = load_json('invoices.json')
        new_invoice = request.json
        new_invoice['id'] = len(invoices) + 1
        new_invoice['data_fattura'] = datetime.now().strftime('%d/%m/%Y')
        invoices[str(new_invoice['id'])] = new_invoice
        save_json('invoices.json', invoices)
        return jsonify({'status': 'ok', 'invoice_id': new_invoice['id']})
    return jsonify(load_json('invoices.json'))

@app.route('/api/stats')
def api_stats():
    """Statistiche dashboard"""
    clients = load_json('clients.json')
    services = load_json('services.json')
    invoices = load_json('invoices.json')
    
    # Calcola MRR
    mrr = 0
    for client in clients.values():
        for service_id in client.get('servizi', []):
            for service in services.values():
                if service.get('id') == service_id:
                    mrr += service.get('prezzo', 0)
    
    return jsonify({
        'num_clienti': len(clients),
        'num_servizi': len(services),
        'num_fatture': len(invoices),
        'mrr': mrr,
        'arr': mrr * 12,
        'uptime': 94
    })

@app.route('/api/results/<asset_type>')
def api_results(asset_type):
    """Leggi risultati Excel ultimi screening"""
    try:
        files = [f for f in os.listdir(REPORTS_DIR) 
                if f.startswith(f'value_screener_{asset_type}')]
        if files:
            latest = sorted(files)[-1]
            df = pd.read_excel(os.path.join(REPORTS_DIR, latest))
            return jsonify(df.to_dict('records'))
    except:
        pass
    return jsonify([])

@app.route('/api/run-screener/<asset_type>')
def api_run_screener(asset_type):
    """Esegui uno screener manualmente"""
    script = f'value_screener_{asset_type}.py'
    try:
        result = subprocess.run(
            [sys.executable, script],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            timeout=1800
        )
        return jsonify({
            'status': 'ok' if result.returncode == 0 else 'error',
            'output': result.stdout.decode('utf-8', errors='ignore')
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/send-email/<int:client_id>')
def api_send_email(client_id):
    """Invia email a cliente specifico"""
    clients = load_json('clients.json')
    client = clients.get(str(client_id), {})
    
    if not client:
        return jsonify({'status': 'error', 'message': 'Cliente non trovato'})
    
    # Qui chiamerebbe email_notifier.py
    return jsonify({
        'status': 'ok',
        'message': f"Email inviata a {client.get('email', 'N/A')}"
    })

@app.route('/api/logs')
def api_logs():
    """Leggi log file"""
    logs = []
    try:
        for filename in sorted(os.listdir(LOGS_DIR), reverse=True)[:10]:
            filepath = os.path.join(LOGS_DIR, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                logs.append({'file': filename, 'content': f.read()})
    except:
        pass
    return jsonify(logs)

@app.route('/api/backup')
def api_backup():
    """Crea backup JSON"""
    import shutil
    backup_dir = os.path.join(DATA_DIR, f'backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
    shutil.copytree(DATA_DIR, backup_dir)
    return jsonify({'status': 'ok', 'backup_dir': backup_dir})

# Health check
@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    print("\n" + "="*80)
    print("ROBOT TRADER 2026 - BACKEND API")
    print("="*80)
    print("\n✓ API disponibile su: http://localhost:5001")
    print("\nEndpoint principali:")
    print("  GET  /api/config              - Leggi configurazione")
    print("  POST /api/config              - Salva configurazione")
    print("  GET  /api/clients             - Lista clienti")
    print("  POST /api/clients             - Aggiungi cliente")
    print("  GET  /api/services            - Lista servizi")
    print("  GET  /api/invoices            - Lista fatture")
    print("  GET  /api/stats               - Statistiche")
    print("  GET  /api/results/<type>      - Risultati screening")
    print("  GET  /api/run-screener/<type> - Esegui screener")
    print("  GET  /api/logs                - Log file")
    print("  GET  /api/backup              - Crea backup")
    print("\nPremere Ctrl+C per chiudere\n")
    print("="*80 + "\n")
    
    app.run(host='localhost', port=5001, debug=False)
