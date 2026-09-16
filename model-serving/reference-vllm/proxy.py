import os
import time
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

VLLM_PORT = os.getenv("VLLM_INTERNAL_PORT", "9000")
VLLM_BASE_URL = f"http://127.0.0.1:{VLLM_PORT}"

app = FastAPI(title="Tempo Scan LLM API", version="1.0.0")

@app.get("/")
def root():
    return {"service": "Tempo Scan LLM", "status": "running", "backend": "vLLM"}

@app.get("/health")
def health():
    try:
        start = time.time()
        r = requests.get(f"{VLLM_BASE_URL}/health", timeout=5)
        return {
            "status": "ok" if r.status_code == 200 else "degraded",
            "vllm_status": r.status_code,
            "latency_seconds": round(time.time() - start, 3),
        }
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "error", "detail": str(e)})

@app.get("/v1/models")
def get_models():
    try:
        r = requests.get(f"{VLLM_BASE_URL}/v1/models", timeout=30)
        return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type", "application/json"))
    except Exception as e:
        return JSONResponse(status_code=503, content={"error": {"message": "vLLM backend unavailable", "detail": str(e)}})

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
        r = requests.post(
            f"{VLLM_BASE_URL}/v1/chat/completions",
            json=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=300,
        )
        return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type", "application/json"))
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": {"message": str(e), "type": "proxy_error"}})

@app.post("/v1/completions")
async def completions(request: Request):
    body = await request.json()
    r = requests.post(f"{VLLM_BASE_URL}/v1/completions", json=body, headers={"Content-Type": "application/json"}, timeout=300)
    return Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type", "application/json"))
