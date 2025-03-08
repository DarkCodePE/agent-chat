import logging
import platform
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.store.postgres import PostgresStore
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.graph.state import State
from app.graph.nodes import retrieve_context, generate_response, summarize_conversation, classify_ambiguity, \
    ask_clarification, capture_important_info
from app.database.postgres import get_postgres_saver, get_postgres_store, get_async_postgres_saver
import os
from dotenv import load_dotenv
from typing import Optional

# Load environment variables
load_dotenv()
logger = logging.getLogger(__name__)


def should_summarize(state: State) -> str:
    """Decide si resumir o continuar."""
    return "summarize_conversation" if len(state["messages"]) > 6 else "generate_response"

def should_ambiguity(state: State) -> str:
    """Decide si resumir o continuar."""
    return "ask_clarification" if state["ambiguity_classification"]["is_ambiguous"] else "generate_response"

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
        workflow.add_node("capture_important_info", capture_important_info)
        workflow.add_node("classify_ambiguity", classify_ambiguity)
        workflow.add_node("ask_clarification", ask_clarification)
        workflow.add_node("generate_response", generate_response)
        workflow.add_node("summarize_conversation", summarize_conversation)

        # Define the flow
        # Fan-out: START va directamente a ambos nodos en paralelo
        workflow.add_edge(START, "retrieve_context")
        workflow.add_edge(START, "capture_important_info")
        # Fan-in: Ambos nodos alimentan a classify_ambiguity
        workflow.add_edge(["retrieve_context", "capture_important_info"], "classify_ambiguity")
        # Después de clasificar, decidir si pedir clarificación o generar respuesta
        workflow.add_conditional_edges(
            "classify_ambiguity",
            should_ambiguity,
            {"ask_clarification": "ask_clarification", "generate_response": "generate_response"}
        )
        # Terminar después de pedir clarificación (esperar respuesta del usuario)
        workflow.add_edge("ask_clarification", END)
        # Decidir si resumir después de generar respuesta
        workflow.add_conditional_edges(
            "generate_response",
            should_summarize,
            {"summarize_conversation": "summarize_conversation", "generate_response": END}
        )
        # Terminar después de resumir
        workflow.add_edge("summarize_conversation", END)

        store = get_postgres_store()
        checkpointer = get_postgres_saver()
        # Compile the graph with the checkpointer
        compiled_graph = workflow.compile(checkpointer=checkpointer, store=store)

        logger.info("Chat graph compiled successfully")
        return compiled_graph

    except Exception as e:
        print(f"Error creating chat graph: {str(e)}")
        logger.error(f"Error creating chat graph: {str(e)}")
        raise
