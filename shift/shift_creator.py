from sqlalchemy.orm import Session
from models import (
    Staff, Store, ShiftRequest, ShiftPattern,
    Shiftresult, StoreDefaultSkillRequirement
)
from collections import defaultdict
from datetime import datetime
import calendar
from ortools.sat.python import cp_model
from typing import Optional, List, Dict, Tuple, Set, Any
import jpholiday
from .shift_validator import get_day_type


def get_holidays(year: int, month: int) -> Set[datetime.date]:
    """指定された年月の祝日を取得する
    
    Args:
        year: 年
        month: 月
    
    Returns:
        holidays: 祝日のセット
    """
    holidays = set()
    _, last_day = calendar.monthrange(year, month)
    for day in range(1, last_day + 1):
        date = datetime(year, month, day).date()
        if jpholiday.is_holiday(date):
            holidays.add(date)
    return holidays


def classify_time_blocks(
    store: Store,
    day_type: str
) -> Tuple[List[Tuple[int, int]], StoreDefaultSkillRequirement]:
    """時間帯を分類し、各時間帯の必要人数を取得する
    
    Args:
        store: 店舗情報
        day_type: 曜日区分
    
    Returns:
        blocks: [(時間, 必要人数)]のリスト
        default_setting: スキル要件設定
    """
    default_setting = next(
        (s for s in store.default_skill_requirements 
         if s.day_type == day_type),
        None
    )
    if not default_setting:
        raise ValueError(f"{day_type} のスキル設定がありません")

    blocks = []
    for hour in range(store.open_hours, store.close_hours):
        if hour < default_setting.peak_start_hour:
            max_people = default_setting.open_people
        elif (default_setting.peak_start_hour <= hour < 
                default_setting.peak_end_hour):
            max_people = default_setting.peak_people
        else:
            max_people = default_setting.close_people
        blocks.append((hour, max_people))
    return blocks, default_setting


def rank_value(rank: str) -> int:
    """スキルランクを数値に変換する
    
    Args:
        rank: スキルランク ("A", "B", "C")
    
    Returns:
        value: 数値 (A=3, B=2, C=1, その他=0)
    """
    return {"A": 3, "B": 2, "C": 1}.get(rank, 0)


def get_skills(
    db_session: Session,
    store_id: int,
    day_type: str
) -> Tuple[Dict[int, Dict[str, int]], Dict[str, int]]:
    """スタッフスキルと店舗スキル必要レベルを取得する
    
    Args:
        db_session: データベースセッション
        store_id: 店舗ID
        day_type: 曜日区分
    
    Returns:
        staff_skills: {staff_id: {スキル名: レベル}}
        store_requirements: {スキル名: 必要レベル}
    """
    # スタッフ情報取得
    staffs = db_session.query(Staff).filter(
        Staff.store_id == store_id
    ).all()
    
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
        msg = (
            f"StoreDefaultSkillRequirement が見つかりません "
            f"store_id={store_id} day_type={day_type}"
        )
        raise ValueError(msg)

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
    """指定された時間帯に最も適したシフトパターンを探す
    
    Args:
        start_time: 開始時間
        end_time: 終了時間
        patterns: シフトパターンリスト
        is_employee: 社員かどうか
    
    Returns:
        pattern: 最適なシフトパターン
    """
    if not patterns:
        return None

    # 社員の場合は、最も長いパターンを優先
    if is_employee:
        valid_patterns = [
            p for p in patterns
            if (p.start_time <= start_time and 
                p.end_time >= end_time)
        ]
        if valid_patterns:
            return max(
                valid_patterns,
                key=lambda p: p.end_time - p.start_time
            )
        return None

    # 完全一致するパターンを探す
    exact_match = next(
        (p for p in patterns 
         if (p.start_time == start_time and 
             p.end_time == end_time)),
        None
    )
    if exact_match:
        return exact_match

    # 時間帯を含むパターンを探す
    containing_pattern = next(
        (p for p in patterns 
         if (p.start_time <= start_time and 
             p.end_time >= end_time)),
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
    shift: Shiftresult,
    staff_skills: Dict[int, Dict[str, int]],
    store_requirements: Dict[str, int],
    patterns: List[ShiftPattern],
    is_employee: bool = False
) -> float:
    """シフトのスコアを計算する
    
    Args:
        shift: シフト結果
        staff_skills: {staff_id: {スキル名: レベル}}
        store_requirements: {スキル名: 必要レベル}
        patterns: シフトパターンリスト
        is_employee: 社員かどうか
    
    Returns:
        score: シフトのスコア
    """
    # スキルペナルティの計算
    skills_penalty = get_skills_penalty(
        shift, staff_skills, store_requirements
    )

    # シフトパターンの適合度を計算
    pattern = get_matching_pattern(
        shift.start_time,
        shift.end_time,
        patterns,
        is_employee
    )
    pattern_score = 0.0
    if pattern:
        if (pattern.start_time == shift.start_time and 
                pattern.end_time == shift.end_time):
            pattern_score = 1.0
        elif (pattern.start_time <= shift.start_time and 
                pattern.end_time >= shift.end_time):
            pattern_score = 0.8
        else:
            pattern_score = 0.5
    else:
        pattern_score = 0.2

    # 総合スコアの計算
    total_score = (
        (1.0 - skills_penalty) * 0.7 +  # スキル適合度
        pattern_score * 0.3  # パターン適合度
    )

    return total_score


