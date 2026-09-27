from sqlalchemy import Column, String, Integer, Text, ForeignKey, UniqueConstraint, Index, TIMESTAMP, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.database import Base

# Use JSONB for PostgreSQL, JSON for SQLite
import os
db_url = os.getenv("DATABASE_URL", "")
JSONType = JSONB if "postgresql" in db_url else JSON


class Import(Base):
    """Represents a Tally XML import"""
    __tablename__ = "imports"

    import_id = Column(String(64), primary_key=True)
    content_hash = Column(String(64), nullable=False, unique=True, index=True)
    document_type = Column(String(50), nullable=False)  # voucherExport or tallyResponse
    status = Column(String(20), nullable=False)  # completed, partial, failed
    detected_encoding = Column(String(20))
    raw_file_path = Column(String(500), nullable=False)

    # Summary counts stored as JSON
    summary = Column(JSONType, nullable=False, default={})

    # Warnings and errors as JSON arrays
    warnings = Column(JSONType, nullable=False, default=[])
    errors = Column(JSONType, nullable=False, default=[])

    # For tallyResponse documents
    tally_response = Column(JSONType)  # Contains businessStatus, counters, lineError

    # Unknown nodes summary across all vouchers
    unknown_nodes_summary = Column(JSONType, default={})

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    vouchers = relationship("Voucher", back_populates="import_record", cascade="all, delete-orphan")


class Voucher(Base):
    """Represents a voucher from Tally XML"""
    __tablename__ = "vouchers"

    voucher_id = Column(String(64), primary_key=True)
    import_id = Column(String(64), ForeignKey("imports.import_id", ondelete="CASCADE"), nullable=False)
    voucher_index = Column(Integer, nullable=False)  # Zero-based source order

    # Voucher attributes (VCHTYPE, ACTION)
    attributes = Column(JSONType, default={})

    # Direct voucher children
    date = Column(String(20))
    voucher_type = Column(String(100))
    voucher_number = Column(String(100))
    party_ledger_name = Column(String(200))
    narration = Column(Text)

    # Voucher-level warnings
    warnings = Column(JSONType, default=[])

    # Unknown nodes found in this voucher
    unknown_nodes = Column(JSONType, default=[])

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    import_record = relationship("Import", back_populates="vouchers")
    ledger_entries = relationship("LedgerEntry", back_populates="voucher", cascade="all, delete-orphan")
    inventory_entries = relationship("InventoryEntry", back_populates="voucher", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_vouchers_import", "import_id"),
    )


class LedgerEntry(Base):
    """Represents ALLLEDGERENTRIES.LIST or LEDGERENTRIES.LIST"""
    __tablename__ = "ledger_entries"

    entry_id = Column(String(64), primary_key=True)
    voucher_id = Column(String(64), ForeignKey("vouchers.voucher_id", ondelete="CASCADE"), nullable=False)
    source_tag = Column(String(50), nullable=False)  # ALLLEDGERENTRIES.LIST or LEDGERENTRIES.LIST
    sort_order = Column(Integer, nullable=False)  # Preserve source order

    ledger_name = Column(String(200))
    is_deemed_positive = Column(String(10))  # Store as-is: "Yes", "No"
    amount = Column(Text)  # Store as text for lossless precision

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    voucher = relationship("Voucher", back_populates="ledger_entries")
    bill_allocations = relationship("BillAllocation", back_populates="ledger_entry", cascade="all, delete-orphan")
    bank_allocations = relationship("BankAllocation", back_populates="ledger_entry", cascade="all, delete-orphan")
    rate_details = relationship("RateDetail",
                              foreign_keys="[RateDetail.ledger_entry_id]",
                              back_populates="ledger_entry",
                              cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_ledger_voucher", "voucher_id"),
    )


class BillAllocation(Base):
    """Bill allocations under ledger entries"""
    __tablename__ = "bill_allocations"

    allocation_id = Column(String(64), primary_key=True)
    ledger_entry_id = Column(String(64), ForeignKey("ledger_entries.entry_id", ondelete="CASCADE"), nullable=False)
    sort_order = Column(Integer, nullable=False)

    name = Column(String(200))
    bill_type = Column(String(50))
    amount = Column(Text)  # Lossless

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    ledger_entry = relationship("LedgerEntry", back_populates="bill_allocations")

    __table_args__ = (
        Index("idx_bill_ledger", "ledger_entry_id"),
    )


