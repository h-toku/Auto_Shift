# schemas.py
from pydantic import BaseModel
from typing import Optional
from datetime import time
class LoginRequest(BaseModel):
    login_code: str
    password: str

class ShiftRequestUpdate(BaseModel):
    staff_id: int
    store_id: int
    year: int
    month: int
    day: int
    status: str  # "○" または "×" または "time"
    start_time: Optional[time] = None  # statusが"time"のときに使用
    end_time: Optional[time] = None    # statusが"time"のときに使用