def get_skills_penalty(
    shift: Shiftresult,
    staff_skills: Dict[int, Dict[str, int]],
    store_requirements: Dict[str, int]
) -> float:
    """スキルペナルティを計算する
    
    Args:
        shift: シフト結果
        staff_skills: {staff_id: {スキル名: レベル}}
        store_requirements: {スキル名: 必要レベル}
    
    Returns:
        penalty: スキルペナルティ（0.0-1.0）
    """
    if shift.staff_id not in staff_skills:
        return 1.0

    staff_skill = staff_skills[shift.staff_id]
    total_diff = 0
    total_weight = 0

    for skill_name, required_level in store_requirements.items():
        if skill_name not in staff_skill:
            continue

        staff_level = staff_skill[skill_name]
        diff = max(0, required_level - staff_level)
        weight = 1.0  # スキルごとの重み付けは必要に応じて調整

        total_diff += diff * weight
        total_weight += weight

    if total_weight == 0:
        return 1.0

    return min(1.0, total_diff / total_weight)


def get_rejection_ratio(
    shift: Shiftresult,
    staff_requests: Dict[int, List[Dict[str, Any]]]
) -> float:
    """シフトの拒否率を計算する
    
    Args:
        shift: シフト結果
        staff_requests: {staff_id: [リクエスト辞書]}
    
    Returns:
        ratio: 拒否率（0.0-1.0）
    """
    if shift.staff_id not in staff_requests:
        return 0.0

    requests = staff_requests[shift.staff_id]
    for req in requests:
        if (req['date'] == shift.date and 
                req['start_time'] == shift.start_time and 
                req['end_time'] == shift.end_time):
            return 1.0 if req.get('is_rejected', False) else 0.0

    return 0.0

def optimize_time_allocation(
    db: Session,
    store: Store,
    staffs: List[Staff],
    patterns: List[ShiftPattern],
    year: int,
    month: int,
    staff_requests: Dict[int, List[Dict[str, Any]]]
) -> List[Shiftresult]:
    """時間配分を最適化する
    
    Args:
        db: データベースセッション
        store: 店舗情報
        staffs: スタッフリスト
        patterns: シフトパターンリスト
        year: 年
        month: 月
        staff_requests: {staff_id: [リクエスト辞書]}
    
    Returns:
        results: シフト結果リスト
    """
    model = cp_model.CpModel()
    last_day = calendar.monthrange(year, month)[1]

    # 変数定義
    x = {}
    for staff in staffs:
        for day in range(1, last_day + 1):
            for pattern in patterns:
                x[(staff.id, day, pattern.id)] = model.NewBoolVar(
                    f'x_{staff.id}_{day}_{pattern.id}'
                )

    # 制約条件の設定
    for staff in staffs:
        for day in range(1, last_day + 1):
            # 1日1パターンのみ
            model.Add(
                sum(x[(staff.id, day, p.id)] for p in patterns) <= 1
            )

            # リクエストとの整合性
            if staff.id in staff_requests:
                for req in staff_requests[staff.id]:
                    if req['date'].day == day:
                        for p in patterns:
                            if (p.start_time == req['start_time'] and 
                                    p.end_time == req['end_time']):
                                if req.get('is_rejected', False):
                                    model.Add(
                                        x[(staff.id, day, p.id)] == 0
                                    )

    # 目的関数の設定
    objective_terms = []
    for staff in staffs:
        for day in range(1, last_day + 1):
            day_type = get_day_type(
                datetime(year, month, day)
            )
            skill_req = db.query(
                StoreDefaultSkillRequirement
            ).filter(
                StoreDefaultSkillRequirement.store_id == store.id,
                StoreDefaultSkillRequirement.day_type == day_type
            ).first()

            if not skill_req:
                continue

            for p in patterns:
                # スキル要件のペナルティを計算
                penalty = get_skills_penalty(
                    staff, p, skill_req
                )
                if penalty > 0:
                    objective_terms.append(
                        x[(staff.id, day, p.id)] * penalty
                    )

    # 公平性のペナルティ（不採用率の均等化）
    for staff in staffs:
        rejection_ratio = get_rejection_ratio(
            staff, staff_requests
        )
        if rejection_ratio > 0:
            for day in range(1, last_day + 1):
                for p in patterns:
                    objective_terms.append(
                        x[(staff.id, day, p.id)] * rejection_ratio
                    )

    model.Minimize(sum(objective_terms))

    # ソルバーの実行
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status != cp_model.OPTIMAL:
        return []

    # 結果の生成
    results = []
    for staff in staffs:
        for day in range(1, last_day + 1):
            for p in patterns:
                if solver.Value(x[(staff.id, day, p.id)]) == 1:
                    results.append(
                        Shiftresult(
                            staff_id=staff.id,
                            date=datetime(year, month, day),
                            start_time=p.start_time,
                            end_time=p.end_time
                        )
                    )

    return results

