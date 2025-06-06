from datetime import datetime, timedelta
from ortools.sat.python import cp_model
from .shift_validator import (
    validate_shift_requests,
    validate_shift_patterns,
    validate_staffing_requirements
)
from .shift_optimizer import optimize_required_staff
from .shift_creator import get_day_type
from models import Shiftresult, Shift
from collections import defaultdict
import math  # mathモジュールをインポート


def generate_shift_results_with_ortools(
    store, employees, staffs, requests, patterns,
    holidays, year, month, db=None
):
    """OR-Toolsを使用してシフトを生成する"""
    print("\n=== シフト生成開始 ===")
    print(f"店舗: {store.name}")
    print(f"対象年月: {year}年{month}月")
    print(f"営業時間: {store.open_hours}時～{store.close_hours}時")
    print(f"社員数: {len(employees)}名")
    print(f"バイトスタッフ数: {len(staffs)}名 "
          f"(内訳: バイト {sum(1 for s in staffs if s.employment_type == 'バイト')}名, "
          f"未成年バイト {sum(1 for s in staffs if s.employment_type == '未成年バイト')}名)")
    print(f"シフト希望数: {len(requests)}件")
    print(f"休業日数: {len(holidays)}日")
    
    if db:
        print("\n既存のシフトデータを削除中...")
        # 既存のシフト結果を削除
        deleted_results = db.query(Shiftresult).filter(
            Shiftresult.year == year,
            Shiftresult.month == month,
            Shiftresult.staff_id.in_([s.id for s in employees + staffs])
        ).delete(synchronize_session=False)
        print(f"削除されたシフト結果: {deleted_results}件")
        
        # 既存のシフトを削除
        deleted_shifts = db.query(Shift).filter(
            Shift.year == year,
            Shift.month == month,
            Shift.staff_id.in_([s.id for s in employees + staffs])
        ).delete(synchronize_session=False)
        print(f"削除されたシフト: {deleted_shifts}件")
        db.flush()
    
    # 1. 入力の検証
    print("\n1. 入力の検証")
    print("シフト希望の検証中...")
    valid_requests = validate_shift_requests(
        requests, employees + staffs, store
    )
    print(f"有効なシフト希望: {len(valid_requests)}件")
    
    print("\nシフトパターンの検証中...")
    valid_patterns = validate_shift_patterns(patterns, store)
    print(f"有効なシフトパターン: {len(valid_patterns)}件")
    
    print("\n必要人数の検証中...")
    last_day = (datetime(year, month + 1, 1) - timedelta(days=1)).day
    validate_staffing_requirements(
        store=store,
        employees=employees,
        staffs=staffs,
        holidays=holidays,
        year=year,
        month=month,
        last_day=last_day
    )
    
    # 2. モデルの構築
    print("\n2. モデルの構築")
    model = cp_model.CpModel()
    print("制約モデルの初期化完了")
    
    # 3. 社員のシフトを確定
    print("\n3. 社員のシフト確定")
    employee_shifts = []
    results = []
    
    # 社員のシフトを希望通りに設定
    for employee in employees:
        print(f"\n社員 {employee.name} のシフト確定:")
        for day in range(1, last_day + 1):
            req = valid_requests.get((employee.id, day))
            if not req:
                continue
                
            if req.status == "O":  # 終日勤務の場合
                # 店舗の営業時間を使用
                start_time = store.open_hours  # 店舗の営業開始時間（5時）
                end_time = store.close_hours   # 店舗の営業終了時間（12時）
                print(f"  {day}日: 終日勤務 ({start_time}時～{end_time}時)")
                
                # 勤務時間を記録（開始時間と終了時間のみ）
                employee_shifts.append((employee.id, day, start_time))  # ピーク時間の計算用
                results.append(
                    Shiftresult(
                        staff_id=employee.id,
                        year=year,
                        month=month,
                        day=day,
                        start_time=start_time,
                        end_time=end_time
                    )
                )
            elif req.status == "time":  # 時間指定の場合
                start_time = req.start_time
                end_time = req.end_time
                print(f"  {day}日: 時間指定 ({start_time}時～{end_time}時)")
                
                # 勤務時間を記録（開始時間と終了時間のみ）
                employee_shifts.append((employee.id, day, start_time))  # ピーク時間の計算用
                results.append(
                    Shiftresult(
                        staff_id=employee.id,
                        year=year,
                        month=month,
                        day=day,
                        start_time=start_time,
                        end_time=end_time
                    )
                )
    
    print(f"\n社員シフトの総時間数: {len(employee_shifts)}時間")
    
    # 4. バイトスタッフの採用/不採用を決定
    print("\n4. バイトスタッフの採用/不採用決定")
    print("時間帯ごとの必要人数を計算中...")
    required_staff, selected_staff_by_day = optimize_required_staff(
        model, store, employees, staffs, holidays,
        year, month, last_day, employee_shifts, valid_requests
    )
    
    # バイトスタッフのシフト時間を調整
    print("\n5. バイトスタッフのシフト時間調整")
    adjusted_shifts, rejection_times = adjust_staff_shifts(
        store, selected_staff_by_day, valid_requests,
        employee_shifts, year, month, last_day, holidays, staffs
    )
    
    # 結果を結合（社員のシフト + 調整後のバイトスタッフのシフト）
    results.extend(adjusted_shifts)
    
    print(f"\n生成されたシフト数: {len(results)}件")
    
    if db:
        print("\nシフトデータをDBに保存中...")
        try:
            # シフトを保存
            for result in results:
                # 新しいシフトを作成
                new_shift = Shift(
                    staff_id=result.staff_id,
                    year=year,
                    month=month,
                    date=result.day,
                    start_time=result.start_time,
                    end_time=result.end_time
                )
                db.add(new_shift)
                db.flush()  # IDを取得するためにflush

                # シフト結果を更新
                result.shift_id = new_shift.id
                db.add(result)
            
            db.commit()
            print("シフトデータの保存が完了しました")
        except Exception as e:
            db.rollback()
            print(f"シフトデータの保存に失敗しました: {str(e)}")
            raise
    
    print("=== シフト生成完了 ===\n")
    return results


