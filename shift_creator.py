from sqlalchemy.orm import Session
from models import (
    Staff, Store, ShiftRequest, ShiftPattern,
    Shiftresult, StoreDefaultSkillRequirement
)
from collections import defaultdict
from datetime import datetime, timedelta
import calendar
from ortools.sat.python import cp_model
from typing import Optional
import jpholiday


def get_day_type(year: int, month: int, day: int, holidays: set[datetime.date]) -> str:
    date = datetime(year, month, day).date()
    weekday = date.weekday()
    next_day = date + timedelta(days=1)
    prev_day = date - timedelta(days=1)

    if date in holidays:
        if prev_day.weekday() in [0, 1, 2, 3] or prev_day.weekday() == 4:  # 平日 or 金曜
            return "土曜日"
        elif date.weekday() == 6 and next_day in holidays:
            return "土曜日"
        elif next_day.weekday() in [0, 1, 2, 3, 4]:
            return "日曜日"
        else:
            return "土曜日"
    elif weekday == 4:
        return "金曜日"
    elif weekday == 5:
        return "土曜日"
    elif weekday == 6:
        return "日曜日"
    else:
        return "平日"


def get_holidays(year, month) -> set[datetime.date]:
    holidays = set()
    _, last_day = calendar.monthrange(year, month)
    for day in range(1, last_day + 1):
        date = datetime(year, month, day).date()
        if jpholiday.is_holiday(date):
            holidays.add(date)
    return holidays


def classify_time_blocks(store: Store, day_type: str):
    default_setting = next((s for s in store.default_skill_requirements if s.day_type == day_type), None)
    if not default_setting:
        raise ValueError(f"{day_type} のスキル設定がありません")

    blocks = []
    for hour in range(store.open_hours, store.close_hours):
        if hour < default_setting.peak_start_hour:
            max_people = default_setting.open_people
        elif default_setting.peak_start_hour <= hour < default_setting.peak_end_hour:
            max_people = default_setting.peak_people
        else:
            max_people = default_setting.close_people
        blocks.append((hour, max_people))
    return blocks, default_setting


def rank_value(rank: str) -> int:
    return {"A": 3, "B": 2, "C": 1}.get(rank, 0)


def choose_best_pattern(
    staff: Staff,
    shift_request: ShiftRequest,
    patterns: list[ShiftPattern],
    requirement: StoreDefaultSkillRequirement,
    assigned_counts: dict[int, int],  # hour → 現在の人数
    open_hour: int,
    close_hour: int,
) -> Optional[ShiftPattern]:
    if shift_request.status == "O" or (shift_request.status and staff.employment_type == "社員"):
        avail_start = open_hour
        avail_end = close_hour
    elif shift_request.status == "time":
        avail_start = shift_request.start_time
        avail_end = shift_request.end_time
    else:
        return None  # 勤務不可

    candidate_patterns = [
        p for p in patterns
        if p.start_time >= avail_start and p.end_time <= avail_end
    ]

    if not candidate_patterns:
        return None

    def pattern_score(p: ShiftPattern) -> int:
        score = 0
        for h in range(p.start_time, p.end_time):
            if h < requirement.peak_start_hour:
                needed = requirement.open_people
            elif h < requirement.peak_end_hour:
                needed = requirement.peak_people
            else:
                needed = requirement.close_people

            current = assigned_counts.get(h, 0)
            if current < needed:
                score += needed - current
        return score

    best_pattern = max(candidate_patterns, key=pattern_score, default=None)
    return best_pattern


