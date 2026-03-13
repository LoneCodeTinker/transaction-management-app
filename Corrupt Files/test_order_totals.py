#!/usr/bin/env python
"""Test script to verify order totals calculation after updates."""

import sys
sys.path.insert(0, '.')

from backend.database import SessionLocal, Base, engine
from backend.models import OrderDB, ItemDB, ClientDB
from backend.order_service import OrderService
from datetime import date

# Initialize clean database
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)

db = SessionLocal()

# Create test client
client = ClientDB(display_name="Test Customer", english_name="Test Customer")
db.add(client)
db.commit()
db.refresh(client)

# Create test order
order = OrderDB(
    client_id=client.id,
    project_name="Test Project",
    date=date.today(),
    placed_by="John",
    mobile_number="123456789",
    discount=0,
    status="pending"
)
db.add(order)
db.commit()
db.refresh(order)

print("=" * 80)
print("TEST 1: Adding items during update")
print("=" * 80)

# Simulate receiving an update with 2 items
item1 = ItemDB(order_id=order.id, description="Item 1", quantity=10, price=50, per_item_discount=0, vat=75)
item2 = ItemDB(order_id=order.id, description="Item 2", quantity=5, price=100, per_item_discount=0, vat=75)
db.add(item1)
db.add(item2)
order.items.append(item1)
order.items.append(item2)

OrderService.calculate_order_totals(order)
db.commit()

print(f"✓ Item 1: qty=10, price=50, total={item1.total}, vat={item1.vat}")
print(f"✓ Item 2: qty=5, price=100, total={item2.total}, vat={item2.vat}")
print(f"✓ Order total: {order.order_total} (expected: 1000)")
print(f"✓ Total after discount: {order.total_after_discount} (expected: 1000)")
print(f"✓ VAT total: {order.vat_total} (expected: 150)")
print(f"✓ Total with VAT: {order.total_with_vat} (expected: 1150)")

assert order.order_total == 1000, f"Expected 1000, got {order.order_total}"
assert order.total_after_discount == 1000, f"Expected 1000, got {order.total_after_discount}"
assert order.vat_total == 150, f"Expected 150, got {order.vat_total}"
assert order.total_with_vat == 1150, f"Expected 1150, got {order.total_with_vat}"
print("✓ TEST 1 PASSED\n")

print("=" * 80)
print("TEST 2: Deleting items during update")
print("=" * 80)

# Simulate update that removes item 2
order.items.remove(item2)
db.delete(item2)
OrderService.calculate_order_totals(order)
db.commit()

print(f"✓ Remaining items: {len(order.items)} (expected: 1)")
print(f"✓ Order total: {order.order_total} (expected: 500)")
print(f"✓ VAT total: {order.vat_total} (expected: 75)")
print(f"✓ Total with VAT: {order.total_with_vat} (expected: 575)")

assert len(order.items) == 1, f"Expected 1 item, got {len(order.items)}"
assert order.order_total == 500, f"Expected 500, got {order.order_total}"
assert order.vat_total == 75, f"Expected 75, got {order.vat_total}"
assert order.total_with_vat == 575, f"Expected 575, got {order.total_with_vat}"
print("✓ TEST 2 PASSED\n")

print("=" * 80)
print("TEST 3: Editing item price/quantity")
print("=" * 80)

# Update item 1 quantity and price (VAT remains unchanged in this test)
item1.quantity = 20
item1.price = 100
# Note: VAT is a stored field, not calculated from price. It stays at 75.
OrderService.calculate_order_totals(order)
db.commit()

print(f"✓ Item 1 updated: qty=20, price=100, total={item1.total}, vat={item1.vat}")
print(f"✓ Order total: {order.order_total} (expected: 2000)")
print(f"✓ VAT total: {order.vat_total} (expected: 75, item1.vat unchanged)")
print(f"✓ Total with VAT: {order.total_with_vat} (expected: 2075)")

assert order.order_total == 2000, f"Expected 2000, got {order.order_total}"
assert order.vat_total == 75, f"Expected 75, got {order.vat_total}"
assert order.total_with_vat == 2075, f"Expected 2075, got {order.total_with_vat}"
print("✓ TEST 3 PASSED\n")

print("=" * 80)
print("TEST 4: Discount application")
print("=" * 80)

# Apply discount
order.discount = 200
OrderService.calculate_order_totals(order)
db.commit()

print(f"✓ Discount applied: {order.discount}")
print(f"✓ Order total: {order.order_total} (expected: 2000)")
print(f"✓ Total after discount: {order.total_after_discount} (expected: 1800)")
print(f"✓ VAT total: {order.vat_total} (expected: 75)")
print(f"✓ Total with VAT: {order.total_with_vat} (expected: 1875)")

assert order.order_total == 2000, f"Expected 2000, got {order.order_total}"
assert order.total_after_discount == 1800, f"Expected 1800, got {order.total_after_discount}"
assert order.vat_total == 75, f"Expected 75, got {order.vat_total}"
assert order.total_with_vat == 1875, f"Expected 1875, got {order.total_with_vat}"
print("✓ TEST 4 PASSED\n")

print("=" * 80)
print("✓ ALL TESTS PASSED!")
print("=" * 80)

db.close()
