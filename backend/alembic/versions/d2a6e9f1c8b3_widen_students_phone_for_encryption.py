"""widen students.phone column for at-rest encryption

Person E, Step 2: Student.phone now goes through
app.core.encryption.EncryptedString, which stores Fernet ciphertext
instead of the plaintext phone number. Ciphertext is meaningfully
longer than any plaintext phone number, so the column needs to grow
from VARCHAR(20) to comfortably fit it. No data migration is performed
here -- any existing plaintext rows must be re-saved through the
application (which will then encrypt them on write) after this
deploys; this migration only widens the column.

Revision ID: d2a6e9f1c8b3
Revises: c15ce365e0bc
Create Date: 2026-08-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2a6e9f1c8b3'
down_revision: Union[str, Sequence[str], None] = 'c15ce365e0bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'students',
        'phone',
        existing_type=sa.String(length=20),
        type_=sa.String(length=255),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema.

    NOTE: downgrading after real (encrypted) phone values have been
    written back will truncate/corrupt them -- ciphertext will not fit
    back into VARCHAR(20). Only safe to run before any encrypted data
    exists.
    """
    op.alter_column(
        'students',
        'phone',
        existing_type=sa.String(length=255),
        type_=sa.String(length=20),
        existing_nullable=True,
    )
