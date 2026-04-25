"""Test that soft-deleted items are excluded from the items relationship."""

from backend.database import init_db, SessionLocal
from backend.models import ItemDB, OrderDB, ClientDB
from datetime import datetime

# Initialize database
init_db()

# Create a test session
session = SessionLocal()
try:
    # Create a test client and order
    test_client = ClientDB(display_name="Test Client")
    session.add(test_client)
    session.commit()
    
    test_order = OrderDB(
        client_id=test_client.id,
        date=datetime.now().date(),
        order_total=0,
        discount=0,
        total_after_discount=0,
        vat_total=0,
        total_with_vat=0
    )
    session.add(test_order)
    session.commit()
    
    # Create test items
    item1 = ItemDB(order_id=test_order.id, description="Item 1", quantity=1, price=100)
    item2 = ItemDB(order_id=test_order.id, description="Item 2", quantity=2, price=200)
    session.add_all([item1, item2])
    session.commit()
    
    # Verify items appear in relationship
    print(f"✓ Items before soft delete: {len(test_order.items)} items")
    for item in test_order.items:
        print(f"  - {item.description} (id={item.id})")
    
    # Soft-delete one item
    item2.deleted_at = datetime.utcnow()
    item2.deleted_by = "test"
    session.commit()
    
    # Refresh order to reload relationship
    session.refresh(test_order)
    
    # Verify soft-deleted item is excluded
    print(f"✓ Items after soft delete: {len(test_order.items)} items")
    for item in test_order.items:
        print(f"  - {item.description} (id={item.id})")
    
    if len(test_order.items) == 1 and test_order.items[0].description == "Item 1":
        print("✓ SUCCESS: Soft-deleted items are automatically excluded from relationship!")
    else:
        print("✗ FAILED: Soft-deleted items still appear in relationship")
        
finally:
    session.close()
