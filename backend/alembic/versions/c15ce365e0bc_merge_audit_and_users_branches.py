"""merge audit and users branches

Revision ID: c15ce365e0bc
Revises: 0a7f4e56f467, e4f1a9c7d3b6
Create Date: 2026-08-23 15:11:36.138447

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c15ce365e0bc'
down_revision: Union[str, Sequence[str], None] = ('0a7f4e56f467', 'e4f1a9c7d3b6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
