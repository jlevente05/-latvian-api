from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import supabase

router = APIRouter()

class SignUpRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

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
        return {
            "access_token": response.session.access_token,
            "user": response.user
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