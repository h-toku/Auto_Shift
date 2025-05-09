"""ok

Revision ID: 03aa3821b07e
Revises: 9a7c90e73b7d
Create Date: 2025-05-09 10:59:12.034750

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '03aa3821b07e'
down_revision: Union[str, None] = '9a7c90e73b7d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
