import requests
import yaml
import json
import os
import time
from datetime import datetime, timedelta
from db import get_db
from scorer import compute_scores, days_since_first_seen, get_baseline, get_historical_median
from data.msrp_baseline import get_msrp, parse_memory_gb, compute_deal_score, get_deal_emoji, compute_heat_score

import sqlite3
from datetime import datetime, timedelta

USERS_FILE = 'data/users.json'
REFERRALS_FILE = 'data/referrals.json'
SHAREABLE_EVENTS_FILE = 'data/shareable_events.json'
DAILY_ALERTS_FILE = 'data/daily_alerts.json'
SUPPRESSED_LOG = 'data/logs/suppressed_alerts.log'
REVENUE_METRICS_FILE = 'data/revenue_funnel_metrics.json'
CONVERSION_PERF_FILE = 'data/conversion_performance.json'

def load_json(file_path, default=None):
    if default is None:
        default = {}
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return default

def save_json(file_path, data):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

def load_telegram_config():
    with open('config/sources.yaml', 'r') as f:
        config = yaml.safe_load(f)
    return config['telegram']

def get_or_create_user(telegram_id):
    users = load_json(USERS_FILE)
    if telegram_id not in users:
        users[telegram_id] = {
            "telegram_id": telegram_id,
            "tier": "free",
            "alerts_seen": 0,
            "high_value_alerts_seen": 0,
            "converted": False,
            "referral_code": f"{telegram_id}-REF",
            "invited_by": None,
            "conversion_heat_score": 0,
            "last_activity": datetime.now().isoformat(),
            "conversion_window_start": None,
            "hours_since_first_exposure": 0,
            "conversion_deadline": None,
            "conversion_attempts": 0,
            "conversion_reliability_score": 0,
            "last_active_hour": "",
            "peak_engagement_window": "",
            "alerts_opened_pattern": []
        }
        save_json(USERS_FILE, users)
    return users, users[telegram_id]

def send_telegram_alert(bot_token, chat_id, message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        print(f"Telegram sent: {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        print(f"Telegram fail: {e}")
        return False

def check_and_alert():
    tg = load_telegram_config()
    chat_id = tg['chat_id']
    users, user = get_or_create_user(chat_id)
    preferred_variants = user.get('preferred_variants', [])
    price_targets = {v['family']: v.get('max_price') for v in preferred_variants if 'max_price' in v}
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.sku, p.name, p.price_usd, p.availability, p.seller, p.url, p.confidence
        FROM products p ORDER BY p.normalized_at DESC LIMIT 5
    """)
    products = cursor.fetchall()
    conn.close()
    
    for prod in products:
        prod_id, sku, name, price, avail, seller, url, conf_score = prod[:8]
        product_tuple = (sku, name, price, avail, seller, url, conf_score)
        final_score, conf_score, reason = compute_scores(product_tuple)

        # Variant filter
        memory_gb_prod = parse_memory_gb(name)
        if preferred_variants:
            variant_match = any(
                v.get('family') == 'all' or v.get('family') == family.lower() and v.get('memory_gb') == memory_gb_prod for v in preferred_variants
            )
            if not variant_match:
                continue
        
        # Price target filter
        max_price = price_targets.get(family.lower())
        if max_price and price > max_price and not (msrp and price <= msrp):
            continue
        
        # Aggregate canonical data
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM canonical_products WHERE confidence_score >= 0.6 ORDER BY updated_at DESC LIMIT 1')
        canonical = c.fetchone()
        conn.close()
        if canonical:
            obj = {
                'family': canonical[1],
                'sources': json.loads(canonical[3]),
                'price_stats': json.loads(canonical[4]),
                'confidence_score': canonical[5]
            }
            in_stock_sources = [s for s in obj['sources'] if s['availability'] == 'in_stock']
            cheapest = min(in_stock_sources, key=lambda s: s['price']) if in_stock_sources else None
            alternatives = [s for s in in_stock_sources if s['price'] > cheapest['price'] * 1.05]
            spread = obj['price_stats']['spread_percent']
            scarcity = 'high' if len(in_stock_sources) <= 2 else 'low'

            # Deal score for cheapest
            family = obj['family']
            memory_gb = obj.get('memory_gb', parse_memory_gb(obj.get('family', '')))
            msrp = get_msrp(family, memory_gb)
            deal_rating, deal_score = compute_deal_score(cheapest['price'] if cheapest else None, msrp, obj['confidence_score'])
            deal_emoji = get_deal_emoji(deal_rating)
            msrp_delta_str = f"{((cheapest['price'] - msrp)/msrp*100):+.0f}%" if msrp and cheapest else "N/A"

            # Guardrail check for user targets
            for v in preferred_variants:
                if v.get('family') == family and v.get('memory_gb') == memory_gb:
                    max_price = v.get('max_price')
                    if max_price and max_price < msrp:
                        expectation_delta = (max_price - msrp) / msrp if msrp else 0
                        expectation_msg = get_expectation_msg(expectation_delta)
                        print(expectation_msg)  # Log warning for now

            # Savings
            saved_vs_msrp = (msrp - cheapest['price']) if msrp and cheapest and cheapest['price'] < msrp else 0
            market_avg = obj['price_stats'].get('avg_price', cheapest['price'] if cheapest else 0)
            saved_vs_market = (market_avg - cheapest['price']) if market_avg > cheapest['price'] else 0

            target_hit = any(v.get('memory_gb') == memory_gb and v.get('max_price', float('inf')) >= cheapest['price'] for v in preferred_variants)

            why_matters = "Near MSRP restock — these sell out fast." if msrp and cheapest['price'] <= msrp * 1.2 else "Lowest price seen in last 48h."

            savings_msg = ""
            if saved_vs_msrp > 0:
                savings_msg += f"\n💸 Save ${saved_vs_msrp:.0f} vs MSRP"
            if saved_vs_market > 0:
                savings_msg += f"\n💸 Save ${saved_vs_market:.0f} vs market"

            target_msg = "\n🎯 Your target hit!" if target_hit else ""

            # First-lookup hierarchy format
            deal_quality_str = f"{deal_emoji} {deal_rating.upper()} ({deal_score}/10)"
            message = f"""
<b>{family} ({memory_gb}GB)</b>

🔥 <b>Best Available Now</b>

<b>${cheapest['price']:.0f} — {cheapest['source_name']}</b>

{deal_quality_str}

Confidence: {obj['confidence_score']:.2f}
In-stock: Yes

{msrp_delta_str}

[ Buy Now: {cheapest.get('url', 'N/A')} ]

---

<b>Want more?</b>
{explore_prompt if 'explore_prompt' in locals() else 'See alternatives, history, restocks below.'}
            """.strip()
        else:
            message = 'No canonical high-conf products ready.'
        
        sent = send_telegram_alert(tg['bot_token'], chat_id, message)
        print(f"Alert sent to {chat_id}: {name} score={final_score}")
        if sent:
            break  # one test alert
    
    print("TEST ALERT COMPLETE")

if __name__ == "__main__":
    check_and_alert()
