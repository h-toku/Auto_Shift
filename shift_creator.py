from sqlalchemy.orm import Session
from models import Staff, ShiftRequest, Store, StoreDefaultSkillRequirement, Shiftresult
from datetime import datetime, timedelta
from collections import defaultdict

def generate_shift_results(store_id: int, year: int, month: int, db: Session):
    """
    指定された店舗・年月の希望とスキル情報を元に仮シフト（Shiftresult）を生成
    """

    # 1. 店舗情報を取得
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise ValueError("店舗が存在しません")

    open_hour = store.open_hours
    close_hour = store.close_hours

    # 2. スタッフ一覧とその希望を取得
    staffs = db.query(Staff).filter(Staff.store_id == store_id).all()
    staff_map = {staff.id: staff for staff in staffs}

    # スタッフの希望を日付ごとに整理
    shift_requests = db.query(ShiftRequest).filter(
        ShiftRequest.staff_id.in_(staff_map.keys()),
        ShiftRequest.year == year,
        ShiftRequest.month == month
    ).all()

    shift_request_map = defaultdict(list)
    for req in shift_requests:
        date_key = (req.day, req.staff_id)
        shift_request_map[date_key].append(req)

    # 3. シフト初期化
    db.query(Shiftresult).filter(
        Shiftresult.staff_id.in_(staff_map.keys()),
        Shiftresult.date.between(year * 100 + month * 1, year * 100 + month * 31)
    ).delete()
    db.commit()

    # 4. 各日ごとにシフト作成
    start_date = datetime(year, month, 1)
    while start_date.month == month:
        day = start_date.day
        weekday = start_date.weekday()  # 0=月, ..., 6=日
        day_type = "平日" if weekday < 4 else ("金曜日" if weekday == 4 else ("土曜日" if weekday == 5 else "日曜日"))

        # その日の要件を取得
        requirement = db.query(StoreDefaultSkillRequirement).filter_by(
            store_id=store_id,
            day_type=day_type
        ).first()

        if not requirement:
            start_date += timedelta(days=1)
            continue

        # 希望が出ているスタッフの中から割当（仮に○ or timeのみ）
        for hour in range(open_hour, close_hour):
            assigned_count = 0
            for staff in staffs:
                reqs = shift_request_map.get((day, staff.id), [])
                for req in reqs:
                    if req.status in ("○", "time"):
                        # 希望時間チェック
                        if req.status == "○" or (req.start_time <= hour < req.end_time):
                            # 仮に希望があれば割り当て（後でスキル考慮を実装）
                            shift = Shiftresult(
                                staff_id=staff.id,
                                date=year * 10000 + month * 100 + day,
                                start_time=hour,
                                end_time=hour + 1
                            )
                            db.add(shift)
                            assigned_count += 1
                            break
                if assigned_count >= requirement.peak_people:
                    break  # 必要人数に達したら終了

        start_date += timedelta(days=1)

    db.commit()
    return True
