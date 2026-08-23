"""add event_payload to automation_executions for dead-letter retry

Revision ID: 3d6b8f1a90c7
Revises: 7a1f9c3e2b44
Create Date: 2026-08-23 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3d6b8f1a90c7'
down_revision: Union[str, Sequence[str], None] = '7a1f9c3e2b44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable at the DB level for existing rows created before this
    # column existed; the ORM model itself still treats it as required
    # for all new writes going forward.
    op.add_column(
        'automation_executions',
        sa.Column('event_payload', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('automation_executions', 'event_payload')
