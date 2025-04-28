import pymysql
from dotenv import load_dotenv
import os

# .envファイルを読み込む
load_dotenv()

# MySQLdb互換のためにpymysqlをインストール
pymysql.install_as_MySQLdb()

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# .envからDATABASE_URLを取得
DATABASE_URL = os.getenv("DATABASE_URL")

# SQLAlchemyの設定
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
