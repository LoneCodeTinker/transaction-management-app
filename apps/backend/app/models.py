"""SQLAlchemy ORM models for the Orders Tracking app."""

from sqlalchemy import Column, Integer, String, Float, Date, Boolean, DateTime, ForeignKey, UniqueConstraint, and_
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import date as DateType, datetime
from typing import Optional, Union
from pydantic import BaseModel, field_validator


def normalize_datetime_string(value: Union[str, DateType, datetime]) -> Union[str, DateType, datetime]:
    """
    Normalize various datetime/date string formats to standard ISO format.
    
    Handles:
    - ISO with space separator (SQLite): '2025-06-24 00:00:00' → '2025-06-24'
    - ISO with T separator: '2025-06-24T00:00:00' → '2025-06-24'
    - Date only: '2025-06-24' → unchanged
    - Already parsed objects: passed through unchanged
    
    For date fields, extracts only the date part (YYYY-MM-DD) regardless of time component.
    This allows accepting datetime strings while properly parsing them as dates.
    
    Args:
        value: String or date/datetime object
        
    Returns:
        Normalized date string (YYYY-MM-DD) or original date/datetime object for Pydantic to parse
    """
    if not isinstance(value, str):
        # Already a date/datetime object, let Pydantic handle it
        return value
    
    value = value.strip()
    
    if not value:
        return value
    
    # Extract date part only (first 10 characters in YYYY-MM-DD format)
    # This handles both '2025-06-24' and '2025-06-24T14:30:00' or '2025-06-24 14:30:00'
    if len(value) >= 10:
        # Take first 10 chars if it matches date pattern (YYYY-MM-DD)
        date_part = value[:10]
        if len(date_part) == 10 and date_part[4] == '-' and date_part[7] == '-':
            return date_part
    
    # Return unchanged if format is not recognized
    return value


class SoftDeleteMixin:
    """
    Mixin to add soft delete capability to any model.
    
    Provides:
    - deleted_at: Timestamp when record was deleted (NULL = not deleted)
    - deleted_by: User/system that deleted the record
    - is_deleted: Property to check if record is soft-deleted
    
    Models using this mixin will automatically exclude soft-deleted records
    from queries via the custom SoftDeleteSession.
    """
    deleted_at = Column(DateTime, nullable=True, index=True)
    deleted_by = Column(String, nullable=True)
    
    @property
    def is_deleted(self) -> bool:
        """Check if this record is soft-deleted."""
        return self.deleted_at is not None


# Import Base after SoftDeleteMixin is defined to avoid circular imports
from .database import Base


class ClientDB(SoftDeleteMixin, Base):
    """SQLAlchemy model for clients in the database."""
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    display_name = Column(String, index=True)
    english_name = Column(String, nullable=True)
    arabic_name = Column(String, nullable=True)
    contact_person = Column(String, nullable=True)
    mobile_number = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    orders = relationship("OrderDB", back_populates="client", cascade="all, delete-orphan")


class OrderDB(SoftDeleteMixin, Base):
    """SQLAlchemy model for orders in the database."""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    project_name = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    date = Column(Date)
    placed_by = Column(String, nullable=True)
    mobile_number = Column(String, nullable=True)
    order_total = Column(Float, default=0)
    discount = Column(Float, default=0)
    total_after_discount = Column(Float, default=0)
    vat_total = Column(Float, default=0)
    total_with_vat = Column(Float, default=0)
    status = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    client = relationship("ClientDB", back_populates="orders")
    items = relationship(
        "ItemDB",
        primaryjoin=lambda: and_(ItemDB.order_id == OrderDB.id, ItemDB.deleted_at.is_(None)),
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="select"
    )
    references = relationship(
        "OrderReferenceDB",
        primaryjoin=lambda: and_(OrderReferenceDB.order_id == OrderDB.id, OrderReferenceDB.deleted_at.is_(None)),
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="select"
    )


class ItemDB(SoftDeleteMixin, Base):
    """SQLAlchemy model for order items in the database."""
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    description = Column(String)
    quantity = Column(Float, default=1)
    price = Column(Float, default=0)
    total = Column(Float, default=0)
    per_item_discount = Column(Float, default=0)
    vat = Column(Float, default=0)

    order = relationship("OrderDB", back_populates="items")


class OrderReferenceDB(SoftDeleteMixin, Base):
    """SQLAlchemy model for order references in the database."""
    __tablename__ = "order_references"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    reference_type = Column(String, nullable=False)
    reference_value = Column(String, nullable=False)
    source_system = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    __table_args__ = (UniqueConstraint('order_id', 'reference_type', 'reference_value', name='uq_order_references'),)

    order = relationship("OrderDB", back_populates="references")


class TransactionDB(Base):
    """SQLAlchemy model for transactions in the database."""
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, index=True)  # sales, purchases, expenses, received
    name = Column(String, index=True)  # vendor or customer
    date = Column(Date)
    description = Column(String, nullable=True)
    reference = Column(String, nullable=True)
    amount = Column(Float)
    vat = Column(Float, default=0)
    total = Column(Float)
    method = Column(String, nullable=True)  # Only for received
    notes = Column(String, nullable=True)  # Only for received
    actions = Column(String, nullable=True)  # Comma-separated list
    done = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# Pydantic models for API requests/responses

# Client models
class ClientCreate(BaseModel):
    display_name: str
    english_name: Optional[str] = None
    arabic_name: Optional[str] = None
    contact_person: Optional[str] = None
    mobile_number: Optional[str] = None
    file_path: Optional[str] = None


class ClientUpdate(BaseModel):
    display_name: Optional[str] = None
    english_name: Optional[str] = None
    arabic_name: Optional[str] = None
    contact_person: Optional[str] = None
    mobile_number: Optional[str] = None
    file_path: Optional[str] = None


