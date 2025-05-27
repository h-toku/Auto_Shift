from sqlalchemy.orm import Session
from models import (
    Staff, Store, ShiftRequest, ShiftPattern,
    Shiftresult, StoreDefaultSkillRequirement, StaffRejectionHistory
)
from collections import defaultdict
from datetime import datetime, timedelta
import calendar
from ortools.sat.python import cp_model
from typing import Optional, List, Dict, Tuple
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

def get_skills(db_session: Session, store_id: int, day_type: str):
    """
    DBからスタッフスキルと店舗スキル必要レベルを取得

    Args:
        db_session: SQLAlchemyのセッション
        store_id: 対象店舗ID
        day_type: 曜日区分 ("平日", "金曜日", "土曜日", "日曜日")

    Returns:
        staff_skills: {staff_id: {"kitchen_a":int, "kitchen_b":int, "hall":int, "leadership":int}}
        store_requirements: {"kitchen_a":int, "kitchen_b":int, "hall":int, "leadership":int}
    """

    # スタッフ情報取得（対象店舗）
    staffs = db_session.query(Staff).filter(Staff.store_id == store_id).all()
    staff_skills = {}
    for s in staffs:
        staff_skills[s.id] = {
            "kitchen_a": rank_value(s.kitchen_a),
            "kitchen_b": rank_value(s.kitchen_b),
            "hall": s.hall,
            "leadership": s.leadership,
        }

    # 店舗のスキル必要レベル取得
    req = db_session.query(StoreDefaultSkillRequirement).filter(
        StoreDefaultSkillRequirement.store_id == store_id,
        StoreDefaultSkillRequirement.day_type == day_type
    ).first()

    if not req:
        raise ValueError(f"StoreDefaultSkillRequirement が見つかりません store_id={store_id} day_type={day_type}")

    store_requirements = {
        "kitchen_a": rank_value(req.kitchen_a),
        "kitchen_b": rank_value(req.kitchen_b),
        "hall": req.hall,
        "leadership": req.leadership,
    }

    return staff_skills, store_requirements


def get_matching_pattern(
    start_time: int,
    end_time: int,
    patterns: List[ShiftPattern],
    is_employee: bool = False
) -> Optional[ShiftPattern]:
    """指定された時間帯に最も適したシフトパターンを探す"""
    if not patterns:
        return None

    # 社員の場合は、最も長いパターンを優先
    if is_employee:
        valid_patterns = [
            p for p in patterns
            if p.start_time <= start_time and p.end_time >= end_time
        ]
        if valid_patterns:
            return max(valid_patterns, key=lambda p: p.end_time - p.start_time)
        return None

    # 完全一致するパターンを探す
    exact_match = next(
        (p for p in patterns if p.start_time == start_time and p.end_time == end_time),
        None
    )
    if exact_match:
        return exact_match

    # 時間帯を含むパターンを探す
    containing_pattern = next(
        (p for p in patterns if p.start_time <= start_time and p.end_time >= end_time),
        None
    )
    if containing_pattern:
        return containing_pattern

    # 最も近いパターンを探す
    best_pattern = None
    min_diff = float('inf')
    for p in patterns:
        start_diff = abs(p.start_time - start_time)
        end_diff = abs(p.end_time - end_time)
        total_diff = start_diff + end_diff
        if total_diff < min_diff:
            min_diff = total_diff
            best_pattern = p

    return best_pattern

def calculate_shift_score(
    pattern: ShiftPattern,
    store: Store,
    peak_start: int,
    peak_end: int,
    day_type: str
) -> float:
    """シフトパターンのスコアを計算（要件に基づく詳細な評価）"""
    score = 0.0
    
    # 1. ピーク時間との重なり評価（重要度: 高）
    peak_hours = set(range(peak_start, peak_end))
    pattern_hours = set(range(pattern.start_time, pattern.end_time))
    peak_cover_ratio = len(peak_hours & pattern_hours) / len(peak_hours) if peak_hours else 0
    score += peak_cover_ratio * 3.0  # ピーク時間の重なりは重要

    # 2. オープン・クローズ対応（重要度: 中）
    can_open = 1 if pattern.start_time <= store.open_hours else 0
    can_close = 1 if pattern.end_time >= store.close_hours else 0
    score += (can_open + can_close) * 1.5

    # 3. 曜日別の評価
    if day_type == "平日":
        # 平日はピーク時間帯のカバーを重視
        score += peak_cover_ratio * 2.0
    elif day_type == "土曜日":
        # 土曜は全体的なカバーを重視
        score += len(pattern_hours) / (store.close_hours - store.open_hours) * 2.0
    elif day_type == "日曜日":
        # 日曜はオープン・クローズ対応を重視
        score += (can_open + can_close) * 2.0

    return score

