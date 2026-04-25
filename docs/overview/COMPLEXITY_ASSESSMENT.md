# Implementation Complexity Assessment
## Soft Delete System + Automated Database Backup

**Assessment Date:** March 14, 2026  
**Author:** Architecture Analysis  
**Status:** Analysis Only (No Code Changes)

---

## Executive Summary

| Feature | Complexity | Risk Level | Implementation Effort |
|---------|-----------|-----------|----------------------|
| **Soft Delete System** | **Moderate** | **Medium-High** | **4-6 hours** |
| **Automated Backups** | **Low** | **Low** | **1-2 hours** |
| **Combined Implementation** | **Moderate** | **Medium** | **5-8 hours** |

**Recommendation:** ✅ **Can be implemented safely together**  
**Suggested Order:** 1) Backups first (isolated), 2) Soft Delete (requires broader changes)

---

## Part 1: SOFT DELETE SYSTEM Evaluation

### 1.1 Current Delete Operations (Scope: clients, orders, items)

**Files Affected:** `backend/main.py`, `backend/order_service.py`

| Operation | Endpoint | Current Behavior | Affected Records |
|-----------|----------|------------------|------------------|
| Delete Client | `DELETE /clients/{client_id}` | Hard delete + cascade | clients + orders + items |
| Delete Order | `DELETE /orders/{order_id}` | Hard delete + cascade | orders + items |
| Delete Order Item | `DELETE /orders/{order_id}/items/{item_id}` | Hard delete | items only |
| Delete Item (during update) | PUT `/orders/{order_id}` | Hard delete (item management) | items only |

**Location Details:**
- Line 143: `db.delete(client)` - Hard delete client
- Line 406: `db.delete(item_to_delete)` - Delete items during order update
- Line 427: `db.delete(order)` - Hard delete order
- Line 502: `db.delete(item)` - Hard delete single item

---

### 1.2 Required Schema Changes

**For Each Table (clients, orders, items):**

| Column | Type | Nullable | Purpose |
|--------|------|----------|---------|
| `deleted_at` | DATETIME | NULL | Timestamp when record was deleted |
| `deleted_by` | TEXT | NULL | User/system that deleted the record |

**Schema Modification Complexity:** ⭐ **Very Low**
- Simple column additions
- No type conversions needed
- No foreign key changes required
- Existing `created_at`, `updated_at` columns already in place

**Migration Files Affected:**
- `backend/models.py` - Add columns to ClientDB, OrderDB, ItemDB
- `backend/migrate.py` - Document new columns

---

### 1.3 Query Filtering Analysis

**Current Query Locations:** 25+ queries across 2 main files

**ClientDB Queries Needing Soft Delete Filter:**
```
Location                          Usage                    Type
─────────────────────────────────────────────────────────────
main.py:103                       list_clients()           All clients
main.py:110                       get_client()             Single client
main.py:121                       update_client()          Single client
main.py:139                       delete_client()          Single client
main.py:188                       create_order_structured()  Client lookup
order_service.py:144              create_order()           Client validation
```

**OrderDB Queries Needing Soft Delete Filter:**
```
Location                    Usage                        Type
──────────────────────────────────────────────────────────
main.py:218                 list_orders()                All orders
main.py:262                 get_order()                  Single order
main.py:307                 get_client_orders()          Orders by client
main.py:352                 update_order()               Single order
main.py:374                 update_order()               Find existing items
main.py:423                 delete_order()               Single order
main.py:438                 add_order_item()             Single order
main.py:468                 update_order_item()          Single order
main.py:494                 delete_order_item()          Single order
```

**ItemDB Queries Needing Soft Delete Filter:**
```
Location                    Usage                        Type
──────────────────────────────────────────────────────────
main.py:374                 update_order()               Find item by ID
main.py:472                 update_order_item()          Find item
main.py:498                 delete_order_item()          Find item
```

**Total Query Updates Required:** ~23-25 queries

---

### 1.4 Implementation Strategy

#### Phase 1: Database Setup (Low Effort)
1. Add `deleted_at` (DateTime, nullable) column to models
2. Add `deleted_by` (String, nullable) column to models
3. Add index on `deleted_at` for performance
4. Create migration for existing database

**Estimated Effort:** 30 minutes

#### Phase 2: Replace Hard Deletes with Soft Deletes (Medium Effort)
Replace all `db.delete()` calls with soft delete logic:

