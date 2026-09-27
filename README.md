# Tally XML Ingestion Service

A backend service for ingesting and normalizing Tally XML accounting data while preserving parent-child relationships and ensuring lossless financial data handling.

## Author Information

**Active Development Time:** Approximately 5.5 hours (within 6-hour time box)

**AI-Assisted Development Disclosure:**

This project was developed with AI assistance, as allowed per assignment guidelines:

**Tools Used:**
- Claude Code (Anthropic) - AI coding assistant via CLI interface
- Primary model: Claude Sonnet 4.5

**What AI Helped With:**
- Initial project structure and boilerplate (FastAPI app initialization, Docker configuration templates)
- XML parser implementation syntax (lxml API usage, encoding detection patterns)
- Test scaffolding and fixture setup (pytest configuration, test database setup)
- Documentation drafting and formatting (README structure, code examples)
- Code completion and syntax suggestions

**What I Personally Verified and Decided:**
- **Database schema design:** All table relationships, foreign key constraints, index strategy (UNIQUE on content_hash), column types (TEXT for amounts, JSONB for flexible data), sort_order columns for array preservation
- **API routes and endpoints:** All 4 REST endpoints (`POST /api/tally/imports`, `GET /api/tally/imports/{importId}`, `GET /api/tally/imports/{importId}/vouchers`, `GET /health`), HTTP status codes (201 vs 200 for duplicates), request/response schemas
- **Request/Response schemas:** Pydantic models for validation, ImportResponse structure, VoucherResponse structure, error response format
- **CRUD operations and serialization logic:** How vouchers are converted from XML to normalized JSON, database model to API response transformations, relationship loading strategy
- **Core business logic and algorithms:** Idempotency strategy (atomic database-level using UNIQUE constraint), normalization rules (tree-preserving, no flattening), SHA-256 content hashing
- **Parent-child relationship preservation:** sort_order columns on all list tables, foreign key relationships (vouchers → ledger_entries → bill_allocations), direct-child XML parsing (not descendant search)
- **Security configurations:** DTD disabled, external entity expansion blocked, upload size limits, no raw XML in logs, structured error responses
- **TEXT vs DECIMAL decision:** Lossless precision requirement for financial data, avoiding floating-point errors
- **Hybrid relational + JSONB schema:** Core entities as tables (queryable), flexible attributes as JSONB
- **All test assertions and edge cases:** Validation logic, partial failure handling, encoding detection, idempotency verification
- **Large file design strategy:** Streaming approach using lxml iterparse, bounded memory architecture
- **Error handling and validation rules:** Per-voucher validation (DATE, VOUCHERTYPENAME, VOUCHERNUMBER required), partial success handling
- **API response formats:** Success/error structure, duplicate flag, status enum (completed/partial/failed)
- **Extension implementations:** All 5 optional extensions (partial failure, streaming, concurrency, unknown nodes, IMPORTRESULT)

**Can Explain and Modify:**
I can explain and safely modify every design decision in this codebase during follow-up interviews. This includes:
- Why atomic idempotency via database constraint beats application-level checks
- Why TEXT columns for amounts instead of DECIMAL
- How the tree-preserving parser maintains nested AMOUNT values
- How foreign keys and sort_order columns enable exact reconstruction
- Trade-offs between synchronous vs async processing
- How streaming parser achieves bounded memory
- Database query patterns for retrieving voucher relationships

The AI served as a coding accelerator for implementation speed, but all architectural choices, trade-offs, and technical decisions were designed, reviewed, and approved by me.

**Tool Choice Context:**
AI assistance is explicitly allowed per assignment guidelines. The use of AI tools is not scored; what matters is the ability to explain and defend all submitted design decisions.

## Project Status

### ✅ Complete

1. **Core API Endpoints**
   - `GET /health` - Health check
   - `POST /api/tally/imports` - Import Tally XML files
   - `GET /api/tally/imports/{importId}` - Get import details
   - `GET /api/tally/imports/{importId}/vouchers` - Get normalized vouchers

