#!/usr/bin/env python3
import json
from typing import Dict, List, Any, Optional
from routing_layer import get_market_feed  # Loads MARKET_FEED
from data.msrp_baseline import get_msrp, parse_memory_gb

# Static source reliability (for fastest mode only)
SOURCE_RELIABILITY = {
    'amazon': 0.9,
    'official_vendor': 1.0,
    'shopify': 0.7,
    'unknown_store': 0.4
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

    valid_markups = []
    for item in items:
        memory_gb = parse_memory_gb(item.get('variant', item.get('name', '')))
        msrp_item = get_msrp(item.get('family', 'Unknown'), memory_gb) if memory_gb else None
        if msrp_item and item['price']:
            markup = ((item['price'] - msrp_item) / msrp_item) * 100
            valid_markups.append(markup)

    avg_markup = sum(valid_markups) / len(valid_markups) if valid_markups else None

    memory_gb = parse_memory_gb(items[0].get('variant', items[0].get('name', ''))) if items else None
    variant_str = f"{memory_gb}GB" if memory_gb else None

    return {
        'price_range': {'min': min(prices) if prices else None, 'max': max(prices) if prices else None},
        'avg_markup_pct': round(avg_markup, 2) if avg_markup else None,
        'sources_count': len(set(i['source'] for i in items)),
        'memory_gb': memory_gb,
        'variant': variant_str
    }

def optimize_buy(family: str, memory_gb: Optional[int] = None, goal: str = 'cheapest') -> Dict[str, Any]:
    """Main entry: best_option from MARKET_FEED for specific variant if memory_gb provided."""
    market_feed = get_market_feed(memory_gb)
    valid_items = filter_valid_items(market_feed, family, memory_gb)
    ranked_items = rank_items(valid_items, goal)
    
    if not ranked_items:
        return {
            'query': f'{family}-{goal}',
            'best_option': None,
            'alternatives': [],
            'market_summary': compute_market_summary(valid_items)
        }
    
    best = ranked_items[0]
    # Add variant info to best
    memory_gb = parse_memory_gb(best.get('variant', best.get('name', '')))
    best['memory_gb'] = memory_gb
    best['variant'] = f"{memory_gb}GB" if memory_gb else None

    alternatives = ranked_items[1:4]  # Up to 3
    for alt in alternatives:
        memory_gb_alt = parse_memory_gb(alt.get('variant', alt.get('name', '')))
        alt['memory_gb'] = memory_gb_alt
        alt['variant'] = f"{memory_gb_alt}GB" if memory_gb_alt else None
    
    reason_map = {
        'cheapest': f"Lowest price (${best['price']}) + high conf ({best['confidence']})",
        'fastest': f"Top reliability source ({best.get('source_type', '?')}) + conf ({best['confidence']})",
        'balanced': f"Balanced score ({best['confidence']:.2f} conf + low price)"
    }
    
    # Compute deal score for best
    memory_gb_best = best.get('memory_gb')
    msrp_best = get_msrp(best.get('family', 'Unknown'), memory_gb_best) if memory_gb_best else None
    deal_rating_best, deal_score_best = compute_deal_score(best.get('price'), msrp_best, best.get('confidence', 0))
    best['deal_rating'] = deal_rating_best
    best['msrp_delta_pct'] = ((best.get('price') - msrp_best) / msrp_best) if msrp_best and best.get('price') else None

    # For alternatives
    for alt in alternatives:
        memory_gb_alt = alt.get('memory_gb')
        msrp_alt = get_msrp(alt.get('family', 'Unknown'), memory_gb_alt) if memory_gb_alt else None
        deal_rating_alt, _ = compute_deal_score(alt.get('price'), msrp_alt, alt.get('confidence', 0))
        alt['deal_rating'] = deal_rating_alt
        alt['msrp_delta_pct'] = ((alt.get('price') - msrp_alt) / msrp_alt) if msrp_alt and alt.get('price') else None

    best['reason'] = reason_map.get(goal, 'Best per criteria')
    
    # Insight and urgency
    urgency = "high" if deal_score_best >= 4 else "medium" if deal_score_best == 3 else "low"
    insight = f"Save ${round(msrp_best - best['price'], 0)} vs MSRP — lowest price available now" if msrp_best and best['price'] < msrp_best else "Strong availability signal"

    # Primary result card for first-lookup UI
    primary_card = {
        'family': family,
        'variant': best.get('variant', 'Unknown'),
        'best_available': True,
        'price': best['price'],
        'source': best['source'],
        'deal_quality': {
            'rating': deal_rating_best,
            'score': f"{deal_score_best}/10",
            'emoji': get_deal_emoji(deal_rating_best)
        },
        'confidence': best.get('confidence', 0),
        'in_stock': best.get('availability') == 'in_stock',
        'msrp_delta': f"+${round(best['price'] - msrp_best, 0)} ({round(((best['price'] - msrp_best)/msrp_best*100), 0)}%)" if msrp_best else 'N/A',
        'action_url': best.get('url')
    }

    return {
        'query': f'{family}-{goal}',
        'primary_card': primary_card,
        'best_option': best,
        'alternatives': alternatives,
        'market_summary': compute_market_summary(valid_items),
        'insight': insight,
        'urgency': urgency,
        'explore_prompt': "Want to compare other deals or variants? See cheapest across sellers, track drops, check restocks. [Explore More]"
    }

if __name__ == '__main__':
    print(json.dumps(optimize_buy('Rock 5B', 'cheapest'), indent=2))
