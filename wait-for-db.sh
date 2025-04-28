#!/bin/bash

# MySQL サーバーが起動しているか確認するまで待機
until mysql -h db -u root -p${MYSQL_ROOT_PASSWORD} -e "SHOW DATABASES;" > /dev/null 2>&1; do
  echo "MySQL is not ready yet. Waiting..."
  sleep 2
done

echo "MySQL is up and running, starting the application..."

# アプリケーションを実行
exec "$@"