from fastapi import FastAPI, HTTPException, Body, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
from datetime import date, datetime
import logging
from sqlalchemy.orm import Session
from sqlalchemy import select, inspect

from .database import engine, SessionLocal, Base, get_db, init_db
from .backup_service import start_scheduler
from .models import (
    TransactionDB, TransactionCreate, TransactionUpdate, Transaction,
    ClientDB, ClientCreate, ClientUpdate, Client,
    OrderDB, OrderCreate, OrderUpdate, Order, StructuredOrderCreate,
    OrderReferenceDB, OrderReference, OrderReferenceCreate,
    ItemDB, ItemCreate, ItemUpdate, Item
)
from .order_service import OrderService


app = FastAPI(title="Orders Tracking API")

# Initialize database
init_db()

# Start backup scheduler
backup_scheduler = start_scheduler()

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
    """Soft-delete a specific client (cascades to orders and items)."""
    audit_log("Delete Client", details=f"ID: {client_id}")

    client = db.query(ClientDB).filter(ClientDB.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")

    # Soft-delete client and cascade to orders/items
    client.deleted_at = datetime.utcnow()
    client.deleted_by = "system"
    
    # Cascade soft-delete to all orders
    for order in client.orders:
        order.deleted_at = datetime.utcnow()
        order.deleted_by = "system"
        # Cascade soft-delete to all items in each order
        for item in order.items:
            item.deleted_at = datetime.utcnow()
            item.deleted_by = "system"
    
    db.commit()

    return {"message": "Client deleted."}


# --- Order Endpoints ---

@app.post("/orders")
def create_order(order_data: OrderCreate, db: Session = Depends(get_db)):
    """Create a new order with items and auto-calculate totals."""
    audit_log("Create Order", details=f"Client ID: {order_data.client_id}, Date: {order_data.date}")
    print(f"Received order creation request at '/orders': {order_data}")

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
        
        # Handle references if provided
        if order_data.references:
            for ref in order_data.references:
                # Check if reference already exists (not soft-deleted)
                existing = db.query(OrderReferenceDB).filter(
                    OrderReferenceDB.order_id == order.id,
                    OrderReferenceDB.reference_type == ref.reference_type,
                    OrderReferenceDB.reference_value == ref.reference_value,
                    OrderReferenceDB.deleted_at.is_(None)
                ).first()
                
                if not existing:
                    new_reference = OrderReferenceDB(
                        order_id=order.id,
                        reference_type=ref.reference_type,
                        reference_value=ref.reference_value,
                        source_system=ref.source_system
                    )
                    db.add(new_reference)
            db.commit()
        
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
        
        # Handle references if provided
        if order_data.references:
            for ref in order_data.references:
                # Check if reference already exists (not soft-deleted)
                existing = db.query(OrderReferenceDB).filter(
                    OrderReferenceDB.order_id == order.id,
                    OrderReferenceDB.reference_type == ref.reference_type,
                    OrderReferenceDB.reference_value == ref.reference_value,
                    OrderReferenceDB.deleted_at.is_(None)
                ).first()
                
                if not existing:
                    new_reference = OrderReferenceDB(
                        order_id=order.id,
                        reference_type=ref.reference_type,
                        reference_value=ref.reference_value,
                        source_system=ref.source_system
                    )
                    db.add(new_reference)
            db.commit()
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
    """Update a specific order with smart item management and recalculate totals.
    including handling of references.
    add the missing feature that's in create_order
    - Accepts client_name for lookup or auto-creation
    - Auto-creates client if name doesn't exist
    """
    audit_log("Update Order", details=f"ID: {order_id}")

    print(order_data.dict()) # debug line to check incoming data
    print(f"Received order update request at '/orders/{order_id}': {order_data}") # debug line to confirm endpoint is hit and data is received

    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    
    # Handle client_name update if provided
    if hasattr(order_data, 'client_name') and order_data.client_name is not None:
        # Compare with current order's client name
        current_client_name = order.client.display_name if order.client else None
        if current_client_name != order_data.client_name:
            # Look up or create client by display_name
            client = db.query(ClientDB).filter(ClientDB.display_name == order_data.client_name).first()
            if not client:
                # Client doesn't exist, create a new one
                client = ClientDB(display_name=order_data.client_name)
                db.add(client)
                db.commit()
                db.refresh(client)
                audit_log("Create Client (Auto)", details=f"Name: {order_data.client_name} (auto-created for order update)")
            order.client_id = client.id  # pyright: ignore
            audit_log("Update Order", details=f"Client ID updated to: {client.id}")

    # Extract items before updating other fields
    items_payload = order_data.items if hasattr(order_data, 'items') and order_data.items is not None else None
    
    # Extract references before updating other fields
    references_payload = order_data.references if hasattr(order_data, 'references') and order_data.references is not None else None
    
    # Update provided non-item, non-reference fields
    update_dict = order_data.dict(exclude_unset=True, exclude={'items', 'references'})
    for key, value in update_dict.items():
        setattr(order, key, value)

    # Smart item management: update existing, create new, delete missing
    if items_payload is not None:
        # 1) Load active items only (exclude soft-deleted)
        active_items = (
            db.query(ItemDB)
            .filter(
                ItemDB.order_id == order_id,
                ItemDB.deleted_at.is_(None)
            )
            .all()
        )
        
        existing_items = {item.id: item for item in active_items}
        payload_ids = set()
        
        # 2) Process payload items
        for item_data in items_payload:
            if item_data.id and item_data.id in existing_items:
                # UPDATE existing item
                db_item = existing_items[item_data.id]
                update_fields = item_data.dict(exclude={'id'}, exclude_unset=True)
                for key, value in update_fields.items():
                    setattr(db_item, key, value)
                payload_ids.add(item_data.id)
            else:
                # CREATE new item (no id or id not found in active items)
                if item_data.description.strip():
                    new_item = ItemDB(
                        order_id=order_id,
                        description=item_data.description,
                        quantity=item_data.quantity,
                        price=item_data.price,
                        per_item_discount=item_data.per_item_discount,
                        vat=item_data.vat
                    )
                    db.add(new_item)
        
        # 3) Soft-delete items missing from payload
        for item_id, db_item in existing_items.items():
            if item_id not in payload_ids:
                db_item.deleted_at = datetime.utcnow()
                db_item.deleted_by = "system"

    # Smart reference management: only delete what's removed, only create what's new
    if references_payload is not None:
        # Get all active references
        active_references = (
            db.query(OrderReferenceDB)
            .filter(
                OrderReferenceDB.order_id == order_id,
                OrderReferenceDB.deleted_at.is_(None)
            )
            .all()
        )
        
        # Create set of payload reference keys (type, value)
        payload_keys = {(ref.reference_type, ref.reference_value) for ref in references_payload}
        # active_keys = {(ref.reference_type, ref.reference_value) for ref in active_references}
        
        # Soft-delete active references not in payload
        for ref in active_references:
            ref_key = (ref.reference_type, ref.reference_value)
            if ref_key not in payload_keys:
                ref.deleted_at = datetime.utcnow()
                ref.deleted_by = "system"
        
        # db.flush()
                    
        # Process references in payload: restore deleted or insert new
        for ref_data in references_payload:
            ref_key = (ref_data.reference_type, ref_data.reference_value)
            
            # Check if reference exists (including soft-deleted)
            """ existing = db.query(OrderReferenceDB).filter(
                OrderReferenceDB.order_id == order_id,
                OrderReferenceDB.reference_type == ref_data.reference_type,
                OrderReferenceDB.reference_value == ref_data.reference_value
            ).first() """

            stmt = select(OrderReferenceDB).where(
                OrderReferenceDB.order_id == order_id,
                OrderReferenceDB.reference_type == ref_data.reference_type,
                OrderReferenceDB.reference_value == ref_data.reference_value
            )

            existing = db.execute(stmt).scalars().first()

            print("Existing found:", existing)

            if existing:
                # Restore if deleted, skip if active
                if existing.deleted_at is not None:
                    existing.deleted_at = None
                    existing.deleted_by = None
                """ elif ref_key not in active_keys:
                    # Only insert if not already in active set
                    new_reference = OrderReferenceDB(
                        order_id=order_id,
                        reference_type=ref_data.reference_type,
                        reference_value=ref_data.reference_value,
                        source_system=ref_data.source_system
                    )
                    db.add(new_reference) """
            
            else:
                new_reference = OrderReferenceDB(
                    order_id=order_id,
                    reference_type=ref_data.reference_type,
                    reference_value=ref_data.reference_value,
                    source_system=ref_data.source_system
                )
                db.add(new_reference)

    # Recalculate totals with final item set
    # order.items is now in sync with database state, so totals will be correct
    OrderService.calculate_order_totals(order)

    db.commit()
    db.refresh(order)

    return {"message": "Order updated."}


@app.delete("/orders/{order_id}")
def delete_order(order_id: int, db: Session = Depends(get_db)):
    """Soft-delete a specific order (cascades to items)."""
    audit_log("Delete Order", details=f"ID: {order_id}")

    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    # Soft-delete order and cascade to items
    order.deleted_at = datetime.utcnow()
    order.deleted_by = "system"
    for item in order.items:
        item.deleted_at = datetime.utcnow()
        item.deleted_by = "system"
    
    db.commit()

    return {"message": "Order deleted."}


@app.post("/orders/{order_id}/items")
def add_order_item(order_id: int, item_data: ItemCreate, db: Session = Depends(get_db)):
    """Add an item to an existing order and recalculate totals."""
    audit_log("Add Order Item", details=f"Order ID: {order_id}")

    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    # Exclude id field when creating new item
    db_item = ItemDB(
        order_id=order_id,
        description=item_data.description,
        quantity=item_data.quantity,
        price=item_data.price,
        per_item_discount=item_data.per_item_discount,
        vat=item_data.vat
    )
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
    """Soft-delete an item from an order and recalculate totals."""
    audit_log("Delete Order Item", details=f"Order ID: {order_id}, Item ID: {item_id}")

    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    item = db.query(ItemDB).filter(ItemDB.id == item_id, ItemDB.order_id == order_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found.")

    # Soft-delete item
    item.deleted_at = datetime.utcnow()
    item.deleted_by = "system"

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
