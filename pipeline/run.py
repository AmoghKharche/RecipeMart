"""Orchestrate pipeline: download → (STT ∥ OCR) → merge → AI recipe; cleanup in finally."""
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import config
from pipeline.download import download_reel
from pipeline.ocr import extract_text_from_frames
from pipeline.recipe_ai import extract_recipe
from pipeline.speech_to_text import speech_to_text


def run_pipeline(reel_url: str) -> str:
    """
    Run full pipeline for one Reel URL. STT and OCR run in parallel after download.
    Creates a unique temp dir and deletes it in a finally block. Returns recipe text or raises.
    """
    base = config.get_temp_base()
    job_id = uuid.uuid4().hex[:12]
    work_dir = base / job_id
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
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
        return recipe
    finally:
        if work_dir.exists():
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except OSError:
                pass
