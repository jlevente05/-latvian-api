from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from app.database import supabase
from anthropic import Anthropic
import os
import json
import traceback

router = APIRouter()
claude = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

def get_token(authorization: str):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    return authorization.replace("Bearer ", "").strip()

def parse_json(text: str):
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


@router.get("/curriculum")
def get_curriculum(authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        profile = supabase.table("users")\
            .select("current_level, native_lang")\
            .eq("id", user_id)\
            .execute()
        current_level = profile.data[0].get("current_level") or "A1"
        native_lang = profile.data[0].get("native_lang") or "hu"

        all_units = supabase.table("units")\
            .select("*")\
            .order("order_index")\
            .execute()

        progress = supabase.table("unit_progress")\
            .select("*")\
            .eq("user_id", user_id)\
            .execute()
        progress_map = {p["unit_id"]: p for p in progress.data}

        current_index = LEVELS.index(current_level) if current_level in LEVELS else 0

        result = []
        for unit in all_units.data:
            level = unit["level"]
            level_index = LEVELS.index(level) if level in LEVELS else 99
            is_locked = level_index > current_index
            is_coming_soon = level in ["C1", "C2"]

            unit_prog = progress_map.get(unit["id"])

            result.append({
                "id": unit["id"],
                "level": level,
                "unit_number": unit["unit_number"],
                "title_en": unit["title_en"],
                "title_lv": unit["title_lv"],
                "title_hu": unit["title_hu"],
                "description": unit["description"],
                "grammar_focus": unit["grammar_focus"],
                "estimated_minutes": unit["estimated_minutes"],
                "order_index": unit["order_index"],
                "locked": is_locked,
                "coming_soon": is_coming_soon,
                "completed": unit_prog.get("test_passed", False) if unit_prog else False,
                "progress": {
                    "dialogue": unit_prog.get("dialogue_completed", False) if unit_prog else False,
                    "vocabulary": unit_prog.get("vocabulary_completed", False) if unit_prog else False,
                    "grammar": unit_prog.get("grammar_completed", False) if unit_prog else False,
                    "reading": unit_prog.get("reading_completed", False) if unit_prog else False,
                    "exercises_score": unit_prog.get("exercises_score") if unit_prog else None,
                    "conversation": unit_prog.get("conversation_completed", False) if unit_prog else False,
                    "test_score": unit_prog.get("test_score") if unit_prog else None,
                    "test_passed": unit_prog.get("test_passed", False) if unit_prog else False,
                } if unit_prog else None,
            })

        return {"curriculum": result, "current_level": current_level, "native_lang": native_lang}
    except Exception as e:
        print("CURRICULUM ERROR:", traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{unit_id}")
def get_unit(unit_id: str, authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        unit = supabase.table("units").select("*").eq("id", unit_id).execute()
        if not unit.data:
            raise HTTPException(status_code=404, detail="Unit not found")
        u = unit.data[0]

        profile = supabase.table("users")\
            .select("native_lang")\
            .eq("id", user_id)\
            .execute()
        native_lang = profile.data[0].get("native_lang") or "hu"

        dialogue = supabase.table("dialogues").select("*").eq("unit_id", unit_id).execute()
        grammar = supabase.table("grammar_points")\
            .select("*")\
            .eq("unit_id", unit_id)\
            .order("order_index")\
            .execute()
        reading = supabase.table("reading_texts").select("*").eq("unit_id", unit_id).execute()
        exercises = supabase.table("unit_exercises")\
            .select("*")\
            .eq("unit_id", unit_id)\
            .order("order_index")\
            .execute()
        vocabulary = supabase.table("vocabulary")\
            .select("*")\
            .eq("unit_id", unit_id)\
            .execute()

        unit_prog = supabase.table("unit_progress")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("unit_id", unit_id)\
            .execute()

        if not unit_prog.data:
            supabase.table("unit_progress").insert({
                "user_id": user_id,
                "unit_id": unit_id,
            }).execute()

        return {
            "unit": u,
            "native_lang": native_lang,
            "dialogue": dialogue.data[0] if dialogue.data else None,
            "grammar_points": grammar.data,
            "reading_text": reading.data[0] if reading.data else None,
            "exercises": exercises.data,
            "vocabulary": vocabulary.data,
            "progress": unit_prog.data[0] if unit_prog.data else None,
        }
    except Exception as e:
        print("UNIT ERROR:", traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))


class SectionComplete(BaseModel):
    section: str

@router.post("/{unit_id}/section-complete")
def complete_section(unit_id: str, data: SectionComplete, authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        valid_sections = ["dialogue", "vocabulary", "grammar", "reading", "conversation"]
        if data.section not in valid_sections:
            raise HTTPException(status_code=400, detail="Invalid section")

        field = f"{data.section}_completed"

        existing = supabase.table("unit_progress")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("unit_id", unit_id)\
            .execute()

        if existing.data:
            supabase.table("unit_progress")\
                .update({field: True})\
                .eq("user_id", user_id)\
                .eq("unit_id", unit_id)\
                .execute()
        else:
            supabase.table("unit_progress").insert({
                "user_id": user_id,
                "unit_id": unit_id,
                field: True,
            }).execute()

        return {"success": True, "section": data.section}
    except Exception as e:
        print("SECTION ERROR:", traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))


class ExerciseSubmit(BaseModel):
    score: int

@router.post("/{unit_id}/exercises-complete")
def complete_exercises(unit_id: str, data: ExerciseSubmit, authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        existing = supabase.table("unit_progress")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("unit_id", unit_id)\
            .execute()

        if existing.data:
            supabase.table("unit_progress")\
                .update({"exercises_score": data.score})\
                .eq("user_id", user_id)\
                .eq("unit_id", unit_id)\
                .execute()
        else:
            supabase.table("unit_progress").insert({
                "user_id": user_id,
                "unit_id": unit_id,
                "exercises_score": data.score,
            }).execute()

        xp_earned = data.score * 2
        profile = supabase.table("users").select("xp").eq("id", user_id).execute()
        current_xp = profile.data[0].get("xp") or 0
        supabase.table("users").update({"xp": current_xp + xp_earned}).eq("id", user_id).execute()

        return {"success": True, "score": data.score, "xp_earned": xp_earned}
    except Exception as e:
        print("EXERCISES ERROR:", traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))


class TestSubmit(BaseModel):
    score: int

@router.post("/{unit_id}/test")
def submit_unit_test(unit_id: str, data: TestSubmit, authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        passed = data.score >= 70

        existing = supabase.table("unit_progress")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("unit_id", unit_id)\
            .execute()

        update_data = {
            "test_score": data.score,
            "test_passed": passed,
        }
        if passed:
            from datetime import datetime
            update_data["completed_at"] = datetime.utcnow().isoformat()

        if existing.data:
            supabase.table("unit_progress")\
                .update(update_data)\
                .eq("user_id", user_id)\
                .eq("unit_id", unit_id)\
                .execute()
        else:
            supabase.table("unit_progress").insert({
                "user_id": user_id,
                "unit_id": unit_id,
                **update_data,
            }).execute()

        xp_earned = 100 if passed else 20
        profile = supabase.table("users").select("xp, current_level").eq("id", user_id).execute()
        current_xp = profile.data[0].get("xp") or 0
        supabase.table("users").update({"xp": current_xp + xp_earned}).eq("id", user_id).execute()

        return {"success": True, "passed": passed, "score": data.score, "xp_earned": xp_earned}
    except Exception as e:
        print("TEST ERROR:", traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))


class GrammarMistake(BaseModel):
    grammar_point_id: str

@router.post("/grammar-mistake")
def log_grammar_mistake(data: GrammarMistake, authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        from datetime import datetime
        existing = supabase.table("grammar_mistakes")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("grammar_point_id", data.grammar_point_id)\
            .execute()

        if existing.data:
            supabase.table("grammar_mistakes")\
                .update({
                    "mistake_count": existing.data[0]["mistake_count"] + 1,
                    "last_seen": datetime.utcnow().isoformat(),
                })\
                .eq("id", existing.data[0]["id"])\
                .execute()
        else:
            supabase.table("grammar_mistakes").insert({
                "user_id": user_id,
                "grammar_point_id": data.grammar_point_id,
                "mistake_count": 1,
                "last_seen": datetime.utcnow().isoformat(),
            }).execute()

        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/grammar-mistakes/my")
def get_my_grammar_mistakes(authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        mistakes = supabase.table("grammar_mistakes")\
            .select("*, grammar_points(*)")\
            .eq("user_id", user_id)\
            .order("mistake_count", desc=True)\
            .limit(10)\
            .execute()

        return mistakes.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))