def get_skills_penalty(
    staff: Staff,
    pattern: ShiftPattern,
    store_req: StoreDefaultSkillRequirement
) -> float:
    """スキル要件に対するペナルティを計算"""
    penalty = 0.0
    
    # キッチンAスキル
    staff_kitchen_a = rank_value(staff.kitchen_a)
    req_kitchen_a = rank_value(store_req.kitchen_a)
    if staff_kitchen_a < req_kitchen_a:
        penalty += (req_kitchen_a - staff_kitchen_a) * 2.0

    # キッチンBスキル
    staff_kitchen_b = rank_value(staff.kitchen_b)
    req_kitchen_b = rank_value(store_req.kitchen_b)
    if staff_kitchen_b < req_kitchen_b:
        penalty += (req_kitchen_b - staff_kitchen_b) * 2.0

    # ホールスキル
    if staff.hall < store_req.hall:
        penalty += (store_req.hall - staff.hall) * 1.5

    # リーダーシップ
    if staff.leadership < store_req.leadership:
        penalty += (store_req.leadership - staff.leadership) * 3.0

    return penalty

def get_rejection_ratio(staff_id: int, db: Session, year: int, month: int) -> float:
    """過去の不採用率を計算"""
    # 過去3ヶ月の不採用履歴を取得
    three_months_ago = datetime(year, month, 1) - timedelta(days=90)
    rejections = db.query(StaffRejectionHistory).filter(
        StaffRejectionHistory.staff_id == staff_id,
        StaffRejectionHistory.date >= three_months_ago
    ).all()
    
    if not rejections:
        return 0.0
    
    total_requests = sum(r.total_requests for r in rejections)
    total_rejections = sum(r.rejected_count for r in rejections)
    
    return total_rejections / total_requests if total_requests > 0 else 0.0

