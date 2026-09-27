"""
Utility functions for hashing and ID generation
"""
import hashlib
import uuid


def compute_sha256(data: bytes) -> str:
    """
    Compute SHA-256 hash of bytes
    Returns lowercase hexadecimal string
    """
    return hashlib.sha256(data).hexdigest().lower()


def generate_import_id() -> str:
    """Generate unique import ID"""
    return f"imp_{uuid.uuid4().hex[:16]}"


def generate_voucher_id() -> str:
    """Generate unique voucher ID"""
    return f"vch_{uuid.uuid4().hex[:16]}"


def generate_ledger_entry_id() -> str:
    """Generate unique ledger entry ID"""
    return f"led_{uuid.uuid4().hex[:16]}"


def generate_inventory_entry_id() -> str:
    """Generate unique inventory entry ID"""
    return f"inv_{uuid.uuid4().hex[:16]}"


def generate_allocation_id() -> str:
    """Generate unique allocation ID"""
    return f"alc_{uuid.uuid4().hex[:16]}"


def generate_rate_detail_id() -> str:
    """Generate unique rate detail ID"""
    return f"rate_{uuid.uuid4().hex[:16]}"
