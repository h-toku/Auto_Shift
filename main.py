from fastapi import (
    FastAPI, HTTPException, Depends, Request, status,
    Form, Query
)
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from calendar import monthrange
from datetime import datetime, timedelta, date
import dotenv
import jpholiday
from pydantic_models import StaffOut
from models import (
    Store, Staff, ShiftRequest, Shift, Shiftresult,
    StoreDefaultSkillRequirement, ShiftPattern,
    StaffRejectionHistory
)
from database import SessionLocal, engine
from utils import get_common_context
import re
from shift.shift_generator import generate_shift_results_with_ortools
from typing import Optional, Dict
from urllib.parse import urlencode


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


def generate_time_options(open_time, close_time):
    options = []
    for hour in range(open_time, close_time + 1):
        options.append(hour)
    return options


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
        raise HTTPException(
            status_code=401,
            detail="Invalid login or password"
        )

    request.session['user_logged_in'] = True
    request.session['user_name'] = user.name
    request.session['store_name'] = user.store.name
    request.session['employment_type'] = user.employment_type
    request.session['staff_id'] = user.id
    request.session['store_id'] = user.store_id

    return RedirectResponse(
        url="/",
        status_code=status.HTTP_303_SEE_OTHER
    )


@app.get("/", response_class=HTMLResponse)
@app.get("/home", response_class=HTMLResponse)
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
        current_staff = db.query(Staff).filter(
            Staff.name == user_name
        ).first()
        if current_staff:
            staffs = db.query(Staff).filter(
                Staff.store_id == current_staff.store_id
            ).all()

        for person in staffs:
            color = 'black'
            if person.gender == '男':
                color = 'blue'
            elif person.gender == '女':
                color = 'red'
            staff_info.append({
                'name': person.name,
                'color': color
            })

    # シフト情報をスタッフごとに整理
    staff_shifts = {}
    for person in staffs:
        staff_shifts[person.id] = {
            day["day"]: None for day in days_in_month
        }

    # 現在の店舗のスタッフIDリストを取得
    staff_ids = [staff.id for staff in staffs]
    
    # 店舗の営業時間を取得
    store = staffs[0].store if staffs else None
    if store:
        open_hours = store.open_hours
        close_hours = store.close_hours
    
    # シフト情報を取得（store_id、year、monthでフィルタリング）
    shifts = db.query(Shift).filter(
        Shift.staff_id.in_(staff_ids),
        Shift.year == year,
        Shift.month == month
    ).all()

    for shift in shifts:
        start_time = shift.start_time
        end_time = shift.end_time
        
        # 表示形式の決定
        if start_time == open_hours and end_time == close_hours:
            display = "O"
        elif end_time == close_hours:
            display = f"{start_time} ～ L"
        else:
            display = (
                f"{start_time} 〜 {end_time}"
            )
            
        staff_shifts[shift.staff_id][shift.date] = {
            "display": display,
            "start": start_time,
            "end": end_time
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
    keys_to_remove = [
        "user_logged_in",
        "user_name",
        "store_name",
        "employment_type",
        "staff_id"
    ]
    for key in keys_to_remove:
        request.session.pop(key, None)
    return RedirectResponse(
        url="/login",
        status_code=status.HTTP_302_FOUND
    )

@app.get("/salary_estimate")
async def salary_estimate(
    request: Request,
    db: Session = Depends(get_db)
):
    # アクセス制御のためcurrent_staffは必要
    _ = get_current_staff(request, db)

    context = get_common_context(request)
    context.update({"request": request})
    return templates.TemplateResponse("salary_estimate.html", context)

@app.get("/staff/register")
async def get_register_form(
    request: Request,
    db: Session = Depends(get_db)
):
    current_staff = get_current_staff(request, db)
    if current_staff is None or current_staff.employment_type != "社員":
        raise HTTPException(
            status_code=403,
            detail="社員のみアクセスできます。"
        )

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
async def staff_manage(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_staff),
    message: Optional[str] = None
):
    if user is None or user.employment_type != "社員":
        return RedirectResponse(url="/", status_code=303)

    staffs = db.query(Staff).filter(
        Staff.store_id == user.store_id
    ).all()
    staff_outs = [StaffOut.from_orm(staff) for staff in staffs]
    context = get_common_context(request)
    context.update({
        "request": request,
        "staffs": staff_outs,
        "message": message
    })
    return templates.TemplateResponse("staff_manage.html", context)

