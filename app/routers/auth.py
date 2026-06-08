from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from app.database import supabase

router = APIRouter()

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
        profile = supabase.table("users").select("native_lang, current_level").eq("id", user_id).execute()
        native_lang = profile.data[0]["native_lang"] if profile.data else "hu"
        current_level = profile.data[0]["current_level"] if profile.data else "A1"
        return {
            "access_token": response.session.access_token,
            "user": response.user,
            "native_lang": native_lang,
            "current_level": current_level
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
        token = authorization.replace("Bearer ", "")
        user = supabase.auth.get_user(token)
        user_id = user.user.id
        supabase.table("users").update({"native_lang": data.native_lang}).eq("id", user_id).execute()
        return {"message": "Language set successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))