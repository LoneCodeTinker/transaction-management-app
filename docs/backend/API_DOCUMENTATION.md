# Orders Management API - Endpoint Documentation

## Client Endpoints

### Create Client
```
POST /clients
```
Request body:
```json
{
  "display_name": "ABC Company",
  "english_name": "ABC Company Ltd",
  "arabic_name": "شركة ايه بي سي",
  "contact_person": "John Doe",
  "mobile_number": "+966501234567",
  "file_path": "/path/to/client/files"
}
```

### List All Clients
```
GET /clients
```

### Get Specific Client
```
GET /clients/{client_id}
```

### Update Client
```
PUT /clients/{client_id}
```
Request body (all fields optional):
```json
{
  "display_name": "Updated Name",
  "contact_person": "Jane Doe",
  "mobile_number": "+966509876543"
}
```

### Delete Client
```
DELETE /clients/{client_id}
```
Note: Cascades delete to all orders and items

---

## Order Endpoints

### Create Order
```
POST /orders
```
Request body:
```json
{
  "client_id": 1,
  "project_name": "Project Alpha",
  "file_path": "/orders/alpha",
  "date": "2026-03-03",
  "placed_by": "John Doe",
  "mobile_number": "+966501234567",
  "discount": 100.00,
  "status": "pending",
  "items": [
    {
      "description": "Item 1",
      "quantity": 10,
      "price": 50.00,
      "per_item_discount": 5.00,
      "vat": 15.00
    },
    {
      "description": "Item 2",
      "quantity": 5,
      "price": 100.00,
      "per_item_discount": 0,
      "vat": 25.00
    }
  ]
}
```

### List All Orders
```
GET /orders
```

### Get Specific Order
```
GET /orders/{order_id}
```
Returns order with calculated totals:
```json
{
  "id": 1,
  "client_id": 1,
  "project_name": "Project Alpha",
  "order_total": 1000.00,
  "discount": 100.00,
  "total_after_discount": 855.00,
  "vat_total": 40.00,
  "total_with_vat": 895.00,
  "status": "pending",
  "items": [...]
}
```

### Get Orders for Specific Client
```
GET /clients/{client_id}/orders
```

### Update Order
```
PUT /orders/{order_id}
```
Request body (all fields optional):
```json
{
  "project_name": "Updated Project",
  "discount": 150.00,
  "status": "completed"
}
```
Note: Totals are recalculated automatically

### Delete Order
```
DELETE /orders/{order_id}
```
Note: Cascades delete to all items

---

## Order Item Endpoints

### Add Item to Order
```
POST /orders/{order_id}/items
```
Request body:
```json
{
  "description": "New Item",
  "quantity": 5,
  "price": 75.00,
  "per_item_discount": 2.50,
  "vat": 20.00
}
```

### Update Order Item
```
PUT /orders/{order_id}/items/{item_id}
```
Request body (all fields optional):
```json
{
  "quantity": 8,
  "price": 80.00,
  "per_item_discount": 3.00
}
```
Note: Parent order totals are recalculated automatically

### Delete Order Item
```
DELETE /orders/{order_id}/items/{item_id}
```
Note: Parent order totals are recalculated automatically

---

## Calculation Logic

All calculations are performed automatically:

- **Item Total**: `quantity × price`
- **Order Total**: `SUM(all items.total)`
- **Total Item Discounts**: `SUM(items.per_item_discount)`
- **Total After Discount**: `order_total - discount - total_item_discounts`
- **VAT Total**: `SUM(items.vat)`
- **Total With VAT**: `total_after_discount + vat_total`

## Default Values

- If `order.placed_by` is not provided, defaults to `client.contact_person`
- If `order.mobile_number` is not provided, defaults to `client.mobile_number`

## HTTP Status Codes

- **200 OK**: Successful GET request
- **201 Created**: Successful POST request
- **204 No Content**: Successful DELETE request
- **400 Bad Request**: Invalid input
- **404 Not Found**: Resource not found
- **500 Internal Server Error**: Server error

## Error Response Format

```json
{
  "detail": "Error message"
}
```

## Cascade Delete Behavior

- Deleting a **Client** deletes all associated **Orders** and **Items**
- Deleting an **Order** deletes all associated **Items**
- Deleting an **Item** does NOT delete the parent Order (order remains)
