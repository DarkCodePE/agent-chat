import logging
import time
from psycopg2 import connect, sql
from app.config.settings import (
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    POSTGRES_DB,
    DB_CONNECTION_RETRIES,
    DB_RETRY_DELAY
)

logger = logging.getLogger(__name__)


def create_database_if_not_exists():
    """
    Creates the database if it does not exist.
    Uses connection retries with exponential backoff for reliability.
    """
    retry_count = 0
    while retry_count < DB_CONNECTION_RETRIES:
        try:
            # Connect to PostgreSQL server without specifying database
            conn = connect(
                dbname="postgres",  # Connect to default postgres DB first
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
                host=POSTGRES_HOST,
                port=POSTGRES_PORT
            )
            conn.autocommit = True
            cursor = conn.cursor()

            # Check if database exists
            cursor.execute(sql.SQL("SELECT 1 FROM pg_database WHERE datname = %s"), (POSTGRES_DB,))
            exists = cursor.fetchone()

            if not exists:
                # Create database
                cursor.execute(sql.SQL("CREATE DATABASE {}").format(
                    sql.Identifier(POSTGRES_DB)
                ))
                logger.info(f"Database '{POSTGRES_DB}' created successfully.")
            else:
                logger.info(f"Database '{POSTGRES_DB}' already exists.")

            cursor.close()
            conn.close()
            return True

        except Exception as e:
            retry_count += 1
            delay = DB_RETRY_DELAY * (2 ** (retry_count - 1))  # Exponential backoff

            if retry_count < DB_CONNECTION_RETRIES:
                logger.warning(
                    f"Database connection attempt {retry_count} failed: {str(e)}. Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                logger.error(f"All database connection attempts failed: {str(e)}")
                raise RuntimeError(f"Could not connect to database after {DB_CONNECTION_RETRIES} attempts")


def init_db():
    """
    Initialize the database by creating all tables defined in models.
    """
    from app.database.base import Base
    from app.database.engine import get_engine

    try:
        # Ensure database exists
        create_database_if_not_exists()

        # Create all tables
        engine = get_engine()
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully")

    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise