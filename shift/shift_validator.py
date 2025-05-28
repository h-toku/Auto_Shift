from typing import Dict, List, Tuple, Set
from datetime import datetime, timedelta
from models import Staff, Store, ShiftRequest, ShiftPattern


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
            print(
                f"警告: 存在しないスタッフIDの希望をスキップ: "
                f"staff_id={req.staff_id}"
            )
            continue
        
        if req.status == "time":
            # 時間指定の検証
            if req.start_time >= req.end_time:
                print(
                    f"警告: 無効な時間指定をスキップ: "
                    f"staff_id={req.staff_id}, day={req.day}, "
                    f"start={req.start_time}, end={req.end_time}"
                )
                continue
            
            if (req.start_time < store.open_hours or 
                    req.end_time > store.close_hours):
                print(
                    f"警告: 営業時間外の希望をスキップ: "
                    f"staff_id={req.staff_id}, day={req.day}, "
                    f"start={req.start_time}, end={req.end_time}"
                )
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
            print(
                f"警告: 無効な時間のパターンをスキップ: "
                f"pattern_id={p.id}, start={p.start_time}, "
                f"end={p.end_time}"
            )
            continue
        
        # 営業時間内の検証
        if (p.start_time < store.open_hours or 
                p.end_time > store.close_hours):
            print(
                f"警告: 営業時間外のパターンをスキップ: "
                f"pattern_id={p.id}, start={p.start_time}, "
                f"end={p.end_time}"
            )
            continue
        
        valid_patterns.append(p)
    
    print(f"有効なシフトパターン: {len(valid_patterns)}件")
    return valid_patterns


def validate_staffing_requirements(
    store: Store,
    employees: List[Staff],
    staffs: List[Staff],
    holidays: Set[datetime.date],
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
    print(
        f"総スタッフ数: {total_staff}人 "
        f"(社員: {len(employees)}人, バイト: {len(staffs)}人)"
    )
    
    for day in range(1, last_day + 1):
        day_type = get_day_type(year, month, day, holidays)
        skill_req = next(
            (r for r in store.default_skill_requirements 
             if r.day_type == day_type),
            None
        )
        if not skill_req:
            raise ValueError(f"{day_type}のスキル設定が見つかりません")
        
        # ピーク時の必要人数チェック
        if skill_req.peak_people > total_staff:
            print(
                f"警告: {day}日({day_type})のピーク時必要人数"
                f"({skill_req.peak_people}人)が総スタッフ数"
                f"({total_staff}人)を超えています"
            )
        
        # オープン時の必要人数チェック
        if skill_req.open_people > total_staff:
            print(
                f"警告: {day}日({day_type})のオープン時必要人数"
                f"({skill_req.open_people}人)が総スタッフ数"
                f"({total_staff}人)を超えています"
            )
        
        # クローズ時の必要人数チェック
        if skill_req.close_people > total_staff:
            print(
                f"警告: {day}日({day_type})のクローズ時必要人数"
                f"({skill_req.close_people}人)が総スタッフ数"
                f"({total_staff}人)を超えています"
            )


def get_day_type(
    year: int,
    month: int,
    day: int,
    holidays: Set[datetime.date]
) -> str:
    """日付から曜日区分を取得する
    
    Args:
        year: 年
        month: 月
        day: 日
        holidays: 祝日セット
    
    Returns:
        day_type: 曜日区分 ("平日", "金曜日", "土曜日", "日曜日")
    """
    date = datetime(year, month, day).date()
    weekday = date.weekday()
    next_day = date + timedelta(days=1)
    prev_day = date - timedelta(days=1)

    if date in holidays:
        if (prev_day.weekday() in [0, 1, 2, 3] or 
                prev_day.weekday() == 4):  # 平日 or 金曜
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