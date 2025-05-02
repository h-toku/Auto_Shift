from sqlalchemy import Column, Integer, String, ForeignKey, Enum, CheckConstraint, Time, Date
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import validates

Base = declarative_base()

class Shift(Base):
    __tablename__ = 'shifts'
    
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey('staffs.id'))
    date = Column(Date)
    start_time = Column(Time)
    end_time = Column(Time)
    
    staff = relationship('Staff', back_populates='shifts')


class ShiftRequest(Base):
    __tablename__ = "shift_requests"

    id = Column(Integer, primary_key=True)
    staff_id = Column(Integer, ForeignKey("staffs.id"), nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)

    status = Column(
        Enum("×", "○", "time", name="status_enum"),
        nullable=False
    )
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)  # 店舗情報との関連
    store = relationship("Store", back_populates="shift_requests", lazy='joined')  # リレーションの即時読み込み

    @validates("start_time", "end_time")
    def validate_times(self, key, value):
        if self.store is None:  # storeがNoneの場合にエラーハンドリング
            raise ValueError("店舗情報が設定されていません。")
        store = self.store  # 店舗情報を取得
        if self.status == "○":  # ステータスが○の場合、オープン時間からクローズ時間まで設定
            if key == "start_time":
                return store.open_time  # オープン時間に設定
            if key == "end_time":
                return store.close_time  # クローズ時間に設定
        else:
            return value  # 通常通り、指定された時間を使用



class Store(Base):
    __tablename__ = 'stores'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    open_hours = Column(Time, nullable=False)  # 修正：open_time → open_hours
    close_hours = Column(Time, nullable=False)  # 修正：close_time → close_hours

    staffs = relationship('Staff', back_populates='store')
    shift_requests = relationship("ShiftRequest", back_populates="store")


class Staff(Base):
    __tablename__ = 'staffs'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    gender = Column(
        Enum("男", "女", name="gender_enum"),
        nullable=True
    )
    desired_days = Column(Integer, nullable=False)
    
    kitchen_a = Column(Integer, default=0, nullable=False)
    kitchen_b = Column(Integer, default=0, nullable=False)
    drink = Column(Integer, default=0, nullable=False)
    hall = Column(Integer, default=0, nullable=False)
    leadership = Column(Integer, default=0, nullable=False)

    employment_type = Column(
        Enum("社員", "バイト", "未成年バイト", name="employment_type_enum"),
        nullable=False
    )
    login_code = Column(String(50), unique=True, nullable=False)
    password = Column(String(100), nullable=False)

    store_id = Column(Integer, ForeignKey('stores.id'))
    store = relationship("Store", back_populates="staffs")
    
    shifts = relationship('Shift', back_populates='staff')

    # 0〜5に制限をかける
    __table_args__ = (
        CheckConstraint('kitchen_a BETWEEN 0 AND 5', name='check_kitchen_a'),
        CheckConstraint('kitchen_b BETWEEN 0 AND 5', name='check_kitchen_b'),
        CheckConstraint('drink BETWEEN 0 AND 5', name='check_drink'),
        CheckConstraint('hall BETWEEN 0 AND 5', name='check_hall'),
        CheckConstraint('leadership BETWEEN 0 AND 5', name='check_leadership'),
    )
