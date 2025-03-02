from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, DateTime, func
from sqlalchemy.ext.declarative import declared_attr
from datetime import datetime

# Create base class for SQLAlchemy models
Base = declarative_base()


class TimeStampedModel:
    """
    Abstract base class that provides created_at and updated_at timestamp fields
    for all models that inherit from it.
    """

    @declared_attr
    def created_at(cls):
        return Column(DateTime, default=datetime.utcnow, nullable=False)

    @declared_attr
    def updated_at(cls):
        return Column(
            DateTime,
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
            nullable=False
        )