def optimize_staffing_levels(
    db: Session,
    store: Store,
    staffs: List[Staff],
    patterns: List[ShiftPattern],
    year: int,
    month: int,
    staff_requests: Dict[int, List[Dict[str, Any]]]
) -> List[Shiftresult]:
    """スタッフ配置を最適化する
    
    Args:
        db: データベースセッション
        store: 店舗情報
        staffs: スタッフリスト
        patterns: シフトパターンリスト
        year: 年
        month: 月
        staff_requests: {staff_id: [リクエスト辞書]}
    
    Returns:
        results: シフト結果リスト
    """
    # 時間配分の最適化
    time_results = optimize_time_allocation(
        db, store, staffs, patterns, year, month, staff_requests
    )

    # スタッフ配置の最適化
    model = cp_model.CpModel()
    last_day = calendar.monthrange(year, month)[1]

    # 変数定義
    x = {}
    for staff in staffs:
        for day in range(1, last_day + 1):
            for hour in range(store.open_hours, store.close_hours):
                x[(staff.id, day, hour)] = model.NewBoolVar(
                    f'x_{staff.id}_{day}_{hour}'
                )

    # 制約条件の設定
    for day in range(1, last_day + 1):
        day_type = get_day_type(datetime(year, month, day))
        skill_req = db.query(StoreDefaultSkillRequirement).filter(
            StoreDefaultSkillRequirement.store_id == store.id,
            StoreDefaultSkillRequirement.day_type == day_type
        ).first()

        if not skill_req:
            continue

        for hour in range(store.open_hours, store.close_hours):
            # 必要人数の制約
            required_staff = skill_req.required_staff
            model.Add(
                sum(x[(s.id, day, hour)] for s in staffs) >= required_staff
            )

            # スキル要件の制約
            for staff in staffs:
                if (staff.kitchen_a < skill_req.kitchen_a or
                        staff.kitchen_b < skill_req.kitchen_b or
                        staff.hall < skill_req.hall or
                        staff.leadership < skill_req.leadership):
                    model.Add(x[(staff.id, day, hour)] == 0)

    # 目的関数の設定
    objective_terms = []
    for staff in staffs:
        for day in range(1, last_day + 1):
            for hour in range(store.open_hours, store.close_hours):
                # 時間配分結果との整合性
                for result in time_results:
                    if (result.staff_id == staff.id and
                            result.date.day == day and
                            result.start_time <= hour < result.end_time):
                        objective_terms.append(
                            x[(staff.id, day, hour)] * 0.1
                        )
                    else:
                        objective_terms.append(
                            x[(staff.id, day, hour)] * 1.0
                        )

    model.Minimize(sum(objective_terms))

    # ソルバーの実行
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status != cp_model.OPTIMAL:
        return time_results

    # 結果の生成
    results = []
    for staff in staffs:
        for day in range(1, last_day + 1):
            start_time = None
            for hour in range(store.open_hours, store.close_hours):
                if solver.Value(x[(staff.id, day, hour)]) == 1:
                    if start_time is None:
                        start_time = hour
                elif start_time is not None:
                    results.append(
                        Shiftresult(
                            staff_id=staff.id,
                            date=datetime(year, month, day),
                            start_time=start_time,
                            end_time=hour
                        )
                    )
                    start_time = None

            if start_time is not None:
                results.append(
                    Shiftresult(
                        staff_id=staff.id,
                        date=datetime(year, month, day),
                        start_time=start_time,
                        end_time=store.close_hours
                    )
                )

    return results

