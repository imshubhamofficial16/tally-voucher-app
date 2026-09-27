"""Add unknown nodes storage

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add unknown_nodes column to vouchers table
    op.add_column(
        'vouchers',
        sa.Column('unknown_nodes', postgresql.JSONB, server_default='[]')
    )

    # Add unknown_nodes_summary to imports table
    op.add_column(
        'imports',
        sa.Column('unknown_nodes_summary', postgresql.JSONB, server_default='{}')
    )


def downgrade() -> None:
    op.drop_column('vouchers', 'unknown_nodes')
    op.drop_column('imports', 'unknown_nodes_summary')