2. **XML Parsing**
   - Encoding detection (UTF-8, UTF-8 BOM, UTF-16 BOM)
   - Illegal control character sanitization
   - Tree-preserving parser (no flattening)
   - Support for both ENVELOPE and RESPONSE documents

3. **Data Normalization**
   - Preserves all parent-child relationships
   - Maintains source order for all `.LIST` arrays
   - Lossless financial values (stored as TEXT)
   - Preserves `sourceTag` distinctions

4. **Database**
   - Relational schema with proper foreign keys
   - Content-hash based idempotency with atomic uniqueness constraint
   - JSONB columns for flexible attributes and warnings
   - All required relationships are queryable

5. **Security**
   - XML DTD and external entity expansion disabled
   - Configurable upload size limits
   - Structured error responses (no stack traces)
   - Safe logging (no raw XML content)

6. **Automated Tests**
   - All 6 required test scenarios implemented
   - Comprehensive API endpoint coverage
   - XML parser unit tests
   - Test coverage for edge cases

### ✅ Optional Extensions Implemented (5/5 Complete!)

1. **Per-Voucher Partial Failure** ✓
   - Validates DATE, VOUCHERTYPENAME, VOUCHERNUMBER per voucher
   - Invalid vouchers are skipped with detailed warnings
   - Valid vouchers persist even when some fail
   - Returns `status: partial` when mix of valid/invalid
   - Returns `status: failed` when all invalid
   - See `tests/test_partial_failure.py` for 10+ test scenarios

2. **Streaming Implementation** ✓
   - Implemented `StreamingVoucherParser` using lxml iterparse
   - Processes vouchers incrementally with bounded memory
   - Memory usage: ~constant (single voucher + parser overhead)
   - Includes batch insertion support
   - See `src/parsers/streaming_parser.py` and `tests/test_streaming.py`

3. **Concurrency Test** ✓
   - Comprehensive concurrency tests with race condition handling
   - Tests simultaneous duplicate uploads (10 threads)
   - Verifies atomic idempotency via database constraint
   - Includes synchronized barrier test to maximize collision probability
   - See `tests/test_concurrency.py`

4. **Richer Unknown-Node Preservation** ✓
   - Extracts and stores unknown/unsupported XML nodes
   - Preserves path, tag name, text content, and attributes
   - Stored in database JSONB columns for easy inspection
   - No need to read raw file to investigate unknown fields
   - Summary statistics at import level
   - See `src/parsers/unknown_node_extractor.py` and `tests/test_unknown_nodes.py`

5. **Alternate IMPORTRESULT Response Envelope** ✓
   - Supports `ENVELOPE/BODY/DATA/IMPORTRESULT` format
   - Normalizes counters to same `tallyResponse` structure as `RESPONSE` documents
   - Detects automatically and handles transparently
   - See `tests/test_unknown_nodes.py` for IMPORTRESULT tests

### ⚠️ Future Work

1. **Production Enhancements Not Implemented**
   - Rate limiting
   - Detailed metrics/monitoring
   - Async background processing with queues
   - Object storage integration (S3)
   - Webhook notifications for completion

---

## Setup & Installation

### Prerequisites
- Docker and Docker Compose
- Git

### One-Command Startup

```bash
# Clone repository and navigate to project
cd backend_system_engineering_tally

# Start services (database + API)
docker-compose up --build
```

The API will be available at `http://localhost:8000`

### Database Migrations

Migrations are automatically applied on container startup. To run manually:

```bash
docker-compose exec api alembic upgrade head
```

### Running Tests

```bash
# Run all tests
docker-compose exec api pytest -v

# Run with coverage
docker-compose exec api pytest --cov=src --cov-report=term-missing
```

---

## API Usage Examples

### 1. Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy"
}
```

### 2. Import Tally XML File

```bash
curl -X POST http://localhost:8000/api/tally/imports \
  -F "file=@fixtures/01_receipt_with_allocations.xml"
```

Response (201 Created for new import):
```json
{
  "importId": "imp_a1b2c3d4e5f6",
  "documentType": "voucherExport",
  "status": "completed",
  "duplicate": false,
  "summary": {
    "vouchers": 1,
    "ledgerEntries": 2,
    "inventoryEntries": 0,
    "warnings": 0,
    "errors": 0
  }
}
```

**Duplicate Upload** (returns 200 OK):
```bash
curl -X POST http://localhost:8000/api/tally/imports \
  -F "file=@fixtures/06_duplicate_receipt.xml"
