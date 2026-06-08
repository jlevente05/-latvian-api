from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import Response
from pydantic import BaseModel
from app.database import supabase
from anthropic import Anthropic
import os
import json
import httpx

router = APIRouter()
claude = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def generate_and_cache_vocabulary(level: str, category: str):
    prompt = f"""Generate exactly 30 Latvian-Hungarian word pairs for level {level}, category: {category}.
Return only a JSON array, nothing else, in this exact format:
[
  {{
    "latvian": "word in latvian",
    "hungarian": "word in hungarian",
    "level": "{level}",
    "category": "{category}",
    "grammar_notes": "brief grammar note in hungarian"
  }}
]
Make sure all words are accurate, natural, and appropriate for {level} level learners."""

    response = claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    words = json.loads(response.content[0].text)
    supabase.table("vocabulary").insert(words).execute()
    return words


@router.get("/tts")
async def text_to_speech(text: str, lang: str):
    url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={text}&tl={lang}&client=gtx"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
    return Response(content=response.content, media_type="audio/mpeg")


@router.get("/")
def get_vocabulary(level: str = None, category: str = None, authorization: str = Header(None)):
    try:
        query = supabase.table("vocabulary").select("*")
        if level:
            query = query.eq("level", level)
        if category:
            query = query.eq("category", category)
        response = query.execute()

        if len(response.data) < 10 and level and category:
            new_words = generate_and_cache_vocabulary(level, category)
            return new_words

        return response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/due")
def get_due_words(authorization: str = Header(None)):
    try:
        token = authorization.replace("Bearer ", "")
        user = supabase.auth.get_user(token)
        user_id = user.user.id

        response = supabase.table("progress")\
            .select("*, vocabulary(*)")\
            .eq("user_id", user_id)\
            .lte("next_review", "now()")\
            .execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/categories")
def get_categories():
    try:
        response = supabase.table("vocabulary").select("level, category").execute()
        seen = set()
        result = []
        for row in response.data:
            key = f"{row['level']}_{row['category']}"
            if key not in seen:
                seen.add(key)
                result.append({"level": row["level"], "category": row["category"]})
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class ExampleRequest(BaseModel):
    vocab_id: str
    latvian: str
    hungarian: str

@router.post("/example")
async def get_example_sentence(data: ExampleRequest):
    try:
        existing = supabase.table("vocabulary")\
            .select("example_lv, example_hu")\
            .eq("id", data.vocab_id)\
            .execute()

        if existing.data and existing.data[0]["example_lv"]:
            return {
                "example_lv": existing.data[0]["example_lv"],
                "example_hu": existing.data[0]["example_hu"]
            }

        prompt = f"""Create one simple example sentence in Latvian using the word "{data.latvian}" (meaning: "{data.hungarian}").
Return only a JSON object, nothing else:
{{
  "example_lv": "the sentence in Latvian",
  "example_hu": "the sentence in Hungarian"
}}
Keep it short and natural, appropriate for A1-A2 level."""

        response = claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        result = json.loads(response.content[0].text)

        supabase.table("vocabulary").update({
            "example_lv": result["example_lv"],
            "example_hu": result["example_hu"]
        }).eq("id", data.vocab_id).execute()

        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))