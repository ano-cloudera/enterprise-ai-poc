import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.core.schemas import ChatRequest, ChatResponse
from app.services.chat import run_chat, run_chat_stream

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await run_chat(request)


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Server-Sent Events version of /chat: emits {"type": "progress", ...}
    frames while the answer is being worked on, then one
    {"type": "done", "response": ChatResponse} frame. See
    app/services/chat.py's run_chat_stream() and AskAIPage.tsx's consumer.
    """
    async def event_source():
        async for item in run_chat_stream(request):
            if item["type"] == "done":
                payload = {"type": "done", "response": item["response"].model_dump()}
            else:
                payload = item
            yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")
