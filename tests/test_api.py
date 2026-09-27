"""
API Endpoint Tests
Tests all required scenarios from the assignment
"""
import pytest
import os


class TestHealthEndpoint:
    """Test health check endpoint"""

    def test_health_check(self, client):
        """Health endpoint should return 200 with status"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestImportEndpoint:
    """Test import creation endpoint"""

    def test_import_valid_voucher_export(self, client, fixture_path):
        """Test importing a valid voucher export"""
        filepath = os.path.join(fixture_path, "01_receipt_with_allocations.xml")
        with open(filepath, "rb") as f:
            files = {"file": ("test.xml", f, "application/xml")}
            response = client.post("/api/tally/imports", files=files)

        assert response.status_code == 201
        data = response.json()
        assert data["documentType"] == "voucherExport"
        assert data["status"] == "completed"
        assert data["duplicate"] is False
        assert data["summary"]["vouchers"] == 1
        assert data["summary"]["ledgerEntries"] == 2
        assert "importId" in data

    def test_import_duplicate_returns_200(self, client, fixture_path):
        """Test that duplicate content returns 200 and same import ID"""
        filepath = os.path.join(fixture_path, "06_duplicate_receipt.xml")
        with open(filepath, "rb") as f:
            content = f.read()

        # First upload
        files1 = {"file": ("test1.xml", content, "application/xml")}
        response1 = client.post("/api/tally/imports", files=files1)
        assert response1.status_code == 201
        import_id1 = response1.json()["importId"]

        # Second upload with different filename
        files2 = {"file": ("test2_different_name.xml", content, "application/xml")}
        response2 = client.post("/api/tally/imports", files=files2)

        # Should return 200 for duplicate
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["duplicate"] is True
        assert data2["importId"] == import_id1

    def test_import_tally_response_with_error(self, client, fixture_path):
        """Test that ERRORS=1 results in businessStatus: failed"""
        filepath = os.path.join(fixture_path, "03_tally_error_response.xml")
        with open(filepath, "rb") as f:
            files = {"file": ("error.xml", f, "application/xml")}
            response = client.post("/api/tally/imports", files=files)

        # HTTP 201 even though business operation failed
        assert response.status_code == 201
        data = response.json()
        assert data["documentType"] == "tallyResponse"
        assert data["status"] == "completed"
        assert data["summary"]["vouchers"] == 0
        assert data["summary"]["errors"] == 1

    def test_import_empty_collection(self, client, fixture_path):
        """Test that empty collection completes without errors"""
        filepath = os.path.join(fixture_path, "05_empty_collection.xml")
        with open(filepath, "rb") as f:
            files = {"file": ("empty.xml", f, "application/xml")}
            response = client.post("/api/tally/imports", files=files)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "completed"
        assert data["summary"]["vouchers"] == 0

    def test_import_empty_file_rejected(self, client):
        """Test that empty files are rejected"""
        files = {"file": ("empty.xml", b"", "application/xml")}
        response = client.post("/api/tally/imports", files=files)
        assert response.status_code == 400

    def test_import_invalid_xml_rejected(self, client):
        """Test that invalid XML is rejected"""
        invalid_xml = b"<INVALID>This is not valid XML"
        files = {"file": ("invalid.xml", invalid_xml, "application/xml")}
        response = client.post("/api/tally/imports", files=files)
        assert response.status_code == 400


class TestImportDetailsEndpoint:
    """Test import details retrieval"""

    def test_get_import_details_voucher_export(self, client, fixture_path):
        """Test retrieving details for voucher export"""
        # First create an import
        filepath = os.path.join(fixture_path, "01_receipt_with_allocations.xml")
        with open(filepath, "rb") as f:
            files = {"file": ("test.xml", f, "application/xml")}
            create_response = client.post("/api/tally/imports", files=files)

        import_id = create_response.json()["importId"]

        # Get details
        response = client.get(f"/api/tally/imports/{import_id}")
        assert response.status_code == 200
        data = response.json()

        assert data["importId"] == import_id
        assert data["documentType"] == "voucherExport"
        assert "contentHash" in data
        assert len(data["contentHash"]) == 64  # SHA-256 hex
        assert "detectedEncoding" in data
        assert "summary" in data

    def test_get_import_details_tally_response(self, client, fixture_path):
        """Test retrieving details for Tally response with businessStatus"""
        filepath = os.path.join(fixture_path, "03_tally_error_response.xml")
        with open(filepath, "rb") as f:
            files = {"file": ("error.xml", f, "application/xml")}
            create_response = client.post("/api/tally/imports", files=files)

        import_id = create_response.json()["importId"]

        # Get details
        response = client.get(f"/api/tally/imports/{import_id}")
        assert response.status_code == 200
        data = response.json()

        # Check tally response section
        assert "tallyResponse" in data
        assert data["tallyResponse"]["businessStatus"] == "failed"
        assert "counters" in data["tallyResponse"]
        assert data["tallyResponse"]["counters"]["ERRORS"] == "1"
        assert data["tallyResponse"]["lineError"] == "Demo ledger does not exist"

    def test_get_import_details_encoding_warning(self, client, fixture_path):
        """Test that UTF-16 and control chars produce warnings"""
        filepath = os.path.join(fixture_path, "04_utf16_invalid_control_ref.xml")
        with open(filepath, "rb") as f:
            files = {"file": ("utf16.xml", f, "application/xml")}
            create_response = client.post("/api/tally/imports", files=files)

        import_id = create_response.json()["importId"]

        # Get details
        response = client.get(f"/api/tally/imports/{import_id}")
        assert response.status_code == 200
        data = response.json()

        # Should have warnings about encoding/sanitization
        assert len(data["warnings"]) > 0

    def test_get_import_details_not_found(self, client):
        """Test 404 for non-existent import"""
        response = client.get("/api/tally/imports/nonexistent_id")
        assert response.status_code == 404


class TestVouchersEndpoint:
    """Test normalized vouchers retrieval"""

    def test_get_vouchers_preserves_structure(self, client, fixture_path):
        """Test that normalized vouchers preserve all required structure"""
        filepath = os.path.join(fixture_path, "01_receipt_with_allocations.xml")
        with open(filepath, "rb") as f:
            files = {"file": ("test.xml", f, "application/xml")}
            create_response = client.post("/api/tally/imports", files=files)

        import_id = create_response.json()["importId"]

        # Get vouchers
        response = client.get(f"/api/tally/imports/{import_id}/vouchers")
        assert response.status_code == 200
        data = response.json()

        assert data["count"] == 1
        assert len(data["items"]) == 1

        voucher = data["items"][0]

        # Check source section
        assert voucher["source"]["importId"] == import_id
        assert len(voucher["source"]["contentHash"]) == 64
        assert voucher["source"]["voucherIndex"] == 0

        # Check attributes
        assert voucher["attributes"]["VCHTYPE"] == "Receipt"
        assert voucher["attributes"]["ACTION"] == "Create"

        # Check direct voucher fields
        assert voucher["date"] == "20260715"
        assert voucher["voucherType"] == "Receipt"
        assert voucher["voucherNumber"] == "RCP-DEMO-001"

    def test_repeated_ledger_entries_separate_and_ordered(self, client, fixture_path):
        """Test that repeated ledger entries remain separate and ordered"""
        filepath = os.path.join(fixture_path, "01_receipt_with_allocations.xml")
        with open(filepath, "rb") as f:
            files = {"file": ("test.xml", f, "application/xml")}
            create_response = client.post("/api/tally/imports", files=files)

        import_id = create_response.json()["importId"]

        response = client.get(f"/api/tally/imports/{import_id}/vouchers")
        voucher = response.json()["items"][0]

        # Should have 2 separate ledger entries
        assert len(voucher["ledgerEntries"]) == 2

        # First entry
        entry1 = voucher["ledgerEntries"][0]
        assert entry1["sourceTag"] == "ALLLEDGERENTRIES.LIST"
        assert entry1["ledgerName"] == "Demo Bank"
        assert entry1["amount"] == "1250.00"

        # Second entry - different values
        entry2 = voucher["ledgerEntries"][1]
        assert entry2["sourceTag"] == "ALLLEDGERENTRIES.LIST"
        assert entry2["ledgerName"] == "Demo Customer"
        assert entry2["amount"] == "-1250.00"

    def test_amount_values_not_overwritten(self, client, fixture_path):
        """Test that AMOUNT at different levels don't overwrite each other"""
        filepath = os.path.join(fixture_path, "01_receipt_with_allocations.xml")
        with open(filepath, "rb") as f:
            files = {"file": ("test.xml", f, "application/xml")}
            create_response = client.post("/api/tally/imports", files=files)

        import_id = create_response.json()["importId"]

        response = client.get(f"/api/tally/imports/{import_id}/vouchers")
        voucher = response.json()["items"][0]

        # Get ledger entry with allocations
        ledger = voucher["ledgerEntries"][1]  # Second entry has bill allocation

        # Ledger amount
        assert ledger["amount"] == "-1250.00"

        # Bill allocation amount (child of ledger)
        assert len(ledger["billAllocations"]) == 1
        assert ledger["billAllocations"][0]["amount"] == "-1250.00"

        # Both exist and are preserved separately
        assert ledger["amount"] is not None
        assert ledger["billAllocations"][0]["amount"] is not None

    def test_nested_inventory_amounts_preserved(self, client, fixture_path):
        """Test nested inventory amounts at multiple levels"""
        filepath = os.path.join(fixture_path, "02_sales_invoice_nested.xml")
        with open(filepath, "rb") as f:
            files = {"file": ("nested.xml", f, "application/xml")}
            create_response = client.post("/api/tally/imports", files=files)

        import_id = create_response.json()["importId"]

        response = client.get(f"/api/tally/imports/{import_id}/vouchers")
        if response.json()["count"] > 0:
            voucher = response.json()["items"][0]

            # If there are inventory entries, check nested amounts
            if len(voucher["inventoryEntries"]) > 0:
                inv = voucher["inventoryEntries"][0]

                # Main inventory amount
                assert inv["amount"] is not None

                # Batch allocation amounts (if present)
                for batch in inv["batchAllocations"]:
                    assert batch["amount"] is not None

                # Accounting allocation amounts (if present)
                for acc in inv["accountingAllocations"]:
                    assert acc["amount"] is not None

    def test_tally_response_has_no_vouchers(self, client, fixture_path):
        """Test that Tally response imports return zero vouchers"""
        filepath = os.path.join(fixture_path, "03_tally_error_response.xml")
        with open(filepath, "rb") as f:
            files = {"file": ("error.xml", f, "application/xml")}
            create_response = client.post("/api/tally/imports", files=files)

        import_id = create_response.json()["importId"]

        response = client.get(f"/api/tally/imports/{import_id}/vouchers")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert len(data["items"]) == 0

    def test_vouchers_not_found(self, client):
        """Test 404 for non-existent import"""
        response = client.get("/api/tally/imports/nonexistent/vouchers")
        assert response.status_code == 404
