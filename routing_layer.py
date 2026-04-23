# Routing Layer: Dual-Feed Output System
# Post-trend router for RESTOCK and MARKET feeds

import json
import logging
from db import get_db

logger = logging.getLogger(__name__)

from data.msrp_baseline import get_msrp

# Authorized sources (official + authorized retailers)
AUTHORIZED_SOURCES = {"official_vendor", "authorized_retailer"}


def get_source_distribution(source_dist_str):
    """Parse source distribution from JSON string."""
    try:
        return json.loads(source_dist_str) if source_dist_str else {}
    except:
        return {}


def calculate_markup_pct(price, msrp):
    """Compute markup percentage from price and MSRP."""
    if not price or not msrp:
        return None
    return ((price - msrp) / msrp) * 100


def get_majority_source(source_dist):
    """Identify majority source type from distribution."""
    if not source_dist:
        return None
    return max(source_dist, key=source_dist.get)


def has_strong_signal_majority(source_dist):
    """Check if strong signals represent >50% majority."""
    if not source_dist:
        return False
    # Assuming strong signals are official + authorized sources
    strong_count = sum(
        source_dist.get(src, 0)
        for src in AUTHORIZED_SOURCES
    )
    total = sum(source_dist.values())
    return (strong_count / total) > 0.5 if total > 0 else False


def route_canonical_trends():
    """
    Route canonical_trends into RESTOCK and MARKET feeds.
    Returns: (restock_feed, market_feed)
    """
    conn = get_db()
    cursor = conn.cursor()
    
    # Fetch all recent canonical_trends (last 24 hours)
    cursor.execute("""
        SELECT family, avg_price, avg_family_confidence,
               source_distribution, strong_pct, weak_pct,
               min_price, max_price, created_at
        FROM canonical_trends
        WHERE created_at >= datetime('now', '-24 hours')
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    restock_feed = []
    market_feed = []
    restock_families = []
    market_families = []
    
    for row in rows:
        family, avg_price, avg_conf, source_dist_str, \
            strong_pct, weak_pct, min_price, max_price, created = row
        
        # Parse source distribution
        source_dist = get_source_distribution(source_dist_str)
        memory_gb = None  # Variant data pending in canonical_trends
        msrp = get_msrp(family, memory_gb)
        markup_pct = calculate_markup_pct(avg_price, msrp)
        majority_source = get_majority_source(source_dist)
        has_strong_majority = has_strong_signal_majority(source_dist)
        
        # Market feed: baseline inclusion (confidence >= 0.5)
        memory_gb = None  # Parse from canonical_trends when added
        variant_str = None
        market_entry = {
            "feed": "market",
            "family": family,
            "memory_gb": memory_gb,
            "variant": variant_str,
            "signal": "availability",
            "price_range": {"min": min_price, "max": max_price},
            "avg_markup": f"{markup_pct:.1f}%" if markup_pct is not None else None,
            "source_distribution": source_dist,
            "confidence": avg_conf,
            "message": "Available across marketplace sources"
        }
        
        # RESTOCK FEED: strict inclusion rules
        # - confidence >= 0.75
        # - strong signal majority (>50%)
        # - price <= MSRP * 1.2
        # - source includes official/authorized majority
        restock_eligible = (
            avg_conf >= 0.75 and
            has_strong_majority and
            msrp and
            avg_price <= msrp * 1.2 and
            majority_source in AUTHORIZED_SOURCES
        )
        
        if restock_eligible:
            memory_gb = None  # Parse from canonical_trends when added
            variant_str = None
            restock_entry = {
                "feed": "restock",
                "family": family,
                "memory_gb": memory_gb,
                "variant": variant_str,
                "signal": "restock",
                "price": avg_price,
                "confidence": avg_conf,
                "source_distribution": source_dist,
                "markup_pct": f"{markup_pct:.1f}%" if markup_pct is not None else None,
                "message": "Official or near-MSRP stock available"
            }
            restock_feed.append(restock_entry)
            restock_families.append(family)
            logger.info(f"RESTOCK: {family} (conf={avg_conf}, markup={markup_pct:.1f}%)")
        else:
            # Fall through to market feed
            market_feed.append(market_entry)
            market_families.append(family)
            if avg_conf < 0.5:
                logger.debug(f"MARKET (low conf): {family}")
            elif not msrp:
                logger.debug(f"MARKET (no MSRP): {family}")
            else:
                logger.debug(f"MARKET (reseller/high markup): {family}")
    
    # Log feed summary
    logger.info(
        f"FEEDS: restock={len(restock_feed)} families={restock_families}, "
        f"market={len(market_feed)} families={market_families}"
    )
    
    return restock_feed, market_feed


def get_restock_feed():
    """Return only RESTOCK feed entries (for alert engine)."""
    restock, _ = route_canonical_trends()
    return restock


def get_market_feed():
    """Return only MARKET feed entries (for dashboards/API)."""
    _, market = route_canonical_trends()
    return market


if __name__ == "__main__":
    # Test run
    import sys
    sys.path.insert(0, ".")
    from db import init_schema
    
    logging.basicConfig(level=logging.INFO)
    init_schema()
    
    print("Testing routing layer...")
    restock, market = route_canonical_trends()
    
    print(f"\n=== RESTOCK FEED ({len(restock)} items) ===")
    for item in restock:
        print(f"  {item['family']}: ${item['price']} (conf={item['confidence']}) - {item['message']}")
    
    print(f"\n=== MARKET FEED ({len(market)} items) ===")
    for item in market:
        print(f"  {item['family']}: {item['price_range']} (markup={item['avg_markup']}) - {item['message']}")