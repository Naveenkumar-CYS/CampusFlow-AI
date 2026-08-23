"""create hostel tables

Revision ID: 5f2a7c4e91b3
Revises: 9b3e5d1f7a02
Create Date: 2026-08-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f2a7c4e91b3'
down_revision: Union[str, Sequence[str], None] = '9b3e5d1f7a02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('hostels',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('hostel_code', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hostels_hostel_code'), 'hostels', ['hostel_code'], unique=True)

    op.create_table('rooms',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('hostel_id', sa.UUID(), nullable=False),
    sa.Column('room_number', sa.String(length=20), nullable=False),
    sa.Column('capacity', sa.Integer(), nullable=False),
    sa.Column('current_occupancy', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('current_occupancy >= 0', name='ck_rooms_occupancy_non_negative'),
    sa.CheckConstraint('current_occupancy <= capacity', name='ck_rooms_occupancy_le_capacity'),
    sa.CheckConstraint('capacity > 0', name='ck_rooms_capacity_positive'),
    sa.ForeignKeyConstraint(['hostel_id'], ['hostels.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('hostel_id', 'room_number', name='uq_rooms_hostel_id_room_number')
    )
    op.create_index(op.f('ix_rooms_hostel_id'), 'rooms', ['hostel_id'], unique=False)

    op.create_table('hostel_allocations',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('student_id', sa.UUID(), nullable=False),
    sa.Column('room_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.Enum('ACTIVE', 'VACATED', 'CANCELLED', name='hostel_allocation_status'), nullable=False),
    sa.Column('vacated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hostel_allocations_room_id'), 'hostel_allocations', ['room_id'], unique=False)
    op.create_index(op.f('ix_hostel_allocations_student_id'), 'hostel_allocations', ['student_id'], unique=False)
    # Partial unique index: at most one ACTIVE allocation per student.
    # Not expressible via op.f()/UniqueConstraint (those can't carry a
    # WHERE clause), so created directly.
    op.create_index(
        'uq_hostel_allocations_one_active_per_student',
        'hostel_allocations',
        ['student_id'],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_hostel_allocations_one_active_per_student', table_name='hostel_allocations')
    op.drop_index(op.f('ix_hostel_allocations_student_id'), table_name='hostel_allocations')
    op.drop_index(op.f('ix_hostel_allocations_room_id'), table_name='hostel_allocations')
    op.drop_table('hostel_allocations')

    op.drop_index(op.f('ix_rooms_hostel_id'), table_name='rooms')
    op.drop_table('rooms')

    op.drop_index(op.f('ix_hostels_hostel_code'), table_name='hostels')
    op.drop_table('hostels')
    # ### end Alembic commands ###
    # Postgres ENUM types are not dropped automatically when the table
    # that used them is dropped -- same pattern as fee_status/admission_status.
    sa.Enum(name='hostel_allocation_status').drop(op.get_bind(), checkfirst=True)
