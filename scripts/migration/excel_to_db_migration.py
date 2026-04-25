"""
Excel → Database Migration Script
---------------------------------
Reads legacy Excel sheet where items are serialized in the Description column
and migrates the data into normalized tables:

clients
orders
items
references

Assumptions based on current schema and migration rules.

Requirements:
    pip install pandas openpyxl sqlalchemy

Usage:
    python excel_to_db_migration.py

Make sure DATABASE_URL points to your SQLite database.
"""

import re
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text

# -----------------------------
# Configuration
# -----------------------------

EXCEL_FILE = "orders.xlsx"
DATABASE_URL = "sqlite:///./orders_tracking.db"

engine = create_engine(DATABASE_URL)


# -----------------------------
# Helper: Client
# -----------------------------

def get_or_create_client(conn, client_name, order_date):
    query = text("""
        SELECT id FROM clients
        WHERE display_name = :name
        LIMIT 1
    """)

    result = conn.execute(query, {"name": client_name}).fetchone()

    if result:
        return result[0]

    insert = text("""
        INSERT INTO clients (
            display_name,
            english_name,
            created_at
        ) VALUES (
            :display_name,
            NULL,
            :created_at
        )
    """)

    res = conn.execute(insert, {
        "display_name": client_name,
        "created_at": order_date
    })

    return res.lastrowid


# -----------------------------
# Helper: Discount Parser
# -----------------------------

def extract_discount(description):
    match = re.search(r"Discount:\s*(\d+(?:\.\d+)?)", description)

    if match:
        discount = float(match.group(1))
        description = re.sub(r";?\s*Discount:\s*\d+(?:\.\d+)?", "", description)
        return discount, description

    return 0.0, description


# -----------------------------
# Helper: Item Parser
# -----------------------------

def parse_items(description):
    items = []

    segments = description.split(";")

    for segment in segments:
        segment = segment.strip()

        if not segment:
            continue

        if "Discount:" in segment:
            continue

        try:
            desc_match = re.search(r"#\d+:\s*(.*?)\s*\|", segment)
            qty_match = re.search(r"Qty:\s*(\d+)", segment)
            price_match = re.search(r"Price:\s*(\d+(?:\.\d+)?)", segment)
            total_match = re.search(r"Total:\s*(\d+(?:\.\d+)?)", segment)
            vat_match = re.search(r"VAT:\s*(\d+(?:\.\d+)?)", segment)

            description_text = desc_match.group(1) if desc_match else ""
            quantity = int(qty_match.group(1)) if qty_match else 0
            price = float(price_match.group(1)) if price_match else 0
            total = float(total_match.group(1)) if total_match else 0
            vat = float(vat_match.group(1)) if vat_match else 0

            items.append({
                "description": description_text,
                "quantity": quantity,
                "price": price,
                "total": total,
                "vat": vat,
                "per_item_discount": 0
            })

        except Exception as e:
            print("Item parse failed:", segment)
            raise e

    return items


# -----------------------------
# Helper: Reference Parser
# -----------------------------

def parse_reference(ref):
    if not ref or pd.isna(ref):
        return None

    match = re.match(r"([A-Za-z]+)#(\d+)", str(ref).strip())

    if match:
        return {
            "type": match.group(1),
            "value": match.group(2)
        }

    return None


# -----------------------------
# Insert Order
# -----------------------------

def insert_order(conn, client_id, row, discount):

    order_total = float(row["Amount"]) if not pd.isna(row["Amount"]) else 0
    vat_total = float(row["VAT"]) if not pd.isna(row["VAT"]) else 0
    total_with_vat = float(row["Total"]) if not pd.isna(row["Total"]) else 0

    total_after_discount = order_total - discount

    status = "completed" if str(row["Done"]).upper() == "TRUE" else "pending"

    order_date = row["Date"]

    query = text("""
        INSERT INTO orders (
            client_id,
            project_name,
            file_path,
            date,
            placed_by,
            mobile_number,
            order_total,
            discount,
            total_after_discount,
            vat_total,
            total_with_vat,
            status,
            created_at
        ) VALUES (
            :client_id,
            NULL,
            NULL,
            :date,
            NULL,
            NULL,
            :order_total,
            :discount,
            :total_after_discount,
            :vat_total,
            :total_with_vat,
            :status,
            :created_at
        )
    """)

    res = conn.execute(query, {
        "client_id": client_id,
        "date": order_date,
        "order_total": order_total,
        "discount": discount,
        "total_after_discount": total_after_discount,
        "vat_total": vat_total,
        "total_with_vat": total_with_vat,
        "status": status,
        "created_at": order_date
    })

    return res.lastrowid


# -----------------------------
# Insert Item
# -----------------------------

def insert_item(conn, order_id, item):

    query = text("""
        INSERT INTO items (
            order_id,
            description,
            quantity,
            price,
            total,
            per_item_discount,
            vat
        ) VALUES (
            :order_id,
            :description,
            :quantity,
            :price,
            :total,
            :per_item_discount,
            :vat
        )
    """)

    conn.execute(query, {
        "order_id": order_id,
        "description": item["description"],
        "quantity": item["quantity"],
        "price": item["price"],
        "total": item["total"],
        "per_item_discount": item["per_item_discount"],
        "vat": item["vat"]
    })


# -----------------------------
# Insert Reference
# -----------------------------

def insert_reference(conn, order_id, order_references, order_date):

    query = text("""
        INSERT INTO order_references (
            order_id,
            type,
            value,
            created_at,
            updated_at
        ) VALUES (
            :order_id,
            :type,
            :value,
            :created_at,
            :updated_at
        )
    """)

    conn.execute(query, {
        "order_id": order_id,
        "type": order_references["type"],
        "value": order_references["value"],
        "created_at": order_date,
        "updated_at": order_date
    })


# -----------------------------
# Migration Runner
# -----------------------------

def run_migration():

    df = pd.read_excel(EXCEL_FILE)

    with engine.begin() as conn:

        for index, row in df.iterrows():

            client_name = row["Client Name"]
            order_date = row["Date"]

            description = str(row["Description"])

            discount, description = extract_discount(description)

            client_id = get_or_create_client(conn, client_name, order_date)

            order_id = insert_order(conn, client_id, row, discount)

            items = parse_items(description)

            for item in items:
                insert_item(conn, order_id, item)

            reference = parse_reference(row["Reference"])

            if reference:
                insert_reference(conn, order_id, reference, order_date)

            print(f"Migrated row {index + 1} → order_id {order_id}")


# -----------------------------
# Entry
# -----------------------------

if __name__ == "__main__":
    run_migration()