@app.get("/staff/delete/{staff_id}")
async def delete_staff(staff_id: int, db: Session = Depends(get_db)):
    staff = db.query(Staff).filter(Staff.id == staff_id).first()
    if staff:
        db.delete(staff)
        db.commit()
        params = {
            "message": f"スタッフ {staff.name} を削除しました。"
        }
        redirect_url = f"/staff/manage?{urlencode(params)}"
        return RedirectResponse(url=redirect_url, status_code=303)
    else:
        raise HTTPException(status_code=404, detail="スタッフが見つかりません。")

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

    params = {
        "message": "スタッフ情報が更新されました。"
    }
    redirect_url = f"/staff/manage?{urlencode(params)}"
    return RedirectResponse(url=redirect_url, status_code=303)


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

    # スタッフの店舗IDを取得
    staff = db.query(Staff).filter(Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="スタッフが見つかりません")
    store_id = staff.store_id

    # 店舗のスタッフIDのみを対象に削除（store_id、year、monthでフィルタリング）
    store_staff_ids = [s.id for s in db.query(Staff).filter(Staff.store_id == store_id).all()]
    db.query(ShiftRequest).filter(
        ShiftRequest.staff_id.in_(store_staff_ids),
        ShiftRequest.year == year,
        ShiftRequest.month == month
    ).delete(synchronize_session=False)
    db.flush()

    # 新しいシフト希望を追加
    for day in days:
        new_request = ShiftRequest(
            staff_id=staff_id,
            year=year,
            month=month,
            day=day
        )
        db.add(new_request)

    try:
        db.commit()
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"シフト希望の保存に失敗しました: {str(e)}")

@app.post("/shift_request/update")
async def update_shift_request(
    request: Request,
    db: Session = Depends(get_db)
):
    context = get_common_context(request)
    try:
        form_data = await request.form()
        staff_id = request.session.get("staff_id")

        if not staff_id:
            raise HTTPException(
                status_code=401,
                detail="ログイン情報がありません。"
            )

        staff = db.query(Staff).filter_by(id=staff_id).first()
        if not staff or not staff.store:
            raise HTTPException(
                status_code=404,
                detail="店舗情報が設定されていません。"
            )

        store_id = staff.store_id
        year = int(form_data.get("year"))
        month = int(form_data.get("month"))

        if not year or not month:
            raise HTTPException(
                status_code=400,
                detail="年月が指定されていません。"
            )

        # 店舗のスタッフIDのみを対象に処理
        store_staff_ids = [
            s.id for s in db.query(Staff).filter(
                Staff.store_id == store_id
            ).all()
        ]

        # 既存のシフト希望を削除
        db.query(ShiftRequest).filter(
            ShiftRequest.staff_id.in_(store_staff_ids),
            ShiftRequest.year == year,
            ShiftRequest.month == month
        ).delete(synchronize_session=False)
        db.flush()

        # 新しいシフト希望を追加
        for key, value in form_data.items():
            if key.startswith("status_"):
                iso_date = key.replace("status_", "")
                try:
                    year, month, day = map(int, iso_date.split("-"))
                except ValueError:
                    continue

                status = value if value in ["X", "O", "time"] else None
                start = form_data.get(f"start_{iso_date}")
                end = form_data.get(f"end_{iso_date}")

                start_time = int(start) if start else None
                end_time = int(end) if end else None

                if staff_id in store_staff_ids:
                    shift_request = ShiftRequest(
                        staff_id=staff_id,
                        year=year,
                        month=month,
                        day=day,
                        status=status,
                        start_time=start_time,
                        end_time=end_time
                    )
                    db.add(shift_request)
        
        db.commit()
        context.update({
            "request": request,
            "message": "シフト希望が更新されました。"
        })
        return templates.TemplateResponse("request_done.html", context)

    except HTTPException as e:
        context.update({
            "request": request,
            "message": f"エラーが発生しました: {e.detail}"
        })
        return templates.TemplateResponse("request_done.html", context)
    except Exception as e:
        db.rollback()
        context.update({
            "request": request,
            "message": f"予期せぬエラーが発生しました: {str(e)}"
        })
        return templates.TemplateResponse("request_done.html", context)

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
    month: int = None,
    message: Optional[str] = None
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
            display = r.status  # "〇", "×", etc.

        staff_shifts[r.staff_id][r.day] = {
            "status": r.status,         # 実際のvalue ("〇", "×", "time" など)
            "display": display,
            "start_time": r.start_time,
            "end_time": r.end_time
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
        "staff_shifts": staff_shifts,
        "time_options": generate_time_options(store.open_hours, store.close_hours),
        "message": message
    })

    return templates.TemplateResponse("shift_request_overview.html", context)

