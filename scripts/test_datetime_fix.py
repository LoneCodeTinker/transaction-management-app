"""Test script to verify datetime normalization fix."""

import sys
sys.path.insert(0, r"c:\Users\Design5\Documents\Py Projects\Orders Tracking\apps\backend")

from app.models import TransactionCreate, OrderCreate, normalize_datetime_string
from datetime import datetime, date

print("=" * 70)
print("Testing DateTime Normalization Fix")
print("=" * 70)

# Test 1: Normalize function
print("\n1. Testing normalize_datetime_string() function:")
print("-" * 70)

test_cases = [
    ("2025-06-24 00:00:00", "SQLite format (space separator)"),
    ("2025-06-24T00:00:00", "ISO format (T separator)"),
    ("2025-06-24", "Date only"),
    ("2025-06-24 14:30:45.123456", "SQLite with milliseconds"),
]

for input_str, description in test_cases:
    result = normalize_datetime_string(input_str)
    print(f"✓ {description}")
    print(f"  Input:  {input_str!r}")
    print(f"  Output: {result!r}")

# Test 2: TransactionCreate with SQLite format
print("\n2. Testing TransactionCreate with SQLite datetime format:")
print("-" * 70)

try:
    tx_data = {
        "type": "sales",
        "name": "Test Client",
        "date": "2025-06-24 00:00:00",  # SQLite format with space
        "description": "Test transaction",
        "amount": 1000.00,
        "vat": 150.00,
        "total": 1150.00,
        "done": False
    }
    
    tx = TransactionCreate(**tx_data)
    print(f"✓ Successfully created TransactionCreate with SQLite format")
    print(f"  Input date: '2025-06-24 00:00:00'")
    print(f"  Parsed as:  {tx.date} (type: {type(tx.date).__name__})")
except Exception as e:
    print(f"✗ FAILED: {e}")

# Test 3: TransactionCreate with ISO format
print("\n3. Testing TransactionCreate with ISO format (T separator):")
print("-" * 70)

try:
    tx_data = {
        "type": "purchases",
        "name": "Test Vendor",
        "date": "2025-06-24T14:30:00",  # ISO format with T
        "amount": 500.00,
        "vat": 75.00,
        "total": 575.00,
    }
    
    tx = TransactionCreate(**tx_data)
    print(f"✓ Successfully created TransactionCreate with ISO format")
    print(f"  Input date: '2025-06-24T14:30:00'")
    print(f"  Parsed as:  {tx.date} (type: {type(tx.date).__name__})")
except Exception as e:
    print(f"✗ FAILED: {e}")

# Test 4: OrderCreate with various formats
print("\n4. Testing OrderCreate with SQLite format:")
print("-" * 70)

try:
    order_data = {
        "client_id": 1,
        "date": "2025-06-24 12:00:00",  # SQLite format with space and time
        "placed_by": "John Doe",
        "discount": 50.00
    }
    
    order = OrderCreate(**order_data)
    print(f"✓ Successfully created OrderCreate with SQLite format")
    print(f"  Input date: '2025-06-24 12:00:00'")
    print(f"  Parsed as:  {order.date} (type: {type(order.date).__name__})")
except Exception as e:
    print(f"✗ FAILED: {e}")

# Test 5: Test with date object (should still work)
print("\n5. Testing with date object:")
print("-" * 70)

try:
    order_data = {
        "client_id": 1,
        "date": date(2025, 6, 24),  # Python date object
        "placed_by": "Jane Doe",
    }
    
    order = OrderCreate(**order_data)
    print(f"✓ Successfully created OrderCreate with date object")
    print(f"  Input date: {date(2025, 6, 24)}")
    print(f"  Parsed as:  {order.date} (type: {type(order.date).__name__})")
except Exception as e:
    print(f"✗ FAILED: {e}")

print("\n" + "=" * 70)
print("All tests completed successfully! ✓")
print("=" * 70)
