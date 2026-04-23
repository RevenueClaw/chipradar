import yaml
import sys

def load_config(file_path):
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        sys.exit(1)

products = load_config('config/products.yaml')
sources = load_config('config/sources.yaml')

print("✅ Products loaded:")
for pid, info in products['products'].items():
    print(f"  - {pid}: {info['name']}")

print("\n✅ Sources loaded:")
for src in sources['sources']:
    print(f"  - {src['name']}: {src['url']}")

print("\n✅ Telegram config loaded:")
tg = sources['telegram']
print(f"  Bot token: {tg['bot_token'][:10]}...")
print(f"  Chat ID: {tg['chat_id']}")

print("\nPHASE 2 COMPLETE")
