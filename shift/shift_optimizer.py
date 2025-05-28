from typing import Dict, List, Tuple, Set
from datetime import datetime
from ortools.sat.python import cp_model
from models import Staff, Store, ShiftPattern, ShiftRequest
from .shift_validator import get_day_type


def optimize_time_allocation(
    model: cp_model.CpModel,
    staffs: List[Staff],
    patterns: List[ShiftPattern],
    requests: Dict[Tuple[int, int], ShiftRequest],
    store: Store,
    last_day: int
) -> Tuple[Dict, Dict]:
    """時間配分の最適化を行う
    
    Returns:
        x: (staff_id, day, pattern_id) → BoolVar
        y: (staff_id, day, hour) → BoolVar
    """
    print("\n=== 時間配分の最適化 ===")
    
    # 変数定義
    x = {}  # (staff_id, day, pattern_id) → BoolVar
    for s in staffs:
        for day in range(1, last_day + 1):
            for p in patterns:
                x[(s.id, day, p.id)] = model.NewBoolVar(
                    f"x_s{s.id}_d{day}_p{p.id}"
                )

    y = {}  # (staff_id, day, hour) → BoolVar
    for s in staffs:
        for day in range(1, last_day + 1):
            for hour in range(store.open_hours, store.close_hours):
                y[(s.id, day, hour)] = model.NewBoolVar(
                    f"y_s{s.id}_d{day}_h{hour}"
                )

    # 1. 連勤制約
    print("連勤制約の設定中...")
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

    # 2. 時間帯制約
    print("時間帯制約の設定中...")
    for s in staffs:
        for day in range(1, last_day + 1):
            for hour in range(store.open_hours, store.close_hours):
                covering = [
                    p for p in patterns 
                    if p.start_time <= hour < p.end_time
                ]
                if covering:
                    pattern_vars = [x[(s.id, day, p.id)] for p in covering]
                    if pattern_vars:
                        model.AddMaxEquality(
                            y[(s.id, day, hour)],
                            pattern_vars
                        )
                else:
                    model.Add(y[(s.id, day, hour)] == 0)

    # 3. 希望勤務時間帯制約
    print("希望勤務時間帯制約の設定中...")
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

    # 4. 1日1パターン制約
    print("1日1パターン制約の設定中...")
    for s in staffs:
        for day in range(1, last_day + 1):
            pattern_vars = [x[(s.id, day, p.id)] for p in patterns]
            if pattern_vars:
                model.Add(sum(pattern_vars) <= 1)

    return x, y


def optimize_staffing_levels(
    model: cp_model.CpModel,
    x: Dict,
    y: Dict,
    staffs: List[Staff],
    employees: List[Staff],
    store: Store,
    patterns: List[ShiftPattern],
    holidays: Set[datetime.date],
    year: int,
    month: int,
    last_day: int,
    objective_terms: List,
    employee_shifts: List[Tuple[int, int, int]] = None
) -> None:
    """人数制限の最適化を行う"""
    print("\n=== 人数制限の最適化 ===")
    
    if employee_shifts is None:
        employee_shifts = []
    
    for day in range(1, last_day + 1):
        day_type = get_day_type(year, month, day, holidays)
        skill_req = next(
            (r for r in store.default_skill_requirements 
             if r.day_type == day_type),
            None
        )
        if not skill_req:
            print(f"エラー: {day_type}のスキル設定が見つかりません")
            raise ValueError(f"Day type '{day_type}' skill setting not found")

        print(f"\n{day}日 ({day_type}) の制約設定:")
        
        # 社員の勤務時間帯を取得
        employee_work_hours = [
            (staff_id, d, h) for staff_id, d, h in employee_shifts
            if staff_id in [e.id for e in employees] and d == day
        ]

        for hour in range(store.open_hours, store.close_hours):
            # ピーク時間帯の判定
            is_peak = False
            if hour < skill_req.peak_start_hour:
                min_staff = skill_req.open_people
                max_staff = skill_req.open_people
                time_type = "オープン"
            elif hour < skill_req.peak_end_hour:
                min_staff = skill_req.peak_people
                max_staff = skill_req.peak_people
                time_type = "ピーク"
                is_peak = True
            else:
                min_staff = skill_req.close_people
                max_staff = skill_req.close_people
                time_type = "クローズ"

            # 社員の勤務数をカウント
            employee_count = sum(
                1 for (_, d, h) in employee_work_hours if h == hour
            )
            
            # バイトの勤務変数を集計
            staff_vars = [y[(s.id, day, hour)] for s in staffs]
            
            if staff_vars:
                if is_peak:
                    # ピーク時の制約
                    min_peak = max(1, max_staff - 3)
                    max_peak = max_staff + 3
                    
                    total_staff = model.NewIntVar(
                        0, len(staffs),
                        f"total_d{day}_h{hour}"
                    )
                    model.Add(total_staff == sum(staff_vars))
                    
                    total_people = model.NewIntVar(
                        0, len(staffs) + len(employees),
                        f"total_people_d{day}_h{hour}"
                    )
                    model.Add(total_people == total_staff + employee_count)
                    
                    model.Add(total_people >= min_peak)
                    model.Add(total_people <= max_peak)
                    
                    # ペナルティの設定
                    shortage = model.NewIntVar(
                        0, max_staff,
                        f"shortage_d{day}_h{hour}"
                    )
                    excess = model.NewIntVar(
                        0, max_staff,
                        f"excess_d{day}_h{hour}"
                    )
                    
                    diff = model.NewIntVar(
                        -max_staff, max_staff,
                        f"diff_d{day}_h{hour}"
                    )
                    model.Add(diff == total_people - max_staff)
                    
                    diff_neg = model.NewBoolVar(f"diff_neg_d{day}_h{hour}")
                    diff_pos = model.NewBoolVar(f"diff_pos_d{day}_h{hour}")
                    diff_zero = model.NewBoolVar(f"diff_zero_d{day}_h{hour}")
                    
                    model.Add(diff <= -2).OnlyEnforceIf(diff_neg)
                    model.Add(diff >= 2).OnlyEnforceIf(diff_pos)
                    model.Add(diff > -2).OnlyEnforceIf(diff_zero.Not())
                    model.Add(diff < 2).OnlyEnforceIf(diff_zero.Not())
                    model.AddBoolOr([diff_neg, diff_pos, diff_zero])
                    
                    model.Add(shortage >= -diff).OnlyEnforceIf(diff_neg)
                    model.Add(shortage == 0).OnlyEnforceIf(diff_pos)
                    model.Add(shortage == 0).OnlyEnforceIf(diff_zero)
                    
                    model.Add(excess >= diff).OnlyEnforceIf(diff_pos)
                    model.Add(excess == 0).OnlyEnforceIf(diff_neg)
                    model.Add(excess == 0).OnlyEnforceIf(diff_zero)
                    
                    objective_terms.append(shortage * 20)
                    objective_terms.append(excess * 5)
                else:
                    # 非ピーク時の制約
                    min_staff = (
                        max(1, skill_req.open_people - 3)
                        if time_type == "オープン"
                        else max(1, skill_req.close_people - 3)
                    )
                    
                    total_staff = model.NewIntVar(
                        0, len(staffs),
                        f"total_d{day}_h{hour}"
                    )
                    model.Add(total_staff == sum(staff_vars))
                    
                    total_people = model.NewIntVar(
                        0, len(staffs) + len(employees),
                        f"total_people_d{day}_h{hour}"
                    )
                    model.Add(total_people == total_staff + employee_count)
                    
                    model.Add(total_people >= min_staff)


