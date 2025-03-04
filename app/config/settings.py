import os
from dotenv import load_dotenv
from typing import Optional

# Load environment variables
load_dotenv()

# PostgreSQL settings
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "123456")
POSTGRES_DB = os.getenv("POSTGRES_DB", "chat_rag")

# Connection pool settings
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))  # 30 minutes
DB_CONNECTION_RETRIES = int(os.getenv("DB_CONNECTION_RETRIES", "5"))
DB_RETRY_DELAY = int(os.getenv("DB_RETRY_DELAY", "5"))  # seconds

# API settings
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "9025"))
API_WORKERS = int(os.getenv("API_WORKERS", "2"))

# LLM settings
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

#VECTOR STORE
QDRANT_URL = os.getenv("QDRANT_URL", "https://your-qdrant-url")  # Reemplázalo con tu URL real
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")  # Asegúrate de que esté en tu .env

# Google Drive settings
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

# Logging settings
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


# Build connection strings
def get_sync_connection_string() -> str:
    """Build the PostgreSQL connection string for synchronous connections."""
    return f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

def get_async_connection_string() -> str:
    """Build the PostgreSQL connection string for asynchronous connections."""
    return f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# Connection strings as properties
postgresql_connection_string = get_sync_connection_string()
postgresql_async_connection_string = get_async_connection_string()