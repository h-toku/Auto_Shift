from sqlalchemy.orm import Session
from models import Store, Staff, StoreDefaultSkillRequirement, ShiftRequest, ShiftPattern
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine


DATABASE_URL="mysql+pymysql://root:FgxCQBiZFtriLCbGzxhcXgpxQZCqqJfA@maglev.proxy.rlwy.net:44128/railway"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# DBセッション生成
db: Session = SessionLocal()

# 1. Stores
stores = [
        Store(id=1,name='ドラゴンボール',open_hours=4,close_hours=12),
        Store(id=2,name='ワンピース',open_hours=5,close_hours=12),
        Store(id=3,name='呪術廻戦',open_hours=4,close_hours=13),
        Store(id=4,name='鬼滅の刃',open_hours=5,close_hours=13)
]
db.add_all(stores)

# 2. Staffs
staffs = [
Staff(id=1,name="孫悟空",gender="男",kitchen_a="A",kitchen_b="A",hall=5,leadership=5,employment_type="社員",login_code="DB001",password="password",store_id=1),
Staff(id=2,name="ベジータ",gender="男",kitchen_a="A",kitchen_b="A",hall=5,leadership=5,employment_type="社員",login_code="DB002",password="password",store_id=1),
Staff(id=3,name="孫悟飯",gender="男",kitchen_a="A",kitchen_b="A",hall=4,leadership=4,employment_type="バイト",login_code="DB003",password="password",store_id=1),
Staff(id=4,name="ピッコロ",gender="男",kitchen_a="A",kitchen_b="B",hall=4,leadership=4,employment_type="バイト",login_code="DB004",password="password",store_id=1),
Staff(id=5,name="クリリン",gender="男",kitchen_a="B",kitchen_b="A",hall=3,leadership=3,employment_type="バイト",login_code="DB005",password="password",store_id=1),
Staff(id=6,name="フリーザ",kitchen_a="B",kitchen_b="A",hall=3,leadership=3,employment_type="バイト",login_code="DB006",password="password",store_id=1),
Staff(id=7,name="セル",kitchen_a="B",kitchen_b="B",hall=4,leadership=3,employment_type="バイト",login_code="DB007",password="password",store_id=1),
Staff(id=8,name="魔人ブウ",kitchen_a="B",kitchen_b="B",hall=5,leadership=2,employment_type="バイト",login_code="DB008",password="password",store_id=1),
Staff(id=9,name="トランクス",gender="男",kitchen_a="B",kitchen_b="B",hall=3,leadership=3,employment_type="バイト",login_code="DB009",password="password",store_id=1),
Staff(id=10,name="ゴテンクス",gender="男",kitchen_a="B",kitchen_b="B",hall=3,leadership=2,employment_type="バイト",login_code="DB010",password="password",store_id=1),
Staff(id=11,name="ブロリー",gender="男",kitchen_a="C",kitchen_b="B",hall=5,leadership=2,employment_type="バイト",login_code="DB011",password="password",store_id=1),
Staff(id=12,name="天津飯",gender="男",kitchen_a="C",kitchen_b="B",hall=3,leadership=3,employment_type="バイト",login_code="DB012",password="password",store_id=1),
Staff(id=13,name="ヤムチャ",gender="男",kitchen_a="C",kitchen_b="C",hall=3,leadership=3,employment_type="バイト",login_code="DB013",password="password",store_id=1),
Staff(id=14,name="18号",gender="女",kitchen_a="C",kitchen_b="C",hall=3,leadership=3,employment_type="バイト",login_code="DB014",password="password",store_id=1),
Staff(id=15,name="ブルマ",gender="女",kitchen_a="C",kitchen_b="C",hall=2,leadership=5,employment_type="バイト",login_code="DB015",password="password",store_id=1),
Staff(id=16,name="ルフィ",gender="男",kitchen_a="A",kitchen_b="A",hall=5,leadership=5,employment_type="社員",login_code="OP001",password="password",store_id=2),
Staff(id=17,name="ゾロ",gender="男",kitchen_a="A",kitchen_b="A",hall=4,leadership=4,employment_type="バイト",login_code="OP002",password="password",store_id=2),
Staff(id=18,name="サンジ",gender="男",kitchen_a="A",kitchen_b="A",hall=3,leadership=3,employment_type="バイト",login_code="OP003",password="password",store_id=2),
Staff(id=19,name="ナミ",gender="女",kitchen_a="C",kitchen_b="C",hall=2,leadership=4,employment_type="バイト",login_code="OP004",password="password",store_id=2),
Staff(id=20,name="ウソップ",gender="男",kitchen_a="B",kitchen_b="A",hall=2,leadership=3,employment_type="バイト",login_code="OP005",password="password",store_id=2),
Staff(id=21,name="シャンクス",gender="男",kitchen_a="B",kitchen_b="B",hall=4,leadership=5,employment_type="バイト",login_code="OP006",password="password",store_id=2),
Staff(id=22,name="ロー",gender="男",kitchen_a="B",kitchen_b="B",hall=3,leadership=3,employment_type="バイト",login_code="OP007",password="password",store_id=2),
Staff(id=23,name="エース",gender="男",kitchen_a="B",kitchen_b="B",hall=3,leadership=4,employment_type="バイト",login_code="OP008",password="password",store_id=2),
Staff(id=24,name="サボ",gender="男",kitchen_a="B",kitchen_b="B",hall=3,leadership=4,employment_type="バイト",login_code="OP009",password="password",store_id=2),
Staff(id=25,name="ロビン",gender="女",kitchen_a="C",kitchen_b="C",hall=2,leadership=4,employment_type="バイト",login_code="OP010",password="password",store_id=2),
Staff(id=26,name="チョッパー",gender="男",kitchen_a="C",kitchen_b="B",hall=2,leadership=3,employment_type="バイト",login_code="OP011",password="password",store_id=2),
Staff(id=27,name="フランキー",gender="男",kitchen_a="C",kitchen_b="C",hall=5,leadership=3,employment_type="バイト",login_code="OP012",password="password",store_id=2),
Staff(id=28,name="ジンベエ",gender="男",kitchen_a="C",kitchen_b="C",hall=4,leadership=4,employment_type="バイト",login_code="OP013",password="password",store_id=2),
Staff(id=29,name="バギー",gender="男",kitchen_a="C",kitchen_b="B",hall=2,leadership=2,employment_type="未成年バイト",login_code="OP014",password="password",store_id=2),
Staff(id=30,name="クロコダイル",gender="男",kitchen_a="C",kitchen_b="B",hall=3,leadership=3,employment_type="未成年バイト",login_code="OP015",password="password",store_id=2),
Staff(id=34,name="五条悟",gender="男",kitchen_a="A",kitchen_b="A",hall=5,leadership=5,employment_type="社員",login_code="JK001",password="password",store_id=3),
Staff(id=35,name="夏油傑",gender="男",kitchen_a="A",kitchen_b="A",hall=5,leadership=5,employment_type="社員",login_code="JK002",password="password",store_id=3),
Staff(id=31,name="虎杖悠仁",gender="男",kitchen_a="A",kitchen_b="A",hall=3,leadership=4,employment_type="バイト",login_code="JK003",password="password",store_id=3),
Staff(id=32,name="伏黒恵",gender="男",kitchen_a="A",kitchen_b="A",hall=3,leadership=3,employment_type="バイト",login_code="JK004",password="password",store_id=3),
Staff(id=33,name="釘崎野薔薇",gender="女",kitchen_a="C",kitchen_b="C",hall=3,leadership=4,employment_type="バイト",login_code="JK005",password="password",store_id=3),
Staff(id=36,name="真人",kitchen_a="B",kitchen_b="A",hall=3,leadership=2,employment_type="バイト",login_code="JK006",password="password",store_id=3),
Staff(id=37,name="七海建人",gender="男",kitchen_a="B",kitchen_b="B",hall=3,leadership=4,employment_type="バイト",login_code="JK007",password="password",store_id=3),
Staff(id=38,name="東堂葵",gender="男",kitchen_a="B",kitchen_b="B",hall=4,leadership=4,employment_type="バイト",login_code="JK008",password="password",store_id=3),
Staff(id=39,name="パンダ",kitchen_a="C",kitchen_b="B",hall=4,leadership=2,employment_type="バイト",login_code="JK009",password="password",store_id=3),
Staff(id=40,name="加茂憲紀",gender="男",kitchen_a="C",kitchen_b="C",hall=3,leadership=3,employment_type="バイト",login_code="JK010",password="password",store_id=3),
Staff(id=41,name="禪院真希",gender="女",kitchen_a="C",kitchen_b="C",hall=3,leadership=3,employment_type="バイト",login_code="JK011",password="password",store_id=3),
Staff(id=42,name="日下部篤也",gender="男",kitchen_a="C",kitchen_b="B",hall=3,leadership=3,employment_type="未成年バイト",login_code="JK012",password="password",store_id=3),
Staff(id=43,name="狗巻棘",gender="男",kitchen_a="C",kitchen_b="B",hall=3,leadership=3,employment_type="未成年バイト",login_code="JK013",password="password",store_id=3),
Staff(id=44,name="羂索",kitchen_a="C",kitchen_b="C",hall=3,leadership=4,employment_type="未成年バイト",login_code="JK014",password="password",store_id=3),
Staff(id=45,name="炭治郎",gender="男",kitchen_a="A",kitchen_b="A",hall=5,leadership=5,employment_type="社員",login_code="KY001",password="password",store_id=4),
Staff(id=46,name="禰豆子",gender="女",kitchen_a="A",kitchen_b="A",hall=5,leadership=5,employment_type="社員",login_code="KY002",password="password",store_id=4),
Staff(id=47,name="善逸",gender="男",kitchen_a="A",kitchen_b="A",hall=5,leadership=5,employment_type="社員",login_code="KY003",password="password",store_id=4),
Staff(id=48,name="伊之助",gender="男",kitchen_a="A",kitchen_b="A",hall=5,leadership=5,employment_type="社員",login_code="KY004",password="password",store_id=4),
Staff(id=49,name="義勇",gender="男",kitchen_a="A",kitchen_b="A",hall=4,leadership=4,employment_type="バイト",login_code="KY005",password="password",store_id=4),
Staff(id=50,name="しのぶ",gender="女",kitchen_a="C",kitchen_b="C",hall=2,leadership=3,employment_type="バイト",login_code="KY006",password="password",store_id=4),
Staff(id=51,name="煉獄杏寿郎",gender="男",kitchen_a="A",kitchen_b="A",hall=4,leadership=5,employment_type="バイト",login_code="KY007",password="password",store_id=4),
Staff(id=52,name="宇髄天元",gender="男",kitchen_a="C",kitchen_b="B",hall=3,leadership=3,employment_type="バイト",login_code="KY008",password="password",store_id=4),
Staff(id=53,name="時透無一郎",gender="男",kitchen_a="C",kitchen_b="B",hall=3,leadership=3,employment_type="バイト",login_code="KY009",password="password",store_id=4),
Staff(id=54,name="甘露寺蜜璃",gender="女",kitchen_a="C",kitchen_b="C",hall=3,leadership=3,employment_type="未成年バイト",login_code="KY010",password="password",store_id=4),
Staff(id=55,name="伊黒小芭内",gender="男",kitchen_a="C",kitchen_b="C",hall=3,leadership=3,employment_type="未成年バイト",login_code="KY011",password="password",store_id=4),
Staff(id=56,name="不死川実弥",gender="男",kitchen_a="C",kitchen_b="B",hall=4,leadership=3,employment_type="未成年バイト",login_code="KY012",password="password",store_id=4),
Staff(id=57,name="鋼鐵塚蛍",gender="男",kitchen_a="C",kitchen_b="B",hall=2,leadership=2,employment_type="未成年バイト",login_code="KY013",password="password",store_id=4),
Staff(id=58,name="鱗滝左近次",gender="男",kitchen_a="C",kitchen_b="C",hall=3,leadership=5,employment_type="未成年バイト",login_code="KY014",password="password",store_id=4)
]
db.add_all(staffs)

