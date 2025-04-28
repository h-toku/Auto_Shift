# schemas.py
from pydantic import BaseModel

class LoginRequest(BaseModel):
    login_code: str
    password: str