def optimize_required_staff(
    db: Session,
    store: Store,
    staffs: List[Staff],
    year: int,
    month: int,
    staff_requests: Dict[int, List[Dict[str, Any]]]
) -> Dict[Tuple[int, int], int]:
    """必要人数を最適化する
    
    Args:
        db: データベースセッション
        store: 店舗情報
        staffs: スタッフリスト
        year: 年
        month: 月
        staff_requests: {staff_id: [リクエスト辞書]}
    
    Returns:
        required_staff: {(日, 時間): 必要人数}
    """
    last_day = calendar.monthrange(year, month)[1]
    required_staff = {}

    for day in range(1, last_day + 1):
        day_type = get_day_type(datetime(year, month, day))
        skill_req = db.query(StoreDefaultSkillRequirement).filter(
            StoreDefaultSkillRequirement.store_id == store.id,
            StoreDefaultSkillRequirement.day_type == day_type
        ).first()

        if not skill_req:
            continue

        for hour in range(store.open_hours, store.close_hours):
            # 基本必要人数
            base_required = skill_req.required_staff

            # リクエストに基づく調整
            available_staff = sum(
                1 for staff in staffs
                if staff.id in staff_requests and any(
                    req['date'].day == day and
                    req['start_time'] <= hour < req['end_time'] and
                    not req.get('is_rejected', False)
                    for req in staff_requests[staff.id]
                )
            )

            # 必要人数の決定
            required_staff[(day, hour)] = min(
                base_required,
                available_staff
            )

    return required_staff

def assign_shift_patterns(
    model: cp_model.CpModel,
    staffs: List[Staff],
    patterns: List[ShiftPattern],
    requests: Dict[Tuple[int, int], ShiftRequest],
    required_staff: Dict[Tuple[int, int], int],
    store: Store,
    last_day: int
) -> Tuple[Dict, Dict]:
    """決定された必要人数に基づいてシフトパターンを割り当てる
    
    Returns:
        x: (staff_id, day, pattern_id) → BoolVar
        y: (staff_id, day, hour) → BoolVar
    """
    print("\n=== シフトパターンの割り当て ===")
    
    # 変数定義
    x = {}  # (staff_id, day, pattern_id) → BoolVar
    for s in staffs:
        for day in range(1, last_day + 1):
            for p in patterns:
                x[(s.id, day, p.id)] = model.NewBoolVar(
                    f"x_s{s.id}_d{day}_p{p.id}")

    y = {}  # (staff_id, day, hour) → BoolVar
    for s in staffs:
        for day in range(1, last_day + 1):
            for hour in range(store.open_hours, store.close_hours):
                y[(s.id, day, hour)] = model.NewBoolVar(
                    f"y_s{s.id}_d{day}_h{hour}")

    # 1. 必要人数の制約
    print("必要人数の制約を設定中...")
    for day in range(1, last_day + 1):
        for hour in range(store.open_hours, store.close_hours):
            required = required_staff.get((day, hour), 0)
            staff_vars = [y[(s.id, day, hour)] for s in staffs]
            if staff_vars:
                model.Add(sum(staff_vars) == required)

    # 2. 時間帯制約
    print("時間帯制約を設定中...")
    for s in staffs:
        for day in range(1, last_day + 1):
            for hour in range(store.open_hours, store.close_hours):
                covering = [p for p in patterns 
                          if p.start_time <= hour < p.end_time]
                if covering:
                    pattern_vars = [x[(s.id, day, p.id)] for p in covering]
                    if pattern_vars:
                        model.AddMaxEquality(y[(s.id, day, hour)], 
                                          pattern_vars)
                else:
                    model.Add(y[(s.id, day, hour)] == 0)

    # 3. 希望勤務時間帯制約
    print("希望勤務時間帯制約を設定中...")
    for s in staffs:
        for day in range(1, last_day + 1):
            req = requests.get((s.id, day))
            for p in patterns:
                if req is None:
                    model.Add(x[(s.id, day, p.id)] == 0)
                    continue

                can_work = True
                if req.status == "O":
                    if (p.start_time < store.open_hours or 
                        p.end_time > store.close_hours):
                        can_work = False
                elif req.status == "time":
                    if (p.end_time <= req.start_time or 
                        p.start_time >= req.end_time):
                        can_work = False
                elif req.status in ("X", ""):
                    can_work = False

                if not can_work:
                    model.Add(x[(s.id, day, p.id)] == 0)

    # 4. 連勤制約
    print("連勤制約を設定中...")
    max_consecutive_days = 5
    for s in staffs:
        for start_day in range(1, last_day - max_consecutive_days + 2):
            work_vars = []
            for day in range(start_day, start_day + max_consecutive_days):
                work_var = model.NewBoolVar(f"work_s{s.id}_d{day}")
                pattern_vars = [x[(s.id, day, p.id)] for p in patterns]
                if pattern_vars:
                    model.AddMaxEquality(work_var, pattern_vars)
                work_vars.append(work_var)
            if work_vars:
                model.Add(sum(work_vars) <= max_consecutive_days)

    return x, y

