import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.schemas import ChatRequest, ChatResponse
from app.services.chat import run_chat, run_chat_stream

router = APIRouter(tags=["chat"])

# CAI's own reverse proxy (a Go/gin component, not this app) has been
# observed to abort an SSE connection with "net/http: abort Handler" when
# no bytes flow for a while — the agent_studio backend's polling loop
# (asyncio.sleep(AGENT_STUDIO_POLL_INTERVAL_SECONDS) between Agent Studio
# event checks) can easily go quiet that long between progress messages.
# Emitting a blank SSE comment line (never seen by the frontend's parser,
# which only reads "data: " lines) on this cadence keeps bytes flowing
# without changing what api.chatStream() actually receives as progress.
_HEARTBEAT_INTERVAL_SECONDS = 15


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await run_chat(request)


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Server-Sent Events version of /chat: emits {"type": "progress", ...}
    frames while the answer is being worked on, then one
    {"type": "done", "response": ChatResponse} frame, with blank
    keep-alive comment lines in between to stop CAI's proxy from treating
    a quiet-but-still-working connection as dead. See
    app/services/chat.py's run_chat_stream() and AskAIPage.tsx's consumer.
    """
    async def event_source():
        stream = run_chat_stream(request)
        pending = asyncio.ensure_future(stream.__anext__())
        try:
            while True:
                try:
                    item = await asyncio.wait_for(asyncio.shield(pending), timeout=_HEARTBEAT_INTERVAL_SECONDS)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                except StopAsyncIteration:
                    return

                if item["type"] == "done":
                    payload = {"type": "done", "response": item["response"].model_dump()}
                else:
                    payload = item
                yield f"data: {json.dumps(payload)}\n\n"
                pending = asyncio.ensure_future(stream.__anext__())
        finally:
            pending.cancel()

    return StreamingResponse(event_source(), media_type="text/event-stream")