def optimize_required_staff(
    model: cp_model.CpModel,
    store: Store,
    employees: List[Staff],
    staffs: List[Staff],
    holidays: Set[datetime.date],
    year: int,
    month: int,
    last_day: int,
    employee_shifts: List[Tuple[int, int, int]] = None
) -> Dict[Tuple[int, int], int]:
    """各時間帯に必要な人数を最適化する
    
    Returns:
        required_staff: (day, hour) → 必要なバイトの人数
    """
    print("\n=== 必要人数の最適化 ===")
    required_staff = {}
    
    if employee_shifts is None:
        employee_shifts = []
    
    for day in range(1, last_day + 1):
        day_type = get_day_type(year, month, day, holidays)
        skill_req = next(
            (r for r in store.default_skill_requirements 
             if r.day_type == day_type),
            None
        )
        if not skill_req:
            raise ValueError(f"{day_type}のスキル設定が見つかりません")

        print(f"\n{day}日 ({day_type}) の人数最適化:")
        
        # 社員の勤務時間帯を取得
        employee_work_hours = [
            (staff_id, d, h) for staff_id, d, h in employee_shifts
            if staff_id in [e.id for e in employees] and d == day
        ]

        for hour in range(store.open_hours, store.close_hours):
            # 時間帯の判定
            if hour < skill_req.peak_start_hour:
                min_people = skill_req.open_people
                time_type = "オープン"
            elif hour < skill_req.peak_end_hour:
                min_people = skill_req.peak_people
                time_type = "ピーク"
            else:
                min_people = skill_req.close_people
                time_type = "クローズ"

            # 社員の勤務数をカウント
            employee_count = sum(
                1 for (_, d, h) in employee_work_hours if h == hour
            )
            
            # 必要なバイトの人数を計算
            required = max(0, min_people - employee_count)
            required_staff[(day, hour)] = required
            
            print(
                f"  {hour}時 ({time_type}): 必要人数={min_people}人, "
                f"社員={employee_count}人, バイト必要={required}人"
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
                    f"x_s{s.id}_d{day}_p{p.id}"
                )

    y = {}  # (staff_id, day, hour) → BoolVar
    for s in staffs:
        for day in range(1, last_day + 1):
            for hour in range(store.open_hours, store.close_hours):
                y[(s.id, day, hour)] = model.NewBoolVar(
                    f"y_s{s.id}_d{day}_h{hour}"
                )

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
                covering = [
                    p for p in patterns 
                    if p.start_time <= hour < p.end_time
                ]
                if covering:
                    pattern_vars = [x[(s.id, day, p.id)] for p in covering]
                    if pattern_vars:
                        model.AddMaxEquality(
                            y[(s.id, day, hour)],
                            pattern_vars
                        )
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
                            f"x_s{staff_id}_d{day}_p{p.id}"
                        )
                
                if (staff_id, day, hour) not in y:
                    y[(staff_id, day, hour)] = model.NewBoolVar(
                        f"y_s{staff_id}_d{day}_h{hour}"
                    )
    
    # 1. 時間帯制約
    print("時間帯制約を設定中...")
    for day in range(1, last_day + 1):
        for hour in range(store.open_hours, store.close_hours):
            staff_ids = daily_staff.get((day, hour), [])
            for staff_id in staff_ids:
                if staff_id not in [s.id for s in staffs]:
                    continue
                
                covering = [
                    p for p in patterns 
                    if p.start_time <= hour < p.end_time
                ]
                if covering:
                    pattern_vars = [x[(staff_id, day, p.id)] for p in covering]
                    if pattern_vars:
                        model.AddMaxEquality(
                            y[(staff_id, day, hour)],
                            pattern_vars
                        )
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