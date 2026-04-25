import re
import json
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from db import get_db
import os

LOG_FILE = 'data/logs/runtime.log'

def log(msg):
    timestamp = datetime.now().isoformat()
    line = f"[{timestamp}] NORMALIZER: {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\\n')

def normalize_raw_data(raw_record):
    source_name = raw_record[2]
    raw_data_str = raw_record[3]
    raw_data = json.loads(raw_data_str)

    content = raw_data.get('html') or raw_data.get('xml_or_json', '') or ''
    if not content:
        log(f"{source_name}: no content")
        return []

    products = []
    log(f"Parsing {source_name} (real data only)")

    # 1. Official Raspberry Pi HTML (BeautifulSoup)
    if 'raspberrypi_official_products' in source_name:
        soup = BeautifulSoup(content, 'html.parser')
        # Better selectors for Raspberry Pi products page
        product_links = soup.find_all('a', href=True)
        log(f"  → Found {len(product_links)} links, scanning for products")
        keywords = ['pi 5', 'rpi5', 'pi5', 'raspberry pi 5', 'raspberry pi 4', 'pi 4', 'raspberry-pi-5', 'raspberrypi5']
        matched = 0
        for a in product_links[:50]:
            href = a.get('href', '')
            if not href.startswith('http') and href.startswith('/'):
                href = 'https://www.raspberrypi.com' + href
            text = a.get_text(strip=True).lower()
            if any(kw in text or kw.replace(' ', '-') in text for kw in keywords):
                name = a.get_text(strip=True)[:100]
                if len(name) < 5: continue  # skip junk
                products.append({
                    'sku': f"rpi_official_{matched}_{name[:20].replace(' ', '_').replace('/', '_')}",
                    'name': name,
                    'price_usd': None,
                    'availability': 'check_page',
                    'url': href,
                    'seller': 'raspberrypi.com',
                    'confidence': 5
                })
                log(f"    → MATCHED: {name[:60]} | URL: {href}")
                matched += 1
        log(f"  → RPi official: {matched} products extracted")

    # 2. Shopify JSON
    elif 'shopify_json' in source_name or 'pimoroni' in source_name:
        try:
            products_json = json.loads(content)
            keywords = ['pi 5', 'rpi5', 'pi5', 'raspberry pi 5', 'raspberry pi 4', 'rock 5b', 'radxa', 'orange pi', 'orange pi 5', 'orange pi 5 plus', 'jetson', 'jetson nano', 'jetson orin']
            for item in products_json[:20]:
                title = item.get('title', '')
                if any(kw in title.lower() for kw in keywords):
                    variants = item.get('variants', [])
                    for v in variants[:5]:
                        price_str = v.get('price')
                        price_usd = float(price_str)/100 if price_str else None
                        avail = v.get('available', False)
                        handle = item.get('handle', '')
                        products.append({
                            'sku': f"{source_name}_{handle}_{v.get('id', 0)}",
                            'name': title,
                            'price_usd': price_usd,
                            'availability': 'in_stock' if avail else 'out_of_stock',
                            'url': item.get('url', f"https://{source_name.split('_')[0]}.com/products/{handle}"),
                            'seller': source_name.split('_')[0],
                            'confidence': 6
                        })
                        log(f"    → MATCHED: {title} ${price_usd or 'N/A'} {avail} conf=6 (JSON)")
                        print(f"NORMALIZER MATCH JSON: {title} | ${price_usd} | {avail} | https://{source_name.split('_')[0]}.com/products/{handle}")
            except:
                log("  → Invalid JSON - logged failure")

    return products

def process_recent_raw(hours_back=24):
    # same as before, but add confidence field to schema if needed (add to products table)
    conn = get_db()
    cursor = conn.cursor()
    cutoff = datetime.now() - timedelta(hours=hours_back)
    cursor.execute("""
        SELECT * FROM products_raw WHERE timestamp > ? ORDER BY id DESC LIMIT 20
    """, (cutoff,))
    raw_records = cursor.fetchall()
    conn.close()

    all_products = []
    for record in raw_records:
        prods = normalize_raw_data(record)
        all_products.extend(prods)

    inserted = 0
    if all_products:
        conn = get_db()
        cursor = conn.cursor()
        for prod in all_products:
            cursor.execute('''
                INSERT OR REPLACE INTO products (sku, name, price_usd, availability, url, seller, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (prod['sku'], prod['name'], prod['price_usd'],
                  prod['availability'], prod['url'], prod['seller'], prod.get('confidence', 0)))
            inserted += cursor.rowcount
        conn.commit()
        conn.close()
        log(f"✅ {inserted} REAL products stored")
        return True
    log("⚠️ NO REAL PRODUCTS")
    return False

def test_normalizer():
    success = process_recent_raw(hours_back=24)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM products WHERE confidence > 0")
    real_total = cursor.fetchone()[0]
    conn.close()
    log(f"REAL high-confidence products: {real_total}")
    return success

if __name__ == "__main__":
    test_normalizer()
