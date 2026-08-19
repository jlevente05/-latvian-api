from fastapi import APIRouter, HTTPException, Header
from app.database import supabase
from anthropic import Anthropic
import os
import json
import traceback

router = APIRouter()
claude = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def parse_json(text: str):
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


@router.post("/generate-unit/{unit_id}")
async def generate_unit_content(unit_id: str, authorization: str = Header(None)):
    try:
        unit = supabase.table("units").select("*").eq("id", unit_id).execute()
        if not unit.data:
            raise HTTPException(status_code=404, detail="Unit not found")
        u = unit.data[0]

        level = u["level"]
        title = u["title_en"]
        grammar_focus = u["grammar_focus"]
        description = u["description"]
        unit_number = u["unit_number"]

        print(f"Generating content for Unit {unit_number}: {title}")

        # Generate dialogue
        dialogue_prompt = f"""You are writing content for Tilts, a Latvian-Hungarian language learning app.

Unit {unit_number} at {level} level: "{title}"
Topic: {description}
Grammar focus: {grammar_focus}

The two recurring characters are:
- Jānis (Latvian, from Riga)
- Márton (Hungarian, from Budapest)

Generate a realistic dialogue between Jānis and Márton about: {description}
The dialogue should naturally introduce the grammar: {grammar_focus}
Length: 8-10 exchanges appropriate for {level} level.

Return only raw JSON, no markdown:
{{
  "lines": [
    {{
      "speaker": "Jānis",
      "text_lv": "Latvian text here",
      "text_hu": "Hungarian translation here"
    }},
    {{
      "speaker": "Márton",
      "text_lv": "Latvian text here",
      "text_hu": "Hungarian translation here"
    }}
  ]
}}"""

        dialogue_response = claude.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2000,
            messages=[{"role": "user", "content": dialogue_prompt}]
        )
        dialogue_data = parse_json(dialogue_response.content[0].text)

        existing_dialogue = supabase.table("dialogues").select("id").eq("unit_id", unit_id).execute()
        if existing_dialogue.data:
            supabase.table("dialogues").update({"lines": dialogue_data["lines"]}).eq("unit_id", unit_id).execute()
        else:
            supabase.table("dialogues").insert({"unit_id": unit_id, "lines": dialogue_data["lines"]}).execute()

        print(f"✓ Dialogue generated")

        # Generate vocabulary
        vocab_prompt = f"""Generate 15 vocabulary words for Tilts language learning app.
Unit {unit_number} at {level} level: "{title}"
Words should come naturally from this dialogue topic: {description}
Grammar focus: {grammar_focus}

Return only raw JSON array, no markdown:
[
  {{
    "latvian": "word in latvian",
    "hungarian": "hungarian translation",
    "level": "{level}",
    "category": "{title.lower().replace(' ', '_')}",
    "grammar_notes": "brief grammar note in Hungarian about this word"
  }}
]"""

        vocab_response = claude.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2000,
            messages=[{"role": "user", "content": vocab_prompt}]
        )
        vocab_data = parse_json(vocab_response.content[0].text)

        existing_vocab = supabase.table("vocabulary").select("id").eq("unit_id", unit_id).execute()
        if not existing_vocab.data:
            for word in vocab_data:
                word["unit_id"] = unit_id
            supabase.table("vocabulary").insert(vocab_data).execute()

        print(f"✓ Vocabulary generated")

        # Generate grammar points
        grammar_prompt = f"""Generate grammar explanations for Tilts language learning app.
Unit {unit_number} at {level} level: "{title}"
Grammar to cover: {grammar_focus}

Generate 1-2 grammar points. Each explanation should be clear, use examples from everyday life, and be anchored to the unit topic: {description}

Return only raw JSON array, no markdown:
[
  {{
    "title": "Grammar point name",
    "explanation_hu": "Clear explanation in Hungarian for someone learning Latvian. Include the rule, why it exists, and common mistakes.",
    "explanation_lv": "Clear explanation in Latvian for someone learning Hungarian. Include the rule, why it exists, and common mistakes.",
    "examples": [
      {{
        "lv": "Latvian example sentence",
        "hu": "Hungarian translation",
        "note": "Brief note about what this example illustrates"
      }},
      {{
        "lv": "Second Latvian example",
        "hu": "Hungarian translation",
        "note": "Brief note"
      }}
    ],
    "order_index": 1
  }}
]"""

        grammar_response = claude.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=3000,
            messages=[{"role": "user", "content": grammar_prompt}]
        )
        grammar_data = parse_json(grammar_response.content[0].text)

        existing_grammar = supabase.table("grammar_points").select("id").eq("unit_id", unit_id).execute()
        if not existing_grammar.data:
            for gp in grammar_data:
                gp["unit_id"] = unit_id
            supabase.table("grammar_points").insert(grammar_data).execute()

        print(f"✓ Grammar points generated")

        # Generate reading text
        reading_prompt = f"""Generate a reading text for Tilts language learning app.
Unit {unit_number} at {level} level: "{title}"
Topic: {description}
Grammar focus: {grammar_focus}

Write a short reading passage in Latvian that:
- Uses the unit's vocabulary and grammar naturally
- Is appropriate length for {level} (A1: 80-100 words, A2: 120-150 words, B1: 200-250 words, B2: 300-350 words)
- Continues the story of Jānis and Márton in some way
- Is engaging and culturally relevant to Latvia or Hungary

Return only raw JSON, no markdown:
{{
  "title": "Title of the reading in Latvian",
  "text_lv": "Full reading text in Latvian",
  "text_hu": "Full Hungarian translation of the reading",
  "vocabulary_highlights": [
    {{
      "word": "key word from text",
      "translation": "translation",
      "note": "grammar or usage note"
    }}
  ],
  "questions": [
    {{
      "question_lv": "Comprehension question in Latvian",
      "question_hu": "Same question in Hungarian",
      "answer_lv": "Answer in Latvian",
      "answer_hu": "Answer in Hungarian"
    }}
  ]
}}"""

        reading_response = claude.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2000,
            messages=[{"role": "user", "content": reading_prompt}]
        )
        reading_data = parse_json(reading_response.content[0].text)

        existing_reading = supabase.table("reading_texts").select("id").eq("unit_id", unit_id).execute()
        if existing_reading.data:
            supabase.table("reading_texts").update(reading_data).eq("unit_id", unit_id).execute()
        else:
            reading_data["unit_id"] = unit_id
            supabase.table("reading_texts").insert(reading_data).execute()

        print(f"✓ Reading text generated")

        # Generate exercises
        exercises_prompt = f"""Generate exercises for Tilts language learning app.
Unit {unit_number} at {level} level: "{title}"
Topic: {description}
Grammar focus: {grammar_focus}

Generate 6 exercises mixing these types: fill_in_the_blank, translation, word_order, listening, grammar_transform, dialogue_completion.
Each exercise should test the unit's grammar and vocabulary.

Return only raw JSON array, no markdown:
[
  {{
    "type": "fill_in_the_blank",
    "order_index": 1,
    "content": {{
      "instruction_hu": "instruction in Hungarian",
      "instruction_lv": "instruction in Latvian",
      "sentence_lv": "Latvian sentence with ___ for blank",
      "sentence_hu": "Hungarian translation"
    }},
    "answer": {{"lv": "correct word", "hu": "hungarian translation"}},
    "explanation_hu": "Why this is correct in Hungarian",
    "explanation_lv": "Why this is correct in Latvian"
  }},
  {{
    "type": "translation",
    "order_index": 2,
    "content": {{
      "instruction_hu": "Fordítsd le magyarra:",
      "instruction_lv": "Tulkojiet ungāru valodā:",
      "sentence_lv": "Latvian sentence to translate"
    }},
    "answer": {{"hu": "correct Hungarian translation"}},
    "explanation_hu": "Grammar note in Hungarian",
    "explanation_lv": "Grammar note in Latvian"
  }},
  {{
    "type": "multiple_choice",
    "order_index": 3,
    "content": {{
      "instruction_hu": "Válaszd ki a helyes választ:",
      "instruction_lv": "Izvēlieties pareizo atbildi:",
      "question": "Question about the grammar or vocabulary",
      "options": ["option1", "option2", "option3", "option4"]
    }},
    "answer": {{"correct": "option1"}},
    "explanation_hu": "Why this is correct in Hungarian",
    "explanation_lv": "Why this is correct in Latvian"
  }}
]
Generate all 6 exercises with variety in types."""

        exercises_response = claude.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=3000,
            messages=[{"role": "user", "content": exercises_prompt}]
        )
        exercises_data = parse_json(exercises_response.content[0].text)

        existing_exercises = supabase.table("unit_exercises").select("id").eq("unit_id", unit_id).execute()
        if not existing_exercises.data:
            for ex in exercises_data:
                ex["unit_id"] = unit_id
            supabase.table("unit_exercises").insert(exercises_data).execute()

        print(f"✓ Exercises generated")

        return {
            "success": True,
            "unit_id": unit_id,
            "unit_title": title,
            "generated": {
                "dialogue_lines": len(dialogue_data["lines"]),
                "vocabulary_words": len(vocab_data),
                "grammar_points": len(grammar_data),
                "exercises": len(exercises_data),
            }
        }

    except Exception as e:
        print("GENERATE ERROR:", traceback.format_exc())
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/generate-all-a1")
async def generate_all_a1(authorization: str = Header(None)):
    try:
        a1_units = supabase.table("units").select("id, title_en").eq("level", "A1").order("order_index").execute()
        results = []
        for unit in a1_units.data:
            try:
                print(f"Generating: {unit['title_en']}")
                result = await generate_unit_content(unit["id"], authorization)
                results.append({"unit": unit["title_en"], "success": True})
            except Exception as e:
                results.append({"unit": unit["title_en"], "success": False, "error": str(e)})
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))