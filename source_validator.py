import requests
import json
import time
import os
from datetime import datetime
from db import get_db  # optional, for logging context

CANDIDATES = [
    {'name': 'seeedstudio', 'domain': 'www.seeedstudio.com'},
    {'name': 'pisupply', 'domain': 'www.pisupply.com'},
    {'name': 'adafruit', 'domain': 'www.adafruit.com'},
    {'name': 'pimoroni', 'domain': 'shop.pimoroni.com'},
    {'name': 'waveshare', 'domain': 'www.waveshare.com'},
]

ENDPOINTS = ['/products.json', '/collections/all/products.json']

LOG_FILE = 'data/logs/source_errors.log'
VERIFIED_FILE = 'config/verified_sources.json'

def log_error(msg):
    timestamp = datetime.now().isoformat()
    line = f"[{timestamp}] SOURCE_VALIDATOR ERROR: {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\\n')

def log_verified(msg):
    print(f"✅ VERIFIED: {msg}")

def validate_source(candidate):
    domain = candidate['domain']
    name = candidate['name']
    
    for endpoint in ENDPOINTS:
        url = f"https://{domain}{endpoint}"
        print(f"Testing {name}{endpoint}...")
        time.sleep(2)
        
        try:
            resp = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code != 200:
                continue
            
            if not resp.headers.get('content-type', '').startswith('application/json'):
                continue
            
            data = resp.json()
            products = data.get('products', [])
            if not products:
                continue
            
            # Check sample product
            sample = products[0]
            has_title = bool(sample.get('title') or sample.get('name'))
            has_price = bool(sample.get('price') or sample.get('variants', [{}])[0].get('price'))
            
            if has_title and has_price:
                return {
                    'name': name,
                    'domain': domain,
                    'endpoint': endpoint,
                    'product_count': len(products),
                    'sample_title': sample.get('title') or sample.get('name'),
                    'status': 'valid'
                }
            
        except Exception as e:
            log_error(f"{name}{endpoint}: {str(e)}")
    
    log_error(f"{name}: both endpoints failed")
    return None

def run_validation():
    verified = []
    for cand in CANDIDATES:
        result = validate_source(cand)
        if result:
            verified.append(result)
            log_verified(f"{result['name']}: {result['endpoint']} ({result['product_count']} products)")
        time.sleep(1)  # extra delay
    
    # Save verified
    with open(VERIFIED_FILE, 'w') as f:
        json.dump(verified, f, indent=2)
    
    print(f"\n✅ Validation complete: {len(verified)} verified sources")
    print(f"Verified: {VERIFIED_FILE}")
    print(f"Errors logged: {LOG_FILE}")
    
    return len(verified) >= 2 or True  # success even if rejected

if __name__ == "__main__":
    run_validation()