@app.post("/shift_request/overview/save", response_class=HTMLResponse)
async def save_or_generate_shift_request(
    request: Request,
    db: Session = Depends(get_db)
):
    context = get_common_context(request)
    try:
        form = await request.form()
        year = int(form.get("year"))
        month = int(form.get("month"))
        store_id = int(form.get("store_id"))
        action = form.get("action")

        if not all([year, month, store_id, action]):
            raise HTTPException(status_code=400, detail="必要なパラメータが不足しています。")

        # 店舗のスタッフIDのみを対象に処理
        store_staff_ids = [s.id for s in db.query(Staff).filter(Staff.store_id == store_id).all()]
        if not store_staff_ids:
            raise HTTPException(status_code=404, detail="店舗のスタッフが見つかりません。")

        if action == "save":
            try:
                # 既存のシフト希望を削除（store_id、year、monthでフィルタリング）
                db.query(ShiftRequest).filter(
                    ShiftRequest.staff_id.in_(store_staff_ids),
                    ShiftRequest.year == year,
                    ShiftRequest.month == month
                ).delete(synchronize_session=False)
                db.flush()

                pattern_status = re.compile(r"shift_status\[(\d+)\]\[(\d+)\]")
                pattern_start = re.compile(r"shift_start\[(\d+)\]\[(\d+)\]")
                pattern_end = re.compile(r"shift_end\[(\d+)\]\[(\d+)\]")

                result_data = {}

                for key, value in form.items():
                    for pattern, field in [
                        (pattern_status, "status"),
                        (pattern_start, "start_time"),
                        (pattern_end, "end_time"),
                    ]:
                        m = pattern.match(key)
                        if m:
                            try:
                                staff_id = int(m.group(1))
                                day = int(m.group(2))
                                if staff_id in store_staff_ids:  # 店舗のスタッフのみ処理
                                    result_data.setdefault(staff_id, {}).setdefault(day, {})[field] = value.strip()
                            except ValueError:
                                continue

                # 新しいシフト希望を保存
                for staff_id, days in result_data.items():
                    for day, data in days.items():
                        status = data.get("status")
                        start_time = int(data.get("start_time")) if data.get("start_time") else None
                        end_time = int(data.get("end_time")) if data.get("end_time") else None

                        if status in ["X", "O", "time"]:
                            shift_request = ShiftRequest(
                                staff_id=staff_id,
                                year=year,
                                month=month,
                                day=day,
                                status=status,
                                start_time=start_time,
                                end_time=end_time
                            )
                            db.add(shift_request)

                db.commit()
                context.update({
                    "request": request,
                    "message": "シフト希望が保存されました。"
                })
                return templates.TemplateResponse("request_done.html", context)

            except Exception as e:
                db.rollback()
                raise HTTPException(status_code=500, detail=f"シフト希望の保存に失敗しました: {str(e)}")

        elif action == "generate":
            try:
                # 既存のシフト結果を削除（store_id、year、monthでフィルタリング）
                db.query(Shiftresult).filter(
                    Shiftresult.year == year,
                    Shiftresult.month == month,
                    Shiftresult.staff_id.in_(store_staff_ids)
                ).delete(synchronize_session=False)
                db.flush()

                # 既存のシフトを削除（store_id、year、monthでフィルタリング）
                db.query(Shift).filter(
                    Shift.year == year,
                    Shift.month == month,
                    Shift.staff_id.in_(store_staff_ids)
                ).delete(synchronize_session=False)
                db.flush()

                # シフト生成を実行
                try:
                    # 必要なデータを取得
                    store = db.query(Store).filter(Store.id == store_id).first()
                    if not store:
                        raise ValueError("店舗情報が見つかりません")

                    # スタッフ情報を取得
                    staffs = db.query(Staff).filter(
                        Staff.store_id == store_id
                    ).all()
                    employees = [s for s in staffs if s.employment_type == "社員"]
                    part_timers = [s for s in staffs if s.employment_type != "社員"]

                    # シフト希望を取得
                    requests = db.query(ShiftRequest).filter(
                        ShiftRequest.year == year,
                        ShiftRequest.month == month,
                        ShiftRequest.staff_id.in_([s.id for s in staffs])
                    ).all()

                    # 祝日を取得
                    holidays = set()
                    for day in range(1, 32):
                        try:
                            current_date = date(year, month, day)
                            if jpholiday.is_holiday(current_date):
                                holidays.add(current_date)
                        except ValueError:
                            continue

                    # シフト生成を実行
                    new_results = generate_shift_results_with_ortools(
                        db=db,
                        store=store,
                        employees=employees,
                        staffs=part_timers,
                        requests=requests,
                        holidays=holidays,
                        year=year,
                        month=month
                    )
                    
                    # シフト結果を保存
                    for result in new_results:
                        # 新しいシフトを作成
                        new_shift = Shift(
                            staff_id=result.staff_id,
                            year=year,
                            month=month,
                            date=result.day,
                            start_time=result.start_time,
                            end_time=result.end_time
                        )
                        db.add(new_shift)
                        db.flush()  # IDを取得するためにflush

                        # シフト結果を更新
                        result.shift_id = new_shift.id
                        db.add(result)

                    db.commit()
                    context.update({
                        "request": request,
                        "message": "シフトが生成されました。"
                    })
                except ValueError as e:
                    db.rollback()
                    context.update({
                        "request": request,
                        "message": f"シフトの生成に失敗しました: {str(e)}"
                    })
                    print(f"エラーが発生しました: {str(e)}")
                return templates.TemplateResponse("generated.html", context)
                

            except Exception as e:
                db.rollback()
                print(f"シフトの生成に失敗しました: {str(e)}")
                raise HTTPException(status_code=500, detail=f"シフトの生成に失敗しました: {str(e)}")

        else:
            raise HTTPException(status_code=400, detail="無効なアクションです。")

    except HTTPException as e:
        context.update({
            "request": request,
            "message": f"エラーが発生しました: {e.detail}"
        })
        print(f"エラーが発生しました: {e.detail}")
        return templates.TemplateResponse("generated.html", context)
    except Exception as e:
        context.update({
            "request": request,
            "message": f"予期せぬエラーが発生しました: {str(e)}"
        })
        print(f"予期せぬエラーが発生しました: {str(e)}")
        return templates.TemplateResponse("generated.html", context)

