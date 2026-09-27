#!/bin/bash
set -e

echo "🔍 Tally XML Ingestion Service - Verification Script"
echo "=================================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Docker
echo "1. Checking Docker..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker found${NC}"
echo ""

# Check Docker Compose
echo "2. Checking Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found. Please install Docker Compose.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker Compose found${NC}"
echo ""

# Start services
echo "3. Starting services..."
docker-compose up -d
echo -e "${GREEN}✓ Services started${NC}"
echo ""

# Wait for services to be ready
echo "4. Waiting for services to be healthy..."
sleep 10
echo -e "${GREEN}✓ Services should be ready${NC}"
echo ""

# Check health endpoint
echo "5. Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s http://localhost:8000/health)
if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    echo -e "${GREEN}✓ Health check passed${NC}"
    echo "   Response: $HEALTH_RESPONSE"
else
    echo -e "${RED}❌ Health check failed${NC}"
    echo "   Response: $HEALTH_RESPONSE"
    exit 1
fi
echo ""

# Run database migrations
echo "6. Running database migrations..."
docker-compose exec -T api alembic upgrade head > /dev/null 2>&1
echo -e "${GREEN}✓ Database migrations applied${NC}"
echo ""

# Run tests
echo "7. Running automated tests..."
if docker-compose exec -T api pytest -v > test_output.log 2>&1; then
    TEST_COUNT=$(grep -c "PASSED" test_output.log || echo "0")
    echo -e "${GREEN}✓ All tests passed ($TEST_COUNT tests)${NC}"
    rm test_output.log
else
    echo -e "${RED}❌ Some tests failed${NC}"
    echo "   Check test_output.log for details"
    exit 1
fi
echo ""

# Test import endpoint
echo "8. Testing import endpoint..."
if [ -f "../fixtures/01_receipt_with_allocations.xml" ]; then
    IMPORT_RESPONSE=$(curl -s -X POST http://localhost:8000/api/tally/imports \
        -F "file=@../fixtures/01_receipt_with_allocations.xml")

    if echo "$IMPORT_RESPONSE" | grep -q "importId"; then
        echo -e "${GREEN}✓ Import endpoint working${NC}"
        IMPORT_ID=$(echo "$IMPORT_RESPONSE" | grep -o '"importId":"[^"]*"' | cut -d'"' -f4)
        echo "   Import ID: $IMPORT_ID"

        # Test details endpoint
        echo ""
        echo "9. Testing details endpoint..."
        DETAILS_RESPONSE=$(curl -s "http://localhost:8000/api/tally/imports/$IMPORT_ID")
        if echo "$DETAILS_RESPONSE" | grep -q "contentHash"; then
            echo -e "${GREEN}✓ Details endpoint working${NC}"
        else
            echo -e "${RED}❌ Details endpoint failed${NC}"
            exit 1
        fi

        # Test vouchers endpoint
        echo ""
        echo "10. Testing vouchers endpoint..."
        VOUCHERS_RESPONSE=$(curl -s "http://localhost:8000/api/tally/imports/$IMPORT_ID/vouchers")
        if echo "$VOUCHERS_RESPONSE" | grep -q "items"; then
            echo -e "${GREEN}✓ Vouchers endpoint working${NC}"
            VOUCHER_COUNT=$(echo "$VOUCHERS_RESPONSE" | grep -o '"count":[0-9]*' | cut -d':' -f2)
            echo "   Voucher count: $VOUCHER_COUNT"
        else
            echo -e "${RED}❌ Vouchers endpoint failed${NC}"
            exit 1
        fi
    else
        echo -e "${RED}❌ Import endpoint failed${NC}"
        echo "   Response: $IMPORT_RESPONSE"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ Fixture file not found, skipping import test${NC}"
fi

echo ""
echo "=================================================="
echo -e "${GREEN}✅ All verifications passed!${NC}"
echo ""
echo "Service is running at: http://localhost:8000"
echo "API Documentation: http://localhost:8000/docs"
echo ""
echo "To stop services: docker-compose down"
echo "To view logs: docker-compose logs -f"
echo ""
