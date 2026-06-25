from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from app.database import supabase
from anthropic import Anthropic
import os
import json
import traceback

router = APIRouter()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def get_token(authorization: str):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    return authorization.replace("Bearer ", "").strip()

class ExerciseRequest(BaseModel):
    level: str
    category: str = None
    weak_spots: list[str] = []
    native_lang: str = "hu"

class ConversationMessage(BaseModel):
    role: str
    content: str

class ConversationRequest(BaseModel):
    messages: list[ConversationMessage]
    topic: str = "general"
    native_lang: str = "hu"

class LevelTestRequest(BaseModel):
    level: str
    native_lang: str = "hu"

@router.post("/exercise")
def generate_exercise(data: ExerciseRequest, authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)

        if data.native_lang == "hu":
            teacher_desc = "Latvian language teacher for a Hungarian native speaker"
            instruction = "Instructions in Hungarian, questions can be in either language"
        else:
            teacher_desc = "Hungarian language teacher for a Latvian native speaker"
            instruction = "Instructions in Latvian, questions can be in either language"

        weak_spots_text = ""
        if data.weak_spots:
            weak_spots_text = f"The student struggles with: {', '.join(data.weak_spots)}. Focus on these."

        prompt = f"""You are a {teacher_desc} at {data.level} level.
Generate one exercise. {instruction}.
Return only raw JSON, no markdown, no code blocks:
{{
  "type": "fill_in_the_blank",
  "instruction_hu": "instruction in the native language",
  "question": "the exercise question",
  "answer": "the correct answer",
  "explanation_hu": "brief grammar explanation in the native language",
  "options": []
}}
Type must be one of: fill_in_the_blank, translate, multiple_choice.
For multiple_choice, options must have exactly 4 items.
For other types, options must be empty list.
{weak_spots_text}
Category: {data.category or "general vocabulary"}"""

        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        exercise = json.loads(raw.strip())
        return exercise
    except Exception as e:
        print("EXERCISE ERROR:", traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/conversation")
def conversation(data: ConversationRequest, authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)

        if data.native_lang == "hu":
            system_prompt = f"""You are a friendly Latvian conversation partner.
The user is a Hungarian native speaker learning Latvian.
Topic: {data.topic}
- Respond naturally in Latvian
- Keep sentences simple and clear
- After your Latvian response, add a line break then write "💡 " followed by a brief Hungarian translation
- If the user makes a grammar mistake, gently correct it at the end with "✏️ " prefix"""
        else:
            system_prompt = f"""You are a friendly Hungarian conversation partner.
The user is a Latvian native speaker learning Hungarian.
Topic: {data.topic}
- Respond naturally in Hungarian
- Keep sentences simple and clear
- After your Hungarian response, add a line break then write "💡 " followed by a brief Latvian translation
- If the user makes a grammar mistake, gently correct it at the end with "✏️ " prefix"""

        messages = [{"role": m.role, "content": m.content} for m in data.messages]

        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1000,
            system=system_prompt,
            messages=messages
        )

        return {"response": response.content[0].text}
    except Exception as e:
        print("CONVERSATION ERROR:", traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/level-test")
def generate_level_test(data: LevelTestRequest, authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)

        if data.native_lang == "hu":
            lang_desc = "Hungarian native speaker learning Latvian"
            instruction = "Instructions and explanations in Hungarian"
        else:
            lang_desc = "Latvian native speaker learning Hungarian"
            instruction = "Instructions and explanations in Latvian"

        prompt = f"""You are a language teacher testing a {lang_desc} at {data.level} level.
Generate exactly 10 multiple choice questions covering vocabulary and grammar for {data.level} level.
{instruction}.
Return only raw JSON array, no markdown:
[
  {{
    "question": "the question",
    "options": ["option1", "option2", "option3", "option4"],
    "answer": "the correct option exactly as written",
    "explanation": "brief explanation in native language"
  }}
]"""

        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        questions = json.loads(raw.strip())
        return {"questions": questions, "level": data.level}
    except Exception as e:
        print("LEVEL TEST ERROR:", traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))