def determine_daily_staff(
    db: Session,
    store: Store,
    staffs: List[Staff],
    employees: List[Staff],
    requests: Dict[Tuple[int, int], ShiftRequest],
    holidays: set[datetime.date],
    year: int,
    month: int,
    last_day: int
) -> Tuple[Dict[Tuple[int, int], List[int]], Dict[int, float]]:
    """日別の勤務メンバーを決定する（スキル要件を考慮）
    
    Args:
        db: データベースセッション
        store: 店舗情報
        staffs: バイトスタッフリスト
        employees: 社員リスト
        requests: シフト希望辞書
        holidays: 祝日セット
        year: 年
        month: 月
        last_day: 月末日
    
    Returns:
        daily_staff: (day, hour) → 勤務スタッフIDのリスト
        rejection_ratios: staff_id → 不採用率
    """
    print("\n=== 日別勤務メンバーの決定（スキル要件考慮） ===")
    
    # 初期化
    daily_staff = {}  # (day, hour) → List[staff_id]
    confirmed_days = set()  # 確定した日
    staff_work_days = defaultdict(set)  # staff_id → 勤務日集合
    staff_rejections = defaultdict(int)  # staff_id → 不採用回数
    total_requests = defaultdict(int)  # staff_id → 希望回数
    
    # スタッフのスキル情報を取得
    staff_skills = {}
    for staff in staffs + employees:
        staff_skills[staff.id] = {
            "kitchen_a": rank_value(staff.kitchen_a),
            "kitchen_b": rank_value(staff.kitchen_b),
            "hall": staff.hall,
            "leadership": staff.leadership,
        }
    
    # 1. 社員の勤務日を確定（スキル要件を考慮）
    for day in range(1, last_day + 1):
        day_type = get_day_type(year, month, day, holidays)
        skill_req = next((r for r in store.default_skill_requirements 
                         if r.day_type == day_type), None)
        if not skill_req:
            raise ValueError(f"{day_type}のスキル設定が見つかりません")
        
        # 社員の勤務を確定（スキル要件を満たす社員を優先）
        available_employees = []
        for emp in employees:
            req = requests.get((emp.id, day))
            if req and req.status != "X":
                # スキル要件をチェック
                emp_skills = staff_skills[emp.id]
                meets_requirements = (
                    emp_skills["kitchen_a"] >= rank_value(skill_req.kitchen_a) and
                    emp_skills["kitchen_b"] >= rank_value(skill_req.kitchen_b) and
                    emp_skills["hall"] >= skill_req.hall and
                    emp_skills["leadership"] >= skill_req.leadership
                )
                if meets_requirements:
                    available_employees.append(emp)
        
        # スキル要件を満たす社員を優先的に配置
        for emp in available_employees:
            for hour in range(store.open_hours, store.close_hours):
                if (day, hour) not in daily_staff:
                    daily_staff[(day, hour)] = []
                daily_staff[(day, hour)].append(emp.id)
            staff_work_days[emp.id].add(day)
    
    # 2. バイトの勤務日を決定（スキル要件を考慮）
    for day in range(1, last_day + 1):
        day_type = get_day_type(year, month, day, holidays)
        skill_req = next((r for r in store.default_skill_requirements 
                         if r.day_type == day_type), None)
        
        # ピーク時間帯の希望者を集計（スキル要件を考慮）
        peak_requests = []
        for staff in staffs:
            req = requests.get((staff.id, day))
            if req and req.status != "X":
                # ピーク時間帯の希望を確認
                if (req.status == "O" or 
                    (req.status == "time" and 
                     req.start_time <= skill_req.peak_start_hour and 
                     req.end_time >= skill_req.peak_end_hour)):
                    # スキル要件をチェック
                    staff_skills = staff_skills[staff.id]
                    meets_requirements = (
                        staff_skills["kitchen_a"] >= rank_value(skill_req.kitchen_a) and
                        staff_skills["kitchen_b"] >= rank_value(skill_req.kitchen_b) and
                        staff_skills["hall"] >= skill_req.hall and
                        staff_skills["leadership"] >= skill_req.leadership
                    )
                    if meets_requirements:
                        peak_requests.append(staff.id)
                        total_requests[staff.id] += 1
        
        # ピーク時間帯の人員調整（スキル要件を考慮）
        if len(peak_requests) > skill_req.peak_people:
            # 不採用者を決定（不採用率とスキル要件を考慮）
            current_rejection_ratios = {
                staff_id: staff_rejections[staff_id] / total_requests[staff_id]
                if total_requests[staff_id] > 0 else 0
                for staff_id in peak_requests
            }
            
            # 不採用者を選定
            to_reject = []
            while len(peak_requests) - len(to_reject) > skill_req.peak_people:
                # 不採用率が低い順にソート
                candidates = sorted(
                    [s for s in peak_requests if s not in to_reject],
                    key=lambda x: current_rejection_ratios[x]
                )
                if not candidates:
                    break
                
                # 連勤制約を考慮
                selected = None
                for staff_id in candidates:
                    work_days = staff_work_days[staff_id]
                    # 確定日前後の連勤をチェック
                    has_consecutive = any(
                        day + i in work_days for i in range(-3, 4)
                        if 1 <= day + i <= last_day
                    )
                    if not has_consecutive:
                        selected = staff_id
                        break
                
                if selected is None:
                    # 連勤制約を満たさない場合は不採用率が最も低い人を選択
                    selected = candidates[0]
                
                to_reject.append(selected)
                staff_rejections[selected] += 1
                current_rejection_ratios[selected] = (
                    staff_rejections[selected] / total_requests[selected]
                )
            
            # 採用者を確定
            confirmed_staff = [s for s in peak_requests if s not in to_reject]
            for staff_id in confirmed_staff:
                for hour in range(store.open_hours, store.close_hours):
                    if (day, hour) not in daily_staff:
                        daily_staff[(day, hour)] = []
                    daily_staff[(day, hour)].append(staff_id)
                staff_work_days[staff_id].add(day)
            
            confirmed_days.add(day)
        else:
            # ピーク時間帯の希望者が少ない場合、全員採用
            for staff_id in peak_requests:
                for hour in range(store.open_hours, store.close_hours):
                    if (day, hour) not in daily_staff:
                        daily_staff[(day, hour)] = []
                    daily_staff[(day, hour)].append(staff_id)
                staff_work_days[staff_id].add(day)
            confirmed_days.add(day)
    
    # 3. 不採用率の計算
    rejection_ratios = {
        staff_id: staff_rejections[staff_id] / total_requests[staff_id]
        if total_requests[staff_id] > 0 else 0
        for staff_id in [s.id for s in staffs]
    }
    
    return daily_staff, rejection_ratios

