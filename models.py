from sqlalchemy import Column, Integer, String, ForeignKey, Enum, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Store(Base):
    __tablename__ = 'stores'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    
    staffs = relationship('Staff', back_populates='store')

class Staff(Base):
    __tablename__ = 'staffs'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
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

    # 0〜5に制限をかける
    __table_args__ = (
        CheckConstraint('kitchen_a BETWEEN 0 AND 5', name='check_kitchen_a'),
        CheckConstraint('kitchen_b BETWEEN 0 AND 5', name='check_kitchen_b'),
        CheckConstraint('drink BETWEEN 0 AND 5', name='check_drink'),
        CheckConstraint('hall BETWEEN 0 AND 5', name='check_hall'),
        CheckConstraint('leadership BETWEEN 0 AND 5', name='check_leadership'),
    )
