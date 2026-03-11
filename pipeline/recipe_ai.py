"""Extract structured recipe from combined text using OpenAI Chat Completions."""
from openai import OpenAI

import config

SYSTEM_PROMPT = """You are a recipe extractor. Given text from a recipe video (transcript, on-screen text, and/or caption), output a clear recipe.

RULES:
1. Standardize ALL ingredient quantities to metric:
   - Solids / weight: use grams (g). Examples: "120g all-purpose flour", "50g butter", "1 medium onion (≈150g)".
   - Liquids: use milliliters (ml). Examples: "60ml olive oil", "240ml milk".
   - Convert from cups, tbsp, tsp, "pinch", "pieces" using standard conversions: 1 cup flour ≈ 120g, 1 cup liquid ≈ 240ml, 1 tbsp ≈ 15ml, 1 tsp ≈ 5ml, 1 tbsp butter ≈ 15g. For whole items (e.g. "1 onion") give approximate grams in parentheses if helpful (e.g. "1 onion (≈150g)").
2. Use this exact structure:

**Dish name** (if evident, otherwise "Recipe")

**Ingredients**
• quantity and ingredient (always in g or ml)
• ...

**Steps**
1. First step.
2. Second step.
...

Use **bold** only for section titles (Dish name, Ingredients, Steps). Use bullet points (•) for ingredients and numbers for steps. Be concise. If the video does not contain enough information to form a recipe, say so briefly."""


def extract_recipe(combined_text: str) -> str:
    """
    Send combined transcript + OCR + caption to OpenAI and return formatted recipe.
    """
    if not config.OPENAI_API_KEY:
        return "OpenAI API key not configured; cannot extract recipe."

    if not (combined_text or "").strip():
        return "No text was extracted from the video (no speech, on-screen text, or caption). Cannot extract a recipe."

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=config.OPENAI_RECIPE_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": combined_text},
        ],
        max_tokens=1500,
    )
    choice = response.choices[0] if response.choices else None
    if not choice or not choice.message or not choice.message.content:
        return "Could not generate recipe from the video content."
    return choice.message.content.strip()
