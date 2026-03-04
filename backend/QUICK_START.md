# Database Schema Update - Quick Start

## File Changes

**Modified Files:**
1. `backend/models.py` - Added 3 new database tables + Pydantic models
2. `backend/main.py` - Added 16 new API endpoints + calculations

**New Files:**
1. `backend/migrate.py` - Database migration runner
2. `backend/migrations.py` - Migration status checker
3. `backend/API_DOCUMENTATION.md` - Complete endpoint reference
4. `backend/IMPLEMENTATION_SUMMARY.md` - Detailed documentation
5. `backend/CHECKLIST.md` - Implementation checklist

## Initialize Database

```bash
# Navigate to project root
cd c:\Users\Design5\Documents\Py Projects\Orders Tracking

# Run migration
python -m backend.migrate
```

Expected output:
```
Starting database migration...
✓ Database migration completed successfully.
✓ Created/Updated tables:
  - clients
  - orders
  - items
  - transactions
```

## Start Backend

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8001
```

## Test Create Client

```bash
curl -X POST http://localhost:8001/clients \
  -H "Content-Type: application/json" \
  -d "{
    \"display_name\": \"ABC Company\",
    \"english_name\": \"ABC Company Ltd\",
    \"contact_person\": \"John Doe\",
    \"mobile_number\": \"+966501234567\"
  }"
```

Response:
```json
{
  "message": "Client created.",
  "id": 1
}
```

## Test Create Order with Items

```bash
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d "{
    \"client_id\": 1,
    \"project_name\": \"Project Alpha\",
    \"date\": \"2026-03-03\",
    \"discount\": 100.00,
    \"items\": [
      {
        \"description\": \"Product A\",
        \"quantity\": 10,
        \"price\": 50.00,
        \"per_item_discount\": 5.00,
        \"vat\": 15.00
      },
      {
        \"description\": \"Product B\",
        \"quantity\": 5,
        \"price\": 100.00,
        \"per_item_discount\": 0,
        \"vat\": 25.00
      }
    ]
  }"
```

Response:
```json
{
  "message": "Order created.",
  "id": 1
}
```

## Test Get Order (with auto-calculated totals)

```bash
curl http://localhost:8000/orders/1
```

Response:
```json
{
  "id": 1,
  "client_id": 1,
  "project_name": "Project Alpha",
  "date": "2026-03-03",
  "placed_by": "John Doe",
  "mobile_number": "+966501234567",
  "order_total": 1000.00,
  "discount": 100.00,
  "total_after_discount": 855.00,
  "vat_total": 40.00,
  "total_with_vat": 895.00,
  "status": null,
  "items": [...]
}
```

## Key Features

✓ **Auto-Calculations**: All totals calculated server-side
✓ **Cascading Deletes**: Delete client → deletes orders → deletes items
✓ **Default Values**: placed_by and mobile_number default from client
✓ **Relationships**: Client → Orders → Items with proper foreign keys
✓ **Audit Logging**: All operations logged to app.log
✓ **Backward Compatible**: Existing transaction endpoints unchanged

## Complete API Reference

See `backend/API_DOCUMENTATION.md` for:
- All endpoint definitions
- Request/response examples
- Calculation logic
- Error handling
- Cascade delete behavior

## Detailed Documentation

See `backend/IMPLEMENTATION_SUMMARY.md` for:
- Complete change log
- Database schema details
- Helper function explanations
- Testing instructions
- Troubleshooting guide
- Next steps for enhancement

## All Endpoints

**Clients**: POST, GET, GET/:id, PUT/:id, DELETE/:id
**Orders**: POST, GET, GET/:id, GET/:client_id/orders, PUT/:id, DELETE/:id
**Items**: POST /:order_id/items, PUT /:order_id/items/:id, DELETE /:order_id/items/:id

Total: 16 new endpoints + existing transaction endpoints

## Support

- Check API_DOCUMENTATION.md for endpoint details
- Check IMPLEMENTATION_SUMMARY.md for architecture details
- Check app.log for audit trail
- All endpoints are CORS-enabled
