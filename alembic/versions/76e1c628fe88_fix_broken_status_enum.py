"""Fix broken status enum

Revision ID: 76e1c628fe88
Revises: 62ba8650126e
Create Date: 2025-05-21 11:08:30.944666

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '76e1c628fe88'
down_revision: Union[str, None] = '62ba8650126e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # ENUM → VARCHAR に変換
    op.execute("ALTER TABLE shift_requests MODIFY COLUMN status VARCHAR(10)")

    # 文字化け対応で強制的に O に変換（正しい定義がないためマッチしない可能性が高い）
    op.execute("UPDATE shift_requests SET status = 'O' WHERE status NOT IN ('X', 'time')")

    # 正しい ENUM に再定義
    op.execute("ALTER TABLE shift_requests MODIFY COLUMN status ENUM('O', 'X', 'time')")

def downgrade():
    op.execute("ALTER TABLE shift_requests MODIFY COLUMN status VARCHAR(10)")
    op.execute("UPDATE shift_requests SET status = '○' WHERE status = 'O'")
    op.execute("UPDATE shift_requests SET status = '×' WHERE status = 'X'")
    op.execute("ALTER TABLE shift_requests MODIFY COLUMN status ENUM('○', '×', 'time')")
