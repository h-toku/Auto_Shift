from fastapi import Request

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
