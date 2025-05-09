from models import Base  # Base を定義しているファイル
from database import engine   # SQLAlchemy の engine を定義しているファイル

# すべてのテーブルを削除
Base.metadata.drop_all(bind=engine)

# テーブルを再作成
Base.metadata.create_all(bind=engine)