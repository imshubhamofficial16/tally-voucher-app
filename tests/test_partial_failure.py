"""
Per-Voucher Partial Failure Tests
Tests for optional partial failure extension
"""
import pytest


class TestPartialFailure:
    """Test per-voucher validation and partial failure handling"""

    def test_voucher_missing_date_skipped(self, client):
        """Test that voucher missing DATE field is skipped with warning"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <COLLECTION>
                        <VOUCHER VCHTYPE="Payment" ACTION="Create">
                            <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
                            <VOUCHERNUMBER>PAY-001</VOUCHERNUMBER>
                            <!-- DATE is missing -->
                        </VOUCHER>
                    </COLLECTION>
                </DATA>
            </BODY>
        </ENVELOPE>'''

        files = {"file": ("missing_date.xml", xml.encode('utf-8'), "application/xml")}
        response = client.post("/api/tally/imports", files=files)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "failed"  # All vouchers invalid
        assert data["summary"]["vouchers"] == 0
        assert data["summary"]["invalidVouchers"] == 1

    def test_voucher_missing_vouchernumber_skipped(self, client):
        """Test that voucher missing VOUCHERNUMBER is skipped"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <COLLECTION>
                        <VOUCHER VCHTYPE="Receipt" ACTION="Create">
                            <DATE>20260101</DATE>
                            <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
                            <!-- VOUCHERNUMBER is missing -->
                        </VOUCHER>
                    </COLLECTION>
                </DATA>
            </BODY>
        </ENVELOPE>'''

        files = {"file": ("missing_number.xml", xml.encode('utf-8'), "application/xml")}
        response = client.post("/api/tally/imports", files=files)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "failed"
        assert data["summary"]["vouchers"] == 0

    def test_voucher_missing_vouchertypename_skipped(self, client):
        """Test that voucher missing VOUCHERTYPENAME is skipped"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <COLLECTION>
                        <VOUCHER VCHTYPE="Sales" ACTION="Create">
                            <DATE>20260101</DATE>
                            <VOUCHERNUMBER>SALE-001</VOUCHERNUMBER>
                            <!-- VOUCHERTYPENAME is missing -->
                        </VOUCHER>
                    </COLLECTION>
                </DATA>
            </BODY>
        </ENVELOPE>'''

        files = {"file": ("missing_type.xml", xml.encode('utf-8'), "application/xml")}
        response = client.post("/api/tally/imports", files=files)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "failed"
        assert data["summary"]["vouchers"] == 0

    def test_partial_failure_some_valid_some_invalid(self, client):
        """
        Test partial failure: document with both valid and invalid vouchers
        Valid vouchers should be persisted, invalid ones skipped
        """
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <COLLECTION>
                        <!-- Valid voucher 1 -->
                        <VOUCHER VCHTYPE="Receipt" ACTION="Create">
                            <DATE>20260101</DATE>
                            <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
                            <VOUCHERNUMBER>RCP-001</VOUCHERNUMBER>
                            <ALLLEDGERENTRIES.LIST>
                                <LEDGERNAME>Cash</LEDGERNAME>
                                <AMOUNT>1000.00</AMOUNT>
                            </ALLLEDGERENTRIES.LIST>
                        </VOUCHER>

                        <!-- Invalid voucher (missing DATE) -->
                        <VOUCHER VCHTYPE="Payment" ACTION="Create">
                            <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
                            <VOUCHERNUMBER>PAY-001</VOUCHERNUMBER>
                        </VOUCHER>

                        <!-- Valid voucher 2 -->
                        <VOUCHER VCHTYPE="Sales" ACTION="Create">
                            <DATE>20260102</DATE>
                            <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
                            <VOUCHERNUMBER>SALE-001</VOUCHERNUMBER>
                            <ALLLEDGERENTRIES.LIST>
                                <LEDGERNAME>Sales Account</LEDGERNAME>
                                <AMOUNT>5000.00</AMOUNT>
                            </ALLLEDGERENTRIES.LIST>
                        </VOUCHER>

                        <!-- Invalid voucher (missing VOUCHERNUMBER) -->
                        <VOUCHER VCHTYPE="Receipt" ACTION="Create">
                            <DATE>20260103</DATE>
                            <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
                        </VOUCHER>
                    </COLLECTION>
                </DATA>
            </BODY>
        </ENVELOPE>'''

        files = {"file": ("partial.xml", xml.encode('utf-8'), "application/xml")}
        response = client.post("/api/tally/imports", files=files)

        assert response.status_code == 201
        data = response.json()

        # Status should be "partial" (some valid, some invalid)
        assert data["status"] == "partial"

        # Should have persisted 2 valid vouchers
        assert data["summary"]["vouchers"] == 2
        assert data["summary"]["validVouchers"] == 2
        assert data["summary"]["invalidVouchers"] == 2
        assert data["summary"]["totalVouchersInSource"] == 4

        # Check warnings for skipped vouchers
        assert data["summary"]["warnings"] == 2

        # Get import details to verify warnings
        import_id = data["importId"]
        details_response = client.get(f"/api/tally/imports/{import_id}")
        details = details_response.json()

        assert len(details["warnings"]) == 2
        assert "Voucher at index 1 skipped" in details["warnings"][0]
        assert "Voucher at index 3 skipped" in details["warnings"][1]

        # Get vouchers to verify only valid ones were persisted
        vouchers_response = client.get(f"/api/tally/imports/{import_id}/vouchers")
        vouchers = vouchers_response.json()

        assert vouchers["count"] == 2

        # Verify source indices are correct (0 and 2, not 0 and 1)
        assert vouchers["items"][0]["source"]["voucherIndex"] == 0
        assert vouchers["items"][1]["source"]["voucherIndex"] == 2

        # Verify voucher content
        assert vouchers["items"][0]["voucherNumber"] == "RCP-001"
        assert vouchers["items"][1]["voucherNumber"] == "SALE-001"

    def test_all_valid_vouchers_status_completed(self, client, fixture_path):
        """Test that document with all valid vouchers has status: completed"""
        import os
        filepath = os.path.join(fixture_path, "01_receipt_with_allocations.xml")
        with open(filepath, "rb") as f:
            files = {"file": ("valid.xml", f, "application/xml")}
            response = client.post("/api/tally/imports", files=files)

        assert response.status_code == 201
        data = response.json()

        # All vouchers valid, should be completed
        assert data["status"] == "completed"
        assert data["summary"]["invalidVouchers"] == 0

    def test_all_invalid_vouchers_status_failed(self, client):
        """Test that document with all invalid vouchers has status: failed"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <COLLECTION>
                        <VOUCHER VCHTYPE="Payment" ACTION="Create">
                            <!-- Missing all required fields -->
                        </VOUCHER>
                        <VOUCHER VCHTYPE="Receipt" ACTION="Create">
                            <DATE>20260101</DATE>
                            <!-- Missing VOUCHERTYPENAME and VOUCHERNUMBER -->
                        </VOUCHER>
                    </COLLECTION>
                </DATA>
            </BODY>
        </ENVELOPE>'''

        files = {"file": ("all_invalid.xml", xml.encode('utf-8'), "application/xml")}
        response = client.post("/api/tally/imports", files=files)

        assert response.status_code == 201
        data = response.json()

        # All invalid, status should be failed
        assert data["status"] == "failed"
        assert data["summary"]["vouchers"] == 0
        assert data["summary"]["validVouchers"] == 0
        assert data["summary"]["invalidVouchers"] == 2
        assert data["summary"]["errors"] == 2

    def test_empty_required_field_treated_as_missing(self, client):
        """Test that empty string in required field is treated as missing"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <COLLECTION>
                        <VOUCHER VCHTYPE="Sales" ACTION="Create">
                            <DATE></DATE>  <!-- Empty -->
                            <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
                            <VOUCHERNUMBER>SALE-001</VOUCHERNUMBER>
                        </VOUCHER>
                    </COLLECTION>
                </DATA>
            </BODY>
        </ENVELOPE>'''

        files = {"file": ("empty_date.xml", xml.encode('utf-8'), "application/xml")}
        response = client.post("/api/tally/imports", files=files)

        assert response.status_code == 201
        data = response.json()

        # Empty DATE should be treated as missing
        assert data["status"] == "failed"
        assert data["summary"]["vouchers"] == 0

    def test_invalid_voucher_has_no_child_records(self, client, db_session):
        """
        Test that invalid vouchers leave no child records in database
        No orphaned ledger entries or inventory entries
        """
        from src.models.database_models import Voucher, LedgerEntry, InventoryEntry

        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <COLLECTION>
                        <!-- Invalid voucher with ledger entries -->
                        <VOUCHER VCHTYPE="Payment" ACTION="Create">
                            <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
                            <!-- Missing DATE and VOUCHERNUMBER -->
                            <ALLLEDGERENTRIES.LIST>
                                <LEDGERNAME>Should Not Be Saved</LEDGERNAME>
                                <AMOUNT>999.99</AMOUNT>
                            </ALLLEDGERENTRIES.LIST>
                        </VOUCHER>
                    </COLLECTION>
                </DATA>
            </BODY>
        </ENVELOPE>'''

        files = {"file": ("orphan_test.xml", xml.encode('utf-8'), "application/xml")}
        response = client.post("/api/tally/imports", files=files)

        import_id = response.json()["importId"]

        # Check database directly
        voucher_count = db_session.query(Voucher).filter(
            Voucher.import_id == import_id
        ).count()
        ledger_count = db_session.query(LedgerEntry).join(Voucher).filter(
            Voucher.import_id == import_id
        ).count()
        inventory_count = db_session.query(InventoryEntry).join(Voucher).filter(
            Voucher.import_id == import_id
        ).count()

        # No voucher should be saved, therefore no child records
        assert voucher_count == 0
        assert ledger_count == 0
        assert inventory_count == 0
