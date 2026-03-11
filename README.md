# RecipeMart

Telegram bot that turns an Instagram Reel URL into a structured recipe: it downloads the reel, extracts text from audio (speech-to-text) and on-screen text (OCR) in parallel, merges with the caption, then uses OpenAI to produce **ingredients in grams/ml** and step-by-step instructions.

## Features

- **Standardized ingredients** – All quantities in metric: grams (g) for solids, milliliters (ml) for liquids. Converts from cups, tbsp, “pieces”, etc. automatically.
- **Fast pipeline** – Speech-to-text and OCR run in parallel after download to reduce wait time.
- **Clean output** – Bold section headers and bullet lists in Telegram.

## Flow

1. Send an Instagram Reel URL to the bot (e.g. `https://www.instagram.com/reel/...`).
2. Bot replies "Processing your reel…", then runs: download → (Whisper STT ∥ OCR) → merge → GPT recipe extraction.
3. Bot sends back the recipe (ingredients in g/ml, steps). Temp files are deleted after each run.

## Requirements

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/) (for audio extraction / optional trim)
- [Tesseract](https://github.com/tesseract-ocr/tesseract) (OCR)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (installed via pip)

## Setup

1. Clone or copy this repo, then create a virtualenv and install dependencies:

   ```bash
   cd RecipeMart
   python3 -m venv .venv
   source .venv/bin/activate   # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and set:

   - `TELEGRAM_BOT_TOKEN` – from [@BotFather](https://t.me/BotFather)
   - `OPENAI_API_KEY` – your OpenAI API key (used for Whisper and GPT)

3. Ensure **FFmpeg** and **Tesseract** are on your PATH (or install them; on macOS: `brew install ffmpeg tesseract`).

## Run the bot

From the project root (RecipeMart):

```bash
python -m bot.main
```

The bot uses long-polling. Send any message that contains an Instagram Reel URL; the bot will reply with "Processing your reel…" and then the extracted recipe (or an error message).

## Project layout

- `config.py` – env vars, `TEMP_DIR`, pipeline limits
- `bot/main.py` – Telegram app and polling
- `bot/handlers.py` – message handler: detect Reel URL, run pipeline, send recipe
- `pipeline/run.py` – orchestration and cleanup
- `pipeline/download.py` – yt-dlp download + caption
- `pipeline/speech_to_text.py` – Whisper API
- `pipeline/ocr.py` – OpenCV + Tesseract
- `pipeline/recipe_ai.py` – OpenAI recipe extraction

## Optional env vars

- `OPENAI_RECIPE_MODEL` – model for recipe extraction (default `gpt-4o-mini`)
- `STT_MAX_DURATION_SECONDS` – cap audio length for Whisper (default 600)
- `OCR_FRAME_INTERVAL_SECONDS` – seconds between sampled frames (default 2)
- `OCR_MAX_FRAMES` – max frames to OCR (default 60)

## Hosting

Run the bot on a VPS or PaaS (e.g. Railway, Render) with Python, FFmpeg, and Tesseract installed. Temp files are deleted after each job, so disk usage stays low.
