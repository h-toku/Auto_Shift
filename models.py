from sqlalchemy import Column, Integer, String, ForeignKey, Enum, CheckConstraint, Time, Date
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import validates

Base = declarative_base()

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
    shift_requests = relationship("ShiftRequest", back_populates="staff")
    shift_results = relationship("Shiftresult", back_populates="staff")

    # 0〜5に制限をかける
    __table_args__ = (
        CheckConstraint('kitchen_a BETWEEN 0 AND 5', name='check_kitchen_a'),
        CheckConstraint('kitchen_b BETWEEN 0 AND 5', name='check_kitchen_b'),
        CheckConstraint('drink BETWEEN 0 AND 5', name='check_drink'),
        CheckConstraint('hall BETWEEN 0 AND 5', name='check_hall'),
        CheckConstraint('leadership BETWEEN 0 AND 5', name='check_leadership'),
    )

class Shift(Base):
    __tablename__ = 'shifts'
    
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey('staffs.id'))
    date = Column(Date)
    start_time = Column(Time)
    end_time = Column(Time)
    
    staff = relationship('Staff', back_populates='shifts')
    shift_results = relationship("Shiftresult", back_populates="shift")

class Shiftresult(Base):
    __tablename__ = 'shift_results'
    
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey('staffs.id'))
    date = Column(Date)
    start_time = Column(Time)
    end_time = Column(Time)
    
    staff = relationship('Staff', back_populates='shift_results')
    shift_id = Column(Integer, ForeignKey("shifts.id"))
    shift = relationship("Shift", back_populates="shift_results")

class ShiftRequest(Base):
    __tablename__ = "shift_requests"

    id = Column(Integer, primary_key=True)
    staff_id = Column(Integer, ForeignKey("staffs.id"), nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)

    status = Column(
        Enum("×", "○", "time", name="status_enum"),
        nullable=True
    )
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    # Staffとのリレーションを修正
    staff = relationship("Staff", back_populates="shift_requests")

    @validates("start_time", "end_time")
    def validate_times(self, key, value):
        if self.staff is None or self.staff.store is None:
            return value  # 店舗が取得できない場合はバリデーションをスキップ

        store = self.staff.store
        if self.status == "○":
            if key == "start_time":
                return store.open_hours
            if key == "end_time":
                return store.close_hours
        return value

class Store(Base):
    __tablename__ = 'stores'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    open_hours = Column(Time, nullable=False)  # 修正：open_time → open_hours
    close_hours = Column(Time, nullable=False)  # 修正：close_time → close_hours
    staffs = relationship('Staff', back_populates='store')
    default_skill_requirements = relationship("StoreDefaultSkillRequirement", back_populates="store")
    skill_overrides = relationship("StoreSkillOverride", back_populates="store")

class StoreDefaultSkillRequirement(Base):
    __tablename__ = "store_default_skill_requirements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    day_type = Column(String(20), nullable=False)  # "平日", "金曜", "土曜", "日曜"
    hour = Column(Integer, nullable=False)  # 0〜23

    kitchen_a = Column(Integer, default=0, nullable=False)
    kitchen_b = Column(Integer, default=0, nullable=False)
    drink = Column(Integer, default=0, nullable=False)
    hall = Column(Integer, default=0, nullable=False)
    leadership = Column(Integer, default=0, nullable=False)
    store = relationship("Store", back_populates="default_skill_requirements")

class StoreSkillOverride(Base):
    __tablename__ = "store_skill_overrides"

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    date = Column(Date, nullable=False)
    hour = Column(Integer, nullable=False)  # 0〜23
    kitchen_a = Column(Integer, default=0, nullable=False)
    kitchen_b = Column(Integer, default=0, nullable=False)
    drink = Column(Integer, default=0, nullable=False)
    hall = Column(Integer, default=0, nullable=False)
    leadership = Column(Integer, default=0, nullable=False)
    store = relationship("Store", back_populates="skill_overrides")