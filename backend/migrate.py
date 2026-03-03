"""
Database migration script for Orders Tracking app.

This script creates or updates all database tables to match the current schema.
Run this before starting the application.
"""

import sys
from database import engine, Base
from models import ClientDB, OrderDB, ItemDB, TransactionDB


def migrate():
    """Create all tables in the database."""
    print("Starting database migration...")
    
    try:
        # Create all tables defined in Base metadata
        Base.metadata.create_all(bind=engine)
        print("✓ Database migration completed successfully.")
        print("✓ Created/Updated tables:")
        print("  - clients")
        print("  - orders")
        print("  - items")
        print("  - transactions")
        return True
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        return False


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
