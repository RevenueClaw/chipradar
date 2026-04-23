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
