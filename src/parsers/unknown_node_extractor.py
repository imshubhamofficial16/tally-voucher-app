"""
Unknown Node Extractor
Extracts and preserves unknown/unsupported XML nodes for inspection
"""
from typing import List, Dict, Any, Set
from lxml import etree


class UnknownNodeExtractor:
    """
    Extracts unknown XML nodes that aren't part of the normalized schema
    Preserves path, tag name, attributes, and text content
    """

    # Known/supported tags in voucher structure
    KNOWN_VOUCHER_TAGS = {
        "DATE", "VOUCHERTYPENAME", "VOUCHERNUMBER", "PARTYLEDGERNAME", "NARRATION",
        "ALLLEDGERENTRIES.LIST", "LEDGERENTRIES.LIST", "ALLINVENTORYENTRIES.LIST"
    }

    KNOWN_LEDGER_TAGS = {
        "LEDGERNAME", "ISDEEMEDPOSITIVE", "AMOUNT",
        "BILLALLOCATIONS.LIST", "BANKALLOCATIONS.LIST", "RATEDETAILS.LIST"
    }

    KNOWN_BILL_ALLOCATION_TAGS = {
        "NAME", "BILLTYPE", "AMOUNT"
    }

    KNOWN_BANK_ALLOCATION_TAGS = {
        "DATE", "NAME", "TRANSACTIONTYPE", "AMOUNT"
    }

    KNOWN_INVENTORY_TAGS = {
        "STOCKITEMNAME", "ISDEEMEDPOSITIVE", "ACTUALQTY", "BILLEDQTY", "RATE", "AMOUNT",
        "BATCHALLOCATIONS.LIST", "ACCOUNTINGALLOCATIONS.LIST", "RATEDETAILS.LIST"
    }

    KNOWN_BATCH_ALLOCATION_TAGS = {
        "GODOWNNAME", "BATCHNAME", "ACTUALQTY", "BILLEDQTY", "AMOUNT"
    }

    KNOWN_ACCOUNTING_ALLOCATION_TAGS = {
        "LEDGERNAME", "ISDEEMEDPOSITIVE", "AMOUNT", "RATEDETAILS.LIST"
    }

    KNOWN_RATE_DETAIL_TAGS = {
        "GSTRATEDUTYHEAD", "GSTRATE"
    }

    def extract_unknown_nodes(
        self,
        voucher_element: etree._Element,
        voucher_index: int
    ) -> List[Dict[str, Any]]:
        """
        Extract all unknown nodes from a voucher

        Returns:
            List of dictionaries with:
            - path: XPath-like path to the node
            - tag: Tag name
            - text: Text content (if any)
            - attributes: Dictionary of attributes
            - parent_context: What the parent was
        """
        unknown_nodes = []

        # Check voucher level
        for child in voucher_element:
            tag = child.tag
            if tag not in self.KNOWN_VOUCHER_TAGS:
                unknown_nodes.append(self._create_node_info(
                    path=f"VOUCHER[{voucher_index}]/{tag}",
                    element=child,
                    parent_context="VOUCHER"
                ))

        # Check ledger entries
        for ledger_idx, ledger in enumerate(voucher_element.findall("ALLLEDGERENTRIES.LIST")):
            unknown_nodes.extend(
                self._extract_from_ledger(ledger, voucher_index, ledger_idx, "ALLLEDGERENTRIES.LIST")
            )

        for ledger_idx, ledger in enumerate(voucher_element.findall("LEDGERENTRIES.LIST")):
            unknown_nodes.extend(
                self._extract_from_ledger(ledger, voucher_index, ledger_idx, "LEDGERENTRIES.LIST")
            )

        # Check inventory entries
        for inv_idx, inventory in enumerate(voucher_element.findall("ALLINVENTORYENTRIES.LIST")):
            unknown_nodes.extend(
                self._extract_from_inventory(inventory, voucher_index, inv_idx)
            )

        return unknown_nodes

    def _extract_from_ledger(
        self,
        ledger_element: etree._Element,
        voucher_idx: int,
        ledger_idx: int,
        source_tag: str
    ) -> List[Dict[str, Any]]:
        """Extract unknown nodes from ledger entry"""
        unknown = []

        for child in ledger_element:
            tag = child.tag

            # Check if tag is known
            if tag not in self.KNOWN_LEDGER_TAGS:
                unknown.append(self._create_node_info(
                    path=f"VOUCHER[{voucher_idx}]/{source_tag}[{ledger_idx}]/{tag}",
                    element=child,
                    parent_context=source_tag
                ))

            # Check bill allocations
            elif tag == "BILLALLOCATIONS.LIST":
                for bill_idx, bill in enumerate(ledger_element.findall("BILLALLOCATIONS.LIST")):
                    for bill_child in bill:
                        if bill_child.tag not in self.KNOWN_BILL_ALLOCATION_TAGS:
                            unknown.append(self._create_node_info(
                                path=f"VOUCHER[{voucher_idx}]/{source_tag}[{ledger_idx}]/BILLALLOCATIONS.LIST[{bill_idx}]/{bill_child.tag}",
                                element=bill_child,
                                parent_context="BILLALLOCATIONS.LIST"
                            ))

            # Check bank allocations
            elif tag == "BANKALLOCATIONS.LIST":
                for bank_idx, bank in enumerate(ledger_element.findall("BANKALLOCATIONS.LIST")):
                    for bank_child in bank:
                        if bank_child.tag not in self.KNOWN_BANK_ALLOCATION_TAGS:
                            unknown.append(self._create_node_info(
                                path=f"VOUCHER[{voucher_idx}]/{source_tag}[{ledger_idx}]/BANKALLOCATIONS.LIST[{bank_idx}]/{bank_child.tag}",
                                element=bank_child,
                                parent_context="BANKALLOCATIONS.LIST"
                            ))

        return unknown

    def _extract_from_inventory(
        self,
        inventory_element: etree._Element,
        voucher_idx: int,
        inv_idx: int
    ) -> List[Dict[str, Any]]:
        """Extract unknown nodes from inventory entry"""
        unknown = []

        for child in inventory_element:
            tag = child.tag

            if tag not in self.KNOWN_INVENTORY_TAGS:
                unknown.append(self._create_node_info(
                    path=f"VOUCHER[{voucher_idx}]/ALLINVENTORYENTRIES.LIST[{inv_idx}]/{tag}",
                    element=child,
                    parent_context="ALLINVENTORYENTRIES.LIST"
                ))

            # Check batch allocations
            elif tag == "BATCHALLOCATIONS.LIST":
                for batch_idx, batch in enumerate(inventory_element.findall("BATCHALLOCATIONS.LIST")):
                    for batch_child in batch:
                        if batch_child.tag not in self.KNOWN_BATCH_ALLOCATION_TAGS:
                            unknown.append(self._create_node_info(
                                path=f"VOUCHER[{voucher_idx}]/ALLINVENTORYENTRIES.LIST[{inv_idx}]/BATCHALLOCATIONS.LIST[{batch_idx}]/{batch_child.tag}",
                                element=batch_child,
                                parent_context="BATCHALLOCATIONS.LIST"
                            ))

            # Check accounting allocations
            elif tag == "ACCOUNTINGALLOCATIONS.LIST":
                for acc_idx, acc in enumerate(inventory_element.findall("ACCOUNTINGALLOCATIONS.LIST")):
                    for acc_child in acc:
                        if acc_child.tag not in self.KNOWN_ACCOUNTING_ALLOCATION_TAGS:
                            unknown.append(self._create_node_info(
                                path=f"VOUCHER[{voucher_idx}]/ALLINVENTORYENTRIES.LIST[{inv_idx}]/ACCOUNTINGALLOCATIONS.LIST[{acc_idx}]/{acc_child.tag}",
                                element=acc_child,
                                parent_context="ACCOUNTINGALLOCATIONS.LIST"
                            ))

        return unknown

    def _create_node_info(
        self,
        path: str,
        element: etree._Element,
        parent_context: str
    ) -> Dict[str, Any]:
        """Create information dictionary for an unknown node"""
        return {
            "path": path,
            "tag": element.tag,
            "text": element.text.strip() if element.text else None,
            "attributes": dict(element.attrib) if element.attrib else {},
            "parent_context": parent_context,
            "has_children": len(element) > 0,
            "child_count": len(element)
        }

    def summarize_unknown_nodes(
        self,
        unknown_nodes: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create summary of unknown nodes for warnings

        Returns:
            Dictionary with:
            - total_count: Number of unknown nodes
            - unique_tags: Set of unique tag names
            - paths: List of unique paths
        """
        if not unknown_nodes:
            return {
                "total_count": 0,
                "unique_tags": [],
                "paths": []
            }

        unique_tags = set(node["tag"] for node in unknown_nodes)
        unique_paths = list(set(node["path"] for node in unknown_nodes))

        return {
            "total_count": len(unknown_nodes),
            "unique_tags": sorted(list(unique_tags)),
            "paths": sorted(unique_paths)[:10]  # Limit to first 10 for readability
        }