def calculate_rejection_targets(
    store, staffs, valid_requests, year, month, last_day, holidays,
    employee_shifts
):
    """不採用率の目安を計算する
    
    Args:
        store: 店舗情報
        staffs: バイトスタッフリスト
        valid_requests: 有効なシフト希望
        year: 年
        month: 月
        last_day: 月末日
        holidays: 休業日リスト
        employee_shifts: 社員のシフトリスト (e_id, day, hour)
    
    Returns:
        rejection_targets: {staff_id: 目安不採用日数}
        day_request_counts: {day: 希望者数}
    """
    print("\n=== 不採用率の目安計算 ===")
    
    # 各スタッフの希望日数を集計
    staff_request_counts = defaultdict(int)  # staff_id → 希望日数
    day_request_counts = defaultdict(int)    # day → 希望者数
    employee_work_days = set()               # 社員の勤務日集合
    
    # 社員の勤務日を記録
    for e_id, day, _ in employee_shifts:
        employee_work_days.add(day)
    
    # バイトの希望日数を集計
    for day in range(1, last_day + 1):
        day_type = get_day_type(year, month, day, holidays)
        skill_req = next(
            (r for r in store.default_skill_requirements 
             if r.day_type == day_type),
            None
        )
        if not skill_req:
            continue
            
        # その日の社員の勤務数をカウント
        employee_count = sum(
            1 for e_id, d, h in employee_shifts
            if d == day and h == skill_req.peak_start_hour
        )
        
        # バイトの希望者をカウント
        for staff in staffs:
            req = valid_requests.get((staff.id, day))
            if req and req.status != "X":
                staff_request_counts[staff.id] += 1
                day_request_counts[day] += 1
    
    # 店舗の必要人数と社員の勤務日数を集計
    total_required = 0
    total_employee_days = 0
    for day in range(1, last_day + 1):
        day_type = get_day_type(year, month, day, holidays)
        skill_req = next(
            (r for r in store.default_skill_requirements 
             if r.day_type == day_type),
            None
        )
        if skill_req:
            total_required += skill_req.peak_people
            # その日の社員の勤務数をカウント
            employee_count = sum(
                1 for e_id, d, h in employee_shifts
                if d == day and h == skill_req.peak_start_hour
            )
            total_employee_days += employee_count
    
    # バイトの総希望日数を計算
    total_staff_requests = sum(staff_request_counts.values())
    
    # バイトの余剰希望日数を計算
    # バイト余剰希望数 = バイト総希望数 - (店舗必要数 - 社員勤務日数)
    excess_staff_requests = total_staff_requests - (total_required - total_employee_days)
    
    print(f"店舗必要人数: {total_required}人")
    print(f"社員勤務日数: {total_employee_days}日")
    print(f"バイト総希望数: {total_staff_requests}日")
    print(f"バイト余剰希望数: {excess_staff_requests}日")
    
    # 各スタッフの不採用目安を計算
    rejection_targets = {}
    
    # スタッフを希望日数でソート
    sorted_staff = sorted(
        [(staff.id, staff_request_counts[staff.id]) for staff in staffs],
        key=lambda x: x[1],
        reverse=True  # 希望日数の多い順
    )
    
    # スタッフを2グループに分割
    mid_point = len(sorted_staff) // 2
    high_request_staff = sorted_staff[:mid_point]  # 希望日数の多いグループ
    low_request_staff = sorted_staff[mid_point:]   # 希望日数の少ないグループ
    
    print("\nスタッフの希望日数による分類:")
    print("希望日数の多いグループ:")
    for staff_id, request_count in high_request_staff:
        staff = next(s for s in staffs if s.id == staff_id)
        print(f"  スタッフID {staff_id} ({staff.employment_type}): "
              f"{request_count}日")
    print("希望日数の少ないグループ:")
    for staff_id, request_count in low_request_staff:
        staff = next(s for s in staffs if s.id == staff_id)
        print(f"  スタッフID {staff_id} ({staff.employment_type}): "
              f"{request_count}日")
    
    if total_staff_requests > 0:
        # 各スタッフの不採用目安を計算
        for staff_id, request_count in sorted_staff:
            # 各スタッフ希望率 = 各スタッフ希望数 / バイト総希望数
            request_ratio = request_count / total_staff_requests
            
            # 希望日数の多いグループは切り上げ、少ないグループは切り下げ
            if (staff_id, request_count) in high_request_staff:
                # 希望日数の多いグループは、不採用率が0.08以上の場合のみ不採用
                target_rejections = math.ceil(excess_staff_requests * request_ratio)
                if request_ratio >= 0.08 and target_rejections < 1:
                    target_rejections = 1
                print(f"スタッフID {staff_id} (希望日数 {request_count}日): "
                      f"希望率 {request_ratio:.1%}, "
                      f"目安不採用日数 {target_rejections}日 (切り上げ)")
            else:
                # 希望日数の少ないグループは、最低でも1日は不採用
                target_rejections = max(1, math.floor(excess_staff_requests * request_ratio))
                print(f"スタッフID {staff_id} (希望日数 {request_count}日): "
                      f"希望率 {request_ratio:.1%}, "
                      f"目安不採用日数 {target_rejections}日 (切り下げ)")
            
            rejection_targets[staff_id] = target_rejections
    
    return rejection_targets, day_request_counts