def optimize_time_patterns(
    model: cp_model.CpModel,
    daily_staff: Dict[Tuple[int, int], List[int]],
    staffs: List[Staff],
    patterns: List[ShiftPattern],
    requests: Dict[Tuple[int, int], ShiftRequest],
    store: Store,
    last_day: int
) -> Tuple[Dict, Dict]:
    """決定されたメンバーに対して時間パターンを最適化する
    
    Returns:
        x: (staff_id, day, pattern_id) → BoolVar
        y: (staff_id, day, hour) → BoolVar
    """
    print("\n=== 時間パターンの最適化 ===")
    
    # 変数定義
    x = {}  # (staff_id, day, pattern_id) → BoolVar
    y = {}  # (staff_id, day, hour) → BoolVar
    
    # 勤務が確定しているスタッフのみ変数を作成
    for day in range(1, last_day + 1):
        for hour in range(store.open_hours, store.close_hours):
            staff_ids = daily_staff.get((day, hour), [])
            for staff_id in staff_ids:
                if staff_id not in [s.id for s in staffs]:
                    continue  # 社員はスキップ
                
                for p in patterns:
                    if (staff_id, day, p.id) not in x:
                        x[(staff_id, day, p.id)] = model.NewBoolVar(
                            f"x_s{staff_id}_d{day}_p{p.id}")
                
                if (staff_id, day, hour) not in y:
                    y[(staff_id, day, hour)] = model.NewBoolVar(
                        f"y_s{staff_id}_d{day}_h{hour}")
    
    # 1. 時間帯制約
    print("時間帯制約を設定中...")
    for day in range(1, last_day + 1):
        for hour in range(store.open_hours, store.close_hours):
            staff_ids = daily_staff.get((day, hour), [])
            for staff_id in staff_ids:
                if staff_id not in [s.id for s in staffs]:
                    continue
                
                covering = [p for p in patterns 
                          if p.start_time <= hour < p.end_time]
                if covering:
                    pattern_vars = [x[(staff_id, day, p.id)] for p in covering]
                    if pattern_vars:
                        model.AddMaxEquality(y[(staff_id, day, hour)], 
                                          pattern_vars)
                else:
                    model.Add(y[(staff_id, day, hour)] == 0)
    
    # 2. 希望勤務時間帯制約
    print("希望勤務時間帯制約を設定中...")
    for day in range(1, last_day + 1):
        for hour in range(store.open_hours, store.close_hours):
            staff_ids = daily_staff.get((day, hour), [])
            for staff_id in staff_ids:
                if staff_id not in [s.id for s in staffs]:
                    continue
                
                req = requests.get((staff_id, day))
                for p in patterns:
                    if (staff_id, day, p.id) not in x:
                        continue
                    
                    can_work = True
                    if req:
                        if req.status == "O":
                            if (p.start_time < store.open_hours or 
                                p.end_time > store.close_hours):
                                can_work = False
                        elif req.status == "time":
                            if (p.end_time <= req.start_time or 
                                p.start_time >= req.end_time):
                                can_work = False
                        elif req.status in ("X", ""):
                            can_work = False
                    
                    if not can_work:
                        model.Add(x[(staff_id, day, p.id)] == 0)
    
    # 3. 1日1パターン制約
    print("1日1パターン制約を設定中...")
    for day in range(1, last_day + 1):
        for staff_id in set(
            s for (d, h), staffs in daily_staff.items() 
            if d == day for s in staffs
        ):
            if staff_id not in [s.id for s in staffs]:
                continue
            
            pattern_vars = [
                x[(staff_id, day, p.id)] 
                for p in patterns 
                if (staff_id, day, p.id) in x
            ]
            if pattern_vars:
                model.Add(sum(pattern_vars) == 1)
    
    return x, y