store_default_skill_requirements = [
StoreDefaultSkillRequirement(id=1,store_id=1,day_type="平日",peak_start_hour=7,peak_end_hour=9,kitchen_a="B",kitchen_b="B",hall=10,peak_people=5,leadership=5,open_people=3,close_people=3),
StoreDefaultSkillRequirement(id=2,store_id=1,day_type="金曜日",peak_start_hour=7,peak_end_hour=10,kitchen_a="A",kitchen_b="A",hall=13,peak_people=6,leadership=10,open_people=3,close_people=4),
StoreDefaultSkillRequirement(id=3,store_id=1,day_type="土曜日",peak_start_hour=6,peak_end_hour=10,kitchen_a="A",kitchen_b="A",hall=15,peak_people=7,leadership=12,open_people=5,close_people=4),
StoreDefaultSkillRequirement(id=4,store_id=1,day_type="日曜日",peak_start_hour=5,peak_end_hour=9,kitchen_a="B",kitchen_b="B",hall=12,peak_people=6,leadership=8,open_people=5,close_people=3),
StoreDefaultSkillRequirement(id=5,store_id=2,day_type="平日",peak_start_hour=7,peak_end_hour=9,kitchen_a="B",kitchen_b="B",hall=10,peak_people=5,leadership=5,open_people=3,close_people=3),
StoreDefaultSkillRequirement(id=6,store_id=2,day_type="金曜日",peak_start_hour=7,peak_end_hour=10,kitchen_a="A",kitchen_b="A",hall=13,peak_people=6,leadership=10,open_people=3,close_people=4),
StoreDefaultSkillRequirement(id=7,store_id=2,day_type="土曜日",peak_start_hour=6,peak_end_hour=10,kitchen_a="A",kitchen_b="A",hall=15,peak_people=7,leadership=12,open_people=5,close_people=4),
StoreDefaultSkillRequirement(id=8,store_id=2,day_type="日曜日",peak_start_hour=5,peak_end_hour=9,kitchen_a="B",kitchen_b="B",hall=12,peak_people=6,leadership=8,open_people=5,close_people=3),
StoreDefaultSkillRequirement(id=9,store_id=3,day_type="平日",peak_start_hour=7,peak_end_hour=9,kitchen_a="B",kitchen_b="B",hall=10,peak_people=5,leadership=5,open_people=3,close_people=3),
StoreDefaultSkillRequirement(id=10,store_id=3,day_type="金曜日",peak_start_hour=7,peak_end_hour=10,kitchen_a="A",kitchen_b="A",hall=13,peak_people=6,leadership=10,open_people=3,close_people=4),
StoreDefaultSkillRequirement(id=11,store_id=3,day_type="土曜日",peak_start_hour=6,peak_end_hour=10,kitchen_a="A",kitchen_b="A",hall=15,peak_people=7,leadership=12,open_people=5,close_people=4),
StoreDefaultSkillRequirement(id=12,store_id=3,day_type="日曜日",peak_start_hour=5,peak_end_hour=9,kitchen_a="B",kitchen_b="B",hall=12,peak_people=6,leadership=8,open_people=5,close_people=3),
StoreDefaultSkillRequirement(id=13,store_id=4,day_type="平日",peak_start_hour=7,peak_end_hour=9,kitchen_a="B",kitchen_b="B",hall=10,peak_people=5,leadership=5,open_people=3,close_people=3),
StoreDefaultSkillRequirement(id=14,store_id=4,day_type="金曜日",peak_start_hour=7,peak_end_hour=10,kitchen_a="A",kitchen_b="A",hall=13,peak_people=6,leadership=10,open_people=3,close_people=4),
StoreDefaultSkillRequirement(id=15,store_id=4,day_type="土曜日",peak_start_hour=6,peak_end_hour=10,kitchen_a="A",kitchen_b="A",hall=15,peak_people=7,leadership=12,open_people=5,close_people=4),
StoreDefaultSkillRequirement(id=16,store_id=4,day_type="日曜日",peak_start_hour=5,peak_end_hour=9,kitchen_a="B",kitchen_b="B",hall=12,peak_people=6,leadership=8,open_people=5,close_people=3),
]
db.add_all(store_default_skill_requirements)