def generate_shift_results_with_ortools(db: Session, store_id: int, year: int, month: int) -> str:
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise ValueError("店舗が見つかりません")

    all_staffs = db.query(Staff).filter(Staff.store_id == store_id).all()
    staffs = [s for s in all_staffs if s.employment_type != "社員"]  # 社員以外
    employees = [s for s in all_staffs if s.employment_type == "社員"]  # 社員

    shift_requests = db.query(ShiftRequest).filter(
        ShiftRequest.year == year,
        ShiftRequest.month == month,
        ShiftRequest.staff_id.in_([s.id for s in all_staffs])
    ).all()

    requests = {(r.staff_id, r.day): r for r in shift_requests}
    patterns = db.query(ShiftPattern).all()
    _, last_day = calendar.monthrange(year, month)

    # --- 1. 社員のシフトをShiftresultに登録 ---
    db.query(Shiftresult).filter(
        Shiftresult.year == year,
        Shiftresult.month == month,
        Shiftresult.staff_id.in_([s.id for s in all_staffs])
    ).delete(synchronize_session=False)

    new_results = []

    for s in employees:
        for day in range(1, last_day + 1):
            req = requests.get((s.id, day))
            if req is None or req.status in ("X", ""):
                continue  # 休み
            start = store.open_hours
            end = store.close_hours
            if req.status == "time":
                start = req.start_time
                end = req.end_time
            for hour in range(start, end):
                new_results.append(Shiftresult(
                    staff_id=s.id,
                    year=year,
                    month=month,
                    day=day,
                    start_time=hour,
                    end_time=hour + 1
                ))

    # --- 2. OR-Toolsモデル ---
    model = cp_model.CpModel()

    # 変数定義
    x = {}  # (staff_id, day, pattern_id) → BoolVar
    for s in staffs:
        for day in range(1, last_day + 1):
            for p in patterns:
                x[(s.id, day, p.id)] = model.NewBoolVar(f"x_s{s.id}_d{day}_p{p.id}")

    y = {}  # (staff_id, day, hour) → BoolVar：勤務しているか
    for s in staffs:
        for day in range(1, last_day + 1):
            for hour in range(store.open_hours, store.close_hours):
                y[(s.id, day, hour)] = model.NewBoolVar(f"y_s{s.id}_d{day}_h{hour}")

    # 連勤制約（簡略化）
    max_consecutive_days = 4
    for s in staffs:
        for start_day in range(1, last_day - max_consecutive_days + 2):
            # 連勤判定用補助変数を作る（日単位で勤務しているか）
            day_vars = []
            for day in range(start_day, start_day + max_consecutive_days):
                # 1日の勤務有無変数を追加（xの集合で判定）
                work_var = model.NewBoolVar(f"work_s{s.id}_d{day}")
                model.AddMaxEquality(work_var, [x[(s.id, day, p.id)] for p in patterns])
                day_vars.append(work_var)
            model.Add(sum(day_vars) <= max_consecutive_days - 1)  # 4連勤禁止

    # y[s,d,h] = OR(x[s,d,p] for p covering hour h)
    for s in staffs:
        for day in range(1, last_day + 1):
            for hour in range(store.open_hours, store.close_hours):
                covering_patterns = [p for p in patterns if p.start_time <= hour < p.end_time]
                if covering_patterns:
                    model.AddMaxEquality(
                        y[(s.id, day, hour)],
                        [x[(s.id, day, p.id)] for p in covering_patterns]
                    )
                else:
                    model.Add(y[(s.id, day, hour)] == 0)

    # --- 希望勤務時間帯制約 ---
    for s in staffs:
        for day in range(1, last_day + 1):
            req = requests.get((s.id, day))
            for p in patterns:
                if req is None:
                    # 希望なしは休み（x=0）
                    model.Add(x[(s.id, day, p.id)] == 0)
                    continue
                # statusによって勤務可否判定
                can_work = False
                if req.status == "O" or (req.status and s.employment_type == "社員"):
                    # フルタイム勤務可
                    if p.start_time >= store.open_hours and p.end_time <= store.close_hours:
                        can_work = True
                elif req.status == "time":
                    if p.start_time >= req.start_time and p.end_time <= req.end_time:
                        can_work = True
                # 休みは勤務不可
                if req.status in ("X", ""):
                    can_work = False
                if not can_work:
                    model.Add(x[(s.id, day, p.id)] == 0)

    # --- 1日1パターンのみ ---
    for s in staffs:
        for day in range(1, last_day + 1):
            model.Add(sum(x[(s.id, day, p.id)] for p in patterns) <= 1)

    # --- 各時間帯の人数制約 ---
    holidays = get_holidays(year, month)
    for day in range(1, last_day + 1):
        date = datetime(year, month, day).date()
        day_type = get_day_type(year, month, day, holidays)
        skill_req = next((r for r in store.default_skill_requirements if r.day_type == day_type), None)
        if not skill_req:
            raise ValueError(f"{day_type} のスキル設定がありません")
        for hour in range(store.open_hours, store.close_hours):
            if hour < skill_req.peak_start_hour:
                max_staff = skill_req.open_people
            elif hour < skill_req.peak_end_hour:
                max_staff = skill_req.peak_people
            else:
                max_staff = skill_req.close_people

            model.Add(
                sum(y[(s.id, day, hour)] for s in staffs) <= max_staff
            )

    # --- 目的関数（スキルポイント最大化） ---
    # スタッフのスキル5項目合計値 × 勤務時間を最大化
    objective_terms = []
    for s in staffs:
        skill_sum = s.skill1 + s.skill2 + s.skill3 + s.skill4 + s.skill5
        for day in range(1, last_day + 1):
            for hour in range(store.open_hours, store.close_hours):
                objective_terms.append(skill_sum * y[(s.id, day, hour)])

    model.Maximize(sum(objective_terms))

    # --- ソルバー実行 ---
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    status = solver.Solve(model)

    if status != cp_model.OPTIMAL and status != cp_model.FEASIBLE:
        return "最適解が見つかりませんでした"

    # --- Shiftresult に結果登録 ---
    for s in staffs:
        for day in range(1, last_day + 1):
            for hour in range(store.open_hours, store.close_hours):
                if solver.BooleanValue(y[(s.id, day, hour)]):
                    new_results.append(Shiftresult(
                        staff_id=s.id,
                        year=year,
                        month=month,
                        day=day,
                        start_time=hour,
                        end_time=hour + 1
                    ))

    db.bulk_save_objects(new_results)
    db.commit()

    return "シフト自動作成完了"
