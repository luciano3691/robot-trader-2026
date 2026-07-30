-- Robot Trader 2026 - Database Schema SQLite
-- python: sqlite3 robot_trader.db < schema.sql

CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    telefono TEXT,
    azienda TEXT,
    stato TEXT DEFAULT 'pending_payment',
    data_iscrizione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_attivazione TIMESTAMP,
    note TEXT
);

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    descrizione TEXT,
    prezzo REAL NOT NULL,
    valuta TEXT DEFAULT 'EUR',
    asset_type TEXT NOT NULL,
    status TEXT DEFAULT 'attivo',
    data_lancio TIMESTAMP
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    service_id INTEGER NOT NULL,
    data_iscrizione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_cancellazione TIMESTAMP,
    stato TEXT DEFAULT 'attivo',
    FOREIGN KEY (client_id) REFERENCES clients(id),
    FOREIGN KEY (service_id) REFERENCES services(id),
    UNIQUE(client_id, service_id)
);

CREATE TABLE IF NOT EXISTS payments (
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
);

CREATE TABLE IF NOT EXISTS email_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER,
    asset_type TEXT,
    email TEXT NOT NULL,
    data_invio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    stato TEXT DEFAULT 'sent',
    file_allegati TEXT,
    note TEXT,
    FOREIGN KEY (client_id) REFERENCES clients(id)
);

CREATE TABLE IF NOT EXISTS execution_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    screener_type TEXT NOT NULL,
    data_esecuzione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tempo_esecuzione_secondi INTEGER,
    stato TEXT DEFAULT 'success',
    risultati_count INTEGER,
    errore TEXT,
    file_output TEXT
);

-- Indici per performance
CREATE INDEX IF NOT EXISTS idx_clients_email ON clients(email);
CREATE INDEX IF NOT EXISTS idx_clients_stato ON clients(stato);
CREATE INDEX IF NOT EXISTS idx_subscriptions_client ON subscriptions(client_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_stato ON subscriptions(stato);
CREATE INDEX IF NOT EXISTS idx_payments_client ON payments(client_id);
CREATE INDEX IF NOT EXISTS idx_payments_stato ON payments(stato);
CREATE INDEX IF NOT EXISTS idx_email_logs_client ON email_logs(client_id);

-- Dati iniziali
INSERT OR IGNORE INTO services (nome, descrizione, prezzo, asset_type, status, data_lancio)
VALUES 
    ('Value Screener AZIONI', 'Screening deep value su 1.200+ ticker USA/EU', 49, 'azioni', 'attivo', '2026-05-01'),
    ('Value Screener ETF', 'Screening ETF indicizzati', 79, 'etf', 'attivo', '2026-05-01'),
    ('Value Screener FONDI', 'Screening Fondi Comuni', 99, 'fondi', 'beta', '2026-05-21');