def calculate_peak_coverage(req, store, skill_req):
    """ピーク時間帯のカバー率を計算する
    
    Args:
        req: シフト希望
        store: 店舗情報
        skill_req: スキル要件
    
    Returns:
        coverage: ピーク時間帯のカバー率（0.0-1.0）
    """
    if req.status == "O":
        # 終日勤務の場合は完全カバー
        return 1.0
    
    if req.status != "time":
        return 0.0
    
    # ピーク時間帯の長さ
    peak_duration = skill_req.peak_end_hour - skill_req.peak_start_hour
    
    # 希望時間とピーク時間の重なりを計算
    overlap_start = max(req.start_time, skill_req.peak_start_hour)
    overlap_end = min(req.end_time, skill_req.peak_end_hour)
    overlap_duration = max(0, overlap_end - overlap_start)
    
    # カバー率を計算
    return overlap_duration / peak_duration if peak_duration > 0 else 0.0

def optimize_required_staff(
    model, store, employees, staffs, holidays,
    year, month, last_day, employee_shifts, valid_requests
):
    """必要人数を最適化する
    
    Args:
        model: OR-Toolsのモデル
        store: 店舗情報
        employees: 社員リスト（employment_type="社員"）
        staffs: バイトスタッフリスト（employment_type="バイト"または"未成年バイト"）
        holidays: 休業日リスト
        year: 年
        month: 月
        last_day: 月末日
        employee_shifts: 社員のシフトリスト (e_id, day, hour)
        valid_requests: 有効なシフト希望
    
    Returns:
        required_staff: (day, hour) → 必要人数
        selected_staff_by_day: day → 採用されたスタッフIDのリスト
    """
    print("\n=== 必要人数の最適化 ===")
    print(f"社員数: {len(employees)}名")
    
    # スタッフの分類を確認
    regular_staff = [s for s in staffs if s.employment_type == 'バイト']
    minor_staff = [s for s in staffs if s.employment_type == '未成年バイト']
    print(f"バイトスタッフ数: {len(staffs)}名 "
          f"(内訳: バイト {len(regular_staff)}名, "
          f"未成年バイト {len(minor_staff)}名)")
    
    # スタッフの詳細情報を表示
    print("\nスタッフの詳細:")
    for staff in staffs:
        print(f"スタッフID {staff.id}: {staff.name} ({staff.employment_type})")
    
    required_staff = {}  # (day, hour) → 必要人数
    selected_staff_by_day = defaultdict(list)  # day → 採用されたスタッフIDのリスト
    staff_work_days = defaultdict(set)  # staff_id → 勤務日集合
    staff_rejections = defaultdict(int)  # staff_id → 不採用回数
    total_requests = defaultdict(int)  # staff_id → 希望回数
    
    # 不採用目安日数を計算
    rejection_targets, _ = calculate_rejection_targets(
        store, staffs, valid_requests, year, month,
        last_day, holidays, employee_shifts
    )
    
    # 日付をソート（土日祝日を優先）
    sorted_days = []
    for day in range(1, last_day + 1):
        current_date = datetime(year, month, day).date()
        is_holiday = current_date in holidays
        is_weekend = current_date.weekday() >= 5
        priority = 2 if is_holiday else (1 if is_weekend else 0)
        sorted_days.append((priority, day))
    sorted_days.sort(reverse=True)
    sorted_days = [day for _, day in sorted_days]
    
    for day in sorted_days:
        day_type = get_day_type(year, month, day, holidays)
        skill_req = next(
            (r for r in store.default_skill_requirements 
             if r.day_type == day_type),
            None
        )
        if not skill_req:
            continue
        
        # その日の社員の勤務数をカウント
        employee_count = sum(
            1 for e_id, d, h in employee_shifts
            if d == day and h == skill_req.peak_start_hour
        )
        
        # バイトの必要人数を計算（社員数を引く）
        required_count = max(0, skill_req.peak_people - employee_count)
        print(f"\n{day}日: 必要人数 {skill_req.peak_people}人 "
              f"(社員 {employee_count}人, バイト必要 {required_count}人)")
        
        # その日の希望者を取得
        available_staff = []
        for s in staffs:
            req = valid_requests.get((s.id, day))
            if not req or req.status == "X":
                continue
            
            # 不採用目安との誤差を計算
            target_rejections = rejection_targets.get(s.id, 0)
            current_rejections = staff_rejections[s.id]
            rejection_error = current_rejections - target_rejections  # 符号付きの誤差
            
            # 誤差が-1～+2の範囲外の場合、採用優先度を下げる
            if rejection_error < -1:  # 不採用が少なすぎる
                rejection_error = 100  # 大きな値で採用優先度を下げる
            elif rejection_error > 2:  # 不採用が多すぎる
                rejection_error = 100  # 大きな値で採用優先度を下げる
            else:
                rejection_error = abs(rejection_error)  # 範囲内の場合は絶対値を使用
            
            # ピーク時間帯の希望を確認
            peak_coverage = 0.0
            if req.status == "O":
                peak_coverage = 1.0
            elif req.status == "time":
                if (req.start_time <= skill_req.peak_start_hour and 
                    req.end_time >= skill_req.peak_end_hour):
                    peak_coverage = 1.0
                elif (req.start_time <= skill_req.peak_start_hour or 
                      req.end_time >= skill_req.peak_end_hour):
                    peak_coverage = 0.5
            
            # 連勤日数を計算
            consecutive_days = 0
            for d in range(day - 1, 0, -1):
                if d in staff_work_days[s.id]:
                    consecutive_days += 1
                else:
                    break
            
            # 連勤制約違反を計算
            consecutive_violation = 0
            if consecutive_days >= 5:  # 5日連勤は制約違反
                consecutive_violation = 1
            
            available_staff.append({
                'id': s.id,
                'employment_type': s.employment_type,
                'rejection_error': rejection_error,  # 不採用目安との誤差
                'peak_coverage': peak_coverage,
                'consecutive_days': consecutive_days,
                'consecutive_violation': consecutive_violation,
                'current_rejections': current_rejections,  # 現在の不採用回数
                'target_rejections': target_rejections  # 目標不採用回数
            })
            total_requests[s.id] += 1
        
        # スコアに基づいてソート（不採用目安との誤差を最優先）
        available_staff.sort(
            key=lambda x: (
                x['rejection_error'],  # 不採用目安との誤差（小さい順）
                -x['peak_coverage'],  # ピークカバー率（高い順）
                -x['consecutive_days'],  # 連勤日数（少ない順）
                x['consecutive_violation']  # 連勤違反（少ない順）
            )
        )
        
        # 必要人数分のスタッフを採用
        for staff_info in available_staff[:required_count]:
            staff_id = staff_info['id']
            selected_staff_by_day[day].append(staff_id)
            staff_work_days[staff_id].add(day)
            print(f"  {day}日: スタッフID {staff_id} "
                  f"({staff_info['employment_type']}) を採用 "
                  f"(不採用目安: {staff_info['target_rejections']}日, "
                  f"現在: {staff_info['current_rejections']}日, "
                  f"誤差: {staff_info['current_rejections'] - staff_info['target_rejections']}日, "
                  f"ピークカバー率: {staff_info['peak_coverage']:.2f}, "
                  f"連勤日数: {staff_info['consecutive_days']}, "
                  f"連勤違反: {staff_info['consecutive_violation']}日)")
        
        # 不採用者を記録
        for staff_info in available_staff[required_count:]:
            staff_id = staff_info['id']
            staff_rejections[staff_id] += 1
            print(f"  {day}日: スタッフID {staff_id} "
                  f"({staff_info['employment_type']}) を不採用 "
                  f"(不採用目安: {staff_info['target_rejections']}日, "
                  f"現在: {staff_info['current_rejections'] + 1}日, "
                  f"誤差: {staff_info['current_rejections'] + 1 - staff_info['target_rejections']}日, "
                  f"ピークカバー率: {staff_info['peak_coverage']:.2f}, "
                  f"連勤日数: {staff_info['consecutive_days']}, "
                  f"連勤違反: {staff_info['consecutive_violation']}日)")
        
        # 時間帯ごとの必要人数を設定
        for hour in range(store.open_hours, store.close_hours):
            if hour < skill_req.peak_start_hour:
                required = skill_req.open_people
            elif hour < skill_req.peak_end_hour:
                required = skill_req.peak_people
            else:
                required = skill_req.close_people
            
            # 社員の勤務を考慮
            employee_count = sum(
                1 for e_id, d, h in employee_shifts
                if d == day and h == hour
            )
            required = max(0, required - employee_count)
            
            required_staff[(day, hour)] = required
    
    # 最終的な不採用率と目安との誤差を表示
    print("\n=== 不採用率の集計 ===")
    for staff in staffs:
        if total_requests[staff.id] > 0:
            target = rejection_targets.get(staff.id, 0)
            actual = staff_rejections[staff.id]
            error = abs(actual - target)
            print(f"スタッフID {staff.id} ({staff.employment_type}): "
                  f"希望日数 {total_requests[staff.id]}日, "
                  f"不採用率 {actual / total_requests[staff.id]:.2f}, "
                  f"不採用目安 {target}日, "
                  f"実際 {actual}日, "
                  f"誤差 {error}日")
    
    return required_staff, selected_staff_by_day 

