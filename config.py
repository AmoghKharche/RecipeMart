"""Configuration: env vars, paths, constants."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Secrets
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# OpenAI model for recipe extraction (gpt-4o-mini is fast and cheap)
OPENAI_RECIPE_MODEL = os.getenv("OPENAI_RECIPE_MODEL", "gpt-4o-mini")

# Temp directory for downloads (per-job subdirs created inside)
_base_temp = os.getenv("TMPDIR", "/tmp")
TEMP_DIR = Path(_base_temp) / "recipemart"

# Optional: project-local tmp (e.g. RecipeMart/tmp)
PROJECT_ROOT = Path(__file__).resolve().parent
LOCAL_TMP = PROJECT_ROOT / "tmp"

# Use LOCAL_TMP if it exists or we're in dev; else system TEMP_DIR
def get_temp_base() -> Path:
    """Base directory for job temp dirs. Prefer local tmp/ for dev."""
    if LOCAL_TMP.exists() or PROJECT_ROOT.exists():
        LOCAL_TMP.mkdir(parents=True, exist_ok=True)
        return LOCAL_TMP
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    return TEMP_DIR

# Pipeline limits (optional)
STT_MAX_DURATION_SECONDS = int(os.getenv("STT_MAX_DURATION_SECONDS", "600"))  # 10 min cap
OCR_FRAME_INTERVAL_SECONDS = float(os.getenv("OCR_FRAME_INTERVAL_SECONDS", "2.0"))
OCR_MAX_FRAMES = int(os.getenv("OCR_MAX_FRAMES", "60"))  # e.g. 2 min at 1 frame/2s
