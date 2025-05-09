from fastapi import FastAPI, HTTPException, Depends, Request, status, Form, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from calendar import monthrange
from datetime import date
import dotenv
import jpholiday
from pydantic_models import Staff, ShiftRequest, StaffOut
from models import Store, Staff, ShiftRequest, Shift, Shiftresult, Shift, StoreDefaultSkillRequirement
from database import SessionLocal, engine
from utils import get_common_context
from datetime import datetime, timedelta, date, time
from schemas import ShiftRequestUpdate

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

def get_current_staff(request: Request, db: Session = Depends(get_db)):
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
    request.session['store_id'] = user.store_id

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
        raise HTTPException(status_code=403, detail="社員のみアクセスできます。")

    context = get_common_context(request)
    context.update({"request": request})
    return templates.TemplateResponse("staff_register.html", context)

@app.post("/staff/register")
async def register_staff(
    request: Request,
    name: str = Form(...),
    gender: str = Form(...),
    kitchen_a: str = Form(0),
    kitchen_b: str = Form(0),
    hall: int = Form(0),
    leadership: int = Form(0),
    employment_type: str = Form(...),
    login_code: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    current_staff = get_current_staff(request, db)
    if current_staff is None or current_staff.employment_type != "社員":
        raise HTTPException(status_code=403, detail="社員のみアクセスできます。")

    new_staff = Staff(
        name=name,
        gender=gender,
        kitchen_a=kitchen_a,
        kitchen_b=kitchen_b,
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

@app.get("/staff/manage")
async def staff_manage(request: Request, db: Session = Depends(get_db), user=Depends(get_current_staff)):
    if user is None or user.employment_type != "社員":
        return RedirectResponse(url="/", status_code=303)

    staffs = db.query(Staff).filter(Staff.store_id == user.store_id).all()
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
        raise HTTPException(status_code=403, detail="社員のみアクセスできます。")

    for item in updates:
        staff = db.query(Staff).filter(
            Staff.id == item["id"],
            Staff.store_id == current_staff.store_id
        ).first()
        if not staff:
            continue

        for key in ["name", "gender", "employment_type", "kitchen_a", "kitchen_b", "hall", "leadership"]:
            if key in item:
                setattr(staff, key, item[key])

    db.commit()
    return {"status": "success"}


@app.get("/shift_request")
async def shift_request_form(
    request: Request,
    db: Session = Depends(get_db),
    year: int = None,
    month: int = None
):

    if not request.session.get("user_logged_in"):
        return RedirectResponse(url="/login", status_code=303)

    staff_id = request.session.get("staff_id")

    staff = db.query(Staff).filter_by(id=staff_id).first()
    store = staff.store
    if not store:
        raise ValueError("店舗情報が見つかりません")

    def generate_time_options(open_time, close_time):
        options = []

        for hour in range(open_time, close_time + 1):
                options.append(hour)

        return options

    # デフォルトは翌月
    today = datetime.today()
    if not year or not month:
        if today.month == 12:
            year = today.year + 1
            month = 1
        else:
            year = today.year
            month = today.month + 1

    # カレンダー日付生成
    first_day = date(year, month, 1)
    dates = []
    d = first_day
    while d.month == month:
        dates.append({
            "day": d.day,
            "iso": d.isoformat(),
            "weekday": ["月", "火", "水", "木", "金", "土", "日"][d.weekday()],
            "is_today": d == today.date(),
            "is_saturday": d.weekday() == 5,
            "is_sunday": d.weekday() == 6,
            "editable": True,
            "time_options": generate_time_options(store.open_hours, store.close_hours)
        })
        d += timedelta(days=1)

    # DBから該当月の希望を取得
    shift_requests = db.query(ShiftRequest).filter_by(
        staff_id=staff_id, year=year, month=month
    ).all()

    # shift_data: iso日付文字列 → {status, start, end}
    shift_data = {}
    for d in dates:
        shift_data[d["iso"]] = {"status": "", "start": "", "end": ""}

    for r in shift_requests:
        iso = date(r.year, r.month, r.day).isoformat()
        shift_data[iso] = {
            "status": r.status or "",
            "start": r.start_time or "",
            "end": r.end_time or ""
        }

    # 年・月の選択肢生成
    current_year = today.year
    years = [current_year, current_year + 1]
    months = list(range(1, 13))

    # テンプレートに渡すコンテキスト
    context = get_common_context(request)
    context.update({
        "request": request,
        "current_year": current_year,
        "current_month": today.month,
        "dates": dates,
        "shift_data": shift_data,
        "years": years,
        "months": months,
        "selected_year": year,
        "selected_month": month,
        "editable": True,
    })
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

@app.post("/shift_request/update")
async def update_shift_request(request: Request, db: Session = Depends(get_db)):
    try:
        form_data = await request.form()
        staff_id = request.session.get("staff_id")

        if not staff_id:
            raise ValueError("ログイン情報がありません。")

        staff = db.query(Staff).filter_by(id=staff_id).first()
        if not staff or not staff.store:
            raise ValueError("店舗情報が設定されていません。")

        for key, value in form_data.items():
            if key.startswith("status_"):
                iso_date = key.replace("status_", "")
                year, month, day = map(int, iso_date.split("-"))

                status = value if value in ["×", "○", "time"] else None
                start = form_data.get(f"start_{iso_date}")
                end = form_data.get(f"end_{iso_date}")

                start_time = int(start) if start else None
                end_time = int(end) if end else None

                shift_request = (
                    db.query(ShiftRequest)
                    .filter_by(staff_id=staff_id, year=year, month=month, day=day)
                    .first()
                )
                if not shift_request:
                    shift_request = ShiftRequest(
                        staff_id=staff_id, year=year, month=month, day=day
                    )
                    db.add(shift_request)

                shift_request.status = status
                shift_request.start_time = start_time
                shift_request.end_time = end_time
        
        context = get_common_context(request)
        context.update( {"request": request, "message": "シフト希望が送信されました。"})

        db.commit()
        return templates.TemplateResponse("done.html",context)

    except Exception as e:
        context.update({"message": f"エラーが発生しました: {str(e)}"})
        return templates.TemplateResponse("done.html", context)



@app.get("/shift_request/done")
async def done_page(request: Request):
    context = get_common_context(request)
    context.update({
        "request": request,
        "message": "シフトリクエストを送信してください。"
    })
    return templates.TemplateResponse("done.html", context)

@app.get("/shift_request/overview")
async def shift_request_overview(
    request: Request,
    db: Session = Depends(get_db),
    year: int = None,
    month: int = None
):
    current_staff = get_current_staff(request, db)
    if current_staff is None or current_staff.employment_type != "社員":
        raise HTTPException(status_code=403, detail="社員のみアクセスできます。")

    store_id = current_staff.store_id
    today = date.today()
    if not year or not month:
        year, month = today.year, today.month +1
    
    store = current_staff.store
    if not store:
        raise ValueError("店舗情報が見つかりません")


    # スタッフ情報の取得
    staff_list = db.query(Staff).filter(Staff.store_id == store_id).all()
    staff_ids = [s.id for s in staff_list]
    staff_map = {s.id: s.name for s in staff_list}

    # シフトリクエストを取得
    shift_requests = []
    if staff_ids:
        shift_requests = db.query(ShiftRequest).filter(
            ShiftRequest.year == year,
            ShiftRequest.month == month,
            ShiftRequest.staff_id.in_(staff_ids)
        ).all()

    # カレンダー日付生成
    first_day = date(year, month, 1)
    dates = []
    d = first_day
    while d.month == month:
        requests_for_day = []
        for r in shift_requests:
            if r.day == d.day and r.status is not None:
                status = r.status
                if status == "time":
                    start_str = r.start_time
                    if r.end_time == store.close_hours:
                        end_str = "L"
                    else:
                        end_str = r.end_time
                    status_display = f"{start_str}〜{end_str}"
                else:
                    status_display = status
                requests_for_day.append({
                    "staff_name": staff_map.get(r.staff_id, "不明"),
                    "status": status_display
                })

        dates.append({
            "day": d.day,
            "iso": d.isoformat(),
            "weekday": ["月", "火", "水", "木", "金", "土", "日"][d.weekday()],
            "is_today": d == today,
            "is_saturday": d.weekday() == 5,
            "is_sunday": d.weekday() == 6,
            "editable": True,
            "requests": requests_for_day
        })
        d += timedelta(days=1)

    # 年・月の選択肢生成
    current_year = today.year
    years = [current_year - 1, current_year, current_year + 1]
    months = list(range(1, 13))

    context = get_common_context(request)
    context.update({"request": request, "dates": dates, "years": years, "months": months, "selected_year": year, "selected_month": month})

    return templates.TemplateResponse("shift_request_overview.html", context)

@app.get("/shift_result")
async def shift_result_page(
    request: Request,
    db: Session = Depends(get_db),
    year: int = None,
    month: int = None
):
    current_staff = get_current_staff(request, db)
    if current_staff is None or current_staff.employment_type != "社員":
        raise HTTPException(status_code=403, detail="社員のみアクセスできます。")

    store = current_staff.store
    if not store:
        raise ValueError("店舗情報が見つかりません")

    # シフト取得
    shifts = db.query(Shift).filter_by(store_id=store.id, year=year, month=month).all()
    staffs = db.query(Staff).filter_by(store_id=store.id).all()

    # 表示用に変換
    shift_by_day = {}
    for shift in shifts:
        key = (shift.day, shift.staff_id)
        shift_by_day[key] = {
            "start_time": shift.start_time.strftime("%H:%M") if shift.start_time else "",
            "end_time": shift.end_time.strftime("%H:%M") if shift.end_time else ""
        }

    context = get_common_context(request)
    context.update({
        "year": year,
        "month": month,
        "days": list(range(1, 32)),
        "staffs": staffs,
        "shift_by_day": shift_by_day,
    })

    return templates.TemplateResponse("shift_result.html", context)

@app.post("/shift_result")
async def save_shift_result(
    request: Request,
    db: Session = Depends(get_db),
    year: int = Form(...),
    month: int = Form(...)
):
    form = await request.form()
    current_staff = get_current_staff(request, db)

    store_id = current_staff.store_id
    db.query(Shiftresult).filter_by(store_id=store_id, year=year, month=month).delete()

    for key, value in form.items():
        if "-" not in key:
            continue
        day_str, staff_id_str, field = key.split("-")  # 例: 15-3-start
        day = int(day_str)
        staff_id = int(staff_id_str)

        shift = db.query(Shiftresult).filter_by(
            store_id=store_id, year=year, month=month, day=day, staff_id=staff_id
        ).first()

        if not shift:
            shift = Shiftresult(
                store_id=store_id,
                year=year,
                month=month,
                day=day,
                staff_id=staff_id
            )
            db.add(shift)

        if field == "start":
            shift.start_time = datetime.strptime(value, "%H:%M").time() if value else None
        elif field == "end":
            shift.end_time = datetime.strptime(value, "%H:%M").time() if value else None

    db.commit()
    return RedirectResponse(url=f"/shift_result?year={year}&month={month}", status_code=303)

@app.post("/publish_shift")
async def publish_shift(
    request: Request,
    db: Session = Depends(get_db),
    year: int = Form(...),
    month: int = Form(...)
):
    current_staff = get_current_staff(request, db)

    # すべての ShiftResult を ShiftCalendar にコピー（公開用）
    results = db.query(Shiftresult).filter_by(store_id=current_staff.store_id, year=year, month=month).all()

    for result in results:
        calendar = Shift(
            staff_id=result.staff_id,
            store_id=result.store_id,
            year=result.year,
            month=result.month,
            day=result.day,
            start_time=result.start_time,
            end_time=result.end_time
        )
        db.add(calendar)

    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.get("/store_settings/default")
async def default_skill_settings(request: Request, db: Session = Depends(get_db)):
    staff = get_current_staff(request, db)
    if not staff or staff.employment_type != "社員":
        return RedirectResponse(url="/login", status_code=303)

    store = staff.store
    if not store:
        return {"error": "店舗が見つかりません"}

    # 既存のスキル設定取得
    existing_settings = db.query(StoreDefaultSkillRequirement).filter_by(store_id=store.id).all()

    settings = {
        "平日": {}, "金曜": {}, "土曜": {}, "日曜": {}
    }
    for s in existing_settings:
        for hour in range(s.peak_start_hour, s.peak_end_hour):
            settings[s.day_type][hour] = {
                "kitchen_a": s.kitchen_a,
                "kitchen_b": s.kitchen_b,
                "hall": s.hall,
                "leadership": s.leadership,
            }

    
    context = get_common_context(request)
    context.update({
        "request": request,
        "store": store,
        "settings": settings,
    })

    return templates.TemplateResponse("store_default_settings.html", context)


@app.post("/store_settings/default/save")
async def save_default_settings(
    request: Request,
    db: Session = Depends(get_db),
):
    form = await request.form()
    staff = get_current_staff(request, db)
    if not staff or staff.employment_type != "社員":
        return RedirectResponse(url="/login", status_code=303)

    store = staff.store
    if not store:
        return {"error": "店舗が見つかりません"}

    # 既存設定削除
    db.query(StoreDefaultSkillRequirement).filter_by(store_id=store.id).delete()

    for day_type in ["平日", "金曜", "土曜", "日曜"]:
        for hour in range(24):
            skill_values = {
                f"{day_type}_{hour}_skill{i}": int(form.get(f"{day_type}_{hour}_skill{i}", 0))
                for i in range(1, 6)
            }

            new_setting = StoreDefaultSkillRequirement(
                store_id=store.id,
                day_type=day_type,
                hour=hour,
                **{
                    f"skill{i}_required": skill_values[f"{day_type}_{hour}_skill{i}"]
                    for i in range(1, 6)
                }
            )
            db.add(new_setting)

    db.commit()
    return RedirectResponse("/store_settings/default", status_code=303)