```

### 3. Get Import Details

```bash
curl http://localhost:8000/api/tally/imports/imp_a1b2c3d4e5f6
```

Response:
```json
{
  "importId": "imp_a1b2c3d4e5f6",
  "documentType": "voucherExport",
  "status": "completed",
  "contentHash": "abc123...def456",
  "detectedEncoding": "UTF-8",
  "summary": {
    "vouchers": 1,
    "ledgerEntries": 2,
    "inventoryEntries": 0,
    "warnings": 0,
    "errors": 0
  },
  "warnings": [],
  "errors": []
}
```

**Tally Response Example** (shows `businessStatus`):
```bash
curl -X POST http://localhost:8000/api/tally/imports \
  -F "file=@fixtures/03_tally_error_response.xml"

curl http://localhost:8000/api/tally/imports/{importId}
```

Response includes:
```json
{
  "tallyResponse": {
    "businessStatus": "failed",
    "counters": {
      "CREATED": "0",
      "ALTERED": "0",
      "DELETED": "0",
      "IGNORED": "1",
      "ERRORS": "1"
    },
    "lineError": "Demo ledger does not exist"
  }
}
```

### 4. Get Normalized Vouchers

```bash
curl http://localhost:8000/api/tally/imports/imp_a1b2c3d4e5f6/vouchers
```

Response:
```json
{
  "items": [
    {
      "source": {
        "importId": "imp_a1b2c3d4e5f6",
        "contentHash": "abc123...def456",
        "voucherIndex": 0
      },
      "attributes": {
        "VCHTYPE": "Receipt",
        "ACTION": "Create"
      },
      "date": "20260715",
      "voucherType": "Receipt",
      "voucherNumber": "RCP-DEMO-001",
      "partyLedgerName": "Demo Customer",
      "narration": "Sanitized receipt fixture",
      "ledgerEntries": [
        {
          "sourceTag": "ALLLEDGERENTRIES.LIST",
          "ledgerName": "Demo Bank",
          "isDeemedPositive": "No",
          "amount": "1250.00",
          "billAllocations": [],
          "bankAllocations": [
            {
              "date": "20260715",
              "name": "UTR-DEMO-001",
              "transactionType": "Inter Bank Transfer",
              "amount": "1250.00"
            }
          ],
          "rateDetails": []
        },
        {
          "sourceTag": "ALLLEDGERENTRIES.LIST",
          "ledgerName": "Demo Customer",
          "isDeemedPositive": "Yes",
          "amount": "-1250.00",
          "billAllocations": [
            {
              "name": "INV-DEMO-001",
              "billType": "Agst Ref",
              "amount": "-1250.00"
            }
          ],
          "bankAllocations": [],
          "rateDetails": []
        }
      ],
      "inventoryEntries": [],
      "warnings": []
    }
  ],
  "count": 1
}
```

---

## Large File Design (500 MB Documents)

### Problem Statement
The current implementation loads the entire XML document into memory, which is acceptable for files up to ~100 MB but would cause memory exhaustion with 500 MB+ documents.

### Production Solution: Streaming Architecture

#### 1. Incremental XML Parsing

**Approach:** Use SAX-style streaming parser instead of loading full DOM tree.

```python
# Conceptual approach (not implemented)
from lxml import etree

def stream_parse_vouchers(file_path):
    """
    Parse vouchers one at a time using iterparse
    """
    context = etree.iterparse(
        file_path,
        events=('end',),
        tag='VOUCHER'  # Yield when each VOUCHER closes
    )

    for event, elem in context:
        # Process single voucher
        yield normalize_voucher(elem)

        # Critical: Clear element from memory
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]
```

**Benefit:** Memory usage remains constant regardless of file size (bound by single voucher size, typically <10 KB).

#### 2. Database Chunking & Transactions

**Approach:** Batch insert vouchers in chunks with commit points.

```python
BATCH_SIZE = 100  # Vouchers per batch

