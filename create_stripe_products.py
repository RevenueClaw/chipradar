#!/usr/bin/env python3
import stripe
import os
import json

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Create Products
basic_product = stripe.Product.create(name='ChipRadar Basic - RESTOCK Alerts')
pro_product = stripe.Product.create(name='ChipRadar Pro - MARKET Intelligence')
instant_product = stripe.Product.create(name='ChipRadar Instant - BUYER Optimizer')

# Create Prices (NO trial_period_days here - set in Checkout Session)
basic_price = stripe.Price.create(
  product=basic_product.id,
  unit_amount=700,  # $7.00 USD
  currency='usd',
  recurring={'interval': 'month'}
)
pro_price = stripe.Price.create(
  product=pro_product.id,
  unit_amount=1900,  # $19.00 USD
  currency='usd',
  recurring={'interval': 'month'}
)
instant_price = stripe.Price.create(
  product=instant_product.id,
  unit_amount=1200,  # $12.00 USD
  currency='usd',
  recurring={'interval': 'month'}
)

# Save IDs
prices = {
  'basic_price_id': basic_price.id,
  'pro_price_id': pro_price.id,
  'instant_price_id': instant_price.id,
  'basic_product_id': basic_product.id,
  'pro_product_id': pro_product.id,
  'instant_product_id': instant_product.id
}

with open('config/stripe_prices.json', 'w') as f:
  json.dump(prices, f, indent=2)

print('SUCCESS: Products/Prices Created!')
print(json.dumps(prices, indent=2))
print('\\nNext: Get pk_live from Stripe dashboard (Developers > API keys > Publishable key).')
print('Update stripe_handler.py with price_ids from above.')
print('Run ngrok for webhook testing.')
