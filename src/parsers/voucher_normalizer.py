"""
Voucher Normalizer
Converts parsed XML tree to normalized JSON structure
Preserves parent-child relationships and source order
"""
from typing import Dict, Any, List, Optional
from lxml import etree


class VoucherNormalizer:
    """
    Normalizes Tally voucher XML to the required JSON contract
    """

    @staticmethod
    def get_text(element: etree._Element, tag: str) -> Optional[str]:
        """Get text from direct child element"""
        child = element.find(tag)
        if child is not None and child.text:
            return child.text.strip()
        return None

    @staticmethod
    def get_attribute(element: etree._Element, attr: str) -> Optional[str]:
        """Get attribute value from element"""
        return element.get(attr)

    def normalize_voucher(
        self,
        voucher_element: etree._Element,
        voucher_index: int,
        import_id: str,
        content_hash: str
    ) -> Dict[str, Any]:
        """
        Normalize a single voucher element
        """
        normalized = {
            "source": {
                "importId": import_id,
                "contentHash": content_hash,
                "voucherIndex": voucher_index
            },
            "attributes": {},
            "date": None,
            "voucherType": None,
            "voucherNumber": None,
            "partyLedgerName": None,
            "narration": None,
            "ledgerEntries": [],
            "inventoryEntries": [],
            "warnings": []
        }

        # Extract attributes
        vchtype = self.get_attribute(voucher_element, "VCHTYPE")
        action = self.get_attribute(voucher_element, "ACTION")
        if vchtype:
            normalized["attributes"]["VCHTYPE"] = vchtype
        if action:
            normalized["attributes"]["ACTION"] = action

        # Extract direct voucher children
        normalized["date"] = self.get_text(voucher_element, "DATE")
        normalized["voucherType"] = self.get_text(voucher_element, "VOUCHERTYPENAME")
        normalized["voucherNumber"] = self.get_text(voucher_element, "VOUCHERNUMBER")
        normalized["partyLedgerName"] = self.get_text(voucher_element, "PARTYLEDGERNAME")
        normalized["narration"] = self.get_text(voucher_element, "NARRATION")

        # Extract ledger entries
        normalized["ledgerEntries"] = self._normalize_ledger_entries(voucher_element)

        # Extract inventory entries
        normalized["inventoryEntries"] = self._normalize_inventory_entries(voucher_element)

        return normalized

    def _normalize_ledger_entries(self, voucher: etree._Element) -> List[Dict[str, Any]]:
        """
        Normalize ALLLEDGERENTRIES.LIST and LEDGERENTRIES.LIST
        Preserves source tag and order
        """
        entries = []

        # Process ALLLEDGERENTRIES.LIST
        all_ledger_lists = voucher.findall("ALLLEDGERENTRIES.LIST")
        for ledger in all_ledger_lists:
            entry = self._normalize_single_ledger_entry(ledger, "ALLLEDGERENTRIES.LIST")
            entries.append(entry)

        # Process LEDGERENTRIES.LIST
        ledger_lists = voucher.findall("LEDGERENTRIES.LIST")
        for ledger in ledger_lists:
            entry = self._normalize_single_ledger_entry(ledger, "LEDGERENTRIES.LIST")
            entries.append(entry)

        return entries

    def _normalize_single_ledger_entry(
        self,
        ledger: etree._Element,
        source_tag: str
    ) -> Dict[str, Any]:
        """Normalize a single ledger entry"""
        entry = {
            "sourceTag": source_tag,
            "ledgerName": self.get_text(ledger, "LEDGERNAME"),
            "isDeemedPositive": self.get_text(ledger, "ISDEEMEDPOSITIVE"),
            "amount": self.get_text(ledger, "AMOUNT"),
            "billAllocations": [],
            "bankAllocations": [],
            "rateDetails": []
        }

        # Extract bill allocations
        bill_allocs = ledger.findall("BILLALLOCATIONS.LIST")
        for bill in bill_allocs:
            entry["billAllocations"].append({
                "name": self.get_text(bill, "NAME"),
                "billType": self.get_text(bill, "BILLTYPE"),
                "amount": self.get_text(bill, "AMOUNT")
            })

        # Extract bank allocations
        bank_allocs = ledger.findall("BANKALLOCATIONS.LIST")
        for bank in bank_allocs:
            entry["bankAllocations"].append({
                "date": self.get_text(bank, "DATE"),
                "name": self.get_text(bank, "NAME"),
                "transactionType": self.get_text(bank, "TRANSACTIONTYPE"),
                "amount": self.get_text(bank, "AMOUNT")
            })

        # Extract rate details from ledger
        rate_details = ledger.findall("RATEDETAILS.LIST")
        for rate in rate_details:
            entry["rateDetails"].append({
                "dutyHead": self.get_text(rate, "GSTRATEDUTYHEAD"),
                "rate": self.get_text(rate, "GSTRATE")
            })

        return entry

    def _normalize_inventory_entries(self, voucher: etree._Element) -> List[Dict[str, Any]]:
        """
        Normalize ALLINVENTORYENTRIES.LIST
        Preserves nested allocations and rate details
        """
        entries = []

        # Process ALLINVENTORYENTRIES.LIST
        inventory_lists = voucher.findall("ALLINVENTORYENTRIES.LIST")
        for inventory in inventory_lists:
            entry = {
                "sourceTag": "ALLINVENTORYENTRIES.LIST",
                "stockItemName": self.get_text(inventory, "STOCKITEMNAME"),
                "isDeemedPositive": self.get_text(inventory, "ISDEEMEDPOSITIVE"),
                "actualQty": self.get_text(inventory, "ACTUALQTY"),
                "billedQty": self.get_text(inventory, "BILLEDQTY"),
                "rate": self.get_text(inventory, "RATE"),
                "amount": self.get_text(inventory, "AMOUNT"),
                "batchAllocations": [],
                "accountingAllocations": [],
                "rateDetails": []
            }

            # Extract batch allocations
            batch_allocs = inventory.findall("BATCHALLOCATIONS.LIST")
            for batch in batch_allocs:
                entry["batchAllocations"].append({
                    "godownName": self.get_text(batch, "GODOWNNAME"),
                    "batchName": self.get_text(batch, "BATCHNAME"),
                    "actualQty": self.get_text(batch, "ACTUALQTY"),
                    "billedQty": self.get_text(batch, "BILLEDQTY"),
                    "amount": self.get_text(batch, "AMOUNT")
                })

            # Extract accounting allocations
            accounting_allocs = inventory.findall("ACCOUNTINGALLOCATIONS.LIST")
            for accounting in accounting_allocs:
                accounting_entry = {
                    "ledgerName": self.get_text(accounting, "LEDGERNAME"),
                    "isDeemedPositive": self.get_text(accounting, "ISDEEMEDPOSITIVE"),
                    "amount": self.get_text(accounting, "AMOUNT"),
                    "rateDetails": []
                }

                # Extract rate details from accounting allocation
                rate_details = accounting.findall("RATEDETAILS.LIST")
                for rate in rate_details:
                    accounting_entry["rateDetails"].append({
                        "dutyHead": self.get_text(rate, "GSTRATEDUTYHEAD"),
                        "rate": self.get_text(rate, "GSTRATE")
                    })

                entry["accountingAllocations"].append(accounting_entry)

            # Extract rate details from inventory itself
            rate_details = inventory.findall("RATEDETAILS.LIST")
            for rate in rate_details:
                entry["rateDetails"].append({
                    "dutyHead": self.get_text(rate, "GSTRATEDUTYHEAD"),
                    "rate": self.get_text(rate, "GSTRATE")
                })

            entries.append(entry)

        return entries
