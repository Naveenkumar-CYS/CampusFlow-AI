"""create audit records table

Revision ID: e4f1a9c7d3b6
Revises: 9b3e5d1f7a02
Create Date: 2026-08-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e4f1a9c7d3b6'
down_revision: Union[str, Sequence[str], None] = '9b3e5d1f7a02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'automation_audit_records',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('audit_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('component', sa.String(length=50), nullable=False),
        sa.Column('event_id', sa.String(length=64), nullable=True),
        sa.Column('workflow_id', sa.String(length=120), nullable=True),
        sa.Column('execution_id', sa.UUID(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=True),
        sa.Column('entity_type', sa.String(length=50), nullable=True),
        sa.Column('entity_id', sa.String(length=120), nullable=True),
        sa.Column('error_type', sa.String(length=120), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('context', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['execution_id'], ['automation_executions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_automation_audit_records_audit_type'), 'automation_audit_records', ['audit_type'], unique=False
    )
    op.create_index(
        op.f('ix_automation_audit_records_status'), 'automation_audit_records', ['status'], unique=False
    )
    op.create_index(
        op.f('ix_automation_audit_records_event_id'), 'automation_audit_records', ['event_id'], unique=False
    )
    op.create_index(
        op.f('ix_automation_audit_records_workflow_id'), 'automation_audit_records', ['workflow_id'], unique=False
    )
    op.create_index(
        op.f('ix_automation_audit_records_execution_id'), 'automation_audit_records', ['execution_id'], unique=False
    )
    op.create_index(
        op.f('ix_automation_audit_records_event_type'), 'automation_audit_records', ['event_type'], unique=False
    )
    op.create_index(
        'ix_audit_records_created_at', 'automation_audit_records', ['created_at'], unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_audit_records_created_at', table_name='automation_audit_records')
    op.drop_index(op.f('ix_automation_audit_records_event_type'), table_name='automation_audit_records')
    op.drop_index(op.f('ix_automation_audit_records_execution_id'), table_name='automation_audit_records')
    op.drop_index(op.f('ix_automation_audit_records_workflow_id'), table_name='automation_audit_records')
    op.drop_index(op.f('ix_automation_audit_records_event_id'), table_name='automation_audit_records')
    op.drop_index(op.f('ix_automation_audit_records_status'), table_name='automation_audit_records')
    op.drop_index(op.f('ix_automation_audit_records_audit_type'), table_name='automation_audit_records')
    op.drop_table('automation_audit_records')
