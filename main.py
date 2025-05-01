from fastapi import FastAPI, HTTPException, Depends, Request, status, Form, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from calendar import monthrange
from datetime import date
import dotenv
import os
import jpholiday
from pydantic_models import StaffCreate, Staff, ShiftRequestCreate, ShiftRequest, StaffOut
from models import Store, Staff, ShiftRequest
from database import SessionLocal, engine
from utils import get_common_context
from typing import List
dotenv.load_dotenv()

templates = Jinja2Templates(directory="templates")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(SessionMiddleware, secret_key="secret-key")

Store.metadata.create_all(bind=engine)
Staff.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_staff(request: Request, db: Session):
    user_name = request.session.get("user_name")
    if not user_name:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ログインが必要です"
        )
    staff = db.query(Staff).filter(Staff.name == user_name).first()
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="スタッフが見つかりません"
        )
    return staff

@app.get("/login")
async def login_page(request: Request):
    context = get_common_context(request)
    context["request"] = request
    return templates.TemplateResponse("login.html", context)

@app.post("/login")
async def login(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    login_code = form_data.get("login_code")
    password = form_data.get("password")

    user = db.query(Staff).filter(Staff.login_code == login_code).first()
    if user is None or password != user.password:
        raise HTTPException(status_code=401, detail="Invalid login or password")

    request.session['user_logged_in'] = True
    request.session['user_name'] = user.name
    request.session['store_name'] = user.store.name
    request.session['employment_type'] = user.employment_type
    request.session['staff_id'] = user.id

    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    db: Session = Depends(get_db),
    year: int = Query(default=None),
    month: int = Query(default=None)
):
    today = date.today()
    year = year or today.year
    month = month or today.month
    _, last_day = monthrange(year, month)

    # カレンダーの日付データの作成
    days_in_month = []
    for d in range(1, last_day + 1):
        current = date(year, month, d)
        weekday = current.strftime("%a")
        style_class = ""
        if current == today:
            style_class = "today"
        elif current.weekday() == 5:
            style_class = "saturday"
        elif current.weekday() == 6 or jpholiday.is_holiday(current):
            style_class = "sunday"
        days_in_month.append({
            "day": d,
            "weekday": weekday,
            "style_class": style_class
        })

    # スタッフ情報の取得
    staffs = []
    staff_info = []
    user_name = request.session.get("user_name")
    if request.session.get("user_logged_in"):
        current_staff = db.query(Staff).filter(Staff.name == user_name).first()
        if current_staff:
            staffs = db.query(Staff).filter(Staff.store_id == current_staff.store_id).all()

        for person in staffs:
            color = 'black'
            if person.gender == '男':
                color = 'blue'
            elif person.gender == '女':
                color = 'red'
            staff_info.append({'name': person.name, 'color': color})

    # シフト情報をスタッフごとに整理
    staff_shifts = {}
    for person in staffs:
        staff_shifts[person.id] = {day["day"]: None for day in days_in_month}
    
    shifts = db.query(Shift).filter(Shift.date >= date(year, month, 1), Shift.date <= date(year, month, last_day)).all()
    
    for shift in shifts:
        staff_shifts[shift.staff_id][shift.date.day] = {
            "start": shift.start_time,
            "end": shift.end_time
        }

    # コンテキストにシフト情報を追加
    context = get_common_context(request)
    context.update({
        "request": request,
        "years": list(range(today.year - 1, today.year + 2)),
        "months": list(range(1, 13)),
        "selected_year": year,
        "selected_month": month,
        "days_in_month": days_in_month,
        "staff_info": staff_info,
        "staff_shifts": staff_shifts
    })

    return templates.TemplateResponse("home.html", context)


@app.post("/logout")
async def logout(request: Request):
    for key in ["user_logged_in", "user_name", "store_name", "employment_type", "staff_id"]:
        request.session.pop(key, None)
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

@app.get("/staff/register")
async def get_register_form(request: Request, db: Session = Depends(get_db)):
    current_staff = get_current_staff(request, db)
    if current_staff is None or current_staff.employment_type != "社員":
        return RedirectResponse(url="/", status_code=303)

    context = get_common_context(request)
    context.update({"request": request})
    return templates.TemplateResponse("staff_register.html", context)

@app.post("/staff/register")
async def register_staff(
    request: Request,
    name: str = Form(...),
    gender: str = Form(...),
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
        gender=gender,
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
    existing = db.query(Staff).filter(Staff.login_code == login_code).first()

    if existing:
        raise HTTPException(status_code=400, detail="このログインコードは既に使われています。")

    db.add(new_staff)
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.get("/staff/manage", response_model=List[StaffOut])  # StaffOutはPydanticモデル
async def staff_manage(request: Request, db: Session = Depends(get_db), user=Depends(get_current_staff)):
    if user is None or user.employment_type != "社員":
        return RedirectResponse(url="/", status_code=303)

    staffs = db.query(Staff).filter(Staff.store_id == user.store_id).all()
    # SQLAlchemyモデルのStaffをPydanticモデルStaffOutに変換
    staff_outs = [StaffOut.from_orm(staff) for staff in staffs]
    context = get_common_context(request)
    context.update({"request": request, "staffs": staff_outs})
    return templates.TemplateResponse("staff_manage.html", context)

@app.post("/staff/update_bulk")
async def update_bulk_staff(
    updates: list[dict],
    request: Request,
    db: Session = Depends(get_db)
):
    current_staff = get_current_staff(request, db)
    if current_staff is None or current_staff.employment_type != "社員":
        return RedirectResponse(url="/", status_code=303)

    for item in updates:
        staff = db.query(Staff).filter(
            Staff.id == item["id"],
            Staff.store_id == current_staff.store_id
        ).first()
        if not staff:
            continue

        for key in ["name", "gender", "employment_type", "desired_days", "kitchen_a", "kitchen_b", "drink", "hall", "leadership"]:
            if key in item:
                setattr(staff, key, item[key])

    db.commit()
    return {"status": "success"}


@app.get("/shift_request")
async def shift_request_form(request: Request, db: Session = Depends(get_db)):
    if not request.session.get("user_logged_in"):
        return RedirectResponse(url="/login", status_code=303)

    context = get_common_context(request)
    context["request"] = request
    return templates.TemplateResponse("shift_request.html", context)

@app.post("/shift_request")
async def submit_shift_request(
    request: Request,
    year: int = Form(...),
    month: int = Form(...),
    days: list[int] = Form(...),
    db: Session = Depends(get_db)
):
    staff_id = request.session.get("staff_id")
    if not staff_id:
        return RedirectResponse(url="/login", status_code=303)

    db.query(ShiftRequest).filter_by(staff_id=staff_id, year=year, month=month).delete()

    for day in days:
        new_request = ShiftRequest(staff_id=staff_id, year=year, month=month, day=day)
        db.add(new_request)

    db.commit()
    return RedirectResponse(url="/", status_code=303)
