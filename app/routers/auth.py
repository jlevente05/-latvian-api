from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from app.database import supabase

router = APIRouter()

def get_token(authorization: str):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    return authorization.replace("Bearer ", "").strip()

class SignUpRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class SetLanguageRequest(BaseModel):
    native_lang: str

@router.post("/signup")
def signup(data: SignUpRequest):
    try:
        response = supabase.auth.sign_up({
            "email": data.email,
            "password": data.password
        })
        return {"message": "Account created successfully", "user": response.user}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login")
def login(data: LoginRequest):
    try:
        response = supabase.auth.sign_in_with_password({
            "email": data.email,
            "password": data.password
        })
        user_id = response.user.id
        profile = supabase.table("users")\
            .select("native_lang, current_level, streak, xp, hearts")\
            .eq("id", user_id)\
            .execute()

        native_lang = "hu"
        current_level = "A1"
        streak = 0
        xp = 0
        hearts = 5

        if profile.data:
            native_lang = profile.data[0].get("native_lang") or "hu"
            current_level = profile.data[0].get("current_level") or "A1"
            streak = profile.data[0].get("streak") or 0
            xp = profile.data[0].get("xp") or 0
            hearts = profile.data[0].get("hearts") or 5

        return {
            "access_token": response.session.access_token,
            "user": response.user,
            "native_lang": native_lang,
            "current_level": current_level,
            "streak": streak,
            "xp": xp,
            "hearts": hearts,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/logout")
def logout():
    try:
        supabase.auth.sign_out()
        return {"message": "Logged out successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/set-language")
def set_language(data: SetLanguageRequest, authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)
        user_id = user.user.id
        supabase.table("users")\
            .update({"native_lang": data.native_lang})\
            .eq("id", user_id)\
            .execute()
        return {"message": "Language set successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))