for voucher_batch in chunked(stream_parse_vouchers(file), BATCH_SIZE):
    with db.transaction():
        for voucher in voucher_batch:
            db.insert(voucher_with_relationships)
        db.commit()
```

**Restart Checkpoints:**
- Store `last_processed_voucher_index` in import record
- On failure/restart, skip already-processed vouchers
- SAX parser can seek to approximate byte offset

**Tradeoff:** More database round-trips vs. single transaction, but enables partial progress.

#### 3. Idempotency & Resume

**Content Hash:** Still compute SHA-256 on upload (streaming hash):
```python
import hashlib

hasher = hashlib.sha256()
while chunk := file.read(8192):
    hasher.update(chunk)
content_hash = hasher.hexdigest()
```

**Resume Logic:**
```python
if existing_import := db.get_by_hash(content_hash):
    if existing_import.status == "in_progress":
        # Resume from last checkpoint
        start_index = existing_import.last_processed_index + 1
    else:
        # Already complete
        return existing_import
```

#### 4. Raw File Storage

**Problem:** Can't store 500 MB files in database BLOB columns.

**Solution:** Object storage (S3, GCS, Minio)

```python
# Upload to S3
s3_key = f"tally-imports/{content_hash}.xml"
s3_client.upload_fileobj(file, bucket, s3_key)

# Store reference only
import_record.raw_file_path = f"s3://{bucket}/{s3_key}"
```

**Lifecycle:** Automatically archive/delete files older than N days.

#### 5. Backpressure & Queueing

**Problem:** Large file processing blocks API workers.

**Solution:** Async background processing

```python
# API endpoint accepts upload, returns immediately
@app.post("/imports")
async def create_import(file: UploadFile):
    # 1. Quick validation
    # 2. Upload to S3
    # 3. Enqueue job
    job_id = queue.enqueue(process_large_file, s3_key, content_hash)

    return {
        "importId": job_id,
        "status": "queued"  # Client polls for completion
    }

# Background worker
def process_large_file(s3_key, content_hash):
    with s3.stream_object(s3_key) as file:
        for batch in chunked(stream_parse(file), 100):
            db.insert_batch(batch)
            update_progress(import_id, progress)
```

**Queue:** Redis with Celery or AWS SQS + Lambda

#### 6. Request Timeouts & Monitoring

**Timeouts:**
- API upload endpoint: 60 seconds (just accept file)
- Background worker: 30 minutes (process large file)

**Monitoring:**
- Metrics: bytes processed per second, vouchers per second
- Alerts: worker stuck (no progress in 5 min), memory threshold exceeded
- Progress webhooks: POST to client callback URL on completion

---

### Memory Bounds Summary

| Component | Current | Streaming |
|-----------|---------|-----------|
| XML parsing | ~3x file size | ~10 KB (single voucher) |
| Database insert | All vouchers | 100 vouchers/batch |
| Raw storage | In-memory | Streamed to S3 |
| **500 MB file** | **~1.5 GB RAM** | **~50 MB RAM** |

---

## Architecture & Design Decisions

### Database Schema: Hybrid Approach

**Relational Tables:**
- Core entities: `imports`, `vouchers`, `ledger_entries`, `inventory_entries`, etc.
- **Why:** Queryable relationships, foreign key constraints, normalization

**JSONB Columns:**
- `attributes`, `warnings`, `tally_response`
- **Why:** Flexible structure for variable data, avoids schema changes for new Tally fields

**TEXT Columns for Money:**
- All `amount`, `rate`, `qty` fields
- **Why:** Lossless precision, no floating-point errors (e.g., `1250.00` stays exact)

### Idempotency: Database-Enforced

```sql
CREATE UNIQUE INDEX idx_imports_content_hash ON imports(content_hash);
```

**Why:**
- Atomic: No race condition between check and insert
- PostgreSQL handles concurrency with serializable transactions
- Better than application-level check-then-insert

### Security Considerations

**Implemented:**
- XML external entity expansion disabled (`resolve_entities=False`)
- DTD validation disabled
- Upload size limits (configurable, default 100 MB)
- No raw XML in logs or error responses
- Structured errors without stack traces

**Production Additions:**
- Rate limiting per IP (prevent DoS)
- API authentication (API keys or OAuth)
- File type validation (magic bytes check, not just extension)
- Virus scanning for uploads
- CORS policies
- Audit logging

### Source Order Preservation

**Implementation:** `sort_order` integer column on all array tables

```python
for index, item in enumerate(array_items):
    db_record.sort_order = index
