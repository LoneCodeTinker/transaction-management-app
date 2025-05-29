from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import openpyxl
import os
from datetime import date, datetime
from openpyxl.utils.exceptions import InvalidFileException
from zipfile import BadZipFile
import shutil

app = FastAPI()

# Allow frontend (localhost:5173) to access backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

EXCEL_FILE = "transactions.xlsx"
SHEET_NAMES = {"sales": "Sales", "received": "Received", "purchases": "Purchases", "expenses": "Expenses"}

class Transaction(BaseModel):
    type: str  # sales, purchases, expenses
    name: str  # vendor or customer
    date: date
    description: Optional[str] = None
    reference: Optional[str] = None
    amount: float
    vat: float
    total: float
    actions: Optional[List[str]] = None  # Change default to None
    done: bool = False


def get_or_create_workbook():
    # Try to load workbook, handle corruption
    try:
        if not os.path.exists(EXCEL_FILE):
            wb = openpyxl.Workbook()
            for sheet in SHEET_NAMES.values():
                wb.create_sheet(sheet)
            if 'Sheet' in wb.sheetnames:
                del wb['Sheet']
            wb.save(EXCEL_FILE)
        wb = openpyxl.load_workbook(EXCEL_FILE)
    except (BadZipFile, InvalidFileException):
        # Corrupted file: backup and recreate
        backup_name = f"transactions_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        shutil.move(EXCEL_FILE, backup_name)
        wb = openpyxl.Workbook()
        for sheet in SHEET_NAMES.values():
            wb.create_sheet(sheet)
        if 'Sheet' in wb.sheetnames:
            del wb['Sheet']
        wb.save(EXCEL_FILE)
        wb = openpyxl.load_workbook(EXCEL_FILE)
    # Ensure all required sheets exist
    changed = False
    for sheet in SHEET_NAMES.values():
        if sheet not in wb.sheetnames:
            wb.create_sheet(sheet)
            changed = True
    if changed:
        wb.save(EXCEL_FILE)
    return wb


def save_transaction_to_excel(tx: Transaction):
    wb = get_or_create_workbook()
    sheet = wb[SHEET_NAMES[tx.type]]
    if sheet.max_row == 1:
        sheet.append([
            "Name", "Date", "Description", "Reference", "Amount", "VAT", "Total", "Actions", "Done"
        ])
    # Ensure actions is always a list
    actions = tx.actions if tx.actions is not None else []
    sheet.append([
        tx.name, tx.date.isoformat(), tx.description, tx.reference, tx.amount, tx.vat, tx.total, ','.join(actions), tx.done
    ])
    wb.save(EXCEL_FILE)


def read_transactions_from_excel(tx_type: str):
    wb = get_or_create_workbook()
    sheet = wb[SHEET_NAMES[tx_type]]
    rows = list(sheet.iter_rows(values_only=True))
    if len(rows) < 2:
        return []
    headers = rows[0]
    transactions = []
    for row in rows[1:]:
        tx = dict(zip(headers, row))
        # Convert actions from comma string to list, filter out empty strings
        if tx.get('Actions'):
            tx['Actions'] = [a for a in tx['Actions'].split(',') if a]
        else:
            tx['Actions'] = []
        transactions.append(tx)
    return transactions


def update_transaction_in_excel(tx_type: str, idx: int, updated: dict):
    wb = get_or_create_workbook()
    sheet = wb[SHEET_NAMES[tx_type]]
    rows = list(sheet.iter_rows(values_only=False))
    if idx + 2 > len(rows):
        raise HTTPException(status_code=404, detail="Transaction not found.")
    headers = [cell.value for cell in rows[0]]
    for col, key in enumerate(headers):
        value = updated.get(key, rows[idx+1][col].value)
        if key == 'Actions' and isinstance(value, list):
            value = ','.join(value)
        rows[idx+1][col].value = value
    wb.save(EXCEL_FILE)


@app.post("/transaction")
def add_transaction(tx: Transaction):
    if tx.type not in SHEET_NAMES:
        raise HTTPException(status_code=400, detail="Invalid transaction type.")
    save_transaction_to_excel(tx)
    return {"message": "Transaction saved."}


@app.get("/transactions/{tx_type}")
def list_transactions(tx_type: str):
    if tx_type not in SHEET_NAMES:
        raise HTTPException(status_code=400, detail="Invalid transaction type.")
    txs = read_transactions_from_excel(tx_type)
    return JSONResponse(content=txs)


@app.put("/transactions/{tx_type}/{idx}")
def update_transaction(tx_type: str, idx: int, updated: dict = Body(...)):
    if tx_type not in SHEET_NAMES:
        raise HTTPException(status_code=400, detail="Invalid transaction type.")
    update_transaction_in_excel(tx_type, idx, updated)
    return {"message": "Transaction updated."}
