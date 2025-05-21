"""Change shift request status from ○ to O

Revision ID: 62ba8650126e
Revises: 41fba14dba76
Create Date: 2025-05-21 10:59:42.393534

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '62ba8650126e'
down_revision: Union[str, None] = '41fba14dba76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute(
        "UPDATE shift_requests SET status = 'O' WHERE status = '○'"
    )


def downgrade():
    op.execute(
        "UPDATE shift_requests SET status = '○' WHERE status = 'O'"
    )
