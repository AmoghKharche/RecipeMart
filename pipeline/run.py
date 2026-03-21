"""Orchestrate pipeline: try caption-only first; else download → (STT ∥ OCR) → merge → AI recipe; cleanup in finally."""
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Tuple

import config
from pipeline.download import download_reel, fetch_caption_only
from pipeline.ocr import extract_text_from_frames
from pipeline.recipe_ai import extract_recipe
from pipeline.recipe_schema import Recipe
from pipeline.speech_to_text import speech_to_text

MIN_CAPTION_LENGTH = 80  # Try caption-only recipe if caption has at least this many chars

_INSUFFICIENT_MARKERS = (
    "insufficient",
    "cannot extract",
    "does not contain enough",
    "not enough information",
    "no text was extracted",
    "no recipe",
)


def _text_suggests_insufficient(text: str) -> bool:
    lower = text.lower()
    return any(m in lower for m in _INSUFFICIENT_MARKERS)


def is_recipe_insufficient(recipe: Recipe) -> bool:
    """True if the AI response indicates it could not extract a real recipe."""
    if recipe.is_insufficient():
        return True
    if _text_suggests_insufficient(recipe.title):
        return True
    for ing in recipe.ingredients:
        if _text_suggests_insufficient(ing.name):
            return True
    for step in recipe.steps:
        if _text_suggests_insufficient(step):
            return True
    return False


def run_pipeline(reel_url: str) -> Tuple[Recipe, bool]:
    """
    Run pipeline for one Reel URL. Tries caption-only first; if sufficient, returns (recipe, True).
    Otherwise downloads video, runs STT+OCR, returns (recipe, False).
    May raise RecipeExtractionError from extract_recipe.
    """
    base = config.get_temp_base()
    job_id = uuid.uuid4().hex[:12]
    work_dir = base / job_id
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        caption = ""
        try:
            caption = fetch_caption_only(reel_url, work_dir)
        except RuntimeError:
            pass
        if caption and len(caption.strip()) >= MIN_CAPTION_LENGTH:
            combined = (
                "Transcript:\n(none)\n\nOn-screen text:\n(none)\n\nCaption:\n"
                + caption.strip()
            )
            recipe = extract_recipe(combined)
            if not is_recipe_insufficient(recipe):
                return recipe, True
        video_path, caption = download_reel(reel_url, work_dir)
        transcript = ""
        on_screen_text = ""
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_stt = executor.submit(speech_to_text, video_path)
            future_ocr = executor.submit(extract_text_from_frames, video_path)
            transcript = future_stt.result()
            on_screen_text = future_ocr.result()
        combined = (
            f"Transcript:\n{transcript or '(none)'}\n\n"
            f"On-screen text:\n{on_screen_text or '(none)'}\n\n"
            f"Caption:\n{caption or '(none)'}"
        )
        recipe = extract_recipe(combined)
        return recipe, False
    finally:
        if work_dir.exists():
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except OSError:
                pass
