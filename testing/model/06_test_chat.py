import os
import requests

BASE_URL = os.getenv("VLLM_BASE_URL", "http://127.0.0.1:8001")
MODEL_NAME = os.getenv(
    "MODEL_NAME",
    "/home/cdsw/models/Qwen3.8-27B-AWQ"
)

payload = {
    "model": MODEL_NAME,
    "messages": [
        {
            "role": "user",
            "content": "Jelaskan dalam 3 poin singkat bagaimana AI membantu analisis sales."
        }
    ],
    "temperature": 0.2,
    "max_tokens": 256
}

url = f"{BASE_URL}/v1/chat/completions"

response = requests.post(
    url,
    headers={"Content-Type": "application/json"},
    json=payload,
    timeout=120
)

print("HTTP Status:", response.status_code)
print("Content-Type:", response.headers.get("content-type"))
print("Raw Response:")
print(response.text[:3000])