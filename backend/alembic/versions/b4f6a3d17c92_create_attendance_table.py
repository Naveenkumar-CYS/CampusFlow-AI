"""create attendance table

Revision ID: b4f6a3d17c92
Revises: 8c1d4f6a3e29
Create Date: 2026-08-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4f6a3d17c92'
down_revision: Union[str, Sequence[str], None] = '8c1d4f6a3e29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('attendance_records',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('student_id', sa.UUID(), nullable=False),
    sa.Column('subject', sa.String(length=120), nullable=False),
    sa.Column('session_date', sa.Date(), nullable=False),
    sa.Column('status', sa.Enum('PRESENT', 'ABSENT', 'LATE', 'EXCUSED', name='attendance_status'), nullable=False),
    sa.Column('marked_by', sa.String(length=120), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint(
        'student_id', 'subject', 'session_date',
        name='uq_attendance_records_student_subject_session_date',
    )
    )
    op.create_index(
        op.f('ix_attendance_records_student_id'), 'attendance_records', ['student_id'], unique=False
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_attendance_records_student_id'), table_name='attendance_records')
    op.drop_table('attendance_records')
    # ### end Alembic commands ###
    # Postgres ENUM types are not dropped automatically when the table
    # that used them is dropped -- same pattern as fee_status/
    # hostel_allocation_status/exam_status.
    sa.Enum(name='attendance_status').drop(op.get_bind(), checkfirst=True)
