import yaml
import sqlite3
import statistics
from datetime import datetime, timedelta
from db import get_db

DB_PATH = 'hardware_alerts.db'

def load_products_config():
    with open('config/products.yaml', 'r') as f:
        return yaml.safe_load(f)['products']

def get_baseline(product_name):
    products = load_products_config()
    for pid, info in products.items():
        if info['name'].lower() in product_name.lower():
            return info['baseline_price_usd']
    return None

def get_historical_median(sku, days=30):
    conn = get_db()
    cursor = conn.cursor()
    cutoff = datetime.now() - timedelta(days=days)
    cursor.execute('''
        SELECT ph.price_usd FROM price_history ph
        JOIN products p ON ph.product_id = p.id
        WHERE p.sku = ? AND ph.timestamp > ?
    ''', (sku, cutoff.isoformat()))
    prices = [row[0] for row in cursor.fetchall() if row[0]]
    conn.close()
    return statistics.median(prices) if len(prices) >= 3 else None

def days_since_first_seen(sku):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT MIN(normalized_at) FROM products WHERE sku = ?', (sku,))
    first = cursor.fetchone()[0]
    conn.close()
    if first:
        delta = datetime.now() - datetime.fromisoformat(first)
        return delta.days
    return 999

def compute_scores(product):
    # product tuple: sku, name, price_usd, availability, seller, url, confidence
    sku, name, price, avail, seller, url, conf = product
    
    opp_score = 0  # 0-10
    conf_score = conf or 0  # 0-6
    rarity_score = 0  # 0-4
    
    # Opportunity (value)
    if avail == 'in_stock':
        opp_score += 5
    if price:
        baseline = get_baseline(name)
        median = get_historical_median(sku)
        if baseline and price <= baseline * 0.9:
            opp_score += 3
        if median and price <= median * 0.85:
            opp_score += 2
    
    # Rarity
    days_first = days_since_first_seen(sku)
    if days_first > 30:
        rarity_score += 4
    elif days_first > 7:
        rarity_score += 2
    elif days_first > 1:
        rarity_score += 1
    
    final_score = min(20, opp_score + conf_score + rarity_score)
    
    reasons = f"opp:{opp_score} conf:{conf_score} rare:{rarity_score}"
    
    return final_score, conf_score, reasons

def test_scorer():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT sku, name, price_usd, availability, seller, url, confidence
        FROM products WHERE confidence > 0 ORDER BY normalized_at DESC LIMIT 5
    ''')
    products = cursor.fetchall()
    conn.close()
    
    print("🧠 New Scoring (real products only):")
    high_scores = []
    for prod in products:
        final, conf, reason = compute_scores(prod)
        print(f"  {prod[0]}: FINAL={final}/20 CONF={conf} ({reason}) | {prod[1]} ${prod[2] or 'N/A'}")
        if final >= 14 and conf >= 4:
            high_scores.append((prod, final, conf, reason))
    
    print(f"\n🚨 Alert-ready (>=14 total, >=4 conf): {len(high_scores)}")
    print("PHASE UPGRADE COMPLETE")

if __name__ == "__main__":
    test_scorer()