def validate_shift_requests(
    requests: List[ShiftRequest],
    staffs: List[Staff],
    store: Store
) -> Dict[Tuple[int, int], ShiftRequest]:
    """シフト希望を検証し、有効な希望のみを返す
    
    Args:
        requests: シフト希望リスト
        staffs: スタッフリスト
        store: 店舗情報
    
    Returns:
        valid_requests: (staff_id, day) → ShiftRequest
    """
    print("\n=== シフト希望の検証 ===")
    valid_requests = {}
    staff_ids = {s.id for s in staffs}
    
    for req in requests:
        if req.staff_id not in staff_ids:
            print(f"警告: 存在しないスタッフIDの希望をスキップ: staff_id={req.staff_id}")
            continue
        
        if req.status == "time":
            # 時間指定の検証
            if req.start_time >= req.end_time:
                print(f"警告: 無効な時間指定をスキップ: staff_id={req.staff_id}, "
                      f"day={req.day}, start={req.start_time}, end={req.end_time}")
                continue
            
            if req.start_time < store.open_hours or req.end_time > store.close_hours:
                print(f"警告: 営業時間外の希望をスキップ: staff_id={req.staff_id}, "
                      f"day={req.day}, start={req.start_time}, end={req.end_time}")
                continue
        
        valid_requests[(req.staff_id, req.day)] = req
    
    print(f"有効なシフト希望: {len(valid_requests)}件")
    return valid_requests


def validate_shift_patterns(
    patterns: List[ShiftPattern],
    store: Store
) -> List[ShiftPattern]:
    """シフトパターンを検証し、有効なパターンのみを返す
    
    Args:
        patterns: シフトパターンリスト
        store: 店舗情報
    
    Returns:
        valid_patterns: 有効なシフトパターンリスト
    """
    print("\n=== シフトパターンの検証 ===")
    valid_patterns = []
    
    for p in patterns:
        # 時間の検証
        if p.start_time >= p.end_time:
            print(f"警告: 無効な時間のパターンをスキップ: "
                  f"pattern_id={p.id}, start={p.start_time}, end={p.end_time}")
            continue
        
        # 営業時間内の検証
        if p.start_time < store.open_hours or p.end_time > store.close_hours:
            print(f"警告: 営業時間外のパターンをスキップ: "
                  f"pattern_id={p.id}, start={p.start_time}, end={p.end_time}")
            continue
        
        valid_patterns.append(p)
    
    print(f"有効なシフトパターン: {len(valid_patterns)}件")
    return valid_patterns


