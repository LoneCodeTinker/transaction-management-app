from fastapi import FastAPI, HTTPException, Body, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
from datetime import date, datetime
import logging
from sqlalchemy.orm import Session

from .database import engine, SessionLocal, Base, get_db, init_db
from .models import (
    TransactionDB, TransactionCreate, TransactionUpdate, Transaction,
    ClientDB, ClientCreate, ClientUpdate, Client,
    OrderDB, OrderCreate, OrderUpdate, Order, StructuredOrderCreate,
    ItemDB, ItemCreate, ItemUpdate, Item
)
from .order_service import OrderService


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
    ip = request.client.host if request.client else "unknown"  # pyright: ignore
    logging.info(f"Access from IP: {ip}, Path: {request.url.path}, Method: {request.method}")
    response = await call_next(request)
    logging.info(f"Response status: {response.status_code} for {request.url.path} from IP: {ip}")
    return response

# --- Error Logging ---
@app.exception_handler(Exception)
async def log_exceptions(request: Request, exc: Exception):
    ip = request.client.host if request.client else "unknown"  # pyright: ignore
    logging.error(f"Error for {request.url.path} from IP: {ip}: {exc}")
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


# --- Client Endpoints ---

@app.post("/clients")
def create_client(client_data: ClientCreate, db: Session = Depends(get_db)):
    """Create a new client."""
    audit_log("Create Client", details=f"Name: {client_data.display_name}")

    db_client = ClientDB(**client_data.dict())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)

    return {"message": "Client created.", "id": db_client.id}


@app.get("/clients")
def list_clients(db: Session = Depends(get_db)):
    """List all clients."""
    clients = db.query(ClientDB).all()
    return clients


