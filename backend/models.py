"""SQLAlchemy ORM models for the Orders Tracking app."""

from sqlalchemy import Column, Integer, String, Float, Date, Boolean, DateTime
from sqlalchemy.sql import func
from .database import Base
from datetime import date as DateType, datetime
from typing import Optional
from pydantic import BaseModel


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