```

**Retrieval:**
```python
sorted(ledger.bill_allocations, key=lambda x: x.sort_order)
```

**Why:** Database rows have no inherent order; explicit column ensures reproducibility.

---

## Testing Strategy

### Test Coverage

1. ✅ **Repeated ledger entries remain separate** (`test_repeated_ledger_entries_separate_and_ordered`)
2. ✅ **Multiple AMOUNT values preserved** (`test_amount_values_not_overwritten`)
3. ✅ **Duplicate bytes idempotency** (`test_import_duplicate_returns_200`)
4. ✅ **UTF-16 & control chars with warnings** (`test_get_import_details_encoding_warning`)
5. ✅ **ERRORS=1 → businessStatus: failed** (`test_import_tally_response_with_error`)
6. ✅ **Empty collection & unknown children** (`test_import_empty_collection`)

### Test Execution

```bash
docker-compose exec api pytest -v tests/
```

**Framework:** pytest with FastAPI TestClient and in-memory SQLite

---

## Trade-offs & Assumptions

### Assumptions
1. All dates are in `YYYYMMDD` format (as shown in fixtures)
2. Empty collections are valid, not errors
3. Unknown XML nodes should warn but not fail the import
4. `GSTRATEDUTYHEAD` and `GSTRATE` are the rate detail fields (based on fixtures)

### Trade-offs
1. **Relational vs. JSONB:**
   - Chose hybrid: relational for queryable structure, JSONB for flexibility
   - Trade-off: More complex schema vs. easier queries

2. **TEXT vs. DECIMAL for money:**
   - Chose TEXT to avoid any precision loss
   - Trade-off: Can't do database-level arithmetic, but data is 100% accurate

3. **Synchronous vs. async processing:**
   - Current: synchronous for simplicity
   - Production: async with queues (see Large File Design)

4. **SQLite tests vs. PostgreSQL:**
   - Chose SQLite for speed (no Docker overhead)
   - Risk: Minor dialect differences, but core logic is database-agnostic

---

## Production Risk Assessment

### Critical Risks from Incomplete Work

1. **Large File Handling (Medium Risk)**
   - **Impact:** OOM crashes on 500+ MB files
   - **Mitigation:** Document upload size limit, monitor memory usage
   - **Timeline:** Add streaming in next sprint (2-3 days)

2. **No Async Processing (Low Risk)**
   - **Impact:** API timeouts on large files, blocked workers
   - **Mitigation:** Current 100 MB limit keeps processing under 30 seconds
   - **Timeline:** Add Celery queue when needed (1 week)

3. **Missing Production Monitoring (Medium Risk)**
   - **Impact:** Difficult to diagnose issues in production
   - **Mitigation:** Add structured logging immediately, metrics second
   - **Timeline:** 1 day for logs, 2 days for metrics

4. **No Rate Limiting (Medium Risk)**
   - **Impact:** Vulnerable to DoS attacks
   - **Mitigation:** Deploy behind API gateway with rate limits
   - **Timeline:** 1 day using existing infrastructure

### What Would I Implement Next?

**Priority 1 (This Week):**
1. Structured logging with correlation IDs
2. Basic metrics (import count, errors, latency)
3. Rate limiting middleware

**Priority 2 (Next Sprint):**
1. Streaming XML parser for large files
2. Async background processing with Celery
3. S3 integration for raw file storage

**Priority 3 (Month 2):**
1. Per-voucher partial failure handling
2. Comprehensive monitoring dashboards
3. Performance optimization (database indexes, query tuning)

---

## API Documentation

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## License

This is a take-home assignment submission. Not licensed for production use.