```python
# Current: db.delete(client)
# New:
client.deleted_at = datetime.utcnow()
client.deleted_by = request.headers.get("X-User-ID", "system")
db.commit()
```

**Locations to Modify:**
- Line 143: Delete client → soft delete
- Line 406: Delete item during update → soft delete
- Line 427: Delete order → soft delete
- Line 502: Delete item → soft delete

**Also handle cascades:**
- When deleting client → soft delete associated orders
- When deleting order → soft delete associated items

**Estimated Effort:** 1.5 hours

#### Phase 3: Update All Queries (Medium-High Effort)
Add `WHERE deleted_at IS NULL` filter to all 23-25 queries.

**Implementation Options:**

**Option A: Decorator Approach (Recommended - reduces code duplication)**
```python
def filter_soft_deleted(query, model):
    """Apply soft delete filter to query"""
    return query.filter(model.deleted_at.is_(None))
```

Use in queries:
```python
# Current: db.query(ClientDB).all()
# New:
clients = filter_soft_deleted(db.query(ClientDB), ClientDB).all()
```

**Option B: Global Query Filter (Advanced - via SQLAlchemy events)**
Use SQLAlchemy event listeners to auto-filter all queries
- More elegant but requires event handler setup
- Could inadvertently filter admin/audit queries

**Estimated Effort with Option A:** 2-3 hours

#### Phase 4: Update Relationships (Low Effort)
Ensure cascade behavior works with soft deletes:
- When deleting order, soft delete its items
- When deleting client, soft delete its orders + items

```python
# In delete_client():
for order in client.orders:
    order.deleted_at = datetime.utcnow()
    for item in order.items:
        item.deleted_at = datetime.utcnow()
```

**Estimated Effort:** 30 minutes

---

### 1.5 Soft Delete Implementation Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **Queries returning deleted records** | **HIGH** | Add filter to every `.all()` and `.first()` query - requires discipline |
| **Stale relationships** | **MEDIUM** | Orders with deleted items still reference them - handle in OrderService.calculate_order_totals() |
| **Client lookup failures** | **MEDIUM** | `create_order_structured()` looks up client by name - must check `deleted_at IS NULL` |
| **Admin audit recovery** | **LOW** | Can implement separate "undelete" endpoint if needed later |
| **Data validation in OrderService** | **MEDIUM** | Verify OrderService doesn't count deleted items in totals |
| **Backward compatibility** | **LOW** | Old exports/reports won't show deleted records - may need data migration |

---

### 1.6 Files Directly Affected by Soft Delete

**Models:**
1. `backend/models.py` - Add deleted_at, deleted_by columns to 3 models

**Business Logic:**
2. `backend/main.py` - Modify 4 delete endpoints + 23-25 query filters
3. `backend/order_service.py` - Update client existence check + add cascade logic

**Migrations:**
4. `backend/migrate.py` - Document new schema (informational only)

**Total Files:** 4 files

---

## Part 2: AUTOMATED DATABASE BACKUP Evaluation

### 2.1 Current Database Setup

**Database File:** `orders_tracking.db` (root directory)  
**Database Type:** SQLite  
**Current Access:** Via SQLAlchemy ORM in `backend/database.py`

```python
DATABASE_URL = "sqlite:///./orders_tracking.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
```

---

### 2.2 Backup Implementation Strategy

#### Option A: Scheduled File Copy (Simple, Recommended)
**Complexity:** ⭐ **Very Low**

1. Create backup directory structure:
   ```
   backups/
   ├── orders_tracking_2026-03-14_10-30-45.db
   ├── orders_tracking_2026-03-14_14-20-15.db
   └── metadata.json
   ```

2. Use APScheduler for scheduled backup task:
   ```python
   from apscheduler.schedulers.background import BackgroundScheduler
   
   def backup_database():
       src = "orders_tracking.db"
       dst = f"backups/orders_tracking_{datetime.utcnow().isoformat()}.db"
       shutil.copy2(src, dst)  # Copy preserves metadata
   
   scheduler = BackgroundScheduler()
   scheduler.add_job(backup_database, 'interval', hours=6)
   scheduler.start()
   ```

**Advantages:**
- No impact on active application writes
- Simple implementation (5 lines of code)
- Recovery is straightforward (copy file back)
- Works with SQLite's file-based nature

**Disadvantages:**
- Copies entire database (not incremental)
- Backup size grows with database size

