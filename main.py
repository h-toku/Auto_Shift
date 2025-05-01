from fastapi import FastAPI, HTTPException, Depends, Request, status, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from models import Store, Staff
from database import SessionLocal, engine
from sqlalchemy.orm import Session
from schemas import LoginRequest
from passlib.context import CryptContext
import dotenv
import os
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles

dotenv.load_dotenv()

templates = Jinja2Templates(directory="templates")

app = FastAPI()

# 静的ファイルの設定
app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(SessionMiddleware, secret_key="secret-key")

# テーブル作成（開発中のみ）
Store.metadata.create_all(bind=engine)
Staff.metadata.create_all(bind=engine)

# データベースセッション取得
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_staff(request: Request, db: Session):
    user_name = request.session.get("user_name")
    if not user_name:
        return None
    return db.query(Staff).filter(Staff.name == user_name).first()

# ログイン画面を表示（GET）
@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    login_code = form_data.get("login_code")
    password = form_data.get("password")
    
    # ユーザーの認証
    user = db.query(Staff).filter(Staff.login_code == login_code).first()
    
    # ユーザーが見つからないか、パスワードが間違っている場合
    if user is None or password != user.password:
        raise HTTPException(status_code=401, detail="Invalid login or password")
    
    # ログイン成功時にはセッションやJWTトークンを生成して返す（リダイレクト）
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    request.session['user_logged_in'] = True
    request.session['user_name'] = user.name  # ユーザー名をセッションに保存
    request.session['store_name'] = user.store.name  # ストア名をセッションに保存
    return response

# ホーム画面表示
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    # セッションからログイン状態を確認
    user_logged_in = request.session.get('user_logged_in', False)
    user_name = request.session.get('user_name') if user_logged_in else None
    store_name = request.session.get('store_name') if user_logged_in else None
    employment_type = request.session.get('employment_type') if user_logged_in else None
    
    # ログインしていない場合はログインボタンを表示
    if not user_logged_in:
        login_button = {"name": "ログイン画面へ", "url": "/login"}
    else:
        login_button = {"name": "ログアウト", "url": "/logout"}

    return templates.TemplateResponse("home.html", {
        "request": request,
        "user_logged_in": user_logged_in,
        "user_name": user_name,
        "store_name": store_name,
        "employment_type": employment_type,
        "login_button": login_button
    })

@app.post("/logout")
async def logout(request: Request):
    # セッションからユーザー情報を削除
    request.session.pop('user_logged_in', None)
    request.session.pop('user_name', None)
    request.session.pop('store_name', None)
    
    # ログイン画面にリダイレクト
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)


@app.get("/staff/register")
def get_register_form(request: Request, db: Session = Depends(get_db)):
    current_staff = get_current_staff(request, db)
    if current_staff is None or current_staff.employment_type != "社員":
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse("staff_register.html", {
        "request": request,
        "employment_type": current_staff.employment_type
    })


@app.post("/staff/register")
def register_staff(
    request: Request,
    name: str = Form(...),
    desired_days: int = Form(...),
    kitchen_a: int = Form(0),
    kitchen_b: int = Form(0),
    drink: int = Form(0),
    hall: int = Form(0),
    leadership: int = Form(0),
    employment_type: str = Form(...),
    login_code: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    current_staff = get_current_staff(request, db)
    if current_staff is None or current_staff.employment_type != "社員":
        return RedirectResponse(url="/", status_code=303)

    new_staff = Staff(
        name=name,
        desired_days=desired_days,
        kitchen_a=kitchen_a,
        kitchen_b=kitchen_b,
        drink=drink,
        hall=hall,
        leadership=leadership,
        employment_type=employment_type,
        login_code=login_code,
        password=password,
        store_id=current_staff.store_id
    )
    db.add(new_staff)
    db.commit()
    return RedirectResponse(url="/", status_code=303)
