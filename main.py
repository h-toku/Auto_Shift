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
from models import Store, Staff, ShiftRequest, Shift, Shiftresult, Shift, StoreDefaultSkillRequirement, ShiftPattern
from database import SessionLocal, engine
from utils import get_common_context
from datetime import datetime, timedelta, date, time
from schemas import ShiftRequestUpdate
from shift_creator import generate_shift_results

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
    japanese_weekdays = ["月", "火", "水", "木", "金", "土", "日"]

    for d in range(1, last_day + 1):
        current = date(year, month, d)
        weekday = japanese_weekdays[current.weekday()]
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
        "staff_shifts": staff_shifts,
        "staffs": staffs,
    })

    return templates.TemplateResponse("home.html", context)


@app.post("/logout")
async def logout(request: Request):
    for key in ["user_logged_in", "user_name", "store_name", "employment_type", "staff_id"]:
        request.session.pop(key, None)
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

@app.get("/salary_estimate")
async def salary_estimate(request: Request, db: Session = Depends(get_db)):
    current_staff = get_current_staff(request, db)

    context = get_common_context(request)
    context.update({"request": request})
    return templates.TemplateResponse("salary_estimate.html", context)

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

@app.get("/staff/delete/{staff_id}")
async def delete_staff(staff_id: int, db: Session = Depends(get_db)):
    staff = db.query(Staff).filter(Staff.id == staff_id).first()
    if staff:
        db.delete(staff)
        db.commit()
        return RedirectResponse(url="/staff/manage", status_code=303)
    return {"error": "スタッフが見つかりません"}

