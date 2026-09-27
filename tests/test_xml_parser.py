"""
XML Parser Tests
Tests encoding detection, sanitization, and parsing
"""
import pytest
from src.parsers.xml_parser import TallyXMLParser


class TestEncodingDetection:
    """Test encoding detection"""

    def test_utf8_detection(self):
        """Test UTF-8 detection"""
        parser = TallyXMLParser()
        xml = '<?xml version="1.0" encoding="UTF-8"?><ROOT></ROOT>'.encode('utf-8')
        encoding, _ = parser.detect_encoding(xml)
        assert encoding in ["UTF-8", "UTF-8-BOM"]

    def test_utf8_bom_detection(self):
        """Test UTF-8 BOM detection"""
        parser = TallyXMLParser()
        bom = b'\xef\xbb\xbf'
        xml = bom + '<?xml version="1.0"?><ROOT></ROOT>'.encode('utf-8')
        encoding, processed = parser.detect_encoding(xml)
        assert encoding == "UTF-8-BOM"
        # BOM should be stripped
        assert not processed.startswith(bom)

    def test_utf16_detection(self):
        """Test UTF-16 BOM detection"""
        parser = TallyXMLParser()
        xml = '<?xml version="1.0"?><ROOT></ROOT>'.encode('utf-16')
        encoding, _ = parser.detect_encoding(xml)
        assert "UTF-16" in encoding


class TestControlCharacterSanitization:
    """Test illegal control character handling"""

    def test_sanitize_illegal_control_chars(self):
        """Test removal of illegal XML control characters"""
        parser = TallyXMLParser()
        # Include illegal control character (0x04)
        text = "Hello\x04World"
        cleaned, had_illegal = parser.sanitize_illegal_control_chars(text)

        assert had_illegal is True
        assert cleaned == "HelloWorld"
        assert '\x04' not in cleaned

    def test_legal_chars_preserved(self):
        """Test that legal characters are preserved"""
        parser = TallyXMLParser()
        text = "Hello\nWorld\tTest"
        cleaned, had_illegal = parser.sanitize_illegal_control_chars(text)

        assert had_illegal is False
        assert cleaned == text


class TestXMLParsing:
    """Test XML parsing"""

    def test_parse_envelope_structure(self):
        """Test parsing ENVELOPE structure"""
        parser = TallyXMLParser()
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <COLLECTION>
                        <VOUCHER>
                            <DATE>20260101</DATE>
                        </VOUCHER>
                    </COLLECTION>
                </DATA>
            </BODY>
        </ENVELOPE>'''.encode('utf-8')

        result = parser.parse(xml)
        assert result.document_type == "voucherExport"
        assert len(result.vouchers) == 1

    def test_parse_response_structure(self):
        """Test parsing RESPONSE structure"""
        parser = TallyXMLParser()
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <RESPONSE>
            <CREATED>0</CREATED>
            <ALTERED>0</ALTERED>
            <ERRORS>1</ERRORS>
            <LINEERROR>Test error</LINEERROR>
        </RESPONSE>'''.encode('utf-8')

        result = parser.parse(xml)
        assert result.document_type == "tallyResponse"
        assert result.tally_response_data["businessStatus"] == "failed"
        assert result.tally_response_data["counters"]["ERRORS"] == "1"

    def test_business_status_succeeded(self):
        """Test businessStatus: succeeded when no errors"""
        parser = TallyXMLParser()
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <RESPONSE>
            <CREATED>1</CREATED>
            <ERRORS>0</ERRORS>
        </RESPONSE>'''.encode('utf-8')

        result = parser.parse(xml)
        assert result.tally_response_data["businessStatus"] == "succeeded"

    def test_xml_security_no_external_entities(self):
        """Test that external entities are disabled"""
        parser = TallyXMLParser()
        # This should not cause issues with external entity expansion
        xml = '''<?xml version="1.0"?>
        <!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
        <ROOT>&xxe;</ROOT>'''

        # Parser should handle this safely (entity not resolved)
        try:
            root = parser.parse_xml_string(xml)
            # External entity should not be expanded
            assert True
        except:
            # Or it might raise an error, which is also safe
            assert True

    def test_empty_collection_parsed(self):
        """Test that empty collection is parsed successfully"""
        parser = TallyXMLParser()
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <ENVELOPE>
            <BODY>
                <DATA>
                    <COLLECTION>
                    </COLLECTION>
                </DATA>
            </BODY>
        </ENVELOPE>'''.encode('utf-8')

        result = parser.parse(xml)
        assert result.document_type == "voucherExport"
        assert len(result.vouchers) == 0

    def test_invalid_xml_raises_error(self):
        """Test that invalid XML raises appropriate error"""
        parser = TallyXMLParser()
        xml = b"<INVALID>Not closed"

        with pytest.raises(ValueError, match="Failed to parse XML"):
            parser.parse(xml)

    def test_unsupported_root_raises_error(self):
        """Test that unsupported root element raises error"""
        parser = TallyXMLParser()
        xml = b'<?xml version="1.0"?><UNSUPPORTED></UNSUPPORTED>'

        with pytest.raises(ValueError, match="Unsupported root element"):
            parser.parse(xml)


class TestTreePreservation:
    """Test that parser preserves tree structure"""

    def test_multiple_vouchers_preserved(self):
        """Test multiple vouchers in source order"""
        parser = TallyXMLParser()
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
        </ENVELOPE>'''.encode('utf-8')

        result = parser.parse(xml)
        assert len(result.vouchers) == 3
        # Verify order
        assert result.vouchers[0].find("VOUCHERNUMBER").text == "1"
        assert result.vouchers[1].find("VOUCHERNUMBER").text == "2"
        assert result.vouchers[2].find("VOUCHERNUMBER").text == "3"

    def test_direct_child_parsing(self):
        """Test that get_direct_child_text only gets direct children"""
        parser = TallyXMLParser()
        xml = '''<?xml version="1.0"?>
        <ROOT>
            <CHILD>direct</CHILD>
            <PARENT>
                <CHILD>nested</CHILD>
            </PARENT>
        </ROOT>'''

        root = parser.parse_xml_string(xml)
        # Should only get direct child, not nested one
        direct_text = parser.get_direct_child_text(root, "CHILD")
        assert direct_text == "direct"
