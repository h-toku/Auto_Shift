from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from models import Staff, ShiftRequest, Store, Shiftresult, StoreDefaultSkillRequirement
from pulp import LpProblem, LpVariable, LpMinimize, lpSum, LpBinary
import jpholiday
from itertools import groupby


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


def add_work_constraints(prob, x, is_worked, d, s_id, hours):
    prob += is_worked[d, s_id] <= lpSum(x[d, h, s_id] for h in hours)
    prob += lpSum(x[d, h, s_id] for h in hours) <= is_worked[d, s_id] * len(hours)


def add_hour_penalty_constraints(prob, x, d, s_id, hours):
    work_hours = lpSum(x[d, h, s_id] for h in hours)
    under = LpVariable(f"under_{d}_{s_id}", 0, 1, LpBinary)
    over = LpVariable(f"over_{d}_{s_id}", 0, 1, LpBinary)
    prob += work_hours >= 4 - 1000 * under
    prob += work_hours <= 8 + 1000 * over
    return under, over


def add_skill_balance_constraint(prob, x, d, h, staffs, target):
    actual = lpSum(x[d, h, s.id] for s in staffs)
    shortage = LpVariable(f"shortage_{d}_{h}", 0)
    excess = LpVariable(f"excess_{d}_{h}", 0)
    prob += actual - excess == target
    return shortage, excess


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

    next_month = datetime(year + int(month == 12), (month % 12) + 1, 1)
    days_in_month = (next_month - timedelta(days=1)).day

    open_hour = min(conf["open"] for conf in store_config.values())
    close_hour = max(conf["close"] for conf in store_config.values())
    hours = list(range(open_hour, close_hour))

    request_map = defaultdict(lambda: defaultdict(set))
    for req in shift_requests:
        if not req.status or req.status.strip() == "X":
            continue
        hours_range = range(store.open_hours, store.close_hours)
        if req.status == "O":
            request_map[req.staff_id][req.day].update(hours_range)
        elif req.status == "time" and req.start_time is not None and req.end_time is not None:
            request_map[req.staff_id][req.day].update(range(req.start_time, req.end_time))

    db.query(Shiftresult).filter(
        Shiftresult.staff_id.in_(staff_ids),
        Shiftresult.year == year,
        Shiftresult.month == month
    ).delete(synchronize_session=False)
    db.commit()

    prob = LpProblem("ShiftScheduling", LpMinimize)
    x = {}
    is_worked = {}
    underwork_penalties = []
    overwork_penalties = []
    shortage_penalties = []
    excess_penalties = []

    for s in staffs:
        for d in range(1, days_in_month + 1):
            is_worked[d, s.id] = LpVariable(f"is_worked_{d}_{s.id}", 0, 1, LpBinary)
            for h in hours:
                x[d, h, s.id] = LpVariable(f"x_{d}_{h}_{s.id}", 0, 1, LpBinary)

            add_work_constraints(prob, x, is_worked, d, s.id, hours)
            under, over = add_hour_penalty_constraints(prob, x, d, s.id, hours)
            underwork_penalties.append(under)
            overwork_penalties.append(over)

    for s in staffs:
    if s.employment_type == "社員":
        for d in range(1, days_in_month + 1):
            for h in hours:
                prob += x[d, h, s.id] == 1 

    # 希望時間外勤務 & 未成年制限
    for s in staffs:
        for d in range(1, days_in_month + 1):
            for h in hours:
                if s.employment_type != "社員" and h not in request_map[s.id].get(d, []):
                    prob += x[d, h, s.id] == 0
                if s.employment_type == "未成年バイト" and h >= 22:
                    prob += x[d, h, s.id] == 0

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

            target = required

            shortage, excess = add_skill_balance_constraint(prob, x, d, h, staffs, target)
            excess_penalties.append(excess)

    # 目的関数：ペナルティ最小化（重みを調整可能）
    prob += (
        10 * lpSum(underwork_penalties) +
        10 * lpSum(overwork_penalties) +
        1 * lpSum(excess_penalties)
    )

    prob.solve()

    # 結果保存（高速化）
    shift_results = []
    for s in staffs:
        for d in range(1, days_in_month + 1):
            # 勤務時間のリストを抽出
            work_hours = [h for h in hours if x[d, h, s.id].varValue == 1]

            # 連続した時間帯にまとめる
            for _, group in groupby(enumerate(work_hours), lambda x: x[0] - x[1]):
                hour_block = list(map(lambda x: x[1], group))
                if hour_block:
                    shift_results.append(Shiftresult(
                        staff_id=s.id,
                        year=year,
                        month=month,
                        day=d,
                        start_time=min(hour_block),
                        end_time=max(hour_block) + 1  # 終了時間は非包含なので +1
                    ))

    db.bulk_save_objects(shift_results)
    db.commit()
    return True
