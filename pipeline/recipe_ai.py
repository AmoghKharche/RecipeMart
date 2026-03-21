"""Extract structured recipe and estimate macros using OpenAI Chat Completions."""
import json

from openai import OpenAI

import config
from pipeline.recipe_schema import Ingredient, MacroEstimate, Recipe

STRUCTURED_SYSTEM_PROMPT = """You are a recipe extractor. Given text from a recipe video (transcript, on-screen text, and/or caption), output a single JSON object only (no markdown).

JSON schema:
{
  "title": string, dish name or "Recipe",
  "servings": number or null — how many people/servings the recipe as written serves; null only if truly unknown,
  "ingredients": [
    {
      "name": string, ingredient name without quantity,
      "amount": number or null — omit or null for "to taste" items,
      "unit": "g" | "ml" | "count" | null — use g for solids, ml for liquids, count for whole items (eggs, cloves),
      "note": string or null — optional extra
    }
  ],
  "steps": [ string, ... ] — ordered cooking steps
}

RULES:
1. Standardize quantities to metric: solids in g, liquids in ml. Convert cups, tbsp, tsp using standard conversions (1 cup flour ≈ 120g, 1 cup liquid ≈ 240ml, 1 tbsp ≈ 15ml or 15g for butter, 1 tsp ≈ 5ml).
2. For whole items prefer count with unit "count" or approximate grams with unit "g".
3. If the content does not contain enough information for a recipe, use title explaining that, empty ingredients and steps arrays.
4. Respond with valid JSON only."""


MACRO_SYSTEM_PROMPT = """You estimate nutrition from a list of ingredients with amounts. Output a single JSON object only.

Schema:
{
  "total": { "calories": number, "protein_g": number, "carbs_g": number, "fat_g": number },
  "per_serving": { "calories": number, "protein_g": number, "carbs_g": number, "fat_g": number }
}

Use reasonable nutrition estimates from typical foods. All macro values in grams for protein/carbs/fat. Calories are kcal.
The ingredient list describes the FULL batch for the given number of servings. per_serving must equal total divided by that serving count.
Round to one decimal place. Respond with valid JSON only."""


class RecipeExtractionError(Exception):
    """Failed to extract or parse a recipe; message is safe to show users."""

    def __init__(self, message: str) -> None:
        self.user_message = message
        super().__init__(message)


def _parse_recipe_json(content: str) -> Recipe:
    data = json.loads(content)
    return Recipe.model_validate(data)


def extract_recipe(combined_text: str) -> Recipe:
    """
    Send combined transcript + OCR + caption to OpenAI; return validated Recipe.
    """
    if not config.OPENAI_API_KEY:
        raise RecipeExtractionError("OpenAI API key not configured; cannot extract recipe.")

    if not (combined_text or "").strip():
        raise RecipeExtractionError(
            "No text was extracted from the video (no speech, on-screen text, or caption). "
            "Cannot extract a recipe."
        )

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    last_err: Exception | None = None
    for _ in range(2):
        try:
            response = client.chat.completions.create(
                model=config.OPENAI_RECIPE_MODEL,
                messages=[
                    {"role": "system", "content": STRUCTURED_SYSTEM_PROMPT},
                    {"role": "user", "content": combined_text},
                ],
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
            choice = response.choices[0] if response.choices else None
            raw = (choice.message.content or "").strip() if choice and choice.message else ""
            if not raw:
                raise RecipeExtractionError("Could not generate recipe from the video content.")
            return _parse_recipe_json(raw)
        except (json.JSONDecodeError, ValueError) as e:
            last_err = e
            continue
    raise RecipeExtractionError(
        "Could not parse recipe from the model. Try again or use a different reel."
        + (f" ({last_err})" if last_err else "")
    )


def _ingredients_to_macro_prompt(ingredients: list[Ingredient], num_servings: float) -> str:
    lines = [f"This recipe is for {num_servings:g} servings (total batch).", "", "Ingredients:"]
    for ing in ingredients:
        parts = [ing.name]
        if ing.amount is not None and ing.unit:
            parts.append(f"{ing.amount:g} {ing.unit}")
        if ing.note:
            parts.append(f"({ing.note})")
        lines.append("- " + " ".join(parts))
    return "\n".join(lines)


def estimate_macros(ingredients: list[Ingredient], num_servings: float) -> MacroEstimate:
    """
    Estimate total and per-serving macros for the given ingredient list (already scaled for the batch).
    num_servings is the number of servings the batch represents (for per-serving division).
    """
    if not config.OPENAI_API_KEY:
        raise RecipeExtractionError("OpenAI API key not configured; cannot estimate macros.")

    if not ingredients:
        raise RecipeExtractionError("No ingredients to analyze.")

    servings = num_servings if num_servings and num_servings > 0 else 1.0
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    user_content = _ingredients_to_macro_prompt(ingredients, servings)
    model = config.OPENAI_MACROS_MODEL or config.OPENAI_RECIPE_MODEL

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": MACRO_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        max_tokens=500,
        response_format={"type": "json_object"},
    )
    choice = response.choices[0] if response.choices else None
    raw = (choice.message.content or "").strip() if choice and choice.message else ""
    if not raw:
        raise RecipeExtractionError("Could not estimate macros.")
    try:
        data = json.loads(raw)
        return MacroEstimate.model_validate(data)
    except (json.JSONDecodeError, ValueError) as e:
        raise RecipeExtractionError(f"Could not parse macro estimate: {e}") from e
