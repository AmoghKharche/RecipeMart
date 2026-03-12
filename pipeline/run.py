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
from pipeline.speech_to_text import speech_to_text

MIN_CAPTION_LENGTH = 80  # Try caption-only recipe if caption has at least this many chars


def _is_insufficient_recipe(recipe: str) -> bool:
    """True if the AI response indicates it could not extract a real recipe."""
    if not recipe or len(recipe.strip()) < 50:
        return True
    lower = recipe.lower()
    markers = (
        "insufficient",
        "cannot extract",
        "does not contain enough",
        "not enough information",
        "no text was extracted",
        "no recipe",
    )
    return any(m in lower for m in markers)


def run_pipeline(reel_url: str) -> Tuple[str, bool]:
    """
    Run pipeline for one Reel URL. Tries caption-only first; if sufficient, returns (recipe, True).
    Otherwise downloads video, runs STT+OCR, returns (recipe, False). Caller can show different Telegram messages.
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
            if not _is_insufficient_recipe(recipe):
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
