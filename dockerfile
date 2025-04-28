FROM python:3.9-slim

# 作業ディレクトリの設定
WORKDIR /app

# 必要なパッケージをインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-dev \
    build-essential \
    default-mysql-client \
    locales && \
    sed -i 's/# ja_JP.UTF-8 UTF-8/ja_JP.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen && \
    rm -rf /var/lib/apt/lists/*

# 環境変数を設定して、日本語ロケールを使う
ENV LANG=ja_JP.UTF-8
ENV LANGUAGE=ja_JP:ja
ENV LC_ALL=ja_JP.UTF-8

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
