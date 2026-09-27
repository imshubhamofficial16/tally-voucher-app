"""
Import Service
Handles the business logic for importing Tally XML files
"""
import os
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.parsers.xml_parser import TallyXMLParser
from src.parsers.voucher_normalizer import VoucherNormalizer
from src.parsers.voucher_validator import VoucherValidator
from src.parsers.unknown_node_extractor import UnknownNodeExtractor
from src.models.database_models import (
    Import, Voucher, LedgerEntry, BillAllocation, BankAllocation,
    InventoryEntry, BatchAllocation, AccountingAllocation, RateDetail
)
from src.utils.hash_utils import (
    compute_sha256, generate_import_id, generate_voucher_id,
    generate_ledger_entry_id, generate_inventory_entry_id,
    generate_allocation_id, generate_rate_detail_id
)
from src.config import config


class ImportService:
    """Service for handling Tally XML imports"""

    def __init__(self, db: Session):
        self.db = db
        self.xml_parser = TallyXMLParser()
        self.normalizer = VoucherNormalizer()
        self.validator = VoucherValidator()
        self.unknown_extractor = UnknownNodeExtractor()

    def process_upload(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Process uploaded Tally XML file
        Returns import response with status and summary
        """
        # Compute content hash
        content_hash = compute_sha256(file_content)

        # Check for existing import (idempotency)
        existing = self.db.query(Import).filter(Import.content_hash == content_hash).first()
        if existing:
            return self._build_import_response(existing, duplicate=True)

        # Parse XML
        try:
            parse_result = self.xml_parser.parse(file_content)
        except Exception as e:
            raise ValueError(f"Failed to parse XML: {str(e)}")

        # Save raw file
        raw_file_path = self._save_raw_file(file_content, content_hash)

        # Generate import ID
        import_id = generate_import_id()

        # Create import record
        import_record = Import(
            import_id=import_id,
            content_hash=content_hash,
            document_type=parse_result.document_type,
            status="completed",
            detected_encoding=parse_result.detected_encoding,
            raw_file_path=raw_file_path,
            warnings=parse_result.warnings,
            errors=[]
        )

        # Process based on document type
        if parse_result.document_type == "voucherExport":
            self._process_voucher_export(
                import_record,
                parse_result,
                content_hash
            )
        elif parse_result.document_type == "tallyResponse":
            self._process_tally_response(
                import_record,
                parse_result
            )

        # Save to database with idempotency protection
        try:
            self.db.add(import_record)
            self.db.commit()
            self.db.refresh(import_record)
        except IntegrityError:
            # Race condition: another request saved this hash
            self.db.rollback()
            existing = self.db.query(Import).filter(Import.content_hash == content_hash).first()
            return self._build_import_response(existing, duplicate=True)

        return self._build_import_response(import_record, duplicate=False)

    def _save_raw_file(self, content: bytes, content_hash: str) -> str:
        """Save raw file and return path"""
        filename = f"{content_hash}.xml"
        filepath = os.path.join(config.RAW_FILES_DIR, filename)

        with open(filepath, 'wb') as f:
            f.write(content)

        return filepath

    def _process_voucher_export(
        self,
        import_record: Import,
        parse_result,
        content_hash: str
    ):
        """
        Process voucher export document with per-voucher validation
        Implements optional partial failure extension
        """
        vouchers = parse_result.vouchers
        total_voucher_count = len(vouchers)

        # Validate all vouchers first
        validation_result = self.validator.validate_vouchers(vouchers)

        valid_vouchers = validation_result["valid_vouchers"]
        invalid_vouchers = validation_result["invalid_vouchers"]

        ledger_count = 0
        inventory_count = 0
        voucher_errors = []
        all_unknown_nodes = []

        # Process only valid vouchers
        for original_idx, voucher_element in valid_vouchers:
            # Extract unknown nodes
            unknown_nodes = self.unknown_extractor.extract_unknown_nodes(
                voucher_element,
                original_idx
            )

            if unknown_nodes:
                all_unknown_nodes.extend(unknown_nodes)
                warning_msg = f"Voucher at index {original_idx} contains {len(unknown_nodes)} unknown/unsupported field(s)"
                import_record.warnings.append(warning_msg)

            # Normalize voucher
            normalized = self.normalizer.normalize_voucher(
                voucher_element,
                original_idx,  # Use original index to preserve source order
                import_record.import_id,
                content_hash
            )

            # Add unknown nodes to normalized data
            normalized["unknown_nodes"] = unknown_nodes

            # Create voucher record
            voucher_record = self._create_voucher_record(import_record.import_id, normalized)
            import_record.vouchers.append(voucher_record)

            ledger_count += len(normalized["ledgerEntries"])
            inventory_count += len(normalized["inventoryEntries"])

        # Add warnings for invalid vouchers
        for original_idx, voucher_element, errors in invalid_vouchers:
            warning_msg = f"Voucher at index {original_idx} skipped: {'; '.join(errors)}"
            import_record.warnings.append(warning_msg)
            voucher_errors.append({
                "voucherIndex": original_idx,
                "errors": errors
            })

        # Determine status
        if len(invalid_vouchers) > 0 and len(valid_vouchers) > 0:
            # Partial success: some valid, some invalid
            import_record.status = "partial"
        elif len(invalid_vouchers) > 0 and len(valid_vouchers) == 0:
            # Complete failure: all invalid
            import_record.status = "failed"
            import_record.errors.extend(voucher_errors)
        else:
            # Complete success: all valid
            import_record.status = "completed"

        # Create summary of unknown nodes
        if all_unknown_nodes:
            import_record.unknown_nodes_summary = self.unknown_extractor.summarize_unknown_nodes(
                all_unknown_nodes
            )

        # Set summary
        import_record.summary = {
            "vouchers": len(valid_vouchers),  # Only count persisted vouchers
            "ledgerEntries": ledger_count,
            "inventoryEntries": inventory_count,
            "warnings": len(parse_result.warnings) + len(invalid_vouchers),
            "errors": len(invalid_vouchers) if import_record.status == "failed" else 0,
            "totalVouchersInSource": total_voucher_count,
            "validVouchers": len(valid_vouchers),
            "invalidVouchers": len(invalid_vouchers)
        }

    def _process_tally_response(self, import_record: Import, parse_result):
        """Process Tally response document"""
        response_data = parse_result.tally_response_data

        import_record.tally_response = response_data

        # Empty summary for response documents
        import_record.summary = {
            "vouchers": 0,
            "ledgerEntries": 0,
            "inventoryEntries": 0,
            "warnings": len(parse_result.warnings),
            "errors": 1 if response_data["businessStatus"] == "failed" else 0
        }

    def _create_voucher_record(self, import_id: str, normalized: Dict[str, Any]) -> Voucher:
        """Create voucher database record with all nested relationships"""
        voucher = Voucher(
            voucher_id=generate_voucher_id(),
            import_id=import_id,
            voucher_index=normalized["source"]["voucherIndex"],
            attributes=normalized["attributes"],
            date=normalized["date"],
            voucher_type=normalized["voucherType"],
            voucher_number=normalized["voucherNumber"],
            party_ledger_name=normalized["partyLedgerName"],
            narration=normalized["narration"],
            warnings=normalized["warnings"],
            unknown_nodes=normalized.get("unknown_nodes", [])
        )

        # Create ledger entries
        for sort_order, ledger_data in enumerate(normalized["ledgerEntries"]):
            ledger = self._create_ledger_entry(voucher.voucher_id, ledger_data, sort_order)
            voucher.ledger_entries.append(ledger)

        # Create inventory entries
        for sort_order, inventory_data in enumerate(normalized["inventoryEntries"]):
            inventory = self._create_inventory_entry(voucher.voucher_id, inventory_data, sort_order)
            voucher.inventory_entries.append(inventory)

        return voucher

    def _create_ledger_entry(
        self,
        voucher_id: str,
        ledger_data: Dict[str, Any],
        sort_order: int
    ) -> LedgerEntry:
        """Create ledger entry with nested allocations"""
        ledger = LedgerEntry(
            entry_id=generate_ledger_entry_id(),
            voucher_id=voucher_id,
            source_tag=ledger_data["sourceTag"],
            sort_order=sort_order,
            ledger_name=ledger_data["ledgerName"],
            is_deemed_positive=ledger_data["isDeemedPositive"],
            amount=ledger_data["amount"]
        )

        # Bill allocations
        for bill_order, bill_data in enumerate(ledger_data["billAllocations"]):
            bill = BillAllocation(
                allocation_id=generate_allocation_id(),
                ledger_entry_id=ledger.entry_id,
                sort_order=bill_order,
                name=bill_data["name"],
                bill_type=bill_data["billType"],
                amount=bill_data["amount"]
            )
            ledger.bill_allocations.append(bill)

        # Bank allocations
        for bank_order, bank_data in enumerate(ledger_data["bankAllocations"]):
            bank = BankAllocation(
                allocation_id=generate_allocation_id(),
                ledger_entry_id=ledger.entry_id,
                sort_order=bank_order,
                date=bank_data["date"],
                name=bank_data["name"],
                transaction_type=bank_data["transactionType"],
                amount=bank_data["amount"]
            )
            ledger.bank_allocations.append(bank)

        # Rate details
        for rate_order, rate_data in enumerate(ledger_data["rateDetails"]):
            rate = RateDetail(
                rate_detail_id=generate_rate_detail_id(),
                ledger_entry_id=ledger.entry_id,
                sort_order=rate_order,
                duty_head=rate_data["dutyHead"],
                rate=rate_data["rate"]
            )
            ledger.rate_details.append(rate)

        return ledger

    def _create_inventory_entry(
        self,
        voucher_id: str,
        inventory_data: Dict[str, Any],
        sort_order: int
    ) -> InventoryEntry:
        """Create inventory entry with nested allocations"""
        inventory = InventoryEntry(
            entry_id=generate_inventory_entry_id(),
            voucher_id=voucher_id,
            source_tag=inventory_data["sourceTag"],
            sort_order=sort_order,
            stock_item_name=inventory_data["stockItemName"],
            is_deemed_positive=inventory_data["isDeemedPositive"],
            actual_qty=inventory_data["actualQty"],
            billed_qty=inventory_data["billedQty"],
            rate=inventory_data["rate"],
            amount=inventory_data["amount"]
        )

        # Batch allocations
        for batch_order, batch_data in enumerate(inventory_data["batchAllocations"]):
            batch = BatchAllocation(
                allocation_id=generate_allocation_id(),
                inventory_entry_id=inventory.entry_id,
                sort_order=batch_order,
                godown_name=batch_data["godownName"],
                batch_name=batch_data["batchName"],
                actual_qty=batch_data["actualQty"],
                billed_qty=batch_data["billedQty"],
                amount=batch_data["amount"]
            )
            inventory.batch_allocations.append(batch)

        # Accounting allocations
        for acc_order, acc_data in enumerate(inventory_data["accountingAllocations"]):
            accounting = AccountingAllocation(
                allocation_id=generate_allocation_id(),
                inventory_entry_id=inventory.entry_id,
                sort_order=acc_order,
                ledger_name=acc_data["ledgerName"],
                is_deemed_positive=acc_data["isDeemedPositive"],
                amount=acc_data["amount"]
            )

            # Rate details under accounting allocation
            for rate_order, rate_data in enumerate(acc_data["rateDetails"]):
                rate = RateDetail(
                    rate_detail_id=generate_rate_detail_id(),
                    accounting_allocation_id=accounting.allocation_id,
                    sort_order=rate_order,
                    duty_head=rate_data["dutyHead"],
                    rate=rate_data["rate"]
                )
                accounting.rate_details.append(rate)

            inventory.accounting_allocations.append(accounting)

        # Rate details under inventory itself
        for rate_order, rate_data in enumerate(inventory_data["rateDetails"]):
            rate = RateDetail(
                rate_detail_id=generate_rate_detail_id(),
                inventory_entry_id=inventory.entry_id,
                sort_order=rate_order,
                duty_head=rate_data["dutyHead"],
                rate=rate_data["rate"]
            )
            inventory.rate_details.append(rate)

        return inventory

    def _build_import_response(self, import_record: Import, duplicate: bool) -> Dict[str, Any]:
        """Build API response for import"""
        return {
            "importId": import_record.import_id,
            "documentType": import_record.document_type,
            "status": import_record.status,
            "duplicate": duplicate,
            "summary": import_record.summary
        }

    def get_import_details(self, import_id: str) -> Optional[Dict[str, Any]]:
        """Get full import details"""
        import_record = self.db.query(Import).filter(Import.import_id == import_id).first()
        if not import_record:
            return None

        details = {
            "importId": import_record.import_id,
            "documentType": import_record.document_type,
            "status": import_record.status,
            "contentHash": import_record.content_hash,
            "detectedEncoding": import_record.detected_encoding,
            "summary": import_record.summary,
            "warnings": import_record.warnings,
            "errors": import_record.errors
        }

        # Include tally response data if present
        if import_record.tally_response:
            details["tallyResponse"] = import_record.tally_response

        return details

    def get_normalized_vouchers(self, import_id: str) -> Dict[str, Any]:
        """Get normalized vouchers for an import"""
        import_record = self.db.query(Import).filter(Import.import_id == import_id).first()
        if not import_record:
            return {"items": [], "count": 0}

        vouchers = []
        for voucher in import_record.vouchers:
            normalized = self._build_normalized_voucher(voucher, import_record.content_hash)
            vouchers.append(normalized)

        return {"items": vouchers, "count": len(vouchers)}

    def _build_normalized_voucher(self, voucher: Voucher, content_hash: str) -> Dict[str, Any]:
        """Build normalized voucher JSON from database record"""
        normalized = {
            "source": {
                "importId": voucher.import_id,
                "contentHash": content_hash,
                "voucherIndex": voucher.voucher_index
            },
            "attributes": voucher.attributes,
            "date": voucher.date,
            "voucherType": voucher.voucher_type,
            "voucherNumber": voucher.voucher_number,
            "partyLedgerName": voucher.party_ledger_name,
            "narration": voucher.narration,
            "ledgerEntries": [],
            "inventoryEntries": [],
            "warnings": voucher.warnings
        }

        # Build ledger entries
        for ledger in sorted(voucher.ledger_entries, key=lambda x: x.sort_order):
            entry = {
                "sourceTag": ledger.source_tag,
                "ledgerName": ledger.ledger_name,
                "isDeemedPositive": ledger.is_deemed_positive,
                "amount": ledger.amount,
                "billAllocations": [],
                "bankAllocations": [],
                "rateDetails": []
            }

            # Bill allocations
            for bill in sorted(ledger.bill_allocations, key=lambda x: x.sort_order):
                entry["billAllocations"].append({
                    "name": bill.name,
                    "billType": bill.bill_type,
                    "amount": bill.amount
                })

            # Bank allocations
            for bank in sorted(ledger.bank_allocations, key=lambda x: x.sort_order):
                entry["bankAllocations"].append({
                    "date": bank.date,
                    "name": bank.name,
                    "transactionType": bank.transaction_type,
                    "amount": bank.amount
                })

            # Rate details
            for rate in sorted(ledger.rate_details, key=lambda x: x.sort_order):
                entry["rateDetails"].append({
                    "dutyHead": rate.duty_head,
                    "rate": rate.rate
                })

            normalized["ledgerEntries"].append(entry)

        # Build inventory entries
        for inventory in sorted(voucher.inventory_entries, key=lambda x: x.sort_order):
            entry = {
                "sourceTag": inventory.source_tag,
                "stockItemName": inventory.stock_item_name,
                "isDeemedPositive": inventory.is_deemed_positive,
                "actualQty": inventory.actual_qty,
                "billedQty": inventory.billed_qty,
                "rate": inventory.rate,
                "amount": inventory.amount,
                "batchAllocations": [],
                "accountingAllocations": [],
                "rateDetails": []
            }

            # Batch allocations
            for batch in sorted(inventory.batch_allocations, key=lambda x: x.sort_order):
                entry["batchAllocations"].append({
                    "godownName": batch.godown_name,
                    "batchName": batch.batch_name,
                    "actualQty": batch.actual_qty,
                    "billedQty": batch.billed_qty,
                    "amount": batch.amount
                })

            # Accounting allocations
            for accounting in sorted(inventory.accounting_allocations, key=lambda x: x.sort_order):
                acc_entry = {
                    "ledgerName": accounting.ledger_name,
                    "isDeemedPositive": accounting.is_deemed_positive,
                    "amount": accounting.amount,
                    "rateDetails": []
                }

                # Rate details under accounting
                for rate in sorted(accounting.rate_details, key=lambda x: x.sort_order):
                    acc_entry["rateDetails"].append({
                        "dutyHead": rate.duty_head,
                        "rate": rate.rate
                    })

                entry["accountingAllocations"].append(acc_entry)

            # Rate details under inventory
            for rate in sorted(inventory.rate_details, key=lambda x: x.sort_order):
                entry["rateDetails"].append({
                    "dutyHead": rate.duty_head,
                    "rate": rate.rate
                })

            normalized["inventoryEntries"].append(entry)

        return normalized
