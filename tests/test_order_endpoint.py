#!/usr/bin/env python
"""Test script for POST /orders/structured endpoint."""

import json
import sqlite3
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.models import ClientDB, OrderDB, ItemDB


def check_database():
    """Check current database state."""
    conn = sqlite3.connect('orders_tracking.db')
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"\n=== Database Tables ===")
    print(f"Tables: {[t[0] for t in tables]}")
    
    # Check clients
    cursor.execute("SELECT id, display_name FROM clients")
    clients = cursor.fetchall()
    print(f"\n=== Clients (Before) ===")
    for client in clients:
        print(f"  ID: {client[0]}, Name: {client[1]}")
    
    # Check orders
    cursor.execute("""
        SELECT id, client_id, project_name, order_total, total_after_discount, 
               vat_total, total_with_vat 
        FROM orders
    """)
    orders = cursor.fetchall()
    print(f"\n=== Orders (Before) ===")
    for order in orders:
        print(f"  ID: {order[0]}, Client ID: {order[1]}, Project: {order[2]}")
        print(f"    order_total: {order[3]}, total_after_discount: {order[4]}")
        print(f"    vat_total: {order[5]}, total_with_vat: {order[6]}")
    
    # Check items
    cursor.execute("""
        SELECT id, order_id, description, quantity, price, total, vat 
        FROM items
    """)
    items = cursor.fetchall()
    print(f"\n=== Items (Before) ===")
    for item in items:
        print(f"  ID: {item[0]}, Order ID: {item[1]}, Description: {item[2]}")
        print(f"    Qty: {item[3]}, Price: {item[4]}, Total: {item[5]}, VAT: {item[6]}")
    
    conn.close()


def test_endpoint():
    """Test POST /orders/structured endpoint."""
    
    payload = {
        "client_name": "Test Client Structured",
        "project_name": "Test Project",
        "date": "2026-03-07",
        "items": [
            {
                "description": "Item A",
                "quantity": 5,
                "price": 10,
                "vat": 1.5
            },
            {
                "description": "Item B",
                "quantity": 2,
                "price": 30,
                "vat": 4.5
            }
        ]
    }
    
    print("\n" + "="*60)
    print("TEST PAYLOAD")
    print("="*60)
    print(json.dumps(payload, indent=2))
    
    check_database()
    
    print("\n" + "="*60)
    print("SENDING POST /orders/structured")
    print("="*60)
    
    try:
        response = requests.post(
            'http://localhost:8001/orders/structured',
            json=payload,
            timeout=5
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            result = response.json()
            order_id = result.get('id')
            client_id = result.get('client_id')
            
            print(f"\n✓ Order created! Order ID: {order_id}, Client ID: {client_id}")
            
            # Check database after creation
            print("\n" + "="*60)
            print("DATABASE AFTER CREATION")
            print("="*60)
            check_database()
            
            # Verify data
            conn = sqlite3.connect('orders_tracking.db')
            cursor = conn.cursor()
            
            # Get order details
            cursor.execute("""
                SELECT order_total, total_after_discount, vat_total, total_with_vat 
                FROM orders WHERE id = ?
            """, (order_id,))
            order_data = cursor.fetchone()
            
            print(f"\n=== ORDER TOTALS (ID: {order_id}) ===")
            if order_data:
                print(f"  order_total: {order_data[0]}")
                print(f"  total_after_discount: {order_data[1]}")
                print(f"  vat_total: {order_data[2]}")
                print(f"  total_with_vat: {order_data[3]}")
                
                # Expected calculations:
                # Item A: 5 * 10 = 50
                # Item B: 2 * 30 = 60
                # order_total = 50 + 60 = 110
                # total_after_discount = 110 - 0 - 0 = 110
                # vat_total = 1.5 + 4.5 = 6.0
                # total_with_vat = 110 + 6.0 = 116.0
                
                expected_order_total = 110.0
                expected_vat_total = 6.0
                expected_total_with_vat = 116.0
                
                print(f"\n=== EXPECTED VS ACTUAL ===")
                print(f"  order_total: {expected_order_total} (expected) vs {order_data[0]} (actual) - {'✓' if order_data[0] == expected_order_total else '✗'}")
                print(f"  vat_total: {expected_vat_total} (expected) vs {order_data[2]} (actual) - {'✓' if order_data[2] == expected_vat_total else '✗'}")
                print(f"  total_with_vat: {expected_total_with_vat} (expected) vs {order_data[3]} (actual) - {'✓' if order_data[3] == expected_total_with_vat else '✗'}")
            
            # Get items
            cursor.execute("""
                SELECT id, description, quantity, price, total, vat 
                FROM items WHERE order_id = ?
            """, (order_id,))
            items = cursor.fetchall()
            
            print(f"\n=== ITEMS FOR ORDER {order_id} ===")
            for item in items:
                print(f"  ID: {item[0]}, {item[1]}")
                print(f"    Qty: {item[2]}, Price: {item[3]}, Total: {item[4]}, VAT: {item[5]}")
            
            conn.close()
        else:
            print(f"✗ Error: {response.json()}")
            
    except requests.exceptions.ConnectionError:
        print("✗ Connection Error: Backend is not running on localhost:8001")
        print("  Please start the backend with: uvicorn backend.main:app --reload --host 0.0.0.0 --port 8001")
    except Exception as e:
        print(f"✗ Error: {e}")


if __name__ == '__main__':
    test_endpoint()
