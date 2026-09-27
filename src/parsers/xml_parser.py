"""
XML Parser for Tally documents
Handles encoding detection, sanitization, and tree-preserving parsing
"""
import re
from typing import Tuple, List, Optional, Dict, Any
from lxml import etree


class XMLParseResult:
    """Container for parse results"""
    def __init__(self):
        self.document_type: Optional[str] = None  # voucherExport or tallyResponse
        self.detected_encoding: Optional[str] = None
        self.warnings: List[str] = []
        self.root: Optional[etree._Element] = None
        self.vouchers: List[etree._Element] = []
        self.tally_response_data: Optional[Dict[str, Any]] = None


class TallyXMLParser:
    """
    Parser for Tally XML documents
    Preserves tree structure and handles encoding issues
    """

    @staticmethod
    def detect_encoding(raw_bytes: bytes) -> Tuple[str, bytes]:
        """
        Detect encoding from BOM or XML declaration
        Returns: (encoding_name, sanitized_bytes)
        """
        # Check for BOM
        if raw_bytes.startswith(b'\xff\xfe'):
            return 'UTF-16LE', raw_bytes
        elif raw_bytes.startswith(b'\xfe\xff'):
            return 'UTF-16BE', raw_bytes
        elif raw_bytes.startswith(b'\xef\xbb\xbf'):
            return 'UTF-8-BOM', raw_bytes[3:]  # Strip BOM for processing

        # Try to detect from XML declaration
        try:
            # Look at first 200 bytes for declaration
            header = raw_bytes[:200].decode('utf-8', errors='ignore')
            encoding_match = re.search(r'encoding=["\']([^"\']+)["\']', header)
            if encoding_match:
                detected = encoding_match.group(1).upper()
                if 'UTF-16' in detected:
                    return detected, raw_bytes
        except:
            pass

        # Default to UTF-8
        return 'UTF-8', raw_bytes

    @staticmethod
    def sanitize_illegal_control_chars(text: str) -> Tuple[str, bool]:
        """
        Remove illegal XML 1.0 control characters
        Returns: (cleaned_text, had_illegal_chars)
        """
        # XML 1.0 legal characters:
        # #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]

        illegal_pattern = re.compile(
            r'[\x00-\x08\x0B\x0C\x0E-\x1F]'  # Control chars except tab, newline, carriage return
        )

        had_illegal = bool(illegal_pattern.search(text))
        cleaned = illegal_pattern.sub('', text)

        return cleaned, had_illegal

    @staticmethod
    def decode_bytes(raw_bytes: bytes, encoding: str) -> Tuple[str, bool]:
        """
        Decode bytes to string and sanitize
        Returns: (decoded_text, had_issues)
        """
        had_issues = False

        # Handle UTF-16 with BOM
        if encoding.startswith('UTF-16'):
            try:
                # Let Python handle BOM automatically
                text = raw_bytes.decode('utf-16')
            except UnicodeDecodeError:
                # Fallback
                text = raw_bytes.decode('utf-16', errors='replace')
                had_issues = True
        else:
            # UTF-8 or UTF-8-BOM
            try:
                text = raw_bytes.decode('utf-8')
            except UnicodeDecodeError:
                text = raw_bytes.decode('utf-8', errors='replace')
                had_issues = True

        # Sanitize illegal control characters
        text, had_illegal = TallyXMLParser.sanitize_illegal_control_chars(text)
        if had_illegal:
            had_issues = True

        return text, had_issues

    @staticmethod
    def parse_xml_string(xml_text: str) -> etree._Element:
        """
        Parse XML string to element tree
        Disables DTD and external entities for security
        """
        parser = etree.XMLParser(
            resolve_entities=False,  # Disable external entity expansion
            no_network=True,         # No network access
            dtd_validation=False,    # Disable DTD validation
            load_dtd=False,          # Don't load DTD
            huge_tree=True,          # Allow large documents
            remove_blank_text=False  # Preserve whitespace in text
        )

        try:
            root = etree.fromstring(xml_text.encode('utf-8'), parser=parser)
            return root
        except etree.XMLSyntaxError as e:
            raise ValueError(f"XML syntax error: {str(e)}")

    @staticmethod
    def get_direct_child_text(element: etree._Element, tag_name: str) -> Optional[str]:
        """
        Get text from a direct child element (not descendants)
        """
        child = element.find(tag_name)
        if child is not None and child.text:
            return child.text.strip()
        return None

    @staticmethod
    def get_all_direct_children(element: etree._Element, tag_name: str) -> List[etree._Element]:
        """
        Get all direct children with given tag name
        Preserves source order
        """
        return element.findall(tag_name)

    def parse(self, raw_bytes: bytes) -> XMLParseResult:
        """
        Main parse method
        Returns parsed structure with metadata
        """
        result = XMLParseResult()

        # Detect encoding
        encoding, processed_bytes = self.detect_encoding(raw_bytes)
        result.detected_encoding = encoding

        # Decode to string
        xml_text, had_encoding_issues = self.decode_bytes(processed_bytes, encoding)
        if had_encoding_issues:
            if encoding.startswith('UTF-16'):
                result.warnings.append("UTF-16 encoding detected and processed")
            result.warnings.append("Illegal XML control characters sanitized")

        # Parse XML
        try:
            root = self.parse_xml_string(xml_text)
            result.root = root
        except ValueError as e:
            raise ValueError(f"Failed to parse XML: {str(e)}")

        # Determine document type
        root_tag = root.tag

        if root_tag == "ENVELOPE":
            # Check if it's a voucher export or import result
            import_result = self._try_extract_import_result(root)
            if import_result:
                result.document_type = "tallyResponse"
                result.tally_response_data = import_result
            else:
                result.document_type = "voucherExport"
                # Extract vouchers
                result.vouchers = self._extract_vouchers_from_envelope(root)

        elif root_tag == "RESPONSE":
            result.document_type = "tallyResponse"
            # Extract response data
            result.tally_response_data = self._extract_tally_response(root)

        else:
            raise ValueError(f"Unsupported root element: {root_tag}")

        return result

    def _extract_vouchers_from_envelope(self, root: etree._Element) -> List[etree._Element]:
        """
        Extract voucher elements from ENVELOPE structure
        Path: ENVELOPE/BODY/DATA/COLLECTION/VOUCHER
        """
        vouchers = []

        body = root.find("BODY")
        if body is None:
            return vouchers

        data = body.find("DATA")
        if data is None:
            return vouchers

        collection = data.find("COLLECTION")
        if collection is None:
            return vouchers

        # Get all VOUCHER elements in source order
        vouchers = collection.findall("VOUCHER")

        return vouchers

    def _extract_tally_response(self, root: etree._Element) -> Dict[str, Any]:
        """
        Extract response counters from RESPONSE element
        """
        response_data = {
            "counters": {},
            "lineError": None
        }

        # Extract counter fields
        counter_fields = ["CREATED", "ALTERED", "DELETED", "IGNORED", "ERRORS"]
        for field in counter_fields:
            text = self.get_direct_child_text(root, field)
            if text is not None:
                response_data["counters"][field] = text

        # Extract line error
        line_error = self.get_direct_child_text(root, "LINEERROR")
        if line_error:
            response_data["lineError"] = line_error

        # Determine business status
        errors_count = response_data["counters"].get("ERRORS", "0")
        try:
            errors_int = int(errors_count)
        except ValueError:
            errors_int = 0

        has_line_error = bool(line_error)

        if errors_int > 0 or has_line_error:
            response_data["businessStatus"] = "failed"
        else:
            response_data["businessStatus"] = "succeeded"

        return response_data

    def _try_extract_import_result(self, root: etree._Element) -> Optional[Dict[str, Any]]:
        """
        Try to extract IMPORTRESULT from ENVELOPE/BODY/DATA/IMPORTRESULT
        Returns None if not found (indicating this is a voucher export instead)
        """
        body = root.find("BODY")
        if body is None:
            return None

        data = body.find("DATA")
        if data is None:
            return None

        import_result = data.find("IMPORTRESULT")
        if import_result is None:
            return None

        # Found IMPORTRESULT, normalize it to same structure as RESPONSE
        response_data = {
            "counters": {},
            "lineError": None
        }

        # Extract counter fields
        counter_fields = ["CREATED", "ALTERED", "DELETED", "IGNORED", "ERRORS"]
        for field in counter_fields:
            text = self.get_direct_child_text(import_result, field)
            if text is not None:
                response_data["counters"][field] = text

        # Extract line error (if present)
        line_error = self.get_direct_child_text(import_result, "LINEERROR")
        if line_error:
            response_data["lineError"] = line_error

        # Determine business status
        errors_count = response_data["counters"].get("ERRORS", "0")
        try:
            errors_int = int(errors_count)
        except ValueError:
            errors_int = 0

        has_line_error = bool(line_error)

        if errors_int > 0 or has_line_error:
            response_data["businessStatus"] = "failed"
        else:
            response_data["businessStatus"] = "succeeded"

        return response_data