class Client(BaseModel):
    id: int
    display_name: str
    english_name: Optional[str]
    arabic_name: Optional[str]
    contact_person: Optional[str]
    mobile_number: Optional[str]
    file_path: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def validate_datetime(cls, v):
        """Normalize and validate datetime fields."""
        if v is None:
            return v
        return normalize_datetime_string(v)


# Item models
class ItemCreate(BaseModel):
    id: Optional[int] = None  # For updates: if present, update existing item; if None, create new
    description: str
    quantity: float = 1
    price: float = 0
    per_item_discount: float = 0
    vat: float = 0


class ItemUpdate(BaseModel):
    description: Optional[str] = None
    quantity: Optional[float] = None
    price: Optional[float] = None
    per_item_discount: Optional[float] = None
    vat: Optional[float] = None


class Item(BaseModel):
    id: int
    order_id: int
    description: str
    quantity: float
    price: float
    total: float
    per_item_discount: float
    vat: float

    class Config:
        from_attributes = True


# OrderReference models
class OrderReferenceCreate(BaseModel):
    reference_type: str
    reference_value: str
    source_system: Optional[str] = None


class OrderReference(BaseModel):
    type: str  # Maps to reference_type in DB
    value: str  # Maps to reference_value in DB
    source_system: Optional[str] = None

    class Config:
        from_attributes = True
        
    @classmethod
    def from_orm(cls, obj):
        return cls(
            type=obj.reference_type,
            value=obj.reference_value,
            source_system=obj.source_system
        )


# Order models
class OrderCreate(BaseModel):
    client_id: int
    project_name: Optional[str] = None
    file_path: Optional[str] = None
    date: DateType
    placed_by: Optional[str] = None
    mobile_number: Optional[str] = None
    discount: float = 0
    status: Optional[str] = None
    items: list[ItemCreate] = []
    references: Optional[list[OrderReferenceCreate]] = None

    @field_validator('date', mode='before')
    @classmethod
    def validate_date(cls, v):
        """Normalize and validate date field."""
        return normalize_datetime_string(v)


class StructuredOrderCreate(BaseModel):
    """Order creation with client name lookup instead of client_id."""
    client_name: str
    project_name: Optional[str] = None
    file_path: Optional[str] = None
    date: DateType
    placed_by: Optional[str] = None
    mobile_number: Optional[str] = None
    discount: float = 0
    status: Optional[str] = None
    items: list[ItemCreate] = []
    references: Optional[list[OrderReferenceCreate]] = None

    @field_validator('date', mode='before')
    @classmethod
    def validate_date(cls, v):
        """Normalize and validate date field."""
        return normalize_datetime_string(v)


class OrderUpdate(BaseModel):
    client_name: Optional[str] = None
    project_name: Optional[str] = None
    file_path: Optional[str] = None
    date: Optional[DateType] = None
    placed_by: Optional[str] = None
    mobile_number: Optional[str] = None
    discount: Optional[float] = None
    status: Optional[str] = None
    items: Optional[list[ItemCreate]] = None  # Optional items for smart update
    references: Optional[list[OrderReferenceCreate]] = None

    class Config:
        extra = "forbid"

    @field_validator('date', mode='before')
    @classmethod
    def validate_date(cls, v):
        """Normalize and validate date field."""
        if v is None:
            return v
        return normalize_datetime_string(v)


class Order(BaseModel):
    id: int
    client_id: int
    project_name: Optional[str]
    file_path: Optional[str]
    date: DateType
    placed_by: Optional[str]
    mobile_number: Optional[str]
    order_total: float
    discount: float
    total_after_discount: float
    vat_total: float
    total_with_vat: float
    status: Optional[str]
    created_at: datetime
    updated_at: datetime
    items: list[Item] = []
    references: list[OrderReference] = []

    class Config:
        from_attributes = True

    @field_validator('date', mode='before')
    @classmethod
    def validate_date(cls, v):
        """Normalize and validate date field."""
        if v is None:
            return v
        return normalize_datetime_string(v)

    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def validate_datetime(cls, v):
        """Normalize and validate datetime fields."""
        if v is None:
            return v
        return normalize_datetime_string(v)


class TransactionCreate(BaseModel):
    type: str
    name: str
    date: DateType
    description: Optional[str] = None
    reference: Optional[str] = None
    amount: float
    vat: float = 0
    total: float
    method: Optional[str] = None
    notes: Optional[str] = None
    actions: Optional[list[str]] = None
    done: bool = False

    @field_validator('date', mode='before')
    @classmethod
    def validate_date(cls, v):
        """Normalize and validate date field."""
        return normalize_datetime_string(v)


class TransactionUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[DateType] = None
    description: Optional[str] = None
    reference: Optional[str] = None
    amount: Optional[float] = None
    vat: Optional[float] = None
    total: Optional[float] = None
    method: Optional[str] = None
    notes: Optional[str] = None
    actions: Optional[list[str]] = None
    done: Optional[bool] = None

    @field_validator('date', mode='before')
    @classmethod
    def validate_date(cls, v):
        """Normalize and validate date field."""
        if v is None:
            return v
        return normalize_datetime_string(v)


class Transaction(BaseModel):
    id: int
    type: str
    name: str
    date: DateType
    description: Optional[str]
    reference: Optional[str]
    amount: float
    vat: float
    total: float
    method: Optional[str]
    notes: Optional[str]
    actions: Optional[list[str]]
    done: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator('date', mode='before')
    @classmethod
    def validate_date(cls, v):
        """Normalize and validate date field."""
        if v is None:
            return v
        return normalize_datetime_string(v)

    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def validate_datetime(cls, v):
        """Normalize and validate datetime fields."""
        if v is None:
            return v
        return normalize_datetime_string(v)
