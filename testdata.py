from sqlalchemy.orm import Session
from models import Store, Staff, StoreDefaultSkillRequirement, StoreSkillOverride, ShiftRequest
from database import SessionLocal  # 例：自作の DB セッション
from datetime import date

# DBセッション生成
db: Session = SessionLocal()

# 1. Stores
stores = [
    Store(id=1, store_name='渋谷店', store_location='東京都渋谷区'),
    Store(id=2, store_name='梅田店', store_location='大阪府大阪市'),
]
db.add_all(stores)

# 2. Staffs
staffs = [
    Staff(id=1, name='田中 太郎', store_id=1, employment_type='社員', skills='5,4,3,2,1', login_code='tanaka001', password='pass123'),
    Staff(id=2, name='山田 花子', store_id=1, employment_type='バイト', skills='3,3,3,3,3', login_code='yamada002', password='pass456'),
    Staff(id=3, name='佐藤 次郎', store_id=2, employment_type='バイト', skills='1,2,3,4,5', login_code='sato003', password='pass789'),
]
db.add_all(staffs)

# 3. StoreDefaultSkillRequirements
requirements = [
    StoreDefaultSkillRequirement(store_id=1, day_type='平日', skill_1=2, skill_2=2, skill_3=2, skill_4=2, skill_5=2),
    StoreDefaultSkillRequirement(store_id=1, day_type='土曜', skill_1=3, skill_2=3, skill_3=3, skill_4=3, skill_5=3),
    StoreDefaultSkillRequirement(store_id=1, day_type='日曜', skill_1=4, skill_2=4, skill_3=4, skill_4=4, skill_5=4),
    StoreDefaultSkillRequirement(store_id=2, day_type='平日', skill_1=1, skill_2=1, skill_3=1, skill_4=1, skill_5=1),
    StoreDefaultSkillRequirement(store_id=2, day_type='金曜', skill_1=2, skill_2=2, skill_3=2, skill_4=2, skill_5=2),
]
db.add_all(requirements)

# 4. StoreSkillOverrides
overrides = [
    StoreSkillOverride(store_id=1, override_date=date(2025, 5, 15), skill_1_override=5, skill_2_override=5, skill_3_override=5, skill_4_override=5, skill_5_override=5),
    StoreSkillOverride(store_id=2, override_date=date(2025, 5, 16), skill_1_override=2, skill_2_override=3, skill_3_override=4, skill_4_override=5, skill_5_override=1),
]
db.add_all(overrides)

# 5. ShiftRequests
requests = [
    ShiftRequest(id=1, staff_id=1, request_date=date(2025, 6, 1), start_time=10, end_time=14, status='approved'),
    ShiftRequest(id=2, staff_id=2, request_date=date(2025, 6, 1), start_time=12, end_time=18, status='pending'),
    ShiftRequest(id=3, staff_id=3, request_date=date(2025, 6, 2), start_time=9, end_time=15, status='rejected'),
]
db.add_all(requests)

# コミット
db.commit()
print("✅ テストデータを挿入しました。")
