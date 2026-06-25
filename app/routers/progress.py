from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from app.database import supabase
from datetime import datetime, timedelta

router = APIRouter()

def get_token(authorization: str):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    return authorization.replace("Bearer ", "").strip()

class ReviewResult(BaseModel):
    vocab_id: str
    quality: int

def sm2(ease_factor: float, interval: int, reps: int, quality: int):
    if quality < 3:
        reps = 0
        interval = 1
    else:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = round(interval * ease_factor)
        reps += 1

    ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ease_factor = max(1.3, ease_factor)
    return ease_factor, interval, reps

@router.post("/review")
def submit_review(data: ReviewResult, authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        existing = supabase.table("progress")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("vocab_id", data.vocab_id)\
            .execute()

        if existing.data:
            row = existing.data[0]
            new_ef, new_interval, new_reps = sm2(
                row["ease_factor"], row["interval_days"], row["reps"], data.quality
            )
            next_review = datetime.utcnow() + timedelta(days=new_interval)
            supabase.table("progress").update({
                "ease_factor": new_ef,
                "interval_days": new_interval,
                "reps": new_reps,
                "next_review": next_review.isoformat(),
                "last_seen": datetime.utcnow().isoformat()
            }).eq("id", row["id"]).execute()
        else:
            new_ef, new_interval, new_reps = sm2(2.5, 1, 0, data.quality)
            next_review = datetime.utcnow() + timedelta(days=new_interval)
            supabase.table("progress").insert({
                "user_id": user_id,
                "vocab_id": data.vocab_id,
                "ease_factor": new_ef,
                "interval_days": new_interval,
                "reps": new_reps,
                "next_review": next_review.isoformat(),
                "last_seen": datetime.utcnow().isoformat()
            }).execute()

        return {"message": "Review saved"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/stats")
def get_stats(authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        response = supabase.table("progress")\
            .select("*")\
            .eq("user_id", user_id)\
            .execute()

        total = len(response.data)
        due = sum(1 for r in response.data if r["next_review"] <= datetime.utcnow().isoformat())

        return {"total_words_seen": total, "due_for_review": due}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))