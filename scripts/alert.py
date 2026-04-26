#!/usr/bin/env python3
import os
import requests
import yaml

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TEST_ALERT = os.getenv('TEST_ALERT', 'false').lower() == 'true'

def format_alert(product):
    \"\"\"Strict live-price-only format\"\"\" 
    return f\"\"\"🚨 {product['variant_full_name']} in stock!

Price: ${product['price']}
At: {product['source']}
{product['url']}\"\"\"

def send_telegram_alert(product):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(\"❌ Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID\")
        return False
    
    url = f\"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage\"
    message = format_alert(product)
    
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print(f\"✅ Alert sent successfully: {product['variant_full_name']}\")
            return True
        else:
            print(f\"❌ Telegram error {resp.status_code}: {resp.text}\")
            return False
    except Exception as e:
        print(f\"❌ Send failed: {e}\")
        return False

if __name__ == '__main__':
    # Load demo/test products
    test_products = [
        {'variant_full_name': 'Radxa ROCK 5B 32GB', 'price': '229', 'source': 'Radxa Store', 'url': 'https://radxa.com/products/rock5-5b-32gb'},
        {'variant_full_name': 'Raspberry Pi 5 16GB', 'price': '269', 'source': 'The Pi Hut', 'url': 'https://thepihut.com/products/raspberry-pi-5-16gb'}
    ]
    
    if TEST_ALERT:
        print(\"🧪 TEST MODE: Sending sample alert...\")
        sent = send_telegram_alert(test_products[0])
        if sent:
            print(\"Test alert delivered!\")
    else:
        print(\"ℹ️ Set TEST_ALERT=true to send test, or run full pipeline for live alerts\")
        print(\"Missing env vars:\", \"BOT\" not in os.environ, \"CHAT\" not in os.environ)