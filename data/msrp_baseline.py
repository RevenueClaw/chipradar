import logging
import re

logger = logging.getLogger(__name__)

MSRP_BASELINE = {
    "Raspberry Pi 5": {
        2: 50,
        4: 60,
        8: 80,
        16: 120
    },
    "Raspberry Pi 4": {
        2: 45,
        4: 55,
        8: 75,
        3: 60
    },
    "Rock 5B": {
        4: 120,
        8: 150,
        16: 200,
        32: 300
    },
    "Orange Pi 5": {
        4: 85,
        8: 110,
        16: 150,
        32: 220
    },
    "Jetson Orin Nano": {
        4: 149,
        8: 199
    }
}

def get_msrp(family, memory_gb):
    if family not in MSRP_BASELINE:
        logger.warning(f"UNKNOWN_FAMILY: {family}")
        return None
    family_msrps = MSRP_BASELINE[family]
    if memory_gb not in family_msrps:
        logger.warning(f"UNKNOWN_VARIANT: {family} {memory_gb}GB")
        return None
    return family_msrps[memory_gb]

def parse_memory_gb(variant_or_name):
    match = re.search(r'(\\d+)[\\s-]*GB', variant_or_name, re.I)
    return int(match.group(1)) if match else None

def compute_deal_score(price, msrp, confidence):
    if msrp is None:
        return "unknown", 0
    delta_pct = (price - msrp) / msrp
    if delta_pct <= -0.10:
        return "excellent", 5
    elif delta_pct <= 0:
        return "great", 4
    elif delta_pct <= 0.20:
        return "fair", 3
    elif delta_pct <= 0.50:
        return "overpriced", 2
    else:
        return "bad", 1

def get_deal_emoji(rating):
    emojis = {
        "excellent": "🟢",
        "great": "🟢",
        "fair": "🟡",
        "overpriced": "🟠",
        "bad": "🔴",
        "unknown": "❓"
    }
    return emojis.get(rating, "❓")


def compute_expectation(delta):
    if delta < -0.20:
        return "very_unlikely"
    elif delta < 0:
        return "unlikely"
    elif delta <= 0.20:
        return "realistic"
    else:
        return "high_probability"

def get_expectation_msg(delta):
    expectation = compute_expectation(delta)
    msgs = {
        "very_unlikely": "⚠️ Extremely unlikely target. Most listings stay above MSRP.",
        "unlikely": "⚠️ Below MSRP — rare, but possible during dips.",
        "realistic": "✅ Good target — likely to trigger.",
        "high_probability": "✅ High probability — expect alerts soon."
    }
    return msgs.get(expectation, "")