def adjust_staff_shifts(
    store, selected_staff_by_day, valid_requests, employee_shifts,
    year, month, last_day, holidays, staffs
):
    """バイトスタッフのシフト時間を調整する
    
    Args:
        store: 店舗情報
        selected_staff_by_day: {day: [staff_id]} 採用されたスタッフ
        valid_requests: 有効なシフト希望
        employee_shifts: 社員のシフトリスト
        year: 年
        month: 月
        last_day: 月末日
        holidays: 休業日リスト
        staffs: スタッフリスト（未成年バイトの判定用）
    
    Returns:
        adjusted_shifts: 調整後のシフトリスト
        rejection_times: {staff_id: (早出時間, 早退時間)} 不採用時間
    """
    print("\n=== バイトスタッフのシフト時間調整 ===")
    adjusted_shifts = []
    rejection_times = defaultdict(lambda: [0, 0])  # (早出時間, 早退時間)
    
    # スタッフIDから未成年バイトかどうかを判定する辞書を作成
    is_minor = {staff.id: staff.employment_type == '未成年バイト' 
                for staff in staffs}
    
    for day in range(1, last_day + 1):
        staff_list = selected_staff_by_day.get(day, [])
        if not staff_list:
            continue
        
        # その日の日種を取得
        day_type = get_day_type(year, month, day, holidays)
        skill_req = next(
            (r for r in store.default_skill_requirements 
             if r.day_type == day_type),
            None
        )
        if not skill_req:
            continue
            
        # その日の社員の勤務を確認
        employee_open = sum(
            1 for e_id, d, h in employee_shifts
            if d == day and h == store.open_hours
        )
        employee_close = sum(
            1 for e_id, d, h in employee_shifts
            if d == day and h == store.close_hours - 1
        )
        
        # バイトの必要人数を計算
        open_staff_needed = max(0, skill_req.open_people - employee_open)
        close_staff_needed = max(0, skill_req.close_people - employee_close)
        
        print(f"\n{day}日 ({day_type}):")
        print(f"オープン必要人数: {open_staff_needed}人 "
              f"(社員 {employee_open}人, 必要 {skill_req.open_people}人)")
        print(f"クローズ必要人数: {close_staff_needed}人 "
              f"(社員 {employee_close}人, 必要 {skill_req.close_people}人)")
        
        # スタッフを時間帯ごとに分類
        open_staff = []  # オープン時間帯のスタッフ
        close_staff = []  # クローズ時間帯のスタッフ
        middle_staff = []  # 中間時間帯のスタッフ
        
        for staff_id in staff_list:
            req = valid_requests.get((staff_id, day))
            if not req or req.status == "X":
                continue
                
            if req.status == "O":
                # 終日勤務の場合は希望時間を店舗の営業時間に設定
                req_start = store.open_hours
                req_end = store.close_hours
            else:  # time
                req_start = req.start_time
                req_end = req.end_time
            
            # 未成年バイトの場合は終了時間を10時までに制限
            if is_minor[staff_id]:
                req_end = min(req_end, 10)
            
            staff_info = {
                'id': staff_id,
                'is_minor': is_minor[staff_id],
                'req_start': req_start,
                'req_end': req_end,
                'rejection_time': [0, 0]  # [早出時間, 早退時間]
            }
            
            # 時間帯ごとに分類（オープンとクローズを優先）
            if req_start <= store.open_hours + 1:
                open_staff.append(staff_info)
            elif req_end >= store.close_hours - 1 and not is_minor[staff_id]:
                close_staff.append(staff_info)
            else:
                middle_staff.append(staff_info)
        
        # オープン時間帯の調整（最優先）
        open_staff.sort(
            key=lambda x: (
                x['req_start'] == store.open_hours,  # オープン時間開始を優先
                -x['req_end']  # 終了時間が遅い順
            ),
            reverse=True
        )
        
        for staff_info in open_staff[:open_staff_needed]:
            # オープン時間帯のシフトを設定
            if staff_info['req_end'] >= store.open_hours + 4:
                # 4時間以上確保できる場合
                staff_info['start_time'] = store.open_hours
                staff_info['end_time'] = min(
                    staff_info['req_end'],
                    staff_info['start_time'] + 5
                )
            else:
                # 4時間確保できない場合は、希望時間内で最長のシフトを設定
                staff_info['start_time'] = staff_info['req_start']
                staff_info['end_time'] = staff_info['req_end']
            
            # 不採用時間を記録
            if staff_info['end_time'] < staff_info['req_end']:
                staff_info['rejection_time'][1] = (
                    staff_info['req_end'] - staff_info['end_time']
                )
        
        # クローズ時間帯の調整（最優先）
        close_staff.sort(
            key=lambda x: (
                x['req_end'] == store.close_hours,  # クローズ時間終了を優先
                x['req_start']  # 開始時間が早い順
            ),
            reverse=True
        )
        
        for staff_info in close_staff[:close_staff_needed]:
            # クローズ時間帯のシフトを設定
            if staff_info['req_end'] - staff_info['req_start'] >= 4:
                # 4時間以上確保できる場合
                staff_info['end_time'] = store.close_hours
                staff_info['start_time'] = max(
                    staff_info['req_start'],
                    staff_info['end_time'] - 5
                )
            else:
                # 4時間確保できない場合は、希望時間内で最長のシフトを設定
                staff_info['start_time'] = staff_info['req_start']
                staff_info['end_time'] = staff_info['req_end']
            
            # 不採用時間を記録
            if staff_info['start_time'] > staff_info['req_start']:
                staff_info['rejection_time'][0] = (
                    staff_info['start_time'] - staff_info['req_start']
                )
        
        # 中間時間帯の調整
        remaining_staff = (
            open_staff[open_staff_needed:] +
            close_staff[close_staff_needed:] +
            middle_staff
        )
        
        for staff_info in remaining_staff:
            # 希望時間内で最長のシフトを設定
            available_hours = staff_info['req_end'] - staff_info['req_start']
            if available_hours >= 5:
                # 5時間以上確保できる場合は中央に配置
                center = (staff_info['req_start'] + staff_info['req_end']) // 2
                staff_info['start_time'] = max(
                    staff_info['req_start'],
                    center - 2
                )
                staff_info['end_time'] = min(
                    staff_info['req_end'],
                    staff_info['start_time'] + 5
                )
            elif available_hours >= 4:
                # 4時間以上確保できる場合は希望時間をそのまま使用
                staff_info['start_time'] = staff_info['req_start']
                staff_info['end_time'] = staff_info['req_end']
            else:
                # 4時間未満の場合は希望時間をそのまま使用
                staff_info['start_time'] = staff_info['req_start']
                staff_info['end_time'] = staff_info['req_end']
            
            # 未成年バイトの場合は終了時間を10時までに制限
            if staff_info['is_minor']:
                staff_info['end_time'] = min(staff_info['end_time'], 10)
                # 4時間確保できない場合は開始時間を調整
                if staff_info['end_time'] - staff_info['start_time'] < 4:
                    staff_info['start_time'] = staff_info['end_time'] - 4
        
        # シフトを記録
        for staff_info in open_staff + close_staff + remaining_staff:
            if 'start_time' not in staff_info:
                continue
                
            adjusted_shifts.append(
                Shiftresult(
                    staff_id=staff_info['id'],
                    year=year,
                    month=month,
                    day=day,
                    start_time=staff_info['start_time'],
                    end_time=staff_info['end_time']
                )
            )
            
            # 不採用時間を集計
            staff_id = staff_info['id']
            rejection_times[staff_id][0] += staff_info['rejection_time'][0]
            rejection_times[staff_id][1] += staff_info['rejection_time'][1]
            
            print(f"  スタッフID {staff_id} "
                  f"({'未成年' if staff_info['is_minor'] else '一般'}): "
                  f"{staff_info['start_time']}時～{staff_info['end_time']}時 "
                  f"(希望: {staff_info['req_start']}時～{staff_info['req_end']}時, "
                  f"不採用: 早出{staff_info['rejection_time'][0]}時間, "
                  f"早退{staff_info['rejection_time'][1]}時間)")
    
    # 不採用時間の均等化
    total_rejection = sum(sum(times) for times in rejection_times.values())
    if total_rejection > 0 and len(rejection_times) > 0:
        avg_rejection = total_rejection / len(rejection_times)
        print(f"\n不採用時間の均等化:")
        print(f"総不採用時間: {total_rejection}時間")
        print(f"平均不採用時間: {avg_rejection:.1f}時間/人")
        
        for staff_id, times in rejection_times.items():
            print(f"  スタッフID {staff_id}: "
                  f"早出{times[0]}時間, 早退{times[1]}時間 "
                  f"(合計: {sum(times)}時間)")
    
    return adjusted_shifts, rejection_times 