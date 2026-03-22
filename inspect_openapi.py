import json
import os
import requests
from pprint import pprint

BASE_URL = os.environ.get("TRIPLETEX_BASE_URL", "https://kkpqfuj-amager.tripletex.dev/v2")
SESSION_TOKEN = os.environ["TRIPLETEX_SESSION_TOKEN"]

auth = ("0", SESSION_TOKEN)

resp = requests.get(f"{BASE_URL}/openapi.json", auth=auth, timeout=30)
resp.raise_for_status()
spec = resp.json()

print("=== /product path ===")
pprint(spec["paths"].get("/product"))

print("\n=== Schemas containing 'product' in the name ===")
for name, schema in spec.get("components", {}).get("schemas", {}).items():
    if "product" in name.lower():
        print(f"\n--- {name} ---")
        print(json.dumps(schema, indent=2, ensure_ascii=False)[:8000])

    