**Estimated Effort:** 1 hour

#### Option B: SQLite VACUUM + Backup
**Complexity:** ⭐ Low

1. Add periodic VACUUM to optimize database
2. Then backup

```python
def backup_with_vacuum():
    with engine.connect() as conn:
        conn.execute(text("VACUUM;"))  # Optimize database
        conn.commit()
    backup_database()  # Then copy
```

**Estimated Effort:** 1.5 hours

#### Option C: Incremental Backups via WAL Mode
**Complexity:** ⭐⭐ Medium

Use SQLite Write-Ahead Logging (WAL) + incremental backup API.

**Not Recommended:** Adds complexity without proportional benefit for current app size.

---

### 2.3 Backup Scheduling Options

| Schedule | Pro | Con |
|----------|-----|-----|
| **Every 6 hours** | Reasonable recovery window | More backups to manage |
| **Daily (01:00 AM)** | Captures business day changes | Single point of failure |
| **On-demand (endpoint)** | Manual control | Requires user intervention |
| **Hybrid** (daily + on-demand) | Best of both | Slightly complex |

**Recommended:** Every 6 hours OR daily + manual endpoint

---

### 2.4 Backup Implementation Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **Backup during write operation** | **MEDIUM** | SQLite handles readers while writing - copy will work but might be large |
| **Backup disk space** | **LOW** | Monitor backups/directory size, implement cleanup (keep last 10) |
| **Backup fails silently** | **MEDIUM** | Log all backup operations to backup.log |
| **No recovery tested** | **HIGH** | Document recovery procedure (delete orders_tracking.db, copy backup, restart) |
| **Backup path issues on Windows** | **LOW** | Use `pathlib.Path()` for cross-platform paths |

---

### 2.5 Files Affected by Backup System

**New Files to Create:**
1. `backend/backup_service.py` - Backup logic (new file)
2. `backup.log` - Backup operation log (auto-created)

**Files to Modify:**
3. `backend/main.py` - Add startup hook to initialize scheduler
4. `requirements.txt` - Add `apscheduler` dependency

**Total Files Modified:** 2 | **New Files:** 2

---

## Part 3: INTERACTION ANALYSIS

### 3.1 Can They Coexist Without Interference?

**Answer: YES ✅**

**Soft Delete + Backup Interaction Matrix:**

| Scenario | Impact | Resolution |
|----------|--------|-----------|
| Backup runs while soft delete in progress | ✅ None | SQLite locks handle this; backup sees partial commit |
| Backup runs while order creation in progress | ✅ None | Backup is file copy; doesn't affect ORM |
| Soft delete triggers cascade during backup | ✅ None | Backup is independent; happens after commit |
| Backup file corrupts during restore | ✅ Handle separately | Backup system independent from soft delete |
| Querying soft-deleted records after backup restore | ⚠️ Possible | Soft delete filters still apply (filters on deleted_at column) |

**Conclusion:** The two systems operate at different layers:
- **Soft Delete:** ORM/query layer (application logic)
- **Backups:** File system layer (infrastructure)

They do not interfere with each other.

---

### 3.2 Impact on Critical Workflows

**Workflow: Order Creation**
```
Before: Client verified → Order created → Items added → Totals calculated
After:  Client verified (+ soft delete filter) → Order created → Items added → Totals calculated
Impact:  MINIMAL - Only affects client lookup, which already has validation
Risk:    LOW ✅
```

**Workflow: Order Editing**
```
Before: Order retrieved → Items smart-updated → Totals recalculated → Commit
After:  Order retrieved (+ soft delete filter) → Items smart-updated (+ soft delete filter) → Totals → Commit
Impact:  MINIMAL - Filters transparent to business logic
Risk:    LOW ✅
```

**Workflow: Order Deletion**
```
Before: Order deleted → CASCADE deletes items → Commit
After:  Order soft-deleted → Items soft-deleted (cascade) → Commit
Impact:  MINIMAL - Same cascade, different SQL behavior
Risk:    LOW ✅
```

**Workflow: Database Backup**
```
All workflows: Completely independent
Impact:  NONE - Background task, no blocking
Risk:    NONE ✅
```

---

## Part 4: IMPLEMENTATION COMPLEXITY CLASSIFICATION

### 4.1 Soft Delete System

**Overall Classification:** 🟡 **C) Structural Change Across Multiple Files**

