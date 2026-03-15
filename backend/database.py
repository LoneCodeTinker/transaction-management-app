"""Database configuration and session management for Orders Tracking app."""

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import select
import os

# SQLite database file
DATABASE_URL = "sqlite:///./orders_tracking.db"

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}  # Required for SQLite with threading
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# --- Soft Delete Global Filter ---

def apply_soft_delete_filter(select_stmt, **kw):
    """
    SQLAlchemy event listener that automatically filters soft-deleted records.
    
    Adds 'WHERE deleted_at IS NULL' to all SELECT queries on models with deleted_at column.
    Can be bypassed by setting execution_options(include_deleted=True).
    """
    # Check if include_deleted flag is set to bypass filtering
    if hasattr(select_stmt, '_execution_options') and select_stmt._execution_options.get('include_deleted', False):
        return select_stmt
    
    # Get all FROM clauses and their tables/entities
    for frm in select_stmt.froms:
        # Extract the mapped class from the FROM clause
        mapper = getattr(frm, 'entity', None)
        if mapper is None and hasattr(frm, 'mapped_table'):
            mapper = frm.mapped_table.entity
        
        # If we found a mapper, check if it has deleted_at column
        if mapper and hasattr(mapper, 'deleted_at'):
            select_stmt = select_stmt.where(mapper.deleted_at.is_(None))
    
    return select_stmt


# Attach the soft delete filter to all SELECT queries
event.listen(select, "before_select", apply_soft_delete_filter, retval=True)


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
