#!/usr/bin/env python3
import json
from typing import Dict, List, Any, Optional
from routing_layer import get_market_feed  # Loads MARKET_FEED
from data.msrp_baseline import MSRP_BASELINE  # Assume exists or inline

# Static source reliability (for fastest mode only)
SOURCE_RELIABILITY = {
    'amazon': 0.9,
    'official_vendor': 1.0,
    'shopify': 0.7,
    'unknown_store': 0.4
}

# MSRP baseline (inline for self-contained)
MSRP_BASELINE = {
    'Raspberry Pi 5': 69.99,
    'Raspberry Pi 4': 55.00,
    'Rock 5B': 119.00,
    'Orange Pi 5': 89.00,
    'Jetson Orin Nano': 499.00
}

def filter_valid_items(market_feed: List[Dict], family: str) -> List[Dict]:
    """Filter MARKET_FEED for family: in_stock + confidence >= 0.5"""
    family_items = []
    for feed_item in market_feed:
        if feed_item.get('family') == family:
            items = feed_item.get('items', [])
            for item in items:
                if (item.get('availability') == 'in_stock' and 
                    item.get('confidence', 0) >= 0.5):
                    item['family'] = family  # Ensure family context
                    family_items.append(item)
    return family_items

def rank_items(items: List[Dict], goal: str) -> List[Dict]:
    """Rank filtered items per goal."""
    if not items:
        return []
    
    def cheapest_key(item):
        return (item['price'], -item['confidence'])
    
    def fastest_key(item):
        rel = SOURCE_RELIABILITY.get(item.get('source_type', 'unknown_store'), 0.4)
        return (-rel, -item['confidence'], item['price'])
    
    def balanced_key(item):
        # Simple inverse price rank (lower price higher rank)
        price_rank_inv = 1.0 / (item['price'] or 1)
        score = 0.5 * item['confidence'] + 0.5 * price_rank_inv
        return -score  # Descending score
    
    key_map = {
        'cheapest': cheapest_key,
        'fastest': fastest_key,
        'balanced': balanced_key
    }
    
    key_fn = key_map.get(goal, cheapest_key)
    return sorted(items, key=key_fn)

def compute_market_summary(items: List[Dict]) -> Dict:
    """Compute summary from filtered items."""
    if not items:
        return {'price_range': {'min': None, 'max': None}, 'avg_markup_pct': None, 'sources_count': 0}
    
    prices = [i['price'] for i in items if i['price']]
    msrp = MSRP_BASELINE.get(items[0]['family'], None)
    avg_markup = ((sum(prices)/len(prices) - msrp)/msrp * 100) if prices and msrp else None
    
    return {
        'price_range': {'min': min(prices), 'max': max(prices)},
        'avg_markup_pct': round(avg_markup, 2) if avg_markup else None,
        'sources_count': len(set(i['source'] for i in items))
    }

def optimize_buy(family: str, goal: str = 'cheapest') -> Dict[str, Any]:
    """Main entry: best_option from MARKET_FEED."""
    market_feed = get_market_feed()
    valid_items = filter_valid_items(market_feed, family)
    ranked_items = rank_items(valid_items, goal)
    
    if not ranked_items:
        return {
            'query': f'{family}-{goal}',
            'best_option': None,
            'alternatives': [],
            'market_summary': compute_market_summary(valid_items)
        }
    
    best = ranked_items[0]
    alternatives = ranked_items[1:4]  # Up to 3
    
    reason_map = {
        'cheapest': f"Lowest price (${best['price']}) + high conf ({best['confidence']})",
        'fastest': f"Top reliability source ({best.get('source_type', '?')}) + conf ({best['confidence']})",
        'balanced': f"Balanced score ({best['confidence']:.2f} conf + low price)"
    }
    
    best['reason'] = reason_map.get(goal, 'Best per criteria')
    
    return {
        'query': f'{family}-{goal}',
        'best_option': best,
        'alternatives': alternatives,
        'market_summary': compute_market_summary(valid_items)
    }

if __name__ == '__main__':
    print(json.dumps(optimize_buy('Rock 5B', 'cheapest'), indent=2))
