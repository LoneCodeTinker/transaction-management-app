"""Test to verify the original error is fixed."""

import sys
sys.path.insert(0, r"c:\Users\Design5\Documents\Py Projects\Orders Tracking\apps\backend")

from app.models import TransactionCreate, OrderCreate, OrderUpdate, TransactionUpdate

print("=" * 80)
print("Testing Original Error Scenario: Invalid isoformat string")
print("=" * 80)

# Original error: "Invalid isoformat string: '2025-06-24 00:00:00'"
# This was happening when SQLite returned datetime with space separator

print("\n✓ BEFORE FIX: Would have failed with:")
print("  Error: Invalid isoformat string: '2025-06-24 00:00:00'")
print("\n✓ AFTER FIX: Now handles all formats gracefully:")
print("-" * 80)

# Test scenarios from real-world usage
test_scenarios = [
    {
        "name": "SQLite returned datetime (space separator)",
        "model": "TransactionCreate",
        "data": {
            "type": "sales",
            "name": "Client A",
            "date": "2025-06-24 00:00:00",  # ← Original error case
            "amount": 5000.00,
            "vat": 750.00,
            "total": 5750.00,
        }
    },
    {
        "name": "SQLite returned datetime with milliseconds",
        "model": "OrderCreate",
        "data": {
            "client_id": 1,
            "date": "2025-06-24 14:30:45.123456",  # ← Milliseconds
            "discount": 100.00,
        }
    },
    {
        "name": "Frontend sent ISO format with T",
        "model": "TransactionCreate",
        "data": {
            "type": "purchases",
            "name": "Vendor B",
            "date": "2025-06-24T09:00:00",  # ← ISO T format
            "amount": 2000.00,
            "vat": 300.00,
            "total": 2300.00,
        }
    },
    {
        "name": "API received date-only string",
        "model": "OrderCreate",
        "data": {
            "client_id": 2,
            "date": "2025-06-25",  # ← Date only
        }
    },
    {
        "name": "Update endpoint with SQLite datetime",
        "model": "TransactionUpdate",
        "data": {
            "date": "2025-06-24 14:30:00",  # ← Space separator in update
            "amount": 3000.00,
        }
    },
    {
        "name": "Order update with ISO format",
        "model": "OrderUpdate",
        "data": {
            "date": "2025-06-24T10:00:00",  # ← ISO T in update
            "discount": 200.00,
        }
    },
]

models = {
    "TransactionCreate": TransactionCreate,
    "OrderCreate": OrderCreate,
    "TransactionUpdate": TransactionUpdate,
    "OrderUpdate": OrderUpdate,
}

success_count = 0
fail_count = 0

for scenario in test_scenarios:
    try:
        ModelClass = models[scenario["model"]]
        instance = ModelClass(**scenario["data"])
        print(f"✓ {scenario['name']}")
        print(f"  Model: {scenario['model']}")
        print(f"  Date Input: {scenario['data']['date']!r}")
        print(f"  Parsed As:  {instance.date}")
        print()
        success_count += 1
    except Exception as e:
        print(f"✗ {scenario['name']}")
        print(f"  Error: {e}")
        print()
        fail_count += 1

print("=" * 80)
print(f"Results: {success_count} passed ✓ | {fail_count} failed ✗")
print("=" * 80)

if fail_count == 0:
    print("\n🎉 SUCCESS! The datetime normalization fix resolves the issue.")
    print("\nKey improvements:")
    print("  • Accepts SQLite format (space separator): '2025-06-24 00:00:00'")
    print("  • Accepts ISO format (T separator):       '2025-06-24T00:00:00'")
    print("  • Accepts date-only format:               '2025-06-24'")
    print("  • Accepts datetime with milliseconds:     '2025-06-24 14:30:45.123456'")
    print("  • Works with both Create and Update endpoints")
else:
    print(f"\n⚠️  {fail_count} test(s) failed. See details above.")