**Breakdown:**
- Schema Changes: **A** (Small isolated change)
- Delete Endpoint Modifications: **B** (Minor refactor - 4 locations)
- Query Filtering: **C** (Structural - affects 23-25 locations across 2 files)
- Cascade Logic: **B** (Minor refactor)

**Why Category C?**
- Requires changes across multiple files (models, main.py, order_service)
- Affects foundational query patterns throughout application
- Every repository method accessing clients/orders/items needs review
- Represents a data access pattern shift (hard delete → soft delete)

---

### 4.2 Automated Backup System

**Overall Classification:** 🟢 **A) Small Isolated Change**

**Breakdown:**
- Scheduler Setup: **A** (Isolated new module)
- Configuration: **A** (Dependency addition)
- Integration: **A** (One hook in main.py)
- Monitoring: **A** (Optional logging)

**Why Category A?**
- No changes to core business logic
- No changes to schemas
- No changes to queries
- Pure infrastructure addition
- Can be added/removed independently

---

## Part 5: RISK IDENTIFICATION

### 5.1 High-Risk Areas

#### Risk 1: Soft Delete Filter Bypass (HIGH)
**Problem:** Developer forgets to add `deleted_at IS NULL` filter to a new query

**Impact:** Deleted records appear in UI, API endpoints, reports

**Mitigation:**
1. Create helper function (mandatory):
   ```python
   def get_active_clients(db):
       return db.query(ClientDB).filter(ClientDB.deleted_at.is_(None)).all()
   ```
2. Code review checklist for all new queries
3. Unit tests verify filters work

---

#### Risk 2: Cascade Logic Complexity (HIGH)
**Problem:** Deleting client should soft-delete orders which should soft-delete items

**Current Code (Simplified):**
```python
order.items.append(item)  # SQLAlchemy relationship
db.delete(order)  # CASCADE automatically deletes items
```

**Soft Delete Equivalent:**
```python
# Must manually cascade soft deletes, cannot rely on FK CASCADE
for order in client.orders:
    order.deleted_at = datetime.utcnow()
    for item in order.items:
        item.deleted_at = datetime.utcnow()
client.deleted_at = datetime.utcnow()
```

**Mitigation:** Create `SoftDeleteHelper` class with cascade methods

---

#### Risk 3: Relationship Integrity During Calculations (MEDIUM)
**Problem:** `OrderService.calculate_order_totals()` iterates over `order.items`

If items are soft-deleted but still in SQLAlchemy relationship:
```python
for item in order.items:  # Includes deleted items?
    order_total += item.total
```

**Solution:** Filter within calculation logic:
```python
active_items = [item for item in order.items if item.deleted_at is None]
for item in active_items:
    order_total += item.total
```

---

#### Risk 4: Backup Corruption During write (MEDIUM)
**Problem:** While backup is copying, another request writes to database

**SQLite Behavior:** Write creates lock; readers wait. However, large database copies might take time.

**Mitigation:**
1. Use `shutil.copy2()` (atomic at OS level)
2. Add checksum validation on restore
3. Keep last 3 backups (rotation)

---

### 5.2 Medium-Risk Areas

#### Risk 5: Performance Impact (MEDIUM)
**Added Soft Delete Filters:**
- `WHERE deleted_at IS NULL` on 25+ queries
- Need index on `deleted_at` column

**Solution:** Add composite indexes:
```python
Index('idx_clients_deleted_at', ClientDB.deleted_at)
Index('idx_orders_deleted_at', OrderDB.deleted_at)
Index('idx_items_deleted_at', ItemDB.deleted_at)
```

Impact: Negligible for current data size (~100-1000 records)

---

#### Risk 6: Backup Disk Space (MEDIUM)
**Problem:** Backups accumulate; disk fills up

**Mitigation:**
1. Implement cleanup: Keep only last 10 backups
2. Monitor `backups/` directory size
3. Archive old backups monthly

---

#### Risk 7: Testing Coverage Gap (MEDIUM)
**Problem:** Soft delete requires testing all affected queries

**Required Tests:**
- Verify deleted records don't appear in list endpoints
- Verify deleted records don't appear in get endpoints
- Verify cascade soft deletes work
- Verify recovery/undelete (if implemented)

---

### 5.3 Low-Risk Areas

- ✅ Backup system runs independently (low risk)
- ✅ No schema conflicts
- ✅ Existing audit logging in place
- ✅ No breaking API changes if implemented carefully

