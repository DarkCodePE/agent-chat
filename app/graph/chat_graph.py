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
from app.graph.nodes import retrieve_context, generate_response
from app.database.postgres import get_postgres_saver, get_postgres_store
import os
from dotenv import load_dotenv
from typing import Optional

# Load environment variables
load_dotenv()
logger = logging.getLogger(__name__)
# logger = logging.getLogger(__name__)
#
# # PostgreSQL settings
# POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
# POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
# POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
# POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "123456")
# POSTGRES_DB = os.getenv("POSTGRES_DB", "chat_rag")
#
# # Connection pool settings
# DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
# DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
# DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
# DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))  # 30 minutes
# DB_CONNECTION_RETRIES = int(os.getenv("DB_CONNECTION_RETRIES", "5"))
# DB_RETRY_DELAY = int(os.getenv("DB_RETRY_DELAY", "5"))  # seconds
#
# # URL de la base de datos
# SQLALCHEMY_DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
# #print(SQLALCHEMY_DATABASE_URL)
# # Configuración del engine y creación de la sesión
# engine = create_engine(
#     SQLALCHEMY_DATABASE_URL,
#     pool_size=DB_POOL_SIZE,
#     max_overflow=DB_MAX_OVERFLOW,
#     pool_timeout=DB_POOL_TIMEOUT,
#     pool_pre_ping=True  # Opcional: ayuda a mantener las conexiones activas
# )
#
# SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
#
# # Configurar el pool y PostgresSaver
# connection_kwargs = {
#     "autocommit": True,
#     "prepare_threshold": 0,
#     "row_factory": dict_row
# }
#
# pool = ConnectionPool(
#     conninfo=SQLALCHEMY_DATABASE_URL,
#     max_size=10,
#     kwargs=connection_kwargs,
# )
#
# checkpointer = PostgresSaver(pool)
# checkpointer.setup()
# # Inicializar PostgresStore con el mismo pool
# store = PostgresStore(pool)


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

        # Define the flow
        workflow.add_edge(START, "retrieve_context")
        workflow.add_edge("retrieve_context", "generate_response")
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
