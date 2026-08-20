from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from app.database import supabase
from typing import Optional, List

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

class OnboardingRequest(BaseModel):
    display_name: str
    native_lang: str
    prior_level: Optional[str] = "beginner"
    learning_reasons: Optional[List[str]] = []
    daily_goal: Optional[str] = "15"

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
            .select("native_lang, current_level, streak, xp, hearts, display_name, onboarding_complete")\
            .eq("id", user_id)\
            .execute()

        native_lang = "hu"
        current_level = "A1"
        streak = 0
        xp = 0
        hearts = 5
        display_name = None
        onboarding_complete = False

        if profile.data:
            native_lang = profile.data[0].get("native_lang") or "hu"
            current_level = profile.data[0].get("current_level") or "A1"
            streak = profile.data[0].get("streak") or 0
            xp = profile.data[0].get("xp") or 0
            hearts = profile.data[0].get("hearts") or 5
            display_name = profile.data[0].get("display_name")
            onboarding_complete = profile.data[0].get("onboarding_complete") or False

        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "user": response.user,
            "native_lang": native_lang,
            "current_level": current_level,
            "streak": streak,
            "xp": xp,
            "hearts": hearts,
            "display_name": display_name,
            "onboarding_complete": onboarding_complete,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/refresh")
def refresh_token(authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        response = supabase.auth.refresh_session(token)
        return {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
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

@router.post("/onboarding")
def complete_onboarding(data: OnboardingRequest, authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)
        user_id = user.user.id
        supabase.table("users").update({
            "display_name": data.display_name,
            "native_lang": data.native_lang,
            "prior_level": data.prior_level,
            "learning_reason": data.learning_reasons,
            "daily_goal": data.daily_goal,
            "onboarding_complete": True,
        }).eq("id", user_id).execute()
        return {"message": "Onboarding complete"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))