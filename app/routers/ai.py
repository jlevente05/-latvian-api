from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from app.database import supabase
from anthropic import Anthropic
import os
import json
import traceback

router = APIRouter()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

class ExerciseRequest(BaseModel):
    level: str
    category: str = None
    weak_spots: list[str] = []

class ConversationMessage(BaseModel):
    role: str
    content: str

class ConversationRequest(BaseModel):
    messages: list[ConversationMessage]
    topic: str = "general"

@router.post("/exercise")
def generate_exercise(data: ExerciseRequest, authorization: str = Header(None)):
    try:
        token = authorization.replace("Bearer ", "")
        user = supabase.auth.get_user(token)

        weak_spots_text = ""
        if data.weak_spots:
            weak_spots_text = f"The student struggles with: {', '.join(data.weak_spots)}. Focus on these."

        prompt = f"""You are a Latvian language teacher for a Hungarian native speaker at {data.level} level.
Generate one exercise in this exact JSON format:
{{
  "type": "fill_in_the_blank" or "translate" or "multiple_choice",
  "instruction_hu": "instruction in Hungarian",
  "question": "the exercise question",
  "answer": "the correct answer",
  "explanation_hu": "brief grammar explanation in Hungarian",
  "options": ["option1", "option2", "option3", "option4"] (only for multiple_choice, otherwise empty list)
}}
{weak_spots_text}
Category: {data.category or "general vocabulary"}
Return only the JSON, nothing else."""

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        exercise = json.loads(response.content[0].text)
        return exercise
    except Exception as e:
        print("EXERCISE ERROR:", traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/conversation")
def conversation(data: ConversationRequest, authorization: str = Header(None)):
    try:
        token = authorization.replace("Bearer ", "")
        user = supabase.auth.get_user(token)

        system_prompt = f"""You are a friendly Latvian conversation partner. 
The user is a Hungarian native speaker learning Latvian.
Topic: {data.topic}
- Respond naturally in Latvian
- Keep sentences simple and clear
- After your Latvian response, add a line break then write "💡 " followed by a brief Hungarian translation of what you said
- If the user makes a grammar mistake, gently correct it at the end with "✏️ " prefix"""

        messages = [{"role": m.role, "content": m.content} for m in data.messages]

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=system_prompt,
            messages=messages
        )

        return {"response": response.content[0].text}
    except Exception as e:
        print("CONVERSATION ERROR:", traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))