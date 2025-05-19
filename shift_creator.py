from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from models import Staff, ShiftRequest, Store, Shiftresult, StoreDefaultSkillRequirement
from pulp import LpProblem, LpVariable, LpMinimize, lpSum, LpBinary
import jpholiday

def get_store_config(db: Session, store_id: int):
    configs = db.query(StoreDefaultSkillRequirement).filter(
        StoreDefaultSkillRequirement.store_id == store_id
    ).all()

    day_type_map = {
        "平日": "weekday", "金曜日": "friday", "土曜日": "saturday", "日曜日": "sunday"
    }

    store_config = {}
    for conf in configs:
        key = day_type_map.get(conf.day_type, conf.day_type)
        store_config[key] = {
            "open": conf.peak_start_hour,
            "close": conf.peak_end_hour,
            "open_people": conf.open_people,
            "peak_people": conf.peak_people,
            "close_people": conf.close_people
        }
    return store_config

def get_day_type(year: int, month: int, day: int) -> str:
    date = datetime(year, month, day)
    if jpholiday.is_holiday(date) or date.weekday() == 6:
        return 'sunday'
    elif date.weekday() == 5:
        return 'saturday'
    elif date.weekday() == 4:
        return 'friday'
    return 'weekday'

def generate_shift_results_with_pulp(store_id: int, year: int, month: int, db: Session):
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise ValueError("店舗が存在しません")

    staffs = db.query(Staff).filter(Staff.store_id == store_id).all()
    staff_ids = [s.id for s in staffs]

    shift_requests = db.query(ShiftRequest).filter(
        ShiftRequest.staff_id.in_(staff_ids),
        ShiftRequest.year == year,
        ShiftRequest.month == month
    ).all()

    store_config = get_store_config(db, store_id)

    # 対象月の日数
    next_month = datetime(year + int(month == 12), (month % 12) + 1, 1)
    days_in_month = (next_month - timedelta(days=1)).day

    open_hour = min(conf["open"] for conf in store_config.values())
    close_hour = max(conf["close"] for conf in store_config.values())
    hours = list(range(open_hour, close_hour))

    staff_map = {s.id: s for s in staffs}

    # シフト希望マップ作成
    request_map = defaultdict(lambda: defaultdict(set))
    for req in shift_requests:
        if not req.status or req.status.strip() == "×":
            continue
        hours_range = range(store.open_hours, store.close_hours)
        if req.status == "○":
            request_map[req.staff_id][req.day].update(hours_range)
        elif req.status == "time" and req.start_time is not None and req.end_time is not None:
            request_map[req.staff_id][req.day].update(range(req.start_time, req.end_time))

    # 既存の仮シフト削除
    db.query(Shiftresult).filter(
        Shiftresult.staff_id.in_(staff_ids),
        Shiftresult.year == year,
        Shiftresult.month == month
    ).delete(synchronize_session=False)
    db.commit()

    # 最適化モデル作成
    prob = LpProblem("ShiftScheduling", LpMinimize)
    x = {}  # 勤務バイナリ
    is_worked = {}  # 出勤日判定
    hour_penalties = []

    for s in staffs:
        for d in range(1, days_in_month + 1):
            is_worked[d, s.id] = LpVariable(f"is_worked_{d}_{s.id}", 0, 1, LpBinary)
            daily_hours = [LpVariable(f"x_{d}_{h}_{s.id}", 0, 1, LpBinary) for h in hours]
            for h, var in zip(hours, daily_hours):
                x[d, h, s.id] = var

            # 出勤判定との関係
            prob += is_worked[d, s.id] <= lpSum(x[d, h, s.id] for h in hours)
            prob += lpSum(x[d, h, s.id] for h in hours) <= is_worked[d, s.id] * len(hours)

            # 勤務時間制約（4〜8時間）
            work_hours = lpSum(x[d, h, s.id] for h in hours)
            under = LpVariable(f"under_{d}_{s.id}", 0, 1, LpBinary)
            over = LpVariable(f"over_{d}_{s.id}", 0, 1, LpBinary)
            prob += work_hours >= 4 - 1000 * under
            prob += work_hours <= 8 + 1000 * over
            hour_penalties.extend([under, over])

    # 希望時間外勤務・未成年夜勤制限
    for s in staffs:
        for d in range(1, days_in_month + 1):
            for h in hours:
                if s.employment_type != "社員" and h not in request_map[s.id].get(d, []):
                    prob += x[d, h, s.id] == 0
                if s.employment_type == "未成年バイト" and h >= 22:
                    prob += x[d, h, s.id] == 0

    # スキル人数調整
    shortage_penalties, excess_penalties = [], []
    for d in range(1, days_in_month + 1):
        day_type = get_day_type(year, month, d)
        conf = store_config[day_type]

        for h in hours:
            if h < conf["open"] or h >= conf["close"]:
                continue

            required = (
                conf["open_people"] if h < conf["open"] + 2 else
                conf["close_people"] if h >= conf["close"] - 2 else
                conf["peak_people"]
            )

            requested = sum(1 for s in staffs if h in request_map[s.id].get(d, []))
            target = min(required, requested)

            actual = lpSum(x[d, h, s.id] for s in staffs)
            shortage = LpVariable(f"shortage_{d}_{h}", 0)
            excess = LpVariable(f"excess_{d}_{h}", 0)
            prob += actual + shortage - excess == target
            shortage_penalties.append(shortage)
            excess_penalties.append(excess)

    # 目的関数：ペナルティ最小化
    prob += lpSum(hour_penalties + shortage_penalties + excess_penalties)
    prob.solve()

    # 結果保存
    for s in staffs:
        for d in range(1, days_in_month + 1):
            for h in hours:
                if x[d, h, s.id].varValue == 1:
                    db.add(Shiftresult(
                        store_id=store_id, staff_id=s.id, year=year,
                        month=month, day=d, hour=h
                    ))
    db.commit()
    return True
