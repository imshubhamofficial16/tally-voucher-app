# Implementation Notes

## Key Requirements Summary
- Parse Tally XML preserving parent-child relationships
- Support ENVELOPE (voucher export) and RESPONSE (operation result) documents
- Preserve financial values losslessly (no float)
- Handle multiple encodings: UTF-8, UTF-8 BOM, UTF-16 BOM, illegal control chars
- Idempotency via SHA-256 content hash
- Return normalized JSON following exact contract

## Critical Integrity Gates
1. ✅ Parent-child ownership (AMOUNT values at different levels)
2. ✅ Lossless money (DECIMAL/TEXT, not float)
3. ✅ Content-based idempotency (atomic)
4. ✅ XML entity safety
5. ✅ Business failure interpretation (HTTP 201 + businessStatus: failed is valid)

## Technology Decisions

### Stack: Python + FastAPI
**Why Python:**
- Excellent XML parsing libraries (lxml handles encoding detection well)
- FastAPI provides clean async APIs with auto-docs
- Strong type hints for data validation
- Good testing ecosystem

### Database: PostgreSQL
**Why:**
- JSONB support for flexible attributes/warnings
- DECIMAL type for lossless financial data
- Robust UNIQUE constraints for idempotency
- Production-ready

### Storage Strategy: Hybrid
- Relational tables for queryable relationships
- JSONB columns for variable attributes/warnings
- Raw files stored on filesystem (would be S3 in production)

## Security Considerations
- Disable XML DTD/external entities
- Upload size limits (configurable)
- No stack traces in API responses
- Never log raw XML content

## Assumptions
- All dates are in YYYYMMDD format (as shown in fixtures)
- Empty collections are valid (not errors)
- Unknown XML nodes should warn but not fail
