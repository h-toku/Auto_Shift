FROM python:3.9-slim

# 作業ディレクトリの設定
WORKDIR /app

# 必要なパッケージをインストール
RUN apt-get update && apt-get install -y \
    python3-dev \
    build-essential \
    default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

# 必要なPythonパッケージのインストール
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコンテナにコピー
COPY . /app/

# スクリプトをコンテナ内にコピー
COPY wait-for-db.sh /wait-for-db.sh

# スクリプトに実行権限を付与
RUN chmod +x /wait-for-db.sh

# ENTRYPOINT により、MySQL が準備できるまで待機し、その後アプリケーションを起動
ENTRYPOINT ["/wait-for-db.sh", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "6060"]