# 4. Shift Requests
shift_requests = [
ShiftRequest(staff_id=16,year=2025,month=6,day=1,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=2,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=3,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=4,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=6,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=7,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=8,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=9,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=11,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=12,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=13,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=14,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=16,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=17,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=18,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=19,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=21,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=22,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=23,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=24,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=26,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=27,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=28,status="O",),
ShiftRequest(staff_id=16,year=2025,month=6,day=29,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=1,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=2,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=3,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=5,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=6,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=7,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=8,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=10,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=11,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=12,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=14,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=15,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=16,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=17,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=19,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=20,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=21,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=23,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=24,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=25,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=26,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=28,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=29,status="O",),
ShiftRequest(staff_id=17,year=2025,month=6,day=30,status="O",),
ShiftRequest(staff_id=18,year=2025,month=6,day=1,status="O",),
ShiftRequest(staff_id=18,year=2025,month=6,day=6,status="O",),
ShiftRequest(staff_id=18,year=2025,month=6,day=7,status="O",),
ShiftRequest(staff_id=18,year=2025,month=6,day=8,status="O",),
ShiftRequest(staff_id=18,year=2025,month=6,day=13,status="O",),
ShiftRequest(staff_id=18,year=2025,month=6,day=14,status="O",),
ShiftRequest(staff_id=18,year=2025,month=6,day=15,status="O",),
ShiftRequest(staff_id=18,year=2025,month=6,day=20,status="O",),
ShiftRequest(staff_id=18,year=2025,month=6,day=21,status="O",),
ShiftRequest(staff_id=18,year=2025,month=6,day=22,status="O",),
ShiftRequest(staff_id=18,year=2025,month=6,day=27,status="O",),
ShiftRequest(staff_id=18,year=2025,month=6,day=28,status="O",),
ShiftRequest(staff_id=18,year=2025,month=6,day=29,status="O",),
ShiftRequest(staff_id=19,year=2025,month=6,day=6,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=19,year=2025,month=6,day=7,status="O",),
ShiftRequest(staff_id=19,year=2025,month=6,day=8,status="time",start_time=5,end_time=11,),
ShiftRequest(staff_id=19,year=2025,month=6,day=13,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=19,year=2025,month=6,day=14,status="O",),
ShiftRequest(staff_id=19,year=2025,month=6,day=15,status="time",start_time=5,end_time=11,),
ShiftRequest(staff_id=19,year=2025,month=6,day=20,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=19,year=2025,month=6,day=21,status="O",),
ShiftRequest(staff_id=19,year=2025,month=6,day=22,status="time",start_time=5,end_time=11,),
ShiftRequest(staff_id=19,year=2025,month=6,day=27,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=19,year=2025,month=6,day=28,status="O",),
ShiftRequest(staff_id=19,year=2025,month=6,day=29,status="time",start_time=5,end_time=11,),
ShiftRequest(staff_id=20,year=2025,month=6,day=1,status="O",),
ShiftRequest(staff_id=20,year=2025,month=6,day=3,status="O",),
ShiftRequest(staff_id=20,year=2025,month=6,day=5,status="O",),
ShiftRequest(staff_id=20,year=2025,month=6,day=7,status="O",),
ShiftRequest(staff_id=20,year=2025,month=6,day=8,status="O",),
ShiftRequest(staff_id=20,year=2025,month=6,day=10,status="O",),
ShiftRequest(staff_id=20,year=2025,month=6,day=12,status="O",),
ShiftRequest(staff_id=20,year=2025,month=6,day=14,status="O",),
ShiftRequest(staff_id=20,year=2025,month=6,day=15,status="O",),
ShiftRequest(staff_id=20,year=2025,month=6,day=17,status="O",),
ShiftRequest(staff_id=20,year=2025,month=6,day=19,status="O",),
ShiftRequest(staff_id=20,year=2025,month=6,day=21,status="O",),
ShiftRequest(staff_id=20,year=2025,month=6,day=22,status="O",),
ShiftRequest(staff_id=20,year=2025,month=6,day=24,status="O",),
ShiftRequest(staff_id=20,year=2025,month=6,day=26,status="O",),
ShiftRequest(staff_id=20,year=2025,month=6,day=28,status="O",),
ShiftRequest(staff_id=20,year=2025,month=6,day=29,status="O",),
ShiftRequest(staff_id=21,year=2025,month=6,day=1,status="O",),
ShiftRequest(staff_id=21,year=2025,month=6,day=2,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=21,year=2025,month=6,day=3,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=21,year=2025,month=6,day=4,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=21,year=2025,month=6,day=5,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=21,year=2025,month=6,day=6,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=21,year=2025,month=6,day=7,status="O",),
ShiftRequest(staff_id=21,year=2025,month=6,day=8,status="O",),
ShiftRequest(staff_id=21,year=2025,month=6,day=9,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=21,year=2025,month=6,day=10,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=21,year=2025,month=6,day=11,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=21,year=2025,month=6,day=12,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=21,year=2025,month=6,day=13,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=21,year=2025,month=6,day=14,status="O",),
ShiftRequest(staff_id=21,year=2025,month=6,day=15,status="O",),
ShiftRequest(staff_id=21,year=2025,month=6,day=16,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=21,year=2025,month=6,day=17,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=21,year=2025,month=6,day=18,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=21,year=2025,month=6,day=19,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=21,year=2025,month=6,day=20,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=21,year=2025,month=6,day=21,status="O",),
ShiftRequest(staff_id=21,year=2025,month=6,day=22,status="O",),
ShiftRequest(staff_id=21,year=2025,month=6,day=23,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=21,year=2025,month=6,day=24,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=21,year=2025,month=6,day=25,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=21,year=2025,month=6,day=26,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=21,year=2025,month=6,day=27,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=21,year=2025,month=6,day=28,status="O",),
ShiftRequest(staff_id=21,year=2025,month=6,day=29,status="O",),
ShiftRequest(staff_id=21,year=2025,month=6,day=30,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=22,year=2025,month=6,day=1,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=22,year=2025,month=6,day=2,status="time",start_time=4,end_time=11,),
ShiftRequest(staff_id=22,year=2025,month=6,day=8,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=22,year=2025,month=6,day=9,status="time",start_time=4,end_time=11,),
ShiftRequest(staff_id=22,year=2025,month=6,day=15,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=22,year=2025,month=6,day=16,status="time",start_time=4,end_time=11,),
ShiftRequest(staff_id=22,year=2025,month=6,day=22,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=22,year=2025,month=6,day=23,status="time",start_time=4,end_time=11,),
ShiftRequest(staff_id=22,year=2025,month=6,day=29,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=22,year=2025,month=6,day=30,status="time",start_time=4,end_time=11,),
ShiftRequest(staff_id=23,year=2025,month=6,day=3,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=23,year=2025,month=6,day=4,status="O",),
ShiftRequest(staff_id=23,year=2025,month=6,day=5,status="O",),
ShiftRequest(staff_id=23,year=2025,month=6,day=10,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=23,year=2025,month=6,day=11,status="O",),
ShiftRequest(staff_id=23,year=2025,month=6,day=12,status="O",),
ShiftRequest(staff_id=23,year=2025,month=6,day=17,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=23,year=2025,month=6,day=18,status="O",),
ShiftRequest(staff_id=23,year=2025,month=6,day=19,status="O",),
ShiftRequest(staff_id=23,year=2025,month=6,day=24,status="time",start_time=8,end_time=12,),
ShiftRequest(staff_id=23,year=2025,month=6,day=25,status="O",),
ShiftRequest(staff_id=23,year=2025,month=6,day=26,status="O",),
ShiftRequest(staff_id=24,year=2025,month=6,day=1,status="O",),
ShiftRequest(staff_id=24,year=2025,month=6,day=3,status="O",),
ShiftRequest(staff_id=24,year=2025,month=6,day=4,status="O",),
ShiftRequest(staff_id=24,year=2025,month=6,day=5,status="O",),
ShiftRequest(staff_id=24,year=2025,month=6,day=6,status="O",),
ShiftRequest(staff_id=24,year=2025,month=6,day=8,status="O",),
ShiftRequest(staff_id=24,year=2025,month=6,day=9,status="O",),
ShiftRequest(staff_id=24,year=2025,month=6,day=11,status="O",),
ShiftRequest(staff_id=24,year=2025,month=6,day=13,status="O",),
ShiftRequest(staff_id=24,year=2025,month=6,day=14,status="O",),
ShiftRequest(staff_id=24,year=2025,month=6,day=15,status="O",),
ShiftRequest(staff_id=24,year=2025,month=6,day=17,status="O",),
ShiftRequest(staff_id=24,year=2025,month=6,day=19,status="O",),
ShiftRequest(staff_id=24,year=2025,month=6,day=20,status="O",),
ShiftRequest(staff_id=24,year=2025,month=6,day=21,status="O",),
ShiftRequest(staff_id=24,year=2025,month=6,day=23,status="O",),
ShiftRequest(staff_id=24,year=2025,month=6,day=25,status="O",),
ShiftRequest(staff_id=24,year=2025,month=6,day=26,status="O",),
ShiftRequest(staff_id=24,year=2025,month=6,day=30,status="O",),
ShiftRequest(staff_id=25,year=2025,month=6,day=1,status="O",),
ShiftRequest(staff_id=25,year=2025,month=6,day=2,status="O",),
ShiftRequest(staff_id=25,year=2025,month=6,day=3,status="O",),
ShiftRequest(staff_id=25,year=2025,month=6,day=4,status="O",),
ShiftRequest(staff_id=25,year=2025,month=6,day=7,status="O",),
ShiftRequest(staff_id=25,year=2025,month=6,day=8,status="O",),
ShiftRequest(staff_id=25,year=2025,month=6,day=9,status="O",),
ShiftRequest(staff_id=25,year=2025,month=6,day=10,status="O",),
ShiftRequest(staff_id=25,year=2025,month=6,day=11,status="O",),
ShiftRequest(staff_id=25,year=2025,month=6,day=14,status="O",),
ShiftRequest(staff_id=25,year=2025,month=6,day=15,status="O",),
ShiftRequest(staff_id=25,year=2025,month=6,day=20,status="O",),
ShiftRequest(staff_id=25,year=2025,month=6,day=24,status="O",),
ShiftRequest(staff_id=25,year=2025,month=6,day=26,status="O",),
ShiftRequest(staff_id=25,year=2025,month=6,day=29,status="O",),
ShiftRequest(staff_id=26,year=2025,month=6,day=1,status="O",),
ShiftRequest(staff_id=26,year=2025,month=6,day=4,status="O",),
ShiftRequest(staff_id=26,year=2025,month=6,day=11,status="O",),
ShiftRequest(staff_id=26,year=2025,month=6,day=14,status="O",),
ShiftRequest(staff_id=26,year=2025,month=6,day=19,status="O",),
ShiftRequest(staff_id=26,year=2025,month=6,day=23,status="O",),
ShiftRequest(staff_id=26,year=2025,month=6,day=25,status="O",),
ShiftRequest(staff_id=26,year=2025,month=6,day=29,status="O",),
ShiftRequest(staff_id=27,year=2025,month=6,day=3,status="O",),
ShiftRequest(staff_id=27,year=2025,month=6,day=5,status="O",),
ShiftRequest(staff_id=27,year=2025,month=6,day=9,status="O",),
ShiftRequest(staff_id=27,year=2025,month=6,day=13,status="O",),
ShiftRequest(staff_id=27,year=2025,month=6,day=16,status="O",),
ShiftRequest(staff_id=27,year=2025,month=6,day=20,status="O",),
ShiftRequest(staff_id=27,year=2025,month=6,day=23,status="O",),
ShiftRequest(staff_id=27,year=2025,month=6,day=26,status="O",),
ShiftRequest(staff_id=27,year=2025,month=6,day=30,status="O",),
ShiftRequest(staff_id=28,year=2025,month=6,day=4,status="O",),
ShiftRequest(staff_id=28,year=2025,month=6,day=8,status="O",),
ShiftRequest(staff_id=28,year=2025,month=6,day=11,status="O",),
ShiftRequest(staff_id=28,year=2025,month=6,day=12,status="O",),
ShiftRequest(staff_id=28,year=2025,month=6,day=21,status="O",),
ShiftRequest(staff_id=28,year=2025,month=6,day=27,status="O",),
ShiftRequest(staff_id=28,year=2025,month=6,day=30,status="O",),
ShiftRequest(staff_id=29,year=2025,month=6,day=1,status="O",),
ShiftRequest(staff_id=29,year=2025,month=6,day=2,status="O",),
ShiftRequest(staff_id=29,year=2025,month=6,day=3,status="O",),
ShiftRequest(staff_id=29,year=2025,month=6,day=6,status="O",),
ShiftRequest(staff_id=29,year=2025,month=6,day=9,status="O",),
ShiftRequest(staff_id=29,year=2025,month=6,day=11,status="O",),
ShiftRequest(staff_id=29,year=2025,month=6,day=16,status="O",),
ShiftRequest(staff_id=29,year=2025,month=6,day=19,status="O",),
ShiftRequest(staff_id=29,year=2025,month=6,day=24,status="O",),
ShiftRequest(staff_id=29,year=2025,month=6,day=28,status="O",),
ShiftRequest(staff_id=30,year=2025,month=6,day=2,status="O",),
ShiftRequest(staff_id=30,year=2025,month=6,day=4,status="O",),
ShiftRequest(staff_id=30,year=2025,month=6,day=11,status="O",),
ShiftRequest(staff_id=30,year=2025,month=6,day=17,status="O",),
ShiftRequest(staff_id=30,year=2025,month=6,day=19,status="O",),
ShiftRequest(staff_id=30,year=2025,month=6,day=25,status="O",),
ShiftRequest(staff_id=30,year=2025,month=6,day=28,status="O",)
]
db.add_all(shift_requests)


# コミット
db.commit()
print("✅ テストデータを挿入しました。")
