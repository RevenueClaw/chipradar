import yaml
import requests
import json
import time
import os
from datetime import datetime
from db import get_db
import glob

LOG_FILE = 'data/logs/runtime.log'
VERIFIED_FILE = 'config/verified_sources.json'

def log(msg):
    timestamp = datetime.now().isoformat()
    line = f"[{timestamp}] COLLECTOR: {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\\n')

def load_verified_sources():
    if os.path.exists(VERIFIED_FILE):
        with open(VERIFIED_FILE, 'r') as f:
            return json.load(f)
    log("No verified_sources.json - skipping Shopify")
    return []

def load_sources():
    # Legacy YAML for non-Shopify (official HTML etc.)
    try:
        with open('config/sources.yaml', 'r') as f:
            yaml_sources = yaml.safe_load(f)['sources']
    except:
        yaml_sources = []
    
    # PRIORITY: ONLY verified Shopify
    verified = load_verified_sources()
    shopify_sources = []
    for v in verified:
        shopify_sources.append({
            'name': v['name'] + '_verified',
            'url': f"https://{v['domain']}{v['endpoint']}",
            'type': 'json',
            'category': v.get('category', 'raspberry_pi_5'),
            'tier': v.get('tier', 1)
        })
    
    log(f"Loaded {len(yaml_sources)} YAML + {len(shopify_sources)} VERIFIED Shopify = {len(yaml_sources) + len(shopify_sources)} total")
    return yaml_sources + shopify_sources

def fetch_source(source):
    url = source['url']
    source_name = source['name']
    
    log(f"Fetching VERIFIED {source_name}: {url}")
    
    try:
        resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0 (compatible; HardwareMonitor/1.0)'})
        log(f"  → Status: {resp.status_code}, len: {len(resp.text)}")
        
        raw_data = {
            "status_code": resp.status_code,
            "url": url,
            "content_type": resp.headers.get('content-type', ''),
            "xml_or_json": resp.text  # for JSON/RSS
        }
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO products_raw (source_name, raw_data) VALUES (?, ?)",
            (source_name, json.dumps(raw_data))
        )
        conn.commit()
        conn.close()
        
        log(f"✅ Stored from VERIFIED {source_name}")
        return raw_data
        
    except Exception as e:
        log(f"❌ VERIFIED fetch failed {source_name}: {str(e)}")
        return None

def run_collector():
    log("=== VERIFIED COLLECTOR START (Shopify validated only) ===")
    sources = load_sources()
    if not sources:
        log("⚠️ NO SOURCES (no verified + no YAML fallback)")
        return False
    
    valid_data = False
    for source in sources:
        raw_data = fetch_source(source)
        if raw_data and raw_data['status_code'] == 200:
            content = raw_data.get('xml_or_json', '')
            if content and ('pi 5' in content.lower() or 'raspberry' in content.lower()):
                valid_data = True
                log(f"  → Pi5 data confirmed in {source['name']}")
        time.sleep(2)  # validated throttle
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM products_raw WHERE source_name LIKE '%verified%'")
    verified_raw = cursor.fetchone()[0]
    conn.close()
    
    log(f"VERIFIED complete: {verified_raw} verified raw records")
    return valid_data

if __name__ == "__main__":
    run_collector()
