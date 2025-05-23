from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from models import Staff, ShiftRequest, Store, Shiftresult, StoreDefaultSkillRequirement
from pulp import LpProblem, LpVariable, LpMaximize, lpSum, LpBinary
import jpholiday
from itertools import groupby


def get_store_config(db: Session, store_id: int):
    store = db.query(Store).filter(Store.id == store_id).first()
    if store is None:
        raise ValueError("指定された店舗が存在しません")

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
            "open": store.open_hours,       # 12時間表記の整数(例:4)
            "close": store.close_hours,     # 12時間表記の整数(例:12)
            "peak_start": conf.peak_start_hour,
            "peak_end": conf.peak_end_hour,
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

    store_config = get_store_config(db, store_id)
    open_hours = store.open_hours
    close_hours = store.close_hours
    hours = list(range(open_hours, close_hours + 1))  # 例: 4～12なら [4,5,...,12]

    staffs = db.query(Staff).filter(Staff.store_id == store_id).all()
    staff_ids = [s.id for s in staffs]
    shift_requests = db.query(ShiftRequest).filter(
        ShiftRequest.staff_id.in_(staff_ids),
        ShiftRequest.year == year,
        ShiftRequest.month == month
    ).all()

    # シフト希望マップ (staff_id -> day -> set(hour))
    request_map = defaultdict(lambda: defaultdict(set))
    for req in shift_requests:
        if not req.status or req.status.strip() == "X":
            continue
        if req.status == "O":
            # 希望全日フルタイム（open～close）
            request_map[req.staff_id][req.day].update(range(open_hours, close_hours))
        elif req.status == "time" and req.start_time is not None and req.end_time is not None:
            # 希望時間帯をセット
            request_map[req.staff_id][req.day].update(range(req.start_time, req.end_time))

    # 既存シフト結果を削除
    db.query(Shiftresult).filter(
        Shiftresult.staff_id.in_(staff_ids),
        Shiftresult.year == year,
        Shiftresult.month == month
    ).delete(synchronize_session=False)
    db.commit()

    prob = LpProblem("ShiftScheduling", LpMaximize)
    next_month = datetime(year + int(month == 12), (month % 12) + 1, 1)
    days_in_month = (next_month - timedelta(days=1)).day

    # 変数作成： x[d,h,s] = 0 or 1
    x = {}
    for s in staffs:
        for d in range(1, days_in_month + 1):
            for h in hours:
                x[d, h, s.id] = LpVariable(f"x_{d}_{h}_{s.id}", 0, 1, LpBinary)

    # 希望以外の時間帯は割り当て禁止
    for s in staffs:
        for d in range(1, days_in_month + 1):
            requested_hours = request_map[s.id].get(d, set())
            for h in hours:
                if h not in requested_hours:
                    prob += x[d, h, s.id] == 0
            # 未成年バイトは22時以降なし（12時間表記で22時以上は想定外。必要あれば条件変更）
            if s.employment_type == "未成年バイト":
                # 12時間表記に合わせてここを調整。例: 10時以降禁止など
                # 例として11時以降禁止にしてみる（要調整）
                for h2 in range(10, close_hours + 1):
                    prob += x[d, h2, s.id] == 0

    # 人数制約（社員以外に適用）
    for d in range(1, days_in_month + 1):
        day_type = get_day_type(year, month, d)
        conf = store_config[day_type]
        for h in hours:
            if h < open_hours or h >= close_hours:
                continue
            if h < conf["peak_start"]:
                limit = conf["open_people"]
            elif conf["peak_start"] <= h < conf["peak_end"]:
                limit = conf["peak_people"]
            else:
                limit = conf["close_people"]

            total_non_employee = lpSum(
                x[d, h, s.id] for s in staffs if s.employment_type != "社員"
            )
            prob += total_non_employee <= limit

    # 目的関数：可能な限り多く割り当てる（総勤務時間最大化）
    prob += lpSum(x[d, h, s.id] for d in range(1, days_in_month + 1) for h in hours for s in staffs)

    prob.solve()

    shift_results = []
    for s in staffs:
        for d in range(1, days_in_month + 1):
            work_hours = [h for h in hours if x[d, h, s.id].varValue == 1]
            # 連続する時間帯に分割して保存
            for _, group in groupby(enumerate(work_hours), lambda x: x[0] - x[1]):
                hour_block = list(map(lambda x: x[1], group))
                if hour_block:
                    start_time = min(hour_block)
                    end_time = max(hour_block) + 1
                    # 4時間未満のシフトは割り当てないルールを入れるならここでチェック可能
                    duration = end_time - start_time
                    if duration < 4:
                        # 4時間未満は除外（シフトなし）
                        continue
                    shift_results.append(Shiftresult(
                        staff_id=s.id,
                        year=year,
                        month=month,
                        day=d,
                        start_time=start_time,
                        end_time=end_time
                    ))

    db.bulk_save_objects(shift_results)
    db.commit()

    return True