def generate_shift_results_with_ortools(db: Session, store_id: int, year: int, month: int) -> str:
    # 1. 店舗取得
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise ValueError(f"Store not found: id={store_id}")

    # 2. スタッフ全員取得・分類
    all_staffs: List[Staff] = db.query(Staff).filter(Staff.store_id == store_id).all()
    employees = [s for s in all_staffs if s.employment_type == "社員"]
    staffs = [s for s in all_staffs if s.employment_type != "社員"]

    # 3. シフト希望取得
    shift_requests: List[ShiftRequest] = db.query(ShiftRequest).filter(
        ShiftRequest.year == year,
        ShiftRequest.month == month,
        ShiftRequest.staff_id.in_([s.id for s in all_staffs])
    ).all()

    requests: Dict[Tuple[int, int], ShiftRequest] = {(r.staff_id, r.day): r for r in shift_requests}

    # 4. シフトパターン取得
    patterns: List[ShiftPattern] = db.query(ShiftPattern).all()
    if not patterns:
        raise ValueError("シフトパターンが設定されていません")

    _, last_day = calendar.monthrange(year, month)

    # 5. 既存のShiftresultを削除
    try:
        db.query(Shiftresult).filter(
            Shiftresult.year == year,
            Shiftresult.month == month,
            Shiftresult.staff_id.in_([s.id for s in all_staffs])
        ).delete(synchronize_session=False)
        db.flush()
    except Exception as e:
        raise ValueError(f"既存のシフト削除に失敗しました: {str(e)}")

    new_results: List[Shiftresult] = []

    # 6. 社員のシフト結果作成（希望をそのまま反映）
    for s in employees:
        for day in range(1, last_day + 1):
            req = requests.get((s.id, day))
            
            # 休み希望の場合は必ずシフトを入れない
            if req is None or req.status in ("X", ""):
                continue

            # 社員の希望をそのまま反映
            if req.status == "O":
                # オープン希望の場合は店舗の営業時間
                start = store.open_hours
                end = store.close_hours
            elif req.status == "time":
                # 時間指定の場合はその時間をそのまま使用
                start = req.start_time
                end = req.end_time
            else:
                continue

            # シフト結果を追加（1時間単位で追加）
            for hour in range(start, end):
                new_results.append(Shiftresult(
                    staff_id=s.id,
                    year=year,
                    month=month,
                    day=day,
                    start_time=hour,
                    end_time=hour + 1,
                    shift_id=None,
                ))

    # 7. OR-Tools モデル作成（バイト用）
    model = cp_model.CpModel()

    # 8. 変数定義（バイトのみ）
    x = {}  # (staff_id, day, pattern_id) → BoolVar
    for s in staffs:
        for day in range(1, last_day + 1):
            for p in patterns:
                x[(s.id, day, p.id)] = model.NewBoolVar(f"x_s{s.id}_d{day}_p{p.id}")

    y = {}  # (staff_id, day, hour) → BoolVar（勤務しているか）
    for s in staffs:
        for day in range(1, last_day + 1):
            for hour in range(store.open_hours, store.close_hours):
                y[(s.id, day, hour)] = model.NewBoolVar(f"y_s{s.id}_d{day}_h{hour}")

    # 9. 連勤制約（バイトのみ）- 制約を緩和
    max_consecutive_days = 5  # 連勤制限を緩和
    for s in staffs:
        for start_day in range(1, last_day - max_consecutive_days + 2):
            work_vars = []
            for day in range(start_day, start_day + max_consecutive_days):
                work_var = model.NewBoolVar(f"work_s{s.id}_d{day}")
                pattern_vars = []
                for p in patterns:
                    pattern_vars.append(x[(s.id, day, p.id)])
                if pattern_vars:
                    model.AddMaxEquality(work_var, pattern_vars)
                work_vars.append(work_var)
            if work_vars:
                model.Add(sum(work_vars) <= max_consecutive_days)  # 制約を緩和

    # 10. y[s,d,h] = OR(x[s,d,p]) ただしpはhを含む勤務パターン
    for s in staffs:
        for day in range(1, last_day + 1):
            for hour in range(store.open_hours, store.close_hours):
                covering = [p for p in patterns if p.start_time <= hour < p.end_time]
                if covering:
                    pattern_vars = []
                    for p in covering:
                        pattern_vars.append(x[(s.id, day, p.id)])
                    if pattern_vars:
                        model.AddMaxEquality(y[(s.id, day, hour)], pattern_vars)
                else:
                    model.Add(y[(s.id, day, hour)] == 0)

    # 11. 希望勤務時間帯制約（バイトのみ）- 大幅に緩和
    for s in staffs:
        for day in range(1, last_day + 1):
            req = requests.get((s.id, day))
            for p in patterns:
                if req is None:
                    model.Add(x[(s.id, day, p.id)] == 0)
                    continue

                can_work = True  # デフォルトでTrue
                if req.status == "O":
                    # オープン希望の場合は、営業時間内のパターンを許可
                    if p.start_time < store.open_hours or p.end_time > store.close_hours:
                        can_work = False
                elif req.status == "time":
                    # 時間指定の場合は、指定時間と重なるパターンを許可
                    if p.end_time <= req.start_time or p.start_time >= req.end_time:
                        can_work = False
                elif req.status in ("X", ""):
                    can_work = False

                if not can_work:
                    model.Add(x[(s.id, day, p.id)] == 0)

    # 12. 1日1パターン以下の制約（バイトのみ）
    for s in staffs:
        for day in range(1, last_day + 1):
            pattern_vars = []
            for p in patterns:
                pattern_vars.append(x[(s.id, day, p.id)])
            if pattern_vars:
                model.Add(sum(pattern_vars) <= 1)

    # 13. 各時間帯の人数制約（社員のシフトも考慮）- 制約を緩和
    holidays = get_holidays(year, month)
    for day in range(1, last_day + 1):
        day_type = get_day_type(year, month, day, holidays)
        skill_req = next((r for r in store.default_skill_requirements if r.day_type == day_type), None)
        if not skill_req:
            raise ValueError(f"Day type '{day_type}' skill setting not found")

        # 社員の勤務時間帯抽出
        employee_work_hours = [
            (r.staff_id, r.day, r.start_time)
            for r in new_results if r.staff_id in [e.id for e in employees] and r.day == day
        ]

        for hour in range(store.open_hours, store.close_hours):
            if hour < skill_req.peak_start_hour:
                min_staff = max(1, skill_req.open_people - 1)  # 最小人数を緩和
                max_staff = min_staff + 3  # 余裕を持たせる
            elif hour < skill_req.peak_end_hour:
                min_staff = max(2, skill_req.peak_people - 1)  # 最小人数を緩和
                max_staff = min_staff + 3  # 余裕を持たせる
            else:
                min_staff = max(1, skill_req.close_people - 1)  # 最小人数を緩和
                max_staff = min_staff + 2  # 余裕を持たせる

            employee_count = sum(1 for (_, d, h) in employee_work_hours if h == hour)
            
            # バイトの勤務変数を集計
            staff_vars = []
            for s in staffs:
                staff_vars.append(y[(s.id, day, hour)])
            
            if staff_vars:
                # 最小人数制約（緩和）
                model.Add(sum(staff_vars) + employee_count >= min_staff)
                # 最大人数制約（緩和）
                model.Add(sum(staff_vars) + employee_count <= max_staff)

    # 14. 目的関数の設定 - 大幅に調整
    objective_terms = []
    
    # スキル要件のペナルティ（重みを大幅に下げる）
    for s in staffs:
        for day in range(1, last_day + 1):
            day_type = get_day_type(year, month, day, holidays)
            skill_req = next((r for r in store.default_skill_requirements if r.day_type == day_type), None)
            
            for p in patterns:
                pattern_var = x[(s.id, day, p.id)]
                skill_penalty = get_skills_penalty(s, p, skill_req) * 0.2  # 重みを0.2倍に
                penalty_var = model.NewIntVar(0, 100, f"penalty_s{s.id}_d{day}_p{p.id}")
                
                model.Add(penalty_var == int(100 * skill_penalty)).OnlyEnforceIf(pattern_var)
                model.Add(penalty_var == 0).OnlyEnforceIf(pattern_var.Not())
                objective_terms.append(penalty_var)

    # 公平性のペナルティ（重みを大幅に上げる）
    for s in staffs:
        for day in range(1, last_day + 1):
            rejection_ratio = get_rejection_ratio(s.id, db, year, month)
            penalty_var = model.NewIntVar(0, 100, f"fairness_s{s.id}_d{day}")
            
            pattern_vars = []
            for p in patterns:
                pattern_vars.append(x[(s.id, day, p.id)])
            
            if pattern_vars:
                no_pattern_selected = model.NewBoolVar(f"no_pattern_s{s.id}_d{day}")
                model.Add(sum(pattern_vars) == 0).OnlyEnforceIf(no_pattern_selected)
                model.Add(sum(pattern_vars) > 0).OnlyEnforceIf(no_pattern_selected.Not())
                
                # 公平性のペナルティを5倍に
                model.Add(penalty_var == int(500 * (1 - rejection_ratio))).OnlyEnforceIf(no_pattern_selected)
                model.Add(penalty_var == 0).OnlyEnforceIf(no_pattern_selected.Not())
                objective_terms.append(penalty_var)

    # 目的関数の最小化
    if objective_terms:
        model.Minimize(sum(objective_terms))

    # 15. モデルを解く
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 120.0  # 時間制限を延長
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return "fail"

    # 16. 解の保存（バイトのシフト）
    for s in staffs:
        for day in range(1, last_day + 1):
            for p in patterns:
                if solver.BooleanValue(x[(s.id, day, p.id)]):
                    for hour in range(p.start_time, p.end_time):
                        new_results.append(Shiftresult(
                            staff_id=s.id,
                            year=year,
                            month=month,
                            day=day,
                            start_time=hour,
                            end_time=hour + 1,
                            shift_id=None,
                        ))

    # 17. 結果を保存
    try:
        db.bulk_save_objects(new_results)
        db.commit()
    except Exception as e:
        db.rollback()
        raise ValueError(f"シフト結果の保存に失敗しました: {str(e)}")

    return "ok"