class BankAllocation(Base):
    """Bank allocations under ledger entries"""
    __tablename__ = "bank_allocations"

    allocation_id = Column(String(64), primary_key=True)
    ledger_entry_id = Column(String(64), ForeignKey("ledger_entries.entry_id", ondelete="CASCADE"), nullable=False)
    sort_order = Column(Integer, nullable=False)

    date = Column(String(20))
    name = Column(String(200))
    transaction_type = Column(String(100))
    amount = Column(Text)  # Lossless

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    ledger_entry = relationship("LedgerEntry", back_populates="bank_allocations")

    __table_args__ = (
        Index("idx_bank_ledger", "ledger_entry_id"),
    )


class InventoryEntry(Base):
    """Represents ALLINVENTORYENTRIES.LIST"""
    __tablename__ = "inventory_entries"

    entry_id = Column(String(64), primary_key=True)
    voucher_id = Column(String(64), ForeignKey("vouchers.voucher_id", ondelete="CASCADE"), nullable=False)
    source_tag = Column(String(50), nullable=False)  # ALLINVENTORYENTRIES.LIST
    sort_order = Column(Integer, nullable=False)

    stock_item_name = Column(String(200))
    is_deemed_positive = Column(String(10))
    actual_qty = Column(Text)  # Keep with units: "2 PCS"
    billed_qty = Column(Text)  # Keep with units
    rate = Column(Text)  # Keep with units: "50.00/PCS"
    amount = Column(Text)  # Lossless

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    voucher = relationship("Voucher", back_populates="inventory_entries")
    batch_allocations = relationship("BatchAllocation", back_populates="inventory_entry", cascade="all, delete-orphan")
    accounting_allocations = relationship("AccountingAllocation", back_populates="inventory_entry", cascade="all, delete-orphan")
    rate_details = relationship("RateDetail",
                              foreign_keys="[RateDetail.inventory_entry_id]",
                              back_populates="inventory_entry",
                              cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_inventory_voucher", "voucher_id"),
    )


class BatchAllocation(Base):
    """Batch allocations under inventory entries"""
    __tablename__ = "batch_allocations"

    allocation_id = Column(String(64), primary_key=True)
    inventory_entry_id = Column(String(64), ForeignKey("inventory_entries.entry_id", ondelete="CASCADE"), nullable=False)
    sort_order = Column(Integer, nullable=False)

    godown_name = Column(String(200))
    batch_name = Column(String(200))
    actual_qty = Column(Text)
    billed_qty = Column(Text)
    amount = Column(Text)  # Lossless

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    inventory_entry = relationship("InventoryEntry", back_populates="batch_allocations")

    __table_args__ = (
        Index("idx_batch_inventory", "inventory_entry_id"),
    )


class AccountingAllocation(Base):
    """Accounting allocations under inventory entries"""
    __tablename__ = "accounting_allocations"

    allocation_id = Column(String(64), primary_key=True)
    inventory_entry_id = Column(String(64), ForeignKey("inventory_entries.entry_id", ondelete="CASCADE"), nullable=False)
    sort_order = Column(Integer, nullable=False)

    ledger_name = Column(String(200))
    is_deemed_positive = Column(String(10))
    amount = Column(Text)  # Lossless

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    inventory_entry = relationship("InventoryEntry", back_populates="accounting_allocations")
    rate_details = relationship("RateDetail",
                              foreign_keys="[RateDetail.accounting_allocation_id]",
                              back_populates="accounting_allocation",
                              cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_accounting_inventory", "inventory_entry_id"),
    )


class RateDetail(Base):
    """Rate details - polymorphic: can belong to ledger, inventory, or accounting allocation"""
    __tablename__ = "rate_details"

    rate_detail_id = Column(String(64), primary_key=True)
    sort_order = Column(Integer, nullable=False)

    # Polymorphic foreign keys (only one should be set)
    ledger_entry_id = Column(String(64), ForeignKey("ledger_entries.entry_id", ondelete="CASCADE"))
    inventory_entry_id = Column(String(64), ForeignKey("inventory_entries.entry_id", ondelete="CASCADE"))
    accounting_allocation_id = Column(String(64), ForeignKey("accounting_allocations.allocation_id", ondelete="CASCADE"))

    duty_head = Column(String(100))
    rate = Column(Text)  # Store as text

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    # Relationships
    ledger_entry = relationship("LedgerEntry", foreign_keys=[ledger_entry_id], back_populates="rate_details")
    inventory_entry = relationship("InventoryEntry", foreign_keys=[inventory_entry_id], back_populates="rate_details")
    accounting_allocation = relationship("AccountingAllocation", foreign_keys=[accounting_allocation_id], back_populates="rate_details")
