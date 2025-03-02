import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import chat
from app.config.settings import API_HOST, API_PORT, API_WORKERS, LOG_LEVEL
from app.database.postgres import check_postgres_connection, close_postgres_connections
from app.database.engine import close_connections
from app.database.init_db import init_db

# Setup logging
logging_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(
    level=logging_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="LangGraph Chatbot API",
    description="API for LangGraph-powered chatbot with PostgreSQL persistence",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router)


@app.get("/health")
def health_check():
    """
    Health check endpoint for monitoring

    Returns:
        dict: Status information about the application and database
    """
    # Check database connection
    db_status = "healthy" if check_postgres_connection() else "unhealthy"

    return {
        "status": "healthy",
        "database": db_status,
        "version": "1.0.0"
    }


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        # Initialize database
        logger.info("Initializing database...")
        init_db()

        # Check database connection
        if check_postgres_connection():
            logger.info("PostgreSQL connection successful")
        else:
            logger.error("PostgreSQL connection failed")

    except Exception as e:
        logger.error(f"Error initializing services: {str(e)}")
        # We don't want to crash the app if services fail to initialize
        # This allows the health check to report unhealthy status


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    logger.info("Application shutting down")

    # Close PostgreSQL connections
    close_postgres_connections()

    # Close SQLAlchemy connections
    close_connections()


if __name__ == "__main__":
    logger.info(f"Starting server on {API_HOST}:{API_PORT} with {API_WORKERS} workers")
    uvicorn.run(
        "app.main:app",
        host=API_HOST,
        port=API_PORT,
        workers=API_WORKERS,
        reload=True  # Enable auto-reload during development
    )