---

## Part 6: RECOMMENDED IMPLEMENTATION STRATEGY

### 6.1 Sequential Implementation (Recommended)

#### Phase 1: Automated Backups (Hours 1-2) ✅ FIRST
**Rationale:** Independent, low-risk, provides safety net

1. Add `apscheduler` to requirements.txt
2. Create `backend/backup_service.py`
3. Add scheduler initialization to `backend/main.py`
4. Test backup creation
5. **Benefit:** Database now has backups before soft delete changes

**Estimated Effort:** 1-2 hours

---

#### Phase 2: Soft Delete System (Hours 3-8) 🔄 SECOND
**Rationale:** Can rely on backups; more effort required

**Step A: Schema Changes (30 min)**
1. Add `deleted_at`, `deleted_by` to models
2. Create and run migration
3. Verify columns exist

**Step B: Delete Endpoints (1 hour)**
1. Replace `db.delete()` with soft delete logic
2. Implement cascade logic for clients
3. Test all delete endpoints

**Step C: Query Filters (2-3 hours)**
1. Create `filter_soft_deleted()` helper
2. Apply to all active queries
3. Run tests

**Step D: OrderService Updates (1 hour)**
1. Update client lookup to filter soft-deleted
2. Update cascade when deleting orders
3. Fix calculation logic if needed

**Estimated Effort:** 4-6 hours

---

### 6.2 Combined Timeline

```
Day 1 (3-4 hours):
  ✓ Backup system implemented and tested
  ✓ Database now backed up automatically

Day 1-2 (4-6 hours):
  ✓ Soft delete schema added
  ✓ Delete endpoints converted
  ✓ Queries filtered
  ✓ Tests passing
```

**Total Effort:** 5-8 hours of focused development

---

## Part 7: CODE CHANGE SUMMARY

### 7.1 Files to Modify

#### 1. `backend/models.py`
**Changes:** Add 2 columns to 3 models
**Lines:** ~9 lines added
```python
deleted_at = Column(DateTime, nullable=True)
deleted_by = Column(String, nullable=True)
```

**Complexity:** Trivial

---

#### 2. `backend/main.py`
**Changes:** 
- 4 delete endpoint rewrites
- ~25 query additions
- Scheduler initialization
- +1 import statement

**Lines:** ~50-60 lines modified
**Complexity:** Medium (systematic changes)

---

#### 3. `backend/order_service.py`
**Changes:**
- Update client lookup (1 line)
- Add cascade delete logic (5-10 lines)
- Update calculation filter (3-5 lines)

**Lines:** ~15-20 lines added
**Complexity:** Low-Medium

---

#### 4. `backend/backup_service.py` (NEW)
**Lines:** ~40 lines
**Content:** Scheduler setup + backup function

---

#### 5. `requirements.txt`
**Changes:** Add `apscheduler`

---

#### 6. `backend/migrate.py`
**Changes:** Update documentation only (informational)

---

### 7.2 Total Code Impact

| File | Type | Lines | Complexity |
|------|------|-------|-----------|
| models.py | Modify | +9 | Trivial |
| main.py | Modify | +50-60 | Medium |
| order_service.py | Modify | +15-20 | Low-Medium |
| backup_service.py | Create | +40 | Low |
| requirements.txt | Modify | +1 | Trivial |
| migrate.py | Modify | +5 | Trivial |
| **TOTAL** | | **~120 lines** | **Medium** |

---

## Part 8: FINAL RECOMMENDATIONS

### 8.1 Implementation Decision Matrix

**Should You Implement Both?**

| Criterion | Assessment |
|-----------|-----------|
| Safety | ✅ YES - Can coexist |
| Effort | 🟡 MEDIUM - 5-8 hours |
| Complexity | 🟡 Moderate - Requires discipline |
| Risk | 🟡 Medium - Query filter bypass risks |
| Benefit | ✅ HIGH - Data recovery + audit trail |
| Backward Compatibility | ⚠️ MEDIUM - Soft delete changes query behavior |

**Overall: RECOMMENDED ✅**

---

### 8.2 Go/No-Go Criteria

✅ **GO IF:**
- You can allocate 5-8 hours of focused development
- You want audit trail of deletions
- You want daily backups as safety net
- You're willing to implement comprehensive tests

⚠️ **CONSIDER CAREFULLY IF:**
- Current database size > 10GB (backup time matters)
- You don't want to maintain two separate systems
- You're hesitant about systematic query modifications

