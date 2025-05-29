from fastapi import (
    FastAPI, HTTPException, Depends, Request, status,
)
from sqlalchemy.orm import Session
from pydantic_models import StaffOut
from models import (
    Store, Staff, ShiftRequest, Shift, Shiftresult,
    StoreDefaultSkillRequirement, ShiftPattern,
    StaffRejectionHistory
)
from database import SessionLocal

def get_common_context(request: Request):
    user_logged_in = request.session.get('user_logged_in', False)
    user_name = request.session.get('user_name') if user_logged_in else None
    store_name = request.session.get('store_name') if user_logged_in else None
    employment_type = request.session.get('employment_type') if user_logged_in else None
    store_id = request.session.get('store_id') if user_logged_in else None

    login_button = {"name": "ログイン画面へ", "url": "/login"} if not user_logged_in else {
        "name": "ログアウト", "url": "/logout"
    }

    return {
        "user_logged_in": user_logged_in,
        "user_name": user_name,
        "store_name": store_name,
        "employment_type": employment_type,
        "login_button": login_button,
        "store_id": store_id
    }

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_staff(request: Request, db: Session = Depends(get_db)):
    user_name = request.session.get("user_name")
    if not user_name:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ログインが必要です"
        )
    staff = db.query(Staff).filter(Staff.name == user_name).first()
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="スタッフが見つかりません"
        )
    return staff


def generate_time_options(request, open_time, close_time):
    options = []
    user_logged_in = request.session.get('user_logged_in', False)
    employment_type = request.session.get('employment_type') if user_logged_in else None
    if employment_type == "未成年バイト":
        for hour in range(open_time, 11):
            options.append(hour)
    else:
        for hour in range(open_time, close_time + 1):
            options.append(hour)
    return options