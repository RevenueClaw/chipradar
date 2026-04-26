#!/usr/bin/env python3
def score_variant(p):
    score = 0
    if p.get('stock') == 'in stock': score += 6
    if p.get('high_memory'): score += 3
    if p.get('ram_gb', 0) >= 32: score += 2
    return score

products = [
    {'variant_full_name': 'Radxa ROCK 5B 32GB', 'ram_gb': 32, 'high_memory': True, 'price': '229', 'stock': 'in stock', 'url': 'https://radxa.com', 'source': 'Radxa Store'},
    {'variant_full_name': 'Raspberry Pi 5 16GB', 'ram_gb': 16, 'high_memory': True, 'price': '269', 'stock': 'in stock', 'url': 'https://thepihut.com', 'source': 'The Pi Hut'},
    {'variant_full_name': 'Orange Pi 5 Plus 32GB', 'ram_gb': 32, 'high_memory': True, 'price': '289', 'stock': 'in stock', 'url': 'https://orangepi.net', 'source': 'Orange Pi Official'}
]

high_opp = [p for p in products if score_variant(p) >= 11]

print(\"Clean live-price-only alerts:\")
for p in high_opp:
    print(f\"\"\"🚨 {p['variant_full_name']} in stock!
Price: ${p['price']}
At: {p['source']}
{p['url']}---\"\"\")
print(\"\\nInternal scores:\", [score_variant(p) for p in high_opp])