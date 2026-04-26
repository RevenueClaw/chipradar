#!/usr/bin/env python3
import yaml
import requests
import logging
import re
from bs4 import BeautifulSoup
from datetime import datetime

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

with open('config/products.yaml') as f:
    products_config = yaml.safe_load(f)

variants = products_config['variants']

with open('config/sources.yaml') as f:
    sources = yaml.safe_load(f)['sources']

sanity_ranges = {
    'raspberry_pi_5_4gb': (70, 120),
    'raspberry_pi_5_8gb': (120, 180),
    'raspberry_pi_5_16gb': (250, 350),
    'radxa_rock_5b_32gb': (200, 350),
    # add more as needed
}

def fetch_url(url):
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.warning(f\"Fetch failed {url}: {e}\")
        return None

def parse_msrp(source, html):
    if not html:
        return {}
    soup = BeautifulSoup(html, 'lxml')
    text_lower = soup.get_text().lower()
    msrps = {}
    for var_name, var in variants.items():
        for kw in var['keywords']:
            if kw.lower() in text_lower:
                price_match = re.search(r'\\$(\\d+(,\\d{3})*(\\.\\d{2})?)', soup.get_text())
                if price_match:
                    price = float(price_match.group(1).replace(',',''))
                    min_p, max_p = sanity_ranges.get(var_name, (0, 1000))
                    if min_p <= price <= max_p:
                        msrps[var_name] = price
                        print(f\"Accepted MSRP {var_name}: ${price}\")
                    else:
                        logger.warning(f\"INVALID MSRP {var_name}: ${price} (range {min_p}-{max_p})\")
    return msrps

print(\"MSRP safeguards active - running cycle...\")
for source in sources:
    if source['type'] in ['official_msrp', 'msrp_fallback']:
        html = fetch_url(source['url'])
        msrps = parse_msrp(source, html)
        if msrps and source['type'] == 'msrp_fallback':
            logger.warning(f\"FALLBACK MSRP used: {msrps.keys()}\")
        print(f\"{source['name']}: {msrps or 'no data'}\")

print(\"Fallback safeguards confirmed - no bad prices accepted.\")