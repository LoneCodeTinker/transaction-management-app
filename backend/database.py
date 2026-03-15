"""Database configuration and session management for Orders Tracking app."""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.orm.exc import DetachedInstanceError
import os

# SQLite database file
DATABASE_URL = "sqlite:///./orders_tracking.db"

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}  # Required for SQLite with threading
)

Base = declarative_base()


# --- Custom Session with Soft Delete Support ---

class SoftDeleteSession(Session):
    """
    Custom SQLAlchemy session that automatically filters soft-deleted records.
    
    Models that inherit from SoftDeleteMixin will automatically exclude
    soft-deleted records (deleted_at IS NOT NULL) from queries.
    
    To include deleted records in a specific query, use:
        query.execution_options(include_deleted=True)
    """
    
    def query(self, *entities, **kwargs):
        """Override query to apply soft delete filter."""
        result = super().query(*entities, **kwargs)
        
        # Check if include_deleted flag is set
        include_deleted = kwargs.get('include_deleted', False)
        if include_deleted:
            return result
        
        # Apply soft delete filter to each entity
        from .models import SoftDeleteMixin
        
        for entity in entities:
            # Handle both direct model classes and column/mapper objects
            mapper_class = None
            
            if hasattr(entity, '__tablename__'):  # It's a model class
                mapper_class = entity
            elif hasattr(entity, 'class_'):  # It's a mapper or instrumented attribute
                mapper_class = entity.class_
            elif hasattr(entity, 'parent'):  # It's a column that has a parent mapper
                mapper_class = entity.parent.class_
            
            # Apply filter if this model uses SoftDeleteMixin
            if mapper_class and issubclass(mapper_class, SoftDeleteMixin):
                result = result.filter(mapper_class.deleted_at.is_(None))
        
        return result


SessionLocal = sessionmaker(bind=engine, class_=SoftDeleteSession)


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
