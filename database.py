# -*- coding: utf-8 -*-
"""
Robot Trader 2026 - Database Manager
Gestisce SQLite con queries dirette (no ORM per semplicità)
"""

import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

DB_FILE = "DATA/robot_trader.db"

class DatabaseManager:
    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        os.makedirs(os.path.dirname(db_file), exist_ok=True)
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        """Context manager per connessioni database"""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_db(self):
        """Inizializza database dal schema"""
        if not os.path.exists(self.db_file):
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Crea tabelle
                cursor.execute('''CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    telefono TEXT,
                    azienda TEXT,
                    stato TEXT DEFAULT 'pending_payment',
                    data_iscrizione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_attivazione TIMESTAMP,
                    note TEXT
                )''')
                
                cursor.execute('''CREATE TABLE IF NOT EXISTS services (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL UNIQUE,
                    descrizione TEXT,
                    prezzo REAL NOT NULL,
                    valuta TEXT DEFAULT 'EUR',
                    asset_type TEXT NOT NULL,
                    status TEXT DEFAULT 'attivo',
                    data_lancio TIMESTAMP
                )''')
                
                cursor.execute('''CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER NOT NULL,
                    service_id INTEGER NOT NULL,
                    data_iscrizione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_cancellazione TIMESTAMP,
                    stato TEXT DEFAULT 'attivo',
                    FOREIGN KEY (client_id) REFERENCES clients(id),
                    FOREIGN KEY (service_id) REFERENCES services(id),
                    UNIQUE(client_id, service_id)
                )''')
                
                cursor.execute('''CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER NOT NULL,
                    importo REAL NOT NULL,
                    valuta TEXT DEFAULT 'EUR',
                    stripe_payment_id TEXT UNIQUE,
                    metodo_pagamento TEXT DEFAULT 'stripe',
                    stato TEXT DEFAULT 'pending',
                    data_pagamento TIMESTAMP,
                    data_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    note TEXT,
                    FOREIGN KEY (client_id) REFERENCES clients(id)
                )''')
                
                cursor.execute('''CREATE TABLE IF NOT EXISTS email_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER,
                    asset_type TEXT,
                    email TEXT NOT NULL,
                    data_invio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    stato TEXT DEFAULT 'sent',
                    file_allegati TEXT,
                    note TEXT,
                    FOREIGN KEY (client_id) REFERENCES clients(id)
                )''')
                
                cursor.execute('''CREATE TABLE IF NOT EXISTS execution_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    screener_type TEXT NOT NULL,
                    data_esecuzione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    tempo_esecuzione_secondi INTEGER,
                    stato TEXT DEFAULT 'success',
                    risultati_count INTEGER,
                    errore TEXT,
                    file_output TEXT
                )''')
                
                # Inserisci servizi iniziali
                cursor.execute('''INSERT OR IGNORE INTO services 
                    (nome, descrizione, prezzo, asset_type, status, data_lancio)
                    VALUES 
                    ('Value Screener AZIONI', 'Screening deep value su 1.200+ ticker USA/EU', 49, 'azioni', 'attivo', '2026-05-01'),
                    ('Value Screener ETF', 'Screening ETF indicizzati', 79, 'etf', 'attivo', '2026-05-01'),
                    ('Value Screener FONDI', 'Screening Fondi Comuni', 99, 'fondi', 'beta', '2026-05-21')
                ''')
                
                conn.commit()
    
    # CLIENTS
    def add_client(self, nome, email, telefono=None, azienda=None, note=None):
        """Aggiungi nuovo cliente"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO clients (nome, email, telefono, azienda, note)
                VALUES (?, ?, ?, ?, ?)''',
                (nome, email, telefono, azienda, note))
            return cursor.lastrowid
    
    def get_clients_by_status(self, stato):
        """Leggi clienti per stato"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM clients WHERE stato = ?', (stato,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_active_clients(self):
        """Leggi solo clienti attivi e pagati"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT c.* FROM clients c
                JOIN subscriptions s ON c.id = s.client_id
                JOIN payments p ON c.id = p.client_id
                WHERE c.stato = 'active' 
                AND s.stato = 'attivo'
                AND p.stato = 'completed'
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    def update_client_status(self, client_id, stato):
        """Aggiorna stato cliente"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE clients SET stato = ? WHERE id = ?',
                (stato, client_id))
    
    # SUBSCRIPTIONS
    def add_subscription(self, client_id, service_id):
        """Aggiungi iscrizione a servizio"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO subscriptions (client_id, service_id)
                VALUES (?, ?)''',
                (client_id, service_id))
            return cursor.lastrowid
    
    def get_subscriptions_by_client(self, client_id):
        """Leggi servizi di un cliente"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.* FROM services s
                JOIN subscriptions sub ON s.id = sub.service_id
                WHERE sub.client_id = ? AND sub.stato = 'attivo'
            ''', (client_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_clients_by_service(self, asset_type):
        """Leggi clienti per asset type (per email_notifier)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT c.id, c.nome, c.email FROM clients c
                JOIN subscriptions s ON c.id = s.client_id
                JOIN services srv ON s.service_id = srv.id
                WHERE srv.asset_type = ?
                AND c.stato = 'active'
                AND s.stato = 'attivo'
            ''', (asset_type,))
            return [dict(row) for row in cursor.fetchall()]
    
    # PAYMENTS
    def add_payment(self, client_id, importo, stripe_payment_id=None):
        """Aggiungi pagamento"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO payments 
                (client_id, importo, stripe_payment_id, stato)
                VALUES (?, ?, ?, 'pending')''',
                (client_id, importo, stripe_payment_id))
            return cursor.lastrowid
    
    def confirm_payment(self, stripe_payment_id):
        """Conferma pagamento da Stripe webhook"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''UPDATE payments SET stato = 'completed', data_pagamento = CURRENT_TIMESTAMP
                WHERE stripe_payment_id = ?''',
                (stripe_payment_id,))
            
            # Aggiorna stato cliente a 'active'
            cursor.execute('''UPDATE clients SET stato = 'active', data_attivazione = CURRENT_TIMESTAMP
                WHERE id = (SELECT client_id FROM payments WHERE stripe_payment_id = ?)''',
                (stripe_payment_id,))
    
    # EMAIL LOGS
    def log_email(self, client_id, asset_type, email, stato='sent', allegati=None):
        """Log invio email"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO email_logs 
                (client_id, asset_type, email, stato, file_allegati)
                VALUES (?, ?, ?, ?, ?)''',
                (client_id, asset_type, email, stato, allegati))
    
    # EXECUTION LOGS
    def log_execution(self, screener_type, tempo_secondi, stato='success', risultati=None, errore=None):
        """Log esecuzione screener"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO execution_logs 
                (screener_type, tempo_esecuzione_secondi, stato, risultati_count, errore)
                VALUES (?, ?, ?, ?, ?)''',
                (screener_type, tempo_secondi, stato, risultati, errore))

# Istanza globale
db = DatabaseManager()
