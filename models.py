from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Store(Base):
    __tablename__ = 'stores'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    
    staffs = relationship('Staff', secondary='staff_store')

class Staff(Base):
    __tablename__ = 'staffs'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    desired_days = Column(Integer, nullable=False)
    kitchen_a = Column(Integer, default=0)
    kitchen_b = Column(Integer, default=0)
    drink = Column(Integer, default=0)
    hall = Column(Integer, default=0)
    leadership = Column(Integer, default=0)
    employment_type = Column(String(50), nullable=False)  # "社員", "バイト", "未成年バイト"
    login_code = Column(String(50), unique=True, nullable=False)  # ログインコード
    password = Column(String(100), nullable=False)  # パスワード
    
    store_id = Column(Integer, ForeignKey('stores.id'))
    store = relationship("Store", back_populates="staffs")

class StaffStore(Base):
    __tablename__ = 'staff_store'

    id = Column(Integer, primary_key=True)
    staff_id = Column(Integer, ForeignKey('staffs.id'))
    store_id = Column(Integer, ForeignKey('stores.id'))
