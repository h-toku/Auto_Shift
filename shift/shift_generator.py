from datetime import datetime, timedelta
from ortools.sat.python import cp_model
from .shift_validator import (
    validate_shift_requests,
    validate_shift_patterns,
    validate_staffing_requirements
)
from .shift_optimizer import optimize_required_staff
from .shift_creator import get_day_type
from models import Shiftresult


def generate_shift_results_with_ortools(
    store, employees, staffs, requests, patterns,
    holidays, year, month
):
    """OR-Toolsを使用してシフトを生成する"""
    print("\n=== シフト生成開始 ===")
    print(f"店舗: {store.name}")
    print(f"対象年月: {year}年{month}月")
    print(f"社員数: {len(employees)}名")
    print(f"バイト数: {len(staffs)}名")
    print(f"シフト希望数: {len(requests)}件")
    print(f"休業日数: {len(holidays)}日")
    
    # 1. 入力の検証
    print("\n1. 入力の検証")
    print("シフト希望の検証中...")
    valid_requests = validate_shift_requests(requests, employees + staffs)
    print(f"有効なシフト希望: {len(valid_requests)}件")
    
    print("\nシフトパターンの検証中...")
    valid_patterns = validate_shift_patterns(patterns, store)
    print(f"有効なシフトパターン: {len(valid_patterns)}件")
    
    print("\n必要人数の検証中...")
    validate_staffing_requirements(store, len(employees) + len(staffs))
    
    # 2. モデルの構築
    print("\n2. モデルの構築")
    model = cp_model.CpModel()
    last_day = (datetime(year, month + 1, 1) - timedelta(days=1)).day
    print("制約モデルの初期化完了")
    
    # 3. 社員のシフトを確定
    print("\n3. 社員のシフト確定")
    employee_shifts = []
    results = []
    for e in employees:
        print(f"\n社員 {e.name} のシフト確定:")
        for day in range(1, last_day + 1):
            req = valid_requests.get((e.id, day))
            if not req or req.status in ("X", ""):
                continue
            
            # 社員の勤務時間を決定（希望通り）
            if req.status == "O":
                start_time = store.open_hours
                end_time = store.close_hours
                print(f"  {day}日: 終日勤務 ({start_time}時～{end_time}時)")
            elif req.status == "time":
                start_time = req.start_time
                end_time = req.end_time
                print(f"  {day}日: 時間指定 ({start_time}時～{end_time}時)")
            else:
                continue
            
            # 勤務時間を記録
            for hour in range(start_time, end_time):
                employee_shifts.append((e.id, day, hour))
                results.append(
                    Shiftresult(
                        staff_id=e.id,
                        day=day,
                        start_time=hour,
                        end_time=hour + 1
                    )
                )
    
    print(f"\n社員シフトの総時間数: {len(employee_shifts)}時間")
    
    # 4. バイトスタッフの採用/不採用を決定
    print("\n4. バイトスタッフの採用/不採用決定")
    print("時間帯ごとの必要人数を計算中...")
    required_staff = optimize_required_staff(
        model, store, employees, staffs, holidays,
        year, month, last_day, employee_shifts
    )
    
    # バイトスタッフの採用を決定
    for day in range(1, last_day + 1):
        day_type = get_day_type(year, month, day, holidays)
        skill_req = next(
            (r for r in store.default_skill_requirements 
             if r.day_type == day_type),
            None
        )
        if not skill_req:
            continue
            
        # ピーク時間帯の必要人数を取得
        peak_hour = skill_req.peak_start_hour
        required_count = required_staff.get((day, peak_hour), 0)
        
        # その日の希望者を取得
        available_staff = []
        for s in staffs:
            req = valid_requests.get((s.id, day))
            if req and req.status != "X":
                available_staff.append((s.id, req))
        
        # 必要人数分のスタッフを採用
        selected_staff = []
        for staff_id, req in available_staff[:required_count]:
            selected_staff.append((staff_id, req))
            print(f"  {day}日: スタッフID {staff_id} を採用")
            
            # 採用されたスタッフのシフトを希望通りに登録
            if req.status == "O":
                start_time = store.open_hours
                end_time = store.close_hours
            else:  # "time"
                start_time = req.start_time
                end_time = req.end_time
                
            for hour in range(start_time, end_time):
                results.append(
                    Shiftresult(
                        staff_id=staff_id,
                        day=day,
                        start_time=hour,
                        end_time=hour + 1
                    )
                )
    
    print(f"\n生成されたシフト数: {len(results)}件")
    print("=== シフト生成完了 ===\n")
    return results 