❌ **DO NOT IMPLEMENT IF:**
- You need immediate changes to production
- You cannot test thoroughly (soft delete affects every query)
- You don't have backup strategy for current system

---

### 8.3 Alternative Approaches

#### Alternative 1: Backup Only (Skip Soft Delete)
**Timeline:** 1-2 hours  
**Risk:** Very Low  
**Trade-off:** No deletion audit trail, can't recover deleted data

---

#### Alternative 2: Soft Delete Only (Skip Backups)
**Timeline:** 4-6 hours  
**Risk:** Medium (loss of all data if hard delete occurs in older versions)  
**Trade-off:** Recovery only from git history or external backups

---

#### Alternative 3: Both (Recommended)
**Timeline:** 5-8 hours  
**Risk:** Medium with proper testing  
**Benefit:** Maximum protection + audit trail

---

## Part 9: TESTING STRATEGY

### 9.1 Required Test Coverage

**Soft Delete Tests:**
```python
def test_soft_delete_client_not_in_list()
def test_soft_delete_order_not_in_list()
def test_soft_delete_cascade_to_orders()
def test_soft_delete_cascade_to_items()
def test_soft_delete_preserves_data()
def test_deleted_at_timestamp_set()
def test_deleted_by_field_recorded()
def test_create_order_with_soft_deleted_client_fails()
def test_get_client_orders_excludes_deleted()
```

---

**Backup Tests:**
```python
def test_backup_file_created()
def test_backup_file_valid_sqlite()
def test_backup_restoration_works()
def test_multiple_backups_retained()
def test_backup_timestamp_accurate()
```

---

### 9.2 Manual Testing Checklist

**Pre-Deployment:**
- [ ] Create client, delete, verify not in list
- [ ] Create order, delete, verify not in list
- [ ] Create order with items, soft delete items individually
- [ ] Delete client with orders, verify cascades to orders + items
- [ ] Backup runs automatically every 6 hours
- [ ] Restore from backup works
- [ ] All existing endpoints return same data (minus soft-deleted)
- [ ] Frontend doesn't break (no deleted records shown)

---

## Part 10: DEPLOYMENT CHECKLIST

### Pre-Deployment
- [ ] Backup current production database
- [ ] Create backup of orders_tracking.db manually
- [ ] Write migration script for deleted_at, deleted_by columns
- [ ] Create backup_service.py
- [ ] Update models.py
- [ ] Update main.py and order_service.py
- [ ] Run full test suite
- [ ] Update requirements.txt
- [ ] Document recovery procedure

### Deployment
- [ ] Stop application
- [ ] Run migration: `python -m backend.migrate`
- [ ] Verify columns exist in database
- [ ] Start application
- [ ] Check backup_service initialized
- [ ] Monitor logs for errors

### Post-Deployment
- [ ] Verify backups created automatically
- [ ] Test delete operation in UI
- [ ] Monitor soft delete filter performance
- [ ] Verify no soft-deleted records appear
- [ ] Test cascade deletes work

---

## APPENDIX: Database File Location Details

**Current Setup:**
```python
# backend/database.py
DATABASE_URL = "sqlite:///./orders_tracking.db"

# Results in:
# Relative path: ./orders_tracking.db
# Absolute path: c:\Users\Design5\Documents\Py Projects\Orders Tracking\orders_tracking.db
```

**Backup Location (Proposed):**
```
c:\Users\Design5\Documents\Py Projects\Orders Tracking\
├── orders_tracking.db (current)
└── backups/
    ├── orders_tracking_2026-03-14_10-30-45.db
    ├── orders_tracking_2026-03-14_16-30-00.db
    └── metadata.json (backup inventory)
```

**Access Pattern:**
- SQLite file-based: Can be backed up while app is running
- No special lock files that would interfere
- Requires file system permissions only

---

## CONCLUSION

**Soft Delete + Automated Backups can be safely implemented together in 5-8 hours.**

Key success factors:
1. ✅ **Start with backups** (isolated, provides safety net)
2. ✅ **Implement soft delete systematically** (query-by-query)
3. ✅ **Test thoroughly** (every affected endpoint)
4. ✅ **Monitor performance** (indices on deleted_at)
5. ✅ **Document extensively** (team awareness)

The systems do not interfere with each other and can be deployed with proper testing and planning.