@app.post("/staff/update_bulk")
async def update_staff_bulk(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    form_data = dict(form)

    # データは "fieldname-{id}" という形式で渡ってくる前提（例：name-3, kitchen_a-3）
    staff_updates: Dict[int, Dict[str, str]] = {}

    for key, value in form_data.items():
        if "-" not in key:
            continue
        field, staff_id_str = key.rsplit("-", 1)
        try:
            staff_id = int(staff_id_str)
        except ValueError:
            continue
        if staff_id not in staff_updates:
            staff_updates[staff_id] = {}
        staff_updates[staff_id][field] = value

    # DB更新
    for staff_id, fields in staff_updates.items():
        staff = db.query(Staff).filter(Staff.id == staff_id).first()
        if not staff:
            continue
        for field, value in fields.items():
            if hasattr(staff, field):
                setattr(staff, field, value)
    db.commit()

    return RedirectResponse(url="/staff/manage", status_code=303)


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
        year, month = today.year, today.month + 1
        if month == 13:
            year += 1
            month = 1

    store = current_staff.store
    if not store:
        raise ValueError("店舗情報が見つかりません")

    # スタッフ一覧
    staff_list = db.query(Staff).filter(Staff.store_id == store_id).all()
    staff_ids = [s.id for s in staff_list]

    # 希望シフトの取得（ShiftRequest）
    shift_requests = db.query(ShiftRequest).filter(
        ShiftRequest.year == year,
        ShiftRequest.month == month,
        ShiftRequest.staff_id.in_(staff_ids)
    ).all()

    # 希望シフトを staff_shifts[staff_id][day] に格納
    staff_shifts = {staff.id: {} for staff in staff_list}
    for r in shift_requests:
        if r.status is None:
            continue
        if r.status == "time":
            start_str = r.start_time
            end_str = "L" if r.end_time == store.close_hours else r.end_time
            display = f"{start_str}〜{end_str}"
        else:
            display = r.status  # "×" など
        staff_shifts[r.staff_id][r.day] = {
            "status": display
        }

    # カレンダー日付生成（縦軸）
    first_day = date(year, month, 1)
    days_in_month = []
    d = first_day
    while d.month == month:
        weekday = d.weekday()
        style_class = ""
        if weekday == 5:
            style_class = "saturday"
        elif weekday == 6 or jpholiday.is_holiday(d):
            style_class = "sunday"
        days_in_month.append({
            "day": d.day,
            "weekday": ["月", "火", "水", "木", "金", "土", "日"][weekday],
            "style_class": style_class
        })
        d += timedelta(days=1)

    # 年・月の選択肢
    current_year = today.year
    years = [current_year - 1, current_year, current_year + 1]
    months = list(range(1, 13))

    context = get_common_context(request)
    context.update({
        "request": request,
        "days_in_month": days_in_month,
        "years": years,
        "months": months,
        "selected_year": year,
        "selected_month": month,
        "staffs": staff_list,
        "staff_shifts": staff_shifts
    })

    return templates.TemplateResponse("shift_request_overview.html", context)


@app.get("/store_settings/default")
async def default_skill_settings(request: Request, db: Session = Depends(get_db)):
    staff = get_current_staff(request, db)
    if not staff or staff.employment_type != "社員":
        return RedirectResponse(url="/login", status_code=303)

    store = staff.store
    if not store:
        return {"error": "店舗が見つかりません"}

    existing_settings = db.query(StoreDefaultSkillRequirement).filter_by(store_id=store.id).all()
    shift_patterns = db.query(ShiftPattern).filter_by(store_id=store.id).all()

    settings = {}
    for s in existing_settings:
        settings[s.day_type] = s  # 1日1レコード

    context = get_common_context(request)
    context.update({
        "request": request,
        "store": store,
        "settings": settings,
        "shift_patterns": shift_patterns,
    })

    return templates.TemplateResponse("store_default_settings.html", context)

@app.post("/store_settings/default/save")
async def save_default_settings(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    staff = get_current_staff(request, db)
    if not staff or staff.employment_type != "社員":
        return RedirectResponse(url="/login", status_code=303)

    store = staff.store
    if not store:
        return {"error": "店舗が見つかりません"}

    db.query(StoreDefaultSkillRequirement).filter_by(store_id=store.id).delete()

    for day_type in ["平日", "金曜日", "土曜日", "日曜日"]:
        new_setting = StoreDefaultSkillRequirement(
            store_id=store.id,
            day_type=day_type,
            peak_start_hour=int(form.get(f"{day_type}_peak_start", 10)),
            peak_end_hour=int(form.get(f"{day_type}_peak_end", 14)),
            kitchen_a=form.get(f"{day_type}_kitchen_a", "C"),
            kitchen_b=form.get(f"{day_type}_kitchen_b", "C"),
            hall=int(form.get(f"{day_type}_hall", 0)),
            people=int(form.get(f"{day_type}_people", 0)),
            leadership=int(form.get(f"{day_type}_leadership", 0)),
        )
        db.add(new_setting)

    db.commit()
    return RedirectResponse("/store_settings/default", status_code=303)

@app.post("/store_settings/shift_patterns/save")
async def save_shift_patterns(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    staff = get_current_staff(request, db)
    if not staff or staff.employment_type != "社員":
        return RedirectResponse(url="/login", status_code=303)

    store = staff.store
    if not store:
        return {"error": "店舗が見つかりません"}

    # 既存パターンの更新・削除
    existing_patterns = db.query(ShiftPattern).filter_by(store_id=store.id).all()
    for pattern in existing_patterns:
        if form.get(f"delete_{pattern.id}"):
            db.delete(pattern)
        else:
            pattern.name = form.get(f"name_{pattern.id}", pattern.name)
            pattern.start_time = int(form.get(f"start_{pattern.id}", pattern.start_time))
            pattern.end_time = int(form.get(f"end_{pattern.id}", pattern.end_time))
            pattern.is_fulltime = f"fulltime_{pattern.id}" in form

    # 新規パターン追加
    if form.get("name_new"):
        new_pattern = ShiftPattern(
            store_id=store.id,
            name=form.get("name_new"),
            start_time=int(form.get("start_new")),
            end_time=int(form.get("end_new")),
            is_fulltime="fulltime_new" in form
        )
        db.add(new_pattern)

    db.commit()
    return RedirectResponse("/store_settings/default", status_code=303)

@app.post("/shift/generate")
async def generate_shift(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    store_id = int(form.get("store_id"))
    year = int(form.get("year"))
    month = int(form.get("month"))

    generate_shift_results(store_id, year, month, db)

    return RedirectResponse(url="/shift/temp_result", status_code=303)

@app.get("/shift/temp_result")
async def shift_temp_result(
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
        year, month = today.year, today.month + 1
        if month == 13:
            year += 1
            month = 1

    store = current_staff.store
    if not store:
        raise ValueError("店舗情報が見つかりません")

    # スタッフ情報の取得
    staff_list = db.query(Staff).filter(Staff.store_id == store_id).all()
    staff_map = {s.id: s.name for s in staff_list}
    staff_ids = list(staff_map.keys())

    # 仮シフト結果の取得
    shift_results = []
    if staff_ids:
        shift_results = db.query(Shiftresult).filter(
            Shiftresult.year == year,
            Shiftresult.month == month,
            Shiftresult.staff_id.in_(staff_ids)
        ).all()

    staff_shifts = {staff.id: {} for staff in staff_list}
    for r in shift_results:
        if r.status is None:
            continue
        if r.status == "time":
            start_str = r.start_time
            end_str = "L" if r.end_time == store.close_hours else r.end_time
            display = f"{start_str}〜{end_str}"
        else:
            display = r.status  # "×" など
        staff_shifts[r.staff_id][r.day] = {
            "status": display
        }

    # カレンダー日付生成
    first_day = date(year, month, 1)
    days_in_month = []
    d = first_day
    while d.month == month:
        weekday = d.weekday()
        style_class = ""
        if weekday == 5:
            style_class = "saturday"
        elif weekday == 6 or jpholiday.is_holiday(d):
            style_class = "sunday"
        days_in_month.append({
            "day": d.day,
            "weekday": ["月", "火", "水", "木", "金", "土", "日"][weekday],
            "style_class": style_class
        })
        d += timedelta(days=1)

    # 年・月の選択肢生成
    current_year = today.year
    years = [current_year - 1, current_year, current_year + 1]
    months = list(range(1, 13))

    context = get_common_context(request)
    context.update({
        "request": request,
        "days_in_month": days_in_month,
        "years": years,
        "months": months,
        "selected_year": year,
        "selected_month": month,
        "staffs": staff_list,
        "staff_shifts": staff_shifts
    })

    return templates.TemplateResponse("shift_temp_result.html", context)

