from fastapi import APIRouter

from app.core.schemas import ChatRequest, ChatResponse
from app.services.chat import run_chat

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await run_chat(request)
