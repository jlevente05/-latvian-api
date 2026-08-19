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

def parse_json(text: str):
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

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
    unit_id: str = None

class TeacherRequest(BaseModel):
    unit_id: str
    section: str
    message: str
    native_lang: str = "hu"
    grammar_mistakes: list[str] = []

class GradeRequest(BaseModel):
    question: str
    user_answer: str
    correct_answer: str
    native_lang: str = "hu"
    explanation: str = ""

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
            instruction = "Instructions in Hungarian"
        else:
            teacher_desc = "Hungarian language teacher for a Latvian native speaker"
            instruction = "Instructions in Latvian"

        weak_spots_text = ""
        if data.weak_spots:
            weak_spots_text = f"The student struggles with: {', '.join(data.weak_spots)}. Focus on these."

        prompt = f"""You are a {teacher_desc} at {data.level} level for the Tilts language learning app.
Generate one exercise. {instruction}.
Return only raw JSON, no markdown:
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

        exercise = parse_json(response.content[0].text)
        return exercise
    except Exception as e:
        print("EXERCISE ERROR:", traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/teacher")
def ai_teacher(data: TeacherRequest, authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        unit = supabase.table("units").select("*").eq("id", data.unit_id).execute()
        if not unit.data:
            raise HTTPException(status_code=404, detail="Unit not found")
        u = unit.data[0]

        mistakes_text = ""
        if data.grammar_mistakes:
            mistakes_text = f"The student has recurring mistakes with: {', '.join(data.grammar_mistakes)}."

        if data.native_lang == "hu":
            system = f"""You are an expert Latvian language teacher for Hungarian speakers on the Tilts app.
You are helping a student with Unit {u['unit_number']}: "{u['title_en']}" at {u['level']} level.
Topic: {u['description']}
Grammar focus: {u['grammar_focus']}
Current section: {data.section}
{mistakes_text}

Rules:
- Always respond in Hungarian (the student's native language) unless demonstrating Latvian
- Be encouraging, patient, and clear
- Always anchor explanations to the unit's topic and vocabulary
- Use examples from the unit's dialogue when possible
- When showing Latvian, always provide Hungarian translation
- Keep responses concise but thorough"""
        else:
            system = f"""You are an expert Hungarian language teacher for Latvian speakers on the Tilts app.
You are helping a student with Unit {u['unit_number']}: "{u['title_en']}" at {u['level']} level.
Topic: {u['description']}
Grammar focus: {u['grammar_focus']}
Current section: {data.section}
{mistakes_text}

Rules:
- Always respond in Latvian (the student's native language) unless demonstrating Hungarian
- Be encouraging, patient, and clear
- Always anchor explanations to the unit's topic and vocabulary
- When showing Hungarian, always provide Latvian translation
- Keep responses concise but thorough"""

        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1000,
            system=system,
            messages=[{"role": "user", "content": data.message}]
        )

        return {"response": response.content[0].text}
    except Exception as e:
        print("TEACHER ERROR:", traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/grade")
def grade_exercise(data: GradeRequest, authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)

        prompt = f"""You are grading a language exercise for the Tilts app.

Question: {data.question}
Student's answer: {data.user_answer}
Correct answer: {data.correct_answer}
Context: {data.explanation}

Grade the student's answer. Accept near-correct answers (minor spelling, punctuation differences).
Return only raw JSON, no markdown:
{{
  "correct": true or false,
  "score": 0 to 100,
  "feedback": "brief encouraging feedback in {'Hungarian' if data.native_lang == 'hu' else 'Latvian'}",
  "correct_answer": "the correct answer",
  "explanation": "grammar explanation in {'Hungarian' if data.native_lang == 'hu' else 'Latvian'}"
}}"""

        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        result = parse_json(response.content[0].text)
        return result
    except Exception as e:
        print("GRADE ERROR:", traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/conversation")
def conversation(data: ConversationRequest, authorization: str = Header(None)):
    try:
        token = get_token(authorization)
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        unit_context = ""
        if data.unit_id:
            unit = supabase.table("units").select("*").eq("id", data.unit_id).execute()
            if unit.data:
                u = unit.data[0]
                unit_context = f"This conversation is part of Unit {u['unit_number']}: '{u['title_en']}'. Stay within this topic and vocabulary level."

        if data.native_lang == "hu":
            system = f"""You are a friendly Latvian conversation partner on the Tilts app.
The user is a Hungarian native speaker learning Latvian.
Topic: {data.topic}
{unit_context}
- Respond naturally in Latvian
- Keep sentences appropriate for the level
- After your Latvian response add a line break then write "💡 " followed by Hungarian translation
- If the user makes a grammar mistake gently correct it with "✏️ " prefix
- Be encouraging and natural"""
        else:
            system = f"""You are a friendly Hungarian conversation partner on the Tilts app.
The user is a Latvian native speaker learning Hungarian.
Topic: {data.topic}
{unit_context}
- Respond naturally in Hungarian
- Keep sentences appropriate for the level
- After your Hungarian response add a line break then write "💡 " followed by Latvian translation
- If the user makes a grammar mistake gently correct it with "✏️ " prefix
- Be encouraging and natural"""

        messages = [{"role": m.role, "content": m.content} for m in data.messages]

        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1000,
            system=system,
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

        prompt = f"""Generate 10 multiple choice questions for a {data.level} level test on the Tilts app.
Testing a {lang_desc}. {instruction}.
Cover vocabulary and grammar from {data.level} level.
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

        questions = parse_json(response.content[0].text)
        return {"questions": questions, "level": data.level}
    except Exception as e:
        print("LEVEL TEST ERROR:", traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))