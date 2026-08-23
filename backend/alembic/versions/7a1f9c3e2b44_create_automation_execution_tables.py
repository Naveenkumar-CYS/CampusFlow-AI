"""create automation execution tables

Revision ID: 7a1f9c3e2b44
Revises: 1ee7281ca523
Create Date: 2026-08-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7a1f9c3e2b44'
down_revision: Union[str, Sequence[str], None] = '1ee7281ca523'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'automation_executions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('event_id', sa.String(length=64), nullable=False),
        sa.Column('workflow_id', sa.String(length=120), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_automation_executions_event_id'), 'automation_executions', ['event_id'], unique=True
    )

    op.create_table(
        'automation_action_executions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('execution_id', sa.UUID(), nullable=False),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('attempt', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['execution_id'], ['automation_executions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_automation_action_executions_execution_id'),
        'automation_action_executions', ['execution_id'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_automation_action_executions_execution_id'), table_name='automation_action_executions')
    op.drop_table('automation_action_executions')
    op.drop_index(op.f('ix_automation_executions_event_id'), table_name='automation_executions')
    op.drop_table('automation_executions')
