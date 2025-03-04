import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException

from pydantic import BaseModel, Field

from app.services.chat_service import process_message, get_chat_history

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)

logger = logging.getLogger(__name__)


# Pydantic models for request/response validation
class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's message")
    thread_id: str = Field(..., description="Unique identifier for the conversation thread")
    reset_thread: bool = Field(False, description="Whether to reset the thread and start a new conversation")


class ChatResponse(BaseModel):
    thread_id: str = Field(..., description="The thread ID")
    message: str = Field(..., description="The original user message")
    answer: str = Field(..., description="The assistant's response")
    error: Optional[str] = Field(None, description="Error message if an error occurred")


class ChatHistoryItem(BaseModel):
    role: str = Field(..., description="The role of the message sender (human or ai)")
    content: str = Field(..., description="The content of the message")


class ChatHistoryResponse(BaseModel):
    thread_id: str = Field(..., description="The thread ID")
    messages: List[ChatHistoryItem] = Field(default_factory=list, description="List of messages in the conversation")


@router.post("/message", response_model=ChatResponse)
async def chat_message(request: ChatRequest) -> Dict[str, Any]:
    """
    Send a message to the chat assistant and get a response.

    Args:
        request: The chat request containing the message and thread ID

    Returns:
        The chat response with the assistant's answer
    """
    try:
        logger.info(f"Processing chat message for thread: {request.thread_id}")
        result = process_message(
            message=request.message,
            thread_id=request.thread_id,
            reset_thread=request.reset_thread
        )

        return result

    except Exception as e:
        print(e)
        logger.error(f"Error in chat_message endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{thread_id}", response_model=ChatHistoryResponse)
async def chat_history(thread_id: str) -> Dict[str, Any]:
    """
    Get the chat history for a specific thread.

    Args:
        thread_id: The thread ID to retrieve history for

    Returns:
        The chat history response with messages
    """
    try:
        logger.info(f"Retrieving chat history for thread: {thread_id}")
        history = await get_chat_history(thread_id)

        # Convert to the response format
        history_items = [
            ChatHistoryItem(role=item["role"], content=item["content"])
            for item in history
        ]

        return {
            "thread_id": thread_id,
            "messages": history_items
        }

    except Exception as e:
        logger.error(f"Error in chat_history endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