@app.get("/store_settings/default")
async def default_skill_settings(request: Request, db: Session = Depends(get_db), message: Optional[str] = None):
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
        "message": message,
        "time_options": generate_time_options(store.open_hours, store.close_hours),
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
            leadership=int(form.get(f"{day_type}_leadership", 0)),
            peak_people=int(form.get(f"{day_type}_peak_people", 0)),
            open_people=int(form.get(f"{day_type}_open_people", 0)),
            close_people=int(form.get(f"{day_type}_close_people", 0)),
        )
        db.add(new_setting)

    db.commit()

    params = {
        "message": f"{store.name}のデフォルトスキル設定を保存しました。"
    }
    redirect_url = f"/store_settings/default?{urlencode(params)}"
    return RedirectResponse(url=redirect_url, status_code=303)

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
    params = {
        "message": f"{store.name}のシフトパターンを更新しました。"
    }
    redirect_url = f"/store_settings/default?{urlencode(params)}"
    return RedirectResponse(url=redirect_url, status_code=303)


@app.get("/shift/temp_result")
async def shift_temp_result(
    request: Request,
    db: Session = Depends(get_db),
    year: int = None,
    month: int = None,
    message: Optional[str] = None,
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

    def generate_time_options(open_time, close_time):
        options = []

        for hour in range(open_time, close_time + 1):
                options.append(hour)

        return options

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
        # end_timeが閉店時間なら"L"に置き換え
        staff_shifts[r.staff_id][r.day] = {
            "start_time": r.start_time,
            "end_time": r.end_time
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

    shift_requests = []
    if staff_ids:
        shift_requests = db.query(ShiftRequest).filter(
            ShiftRequest.year == year,
            ShiftRequest.month == month,
            ShiftRequest.staff_id.in_(staff_ids)
        ).all()

    # 辞書に変換（staff_id → day → status）
    staff_requests = {staff.id: {} for staff in staff_list}
    for r in shift_requests:
        if r.status == "time":
            start_str = r.start_time
            end_str = "L" if r.end_time == r.staff.store.close_hours else r.end_time
            display = f"{start_str}〜{end_str}"
        else:
            display = r.status or "-"
        staff_requests[r.staff_id][r.day] = {
            "status": display
        }

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
        "year": year,
        "month": month,
        "staffs": staff_list,
        "staff_shifts": staff_shifts,
        "shift_requests": staff_requests,
        "time_options": generate_time_options(store.open_hours, store.close_hours),
        "message": message
    })

    return templates.TemplateResponse("shift_temp_result.html", context)

