from sqlalchemy import Column, Integer, String, ForeignKey, Enum, CheckConstraint, Time, Boolean
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

    kitchen_a = Column(
        Enum("A", "B", "C", name="kitchen_a_enum"),
        default="C",
        nullable=False
    )
    kitchen_b = Column(
        Enum("A", "B", "C", name="kitchen_b_enum"),
        default="C",
        nullable=False
    )
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
        CheckConstraint('leadership BETWEEN 0 AND 5', name='check_leadership'),
        CheckConstraint('hall BETWEEN 0 AND 5', name='check_hall')
    )

class Shift(Base):
    __tablename__ = 'shifts'

    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey('staffs.id'))
    date = Column(Integer, nullable=False)
    start_time = Column(Integer, nullable=False)
    end_time = Column(Integer, nullable=False)

    staff = relationship('Staff', back_populates='shifts')
    shift_results = relationship("Shiftresult", back_populates="shift")

class Shiftresult(Base):
    __tablename__ = 'shift_results'
    
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey('staffs.id'))
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)
    start_time = Column(Integer, nullable=False) 
    end_time = Column(Integer, nullable=False) 
    
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
    start_time = Column(Integer, nullable=True)
    end_time = Column(Integer, nullable=True)
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
    open_hours = Column(Integer, nullable=False) 
    close_hours = Column(Integer, nullable=False) 
    staffs = relationship('Staff', back_populates='store')
    default_skill_requirements = relationship("StoreDefaultSkillRequirement", back_populates="store")
    shift_patterns = relationship("ShiftPattern", back_populates="store", cascade="all, delete-orphan")

class StoreDefaultSkillRequirement(Base):
    __tablename__ = "store_default_skill_requirements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    day_type = Column(
        Enum("平日", "金曜日", "土曜日","日曜日", name="day_type_enum"),
        nullable=False
    )
    peak_start_hour = Column(Integer, nullable=False)
    peak_end_hour = Column(Integer, nullable=False)

    kitchen_a = Column(
        Enum("A", "B", "C", name="kitchen_a_enum"),
        default="C",
        nullable=False
    )
    kitchen_b = Column(
        Enum("A", "B", "C", name="kitchen_b_enum"),
        default="C",
        nullable=False
    )
    hall = Column(Integer, default=0, nullable=False)
    leadership = Column(Integer, default=0, nullable=False)
    store = relationship("Store", back_populates="default_skill_requirements")
    peak_people = Column(Integer, default=0, nullable=False)
    open_people = Column(Integer, default=0, nullable=False)
    close_people = Column(Integer, default=0, nullable=False)

class ShiftPattern(Base):
    __tablename__ = "shift_patterns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    name = Column(String(255), nullable=False)
    start_time = Column(Integer, nullable=False) 
    end_time = Column(Integer, nullable=False)
    is_fulltime = Column(Boolean, default=False)
    default = Column(Boolean, default=False)

    store = relationship("Store", back_populates="shift_patterns")