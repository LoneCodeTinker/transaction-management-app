"""
Database Schema Migration: Orders Management System

This migration implements a complete orders management system with three new tables:
- clients: Store client information
- orders: Store order details with calculations
- items: Store line items for each order

Previous Table:
- transactions: Kept for backward compatibility

New Schema Structure:

TABLE: clients
├── id (PK)
├── display_name
├── english_name
├── arabic_name
├── contact_person
├── mobile_number
├── file_path
├── created_at
└── updated_at

TABLE: orders
├── id (PK)
├── client_id (FK → clients.id, CASCADE DELETE)
├── project_name
├── file_path
├── date
├── placed_by (defaults to client.contact_person)
├── mobile_number (defaults to client.mobile_number)
├── order_total (auto-calculated)
├── discount
├── total_after_discount (auto-calculated)
├── vat_total (auto-calculated)
├── total_with_vat (auto-calculated)
├── status
├── created_at
└── updated_at

TABLE: items
├── id (PK)
├── order_id (FK → orders.id, CASCADE DELETE)
├── description
├── quantity
├── price
├── total (auto-calculated = quantity × price)
├── per_item_discount
└── vat

Relationships:
- Client.orders: One-to-Many (cascade delete)
- Order.client: Many-to-One
- Order.items: One-to-Many (cascade delete)
- Item.order: Many-to-One

Calculation Logic:
1. item.total = quantity × price
2. order_total = SUM(items.total)
3. total_item_discounts = SUM(items.per_item_discount)
4. total_after_discount = order_total - discount - total_item_discounts
5. vat_total = SUM(items.vat)
6. total_with_vat = total_after_discount + vat_total

Default Values:
- If order.placed_by is empty → uses client.contact_person
- If order.mobile_number is empty → uses client.mobile_number

Cascade Behavior:
- Deleting a client deletes all associated orders (which cascades to delete items)
- Deleting an order deletes all associated items

Migration Steps:
1. Backup existing database (backup creates tables)
2. Run: python -m backend.migrate
3. Verify tables exist in database
4. Test API endpoints

Running the Migration:
From the project root:
  python -m backend.migrate

Or from the backend directory:
  python migrate.py
"""

from sqlalchemy import inspect
from .database import engine, Base
from .models import ClientDB, OrderDB, ItemDB, TransactionDB


def check_migration_status():
    """Check which tables exist in the database."""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    print("Current database tables:")
    for table in existing_tables:
        print(f"  ✓ {table}")
    
    required_tables = {"clients", "orders", "items", "transactions"}
    missing = required_tables - set(existing_tables)
    
    if missing:
        print(f"\nMissing tables: {', '.join(missing)}")
        return False
    
    print("\n✓ All required tables exist")
    return True


def apply_migration():
    """Create all missing tables."""
    Base.metadata.create_all(bind=engine)
    print("✓ Migration applied successfully")


if __name__ == "__main__":
    print("Checking migration status...\n")
    if not check_migration_status():
        print("\nApplying migration...")
        apply_migration()
        check_migration_status()