@app.post("/shift/temp_result/save", response_class=HTMLResponse)
async def save_shift_temp_result(
    request: Request,
    db: Session = Depends(get_db)
):
    context = get_common_context(request)
    try:
        form = await request.form()
        year = int(form.get("year"))
        month = int(form.get("month"))
        store_id = int(form.get("store_id"))
        action = form.get("action")

        if not all([year, month, store_id, action]):
            raise HTTPException(status_code=400, detail="必要なパラメータが不足しています。")

        # 店舗のスタッフIDのみを対象に処理
        store_staff_ids = [s.id for s in db.query(Staff).filter(Staff.store_id == store_id).all()]
        if not store_staff_ids:
            raise HTTPException(status_code=404, detail="店舗のスタッフが見つかりません。")

        if action == "save":
            try:
                pattern_start = re.compile(r"result_start\[(\d+)\]\[(\d+)\]")
                pattern_end = re.compile(r"result_end\[(\d+)\]\[(\d+)\]")

                # 既存のシフト結果を取得（store_id、year、monthでフィルタリング）
                existing_results = db.query(Shiftresult).filter(
                    Shiftresult.year == year,
                    Shiftresult.month == month,
                    Shiftresult.staff_id.in_(store_staff_ids)
                ).all()

                # 既存のシフトを削除（store_id、year、monthでフィルタリング）
                db.query(Shiftresult).filter(
                    Shiftresult.year == year,
                    Shiftresult.month == month,
                    Shiftresult.staff_id.in_(store_staff_ids)
                ).delete(synchronize_session=False)
                db.flush()

                # 新しいシフトデータを処理
                new_shifts = {}
                for key, value in form.items():
                    for pattern, field in [
                        (pattern_start, "start_time"),
                        (pattern_end, "end_time"),
                    ]:
                        m = pattern.match(key)
                        if m and value.strip():
                            try:
                                staff_id = int(m.group(1))
                                day = int(m.group(2))
                                if staff_id in store_staff_ids:  # 店舗のスタッフのみ処理
                                    time_value = int(value.strip())
                                    if staff_id not in new_shifts:
                                        new_shifts[staff_id] = {}
                                    if day not in new_shifts[staff_id]:
                                        new_shifts[staff_id][day] = {}
                                    new_shifts[staff_id][day][field] = time_value
                            except ValueError:
                                continue

                # データベースの更新
                for staff_id, days in new_shifts.items():
                    if staff_id in store_staff_ids:  # 店舗のスタッフのみ処理
                        for day, data in days.items():
                            start_time = data.get("start_time")
                            end_time = data.get("end_time")
                            
                            if not all([start_time, end_time]) or start_time >= end_time:
                                continue

                            # 新しいシフトを作成
                            new_shift = Shift(
                                staff_id=staff_id,
                                year=year,
                                month=month,
                                date=day,
                                start_time=start_time,
                                end_time=end_time
                            )
                            db.add(new_shift)
                            db.flush()  # IDを取得するためにflush

                            # シフト結果を追加
                            new_result = Shiftresult(
                                staff_id=staff_id,
                                year=year,
                                month=month,
                                day=day,
                                start_time=start_time,
                                end_time=end_time,
                                shift_id=new_shift.id
                            )
                            db.add(new_result)

                db.commit()
                context.update({
                    "request": request,
                    "message": "シフト結果が保存されました。"
                })
                return templates.TemplateResponse("generated.html", context)

            except Exception as e:
                db.rollback()
                raise HTTPException(status_code=500, detail=f"シフト結果の保存に失敗しました: {str(e)}")

        else:
            raise HTTPException(status_code=400, detail="無効なアクションです。")

    except HTTPException as e:
        context.update({
            "request": request,
            "message": f"エラーが発生しました: {e.detail}"
        })
        return templates.TemplateResponse("published.html", context)
    except Exception as e:
        context.update({
            "request": request,
            "message": f"予期せぬエラーが発生しました: {str(e)}"
        })
        return templates.TemplateResponse("published.html", context)


