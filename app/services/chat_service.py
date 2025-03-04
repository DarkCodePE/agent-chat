import logging
from typing import Dict, Any, List, Optional
import traceback
from langchain_core.messages import HumanMessage, AIMessage

from app.database.postgres import get_postgres_saver, get_async_postgres_saver
from app.graph.chat_graph import create_chat_graph

logger = logging.getLogger(__name__)


def process_message(
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
        logger.info(f"Creating chat graph for thread {thread_id}")
        graph = create_chat_graph()
        logger.info(f"Chat graph created successfully for thread {thread_id}")

        # Set up configuration with the thread_id
        config = {
            "configurable": {
                "thread_id": thread_id,
                "reset_thread": reset_thread
            }
        }
        logger.info(f"Configuration set for thread {thread_id}: {config}")

        # Prepare the initial state
        initial_state = {
            "input": message,
            "chat_history": [],
            "context": "",
            "answer": "",
            "documents": [],
            "web_search": "No",
            "summary": ""  # Make sure all expected state fields are initialized
        }
        logger.info(f"Initial state prepared for thread {thread_id}")

        # Use ainvoke instead of invoke since retrieve_context is async
        logger.info(f"Invoking graph for thread {thread_id}")
        try:
            result = graph.invoke(initial_state, config)
            logger.info(f"Graph execution completed for thread {thread_id}")
        except Exception as graph_error:
            logger.error(f"Error during graph execution: {str(graph_error)}")
            logger.error(f"Graph execution traceback: {traceback.format_exc()}")
            raise graph_error

        logger.info(f"Final state keys: {result.keys()}")
        return {
            "thread_id": thread_id,
            "message": message,
            "answer": result.get("answer", "I encountered an error generating a response.")
        }

    except Exception as e:
        error_detail = str(e) if str(e) else "Unknown error (empty exception message)"
        stack_trace = traceback.format_exc()
        logger.error(f"Error processing message: {error_detail}")
        logger.error(f"Stack trace: {stack_trace}")
        return {
            "thread_id": thread_id,
            "message": message,
            "answer": f"I'm sorry, I encountered an error. Technical details: {error_detail}",
            "error": error_detail
        }


async def get_chat_history(thread_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve the chat history for a given thread.

    Args:
        thread_id: The thread ID

    Returns:
        List of message objects with role and content
    """
    try:
        # Create the chat graph to access its API
        logger.info(f"Creating chat graph for thread {thread_id}")
        graph = await create_chat_graph()

        # Create a configuration for the thread
        config = {"configurable": {"thread_id": thread_id}}

        # Check if the graph has state for this thread
        if not graph.exists(config):
            logger.info(f"No state exists for thread {thread_id}")
            return []

        # Use graph.get_state() to retrieve the state properly
        try:
            state_snapshot = graph.get_state(config)
            logger.info(f"Retrieved state snapshot for thread {thread_id}")
        except Exception as e:
            logger.error(f"Error retrieving state from graph: {str(e)}")
            logger.error(traceback.format_exc())
            return []

        # Extract chat history from the values
        chat_history = state_snapshot.values.get("chat_history", [])

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
        stack_trace = traceback.format_exc()
        logger.error(f"Error retrieving chat history: {str(e)}")
        logger.error(f"Stack trace: {stack_trace}")
        return []
