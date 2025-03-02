import logging
from typing import Dict, Any, List, Optional

from langchain_core.messages import HumanMessage, AIMessage

from app.database.postgres import get_postgres_saver
from app.graph.chat_graph import create_chat_graph

logger = logging.getLogger(__name__)


async def process_message(
        message: str,
        thread_id: str,
        reset_thread: bool = False
) -> Dict[str, Any]:
    """
    Process a chat message using the LangGraph workflow.

    Args:
        message: The user's message
        thread_id: A unique identifier for this conversation thread
        reset_thread: Whether to reset the thread and start a new conversation

    Returns:
        dict: The result containing the answer and updated state
    """
    try:
        # Create the chat graph
        graph = create_chat_graph()

        # Set up configuration with the thread_id
        # This is what allows persistence across messages
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }

        # Prepare the initial state
        # The actual state may be loaded from the database if it exists
        initial_state = {
            "input": message,
            "chat_history": [],
            "context": "",
            "answer": "",
            "documents": [],
            "web_search": "No",
        }

        # Invoke the graph with the initial state and configuration
        logger.info(f"Processing message in thread {thread_id}")
        result = graph.invoke(initial_state, config)
        logger.info(f"Final state: {result}")
        return {
            "thread_id": thread_id,
            "message": message,
            "answer": result["answer"],
        }

    except Exception as e:
        print(f"Error processing message: {str(e)}")
        logger.error(f"Error processing message: {str(e)}")
        raise e


async def get_chat_history(thread_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve the chat history for a given thread.

    Args:
        thread_id: The thread ID

    Returns:
        List of message objects with role and content
    """
    try:
        # Get the checkpointer directly instead of creating a new graph
        checkpointer = get_postgres_saver()

        # Create a configuration to retrieve the state
        config = {"configurable": {"thread_id": thread_id}}

        # Get the state
        state = checkpointer.get(config)

        # Extract chat history from the channel_values
        chat_history = state.get("channel_values", {}).get("chat_history", [])

        if not chat_history:
            logger.info(f"Empty chat history for thread {thread_id}")
            return []

        # Format into a more user-friendly structure
        formatted_history = []

        # Process each message in the chat history
        for message in chat_history:
            # Skip any items that don't have the expected structure
            if not hasattr(message, 'content'):
                continue

            if isinstance(message, HumanMessage):
                formatted_history.append({
                    "role": "human",
                    "content": message.content
                })
            elif isinstance(message, AIMessage):
                formatted_history.append({
                    "role": "ai",
                    "content": message.content
                })
            elif hasattr(message, 'type') and message.type in ["human", "ai"]:
                formatted_history.append({
                    "role": message.type,
                    "content": message.content
                })
            elif hasattr(message, '__class__') and hasattr(message.__class__, '__name__'):
                # Fallback: Determine the role based on message class name
                role = "human" if "Human" in message.__class__.__name__ else "ai"
                formatted_history.append({
                    "role": role,
                    "content": message.content
                })

        logger.info(f"Retrieved {len(formatted_history)} messages for thread {thread_id}")
        return formatted_history

    except Exception as e:
        logger.error(f"Error retrieving chat history: {str(e)}")
        return []