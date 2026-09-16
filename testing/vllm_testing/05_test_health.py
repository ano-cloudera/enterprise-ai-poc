import os
import requests

BASE_URL = os.getenv("VLLM_BASE_URL", "http://127.0.0.1:8000")

for endpoint in ["/health", "/v1/models"]:
    url = BASE_URL + endpoint
    try:
        r = requests.get(url, timeout=15)
        print(f"{url} -> HTTP {r.status_code}")
        print(r.text[:2000])
        print()
    except Exception as exc:
        print(f"{url} -> ERROR: {exc}")
