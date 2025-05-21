"""Fix broken status 

Revision ID: 55b1023fb996
Revises: 76e1c628fe88
Create Date: 2025-05-21 11:11:42.102562

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '55b1023fb996'
down_revision: Union[str, None] = '76e1c628fe88'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # 1. 一時的に VARCHAR に変更
    op.execute("ALTER TABLE shift_requests MODIFY COLUMN status VARCHAR(10)")

    # 2. データを全角 → 半角へ変換
    op.execute("UPDATE shift_requests SET status = 'O' WHERE status = '○'")
    op.execute("UPDATE shift_requests SET status = 'X' WHERE status = '×'")

    # 3. ENUM に戻す
    op.execute("ALTER TABLE shift_requests MODIFY COLUMN status ENUM('O', 'X', 'time')")

def downgrade():
    op.execute("ALTER TABLE shift_requests MODIFY COLUMN status VARCHAR(10)")
    op.execute("UPDATE shift_requests SET status = '○' WHERE status = 'O'")
    op.execute("UPDATE shift_requests SET status = '×' WHERE status = 'X'")
    op.execute("ALTER TABLE shift_requests MODIFY COLUMN status ENUM('○', '×', 'time')")
