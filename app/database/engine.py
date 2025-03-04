import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import QueuePool

from app.config.settings import (
    postgresql_connection_string,
    postgresql_async_connection_string,
    DB_POOL_SIZE,
    DB_MAX_OVERFLOW,
    DB_POOL_TIMEOUT,
    DB_POOL_RECYCLE
)

logger = logging.getLogger(__name__)

# Global engine instances
_sync_engine = None
_async_engine = None


def get_engine():
    """
    Get or create the SQLAlchemy engine for synchronous operations.
    Uses a singleton pattern to ensure only one engine exists.
    """
    global _sync_engine

    if _sync_engine is None:
        logger.info("Creating SQLAlchemy sync engine")
        _sync_engine = create_engine(
            postgresql_connection_string,
            poolclass=QueuePool,
            pool_size=DB_POOL_SIZE,
            max_overflow=DB_MAX_OVERFLOW,
            pool_timeout=DB_POOL_TIMEOUT,
            pool_recycle=DB_POOL_RECYCLE,
            pool_pre_ping=True  # Verify connection is still alive before using
        )

    return _sync_engine


def get_async_engine():
    """
    Get or create the SQLAlchemy engine for asynchronous operations.
    Uses a singleton pattern to ensure only one engine exists.
    """
    global _async_engine

    if _async_engine is None:
        logger.info("Creating SQLAlchemy async engine")
        _async_engine = create_async_engine(
            postgresql_async_connection_string,
            pool_size=DB_POOL_SIZE,
            max_overflow=DB_MAX_OVERFLOW,
            pool_timeout=DB_POOL_TIMEOUT,
            pool_recycle=DB_POOL_RECYCLE,
            pool_pre_ping=True  # Verify connection is still alive before using
        )

    return _async_engine


# Create session factories
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=get_engine()
)

AsyncSessionLocal = sessionmaker(
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    bind=get_async_engine()
)


def get_db():
    """
    Dependency for getting a database session.
    Yields a session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db():
    """
    Dependency for getting an async database session.
    Yields a session and ensures it's closed after use.
    """
    async with AsyncSessionLocal() as session:
        yield session


def close_connections():
    """Close all database connections on application shutdown."""
    _sync_engine = get_engine()
    _async_engine = get_async_engine()
    if _sync_engine:
        _sync_engine.dispose()
        logger.info("Synchronous database connections closed")

        # Para el motor asíncrono, no podemos usar await directamente aquí
        # ya que esta función no es asíncrona
    if _async_engine:
        # Programamos la tarea para que se ejecute
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(_async_engine.dispose())
            else:
                # Si no hay un bucle en ejecución, creamos uno temporal
                asyncio.run(_async_engine.dispose())
        except Exception as e:
            logger.error(f"Error closing async engine: {str(e)}")

        logger.info("Asynchronous database connections scheduled for closure")

        # Reseteamos las referencias
    _sync_engine = None
    _async_engine = None