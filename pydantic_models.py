from pydantic import BaseModel
from typing import Optional, List
from datetime import date, time
from enum import Enum


class GenderEnum(str, Enum):
    男 = "男"
    女 = "女"


class EmploymentTypeEnum(str, Enum):
    社員 = "社員"
    バイト = "バイト"
    未成年バイト = "未成年バイト"


class ShiftBase(BaseModel):
    date: date
    start_time: time
    end_time: time


class ShiftCreate(ShiftBase):
    staff_id: int


class Shift(ShiftBase):
    id: int
    staff_id: int

    class Config:
        orm_mode = True


class ShiftRequestBase(BaseModel):
    year: int
    month: int
    day: int
    status: str
    start_time: Optional[time]
    end_time: Optional[time]


class ShiftRequestCreate(ShiftRequestBase):
    staff_id: int


class ShiftRequest(ShiftRequestBase):
    id: int
    staff_id: int

    class Config:
        orm_mode = True


class StaffBase(BaseModel):
    name: str
    gender: GenderEnum
    desired_days: int
    kitchen_a: int
    kitchen_b: int
    drink: int
    hall: int
    leadership: int
    employment_type: EmploymentTypeEnum
    login_code: str


class StaffCreate(StaffBase):
    password: str
    store_id: int


class Staff(StaffBase):
    id: int
    store_id: int

    class Config:
        orm_mode = True


class StoreBase(BaseModel):
    name: str
    open_hours: str
    close_hours: str


class StoreCreate(StoreBase):
    pass


class Store(StoreBase):
    id: int

    class Config:
        orm_mode = True


class StaffOut(BaseModel):
    id: int
    name: str
    gender: Optional[str] = None
    employment_type: str
    store_id: int
    kitchen_a: str
    kitchen_b: str
    hall: int
    leadership: int
    login_code: str
    password: str

    model_config = {
        "from_attributes": True
    }
