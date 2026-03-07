"""OrderService - Centralizes order creation logic including parsing, validation, and persistence."""

import re
from typing import Optional, Tuple, List, Dict
from sqlalchemy.orm import Session
from .models import OrderDB, ItemDB, ClientDB


class OrderService:
    """Service layer for order management operations."""

    @staticmethod
    def parse_serialized_description(description: str) -> Tuple[List[Dict], float]:
        """
        Parse serialized description string into items and discount.
        
        Format: #1: Item Name | Qty: 10 | Price: 50 | Total: 500 | VAT: 75; 
                #2: Item Name 2 | Qty: 5 | Price: 100 | Total: 500 | VAT: 75; 
                Discount: 100
        
        Args:
            description: Serialized description string
            
        Returns:
            Tuple of (items list, discount amount)
        """
        if not description:
            return [], 0.0

        parts = description.split(';')
        parts = [s.strip() for s in parts if s.strip()]

        discount = 0.0
        # Check if last part is discount
        if parts and re.match(r'^Discount:', parts[-1], re.IGNORECASE):
            match = re.match(r'^Discount:\s*([\d.]+)', parts[-1], re.IGNORECASE)
            if match:
                discount = float(match.group(1))
            parts.pop()

        items = []
        pattern = r'#\d+:\s*(.*?)\s*\|\s*Qty:\s*(\d+)\s*\|\s*Price:\s*([\d.]+)\s*\|\s*Total:\s*([\d.]+)\s*\|\s*VAT:\s*([\d.]+)'

        for item_str in parts:
            match = re.match(pattern, item_str, re.IGNORECASE)
            if match:
                items.append({
                    'description': match.group(1).strip(),
                    'quantity': int(match.group(2)),
                    'price': float(match.group(3)),
                    'total': float(match.group(4)),
                    'vat': float(match.group(5)),
                    'per_item_discount': 0.0
                })
            else:
                # Fallback: treat as plain description
                items.append({
                    'description': item_str.strip(),
                    'quantity': 1,
                    'price': 0.0,
                    'total': 0.0,
                    'vat': 0.0,
                    'per_item_discount': 0.0
                })

        return items, discount

    @staticmethod
    def calculate_item_total(quantity: float, price: float) -> float:
        """Calculate item total = quantity × price."""
        return quantity * price

    @staticmethod
    def calculate_order_totals(order: OrderDB) -> None:
        """
        Calculate and update order totals based on items.
        
        Updates:
        - item.total for each item
        - order.order_total (sum of all item totals)
        - order.total_after_discount (order_total - discount - per_item_discounts)
        - order.vat_total (sum of all item VATs)
        - order.total_with_vat (total_after_discount + vat_total)
        """
        order_total = 0.0
        total_item_discounts = 0.0
        vat_total = 0.0

        for item in order.items:
            item.total = OrderService.calculate_item_total(item.quantity, item.price)
            order_total += item.total
            total_item_discounts += item.per_item_discount
            vat_total += item.vat

        order.order_total = order_total  # pyright: ignore
        order.total_after_discount = order_total - order.discount - total_item_discounts  # pyright: ignore
        order.vat_total = vat_total  # pyright: ignore
        order.total_with_vat = order.total_after_discount + vat_total  # pyright: ignore

    @staticmethod
    def create_order(
        db: Session,
        client_id: int,
        project_name: Optional[str],
        file_path: Optional[str],
        date,
        placed_by: Optional[str],
        mobile_number: Optional[str],
        discount: float,
        status: Optional[str],
        items: List[Dict],
        serialized_description: Optional[str] = None
    ) -> OrderDB:
        """
        Create an order with items in a database transaction.
        
        Responsibilities:
        - Verify client exists
        - Parse serialized description if provided
        - Create order and item records
        - Calculate totals
        - Persist in database transaction
        
        Args:
            db: Database session
            client_id: Client ID (must exist)
            project_name: Optional project name
            file_path: Optional file path
            date: Order date
            placed_by: Person placing order (defaults to client contact person)
            mobile_number: Mobile number (defaults to client mobile)
            discount: Order-level discount
            status: Order status
            items: List of item dictionaries
            serialized_description: Optional serialized format for parsing items
            
        Returns:
            Created OrderDB instance
            
        Raises:
            ValueError: If client not found or parsing fails
        """
        # Verify client exists
        client = db.query(ClientDB).filter(ClientDB.id == client_id).first()
        if not client:
            raise ValueError("Client not found.")

        # Parse serialized description if provided
        if serialized_description:
            items, parsed_discount = OrderService.parse_serialized_description(serialized_description)
            if parsed_discount > 0:
                discount = parsed_discount

        # Set defaults from client if not provided
        placed_by = placed_by or client.contact_person
        mobile_number = mobile_number or client.mobile_number

        # Create order
        order = OrderDB(
            client_id=client_id,
            project_name=project_name,
            file_path=file_path,
            date=date,
            placed_by=placed_by,
            mobile_number=mobile_number,
            discount=discount,
            status=status
        )

        # Create and add items
        for item_data in items:
            item = ItemDB(
                description=item_data.get('description', ''),
                quantity=item_data.get('quantity', 1),
                price=item_data.get('price', 0),
                per_item_discount=item_data.get('per_item_discount', 0),
                vat=item_data.get('vat', 0)
            )
            order.items.append(item)

        # Calculate totals
        OrderService.calculate_order_totals(order)

        # Save to database in transaction
        db.add(order)
        db.commit()
        db.refresh(order)

        return order
