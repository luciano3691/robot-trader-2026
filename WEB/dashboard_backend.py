from flask import Flask, jsonify, send_file
from flask_cors import CORS
import os
import pandas as pd
from datetime import datetime

app = Flask(__name__)
CORS(app)

REPORTS_DIR = r"C:\Users\lucia\Desktop\ROBOT TRADER 2026\PYTHON_SCRIPTS\REPORTS_DAILY"

def get_latest_reports():
    """Legge ultimi 3 file Excel"""
    reports = {'azioni': None, 'etf': None, 'fondi': None}
    
    try:
        if os.path.exists(REPORTS_DIR):
            files = [f for f in os.listdir(REPORTS_DIR) if f.endswith('.xlsx')]
            files.sort(reverse=True)
            
            for file in files:
                path = os.path.join(REPORTS_DIR, file)
                if 'value_screener_azioni' in file.lower() and not reports['azioni']:
                    reports['azioni'] = path
                elif 'ETF' in file and not reports['etf']:
                    reports['etf'] = path
                elif 'FONDI' in file and not reports['fondi']:
                    reports['fondi'] = path
    except Exception as e:
        print(f"Errore: {e}")
    
    return reports

@app.route('/api/dashboard')
def get_dashboard():
    """API JSON"""
    reports = get_latest_reports()
    data = {
        'timestamp': datetime.now().isoformat(),
        'azioni': None,
        'etf': None,
        'fondi': None
    }
    
    for key, path in reports.items():
        if path and os.path.exists(path):
            try:
                df = pd.read_excel(path, sheet_name=0)
                data[key] = {
                    'count': len(df),
                    'file': os.path.basename(path),
                    'data': df.head(10).to_dict(orient='records')
                }
            except Exception as e:
                print(f"Errore lettura {key}: {e}")
    
    return jsonify(data)

@app.route('/')
def index():
    """Serve dashboard HTML"""
    html_path = os.path.join(os.path.dirname(__file__), 'dashboard.html')
    if os.path.exists(html_path):
        return send_file(html_path)
    return jsonify({'error': 'dashboard.html non trovato'})

if __name__ == '__main__':
    print("Dashboard su http://localhost:5000")
    app.run(debug=True, port=5000)
