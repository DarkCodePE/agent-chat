import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.store.postgres import PostgresStore
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.graph.state import State
from app.graph.nodes import retrieve_context, generate_response, summarize_conversation
from app.database.postgres import get_postgres_saver, get_postgres_store
import os
from dotenv import load_dotenv
from typing import Optional

# Load environment variables
load_dotenv()
logger = logging.getLogger(__name__)

def should_summarize(state: State) -> str:
    """Decide si resumir o continuar."""
    return "summarize_conversation" if len(state["chat_history"]) > 6 else "generate_response"


def create_chat_graph():
    """
    Create and compile the chat graph with the node functions.

    Returns:
        The compiled graph ready to be invoked
    """
    try:
        # Create the graph with our State type
        workflow = StateGraph(State)

        # Add the nodes
        workflow.add_node("retrieve_context", retrieve_context)
        workflow.add_node("generate_response", generate_response)
        workflow.add_node("summarize_conversation", summarize_conversation)

        # Define the flow
        workflow.add_edge(START, "retrieve_context")
        workflow.add_conditional_edges("retrieve_context", should_summarize)
        workflow.add_edge("summarize_conversation", "generate_response")
        workflow.add_edge("generate_response", END)

        # Get the PostgreSQL saver for persistence
        checkpointer = get_postgres_saver()

        # Get the PostgreSQL store for cross-thread state
        store = get_postgres_store()
        #checkpointer = MemorySaver()
        # Compile the graph with the checkpointer
        compiled_graph = workflow.compile(checkpointer=checkpointer, store=store)

        logger.info("Chat graph compiled successfully")
        return compiled_graph

    except Exception as e:
        print(f"Error creating chat graph: {str(e)}")
        logger.error(f"Error creating chat graph: {str(e)}")
        raise
