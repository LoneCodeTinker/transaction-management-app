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
import os
import pandas as pd
import tkinter as tk
from datetime import datetime
from sqlalchemy import create_engine, text
from tkinter import filedialog
from pathlib import Path


# -----------------------------
# Configuration
# -----------------------------

def normalize_date_string(date_val):
    """Normalize date string formats for pandas to_datetime parsing."""
    if pd.isna(date_val):
        return date_val
    
    date_str = str(date_val).strip()
    
    # Convert SQLite/Excel space separator to ISO T separator for pandas compatibility
    if ' ' in date_str and len(date_str) > 10:
        parts = date_str.split(' ', 1)
        if len(parts) == 2 and '-' in parts[0] and ':' in parts[1]:
            return f"{parts[0]}T{parts[1]}"
    
    return date_str


def choose_file():
    root = tk.Tk()
    root.withdraw()  # hide the main window
    file_path = filedialog.askopenfilename(
        title="Select Excel file",
        filetypes=[("Excel files", "*.xlsx *.xls")]
    )
    return file_path

# EXCEL_FILE = choose_file()
EXCEL_FILE = Path(
    input("Drag & drop your Excel file here (or paste path)>_ ").strip().strip('"').strip("'")
).expanduser()
db_input = input("Drag & drop your DB file here (or paste path)>_ ").strip().strip('"').strip("'")

db_path = Path(db_input).expanduser()

# Force correct handling of absolute vs relative paths
if not db_path.is_absolute():
    db_path = (Path.cwd() / db_path).resolve()


# -----------------------------
# Debug Line
# -----------------------------

print("RAW INPUT:", db_input)
print("FINAL PATH:", db_path)
input("continue")

# Now safely create parent directory
db_path.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{db_path}"


engine = create_engine(DATABASE_URL)


# -----------------------------
# Database initialize
# -----------------------------

def validate_columns(df):
    required_columns = [
        "Name",
        "Date",
        "Description",
        "Reference",
        "Amount",
        "VAT",
        "Total",
        "Done"
    ]

    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        print("\n❌ Column validation failed")
        print("Missing columns:", missing)
        print("Available columns:", list(df.columns))
        return False

    print("✅ Excel columns validated")
    return True


# -----------------------------
# Database initialize
# -----------------------------

def ensure_tables_exist(conn):

    # Create tables first
    conn.execute(text(""" CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        display_name TEXT,
        english_name TEXT,
        arabic_name TEXT,
        contact_person TEXT,
        mobile_number TEXT,
        file_path TEXT,
        created_at DATETIME,
        updated_at DATETIME,
        deleted_at DATETIME,
        deleted_by TEXT
    )"""))

    conn.execute(text(""" CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        project_name TEXT,
        file_path TEXT,
        date DATETIME,
        placed_by TEXT,
        mobile_number TEXT,
        order_total REAL,
        discount REAL,
        total_after_discount REAL,
        vat_total REAL,
        total_with_vat REAL,
        status TEXT,
        created_at DATETIME,
        updated_at DATETIME,
        deleted_at DATETIME,
        deleted_by TEXT
    )"""))

    conn.execute(text(""" CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        description TEXT,
        quantity INTEGER,
        price REAL,
        total REAL,
        per_item_discount REAL,
        vat REAL,
        deleted_at DATETIME,
        deleted_by TEXT
    )"""))

    conn.execute(text(""" CREATE TABLE IF NOT EXISTS order_references (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        reference_type TEXT,
        reference_value TEXT,
        source_system TEXT,
        created_at DATETIME,
        updated_at DATETIME,
        deleted_at DATETIME,
        deleted_by TEXT
    )"""))

    # -----------------------------
    # Ensure columns exist
    # -----------------------------

    ensure_columns_exist(conn, "clients", {
        "display_name": "TEXT",
        "english_name": "TEXT",
        "arabic_name": "TEXT",
        "contact_person": "TEXT",
        "mobile_number": "TEXT",
        "file_path": "TEXT",
        "created_at": "DATETIME",
        "updated_at": "DATETIME",
        "deleted_at": "DATETIME",
        "deleted_by": "TEXT"
    })

    ensure_columns_exist(conn, "orders", {
        "client_id": "INTEGER",
        "project_name": "TEXT",
        "file_path": "TEXT",
        "date": "DATETIME",
        "placed_by": "TEXT",
        "mobile_number": "TEXT",
        "order_total": "REAL",
        "discount": "REAL",
        "total_after_discount": "REAL",
        "vat_total": "REAL",
        "total_with_vat": "REAL",
        "status": "TEXT",
        "created_at": "DATETIME",
        "updated_at": "DATETIME",
        "deleted_at": "DATETIME",
        "deleted_by": "TEXT"
    })

    ensure_columns_exist(conn, "items", {
        "order_id": "INTEGER",
        "description": "TEXT",
        "quantity": "INTEGER",
        "price": "REAL",
        "total": "REAL",
        "per_item_discount": "REAL",
        "vat": "REAL",
        "deleted_at": "DATETIME",
        "deleted_by": "TEXT"
    })

    ensure_columns_exist(conn, "order_references", {
        "order_id": "INTEGER",
        "reference_type": "TEXT",
        "reference_value": "TEXT",
        "source_system": "TEXT",
        "created_at": "DATETIME",
        "updated_at": "DATETIME",
        "deleted_at": "DATETIME",
        "deleted_by": "TEXT"
    })


# -----------------------------
# Helper: Correct db schema
# -----------------------------

def ensure_columns_exist(conn, table_name, required_columns):
    existing_cols = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    existing_col_names = {col[1] for col in existing_cols}

    for col_name, col_type in required_columns.items():
        if col_name not in existing_col_names:
            print(f"⚠️ Adding missing column '{col_name}' to '{table_name}'")
            conn.execute(text(
                f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"
            ))
            
            
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
            reference_type,
            reference_value,
            created_at,
            updated_at
        ) VALUES (
            :order_id,
            :reference_type,
            :reference_value,
            :created_at,
            :updated_at
        )
    """)

    conn.execute(query, {
        "order_id": order_id,
        "reference_type": order_references["type"],
        "reference_value": order_references["value"],
        "created_at": order_date,
        "updated_at": order_date
    })


# -----------------------------
# Migration Runner
# -----------------------------

def run_migration():

    df = pd.read_excel(EXCEL_FILE)
    
    df.columns = (
        df.columns
        .str.strip()
        .str.replace("\xa0", " ", regex=False)
    )

    if not validate_columns(df):
        print("❌ Migration aborted due to column mismatch")
        return
    
    # Normalize date formats before parsing (handles SQLite space separator: '2025-06-24 00:00:00')
    df["Date"] = df["Date"].apply(normalize_date_string)
    
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df[df["Date"].notna()]
    df["Date"] = df["Date"].dt.to_pydatetime()
    df = df.sort_values(by="Date").reset_index(drop=True)

    with engine.begin() as conn:
        ensure_tables_exist(conn)
        

        for index, row in df.iterrows():

            client_name = row["Name"]
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