def validate_staffing_requirements(
    store: Store,
    employees: List[Staff],
    staffs: List[Staff],
    holidays: set[datetime.date],
    year: int,
    month: int,
    last_day: int
) -> None:
    """必要人数の設定を検証する
    
    Args:
        store: 店舗情報
        employees: 社員リスト
        staffs: バイトスタッフリスト
        holidays: 祝日セット
        year: 年
        month: 月
        last_day: 月末日
    """
    print("\n=== 必要人数の検証 ===")
    
    total_staff = len(employees) + len(staffs)
    print(f"総スタッフ数: {total_staff}人 (社員: {len(employees)}人, "
          f"バイト: {len(staffs)}人)")
    
    for day in range(1, last_day + 1):
        day_type = get_day_type(year, month, day, holidays)
        skill_req = next((r for r in store.default_skill_requirements 
                         if r.day_type == day_type), None)
        if not skill_req:
            raise ValueError(f"{day_type}のスキル設定が見つかりません")
        
        # ピーク時の必要人数チェック
        if skill_req.peak_people > total_staff:
            print(f"警告: {day}日({day_type})のピーク時必要人数({skill_req.peak_people}人)が "
                  f"総スタッフ数({total_staff}人)を超えています")
        
        # オープン時の必要人数チェック
        if skill_req.open_people > total_staff:
            print(f"警告: {day}日({day_type})のオープン時必要人数({skill_req.open_people}人)が "
                  f"総スタッフ数({total_staff}人)を超えています")
        
        # クローズ時の必要人数チェック
        if skill_req.close_people > total_staff:
            print(f"警告: {day}日({day_type})のクローズ時必要人数({skill_req.close_people}人)が "
                  f"総スタッフ数({total_staff}人)を超えています")


def add_skill_and_fairness_penalties(
    model: cp_model.CpModel,
    x: Dict,
    staffs: List[Staff],
    patterns: List[ShiftPattern],
    store: Store,
    holidays: set[datetime.date],
    year: int,
    month: int,
    last_day: int,
    objective_terms: List,
    db: Session
) -> None:
    """スキル要件と公平性のペナルティを追加する
    
    Args:
        model: CP-SATモデル
        x: 変数辞書
        staffs: バイトスタッフリスト
        patterns: シフトパターンリスト
        store: 店舗情報
        holidays: 祝日セット
        year: 年
        month: 月
        last_day: 月末日
        objective_terms: 目的関数の項リスト
        db: データベースセッション
    """
    print("\n=== スキル要件と公平性のペナルティ設定 ===")
    
    # スキル要件のペナルティ
    for day in range(1, last_day + 1):
        day_type = get_day_type(year, month, day, holidays)
        skill_req = next((r for r in store.default_skill_requirements 
                         if r.day_type == day_type), None)
        if not skill_req:
            continue
        
        for staff in staffs:
            for p in patterns:
                if (staff.id, day, p.id) not in x:
                    continue
                
                # スキル要件のペナルティを計算
                penalty = get_skills_penalty(
                    staff, p, skill_req
                )
                if penalty > 0:
                    objective_terms.append(x[(staff.id, day, p.id)] * penalty)
    
    # 公平性のペナルティ（不採用率の均等化）
    for staff in staffs:
        rejection_ratio = get_rejection_ratio(
            staff, staff_requests
        )
        if rejection_ratio > 0:
            for day in range(1, last_day + 1):
                for p in patterns:
                    if (staff.id, day, p.id) in x:
                        objective_terms.append(
                            x[(staff.id, day, p.id)] * rejection_ratio * 100
                        )

def create_shift(
    db,
    store: Store,
    employees: List[Staff],
    staffs: List[Staff],
    shift_requests: List[ShiftRequest],
    holidays: Set[datetime.date],
    year: int,
    month: int
) -> List[Shiftresult]:
    """シフトを生成する
    
    Args:
        db: データベースセッション
        store: 店舗情報
        employees: 社員リスト
        staffs: バイトリスト
        shift_requests: シフト希望リスト
        holidays: 休日リスト
        year: 年
        month: 月
    
    Returns:
        生成されたシフト結果のリスト
    """
    # 月末日を取得
    if month == 12:
        last_day = 31
    else:
        last_day = (
            datetime(year, month + 1, 1) -
            datetime(year, month, 1)
        ).days
    
    # シフトパターンを取得
    patterns = store.shift_patterns
    
    # シフトを生成
    from .shift_generator import generate_shift_results_with_ortools
    results = generate_shift_results_with_ortools(
        store=store,
        employees=employees,
        staffs=staffs,
        requests=shift_requests,
        patterns=patterns,
        holidays=holidays,
        year=year,
        month=month
    )
    
    # 結果を保存
    if results:
        for r in results:
            db.add(r)
        db.commit()
    
    return results