import sqlite3
import json
from datetime import datetime
import os

DB_PATH = 'hardware_alerts.db'

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL;')  # Better concurrency
    return conn

def init_schema():
    conn = get_db()
    cursor = conn.cursor()
    
    # products_raw: raw fetches
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products_raw (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            source_name TEXT NOT NULL,
            raw_data TEXT NOT NULL  -- JSON string
        )
    ''')
    
    # products: normalized
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE,
            name TEXT,
            family TEXT,
            memory_gb INTEGER,
            storage TEXT,
            variant TEXT,
            price_usd REAL,
            availability TEXT,
            url TEXT,
            seller TEXT,
            tier INTEGER DEFAULT 1,
            confidence INTEGER DEFAULT 0,
            normalized_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS canonical_products (
            product_id TEXT PRIMARY KEY,
            family TEXT NOT NULL,
            variant JSON,
            sources JSON,
            price_stats JSON,
            confidence_score REAL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # products: normalized (added confidence)
    cursor.execute('ALTER TABLE products ADD COLUMN confidence INTEGER DEFAULT 0')

    # price_history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            price_usd REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    ''')
    
    # alerts
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            score INTEGER,
            reason TEXT,
            sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Schema initialized")

def test_write_read():
    init_schema()
    
    # Write dummy raw
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO products_raw (source_name, raw_data) VALUES (?, ?)",
        ("test_source", json.dumps({"price": 99.99, "stock": "yes"}))
    )
    raw_id = cursor.lastrowid
    conn.commit()
    
    # Read raw
    cursor.execute("SELECT * FROM products_raw WHERE id=?", (raw_id,))
    raw = cursor.fetchone()
    print(f"✅ Raw write/read: ID={raw[0]}, data={raw[3][:50]}...")
    
    # Write normalized product
    cursor.execute('''
        INSERT OR IGNORE INTO products (sku, name, price_usd, availability, seller)
        VALUES (?, ?, ?, ?, ?)
    ''', ("RPI5-TEST", "Raspberry Pi 5 Test", 99.99, "in_stock", "test_seller"))
    cursor.execute("SELECT id FROM products WHERE sku=?", ("RPI5-TEST",))
    prod_id = cursor.fetchone()[0]
    
    # Write price history
    cursor.execute(
        "INSERT INTO price_history (product_id, price_usd) VALUES (?, ?)",
        (prod_id, 99.99)
    )
    
    # Write alert
    cursor.execute(
        "INSERT INTO alerts (product_id, score, reason) VALUES (?, ?, ?)",
        (prod_id, 18, "Test high score")
    )
    
    conn.commit()
    conn.close()
    
    # Read counts
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM products_raw")
    print(f"✅ Tables populated: raw={cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM products")
    print(f"  products={cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM price_history")
    print(f"  history={cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM alerts")
    print(f"  alerts={cursor.fetchone()[0]}")
    conn.close()
    
    print("PHASE 3 COMPLETE")

if __name__ == "__main__":
    test_write_read()