@app.get("/clients/{client_id}")
def get_client(client_id: int, db: Session = Depends(get_db)):
    """Get a specific client."""
    client = db.query(ClientDB).filter(ClientDB.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")
    return client


@app.put("/clients/{client_id}")
def update_client(client_id: int, client_data: ClientUpdate, db: Session = Depends(get_db)):
    """Update a specific client."""
    audit_log("Update Client", details=f"ID: {client_id}")

    client = db.query(ClientDB).filter(ClientDB.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")

    for key, value in client_data.dict(exclude_unset=True).items():
        setattr(client, key, value)

    db.commit()
    db.refresh(client)

    return {"message": "Client updated."}


@app.delete("/clients/{client_id}")
def delete_client(client_id: int, db: Session = Depends(get_db)):
    """Delete a specific client (cascades to orders and items)."""
    audit_log("Delete Client", details=f"ID: {client_id}")

    client = db.query(ClientDB).filter(ClientDB.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")

    db.delete(client)
    db.commit()

    return {"message": "Client deleted."}


# --- Order Endpoints ---

@app.post("/orders")
def create_order(order_data: OrderCreate, db: Session = Depends(get_db)):
    """Create a new order with items and auto-calculate totals."""
    audit_log("Create Order", details=f"Client ID: {order_data.client_id}, Date: {order_data.date}")

    try:
        order = OrderService.create_order(
            db=db,
            client_id=order_data.client_id,
            project_name=order_data.project_name,
            file_path=order_data.file_path,
            date=order_data.date,
            placed_by=order_data.placed_by,
            mobile_number=order_data.mobile_number,
            discount=order_data.discount,
            status=order_data.status,
            items=[item.dict() for item in order_data.items]
        )
        return {"message": "Order created.", "id": order.id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/orders/structured")
def create_order_structured(order_data: StructuredOrderCreate, db: Session = Depends(get_db)):
    """
    Create a new order with structured item array and client name lookup.
    
    Unlike POST /orders which requires client_id, this endpoint:
    - Accepts client_name for lookup or auto-creation
    - Accepts items as structured array instead of serialized string
    - Auto-creates client if name doesn't exist
    """
    audit_log("Create Order (Structured)", details=f"Client Name: {order_data.client_name}, Date: {order_data.date}")

    try:
        # Look up or create client by display_name
        client = db.query(ClientDB).filter(ClientDB.display_name == order_data.client_name).first()
        if not client:
            # Client doesn't exist, create a new one
            client = ClientDB(display_name=order_data.client_name)
            db.add(client)
            db.commit()
            db.refresh(client)
            audit_log("Create Client (Auto)", details=f"Name: {order_data.client_name} (auto-created for order)")

        # Use OrderService to create order
        order = OrderService.create_order(
            db=db,
            client_id=int(client.id),  # pyright: ignore
            project_name=order_data.project_name,
            file_path=order_data.file_path,
            date=order_data.date,
            placed_by=order_data.placed_by,
            mobile_number=order_data.mobile_number,
            discount=order_data.discount,
            status=order_data.status,
            items=[item.dict() for item in order_data.items]
        )
        return {"message": "Order created.", "id": order.id, "client_id": order.client_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/orders")
def list_orders(db: Session = Depends(get_db)):
    """List all orders with client names and structured items."""
    orders = db.query(OrderDB).all()
    
    # Transform to response format with client names and items
    result = []
    for order in orders:
        client_name = order.client.display_name if order.client else "Unknown"
        order_dict = {
            "id": order.id,
            "client_id": order.client_id,
            "Name": client_name,
            "Date": order.date.isoformat() if isinstance(order.date, date) else order.date,
            "project_name": order.project_name,
            "placed_by": order.placed_by,
            "mobile_number": order.mobile_number,
            "order_total": order.order_total,
            "discount": order.discount,
            "total_after_discount": order.total_after_discount,
            "vat_total": order.vat_total,
            "total_with_vat": order.total_with_vat,
            "status": order.status,
            "items": [
                {
                    "id": item.id,
                    "order_id": item.order_id,
                    "description": item.description,
                    "quantity": item.quantity,
                    "price": item.price,
                    "total": item.total,
                    "per_item_discount": item.per_item_discount,
                    "vat": item.vat
                }
                for item in order.items
            ],
            "created_at": order.created_at.isoformat() if isinstance(order.created_at, datetime) else order.created_at,
            "updated_at": order.updated_at.isoformat() if isinstance(order.updated_at, datetime) else order.updated_at,
        }
        result.append(order_dict)
    
    return JSONResponse(content=result)


@app.get("/orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    """Get a specific order with client names and structured items."""
    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    
    client_name = order.client.display_name if order.client else "Unknown"
    order_dict = {
        "id": order.id,
        "client_id": order.client_id,
        "Name": client_name,
        "Date": order.date.isoformat() if isinstance(order.date, date) else order.date,
        "project_name": order.project_name,
        "placed_by": order.placed_by,
        "mobile_number": order.mobile_number,
        "order_total": order.order_total,
        "discount": order.discount,
        "total_after_discount": order.total_after_discount,
        "vat_total": order.vat_total,
        "total_with_vat": order.total_with_vat,
        "status": order.status,
        "items": [
            {
                "id": item.id,
                "order_id": item.order_id,
                "description": item.description,
                "quantity": item.quantity,
                "price": item.price,
                "total": item.total,
                "per_item_discount": item.per_item_discount,
                "vat": item.vat
            }
            for item in order.items
        ],
        "created_at": order.created_at.isoformat() if isinstance(order.created_at, datetime) else order.created_at,
        "updated_at": order.updated_at.isoformat() if isinstance(order.updated_at, datetime) else order.updated_at,
    }
    return JSONResponse(content=order_dict)


@app.get("/clients/{client_id}/orders")
def get_client_orders(client_id: int, db: Session = Depends(get_db)):
    """Get all orders for a specific client with structured items."""
    client = db.query(ClientDB).filter(ClientDB.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")

    orders = db.query(OrderDB).filter(OrderDB.client_id == client_id).all()
    
    # Transform to response format with client names and items
    result = []
    for order in orders:
        order_dict = {
            "id": order.id,
            "client_id": order.client_id,
            "Name": client.display_name,
            "Date": order.date.isoformat() if isinstance(order.date, date) else order.date,
            "project_name": order.project_name,
            "placed_by": order.placed_by,
            "mobile_number": order.mobile_number,
            "order_total": order.order_total,
            "discount": order.discount,
            "total_after_discount": order.total_after_discount,
            "vat_total": order.vat_total,
            "total_with_vat": order.total_with_vat,
            "status": order.status,
            "items": [
                {
                    "id": item.id,
                    "order_id": item.order_id,
                    "description": item.description,
                    "quantity": item.quantity,
                    "price": item.price,
                    "total": item.total,
                    "per_item_discount": item.per_item_discount,
                    "vat": item.vat
                }
                for item in order.items
            ],
            "created_at": order.created_at.isoformat() if isinstance(order.created_at, datetime) else order.created_at,
            "updated_at": order.updated_at.isoformat() if isinstance(order.updated_at, datetime) else order.updated_at,
        }
        result.append(order_dict)
    
    return JSONResponse(content=result)


@app.put("/orders/{order_id}")
def update_order(order_id: int, order_data: OrderUpdate, db: Session = Depends(get_db)):
    """Update a specific order and recalculate totals."""
    audit_log("Update Order", details=f"ID: {order_id}")

    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    # Update provided fields
    for key, value in order_data.dict(exclude_unset=True).items():
        setattr(order, key, value)

    # Recalculate totals
    OrderService.calculate_order_totals(order)

    db.commit()
    db.refresh(order)

    return {"message": "Order updated."}


@app.delete("/orders/{order_id}")
def delete_order(order_id: int, db: Session = Depends(get_db)):
    """Delete a specific order (cascades to items)."""
    audit_log("Delete Order", details=f"ID: {order_id}")

    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    db.delete(order)
    db.commit()

    return {"message": "Order deleted."}


@app.post("/orders/{order_id}/items")
def add_order_item(order_id: int, item_data: ItemCreate, db: Session = Depends(get_db)):
    """Add an item to an existing order and recalculate totals."""
    audit_log("Add Order Item", details=f"Order ID: {order_id}")

    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    db_item = ItemDB(**item_data.dict(), order_id=order_id)
    db.add(db_item)

    # Recalculate order totals
    order.items.append(db_item)
    OrderService.calculate_order_totals(order)

    db.commit()
    db.refresh(order)

    return {"message": "Item added.", "order_id": order_id, "item_id": db_item.id}


@app.put("/orders/{order_id}/items/{item_id}")
def update_order_item(order_id: int, item_id: int, item_data: ItemUpdate, db: Session = Depends(get_db)):
    """Update an item in an order and recalculate totals."""
    audit_log("Update Order Item", details=f"Order ID: {order_id}, Item ID: {item_id}")

    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    item = db.query(ItemDB).filter(ItemDB.id == item_id, ItemDB.order_id == order_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found.")

    # Update item fields
    for key, value in item_data.dict(exclude_unset=True).items():
        setattr(item, key, value)

    # Recalculate order totals
    OrderService.calculate_order_totals(order)

    db.commit()
    db.refresh(order)

    return {"message": "Item updated."}


@app.delete("/orders/{order_id}/items/{item_id}")
def delete_order_item(order_id: int, item_id: int, db: Session = Depends(get_db)):
    """Delete an item from an order and recalculate totals."""
    audit_log("Delete Order Item", details=f"Order ID: {order_id}, Item ID: {item_id}")

    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    item = db.query(ItemDB).filter(ItemDB.id == item_id, ItemDB.order_id == order_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found.")

    db.delete(item)

    # Recalculate order totals
    OrderService.calculate_order_totals(order)

    db.commit()

    return {"message": "Item deleted."}


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
        elif key == "date" and isinstance(value, str):
            # Convert string date to date object
            try:
                setattr(transaction, key, datetime.strptime(value, "%Y-%m-%d").date())
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail=f"Invalid date format for {key}. Use YYYY-MM-DD.")
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
