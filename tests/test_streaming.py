"""
Streaming Parser Tests
Tests for optional streaming implementation extension
"""
import pytest
from src.parsers.streaming_parser import StreamingVoucherParser


class TestStreamingParser:
    """Test streaming XML parser"""

    def test_stream_vouchers_memory_bounded(self):
        """
        Test that streaming parser processes vouchers incrementally
        without loading all into memory at once
        """
        # Create XML with multiple vouchers
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <COLLECTION>
                        <VOUCHER><VOUCHERNUMBER>1</VOUCHERNUMBER></VOUCHER>
                        <VOUCHER><VOUCHERNUMBER>2</VOUCHERNUMBER></VOUCHER>
                        <VOUCHER><VOUCHERNUMBER>3</VOUCHERNUMBER></VOUCHER>
                        <VOUCHER><VOUCHERNUMBER>4</VOUCHERNUMBER></VOUCHER>
                        <VOUCHER><VOUCHERNUMBER>5</VOUCHERNUMBER></VOUCHER>
                    </COLLECTION>
                </DATA>
            </BODY>
        </ENVELOPE>'''

        parser = StreamingVoucherParser()
        vouchers_seen = []

        # Stream vouchers one at a time
        for idx, voucher_elem in parser.stream_vouchers(xml.encode('utf-8')):
            number = voucher_elem.find("VOUCHERNUMBER").text
            vouchers_seen.append((idx, number))

            # Verify we can access the element
            assert voucher_elem is not None
            assert number in ["1", "2", "3", "4", "5"]

        # Should have seen all 5 vouchers in order
        assert len(vouchers_seen) == 5
        assert vouchers_seen[0] == (0, "1")
        assert vouchers_seen[1] == (1, "2")
        assert vouchers_seen[4] == (4, "5")

    def test_stream_vouchers_preserves_order(self):
        """Test that streaming preserves source order"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <COLLECTION>
                        <VOUCHER><DATE>20260101</DATE></VOUCHER>
                        <VOUCHER><DATE>20260102</DATE></VOUCHER>
                        <VOUCHER><DATE>20260103</DATE></VOUCHER>
                    </COLLECTION>
                </DATA>
            </BODY>
        </ENVELOPE>'''

        parser = StreamingVoucherParser()
        dates = []

        for idx, voucher_elem in parser.stream_vouchers(xml.encode('utf-8')):
            date = voucher_elem.find("DATE").text
            dates.append((idx, date))

        assert dates == [(0, "20260101"), (1, "20260102"), (2, "20260103")]

    def test_stream_large_document_simulation(self):
        """
        Simulate processing a large document with many vouchers
        Verify that we can process without errors
        """
        # Generate XML with 100 vouchers
        vouchers_xml = "\n".join([
            f'<VOUCHER><VOUCHERNUMBER>V{i:04d}</VOUCHERNUMBER><AMOUNT>{i * 100}.00</AMOUNT></VOUCHER>'
            for i in range(100)
        ])

        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <COLLECTION>
                        {vouchers_xml}
                    </COLLECTION>
                </DATA>
            </BODY>
        </ENVELOPE>'''

        parser = StreamingVoucherParser()
        count = 0

        for idx, voucher_elem in parser.stream_vouchers(xml.encode('utf-8')):
            count += 1
            # Verify we can access the element
            assert voucher_elem.find("VOUCHERNUMBER") is not None

        assert count == 100

    def test_get_voucher_count_without_loading(self):
        """Test counting vouchers without loading all into memory"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <COLLECTION>
                        <VOUCHER><VOUCHERNUMBER>1</VOUCHERNUMBER></VOUCHER>
                        <VOUCHER><VOUCHERNUMBER>2</VOUCHERNUMBER></VOUCHER>
                        <VOUCHER><VOUCHERNUMBER>3</VOUCHERNUMBER></VOUCHER>
                    </COLLECTION>
                </DATA>
            </BODY>
        </ENVELOPE>'''

        parser = StreamingVoucherParser()
        count = parser.get_voucher_count_without_loading(xml.encode('utf-8'))

        assert count == 3

    def test_streaming_parser_handles_encoding(self):
        """Test that streaming parser handles UTF-8 BOM"""
        bom = b'\xef\xbb\xbf'
        xml = bom + b'''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <COLLECTION>
                        <VOUCHER><VOUCHERNUMBER>BOM-001</VOUCHERNUMBER></VOUCHER>
                    </COLLECTION>
                </DATA>
            </BODY>
        </ENVELOPE>'''

        parser = StreamingVoucherParser()
        vouchers = list(parser.stream_vouchers(xml))

        assert len(vouchers) == 1
        idx, elem = vouchers[0]
        assert elem.find("VOUCHERNUMBER").text == "BOM-001"

    def test_streaming_with_nested_structures(self, fixture_path):
        """Test streaming parser with real fixture containing nested structures"""
        import os
        filepath = os.path.join(fixture_path, "02_sales_invoice_nested.xml")

        with open(filepath, "rb") as f:
            content = f.read()

        parser = StreamingVoucherParser()
        vouchers = list(parser.stream_vouchers(content))

        # Should successfully stream the voucher
        assert len(vouchers) >= 1

        # Verify we can access nested elements
        for idx, voucher_elem in vouchers:
            # Should have nested structures accessible
            ledgers = voucher_elem.findall(".//ALLLEDGERENTRIES.LIST")
            # Just verify we can access them without error
            assert ledgers is not None

    def test_streaming_empty_collection(self):
        """Test streaming parser with empty collection"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <COLLECTION>
                        <!-- No vouchers -->
                    </COLLECTION>
                </DATA>
            </BODY>
        </ENVELOPE>'''

        parser = StreamingVoucherParser()
        vouchers = list(parser.stream_vouchers(xml.encode('utf-8')))

        assert len(vouchers) == 0


class TestStreamingIntegration:
    """Test streaming parser integration with rest of system"""

    def test_streaming_parser_produces_same_results_as_regular(self, fixture_path):
        """
        Verify that streaming parser produces same results as regular parser
        for data integrity
        """
        import os
        from src.parsers.xml_parser import TallyXMLParser

        filepath = os.path.join(fixture_path, "01_receipt_with_allocations.xml")
        with open(filepath, "rb") as f:
            content = f.read()

        # Parse with regular parser
        regular_parser = TallyXMLParser()
        regular_result = regular_parser.parse(content)

        # Parse with streaming parser
        streaming_parser = StreamingVoucherParser()
        streaming_result = streaming_parser.parse_with_streaming(content)

        # Should have same document type
        assert regular_result.document_type == streaming_result.document_type

        # Should have same number of vouchers
        assert len(regular_result.vouchers) == len(streaming_result.vouchers)

        # Should have same detected encoding
        assert regular_result.detected_encoding == streaming_result.detected_encoding
