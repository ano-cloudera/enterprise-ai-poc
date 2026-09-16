import os
import time
import requests

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response


# =========================================================
# Configuration
# =========================================================

VLLM_PORT = os.getenv(
    "VLLM_INTERNAL_PORT",
    "9000"
)

VLLM_BASE_URL = (
    f"http://127.0.0.1:{VLLM_PORT}"
)


# =========================================================
# Application
# =========================================================

app = FastAPI(
    title="Tempo Scan LLM API",
    description=(
        "Cloudera AI proxy for vLLM "
        "OpenAI-compatible API"
    ),
    version="1.0.0"
)


# =========================================================
# Root
# =========================================================

@app.get("/")
def root():

    return {
        "service": "Tempo Scan LLM",
        "status": "running",
        "backend": "vLLM",
        "backend_url": VLLM_BASE_URL
    }


# =========================================================
# Health
# =========================================================

@app.get("/health")
def health():

    try:

        start = time.time()

        response = requests.get(
            f"{VLLM_BASE_URL}/health",
            timeout=5
        )

        latency = round(
            time.time() - start,
            3
        )


        if response.status_code == 200:

            return {
                "status": "ok",
                "backend": "vLLM",
                "vllm_status": 200,
                "latency_seconds": latency
            }


        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "backend": "vLLM",
                "vllm_status": response.status_code,
                "response": response.text[:500]
            }
        )


    except Exception as e:

        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "backend": "vLLM",
                "detail": str(e)
            }
        )


# =========================================================
# Models
# =========================================================

@app.get("/v1/models")
def get_models():

    try:

        response = requests.get(
            f"{VLLM_BASE_URL}/v1/models",
            timeout=30
        )


        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type=(
                response.headers.get(
                    "content-type",
                    "application/json"
                )
            )
        )


    except Exception as e:

        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "message": (
                        "vLLM backend unavailable"
                    ),
                    "type": "backend_unavailable",
                    "detail": str(e)
                }
            }
        )


# =========================================================
# Chat Completions
# =========================================================

@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request
):

    try:

        body = await request.json()


        print(
            "Chat completion request:",
            body.get("model")
        )


        response = requests.post(
            (
                f"{VLLM_BASE_URL}"
                "/v1/chat/completions"
            ),
            json=body,
            headers={
                "Content-Type":
                "application/json",

                "Accept":
                "application/json"
            },
            timeout=300
        )


        print(
            "vLLM response status:",
            response.status_code
        )


        if response.status_code != 200:

            print(
                "vLLM response:",
                response.text[:2000]
            )


        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type=(
                response.headers.get(
                    "content-type",
                    "application/json"
                )
            )
        )


    except Exception as e:

        print(
            "Chat proxy error:",
            str(e)
        )


        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": str(e),
                    "type": "proxy_error"
                }
            }
        )


# =========================================================
# Optional Completion Endpoint
# =========================================================

@app.post("/v1/completions")
async def completions(
    request: Request
):

    try:

        body = await request.json()


        response = requests.post(
            (
                f"{VLLM_BASE_URL}"
                "/v1/completions"
            ),
            json=body,
            headers={
                "Content-Type":
                "application/json"
            },
            timeout=300
        )


        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type=(
                response.headers.get(
                    "content-type",
                    "application/json"
                )
            )
        )


    except Exception as e:

        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": str(e),
                    "type": "proxy_error"
                }
            }
        )