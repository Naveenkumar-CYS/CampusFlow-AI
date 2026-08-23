"""create fees table

Revision ID: 9b3e5d1f7a02
Revises: 3d6b8f1a90c7
Create Date: 2026-08-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b3e5d1f7a02'
down_revision: Union[str, Sequence[str], None] = '3d6b8f1a90c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # No explicit enum .create() call here -- op.create_table() creates
    # the type itself when it encounters sa.Enum(...) on a column,
    # exactly like the working admissions migration does for
    # admission_status. A separate explicit create() call before this
    # (an earlier draft of this migration had one) collides with that
    # automatic creation -- DuplicateObject. Don't add one back.
    op.create_table('fees',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('fee_id', sa.String(length=32), nullable=False),
    sa.Column('student_id', sa.UUID(), nullable=False),
    sa.Column('fee_type', sa.String(length=50), nullable=False),
    sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'PAID', 'OVERDUE', 'CANCELLED', name='fee_status'), nullable=False),
    sa.Column('payment_reference', sa.String(length=120), nullable=True),
    sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fees_fee_id'), 'fees', ['fee_id'], unique=True)
    op.create_index(op.f('ix_fees_student_id'), 'fees', ['student_id'], unique=False)
    op.create_index(op.f('ix_fees_payment_reference'), 'fees', ['payment_reference'], unique=True)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_fees_payment_reference'), table_name='fees')
    op.drop_index(op.f('ix_fees_student_id'), table_name='fees')
    op.drop_index(op.f('ix_fees_fee_id'), table_name='fees')
    op.drop_table('fees')
    # ### end Alembic commands ###
    # Postgres ENUM types are not dropped automatically when the table
    # that used them is dropped -- without this, a downgrade followed by
    # a re-upgrade fails with "type fee_status already exists" (same
    # pattern as the admissions migration's admission_status handling).
    sa.Enum(name='fee_status').drop(op.get_bind(), checkfirst=True)
