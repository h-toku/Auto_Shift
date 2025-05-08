from sqlalchemy.orm import Session
from models import Store, Staff, StoreDefaultSkillRequirement, StoreSkillOverride, ShiftRequest
from database import SessionLocal  # 例：自作の DB セッション
from datetime import date, time

# DBセッション生成
db: Session = SessionLocal()

# 1. Stores
stores = [
        Store(id=1,name='ドラゴンボール',open_hours=time(16,0),close_hours=time(0,0)),
        Store(id=2,name='ワンピース',open_hours=time(17,0),close_hours=time(0,0)),
        Store(id=3,name='呪術廻戦',open_hours=time(16,0),close_hours=time(1,0)),
        Store(id=4,name='鬼滅の刃',open_hours=time(17,0),close_hours=time(1,0))
]
db.add_all(stores)

# 2. Staffs
staffs = [
        Staff(id=1,name="孫悟空",gender="男",desired_days=5,kitchen_a=5,kitchen_b=4,drink=5,hall=4,leadership=4,employment_type="社員",login_code="DB001",password="password",store_id=1),
        Staff(id=2,name="ベジータ",gender="男",desired_days=5,kitchen_a=5,kitchen_b=4,drink=4,hall=4,leadership=4,employment_type="社員",login_code="DB002",password="password",store_id=1),
        Staff(id=3,name="孫悟飯",gender="男",desired_days=5,kitchen_a=4,kitchen_b=3,drink=4,hall=4,leadership=4,employment_type="バイト",login_code="DB003",password="password",store_id=1),
        Staff(id=4,name="ピッコロ",gender="男",desired_days=5,kitchen_a=4,kitchen_b=3,drink=3,hall=4,leadership=4,employment_type="バイト",login_code="DB004",password="password",store_id=1),
        Staff(id=5,name="クリリン",gender="男",desired_days=5,kitchen_a=3,kitchen_b=4,drink=4,hall=3,leadership=3,employment_type="バイト",login_code="DB005",password="password",store_id=1),
        Staff(id=6,name="フリーザ",desired_days=5,kitchen_a=5,kitchen_b=5,drink=4,hall=3,leadership=3,employment_type="バイト",login_code="DB006",password="password",store_id=1),
        Staff(id=7,name="セル",desired_days=5,kitchen_a=5,kitchen_b=4,drink=4,hall=4,leadership=3,employment_type="バイト",login_code="DB007",password="password",store_id=1),
        Staff(id=8,name="魔人ブウ",desired_days=5,kitchen_a=5,kitchen_b=3,drink=3,hall=5,leadership=2,employment_type="バイト",login_code="DB008",password="password",store_id=1),
        Staff(id=9,name="トランクス",gender="男",desired_days=5,kitchen_a=4,kitchen_b=4,drink=4,hall=3,leadership=3,employment_type="バイト",login_code="DB009",password="password",store_id=1),
        Staff(id=10,name="ゴテンクス",gender="男",desired_days=5,kitchen_a=4,kitchen_b=4,drink=5,hall=3,leadership=2,employment_type="バイト",login_code="DB010",password="password",store_id=1),
        Staff(id=11,name="ブロリー",gender="男",desired_days=5,kitchen_a=5,kitchen_b=3,drink=3,hall=5,leadership=2,employment_type="バイト",login_code="DB011",password="password",store_id=1),
        Staff(id=12,name="天津飯",gender="男",desired_days=5,kitchen_a=3,kitchen_b=4,drink=3,hall=3,leadership=3,employment_type="バイト",login_code="DB012",password="password",store_id=1),
        Staff(id=13,name="ヤムチャ",gender="男",desired_days=5,kitchen_a=3,kitchen_b=3,drink=3,hall=3,leadership=3,employment_type="バイト",login_code="DB013",password="password",store_id=1),
        Staff(id=14,name="18号",gender="女",desired_days=5,kitchen_a=4,kitchen_b=4,drink=4,hall=3,leadership=3,employment_type="バイト",login_code="DB014",password="password",store_id=1),
        Staff(id=15,name="ブルマ",gender="女",desired_days=5,kitchen_a=1,kitchen_b=5,drink=2,hall=2,leadership=5,employment_type="バイト",login_code="DB015",password="password",store_id=1),
        Staff(id=16,name="ルフィ",gender="男",desired_days=5,kitchen_a=5,kitchen_b=4,drink=5,hall=4,leadership=5,employment_type="社員",login_code="OP001",password="password",store_id=2),
        Staff(id=17,name="ゾロ",gender="男",desired_days=5,kitchen_a=5,kitchen_b=4,drink=3,hall=4,leadership=4,employment_type="バイト",login_code="OP002",password="password",store_id=2),
        Staff(id=18,name="サンジ",gender="男",desired_days=5,kitchen_a=4,kitchen_b=5,drink=4,hall=3,leadership=3,employment_type="バイト",login_code="OP003",password="password",store_id=2),
        Staff(id=19,name="ナミ",gender="女",desired_days=5,kitchen_a=2,kitchen_b=4,drink=3,hall=2,leadership=4,employment_type="バイト",login_code="OP004",password="password",store_id=2),
        Staff(id=20,name="ウソップ",gender="男",desired_days=5,kitchen_a=2,kitchen_b=3,drink=3,hall=2,leadership=3,employment_type="バイト",login_code="OP005",password="password",store_id=2),
        Staff(id=21,name="シャンクス",gender="男",desired_days=5,kitchen_a=5,kitchen_b=5,drink=4,hall=4,leadership=5,employment_type="バイト",login_code="OP006",password="password",store_id=2),
        Staff(id=22,name="ロー",gender="男",desired_days=5,kitchen_a=4,kitchen_b=5,drink=4,hall=3,leadership=3,employment_type="バイト",login_code="OP007",password="password",store_id=2),
        Staff(id=23,name="エース",gender="男",desired_days=5,kitchen_a=4,kitchen_b=4,drink=4,hall=3,leadership=4,employment_type="バイト",login_code="OP008",password="password",store_id=2),
        Staff(id=24,name="サボ",gender="男",desired_days=5,kitchen_a=4,kitchen_b=5,drink=4,hall=3,leadership=4,employment_type="バイト",login_code="OP009",password="password",store_id=2),
        Staff(id=25,name="ロビン",gender="女",desired_days=5,kitchen_a=3,kitchen_b=4,drink=3,hall=2,leadership=4,employment_type="バイト",login_code="OP010",password="password",store_id=2),
        Staff(id=26,name="チョッパー",gender="男",desired_days=5,kitchen_a=3,kitchen_b=3,drink=3,hall=2,leadership=3,employment_type="バイト",login_code="OP011",password="password",store_id=2),
        Staff(id=27,name="フランキー",gender="男",desired_days=5,kitchen_a=4,kitchen_b=3,drink=2,hall=5,leadership=3,employment_type="バイト",login_code="OP012",password="password",store_id=2),
        Staff(id=28,name="ジンベエ",gender="男",desired_days=5,kitchen_a=4,kitchen_b=4,drink=3,hall=4,leadership=4,employment_type="バイト",login_code="OP013",password="password",store_id=2),
        Staff(id=29,name="バギー",gender="男",desired_days=5,kitchen_a=3,kitchen_b=3,drink=2,hall=2,leadership=2,employment_type="未成年バイト",login_code="OP014",password="password",store_id=2),
        Staff(id=30,name="クロコダイル",gender="男",desired_days=5,kitchen_a=4,kitchen_b=4,drink=3,hall=3,leadership=3,employment_type="未成年バイト",login_code="OP015",password="password",store_id=2),
        Staff(id=34,name="五条悟",gender="男",desired_days=5,kitchen_a=5,kitchen_b=5,drink=5,hall=4,leadership=5,employment_type="社員",login_code="JK001",password="password",store_id=3),
        Staff(id=35,name="夏油傑",gender="男",desired_days=5,kitchen_a=4,kitchen_b=5,drink=4,hall=3,leadership=4,employment_type="社員",login_code="JK002",password="password",store_id=3),
        Staff(id=31,name="虎杖悠仁",gender="男",desired_days=5,kitchen_a=4,kitchen_b=4,drink=4,hall=3,leadership=4,employment_type="バイト",login_code="JK003",password="password",store_id=3),
        Staff(id=32,name="伏黒恵",gender="男",desired_days=5,kitchen_a=4,kitchen_b=4,drink=3,hall=3,leadership=3,employment_type="バイト",login_code="JK004",password="password",store_id=3),
        Staff(id=33,name="釘崎野薔薇",gender="女",desired_days=5,kitchen_a=3,kitchen_b=4,drink=3,hall=3,leadership=4,employment_type="バイト",login_code="JK005",password="password",store_id=3),
        Staff(id=36,name="真人",desired_days=5,kitchen_a=4,kitchen_b=4,drink=4,hall=3,leadership=2,employment_type="バイト",login_code="JK006",password="password",store_id=3),
        Staff(id=37,name="七海建人",gender="男",desired_days=5,kitchen_a=3,kitchen_b=4,drink=3,hall=3,leadership=4,employment_type="バイト",login_code="JK007",password="password",store_id=3),
        Staff(id=38,name="東堂葵",gender="男",desired_days=5,kitchen_a=5,kitchen_b=5,drink=4,hall=4,leadership=4,employment_type="バイト",login_code="JK008",password="password",store_id=3),
        Staff(id=39,name="パンダ",desired_days=5,kitchen_a=4,kitchen_b=3,drink=3,hall=4,leadership=2,employment_type="バイト",login_code="JK009",password="password",store_id=3),
        Staff(id=40,name="加茂憲紀",gender="男",desired_days=5,kitchen_a=3,kitchen_b=3,drink=3,hall=3,leadership=3,employment_type="バイト",login_code="JK010",password="password",store_id=3),
        Staff(id=41,name="禪院真希",gender="女",desired_days=5,kitchen_a=4,kitchen_b=4,drink=4,hall=3,leadership=3,employment_type="バイト",login_code="JK011",password="password",store_id=3),
        Staff(id=42,name="日下部篤也",gender="男",desired_days=5,kitchen_a=3,kitchen_b=4,drink=3,hall=3,leadership=3,employment_type="未成年バイト",login_code="JK012",password="password",store_id=3),
        Staff(id=43,name="狗巻棘",gender="男",desired_days=5,kitchen_a=3,kitchen_b=4,drink=3,hall=3,leadership=3,employment_type="未成年バイト",login_code="JK013",password="password",store_id=3),
        Staff(id=44,name="羂索",desired_days=5,kitchen_a=5,kitchen_b=5,drink=4,hall=3,leadership=4,employment_type="未成年バイト",login_code="JK014",password="password",store_id=3),
        Staff(id=45,name="炭治郎",gender="男",desired_days=5,kitchen_a=4,kitchen_b=5,drink=4,hall=3,leadership=5,employment_type="社員",login_code="KY001",password="password",store_id=4),
        Staff(id=46,name="禰豆子",gender="女",desired_days=5,kitchen_a=4,kitchen_b=4,drink=4,hall=4,leadership=3,employment_type="社員",login_code="KY002",password="password",store_id=4),
        Staff(id=47,name="善逸",gender="男",desired_days=5,kitchen_a=3,kitchen_b=4,drink=5,hall=3,leadership=2,employment_type="社員",login_code="KY003",password="password",store_id=4),
        Staff(id=48,name="伊之助",gender="男",desired_days=5,kitchen_a=5,kitchen_b=4,drink=5,hall=3,leadership=3,employment_type="社員",login_code="KY004",password="password",store_id=4),
        Staff(id=49,name="義勇",gender="男",desired_days=5,kitchen_a=5,kitchen_b=5,drink=4,hall=4,leadership=4,employment_type="バイト",login_code="KY005",password="password",store_id=4),
        Staff(id=50,name="しのぶ",gender="女",desired_days=5,kitchen_a=3,kitchen_b=4,drink=4,hall=2,leadership=3,employment_type="バイト",login_code="KY006",password="password",store_id=4),
        Staff(id=51,name="煉獄杏寿郎",gender="男",desired_days=5,kitchen_a=5,kitchen_b=4,drink=4,hall=4,leadership=5,employment_type="バイト",login_code="KY007",password="password",store_id=4),
        Staff(id=52,name="宇髄天元",gender="男",desired_days=5,kitchen_a=5,kitchen_b=4,drink=5,hall=3,leadership=3,employment_type="バイト",login_code="KY008",password="password",store_id=4),
        Staff(id=53,name="時透無一郎",gender="男",desired_days=5,kitchen_a=5,kitchen_b=4,drink=5,hall=3,leadership=3,employment_type="バイト",login_code="KY009",password="password",store_id=4),
        Staff(id=54,name="甘露寺蜜璃",gender="女",desired_days=5,kitchen_a=4,kitchen_b=4,drink=4,hall=3,leadership=3,employment_type="未成年バイト",login_code="KY010",password="password",store_id=4),
        Staff(id=55,name="伊黒小芭内",gender="男",desired_days=5,kitchen_a=4,kitchen_b=4,drink=4,hall=3,leadership=3,employment_type="未成年バイト",login_code="KY011",password="password",store_id=4),
        Staff(id=56,name="不死川実弥",gender="男",desired_days=5,kitchen_a=5,kitchen_b=4,drink=4,hall=4,leadership=3,employment_type="未成年バイト",login_code="KY012",password="password",store_id=4),
        Staff(id=57,name="鋼鐵塚蛍",gender="男",desired_days=5,kitchen_a=2,kitchen_b=5,drink=2,hall=2,leadership=2,employment_type="未成年バイト",login_code="KY013",password="password",store_id=4),
        Staff(id=58,name="鱗滝左近次",gender="男",desired_days=5,kitchen_a=3,kitchen_b=4,drink=3,hall=3,leadership=5,employment_type="未成年バイト",login_code="KY014",password="password",store_id=4)
]
db.add_all(staffs)

# コミット
db.commit()
print("✅ テストデータを挿入しました。")
