"""
Streaming XML Parser for Large Files
Implements incremental parsing with bounded memory
"""
import io
from typing import Iterator, Tuple, Optional
from lxml import etree

from src.parsers.xml_parser import TallyXMLParser, XMLParseResult


class StreamingVoucherParser:
    """
    Streaming parser for large Tally XML files
    Uses iterparse to process vouchers one at a time
    """

    def __init__(self):
        self.base_parser = TallyXMLParser()

    def stream_vouchers(
        self,
        file_content: bytes,
        batch_size: int = 100
    ) -> Iterator[Tuple[int, etree._Element]]:
        """
        Stream vouchers from XML file one at a time

        Args:
            file_content: Raw XML bytes
            batch_size: Number of vouchers to yield before clearing (for memory management)

        Yields:
            Tuples of (voucher_index, voucher_element)

        Memory usage: ~constant (bounded by single voucher size + parser overhead)
        """
        # Detect encoding
        encoding, processed_bytes = self.base_parser.detect_encoding(file_content)

        # Decode to string
        xml_text, had_encoding_issues = self.base_parser.decode_bytes(processed_bytes, encoding)

        # Create file-like object for streaming
        xml_stream = io.BytesIO(xml_text.encode('utf-8'))

        # Create secure parser
        parser = etree.XMLParser(
            resolve_entities=False,
            no_network=True,
            dtd_validation=False,
            load_dtd=False,
            huge_tree=True,
            remove_blank_text=False
        )

        # Use iterparse to stream VOUCHER elements
        voucher_index = 0
        context = etree.iterparse(
            xml_stream,
            events=('end',),
            tag='VOUCHER',
            parser=parser
        )

        for event, elem in context:
            # Yield the voucher element
            yield voucher_index, elem
            voucher_index += 1

            # Critical: Clear element from memory to prevent accumulation
            elem.clear()

            # Also clear parent references to free memory
            while elem.getprevious() is not None:
                del elem.getparent()[0]

            # Periodic cleanup every batch_size vouchers
            if voucher_index % batch_size == 0:
                # Force garbage collection hint (Python will decide)
                del context

                # Recreate context for next batch
                context = etree.iterparse(
                    xml_stream,
                    events=('end',),
                    tag='VOUCHER',
                    parser=parser
                )

    def parse_with_streaming(
        self,
        file_content: bytes
    ) -> XMLParseResult:
        """
        Parse XML file using streaming approach
        Returns parse result with voucher iterator instead of list

        Note: This collects vouchers into a list for compatibility.
        For true streaming, use stream_vouchers() directly.
        """
        # First, do a quick non-streaming parse to detect document type
        # We need to check if it's ENVELOPE or RESPONSE
        result = XMLParseResult()

        # Detect encoding
        encoding, processed_bytes = self.base_parser.detect_encoding(file_content)
        result.detected_encoding = encoding

        # Decode
        xml_text, had_encoding_issues = self.base_parser.decode_bytes(processed_bytes, encoding)
        if had_encoding_issues:
            if encoding.startswith('UTF-16'):
                result.warnings.append("UTF-16 encoding detected and processed")
            result.warnings.append("Illegal XML control characters sanitized")

        # Quick parse just to get root element
        try:
            root = self.base_parser.parse_xml_string(xml_text)
            result.root = root
        except ValueError as e:
            raise ValueError(f"Failed to parse XML: {str(e)}")

        root_tag = root.tag

        if root_tag == "ENVELOPE":
            result.document_type = "voucherExport"

            # Stream vouchers instead of loading all at once
            result.vouchers = []
            for idx, voucher_elem in self.stream_vouchers(file_content):
                # For this implementation, we still collect them
                # In production, you'd process each immediately
                result.vouchers.append(voucher_elem)

        elif root_tag == "RESPONSE":
            result.document_type = "tallyResponse"
            result.tally_response_data = self.base_parser._extract_tally_response(root)

        else:
            raise ValueError(f"Unsupported root element: {root_tag}")

        return result

    def get_voucher_count_without_loading(self, file_content: bytes) -> int:
        """
        Count vouchers without loading all into memory
        Useful for progress reporting
        """
        count = 0
        for _, _ in self.stream_vouchers(file_content):
            count += 1
        return count


class StreamingImportProcessor:
    """
    Processes imports using streaming parser with batch inserts
    For production use with large files
    """

    def __init__(self, db_session, batch_size: int = 100):
        self.db = db_session
        self.batch_size = batch_size
        self.streaming_parser = StreamingVoucherParser()

    def process_streaming_import(
        self,
        file_content: bytes,
        import_record,
        content_hash: str,
        normalizer,
        create_voucher_fn
    ) -> dict:
        """
        Process import using streaming approach

        Args:
            file_content: Raw XML bytes
            import_record: Import database record (already created)
            content_hash: SHA-256 hash
            normalizer: VoucherNormalizer instance
            create_voucher_fn: Function to create voucher records

        Returns:
            Dictionary with statistics
        """
        from src.parsers.voucher_validator import VoucherValidator

        validator = VoucherValidator()

        total_processed = 0
        valid_count = 0
        invalid_count = 0
        ledger_count = 0
        inventory_count = 0

        batch_vouchers = []

        # Stream vouchers one at a time
        for voucher_index, voucher_element in self.streaming_parser.stream_vouchers(file_content):
            # Validate
            validation_result = validator.validate_voucher(voucher_element)

            if validation_result.is_valid:
                # Normalize
                normalized = normalizer.normalize_voucher(
                    voucher_element,
                    voucher_index,
                    import_record.import_id,
                    content_hash
                )

                # Create voucher record
                voucher_record = create_voucher_fn(import_record.import_id, normalized)
                batch_vouchers.append(voucher_record)

                ledger_count += len(normalized["ledgerEntries"])
                inventory_count += len(normalized["inventoryEntries"])
                valid_count += 1

                # Batch insert when reaching batch size
                if len(batch_vouchers) >= self.batch_size:
                    self._flush_batch(import_record, batch_vouchers)
                    batch_vouchers = []

            else:
                # Invalid voucher
                warning_msg = f"Voucher at index {voucher_index} skipped: {'; '.join(validation_result.errors)}"
                import_record.warnings.append(warning_msg)
                invalid_count += 1

            total_processed += 1

        # Flush remaining vouchers
        if batch_vouchers:
            self._flush_batch(import_record, batch_vouchers)

        # Determine status
        if invalid_count > 0 and valid_count > 0:
            status = "partial"
        elif invalid_count > 0 and valid_count == 0:
            status = "failed"
        else:
            status = "completed"

        return {
            "status": status,
            "total_processed": total_processed,
            "valid_count": valid_count,
            "invalid_count": invalid_count,
            "ledger_count": ledger_count,
            "inventory_count": inventory_count
        }

    def _flush_batch(self, import_record, batch_vouchers):
        """
        Flush batch of vouchers to database
        Commits transaction
        """
        for voucher_record in batch_vouchers:
            import_record.vouchers.append(voucher_record)

        self.db.commit()
        self.db.refresh(import_record)
