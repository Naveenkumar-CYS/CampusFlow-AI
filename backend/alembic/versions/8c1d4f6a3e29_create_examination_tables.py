"""create examination tables

Revision ID: 8c1d4f6a3e29
Revises: 5f2a7c4e91b3
Create Date: 2026-08-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c1d4f6a3e29'
down_revision: Union[str, Sequence[str], None] = '5f2a7c4e91b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('exams',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('exam_code', sa.String(length=32), nullable=False),
    sa.Column('subject', sa.String(length=120), nullable=False),
    sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.Enum('SCHEDULED', 'COMPLETED', 'CANCELLED', name='exam_status'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_exams_exam_code'), 'exams', ['exam_code'], unique=True)

    op.create_table('exam_registrations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('student_id', sa.UUID(), nullable=False),
    sa.Column('exam_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['exam_id'], ['exams.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('student_id', 'exam_id', name='uq_exam_registrations_student_id_exam_id')
    )
    op.create_index(op.f('ix_exam_registrations_exam_id'), 'exam_registrations', ['exam_id'], unique=False)
    op.create_index(op.f('ix_exam_registrations_student_id'), 'exam_registrations', ['student_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_exam_registrations_student_id'), table_name='exam_registrations')
    op.drop_index(op.f('ix_exam_registrations_exam_id'), table_name='exam_registrations')
    op.drop_table('exam_registrations')

    op.drop_index(op.f('ix_exams_exam_code'), table_name='exams')
    op.drop_table('exams')
    # ### end Alembic commands ###
    # Postgres ENUM types are not dropped automatically when the table
    # that used them is dropped -- same pattern as fee_status/admission_status/
    # hostel_allocation_status.
    sa.Enum(name='exam_status').drop(op.get_bind(), checkfirst=True)