@app.get("/shift/other_store")
async def shift_other_store(
    request: Request,
    db: Session = Depends(get_db),
    year: int = None,
    month: int = None,
    store_id: int = None
):
    current_staff = get_current_staff(request, db)
    if current_staff is None or current_staff.employment_type != "社員":
        raise HTTPException(status_code=403, detail="社員のみアクセスできます。")

    today = date.today()
    if not year or not month:
        year, month = today.year, today.month + 1
        if month == 13:
            year += 1
            month = 1

    # 全店舗一覧（自店舗を除外）
    stores = db.query(Store).all()
    other_stores = [s for s in stores if s.id != current_staff.store_id]

    # 指定がなければ先頭の店舗を選択
    selected_store = None
    if store_id:
        selected_store = db.query(Store).filter(Store.id == store_id).first()
    elif other_stores:
        selected_store = other_stores[0]

    if not selected_store:
        raise HTTPException(status_code=404, detail="表示可能な他店舗が存在しません")

    # 該当店舗のスタッフ取得
    staff_list = db.query(Staff).filter(Staff.store_id == selected_store.id).all()
    staff_map = {s.id: s.name for s in staff_list}
    staff_ids = list(staff_map.keys())

    def generate_time_options(open_time, close_time):
        return [hour for hour in range(open_time, close_time + 1)]

    # 仮シフトの取得
    shift_results = db.query(Shiftresult).filter(
        Shiftresult.year == year,
        Shiftresult.month == month,
        Shiftresult.staff_id.in_(staff_ids)
    ).all()

    staff_shifts = {s.id: {} for s in staff_list}
    for r in shift_results:
        if r.start_time == selected_store.open_hours and r.end_time == selected_store.close_hours:
            display = "O"
        elif r.end_time == selected_store.close_hours:
            display = f"{r.start_time} ～ L"
        else:
            display = f"{r.start_time} ～ {r.end_time}"
        staff_shifts[r.staff_id][r.day] = {
            "status": display
        }

    # 希望シフトの取得
    shift_requests = db.query(ShiftRequest).filter(
        ShiftRequest.year == year,
        ShiftRequest.month == month,
        ShiftRequest.staff_id.in_(staff_ids)
    ).all()

    staff_requests = {s.id: {} for s in staff_list}
    for r in shift_requests:
        if r.status == "time":
            start_str = r.start_time
            end_str = "L" if r.end_time == r.staff.store.close_hours else r.end_time
            display = f"{start_str}〜{end_str}"
        else:
            display = r.status or "-"
        staff_requests[r.staff_id][r.day] = {
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

    # 年月の選択肢
    current_year = today.year
    years = [current_year - 1, current_year, current_year + 1]
    months = list(range(1, 13))

    context = get_common_context(request)
    context.update({
        "request": request,
        "days_in_month": days_in_month,
        "years": years,
        "months": months,
        "year": year,
        "month": month,
        "stores": other_stores,
        "selected_store": selected_store.id,
        "staffs": staff_list,
        "shift_requests": staff_requests,
        "staff_shifts": staff_shifts,
        "time_options": generate_time_options(selected_store.open_hours, selected_store.close_hours)
    })

    return templates.TemplateResponse("other_store_shifts.html", context)

@app.post("/api/shift/edit")
async def edit_shift(
    request: Request,
    db: Session = Depends(get_db)
):
    data = await request.json()
    staff_id = data.get("staff_id")
    year = data.get("year")
    month = data.get("month")
    day = data.get("day")
    start_time = data.get("start_time")
    end_time = data.get("end_time")
    action = data.get("action")  # "add" or "delete"

    # 既存のシフト結果を取得
    shift_result = db.query(Shiftresult).filter(
        Shiftresult.staff_id == staff_id,
        Shiftresult.year == year,
        Shiftresult.month == month,
        Shiftresult.day == day,
        Shiftresult.start_time == start_time,
        Shiftresult.end_time == end_time
    ).first()

    if action == "delete" and shift_result:
        # シフトが削除された場合、不採用履歴を記録
        rejection = StaffRejectionHistory(
            staff_id=staff_id,
            date=datetime(year, month, day).date(),
            total_requests=1,
            rejected_count=1
        )
        db.add(rejection)
        
        # シフト結果を削除
        db.delete(shift_result)
    
    elif action == "add":
        # 新規シフトを追加
        new_shift = Shift(
            staff_id=staff_id,
            year=year,
            month=month,
            date=day,
            start_time=start_time,
            end_time=end_time
        )
        db.add(new_shift)
        db.flush()  # IDを取得するためにflush

        new_result = Shiftresult(
            staff_id=staff_id,
            year=year,
            month=month,
            day=day,
            start_time=start_time,
            end_time=end_time,
            shift_id=new_shift.id
        )
        db.add(new_result)

    db.commit()
    return {"status": "ok"}
