from fastapi import FastAPI
import mysql.connector

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/db-test")
def db_test():
    try:
        # MySQLに接続
        conn = mysql.connector.connect(
            host="db",
            port=3306,
            user="root",
            password="password",
            database="shift_scheduler"
        )
        return {"message": "DB接続成功"}
    except mysql.connector.Error as err:
        return {"message": f"DB接続エラー: {err}"}


        
        