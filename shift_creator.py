from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from models import Staff, ShiftRequest, Store, Shiftresult
from pulp import LpProblem, LpVariable, LpMinimize, lpSum, LpBinary
import jpholiday

def get_day_type(year: int, month: int, day: int) -> str:
    date = datetime(year, month, day)
    if jpholiday.is_holiday(date) or date.weekday() == 6:
        return 'sunday'
    elif date.weekday() == 5:
        return 'saturday'
    elif date.weekday() == 4:
        return 'friday'
    else:
        return 'weekday'

def generate_shift_results_with_pulp(store_id: int, year: int, month: int, db: Session):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise ValueError("店舗が存在しません")

    staffs = db.query(Staff).filter(Staff.store_id == store_id).all()
    shift_requests = db.query(ShiftRequest).filter(
        ShiftRequest.staff_id.in_([s.id for s in staffs]),
        ShiftRequest.year == year,
        ShiftRequest.month == month
    ).all()

    # 日数・時間範囲定義
    days_in_month = (datetime(year, month % 12 + 1, 1) - timedelta(days=1)).day
    hours = list(range(7, 24))  # 7時〜23時

    # マップ作成
    staff_map = {s.id: s for s in staffs}
    request_map = defaultdict(lambda: defaultdict(set))  # staff_id -> day -> set of hours

    for req in shift_requests:
        request_map[req.staff_id][req.day].add(req.hour)

    # 希望なし or 空の希望 → 休み希望
    rest_day_map = defaultdict(set)
    for s in staffs:
        for d in range(1, days_in_month + 1):
            if d not in request_map[s.id] or len(request_map[s.id][d]) == 0:
                rest_day_map[s.id].add(d)

    # 店舗設定（仮）
    store_config = {
        "weekday": {"open": 9, "close": 22, "open_people": 2, "peak_people": 4, "close_people": 2},
        "friday":  {"open": 9, "close": 23, "open_people": 2, "peak_people": 5, "close_people": 3},
        "saturday": {"open": 8, "close": 23, "open_people": 3, "peak_people": 5, "close_people": 3},
        "sunday": {"open": 9, "close": 21, "open_people": 2, "peak_people": 4, "close_people": 2},
    }

    # 既存結果削除
    staff_ids = [s.id for s in staffs]
    db.query(Shiftresult).filter(
        Shiftresult.staff_id.in_(staff_ids),
        Shiftresult.year == year,
        Shiftresult.month == month
    ).delete(synchronize_session=False)
    db.commit()

    # 最適化モデル
    prob = LpProblem("ShiftScheduling", LpMinimize)
    x = {}
    is_worked = {}

    for s in staffs:
        for d in range(1, days_in_month + 1):
            is_worked[d, s.id] = LpVariable(f"is_worked_{d}_{s.id}", 0, 1, LpBinary)
            for h in hours:
                x[d, h, s.id] = LpVariable(f"x_{d}_{h}_{s.id}", 0, 1, LpBinary)

    # 出勤判定制約
    for s in staffs:
        for d in range(1, days_in_month + 1):
            prob += is_worked[d, s.id] <= lpSum(x[d, h, s.id] for h in hours)
            prob += lpSum(x[d, h, s.id] for h in hours) <= is_worked[d, s.id] * len(hours)

    # 希望休ペナルティ
    rest_penalties = []
    for s in staffs:
        for d in rest_day_map[s.id]:
            penalty_var = LpVariable(f"rest_penalty_{d}_{s.id}", 0, 1, LpBinary)
            prob += lpSum(x[d, h, s.id] for h in hours) <= 1000 * (1 - penalty_var)
            rest_penalties.append(penalty_var)

    # 勤務時間制約（4〜8時間）
    hour_penalties = []
    for s in staffs:
        for d in range(1, days_in_month + 1):
            work_hours = lpSum(x[d, h, s.id] for h in hours)
            under_var = LpVariable(f"under_hours_{d}_{s.id}", 0, 1, LpBinary)
            over_var = LpVariable(f"over_hours_{d}_{s.id}", 0, 1, LpBinary)
            prob += work_hours >= 4 - 1000 * under_var
            prob += work_hours <= 8 + 1000 * over_var
            hour_penalties.extend([under_var, over_var])

    # 社員：6日休み
    for s in staffs:
        if s.employment_type == "社員":
            prob += lpSum(is_worked[d, s.id] for d in range(1, days_in_month + 1)) == (days_in_month - 6)

    # 希望時間と夜勤制限
    for s in staffs:
        for d in range(1, days_in_month + 1):
            for h in hours:
                if s.employment_type != "社員":
                    if h not in request_map[s.id].get(d, []):
                        prob += x[d, h, s.id] == 0
                elif d in rest_day_map[s.id]:
                    prob += x[d, h, s.id] == 0
                if s.employment_type == "未成年バイト" and h >= 22:
                    prob += x[d, h, s.id] == 0

    # スキル人数制約
    for d in range(1, days_in_month + 1):
        day_type = get_day_type(year, month, d)
        conf = store_config[day_type]
        open_hour, close_hour = conf["open"], conf["close"]

        for h in hours:
            if h < open_hour or h >= close_hour:
                continue
            if h < open_hour + 2:
                required = conf["open_people"]
            elif h >= close_hour - 2:
                required = conf["close_people"]
            else:
                required = conf["peak_people"]
            prob += lpSum(x[d, h, s.id] for s in staffs) >= required

    # 目的関数
    prob += 100 * lpSum(rest_penalties) + 50 * lpSum(hour_penalties)

    # 最適化
    prob.solve()

    # 結果保存
    for (d, h, s_id), var in x.items():
        if var.varValue == 1:
            db.add(Shiftresult(
                staff_id=s_id,
                year=year,
                month=month,
                day=d,
                start_time=h,
                end_time=h + 1
            ))

    db.commit()
    return True
