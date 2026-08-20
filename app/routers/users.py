from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from app.database import supabase
from datetime import date, timedelta

router = APIRouter()

def get_token(authorization: str):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    return authorization.replace("Bearer ", "").strip()

class ActivityUpdate(BaseModel):
    xp_earned: int
    hearts_remaining: int

@router.get("/profile")
def get_profile(authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        profile = supabase.table("users").select("*").eq("id", user_id).execute()
        if not profile.data:
            raise HTTPException(status_code=404, detail="User not found")

        p = profile.data[0]

        words_learned = supabase.table("progress")\
            .select("id")\
            .eq("user_id", user_id)\
            .execute()

        units_completed = supabase.table("unit_progress")\
            .select("id")\
            .eq("user_id", user_id)\
            .eq("test_passed", True)\
            .execute()

        return {
            "email": user.user.email,
            "display_name": p.get("display_name"),
            "native_lang": p.get("native_lang") or "hu",
            "current_level": p.get("current_level") or "A1",
            "streak": p.get("streak") or 0,
            "xp": p.get("xp") or 0,
            "hearts": p.get("hearts") or 5,
            "words_learned": len(words_learned.data),
            "units_completed": len(units_completed.data),
            "daily_goal": p.get("daily_goal"),
            "learning_reason": p.get("learning_reason"),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/leaderboard")
def get_leaderboard(authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)

        users = supabase.table("users")\
            .select("id, display_name, email, xp, current_level, streak")\
            .order("xp", desc=True)\
            .execute()

        result = []
        for i, u in enumerate(users.data):
            result.append({
                "rank": i + 1,
                "display_name": u.get("display_name") or u.get("email", "").split("@")[0],
                "xp": u.get("xp") or 0,
                "current_level": u.get("current_level") or "A1",
                "streak": u.get("streak") or 0,
            })

        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/activity")
def update_activity(data: ActivityUpdate, authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        profile = supabase.table("users").select("*").eq("id", user_id).execute()
        p = profile.data[0]

        today = date.today()
        last_active = p.get("last_active")
        current_streak = p.get("streak") or 0

        if last_active:
            last_date = date.fromisoformat(str(last_active))
            if last_date == today:
                new_streak = current_streak
            elif last_date == today - timedelta(days=1):
                new_streak = current_streak + 1
            else:
                new_streak = 1
        else:
            new_streak = 1

        new_xp = (p.get("xp") or 0) + data.xp_earned

        supabase.table("users").update({
            "streak": new_streak,
            "last_active": today.isoformat(),
            "xp": new_xp,
            "hearts": data.hearts_remaining,
        }).eq("id", user_id).execute()

        return {
            "streak": new_streak,
            "xp": new_xp,
            "hearts": data.hearts_remaining,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/lose-heart")
def lose_heart(authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        profile = supabase.table("users").select("hearts").eq("id", user_id).execute()
        current_hearts = profile.data[0].get("hearts") or 5

        if current_hearts <= 0:
            raise HTTPException(status_code=400, detail="No hearts remaining")

        new_hearts = current_hearts - 1
        supabase.table("users").update({"hearts": new_hearts}).eq("id", user_id).execute()

        return {"hearts": new_hearts}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/refill-hearts")
def refill_hearts(authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        today = date.today()
        profile = supabase.table("users").select("hearts_last_refill").eq("id", user_id).execute()
        last_refill = profile.data[0].get("hearts_last_refill")

        if last_refill and date.fromisoformat(str(last_refill)) == today:
            raise HTTPException(status_code=400, detail="Hearts already refilled today")

        supabase.table("users").update({
            "hearts": 5,
            "hearts_last_refill": today.isoformat()
        }).eq("id", user_id).execute()

        return {"hearts": 5}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))