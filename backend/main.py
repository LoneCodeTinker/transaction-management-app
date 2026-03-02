from fastapi import FastAPI, HTTPException, Body, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
from datetime import date, datetime
import logging
from sqlalchemy.orm import Session

from .database import engine, SessionLocal, Base, get_db, init_db
from .models import TransactionDB, TransactionCreate, TransactionUpdate, Transaction


app = FastAPI(title="Orders Tracking API")

# Initialize database
init_db()

# --- Logging Setup ---
logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
# Remove all handlers first to avoid duplicates
if logger.hasHandlers():
    logger.handlers.clear()
# File handler
file_handler = logging.FileHandler("app.log")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
# Stream handler (console)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

# Also attach handlers to uvicorn loggers so uvicorn/fastapi logs appear in console and file
for name in ('uvicorn', 'uvicorn.error', 'uvicorn.access'):
    uv_logger = logging.getLogger(name)
    uv_logger.setLevel(logging.INFO)
    # Clear existing handlers to avoid duplicate messages
    if uv_logger.hasHandlers():
        uv_logger.handlers.clear()
    uv_logger.addHandler(file_handler)
    uv_logger.addHandler(stream_handler)
    uv_logger.propagate = False

# --- Access Log & IP Log Middleware ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    ip = request.client.host
    logging.info(f"Access from IP: {ip}, Path: {request.url.path}, Method: {request.method}")
    response = await call_next(request)
    logging.info(f"Response status: {response.status_code} for {request.url.path} from IP: {ip}")
    return response

# --- Error Logging ---
@app.exception_handler(Exception)
async def log_exceptions(request: Request, exc: Exception):
    logging.error(f"Error for {request.url.path} from IP: {request.client.host}: {exc}")
    return JSONResponse(status_code=500, content={"detail": str(exc)})

# --- Audit Log Helper ---
def audit_log(event: str, user_ip: str = "unknown", details: str = ""):
    logging.info(f"AUDIT: {event} | IP: {user_ip} | {details}")

# Allow frontend to access backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

VALID_TRANSACTION_TYPES = {"sales", "received", "purchases", "expenses"}


# --- Database API Endpoints ---

@app.post("/transaction")
def add_transaction(tx_data: TransactionCreate, db: Session = Depends(get_db)):
    """Create a new transaction."""
    if tx_data.type not in VALID_TRANSACTION_TYPES:
        raise HTTPException(status_code=400, detail="Invalid transaction type.")
    
    # Convert actions list to comma-separated string for storage
    actions_str = ','.join(tx_data.actions) if tx_data.actions else ""
    
    # Audit log
    audit_log("Add Transaction", details=f"Type: {tx_data.type}, Name: {tx_data.name}, Date: {tx_data.date}")
    
    # Create and save transaction
    db_transaction = TransactionDB(
        type=tx_data.type,
        name=tx_data.name,
        date=tx_data.date,
        description=tx_data.description,
        reference=tx_data.reference,
        amount=tx_data.amount,
        vat=tx_data.vat,
        total=tx_data.total,
        method=tx_data.method,
        notes=tx_data.notes,
        actions=actions_str,
        done=tx_data.done
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    
    return {"message": "Transaction saved.", "id": db_transaction.id}


@app.get("/transactions/{tx_type}")
def list_transactions(tx_type: str, db: Session = Depends(get_db)):
    """List all transactions of a specific type."""
    if tx_type not in VALID_TRANSACTION_TYPES:
        raise HTTPException(status_code=400, detail="Invalid transaction type.")
    
    transactions = db.query(TransactionDB).filter(TransactionDB.type == tx_type).all()
    
    # Convert to response format with field names matching frontend expectations
    result = []
    for tx in transactions:
        tx_dict = {
            "id": tx.id,
            "Name": tx.name,
            "Date": tx.date.isoformat() if isinstance(tx.date, date) else tx.date,
            "Description": tx.description,
            "Reference": tx.reference,
            "Amount": tx.amount,
            "VAT": tx.vat,
            "Total": tx.total,
            "Method": tx.method,
            "Notes": tx.notes,
            "Actions": [a for a in (tx.actions or '').split(',') if a],
            "Done": tx.done
        }
        result.append(tx_dict)
    
    return JSONResponse(content=result)


@app.put("/transactions/{tx_type}/{tx_id}")
def update_transaction(tx_type: str, tx_id: int, updated: dict = Body(...), db: Session = Depends(get_db)):
    """Update a specific transaction."""
    if tx_type not in VALID_TRANSACTION_TYPES:
        raise HTTPException(status_code=400, detail="Invalid transaction type.")
    
    # Audit log
    audit_log("Update Transaction", details=f"Type: {tx_type}, ID: {tx_id}")
    
    # Find transaction
    transaction = db.query(TransactionDB).filter(
        TransactionDB.id == tx_id,
        TransactionDB.type == tx_type
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    
    # Update fields
    for key, value in updated.items():
        if key == "actions" and isinstance(value, list):
            setattr(transaction, key, ','.join(value))
        elif hasattr(transaction, key):
            setattr(transaction, key, value)
    
    db.commit()
    db.refresh(transaction)
    
    return {"message": "Transaction updated."}


@app.delete("/transactions/{tx_type}/{tx_id}")
def delete_transaction(tx_type: str, tx_id: int, db: Session = Depends(get_db)):
    """Delete a specific transaction."""
    if tx_type not in VALID_TRANSACTION_TYPES:
        raise HTTPException(status_code=400, detail="Invalid transaction type.")
    
    # Audit log
    audit_log("Delete Transaction", details=f"Type: {tx_type}, ID: {tx_id}")
    
    # Find and delete transaction
    transaction = db.query(TransactionDB).filter(
        TransactionDB.id == tx_id,
        TransactionDB.type == tx_type
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    
    db.delete(transaction)
    db.commit()
    
    return {"message": "Transaction deleted."}
