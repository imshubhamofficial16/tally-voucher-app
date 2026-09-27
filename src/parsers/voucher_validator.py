"""
Voucher Validator
Validates individual vouchers for required fields
"""
from typing import Dict, Any, List, Optional
from lxml import etree


class VoucherValidationResult:
    """Result of voucher validation"""
    def __init__(self, is_valid: bool, errors: List[str]):
        self.is_valid = is_valid
        self.errors = errors


class VoucherValidator:
    """
    Validates vouchers according to business rules
    Per-voucher partial failure extension
    """

    # Required fields for a valid voucher
    REQUIRED_FIELDS = ["DATE", "VOUCHERTYPENAME", "VOUCHERNUMBER"]

    @staticmethod
    def get_direct_child_text(element: etree._Element, tag: str) -> Optional[str]:
        """Get text from direct child element"""
        child = element.find(tag)
        if child is not None and child.text:
            text = child.text.strip()
            return text if text else None
        return None

    def validate_voucher(self, voucher_element: etree._Element) -> VoucherValidationResult:
        """
        Validate a voucher element for required fields

        Required fields:
        - DATE: Must be present and non-empty
        - VOUCHERTYPENAME: Must be present and non-empty
        - VOUCHERNUMBER: Must be present and non-empty

        Returns:
            VoucherValidationResult with is_valid flag and list of errors
        """
        errors = []

        for field in self.REQUIRED_FIELDS:
            value = self.get_direct_child_text(voucher_element, field)
            if value is None or value == "":
                errors.append(f"Missing or empty required field: {field}")

        is_valid = len(errors) == 0

        return VoucherValidationResult(is_valid=is_valid, errors=errors)

    def validate_vouchers(
        self,
        voucher_elements: List[etree._Element]
    ) -> Dict[str, Any]:
        """
        Validate multiple vouchers

        Returns:
            Dictionary with:
            - valid_vouchers: List of (index, element) tuples for valid vouchers
            - invalid_vouchers: List of (index, element, errors) tuples for invalid vouchers
            - total_count: Total number of vouchers
            - valid_count: Number of valid vouchers
            - invalid_count: Number of invalid vouchers
        """
        valid_vouchers = []
        invalid_vouchers = []

        for index, voucher_element in enumerate(voucher_elements):
            result = self.validate_voucher(voucher_element)

            if result.is_valid:
                valid_vouchers.append((index, voucher_element))
            else:
                invalid_vouchers.append((index, voucher_element, result.errors))

        return {
            "valid_vouchers": valid_vouchers,
            "invalid_vouchers": invalid_vouchers,
            "total_count": len(voucher_elements),
            "valid_count": len(valid_vouchers),
            "invalid_count": len(invalid_vouchers)
        }
