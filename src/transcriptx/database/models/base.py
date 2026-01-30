"""Database model base definitions."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    desc,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy.sql import func

# Use JSON for SQLite, JSONB for PostgreSQL
try:
    from sqlalchemy import JSON as JSONType  # Use JSON for SQLite
except ImportError:
    try:
        from sqlalchemy.dialects.postgresql import (
            JSONB as JSONType,
        )  # Use JSONB for PostgreSQL
    except ImportError:
        pass  # Fallback for older SQLAlchemy

Base = declarative_base()

__all__ = [
    "Base",
    "JSONType",
    "Mapped",
    "relationship",
    "Column",
    "Integer",
    "String",
    "Text",
    "Float",
    "Boolean",
    "DateTime",
    "ForeignKey",
    "Index",
    "UniqueConstraint",
    "func",
    "desc",
    "event",
    "hybrid_property",
]


# Event listeners for automatic timestamp updates
@event.listens_for(Base, "before_update", propagate=True)
def timestamp_before_update(mapper, connection, target):
    """Automatically update the updated_at timestamp before any update."""
    target.updated_at = func.now()
