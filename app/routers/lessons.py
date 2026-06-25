from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from app.database import supabase
from anthropic import Anthropic
import os
import json
import traceback

router = APIRouter()
claude = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

LEVELS = ["A1", "A2", "B1", "B2"]

def get_token(authorization: str):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    return authorization.replace("Bearer ", "").strip()

def ensure_vocabulary(level: str, topic: str):
    existing = supabase.table("vocabulary")\
        .select("id")\
        .eq("level", level)\
        .eq("category", topic)\
        .execute()

    if len(existing.data) >= 20:
        return

    prompt = f"""Generate exactly 30 Latvian-Hungarian word pairs for level {level}, category: {topic}.
Return only raw JSON array, no markdown, no code blocks:
[
  {{
    "latvian": "word in latvian",
    "hungarian": "word in hungarian",
    "level": "{level}",
    "category": "{topic}",
    "grammar_notes": "brief grammar note in hungarian"
  }}
]
Make sure all words are accurate and appropriate for {level} level."""

    response = claude.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    words = json.loads(raw.strip())
    supabase.table("vocabulary").insert(words).execute()


@router.get("/tree")
def get_lesson_tree(authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        profile = supabase.table("users")\
            .select("current_level, native_lang")\
            .eq("id", user_id)\
            .execute()
        current_level = profile.data[0].get("current_level") or "A1"

        all_lessons = supabase.table("lessons")\
            .select("*")\
            .order("level")\
            .order("unit")\
            .order("position")\
            .execute()

        completions = supabase.table("lesson_completions")\
            .select("lesson_id, score")\
            .eq("user_id", user_id)\
            .execute()
        completed_ids = {c["lesson_id"]: c["score"] for c in completions.data}

        level_tests = supabase.table("level_tests")\
            .select("level, passed")\
            .eq("user_id", user_id)\
            .execute()
        passed_levels = {t["level"] for t in level_tests.data if t["passed"]}

        tree = {}
        for lesson in all_lessons.data:
            level = lesson["level"]
            unit = lesson["unit"]

            if level not in tree:
                tree[level] = {}
            if unit not in tree[level]:
                tree[level][unit] = {
                    "unit": unit,
                    "topic": lesson["topic"],
                    "lessons": [],
                    "locked": False,
                }

            level_index = LEVELS.index(level) if level in LEVELS else 99
            current_index = LEVELS.index(current_level) if current_level in LEVELS else 0
            is_locked = level_index > current_index
            is_completed = lesson["id"] in completed_ids

            tree[level][unit]["lessons"].append({
                "id": lesson["id"],
                "position": lesson["position"],
                "type": lesson["type"],
                "topic": lesson["topic"],
                "completed": is_completed,
                "score": completed_ids.get(lesson["id"]),
                "locked": is_locked,
            })
            tree[level][unit]["locked"] = is_locked

        result = []
        for level in LEVELS:
            if level in tree:
                level_index = LEVELS.index(level)
                current_index = LEVELS.index(current_level)
                result.append({
                    "level": level,
                    "locked": level_index > current_index,
                    "passed": level in passed_levels,
                    "units": list(tree[level].values()),
                })

        return result
    except Exception as e:
        print("TREE ERROR:", traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{lesson_id}")
def get_lesson(lesson_id: str, authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        lesson = supabase.table("lessons")\
            .select("*")\
            .eq("id", lesson_id)\
            .execute()

        if not lesson.data:
            raise HTTPException(status_code=404, detail="Lesson not found")

        l = lesson.data[0]
        ensure_vocabulary(l["level"], l["topic"])

        vocab = supabase.table("vocabulary")\
            .select("*")\
            .eq("level", l["level"])\
            .eq("category", l["topic"])\
            .limit(20)\
            .execute()

        profile = supabase.table("users")\
            .select("native_lang")\
            .eq("id", user_id)\
            .execute()
        native_lang = profile.data[0].get("native_lang") or "hu"

        return {
            "lesson": l,
            "vocabulary": vocab.data,
            "native_lang": native_lang,
        }
    except Exception as e:
        print("LESSON ERROR:", traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))


class LessonComplete(BaseModel):
    score: int
    hearts_remaining: int
    xp_earned: int

@router.post("/{lesson_id}/complete")
def complete_lesson(lesson_id: str, data: LessonComplete, authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        existing = supabase.table("lesson_completions")\
            .select("id")\
            .eq("user_id", user_id)\
            .eq("lesson_id", lesson_id)\
            .execute()

        if existing.data:
            supabase.table("lesson_completions").update({
                "score": data.score,
                "hearts_remaining": data.hearts_remaining,
            }).eq("id", existing.data[0]["id"]).execute()
        else:
            supabase.table("lesson_completions").insert({
                "user_id": user_id,
                "lesson_id": lesson_id,
                "score": data.score,
                "hearts_remaining": data.hearts_remaining,
            }).execute()

        profile = supabase.table("users").select("xp").eq("id", user_id).execute()
        current_xp = profile.data[0].get("xp") or 0
        new_xp = current_xp + data.xp_earned

        supabase.table("users").update({
            "xp": new_xp,
            "hearts": data.hearts_remaining,
        }).eq("id", user_id).execute()

        lesson = supabase.table("lessons").select("*").eq("id", lesson_id).execute()
        l = lesson.data[0]

        unit_lessons = supabase.table("lessons")\
            .select("id")\
            .eq("level", l["level"])\
            .eq("unit", l["unit"])\
            .execute()
        unit_lesson_ids = {ul["id"] for ul in unit_lessons.data}

        unit_completions = supabase.table("lesson_completions")\
            .select("lesson_id")\
            .eq("user_id", user_id)\
            .execute()
        completed_in_unit = {c["lesson_id"] for c in unit_completions.data if c["lesson_id"] in unit_lesson_ids}

        unit_complete = unit_lesson_ids == completed_in_unit

        all_lessons = supabase.table("lessons")\
            .select("id")\
            .eq("level", l["level"])\
            .execute()
        all_level_ids = {al["id"] for al in all_lessons.data}

        all_completions = supabase.table("lesson_completions")\
            .select("lesson_id")\
            .eq("user_id", user_id)\
            .execute()
        completed_level = {c["lesson_id"] for c in all_completions.data if c["lesson_id"] in all_level_ids}
        level_complete = all_level_ids == completed_level

        return {
            "success": True,
            "unit_complete": unit_complete,
            "level_complete": level_complete,
            "xp_total": new_xp,
        }
    except Exception as e:
        print("COMPLETE ERROR:", traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))


class LevelTestSubmit(BaseModel):
    level: str
    score: int

@router.post("/level-test/submit")
def submit_level_test(data: LevelTestSubmit, authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        passed = data.score >= 80

        supabase.table("level_tests").insert({
            "user_id": user_id,
            "level": data.level,
            "score": data.score,
            "passed": passed,
        }).execute()

        if passed:
            level_index = LEVELS.index(data.level) if data.level in LEVELS else -1
            if level_index >= 0 and level_index < len(LEVELS) - 1:
                next_level = LEVELS[level_index + 1]
                supabase.table("users").update({
                    "current_level": next_level
                }).eq("id", user_id).execute()

        return {"passed": passed, "score": data.score}
    except Exception as e:
        print("LEVEL TEST ERROR:", traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))