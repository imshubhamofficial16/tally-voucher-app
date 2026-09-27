"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create imports table
    op.create_table(
        'imports',
        sa.Column('import_id', sa.String(64), primary_key=True),
        sa.Column('content_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('document_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('detected_encoding', sa.String(20)),
        sa.Column('raw_file_path', sa.String(500), nullable=False),
        sa.Column('summary', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('warnings', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('errors', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('tally_response', postgresql.JSONB),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )
    op.create_index('idx_imports_content_hash', 'imports', ['content_hash'], unique=True)

    # Create vouchers table
    op.create_table(
        'vouchers',
        sa.Column('voucher_id', sa.String(64), primary_key=True),
        sa.Column('import_id', sa.String(64), sa.ForeignKey('imports.import_id', ondelete='CASCADE'), nullable=False),
        sa.Column('voucher_index', sa.Integer, nullable=False),
        sa.Column('attributes', postgresql.JSONB, server_default='{}'),
        sa.Column('date', sa.String(20)),
        sa.Column('voucher_type', sa.String(100)),
        sa.Column('voucher_number', sa.String(100)),
        sa.Column('party_ledger_name', sa.String(200)),
        sa.Column('narration', sa.Text),
        sa.Column('warnings', postgresql.JSONB, server_default='[]'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )
    op.create_index('idx_vouchers_import', 'vouchers', ['import_id'])

    # Create ledger_entries table
    op.create_table(
        'ledger_entries',
        sa.Column('entry_id', sa.String(64), primary_key=True),
        sa.Column('voucher_id', sa.String(64), sa.ForeignKey('vouchers.voucher_id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_tag', sa.String(50), nullable=False),
        sa.Column('sort_order', sa.Integer, nullable=False),
        sa.Column('ledger_name', sa.String(200)),
        sa.Column('is_deemed_positive', sa.String(10)),
        sa.Column('amount', sa.Text),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )
    op.create_index('idx_ledger_voucher', 'ledger_entries', ['voucher_id'])

    # Create bill_allocations table
    op.create_table(
        'bill_allocations',
        sa.Column('allocation_id', sa.String(64), primary_key=True),
        sa.Column('ledger_entry_id', sa.String(64), sa.ForeignKey('ledger_entries.entry_id', ondelete='CASCADE'), nullable=False),
        sa.Column('sort_order', sa.Integer, nullable=False),
        sa.Column('name', sa.String(200)),
        sa.Column('bill_type', sa.String(50)),
        sa.Column('amount', sa.Text),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )
    op.create_index('idx_bill_ledger', 'bill_allocations', ['ledger_entry_id'])

    # Create bank_allocations table
    op.create_table(
        'bank_allocations',
        sa.Column('allocation_id', sa.String(64), primary_key=True),
        sa.Column('ledger_entry_id', sa.String(64), sa.ForeignKey('ledger_entries.entry_id', ondelete='CASCADE'), nullable=False),
        sa.Column('sort_order', sa.Integer, nullable=False),
        sa.Column('date', sa.String(20)),
        sa.Column('name', sa.String(200)),
        sa.Column('transaction_type', sa.String(100)),
        sa.Column('amount', sa.Text),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )
    op.create_index('idx_bank_ledger', 'bank_allocations', ['ledger_entry_id'])

    # Create inventory_entries table
    op.create_table(
        'inventory_entries',
        sa.Column('entry_id', sa.String(64), primary_key=True),
        sa.Column('voucher_id', sa.String(64), sa.ForeignKey('vouchers.voucher_id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_tag', sa.String(50), nullable=False),
        sa.Column('sort_order', sa.Integer, nullable=False),
        sa.Column('stock_item_name', sa.String(200)),
        sa.Column('is_deemed_positive', sa.String(10)),
        sa.Column('actual_qty', sa.Text),
        sa.Column('billed_qty', sa.Text),
        sa.Column('rate', sa.Text),
        sa.Column('amount', sa.Text),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )
    op.create_index('idx_inventory_voucher', 'inventory_entries', ['voucher_id'])

    # Create batch_allocations table
    op.create_table(
        'batch_allocations',
        sa.Column('allocation_id', sa.String(64), primary_key=True),
        sa.Column('inventory_entry_id', sa.String(64), sa.ForeignKey('inventory_entries.entry_id', ondelete='CASCADE'), nullable=False),
        sa.Column('sort_order', sa.Integer, nullable=False),
        sa.Column('godown_name', sa.String(200)),
        sa.Column('batch_name', sa.String(200)),
        sa.Column('actual_qty', sa.Text),
        sa.Column('billed_qty', sa.Text),
        sa.Column('amount', sa.Text),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )
    op.create_index('idx_batch_inventory', 'batch_allocations', ['inventory_entry_id'])

    # Create accounting_allocations table
    op.create_table(
        'accounting_allocations',
        sa.Column('allocation_id', sa.String(64), primary_key=True),
        sa.Column('inventory_entry_id', sa.String(64), sa.ForeignKey('inventory_entries.entry_id', ondelete='CASCADE'), nullable=False),
        sa.Column('sort_order', sa.Integer, nullable=False),
        sa.Column('ledger_name', sa.String(200)),
        sa.Column('is_deemed_positive', sa.String(10)),
        sa.Column('amount', sa.Text),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )
    op.create_index('idx_accounting_inventory', 'accounting_allocations', ['inventory_entry_id'])

    # Create rate_details table (polymorphic)
    op.create_table(
        'rate_details',
        sa.Column('rate_detail_id', sa.String(64), primary_key=True),
        sa.Column('sort_order', sa.Integer, nullable=False),
        sa.Column('ledger_entry_id', sa.String(64), sa.ForeignKey('ledger_entries.entry_id', ondelete='CASCADE')),
        sa.Column('inventory_entry_id', sa.String(64), sa.ForeignKey('inventory_entries.entry_id', ondelete='CASCADE')),
        sa.Column('accounting_allocation_id', sa.String(64), sa.ForeignKey('accounting_allocations.allocation_id', ondelete='CASCADE')),
        sa.Column('duty_head', sa.String(100)),
        sa.Column('rate', sa.Text),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now())
    )


def downgrade() -> None:
    op.drop_table('rate_details')
    op.drop_table('accounting_allocations')
    op.drop_table('batch_allocations')
    op.drop_table('inventory_entries')
    op.drop_table('bank_allocations')
    op.drop_table('bill_allocations')
    op.drop_table('ledger_entries')
    op.drop_table('vouchers')
    op.drop_table('imports')
