import os
import json
import httpx

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse


# =========================================================
# Configuration
# =========================================================

# Bumped whenever proxy.py changes in a way we need to verify actually
# reached the running container (e.g. after debugging a stale-process
# issue) -- check via GET /debug-version.
PROXY_BUILD_MARKER = "2026-09-22-normalize-v3"

VLLM_PORT = os.getenv(
    "VLLM_INTERNAL_PORT",
    "9000"
)

VLLM_BASE_URL = os.getenv(
    "VLLM_BASE_URL",
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
# Helpers
# =========================================================

def normalize_messages(messages):
    """
    Normalize messages for Qwen/vLLM compatibility.

    Agent Studio (via LiteLLM) can send more than one system/developer
    message, or a system message that isn't first in the array. Qwen's
    chat template rejects that with:
        "System message must be at the beginning."

    Rules:
    1. Merge all system messages.
    2. Treat developer messages as system instructions.
    3. Put exactly one system message at the beginning.
    4. Preserve order of all non-system messages.
    """

    if not messages:
        return messages

    system_parts = []
    non_system_messages = []

    for message in messages:

        role = message.get("role")
        content = message.get("content", "")

        if role in ("system", "developer"):

            if content:
                system_parts.append(content)

        else:

            non_system_messages.append(message)

    normalized = []

    if system_parts:

        normalized.append(
            {
                "role": "system",
                "content": "\n\n".join(system_parts)
            }
        )

    normalized.extend(non_system_messages)

    return normalized


def print_message_roles(label, messages):

    try:

        roles = [message.get("role") for message in messages]
        print(f"{label}: {roles}", flush=True)

    except Exception:

        pass


def safe_json_error(message, error_type="proxy_error", status_code=500):

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "message": str(message),
                "type": error_type
            }
        }
    )


# =========================================================
# Root
# =========================================================

@app.get("/")
async def root():

    return {
        "service": "Tempo Scan LLM",
        "status": "running",
        "backend": "vLLM",
        "backend_url": VLLM_BASE_URL,
        "build": PROXY_BUILD_MARKER
    }


# =========================================================
# Debug: confirm which proxy.py build is actually running
# =========================================================

@app.get("/debug-version")
async def debug_version():

    return {
        "build": PROXY_BUILD_MARKER,
        "file": __file__,
        "has_normalize_messages": "normalize_messages" in globals()
    }


# =========================================================
# Health
# =========================================================

@app.get("/health")
async def health():

    try:

        async with httpx.AsyncClient(timeout=10) as client:

            response = await client.get(f"{VLLM_BASE_URL}/v1/models")

        if response.status_code == 200:

            return {
                "status": "ok",
                "backend": "vLLM",
                "vllm_status": 200
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

        return safe_json_error(
            e,
            error_type="health_error",
            status_code=503
        )


# =========================================================
# Models
# =========================================================

@app.get("/v1/models")
async def get_models():

    try:

        async with httpx.AsyncClient(timeout=30) as client:

            response = await client.get(f"{VLLM_BASE_URL}/v1/models")

        content_type = response.headers.get("content-type", "")

        if "application/json" in content_type:

            return JSONResponse(
                status_code=response.status_code,
                content=response.json()
            )

        return JSONResponse(
            status_code=response.status_code,
            content={"raw_response": response.text}
        )

    except Exception as e:

        return safe_json_error(
            e,
            error_type="backend_unavailable"
        )


# =========================================================
# Chat Completions
# =========================================================

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):

    try:

        payload = await request.json()

    except Exception as e:

        return safe_json_error(
            f"Invalid JSON body: {e}",
            error_type="invalid_request",
            status_code=400
        )

    print("Chat completion request:", payload.get("model"))

    # =====================================================
    # Normalize Agent Studio / LiteLLM messages
    # =====================================================
    # Agent Studio can send system/developer messages out of order or
    # more than once; vLLM/Qwen rejects that outright, so fix it up here
    # before forwarding, rather than passing the request through as-is.

    raw_messages = payload.get("messages", [])

    print_message_roles("RAW MESSAGE ROLES", raw_messages)

    if raw_messages:

        payload["messages"] = normalize_messages(raw_messages)

    print_message_roles(
        "NORMALIZED MESSAGE ROLES",
        payload.get("messages", [])
    )

    stream = bool(payload.get("stream", False))

    # =====================================================
    # Streaming request
    # =====================================================

    if stream:

        async def stream_generator():

            try:

                async with httpx.AsyncClient(timeout=None) as client:

                    async with client.stream(
                        "POST",
                        f"{VLLM_BASE_URL}/v1/chat/completions",
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    ) as response:

                        async for chunk in response.aiter_raw():

                            yield chunk

            except Exception as e:

                error_payload = {
                    "error": {
                        "message": str(e),
                        "type": "stream_proxy_error"
                    }
                }

                yield json.dumps(error_payload).encode("utf-8")

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream"
        )

    # =====================================================
    # Non-streaming request
    # =====================================================

    try:

        async with httpx.AsyncClient(timeout=300) as client:

            response = await client.post(
                f"{VLLM_BASE_URL}/v1/chat/completions",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
            )

        print("vLLM response status:", response.status_code)

        if response.status_code != 200:

            print("vLLM response:", response.text[:2000])

        content_type = response.headers.get("content-type", "")

        if "application/json" in content_type:

            return JSONResponse(
                status_code=response.status_code,
                content=response.json()
            )

        return JSONResponse(
            status_code=response.status_code,
            content={"raw_response": response.text}
        )

    except Exception as e:

        print("Chat proxy error:", str(e))

        return safe_json_error(e)


# =========================================================
# Optional Completion Endpoint
# =========================================================

@app.post("/v1/completions")
async def completions(request: Request):

    try:

        payload = await request.json()

    except Exception as e:

        return safe_json_error(
            f"Invalid JSON body: {e}",
            error_type="invalid_request",
            status_code=400
        )

    stream = bool(payload.get("stream", False))

    if stream:

        async def stream_generator():

            try:

                async with httpx.AsyncClient(timeout=None) as client:

                    async with client.stream(
                        "POST",
                        f"{VLLM_BASE_URL}/v1/completions",
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    ) as response:

                        async for chunk in response.aiter_raw():

                            yield chunk

            except Exception as e:

                error_payload = {
                    "error": {
                        "message": str(e),
                        "type": "stream_proxy_error"
                    }
                }

                yield json.dumps(error_payload).encode("utf-8")

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream"
        )

    try:

        async with httpx.AsyncClient(timeout=300) as client:

            response = await client.post(
                f"{VLLM_BASE_URL}/v1/completions",
                json=payload,
                headers={"Content-Type": "application/json"}
            )

        content_type = response.headers.get("content-type", "")

        if "application/json" in content_type:

            return JSONResponse(
                status_code=response.status_code,
                content=response.json()
            )

        return JSONResponse(
            status_code=response.status_code,
            content={"raw_response": response.text}
        )

    except Exception as e:

        return safe_json_error(e)
