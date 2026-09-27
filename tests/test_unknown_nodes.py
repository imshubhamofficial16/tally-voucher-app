"""
Unknown Node Preservation Tests
Tests for richer unknown-node preservation extension
"""
import pytest


class TestUnknownNodeExtraction:
    """Test unknown node detection and preservation"""

    def test_unknown_field_at_voucher_level(self, client):
        """Test that unknown fields at voucher level are detected"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <COLLECTION>
                        <VOUCHER VCHTYPE="Sales" ACTION="Create">
                            <DATE>20260101</DATE>
                            <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
                            <VOUCHERNUMBER>SALE-001</VOUCHERNUMBER>
                            <CUSTOMFIELD1>Custom Value 1</CUSTOMFIELD1>
                            <CUSTOMFIELD2>Custom Value 2</CUSTOMFIELD2>
                        </VOUCHER>
                    </COLLECTION>
                </DATA>
            </BODY>
        </ENVELOPE>'''

        files = {"file": ("unknown.xml", xml.encode('utf-8'), "application/xml")}
        response = client.post("/api/tally/imports", files=files)

        assert response.status_code == 201
        data = response.json()

        # Should have warning about unknown fields
        assert data["summary"]["warnings"] > 0

        # Get import details
        import_id = data["importId"]
        details_response = client.get(f"/api/tally/imports/{import_id}")
        details = details_response.json()

        # Should have warning about unknown fields
        assert any("unknown" in w.lower() or "unsupported" in w.lower() for w in details["warnings"])

    def test_unknown_nodes_preserved_in_voucher(self, client):
        """Test that unknown nodes are stored in voucher record"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <COLLECTION>
                        <VOUCHER VCHTYPE="Receipt" ACTION="Create">
                            <DATE>20260101</DATE>
                            <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
                            <VOUCHERNUMBER>RCP-001</VOUCHERNUMBER>
                            <UDF_FIELD>User Defined Field</UDF_FIELD>
                            <ALLLEDGERENTRIES.LIST>
                                <LEDGERNAME>Cash</LEDGERNAME>
                                <AMOUNT>1000.00</AMOUNT>
                            </ALLLEDGERENTRIES.LIST>
                        </VOUCHER>
                    </COLLECTION>
                </DATA>
            </BODY>
        </ENVELOPE>'''

        files = {"file": ("udf.xml", xml.encode('utf-8'), "application/xml")}
        response = client.post("/api/tally/imports", files=files)

        import_id = response.json()["importId"]

        # Get vouchers
        vouchers_response = client.get(f"/api/tally/imports/{import_id}/vouchers")
        vouchers = vouchers_response.json()

        assert vouchers["count"] == 1
        # Voucher should be persisted despite unknown field
        assert vouchers["items"][0]["voucherNumber"] == "RCP-001"

    def test_multiple_unknown_fields_tracked(self, client):
        """Test that multiple unknown fields are all tracked"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <COLLECTION>
                        <VOUCHER VCHTYPE="Payment" ACTION="Create">
                            <DATE>20260101</DATE>
                            <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
                            <VOUCHERNUMBER>PAY-001</VOUCHERNUMBER>
                            <FIELD1>Value 1</FIELD1>
                            <FIELD2>Value 2</FIELD2>
                            <FIELD3>Value 3</FIELD3>
                        </VOUCHER>
                    </COLLECTION>
                </DATA>
            </BODY>
        </ENVELOPE>'''

        files = {"file": ("multiple_unknown.xml", xml.encode('utf-8'), "application/xml")}
        response = client.post("/api/tally/imports", files=files)

        import_id = response.json()["importId"]

        # Get import details
        details_response = client.get(f"/api/tally/imports/{import_id}")
        details = details_response.json()

        # Should have warning mentioning multiple fields
        warning_text = " ".join(details["warnings"])
        assert "3" in warning_text or "multiple" in warning_text.lower()

    def test_known_fields_not_flagged_as_unknown(self, client, fixture_path):
        """Test that standard fields are not flagged as unknown"""
        import os
        filepath = os.path.join(fixture_path, "01_receipt_with_allocations.xml")

        with open(filepath, "rb") as f:
            files = {"file": ("known.xml", f, "application/xml")}
            response = client.post("/api/tally/imports", files=files)

        import_id = response.json()["importId"]

        # Get import details
        details_response = client.get(f"/api/tally/imports/{import_id}")
        details = details_response.json()

        # Should not have warnings about unknown fields
        unknown_warnings = [w for w in details["warnings"] if "unknown" in w.lower() or "unsupported" in w.lower()]
        assert len(unknown_warnings) == 0

    def test_unknown_nodes_dont_block_processing(self, client):
        """Test that unknown nodes don't prevent voucher processing"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <COLLECTION>
                        <VOUCHER VCHTYPE="Sales" ACTION="Create">
                            <DATE>20260101</DATE>
                            <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
                            <VOUCHERNUMBER>SALE-001</VOUCHERNUMBER>
                            <UNKNOWN_NODE>Should not cause failure</UNKNOWN_NODE>
                            <ALLLEDGERENTRIES.LIST>
                                <LEDGERNAME>Sales Account</LEDGERNAME>
                                <AMOUNT>5000.00</AMOUNT>
                                <UNKNOWN_LEDGER_FIELD>Also ignored</UNKNOWN_LEDGER_FIELD>
                            </ALLLEDGERENTRIES.LIST>
                        </VOUCHER>
                    </COLLECTION>
                </DATA>
            </BODY>
        </ENVELOPE>'''

        files = {"file": ("mixed.xml", xml.encode('utf-8'), "application/xml")}
        response = client.post("/api/tally/imports", files=files)

        assert response.status_code == 201
        data = response.json()

        # Should be completed despite unknown fields
        assert data["status"] == "completed"
        assert data["summary"]["vouchers"] == 1

        # Verify voucher was persisted
        import_id = data["importId"]
        vouchers_response = client.get(f"/api/tally/imports/{import_id}/vouchers")
        vouchers = vouchers_response.json()

        assert vouchers["count"] == 1
        assert vouchers["items"][0]["voucherNumber"] == "SALE-001"
        assert len(vouchers["items"][0]["ledgerEntries"]) == 1


class TestImportResultSupport:
    """Test IMPORTRESULT envelope support"""

    def test_importresult_envelope_with_errors(self, client):
        """Test that ENVELOPE with IMPORTRESULT is treated as tallyResponse"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <IMPORTRESULT>
                        <CREATED>0</CREATED>
                        <ALTERED>0</ALTERED>
                        <DELETED>0</DELETED>
                        <IGNORED>1</IGNORED>
                        <ERRORS>1</ERRORS>
                        <LINEERROR>Ledger does not exist</LINEERROR>
                    </IMPORTRESULT>
                </DATA>
            </BODY>
        </ENVELOPE>'''

        files = {"file": ("importresult.xml", xml.encode('utf-8'), "application/xml")}
        response = client.post("/api/tally/imports", files=files)

        assert response.status_code == 201
        data = response.json()

        # Should be recognized as tallyResponse, not voucherExport
        assert data["documentType"] == "tallyResponse"
        assert data["summary"]["vouchers"] == 0

        # Get details
        import_id = data["importId"]
        details_response = client.get(f"/api/tally/imports/{import_id}")
        details = details_response.json()

        # Should have tallyResponse section
        assert "tallyResponse" in details
        assert details["tallyResponse"]["businessStatus"] == "failed"
        assert details["tallyResponse"]["counters"]["ERRORS"] == "1"
        assert details["tallyResponse"]["lineError"] == "Ledger does not exist"

    def test_importresult_envelope_success(self, client):
        """Test IMPORTRESULT with successful import"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <IMPORTRESULT>
                        <CREATED>5</CREATED>
                        <ALTERED>2</ALTERED>
                        <DELETED>0</DELETED>
                        <IGNORED>0</IGNORED>
                        <ERRORS>0</ERRORS>
                    </IMPORTRESULT>
                </DATA>
            </BODY>
        </ENVELOPE>'''

        files = {"file": ("importresult_success.xml", xml.encode('utf-8'), "application/xml")}
        response = client.post("/api/tally/imports", files=files)

        assert response.status_code == 201
        data = response.json()

        assert data["documentType"] == "tallyResponse"

        # Get details
        import_id = data["importId"]
        details_response = client.get(f"/api/tally/imports/{import_id}")
        details = details_response.json()

        # Should have succeeded status
        assert details["tallyResponse"]["businessStatus"] == "succeeded"
        assert details["tallyResponse"]["counters"]["CREATED"] == "5"
        assert details["tallyResponse"]["counters"]["ALTERED"] == "2"

    def test_envelope_with_collection_not_treated_as_importresult(self, client):
        """Test that normal ENVELOPE with COLLECTION is not confused with IMPORTRESULT"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <COLLECTION>
                        <VOUCHER VCHTYPE="Sales" ACTION="Create">
                            <DATE>20260101</DATE>
                            <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
                            <VOUCHERNUMBER>SALE-001</VOUCHERNUMBER>
                        </VOUCHER>
                    </COLLECTION>
                </DATA>
            </BODY>
        </ENVELOPE>'''

        files = {"file": ("normal_envelope.xml", xml.encode('utf-8'), "application/xml")}
        response = client.post("/api/tally/imports", files=files)

        assert response.status_code == 201
        data = response.json()

        # Should be voucherExport, not tallyResponse
        assert data["documentType"] == "voucherExport"
        assert data["summary"]["vouchers"] == 1
